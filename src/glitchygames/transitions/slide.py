"""Slide scene transition.

Old scene slides out in one direction, new scene slides in from
the opposite side. Used for elevator rides, level progression, etc.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    import pygame

from glitchygames.transitions.base import Transition


class SlideTransition(Transition):
    """Directional slide: old scene pushes out, new scene pushes in.

    Args:
        direction: Slide direction ('up', 'down', 'left', 'right').
            'up' means old scene slides up and off, new slides in from below.
        duration: Transition duration in seconds.
        easing: Easing function name.

    """

    def __init__(
        self,
        direction: str = 'left',
        duration: float = 0.8,
        easing: str = 'ease_in_out_quad',
    ) -> None:
        """Initialize the slide transition."""
        super().__init__(duration=duration, easing=easing)
        self._direction = direction

    @override
    def _render_frame(
        self,
        screen: pygame.Surface,
        old_surface: pygame.Surface,
        new_surface: pygame.Surface,
    ) -> None:
        """Render the slide effect.

        Args:
            screen: Display surface.
            old_surface: Outgoing scene.
            new_surface: Incoming scene.

        """
        progress = self.eased_progress
        width = screen.get_width()
        height = screen.get_height()

        if self._direction == 'left':
            offset_x = int(-width * progress)
            screen.blit(old_surface, (offset_x, 0))
            screen.blit(new_surface, (offset_x + width, 0))

        elif self._direction == 'right':
            offset_x = int(width * progress)
            screen.blit(old_surface, (offset_x, 0))
            screen.blit(new_surface, (offset_x - width, 0))

        elif self._direction == 'up':
            offset_y = int(-height * progress)
            screen.blit(old_surface, (0, offset_y))
            screen.blit(new_surface, (0, offset_y + height))

        elif self._direction == 'down':
            offset_y = int(height * progress)
            screen.blit(old_surface, (0, offset_y))
            screen.blit(new_surface, (0, offset_y - height))
