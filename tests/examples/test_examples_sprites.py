"""The engine's checks of a bundled sprite file, run on the engine's own sprites.

Every pixel row is the same width, and a save round trip keeps each sprite's timings,
hitboxes, pixels, metadata and transitions. A package with sprites of its own runs these
checks on them from its own tests (Papyrus's, and Bitmappy's sprite library in
src/apps/bitmappy/tests/test_bitmappy_sprite_library.py).
"""

from pathlib import Path

import pygame
import pytest

from glitchygames.display_mode import set_display_mode
from tests.harness import imported_engine_directory

# The imported engine's directory (installed: never the source tree by accident)
ENGINE_PACKAGE_DIRECTORY = imported_engine_directory()


# The engine's sprites. A package with sprites of its own checks them with these tests from its
# own tests (Papyrus's: src/games/brave-adventurer/tests/papyrus/; Bitmappy's sprite library:
# src/apps/bitmappy/tests/test_bitmappy_sprite_library.py)
BUNDLED_SPRITE_FILES = sorted((ENGINE_PACKAGE_DIRECTORY / 'assets').glob('*.toml'))


def _sprite_file_test_id(sprite_file: Path) -> str:
    """Name a bundled sprite file relative to the engine (the same id under nox and uv run).

    Returns:
        str: The file's path inside the engine package, e.g. ``assets/eraser.toml``.

    """
    return sprite_file.relative_to(ENGINE_PACKAGE_DIRECTORY).as_posix()


def _pixel_blocks(sprite_data: dict) -> list[tuple[str, str]]:
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


@pytest.mark.parametrize('sprite_file', BUNDLED_SPRITE_FILES, ids=_sprite_file_test_id)
def test_bundled_sprite_rows_have_equal_lengths(sprite_file):
    """Every pixel row in a bundled sprite is the same width.

    The loader pads a short row with its last character (and truncates a long one), which
    silently changes the art, e.g. a 9-wide row in gold_scarab.toml frame 2 drew a notch.
    """
    import tomllib

    from glitchygames.sprites import AnimatedSprite

    sprite_data = tomllib.loads(sprite_file.read_text(encoding='utf-8'))
    for label, pixels in _pixel_blocks(sprite_data):
        rows = AnimatedSprite.parse_toml_pixel_lines(pixels)
        row_lengths = {len(row) for row in rows}
        assert len(row_lengths) <= 1, f'{sprite_file} {label}: row lengths {sorted(row_lengths)}'


# The engine's own sprite test data. The engine bundles no animated sprite, so the animated-sprite
# checks also run on these fixtures (colors.toml and girl.toml are animated)
TESTS_DIRECTORY = Path(__file__).resolve().parents[1]
SPRITE_FIXTURES_DIRECTORY = TESTS_DIRECTORY / 'fixtures' / 'sprites'
ANIMATED_SPRITE_FILES = [
    sprite_file
    for sprite_file in [*BUNDLED_SPRITE_FILES, *sorted(SPRITE_FIXTURES_DIRECTORY.glob('*.toml'))]
    if '[[animation]]' in sprite_file.read_text(encoding='utf-8')
]


def _animated_sprite_file_test_id(sprite_file: Path) -> str:
    """Name an animated sprite file: a bundled one inside the engine, a fixture inside tests/.

    Returns:
        str: ``assets/<name>.toml`` for a bundled sprite, ``fixtures/sprites/<name>.toml`` for a
        fixture.

    """
    if sprite_file.is_relative_to(ENGINE_PACKAGE_DIRECTORY):
        return _sprite_file_test_id(sprite_file)
    return sprite_file.relative_to(TESTS_DIRECTORY).as_posix()


def test_the_animated_sprite_checks_have_sprites_to_run_on():
    """The animated-sprite checks never run on nothing (an empty parameter set only skips)."""
    assert ANIMATED_SPRITE_FILES


DEFAULT_TOML_FRAME_INTERVAL = 0.5


def _animation_timings(sprite_data: dict) -> list[tuple[str, float, bool, list[float | None]]]:
    """Return each animation's timing as written in a sprite file.

    Returns:
        list[tuple[str, float, bool, list[float | None]]]: (namespace, frame_interval, loop,
        per-frame frame_interval overrides in frame_index order, None where absent).

    """
    timings: list[tuple[str, float, bool, list[float | None]]] = []
    for animation in sprite_data.get('animation', []):
        frames = sorted(animation.get('frame', []), key=lambda frame: frame.get('frame_index', 0))
        timings.append((
            animation.get('namespace', 'default'),
            animation.get('frame_interval', DEFAULT_TOML_FRAME_INTERVAL),
            animation.get('loop', True),
            [frame.get('frame_interval') for frame in frames],
        ))
    return timings


