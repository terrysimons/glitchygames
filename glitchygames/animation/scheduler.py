"""Coroutine scheduler for animation state behaviors.

Runs async behavior functions one step per frame. Each behavior is a
generator that yields to pause until the next frame, receives dt back,
and is cancelled (GeneratorExit) when the state exits.

Usage:
    scheduler = BehaviorScheduler()

    def my_behavior(sprite, ctx):
        # on_enter
        sprite.spawn_hitbox()
        dt = yield  # wait one frame
        while not ctx.get('animation_complete'):
            sprite.check_hits()
            dt = yield
        # on_exit (when generator returns or is cancelled)
        sprite.cleanup()

    scheduler.start(my_behavior, sprite, ctx)
    scheduler.step(dt)  # advances one frame
    scheduler.cancel()  # forces exit
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Generator
from typing import Any

log: logging.Logger = logging.getLogger('game.animation.scheduler')


class BehaviorContext:
    """Context object passed to behavior coroutines.

    Provides access to animation state variables and frame control.
    The `next_frame()` method is used as the yield target in behaviors.

    Args:
        initial_context: Starting variable values.

    """

    def __init__(self, initial_context: dict[str, Any] | None = None) -> None:
        """Initialize the behavior context."""
        self._variables: dict[str, Any] = dict(initial_context) if initial_context else {}
        self._dt: float = 0.0

    def get(self, name: str, default: Any = False) -> Any:  # noqa: FBT002
        """Get a context variable.

        Args:
            name: Variable name.
            default: Value if not found.

        Returns:
            The variable value or default.

        """
        return self._variables.get(name, default)

    @property
    def animation_complete(self) -> bool:
        """Whether the current non-looping animation has finished."""
        return bool(self._variables.get('animation_complete', False))

    @property
    def dt(self) -> float:
        """Delta time from the most recent frame."""
        return self._dt

    def update(self, variables: dict[str, Any], dt: float) -> None:
        """Update context with new frame data.

        Args:
            variables: Updated variable values.
            dt: Delta time for this frame.

        """
        self._variables.update(variables)
        self._dt = dt


# Type alias for behavior generator functions
BehaviorFunction = Callable[[Any, BehaviorContext], Generator[None, float | None]]


class BehaviorScheduler:
    """Runs a single behavior coroutine one step per frame.

    Manages the lifecycle of a behavior generator: start, step each
    frame, and cancel on state exit.
    """

    def __init__(self) -> None:
        """Initialize the scheduler with no active behavior."""
        self._generator: Generator[None, float | None] | None = None
        self._context: BehaviorContext = BehaviorContext()
        self._started: bool = False

    @property
    def is_running(self) -> bool:
        """Whether a behavior is currently active."""
        return self._generator is not None and self._started

    @property
    def context(self) -> BehaviorContext:
        """The current behavior context."""
        return self._context

    def start(
        self,
        behavior_function: BehaviorFunction,
        sprite: Any,
        initial_context: dict[str, Any] | None = None,
    ) -> None:
        """Start a new behavior coroutine.

        Cancels any running behavior first.

        Args:
            behavior_function: Generator function defining the behavior.
            sprite: The sprite this behavior controls.
            initial_context: Starting variable values.

        """
        self.cancel()
        self._context = BehaviorContext(initial_context)
        self._generator = behavior_function(sprite, self._context)
        self._started = False

        # Prime the generator (advance to first yield)
        try:
            next(self._generator)
            self._started = True
        except StopIteration:
            # Behavior completed immediately (no yields)
            self._generator = None
            self._started = False

    def step(self, variables: dict[str, Any], dt: float) -> None:
        """Advance the behavior by one frame.

        Sends dt to the coroutine and updates context variables.

        Args:
            variables: Current frame's context variables.
            dt: Delta time for this frame.

        """
        if self._generator is None:
            return

        self._context.update(variables, dt)

        try:
            self._generator.send(dt)
        except StopIteration:
            # Behavior completed naturally
            self._generator = None
            self._started = False

    def cancel(self) -> None:
        """Cancel the running behavior.

        Sends GeneratorExit to the coroutine, allowing cleanup code
        in finally blocks to run.
        """
        if self._generator is not None:
            try:
                self._generator.close()
            except Exception:
                log.exception('Error closing behavior coroutine')
            self._generator = None
            self._started = False
