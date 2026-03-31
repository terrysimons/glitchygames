"""Easing functions for tween interpolation.

Implements Robert Penner's easing equations as pure functions.
Each function takes a normalized time value t (0.0 to 1.0) and
returns an eased value (0.0 to 1.0 for most curves, may overshoot
for elastic and back).

Reference: https://easings.net/
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

# --- Linear ---


def linear(t: float) -> float:
    """No easing, no acceleration."""
    return t


# --- Quadratic (t^2) ---


def ease_in_quad(t: float) -> float:
    """Accelerating from zero velocity."""
    return t * t


def ease_out_quad(t: float) -> float:
    """Decelerating to zero velocity."""
    return t * (2.0 - t)


def ease_in_out_quad(t: float) -> float:
    """Acceleration until halfway, then deceleration."""
    if t < 0.5:
        return 2.0 * t * t
    return -1.0 + (4.0 - 2.0 * t) * t


# --- Cubic (t^3) ---


def ease_in_cubic(t: float) -> float:
    """Accelerating from zero velocity."""
    return t * t * t


def ease_out_cubic(t: float) -> float:
    """Decelerating to zero velocity."""
    shifted = t - 1.0
    return shifted * shifted * shifted + 1.0


def ease_in_out_cubic(t: float) -> float:
    """Acceleration until halfway, then deceleration."""
    if t < 0.5:
        return 4.0 * t * t * t
    shifted = 2.0 * t - 2.0
    return 0.5 * shifted * shifted * shifted + 1.0


# --- Quartic (t^4) ---


def ease_in_quart(t: float) -> float:
    """Accelerating from zero velocity."""
    return t * t * t * t


def ease_out_quart(t: float) -> float:
    """Decelerating to zero velocity."""
    shifted = t - 1.0
    return 1.0 - shifted * shifted * shifted * shifted


def ease_in_out_quart(t: float) -> float:
    """Acceleration until halfway, then deceleration."""
    if t < 0.5:
        return 8.0 * t * t * t * t
    shifted = t - 1.0
    return 1.0 - 8.0 * shifted * shifted * shifted * shifted


# --- Quintic (t^5) ---


def ease_in_quint(t: float) -> float:
    """Accelerating from zero velocity."""
    return t * t * t * t * t


def ease_out_quint(t: float) -> float:
    """Decelerating to zero velocity."""
    shifted = t - 1.0
    return shifted * shifted * shifted * shifted * shifted + 1.0


def ease_in_out_quint(t: float) -> float:
    """Acceleration until halfway, then deceleration."""
    if t < 0.5:
        return 16.0 * t * t * t * t * t
    shifted = 2.0 * t - 2.0
    return 0.5 * shifted * shifted * shifted * shifted * shifted + 1.0


# --- Sine ---


def ease_in_sine(t: float) -> float:
    """Sinusoidal acceleration from zero velocity."""
    return 1.0 - math.cos(t * math.pi / 2.0)


def ease_out_sine(t: float) -> float:
    """Sinusoidal deceleration to zero velocity."""
    return math.sin(t * math.pi / 2.0)


def ease_in_out_sine(t: float) -> float:
    """Sinusoidal acceleration and deceleration."""
    return 0.5 * (1.0 - math.cos(math.pi * t))


# --- Exponential ---


def ease_in_expo(t: float) -> float:
    """Exponential acceleration from zero velocity."""
    if t == 0.0:
        return 0.0
    return math.pow(2.0, 10.0 * (t - 1.0))


def ease_out_expo(t: float) -> float:
    """Exponential deceleration to zero velocity."""
    if t == 1.0:
        return 1.0
    return 1.0 - math.pow(2.0, -10.0 * t)


def ease_in_out_expo(t: float) -> float:
    """Exponential acceleration and deceleration."""
    if t == 0.0:
        return 0.0
    if t == 1.0:
        return 1.0
    if t < 0.5:
        return 0.5 * math.pow(2.0, 20.0 * t - 10.0)
    return 1.0 - 0.5 * math.pow(2.0, -20.0 * t + 10.0)


# --- Circular ---


def ease_in_circ(t: float) -> float:
    """Circular acceleration from zero velocity."""
    return 1.0 - math.sqrt(1.0 - t * t)


def ease_out_circ(t: float) -> float:
    """Circular deceleration to zero velocity."""
    shifted = t - 1.0
    return math.sqrt(1.0 - shifted * shifted)


def ease_in_out_circ(t: float) -> float:
    """Circular acceleration and deceleration."""
    if t < 0.5:
        return 0.5 * (1.0 - math.sqrt(1.0 - 4.0 * t * t))
    shifted = 2.0 * t - 2.0
    return 0.5 * (math.sqrt(1.0 - shifted * shifted) + 1.0)


# --- Elastic ---

_ELASTIC_PERIOD = 0.3
_ELASTIC_AMPLITUDE = 1.0


def ease_in_elastic(t: float) -> float:
    """Elastic acceleration (spring overshoot at start)."""
    if t == 0.0:
        return 0.0
    if t == 1.0:
        return 1.0
    period = _ELASTIC_PERIOD
    shift = period / 4.0
    adjusted = t - 1.0
    return -(
        _ELASTIC_AMPLITUDE
        * math.pow(2.0, 10.0 * adjusted)
        * math.sin((adjusted - shift) * (2.0 * math.pi) / period)
    )


def ease_out_elastic(t: float) -> float:
    """Elastic deceleration (spring overshoot at end)."""
    if t == 0.0:
        return 0.0
    if t == 1.0:
        return 1.0
    period = _ELASTIC_PERIOD
    shift = period / 4.0
    return (
        _ELASTIC_AMPLITUDE
        * math.pow(2.0, -10.0 * t)
        * math.sin((t - shift) * (2.0 * math.pi) / period)
        + 1.0
    )


def ease_in_out_elastic(t: float) -> float:
    """Elastic acceleration and deceleration."""
    if t == 0.0:
        return 0.0
    if t == 1.0:
        return 1.0
    period = _ELASTIC_PERIOD * 1.5
    shift = period / 4.0
    adjusted = 2.0 * t - 1.0
    if t < 0.5:
        return -0.5 * (
            math.pow(2.0, 10.0 * adjusted) * math.sin((adjusted - shift) * (2.0 * math.pi) / period)
        )
    return (
        0.5
        * math.pow(2.0, -10.0 * adjusted)
        * math.sin((adjusted - shift) * (2.0 * math.pi) / period)
        + 1.0
    )


# --- Back (overshoot) ---

_BACK_OVERSHOOT = 1.70158


def ease_in_back(t: float) -> float:
    """Overshoot acceleration (pulls back before accelerating)."""
    return t * t * ((_BACK_OVERSHOOT + 1.0) * t - _BACK_OVERSHOOT)


def ease_out_back(t: float) -> float:
    """Overshoot deceleration (overshoots target then returns)."""
    shifted = t - 1.0
    return shifted * shifted * ((_BACK_OVERSHOOT + 1.0) * shifted + _BACK_OVERSHOOT) + 1.0


def ease_in_out_back(t: float) -> float:
    """Overshoot acceleration and deceleration."""
    overshoot = _BACK_OVERSHOOT * 1.525
    if t < 0.5:
        scaled = 2.0 * t
        return 0.5 * (scaled * scaled * ((overshoot + 1.0) * scaled - overshoot))
    scaled = 2.0 * t - 2.0
    return 0.5 * (scaled * scaled * ((overshoot + 1.0) * scaled + overshoot) + 2.0)


# --- Bounce ---


def ease_out_bounce(t: float) -> float:
    """Bouncing deceleration (like a ball dropping and bouncing)."""
    # Magic numbers from Penner's original bounce equation
    boundary_1 = 1.0 / 2.75
    boundary_2 = 2.0 / 2.75
    boundary_3 = 2.5 / 2.75
    scale_factor = 7.5625

    if t < boundary_1:
        return scale_factor * t * t
    if t < boundary_2:
        adjusted = t - 1.5 / 2.75
        return scale_factor * adjusted * adjusted + 0.75
    if t < boundary_3:
        adjusted = t - 2.25 / 2.75
        return scale_factor * adjusted * adjusted + 0.9375
    adjusted = t - 2.625 / 2.75
    return scale_factor * adjusted * adjusted + 0.984375


def ease_in_bounce(t: float) -> float:
    """Bouncing acceleration."""
    return 1.0 - ease_out_bounce(1.0 - t)


def ease_in_out_bounce(t: float) -> float:
    """Bouncing acceleration and deceleration."""
    if t < 0.5:
        return 0.5 * ease_in_bounce(2.0 * t)
    return 0.5 * ease_out_bounce(2.0 * t - 1.0) + 0.5


# --- Lookup ---

EASING_FUNCTIONS: dict[str, Callable[[float], float]] = {
    'linear': linear,
    'ease_in_quad': ease_in_quad,
    'ease_out_quad': ease_out_quad,
    'ease_in_out_quad': ease_in_out_quad,
    'ease_in_cubic': ease_in_cubic,
    'ease_out_cubic': ease_out_cubic,
    'ease_in_out_cubic': ease_in_out_cubic,
    'ease_in_quart': ease_in_quart,
    'ease_out_quart': ease_out_quart,
    'ease_in_out_quart': ease_in_out_quart,
    'ease_in_quint': ease_in_quint,
    'ease_out_quint': ease_out_quint,
    'ease_in_out_quint': ease_in_out_quint,
    'ease_in_sine': ease_in_sine,
    'ease_out_sine': ease_out_sine,
    'ease_in_out_sine': ease_in_out_sine,
    'ease_in_expo': ease_in_expo,
    'ease_out_expo': ease_out_expo,
    'ease_in_out_expo': ease_in_out_expo,
    'ease_in_circ': ease_in_circ,
    'ease_out_circ': ease_out_circ,
    'ease_in_out_circ': ease_in_out_circ,
    'ease_in_elastic': ease_in_elastic,
    'ease_out_elastic': ease_out_elastic,
    'ease_in_out_elastic': ease_in_out_elastic,
    'ease_in_back': ease_in_back,
    'ease_out_back': ease_out_back,
    'ease_in_out_back': ease_in_out_back,
    'ease_in_bounce': ease_in_bounce,
    'ease_out_bounce': ease_out_bounce,
    'ease_in_out_bounce': ease_in_out_bounce,
}


def get_easing(name: str) -> Callable[[float], float]:
    """Look up an easing function by name.

    Args:
        name: The easing function name (e.g., 'ease_out_quad').

    Returns:
        The easing function.

    Raises:
        KeyError: If the easing name is not recognized.

    """
    if name not in EASING_FUNCTIONS:
        available = ', '.join(sorted(EASING_FUNCTIONS.keys()))
        msg = f"Unknown easing function '{name}'. Available: {available}"
        raise KeyError(msg)
    return EASING_FUNCTIONS[name]