@pytest.fixture
def real_display():
    """Give AnimatedSprite a real display for loading and saving."""
    pygame.init()
    if pygame.display.get_surface() is None:
        set_display_mode(size=(96, 64))


@pytest.mark.usefixtures('real_display')
@pytest.mark.parametrize('sprite_file', ANIMATED_SPRITE_FILES, ids=_animated_sprite_file_test_id)
def test_bundled_animation_timings_survive_a_save_round_trip(sprite_file, tmp_path):
    """Load -> save writes each animation's frame_interval, loop and per-frame overrides back.

    The writer used to hard-code frame_interval = 0.5 and loop = true, so saving (Bitmappy
    saves this way) lost every animation's timing.
    """
    import tomllib

    from glitchygames.sprites import AnimatedSprite

    original_sprite = AnimatedSprite(str(sprite_file))
    if original_sprite.get_total_frame_count() == 1:
        pytest.skip('single-frame sprites are saved in the static format, without timing')
    saved_file = tmp_path / sprite_file.name
    original_sprite.save(str(saved_file), 'toml')

    original_data = tomllib.loads(sprite_file.read_text(encoding='utf-8'))
    saved_data = tomllib.loads(saved_file.read_text(encoding='utf-8'))
    assert _animation_timings(saved_data) == _animation_timings(original_data)

    reloaded_sprite = AnimatedSprite(str(saved_file))
    for animation_name, frames in original_sprite._animations.items():
        reloaded_durations = [
            frame.duration for frame in reloaded_sprite._animations[animation_name]
        ]
        assert reloaded_durations == [frame.duration for frame in frames], animation_name


def _hitbox_sections(sprite_data: dict) -> tuple[dict | None, list[dict | None]]:
    """Return the hitboxes a sprite file defines explicitly.

    Returns:
        tuple[dict | None, list[dict | None]]: The [sprite.hitbox] table (or None) and each
        animation frame's [animation.frame.hitbox] (None where absent), in file order with
        frames in frame_index order.

    """
    frame_hitboxes: list[dict | None] = []
    for animation in sprite_data.get('animation', []):
        frames = sorted(animation.get('frame', []), key=lambda frame: frame.get('frame_index', 0))
        frame_hitboxes.extend(frame.get('hitbox') for frame in frames)
    return sprite_data.get('sprite', {}).get('hitbox'), frame_hitboxes


@pytest.mark.usefixtures('real_display')
@pytest.mark.parametrize('sprite_file', BUNDLED_SPRITE_FILES, ids=_sprite_file_test_id)
def test_bundled_hitboxes_survive_a_save_round_trip_unchanged(sprite_file, tmp_path):
    """Save writes exactly the hitboxes the file defined: none are synthesised.

    The writer used to turn the visible-pixel fallback into explicit [sprite.hitbox] and
    [animation.frame.hitbox] sections, so saving a sprite without hitboxes froze them.
    """
    import tomllib

    from glitchygames.sprites import AnimatedSprite

    original_sprite = AnimatedSprite(str(sprite_file))
    original_data = tomllib.loads(sprite_file.read_text(encoding='utf-8'))
    if original_sprite.get_total_frame_count() == 1 and 'animation' in original_data:
        pytest.skip('a one-frame animation is saved in the static format')
    saved_file = tmp_path / sprite_file.name
    original_sprite.save(str(saved_file), 'toml')

    saved_data = tomllib.loads(saved_file.read_text(encoding='utf-8'))
    assert _hitbox_sections(saved_data) == _hitbox_sections(original_data)


def _rgba_frames(sprite) -> dict[tuple[str, int], tuple[tuple[int, int], list[tuple[int, ...]]]]:
    """Return every frame's size and pixels as RGBA tuples (RGB pixels get alpha 255).

    Returns:
        dict: (animation name, frame position) -> (size, RGBA pixels).

    """
    frames = {}
    for animation_name, animation_frames in sprite._animations.items():
        for frame_position, frame in enumerate(animation_frames):
            rgba_pixels = [
                pixel if len(pixel) == 4 else (*pixel, 255) for pixel in frame.get_pixel_data()
            ]
            frames[animation_name, frame_position] = (frame.get_size(), rgba_pixels)
    return frames


@pytest.mark.usefixtures('real_display')
@pytest.mark.parametrize('sprite_file', BUNDLED_SPRITE_FILES, ids=_sprite_file_test_id)
def test_bundled_sprite_pixels_survive_a_save_round_trip(sprite_file, tmp_path):
    """Load -> save -> reload gives every frame (static and animated) the same pixels."""
    from glitchygames.sprites import AnimatedSprite

    original_sprite = AnimatedSprite(str(sprite_file))
    saved_file = tmp_path / sprite_file.name
    original_sprite.save(str(saved_file), 'toml')
    reloaded_sprite = AnimatedSprite(str(saved_file))

    original_frames = _rgba_frames(original_sprite)
    reloaded_frames = list(_rgba_frames(reloaded_sprite).values())
    # A one-frame sprite is saved in the static format, which may rename its animation
    assert len(reloaded_frames) == len(original_frames)
    for (frame_key, original_frame), reloaded_frame in zip(
        original_frames.items(), reloaded_frames, strict=True
    ):
        assert reloaded_frame == original_frame, frame_key


