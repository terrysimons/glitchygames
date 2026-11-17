"""Tests for sprite_toml: a sprite file's text as data, parsed and written."""

import ast
import re
import sys
from pathlib import Path

import pytest

from glitchygames.sprites import sprite_toml, tags
from glitchygames.sprites.sprite_toml import parse_sprite_toml, write_sprite_toml
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
