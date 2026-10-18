"""Tween system for smooth property interpolation.

Provides Tween, TweenSequence, TweenGroup, and TweenManager for
animating any numeric property on any object using easing functions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from glitchygames.effects.easing import get_easing

if TYPE_CHECKING:
    from collections.abc import Callable

log: logging.Logger = logging.getLogger('game.effects.tween')

# Repeat forever
REPEAT_INFINITE = -1


@runtime_checkable
class HasDirtyFlag(Protocol):
    """Protocol for objects that support dirty-rect rendering."""

    dirty: int


class Tween:
    """Interpolates a single numeric property on a target object.

    Uses easing functions to smoothly transition a property from
    start_value to end_value over a specified duration.

    Args:
        target: The object whose property will be tweened.
        property_name: The attribute name to interpolate.
        end_value: The target value to interpolate toward.
        duration: Time in seconds for the tween to complete.
        start_value: Starting value. If None, uses the property's
            current value when the tween first updates.
        easing: Name of the easing function (default: 'linear').
        delay: Seconds to wait before the tween begins.
        on_complete: Callback invoked when the tween finishes.
        repeat: Number of additional repetitions. 0 = play once,
            -1 (REPEAT_INFINITE) = loop forever.
        ping_pong: If True, reverse direction on each repeat.

    """

    def __init__(
        self,
        target: Any,
        property_name: str,
        end_value: float,
        duration: float,
        start_value: float | None = None,
        easing: str = 'linear',
        delay: float = 0.0,
        on_complete: Callable[[], None] | None = None,
        repeat: int = 0,
        *,
        ping_pong: bool = False,
    ) -> None:
        """Initialize the tween."""
        self._target = target
        self._property_name = property_name
        self._end_value = end_value
        self._duration = max(duration, 0.0001)  # Prevent division by zero
        self._start_value_arg = start_value
        self._start_value: float | None = start_value
        self._easing_name = easing
        self._easing_function = get_easing(easing)
        self._delay = delay
        self._on_complete = on_complete
        self._repeat = repeat
        self._ping_pong = ping_pong

        self._elapsed: float = 0.0
        self._delay_elapsed: float = 0.0
        self._is_complete: bool = False
        self._is_cancelled: bool = False
        self._repeat_count: int = 0
        self._is_reversed: bool = False

    def update(self, dt: float) -> bool:
        """Advance the tween by dt seconds.

        Args:
            dt: Delta time in seconds since last update.

        Returns:
            True when the tween has fully completed (all repeats done).

        """
        if self._is_complete or self._is_cancelled:
            return True

        # Handle delay
        if self._delay_elapsed < self._delay:
            self._delay_elapsed += dt
            if self._delay_elapsed < self._delay:
                return False
            # Apply leftover dt after delay
            dt = self._delay_elapsed - self._delay

        # Resolve start value on first real update
        if self._start_value is None:
            self._start_value = float(getattr(self._target, self._property_name))

        self._elapsed += dt

        # Calculate normalized time (0.0 to 1.0), clamped.
        # The clamp handles both overshoot (large dt) and floating-point
        # accumulation (e.g., 10 * 0.1 = 0.9999... not 1.0) by treating
        # anything at or beyond the duration as complete.
        normalized_time = min(self._elapsed / self._duration, 1.0)

        # Determine interpolation direction
        if self._is_reversed:
            start = self._end_value
            end = self._start_value
        else:
            start = self._start_value
            end = self._end_value

        # Apply easing and interpolate
        eased_time = self._easing_function(normalized_time)
        current_value = start + (end - start) * eased_time

        # Set the property on the target
        setattr(self._target, self._property_name, current_value)

        # Mark sprite dirty for re-rendering if applicable.
        # Only upgrade dirty 0→1; never downgrade 2→1 (2 = always redraw)
        if isinstance(self._target, HasDirtyFlag) and self._target.dirty == 0:
            self._target.dirty = 1

        # Check if this iteration is complete.
        # Floating-point accumulation means sum(dt) may not exactly reach
        # duration (e.g., 10 * 0.1 = 0.9999... not 1.0). We use a small
        # epsilon relative to dt magnitude to handle this correctly.
        completion_epsilon = 1e-9
        if self._elapsed >= self._duration - completion_epsilon:
            return self._handle_iteration_complete()

        return False

    def _handle_iteration_complete(self) -> bool:
        """Handle completion of one iteration.

        Returns:
            True if all iterations are done, False if repeating.

        """
        # Check for repeats
        if self._repeat == REPEAT_INFINITE or self._repeat_count < self._repeat:
            self._repeat_count += 1
            self._elapsed = 0.0
            if self._ping_pong:
                self._is_reversed = not self._is_reversed
            return False

        # Fully complete
        self._is_complete = True
        if self._on_complete is not None:
            self._on_complete()
        return True

    def cancel(self) -> None:
        """Stop the tween immediately without calling on_complete."""
        self._is_cancelled = True

    @property
    def is_complete(self) -> bool:
        """Whether the tween has finished all iterations."""
        return self._is_complete

    @property
    def is_active(self) -> bool:
        """Whether the tween is still running (not complete or cancelled)."""
        return not self._is_complete and not self._is_cancelled

    @property
    def target(self) -> Any:
        """The object being tweened."""
        return self._target

    @property
    def property_name(self) -> str:
        """The property name being tweened."""
        return self._property_name


class TweenSequence:
    """Runs tweens one after another in sequence.

    Each tween starts only after the previous one completes.
    The sequence is complete when the last tween finishes.

    Args:
        tweens: The tweens to run in order.

    """

    def __init__(self, *tweens: Tween) -> None:
        """Initialize the sequence with tweens to run serially."""
        self._tweens: list[Tween] = list(tweens)
        self._current_index: int = 0
        self._is_complete: bool = len(self._tweens) == 0

    def update(self, dt: float) -> bool:
        """Advance the current tween in the sequence.

        Args:
            dt: Delta time in seconds.

        Returns:
            True when all tweens in the sequence have completed.

        """
        if self._is_complete:
            return True

        current_tween = self._tweens[self._current_index]
        if current_tween.update(dt):
            self._current_index += 1
            if self._current_index >= len(self._tweens):
                self._is_complete = True
                return True

        return False

    def cancel(self) -> None:
        """Cancel all tweens in the sequence."""
        for tween in self._tweens:
            tween.cancel()
        self._is_complete = True

    @property
    def is_complete(self) -> bool:
        """Whether all tweens in the sequence have finished."""
        return self._is_complete

    @property
    def is_active(self) -> bool:
        """Whether the sequence is still running."""
        return not self._is_complete


class TweenGroup:
    """Runs tweens simultaneously in parallel.

    All tweens update together each frame. The group is complete
    when every tween in it has finished.

    Args:
        tweens: The tweens to run in parallel.

    """

    def __init__(self, *tweens: Tween) -> None:
        """Initialize the group with tweens to run in parallel."""
        self._tweens: list[Tween] = list(tweens)
        self._is_complete: bool = len(self._tweens) == 0

    def update(self, dt: float) -> bool:
        """Update all tweens in the group simultaneously.

        Args:
            dt: Delta time in seconds.

        Returns:
            True when all tweens in the group have completed.

        """
        if self._is_complete:
            return True

        all_done = True
        for tween in self._tweens:
            if tween.is_active and not tween.update(dt):
                all_done = False

        if all_done:
            self._is_complete = True

        return self._is_complete

    def cancel(self) -> None:
        """Cancel all tweens in the group."""
        for tween in self._tweens:
            tween.cancel()
        self._is_complete = True

    @property
    def is_complete(self) -> bool:
        """Whether all tweens in the group have finished."""
        return self._is_complete

    @property
    def is_active(self) -> bool:
        """Whether the group is still running."""
        return not self._is_complete


class TweenManager:
    """Manages all active tweens for a scene.

    Provides a convenient API for creating, updating, and cancelling
    tweens. One TweenManager per scene -- updated in Scene.dt_tick().
    """

    def __init__(self) -> None:
        """Initialize the tween manager with an empty active list."""
        self._active: list[Tween | TweenSequence | TweenGroup] = []

    def update(self, dt: float) -> None:
        """Update all active tweens and remove completed ones.

        Args:
            dt: Delta time in seconds since last frame.

        """
        self._active = [
            tweened_item for tweened_item in self._active if not tweened_item.update(dt)
        ]

    def tween(
        self,
        target: Any,
        property_name: str,
        end_value: float,
        duration: float,
        **kwargs: Any,
    ) -> Tween:
        """Create and register a new tween.

        Args:
            target: The object whose property will be tweened.
            property_name: The attribute name to interpolate.
            end_value: The target value.
            duration: Time in seconds.
            **kwargs: Additional Tween arguments (start_value, easing,
                delay, on_complete, repeat, ping_pong).

        Returns:
            The created Tween instance.

        """
        new_tween = Tween(
            target=target,
            property_name=property_name,
            end_value=end_value,
            duration=duration,
            **kwargs,
        )
        self._active.append(new_tween)
        return new_tween

    def sequence(self, *tweens: Tween) -> TweenSequence:
        """Create and register a tween sequence (serial execution).

        Args:
            *tweens: Tweens to run one after another.

        Returns:
            The created TweenSequence instance.

        """
        new_sequence = TweenSequence(*tweens)
        self._active.append(new_sequence)
        return new_sequence

    def group(self, *tweens: Tween) -> TweenGroup:
        """Create and register a tween group (parallel execution).

        Args:
            *tweens: Tweens to run simultaneously.

        Returns:
            The created TweenGroup instance.

        """
        new_group = TweenGroup(*tweens)
        self._active.append(new_group)
        return new_group

    def cancel_all(self, target: Any | None = None) -> None:
        """Cancel tweens.

        If target is specified, only cancel tweens on that target.
        If target is None, cancel all tweens.

        Args:
            target: Optional target to filter by.

        """
        if target is None:
            for tweened_item in self._active:
                tweened_item.cancel()
            self._active.clear()
        else:
            for tweened_item in self._active:
                if isinstance(tweened_item, Tween) and tweened_item.target is target:
                    tweened_item.cancel()

    @property
    def active_count(self) -> int:
        """Number of currently active tweens/sequences/groups."""
        return len(self._active)
