"""The game's tests run on its own display size: 800x480, as the game runs by default."""

from __future__ import annotations

import pygame
import pytest

from glitchygames.display_mode import set_display_mode

SCREEN_SIZE = (800, 480)


@pytest.fixture(autouse=True)
def display():
    """The game's display: 800x480."""
    if not pygame.get_init():
        pygame.init()
    surface = pygame.display.get_surface()
    if surface is None or surface.get_size() != SCREEN_SIZE:
        set_display_mode(size=SCREEN_SIZE)
