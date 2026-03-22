"""TOML parsing and normalization for the Bitmappy editor."""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import logging

from .constants import LOG, MIN_COLOR_FIELD_VALUES_FOR_BLUE, MIN_COLOR_FIELD_VALUES_FOR_GREEN


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
        log.warning(f'Standard TOML parsing failed: {e}')
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
    # Create a custom TOML parser that handles duplicates
    lines = content.split('\n')
    processed_lines: list[str] = []
    seen_keys: set[str] = set()

    for line in lines:
        # Check if this line defines a key-value pair
        if '=' in line and not line.strip().startswith('#'):
            # Extract the key part (before the =)
            key_part = line.split('=')[0].strip()

            # Check if this is a section header like [colors."X"]
            if key_part.startswith('[') and key_part.endswith(']'):
                # This is a section header, keep it
                processed_lines.append(line)
                continue

            # Check if this is a simple key = value pair
            if not key_part.startswith('[') and not key_part.startswith('"'):
                # This might be a simple key, check for duplicates
                if key_part in seen_keys:
                    log.warning(f'Duplicate key found: {key_part}, keeping last value')
                else:
                    seen_keys.add(key_part)
                processed_lines.append(line)
                continue

        # For all other lines, keep them as-is
        processed_lines.append(line)

    # Now try to parse the cleaned content
    cleaned_content = '\n'.join(processed_lines)

    try:
        return tomllib.loads(cleaned_content)
    except tomllib.TOMLDecodeError as e:
        # If it still fails, try a more aggressive approach
        log.warning(f'Cleaned TOML parsing also failed: {e}')
        return _parse_toml_with_regex(content, log)


def _parse_toml_with_regex(content: str, log: logging.Logger) -> dict[str, Any]:
    """Parse TOML content using regex to handle malformed content.

    Args:
        content: TOML content string
        log: Logger for warnings

    Returns:
        Parsed TOML data

    """
    data: dict[str, Any] = {}
    current_section: str | None = None

    lines = content.split('\n')
    for line_num, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue

        # Handle section headers
        if line.startswith('[') and line.endswith(']'):
            section_name = line[1:-1]
            if section_name not in data:
                data[section_name] = {}
            current_section = section_name
            continue

        # Handle key-value pairs
        if '=' in line:
            try:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes from key if present
                if key.startswith('"') and key.endswith('"'):
                    key = key[1:-1]

                # Parse the value
                parsed_value = _parse_toml_value(value)

                if current_section:
                    data[current_section][key] = parsed_value
                else:
                    data[key] = parsed_value

            except (ValueError, TypeError, KeyError) as e:
                log.warning(f'Failed to parse line {line_num}: {line} - {e}')
                continue

    return data


def _parse_toml_value(value: str) -> str | bool | int | float | list[Any]:
    """Parse a TOML value string into Python object.

    Args:
        value: Value string from TOML

    Returns:
        Parsed Python value

    """
    value = value.strip()

    # Handle quoted strings
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]

    # Handle triple-quoted strings
    if value.startswith('"""') and value.endswith('"""'):
        return value[3:-3]

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
                f"Fixed comma-separated color format for '{color_key}':"
                f' {field_value} -> separate fields'
            )
        elif field_name == 'green' and len(values) >= 1:
            fixed_color['green'] = values[0]
        elif field_name == 'blue' and len(values) >= 1:
            fixed_color['blue'] = values[0]
    except (ValueError, IndexError) as e:
        log.warning(
            f"Failed to parse comma-separated color value '{field_value}' for '{color_key}': {e}"
        )
        fixed_color[field_name] = field_value


def _fix_color_entry(
    color_data: dict[str, Any], color_key: str, log: logging.Logger
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
        if isinstance(field_value, str) and ',' in field_value:
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

        return normalized_data

    except (AttributeError, KeyError, TypeError) as e:
        LOG.warning(f'Error normalizing TOML data: {e}')
        return config_data
