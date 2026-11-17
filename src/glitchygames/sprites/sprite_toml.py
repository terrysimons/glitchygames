"""A sprite file's text as data: parsed from TOML text and written back as TOML text.

This module imports only the standard library (no pygame, no engine module) so it can be lifted
into a pygame-free package unchanged. A sprite file is a TOML document; ``parse_sprite_toml``
turns text into that document and ``write_sprite_toml`` turns a document into text in the
layout the engine writes: a round trip keeps the same parsed sprite, not the same bytes.
"""

from __future__ import annotations

import math
import tomllib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

# The [sprite] key holding a sprite's tags (the engine's glitchygames.sprites.tags.TAGS_KEY;
# a test keeps the two equal, as this module may import only the standard library)
TAGS_KEY = 'tags'

# The keys the engine's loader reads (AnimatedSprite._load_toml and its static loader), by table.
# The writer refuses any other key rather than dropping it, so a round trip keeps the sprite.
DOCUMENT_KEYS = frozenset({'sprite', 'colors', 'animation', 'transition'})
SPRITE_KEYS = frozenset({'name', 'description', TAGS_KEY, 'frame_anchor', 'pixels', 'hitbox'})
HITBOX_KEYS = ('offset_x', 'offset_y', 'width', 'height')
ANIMATION_KEYS = frozenset({'namespace', 'frame_interval', 'loop', 'frame'})
FRAME_KEYS = frozenset({'namespace', 'frame_index', 'frame_interval', 'pixels', 'hitbox'})
COLOR_KEYS = frozenset({'red', 'green', 'blue', 'alpha'})

# Characters TOML basic strings must escape with a short escape sequence
# (https://toml.io/en/v1.0.0#string)
TOML_SHORT_ESCAPES = {
    '\\': '\\\\',
    '"': '\\"',
    '\b': '\\b',
    '\t': '\\t',
    '\n': '\\n',
    '\f': '\\f',
    '\r': '\\r',
}
# Code points below this, and DEL, are control characters TOML strings must escape
TOML_FIRST_PRINTABLE_CODE_POINT = 0x20
TOML_DELETE_CODE_POINT = 0x7F
# Bare TOML keys may use only these characters
TOML_BARE_KEY_CHARACTERS = frozenset(
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-'
)


def toml_basic_string(value: str) -> str:
    """Quote a string as a TOML basic string, escaping what TOML requires.

    Returns:
        str: The quoted, escaped string: a quote becomes backslash-quote, a backslash
        becomes two backslashes and control characters use their escape sequences.

    """
    escaped_characters: list[str] = []
    for character in value:
        if character in TOML_SHORT_ESCAPES:
            escaped_characters.append(TOML_SHORT_ESCAPES[character])
        elif (
            ord(character) < TOML_FIRST_PRINTABLE_CODE_POINT
            or ord(character) == TOML_DELETE_CODE_POINT
        ):
            escaped_characters.append(f'\\u{ord(character):04X}')
        else:
            escaped_characters.append(character)
    return '"' + ''.join(escaped_characters) + '"'


def toml_pixel_block(pixel_text: str) -> str:
    """Write pixel rows as a TOML multi-line basic string, one row per line.

    Each row is escaped as toml_basic_string escapes (a backslash, a quote and control
    characters), so any glyph survives: unescaped, a row ending in a backslash glyph joins the
    next row (TOML's line-ending backslash), and three quote glyphs end the string. The line
    breaks between rows stay real so the rows stay readable. A trailing line break of the input
    is dropped: the closing quotes' line ends the last row.

    Returns:
        str: The rows wrapped in triple quotes, the opening quotes on their own line.

    """
    rows = pixel_text.removesuffix('\n').split('\n')
    # toml_basic_string quotes a row; the quotes are dropped, the escapes kept
    escaped_rows = [toml_basic_string(row)[1:-1] for row in rows]
    return '"""\n' + '\n'.join(escaped_rows) + '\n"""'


def toml_tags_line(tags: list[str]) -> str:
    """Return the ``tags = [...]`` line a writer puts in ``[sprite]``, or '' for no tags.

    Args:
        tags: The tags (``glitchygames.sprites.tags``: already in their one spelling).

    Returns:
        The line, with its newline, or ''.

    """
    if not tags:
        return ''
    return f'{TAGS_KEY} = [{", ".join(toml_basic_string(tag) for tag in tags)}]\n'


