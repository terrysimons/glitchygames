"""Root sprite class for Glitchy Games Engine.

This module contains the base RootSprite class that all Glitchy Games sprites
inherit from.
"""

from __future__ import annotations

import logging
from typing import Any, Self, cast, override

import pygame

from glitchygames.events import MouseEvents
from glitchygames.interfaces import SpriteInterface

LOG = logging.getLogger('game.sprites')


class RootSprite(MouseEvents, SpriteInterface, pygame.sprite.DirtySprite):
    """A root sprite class.  All Glitchy Games sprites inherit from this class."""

    log = LOG

    # Override pygame's optional property typing — GlitchyGames sprites always
    # have a valid image and rect after __init__, so the getter return types
    # narrow out None.  Setters keep the parent's wider parameter types to
    # satisfy LSP.

    @property
    @override
    def image(self) -> pygame.Surface:
        """Return the sprite image (always non-None for GlitchyGames sprites)."""
        return self._gg_image

    @image.setter
    def image(self, value: pygame.Surface | None) -> None:
        self._gg_image = cast('pygame.Surface', value)

    @property
    @override
    def rect(self) -> pygame.FRect | pygame.Rect:
        """Return the sprite rect (always non-None for GlitchyGames sprites)."""
        return self._gg_rect

    @rect.setter
    def rect(self, value: pygame.FRect | pygame.Rect | None) -> None:
        self._gg_rect = cast('pygame.FRect | pygame.Rect', value)

    def __init__(self: Self, groups: pygame.sprite.LayeredDirty[Any] | None = None) -> None:
        """Initialize a RootSprite.

        Args:
            groups (pygame.sprite.LayeredDirty[Any] | None): The sprite groups to add the sprite to.

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(groups)
        self._gg_rect = pygame.Rect(0, 0, 0, 0)
        self._gg_image = pygame.Surface((0, 0))  # Non-null placeholder; subclasses replace
