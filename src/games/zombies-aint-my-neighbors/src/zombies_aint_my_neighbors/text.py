"""Text for the game's screens: stacked lines of text and a centred picture.

Fonts and single lines come from the engine (``glitchygames.fonts.font_manager``: ``bundled_font``,
``fitted_font``, ``render_line``); this game asks for the bold font.

Text is rendered once, when a scene is set up, and shown as sprites: a ``TextPicture`` swaps
between images made in advance and is shown or hidden, so no frame renders text (master plan,
decision 11). The shape follows Mr. Muncher's ``Picture`` (src/games/mr-muncher/src/mr_muncher/
scenery.py); this game keeps its own copy, since a member never imports another member's code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

import pygame

from glitchygames.fonts import font_manager
from glitchygames.sprites import Sprite

if TYPE_CHECKING:
    from collections.abc import Sequence

type Colour = tuple[int, int, int]

# The game's name: the window's title on the title, a stage and the game over, and the start of
# every other scene's, "<game name> - <part>" (an f-string in each scene's NAME, which the
# process-state guard reads as immutable; tests/test_process_state_guard.py)
GAME_NAME = "Zombies Ain't My Neighbors"
# The space between stacked lines of text, in pixels
LINE_GAP = 4


def render_lines(*, font: pygame.font.Font, lines: Sequence[str], colour: Colour) -> pygame.Surface:
    """Render lines of text stacked and centred on one transparent image.

    Args:
        font: The font.
        lines: The lines, top to bottom.
        colour: Their colour.

    Returns:
        The image (per-pixel alpha).

    """
    rendered = [font_manager.render_line(font=font, text=line, color=colour) for line in lines]
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
