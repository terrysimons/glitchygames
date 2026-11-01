"""Wipe scene transition.

A progressive reveal where the new scene is unveiled directionally,
like a curtain being pulled. Unlike slide, the surfaces don't move —
a clipping rect grows to reveal the new scene.
"""

from __future__ import annotations

from typing import override

import pygame

from glitchygames.transitions.base import Transition, checked_direction


class WipeTransition(Transition):
    """Directional wipe reveal.

    The new scene is progressively revealed from one edge, covering
    the old scene. The surfaces stay in place — only the visible
    area changes.

    Args:
        direction: Wipe direction ('left', 'right', 'up', 'down').
            'left' reveals from the left edge moving right.
        duration: Transition duration in seconds.
        easing: Easing function name.

    Raises:
        ValueError: If direction is not one of the four above.

    """

    def __init__(
        self,
        direction: str = 'left',
        duration: float = 0.6,
        easing: str = 'ease_in_out_quad',
    ) -> None:
        """Initialize the wipe transition."""
        super().__init__(duration=duration, easing=easing)
        self._direction = checked_direction(direction)

    @override
    def _render_frame(
        self,
        screen: pygame.Surface,
        old_surface: pygame.Surface,
        new_surface: pygame.Surface,
    ) -> None:
        """Render the wipe effect.

        Args:
            screen: Display surface.
            old_surface: Outgoing scene.
            new_surface: Incoming scene.

        """
        progress = self.eased_progress
        width = screen.get_width()
        height = screen.get_height()

        # Draw old scene as the base
        screen.blit(old_surface, (0, 0))

        # Draw new scene clipped to the revealed area
        if self._direction == 'left':
            reveal_width = int(width * progress)
            clip_rect = pygame.Rect(0, 0, reveal_width, height)
        elif self._direction == 'right':
            reveal_width = int(width * progress)
            clip_x = width - reveal_width
            clip_rect = pygame.Rect(clip_x, 0, reveal_width, height)
        elif self._direction == 'up':
            # Typo-free: 'up' reveals from top moving downward
            reveal_height = int(height * progress)
            clip_rect = pygame.Rect(0, 0, width, reveal_height)
        elif self._direction == 'down':
            reveal_height = int(height * progress)
            clip_y = height - reveal_height
            clip_rect = pygame.Rect(0, clip_y, width, reveal_height)
        else:
            clip_rect = pygame.Rect(0, 0, width, height)

        # Blit only the revealed portion of the new scene
        screen.blit(new_surface, clip_rect.topleft, area=clip_rect)
