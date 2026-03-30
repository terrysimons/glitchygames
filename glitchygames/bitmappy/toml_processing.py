"""TOML parsing and normalization for the Bitmappy editor.

Also provides shared utility functions for color quantization, glyph mapping,
and TOML generation used by both the file I/O and AI integration modules.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from glitchygames.color import ALPHA_TRANSPARENCY_THRESHOLD
from glitchygames.sprites import SPRITE_GLYPHS

if TYPE_CHECKING:
    import logging

    import numpy as np
    import pygame

from glitchygames.color import RGB_COMPONENT_COUNT

from .constants import (
    COLOR_QUANTIZATION_GROUP_DISTANCE_THRESHOLD,
    LOG,
    MAGENTA_TRANSPARENT,
    MIN_COLOR_FIELD_VALUES_FOR_BLUE,
    MIN_COLOR_FIELD_VALUES_FOR_GREEN,
    PROGRESS_LOG_MIN_HEIGHT,
    TRANSPARENT_GLYPH,
)


def parse_toml_robustly(content: str, log: logging.Logger | None = None) -> dict[str, Any]:
    """Parse TOML content with graceful handling of duplicate keys and malformed content.

    Args:
        content: TOML content string
        log: Optional logger for warnings

    Returns:
        Parsed TOML data with duplicate keys resolved (last value wins)

    """
    if log is None:
        log = LOG

    try:
        # First try standard TOML parsing
        data = tomllib.loads(content)
        # Fix color format if needed
        return _fix_color_format_in_toml_data(data, log)
    except tomllib.TOMLDecodeError as e:
        # If parsing fails due to duplicate keys, use a more permissive approach
        log.warning('Standard TOML parsing failed: %s', e)
        log.info('Attempting to parse TOML with duplicate key handling...')

        # Use a custom parser that handles duplicates
        data = _parse_toml_permissively(content, log)
        # Fix color format if needed
        return _fix_color_format_in_toml_data(data, log)


def _parse_toml_permissively(content: str, log: logging.Logger) -> dict[str, Any]:
    """Parse TOML content permissively, handling duplicate keys by taking the last value.

    Args:
        content: TOML content string
        log: Logger for warnings

    Returns:
        Parsed TOML data with duplicate keys resolved

    """
    # Deduplicate by tracking the current section and keeping only the last
    # occurrence of each key within that section.
    lines = content.split('\n')
    current_section = ''
    # Maps (section, key) -> line index for last occurrence
    key_positions: dict[tuple[str, str], int] = {}
    duplicate_indices: set[int] = set()

    for line_index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        # Track current section
        if stripped.startswith('[') and stripped.endswith(']'):
            current_section = stripped
            continue

        # Check for key = value pairs
        if '=' in stripped and not stripped.startswith('['):
            key_part = stripped.split('=')[0].strip()
            section_key = (current_section, key_part)

            if section_key in key_positions:
                # Mark the PREVIOUS occurrence for removal (keep last)
                duplicate_indices.add(key_positions[section_key])
                log.warning(
                    'Duplicate key found: %s in %s, keeping last value',
                    key_part,
                    current_section or 'root',
                )

            key_positions[section_key] = line_index

    # Build cleaned content without duplicate lines
    cleaned_lines = [
        line for line_index, line in enumerate(lines) if line_index not in duplicate_indices
    ]
    cleaned_content = '\n'.join(cleaned_lines)

    try:
        return tomllib.loads(cleaned_content)
    except tomllib.TOMLDecodeError as e:
        # If it still fails, try regex-based parsing
        log.warning('Cleaned TOML parsing also failed: %s', e)
        return _parse_toml_with_regex(content, log)


class _RegexParserState:
    """Mutable state for the regex-based TOML parser."""

    def __init__(self, lines: list[str]) -> None:
        self.data: dict[str, Any] = {}
        self.section_path: list[str] = []
        self.array_path: list[str] | None = None
        self.lines = lines
        self.line_index = 0

    def advance(self) -> tuple[str, int]:
        """Advance to the next line.

        Returns:
            Tuple of (stripped_line, line_number).
        """
        line = self.lines[self.line_index].strip()
        line_num = self.line_index + 1
        self.line_index += 1
        return line, line_num

    def get_target_dict(self) -> dict[str, Any]:
        """Get the dict where the current key-value pair should be stored.

        Returns:
            The target dictionary for the current section.
        """
        if self.array_path:
            last_entry = _get_array_last_entry(self.data, self.array_path)
            sub_path = self.section_path[len(self.array_path) :]
            return _get_nested_dict(last_entry, sub_path)
        return _get_nested_dict(self.data, self.section_path)


def _parse_toml_with_regex(content: str, log: logging.Logger) -> dict[str, Any]:
    """Parse TOML content using regex to handle malformed content.

    Args:
        content: TOML content string
        log: Logger for warnings

    Returns:
        Parsed TOML data
    """
    state = _RegexParserState(content.split('\n'))

    while state.line_index < len(state.lines):
        line, line_num = state.advance()

        if not line or line.startswith('#'):
            continue

        if line.startswith('[[') and line.endswith(']]'):
            _handle_array_of_tables(state, line)
        elif line.startswith('['):
            _handle_section_header(state, line, line_num, log)
        elif '=' in line:
            _handle_key_value(state, line, line_num, log)
        else:
            log.warning('Unrecognized line %s: %s', line_num, line)

    return state.data


def _handle_array_of_tables(state: _RegexParserState, line: str) -> None:
    """Handle [[array.of.tables]] headers."""
    array_name = line[2:-2]
    state.array_path = _parse_section_path(array_name)
    _ensure_array_of_tables(state.data, state.array_path)
    state.section_path = state.array_path


def _handle_section_header(
    state: _RegexParserState,
    line: str,
    line_num: int,
    log: logging.Logger,
) -> None:
    """Handle [section] headers, including malformed ones."""
    if line.endswith(']'):
        section_name = line[1:-1]
    else:
        section_name = line[1:]
        log.warning('Malformed section header at line %s: %s', line_num, line)

    parsed_path = _parse_section_path(section_name)

    if state.array_path and _is_sub_path(state.array_path, parsed_path):
        state.section_path = parsed_path
        last_entry = _get_array_last_entry(state.data, state.array_path)
        sub_path = parsed_path[len(state.array_path) :]
        _ensure_nested_dict(last_entry, sub_path)
    else:
        state.array_path = None
        state.section_path = parsed_path
        _ensure_nested_dict(state.data, state.section_path)


def _handle_key_value(
    state: _RegexParserState,
    line: str,
    line_num: int,
    log: logging.Logger,
) -> None:
    """Handle key = value pairs, including multi-line triple-quoted strings."""
    try:
        key, value = line.split('=', 1)
        key = key.strip()
        value = _strip_inline_comment(value.strip())

        # Handle multi-line triple-quoted strings
        if value == '"""' or (value.startswith('"""') and not value.endswith('"""')):
            value = _read_multiline_string(state, value)
            parsed_value: str | bool | int | float | list[Any] = value
        else:
            parsed_value = _parse_toml_value(value)

        # Remove quotes from key
        if key.startswith('"') and key.endswith('"'):
            key = key[1:-1]

        state.get_target_dict()[key] = parsed_value

    except (ValueError, TypeError, KeyError) as e:
        log.warning('Failed to parse line %s: %s - %s', line_num, line, e)


