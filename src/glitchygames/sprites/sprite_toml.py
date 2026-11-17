"""A sprite file's text as data: parsed from TOML text and written back as TOML text.

This module imports only the standard library (no pygame, no engine module) so it can be lifted
into a pygame-free package unchanged. A sprite file is a TOML document; ``parse_sprite_toml``
turns text into that document and ``write_sprite_toml`` turns a document into text in the
layout the engine writes: a round trip keeps the same parsed sprite, not the same bytes.
"""

from __future__ import annotations

import math
import tomllib
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

# The [sprite] key holding a sprite's tags (the engine's glitchygames.sprites.tags.TAGS_KEY;
# a test keeps the two equal, as this module may import only the standard library)
TAGS_KEY = 'tags'

# The keys the engine's loader reads (AnimatedSprite._load_toml and its static loader), by table.
# The loader treats every one as optional, so the writer writes a key when the document has it
# and omits it when it does not, never defaulting: a round trip keeps the parsed sprite exactly.
# Inside these tables the writer refuses any other key rather than dropping it. A top-level table
# the engine does not own (a game's own, such as Drawing Fire's [swatches]) is written back as is.
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
    breaks between rows stay real so the rows stay readable. The text is written exactly as
    given: TOML drops the newline right after the opening quotes, so the string parses back
    equal, with a final line break only if the text had one ('' and 'a' stay '' and 'a').

    Returns:
        str: The rows wrapped in triple quotes, the opening quotes on their own line.

    """
    rows = pixel_text.split('\n')
    # toml_basic_string quotes a row; the quotes are dropped, the escapes kept
    escaped_rows = [toml_basic_string(row)[1:-1] for row in rows]
    return '"""\n' + '\n'.join(escaped_rows) + '"""'


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

    The static layout is a ``[sprite]`` table with ``pixels``; an animated sprite is ``[sprite]``,
    then each ``[[animation]]`` with its ``[[animation.frame]]`` tables. Then come ``[colors]`` in
    the document's order, each ``[[transition]]`` and any other top-level table (a game's own),
    written as it is. A key the document has is written, one it lacks is left out, so parsing the
    text gives the document back. A key the writer does not know inside the engine's own tables
    (it would be dropped) is refused with a ValueError naming each by its path
    (``sprite.unknown_key``, ``animation[0].frame[1].extra``).

    Args:
        data: The sprite document (as ``parse_sprite_toml`` returns).

    Returns:
        The TOML text.

    """
    _check_document(data=data)
    # A value of the document's root must come before any table header, or it joins that table
    lines: list[str] = [
        f'{toml_key(key)} = {_inline_value(value)}\n'
        for key, value in data.items()
        if key not in DOCUMENT_KEYS and not isinstance(value, dict)
    ]
    if 'sprite' in data:
        lines.append(_sprite_section(sprite=data['sprite']))
    lines.extend(_animation_section(animation=animation) for animation in data.get('animation', []))
    lines.append(_colors_section(colors=data.get('colors', {})))
    for transition in data.get('transition', []):
        lines.extend((
            '\n[[transition]]\n',
            *(f'{toml_key(key)} = {_inline_value(value)}\n' for key, value in transition.items()),
        ))
    lines.extend(
        _generic_table_section(path=(key,), table=cast('dict[str, Any]', table))
        for key, table in data.items()
        if key not in DOCUMENT_KEYS and isinstance(table, dict)
    )
    return ''.join(lines)


