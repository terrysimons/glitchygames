"""Write the kids' sprite files from the rig: ``python -m zombies_aint_my_neighbors.art.build``.

Each file holds every kid animation the character BOM lists (section 3), in its order, with
the BOM's intervals, loop flags, hitbox and anchor, and a ``[[transition]]`` for each Then that
names a namespace in the same file. All four kids are built (feature plan 3).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING, Final

from zombies_aint_my_neighbors.art import palettes, poses, rig

if TYPE_CHECKING:
    from collections.abc import Sequence

    from zombies_aint_my_neighbors.art.palettes import KidLook

# Where the game's sprite files live (package data)
SPRITES_DIRECTORY: Final = Path(__file__).resolve().parents[1] / 'sprites'
# The kids built: all four, in player order (the owner approved Dex, 2026-11-14)
KIDS_TO_BUILD: Final = palettes.KIDS
# BOM section 3: the kids' body hitbox, in native pixels
KID_HITBOX: Final = {'offset_x': 6, 'offset_y': 12, 'width': 20, 'height': 36}
KID_TAGS: Final = ('character', 'kid', 'player')


def _format_interval(seconds: float) -> str:
    """Return an interval as TOML writes it (no trailing zeros past one decimal).

    Returns:
        The number's text.

    """
    return repr(seconds)


def sprite_file_text(*, look: KidLook) -> str:
    """Return a kid's sprite file, as TOML.

    Returns:
        The file's text.

    """
    lines = [
        "# Written by zombies_aint_my_neighbors.art.build from the kids' rig: edit the rig and",
        '# rebuild, never this file (plans/2026-11-14-zombies-aint-my-neighbors-3-dex.md)',
        '[sprite]',
        f'name = "{look.name}"',
        f'description = "{look.name.title()}, a player kid: every animation in the character BOM"',
        'tags = [' + ', '.join(f'"{tag}"' for tag in KID_TAGS) + ']',
        'frame_anchor = "bottom"',
        '',
        '[sprite.hitbox]',
        *(f'{key} = {value}' for key, value in KID_HITBOX.items()),
        '',
        '[colors]',
        *(
            f'"{character}" = {{ red = {red}, green = {green}, blue = {blue} }}'
            for character, (red, green, blue) in look.palette.items()
        ),
    ]
    frames = rig.kid_frames(look=look)
    specs = {spec.state: spec for spec in poses.KID_ANIMATIONS}
    transitions: list[tuple[str, str, str]] = []
    for name, grids in frames.items():
        state, _, facing = name.rpartition('_')
        spec = specs[state] if state in specs else specs[name]
        lines += [
            '',
            '[[animation]]',
            f'namespace = "{name}"',
            f'frame_interval = {_format_interval(spec.frame_interval)}',
            f'loop = {"true" if spec.loop else "false"}',
        ]
        for index, grid in enumerate(grids):
            lines += [
                '',
                '[[animation.frame]]',
                f'namespace = "{name}"',
                f'frame_index = {index}',
                'pixels = """',
                *grid,
                '"""',
            ]
        if spec.then_state is not None:
            target = spec.then_state if spec.then_state in frames else f'{spec.then_state}_{facing}'
            transitions.append((name, target, spec.when))
    for source, target, when in transitions:
        lines += [
            '',
            '[[transition]]',
            f'from = "{source}"',
            f'to = "{target}"',
            f'when = "{when}"',
        ]
    return '\n'.join(lines) + '\n'


def build(*, directory: Path, kids: Sequence[KidLook] = KIDS_TO_BUILD) -> list[Path]:
    """Write each kid's sprite file into a directory.

    Returns:
        The files written.

    """
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for look in kids:
        path = directory / f'{look.name}.toml'
        path.write_text(sprite_file_text(look=look))
        written.append(path)
    return written


def main(argv: Sequence[str] | None = None) -> None:
    """Rebuild the sprite files (into the package's sprites directory by default)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=SPRITES_DIRECTORY)
    arguments = parser.parse_args(argv)
    for path in build(directory=arguments.output):
        print(path)  # ruff: ignore[print]


if __name__ == '__main__':  # pragma: no cover - run as a script; main() is tested
    main()
