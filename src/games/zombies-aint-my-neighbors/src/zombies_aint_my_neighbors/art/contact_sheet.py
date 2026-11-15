"""Render a kid's frames to a PNG contact sheet, to check the art by eye.

``python -m zombies_aint_my_neighbors.art.contact_sheet --kid dex --output sheet.png`` draws one
row per animation (its namespace on the left), every frame at 4x on a mid-grey background (so
magenta shows as transparent and dark outlines stay visible), straight from the rig.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pygame

from glitchygames.fonts import FontManager
from glitchygames.fonts.font_manager import bundled_font_path
from zombies_aint_my_neighbors.art import palettes, rig

if TYPE_CHECKING:
    from collections.abc import Sequence

    from zombies_aint_my_neighbors.art.palettes import KidLook

SCALE: Final = 4
LABEL_WIDTH: Final = 150
GAP: Final = 6
BACKGROUND: Final = (120, 124, 132)
LABEL_COLOUR: Final = (240, 240, 240)
LABEL_FONT_SIZE: Final = 12


def frame_surface(*, grid: rig.Grid, look: KidLook) -> pygame.Surface:
    """Return one frame as a surface at 4x, transparent where the frame is magenta.

    Returns:
        The surface (per-pixel alpha).

    """
    surface = pygame.Surface((rig.WIDTH * SCALE, rig.HEIGHT * SCALE), pygame.SRCALPHA)
    for y, row in enumerate(grid):
        for x, character in enumerate(row):
            if character == palettes.TRANSPARENT:
                continue
            surface.fill(look.palette[character], (x * SCALE, y * SCALE, SCALE, SCALE))
    return surface


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
    font = pygame.font.Font(bundled_font_path(font_name='VeraBd'), LABEL_FONT_SIZE)
    for row, (name, grids) in enumerate(frames.items()):
        top = row * cell_height
        label = font.render(name, antialias=FontManager.antialias(), color=LABEL_COLOUR)
        sheet.blit(label, (GAP, top + cell_height // 2 - label.get_height() // 2))
        for column, grid in enumerate(grids):
            sheet.blit(
                frame_surface(grid=grid, look=look), (LABEL_WIDTH + column * cell_width, top)
            )
    return sheet


def main(argv: Sequence[str] | None = None) -> None:
    """Write a kid's contact sheet to a PNG."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kid', choices=[look.name for look in palettes.KIDS], default='dex')
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args(argv)
    look = next(look for look in palettes.KIDS if look.name == arguments.kid)
    pygame.init()  # safe to call again: the sheet's font needs pygame initialised
    pygame.image.save(contact_sheet(look=look), str(arguments.output))
    print(arguments.output)  # ruff: ignore[print]


if __name__ == '__main__':  # pragma: no cover - run as a script; main() is tested
    main()
