"""Write the kids' sprite files from the rig: ``python -m zombies_aint_my_neighbors.art.build``.

Each file holds every kid animation the character BOM lists (section 3), in its order, with
the BOM's intervals, loop flags, hitbox and anchor, and a ``[[transition]]`` for each Then that
names a namespace in the same file. All four kids are built (feature plan 3).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING, Final

from zombies_aint_my_neighbors.art import (
    door_rig,
    neighbor_rig,
    palettes,
    poses,
    rig,
    tv_rig,
    weapon_rig,
    zombie_rig,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from zombies_aint_my_neighbors.art.palettes import KidLook

# Where the game's sprite files live (package data)
SPRITES_DIRECTORY: Final = Path(__file__).resolve().parents[1] / 'sprites'
# The kids built: all four, in player order (the owner approved Dex, 2026-11-14)
KIDS_TO_BUILD: Final = palettes.KIDS
# BOM section 3: the kids' body hitbox, in native pixels
KID_HITBOX: Final = {'offset_x': 6, 'offset_y': 12, 'width': 20, 'height': 36}
KID_TAGS: Final = ('character', 'kid', 'player')
# Character BOM 5.1: the Lawn Zombie's body hitbox (a kid's), and the props BOM's TV's
ZOMBIE_HITBOX: Final = {'offset_x': 6, 'offset_y': 12, 'width': 20, 'height': 36}
TV_HITBOX: Final = {'offset_x': 4, 'offset_y': 12, 'width': 40, 'height': 32}
# The props BOM's Channel Changer (its whole canvas: never collided, it is in a hand) and zap
CHANNEL_CHANGER_HITBOX: Final = {'offset_x': 0, 'offset_y': 0, 'width': 12, 'height': 12}
ZAP_HITBOX: Final = {'offset_x': 2, 'offset_y': 2, 'width': 8, 'height': 8}
# Character BOM section 6: the neighbors' hitbox; the effects' is their whole frame (never collided)
NEIGHBOR_HITBOX: Final = {'offset_x': 4, 'offset_y': 8, 'width': 24, 'height': 40}
EFFECT_HITBOX: Final = {'offset_x': 0, 'offset_y': 0, 'width': 32, 'height': 48}
NEIGHBOR_DESCRIPTIONS: Final = {
    'pizza_teen': 'The Pizza Delivery Teen, a neighbor to save (character BOM section 6)',
    'lawn_chair_reader': 'The Lawn-Chair Reader, a neighbor to save (character BOM section 6)',
}
_NEIGHBOR_HEADER: Final = (
    "Written by zombies_aint_my_neighbors.art.build from the neighbors' rig: edit the rig",
    'and rebuild, never this file',
    '(plans/2026-11-15-zombies-aint-my-neighbors-7-neighbors-and-lives.md)',
)
_BUILT_HEADER: Final = 'rebuild, never this file'


def _format_interval(seconds: float) -> str:
    """Return an interval as TOML writes it (no trailing zeros past one decimal).

    Returns:
        The number's text.

    """
    return repr(seconds)


def character_sprite_text(  # ruff: ignore[too-many-arguments] - a sprite file has this many parts, each named
    *,
    header: Sequence[str],
    name: str,
    description: str,
    tags: Sequence[str],
    hitbox: Mapping[str, int],
    palette: Mapping[str, tuple[int, int, int]],
    frames: Mapping[str, Sequence[rig.Grid]],
    specs: Sequence[poses.AnimationSpec],
) -> str:
    """Return a sprite file, as TOML: any character or prop the rigs draw.

    Args:
        header: Comment lines at the top (without their ``# ``).
        name: The sprite's name.
        description: Its description.
        tags: Its tags.
        hitbox: Its hitbox (``offset_x``, ``offset_y``, ``width``, ``height``).
        palette: Palette character -> colour.
        frames: Namespace -> its frames, in the file's order.
        specs: The animation specs (by state); a Then naming a namespace in the file becomes a
            ``[[transition]]``.

    Returns:
        The file's text.

    """
    lines = [
        *(f'# {line}' for line in header),
        '[sprite]',
        f'name = "{name}"',
        f'description = "{description}"',
        'tags = [' + ', '.join(f'"{tag}"' for tag in tags) + ']',
        'frame_anchor = "bottom"',
        '',
        '[sprite.hitbox]',
        *(f'{key} = {value}' for key, value in hitbox.items()),
        '',
        '[colors]',
        *(
            f'"{character}" = {{ red = {red}, green = {green}, blue = {blue} }}'
            for character, (red, green, blue) in palette.items()
        ),
    ]
    by_state = {spec.state: spec for spec in specs}
    transitions: list[tuple[str, str, str]] = []
    for namespace, grids in frames.items():
        state, _, facing = namespace.rpartition('_')
        spec = by_state[state] if state in by_state else by_state[namespace]
        lines += [
            '',
            '[[animation]]',
            f'namespace = "{namespace}"',
            f'frame_interval = {_format_interval(spec.frame_interval)}',
            f'loop = {"true" if spec.loop else "false"}',
        ]
        for index, grid in enumerate(grids):
            lines += [
                '',
                '[[animation.frame]]',
                f'namespace = "{namespace}"',
                f'frame_index = {index}',
                'pixels = """',
                *grid,
                '"""',
            ]
        if spec.then_state is not None:
            target = spec.then_state if spec.then_state in frames else f'{spec.then_state}_{facing}'
            transitions.append((namespace, target, spec.when))
    for source, target, when in transitions:
        lines += [
            '',
            '[[transition]]',
            f'from = "{source}"',
            f'to = "{target}"',
            f'when = "{when}"',
        ]
    return '\n'.join(lines) + '\n'


