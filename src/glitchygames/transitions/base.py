"""Base class for scene transitions.

Transitions capture screenshots of old and new scenes, then render
a composited animation between them for a duration. Scenes are NOT
live during the transition -- just surfaces being blended.

Subclasses implement start(), update(), and render() to define
the visual effect.
"""

from __future__ import annotations

import bisect
import enum
import logging
import operator
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    import pygame

from glitchygames.effects.easing import get_easing

log: logging.Logger = logging.getLogger('game.transitions')

# Half-width of the central difference used to estimate the easing slope
EASING_SLOPE_STEP = 1e-3

# The edges a directional transition (slide, wipe) can move toward.
DIRECTIONS = ('left', 'right', 'up', 'down')


def checked_direction(direction: str) -> str:
    """Return the direction if a directional transition knows it.

    Args:
        direction: The requested direction.

    Returns:
        The direction, unchanged.

    Raises:
        ValueError: If the direction is not one of DIRECTIONS.

    """
    if direction not in DIRECTIONS:
        message = f'Unknown transition direction {direction!r}; expected one of {DIRECTIONS}'
        raise ValueError(message)
    return direction


class TransitionState(enum.Enum):
    """Lifecycle state of a transition."""

    IDLE = 'idle'
    RUNNING = 'running'
    COMPLETE = 'complete'


class Transition:
    """Base class for scene transitions.

    Manages timing, easing, and lifecycle. Subclasses override
    _render_frame() to define the visual effect.

    Args:
        duration: Transition duration in seconds.
        easing: Easing function name (from glitchygames.effects.easing).
        on_update: Called with this transition after every update() that is still
            running, after cues fire. Use it to drive state from the transition's progress.

    """

    def __init__(
        self,
        duration: float = 0.5,
        easing: str = 'ease_in_out_quad',
        on_update: Callable[[Transition], None] | None = None,
    ) -> None:
        """Initialize the transition."""
        self._duration = duration
        self._easing_name = easing
        self._easing_func = get_easing(easing)
        self._on_update = on_update
        # Sorted by progress; equal progresses keep insertion order
        self._cues: list[tuple[float, int, Callable[[], None]]] = []
        self._next_cue_index = 0
        self._elapsed: float = 0.0
        self._state = TransitionState.IDLE
        self._old_surface: pygame.Surface | None = None
        self._new_surface: pygame.Surface | None = None

    @property
    def state(self) -> TransitionState:
        """Current lifecycle state."""
        return self._state

    @property
    def progress(self) -> float:
        """Raw progress from 0.0 to 1.0 (before easing)."""
        if self._duration <= 0:
            return 1.0
        return min(1.0, self._elapsed / self._duration)

    @property
    def eased_progress(self) -> float:
        """Eased progress from 0.0 to 1.0."""
        return self._easing_func(self.progress)

    def add_cue(self, progress: float, callback: Callable[[], None]) -> None:
        """Call callback once when raw progress first reaches progress.

        Cues fire in ascending progress order, before on_update, on the frame that reaches
        them; one large dt fires every cue it passes. A cue at 0.0 fires on the first update
        and a cue at 1.0 on the completing frame.

        Args:
            progress: Raw progress 0.0-1.0 at which to fire.
            callback: Called with no arguments.

        Raises:
            ValueError: If progress is outside 0.0-1.0.

        """
        if not 0.0 <= progress <= 1.0:
            message = f'progress must be between 0.0 and 1.0, got {progress}'
            raise ValueError(message)
        bisect.insort(
            self._cues,
            (progress, len(self._cues), callback),
            key=operator.itemgetter(0, 1),
        )

    def eased_velocity_at(self, progress: float) -> float:
        """Slope of the easing curve (d eased / d raw progress) at a raw progress.

        Uses a central difference, one-sided at 0.0 and 1.0.

        Args:
            progress: Raw progress 0.0-1.0.

        Returns:
            The slope; 1.0 everywhere for linear easing.

        """
        lower = max(0.0, progress - EASING_SLOPE_STEP)
        upper = min(1.0, progress + EASING_SLOPE_STEP)
        return (self._easing_func(upper) - self._easing_func(lower)) / (upper - lower)

    def start(
        self,
        old_surface: pygame.Surface,
        new_surface: pygame.Surface,
    ) -> None:
        """Begin the transition with captured scene screenshots.

        Args:
            old_surface: Screenshot of the outgoing scene.
            new_surface: Screenshot of the incoming scene.

        """
        self._old_surface = old_surface.copy()
        self._new_surface = new_surface.copy()
        self._elapsed = 0.0
        self._next_cue_index = 0
        self._state = TransitionState.RUNNING
        log.info(
            'Transition started: %s (%.1fs, %s)',
            type(self).__name__,
            self._duration,
            self._easing_name,
        )

    def update(self, dt: float) -> bool:
        """Advance the transition by dt seconds.

        Args:
            dt: Delta time in seconds.

        Returns:
            True when the transition is complete.

        """
        if self._state != TransitionState.RUNNING:
            return True

        self._elapsed += dt

        current_progress = self.progress
        while (
            self._next_cue_index < len(self._cues)
            and self._cues[self._next_cue_index][0] <= current_progress
        ):
            callback = self._cues[self._next_cue_index][2]
            self._next_cue_index += 1
            callback()
        if self._on_update is not None:
            self._on_update(self)

        if self._elapsed >= self._duration:
            self._state = TransitionState.COMPLETE
            log.info('Transition complete: %s', type(self).__name__)
            return True

        return False

    def render(self, screen: pygame.Surface) -> None:
        """Render the current transition frame to the screen.

        Args:
            screen: The display surface to render onto.

        """
        if self._old_surface is None or self._new_surface is None:
            return

        self._render_frame(screen, self._old_surface, self._new_surface)

    def _render_frame(
        self,
        screen: pygame.Surface,
        old_surface: pygame.Surface,  # ruff: ignore[unused-method-argument]
        new_surface: pygame.Surface,
    ) -> None:
        """Render one frame of the transition effect.

        Subclasses must override this to implement the visual effect.

        Args:
            screen: The display surface.
            old_surface: Screenshot of the outgoing scene.
            new_surface: Screenshot of the incoming scene.

        """
        # Default: instant cut to new scene
        screen.blit(new_surface, (0, 0))
