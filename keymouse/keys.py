"""Cross-platform key identity registry.

The app talks to keys through a stable, platform-neutral *key id* (a
string) instead of raw OS codes. Each id maps to:

  - ``name`` : human-readable display label
  - ``vk``   : the Windows virtual-key code (used by the Win32 backend)
  - ``char`` : the single character if it is a printable key
  - ``key``  : the pynput ``Key`` member name if it is a special key
  - ``mouse``: whether it is a mouse button

This lets the same ``keymouse.cfg`` bindings work on Windows (Win32
backend) and on Linux/macOS (pynput backend) with no format change.
"""

from __future__ import annotations

# A key entry: (id, name, vk, char, key_name, is_mouse)
#
#   id       - canonical, platform-neutral identifier stored in the config
#   name     - human readable label shown in the GUI / banner
#   vk       - Windows virtual-key code (see keys.py helpers) or None
#   char     - single printable character or None
#   key_name - pynput keyboard.Key member name or None
#   is_mouse - True for mouse buttons
_KEYS: list[tuple] = [
    # --- Letter / digit / symbol keys (by character) -------------------
    ("a", "A",        0x41, "a", None, False),
    ("b", "B",        0x42, "b", None, False),
    ("c", "C",        0x43, "c", None, False),
    ("d", "D",        0x44, "d", None, False),
    ("e", "E",        0x45, "e", None, False),
    ("f", "F",        0x46, "f", None, False),
    ("g", "G",        0x47, "g", None, False),
    ("h", "H",        0x48, "h", None, False),
    ("i", "I",        0x49, "i", None, False),
    ("j", "J",        0x4A, "j", None, False),
    ("k", "K",        0x4B, "k", None, False),
    ("l", "L",        0x4C, "l", None, False),
    ("m", "M",        0x4D, "m", None, False),
    ("n", "N",        0x4E, "n", None, False),
    ("o", "O",        0x4F, "o", None, False),
    ("p", "P",        0x50, "p", None, False),
    ("q", "Q",        0x51, "q", None, False),
    ("r", "R",        0x52, "r", None, False),
    ("s", "S",        0x53, "s", None, False),
    ("t", "T",        0x54, "t", None, False),
    ("u", "U",        0x55, "u", None, False),
    ("v", "V",        0x56, "v", None, False),
    ("w", "W",        0x57, "w", None, False),
    ("x", "X",        0x58, "x", None, False),
    ("y", "Y",        0x59, "y", None, False),
    ("z", "Z",        0x5A, "z", None, False),
    ("0", "0",        0x30, "0", None, False),
    ("1", "1",        0x31, "1", None, False),
    ("2", "2",        0x32, "2", None, False),
    ("3", "3",        0x33, "3", None, False),
    ("4", "4",        0x34, "4", None, False),
    ("5", "5",        0x35, "5", None, False),
    ("6", "6",        0x36, "6", None, False),
    ("7", "7",        0x37, "7", None, False),
    ("8", "8",        0x38, "8", None, False),
    ("9", "9",        0x39, "9", None, False),
    ("space", "Space",        0x20, " ", "space", False),
    ("tab", "Tab",            0x09, "\t", "tab", False),
    ("enter", "Enter",        0x0D, "\r", "enter", False),
    ("backspace", "Backspace",0x08, "\b", "backspace", False),
    ("esc", "Esc",            0x1B, None, "esc", False),
    ("minus", "-",            0xBD, "-", None, False),
    ("equal", "=",            0xBB, "=", None, False),
    ("bracketleft", "[",      0xDB, "[", None, False),
    ("bracketright", "]",     0xDD, "]", None, False),
    ("backslash", "\\",       0xDC, "\\", None, False),
    ("semicolon", ";",        0xBA, ";", None, False),
    ("apostrophe", "'",       0xDE, "'", None, False),
    ("grave", "`",            0xC0, "`", None, False),
    ("comma", ",",            0xBC, ",", None, False),
    ("period", ".",           0xBE, ".", None, False),
    ("slash", "/",            0xBF, "/", None, False),

    # --- Function keys ------------------------------------------------
    ("f1", "F1",   0x70, None, "f1", False),
    ("f2", "F2",   0x71, None, "f2", False),
    ("f3", "F3",   0x72, None, "f3", False),
    ("f4", "F4",   0x73, None, "f4", False),
    ("f5", "F5",   0x74, None, "f5", False),
    ("f6", "F6",   0x75, None, "f6", False),
    ("f7", "F7",   0x76, None, "f7", False),
    ("f8", "F8",   0x77, None, "f8", False),
    ("f9", "F9",   0x78, None, "f9", False),
    ("f10", "F10", 0x79, None, "f10", False),
    ("f11", "F11", 0x7A, None, "f11", False),
    ("f12", "F12", 0x7B, None, "f12", False),
    ("f13", "F13", 0x7C, None, "f13", False),
    ("f14", "F14", 0x7D, None, "f14", False),
    ("f15", "F15", 0x7E, None, "f15", False),
    ("f16", "F16", 0x7F, None, "f16", False),
    ("f17", "F17", 0x80, None, "f17", False),
    ("f18", "F18", 0x81, None, "f18", False),
    ("f19", "F19", 0x82, None, "f19", False),
    ("f20", "F20", 0x83, None, "f20", False),
    ("f21", "F21", 0x84, None, "f21", False),
    ("f22", "F22", 0x85, None, "f22", False),
    ("f23", "F23", 0x86, None, "f23", False),
    ("f24", "F24", 0x87, None, "f24", False),

    # --- Navigation / editing ------------------------------------------
    ("up", "Up",       0x26, None, "up", False),
    ("down", "Down",   0x28, None, "down", False),
    ("left", "Left",   0x25, None, "left", False),
    ("right", "Right", 0x27, None, "right", False),
    ("pageup", "PgUp",   0x21, None, "page_up", False),
    ("pagedown", "PgDn", 0x22, None, "page_down", False),
    ("home", "Home",   0x24, None, "home", False),
    ("end", "End",     0x23, None, "end", False),
    ("insert", "Ins",  0x2D, None, "insert", False),
    ("delete", "Del",  0x2E, None, "delete", False),
    ("pause", "Pause", 0x13, None, "pause", False),
    ("printscreen", "PrtSc", 0x2C, None, "print_screen", False),

    # --- Numpad (explicit) --------------------------------------------
    ("kp_0", "Numpad0",  0x60, None, None, False),
    ("kp_1", "Numpad1",  0x61, None, None, False),
    ("kp_2", "Numpad2",  0x62, None, None, False),
    ("kp_3", "Numpad3",  0x63, None, None, False),
    ("kp_4", "Numpad4",  0x64, None, None, False),
    ("kp_5", "Numpad5",  0x65, None, None, False),
    ("kp_6", "Numpad6",  0x66, None, None, False),
    ("kp_7", "Numpad7",  0x67, None, None, False),
    ("kp_8", "Numpad8",  0x68, None, None, False),
    ("kp_9", "Numpad9",  0x69, None, None, False),
    ("kp_multiply", "Num*", 0x6A, None, None, False),
    ("kp_add", "Num+",      0x6B, None, None, False),
    ("kp_separator", "Num,",0x6C, None, None, False),
    ("kp_subtract", "Num-", 0x6D, None, None, False),
    ("kp_decimal", "Num.", 0x6E, None, None, False),
    ("kp_divide", "Num/",   0x6F, None, None, False),

    # --- Lock / modifier keys ------------------------------------------
    ("numlock", "NumLock",     0x90, None, "num_lock", False),
    ("scrolllock", "ScrollLock",0x91, None, "scroll_lock", False),
    ("capslock", "CapsLock",   0x14, None, "caps_lock", False),
    ("shift", "Shift",    0x10, None, "shift", False),
    ("ctrl", "Ctrl",      0x11, None, "ctrl", False),
    ("alt", "Alt",        0x12, None, "alt", False),
    ("lshift", "LShift",  0xA0, None, "shift", False),
    ("rshift", "RShift",  0xA1, None, "shift_r", False),
    ("lctrl", "LCtrl",    0xA2, None, "ctrl_l", False),
    ("rctrl", "RCtrl",    0xA3, None, "ctrl_r", False),
    ("lalt", "LAlt",      0xA4, None, "alt_l", False),
    ("ralt", "RAlt",      0xA5, None, "alt_r", False),
    ("menu", "Menu",      0x5D, None, "menu", False),
    ("win", "Win",        0x5B, None, "cmd", False),

    # --- Mouse buttons -------------------------------------------------
    ("lmb", "LMB", 0x01, None, None, True),
    ("rmb", "RMB", 0x02, None, None, True),
    ("mmb", "MMB", 0x04, None, None, True),
    ("x1", "X1",   0x05, None, None, True),
    ("x2", "X2",   0x06, None, None, True),
]

