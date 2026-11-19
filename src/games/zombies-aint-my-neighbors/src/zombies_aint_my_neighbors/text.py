"""Text for the game's screens: the bundled bold font, rendered lines and a centred picture.

Text is rendered once, when a scene is set up, and shown as sprites: a ``TextPicture`` swaps
between images made in advance and is shown or hidden, so no frame renders text (master plan,
decision 11). The shape follows Mr. Muncher's ``Picture`` (src/games/mr-muncher/src/mr_muncher/
scenery.py); this game keeps its own copy, since a member never imports another member's code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

import pygame

from glitchygames.fonts import FontManager
from glitchygames.fonts.font_manager import bundled_font_path
from glitchygames.sprites import Sprite

if TYPE_CHECKING:
    from collections.abc import Sequence

type Colour = tuple[int, int, int]

# Fonts never get smaller than this when fitted to a width
SMALLEST_FONT_SIZE = 8
# The space between stacked lines of text, in pixels
LINE_GAP = 4


def title_font(*, size: int) -> pygame.font.Font:
    """Return the bundled Bitstream Vera Bold at a size.

    Uncached on purpose: a scene asks once per size in ``setup()`` and keeps the font, so no
    module-level state exists for the process-state guard to flag.

    Args:
        size: The point size.

    Returns:
        The font.

    """
    return pygame.font.Font(bundled_font_path(font_name='VeraBd'), size)


def fitted_title_font(*, texts: Sequence[str], width: int, largest: int) -> pygame.font.Font:
    """Return the largest bold font, up to a size, in which every text fits a width.

    Args:
        texts: The texts that must fit.
        width: The width they must fit, in pixels.
        largest: The largest size wanted.

    Returns:
        The font (``SMALLEST_FONT_SIZE`` when even that is too wide).

    """
    for size in range(largest, SMALLEST_FONT_SIZE, -1):
        font = title_font(size=size)
        if all(font.size(line)[0] <= width for line in texts):
            return font
    return title_font(size=SMALLEST_FONT_SIZE)


def render_text(*, font: pygame.font.Font, text: str, colour: Colour) -> pygame.Surface:
    """Render a line of text, antialiased as the engine's fonts are.

    Args:
        font: The font.
        text: The text.
        colour: Its colour.

    Returns:
        The rendered line (per-pixel alpha).

    """
    return font.render(text, antialias=FontManager.antialias(), color=colour)


def render_lines(*, font: pygame.font.Font, lines: Sequence[str], colour: Colour) -> pygame.Surface:
    """Render lines of text stacked and centred on one transparent image.

    Args:
        font: The font.
        lines: The lines, top to bottom.
        colour: Their colour.

    Returns:
        The image (per-pixel alpha).

    """
    rendered = [render_text(font=font, text=line, colour=colour) for line in lines]
    width = max(line.get_width() for line in rendered)
    height = sum(line.get_height() for line in rendered) + LINE_GAP * (len(rendered) - 1)
    image = pygame.Surface((width, height), pygame.SRCALPHA)
    top = 0
    for line in rendered:
        image.blit(line, ((width - line.get_width()) // 2, top))
        top += line.get_height() + LINE_GAP
    return image


class TextPicture(Sprite):
    """A picture (usually text) centred on a point, in screen space, that can be hidden."""

    def __init__(
        self: Self,
        *,
        image: pygame.Surface,
        centre: tuple[int, int],
        name: str,
        groups: pygame.sprite.LayeredDirty[Any],
    ) -> None:
        """Show a picture centred on a point.

        Args:
            image: The picture.
            centre: Its centre, in pixels.
            name: Its name.
            groups: The sprite group to add it to.

        """
        self.centre = centre
        super().__init__(
            x=0, y=0, width=image.get_width(), height=image.get_height(), name=name, groups=groups
        )
        self.dirty = 2
        self.show_image(image=image)

    def show_image(self: Self, *, image: pygame.Surface) -> None:
        """Show another picture, centred on the same point (nothing changes if it is shown).

        Args:
            image: The picture.

        """
        if getattr(self, 'image', None) is image:
            return
        self.image = image
        self.rect = image.get_rect(center=self.centre)

    def set_shown(self: Self, *, shown: bool) -> None:
        """Show or hide the picture, writing ``visible`` only when it changes.

        Args:
            shown: Whether it is shown.

        """
        visible = 1 if shown else 0
        if self.visible != visible:
            self.visible = visible
