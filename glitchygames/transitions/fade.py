"""Fade and crossfade scene transitions.

FadeTransition: fade to a solid color, then reveal the new scene.
CrossfadeTransition: alpha-blend the old scene into the new scene.
"""

from __future__ import annotations

from typing import override

import pygame

from glitchygames.transitions.base import Transition


class FadeTransition(Transition):
    """Fade through a solid color (default black).

    First half: old scene fades to the color.
    Second half: color fades to reveal new scene.

    Args:
        duration: Total transition duration in seconds.
        color: The intermediate color (default black).
        easing: Easing function name.

    """

    def __init__(
        self,
        duration: float = 0.5,
        color: tuple[int, int, int] = (0, 0, 0),
        easing: str = 'ease_in_out_quad',
    ) -> None:
        """Initialize the fade transition."""
        super().__init__(duration=duration, easing=easing)
        self._color = color
        self._overlay: pygame.Surface | None = None

    @override
    def start(
        self,
        old_surface: pygame.Surface,
        new_surface: pygame.Surface,
    ) -> None:
        """Begin the fade transition."""
        super().start(old_surface, new_surface)
        self._overlay = pygame.Surface(old_surface.get_size())
        self._overlay.fill(self._color)

    @override
    def _render_frame(
        self,
        screen: pygame.Surface,
        old_surface: pygame.Surface,
        new_surface: pygame.Surface,
    ) -> None:
        """Render the fade effect.

        Args:
            screen: Display surface.
            old_surface: Outgoing scene.
            new_surface: Incoming scene.

        """
        if self._overlay is None:
            return

        progress = self.eased_progress
        halfway = 0.5

        if progress < halfway:
            # First half: old scene → solid color
            fade_alpha = int(255 * (progress / halfway))
            screen.blit(old_surface, (0, 0))
            self._overlay.set_alpha(fade_alpha)
            screen.blit(self._overlay, (0, 0))
        else:
            # Second half: solid color → new scene
            fade_alpha = int(255 * ((1.0 - progress) / halfway))
            screen.blit(new_surface, (0, 0))
            self._overlay.set_alpha(fade_alpha)
            screen.blit(self._overlay, (0, 0))


class CrossfadeTransition(Transition):
    """Alpha-blend the old scene directly into the new scene.

    Args:
        duration: Transition duration in seconds.
        easing: Easing function name.

    """

    @override
    def _render_frame(
        self,
        screen: pygame.Surface,
        old_surface: pygame.Surface,
        new_surface: pygame.Surface,
    ) -> None:
        """Render the crossfade effect.

        Args:
            screen: Display surface.
            old_surface: Outgoing scene.
            new_surface: Incoming scene.

        """
        alpha = int(255 * self.eased_progress)

        screen.blit(old_surface, (0, 0))
        new_surface.set_alpha(alpha)
        screen.blit(new_surface, (0, 0))
        new_surface.set_alpha(255)  # Reset so future renders aren't affected
