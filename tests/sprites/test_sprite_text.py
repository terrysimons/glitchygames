"""Tests for sprite_text: a sprite loaded from text, by the one path a file's load also takes."""

import logging

import pygame
import pytest

from glitchygames.display_mode import set_display_mode
from glitchygames.sprites import AnimatedSprite, SpriteFactory
from glitchygames.sprites.sprite_text import sprite_from_text, sprite_to_text
from glitchygames.sprites.sprite_toml import parse_sprite_toml
from glitchygames.testing.sprite_files import check_text_and_file_loads_agree

# A static sprite whose second row is shorter than its first: the loader repairs it and says so
SHORT_ROW_TEXT = """\
[sprite]
name = "dex"
pixels = \"\"\"
##
#
\"\"\"

[colors."#"]
red = 0
green = 0
blue = 0
"""

# One animation of two one-pixel frames, the second frame's pixel on a longer hold
ANIMATED_TEXT = """\
[sprite]
name = "blink"
description = "two frames"

[[animation]]
namespace = "blink"
frame_interval = 0.25
loop = false

[[animation.frame]]
namespace = "blink"
frame_index = 0
pixels = \"\"\"
#
\"\"\"

[[animation.frame]]
namespace = "blink"
frame_index = 1
frame_interval = 1.5
pixels = \"\"\"
.
\"\"\"

[colors."#"]
red = 0
green = 0
blue = 0

[colors."."]
red = 255
green = 255
blue = 255
"""

# Pixels in [sprite] and an [[animation]] in one document: a file like this is refused
MIXED_TEXT = (
    SHORT_ROW_TEXT
    + """
[[animation]]
namespace = "idle"
"""
)


@pytest.fixture(autouse=True)
def display():
    """Give AnimatedSprite a real display for loading and saving."""
    pygame.init()
    if pygame.display.get_surface() is None:
        set_display_mode(size=(96, 64))


def test_the_agreement_check_fails_when_the_text_loads_differently(tmp_path, mocker):
    """The check can fail: a text load that changes the sprite is reported with the file."""
    sprite_file = tmp_path / 'blink.toml'
    sprite_file.write_text(ANIMATED_TEXT, encoding='utf-8')

    def load_a_slower_sprite(*, text, source_name):
        sprite = sprite_from_text(text=text, source_name=source_name)
        sprite.animations['blink'][0].duration = 9.0
        return sprite

    mocker.patch(
        'glitchygames.testing.sprite_files.sprite_from_text', side_effect=load_a_slower_sprite
    )

    with pytest.raises(AssertionError, match=r'blink\.toml: animation_metadata'):
        check_text_and_file_loads_agree(sprite_file=sprite_file)


def test_repair_warnings_name_the_text_source(caplog):
    """A repair made while loading text names where the text came from."""
    with caplog.at_level(logging.WARNING):
        sprite = sprite_from_text(text=SHORT_ROW_TEXT, source_name='dex from the console')

    assert 'dex from the console' in caplog.text
    assert sprite.pixel_row_repairs


def test_an_animated_text_loads_every_animation_key():
    """An animated text loads its name, description, timings and animation order."""
    sprite = sprite_from_text(text=ANIMATED_TEXT, source_name='blink from the console')

    assert isinstance(sprite, AnimatedSprite)
    assert sprite.name == 'blink'
    assert sprite.description == 'two frames'
    assert [frame.duration for frame in sprite.animations['blink']] == [0.25, 1.5]
    assert sprite.animation_order == ['blink']


def test_text_that_is_not_toml_is_refused_naming_its_source():
    """Text that is not TOML is refused, and the error names where it came from."""
    with pytest.raises(ValueError, match='dex from the console is not valid TOML'):
        sprite_from_text(text='[sprite\n', source_name='dex from the console')


def test_a_file_that_is_not_toml_is_refused_naming_the_file(tmp_path):
    """A file that is not TOML is refused by the text load, naming the file."""
    bad_file = tmp_path / 'bad.toml'
    bad_file.write_text('[sprite\n', encoding='utf-8')

    with pytest.raises(ValueError, match=r'bad\.toml is not valid TOML'):
        AnimatedSprite(str(bad_file))


def test_a_file_that_is_not_utf8_is_refused_naming_the_file(tmp_path):
    """A file whose bytes are not UTF-8 is refused, naming the file."""
    bad_file = tmp_path / 'latin.toml'
    bad_file.write_bytes(b'[sprite]\nname = "caf\xe9"\n')

    with pytest.raises(ValueError, match=r'Error loading TOML file .*latin\.toml'):
        AnimatedSprite(str(bad_file))


