"""The sprite file schema (glitchygames/sprites/sprite_file_schema.py): values checked once.

The bug it answers (2026-11-17): a sprite file whose ``frame_interval`` was text loaded without a
word, and the game crashed on its first frame, in ``AnimatedSprite.update``. Every value a sprite
file holds is checked at load now, by type and range, so a bad file fails there, naming the file
and the field.
"""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

import pytest

from glitchygames.sprites import SpriteFactory, sprite_file_schema, sprite_toml
from glitchygames.sprites.sprite_file_schema import SpriteFileError, validate_sprite_file

if TYPE_CHECKING:
    from pathlib import Path

# A file holding every field the loaders read, each with a valid value
EVERY_FIELD: dict[str, Any] = {
    'sprite': {
        'name': 'blink',
        'description': 'two frames',
        'tags': ['test'],
        'frame_anchor': 'bottom',
        'hitbox': {'offset_x': 0, 'offset_y': 0, 'width': 2, 'height': 2},
    },
    'animation': [
        {
            'namespace': 'blink',
            'frame_interval': 0.25,
            'loop': True,
            'frame': [
                {
                    'namespace': 'blink',
                    'frame_index': 0,
                    'frame_interval': 0.5,
                    'pixels': '#.\n.#',
                    'hitbox': {'offset_x': 0, 'offset_y': 0, 'width': 2, 'height': 2},
                },
            ],
        },
    ],
    'transition': [{'from': 'blink', 'to': 'blink', 'when': 'done'}],
    'colors': {
        '#': {'red': 255, 'green': 0, 'blue': 0},
        '.': {'red': 255, 'green': 0, 'blue': 255, 'alpha': 128},
    },
}


def _with(path: tuple[str | int, ...], value: object) -> dict[str, Any]:
    """The every-field file with one value replaced.

    Returns:
        The file's data.
    """
    data = copy.deepcopy(EVERY_FIELD)
    node: Any = data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    return data


def test_a_file_with_every_field_valid_passes():
    """The baseline the other tests change one value of."""
    validate_sprite_file(data=EVERY_FIELD, source_name='blink.toml')


def test_a_static_sprite_passes():
    """[sprite] pixels and colors alone: the static form."""
    validate_sprite_file(
        data={
            'sprite': {'name': 'dot', 'pixels': '#'},
            'colors': {'#': {'red': 1, 'green': 2, 'blue': 3}},
        },
        source_name='dot.toml',
    )


@pytest.mark.parametrize(
    ('path', 'value'),
    [
        (('animation', 0, 'frame_interval'), 'fast'),
        (('animation', 0, 'frame_interval'), 0),
        (('animation', 0, 'frame_interval'), -0.5),
        (('animation', 0, 'frame_interval'), True),
        (('animation', 0, 'frame', 0, 'frame_interval'), 'slow'),
        (('animation', 0, 'loop'), 'false'),
        (('colors', '#', 'red'), 300),
        (('colors', '#', 'red'), 'red'),
        (('colors', '.', 'alpha'), 256),
        (('sprite', 'hitbox', 'width'), 'x'),
        (('animation', 0, 'frame', 0, 'hitbox', 'height'), 1.5),
        (('sprite', 'name'), 5),
        (('animation', 0, 'namespace'), 5),
        (('animation', 0, 'frame', 0, 'frame_index'), -1),
        (('sprite', 'tags'), 'test'),
    ],
    ids=[
        'frame_interval is text',
        'frame_interval is zero',
        'frame_interval is negative',
        'frame_interval is a boolean',
        "a frame's frame_interval is text",
        'loop is text',
        'a color channel over 255',
        'a color channel is text',
        'alpha over 255',
        'a hitbox width is text',
        'a hitbox height is fractional',
        'the name is a number',
        'a namespace is a number',
        'a frame index is negative',
        'tags is not a list',
    ],
)
def test_a_value_of_the_wrong_type_or_range_is_refused_naming_file_and_field(path, value):
    """The error names the file and the field, as a person would find it in the file."""
    with pytest.raises(SpriteFileError) as refusal:
        validate_sprite_file(data=_with(path, value), source_name='blink.toml')

    message = str(refusal.value)
    assert 'blink.toml' in message
    assert '.'.join(str(part) for part in path) in message


