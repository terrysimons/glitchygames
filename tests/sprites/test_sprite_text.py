"""Tests for sprite_text: a sprite loaded from text, by the one path a file's load also takes."""

import logging

import pygame
import pytest

from glitchygames.color import RGBA_COMPONENT_COUNT
from glitchygames.display_mode import set_display_mode
from glitchygames.sprites import AnimatedSprite, SpriteFactory
from glitchygames.sprites.constants import SPRITE_GLYPHS
from glitchygames.sprites.frame import SpriteFrame
from glitchygames.sprites.sprite_text import (
    SpriteColorLimitError,
    sprite_from_text,
    sprite_text_from_frames,
    sprite_to_text,
    surface_rgba_pixels,
)
from glitchygames.sprites.sprite_toml import parse_sprite_toml, write_sprite_toml
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

# Two glyphs, b and B, share one color (as slime-jump's do); c is a second color
TWO_GLYPHS_ONE_COLOR_TEXT = """\
[sprite]
name = "twins"
pixels = \"\"\"
bBc
\"\"\"

[colors.b]
red = 80
green = 220
blue = 120

[colors.B]
red = 80
green = 220
blue = 120

[colors.c]
red = 0
green = 0
blue = 255
"""

# A palette entry no pixel uses: x, translucent, between the two used colors
UNUSED_COLOR_TEXT = """\
[sprite]
name = "spare"

[[animation]]
namespace = "spare"
frame_interval = 0.5
loop = true

[[animation.frame]]
namespace = "spare"
frame_index = 0
pixels = \"\"\"
#o
\"\"\"

[[animation.frame]]
namespace = "spare"
frame_index = 1
pixels = \"\"\"
o#
\"\"\"

[colors."#"]
red = 0
green = 0
blue = 0

[colors.x]
red = 10
green = 20
blue = 30
alpha = 100

[colors.o]
red = 255
green = 128
blue = 0
"""

# Frame tables without frame_index, as Papyrus's cobra writes them: the loader plays them in
# file order
NO_FRAME_INDEX_TEXT = """\
[sprite]
name = "coil"

[[animation]]
namespace = "idle"
frame_interval = 0.5
loop = true

[[animation.frame]]
namespace = "idle"
pixels = \"\"\"
#.
\"\"\"

[[animation.frame]]
namespace = "idle"
pixels = \"\"\"
.#
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

# A game's own top-level table, as Drawing Fire's soldier carries its livery swatches
SWATCHES_TEXT = """\
[sprite]
name = "trooper"
pixels = \"\"\"
hH
\"\"\"

[colors.h]
red = 200
green = 30
blue = 30

[colors.H]
red = 120
green = 10
blue = 10

[swatches.livery.helmet]
role = "primary"
colors = ["h", "H"]
"""

# The palette gives the transparency key's usual glyph to an ordinary color
KEY_GLYPH_TAKEN_TEXT = """\
[sprite]
name = "taken"
pixels = \"\"\"
\u2588#
\"\"\"

[colors."\u2588"]
red = 200
green = 0
blue = 0

