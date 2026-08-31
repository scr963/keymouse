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
| Windows         | double-click `run_keymouse.bat`           |
| macOS / Linux   | `./run_keymouse.sh`                       |
| PowerShell (any)| `pwsh ./run_keymouse.ps1` (or `run.ps1`)  |

Or run directly (needs `pynput` on Linux/macOS):

```sh
python -m pip install -r requirements.txt
python keymouse.py
```

## Platform support

* **Windows** – native backend (`SendInput` + a low-level keyboard hook),
  no dependencies. Low latency, good for games.
* **Linux / macOS** – cross-platform backend via [`pynput`](https://pypi.org/project/pynput/).
  Installed automatically by the launchers from `requirements.txt`.

Key bindings are stored as stable, cross-platform ids in `keymouse.cfg`,
so the same folder works on every OS. The enable key (default `NumLock`)
is a *toggle*; the engine only looks while enabled.

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
