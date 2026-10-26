"""Alpha channel detection and conversion for the Bitmappy editor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from glitchygames.color import MAX_COLOR_CHANNEL_VALUE, RGBA_COMPONENT_COUNT

from .constants import ai_training_state
from .toml_processing import normalize_toml_data


def _detect_alpha_channel(colors: dict[str, Any]) -> bool:
    """Detect if colors contain alpha channel information or magenta transparency.

    Args:
        colors: Dictionary of color definitions

    Returns:
        bool: True if alpha channel is detected or magenta transparency is present

    """
    for color_data_raw in colors.values():
        if isinstance(color_data_raw, dict):
            color_data: dict[str, int] = color_data_raw  # type: ignore[assignment]
            # Check for alpha key or RGBA values
            if 'alpha' in color_data or 'a' in color_data:
                return True
            # Check if we have 4 values (RGBA) instead of 3 (RGB)
            if len(color_data) == RGBA_COMPONENT_COUNT:
                return True
            # Check for magenta transparency (255, 0, 255)
            r_val = int(color_data.get('red', 0) if 'red' in color_data else color_data.get('r', 0))
            g_val = int(
                color_data.get('green', 0) if 'green' in color_data else color_data.get('g', 0),
            )
            b_val = int(
                color_data.get('blue', 0) if 'blue' in color_data else color_data.get('b', 0),
            )
            if r_val == MAX_COLOR_CHANNEL_VALUE and g_val == 0 and b_val == MAX_COLOR_CHANNEL_VALUE:
                return True
    return False


def _detect_alpha_channel_in_animation(animation_data: dict[str, Any] | list[Any]) -> bool:
    """Detect if animation frames contain alpha channel information.

    Args:
        animation_data: Animation configuration data

    Returns:
        bool: True if alpha channel is detected in any frame

    """
    # Handle different animation data structures
    if isinstance(animation_data, dict):
        for frame_data in animation_data.values():
            if (
                isinstance(frame_data, dict)
                and 'colors' in frame_data
                and _detect_alpha_channel(frame_data['colors'])  # type: ignore[arg-type]
            ):
                return True
    elif isinstance(animation_data, list):  # type: ignore[reportUnnecessaryIsInstance]
        # Handle list-based animation data
        for frame_data in animation_data:
            if (
                isinstance(frame_data, dict)
                and 'colors' in frame_data
                and _detect_alpha_channel(frame_data['colors'])  # type: ignore[arg-type]
            ):
                return True
    return False


def convert_sprite_to_alpha_format(sprite_data: dict[str, Any]) -> dict[str, Any]:
    """Convert sprite data to proper alpha format.

    Args:
        sprite_data: Original sprite data

    Returns:
        dict: Converted sprite data with alpha support

    """
    converted_data = sprite_data.copy()

    if sprite_data.get('has_alpha'):
        # Convert colors to RGBA format if needed
        if 'colors' in converted_data:
            converted_data['colors'] = _convert_colors_to_rgba(converted_data['colors'])

        # Convert animation colors if present
        if 'animations' in converted_data:
            converted_data['animations'] = _convert_animation_colors_to_rgba(
                converted_data['animations'],
            )

    return converted_data


def _convert_colors_to_rgba(colors: dict[str, Any]) -> dict[str, Any]:
    """Convert color definitions to RGBA format with magenta transparency.

    Args:
        colors: Original color definitions

    Returns:
        dict: Colors converted to RGBA format

    """
    converted_colors: dict[str, Any] = {}

    for color_key, color_data_raw in colors.items():
        if isinstance(color_data_raw, dict):
            color_data: dict[str, int] = color_data_raw  # type: ignore[assignment]
            # Extract RGB values
            r = int(color_data.get('red', 0) if 'red' in color_data else color_data.get('r', 0))
            g = int(color_data.get('green', 0) if 'green' in color_data else color_data.get('g', 0))
            b = int(color_data.get('blue', 0) if 'blue' in color_data else color_data.get('b', 0))

            # Check for magenta transparency (255, 0, 255) = alpha 0
            if r == MAX_COLOR_CHANNEL_VALUE and g == 0 and b == MAX_COLOR_CHANNEL_VALUE:
                a = 0  # Fully transparent
            else:
                a = int(
                    color_data.get('alpha', 255)
                    if 'alpha' in color_data
                    else color_data.get('a', 255),
                )  # Default to opaque

            converted_colors[color_key] = {'red': r, 'green': g, 'blue': b, 'alpha': a}
        else:
            converted_colors[color_key] = color_data_raw

    return converted_colors


def _convert_animation_colors_to_rgba(animations: dict[str, Any]) -> dict[str, Any]:
    """Convert animation frame colors to RGBA format.

    Args:
        animations: Animation data with color definitions

    Returns:
        dict: Animation data with RGBA colors

    """
    converted_animations: dict[str, Any] = {}

    for frame_name, frame_data in animations.items():
        if isinstance(frame_data, dict) and 'colors' in frame_data:
            converted_animations[frame_name] = frame_data.copy()
            converted_animations[frame_name]['colors'] = _convert_colors_to_rgba(
                frame_data['colors'],  # type: ignore[arg-type]
            )
        else:
            converted_animations[frame_name] = frame_data

    return converted_animations


def parse_toml_sprite_data(config_file: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Parse a TOML sprite config file and extract sprite data.

    Args:
        config_file: Path to the TOML config file.

    Returns:
        Tuple of (config_data, sprite_data) dictionaries.

    """
    import tomllib

    with config_file.open(mode='rb') as f:
        config_data = tomllib.load(f)

    config_data = normalize_toml_data(config_data)

    sprite_data = {
        'name': config_data.get('sprite', {}).get('name', 'Unknown'),
        'format': ai_training_state['format'],
        'sprite_type': 'animated' if 'animation' in config_data else 'static',
        'has_alpha': False,
    }

    if 'sprite' in config_data:
        sprite_data['pixels'] = config_data['sprite'].get('pixels', '')
        sprite_data['colors'] = config_data.get('colors', {})
        sprite_data['has_alpha'] = _detect_alpha_channel(config_data.get('colors', {}))

    if 'animation' in config_data:
        sprite_data['animations'] = config_data['animation']
        sprite_data['has_alpha'] = _detect_alpha_channel_in_animation(config_data['animation'])

    return config_data, sprite_data
