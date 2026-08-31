"""Graphical setup UI for Keymouse.

Built on tkinter (no third-party deps) for portability. This module only
renders widgets and edits a Config; validation/persistence live in
config.py and the math in curve.py.

The look is the classic tactile Windows-9x style: grey raised/sunken
panels, MS Sans Serif, and beveled buttons.
"""

from __future__ import annotations

import os
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox

from . import curve as curvemod
from . import input as win
from . import keys as K
from .config import TUNINGS, Config, CONFIG_FILE, save_config, load_config
from .engine import RuntimeState

# Key ids that are never usable as a rebind target (reserved).
# Includes modifiers/lock/OS keys. Mouse buttons (LMB/RMB/etc) and
# normal keys are all valid bind targets.
_IGNORED_IDS = K.RESERVED_IDS

# Classic Windows-9x palette and type.
BG = "#c0c0c0"
FACE = "MS Sans Serif"
TROUGH = "#808080"
ACCENT = "#000080"      # dark blue for section titles

BIND_LABELS = [
    ("look_left", "Look Left"),
    ("look_right", "Look Right"),
    ("look_up", "Look Up"),
    ("look_down", "Look Down"),
    ("fire", "Fire (LMB)"),
    ("aim", "Aim (RMB)"),
    ("toggle", "Enable"),
]

ACTION_HINT = {
    "look_left": "Hold to look left. Click the key to change it.",
    "look_right": "Hold to look right. Click the key to change it.",
    "look_up": "Hold to look up (pitch). Click the key to change it.",
    "look_down": "Hold to look down (pitch). Click the key to change it.",
    "fire": "Sends a left mouse click. Hold to fire.",
    "aim": "Sends a right mouse click. Hold to aim.",
    "toggle": "Cycles mouse-look on and off. Default: NumLock.",
}


class _Tip:
    """Classic yellow hover tooltip."""

    def __init__(self, widget, text, delay=450):
        self.widget = widget
        self.text = text
        self._after = None
        self._win = None
        widget.bind("<Enter>", lambda e: self._schedule())
        widget.bind("<Leave>", lambda e: self._cancel())
        widget.bind("<ButtonPress>", lambda e: self._cancel())

    def _schedule(self):
        self._cancel()
        try:
            self._after = self.widget.after(450, self._show)
        except tk.TclError:
            pass

    def _cancel(self):
        if self._after is not None:
            try:
                self.widget.after_cancel(self._after)
            except Exception:
                pass
            self._after = None
        if self._win is not None:
            try:
                self._win.destroy()
            except Exception:
                pass
            self._win = None

    def _show(self):
        self._after = None
        try:
            self._win = tk.Toplevel(self.widget)
            self._win.withdraw()
            self._win.overrideredirect(True)
            self._win.configure(bg="black")
            lbl = tk.Label(self._win, text=self.text, justify="left",
                           bg="#ffffe1", fg="black",
                           font=(FACE, 8), padx=6, pady=3)
            lbl.pack()
            self._win.deiconify()
            x = self.widget.winfo_pointerx() + 14
            y = self.widget.winfo_pointery() + 18
            self._win.wm_geometry("+%d+%d" % (x, y))
        except tk.TclError:
            pass