[colors."#"]
red = 0
green = 0
blue = 0
"""

GREEN = (0, 255, 0)
SHARED_COLOR = (80, 220, 120)

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


def solid_surface(*, size, color):
    """Build a SRCALPHA surface of one color.

    Returns:
        The surface.

    """
    surface = pygame.Surface(size, pygame.SRCALPHA)
    surface.fill(color)
    return surface


def only_animation_frames(sprite):
    """Return the frames of the sprite's only animation.

    Returns:
        The frame list.

    """
    assert len(sprite.animations) == 1
    return next(iter(sprite.animations.values()))


def test_frames_become_one_animation_with_each_frames_own_interval():
    """Each surface becomes a frame of one animation named for the sprite, with its interval."""
    text = sprite_text_from_frames(
        frames=[
            solid_surface(size=(4, 4), color=(255, 0, 0, 255)),
            solid_surface(size=(4, 4), color=(0, 0, 255, 255)),
        ],
        frame_intervals=[0.1, 0.25],
        name='blink',
    )

    sprite = sprite_from_text(text=text, source_name='t')

    assert list(sprite.animations) == ['blink']
    assert [frame.duration for frame in only_animation_frames(sprite)] == [0.1, 0.25]
    # Opaque colors load as plain RGB
    assert [frame.get_pixel_data()[0] for frame in only_animation_frames(sprite)] == [
        (255, 0, 0),
        (0, 0, 255),
    ]


def test_one_frame_is_written_in_the_static_layout_and_round_trips():
    """A single surface is a static sprite whose pixels load back exactly."""
    surface = solid_surface(size=(3, 2), color=(50, 60, 70, 255))
    surface.set_at((0, 0), (1, 2, 3, 255))
    surface.set_at((1, 0), (4, 5, 6, 255))
    surface.set_at((2, 1), (7, 8, 9, 255))

    text = sprite_text_from_frames(frames=[surface], frame_intervals=[0.1], name='one')

    assert 'pixels' in parse_sprite_toml(text=text, source_name='t')['sprite']
    reloaded = sprite_from_text(text=text, source_name='t')
    # Opaque pixels may load as plain RGB; compare them as RGBA
    reloaded_pixels = [
        pixel if len(pixel) == RGBA_COMPONENT_COUNT else (*pixel, 255)
        for pixel in only_animation_frames(reloaded)[0].get_pixel_data()
    ]
    assert reloaded_pixels == surface_rgba_pixels(surface=surface)


def test_partial_alpha_is_kept():
    """A pixel with partial alpha is written with its alpha."""
    text = sprite_text_from_frames(
        frames=[solid_surface(size=(4, 4), color=(255, 0, 0, 128))],
        frame_intervals=[0.1],
        name='glass',
    )

    colors = parse_sprite_toml(text=text, source_name='t')['colors'].values()

    assert {'red': 255, 'green': 0, 'blue': 0, 'alpha': 128} in colors


def distinct_color_surface(*, color_count):
    """Build a surface of color_count distinct opaque colors in a row.

    Returns:
        The surface.

    """
    surface = pygame.Surface((color_count, 1), pygame.SRCALPHA)
    for x in range(color_count):
        surface.set_at((x, 0), (x, 10, 20, 255))
    return surface


def test_more_colors_than_glyphs_is_refused_with_the_count():
    """One more color than the glyph set holds is refused, with the count and the limit."""
    too_many = len(SPRITE_GLYPHS) + 1

    with pytest.raises(SpriteColorLimitError) as refusal:
        sprite_text_from_frames(
            frames=[distinct_color_surface(color_count=too_many)],
            frame_intervals=[0.1],
            name='photo',
        )

    assert (refusal.value.color_count, refusal.value.limit) == (too_many, len(SPRITE_GLYPHS))
    # The same check with literal values: it pins today's limit of 64 glyphs
    assert (refusal.value.color_count, refusal.value.limit) == (65, 64)
    assert isinstance(refusal.value, ValueError)


def test_the_colors_of_all_frames_are_counted_together():
    """Colors are counted across frames, not per frame."""
    half = len(SPRITE_GLYPHS) // 2 + 1
    first = distinct_color_surface(color_count=half)
    second = pygame.Surface((half, 1), pygame.SRCALPHA)
    for x in range(half):
        second.set_at((x, 0), (x, 200, 20, 255))

    with pytest.raises(SpriteColorLimitError):
        sprite_text_from_frames(frames=[first, second], frame_intervals=[0.1, 0.1], name='x')


def test_exactly_as_many_colors_as_glyphs_is_accepted():
    """The limit itself is allowed."""
    text = sprite_text_from_frames(
        frames=[distinct_color_surface(color_count=len(SPRITE_GLYPHS))],
        frame_intervals=[0.1],
        name='full',
    )

    assert len(parse_sprite_toml(text=text, source_name='t')['colors']) == len(SPRITE_GLYPHS)


@pytest.mark.parametrize('intervals', [[], [0.1, 0.1]])
def test_intervals_must_match_the_frames(intervals):
    """A count of intervals that differs from the frames is refused, naming frame_intervals."""
    with pytest.raises(ValueError, match='frame_intervals'):
        sprite_text_from_frames(
            frames=[solid_surface(size=(4, 4), color=(255, 0, 0, 255))],
            frame_intervals=intervals,
            name='x',
        )


def test_no_frames_is_refused():
    """No frames is refused, naming frames."""
    with pytest.raises(ValueError, match='at least one frame'):
        sprite_text_from_frames(frames=[], frame_intervals=[], name='x')


def test_frames_of_different_sizes_are_refused():
    """Frames of different sizes are refused, naming size."""
    with pytest.raises(ValueError, match='size'):
        sprite_text_from_frames(
            frames=[
                solid_surface(size=(4, 4), color=(255, 0, 0, 255)),
                solid_surface(size=(8, 8), color=(255, 0, 0, 255)),
            ],
            frame_intervals=[0.1, 0.1],
            name='x',
        )


def test_surface_rgba_pixels_are_row_major_with_alpha():
    """Pixels come row by row, x within y, as (red, green, blue, alpha)."""
    surface = pygame.Surface((2, 2), pygame.SRCALPHA)
    surface.set_at((0, 0), (1, 2, 3, 4))
    surface.set_at((1, 0), (5, 6, 7, 8))
    surface.set_at((0, 1), (9, 10, 11, 12))
    surface.set_at((1, 1), (13, 14, 15, 16))

    assert surface_rgba_pixels(surface=surface) == [
        (1, 2, 3, 4),
        (5, 6, 7, 8),
        (9, 10, 11, 12),
        (13, 14, 15, 16),
    ]


def test_surface_rgba_pixels_of_a_surface_without_alpha_are_opaque():
    """A surface with no alpha channel reads as fully opaque."""
    surface = pygame.Surface((2, 1))
    surface.fill((10, 20, 30))

    assert surface_rgba_pixels(surface=surface) == [(10, 20, 30, 255), (10, 20, 30, 255)]


def drawn_over(*, sprite, background_color):
    """Blit the sprite's drawn image onto a surface of one color.

    Returns:
        The RGB of each pixel of the first row.

    """
    background = pygame.Surface(sprite.image.get_size())
    background.fill(background_color)
    background.blit(sprite.image, (0, 0))
    return [tuple(background.get_at((x, 0)))[:3] for x in range(background.get_width())]


def test_every_transparent_pixel_is_one_color_whatever_its_rgb():
    """Pixels of alpha 0 with different RGBs are one color: they cost one glyph, not several."""
    visible_colors = len(SPRITE_GLYPHS) - 1
    surface = distinct_color_surface(color_count=visible_colors + 3)
    for x, rgb in enumerate([(0, 0, 0), (9, 9, 9), (1, 2, 3)], start=visible_colors):
        surface.set_at((x, 0), (*rgb, 0))

    text = sprite_text_from_frames(frames=[surface], frame_intervals=[0.1], name='ghost')

    colors = parse_sprite_toml(text=text, source_name='t')['colors']
    assert len(colors) == visible_colors + 1


def test_a_full_glyph_set_of_visible_colors_and_transparent_pixels_is_accepted():
    """The limit counts visible colors: transparent pixels of any RGB add none."""
    visible_colors = len(SPRITE_GLYPHS)
    surface = distinct_color_surface(color_count=visible_colors + 2)
    surface.set_at((visible_colors, 0), (0, 0, 0, 0))
    surface.set_at((visible_colors + 1, 0), (9, 9, 9, 0))

    text = sprite_text_from_frames(frames=[surface], frame_intervals=[0.1], name='full')

    assert sprite_from_text(text=text, source_name='t').animations['full']


def test_transparent_pixels_load_back_transparent():
    """Alpha 0 pixels, whatever their RGB, load as the transparency key and draw as nothing."""
    surface = pygame.Surface((3, 1), pygame.SRCALPHA)
    surface.set_at((0, 0), (0, 0, 0, 0))
    surface.set_at((1, 0), (9, 9, 9, 0))
    surface.set_at((2, 0), (255, 0, 0, 255))

    sprite = sprite_from_text(
        text=sprite_text_from_frames(frames=[surface], frame_intervals=[0.1], name='ghost'),
        source_name='t',
    )

    # The loaded frame reports the transparency key (magenta) for them
    assert only_animation_frames(sprite)[0].get_pixel_data() == [
        (255, 0, 255),
        (255, 0, 255),
        (255, 0, 0),
    ]
    assert drawn_over(sprite=sprite, background_color=(10, 20, 30)) == [
        (10, 20, 30),
        (10, 20, 30),
        (255, 0, 0),
    ]


def test_an_opaque_magenta_pixel_becomes_transparent_as_the_format_cannot_hold_it():
    """Opaque magenta is the format's transparency key: it loads and draws as transparent.

    The image loses that color; it is not changed to another. The docs page says so.
    """
    surface = pygame.Surface((2, 1), pygame.SRCALPHA)
    surface.set_at((0, 0), (255, 0, 255, 255))
    surface.set_at((1, 0), (255, 0, 0, 255))

    sprite = sprite_from_text(
        text=sprite_text_from_frames(frames=[surface], frame_intervals=[0.1], name='key'),
        source_name='t',
    )

    # The frame's pixels hold the key's RGB, the same as a transparent pixel's
    assert only_animation_frames(sprite)[0].get_pixel_data() == [(255, 0, 255), (255, 0, 0)]
    assert drawn_over(sprite=sprite, background_color=(10, 20, 30)) == [(10, 20, 30), (255, 0, 0)]


def saved_document(*, sprite):
    """Write a sprite and parse the text, as a reader of the saved file sees it.

    Returns:
        The parsed document of the sprite's text.

    """
    return parse_sprite_toml(text=sprite_to_text(sprite=sprite), source_name='saved')


def test_two_glyphs_sharing_a_color_both_survive_a_save():
    """An unchanged frame keeps its loaded rows glyph for glyph, so b and B both stay."""
    sprite = sprite_from_text(text=TWO_GLYPHS_ONE_COLOR_TEXT, source_name='twins')

    assert saved_document(sprite=sprite) == parse_sprite_toml(
        text=TWO_GLYPHS_ONE_COLOR_TEXT, source_name='twins'
    )


def test_an_unused_color_survives_a_save():
    """Every [colors] entry is written, used or not, in the file's order, alpha and all."""
    sprite = sprite_from_text(text=UNUSED_COLOR_TEXT, source_name='spare')

    document = saved_document(sprite=sprite)

    assert document == parse_sprite_toml(text=UNUSED_COLOR_TEXT, source_name='spare')
    assert list(document['colors']) == ['#', 'x', 'o']


