"""Checks of a sprite file, for the engine's tests and for every package that ships sprites.

Every pixel row is the same width, and a save round trip keeps a sprite's timings, hitboxes,
pixels, metadata and transitions. The engine runs these checks on its own sprites
(tests/sprites/test_engine_sprite_files.py), the repository runs them on every workspace member's
sprites, discovered (tests/test_workspace_sprite_files.py), and a package with sprites of its own
may run them from its own tests too (Papyrus's, and Bitmappy's sprite library)::

    from glitchygames.testing import sprite_files


    def test_rows_have_equal_lengths(sprite_file):
        sprite_files.check_rows_have_equal_lengths(sprite_file=sprite_file)

Each ``check_*`` function raises ``AssertionError`` naming the sprite file and the difference, or
skips (``pytest.skip``) where the sprite is saved in a format that cannot carry what the check
compares. The round trip checks need a display set (``set_display_mode``), since a sprite loads
and saves through one. The functions are named ``check_*`` so pytest never collects them from a
test module that imports this one.

This module imports pytest, as ``glitchygames.testing.replays`` does; ``glitchygames.testing``
never imports it, so the engine's runtime does not need pytest.
"""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING, Any

import pytest

from glitchygames.sprites import AnimatedSprite

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

# The frame_interval a sprite file gets when it names none
DEFAULT_TOML_FRAME_INTERVAL = 0.5
ANIMATION_MARKER = '[[animation]]'
SPRITE_FILE_PATTERN = '*.toml'
OPAQUE_ALPHA = 255
RGBA_CHANNEL_COUNT = 4

type SpriteData = dict[str, Any]
type AnimationTiming = tuple[str, float, bool, list[float | None]]
type FrameKey = tuple[str, int]
type FramePixels = tuple[tuple[int, int], list[tuple[int, ...]]]


def _read_sprite_data(*, sprite_file: Path) -> SpriteData:
    """Parse a sprite file as TOML.

    Returns:
        SpriteData: The file's tables.

    """
    return tomllib.loads(sprite_file.read_text(encoding='utf-8'))


def _pixel_blocks(*, sprite_data: SpriteData) -> list[tuple[str, str]]:
    """Return (label, pixels) for the static sprite and every animation frame in a sprite file.

    Returns:
        list[tuple[str, str]]: One entry per pixel block, labelled for failure messages.

    """
    blocks: list[tuple[str, str]] = []
    static_pixels = sprite_data.get('sprite', {}).get('pixels')
    if static_pixels is not None:
        blocks.append(('sprite', static_pixels))
    for animation_index, animation in enumerate(sprite_data.get('animation', [])):
        for frame_index, frame in enumerate(animation.get('frame', [])):
            if 'pixels' in frame:
                label = f'animation {animation_index} frame {frame_index}'
                blocks.append((label, frame['pixels']))
    return blocks


def _frames_in_file_order(*, animation: SpriteData) -> list[SpriteData]:
    """Return an animation's frames in the order the loader gives them: the file's order.

    The loader (AnimatedSprite._process_toml_animation) sorts by a ``frame_index`` attribute that
    SpriteFrame never has, so the sort keeps the file's order and a ``frame_index`` key in the
    file does not reorder anything. Sorting by the key here would disagree with the loader for a
    file where only some frames carry one.

    Returns:
        list[SpriteData]: The ``[[animation.frame]]`` tables, in file order.

    """
    return animation.get('frame', [])


def _animation_timings(*, sprite_data: SpriteData) -> list[AnimationTiming]:
    """Return each animation's timing as written in a sprite file.

    Returns:
        list[AnimationTiming]: (namespace, frame_interval, loop, per-frame frame_interval
        overrides in file order, None where absent).

    """
    return [
        (
            animation.get('namespace', 'default'),
            animation.get('frame_interval', DEFAULT_TOML_FRAME_INTERVAL),
            animation.get('loop', True),
            [frame.get('frame_interval') for frame in _frames_in_file_order(animation=animation)],
        )
        for animation in sprite_data.get('animation', [])
    ]


def _hitbox_sections(
    *, sprite_data: SpriteData
) -> tuple[SpriteData | None, list[SpriteData | None]]:
    """Return the hitboxes a sprite file defines explicitly.

    Returns:
        tuple[SpriteData | None, list[SpriteData | None]]: The [sprite.hitbox] table (or None) and
        each animation frame's [animation.frame.hitbox] (None where absent), in file order with
        frames in file order.

    """
    frame_hitboxes: list[SpriteData | None] = []
    for animation in sprite_data.get('animation', []):
        frame_hitboxes.extend(
            frame.get('hitbox') for frame in _frames_in_file_order(animation=animation)
        )
    return sprite_data.get('sprite', {}).get('hitbox'), frame_hitboxes


