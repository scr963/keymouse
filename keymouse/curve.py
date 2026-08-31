"""Pure curve / smoothing mathematics.

Everything in this module is deterministic and side-effect free, taking
all inputs as explicit arguments. This makes the tuning math unit
testable without any OS dependency.
"""

from __future__ import annotations

import math

# Curve kinds offered to the user, as (key, display label) pairs.
CURVES = [
    ("power", "Power"),
    ("linear", "Linear"),
    ("exponential", "Exponential"),
    ("sigmoid", "Sigmoid (S)"),
    ("logarithmic", "Logarithmic"),
    ("smoothstep", "Smoothstep"),
]
CURVE_BY_KEY = dict(CURVES)


def curve_shape(progress: float, kind: str, power: float) -> float:
    """Normalized [0,1] curve shape at hold progress ``progress``.

    ``progress`` is clamped to [0,1]; output is in [0,1].
    """
    progress = max(0.0, min(progress, 1.0))
    if kind == "linear":
        return progress
    if kind == "power":
        return progress ** power
    if kind == "exponential":
        denom = math.exp(power) - 1.0
        if denom == 0.0:
            return 0.0
        return (math.exp(power * progress) - 1.0) / denom
    if kind == "sigmoid":
        s = power * 4.0
        g0 = 1.0 / (1.0 + math.exp(s / 2.0))
        g1 = 1.0 / (1.0 + math.exp(-s / 2.0))
        span = g1 - g0
        if span == 0.0:
            return 0.0
        val = 1.0 / (1.0 + math.exp(-s * (progress - 0.5)))
        return max(0.0, min(1.0, (val - g0) / span))
    if kind == "logarithmic":
        return math.log1p(progress * (math.e - 1.0))
    if kind == "smoothstep":
        return progress * progress * (3.0 - 2.0 * progress)
    # Unknown kind -> fall back to linear so the UI never stalls.
    return progress


def target_speed(direction: int, hold_time: float, max_speed: float,
                 ramp_time: float, curve_type: str, power: float,
                 min_frac: float) -> float:
    """Target (un-smoothed) speed in px/s for a pressed direction.

    ``direction`` is -1, 0 or +1. ``hold_time`` is seconds since the
    direction was pressed. ``min_frac`` is the fraction of ``max_speed``
    that is already present at an instant press (the curve floor).
    """
    if direction == 0:
        return 0.0
    if ramp_time <= 0.0 or hold_time < 0.0:
        return 0.0
    progress = min(hold_time / ramp_time, 1.0)
    shape = curve_shape(progress, curve_type, power)
    frac = min_frac + (1.0 - min_frac) * shape
    return direction * max_speed * frac


def smooth_damp(current: float, target: float, velocity: float,
                smooth_time: float, max_speed: float, dt: float) -> tuple[float, float]:
    """Frame-rate independent critically-damped smoothing.

    Returns the new ``current`` and ``velocity``. ``smooth_time`` is the
    approximate settle time in seconds. ``max_speed`` bounds how fast the
    value may move per frame to avoid overshoot blowups.

    This is the well-known Unity Mathf.SmoothDamp port, which avoids
    overshoot and is stable across varying frame times.
    """
    if smooth_time <= 0.0 or dt <= 0.0:
        return target, 0.0

    omega = 2.0 / smooth_time
    x = omega * dt
    # exp(-x) approximation (rational) - cheap and glitch-free.
    exp_approx = 1.0 / (1.0 + x + 0.48 * x * x + 0.235 * x * x * x)

    max_change = max_speed * smooth_time
    delta = current - target
    delta = max(-max_change, min(delta, max_change))
    target_adj = current - delta

    temp = (velocity + omega * delta) * dt
    new_velocity = (velocity - omega * temp) * exp_approx
    output = target_adj + (delta + temp) * exp_approx

    # Prevent overflow past the target (kills oscillation).
    if (target - current > 0.0) == (output > target):
        output = target
        new_velocity = (output - target_adj) / dt
    return output, new_velocity
