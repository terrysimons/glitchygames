#!/usr/bin/env python3
"""Render the host app's icon set from a sprite TOML (the owner chose shroom4.toml, 2026-10-29).

The sprite is loaded with the engine's own loader, trimmed to its visible pixels, and drawn
nearest neighbor at the largest whole-number scale that fits, centered on the preview's
checkerboard inside a rounded square on Apple's macOS icon grid (an 824 pt body in a 1024 pt
canvas, corner radius 185.4: Apple's macOS app icon template). Every size is drawn on its own
rather than shrunk from the largest, so small sizes don't blur.

Usage (from the repo root):
    SDL_VIDEODRIVER=dummy uv run python src/quicklook/tools/make_app_icon.py \
        src/apps/bitmappy/src/bitmappy/resources/sprites/shroom4.toml \
        src/quicklook/App/HostApp/Assets.xcassets/AppIcon.appiconset
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

CANVAS_POINTS = 1024
BODY_POINTS = 824
CORNER_RADIUS_POINTS = 185.4
# The sprite takes up to this share of the body, leaving the checkerboard as a frame around it
SPRITE_SHARE_OF_BODY = 0.8
# The preview's checkerboard grays (SpriteRenderer.checkerboardImage: 0.85 and 0.65)
CHECKER_LIGHT = (217, 217, 217, 255)
CHECKER_DARK = (166, 166, 166, 255)
# Checkerboard cells are this many sprite pixels on a side, so they line up with the art
CHECKER_CELL_SPRITE_PIXELS = 2
# The rounded square's edge is drawn this many times larger, then smoothed down to size
EDGE_SUPERSAMPLING = 4
# (points, scale) for every macOS app icon slot
ICON_SLOTS = [(points, scale) for points in (16, 32, 128, 256, 512) for scale in (1, 2)]


def visible_sprite(sprite_path: Path) -> object:
    """Load the sprite's first frame with the engine and trim it to its visible pixels.

    Returns:
        A pygame Surface with per-pixel alpha, transparent where the engine treats a pixel as
        transparent.

    """
    import pygame

    from glitchygames.sprites.animated import AnimatedSprite
    from glitchygames.sprites.pixel_utils import is_color_transparent

    sprite = AnimatedSprite(str(sprite_path))
    frame = sprite._animations[sprite._animation_order[0]][0]
    width, height = frame.image.get_width(), frame.image.get_height()
    surface = pygame.Surface((width, height), pygame.SRCALPHA)
    for index, pixel in enumerate(frame.pixels):
        if not is_color_transparent(pixel):
            surface.set_at((index % width, index // width), pixel)
    return surface.subsurface(surface.get_bounding_rect()).copy()


def rounded_square_mask(pixel_size: int) -> object:
    """Return a white rounded square on the icon grid, with a smoothed edge, as an alpha mask."""
    import pygame

    large_size = pixel_size * EDGE_SUPERSAMPLING
    points_to_large = large_size / CANVAS_POINTS
    body = round(BODY_POINTS * points_to_large)
    offset = (large_size - body) // 2
    mask = pygame.Surface((large_size, large_size), pygame.SRCALPHA)
    pygame.draw.rect(
        mask,
        (255, 255, 255, 255),
        pygame.Rect(offset, offset, body, body),
        border_radius=round(CORNER_RADIUS_POINTS * points_to_large),
    )
    return pygame.transform.smoothscale(mask, (pixel_size, pixel_size))


def icon_image(sprite: object, pixel_size: int) -> object:
    """Draw one icon of pixel_size x pixel_size.

    Returns:
        The icon as a pygame Surface with per-pixel alpha.

    """
    import pygame

    body = BODY_POINTS * pixel_size / CANVAS_POINTS
    longest_side = max(sprite.get_width(), sprite.get_height())
    fit = body * SPRITE_SHARE_OF_BODY / longest_side
    # Whole-number scales keep every sprite pixel a square block; tiny sizes can't, so shrink
    scale = int(fit) if fit >= 1 else fit
    sprite_size = (
        max(1, round(sprite.get_width() * scale)),
        max(1, round(sprite.get_height() * scale)),
    )
    sprite_position = ((pixel_size - sprite_size[0]) // 2, (pixel_size - sprite_size[1]) // 2)

    icon = pygame.Surface((pixel_size, pixel_size), pygame.SRCALPHA)
    cell = max(1, round(scale * CHECKER_CELL_SPRITE_PIXELS))
    # Cells start from the sprite's corner, so the grid lines up with its pixels
    first_x = sprite_position[0] % cell - cell
    first_y = sprite_position[1] % cell - cell
    for cell_y in range(first_y, pixel_size, cell):
        for cell_x in range(first_x, pixel_size, cell):
            column = (cell_x - first_x) // cell
            row = (cell_y - first_y) // cell
            color = CHECKER_LIGHT if (column + row) % 2 == 0 else CHECKER_DARK
            icon.fill(color, pygame.Rect(cell_x, cell_y, cell, cell))
    icon.blit(rounded_square_mask(pixel_size), (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    # pygame.transform.scale is nearest neighbor
    icon.blit(pygame.transform.scale(sprite, sprite_size), sprite_position)
    return icon


def main() -> None:
    """Write every icon size and the asset catalog's Contents.json."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('sprite', type=Path, help='sprite TOML file')
    parser.add_argument('icon_set', type=Path, help='AppIcon.appiconset directory to write into')
    arguments = parser.parse_args()

    # The static-sprite path calls Surface.convert(), which needs a display mode
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    import pygame

    pygame.display.init()
    pygame.display.set_mode((1, 1))

    sprite = visible_sprite(arguments.sprite)
    arguments.icon_set.mkdir(parents=True, exist_ok=True)
    images = []
    for points, scale in ICON_SLOTS:
        filename = f'icon_{points}x{points}@{scale}x.png'
        pygame.image.save(icon_image(sprite, points * scale), arguments.icon_set / filename)
        images.append({
            'filename': filename,
            'idiom': 'mac',
            'scale': f'{scale}x',
            'size': f'{points}x{points}',
        })
    contents = {'images': images, 'info': {'author': 'xcode', 'version': 1}}
    (arguments.icon_set / 'Contents.json').write_text(json.dumps(contents, indent=2) + '\n')
    print(f'{arguments.sprite} -> {arguments.icon_set}')  # ruff: ignore[print] - command-line tool output

    pygame.quit()


if __name__ == '__main__':
    main()