def _rgba_frames(*, sprite: AnimatedSprite) -> dict[FrameKey, FramePixels]:
    """Return every frame's size and pixels as RGBA tuples (RGB pixels get alpha 255).

    Returns:
        dict[FrameKey, FramePixels]: (animation name, frame position) -> (size, RGBA pixels).

    """
    frames: dict[FrameKey, FramePixels] = {}
    for animation_name, animation_frames in sprite.animations.items():
        for frame_position, frame in enumerate(animation_frames):
            rgba_pixels: list[tuple[int, ...]] = [
                pixel if len(pixel) == RGBA_CHANNEL_COUNT else (*pixel, OPAQUE_ALPHA)
                for pixel in frame.get_pixel_data()
            ]
            frames[animation_name, frame_position] = (frame.get_size(), rgba_pixels)
    return frames


def _metadata(*, sprite: AnimatedSprite) -> tuple[object, ...]:
    """Return what a save must keep of a sprite besides its pixels.

    Returns:
        tuple[object, ...]: The sprite's name, description, frame_anchor and hitbox.

    """
    return (sprite.name, sprite.description, sprite.frame_anchor, sprite.hitbox)


def _save_and_reload(
    *, sprite_file: Path, directory: Path
) -> tuple[AnimatedSprite, Path, AnimatedSprite]:
    """Load a sprite file, save it into a directory and load the saved file.

    Returns:
        tuple[AnimatedSprite, Path, AnimatedSprite]: The original sprite, the saved file and the
        reloaded sprite.

    """
    original_sprite = AnimatedSprite(str(sprite_file))
    saved_file = directory / sprite_file.name
    original_sprite.save(str(saved_file), 'toml')
    return original_sprite, saved_file, AnimatedSprite(str(saved_file))


def check_rows_have_equal_lengths(*, sprite_file: Path) -> None:
    """Check that every pixel row in a sprite file is the same width.

    The loader pads a short row with its last character (and truncates a long one), which
    silently changes the art, e.g. a 9-wide row in gold_scarab.toml frame 2 drew a notch.

    Args:
        sprite_file: The sprite file to check.

    Raises:
        AssertionError: A pixel block has rows of more than one width; the message names the file,
            the block and the widths.

    """
    sprite_data = _read_sprite_data(sprite_file=sprite_file)
    for label, pixels in _pixel_blocks(sprite_data=sprite_data):
        rows = AnimatedSprite.parse_toml_pixel_lines(pixels)
        row_lengths = {len(row) for row in rows}
        if len(row_lengths) > 1:
            message = f'{sprite_file} {label}: row lengths {sorted(row_lengths)}'
            raise AssertionError(message)


def check_animation_timings_survive_a_save_round_trip(
    *, sprite_file: Path, directory: Path
) -> None:
    """Check that load -> save writes each animation's frame_interval, loop and overrides back.

    The writer used to hard-code frame_interval = 0.5 and loop = true, so saving (Bitmappy saves
    this way) lost every animation's timing.

    Args:
        sprite_file: The animated sprite file to check.
        directory: Where to save the sprite (a ``tmp_path``).

    Raises:
        AssertionError: The saved file's timings, or the reloaded frames' durations, differ from
            the original's; the message names the file (and the animation).

    """
    original_sprite = AnimatedSprite(str(sprite_file))
    if original_sprite.get_total_frame_count() == 1:
        pytest.skip('single-frame sprites are saved in the static format, without timing')
    saved_file = directory / sprite_file.name
    original_sprite.save(str(saved_file), 'toml')

    original_timings = _animation_timings(sprite_data=_read_sprite_data(sprite_file=sprite_file))
    saved_timings = _animation_timings(sprite_data=_read_sprite_data(sprite_file=saved_file))
    if saved_timings != original_timings:
        message = f'{sprite_file}: saved timings {saved_timings} != original {original_timings}'
        raise AssertionError(message)

    reloaded_sprite = AnimatedSprite(str(saved_file))
    for animation_name, frames in original_sprite.animations.items():
        original_durations = [frame.duration for frame in frames]
        reloaded_durations = [
            frame.duration for frame in reloaded_sprite.animations[animation_name]
        ]
        if reloaded_durations != original_durations:
            message = (
                f'{sprite_file} {animation_name}: reloaded durations {reloaded_durations} '
                f'!= original {original_durations}'
            )
            raise AssertionError(message)


