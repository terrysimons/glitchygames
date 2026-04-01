"""Input action mapping module for GlitchyGames.

Maps physical inputs (keyboard keys, controller buttons, analog axes)
to named game actions. Supports event-driven lookup and frame-based
state tracking.

Usage:
    from glitchygames.input import ActionMap

    actions = ActionMap()
    actions.bind('jump', keyboard=pygame.K_SPACE,
                 controller_button=pygame.CONTROLLER_BUTTON_A)
"""

from glitchygames.input.action_map import ActionMap, AxisBinding, Binding

__all__ = [
    'ActionMap',
    'AxisBinding',
    'Binding',
]
