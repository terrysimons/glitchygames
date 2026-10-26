"""A message centred over a dimmed picture of the game: the pause screen's look, shared.

``MessageScreen`` is the one drawing path for "pause-style message over the game": the pause
screen (glitchygames/scenes/builtin_scenes/pause_scene.py) draws its ``PAUSED`` with it, and the
watched replay's start screen (glitchygames/replay/controls.py) is a subclass that changes the
message and the look and adds a smaller hint line under the message. A subclass changes only the
class attributes (and ``hint_text`` for a hint worked out at draw time).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Self

import pygame

from glitchygames.color import BLACK, WHITE

if TYPE_CHECKING:
    from pathlib import Path


class MessageScreen:
    """Draws a centred message (and an optional hint line under it) over a dimmed surface.

    The defaults are the pause screen's look: the whole surface dimmed with black at alpha 128,
    then ``PAUSED`` in pygame's default font at size 72, white, centred on the surface. Fonts and
    rendered text are made on the first draw and reused, so drawing every frame costs blits only.

    Attributes:
        MESSAGE: The message, centred on the surface.
        MESSAGE_FONT_PATH: The message's font file, or None for pygame's default font.
        MESSAGE_FONT_SIZE: The message's font size.
        MESSAGE_COLOR: The message's colour.
        HINT_FONT_PATH: The hint line's font file, or None for pygame's default font.
        HINT_FONT_SIZE: The hint line's font size.
        HINT_COLOR: The hint line's colour.
        HINT_GAP: Pixels between the message's bottom and the hint line's top.
        DIM_COLOR: The colour laid over the whole surface.
        DIM_ALPHA: How opaque that colour is (0-255).

    """

    MESSAGE: ClassVar[str] = 'PAUSED'
    MESSAGE_FONT_PATH: ClassVar[Path | None] = None
    MESSAGE_FONT_SIZE: ClassVar[int] = 72
    MESSAGE_COLOR: ClassVar[tuple[int, int, int]] = WHITE
    HINT_FONT_PATH: ClassVar[Path | None] = None
    HINT_FONT_SIZE: ClassVar[int] = 24
    HINT_COLOR: ClassVar[tuple[int, int, int]] = WHITE
    HINT_GAP: ClassVar[int] = 16
    DIM_COLOR: ClassVar[tuple[int, int, int]] = BLACK
    DIM_ALPHA: ClassVar[int] = 128

    def __init__(self: Self) -> None:
        """Prepare the screen; fonts and text are made on the first draw."""
        self._message_surface: pygame.Surface | None = None
        self._hint_surface: pygame.Surface | None = None
        self._rendered_hint: str | None = None
        # The dimming layer, kept for the size it was made for
        self._dim_surface: pygame.Surface | None = None

    def hint_text(self: Self) -> str | None:
        """Return the smaller line drawn under the message (none on the pause screen).

        Returns:
            The hint, or None for no hint line.

        """
        return None

    def render(
        self: Self, *, backdrop: pygame.Surface, area_size: tuple[int, int] | None = None
    ) -> pygame.Surface:
        """Return a copy of ``backdrop`` with the screen drawn over it.

        Args:
            backdrop: The picture of the game (left unchanged).
            area_size: The (width, height) dimmed and centred on, from the top-left corner;
                None for the backdrop's own size.

        Returns:
            The new surface.

        """
        image = backdrop.copy()
        self.draw(surface=image, area_size=area_size)
        return image

    def draw(
        self: Self, *, surface: pygame.Surface, area_size: tuple[int, int] | None = None
    ) -> None:
        """Dim ``surface``, then draw the message centred on it and the hint line under it.

        Args:
            surface: The surface to draw onto (changed in place).
            area_size: The (width, height) dimmed and centred on, from the top-left corner;
                None for the surface's own size (the pause screen passes the game's screen
                size, which a custom screenshot need not have).

        """
        size = surface.get_size() if area_size is None else area_size
        surface.blit(self._dimming_layer(size=size), (0, 0))
        message_rect, hint_rect = self.text_rects(size=size)
        surface.blit(self._message(), message_rect)
        hint_surface = self._hint()
        if hint_surface is not None and hint_rect is not None:
            surface.blit(hint_surface, hint_rect)

    def text_rects(self: Self, *, size: tuple[int, int]) -> tuple[pygame.Rect, pygame.Rect | None]:
        """Return where the message and the hint line go on a surface of ``size``.

        Args:
            size: The surface's (width, height).

        Returns:
            The message's rect, centred on the surface, and the hint line's rect, centred
            horizontally ``HINT_GAP`` pixels under the message (None without a hint).

        """
        width, height = size
        message_rect = self._message().get_rect()
        message_rect.center = (width // 2, height // 2)
        hint_surface = self._hint()
        if hint_surface is None:
            return message_rect, None
        hint_rect = hint_surface.get_rect()
        hint_rect.midtop = (width // 2, message_rect.bottom + self.HINT_GAP)
        return message_rect, hint_rect

    def _message(self: Self) -> pygame.Surface:
        if self._message_surface is None:
            font = pygame.font.Font(self.MESSAGE_FONT_PATH, self.MESSAGE_FONT_SIZE)
            self._message_surface = font.render(
                self.MESSAGE, antialias=True, color=self.MESSAGE_COLOR
            )
        return self._message_surface

    def _hint(self: Self) -> pygame.Surface | None:
        hint = self.hint_text()
        if hint is None:
            return None
        if self._hint_surface is None or hint != self._rendered_hint:
            font = pygame.font.Font(self.HINT_FONT_PATH, self.HINT_FONT_SIZE)
            self._hint_surface = font.render(hint, antialias=True, color=self.HINT_COLOR)
            self._rendered_hint = hint
        return self._hint_surface

    def _dimming_layer(self: Self, *, size: tuple[int, int]) -> pygame.Surface:
        if self._dim_surface is None or self._dim_surface.get_size() != size:
            self._dim_surface = pygame.Surface(size)
            self._dim_surface.fill(self.DIM_COLOR)
            self._dim_surface.set_alpha(self.DIM_ALPHA)
        return self._dim_surface
