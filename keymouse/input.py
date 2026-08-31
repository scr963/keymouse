"""Cross-platform input layer.

Exposes a small, uniform API used by the engine and GUI. The concrete
backend is chosen automatically from the platform:

  - ``win32`` : native SendInput + WH_KEYBOARD_LL hooks on Windows.
                Low-level, low-latency, can swallow bound keys at the OS
                level so games see clean input. No extra dependencies.
  - ``pynput``: cross-platform backend for Linux / macOS. Uses pynput's
                listeners (which also support key suppression) and a
                controller to move the mouse and click. Requires the
                ``pynput`` package (see requirements.txt).

Everything above is isolated behind this module so the engine, GUI and
entry point never touch either backend directly.
"""

from __future__ import annotations

import threading
import sys

from . import keys as _K

# ----------------------------------------------------------------------
# Mouse event flags (kept stable so the engine speaks one language).
# The win32 backend uses them verbatim; the pynput backend maps them.
# ----------------------------------------------------------------------
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040


class InputError(Exception):
    """Raised when mouse events fail to inject."""


_platform = sys.platform
_win = (_platform == "win32")

# Backends are registered here; the active one is built at import time.
_active = None


# ======================================================================
# Win32 backend (native, no dependencies)
# ======================================================================
class _Win32Backend:
    name = "win32"

    def __init__(self):
        import time
        self._time = time

        import ctypes
        from ctypes import wintypes as wt
        self.ctypes = ctypes
        self.wt = wt

        try:
            self._user32 = ctypes.WinDLL("user32", use_last_error=True)
            self._winmm = ctypes.WinDLL("winmm")
            self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        except OSError:
            self._user32 = None
            self._winmm = None
            self._kernel32 = None

        # Typed INPUT structures.
        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", wt.LONG),
                ("dy", wt.LONG),
                ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD),
                ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.c_size_t),
            ]

        class _INPUT_U(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT)]

        class INPUT(ctypes.Structure):
            _anonymous_ = ("u",)
            _fields_ = [("type", wt.DWORD), ("u", _INPUT_U)]

        self.INPUT = INPUT
        self._INPUT_MOUSE = 0

        # Hook plumbing.
        self.WH_KEYBOARD_LL = 13
        self.HC_ACTION = 0
        self.WM_QUIT = 0x0012
        self.WM_KEYDOWN = 0x0100
        self.WM_KEYUP = 0x0101
        self.WM_SYSKEYDOWN = 0x0104
        self.WM_SYSKEYUP = 0x0105
        self._KEYPROC = ctypes.CFUNCTYPE(
            ctypes.c_ssize_t, ctypes.c_int, wt.WPARAM, wt.LPARAM)
        self._MOUSE_VKS = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06}

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("vkCode", wt.DWORD),
                ("scanCode", wt.DWORD),
                ("flags", wt.DWORD),
                ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.c_size_t),
            ]

        self.KBDLLHOOKSTRUCT = KBDLLHOOKSTRUCT

    # --------------------------------------------------------------
    def available(self):
        return self._user32 is not None

    def _mouse_input(self, flags, dx=0, dy=0):
        inp = self.INPUT()
        inp.type = self._INPUT_MOUSE
        inp.mi.dx = dx
        inp.mi.dy = dy
        inp.mi.dwFlags = flags
        return inp

    def batch_mouse(self, items):
        if self._user32 is None:
            raise InputError("user32 not available")
        if not items:
            return
        inputs = [self._mouse_input(f, dx, dy)
                  for f, dx, dy in items]
        arr = (self.INPUT * len(inputs))(*inputs)
        inserted = self._user32.SendInput(
            len(inputs), self.ctypes.byref(arr),
            self.ctypes.sizeof(self.INPUT))
        if inserted == 0:
            code = self.ctypes.get_last_error()
            raise InputError("SendInput blocked (last error=%d). "
                             "Try running as administrator." % code)

    def key_is_down(self, key_id):
        if self._user32 is None:
            return False
        vk = _K.vk_of(key_id)
        if vk is None:
            return False
        return bool(self._user32.GetAsyncKeyState(vk) & 0x8000)

    def held_keys(self):
        """Set of canonically-named key ids currently held (for rebinding)."""
        if self._user32 is None:
            return set()
        out = set()
        for vk, e in _K._BY_VK.items():
            if self._user32.GetAsyncKeyState(vk) & 0x8000:
                out.add(e[0])
        return out

    def set_timer_resolution(self, enable, period_ms=1):
        if self._winmm is None:
            return
        if enable:
            self._winmm.timeBeginPeriod(period_ms)
        else:
            self._winmm.timeEndPeriod(period_ms)

    def warm_input_queue(self):
        if self._user32 is None:
            return
        msg = self.wt.MSG()
        for _ in range(8):
            self._user32.PeekMessageW(self.ctypes.byref(msg), None, 0, 0, 0)
            self._time.sleep(0.005)

    def time_sleep(self, seconds):
        self._time.sleep(seconds)

    # --------------------------------------------------------------
    # Keyboard blocking via a low-level hook.
    # --------------------------------------------------------------
    def make_blocker(self, cfg, state):
        return _Win32Blocker(self, cfg, state)

    def _current_thread_id(self):
        return int(self._kernel32.GetCurrentThreadId())

    def _run_message_loop(self):
        msg = self.wt.MSG()
        while True:
            r = self._user32.GetMessageW(self.ctypes.byref(msg), None, 0, 0)
            if r <= 0:
                break
            self._user32.TranslateMessage(self.ctypes.byref(msg))
            self._user32.DispatchMessageW(self.ctypes.byref(msg))


