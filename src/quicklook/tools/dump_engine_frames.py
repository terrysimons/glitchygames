#!/usr/bin/env python3
"""Dump sprite frames exactly as the engine loads them, as golden data for the QuickLook tests.

For each sprite TOML, copies it to <out>/<stem>.toml and writes <out>/<stem>.json:

    {"animations": [{"name": str, "loop": bool | null,
                     "frames": [{"width": int, "height": int, "duration": float,
                                 "pixels": [[r, g, b, a], ...]}]}]}

The Swift tests (src/quicklook/Tests/SpriteCoreTests/GoldenFrameTests.swift) load each copied
TOML with SpriteCore and compare against the JSON, so the preview draws what the game draws.

Test-only: it reads AnimatedSprite's private attributes (_animation_order, _animations,
_loop_flags), which have no public equivalent for "every frame of every animation".

Usage (from the repo root):
    SDL_VIDEODRIVER=dummy uv run python src/quicklook/tools/dump_engine_frames.py \
        --out src/quicklook/Tests/SpriteCoreTests/Golden <sprite.toml>...
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

RGB_COMPONENT_COUNT = 3
OPAQUE_ALPHA = 255


def rgba(pixel: tuple[int, ...]) -> list[int]:
    """Return a pixel as [r, g, b, a]; RGB pixels are opaque."""
    if len(pixel) == RGB_COMPONENT_COUNT:
        return [*pixel, OPAQUE_ALPHA]
    return list(pixel)


def dump_sprite(sprite_path: Path) -> dict[str, object]:
    """Load one sprite with the engine and return its golden data.

    Returns:
        The animations, their loop flags and every frame's size, duration and RGBA pixels.

    """
    from glitchygames.sprites.animated import AnimatedSprite

    sprite = AnimatedSprite(str(sprite_path))
    animations: list[dict[str, object]] = []
    # _animation_order lists a repeated namespace once per table; the engine keeps one entry
    # per name in _animations, so dump each name once, where it first appears
    seen_names: set[str] = set()
    for animation_name in sprite._animation_order:
        if animation_name in seen_names:
            continue
        seen_names.add(animation_name)
        frames = sprite._animations[animation_name]
        animations.append({
            'name': animation_name,
            'loop': sprite._loop_flags.get(animation_name),
            'frames': [
                {
                    'width': frame.image.get_width(),
                    'height': frame.image.get_height(),
                    'duration': frame.duration,
                    'pixels': [rgba(pixel) for pixel in frame.pixels],
                }
                for frame in frames
            ],
        })
    return {'animations': animations}


def main() -> None:
    """Dump every sprite named on the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--out', type=Path, required=True, help='golden directory to write into')
    parser.add_argument('sprites', type=Path, nargs='+', help='sprite TOML files')
    arguments = parser.parse_args()

    # The static-sprite path calls Surface.convert(), which needs a display mode
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    import pygame

    pygame.display.init()
    pygame.display.set_mode((1, 1))

    arguments.out.mkdir(parents=True, exist_ok=True)
    for sprite_path in arguments.sprites:
        golden_toml = arguments.out / f'{sprite_path.stem}.toml'
        shutil.copyfile(sprite_path, golden_toml)
        golden_json = arguments.out / f'{sprite_path.stem}.json'
        golden_json.write_text(json.dumps(dump_sprite(sprite_path), indent=1) + '\n')
        print(f'{sprite_path} -> {golden_json}')  # ruff: ignore[print] - command-line tool output

    pygame.quit()


if __name__ == '__main__':
    main()
