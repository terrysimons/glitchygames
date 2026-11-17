"""Tests for sprite_toml: a sprite file's text as data, parsed and written."""

import ast
import re
import sys
from pathlib import Path

import pytest

from glitchygames.sprites import sprite_toml, tags
from glitchygames.sprites.sprite_toml import (
    parse_sprite_toml,
    split_sprite_text,
    write_sprite_toml,
)

# A static sprite: pixels in [sprite], three colors including the '#', 'é' and 'Ŧ' glyphs
STATIC_SPRITE_TEXT = '''\
[sprite]
name = "tiny"
description = """a tiny
sprite"""
tags = ["one", "two"]
frame_anchor = "bottom_center"
pixels = """
#é
Ŧ#
"""

[sprite.hitbox]
offset_x = 0
offset_y = 1
width = 2
height = 1

[colors."#"]
red = 0
green = 0
blue = 0

[colors."é"]
red = 255
green = 0
blue = 0
alpha = 128

[colors."Ŧ"]
red = 0
green = 255
blue = 0

[[transition]]
from = "idle"
to = "run"
speed = 1.5
'''

# Colors defined z, a, m: the file's order is not alphabetical
COLORS_IN_ORDER_Z_A_M = """\
[sprite]
name = "ordered"
pixels = \"\"\"
za
m.
\"\"\"

[colors.z]
red = 1
green = 1
blue = 1

[colors.a]
red = 2
green = 2
blue = 2

[colors.m]
red = 3
green = 3
blue = 3
"""

TWO_ANIMATIONS_TEXT = """\
[sprite]
name = "walker"

[[animation]]
namespace = "idle"
frame_interval = 0.5
loop = true

[[animation.frame]]
namespace = "idle"
frame_index = 0
pixels = \"\"\"
ab
ba
\"\"\"

[animation.frame.hitbox]
offset_x = 0
offset_y = 0
width = 2
height = 2

[[animation.frame]]
namespace = "idle"
frame_index = 1
frame_interval = 0.25
pixels = \"\"\"
ba
ab
\"\"\"

[[animation]]
namespace = "run"
frame_interval = 0.1
loop = false

[[animation.frame]]
namespace = "run"
frame_index = 0
pixels = \"\"\"
aa
bb
\"\"\"

[colors.a]
red = 255
green = 255
blue = 255

[colors.b]
red = 0
green = 0
blue = 0
"""


def top_level_name(node: ast.AST) -> str:
    """Return the top-level package an import statement names."""
    if isinstance(node, ast.Import):
        return node.names[0].name.split('.')[0]
    assert isinstance(node, ast.ImportFrom)
    return '__future__' if node.module is None else node.module.split('.')[0]


def is_import(node: ast.AST) -> bool:
    """Return whether the node is an import statement."""
    return isinstance(node, (ast.Import, ast.ImportFrom))


def test_text_that_is_not_toml_is_refused_naming_its_source():
    """Invalid TOML raises ValueError that names where the text came from."""
    with pytest.raises(ValueError, match='dex from the console'):
        parse_sprite_toml(text='[sprite\nname = ', source_name='dex from the console')


def test_a_written_document_parses_back_to_the_same_document():
    """A static document survives write then parse unchanged."""
    text = STATIC_SPRITE_TEXT
    document = parse_sprite_toml(text=text, source_name='test')
    assert parse_sprite_toml(text=write_sprite_toml(data=document), source_name='test') == document


def test_an_animated_document_parses_back_to_the_same_document():
    """An animated document survives write then parse unchanged."""
    document = parse_sprite_toml(text=TWO_ANIMATIONS_TEXT, source_name='test')
    assert parse_sprite_toml(text=write_sprite_toml(data=document), source_name='test') == document


def test_colors_keep_the_files_order():
    """The colors come back in the order the file defined them."""
    document = parse_sprite_toml(text=COLORS_IN_ORDER_Z_A_M, source_name='test')
    written = write_sprite_toml(data=document)
    assert list(parse_sprite_toml(text=written, source_name='test')['colors']) == ['z', 'a', 'm']


def test_an_animated_document_is_written_in_the_animated_layout():
    """An animated document has no pixels before its first animation."""
    document = parse_sprite_toml(text=TWO_ANIMATIONS_TEXT, source_name='test')
    written = write_sprite_toml(data=document)
    assert '[[animation]]' in written
    assert 'pixels' not in written.split('[[animation]]')[0]


