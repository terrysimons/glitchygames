"""Scene transition effects for GlitchyGames.

Provides composable transition objects that render visual effects
between scene switches. Transitions capture screenshots of old and
new scenes and animate between them.

Usage:
    from glitchygames.transitions import FadeTransition

    self.transition_to(next_scene, FadeTransition(duration=0.5))
"""

from glitchygames.transitions.base import Transition, TransitionState
from glitchygames.transitions.elevator import ElevatorTransition
from glitchygames.transitions.fade import CrossfadeTransition, FadeTransition
from glitchygames.transitions.slide import SlideTransition
from glitchygames.transitions.wipe import WipeTransition

__all__ = [
    'CrossfadeTransition',
    'ElevatorTransition',
    'FadeTransition',
    'SlideTransition',
    'Transition',
    'TransitionState',
    'WipeTransition',
]
