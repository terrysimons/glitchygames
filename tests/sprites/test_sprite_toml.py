"""Tests for sprite_toml: a sprite file's text as data, parsed and written."""

import ast
import sys
from pathlib import Path

import pytest

from glitchygames.sprites import sprite_toml
from glitchygames.sprites.sprite_toml import parse_sprite_toml, write_sprite_toml

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
    written = write_sprite_toml(data=document)
    assert '[[animation]]' not in written
    assert 'pixels' in written.split('[colors]')[0]


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
