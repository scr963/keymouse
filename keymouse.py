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


def _venv_python() -> str:
    if os.name == "nt":
        return os.path.join(_VENV_DIR, "Scripts", "python.exe")
    return os.path.join(_VENV_DIR, "bin", "python")


def _run(cmd, timeout=240):
    """Run a subprocess non-interactively; never let it hang or prompt."""
    env = dict(os.environ)
    env["PIP_NO_INPUT"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    try:
        subprocess.run(cmd, timeout=timeout, env=env,
                       stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False
    return True


def _py_has(module: str) -> bool:
    return _run([sys.executable, "-c", "import %s" % module])


def _has_pynput() -> bool:
    try:
        import pynput  # noqa: F401
        return True
    except Exception:
        return False


def _ensure_backend() -> bool:
    """Make a usable input backend exist, automatically and idempotently.

    Windows: the native backend is always there - nothing to do.
    Elsewhere: we build a self-contained project venv (which carries its own
    pip via ensurepip, no global install, no sudo, no PEP 668 issues), make
    sure pynput + its deps are in it, then re-exec under the venv's Python.
    Works even when the system Python has no pip module at all.
    """
    if _has_pynput():
        return True
    if sys.platform == "win32":
        return False  # native backend should already be present

    venv_py = _venv_python()

    # 1. Create the venv if it is not there yet.
    if not os.path.isfile(venv_py):
        print("[i] First run: creating an isolated Python environment (.venv)...")
        if not _run([sys.executable, "-m", "venv", _VENV_DIR]):
            print("[!] Could not create the virtual environment.")
        if not os.path.isfile(venv_py):
            print("[!] venv not available; install Python's venv module, "
                  "e.g. on Debian/Ubuntu:  sudo apt install python3-venv")
            return False

    # 2. Make sure the venv has pip (the venv's ensurepip may be disabled).
    _run([venv_py, "-m", "ensurepip", "--default-pip", "--upgrade"])

    # 3. Install pynput (and its platform deps) into the venv.
    if not _py_has_venv(venv_py, "pynput"):
        print("[i] Installing pynput into .venv (one-time)...")
        if not _run([venv_py, "-m", "pip", "install", "pynput"]):
            print("[!] pynput install failed. Check your internet connection "
                  "and try again.")
            return False

    # 4. Re-launch under the venv's Python so it sees the installed deps.
    if os.path.abspath(sys.executable) != os.path.abspath(venv_py):
        try:
            os.execv(venv_py, [venv_py, os.path.abspath(__file__)]
                     + list(sys.argv[1:]))
        except Exception as exc:
            print("[!] Could not relaunch under .venv: %r" % (exc,))
            return False

    return _has_pynput()


def _py_has_venv(venv_py: str, module: str) -> bool:
    return _run([venv_py, "-c", "import %s" % module])


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