def sprite_file_text(*, look: KidLook) -> str:
    """Return a kid's sprite file, as TOML.

    Returns:
        The file's text.

    """
    return character_sprite_text(
        header=(
            "Written by zombies_aint_my_neighbors.art.build from the kids' rig: edit the rig and",
            'rebuild, never this file (plans/2026-11-14-zombies-aint-my-neighbors-3-dex.md)',
        ),
        name=look.name,
        description=f'{look.name.title()}, a player kid: every animation in the character BOM',
        tags=KID_TAGS,
        hitbox=KID_HITBOX,
        palette=look.palette,
        frames=rig.kid_frames(look=look),
        specs=poses.KID_ANIMATIONS,
    )


def zombie_sprite_text() -> str:
    """Return the Lawn Zombie's sprite file, as TOML.

    Returns:
        The file's text.

    """
    return character_sprite_text(
        header=(
            "Written by zombies_aint_my_neighbors.art.build from the zombie's rig: edit the",
            'rig and '
            + _BUILT_HEADER
            + ' (plans/2026-11-14-zombies-aint-my-neighbors-5-zombies.md)',
        ),
        name='lawn_zombie',
        description='The Lawn Zombie: a shambling neighbor in a bathrobe (character BOM 5.1)',
        tags=('character', 'monster', 'zombie'),
        hitbox=ZOMBIE_HITBOX,
        palette=zombie_rig.ZOMBIE_PALETTE,
        frames=zombie_rig.zombie_frames(),
        specs=zombie_rig.ZOMBIE_ANIMATIONS,
    )


def tv_sprite_text() -> str:
    """Return the TV's sprite file, as TOML.

    Returns:
        The file's text.

    """
    return character_sprite_text(
        header=(
            "Written by zombies_aint_my_neighbors.art.build from the TV's rig: edit the rig and",
            f'{_BUILT_HEADER} (plans/2026-11-14-zombies-aint-my-neighbors-props-bom.md)',
        ),
        name='tv',
        description='A TV set showing static: monsters come out of it (props BOM)',
        tags=('prop', 'spawner', 'tv'),
        hitbox=TV_HITBOX,
        palette=tv_rig.TV_PALETTE,
        frames=tv_rig.tv_frames(),
        specs=tv_rig.TV_ANIMATIONS,
    )


def channel_changer_sprite_text() -> str:
    """Return the Channel Changer's sprite file, as TOML.

    Returns:
        The file's text.

    """
    return character_sprite_text(
        header=(
            "Written by zombies_aint_my_neighbors.art.build from the weapons' rig: edit the rig",
            f'and {_BUILT_HEADER} (plans/2026-11-14-zombies-aint-my-neighbors-props-bom.md)',
        ),
        name='channel_changer',
        description="The Channel Changer: the kids' TV remote, held while shooting (props BOM)",
        tags=('prop', 'weapon'),
        hitbox=CHANNEL_CHANGER_HITBOX,
        palette=weapon_rig.WEAPON_PALETTE,
        frames=weapon_rig.channel_changer_frames(),
        specs=weapon_rig.CHANNEL_CHANGER_ANIMATIONS,
    )