def test_a_static_document_is_written_with_its_pixels_in_sprite():
    """A static document keeps pixels in [sprite] and has no animation."""
    document = parse_sprite_toml(text=STATIC_SPRITE_TEXT, source_name='test')
    written = parse_sprite_toml(text=write_sprite_toml(data=document), source_name='test')
    assert written['sprite']['pixels'] == document['sprite']['pixels']
    assert 'animation' not in written


def test_a_document_without_colors_or_transitions_writes_neither():
    """Colors and transitions are written only when the document has them."""
    written = write_sprite_toml(data={'sprite': {'name': 'bare'}})
    assert '[colors]' not in written
    assert '[[transition]]' not in written
    assert parse_sprite_toml(text=written, source_name='test') == {'sprite': {'name': 'bare'}}


def test_the_module_imports_only_the_standard_library():
    """The module may be lifted into a pygame-free package: standard library only."""
    module = ast.parse(Path(sprite_toml.__file__).read_text(encoding='utf-8'))
    imported = {top_level_name(node) for node in ast.walk(module) if is_import(node)}
    assert imported <= set(sys.stdlib_module_names) | {'__future__'}


def test_the_tags_key_matches_the_engines():
    """The local constant (the module may not import the engine) equals the engine's."""
    assert sprite_toml.TAGS_KEY == tags.TAGS_KEY


def animated_document():
    """Return a fresh parsed animated document to damage."""
    return parse_sprite_toml(text=TWO_ANIMATIONS_TEXT, source_name='test')


def with_value(document, path, value):
    """Set a value at a path of keys and list indexes in the document, and return the document."""
    node = document
    for step in path[:-1]:
        node = node[step]
    node[path[-1]] = value
    return document


@pytest.mark.parametrize(
    ('path', 'unknown_key_path'),
    [
        (('sprite', 'unknown_key'), 'sprite.unknown_key'),
        (('animation', 0, 'extra'), 'animation[0].extra'),
        (('animation', 0, 'frame', 1, 'extra'), 'animation[0].frame[1].extra'),
        (('animation', 0, 'frame', 0, 'hitbox', 'extra'), 'animation[0].frame[0].hitbox.extra'),
        (('colors', 'a', 'extra'), 'colors.a.extra'),
    ],
)
def test_a_key_the_writer_does_not_know_is_refused_naming_its_path(path, unknown_key_path):
    """An unknown key at any level raises rather than being dropped."""
    document = with_value(animated_document(), path, 1)
    with pytest.raises(ValueError, match=re.escape(f'unknown key {unknown_key_path}')):
        write_sprite_toml(data=document)


def test_an_unknown_key_in_a_static_sprite_hitbox_is_refused():
    """The static layout's [sprite.hitbox] is checked as well."""
    document = parse_sprite_toml(text=STATIC_SPRITE_TEXT, source_name='test')
    document['sprite']['hitbox']['extra'] = 1
    with pytest.raises(ValueError, match=r'unknown key sprite\.hitbox\.extra'):
        write_sprite_toml(data=document)


def test_a_document_using_every_key_the_loader_reads_round_trips_equal():
    """Every key AnimatedSprite's loaders read (the top-level [alpha] is not one) survives."""
    animated = animated_document()
    animated['sprite'].update(
        description='d', tags=['one'], frame_anchor='bottom', hitbox=dict.fromkeys(HITBOX, 1)
    )
    animated['colors']['a']['alpha'] = 10
    animated['transition'] = [{'from': 'idle', 'to': 'run', 'on': True, 'wait': 0.5}]
    for document in (animated, parse_sprite_toml(text=STATIC_SPRITE_TEXT, source_name='test')):
        written = write_sprite_toml(data=document)
        assert parse_sprite_toml(text=written, source_name='test') == document


HITBOX = ('offset_x', 'offset_y', 'width', 'height')


def test_every_problem_is_named_in_one_refusal():
    """All unknown keys are reported together."""
    document = animated_document()
    document['sprite']['extra'] = 1
    document['colors']['a']['extra'] = 1
    with pytest.raises(ValueError, match=r'sprite\.extra.*colors\.a\.extra'):
        write_sprite_toml(data=document)


OPTIONAL_KEYS_OMITTED_TEXT = """\
[sprite]

[[animation]]

[[animation.frame]]
pixels = \"\"\"
a
\"\"\"

[[animation.frame]]
frame_interval = 0.2

[colors.a]
"""