def toml_multiline_basic_string(value: str) -> str:
    """Quote a string as a TOML multi-line basic string (triple quotes), escaping as needed.

    Newlines stay as real line breaks so descriptions stay readable. Backslashes and quotes
    are escaped (so no run of three quotes can end the string early), as are other control
    characters, and a leading newline is written as an escape because TOML drops a newline
    right after the opening quotes.

    Returns:
        str: The value wrapped in triple quotes.

    """
    escaped_characters: list[str] = []
    for position, character in enumerate(value):
        if character == '\n' and position > 0:
            escaped_characters.append(character)
        elif character in TOML_SHORT_ESCAPES:
            escaped_characters.append(TOML_SHORT_ESCAPES[character])
        elif (
            ord(character) < TOML_FIRST_PRINTABLE_CODE_POINT
            or ord(character) == TOML_DELETE_CODE_POINT
        ):
            escaped_characters.append(f'\\u{ord(character):04X}')
        else:
            escaped_characters.append(character)
    return '"""' + ''.join(escaped_characters) + '"""'


def toml_key(key: str) -> str:
    """Return a TOML key: bare when TOML allows it, otherwise a quoted basic string.

    Returns:
        str: The key as written in a TOML file.

    """
    if key and all(character in TOML_BARE_KEY_CHARACTERS for character in key):
        return key
    return toml_basic_string(key)