def zap_sprite_text() -> str:
    """Return the zap's sprite file, as TOML.

    Returns:
        The file's text.

    """
    return character_sprite_text(
        header=(
            "Written by zombies_aint_my_neighbors.art.build from the weapons' rig: edit the rig",
            f'and {_BUILT_HEADER} (plans/2026-11-14-zombies-aint-my-neighbors-props-bom.md)',
        ),
        name='zap',
        description='A zap of TV static, fired by the Channel Changer (props BOM)',
        tags=('prop', 'projectile'),
        hitbox=ZAP_HITBOX,
        palette=weapon_rig.WEAPON_PALETTE,
        frames=weapon_rig.zap_frames(),
        specs=weapon_rig.ZAP_ANIMATIONS,
    )


def neighbor_sprite_text(*, name: str) -> str:
    """Return a neighbor's sprite file, as TOML.

    Args:
        name: ``pizza_teen`` or ``lawn_chair_reader``.

    Returns:
        The file's text.

    """
    return character_sprite_text(
        header=_NEIGHBOR_HEADER,
        name=name,
        description=NEIGHBOR_DESCRIPTIONS[name],
        tags=('character', 'neighbor'),
        hitbox=NEIGHBOR_HITBOX,
        palette=neighbor_rig.NEIGHBOR_LOOKS[name],
        frames=neighbor_rig.neighbor_frames(name=name),
        specs=neighbor_rig.NEIGHBOR_ANIMATIONS,
    )


def saved_sprite_text() -> str:
    """Return the saved effect's sprite file, as TOML.

    Returns:
        The file's text.

    """
    return character_sprite_text(
        header=_NEIGHBOR_HEADER,
        name='saved',
        description='A neighbor saved: streaming up into the VR safe room (character BOM)',
        tags=('effect',),
        hitbox=EFFECT_HITBOX,
        palette=neighbor_rig.EFFECT_PALETTE,
        frames=neighbor_rig.saved_frames(),
        specs=neighbor_rig.SAVED_ANIMATIONS,
    )


def lost_sprite_text() -> str:
    """Return the lost effect's sprite file, as TOML.

    Returns:
        The file's text.

    """
    return character_sprite_text(
        header=_NEIGHBOR_HEADER,
        name='lost',
        description='A neighbor lost: flickering out as TV static (character BOM)',
        tags=('effect',),
        hitbox=EFFECT_HITBOX,
        palette=neighbor_rig.EFFECT_PALETTE,
        frames=neighbor_rig.lost_frames(),
        specs=neighbor_rig.LOST_ANIMATIONS,
    )


DOOR_HITBOX: Final = {'offset_x': 8, 'offset_y': 16, 'width': 32, 'height': 32}


def door_sprite_text() -> str:
    """Return the exit door's sprite file, as TOML.

    Returns:
        The file's text.

    """
    return character_sprite_text(
        header=(
            "Written by zombies_aint_my_neighbors.art.build from the door's rig: edit the rig",
            f'and {_BUILT_HEADER} (plans/2026-11-14-zombies-aint-my-neighbors-props-bom.md)',
        ),
        name='exit_door',
        description='The exit door: a garden gate in the hedge, open when a stage is cleared',
        tags=('prop', 'door'),
        hitbox=DOOR_HITBOX,
        palette=door_rig.DOOR_PALETTE,
        frames=door_rig.door_frames(),
        specs=door_rig.DOOR_ANIMATIONS,
    )


def build(*, directory: Path, kids: Sequence[KidLook] = KIDS_TO_BUILD) -> list[Path]:
    """Write each kid's sprite file, the Lawn Zombie's, the TV's and the weapons' into a directory.

    Returns:
        The files written.

    """
    directory.mkdir(parents=True, exist_ok=True)
    texts = {f'{look.name}.toml': sprite_file_text(look=look) for look in kids}
    texts |= {
        'lawn_zombie.toml': zombie_sprite_text(),
        'tv.toml': tv_sprite_text(),
        'channel_changer.toml': channel_changer_sprite_text(),
        'zap.toml': zap_sprite_text(),
        'pizza_teen.toml': neighbor_sprite_text(name='pizza_teen'),
        'lawn_chair_reader.toml': neighbor_sprite_text(name='lawn_chair_reader'),
        'saved.toml': saved_sprite_text(),
        'lost.toml': lost_sprite_text(),
        'exit_door.toml': door_sprite_text(),
    }
    written: list[Path] = []
    for file_name, text in texts.items():
        path = directory / file_name
        path.write_text(text)
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