def check_hitboxes_survive_a_save_round_trip_unchanged(
    *, sprite_file: Path, directory: Path
) -> None:
    """Check that save writes exactly the hitboxes the file defined: none are synthesized.

    The writer used to turn the visible-pixel fallback into explicit [sprite.hitbox] and
    [animation.frame.hitbox] sections, so saving a sprite without hitboxes froze them.

    Args:
        sprite_file: The sprite file to check.
        directory: Where to save the sprite (a ``tmp_path``).

    Raises:
        AssertionError: The saved file's hitbox sections differ from the original's; the message
            names the file.

    """
    original_sprite = AnimatedSprite(str(sprite_file))
    original_data = _read_sprite_data(sprite_file=sprite_file)
    if original_sprite.get_total_frame_count() == 1 and 'animation' in original_data:
        pytest.skip('a one-frame animation is saved in the static format')
    saved_file = directory / sprite_file.name
    original_sprite.save(str(saved_file), 'toml')

    saved_hitboxes = _hitbox_sections(sprite_data=_read_sprite_data(sprite_file=saved_file))
    original_hitboxes = _hitbox_sections(sprite_data=original_data)
    if saved_hitboxes != original_hitboxes:
        message = f'{sprite_file}: saved hitboxes {saved_hitboxes} != original {original_hitboxes}'
        raise AssertionError(message)


def check_pixels_survive_a_save_round_trip(*, sprite_file: Path, directory: Path) -> None:
    """Check that load -> save -> reload gives every frame (static and animated) the same pixels.

    Args:
        sprite_file: The sprite file to check.
        directory: Where to save the sprite (a ``tmp_path``).

    Raises:
        AssertionError: The reloaded sprite has a different number of frames, or a frame with a
            different size or pixels; the message names the file and the frame.

    """
    original_sprite, _saved_file, reloaded_sprite = _save_and_reload(
        sprite_file=sprite_file, directory=directory
    )
    original_frames = _rgba_frames(sprite=original_sprite)
    reloaded_frames = list(_rgba_frames(sprite=reloaded_sprite).values())
    # A one-frame sprite is saved in the static format, which may rename its animation
    if len(reloaded_frames) != len(original_frames):
        message = (
            f'{sprite_file}: {len(reloaded_frames)} frames reloaded, '
            f'{len(original_frames)} originally'
        )
        raise AssertionError(message)
    for (frame_key, original_frame), reloaded_frame in zip(
        original_frames.items(), reloaded_frames, strict=True
    ):
        if reloaded_frame != original_frame:
            message = f'{sprite_file} frame {frame_key}: pixels differ after a save round trip'
            raise AssertionError(message)


def check_metadata_survives_a_save_round_trip(*, sprite_file: Path, directory: Path) -> None:
    """Check that load -> save -> reload keeps the [sprite] name, description, frame_anchor, hitbox.

    The single-frame (static) writer used to drop description.

    Args:
        sprite_file: The sprite file to check.
        directory: Where to save the sprite (a ``tmp_path``).

    Raises:
        AssertionError: The reloaded sprite's metadata differs; the message names the file.

    """
    original_sprite, _saved_file, reloaded_sprite = _save_and_reload(
        sprite_file=sprite_file, directory=directory
    )
    original_metadata = _metadata(sprite=original_sprite)
    reloaded_metadata = _metadata(sprite=reloaded_sprite)
    if reloaded_metadata != original_metadata:
        message = f'{sprite_file}: reloaded metadata {reloaded_metadata} != {original_metadata}'
        raise AssertionError(message)


def check_transitions_survive_a_save_round_trip(*, sprite_file: Path, directory: Path) -> None:
    """Check that load -> save writes every [[transition]] back with the same keys, values, order.

    The writers used to drop them, so saving (e.g. from Bitmappy) lost the animation state
    machine (cobra 2 -> 0 transitions, Papyrus player 6 -> 0).

    Args:
        sprite_file: The sprite file to check.
        directory: Where to save the sprite (a ``tmp_path``).

    Raises:
        AssertionError: The saved file's transitions differ from the original's; the message
            names the file.

    """
    original_data = _read_sprite_data(sprite_file=sprite_file)
    saved_file = directory / sprite_file.name
    AnimatedSprite(str(sprite_file)).save(str(saved_file), 'toml')

    saved_transitions = _read_sprite_data(sprite_file=saved_file).get('transition', [])
    original_transitions = original_data.get('transition', [])
    if saved_transitions != original_transitions:
        message = (
            f'{sprite_file}: saved transitions {saved_transitions} '
            f'!= original {original_transitions}'
        )
        raise AssertionError(message)


def animated_sprite_files(*, directories: Iterable[Path]) -> list[Path]:
    """Return the sprite files in directories that define an animation.

    Args:
        directories: The directories to look in, each searched for ``*.toml`` files.

    Returns:
        list[Path]: The files containing a ``[[animation]]`` table, each directory's in name order,
        the directories in the order given.

    """
    return [
        sprite_file
        for directory in directories
        for sprite_file in sorted(directory.glob(SPRITE_FILE_PATTERN))
        if ANIMATION_MARKER in sprite_file.read_text(encoding='utf-8')
    ]