def test_keys_the_loader_treats_as_optional_are_not_added_by_a_round_trip():
    """An animation without loop and frames without frame_index come back without them."""
    document = parse_sprite_toml(text=OPTIONAL_KEYS_OMITTED_TEXT, source_name='test')
    written = parse_sprite_toml(text=write_sprite_toml(data=document), source_name='test')
    assert written == document
    assert 'loop' not in written['animation'][0]
    assert 'frame_index' not in written['animation'][0]['frame'][0]


SWATCHES_TEXT = """\
title = "root value"

[sprite]
name = "soldier"

[swatches.livery.helmet]
colors = ["h", "H"]
role = "primary"

[swatches.livery.uniform]
colors = ["u", "U"]
role = "secondary"
weights = [1, 2.5, true]
steps = [{ at = 1, to = "x" }, { at = 2, to = "y" }]

[swatches.empty]

[alpha]
blending = true
"""


def test_a_table_the_engine_does_not_own_is_written_back_as_it_is():
    """A game's own tables (Drawing Fire's swatches) and an [alpha] table survive."""
    document = parse_sprite_toml(text=SWATCHES_TEXT, source_name='test')
    written = parse_sprite_toml(text=write_sprite_toml(data=document), source_name='test')
    assert written == document
    assert written['swatches']['livery']['helmet']['colors'] == ['h', 'H']
    assert written['title'] == 'root value'


def test_a_value_the_toml_format_cannot_hold_here_is_refused():
    """Only tables, arrays, strings, numbers and booleans are written for a game's own tables."""
    with pytest.raises(TypeError, match='Cannot write'):
        write_sprite_toml(data={'sprite': {'name': 'x'}, 'extra': {'when': object()}})


def test_a_document_without_a_sprite_table_round_trips():
    """The loader accepts a file with no [sprite]; so does the writer, adding none."""
    document = parse_sprite_toml(text='[colors.a]\nred = 1\n', source_name='test')
    written = parse_sprite_toml(text=write_sprite_toml(data=document), source_name='test')
    assert written == document
    assert 'sprite' not in written


def split_documents(text):
    """Split sprite text and parse each frame's text back into its document."""
    return [
        parse_sprite_toml(text=each, source_name='split') for each in split_sprite_text(text=text)
    ]


def test_each_frame_becomes_its_own_sprite_in_animation_and_frame_order():
    """Frames are named <sprite>-<animation>-<frame>, animations in file order, frames from 0."""
    names = [document['sprite']['name'] for document in split_documents(TWO_ANIMATIONS_TEXT)]
    assert names == ['walker-idle-0', 'walker-idle-1', 'walker-run-0']


def test_a_split_frame_keeps_its_pixels_and_only_the_colors_it_uses():
    """Each frame is a static sprite with its pixels, and [colors] holds just the glyphs used."""
    first, _second, third = split_documents(TWO_ANIMATIONS_TEXT)
    assert first['sprite']['pixels'] == 'ab\nba\n'
    assert set(first['colors']) == {'a', 'b'}
    assert 'animation' not in first
    assert third['sprite']['pixels'] == 'aa\nbb\n'
    assert set(third['colors']) == {'a', 'b'}


def test_a_frame_keeps_only_the_colors_it_uses_in_the_sources_order():
    """A glyph the frame does not use is dropped; the rest keep the source's color order."""
    text = COLORS_IN_ORDER_Z_A_M.replace('za\nm.', 'mz\nmz')
    (only,) = split_documents(text)
    assert list(only['colors']) == ['z', 'm']
    assert 'a' not in only['colors']


def test_a_single_frame_sprite_splits_into_itself():
    """A static sprite is one frame: its pixels, colors and sprite-level keys carry over."""
    (only,) = split_documents(STATIC_SPRITE_TEXT)
    source = parse_sprite_toml(text=STATIC_SPRITE_TEXT, source_name='test')
    assert only['sprite']['pixels'] == source['sprite']['pixels']
    assert only['sprite']['name'] == 'tiny-default-0'
    assert only['sprite']['description'] == 'a tiny\nsprite'
    assert only['sprite']['tags'] == ['one', 'two']
    assert only['sprite']['frame_anchor'] == 'bottom_center'
    assert only['sprite']['hitbox'] == source['sprite']['hitbox']
    assert only['colors'] == source['colors']