class _Win32Blocker:
    """Owns a WH_KEYBOARD_LL hook on a dedicated message-loop thread."""

    def __init__(self, backend, cfg, state):
        self._b = backend
        self.cfg = cfg
        self.state = state
        self._cb = None
        self._hook = None
        self._tid = None
        self._thread = None
        self._down = {}

    def start(self):
        b = self._b
        if b._user32 is None or not b.available() or self._thread is not None:
            return
        b._user32.SetWindowsHookExW.argtypes = [
            b.ctypes.c_int, b._KEYPROC, b.wt.HINSTANCE, b.wt.DWORD]
        b._user32.SetWindowsHookExW.restype = b.ctypes.c_void_p
        b._user32.UnhookWindowsHookEx.argtypes = [b.ctypes.c_void_p]
        b._user32.UnhookWindowsHookEx.restype = b.wt.BOOL
        b._user32.CallNextHookEx.argtypes = [
            b.ctypes.c_void_p, b.ctypes.c_int, b.wt.WPARAM, b.wt.LPARAM]
        b._user32.CallNextHookEx.restype = b.ctypes.c_ssize_t
        b._user32.GetMessageW.argtypes = [
            b.ctypes.POINTER(b.wt.MSG), b.wt.HWND, b.wt.UINT, b.wt.UINT]
        b._user32.GetMessageW.restype = b.wt.BOOL
        b._user32.TranslateMessage.argtypes = [b.ctypes.POINTER(b.wt.MSG)]
        b._user32.DispatchMessageW.argtypes = [b.ctypes.POINTER(b.wt.MSG)]
        b._user32.PostThreadMessageW.argtypes = [
            b.wt.DWORD, b.wt.UINT, b.wt.WPARAM, b.wt.LPARAM]
        b._user32.PostThreadMessageW.restype = b.wt.BOOL
        b._kernel32.GetCurrentThreadId.restype = b.wt.DWORD

        self._cb = b._KEYPROC(self._proc)
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="keymouse-kbdhook")
        self._thread.start()

    def stop(self):
        th = self._thread
        if th is None:
            return
        self._thread = None
        if self._tid is not None:
            self._b._user32.PostThreadMessageW(self._tid, self._b.WM_QUIT, 0, 0)
        th.join(timeout=1)

    def is_down(self, key_id):
        b = self._b
        vk = _K.vk_of(key_id)
        if vk is None:
            return False
        if vk in b._MOUSE_VKS:
            return bool(b._user32.GetAsyncKeyState(vk) & 0x8000)
        return bool(self._down.get(vk, False))

    def _bound_vks(self):
        b = self._b
        out = set()
        for action, kid in self.cfg.keys.items():
            if kid and action != "toggle":
                vk = _K.vk_of(kid)
                if vk is not None and vk not in b._MOUSE_VKS:
                    out.add(vk)
        return out

    def _run(self):
        b = self._b
        self._tid = b._current_thread_id()
        self._hook = b._user32.SetWindowsHookExW(
            b.WH_KEYBOARD_LL, self._cb, None, 0)
        if not self._hook:
            self._tid = None
            return
        try:
            b._run_message_loop()
        finally:
            b._user32.UnhookWindowsHookEx(self._hook)
            self._hook = None

    def _proc(self, nCode, wParam, lParam):
        b = self._b
        if nCode == b.HC_ACTION:
            data = b.ctypes.cast(
                lParam, b.ctypes.POINTER(b.KBDLLHOOKSTRUCT)).contents
            vk = data.vkCode
            is_up = wParam in (b.WM_KEYUP, b.WM_SYSKEYUP)
            self._down[vk] = not is_up
            if self.state.enabled and vk in self._bound_vks():
                return 1
        return b._user32.CallNextHookEx(self._hook, nCode, wParam, lParam)