def test_an_edited_pixel_takes_the_first_glyph_of_its_color():
    """An edited frame writes each pixel with the first remembered glyph of its color.

    Every remembered entry is still written, B among them, though no pixel uses it any more.
    """
    sprite = sprite_from_text(text=TWO_GLYPHS_ONE_COLOR_TEXT, source_name='twins')
    (frame,) = only_animation_frames(sprite)
    frame.set_pixel_data([SHARED_COLOR, SHARED_COLOR, SHARED_COLOR])

    document = saved_document(sprite=sprite)

    assert document['sprite']['pixels'] == 'bbb\n'
    assert (
        document['colors']
        == parse_sprite_toml(text=TWO_GLYPHS_ONE_COLOR_TEXT, source_name='twins')['colors']
    )


def test_an_edited_pixel_of_a_new_color_gets_a_new_glyph():
    """A color the palette doesn't have gets a glyph of its own, after the remembered ones."""
    sprite = sprite_from_text(text=TWO_GLYPHS_ONE_COLOR_TEXT, source_name='twins')
    (frame,) = only_animation_frames(sprite)
    frame.set_pixel_data([SHARED_COLOR, GREEN, (0, 0, 255)])

    document = saved_document(sprite=sprite)

    *remembered_glyphs, new_glyph = document['colors']
    assert remembered_glyphs == ['b', 'B', 'c']
    assert new_glyph in SPRITE_GLYPHS
    assert document['colors'][new_glyph] == {'red': 0, 'green': 255, 'blue': 0}
    assert document['sprite']['pixels'] == f'b{new_glyph}c\n'


