"""Animation state machine with TOML-declared transitions and coroutine behaviors.

Manages animation transitions based on physics state. Transitions are
defined in TOML sprite files or added via code. Coroutine behaviors
allow complex multi-step state logic (entry → per-frame → exit).

Usage:
    sm = AnimationStateMachine(sprite)
    sm.load_from_toml(transition_data)
    sm.evaluate(context)  # called each frame
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol, TypeIs

from glitchygames.animation.expressions import Expression, parse
from glitchygames.animation.scheduler import BehaviorFunction, BehaviorScheduler

if TYPE_CHECKING:
    from collections.abc import Callable

# Type alias for state callbacks (no arguments, no return)
type StateCallback = Callable[[], None]

log: logging.Logger = logging.getLogger('game.animation.state_machine')


# What the state machine uses of its sprite, when the sprite has it (an AnimatedSprite has all
# three; the example games' players are plain Sprites with none). Each is detected with hasattr.
class ReportsAnimationCompletion(Protocol):
    """A sprite that says whether its current non-looping animation has finished."""

    def is_animation_complete(self) -> bool:
        """Return True once the current non-looping animation has finished."""
        ...


class PlaysAnimations(Protocol):
    """A sprite that switches to a named animation (AnimatedSprite.play)."""

    def play(self, animation_name: str | None = None) -> None:
        """Start playing the named animation."""
        ...


class HasAnimationLoopFlags(Protocol):
    """A sprite with per-animation loop flags (AnimatedSprite): it loops as the flag says.

    The flags themselves are AnimatedSprite's private ``_loop_flags``, so they are not a
    member; _switch_to reads them by name.
    """

    is_looping: bool


def _reports_animation_completion(sprite: object) -> TypeIs[ReportsAnimationCompletion]:
    return hasattr(sprite, 'is_animation_complete')


def _plays_animations(sprite: object) -> TypeIs[PlaysAnimations]:
    return hasattr(sprite, 'play')


def _has_animation_loop_flags(sprite: object) -> TypeIs[HasAnimationLoopFlags]:
    # Only _loop_flags is checked, as always: is_looping is then set on the sprite
    return hasattr(sprite, '_loop_flags')


class Transition:
    """A single transition rule from one state to another.

    Args:
        from_state: Source animation namespace.
        to_state: Target animation namespace.
        condition: Parsed expression from `when` clause.

    """

    def __init__(
        self,
        from_state: str,
        to_state: str,
        condition: Expression,
    ) -> None:
        """Initialize the transition."""
        self.from_state = from_state
        self.to_state = to_state
        self.condition = condition

    def should_fire(self, context: dict[str, Any]) -> bool:
        """Check if this transition's condition is met.

        Args:
            context: Current frame's variable values.

        Returns:
            True if the transition should fire.

        """
        result = self.condition.evaluate(context)
        return bool(result)


class AnimationStateMachine:
    """Manages animation transitions for a sprite.

    Evaluates transition rules each frame, switches animations when
    conditions are met, and runs coroutine behaviors for active states.

    Args:
        sprite: The AnimatedSprite this state machine controls.

    """

    def __init__(self, sprite: object) -> None:
        """Initialize the state machine."""
        self._sprite: object = sprite
        self._transitions: list[Transition] = []
        self._behaviors: dict[str, BehaviorFunction] = {}
        self._callbacks_on_enter: dict[str, list[StateCallback]] = {}
        self._callbacks_on_exit: dict[str, list[StateCallback]] = {}
        self._callbacks_on_complete: dict[str, list[StateCallback]] = {}
        self._scheduler: BehaviorScheduler = BehaviorScheduler()
        self._current_state: str = ''
        self._time_in_state: float = 0.0

    @property
    def current_state(self) -> str:
        """The current animation state name."""
        return self._current_state

    @property
    def time_in_state(self) -> float:
        """Seconds since entering the current state."""
        return self._time_in_state

    def load_from_toml(self, transitions_data: list[dict[str, Any]]) -> None:
        """Load transition rules from parsed TOML data.

        Args:
            transitions_data: List of transition dicts from TOML,
                each with 'from', 'to', and 'when' keys.

        """
        for transition_dict in transitions_data:
            from_state = transition_dict.get('from', '')
            to_state = transition_dict.get('to', '')
            when_expr = transition_dict.get('when', '')

            if not from_state or not to_state or not when_expr:
                log.warning(
                    'Skipping incomplete transition: %s',
                    transition_dict,
                )
                continue

            try:
                condition = parse(when_expr)
            except ValueError:
                log.exception(
                    "Failed to parse transition expression '%s'",
                    when_expr,
                )
                continue

            self._transitions.append(
                Transition(
                    from_state=from_state,
                    to_state=to_state,
                    condition=condition,
                ),
            )

    def add_transition(
        self,
        from_state: str,
        to_state: str,
        condition: Expression | None = None,
        when: str | None = None,
    ) -> None:
        """Add a transition rule via code.

        Provide either a pre-parsed Expression or a `when` string.

        Args:
            from_state: Source animation namespace.
            to_state: Target animation namespace.
            condition: Pre-parsed expression (takes precedence).
            when: Expression string to parse.

        Raises:
            ValueError: If no condition expression is provided.

        """
        if condition is None and when is not None:
            condition = parse(when)
        if condition is None:
            msg = 'Must provide either condition or when'
            raise ValueError(msg)

        self._transitions.append(
            Transition(
                from_state=from_state,
                to_state=to_state,
                condition=condition,
            ),
        )

    def behavior(self, state_name: str) -> Callable[[BehaviorFunction], BehaviorFunction]:
        """Decorator to register a coroutine behavior for a state.

        Usage:
            @state_machine.behavior('attack')
            def attack_behavior(sprite, ctx):
                sprite.spawn_hitbox()
                dt = yield
                while not ctx.animation_complete:
                    dt = yield
                sprite.cleanup()

        Args:
            state_name: The animation state this behavior applies to.

        Returns:
            Decorator function.

        """

        def decorator(func: BehaviorFunction) -> BehaviorFunction:
            self._behaviors[state_name] = func
            return func

        return decorator

    def on_enter(self, state_name: str, callback: StateCallback) -> None:
        """Register a callback for when a state is entered.

        Args:
            state_name: The animation state name.
            callback: Called with no arguments when entering the state.

        """
        self._callbacks_on_enter.setdefault(state_name, []).append(callback)

    def on_exit(self, state_name: str, callback: StateCallback) -> None:
        """Register a callback for when a state is exited.

        Args:
            state_name: The animation state name.
            callback: Called with no arguments when leaving the state.

        """
        self._callbacks_on_exit.setdefault(state_name, []).append(callback)

    def on_complete(self, state_name: str, callback: StateCallback) -> None:
        """Register a callback for when a non-looping animation completes.

        Args:
            state_name: The animation state name.
            callback: Called when the animation reaches its last frame.

        """
        self._callbacks_on_complete.setdefault(state_name, []).append(callback)

    def evaluate(self, context: dict[str, Any], dt: float = 0.0) -> None:
        """Check transitions and advance the behavior coroutine.

        Called each frame. Checks all transitions from the current state,
        switches if a condition is met, and steps the active behavior.

        Args:
            context: Current physics/game state variables.
            dt: Delta time for this frame.

        """
        self._time_in_state += dt

        # Add built-in context variables
        context['timer'] = self._time_in_state

        # Check animation_complete from sprite if available
        if _reports_animation_completion(self._sprite):
            context['animation_complete'] = self._sprite.is_animation_complete()
        elif 'animation_complete' not in context:
            context['animation_complete'] = False

        # Check transitions from current state
        for transition in self._transitions:
            if transition.from_state != self._current_state:
                continue
            if transition.should_fire(context):
                self._switch_to(transition.to_state, context)
                break

        # Step the behavior coroutine
        self._scheduler.step(variables=context, dt=dt)

        # Check on_complete callbacks
        if context.get('animation_complete') and self._current_state in self._callbacks_on_complete:
            for callback in self._callbacks_on_complete[self._current_state]:
                callback()

    def set_state(self, state_name: str, context: dict[str, Any] | None = None) -> None:
        """Force-set the current state without checking transitions.

        Useful for initial state setup.

        Args:
            state_name: The animation state to switch to.
            context: Optional initial context for the behavior.

        """
        self._switch_to(state_name, context or {})

    def _switch_to(self, new_state: str, context: dict[str, Any]) -> None:
        """Transition to a new state.

        Fires exit callbacks, cancels behavior, switches animation,
        fires enter callbacks, starts new behavior.

        Args:
            new_state: Target animation state name.
            context: Current context for the new behavior.

        """
        old_state = self._current_state

        # Fire exit callbacks for old state
        if old_state in self._callbacks_on_exit:
            for callback in self._callbacks_on_exit[old_state]:
                callback()

        # Cancel old behavior
        self._scheduler.cancel()

        # Switch animation on the sprite
        self._current_state = new_state
        self._time_in_state = 0.0

        if _plays_animations(self._sprite):
            self._sprite.play(new_state)

        # Auto-set loop mode from animation data if available
        if _has_animation_loop_flags(self._sprite):
            # AnimatedSprite's private flags, read by name (the guard found them)
            loop_flags: dict[str, bool] = getattr(self._sprite, '_loop_flags', {})
            if new_state in loop_flags:
                self._sprite.is_looping = loop_flags[new_state]

        # Fire enter callbacks
        if new_state in self._callbacks_on_enter:
            for callback in self._callbacks_on_enter[new_state]:
                callback()

        # Start new behavior coroutine if registered
        if new_state in self._behaviors:
            self._scheduler.start(
                behavior_function=self._behaviors[new_state],
                sprite=self._sprite,
                initial_context=context,
            )