def split_sprite_text(*, text: str) -> list[str]:
    """Split a sprite file's text into one single-image sprite text per frame.

    Each frame becomes a static-layout document: ``[sprite]`` named
    ``<sprite>-<animation>-<frame>`` (the sprite's name defaults to ``animated_sprite`` and an
    animation's namespace to ``default``, as the loader does; frames are numbered from 0 within
    their animation, animations in file order), the source's ``description``, ``tags`` and
    ``frame_anchor`` where it has them, the frame's ``pixels`` and its hitbox (the frame's, else
    the sprite's) as ``[sprite.hitbox]``. ``[colors]`` keeps the glyphs the frame uses, in the
    source's color order. A static sprite is one frame, named with the ``default`` animation and
    frame 0, even without pixels. A frame without ``pixels`` (the loader defaults them to '')
    becomes a sprite with empty pixels, and an animation with no frames gives none.

    Names follow from that rule, so two animations with the same namespace (or both omitting it)
    give frames with the same name: the names are not made unique.

    A split frame is a new single-image sprite, not a round trip: a game's own top-level tables
    (Drawing Fire's ``[swatches]``) and ``[[transition]]`` are not carried into it, because they
    name glyphs and animations the frame may not keep.

    Args:
        text: The sprite file's TOML text.

    Returns:
        One TOML text per frame, in animation and frame order.

    """
    # parse_sprite_toml raises ValueError for text that is not valid TOML
    document = parse_sprite_toml(text=text, source_name='sprite text')
    sprite: Mapping[str, Any] = document.get('sprite', {})
    sprite_name = sprite.get('name', 'animated_sprite')
    colors: Mapping[str, Any] = document.get('colors', {})
    animations: list[Mapping[str, Any]] = document.get('animation', [])
    if animations:
        frames = [
            (animation.get('namespace', 'default'), frame_number, frame)
            for animation in animations
            for frame_number, frame in enumerate(animation.get('frame', []))
        ]
    else:
        frames = [('default', 0, sprite)]
    texts: list[str] = []
    for animation_name, frame_number, frame in frames:
        frame_name = f'{sprite_name}-{animation_name}-{frame_number}'
        frame_sprite: dict[str, Any] = {'name': frame_name}
        frame_sprite.update({
            key: sprite[key] for key in ('description', TAGS_KEY, 'frame_anchor') if key in sprite
        })
        # The loader defaults a frame's missing pixels to '': an empty frame is still a frame
        pixels = frame.get('pixels', '')
        frame_sprite['pixels'] = pixels
        hitbox = frame.get('hitbox', sprite.get('hitbox'))
        if hitbox is not None:
            frame_sprite['hitbox'] = hitbox
        glyphs_used = set(pixels)
        frame_document: dict[str, Any] = {
            'sprite': frame_sprite,
            'colors': {glyph: color for glyph, color in colors.items() if glyph in glyphs_used},
        }
        texts.append(write_sprite_toml(data=frame_document))
    return texts


def _sprite_section(*, sprite: Mapping[str, Any]) -> str:
    """Write the ``[sprite]`` table and its hitbox.

    Returns:
        The TOML text.

    """
    lines = ['[sprite]\n']
    if 'name' in sprite:
        lines.append(f'name = {toml_basic_string(sprite["name"])}\n')
    if 'description' in sprite:
        lines.append(f'description = {toml_multiline_basic_string(sprite["description"])}\n')
    if TAGS_KEY in sprite:
        # toml_tags_line writes no line for no tags, which would lose an empty list
        lines.append(toml_tags_line(sprite[TAGS_KEY]) or f'{TAGS_KEY} = []\n')
    if 'frame_anchor' in sprite:
        lines.append(f'frame_anchor = {toml_basic_string(sprite["frame_anchor"])}\n')
    if 'pixels' in sprite:
        lines.append(f'pixels = {toml_pixel_block(sprite["pixels"])}\n')
    lines.append('\n')
    if 'hitbox' in sprite:
        lines.append(_hitbox_section(section_header='[sprite.hitbox]', hitbox=sprite['hitbox']))
    return ''.join(lines)


def _check_document(*, data: Mapping[str, Any]) -> None:
    """Refuse a document with a key in the engine's own tables the writer would drop.

    Raises:
        ValueError: Naming every unknown key by its path.

    """
    problems: list[str] = []
    sprite: Mapping[str, Any] | None = data.get('sprite')
    if sprite is not None:
        _check_table(table=sprite, path='sprite', known_keys=SPRITE_KEYS, problems=problems)
        _check_hitbox(hitbox=sprite.get('hitbox'), path='sprite.hitbox', problems=problems)
    for character, color in data.get('colors', {}).items():
        _check_table(
            table=color, path=f'colors.{character}', known_keys=COLOR_KEYS, problems=problems
        )
    for animation_index, animation in enumerate(data.get('animation', [])):
        animation_path = f'animation[{animation_index}]'
        _check_table(
            table=animation, path=animation_path, known_keys=ANIMATION_KEYS, problems=problems
        )
        for frame_index, frame in enumerate(animation.get('frame', [])):
            frame_path = f'{animation_path}.frame[{frame_index}]'
            _check_table(table=frame, path=frame_path, known_keys=FRAME_KEYS, problems=problems)
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
    problems: list[str],
) -> None:
    """Add a problem for each key in the table that the writer does not know."""
    problems.extend(f'unknown key {path}.{key}' for key in table if key not in known_keys)