@pytest.mark.usefixtures('real_display')
@pytest.mark.parametrize('sprite_file', BUNDLED_SPRITE_FILES, ids=_sprite_file_test_id)
def test_bundled_sprite_metadata_survives_a_save_round_trip(sprite_file, tmp_path):
    """Load -> save -> reload keeps the [sprite] name, description, frame_anchor and hitbox.

    The single-frame (static) writer used to drop description.
    """
    from glitchygames.sprites import AnimatedSprite

    original_sprite = AnimatedSprite(str(sprite_file))
    saved_file = tmp_path / sprite_file.name
    original_sprite.save(str(saved_file), 'toml')
    reloaded_sprite = AnimatedSprite(str(saved_file))

    def metadata(sprite):
        return (sprite.name, sprite.description, sprite.frame_anchor, sprite.hitbox)

    assert metadata(reloaded_sprite) == metadata(original_sprite)


@pytest.mark.usefixtures('real_display')
def test_static_sprite_metadata_survives_a_save_round_trip(tmp_path):
    """A single-frame sprite keeps name, description, frame_anchor and hitbox when saved."""
    from glitchygames.sprites import AnimatedSprite

    sprite_file = tmp_path / 'static.toml'
    sprite_file.write_text(
        '[sprite]\nname = "rock"\ndescription = """A grey rock.\nIt does not move."""\n'
        'frame_anchor = "bottom"\npixels = """\n#.\n##\n"""\n\n'
        '[sprite.hitbox]\noffset_x = 0\noffset_y = 0\nwidth = 2\nheight = 2\n\n'
        '[colors."#"]\nred = 90\ngreen = 90\nblue = 90\n\n'
        '[colors."."]\nred = 255\ngreen = 0\nblue = 255\n',
        encoding='utf-8',
    )
    original_sprite = AnimatedSprite(str(sprite_file))
    saved_file = tmp_path / 'resaved.toml'
    original_sprite.save(str(saved_file), 'toml')
    reloaded_sprite = AnimatedSprite(str(saved_file))

    assert reloaded_sprite.description == 'A grey rock.\nIt does not move.'
    assert (reloaded_sprite.name, reloaded_sprite.frame_anchor, reloaded_sprite.hitbox) == (
        original_sprite.name,
        original_sprite.frame_anchor,
        original_sprite.hitbox,
    )


@pytest.mark.usefixtures('real_display')
@pytest.mark.parametrize('sprite_file', BUNDLED_SPRITE_FILES, ids=_sprite_file_test_id)
def test_bundled_transitions_survive_a_save_round_trip(sprite_file, tmp_path):
    """Load -> save writes every [[transition]] back with the same keys, values and order.

    The writers used to drop them, so saving (e.g. from Bitmappy) lost the animation state
    machine (cobra 2 -> 0 transitions, Papyrus player 6 -> 0).
    """
    import tomllib

    from glitchygames.sprites import AnimatedSprite

    original_data = tomllib.loads(sprite_file.read_text(encoding='utf-8'))
    saved_file = tmp_path / sprite_file.name
    AnimatedSprite(str(sprite_file)).save(str(saved_file), 'toml')

    saved_data = tomllib.loads(saved_file.read_text(encoding='utf-8'))
    assert saved_data.get('transition', []) == original_data.get('transition', [])


@pytest.mark.usefixtures('real_display')
@pytest.mark.parametrize('frame_count', [1, 2], ids=['single-frame-writer', 'animated-writer'])
def test_names_and_descriptions_needing_escapes_round_trip(frame_count, tmp_path):
    """Quotes, backslashes, triple quotes and a leading newline survive both writers."""
    import pygame as real_pygame

    from glitchygames.sprites import AnimatedSprite, SpriteFrame

    sprite = AnimatedSprite()
    frames = [SpriteFrame(real_pygame.Surface((2, 2))) for _ in range(frame_count)]
    for frame in frames:
        frame.pixels = [(0, 0, 0)] * 4
    sprite.add_animation('idle', frames)
    sprite.name = 'say "hi" \\ bye'
    sprite.description = '\nFirst line with """triple quotes""" and a \\ backslash.\nSecond line.'
    saved_file = tmp_path / 'escapes.toml'

    sprite.save(str(saved_file), 'toml')
    reloaded_sprite = AnimatedSprite(str(saved_file))

    assert (reloaded_sprite.name, reloaded_sprite.description) == (
        sprite.name,
        sprite.description,
    )