def _read_multiline_string(state: _RegexParserState, first_value: str) -> str:
    """Read a multi-line triple-quoted string from the parser state.

    Returns:
        The concatenated multi-line string content.
    """
    parts = [first_value.removeprefix('"""')]
    while state.line_index < len(state.lines):
        next_line = state.lines[state.line_index]
        state.line_index += 1
        if '"""' in next_line:
            parts.append(next_line[: next_line.index('"""')])
            break
        parts.append(next_line)
    return '\n'.join(parts)


def _is_sub_path(parent: list[str], child: list[str]) -> bool:
    """Check if child path starts with parent path.

    Returns:
        True if child starts with all elements of parent.
    """
    if len(child) <= len(parent):
        return False
    return child[: len(parent)] == parent


def _ensure_array_of_tables(data: dict[str, Any], path: list[str]) -> None:
    """Ensure a path points to a list and append a new dict entry.

    For [[animation.frame]], ensures data['animation'] is a list with
    the last entry having a 'frame' key that is also a list.
    """
    current = data
    for i, key in enumerate(path):
        if i == len(path) - 1:
            # Last key — ensure it's a list and append new dict
            if key not in current:
                current[key] = []
            if isinstance(current[key], list):
                current[key].append({})
            else:
                current[key] = [{}]
        else:
            # Intermediate key — navigate into it
            if key not in current:
                current[key] = {}
            current = current[key][-1] if isinstance(current[key], list) else current[key]


