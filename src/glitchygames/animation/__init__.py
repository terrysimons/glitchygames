"""Animation state machine for GlitchyGames.

Provides TOML-declared transitions and coroutine-based state behaviors
for sprites. Transitions evaluate physics state via a minimal expression
language. Behaviors are generator functions that run entry/per-frame/exit
logic across multiple frames.

Usage:
    sm = AnimationStateMachine(sprite)
    sm.load_from_toml(data['transition'])
    sm.evaluate(physics_context, dt)
"""

from glitchygames.animation.expressions import Expression, parse
from glitchygames.animation.scheduler import BehaviorContext, BehaviorScheduler
from glitchygames.animation.state_machine import AnimationStateMachine, Transition

__all__ = [
    'AnimationStateMachine',
    'BehaviorContext',
    'BehaviorScheduler',
    'Expression',
    'Transition',
    'parse',
]
