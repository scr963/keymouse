"""Keymouse entry point.

The app manages its own input backend. On non-Windows systems where
``pynput`` is missing it installs it automatically (once), so the launcher
never has to - and there is no fragile, hang-prone install step before the
app runs.
"""

import os
import subprocess
import sys
import threading
import tkinter as tk

from keymouse import engine, input as win, keys as K
from keymouse.config import Config, CONFIG_FILE, load_or_default
from keymouse.gui import SetupGui


def _ensure_backend() -> bool:
    """Make sure a usable input backend exists.

    On Windows the native backend is always available. Elsewhere the app
    needs ``pynput``; if it is missing, install it automatically (once),
    then re-check.
    """
    if win.available():
        return True
    if sys.platform == "win32":
        return False  # native backend should already be present
    print("[i] pynput is not installed - installing it now (one-time)...")
    cmd = [sys.executable, "-m", "pip", "install",
           "--user", "--break-system-packages", "pynput"]
    try:
        env = dict(os.environ)
        env["PIP_NO_INPUT"] = "1"
        subprocess.run(cmd, timeout=120, env=env)
    except Exception as exc:
        print("[!] Could not auto-install pynput: %r" % (exc,))
        return False
    # Re-select the backend so it sees the freshly-installed pynput.
    try:
        import importlib
        mod = sys.modules["keymouse.input"]
        mod._active = mod._build_backend()
    except Exception:
        pass
    return win.available()


def _banner(cfg: Config):
    line = "=" * 60
    print(line)
    print(" Keymouse")
    print("  Look keys ....... mouse look (joystick curve)")
    print("  Fire key ........ left click (hold fires)")
    print("  Aim key ......... right click (hold aims)")
    print("  Enable key ...... toggles look on/off")
    print("  Quit ............ Ctrl+Alt+Q or close the window")
    print("  All keys are configurable in the Keybinds panel.")
    print(line)
    for action in ("look_up", "look_down", "look_left", "look_right",
                   "fire", "aim", "toggle"):
        print("  %-12s %s" % (action + ":", _name(cfg, action)))
    print(line)


def _name(cfg, action):
    return K.name_of(cfg.keys[action])


def main(argv=None):
    cfg = load_or_default(CONFIG_FILE)

    if not _ensure_backend():
        print("[!] No usable input backend.")
        if sys.platform == "win32":
            print("    This build requires Windows.")
        else:
            print("    Install pynput manually with:")
            print("        python3 -m pip install --user --break-system-packages pynput")
        return 1

    print("[i] input backend: %s" % win.backend_name())

    _banner(cfg)

    state = engine.RuntimeState(enabled=False)
    stop = threading.Event()
    eng = engine.start(cfg, state, stop)

    root = tk.Tk()
    gui = SetupGui(cfg, state, root, on_quit=lambda: stop.set(),
                   on_toggle=eng.toggle)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    except tk.TclError:
        stop.set()
    finally:
        stop.set()
        eng.thread.join(timeout=3)
    return 0


if __name__ == "__main__":
    sys.exit(main())