def _get_array_last_entry(data: dict[str, Any], path: list[str]) -> dict[str, Any]:
    """Get the last entry in an array-of-tables at the given path.

    Returns:
        The last dict entry in the array at the given path.
    """
    current: dict[str, Any] = data
    for key in path:
        value: Any = current[key]
        current = cast('dict[str, Any]', value[-1] if isinstance(value, list) else value)
    return current


def _strip_inline_comment(value: str) -> str:
    """Strip an inline comment from a TOML value string.

    Preserves '#' characters inside quoted strings.

    Args:
        value: The raw value string (may include trailing comment).

    Returns:
        The value with any inline comment removed.
    """
    if value.startswith('"'):
        # Find the closing quote, then check for comment after it
        close_quote = value.find('"', 1)
        if close_quote >= 0:
            after_quote = value[close_quote + 1 :]
            comment_index = after_quote.find('#')
            if comment_index >= 0:
                return value[: close_quote + 1].strip()
        return value
    # Unquoted value — strip at first '#'
    comment_index = value.find('#')
    if comment_index >= 0:
        return value[:comment_index].strip()
    return value


def _parse_section_path(section_name: str) -> list[str]:
    """Parse a dotted TOML section name into path components.

    Handles quoted keys like 'colors."."' -> ['colors', '.'].

    Args:
        section_name: The section name string (e.g., 'colors."."').

    Returns:
        List of path components with quotes stripped.
    """
    parts: list[str] = []
    remaining = section_name.strip()
    while remaining:
        if remaining.startswith('"'):
            # Quoted key — find closing quote
            end_quote = remaining.index('"', 1)
            parts.append(remaining[1:end_quote])
            remaining = remaining[end_quote + 1 :]
            remaining = remaining.removeprefix('.')
        else:
            # Unquoted key — split on dot
            dot_index = remaining.find('.')
            if dot_index >= 0:
                parts.append(remaining[:dot_index])
                remaining = remaining[dot_index + 1 :]
            else:
                parts.append(remaining)
                remaining = ''
    return parts


def _ensure_nested_dict(data: dict[str, Any], path: list[str]) -> None:
    """Ensure a nested dict structure exists for the given path.

    Args:
        data: Root dictionary.
        path: List of keys to create nested dicts for.
    """
    current = data
    for key in path:
        if key not in current:
            current[key] = {}
        current = current[key]


def _get_nested_dict(data: dict[str, Any], path: list[str]) -> dict[str, Any]:
    """Get the nested dict at the given path, or root if path is empty.

    Args:
        data: Root dictionary.
        path: List of keys to traverse.

    Returns:
        The nested dict at the path location.
    """
    current = data
    for key in path:
        current = current[key]
    return current


def _parse_toml_value(value: str) -> str | bool | int | float | list[Any]:  # noqa: PLR0911
    """Parse a TOML value string into Python object.

    Args:
        value: Value string from TOML

    Returns:
        Parsed Python value

    """
    value = value.strip()

    # Handle triple-quoted strings (must check before single quotes)
    if value.startswith('"""') and value.endswith('"""'):
        return value[3:-3]

    # Handle quoted strings
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]

    # Handle boolean values
    if value.lower() in {'true', 'false'}:
        return value.lower() == 'true'

    # Handle numeric values
    try:
        if '.' in value:
            return float(value)
        return int(value)
    except ValueError:
        pass

    # Handle arrays (comma-separated values)
    if ',' in value:
        return [_parse_toml_value(item.strip()) for item in value.split(',')]

    # Return as string if nothing else matches
    return value