_BY_ID: dict = {e[0]: e for e in _KEYS}
_BY_VK: dict[int, tuple] = {e[2]: e for e in _KEYS if e[2] is not None}
_BY_CHAR: dict[str, tuple] = {e[3]: e for e in _KEYS if e[3] is not None}
_BY_KEYNAME: dict[str, tuple] = {e[4]: e for e in _KEYS if e[4] is not None}

# Canonical aliases so identifiers stay small and stable.
ALIASES = {
    "kp_enter": "enter",
    "num_enter": "enter",
    "num_lock": "numlock",
    "scroll_lock": "scrolllock",
    "caps_lock": "capslock",
    "return": "enter",
    "pgup": "pageup",
    "pgdn": "pagedown",
    "esc": "esc",
    "ctrl": "ctrl",
}

# Reserved / ignored key ids that are never valid rebind targets
# (modifiers, lock keys, OS keys).
RESERVED_IDS = {
    "shift", "ctrl", "alt", "lshift", "rshift", "lctrl", "rctrl",
    "lalt", "ralt", "capslock", "win", "menu", "pause", "printscreen",
}

ACTIONS = ("look_left", "look_right", "look_up", "look_down",
           "fire", "aim", "toggle")

DEFAULT_BINDINGS = {
    "look_up": "up",
    "look_down": "down",
    "look_left": "left",
    "look_right": "right",
    "fire": "kp_0",
    "aim": "kp_decimal",
    "toggle": "numlock",
}


def normalize(key: str | int | None) -> str | None:
    """Return a canonical key id for a raw id / VK / None."""
    if key is None:
        return None
    if isinstance(key, str):
        return ALIASES.get(key, key)
    if isinstance(key, bool):
        return None
    if isinstance(key, int):
        if key <= 0:
            return None
        e = _BY_VK.get(key)
        return e[0] if e else None
    return None


def is_valid(key: str | int | None) -> bool:
    return normalize(key) in _BY_ID


def name_of(key: str | int | None) -> str:
    key = normalize(key)
    if not key or key not in _BY_ID:
        return "None"
    return _BY_ID[key][1]


def vk_of(key: str | int) -> int | None:
    key = normalize(key)
    if not key or key not in _BY_ID:
        return None
    return _BY_ID[key][2]


def is_mouse(key: str | int) -> bool:
    key = normalize(key)
    return bool(key and key in _BY_ID and _BY_ID[key][5])


def is_reserved(key: str | int) -> bool:
    return normalize(key) in RESERVED_IDS


ALL_IDS = tuple(_BY_ID.keys())

# Backwards-compat: VK codes that used to be sentinel for "unbound".
UNBOUND = None
