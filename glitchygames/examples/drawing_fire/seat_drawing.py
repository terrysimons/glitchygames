"""Drawing the seats in pencil: the join note, each player's card, and the choosing highlight.

Kept apart from ``drawing`` (which draws the battle) so neither grows too long. The same rules
hold: text is rendered once per content (``drawing.text_surface``), fonts are made once, and a
hand-drawn line wanders by ``drawing.wobble``, never by a random stream.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from glitchygames.examples.drawing_fire.battle import ARMY_NAMES, Side
from glitchygames.examples.drawing_fire.drawing import (
    ARMY_COLORS,
    HATCH_COLOR,
    PENCIL_COLOR,
    SANDBAG_WASH_COLOR,
    text_surface,
    wobble,
)
from glitchygames.examples.drawing_fire.seats import SideChoice, Stage

if TYPE_CHECKING:
    from glitchygames.examples.drawing_fire.battle import Soldier
    from glitchygames.examples.drawing_fire.drawing import Color
    from glitchygames.examples.drawing_fire.seats import PlayerSeat

# A pale sticky note and a white index card, both unlike the paper and either army's colour
NOTE_COLOR: Color = (255, 241, 168)
CARD_COLOR: Color = (255, 255, 255)
# The note sits in the bottom-left corner, below the ground; the cards follow it to the right
SEAT_MARGIN_PIXELS = 10
SEAT_GAP_PIXELS = 8
SEAT_PADDING_PIXELS = 6
SEAT_LINE_GAP_PIXELS = 1
NOTE_TITLE_FONT_SIZE = 18
NOTE_FONT_SIZE = 13
NOTE_LINES = ('Press START to join!', 'Enter on the keyboard', 'and take over a soldier')
NOTE_TAPE_SIZE = (36, 8)
# A card holds a title and three lines (the side card is the tallest)
CARD_SIZE = (160, 80)
CARD_FONT_SIZE = 13
# The chosen line on a side card is marked by a pointer this wide (px) and a wash behind it
CARD_POINTER_PIXELS = 6
SIDE_CHOICE_TEXTS = {
    SideChoice.RANDOM: 'Random',
    SideChoice.PLATOON: ARMY_NAMES[Side.PLATOON],
    SideChoice.BRIGADE: ARMY_NAMES[Side.BRIGADE],
}
SIDE_CHOICE_WASHES: dict[SideChoice, Color] = {
    SideChoice.RANDOM: HATCH_COLOR,
    SideChoice.PLATOON: ARMY_COLORS[Side.PLATOON],
    SideChoice.BRIGADE: ARMY_COLORS[Side.BRIGADE],
}

# The highlight is a hand-drawn ring round the soldier's body, his chooser's name above it
HIGHLIGHT_CENTER_ABOVE_FEET = 18
HIGHLIGHT_RADII = (17, 26)
HIGHLIGHT_POINTS = 16
# The pencil runs on past where it started, as a hand drawing a circle does (points)
HIGHLIGHT_OVERSHOOT_POINTS = 3
HIGHLIGHT_LINE_WIDTH = 2
HIGHLIGHT_LABEL_GAP_PIXELS = 4
HIGHLIGHT_FONT_SIZE = 14
# Salt for the ring's wobble (drawing's own salts are 1 to 7)
SALT_HIGHLIGHT = 8


def join_note_rect(surface: pygame.Surface) -> pygame.Rect:
    """Find where the join note goes: the bottom-left corner, sized to its text.

    Returns:
        The note's rectangle.

    """
    lines = _note_lines()
    width = max(line.get_width() for line in lines) + 2 * SEAT_PADDING_PIXELS
    height = sum(line.get_height() + SEAT_LINE_GAP_PIXELS for line in lines) + (
        2 * SEAT_PADDING_PIXELS
    )
    note = pygame.Rect(0, 0, width, height)
    note.bottomleft = (SEAT_MARGIN_PIXELS, surface.get_height() - SEAT_MARGIN_PIXELS)
    return note


def seat_card_rect(surface: pygame.Surface, *, slot: int) -> pygame.Rect:
    """Find where a player's card goes: in a row to the right of the join note.

    Args:
        surface: Where the cards are drawn.
        slot: Which card in the row (0 first).

    Returns:
        The card's rectangle.

    """
    note = join_note_rect(surface)
    card = pygame.Rect((0, 0), CARD_SIZE)
    card.bottomleft = (
        note.right + SEAT_GAP_PIXELS + slot * (CARD_SIZE[0] + SEAT_GAP_PIXELS),
        note.bottom,
    )
    return card


def _note_lines() -> tuple[pygame.Surface, ...]:
    """Render the note's lines (each once: text_surface keeps them).

    Returns:
        The title, then the smaller lines.

    """
    title, *rest = NOTE_LINES
    return (
        text_surface(title, size=NOTE_TITLE_FONT_SIZE),
        *(text_surface(line, size=NOTE_FONT_SIZE) for line in rest),
    )


def _blit_lines(
    surface: pygame.Surface, lines: tuple[pygame.Surface, ...], *, topleft: tuple[int, int]
) -> None:
    """Write lines one under another."""
    left, top = topleft
    for line in lines:
        surface.blit(line, (left, top))
        top += line.get_height() + SEAT_LINE_GAP_PIXELS


def draw_join_prompt(surface: pygame.Surface) -> None:
    """Stick the "Press START to join!" note on the paper, taped at the top.

    Args:
        surface: Where to draw.

    """
    note = join_note_rect(surface)
    pygame.draw.rect(surface=surface, color=NOTE_COLOR, rect=note)
    pygame.draw.rect(surface=surface, color=PENCIL_COLOR, rect=note, width=1)
    tape = pygame.Rect((0, 0), NOTE_TAPE_SIZE)
    tape.center = note.midtop
    pygame.draw.rect(surface=surface, color=SANDBAG_WASH_COLOR, rect=tape)
    _blit_lines(
        surface,
        _note_lines(),
        topleft=(note.left + SEAT_PADDING_PIXELS, note.top + SEAT_PADDING_PIXELS),
    )


def draw_seat_card(
    surface: pygame.Surface, seat: PlayerSeat, *, slot: int, battle_over: bool
) -> None:
    """Draw the index card of a player not yet playing.

    It shows his side choice, how to choose a soldier, or that he waits (the scene gives a
    playing player no card).

    Args:
        surface: Where to draw.
        seat: The player.
        slot: Which card in the row it is.
        battle_over: Whether the battle is over (a waiting player waits for the next one).

    """
    card = seat_card_rect(surface, slot=slot)
    pygame.draw.rect(surface=surface, color=CARD_COLOR, rect=card)
    pygame.draw.rect(surface=surface, color=PENCIL_COLOR, rect=card, width=1)
    if seat.stage is Stage.CHOOSING_SIDE:
        texts = (f'{seat.name}: choose a side', *SIDE_CHOICE_TEXTS.values())
    elif seat.stage is Stage.CHOOSING_SOLDIER:
        texts = (f'{seat.name}: choose a soldier', 'LEFT / RIGHT to look', 'START takes him')
    else:
        reason = 'for the next battle' if battle_over else 'for a free soldier'
        texts = (f'{seat.name}: waiting', reason)
    lines = tuple(text_surface(text, size=CARD_FONT_SIZE) for text in texts)
    text_left = card.left + SEAT_PADDING_PIXELS + CARD_POINTER_PIXELS + SEAT_PADDING_PIXELS // 2
    if seat.stage is Stage.CHOOSING_SIDE:
        # The chosen line (under the title) is washed in its colour, behind the text, and
        # pointed at
        chosen_index = 1 + tuple(SideChoice).index(seat.side_choice)
        chosen_top = card.top + SEAT_PADDING_PIXELS
        for line in lines[:chosen_index]:
            chosen_top += line.get_height() + SEAT_LINE_GAP_PIXELS
        chosen = lines[chosen_index]
        wash = pygame.Rect(text_left - 2, chosen_top, chosen.get_width() + 4, chosen.get_height())
        pygame.draw.rect(surface=surface, color=SIDE_CHOICE_WASHES[seat.side_choice], rect=wash)
        pointer_left = card.left + SEAT_PADDING_PIXELS
        pygame.draw.polygon(
            surface=surface,
            color=PENCIL_COLOR,
            points=[
                (pointer_left, wash.top + 3),
                (pointer_left + CARD_POINTER_PIXELS, wash.centery),
                (pointer_left, wash.bottom - 3),
            ],
        )
    _blit_lines(surface, lines, topleft=(text_left, card.top + SEAT_PADDING_PIXELS))


def draw_soldier_highlight(surface: pygame.Surface, soldier: Soldier, *, name: str) -> None:
    """Ring the soldier a player is choosing in pencil, with the player's name over him.

    Args:
        surface: Where to draw.
        soldier: The highlighted soldier.
        name: The choosing player's name.

    """
    center_x = soldier.x
    center_y = soldier.y - HIGHLIGHT_CENTER_ABOVE_FEET
    radius_x, radius_y = HIGHLIGHT_RADII
    points: list[tuple[float, float]] = []
    for index in range(HIGHLIGHT_POINTS + HIGHLIGHT_OVERSHOOT_POINTS):
        angle = 2 * math.pi * index / HIGHLIGHT_POINTS
        # Keyed on the point and the soldier, not where he is, so the ring keeps its shape as
        # he walks; the overshoot runs a little outside the start, as a pencil would
        offset_x, offset_y = wobble(x=index, y=soldier.soldier_id, salt=SALT_HIGHLIGHT)
        overshoot = 2.0 if index >= HIGHLIGHT_POINTS else 0.0
        points.append((
            center_x + (radius_x + overshoot) * math.cos(angle) + offset_x,
            center_y - (radius_y + overshoot) * math.sin(angle) + offset_y,
        ))
    pygame.draw.lines(
        surface=surface,
        color=PENCIL_COLOR,
        closed=False,
        points=points,
        width=HIGHLIGHT_LINE_WIDTH,
    )
    label = text_surface(name, size=HIGHLIGHT_FONT_SIZE)
    surface.blit(
        label,
        label.get_rect(
            midbottom=(
                round(center_x),
                round(center_y - radius_y - HIGHLIGHT_LABEL_GAP_PIXELS),
            )
        ),
    )
