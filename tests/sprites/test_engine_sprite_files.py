"""The engine's checks of a bundled sprite file, run on the engine's own sprites.

Every pixel row is the same width, and a save round trip keeps each sprite's timings,
hitboxes, pixels, metadata and transitions. The checks are glitchygames.testing.sprite_files; a
package with sprites of its own runs them on them from its own tests (Papyrus's, and Bitmappy's
sprite library in src/apps/bitmappy/tests/test_bitmappy_sprite_library.py).
"""

from pathlib import Path
from typing import TYPE_CHECKING

import pygame
import pytest

import glitchygames
from glitchygames.display_mode import set_display_mode
from glitchygames.testing import sprite_files

if TYPE_CHECKING:
    from glitchygames.sprites import AnimatedSprite

# The imported engine's directory (installed: never the source tree by accident)
ENGINE_PACKAGE_DIRECTORY = Path(glitchygames.__file__).resolve().parent

# The engine's sprites. A package with sprites of its own checks them with the same checks from its
# own tests (Papyrus's: src/games/brave-adventurer/tests/papyrus/; Bitmappy's sprite library:
# src/apps/bitmappy/tests/test_bitmappy_sprite_library.py)
BUNDLED_SPRITE_FILES = sorted((ENGINE_PACKAGE_DIRECTORY / 'assets').glob('*.toml'))

# The engine's own sprite test data. The engine bundles no animated sprite, so the animated-sprite
# checks also run on these fixtures (colors.toml and girl.toml are animated)
TESTS_DIRECTORY = Path(__file__).resolve().parents[1]
SPRITE_FIXTURES_DIRECTORY = TESTS_DIRECTORY / 'fixtures' / 'sprites'
ANIMATED_SPRITE_FILES = sprite_files.animated_sprite_files(
    directories=[ENGINE_PACKAGE_DIRECTORY / 'assets', SPRITE_FIXTURES_DIRECTORY]
)


def _sprite_file_test_id(sprite_file: Path) -> str:
    """Name a bundled sprite file relative to the engine (the same id under nox and uv run).

    Returns:
        str: The file's path inside the engine package, e.g. ``assets/eraser.toml``.

    """
    return sprite_file.relative_to(ENGINE_PACKAGE_DIRECTORY).as_posix()


def _animated_sprite_file_test_id(sprite_file: Path) -> str:
    """Name an animated sprite file: a bundled one inside the engine, a fixture inside tests/.

    Returns:
        str: ``assets/<name>.toml`` for a bundled sprite, ``fixtures/sprites/<name>.toml`` for a
        fixture.

    """
    if sprite_file.is_relative_to(ENGINE_PACKAGE_DIRECTORY):
        return _sprite_file_test_id(sprite_file)
    return sprite_file.relative_to(TESTS_DIRECTORY).as_posix()


@pytest.fixture
def real_display():
    """Give AnimatedSprite a real display for loading and saving."""
    pygame.init()
    if pygame.display.get_surface() is None:
        set_display_mode(size=(96, 64))


@pytest.mark.parametrize('sprite_file', BUNDLED_SPRITE_FILES, ids=_sprite_file_test_id)
def test_bundled_sprite_rows_have_equal_lengths(sprite_file):
    """Every pixel row in a bundled sprite is the same width."""
    sprite_files.check_rows_have_equal_lengths(sprite_file=sprite_file)


def test_the_animated_sprite_checks_have_sprites_to_run_on():
    """The animated-sprite checks never run on nothing (an empty parameter set only skips)."""
    assert ANIMATED_SPRITE_FILES


@pytest.mark.usefixtures('real_display')
@pytest.mark.parametrize('sprite_file', ANIMATED_SPRITE_FILES, ids=_animated_sprite_file_test_id)
def test_bundled_animation_timings_survive_a_save_round_trip(sprite_file, tmp_path):
    """Load -> save writes each animation's frame_interval, loop and per-frame overrides back."""
    sprite_files.check_animation_timings_survive_a_save_round_trip(
        sprite_file=sprite_file, directory=tmp_path
    )


@pytest.mark.usefixtures('real_display')
@pytest.mark.parametrize('sprite_file', BUNDLED_SPRITE_FILES, ids=_sprite_file_test_id)
def test_bundled_hitboxes_survive_a_save_round_trip_unchanged(sprite_file, tmp_path):
    """Save writes exactly the hitboxes the file defined: none are synthesized."""
    sprite_files.check_hitboxes_survive_a_save_round_trip_unchanged(
        sprite_file=sprite_file, directory=tmp_path
    )


@pytest.mark.usefixtures('real_display')
@pytest.mark.parametrize('sprite_file', BUNDLED_SPRITE_FILES, ids=_sprite_file_test_id)
def test_bundled_sprite_pixels_survive_a_save_round_trip(sprite_file, tmp_path):
    """Load -> save -> reload gives every frame (static and animated) the same pixels."""
    sprite_files.check_pixels_survive_a_save_round_trip(sprite_file=sprite_file, directory=tmp_path)