def test_a_frames_hitbox_wins_over_the_sprites_and_the_sprites_is_the_fallback():
    """The frame's own hitbox is used when it has one, else the sprite's."""
    text = TWO_ANIMATIONS_TEXT.replace(
        '[sprite]\nname = "walker"\n',
        '[sprite]\nname = "walker"\n\n[sprite.hitbox]\nwidth = 9\nheight = 9\n',
    )
    first, second, _third = split_documents(text)
    assert first['sprite']['hitbox'] == {'offset_x': 0, 'offset_y': 0, 'width': 2, 'height': 2}
    assert second['sprite']['hitbox'] == {'width': 9, 'height': 9}


def test_names_use_the_loaders_defaults_where_the_source_omits_them():
    """No sprite name is 'animated_sprite' and no animation namespace is 'default'."""
    text = '[[animation]]\n[[animation.frame]]\npixels = "a"\n[colors.a]\nred = 1\n'
    (only,) = split_documents(text)
    assert only['sprite']['name'] == 'animated_sprite-default-0'
    assert 'description' not in only['sprite']
    assert 'hitbox' not in only['sprite']


def test_a_games_own_tables_are_not_carried_into_split_frames():
    """A split frame is a new single-image sprite: [swatches] names glyphs it may not keep."""
    text = SWATCHES_TEXT.replace('name = "soldier"', 'name = "soldier"\npixels = "h"')
    (only,) = split_documents(text)
    assert 'swatches' not in only
    assert 'alpha' not in only
    assert 'title' not in only


def test_a_sprite_without_pixels_or_animations_splits_into_one_empty_sprite():
    """Like an animated frame without pixels, a static sprite without them is one empty frame."""
    (only,) = split_documents('[sprite]\nname = "empty"\n')
    assert only['sprite']['name'] == 'empty-default-0'
    assert not only['sprite']['pixels']
    assert 'colors' not in only


def test_an_animation_with_no_frames_gives_no_sprites():
    """Only frames are split: an animation without any contributes nothing."""
    assert split_sprite_text(text='[sprite]\nname = "x"\n[[animation]]\nnamespace = "a"\n') == []


def test_a_frame_without_pixels_becomes_an_empty_sprite():
    """The loader defaults a frame's missing pixels to '', so the frame is split, not refused."""
    text = '[sprite]\nname = "x"\n[[animation]]\nnamespace = "walk"\n[[animation.frame]]\n'
    (only,) = split_documents(text)
    assert only['sprite']['name'] == 'x-walk-0'
    assert not only['sprite']['pixels']
    assert 'colors' not in only


def test_empty_pixels_and_empty_colors_are_written_and_parse_back():
    """write_sprite_toml handles pixels = '' with an empty [colors]; the text parses back."""
    document = {'sprite': {'name': 'x', 'pixels': ''}, 'colors': {}}
    written = parse_sprite_toml(text=write_sprite_toml(data=document), source_name='test')
    assert written['sprite']['name'] == 'x'
    assert not written['sprite']['pixels']
    assert written['colors'] == {}


@pytest.mark.parametrize('pixels', ['', 'a', 'ab\ncd', 'ab\ncd\n', '\nab', '\\\n"""'])
def test_pixels_round_trip_exactly_with_or_without_a_final_newline(pixels):
    """The text is written as given: no final newline is added to it, none is dropped."""
    static = {'sprite': {'name': 'x', 'pixels': pixels}}
    animated = {'animation': [{'frame': [{'pixels': pixels}]}]}
    for document in (static, animated):
        written = parse_sprite_toml(text=write_sprite_toml(data=document), source_name='test')
        assert written == document


def test_animations_with_the_same_namespace_give_frames_with_the_same_name():
    """The naming rule does not make names unique: two 'a' animations both give x-a-0."""
    frame = '[[animation.frame]]\npixels = "p"\n'
    text = f'[sprite]\nname = "x"\n[[animation]]\nnamespace = "a"\n{frame}'
    text += f'[[animation]]\nnamespace = "a"\n{frame}'
    names = [document['sprite']['name'] for document in split_documents(text)]
    assert names == ['x-a-0', 'x-a-0']


def test_animations_without_a_namespace_give_frames_named_default():
    """Both omitting the namespace is the same case: x-default-0 twice."""
    frame = '[[animation.frame]]\npixels = "p"\n'
    text = f'[sprite]\nname = "x"\n[[animation]]\n{frame}[[animation]]\n{frame}'
    names = [document['sprite']['name'] for document in split_documents(text)]
    assert names == ['x-default-0', 'x-default-0']