def test_only_the_edited_frame_of_an_animation_changes_its_glyphs():
    """An unchanged frame keeps its rows beside an edited one in the same sprite."""
    sprite = sprite_from_text(text=TWO_GLYPHS_ONE_COLOR_TEXT, source_name='twins')
    edited_frame = SpriteFrame(pygame.Surface((3, 1)))
    edited_frame.set_pixel_data([SHARED_COLOR, SHARED_COLOR, SHARED_COLOR])
    sprite.add_frame(sprite.animation_order[0], edited_frame)

    document = saved_document(sprite=sprite)

    (animation,) = document['animation']
    assert [frame['pixels'] for frame in animation['frame']] == ['bBc\n', 'bbb\n']


def test_a_repaired_frame_is_written_by_its_colors():
    """A frame whose rows the load repaired is written from its pixels, never the bad rows."""
    sprite = sprite_from_text(text=SHORT_ROW_TEXT, source_name='dex')

    document = saved_document(sprite=sprite)

    assert '\x00' not in document['sprite']['pixels']
    assert (
        sprite_from_text(text=sprite_to_text(sprite=sprite), source_name='saved').pixel_row_repairs
        == []
    )


def test_an_animation_loaded_without_frame_index_is_saved_without_it():
    """Frames that named no frame_index are written without one, so the document is the same."""
    sprite = sprite_from_text(text=NO_FRAME_INDEX_TEXT, source_name='coil')

    assert saved_document(sprite=sprite) == parse_sprite_toml(
        text=NO_FRAME_INDEX_TEXT, source_name='coil'
    )


