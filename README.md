# Keymouse

Keyboard-driven **mouse look**: hold a button and your cursor sweeps
across the screen using a configurable acceleration curve, plus fire/aim
mouse buttons and an enable toggle.

Pure Python + tkinter, no build step.

## Run

The launcher finds a Python with tkinter (installing it if needed) and
starts the app.

| Platform        | Command                                   |
|-----------------|-------------------------------------------|
| Windows         | double-click `keymouse.bat`               |
| macOS / Linux   | `./keymouse.sh`                           |
| PowerShell (any)| `pwsh ./keymouse.ps1`                     |

Or run directly. On Linux/macOS the app automatically builds an isolated
`.venv` on first run (no sudo, no system pip needed) and installs `pynput`
into it, then launches:

```sh
python keymouse.py
```

## Platform support

* **Windows** – native backend (`SendInput` + a low-level keyboard hook),
  no dependencies. Low latency, good for games.
* **Linux / macOS** – cross-platform backend via [`pynput`](https://pypi.org/project/pynput/).
  The app installs it automatically on first launch.

Key bindings are stored as stable, cross-platform ids in `keymouse.cfg`,
so the same folder works on every OS. The enable key (default `NumLock`)
is a *toggle*; the engine only looks while enabled.

> **"Swallow bound keys" is OFF by default.** Swallowing uses an OS-level
> keyboard grab so pressed bound keys never reach the active window (no
> "double input"). It's disabled by default because a stuck grab can lock
> the desktop on Linux/macOS. Turn it on in the UI only if you need it and
> are OK with that trade-off.

> On some platforms injecting input into elevated games may be blocked.
> On Windows you may need to run keymouse as administrator in that case.

## Keys

Defaults (all rebindable in the UI):

| Action      | Key        |
|-------------|------------|
| Look up     | Up arrow   |
| Look down   | Down arrow |
| Look left   | Left arrow |
| Look right  | Right arrow|
| Fire (LMB)  | Numpad 0   |
| Aim (RMB)   | Numpad .   |
| Enable      | NumLock    |
| Quit        | Ctrl+Alt+Q |

## Layout

```
keymouse/
  keys.py     cross-platform key-id registry
  config.py   settings + validation + I/O
  curve.py    acceleration curve math
  engine.py   mouse-look engine thread
  input.py    input backend facade (win32 / pynput)
  gui.py      tkinter setup UI
keymouse.py   entry point
```