@pytest.mark.parametrize(
    'path',
    [('sprite', 'fram_anchor'), ('animation', 0, 'frame_intervall'), ('colors', '#', 'gren')],
    ids=['a misspelled sprite key', 'a misspelled animation key', 'a misspelled color key'],
)
def test_a_misspelled_key_inside_a_known_section_is_refused(path):
    """A typo is caught at load, not silently ignored."""
    with pytest.raises(SpriteFileError, match=path[-1]):
        validate_sprite_file(data=_with(path, 1), source_name='blink.toml')


def test_a_table_of_a_games_own_is_kept():
    """Games keep data of their own beside the sprite (Drawing Fire's swatches)."""
    data = {**copy.deepcopy(EVERY_FIELD), 'swatches': {'livery': {'helmet': {'role': 'x'}}}}

    validate_sprite_file(data=data, source_name='blink.toml')


def _leaf_paths(node: object, path: tuple[str | int, ...] = ()) -> list[tuple[str | int, ...]]:
    """Every scalar value's path in a file's data.

    Returns:
        The paths.
    """
    if isinstance(node, dict):
        return [leaf for key, value in node.items() for leaf in _leaf_paths(value, (*path, key))]
    if isinstance(node, list) and node and not isinstance(node[0], str):
        return [
            leaf for index, item in enumerate(node) for leaf in _leaf_paths(item, (*path, index))
        ]
    return [path]


@pytest.mark.parametrize(
    'path', _leaf_paths(EVERY_FIELD), ids=lambda path: '.'.join(str(part) for part in path)
)
def test_every_field_a_file_holds_is_type_checked(path):
    """The invariant over the whole class: no field takes a value of the wrong type.

    A table where a value belongs is wrong for every field, so each one must refuse it.
    """
    with pytest.raises(SpriteFileError):
        validate_sprite_file(data=_with(path, {'not': 'a value'}), source_name='blink.toml')


def test_a_sprite_whose_frame_interval_is_text_is_refused_at_load(tmp_path: Path):
    """The reported bug: it loaded, then crashed the game in update. It fails at load now."""
    sprite_file = tmp_path / 'fast.toml'
    sprite_file.write_text(
        """[sprite]
name = "blink"

[[animation]]
namespace = "blink"
frame_interval = "fast"

[[animation.frame]]
pixels = "#"

[colors."#"]
red = 255
green = 0
blue = 0
""",
        encoding='utf-8',
    )

    with pytest.raises(SpriteFileError, match=r'fast\.toml.*frame_interval'):
        SpriteFactory.load_sprite(filename=str(sprite_file))


def test_a_static_sprite_whose_color_is_text_is_refused_at_load(tmp_path: Path):
    """The static loader is checked the same way."""
    sprite_file = tmp_path / 'dot.toml'
    sprite_file.write_text(
        '[sprite]\nname = "dot"\npixels = "#"\n\n[colors."#"]\nred = "red"\ngreen = 0\nblue = 0\n',
        encoding='utf-8',
    )

    with pytest.raises(SpriteFileError, match=r'dot\.toml.*red'):
        SpriteFactory.load_sprite(filename=str(sprite_file))


def schema_keys(model: type[sprite_file_schema.BaseModel]) -> frozenset[str]:
    """Return the keys a schema section accepts, as a file spells them (aliases included).

    Returns:
        The keys.

    """
    return frozenset(field.alias or name for name, field in model.model_fields.items())


@pytest.mark.parametrize(
    ('model', 'writer_keys'),
    [
        (sprite_file_schema.SpriteFile, sprite_toml.DOCUMENT_KEYS),
        (sprite_file_schema.Sprite, sprite_toml.SPRITE_KEYS),
        (sprite_file_schema.Hitbox, frozenset(sprite_toml.HITBOX_KEYS)),
        (sprite_file_schema.Animation, sprite_toml.ANIMATION_KEYS),
        (sprite_file_schema.Frame, sprite_toml.FRAME_KEYS),
        (sprite_file_schema.Color, sprite_toml.COLOR_KEYS),
    ],
    ids=['document', 'sprite', 'hitbox', 'animation', 'frame', 'color'],
)
def test_the_schema_accepts_exactly_the_keys_the_writer_writes(model, writer_keys):
    """Each section's keys are the writer's (sprite_toml.py), so a written file always loads.

    Both ways: a key the writer writes but the schema refuses makes a file nothing can load
    (``profile`` and ``color_space``, 2026-11-18); one the schema accepts but the writer refuses
    makes a loaded sprite unsavable.
    """
    assert schema_keys(model) == writer_keys