def test_a_renamed_animation_keeps_its_frames_without_frame_index():
    """A rename carries the animation's lack of frame_index, as it carries its loop flag."""
    sprite = sprite_from_text(text=NO_FRAME_INDEX_TEXT, source_name='coil')
    sprite.rename_animation(old_name='idle', new_name='rest')

    (animation,) = saved_document(sprite=sprite)['animation']

    assert animation['namespace'] == 'rest'
    assert all('frame_index' not in frame for frame in animation['frame'])


def test_reordered_frames_without_frame_index_load_in_their_new_order():
    """Frames are written in list order, so a reorder survives without an index to say so."""
    sprite = sprite_from_text(text=NO_FRAME_INDEX_TEXT, source_name='coil')
    first, second = sprite.animations['idle']
    sprite.animations['idle'][:] = [second, first]

    reloaded = sprite_from_text(text=sprite_to_text(sprite=sprite), source_name='saved')

    assert [frame.get_pixel_data() for frame in reloaded.animations['idle']] == [
        second.get_pixel_data(),
        first.get_pixel_data(),
    ]


def test_an_animation_added_in_code_is_saved_with_frame_index():
    """Only a loaded animation that had no frame_index omits it; one built in code has it."""
    sprite = sprite_from_text(text=NO_FRAME_INDEX_TEXT, source_name='coil')
    frame = SpriteFrame(pygame.Surface((2, 1)))
    frame.set_pixel_data([(0, 0, 0), (0, 0, 0)])
    sprite.add_animation('blink', [frame])

    idle, blink = saved_document(sprite=sprite)['animation']

    assert all('frame_index' not in each for each in idle['frame'])
    assert [each['frame_index'] for each in blink['frame']] == [0]


