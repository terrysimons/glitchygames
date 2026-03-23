"""TOML parsing and normalization for the Bitmappy editor.

Also provides shared utility functions for color quantization, glyph mapping,
and TOML generation used by both the file I/O and AI integration modules.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glitchygames.color import ALPHA_TRANSPARENCY_THRESHOLD
from glitchygames.sprites import SPRITE_GLYPHS

if TYPE_CHECKING:
    import logging

    import numpy as np
    import pygame

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
                color_groups[closest_group].append(color)  # type: ignore[index]
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
        f' available glyphs'
    )
    if has_transparency:
        log.info('Reserved 1 glyph for transparency')

    color_mapping: dict[tuple[int, int, int], str] = {}
    glyph_index = 0

    # First, ensure magenta (transparency) gets a glyph if we have transparency
    if has_transparency and MAGENTA_TRANSPARENT in unique_colors:
        color_mapping[MAGENTA_TRANSPARENT] = TRANSPARENT_GLYPH
        log.info(f"Reserved glyph '{TRANSPARENT_GLYPH}' for transparency (magenta)")

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


def generate_pixel_string(
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
                log.debug(f'Mapped unmapped color {color_key} to {closest_color}')

            row_chars.append(color_mapping[color_key])
        rows.append(''.join(row_chars))

        # Log progress for large images
        if height > PROGRESS_LOG_MIN_HEIGHT and y % (height // 10) == 0:
            log.info(f'Progress: {y}/{height} rows processed')

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
                log.info(f'Defined color {glyph}: RGB({r}, {g}, {b})')
                break

    if not unique_glyphs:
        log.error('No colors to define - this will cause display issues!')
        raise ValueError('No colors found in the converted sprite')

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
        if len(pixel) >= 3:  # noqa: PLR2004
            unique_colors.add((int(pixel[0]), int(pixel[1]), int(pixel[2])))
    return unique_colors


def build_pixel_string_from_pixels(
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