def _fix_comma_separated_color_field(
    field_name: str,
    field_value: str,
    fixed_color: dict[str, Any],
    color_key: str,
    log: logging.Logger,
) -> None:
    """Parse a comma-separated color field value and populate the fixed_color dict.

    Args:
        field_name: The color field name ("red", "green", or "blue").
        field_value: The comma-separated string value.
        fixed_color: Dictionary to populate with parsed values.
        color_key: The color key name (for logging).
        log: Logger for warnings.

    """
    try:
        values = [int(x.strip()) for x in field_value.split(',')]

        if field_name == 'red' and len(values) >= 1:
            fixed_color['red'] = values[0]
            if len(values) >= MIN_COLOR_FIELD_VALUES_FOR_GREEN:
                fixed_color['green'] = values[1]
            if len(values) >= MIN_COLOR_FIELD_VALUES_FOR_BLUE:
                fixed_color['blue'] = values[2]
            log.warning(
                "Fixed comma-separated color format for '%s': %s -> separate fields",
                color_key,
                field_value,
            )
        elif field_name == 'green' and len(values) >= 1:
            fixed_color['green'] = values[0]
        elif field_name == 'blue' and len(values) >= 1:
            fixed_color['blue'] = values[0]
    except (ValueError, IndexError) as e:
        log.warning(
            "Failed to parse comma-separated color value '%s' for '%s': %s",
            field_value,
            color_key,
            e,
        )
        fixed_color[field_name] = field_value


def _fix_list_color_field(
    field_name: str,
    field_value: list[Any],
    fixed_color: dict[str, Any],
    color_key: str,
    log: logging.Logger,
) -> None:
    """Fix a color field that was parsed as a list (e.g., [255, 0, 0] from regex parser).

    Args:
        field_name: The color field name ("red", "green", or "blue").
        field_value: The list of parsed values.
        fixed_color: Dictionary to populate with parsed values.
        color_key: The color key name (for logging).
        log: Logger for warnings.
    """
    values = [int(value) for value in field_value if isinstance(value, int | float)]

    if field_name == 'red' and len(values) >= 1:
        fixed_color['red'] = values[0]
        if len(values) >= MIN_COLOR_FIELD_VALUES_FOR_GREEN:
            fixed_color['green'] = values[1]
        if len(values) >= MIN_COLOR_FIELD_VALUES_FOR_BLUE:
            fixed_color['blue'] = values[2]
        log.warning(
            "Fixed list color format for '%s': %s -> separate fields",
            color_key,
            field_value,
        )
    elif field_name == 'green' and len(values) >= 1:
        fixed_color['green'] = values[0]
    elif field_name == 'blue' and len(values) >= 1:
        fixed_color['blue'] = values[0]


def _fix_color_entry(
    color_data: dict[str, Any],
    color_key: str,
    log: logging.Logger,
) -> dict[str, Any]:
    """Fix a single color entry's format, handling comma-separated values.

    Args:
        color_data: Dictionary of color fields for one color entry.
        color_key: The color key name (for logging).
        log: Logger for warnings.

    Returns:
        Fixed color entry dictionary.

    """
    fixed_color: dict[str, Any] = {}
    for field_name in ['red', 'green', 'blue']:
        if field_name not in color_data:
            continue
        field_value = color_data[field_name]
        if isinstance(field_value, list):
            # Handle list values from regex parser (e.g., [255, 0, 0])
            _fix_list_color_field(
                field_name,
                cast('list[Any]', field_value),
                fixed_color,
                color_key,
                log,
            )
        elif isinstance(field_value, str) and ',' in field_value:
            _fix_comma_separated_color_field(field_name, field_value, fixed_color, color_key, log)
        else:
            fixed_color[field_name] = field_value
    return fixed_color


def _fix_color_format_in_toml_data(data: dict[str, Any], log: logging.Logger) -> dict[str, Any]:
    """Fix incorrect color format in TOML data.

    Converts comma-separated values to separate fields.

    Args:
        data: Parsed TOML data
        log: Logger for warnings

    Returns:
        Fixed TOML data with proper color format

    """
    if 'colors' not in data:
        return data

    fixed_colors = {}
    for color_key, color_data in data['colors'].items():
        if isinstance(color_data, dict):
            fixed_colors[color_key] = _fix_color_entry(color_data, color_key, log)  # type: ignore[arg-type]
        else:
            fixed_colors[color_key] = color_data

    data['colors'] = fixed_colors
    return data