# Valid TOML of every shape the writer must either write back equal or refuse with ValueError
SHAPE_DOCUMENT_TEXTS = {
    'animation is an integer': 'animation = 3\n',
    'animation is a table': '[animation]\nnamespace = "a"\n',
    'animation holds an integer': 'animation = [3]\n',
    'frames are a table': '[[animation]]\n[animation.frame]\npixels = "a"\n',
    'colors is an integer': 'colors = 3\n',
    'a color is an integer': '[colors]\na = 3\n',
    'sprite is an integer': 'sprite = 3\n',
    'sprite pixels is an integer': '[sprite]\npixels = 3\n',
    'transition is an integer': 'transition = 3\n',
    'transition is a table': '[transition]\nfrom = "a"\n',
    'a boolean color value': '[colors.a]\nred = true\n',
    'a string color value': '[colors.a]\nred = "255"\n',
    'a float color value': '[colors.a]\nred = 1.5\n',
    'a string hitbox value': '[sprite.hitbox]\nwidth = "8"\n',
    'tags is a string': '[sprite]\ntags = "item"\n',
    'tags holds an integer': '[sprite]\ntags = ["a", 1]\n',
    'frame pixels is an array': '[[animation]]\n[[animation.frame]]\npixels = ["ab", "cd"]\n',
    'an integer name': '[sprite]\nname = 5\n',
    'an integer description': '[sprite]\ndescription = 5\n',
    'an integer frame anchor': '[sprite]\nframe_anchor = 5\n',
    'a date name': '[sprite]\nname = 2026-11-17\n',
    'a string frame index': '[[animation]]\n[[animation.frame]]\nframe_index = "1"\n',
    'a string loop': '[[animation]]\nloop = "yes"\n',
    'a date in a games own table': '[swatches]\nmade = 2026-11-17\n',
    'a datetime in a transition': '[[transition]]\nat = 2026-11-17T10:30:00Z\n',
    'times and datetimes in a games own table': (
        'a = 10:30:00\nb = 2026-11-17T10:30:00.5\nc = 2026-11-17T10:30:00+02:00\n'
        '[game]\nwhen = [2026-11-17, 10:30:00]\n'
    ),
    'empty containers': (
        'animation = []\ntransition = []\ncolors = {}\nsprite = {}\nother = {}\nlist = []\n'
    ),
    'an animation with an empty frame list': '[[animation]]\nframe = []\n',
    'a sprite with the Part 2 keys': (
        '[sprite]\nname = "x"\nprofile = "8-bit+"\ncolor_space = "9-bit RGB"\n'
    ),
}


@pytest.mark.parametrize(
    'text', list(SHAPE_DOCUMENT_TEXTS.values()), ids=list(SHAPE_DOCUMENT_TEXTS)
)
def test_a_parsed_document_is_written_back_equal_or_refused_with_a_value_error(text):
    """The invariant: write_sprite_toml raises ValueError or returns text parsing back equal."""
    document = parse_sprite_toml(text=text, source_name='test')
    try:
        written = write_sprite_toml(data=document)
    except ValueError:
        return
    assert parse_sprite_toml(text=written, source_name='test') == document


@pytest.mark.parametrize(
    ('text', 'path'),
    [
        ('animation = 3\n', 'animation'),
        ('[animation]\nnamespace = "a"\n', 'animation'),
        ('animation = [3]\n', r'animation\[0\]'),
        ('[[animation]]\n[animation.frame]\npixels = "a"\n', r'animation\[0\]\.frame'),
        ('colors = 3\n', 'colors'),
        ('[colors]\na = 3\n', r'colors\.a'),
        ('sprite = 3\n', 'sprite'),
        ('[sprite]\npixels = 3\n', r'sprite\.pixels'),
        ('transition = 3\n', 'transition'),
        ('[colors.a]\nred = true\n', r'colors\.a\.red'),
        ('[colors.a]\nred = "255"\n', r'colors\.a\.red'),
        ('[sprite.hitbox]\nwidth = "8"\n', r'sprite\.hitbox\.width'),
        ('[sprite]\nhitbox = 3\n', r'sprite\.hitbox'),
        ('[sprite]\ntags = "item"\n', r'sprite\.tags'),
        ('[sprite]\ntags = ["a", 1]\n', r'sprite\.tags\[1\]'),
        (
            '[[animation]]\n[[animation.frame]]\npixels = ["ab"]\n',
            r'animation\[0\]\.frame\[0\]\.pixels',
        ),
        ('[sprite]\nname = 5\n', r'sprite\.name'),
        ('[sprite]\ndescription = 5\n', r'sprite\.description'),
        ('[sprite]\nframe_anchor = 5\n', r'sprite\.frame_anchor'),
        ('[[animation]]\nloop = "yes"\n', r'animation\[0\]\.loop'),
    ],
)
def test_a_value_of_the_wrong_type_is_refused_naming_its_path(text, path):
    """Valid TOML of the wrong type or shape raises ValueError naming where, never TypeError."""
    document = parse_sprite_toml(text=text, source_name='test')
    with pytest.raises(ValueError, match=f'Cannot write the sprite document.*{path}'):
        write_sprite_toml(data=document)