def test_a_missing_file_is_still_a_file_not_found_error(tmp_path):
    """A missing file still raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match='Sprite file not found'):
        AnimatedSprite(str(tmp_path / 'missing.toml'))


def test_loading_text_makes_no_temporary_file(mocker):
    """Text loads straight from memory: nothing asks the temporary-file module for a file."""
    named_temporary_file = mocker.patch('tempfile.NamedTemporaryFile')
    temporary_directory = mocker.patch('tempfile.TemporaryDirectory')
    make_temporary_file = mocker.patch('tempfile.mkstemp')

    SpriteFactory.load_sprite_from_text(text=SHORT_ROW_TEXT, source_name='test')

    for temporary in (named_temporary_file, temporary_directory, make_temporary_file):
        temporary.assert_not_called()


def test_the_factory_loads_static_text_as_an_animated_sprite():
    """The factory loads static text as a one-frame AnimatedSprite."""
    sprite = SpriteFactory.load_sprite_from_text(text=SHORT_ROW_TEXT, source_name='dex')

    assert isinstance(sprite, AnimatedSprite)
    assert sprite.name == 'dex'


def test_text_with_static_and_animated_content_is_refused_as_a_file_is(tmp_path):
    """The factory refuses mixed text, and refuses the same content in a file the same way."""
    mixed_file = tmp_path / 'mixed.toml'
    mixed_file.write_text(MIXED_TEXT, encoding='utf-8')

    with pytest.raises(ValueError, match='Invalid sprite file') as from_file:
        SpriteFactory.load_sprite(filename=str(mixed_file))
    with pytest.raises(ValueError, match='Invalid sprite file') as from_text:
        SpriteFactory.load_sprite_from_text(text=MIXED_TEXT, source_name='test')

    assert str(from_text.value) == str(from_file.value)


def test_text_without_any_sprite_content_is_refused():
    """Text with neither pixels nor animations is refused as a file is."""
    with pytest.raises(ValueError, match='Invalid sprite file'):
        SpriteFactory.load_sprite_from_text(text='[sprite]\nname = "empty"\n', source_name='test')


def test_the_factory_refuses_a_file_that_is_not_toml_as_it_refuses_the_same_text(tmp_path):
    """Both routes name the source and say "is not valid TOML", for the same bad TOML."""
    bad_file = tmp_path / 'bad.toml'
    bad_file.write_text('[sprite\n', encoding='utf-8')

    with pytest.raises(ValueError, match=r'bad\.toml is not valid TOML') as from_file:
        SpriteFactory.load_sprite(filename=str(bad_file))
    with pytest.raises(ValueError, match=r'bad\.toml is not valid TOML') as from_text:
        SpriteFactory.load_sprite_from_text(text='[sprite\n', source_name=str(bad_file))

    assert str(from_text.value) == str(from_file.value)


def test_a_single_frame_sprite_is_written_in_the_static_layout():
    """One animation with one frame is written with its pixels in [sprite], as save always did."""
    text = sprite_to_text(sprite=sprite_from_text(text=SHORT_ROW_TEXT, source_name='static'))

    document = parse_sprite_toml(text=text, source_name='written')
    assert 'pixels' in document['sprite']
    assert 'animation' not in document


def test_an_animated_sprite_is_written_with_its_animations():
    """Several frames are written as [[animation]] tables, and the text loads back the same."""
    sprite = sprite_from_text(text=ANIMATED_TEXT, source_name='animated')
    text = sprite_to_text(sprite=sprite)

    document = parse_sprite_toml(text=text, source_name='written')
    assert 'pixels' not in document['sprite']
    assert len(document['animation'][0]['frame']) == 2
    reloaded = sprite_from_text(text=text, source_name='reloaded')
    assert reloaded.animations.keys() == sprite.animations.keys()
    assert [frame.get_pixel_data() for frame in reloaded.animations['blink']] == [
        frame.get_pixel_data() for frame in sprite.animations['blink']
    ]


def test_to_text_is_what_sprite_to_text_returns():
    """The method and the interface function are the same text."""
    sprite = sprite_from_text(text=ANIMATED_TEXT, source_name='animated')

    assert sprite.to_text() == sprite_to_text(sprite=sprite)


def test_save_writes_the_text_and_refuses_other_formats(tmp_path):
    """Save writes to_text() for a single-frame sprite, and refuses a format it cannot write."""
    sprite = sprite_from_text(text=SHORT_ROW_TEXT, source_name='static')
    saved_file = tmp_path / 'dex.toml'

    sprite.save(str(saved_file), 'toml')

    assert saved_file.read_text(encoding='utf-8') == sprite.to_text()
    with pytest.raises(ValueError, match='ormat'):
        sprite.save(str(saved_file), 'png')
