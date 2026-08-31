"""Configuration: a dataclass with validated, coherent defaults + I/O.

The critical fix here is that the field defaults, the tuning ranges, and
the validation bounds all come from ONE source (a per-field spec), so the
GUI scales and the CLI/config can never disagree with each other the way
the old code did.
"""

from __future__ import annotations

import json
import os
import dataclasses
from dataclasses import dataclass, field

from . import keys as K

DEFAULT_POLL_MS = 2.0
DEFAULT_RAMP_S = 0.22
DEFAULT_POWER = 1.4
DEFAULT_MIN_FRAC = 0.10
DEFAULT_SPEED = 3000.0
DEFAULT_SMOOTH_S = 0.015
DEFAULT_CURVE = "power"

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "keymouse.cfg")


@dataclass
class Tuning:
    """A single knob's spec: units, min, max, step, default, tooltip."""
    key: str
    label: str
    unit: str
    minimum: float
    maximum: float
    step: float
    default: float
    hint: str

    def clamp(self, value: float) -> float:
        return max(self.minimum, min(self.maximum, float(value)))


# One range spec per numeric knob. The GUI builds scales from these, and
# validation clamps against them - a single source of truth.
TUNINGS: dict[str, Tuning] = {
    "max_speed_x": Tuning(
        "max_speed_x", "Max X speed", "px/s", 100.0, 4000.0, 10.0,
        DEFAULT_SPEED,
        "Horizontal look speed at full deflection."),
    "max_speed_y": Tuning(
        "max_speed_y", "Max Y speed", "px/s", 100.0, 4000.0, 10.0,
        DEFAULT_SPEED,
        "Vertical look speed at full deflection. Keep equal to X for a "
        "clean square in games with symmetric vertical sensitivity."),
    "ramp_time": Tuning(
        "ramp_time", "Ramp time", "s", 0.05, 1.00, 0.01, DEFAULT_RAMP_S,
        "Seconds to reach full speed from a fresh hold."),
    "accel_power": Tuning(
        "accel_power", "Power", "", 0.1, 4.0, 0.05, DEFAULT_POWER,
        "Shapes the curve. >1 = slow start/fast sweep, <1 = quick jump."),
    "min_frac": Tuning(
        "min_frac", "Min fraction", "%", 0.0, 50.0, 1.0, DEFAULT_MIN_FRAC * 100.0,
        "Floor offset on the curve: how much speed is present at an "
        "instant press. Higher = more responsive, coarser."),
    "smooth_tau": Tuning(
        "smooth_tau", "Smoothing", "s", 0.005, 0.100, 0.001, DEFAULT_SMOOTH_S,
        "Smoothing settle time (critically damped spring)."),
    "poll_interval": Tuning(
        "poll_interval", "Poll interval", "ms", 1.0, 30.0, 1.0,
        DEFAULT_POLL_MS,
        "How often keys are sampled and mouse events are sent (ms). "
        "Lower = snappier."),
}


@dataclass
class Config:
    """Mutable, validated settings object."""

    max_speed_x: float = DEFAULT_SPEED
    max_speed_y: float = DEFAULT_SPEED
    ramp_time: float = DEFAULT_RAMP_S
    accel_power: float = DEFAULT_POWER
    min_frac: float = DEFAULT_MIN_FRAC
    smooth_tau: float = DEFAULT_SMOOTH_S
    poll_interval: float = DEFAULT_POLL_MS / 1000.0
    curve_type: str = DEFAULT_CURVE
    # When True, bound keys are swallowed at the OS level so they never
    # reach the active window (avoids "double input"). Requires an OS-level
    # keyboard grab, which is OFF by default because on Linux/macOS a stuck
    # grab can lock the desktop. Kept off unless the user enables it.
    suppress_keys: bool = False
    # Key bindings are stored as canonical key ids (strings); see keys.py.
    keys: dict[str, str] = field(default_factory=lambda: dict(K.DEFAULT_BINDINGS))

    # -- validation ----------------------------------------------------

    def validate(self) -> "Config":
        """Clamp and normalize every field in place; return self."""
        for name, spec in TUNINGS.items():
            value = getattr(self, name)
            if name == "min_frac":
                value = value * 100.0
                value = spec.clamp(value)
                setattr(self, name, value / 100.0)
            elif name == "poll_interval":
                # stored in seconds, spec is in ms
                value = value * 1000.0
                value = spec.clamp(value)
                setattr(self, name, value / 1000.0)
            else:
                setattr(self, name, spec.clamp(value))
        if self.curve_type not in _curve_keys():
            self.curve_type = DEFAULT_CURVE
        for action in K.ACTIONS:
            key = self.keys.get(action)
            # None means "unbound"; otherwise a known key id is required.
            if key is None:
                continue
            key = K.normalize(key)
            if not K.is_valid(key):
                self.keys[action] = K.DEFAULT_BINDINGS[action]
            else:
                self.keys[action] = key
        return self

    def copy_safe(self) -> "Config":
        return Config(**dataclasses.asdict(self))

    # -- serialization -------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "max_speed_x": self.max_speed_x,
            "max_speed_y": self.max_speed_y,
            "ramp_time": self.ramp_time,
            "accel_power": self.accel_power,
            "min_frac": self.min_frac,
            "smooth_tau": self.smooth_tau,
            "poll_interval": self.poll_interval,
            "curve_type": self.curve_type,
            "suppress_keys": self.suppress_keys,
            "keys": dict(self.keys),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        cfg = cls()
        spec = set(TUNINGS)
        for k, v in data.items():
            if k in spec:
                setattr(cfg, k, v)
            elif k == "curve_type":
                cfg.curve_type = v
            elif k == "suppress_keys":
                cfg.suppress_keys = bool(v)
            elif k == "keys" and isinstance(v, dict):
                for action, raw in v.items():
                    if action in K.ACTIONS:
                        if raw in (None, 0):
                            # Old configs used VK 0 (and new ones use None)
                            # to mean "unbound" - preserve it.
                            cfg.keys[action] = None
                        else:
                            kid = K.normalize(raw)
                            if kid is not None and K.is_valid(kid):
                                cfg.keys[action] = kid
        return cfg.validate()


def _curve_keys() -> set[str]:
    from . import curve  # local import to avoid circular import at module load
    return set(curve.CURVE_BY_KEY)


def save_config(cfg: Config, path: str) -> None:
    cfg.validate()
    with open(path, "w") as fh:
        json.dump(cfg.to_dict(), fh, indent=2)


def load_config(path: str) -> Config:
    with open(path) as fh:
        data = json.load(fh)
    return Config.from_dict(data)


def load_or_default(path: str | None = None) -> Config:
    path = path or CONFIG_FILE
    if os.path.exists(path):
        try:
            return load_config(path)
        except Exception as exc:  # noqa: BLE001 - a bad cfg must not brick startup
            print("[!] could not load config (%s); using defaults" % exc)
    return Config().validate()