def test_every_wrong_type_is_named_in_one_refusal():
    """Wrong types are reported together with the unknown keys, as one error."""
    document = {
        'sprite': {'name': 5, 'extra': 1},
        'colors': {'a': {'red': True}, 'b': 3},
    }
    with pytest.raises(ValueError, match=r'sprite\.extra.*sprite\.name.*colors\.a\.red.*colors\.b'):
        write_sprite_toml(data=document)


def test_dates_and_times_are_written_as_toml_literals_and_parse_back_equal():
    """A date, datetime or time anywhere in a games own tables survives as the same value."""
    text = SHAPE_DOCUMENT_TEXTS['times and datetimes in a games own table']
    text += '[[transition]]\nat = 2026-11-17T10:30:00Z\n'
    document = parse_sprite_toml(text=text, source_name='test')
    written = write_sprite_toml(data=document)
    assert parse_sprite_toml(text=written, source_name='test') == document
    assert 'datetime.' not in written


def test_a_document_with_the_part_two_keys_round_trips():
    """Profile and color_space are known [sprite] keys, strings."""
    document = parse_sprite_toml(
        text=SHAPE_DOCUMENT_TEXTS['a sprite with the Part 2 keys'], source_name='test'
    )
    written = write_sprite_toml(data=document)
    assert parse_sprite_toml(text=written, source_name='test') == document
    assert 'profile = "8-bit+"' in written


def test_a_part_two_key_of_the_wrong_type_is_refused():
    """Profile is a string like the other [sprite] text keys."""
    with pytest.raises(ValueError, match=r'sprite\.profile'):
        write_sprite_toml(data={'sprite': {'profile': 3}})


@pytest.mark.parametrize(
    'text',
    [
        'animation = 3\n',
        '[animation]\nnamespace = "a"\n',
        'colors = 3\n',
        '[colors]\na = 3\n',
        '[sprite]\npixels = 3\n',
        '[[animation]]\nframe = 3\n',
        '[sprite]\nname = 5\n',
    ],
)
def test_text_of_the_wrong_shape_is_refused_by_split_with_a_value_error(text):
    """split_sprite_text refuses what the writer refuses, with ValueError, not AttributeError."""
    with pytest.raises(ValueError, match='Cannot split the sprite text'):
        split_sprite_text(text=text)


def test_split_refuses_text_that_is_not_toml_naming_sprite_text():
    """Split takes no source name, so the error names the generic sprite text."""
    with pytest.raises(ValueError, match='sprite text is not valid TOML'):
        split_sprite_text(text='[sprite\nname = ')


def test_frames_are_numbered_in_the_loaders_frame_index_order():
    """Frame index 1 written before frame index 0 is frame 1: the names match the loader's."""
    text = (
        '[sprite]\nname = "k-w"\n[[animation]]\nnamespace = "k"\n'
        '[[animation.frame]]\nframe_index = 1\npixels = "b"\n'
        '[[animation.frame]]\nframe_index = 0\npixels = "a"\n'
    )
    document = parse_sprite_toml(text=text, source_name='test')
    loader_order = [
        frame['pixels']
        for frame in sprite_toml.frame_tables_in_load_order(document['animation'][0]['frame'])
    ]
    split = {each['sprite']['name']: each['sprite']['pixels'] for each in split_documents(text)}
    assert loader_order == ['a', 'b']
    assert split == {f'k-w-k-{index}': pixels for index, pixels in enumerate(loader_order)}


def test_frame_tables_in_load_order_is_the_one_the_engine_uses():
    """The engine's animated module keeps the name importable and it is the same function."""
    from glitchygames.sprites import animated

    assert animated.frame_tables_in_load_order is sprite_toml.frame_tables_in_load_order
