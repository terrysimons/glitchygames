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
from tests.test_workspace_sprite_files import MEMBER_SPRITE_FILES, sprite_file_id

# The sprite files the Python loader reads: every member's, Bitmappy's library among them
BITMAPPY_LIBRARY_PREFIX = 'apps/bitmappy/src/bitmappy/resources/sprites/'

# The engine's own sprites (src/glitchygames/assets) join the members'
SHIPPED_SPRITE_FILES = [
    *sorted((Path(sprite_toml.__file__).parent.parent / 'assets').glob('*.toml')),
    *MEMBER_SPRITE_FILES,
]

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


def test_the_bitmappy_library_is_among_the_files_checked():
    """The round trip below covers Bitmappy's sprite library as well as the games'."""
    names = {sprite_file_id(sprite_file) for sprite_file in MEMBER_SPRITE_FILES}
    assert any(name.startswith(BITMAPPY_LIBRARY_PREFIX) for name in names)


@pytest.mark.parametrize('sprite_file', SHIPPED_SPRITE_FILES, ids=sprite_file_id)
def test_every_shipped_sprite_file_round_trips(sprite_file):
    """Parsing a shipped sprite, writing it and parsing the text gives an equal document."""
    text = sprite_file.read_text(encoding='utf-8')
    document = parse_sprite_toml(text=text, source_name=str(sprite_file))
    written = write_sprite_toml(data=document)
    assert parse_sprite_toml(text=written, source_name=str(sprite_file)) == document


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
    assert only['sprite']['pixels'].strip() == ''
    assert 'colors' not in only


def test_an_animation_with_no_frames_gives_no_sprites():
    """Only frames are split: an animation without any contributes nothing."""
    assert split_sprite_text(text='[sprite]\nname = "x"\n[[animation]]\nnamespace = "a"\n') == []


def test_a_frame_without_pixels_becomes_an_empty_sprite():
    """The loader defaults a frame's missing pixels to '', so the frame is split, not refused."""
    text = '[sprite]\nname = "x"\n[[animation]]\nnamespace = "walk"\n[[animation.frame]]\n'
    (only,) = split_documents(text)
    assert only['sprite']['name'] == 'x-walk-0'
    assert only['sprite']['pixels'].strip() == ''
    assert 'colors' not in only


def test_empty_pixels_and_empty_colors_are_written_and_parse_back():
    """write_sprite_toml handles pixels = '' with an empty [colors]; the text parses back."""
    document = {'sprite': {'name': 'x', 'pixels': ''}, 'colors': {}}
    written = parse_sprite_toml(text=write_sprite_toml(data=document), source_name='test')
    assert written['sprite']['name'] == 'x'
    assert written['sprite']['pixels'].strip() == ''
    assert 'colors' not in written


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


def test_a_shipped_multi_animation_sprite_splits_into_loadable_frames_with_equal_pixels():
    """Every frame of a real sprite is written, loads, and keeps its source pixels."""
    (sprite_file,) = [
        path
        for path in MEMBER_SPRITE_FILES
        if path.as_posix().endswith('brave_adventurer_papyrus/sprites/player.toml')
    ]
    source = parse_sprite_toml(text=sprite_file.read_text(encoding='utf-8'), source_name='source')
    source_pixels = [
        frame['pixels'] for animation in source['animation'] for frame in animation['frame']
    ]
    assert len(source['animation']) > 1
    written = split_documents(sprite_file.read_text(encoding='utf-8'))
    assert [document['sprite']['pixels'] for document in written] == source_pixels
    for document in written:
        assert set(document['colors']) <= set(source['colors'])