class SetupGui:
    def __init__(self, cfg: Config, state: RuntimeState, root: tk.Tk,
                 on_quit, on_toggle=None):
        self.cfg = cfg
        self.state = state
        self.root = root
        self.on_quit = on_quit
        self.on_toggle = on_toggle or (lambda: None)
        self._capture = None
        self._closed = False

        root.title("Keymouse")
        root.configure(bg=BG)
        root.resizable(False, False)

        state.on_change = self._on_state_changed

        self._build()
        self._refresh_curve()
        self._paint_status()
        self._poll_state()
        root.protocol("WM_DELETE_WINDOW", self.quit)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build(self):
        outer = tk.Frame(self.root, bg=BG, bd=3, relief="raised")
        outer.pack(fill="both", expand=True, padx=6, pady=6)

        body = tk.Frame(outer, bg=BG, bd=1, relief="sunken")
        body.pack(fill="both", expand=True, padx=2, pady=2)

        # Left column: the tuning sliders.
        left = tk.Frame(body, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(4, 2), pady=4)
        self._build_knobs(left)

        # Right column: Curve on top, Keybinds below it.
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="y", padx=(2, 4), pady=4)
        self._build_curve(right)
        self._build_binds(right)

        # Bottom bar: status on the left, action buttons on the right.
        bottom = tk.Frame(outer, bg=BG)
        bottom.pack(fill="x", padx=6, pady=(2, 6))
        self._build_bottom(bottom)

    def _build_knobs(self, parent):
        group = tk.LabelFrame(parent, text="Mouse Look", bg=BG, fg="black",
                              font=(FACE, 8, "bold"), padx=6, pady=3)
        group.pack(fill="both", expand=True)

        c = self.cfg
        self.scales = {}
        grid = tk.Frame(group, bg=BG)
        grid.pack(fill="x", padx=4, pady=2)
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        def value_for(name):
            value = getattr(c, name)
            if name == "min_frac":
                return value * 100.0
            if name == "poll_interval":
                return value * 1000.0
            return value

        rows = [("Sensitivity (px/s)", ("max_speed_x", "max_speed_y")),
                ("Ramp", ("ramp_time", "accel_power")),
                ("Floor / Smoothing", ("min_frac", "smooth_tau")),
                ("Polling", ("poll_interval",))]

        r = 0
        for title, names in rows:
            tk.Label(grid, text=title, bg=BG, fg=ACCENT,
                     font=(FACE, 8, "bold"), anchor="w"
                     ).grid(row=r, column=0, columnspan=2, sticky="ew",
                            padx=4, pady=(4, 0))
            r += 1
            for col, name in enumerate(names):
                spec = TUNINGS[name]
                scale = tk.Scale(grid, from_=spec.minimum, to=spec.maximum,
                                 resolution=spec.step, orient="horizontal",
                                 length=132, showvalue=True, bg=BG, fg="black",
                                 activebackground=BG, highlightthickness=0,
                                 troughcolor=TROUGH, font=(FACE, 8), bd=1,
                                 command=lambda _v, n=name: self._knob_changed(n))
                scale.set(value_for(name))
                self.scales[name] = scale
                scale.grid(row=r, column=col, sticky="ew", padx=4, pady=2)
                _Tip(scale, spec.hint)
            r += 1

    def _build_curve(self, parent):
        group = tk.LabelFrame(parent, text="Ramp", bg=BG, fg="black",
                              font=(FACE, 8, "bold"), padx=5, pady=3)
        group.pack(fill="both", expand=True)

        self.curve_name = tk.Label(group, text="", bg=BG, fg="black",
                                   font=(FACE, 8, "bold"), anchor="w")
        self.curve_name.pack(fill="x", padx=(6, 6), pady=(4, 0))

        self.canvas = tk.Canvas(group, width=170, height=120, bg="white",
                                highlightthickness=0)
        self.canvas.pack(padx=6, pady=(4, 4))
        _Tip(self.canvas, "Preview: look speed vs hold time.\n"
                          "Red = speed curve, blue = min floor.")

        self.curve_var = tk.StringVar(value=self._curve_label())
        menu = tk.OptionMenu(group, self.curve_var,
                             *[label for _, label in curvemod.CURVES],
                             command=self._on_curve_select)
        menu.config(bg=BG, fg="black", activebackground=BG, font=(FACE, 8),
                    relief="raised", bd=1, highlightthickness=0, takefocus=0)
        menu["menu"].config(bg=BG, fg="black", font=(FACE, 8))
        menu.pack(fill="x", padx=6, pady=(2, 6))

    def _build_binds(self, parent):
        group = tk.LabelFrame(parent, text="Keybinds", bg=BG, fg="black",
                              font=(FACE, 8, "bold"), padx=6, pady=4)
        group.pack(fill="both", expand=True)

        self.bind_buttons = {}
        for action, label in BIND_LABELS:
            cell = tk.Frame(group, bg=BG)
            cell.pack(fill="x", padx=6, pady=1)

            name = tk.Label(cell, text=label, bg=BG, fg="black",
                            font=(FACE, 8), width=14, anchor="w")
            name.pack(side="left")
            _Tip(name, ACTION_HINT[action])

            btn = tk.Button(cell, text=self._bind_label(self.cfg.keys[action]),
                            font=(FACE, 8), relief="raised", bg=BG,
                            activebackground=BG, bd=2, width=10,
                            command=lambda a=action: self._start_record(a))
            btn.pack(side="left", padx=(6, 0))
            _Tip(btn, "Click, then press the new key.\n"
                      "It binds when you LIFT the key.\n"
                      "Esc cancels. Backspace unbinds.")
            self.bind_buttons[action] = btn

    def _bind_label(self, key_id):
        return "None" if not key_id else K.name_of(key_id)

    def _build_bottom(self, parent):
        self.status_btn = tk.Button(parent, text="", font=(FACE, 8, "bold"),
                                    relief="raised", bd=2, padx=10, pady=2,
                                    command=self._toggle_enabled)
        self.status_btn.pack(side="left", padx=4, pady=4)

        btns = tk.Frame(parent, bg=BG)
        btns.pack(side="right")
        for text, cmd in (("Defaults", self._set_defaults),
                          ("Load...", self._load),
                          ("Save", self._save),
                          ("Quit", self.quit)):
            tk.Button(btns, text=text, font=(FACE, 8), relief="raised",
                      bg=BG, activebackground=BG, bd=2, padx=10,
                      command=cmd).pack(side="left", padx=4)

    def _toggle_enabled(self):
        self.on_toggle()

    # ------------------------------------------------------------------
    # Knob handlers
    # ------------------------------------------------------------------
    def _knob_changed(self, *_):
        if self._closed:
            return
        try:
            c = self.cfg
            for name, scale in self.scales.items():
                raw = float(scale.get())
                if name == "min_frac":
                    setattr(c, name, raw / 100.0)
                elif name == "poll_interval":
                    setattr(c, name, raw / 1000.0)
                else:
                    setattr(c, name, raw)
            self._refresh_curve()
        except tk.TclError:
            pass

    def _on_curve_select(self, label):
        for key, lbl in curvemod.CURVES:
            if lbl == label:
                self.cfg.curve_type = key
                break
        self._refresh_curve()

    def _curve_label(self):
        return curvemod.CURVE_BY_KEY.get(self.cfg.curve_type,
                                         self.cfg.curve_type)

    def _refresh_curve(self):
        try:
            self.curve_name.config(text="Curve: %s" % self._curve_label())
            canvas = self.canvas
            canvas.delete("all")
            w = canvas.winfo_width() or 170
            h = canvas.winfo_height() or 120
            ox, oy, mx, my = 26, 6, 6, 16
            fw, fh = w - ox - mx, h - oy - my
            canvas.create_rectangle(ox, oy, ox + fw, oy + fh,
                                    outline="#808080")
            for i in range(1, 10):
                xx = ox + fw * i / 10.0
                canvas.create_line(xx, oy, xx, oy + fh, fill="#d0d0d0")
            c = self.cfg
            floor_y = oy + fh - c.min_frac * fh
            canvas.create_line(ox, floor_y, ox + fw, floor_y,
                               fill="#0000ff", dash=(2, 2))
            n = 48
            pts = []
            for i in range(n + 1):
                frac = i / float(n)
                t = frac * c.ramp_time
                speed = curvemod.target_speed(
                    1, t, 1.0, c.ramp_time, c.curve_type, c.accel_power,
                    c.min_frac)
                x = ox + fw * frac
                y = oy + fh - speed * fh
                pts.append((x, y))
            for i in range(1, len(pts)):
                canvas.create_line(pts[i - 1], pts[i], fill="#ff0000", width=2)
            canvas.create_text(ox, oy + fh + 11, text="%0.2fs" % c.ramp_time,
                               font=(FACE, 7), fill="#404040", anchor="w")
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Rebind (clickable key button -> poll-based key capture).
    #
    # Keys are captured by polling the physical keyboard with
    # GetAsyncKeyState - the exact same mechanism the engine uses to read
    # look keys. Tk's own key-event delivery is unreliable for this
    # (focus/grab routing), so we never depend on it.
    # ------------------------------------------------------------------
    def _start_record(self, action):
        self._close_capture()

        top = tk.Toplevel(self.root)
        top.title("Rebind")
        top.configure(bg=BG)
        top.resizable(False, False)
        top.transient(self.root)
        top.protocol("WM_DELETE_WINDOW", lambda: self._cancel_capture(top))

        frame = tk.Frame(top, bg=BG, bd=3, relief="raised")
        frame.pack(fill="both", expand=True, padx=6, pady=6)
        body = tk.Frame(frame, bg=BG, bd=1, relief="sunken")
        body.pack(fill="both", expand=True, padx=2, pady=2)

        tk.Label(body, text="Press an action", anchor="w",
                 bg=BG, fg=ACCENT, font=(FACE, 8, "bold")
                 ).pack(fill="x", padx=8, pady=(6, 0))
        tk.Label(body, text="Press the new key.\nEsc cancels.\nBackspace removes the binding.",
                 bg=BG, fg="black", font=(FACE, 8), justify="left"
                 ).pack(fill="x", padx=8, pady=(2, 6))

        top.update_idletasks()
        top.geometry("%dx%d" % (max(top.winfo_reqwidth(), 240),
                                top.winfo_reqheight()))
        top.focus_force()

        # Capture state for the poll loop.
        self._capture = top
        self._capture_action = action
        # Seed from the live key state: any key already held when the dialog
        # opened (i.e. the mouse click that opened it) is an "opener". That
        # key's very first release is ignored, so lifting it doesn't bind
        # the opener to itself; every other key release binds immediately.
        self._capture_prev = win.held_keys()
        self._capture_opener = set(self._capture_prev)
        self._capture_id = 0
        try:
            top.after(40, self._poll_capture)
        except tk.TclError:
            self._capture = None

    def _poll_capture(self):
        top = self._capture
        if top is None:
            return
        if not top.winfo_exists():
            self._capture = None
            return

        # Escape cancels the rebind outright.
        if "esc" in win.held_keys():
            self._close_capture()
            return

        now_held = win.held_keys()
        # A key was released since the last poll (bind on LIFT, never press).
        released = self._capture_prev - now_held
        captured = None
        for kid in sorted(released):
            if kid in _IGNORED_IDS:
                continue
            if kid == "backspace":
                captured = kid
                break
            if kid in self._capture_opener:
                self._capture_opener.discard(kid)
            else:
                captured = kid
                break
        self._capture_prev = now_held

        if captured is not None:
            self._on_captured(self._capture_action, captured)
            return

        try:
            top.after(20, self._poll_capture)
        except tk.TclError:
            self._capture = None

    def _cancel_capture(self, top):
        if self._capture is top:
            self._capture = None
        try:
            top.destroy()
        except tk.TclError:
            pass

    def _close_capture(self):
        if self._capture is not None:
            self._cancel_capture(self._capture)

    def _on_captured(self, action, key_id):
        # Close the capture window first, then apply.
        self._close_capture()
        # Backspace unbinds the action (removes its key).
        self.cfg.keys[action] = None if key_id == "backspace" else key_id
        self._refresh_binds()

    def _show_bind(self, action):
        self.bind_buttons[action].config(
            text=K.name_of(self.cfg.keys[action]),
            relief="raised", bg=BG, fg="black")

    def _refresh_binds(self):
        for action, btn in getattr(self, "bind_buttons", {}).items():
            btn.config(text=self._bind_label(self.cfg.keys[action]),
                       relief="raised", bg=BG, fg="black")

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _set_defaults(self):
        self._close_capture()
        self.cfg = Config().validate()
        self._push_to_widgets()

    def _push_to_widgets(self):
        c = self.cfg
        try:
            for name, scale in self.scales.items():
                value = getattr(c, name)
                if name == "min_frac":
                    value = value * 100.0
                elif name == "poll_interval":
                    value = value * 1000.0
                scale.set(value)
            self.curve_var.set(self._curve_label())
            self._refresh_binds()
            self._refresh_curve()
        except tk.TclError:
            pass

    def _save(self):
        """Write the current config to CONFIG_FILE. Nothing is ever written
        automatically - only this explicit action touches disk."""
        try:
            save_config(self.cfg, CONFIG_FILE)
            self.root.bell()
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc), parent=self.root)

    def _load(self):
        path = filedialog.askopenfilename(
            parent=self.root, title="Load config",
            initialdir=os.path.dirname(CONFIG_FILE),
            filetypes=[("Config files", "*.cfg"), ("JSON files", "*.json"),
                       ("All files", "*.*")])
        if not path:
            return
        try:
            self.cfg = load_config(path)
        except Exception as exc:
            messagebox.showerror("Load failed", str(exc), parent=self.root)
            return
        self._push_to_widgets()

    # ------------------------------------------------------------------
    # Status / lifecycle
    # ------------------------------------------------------------------
    def _on_state_changed(self, enabled: bool):
        self._paint_status()

    def _paint_status(self):
        if self.state.enabled:
            text = "ENABLED"
            active = "#007a00"
        else:
            text = "DISABLED"
            active = "#7a0000"
        if self.state.warned:
            self.status_btn.config(text="BLOCKED", bg="#cc0000", fg="white")
            return
        self.status_btn.config(text=text, bg=active, fg="white")

    def _poll_state(self):
        if self._closed:
            return
        self._paint_status()
        try:
            self.root.after(200, self._poll_state)
        except tk.TclError:
            pass

    def quit(self):
        if self._closed:
            return
        self._closed = True
        self._close_capture()
        self.state.on_change = None
        try:
            self.root.update_idletasks()
        except Exception:
            pass
        self.on_quit()
        try:
            self.root.destroy()
        except Exception:
            pass