def toml_scalar(value: object) -> str:
    """Format a string, boolean, integer or float as a TOML value.

    Returns:
        str: The value as written in a TOML file.

    Raises:
        TypeError: For any other type (TOML tables, arrays and dates are not supported here).

    """
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, str):
        return toml_basic_string(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return 'nan'
        if math.isinf(value):
            return 'inf' if value > 0 else '-inf'
        return repr(value)
    msg = f'Cannot write {type(value).__name__} value {value!r} as a TOML scalar'
    raise TypeError(msg)


def parse_sprite_toml(*, text: str, source_name: str) -> dict[str, Any]:
    """Parse a sprite file's text into its document.

    Args:
        text: The sprite file's TOML text.
        source_name: What the text came from (a file name, a console), named in the error.

    Returns:
        The parsed document: tables as dicts, ``[[animation]]`` and ``[[transition]]`` as lists,
        keys in the file's order.

    Raises:
        ValueError: If the text is not valid TOML, naming ``source_name``.

    """
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        msg = f'{source_name} is not valid TOML: {error}'
        raise ValueError(msg) from error


def write_sprite_toml(*, data: Mapping[str, Any]) -> str:
    """Write a sprite document as TOML text in the engine's layout.

    A document whose ``[sprite]`` table has ``pixels`` is written in the static layout. Any other
    is written as ``[sprite]``, then each ``[[animation]]`` with its ``[[animation.frame]]``
    tables, then ``[colors]`` in the document's order, then each ``[[transition]]``. A document
    with a key the writer does not know (it would be dropped) or without one it needs is refused
    with a ValueError naming each by its path (``sprite.name``, ``animation[0].frame``).

    Args:
        data: The sprite document (as ``parse_sprite_toml`` returns).

    Returns:
        The TOML text.

    """
    _check_document(data=data)
    sprite = data['sprite']
    lines: list[str] = ['[sprite]\n', f'name = {toml_basic_string(sprite["name"])}\n']
    if sprite.get('description'):
        lines.append(f'description = {toml_multiline_basic_string(sprite["description"])}\n')
    lines.append(toml_tags_line(sprite.get(TAGS_KEY, [])))
    if 'frame_anchor' in sprite:
        lines.append(f'frame_anchor = {toml_basic_string(sprite["frame_anchor"])}\n')
    if 'pixels' in sprite:
        lines.append(f'pixels = {toml_pixel_block(sprite["pixels"])}\n\n')
    else:
        lines.append('\n')
    if 'hitbox' in sprite:
        lines.append(_hitbox_section(section_header='[sprite.hitbox]', hitbox=sprite['hitbox']))
    lines.extend(_animation_section(animation=animation) for animation in data.get('animation', []))
    lines.append(_colors_section(colors=data.get('colors', {})))
    for transition in data.get('transition', []):
        lines.extend((
            '\n[[transition]]\n',
            *(f'{toml_key(key)} = {toml_scalar(value)}\n' for key, value in transition.items()),
        ))
    return ''.join(lines)


def _check_document(*, data: Mapping[str, Any]) -> None:
    """Refuse a document the writer cannot write without dropping or inventing keys.

    Raises:
        ValueError: Naming every unknown and every missing key by its path.

    """
    problems: list[str] = []
    _check_table(
        table=data,
        path='',
        known_keys=DOCUMENT_KEYS,
        required_keys=('sprite',),
        problems=problems,
    )
    sprite: Mapping[str, Any] | None = data.get('sprite')
    if sprite is not None:
        _check_table(
            table=sprite,
            path='sprite',
            known_keys=SPRITE_KEYS,
            required_keys=('name',),
            problems=problems,
        )
        _check_hitbox(hitbox=sprite.get('hitbox'), path='sprite.hitbox', problems=problems)
    for character, color in data.get('colors', {}).items():
        _check_table(
            table=color,
            path=f'colors.{character}',
            known_keys=COLOR_KEYS,
            required_keys=('red', 'green', 'blue'),
            problems=problems,
        )
    for animation_index, animation in enumerate(data.get('animation', [])):
        animation_path = f'animation[{animation_index}]'
        _check_table(
            table=animation,
            path=animation_path,
            known_keys=ANIMATION_KEYS,
            required_keys=('namespace', 'frame_interval', 'loop', 'frame'),
            problems=problems,
        )
        for frame_index, frame in enumerate(animation.get('frame', [])):
            frame_path = f'{animation_path}.frame[{frame_index}]'
            _check_table(
                table=frame,
                path=frame_path,
                known_keys=FRAME_KEYS,
                required_keys=('frame_index', 'pixels'),
                problems=problems,
            )
            _check_hitbox(
                hitbox=frame.get('hitbox'), path=f'{frame_path}.hitbox', problems=problems
            )
    if problems:
        msg = 'Cannot write the sprite document: ' + '; '.join(problems)
        raise ValueError(msg)


def _check_table(
    *,
    table: Mapping[str, Any],
    path: str,
    known_keys: frozenset[str],
    required_keys: tuple[str, ...],
    problems: list[str],
) -> None:
    """Add a problem for each unknown key in the table and each required key it lacks."""
    prefix = f'{path}.' if path else ''
    problems.extend(f'unknown key {prefix}{key}' for key in table if key not in known_keys)
    problems.extend(f'missing key {prefix}{key}' for key in required_keys if key not in table)


def _check_hitbox(*, hitbox: Mapping[str, Any] | None, path: str, problems: list[str]) -> None:
    """Check a hitbox table, when there is one."""
    if hitbox is not None:
        _check_table(
            table=hitbox,
            path=path,
            known_keys=frozenset(HITBOX_KEYS),
            required_keys=HITBOX_KEYS,
            problems=problems,
        )


def _animation_section(*, animation: Mapping[str, Any]) -> str:
    """Write one ``[[animation]]`` table with its ``[[animation.frame]]`` tables.

    Returns:
        The TOML text.

    """
    namespace = toml_basic_string(animation['namespace'])
    lines = [
        '[[animation]]\n',
        f'namespace = {namespace}\n',
        f'frame_interval = {toml_scalar(animation["frame_interval"])}\n',
        f'loop = {toml_scalar(animation["loop"])}\n\n',
    ]
    for frame in animation['frame']:
        lines.extend((
            '[[animation.frame]]\n',
            f'namespace = {namespace}\n',
            f'frame_index = {toml_scalar(frame["frame_index"])}\n',
        ))
        if 'frame_interval' in frame:
            lines.append(f'frame_interval = {toml_scalar(frame["frame_interval"])}\n')
        lines.append(f'pixels = {toml_pixel_block(frame["pixels"])}\n\n')
        if 'hitbox' in frame:
            lines.append(
                _hitbox_section(section_header='[animation.frame.hitbox]', hitbox=frame['hitbox'])
            )
    return ''.join(lines)


def _hitbox_section(*, section_header: str, hitbox: Mapping[str, int]) -> str:
    """Write a hitbox table: its offset and size.

    Returns:
        The TOML text, ending in a blank line.

    """
    return (
        f'{section_header}\n'
        f'offset_x = {hitbox["offset_x"]}\n'
        f'offset_y = {hitbox["offset_y"]}\n'
        f'width = {hitbox["width"]}\n'
        f'height = {hitbox["height"]}\n\n'
    )


def _colors_section(*, colors: Mapping[str, Mapping[str, int]]) -> str:
    """Write the ``[colors]`` tables in the mapping's order, or '' for no colors.

    Returns:
        The TOML text.

    """
    if not colors:
        return ''
    lines = ['[colors]\n']
    for character, color in colors.items():
        # Quoted and escaped, so a backslash or quote glyph is a valid key
        lines.extend((
            f'[colors.{toml_basic_string(character)}]\n',
            f'red = {color["red"]}\n',
            f'green = {color["green"]}\n',
            f'blue = {color["blue"]}\n',
        ))
        if 'alpha' in color:
            lines.append(f'alpha = {color["alpha"]}\n')
        lines.append('\n')
    return ''.join(lines)
