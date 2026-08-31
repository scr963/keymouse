"""Keymouse entry point.

Thin launcher: wires up config, the engine thread and the GUI. All real
logic lives in the ``keymouse`` package modules.
"""

import sys
import threading
import tkinter as tk

from keymouse import engine, input as win, keys as K
from keymouse.config import Config, CONFIG_FILE, load_or_default
from keymouse.gui import SetupGui


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

    if not win.available():
        print("[!] No usable input backend - keymouse needs either the "
              "Windows API (win32) or the 'pynput' package "
              "(pip install pynput).")
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