@pytest.mark.usefixtures('real_display')
@pytest.mark.parametrize('sprite_file', BUNDLED_SPRITE_FILES, ids=_sprite_file_test_id)
def test_bundled_sprite_metadata_survives_a_save_round_trip(sprite_file, tmp_path):
    """Load -> save -> reload keeps the [sprite] name, description, frame_anchor and hitbox."""
    sprite_files.check_metadata_survives_a_save_round_trip(
        sprite_file=sprite_file, directory=tmp_path
    )


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


@pytest.mark.parametrize('sprite_file', BUNDLED_SPRITE_FILES, ids=_sprite_file_test_id)
def test_bundled_sprite_tags_are_well_formed(sprite_file):
    """Every bundled sprite's [sprite] tags, if any, is an array of strings."""
    sprite_files.check_sprite_tags_are_well_formed(sprite_file=sprite_file)


def _two_by_two_sprite(*, frame_count: int) -> AnimatedSprite:
    """Return a sprite of 2x2 black frames: one for the single-frame writer, two for the other.

    Returns:
        The sprite, with no name, description or tags set.

    """
    from glitchygames.sprites import AnimatedSprite, SpriteFrame

    sprite = AnimatedSprite()
    frames = [SpriteFrame(pygame.Surface((2, 2))) for _ in range(frame_count)]
    for frame in frames:
        frame.pixels = [(0, 0, 0)] * 4
    sprite.add_animation('idle', frames)
    return sprite


@pytest.mark.usefixtures('real_display')
@pytest.mark.parametrize('frame_count', [1, 2], ids=['single-frame-writer', 'animated-writer'])
def test_tags_round_trip_right_after_the_description(frame_count, tmp_path):
    """Both writers write the tags after the description; a reload has them, in order."""
    from glitchygames.sprites import AnimatedSprite

    sprite = _two_by_two_sprite(frame_count=frame_count)
    sprite.description = 'A sword.'
    sprite.tags = ['weapon', 'item', 'say "hi"']
    saved_file = tmp_path / 'tagged.toml'

    sprite.save(str(saved_file), 'toml')

    assert AnimatedSprite(str(saved_file)).tags == ['weapon', 'item', 'say "hi"']
    lines = saved_file.read_text(encoding='utf-8').splitlines()
    tags_line = 'tags = ["weapon", "item", "say \\"hi\\""]'
    assert lines.index(tags_line) == lines.index('description = """A sword."""') + 1


@pytest.mark.usefixtures('real_display')
@pytest.mark.parametrize('frame_count', [1, 2], ids=['single-frame-writer', 'animated-writer'])
def test_a_sprite_without_tags_writes_no_tags(frame_count, tmp_path):
    """A sprite with no tags is written without the key, as before tags existed."""
    from glitchygames.sprites import AnimatedSprite

    sprite = _two_by_two_sprite(frame_count=frame_count)
    saved_file = tmp_path / 'untagged.toml'

    sprite.save(str(saved_file), 'toml')

    assert 'tags' not in saved_file.read_text(encoding='utf-8')
    assert AnimatedSprite(str(saved_file)).tags == []


@pytest.mark.usefixtures('real_display')
def test_a_files_tags_load_in_their_one_spelling(tmp_path):
    """Loaded tags are normalized: case, spaces and repeats."""
    from glitchygames.sprites import AnimatedSprite

    sprite_file = tmp_path / 'spelled.toml'
    sprite_file.write_text(
        """[sprite]
name = "rock"
tags = ["Stone ", "ROCK", "stone"]
pixels = '''
#
'''

[colors."#"]
red = 90
green = 90
blue = 90
""",
        encoding='utf-8',
    )

    assert AnimatedSprite(str(sprite_file)).tags == ['stone', 'rock']


@pytest.mark.parametrize(
    ('tags_toml', 'problem'),
    [('"rock"', "tags must be an array of strings, not 'rock'"), ('["rock", 3]', 'tag 2')],
    ids=['not-an-array', 'not-a-string'],
)
def test_malformed_tags_fail_the_well_formed_check(tags_toml, problem, tmp_path):
    """The check names the file and the problem."""
    sprite_file = tmp_path / 'malformed.toml'
    sprite_file.write_text(f'[sprite]\nname = "rock"\ntags = {tags_toml}\n', encoding='utf-8')

    with pytest.raises(AssertionError, match=problem):
        sprite_files.check_sprite_tags_are_well_formed(sprite_file=sprite_file)


@pytest.mark.usefixtures('real_display')
@pytest.mark.parametrize('sprite_file', BUNDLED_SPRITE_FILES, ids=_sprite_file_test_id)
def test_bundled_transitions_survive_a_save_round_trip(sprite_file, tmp_path):
    """Load -> save writes every [[transition]] back with the same keys, values and order."""
    sprite_files.check_transitions_survive_a_save_round_trip(
        sprite_file=sprite_file, directory=tmp_path
    )


@pytest.mark.usefixtures('real_display')
@pytest.mark.parametrize('frame_count', [1, 2], ids=['single-frame-writer', 'animated-writer'])
def test_names_and_descriptions_needing_escapes_round_trip(frame_count, tmp_path):
    """Quotes, backslashes, triple quotes and a leading newline survive both writers."""
    from glitchygames.sprites import AnimatedSprite, SpriteFrame

    sprite = AnimatedSprite()
    frames = [SpriteFrame(pygame.Surface((2, 2))) for _ in range(frame_count)]
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