# ======================================================================
# pynput backend (Linux / macOS)
# ======================================================================
class _PynputBackend:
    name = "pynput"

    def __init__(self):
        self._listener = None
        self._mouse = None
        self._keyboard = None
        self._state = {}
        self._lock = threading.RLock()

    # -- helpers --------------------------------------------------------
    def _import(self):
        from pynput import keyboard, mouse
        return keyboard, mouse

    def available(self):
        try:
            key_mouse = self._import()
            return True
        except ImportError:
            return False

    def _make_controllers(self):
        keyboard, mouse = self._import()
        if self._keyboard is None:
            self._keyboard = keyboard.Controller()
            self._mouse = mouse.Controller()
        return keyboard, mouse

    # -- key-id <-> pynput key ------------------------------------------
    def _pynput_to_id(self, k):
        """Convert a pynput key/value into a canonical key id or None."""
        keyboard, mouse = self._import()
        if isinstance(k, keyboard.Key):
            kid = _K.normalize(getattr(k, "name", None))
            return kid
        if isinstance(k, keyboard.KeyCode):
            ch = getattr(k, "char", None)
            if ch is not None:
                kid = _K.normalize(ch)
                if kid:
                    return kid
            # Fall back to the Windows-style VK if available.
            vk = getattr(k, "vk", None)
            return _K.normalize(vk)
        if isinstance(k, mouse.Button):
            bmap = {"left": "lmb", "right": "rmb", "middle": "mmb",
                    "x1": "x1", "x2": "x2"}
            return bmap.get(getattr(k, "name", None))
        return None

    def _id_to_pynput(self, key_id):
        """Convert a canonical key id to a pynput Key/KeyCode for sending."""
        keyboard, _ = self._import()
        kid = _K.normalize(key_id)
        if not kid:
            return None
        name, _, _, char, keyname, is_mouse = _K._BY_ID[kid]
        if is_mouse:
            bmap = {"lmb": "left", "rmb": "right", "mmb": "middle",
                    "x1": "x1", "x2": "x2"}
            return bmap.get(kid)
        if keyname is not None:
            return getattr(keyboard.Key, keyname)
        if char is not None:
            return keyboard.KeyCode.from_char(char)
        return None

    # -- public API ------------------------------------------------------
    def batch_mouse(self, items):
        """Apply a list of (flags, dx, dy) mouse events."""
        keyboard, mouse = self._make_controllers()
        for flags, dx, dy in items:
            if flags & MOUSEEVENTF_MOVE:
                mouse.move(dx, dy)
            elif flags & MOUSEEVENTF_LEFTDOWN:
                mouse.press(mouse.Button.left)
            elif flags & MOUSEEVENTF_LEFTUP:
                mouse.release(mouse.Button.left)
            elif flags & MOUSEEVENTF_RIGHTDOWN:
                mouse.press(mouse.Button.right)
            elif flags & MOUSEEVENTF_RIGHTUP:
                mouse.release(mouse.Button.right)
            elif flags & MOUSEEVENTF_MIDDLEDOWN:
                mouse.press(mouse.Button.middle)
            elif flags & MOUSEEVENTF_MIDDLEUP:
                mouse.release(mouse.Button.middle)

    def key_is_down(self, key_id):
        kid = _K.normalize(key_id)
        with self._lock:
            return bool(self._state.get(kid, False))

    def held_keys(self):
        """Set of canonically-named key ids currently held (for rebinding)."""
        with self._lock:
            return {kid for kid, down in self._state.items() if down}

    def set_timer_resolution(self, enable, period_ms=1):
        pass  # not applicable outside Windows

    def warm_input_queue(self):
        pass

    def time_sleep(self, seconds):
        import time
        time.sleep(seconds)

    # -- listener + blocking --------------------------------------------
    def make_blocker(self, cfg, state):
        return _PynputBlocker(self, cfg, state)


