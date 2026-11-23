"""Render a kid's frames, or the intro's, to a PNG contact sheet, to check the art by eye.

``python -m zombies_aint_my_neighbors.art.contact_sheet --kid dex --output sheet.png`` draws one
row per animation (its namespace on the left), every frame at 4x on a mid-grey background (so
magenta shows as transparent and dark outlines stay visible), straight from the rig.
``--intro`` draws the intro's sprites instead (feature plan 12), one row per sprite and animation.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pygame

from glitchygames.fonts import font_manager
from zombies_aint_my_neighbors.art import intro_rig, palettes, rig

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from zombies_aint_my_neighbors.art.palettes import KidLook

SCALE: Final = 4
LABEL_WIDTH: Final = 150
GAP: Final = 6
BACKGROUND: Final = (120, 124, 132)
LABEL_COLOUR: Final = (240, 240, 240)
LABEL_FONT_SIZE: Final = 12


def grid_surface(*, grid: rig.Grid, palette: Mapping[str, tuple[int, int, int]]) -> pygame.Surface:
    """Return any frame as a surface at 4x, transparent where the frame is magenta.

    Returns:
        The surface (per-pixel alpha), the grid's size times ``SCALE``.

    """
    surface = pygame.Surface((len(grid[0]) * SCALE, len(grid) * SCALE), pygame.SRCALPHA)
    for y, row in enumerate(grid):
        for x, character in enumerate(row):
            if character == palettes.TRANSPARENT:
                continue
            surface.fill(palette[character], (x * SCALE, y * SCALE, SCALE, SCALE))
    return surface


def frame_surface(*, grid: rig.Grid, look: KidLook) -> pygame.Surface:
    """Return one kid frame as a surface at 4x, transparent where the frame is magenta.

    Returns:
        The surface (per-pixel alpha).

    """
    return grid_surface(grid=grid, palette=look.palette)


def contact_sheet(*, look: KidLook) -> pygame.Surface:
    """Return a kid's contact sheet: one labelled row per animation.

    Returns:
        The sheet.

    """
    frames = rig.kid_frames(look=look)
    most_frames = max(len(grids) for grids in frames.values())
    cell_width, cell_height = rig.WIDTH * SCALE + GAP, rig.HEIGHT * SCALE + GAP
    sheet = pygame.Surface((LABEL_WIDTH + most_frames * cell_width, len(frames) * cell_height))
    sheet.fill(BACKGROUND)
    font = font_manager.bundled_font(bold=True, size=LABEL_FONT_SIZE)
    for row, (name, grids) in enumerate(frames.items()):
        top = row * cell_height
        label = font_manager.render_line(font=font, text=name, color=LABEL_COLOUR)
        sheet.blit(label, (GAP, top + cell_height // 2 - label.get_height() // 2))
        for column, grid in enumerate(grids):
            sheet.blit(
                frame_surface(grid=grid, look=look), (LABEL_WIDTH + column * cell_width, top)
            )
    return sheet


def intro_contact_sheet() -> pygame.Surface:
    """Return the intro's contact sheet: one labelled row per sprite and animation.

    Every row is as tall as the tallest intro frame (the TV's 64), so the sprites line up.

    Returns:
        The sheet.

    """
    rows = [
        (f'{sprite.removeprefix("intro_")}: {name}', grids, intro_rig.intro_palette(sprite=sprite))
        for sprite in intro_rig.INTRO_ANIMATIONS
        for name, grids in intro_rig.intro_frames(sprite=sprite).items()
    ]
    tallest = max(len(grids[0]) for _, grids, _ in rows)
    widest = max(len(grids[0][0]) for _, grids, _ in rows)
    most_frames = max(len(grids) for _, grids, _ in rows)
    cell_width, cell_height = widest * SCALE + GAP, tallest * SCALE + GAP
    sheet = pygame.Surface((LABEL_WIDTH + most_frames * cell_width, len(rows) * cell_height))
    sheet.fill(BACKGROUND)
    font = font_manager.bundled_font(bold=True, size=LABEL_FONT_SIZE)
    for row, (label_text, grids, palette) in enumerate(rows):
        top = row * cell_height
        label = font_manager.render_line(font=font, text=label_text, color=LABEL_COLOUR)
        sheet.blit(label, (GAP, top + cell_height // 2 - label.get_height() // 2))
        for column, grid in enumerate(grids):
            sheet.blit(
                grid_surface(grid=grid, palette=palette), (LABEL_WIDTH + column * cell_width, top)
            )
    return sheet


def main(argv: Sequence[str] | None = None) -> None:
    """Write a kid's contact sheet, or the intro's, to a PNG."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kid', choices=[look.name for look in palettes.KIDS], default='dex')
    parser.add_argument('--intro', action='store_true', help="the intro's sprites instead")
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args(argv)
    look = next(look for look in palettes.KIDS if look.name == arguments.kid)
    pygame.init()  # safe to call again: the sheet's font needs pygame initialised
    sheet = intro_contact_sheet() if arguments.intro else contact_sheet(look=look)
    pygame.image.save(sheet, str(arguments.output))
    print(arguments.output)  # ruff: ignore[print]


if __name__ == '__main__':  # pragma: no cover - run as a script; main() is tested
    main()