def test_a_games_own_table_survives_a_save():
    """A top-level table the engine doesn't own ([swatches]) is written back unchanged."""
    sprite = sprite_from_text(text=SWATCHES_TEXT, source_name='trooper')

    assert saved_document(sprite=sprite) == parse_sprite_toml(
        text=SWATCHES_TEXT, source_name='trooper'
    )


def test_a_games_own_table_is_copied_with_the_sprite_metadata():
    """Bitmappy saves a one-frame sprite through a copy: the game's tables go with it."""
    source = sprite_from_text(text=SWATCHES_TEXT, source_name='trooper')
    copy = AnimatedSprite()
    copy.add_animation('trooper', list(source.animations['trooper']))

    copy.copy_sprite_metadata_from(source)

    assert saved_document(sprite=copy)['swatches'] == {
        'livery': {'helmet': {'role': 'primary', 'colors': ['h', 'H']}}
    }


def test_transparent_pixels_never_take_a_glyph_the_palette_gives_another_color():
    """With the key's usual glyph taken by red, a transparent pixel gets a glyph of its own.

    Every pixel's color survives the save and reload: red stays red, the key stays the key.
    """
    red = (200, 0, 0)
    sprite = sprite_from_text(text=KEY_GLYPH_TAKEN_TEXT, source_name='taken')
    (frame,) = only_animation_frames(sprite)
    frame.set_pixel_data([red, (255, 0, 255)])

    reloaded = sprite_from_text(text=sprite_to_text(sprite=sprite), source_name='saved')

    (reloaded_frame,) = only_animation_frames(reloaded)
    assert [pixel[:3] for pixel in reloaded_frame.get_pixel_data()] == [red, (255, 0, 255)]


def test_transparent_pixels_with_every_glyph_taken_are_refused():
    """With the key's glyph and every glyph of the set given to colors, the key has none left."""
    colors = {'█': {'red': 200, 'green': 0, 'blue': 0}}
    colors.update({glyph: {'red': 0, 'green': 0, 'blue': 0} for glyph in SPRITE_GLYPHS})
    text = write_sprite_toml(data={'sprite': {'name': 'full', 'pixels': '█\n'}, 'colors': colors})
    sprite = sprite_from_text(text=text, source_name='full')
    (frame,) = only_animation_frames(sprite)
    frame.set_pixel_data([(255, 0, 255)])

    with pytest.raises(ValueError, match='Too many colors'):
        sprite_to_text(sprite=sprite)


def test_a_resized_frame_is_written_by_its_colors_at_its_new_size():
    """A frame resized to another shape writes its new rows, even when its pixels line up.

    Two pixels side by side become two stacked: the colors in order are the same, so only the
    frame's size tells the loaded rows no longer fit.
    """
    text = (
        '[sprite]\nname = "turn"\npixels = """\n#.\n"""\n\n'
        '[colors."#"]\nred = 0\ngreen = 0\nblue = 0\n\n'
        '[colors."."]\nred = 255\ngreen = 0\nblue = 255\n'
    )
    sprite = sprite_from_text(text=text, source_name='turn')
    (frame,) = only_animation_frames(sprite)
    frame.image = pygame.Surface((1, 2))
    frame.set_pixel_data([(0, 0, 0), (255, 0, 255)])

    reloaded = sprite_from_text(text=sprite_to_text(sprite=sprite), source_name='saved')

    (reloaded_frame,) = only_animation_frames(reloaded)
    assert reloaded_frame.get_size() == (1, 2)