def _normalize_escaped_newlines(text: str) -> str:
    r"""Convert escaped newline sequences to actual newlines.

    Handles both \\\\n (double escaped) and \\n (single escaped).

    Args:
        text: String potentially containing escaped newlines.

    Returns:
        String with actual newline characters.

    """
    return text.replace('\\\\n', '\n').replace('\\n', '\n')


def _normalize_animation_pixels(animation_list: list[Any]) -> None:
    """Normalize pixel strings in animation frame data in-place.

    Args:
        animation_list: List of animation dictionaries with frame data.

    """
    for animation in animation_list:
        if not isinstance(animation, dict) or 'frame' not in animation:
            continue
        for frame in animation['frame']:  # type: ignore[index]
            if isinstance(frame, dict) and 'pixels' in frame and isinstance(frame['pixels'], str):
                frame['pixels'] = _normalize_escaped_newlines(frame['pixels'])


def normalize_toml_data(config_data: dict[str, Any]) -> dict[str, Any]:
    """Normalize TOML data by converting triple-quoted strings to proper format.

    Args:
        config_data: Raw TOML data loaded from file

    Returns:
        Normalized TOML data with proper string formatting

    """
    try:
        normalized_data = config_data.copy()

        # Handle sprite pixels
        if 'sprite' in normalized_data and 'pixels' in normalized_data['sprite']:
            pixels = normalized_data['sprite']['pixels']
            if isinstance(pixels, str):
                normalized_data['sprite']['pixels'] = _normalize_escaped_newlines(pixels)

        # Handle animation frame pixels
        if 'animation' in normalized_data:
            _normalize_animation_pixels(normalized_data['animation'])

    except (AttributeError, KeyError, TypeError) as e:
        LOG.warning(f'Error normalizing TOML data: {e}')
        return config_data
    else:
        return normalized_data


# ──────────────────────────────────────────────────────────────────────────────
# Shared utilities for color quantization, glyph mapping, and TOML generation
# Used by both file_io.py (PNG conversion) and ai_integration.py
# ──────────────────────────────────────────────────────────────────────────────


def color_distance(color_1: tuple[int, int, int], color_2: tuple[int, int, int]) -> float:
    """Calculate squared Euclidean distance between two RGB colors.

    Args:
        color_1: First RGB color tuple.
        color_2: Second RGB color tuple.

    Returns:
        Squared Euclidean distance as a float.

    """
    return sum((int(a) - int(b)) ** 2 for a, b in zip(color_1, color_2, strict=True))


def quantize_colors_if_needed(
    unique_colors: set[tuple[int, int, int]],
    *,
    has_transparency: bool,
    max_colors: int = 1000,
    log: logging.Logger | None = None,
) -> set[tuple[int, int, int]]:
    """Quantize colors if there are too many for the palette.

    Args:
        unique_colors: Set of unique RGB color tuples.
        has_transparency: Whether the image has transparency.
        max_colors: Maximum number of colors allowed.
        log: Optional logger.

    Returns:
        Possibly reduced set of unique colors.

    """
    if log is None:
        log = LOG

    reserved_for_transparency = 1 if has_transparency else 0
    available_colors = max_colors - reserved_for_transparency

    if len(unique_colors) <= available_colors:
        return unique_colors

    log.info('Too many colors detected, using color quantization...')
    color_groups: dict[tuple[int, int, int], list[tuple[int, int, int]]] = {}
    for color in unique_colors:
        closest_group = None
        min_distance = float('inf')

        for group_color in color_groups:
            distance = sum((a - b) ** 2 for a, b in zip(color, group_color, strict=True))
            if distance < min_distance:
                min_distance = distance
                closest_group = group_color

        # If no close group exists and we have space, create new group
        if closest_group is None or min_distance > COLOR_QUANTIZATION_GROUP_DISTANCE_THRESHOLD:
            if len(color_groups) < available_colors:
                color_groups[color] = [color]
            else:
                # Add to closest existing group
                color_groups[closest_group].append(color)  # type: ignore[index] # ty: ignore[invalid-argument-type]
        else:
            color_groups[closest_group].append(color)

    # Create representative colors for each group
    representative_colors = [group_color for group_color, colors in color_groups.items() if colors]
    result = set(representative_colors)
    log.info(f'Quantized to {len(result)} representative colors')
    log.info(f'Available colors: {available_colors}, Color groups created: {len(color_groups)}')
    return result