def _check_hitbox(*, hitbox: Mapping[str, Any] | None, path: str, problems: list[str]) -> None:
    """Check a hitbox table, when there is one."""
    if hitbox is not None:
        _check_table(table=hitbox, path=path, known_keys=frozenset(HITBOX_KEYS), problems=problems)


def _animation_section(*, animation: Mapping[str, Any]) -> str:
    """Write one ``[[animation]]`` table with its ``[[animation.frame]]`` tables.

    Returns:
        The TOML text.

    """
    lines = ['[[animation]]\n']
    lines.extend(
        f'{key} = {_inline_value(animation[key])}\n'
        for key in ('namespace', 'frame_interval', 'loop')
        if key in animation
    )
    lines.append('\n')
    for frame in animation.get('frame', []):
        lines.append('[[animation.frame]]\n')
        lines.extend(
            f'{key} = {_frame_value(key=key, value=frame[key])}\n'
            for key in ('namespace', 'frame_index', 'frame_interval', 'pixels')
            if key in frame
        )
        lines.append('\n')
        if 'hitbox' in frame:
            lines.append(
                _hitbox_section(section_header='[animation.frame.hitbox]', hitbox=frame['hitbox'])
            )
    return ''.join(lines)


def _frame_value(*, key: str, value: object) -> str:
    """Write a frame's value: pixels as a block of rows, any other key inline.

    Returns:
        The TOML text of the value.

    """
    return toml_pixel_block(str(value)) if key == 'pixels' else _inline_value(value)


def _hitbox_section(*, section_header: str, hitbox: Mapping[str, int]) -> str:
    """Write a hitbox table: the offset and size keys it has.

    Returns:
        The TOML text, ending in a blank line.

    """
    return (
        f'{section_header}\n'
        + ''.join(f'{key} = {hitbox[key]}\n' for key in HITBOX_KEYS if key in hitbox)
        + '\n'
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
        lines.append(f'[colors.{toml_basic_string(character)}]\n')
        lines.extend(
            f'{key} = {color[key]}\n' for key in ('red', 'green', 'blue', 'alpha') if key in color
        )
        lines.append('\n')
    return ''.join(lines)


def _generic_table_section(*, path: tuple[str, ...], table: dict[str, Any]) -> str:
    """Write a table the engine does not own: its values first, then its sub-tables.

    Returns:
        The TOML text.

    """
    values = {key: item for key, item in table.items() if not isinstance(item, dict)}
    sub_tables = {
        key: cast('dict[str, Any]', item) for key, item in table.items() if isinstance(item, dict)
    }
    lines: list[str] = []
    # A table with only sub-tables needs no header of its own; an empty one keeps its header
    if values or not sub_tables:
        lines.append('\n[' + '.'.join(toml_key(part) for part in path) + ']\n')
        lines.extend(f'{toml_key(key)} = {_inline_value(item)}\n' for key, item in values.items())
    lines.extend(
        _generic_table_section(path=(*path, key), table=item) for key, item in sub_tables.items()
    )
    return ''.join(lines)


def _inline_value(value: object) -> str:
    """Write a value on one line: a scalar, an array or an inline table.

    Returns:
        The TOML text of the value.

    """
    if isinstance(value, list):
        items = cast('list[object]', value)
        return '[' + ', '.join(_inline_value(item) for item in items) + ']'
    if isinstance(value, dict):
        table = cast('dict[str, object]', value)
        return (
            '{ '
            + ', '.join(f'{toml_key(key)} = {_inline_value(item)}' for key, item in table.items())
            + ' }'
            if table
            else '{}'
        )
    return toml_scalar(value)
