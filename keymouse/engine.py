"""The mouse-look engine: samples keys, computes smoothed movement,
and injects mouse events.

The core math is factored into :meth:`MouseEngine.step` which is pure
and unit-testable; the OS glue (polling, SendInput, threading) lives in
:meth:`MouseEngine.run` / :func:`start`.
"""

from __future__ import annotations

import time
import threading

from . import curve, input as win, keys as K


class MouseEngine:
    """Reads bound keys and drives the mouse.

    Lives on its own thread. ``stop`` is a threading.Event; the engine
    exits cleanly and always releases held buttons and resets the timer
    resolution when it finishes.
    """

    def __init__(self, cfg, state, stop: threading.Event):
        self.cfg = cfg
        self.state = state
        self.stop = stop

        # Integration state (position accumulators + smoothing).
        self._px = 0.0
        self._py = 0.0
        self._rpx = 0.0
        self._rpy = 0.0
        self._pvx = 0.0
        self._pvy = 0.0
        self._laste_x = 0.0
        self._laste_y = 0.0
        self._hold_x = 0.0
        self._hold_y = 0.0
        self._last_dir_x = 0
        self._last_dir_y = 0

        # Edge detection for toggles / direction memory.
        self._was_toggle = False
        self._prev = {a: False for a in K.ACTIONS}

        self._lbtn = False
        self._rbtn = False

    # ------------------------------------------------------------------
    # Core per-tick computation (pure given the current key states).
    # ------------------------------------------------------------------
    def step(self, held: dict[str, bool], dt: float) -> tuple[int, int] | None:
        """Advance one tick. Returns (dx, dy) to move or None.

        ``held`` is a dict of action->bool current pressed state.
        ``dt`` is the elapsed seconds since the last tick.
        """
        # Remember the most recently pressed look direction while held,
        # so pressing the opposite key keeps going the same way.
        for a, d in (("look_right", 1), ("look_left", -1)):
            if held[a] and not self._prev[a]:
                self._last_dir_x = d
        for a, d in (("look_down", 1), ("look_up", -1)):
            if held[a] and not self._prev[a]:
                self._last_dir_y = d
        self._prev["look_right"] = held["look_right"]
        self._prev["look_left"] = held["look_left"]
        self._prev["look_down"] = held["look_down"]
        self._prev["look_up"] = held["look_up"]

        if held["look_right"] and held["look_left"]:
            dir_x = self._last_dir_x
        elif held["look_right"]:
            dir_x = 1
        elif held["look_left"]:
            dir_x = -1
        else:
            dir_x = 0

        if held["look_down"] and held["look_up"]:
            dir_y = self._last_dir_y
        elif held["look_down"]:
            dir_y = 1
        elif held["look_up"]:
            dir_y = -1
        else:
            dir_y = 0

        any_dir = dir_x != 0 or dir_y != 0
        if any_dir:
            self._hold_x += dt
            self._hold_y += dt
        else:
            self._hold_x = 0.0
            self._hold_y = 0.0

        c = self.cfg
        tx = curve.target_speed(dir_x, self._hold_x, c.max_speed_x,
                                c.ramp_time, c.curve_type, c.accel_power,
                                c.min_frac)
        ty = curve.target_speed(dir_y, self._hold_y, c.max_speed_y,
                                c.ramp_time, c.curve_type, c.accel_power,
                                c.min_frac)

        self._rpx += tx * dt
        self._rpy += ty * dt
        self._px, self._pvx = curve.smooth_damp(
            self._px, self._rpx, self._pvx, c.smooth_tau, c.max_speed_x, dt)
        self._py, self._pvy = curve.smooth_damp(
            self._py, self._rpy, self._pvy, c.smooth_tau, c.max_speed_y, dt)

        ix = int(self._px - self._laste_x)
        iy = int(self._py - self._laste_y)
        if ix == 0 and iy == 0:
            return None
        self._laste_x += ix
        self._laste_y += iy
        return (ix, iy)

    # ------------------------------------------------------------------
    # Button handling.
    # ------------------------------------------------------------------
    def _update_buttons(self, held: dict[str, bool]) -> None:
        events: list[tuple[int, int, int]] = []
        if held["fire"] and not self._lbtn:
            events.append((win.MOUSEEVENTF_LEFTDOWN, 0, 0))
            self._lbtn = True
        elif not held["fire"] and self._lbtn:
            events.append((win.MOUSEEVENTF_LEFTUP, 0, 0))
            self._lbtn = False
        if held["aim"] and not self._rbtn:
            events.append((win.MOUSEEVENTF_RIGHTDOWN, 0, 0))
            self._rbtn = True
        elif not held["aim"] and self._rbtn:
            events.append((win.MOUSEEVENTF_RIGHTUP, 0, 0))
            self._rbtn = False
        if events:
            win.batch_mouse(events)

    def _release_buttons(self) -> None:
        events = []
        if self._lbtn:
            events.append((win.MOUSEEVENTF_LEFTUP, 0, 0))
            self._lbtn = False
        if self._rbtn:
            events.append((win.MOUSEEVENTF_RIGHTUP, 0, 0))
            self._rbtn = False
        if events:
            win.batch_mouse(events)

    # ------------------------------------------------------------------
    # Toggle handling.
    # ------------------------------------------------------------------
    def _poll_toggle(self) -> None:
        nk = win.key_is_down(self.cfg.keys["toggle"])
        if nk and not self._was_toggle:
            self.toggle()
        self._was_toggle = nk

    def toggle(self) -> None:
        """Flip enabled state on/off (called by the UI toggle key or the
        GUI Enable/Disable button). Resets look integration and releases
        any held mouse buttons for a clean hand-off."""
        self.state.enabled = not self.state.enabled
        self._reset_look()
        self._release_buttons()
        self._on_status_change()

    def _reset_look(self) -> None:
        self._px = self._py = 0.0
        self._rpx = self._rpy = 0.0
        self._pvx = self._pvy = 0.0
        self._laste_x = self._laste_y = 0.0
        self._hold_x = self._hold_y = 0.0

    # ------------------------------------------------------------------
    # Hook for the GUI to observe state changes without shared globals.
    # ------------------------------------------------------------------
    def _on_status_change(self) -> None:
        if self.state.on_change:
            try:
                self.state.on_change(self.state.enabled)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # The OS loop.
    # ------------------------------------------------------------------
    def run(self) -> None:
        win.set_timer_resolution(True)
        blocker = win.make_blocker(self.cfg, self.state)
        blocker.start()
        self._blocker = blocker
        try:
            win.warm_input_queue()
            self._was_toggle = win.key_is_down(self.cfg.keys["toggle"])
            self._on_status_change()

            last = time.perf_counter()
            while not self.stop.is_set():
                # Quit hotkey: Ctrl+Alt+Q.
                if (win.key_is_down("ctrl") and win.key_is_down("alt")
                        and win.key_is_down("q")):
                    break

                self._poll_toggle()

                now = time.perf_counter()
                dt = now - last
                if dt <= 0.0:
                    dt = 0.0
                if dt > 0.25:
                    dt = 0.25  # clamp huge gaps (sleep/block) to avoid jumps
                last = now

                if self.state.enabled:
                    held = {
                        "look_up": blocker.is_down(self.cfg.keys["look_up"]),
                        "look_down": blocker.is_down(self.cfg.keys["look_down"]),
                        "look_left": blocker.is_down(self.cfg.keys["look_left"]),
                        "look_right": blocker.is_down(self.cfg.keys["look_right"]),
                        "fire": blocker.is_down(self.cfg.keys["fire"]),
                        "aim": blocker.is_down(self.cfg.keys["aim"]),
                        "toggle": win.key_is_down(self.cfg.keys["toggle"]),
                    }

                    moved = self.step(held, dt)
                    if moved is not None:
                        dx, dy = moved
                        try:
                            win.batch_mouse([(win.MOUSEEVENTF_MOVE, dx, dy)])
                            if self.state.warned:
                                self.state.warned = False
                                self._on_status_change()
                        except win.InputError:
                            if not self.state.warned:
                                self.state.warned = True
                                self._on_status_change()

                    self._update_buttons(held)

                _sleep_until(now, self.cfg.poll_interval)
        finally:
            blocker.stop()
            self._release_buttons()
            win.set_timer_resolution(False)


def _sleep_until(now: float, interval: float) -> None:
    """Sleep just enough to keep a steady tick rate without drifting."""
    target = now + interval
    remaining = target - time.perf_counter()
    if remaining > 0:
        time.sleep(remaining)


class RuntimeState:
    """Shared, thread-safe-ish status the engine writes and the GUI reads."""

    def __init__(self, enabled: bool):
        self.enabled = enabled
        self.warned = False
        self.on_change = None  # callable(enabled: bool) or None

    @property
    def status_text(self) -> str:
        text = "[+] ENABLED" if self.enabled else "[-] DISABLED  keyboard normal"
        if self.warned:
            text += "   [!] SendInput blocked - run as admin"
        return text


def start(cfg, state: RuntimeState, stop: threading.Event) -> MouseEngine:
    """Spawn the daemon engine thread and return the engine instance.

    The engine drives its own daemon thread; stop it via ``stop`` (a
    threading.Event) and wait on ``engine.thread`` for shutdown.
    """
    engine = MouseEngine(cfg, state, stop)
    engine.thread = threading.Thread(target=engine.run, daemon=True,
                                     name="keymouse-engine")
    engine.thread.start()
    return engine