def build_color_to_glyph_mapping(
    unique_colors: set[tuple[int, int, int]],
    *,
    has_transparency: bool,
    force_single_char_glyphs: bool = False,
    log: logging.Logger | None = None,
) -> dict[tuple[int, int, int], str]:
    """Build a mapping from RGB colors to glyph characters.

    Args:
        unique_colors: Set of unique RGB color tuples.
        has_transparency: Whether the image has transparency.
        force_single_char_glyphs: If True, limit to first 64 single-char glyphs.
        log: Optional logger.

    Returns:
        Dictionary mapping RGB tuples to glyph strings.

    """
    if log is None:
        log = LOG

    max_glyphs = 64 if force_single_char_glyphs else 1000
    available_glyphs = list(SPRITE_GLYPHS[:max_glyphs])
    reserved_for_transparency = 1 if has_transparency else 0
    available_color_count = len(available_glyphs) - reserved_for_transparency

    log.info(
        f'Mapping colors: {len(unique_colors)} unique colors to {available_color_count}'
        f' available glyphs',
    )
    if has_transparency:
        log.info('Reserved 1 glyph for transparency')

    color_mapping: dict[tuple[int, int, int], str] = {}
    glyph_index = 0

    # First, ensure magenta (transparency) gets a glyph if we have transparency
    if has_transparency and MAGENTA_TRANSPARENT in unique_colors:
        color_mapping[MAGENTA_TRANSPARENT] = TRANSPARENT_GLYPH
        log.info("Reserved glyph '%s' for transparency (magenta)", TRANSPARENT_GLYPH)

    # Map other colors to available glyphs
    for color in sorted(unique_colors):
        if color == MAGENTA_TRANSPARENT and has_transparency:
            continue  # Already handled above

        if glyph_index < available_color_count:
            color_mapping[color] = available_glyphs[glyph_index]
            glyph_index += 1
        else:
            # Map to closest existing color
            closest_color = min(
                color_mapping.keys(),
                key=lambda c: color_distance(color, c),
            )
            color_mapping[color] = color_mapping[closest_color]

    log.info(f'Final color mapping: {len(color_mapping)} colors mapped to glyphs')
    return color_mapping


