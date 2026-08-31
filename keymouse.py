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


_HERE = os.path.dirname(os.path.abspath(__file__))
_VENV_DIR = os.path.join(_HERE, ".venv")


def _venv_python():
    """Path to the venv's Python interpreter."""
    if os.name == "nt":
        return os.path.join(_VENV_DIR, "Scripts", "python.exe")
    return os.path.join(_VENV_DIR, "bin", "python")


def _pynput_present(python=None) -> bool:
    """True if pynput is importable, under `python` (default: this process)."""
    if python is None:
        try:
            import pynput  # noqa: F401
            return True
        except Exception:
            return False
    try:
        r = subprocess.run([python, "-c", "import pynput"],
                           capture_output=True, timeout=30)
        return r.returncode == 0
    except Exception:
        return False


def _ensure_backend() -> bool:
    """Ensure a usable input backend exists — automatically and idempotently.

    On Windows the native backend is always available.
    Everywhere else the app needs ``pynput``. On first run we build an
    isolated project venv (which brings its own pip via ``ensurepip``, so it
    works even when the system Python has no pip and needs no sudo or global
    installs), install pynput + its platform deps into it, then relaunch
    under that Python. Later runs just reuse the venv.
    """
    if _pynput_present():
        return True
    if sys.platform == "win32":
        return False  # native backend should already be present

    venv_py = _venv_python()

    # 1. Create the venv once.
    if not os.path.isfile(venv_py):
        print("[keymouse] First run: creating an isolated environment (.venv)...")
        subprocess.run([sys.executable, "-m", "venv", _VENV_DIR], timeout=240)
    if not os.path.isfile(venv_py):
        print("[keymouse] Could not create .venv. On Debian/Ubuntu, run once:")
        print("              sudo apt install python3-venv")
        return False

    # 2. Give the venv a working pip (usually bundled; guard for stripped builds).
    subprocess.run([venv_py, "-m", "ensurepip", "--default-pip", "--upgrade"],
                   timeout=240)

    # 3. Install pynput into the venv.
    if not _pynput_present(venv_py):
        print("[keymouse] Installing pynput (one-time)...")
        r = subprocess.run([venv_py, "-m", "pip", "install", "pynput"],
                           timeout=300)
        if r.returncode != 0 or not _pynput_present(venv_py):
            print("[keymouse] pynput install failed. Check your internet "
                  "connection and run again.")
            return False

    # 4. Relaunch under the venv's Python so it can import pynput.
    if os.path.abspath(sys.executable) != os.path.abspath(venv_py):
        os.execv(venv_py, [venv_py, os.path.abspath(__file__)] + sys.argv[1:])

    return True


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
            print("    Run once to enable:  sudo apt install python3-venv")
            print("    then launch again.")
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