class _PynputBlocker:
    """Tracks key state and suppresses bound keys via pynput listeners."""

    def __init__(self, backend, cfg, state):
        self._b = backend
        self.cfg = cfg
        self.state = state
        self._klistener = None
        self._mlistener = None

    def start(self):
        b = self._b
        keyboard, mouse = b._import()
        b._make_controllers()

        def sup(k):
            self._update(k, True)

        def rev(k):
            self._update(k, False)

        self._klistener = keyboard.Listener(on_press=sup, on_release=rev)
        self._mlistener = mouse.Listener(on_click=self._on_click)
        self._klistener.daemon = True
        self._mlistener.daemon = True
        self._klistener.start()
        self._mlistener.start()

    def stop(self):
        for l in (self._klistener, self._mlistener):
            if l is not None and l.running:
                try:
                    l.stop()
                except Exception:
                    pass
        self._klistener = None
        self._mlistener = None

    def _bound_kids(self):
        return {kid for action, kid in self.cfg.keys.items()
                if kid and action != "toggle" and not _K.is_mouse(kid)}

    def _on_click(self, x, y, button, pressed):
        b = self._b
        kid = b._pynput_to_id(button)
        if kid is None:
            return
        with b._lock:
            b._state[kid] = bool(pressed)

    def _update(self, k, down):
        b = self._b
        kid = b._pynput_to_id(k)
        if kid is None:
            return
        with b._lock:
            b._state[kid] = down
        # Swallow bound keys while enabled (normal key must not reach the app).
        if down and self.state.enabled and kid in self._bound_kids():
            try:
                self._klistener.suppress_event()
            except Exception:
                pass

    def is_down(self, key_id):
        kid = _K.normalize(key_id)
        with self._b._lock:
            return bool(self._b._state.get(kid, False))


# ======================================================================
# Facade: choose the best backend for this platform.
# ======================================================================
def _build_backend():
    if _win:
        b = _Win32Backend()
        if b.available():
            return b
    # Non-Windows, or Windows without user32: fall back to pynput.
    b = _PynputBackend()
    return b


_active = _build_backend()


def available() -> bool:
    """True if a usable input backend is ready."""
    return _active.available()


def backend_name() -> str:
    return _active.name


def win_available() -> bool:
    """Deprecated alias kept for callers; True when any backend is ready."""
    return _active.available()


# --- Facade function wrappers ---------------------------------------
def key_is_down(key_id) -> bool:
    return _active.key_is_down(key_id)


def held_keys() -> set:
    return _active.held_keys()


def batch_mouse(items) -> None:
    _active.batch_mouse(items)


def set_timer_resolution(enable: bool, period_ms: int = 1) -> None:
    _active.set_timer_resolution(enable, period_ms)


def warm_input_queue() -> None:
    _active.warm_input_queue()


def time_sleep(seconds: float) -> None:
    _active.time_sleep(seconds)


# --- Blocking / key-state tracking ----------------------------------
_shared_blocker = None


def make_blocker(cfg, state):
    global _shared_blocker
    _shared_blocker = _active.make_blocker(cfg, state)
    return _shared_blocker


def KeyboardBlocker(cfg, state):
    """Build (but do not start) the active backend's key blocker."""
    return make_blocker(cfg, state)


def shutdown_blocker():
    global _shared_blocker
    if _shared_blocker is not None:
        _shared_blocker.stop()
        _shared_blocker = None
