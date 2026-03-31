"""Effects module for GlitchyGames.

Provides tweening, easing, and interpolation utilities for smooth
animations, camera effects, and UI transitions.
"""

from glitchygames.effects.easing import EASING_FUNCTIONS, get_easing
from glitchygames.effects.tween import Tween, TweenGroup, TweenManager, TweenSequence

__all__ = [
    'EASING_FUNCTIONS',
    'Tween',
    'TweenGroup',
    'TweenManager',
    'TweenSequence',
    'get_easing',
]
