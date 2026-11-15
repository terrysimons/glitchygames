"""The heads-up display: each player's lives, the stage and the neighbors rescued.

Feature plan 7 (plans/2026-11-15-zombies-aint-my-neighbors-7-neighbors-and-lives.md), Task 9.
Screen-space text pictures (every object is a sprite, CLAUDE.md) drawn over the yard. Along the
top, each joined slot shows ``P1``, a multiplication sign and its lives (``P1 x3``, drawn with
the real sign) in its colour, or ``P1 OUT`` with none left; a free slot shows nothing. At the
bottom: ``STAGE n   NEIGHBORS rescued/total``. Every lives label is rendered once, when the
display is made (master plan decision 11); the status line renders only when it changes, which
is only on a rescue. The multiplication sign rather than a heart: the bundled font covers
Latin-1, and a heart could draw as a missing-glyph box.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from zombies_aint_my_neighbors import text
from zombies_aint_my_neighbors.roster import MAXIMUM_PLAYERS, PLAYER_COLOURS
from zombies_aint_my_neighbors.run_state import LIVES_PER_PLAYER

if TYPE_CHECKING:
    from collections.abc import Collection

    import pygame

    from zombies_aint_my_neighbors.run_state import RunState

HUD_FONT_SIZE: Final = 16
# Drawn over every world sprite (their layers are their feet's rows, under 1000)
HUD_LAYER: Final = 100_000
# How far the labels sit from the screen's top and bottom edges
EDGE_MARGIN: Final = 14
STATUS_COLOUR: Final = (230, 230, 210)


def lives_label(*, slot_index: int, lives: int) -> str:
    """Return a slot's lives label: P1, a multiplication sign and the lives, or ``P1 OUT``.

    Returns:
        The label.

    """
    count = f'\N{MULTIPLICATION SIGN}{lives}' if lives else 'OUT'
    return f'P{slot_index + 1} {count}'


class Hud:
    """The lives along the top and the stage's progress along the bottom."""

    def __init__(
        self, *, screen_width: int, screen_height: int, groups: pygame.sprite.LayeredDirty[Any]
    ) -> None:
        """Render every lives label and make the pictures, over the yard.

        Args:
            screen_width: The screen's width.
            screen_height: The screen's height.
            groups: The scene's sprites.

        """
        self._font = text.title_font(size=HUD_FONT_SIZE)
        self._groups = groups
        # Each slot's label for each count of lives, rendered now
        self._lives_images = [
            {
                lives: text.render_text(
                    font=self._font,
                    text=lives_label(slot_index=slot_index, lives=lives),
                    colour=colour,
                )
                for lives in range(LIVES_PER_PLAYER + 1)
            }
            for slot_index, colour in enumerate(PLAYER_COLOURS)
        ]
        column_width = screen_width // MAXIMUM_PLAYERS
        self._lives_pictures = [
            text.TextPicture(
                image=self._lives_images[slot_index][LIVES_PER_PLAYER],
                centre=(column_width * slot_index + column_width // 2, EDGE_MARGIN),
                name=f'Lives P{slot_index + 1}',
                groups=groups,
            )
            for slot_index in range(MAXIMUM_PLAYERS)
        ]
        self._lives_texts = [
            lives_label(slot_index=slot_index, lives=LIVES_PER_PLAYER)
            for slot_index in range(MAXIMUM_PLAYERS)
        ]
        self.status_text = ''
        self._status_picture = text.TextPicture(
            image=text.render_text(font=self._font, text=' ', colour=STATUS_COLOUR),
            centre=(screen_width // 2, screen_height - EDGE_MARGIN),
            name='Stage status',
            groups=groups,
        )
        for picture in (*self._lives_pictures, self._status_picture):
            groups.change_layer(picture, HUD_LAYER)

    def lives_text(self, *, slot_index: int) -> str:
        """Return the lives label a slot shows.

        Returns:
            The label.

        """
        return self._lives_texts[slot_index]

    def lives_picture(self, *, slot_index: int) -> text.TextPicture:
        """Return a slot's lives picture.

        Returns:
            The picture.

        """
        return self._lives_pictures[slot_index]

    def show(
        self, *, run: RunState, joined_slots: Collection[int], rescued: int, total: int
    ) -> None:
        """Show the run's lives for the joined slots, and the stage's progress.

        Args:
            run: The run (its stage and lives).
            joined_slots: The slots a player holds.
            rescued: Neighbors rescued this stage.
            total: Neighbors the stage began with.

        """
        for slot_index, picture in enumerate(self._lives_pictures):
            lives = run.lives[slot_index]
            picture.show_image(image=self._lives_images[slot_index][lives])
            picture.set_shown(shown=slot_index in joined_slots)
            self._lives_texts[slot_index] = lives_label(slot_index=slot_index, lives=lives)
        status = f'STAGE {run.stage}   NEIGHBORS {rescued}/{total}'
        if status != self.status_text:
            self.status_text = status
            self._status_picture.show_image(
                image=text.render_text(font=self._font, text=status, colour=STATUS_COLOUR)
            )
