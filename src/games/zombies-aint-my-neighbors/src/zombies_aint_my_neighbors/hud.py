"""The heads-up display: each player's lives, the stage and the neighbors rescued.

Feature plan 7 (plans/2026-11-15-zombies-aint-my-neighbors-7-neighbors-and-lives.md), Task 9.
Screen-space text pictures (every object is a sprite, CLAUDE.md) drawn over the yard. Along the
top, each joined slot shows ``P1``, a multiplication sign and its lives (``P1 x3``, drawn with
the real sign) in its colour, or ``P1 OUT`` with none left; a free slot shows nothing. At the
bottom: ``STAGE n   NEIGHBORS rescued/total``. Every lives label is rendered once, when the
display is made (master plan decision 11); the status line renders only when it changes, which
is only on a rescue. The multiplication sign rather than a heart: the bundled font covers
Latin-1, and a heart could draw as a missing-glyph box.

Feature plan 8 adds, under each joined player's lives, the weapon held (``ZAP`` or ``LASER``)
and the laser's battery as a bar in the player's colour, grey while the battery is dead. Every
label and every bar (each tenth of a second of charge, alive or dead) is drawn when the display
is made.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

import pygame

from glitchygames.fonts import font_manager
from zombies_aint_my_neighbors import text
from zombies_aint_my_neighbors.kid import Weapon
from zombies_aint_my_neighbors.roster import MAXIMUM_PLAYERS, PLAYER_COLOURS
from zombies_aint_my_neighbors.run_state import LIVES_PER_PLAYER

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from zombies_aint_my_neighbors.kid import Kid
    from zombies_aint_my_neighbors.run_state import RunState

HUD_FONT_SIZE: Final = 16
# Drawn over every world sprite (their layers are their feet's rows, under 1000)
HUD_LAYER: Final = 100_000
# How far the labels sit from the screen's top and bottom edges
EDGE_MARGIN: Final = 14
STATUS_COLOUR: Final = (230, 230, 210)
# Feature plan 8: the weapon's label and the battery bar, under each player's lives
WEAPON_FONT_SIZE: Final = 12
# Read-only: module state shared by every engine context (tests/test_process_state_guard.py)
WEAPON_LABELS: Final = MappingProxyType({
    Weapon.CHANNEL_CHANGER: 'ZAP',
    Weapon.LASER_POINTER: 'LASER',
})
WEAPON_ROW: Final = EDGE_MARGIN + 16
BATTERY_ROW: Final = EDGE_MARGIN + 29
BATTERY_WIDTH: Final = 40
BATTERY_HEIGHT: Final = 5
# The bar shows the charge in tenths of a second: FULL_SECONDS (3.0) is 30 of them
BATTERY_STEPS: Final = 30
DEAD_COLOUR: Final = (110, 110, 110)
BAR_FRAME_COLOUR: Final = (24, 16, 32)


def lives_label(*, slot_index: int, lives: int) -> str:
    """Return a slot's lives label: P1, a multiplication sign and the lives, or ``P1 OUT``.

    Returns:
        The label.

    """
    count = f'\N{MULTIPLICATION SIGN}{lives}' if lives else 'OUT'
    return f'P{slot_index + 1} {count}'


def battery_bar(*, steps: int, dead: bool, colour: tuple[int, int, int]) -> pygame.Surface:
    """Return a battery bar: a dark frame, filled a share of its width in a colour.

    Args:
        steps: How full, in tenths of a second (0 to ``BATTERY_STEPS``).
        dead: Whether the battery is dead (the fill is grey).
        colour: The player's colour.

    Returns:
        The bar.

    """
    bar = pygame.Surface((BATTERY_WIDTH, BATTERY_HEIGHT))
    bar.fill(BAR_FRAME_COLOUR)
    inner_width = BATTERY_WIDTH - 2
    filled = round(inner_width * steps / BATTERY_STEPS)
    if filled:
        bar.fill(DEAD_COLOUR if dead else colour, pygame.Rect(1, 1, filled, BATTERY_HEIGHT - 2))
    return bar


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
        self._font = font_manager.bundled_font(bold=True, size=HUD_FONT_SIZE)
        self._groups = groups
        # Each slot's label for each count of lives, rendered now
        self._lives_images = [
            {
                lives: font_manager.render_line(
                    font=self._font,
                    text=lives_label(slot_index=slot_index, lives=lives),
                    color=colour,
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
            image=font_manager.render_line(font=self._font, text=' ', color=STATUS_COLOUR),
            centre=(screen_width // 2, screen_height - EDGE_MARGIN),
            name='Stage status',
            groups=groups,
        )
        weapon_font = font_manager.bundled_font(bold=True, size=WEAPON_FONT_SIZE)
        self._weapon_images = [
            {
                weapon: font_manager.render_line(font=weapon_font, text=label, color=colour)
                for weapon, label in WEAPON_LABELS.items()
            }
            for colour in PLAYER_COLOURS
        ]
        self._battery_images = [
            {
                (steps, dead): battery_bar(steps=steps, dead=dead, colour=colour)
                for steps in range(BATTERY_STEPS + 1)
                for dead in (False, True)
            }
            for colour in PLAYER_COLOURS
        ]
        self._weapon_texts = [WEAPON_LABELS[Weapon.CHANNEL_CHANGER]] * MAXIMUM_PLAYERS
        self._battery_shown = [(BATTERY_STEPS, False)] * MAXIMUM_PLAYERS
        self._weapon_pictures = [
            text.TextPicture(
                image=self._weapon_images[slot_index][Weapon.CHANNEL_CHANGER],
                centre=(column_width * slot_index + column_width // 2, WEAPON_ROW),
                name=f'Weapon P{slot_index + 1}',
                groups=groups,
            )
            for slot_index in range(MAXIMUM_PLAYERS)
        ]
        self._battery_pictures = [
            text.TextPicture(
                image=self._battery_images[slot_index][BATTERY_STEPS, False],
                centre=(column_width * slot_index + column_width // 2, BATTERY_ROW),
                name=f'Battery P{slot_index + 1}',
                groups=groups,
            )
            for slot_index in range(MAXIMUM_PLAYERS)
        ]
        for picture in (
            *self._lives_pictures,
            self._status_picture,
            *self._weapon_pictures,
            *self._battery_pictures,
        ):
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

    def weapon_text(self, *, slot_index: int) -> str:
        """Return the weapon label a slot shows.

        Returns:
            ``ZAP`` or ``LASER``.

        """
        return self._weapon_texts[slot_index]

    def weapon_picture(self, *, slot_index: int) -> text.TextPicture:
        """Return a slot's weapon picture.

        Returns:
            The picture.

        """
        return self._weapon_pictures[slot_index]

    def battery_shown(self, *, slot_index: int) -> tuple[float, bool]:
        """Return the battery a slot's bar shows: how full (in tenths of a second), and dead.

        Returns:
            (fraction full, whether dead).

        """
        steps, dead = self._battery_shown[slot_index]
        return (steps / BATTERY_STEPS, dead)

    def battery_picture(self, *, slot_index: int) -> text.TextPicture:
        """Return a slot's battery bar.

        Returns:
            The picture.

        """
        return self._battery_pictures[slot_index]

    def show(
        self,
        *,
        run: RunState,
        joined_slots: Collection[int],
        rescued: int,
        total: int,
        kids: Mapping[int, Kid] | None = None,
    ) -> None:
        """Show the run's lives for the joined slots, their weapons and batteries, and progress.

        Args:
            run: The run (its stage and lives).
            joined_slots: The slots a player holds.
            rescued: Neighbors rescued this stage.
            total: Neighbors the stage began with.
            kids: Each joined slot's kid (its weapon and battery; feature plan 8).

        """
        for slot_index in range(MAXIMUM_PLAYERS):
            kid = (kids or {}).get(slot_index)
            shown = slot_index in joined_slots and kid is not None
            self._weapon_pictures[slot_index].set_shown(shown=shown)
            self._battery_pictures[slot_index].set_shown(shown=shown)
            if kid is None:
                continue
            self._weapon_texts[slot_index] = WEAPON_LABELS[kid.weapon]
            self._weapon_pictures[slot_index].show_image(
                image=self._weapon_images[slot_index][kid.weapon]
            )
            steps = min(BATTERY_STEPS, max(0, round(kid.battery.charge_seconds * 10)))
            self._battery_shown[slot_index] = (steps, kid.battery.is_dead)
            self._battery_pictures[slot_index].show_image(
                image=self._battery_images[slot_index][steps, kid.battery.is_dead]
            )
        for slot_index, picture in enumerate(self._lives_pictures):
            lives = run.lives[slot_index]
            picture.show_image(image=self._lives_images[slot_index][lives])
            picture.set_shown(shown=slot_index in joined_slots)
            self._lives_texts[slot_index] = lives_label(slot_index=slot_index, lives=lives)
        status = f'STAGE {run.stage}   NEIGHBORS {rescued}/{total}'
        if status != self.status_text:
            self.status_text = status
            self._status_picture.show_image(
                image=font_manager.render_line(font=self._font, text=status, color=STATUS_COLOUR)
            )