def generate_pixel_string(  # noqa: PLR0913
    pixel_array: np.ndarray[Any, Any],
    width: int,
    height: int,
    *,
    has_transparency: bool,
    original_image: pygame.Surface | None,
    color_mapping: dict[tuple[int, int, int], str],
    log: logging.Logger | None = None,
) -> str:
    """Generate the pixel string for TOML output from pixel data.

    Args:
        pixel_array: The numpy pixel array from the image.
        width: Image width.
        height: Image height.
        has_transparency: Whether the image has transparency.
        original_image: The original image with alpha channel, or None.
        color_mapping: Mapping from RGB tuples to glyph characters.
        log: Optional logger.

    Returns:
        The pixel string with newlines between rows.

    """
    if log is None:
        log = LOG

    log.info('Generating pixel string...')
    rows: list[str] = []
    for y in range(height):
        row_chars: list[str] = []
        for x in range(width):
            r, g, b = pixel_array[x, y]
            color_key = (int(r), int(g), int(b))

            # Handle transparency - check if this pixel should be transparent
            if has_transparency and original_image is not None:
                original_pixel = original_image.get_at((x, y))
                if original_pixel.a < ALPHA_TRANSPARENCY_THRESHOLD:
                    color_key = MAGENTA_TRANSPARENT

            # If color is not in mapping, find closest mapped color
            if color_key not in color_mapping:
                closest_color = min(
                    color_mapping.keys(),
                    key=lambda c: color_distance(color_key, c),
                )
                color_mapping[color_key] = color_mapping[closest_color]
                log.debug('Mapped unmapped color %s to %s', color_key, closest_color)

            row_chars.append(color_mapping[color_key])
        rows.append(''.join(row_chars))

        # Log progress for large images
        if height > PROGRESS_LOG_MIN_HEIGHT and y % (height // 10) == 0:
            log.info('Progress: %s/%s rows processed', y, height)

    return '\n'.join(rows)


def generate_toml_content(
    file_path: str,
    pixel_string: str,
    color_mapping: dict[tuple[int, int, int], str],
    *,
    log: logging.Logger | None = None,
) -> str:
    """Generate the TOML file content from pixel string and color mapping.

    Args:
        file_path: Original PNG file path (used for naming).
        pixel_string: The pixel string with glyph characters.
        color_mapping: Mapping from RGB tuples to glyph characters.
        log: Optional logger.

    Returns:
        The complete TOML content string.

    Raises:
        ValueError: If no color definitions were generated.

    """
    if log is None:
        log = LOG

    toml_content = (
        f'[sprite]\n'
        f'name = "imported_from_{Path(file_path).stem}"\n'
        f'pixels = """\n'
        f'{pixel_string}\n'
        f'"""\n'
        f'\n'
        f'[colors]\n'
        f''
    )

    # Add color definitions - collect unique glyphs first
    unique_glyphs = set(color_mapping.values())
    log.info(f'Unique glyphs to define: {sorted(unique_glyphs)}')

    for glyph in sorted(unique_glyphs):
        # Find the first color that maps to this glyph
        for color, mapped_glyph in color_mapping.items():
            if mapped_glyph == glyph:
                r, g, b = color
                # Quote the glyph to handle special characters like '.'
                toml_content += f'[colors."{glyph}"]\nred = {r}\ngreen = {g}\nblue = {b}\n\n'
                log.info('Defined color %s: RGB(%s, %s, %s)', glyph, r, g, b)
                break

    if not unique_glyphs:
        log.error('No colors to define - this will cause display issues!')
        msg = 'No colors found in the converted sprite'
        raise ValueError(msg)

    log.info(f'Generated {len(unique_glyphs)} color definitions')
    return toml_content


def collect_unique_colors_from_pixels(
    pixels: list[tuple[int, ...]],
) -> set[tuple[int, int, int]]:
    """Extract unique RGB colors from a list of pixel color tuples.

    Args:
        pixels: List of pixel color tuples (RGB or RGBA).

    Returns:
        Set of unique RGB color tuples (first 3 components).

    """
    unique_colors: set[tuple[int, int, int]] = set()
    for pixel in pixels:
        if len(pixel) >= RGB_COMPONENT_COUNT:
            unique_colors.add((int(pixel[0]), int(pixel[1]), int(pixel[2])))
    return unique_colors


def build_pixel_string_from_pixels(  # noqa: PLR0913
    pixels: list[tuple[int, ...]],
    width: int,
    height: int,
    color_to_glyph: dict[tuple[int, int, int], str],
    sorted_colors: list[tuple[int, int, int]],
    *,
    force_single_char_glyphs: bool = False,
) -> str:
    """Build a glyph pixel string from a flat list of pixel colors.

    Args:
        pixels: List of pixel color tuples (RGB or RGBA).
        width: Image width in pixels.
        height: Image height in pixels.
        color_to_glyph: Mapping from RGB tuples to glyph characters.
        sorted_colors: Sorted list of unique colors (unused but kept for API compat).
        force_single_char_glyphs: If True, limit to single-character glyph lookup.

    Returns:
        The pixel string with newlines between rows.

    """
    _ = force_single_char_glyphs  # Reserved for future use
    _ = sorted_colors  # Available via color_to_glyph.keys()

    rows: list[str] = []
    for y in range(height):
        row_chars: list[str] = []
        for x in range(width):
            pixel_index = y * width + x
            if pixel_index < len(pixels):
                pixel = pixels[pixel_index]
                color_key = (int(pixel[0]), int(pixel[1]), int(pixel[2]))

                if color_key in color_to_glyph:
                    row_chars.append(color_to_glyph[color_key])
                else:
                    # Find closest color in mapping
                    closest = min(
                        color_to_glyph.keys(),
                        key=lambda c: color_distance(color_key, c),
                    )
                    row_chars.append(color_to_glyph[closest])
            else:
                # Out of bounds — use transparency glyph
                row_chars.append(TRANSPARENT_GLYPH)
        rows.append(''.join(row_chars))

    return '\n'.join(rows)
