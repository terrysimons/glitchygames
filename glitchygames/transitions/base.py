"""Base class for scene transitions.

Transitions capture screenshots of old and new scenes, then render
a composited animation between them for a duration. Scenes are NOT
live during the transition -- just surfaces being blended.

Subclasses implement start(), update(), and render() to define
the visual effect.
"""

from __future__ import annotations

import enum
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pygame

from glitchygames.effects.easing import get_easing

log: logging.Logger = logging.getLogger('game.transitions')


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

    """

    def __init__(
        self,
        duration: float = 0.5,
        easing: str = 'ease_in_out_quad',
    ) -> None:
        """Initialize the transition."""
        self._duration = duration
        self._easing_name = easing
        self._easing_func = get_easing(easing)
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
