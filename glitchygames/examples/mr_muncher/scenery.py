"""Mr. Muncher's still sprites (screen space: they never move) and its text helpers.

Sprockets sit on their tiles, pictures and text lines are centred on a point, and the side panels
are the edges of a film strip with lines of text and pictures on them.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Self

import pygame

from glitchygames.examples.mr_muncher import drawing
from glitchygames.fonts.font_manager import bundled_font_path
from glitchygames.sprites import Sprite

if TYPE_CHECKING:
    from glitchygames.examples.mr_muncher.actors import MazeGeometry

type Color = tuple[int, int, int]

# Fitted fonts never get smaller than this
SMALLEST_FONT_SIZE = 8
# A snack blinks: lit, then dark, this long each
SNACK_TWINKLE_SECONDS = 0.2


def bundled_font(*, bold: bool, size: int) -> pygame.font.Font:
    """Return a bundled Bitstream Vera font.

    Args:
        bold: Vera Bold rather than Vera.
        size: The point size.

    Returns:
        The font.

    """
    return pygame.font.Font(bundled_font_path(font_name='VeraBd' if bold else 'Vera'), size)


def fitted_font(
    *, bold: bool, texts: tuple[str, ...], width: int, largest: int
) -> pygame.font.Font:
    """Return the largest bundled font, up to a size, in which every text fits a width.

    Args:
        bold: Vera Bold rather than Vera.
        texts: The texts that must fit.
        width: The width they must fit, in pixels.
        largest: The largest size wanted.

    Returns:
        The font (SMALLEST_FONT_SIZE when even that is too wide).

    """
    for size in range(largest, SMALLEST_FONT_SIZE, -1):
        font = bundled_font(bold=bold, size=size)
        if all(font.size(text)[0] <= width for text in texts):
            return font
    return bundled_font(bold=bold, size=SMALLEST_FONT_SIZE)


def render_text(*, font: pygame.font.Font, text: str, color: Color) -> pygame.Surface:
    """Render a line of anti-aliased text.

    Args:
        font: The font.
        text: The text.
        color: Its colour.

    Returns:
        The rendered line (per-pixel alpha).

    """
    return font.render(text, antialias=True, color=color)


class Sprocket(Sprite):
    """A sprocket or snack (screen space: it never moves); hidden once eaten."""

    def __init__(
        self: Self,
        *,
        cell: tuple[int, int],
        is_snack: bool,
        geometry: MazeGeometry,
        layer: int,
        groups: pygame.sprite.LayeredDirty[Any],
    ) -> None:
        """Draw the sprocket centred on its tile.

        Args:
            cell: Its tile.
            is_snack: True for a snack.
            geometry: Where the maze is on screen.
            layer: The sprite layer.
            groups: The sprite group to add it to.

        """
        self._layer = layer
        self.cell = cell
        self.is_snack = is_snack
        self.tile_size = geometry.tile_size
        image = (
            drawing.snack_picture(tile_size=geometry.tile_size, lit=True)
            if is_snack
            else drawing.sprocket_picture(tile_size=geometry.tile_size)
        )
        centre_x, centre_y = geometry.pixel_centre(tile_x=cell[0], tile_y=cell[1])
        side = image.get_width()
        super().__init__(
            x=round(centre_x - side / 2),
            y=round(centre_y - side / 2),
            width=side,
            height=side,
            name='Snack' if is_snack else 'Sprocket',
            groups=groups,
        )
        self.image = image
        self.dirty = 2

    @property
    def eaten(self: Self) -> bool:
        """Whether the player has eaten it (it is then not drawn)."""
        return not self.visible

    def eat(self: Self) -> None:
        """Eat it: it is no longer drawn."""
        self.visible = 0

    def pose(self: Self, *, game_time: float) -> None:
        """Blink a snack (a plain sprocket never changes).

        Args:
            game_time: The scene's game time.

        """
        if self.is_snack:
            lit = math.floor(game_time / SNACK_TWINKLE_SECONDS) % 2 == 0
            self.image = drawing.snack_picture(tile_size=self.tile_size, lit=lit)


class Picture(Sprite):
    """A still picture or a line of text, centred on a point (screen space)."""

    def __init__(
        self: Self,
        *,
        image: pygame.Surface,
        centre: tuple[float, float],
        layer: int,
        name: str,
        groups: pygame.sprite.LayeredDirty[Any],
    ) -> None:
        """Show a picture centred on a point.

        Args:
            image: The picture.
            centre: Its centre, in pixels.
            layer: The sprite layer.
            name: Its name.
            groups: The sprite group to add it to.

        """
        self._layer = layer
        self.centre = centre
        super().__init__(
            x=0, y=0, width=image.get_width(), height=image.get_height(), name=name, groups=groups
        )
        self.dirty = 2
        self.change_image(image=image)

    def change_image(self: Self, *, image: pygame.Surface) -> None:
        """Show another picture, centred on the same point.

        Args:
            image: The picture.

        """
        self.image = image
        self.rect = image.get_rect(center=(round(self.centre[0]), round(self.centre[1])))

    def move_to(self: Self, *, centre: tuple[float, float]) -> None:
        """Centre the picture on another point.

        Args:
            centre: The new centre, in pixels.

        """
        self.centre = centre
        self.change_image(image=self.image)


class SidePanel(Sprite):
    """A side panel (the edge of a film strip) showing lines of text and pictures."""

    def __init__(
        self: Self,
        *,
        area: pygame.Rect,
        holes_on_left: bool,
        layer: int,
        groups: pygame.sprite.LayeredDirty[Any],
    ) -> None:
        """Make an empty panel covering an area of the screen.

        Args:
            area: The screen area it covers.
            holes_on_left: Put its sprocket holes along its left edge (else its right).
            layer: The sprite layer.
            groups: The sprite group to add it to.

        """
        self._layer = layer
        super().__init__(
            x=area.x,
            y=area.y,
            width=area.width,
            height=area.height,
            name='SidePanel',
            groups=groups,
        )
        self.holes_on_left = holes_on_left
        # The text column: the panel without its sprocket holes
        holes_width = drawing.SPROCKET_HOLE_MARGIN * 2 + drawing.SPROCKET_HOLE_WIDTH
        self.text_centre_x = (
            (holes_width + area.width) // 2 if holes_on_left else (area.width - holes_width) // 2
        )
        self.contents: tuple[object, ...] | None = None
        self.dirty = 2
        self.draw(contents=(), items=())

    def draw(
        self: Self,
        *,
        contents: tuple[object, ...],
        items: tuple[tuple[pygame.Surface, int], ...],
    ) -> None:
        """Redraw the panel.

        Args:
            contents: What the panel shows (callers redraw only when it changes).
            items: The pictures to draw (each centred on the text column) with their tops.

        """
        self.contents = contents
        panel = drawing.film_strip_panel(
            width=self.rect.width, height=self.rect.height, holes_on_left=self.holes_on_left
        ).copy()
        for picture, top in items:
            panel.blit(picture, (self.text_centre_x - picture.get_width() // 2, top))
        self.image = panel
