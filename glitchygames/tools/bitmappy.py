#!/usr/bin/env python3
"""Glitchy Games Bitmap Editor."""

from __future__ import annotations

import contextlib
import logging
import multiprocessing
import operator
import signal
import sys
import tempfile
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from queue import Empty
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

import pygame

if TYPE_CHECKING:
    import numpy as np

# Try to import aisuite, but don't fail if it's not available.
# Catch AttributeError too — docstring_parser (an aisuite transitive dependency)
# uses ast.NameConstant which was removed in Python 3.14.
try:
    import aisuite as ai
except (ImportError, AttributeError):
    ai = None  # ty: ignore[invalid-assignment]

# Try to import backoff for retry logic
try:
    import backoff
except ImportError:
    backoff = None  # ty: ignore[invalid-assignment]

# Try to import voice recognition, but don't fail if it's not available
try:
    from glitchygames.events.voice import VoiceEventManager
except ImportError:
    VoiceEventManager = None  # ty: ignore[invalid-assignment]

from http import HTTPStatus

from pydantic import BaseModel

from glitchygames import events
from glitchygames.ai import (
    build_refinement_messages,
    build_sprite_generation_messages,
    get_sprite_size_hint,
    validate_ai_response,
)
from glitchygames.ai import (
    clean_ai_response as ai_clean_response,
)
from glitchygames.color import (
    ALPHA_TRANSPARENCY_THRESHOLD,
    MAX_COLOR_CHANNEL_VALUE,
    MAX_PER_PIXEL_ALPHA,
    RGB_COMPONENT_COUNT,
    RGBA_COMPONENT_COUNT,
)
from glitchygames.engine import GameEngine
from glitchygames.pixels import rgb_triplet_generator
from glitchygames.scenes import Scene
from glitchygames.sprites import (
    SPRITE_GLYPHS,
    BitmappySprite,
    SpriteFactory,
)
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from glitchygames.sprites.constants import DEFAULT_FILE_FORMAT
from glitchygames.ui import (
    ColorWellSprite,
    MenuBar,
    MenuItem,
    MultiLineTextBox,
    SliderSprite,
    TabControlSprite,
    TextSprite,
)
from glitchygames.ui.dialogs import (
    LoadDialogScene,
    NewCanvasDialogScene,
    SaveDialogScene,
)

from .canvas_interfaces import (
    AnimatedCanvasInterface,
    AnimatedCanvasRenderer,
    AnimatedSpriteSerializer,
)
from .controller_mode_system import ControllerMode
from .controller_selection import ControllerSelection
from .film_strip import FilmStripWidget
from .multi_controller_manager import MultiControllerManager
from .operation_history import (
    CanvasOperationTracker,
    CrossAreaOperationTracker,
    FilmStripOperationTracker,
)
from .undo_redo_manager import UndoRedoManager
from .visual_collision_manager import VisualCollisionManager

# Constants
MAGENTA_TRANSPARENT = (255, 0, 255)  # Magenta color used for transparency
TRANSPARENT_GLYPH = '█'  # Block character used for transparent pixels

# Bitmappy-specific constants
LARGE_SPRITE_DIMENSION = 128  # Sprites this size or larger get special handling
MIN_PIXEL_DISPLAY_SIZE = 2  # Minimum pixel display size for large sprites
MODEL_DOWNLOAD_TIME_THRESHOLD_SECONDS = 60  # AI model response time threshold
PIXEL_CHANGE_DEBOUNCE_SECONDS = 0.1  # Debounce timer for auto-submit
SPRITE_ASPECT_RATIO_TOLERANCE = 0.2  # Tolerance for AI training aspect ratio matching
COLOR_QUANTIZATION_GROUP_DISTANCE_THRESHOLD = 1000  # Squared Euclidean distance for color grouping
DEBUG_LOG_FIRST_N_PIXELS = 5  # How many non-magenta pixels to log for debugging
MIN_FILM_STRIPS_FOR_PANEL_POSITIONING = 2  # Minimum film strips before AI panel positioning
MAX_COLORS_FOR_AI_TRAINING = 64  # Max unique colors before quantization
PROGRESS_LOG_MIN_HEIGHT = 32  # Minimum image height to trigger progress logging
CONTROLLER_ACCEL_LEVEL1_TIME = 0.8  # Acceleration timing thresholds
CONTROLLER_ACCEL_LEVEL2_TIME = 1.5
CONTROLLER_ACCEL_LEVEL3_TIME = 2.5
CONTROLLER_ACCEL_JUMP_LEVEL1 = 2  # Pixel jump sizes at acceleration levels
CONTROLLER_ACCEL_JUMP_LEVEL2 = 4
CONTROLLER_ACCEL_JUMP_LEVEL3 = 8
HAT_INPUT_MAGNITUDE_THRESHOLD = 0.5  # Joystick hat dead zone
AI_TRAINING_SINGLE_FRAME_EXAMPLE_COUNT = 2  # Threshold for single-frame sprite shortcut
JOYSTICK_LEFT_SHOULDER_BUTTON = 9  # Joystick button mapping for left shoulder
JOYSTICK_HAT_RIGHT = 2  # Joystick hat bitmask for right direction
JOYSTICK_HAT_DOWN = 4  # Joystick hat bitmask for down direction
JOYSTICK_HAT_LEFT = 8  # Joystick hat bitmask for left direction
MIN_COLOR_FIELD_VALUES_FOR_GREEN = 2  # Minimum parsed color field values for green
MIN_COLOR_FIELD_VALUES_FOR_BLUE = 3  # Minimum parsed color field values for blue
AI_CAPABILITY_RESPONSE_FIELD_COUNT = 2  # Expected field count for AI capability response
AI_VALIDATION_MAX_RETRIES = 2  # Maximum retries for AI response validation

if TYPE_CHECKING:
    import argparse
    from collections.abc import Callable

    from glitchygames.tools.ascii_renderer import ASCIIRenderer
    from glitchygames.tools.visual_collision_manager import VisualIndicator

LOG = logging.getLogger('game.tools.bitmappy')


class MockEvent(BaseModel):
    """Lightweight mock event for internal file-loading calls."""

    text: str


# Turn on sprite debugging
BitmappySprite.DEBUG = True
MAX_PIXELS_ACROSS = 64
MIN_PIXELS_ACROSS = 1
MAX_PIXELS_TALL = 64
MIN_PIXELS_TALL = 1
MIN_COLOR_VALUE = 0
MAX_COLOR_VALUE = 255


def detect_file_format(filename: str) -> str:
    """Detect file format from filename extension.

    Note: Only TOML format is currently supported.

    Args:
        filename: The filename to analyze

    Returns:
        The detected format string (currently only "toml")

    Raises:
        ValueError: If the file extension is not a supported format

    """
    extension = Path(filename).suffix.lower().lstrip('.')
    if extension in {'toml', ''}:
        return 'toml'
    msg = f'Unsupported file format: .{extension} (only TOML is supported)'
    raise ValueError(msg)


def resource_path(*path_segments: str) -> Path:
    """Return the absolute Path to a resource.

    Args:
        *path_segments: Path segments to join

    Returns:
        Path: Absolute path to the resource

    """
    if hasattr(sys, '_MEIPASS'):
        # Running in PyInstaller bundle — _MEIPASS is set by PyInstaller at runtime
        base_path = Path(sys._MEIPASS)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportAttributeAccessIssue]
        # Note: We used --add-data "...:glitchygames/assets", so we must include
        # glitchygames/assets in the final path segments, e.g.:
        return base_path.joinpath(*path_segments)
    # Running in normal Python environment
    return Path(__file__).parent.parent.joinpath(*path_segments[1:])


AI_MODEL: str = 'anthropic:claude-sonnet-4-5'
# AI_MODEL = "ollama:gpt-oss:20b"
# AI_MODEL = "ollama:mistral-nemo:12b"
AI_TIMEOUT = 600  # Seconds to wait for AI response (10 minutes for ollama models)
AI_QUEUE_SIZE = 10
AI_MAX_CONTEXT_SIZE = 65536  # Total context window size
AI_MAX_INPUT_TOKENS = 8192  # Maximum tokens for INPUT (prompts, examples)
AI_MAX_OUTPUT_TOKENS = 64000  # Maximum tokens for OUTPUT (AI response, large sprites)
AI_MAX_TRAINING_EXAMPLES = 1000  # Allow many more training examples for full context

# Retry configuration for AI requests
AI_MAX_RETRIES = 5  # Maximum number of retry attempts
AI_BASE_DELAY = 1.0  # Base delay in seconds for exponential backoff
AI_MAX_DELAY = 60.0  # Maximum delay between retries

# Model download timeout (much longer for initial model download)
AI_MODEL_DOWNLOAD_TIMEOUT = 1800  # 30 minutes for model download
# Load sprite files for AI training using SpriteFactory
ai_training_state: dict[str, list[dict[str, Any]] | str | None] = {
    'data': [],
    'format': None,  # Will be detected from training files
}

# Load sprite configuration files for AI training
SPRITE_CONFIG_DIR = resource_path('glitchygames', 'examples', 'resources', 'sprites')


def _alpha_blend_pixel(
    source: tuple[int, ...], destination: tuple[int, ...], additional_alpha: float
) -> tuple[int, int, int, int] | None:
    """Alpha-blend a single source pixel over a destination pixel.

    Args:
        source: Source pixel as RGB or RGBA tuple.
        destination: Destination pixel as RGBA tuple.
        additional_alpha: Additional alpha multiplier (0.0-1.0).

    Returns:
        Blended RGBA tuple, or None if the source pixel should be skipped.

    """
    if len(source) == RGBA_COMPONENT_COUNT:
        src_r, src_g, src_b, src_a = source
    else:
        src_r, src_g, src_b = source
        src_a = 255

    # Skip magenta transparency color (255, 0, 255)
    if src_r == MAX_COLOR_CHANNEL_VALUE and src_g == 0 and src_b == MAX_COLOR_CHANNEL_VALUE:
        return None

    # Apply additional alpha reduction
    src_a = int(src_a * additional_alpha)

    # Skip fully transparent pixels
    if src_a == 0:
        return None

    dst_r, dst_g, dst_b, dst_a = destination

    # Standard alpha compositing using "over" operation
    src_alpha_norm = src_a / 255.0
    dst_alpha_norm = dst_a / 255.0
    out_alpha_norm = src_alpha_norm + dst_alpha_norm * (1.0 - src_alpha_norm)

    if out_alpha_norm > 0:
        inv_src = 1.0 - src_alpha_norm
        out_r = int((src_r * src_alpha_norm + dst_r * dst_alpha_norm * inv_src) / out_alpha_norm)
        out_g = int((src_g * src_alpha_norm + dst_g * dst_alpha_norm * inv_src) / out_alpha_norm)
        out_b = int((src_b * src_alpha_norm + dst_b * dst_alpha_norm * inv_src) / out_alpha_norm)
        return (out_r, out_g, out_b, int(out_alpha_norm * 255))

    return (0, 0, 0, 0)


def _composite_frames_with_alpha(  # pyright: ignore[reportUnusedFunction]
    frames: list[SpriteFrame], additional_alpha: float = 0.5
) -> list[tuple[int, ...]]:
    """Composite multiple frames together with additional alpha transparency.

    Args:
        frames: List of SpriteFrame objects to composite
        additional_alpha: Additional alpha multiplier (0.0-1.0). Default 0.5 for 50% transparency.

    Returns:
        List of RGBA tuples representing the composited frame pixels

    """
    if not frames:
        return []

    # Get dimensions from first frame
    width, height = frames[0].get_size()
    pixel_count = width * height

    # Initialize composite with transparent background
    composite = [(0, 0, 0, 0) for _ in range(pixel_count)]

    # Composite each frame on top with additional alpha
    for frame in frames:
        frame_pixels = frame.get_pixel_data()

        for i in range(min(len(frame_pixels), pixel_count)):
            blended = _alpha_blend_pixel(frame_pixels[i], composite[i], additional_alpha)
            if blended is not None:
                composite[i] = blended

    return composite  # ty: ignore[invalid-return-type]


def _create_composite_frame_from_pixels(  # type: ignore[reportUnusedFunction]
    pixels: list[tuple[int, ...]], width: int, height: int, duration: float = 0.5
) -> SpriteFrame:
    """Create a SpriteFrame from composited pixel data.

    Args:
        pixels: List of RGBA tuples
        width: Frame width
        height: Frame height
        duration: Frame duration

    Returns:
        SpriteFrame object with the composited pixels

    """
    # Create surface
    surface = pygame.Surface((width, height), pygame.SRCALPHA)

    # Fill with pixels
    for i, pixel in enumerate(pixels):
        x = i % width
        y = i // width
        if y < height:
            surface.set_at((x, y), pixel)

    # Create frame
    frame = SpriteFrame(surface, duration)
    frame.pixels = pixels
    return frame


def _get_visible_width(text: str) -> int:
    """Get the visible width of text, excluding ANSI escape sequences.

    Args:
        text: Text possibly containing ANSI color codes

    Returns:
        int: Visible character count

    """
    import re

    # Remove ANSI escape sequences (color codes, etc.)
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    return len(ansi_escape.sub('', text))


def _render_frames_side_by_side(
    frames: list[SpriteFrame], renderer: ASCIIRenderer, separator: str = '  '
) -> str:
    """Render multiple frames side-by-side as ASCII art, wrapping to screen width.

    Args:
        frames: List of SpriteFrame objects to render
        renderer: ASCIIRenderer instance
        separator: String to place between frames (default: two spaces)

    Returns:
        str: ASCII representation with frames arranged horizontally, wrapping at screen width

    """
    if not frames:
        return ''

    import shutil

    # Get terminal width
    terminal_width = shutil.get_terminal_size().columns

    # Render each frame to ASCII
    frame_outputs: list[list[str]] = []
    for frame in frames:
        ascii_output = _render_frame_to_ascii(frame, renderer)
        if ascii_output:
            frame_outputs.append(ascii_output.split('\n'))
        else:
            # If rendering failed, use empty placeholder
            width, height = frame.get_size()
            frame_outputs.append([' ' * width] * height)  # ty: ignore[invalid-argument-type]

    if not frame_outputs:
        return ''

    # Calculate frame width (visible characters only, excluding ANSI codes)
    frame_width = _get_visible_width(frame_outputs[0][0]) if frame_outputs[0] else 0
    separator_width = len(separator)

    # Calculate how many frames fit per row
    frames_per_row = max(1, (terminal_width + separator_width) // (frame_width + separator_width))

    # Split frames into rows
    frame_rows = [
        frame_outputs[i : i + frames_per_row] for i in range(0, len(frame_outputs), frames_per_row)
    ]

    # Render each row and combine vertically
    all_rows: list[str] = []
    for row_frames in frame_rows:
        # Find the maximum number of lines in this row
        max_lines = max(len(lines) for lines in row_frames)

        # Pad frames in this row to have the same number of lines
        for lines in row_frames:
            if lines and len(lines) < max_lines:
                # Get visible width from first line (excluding ANSI codes)
                width = _get_visible_width(lines[0]) if lines else 0
                # Pad with empty lines
                lines.extend([' ' * width] * (max_lines - len(lines)))

        # Combine frames in this row horizontally
        row_lines: list[str] = []
        for line_idx in range(max_lines):
            line_parts: list[str] = []
            for frame_lines in row_frames:
                if line_idx < len(frame_lines):
                    line_parts.append(frame_lines[line_idx])
                else:
                    line_parts.append('')
            row_lines.append(separator.join(line_parts))

        # Add this row to all rows
        all_rows.append('\n'.join(row_lines))

    # Combine all rows vertically with a blank line separator
    return '\n\n'.join(all_rows)


def _build_color_to_glyph_map(pixels: list[tuple[int, ...]]) -> dict[tuple[int, ...], str]:
    """Map unique RGB colors in pixel data to glyph characters.

    Args:
        pixels: List of pixel tuples (RGB or RGBA).

    Returns:
        Dictionary mapping RGB tuples to glyph characters.

    """
    from glitchygames.sprites import SPRITE_GLYPHS

    unique_colors: dict[tuple[int, ...], str] = {}
    char_index = 0
    for pixel in pixels:
        rgb = pixel[:3] if len(pixel) == RGBA_COMPONENT_COUNT else pixel
        if rgb not in unique_colors:
            unique_colors[rgb] = SPRITE_GLYPHS[char_index % len(SPRITE_GLYPHS)]
            char_index += 1

    if unique_colors:
        LOG.debug(f'_render_frame_to_ascii: Found {len(unique_colors)} unique colors')
        LOG.debug(
            f'_render_frame_to_ascii: First unique color: {next(iter(unique_colors.keys()))} ->'
            f" '{next(iter(unique_colors.values()))}'"
        )

    return unique_colors


def _build_ascii_grid(
    pixels: list[tuple[int, ...]], width: int, height: int, color_map: dict[tuple[int, ...], str]
) -> str:
    """Build an ASCII grid string from pixel data and a color-to-glyph map.

    Args:
        pixels: List of pixel tuples (RGB or RGBA).
        width: Frame width in pixels.
        height: Frame height in pixels.
        color_map: Dictionary mapping RGB tuples to glyph characters.

    Returns:
        Multiline string of glyph characters.

    """
    pixel_lines: list[str] = []
    for y in range(height):
        line: list[str] = []
        for x in range(width):
            idx = y * width + x
            if idx < len(pixels):
                pixel = pixels[idx]
                rgb = pixel[:3] if len(pixel) == RGBA_COMPONENT_COUNT else pixel
                line.append(color_map.get(rgb, ' '))
        pixel_lines.append(''.join(line))
    return '\n'.join(pixel_lines)


def _build_renderer_color_dict(
    pixels: list[tuple[int, ...]], color_map: dict[tuple[int, ...], str]
) -> dict[str, tuple[int, ...]]:
    """Build an RGBA color dictionary for the ASCII renderer.

    Args:
        pixels: List of pixel tuples (RGB or RGBA).
        color_map: Dictionary mapping RGB tuples to glyph characters.

    Returns:
        Dictionary mapping glyph characters to RGBA tuples.

    """
    colors_dict: dict[str, tuple[int, ...]] = {}
    for rgb, char in color_map.items():
        # Find the alpha value from the first pixel matching this RGB
        alpha = 255
        for pixel in pixels:
            if len(pixel) == RGBA_COMPONENT_COUNT and pixel[:3] == rgb:
                alpha = pixel[3]
                break

        # Special handling: magenta (255, 0, 255) should render as white blocks
        if rgb == (255, 0, 255):
            colors_dict[char] = (255, 255, 255, alpha)
        else:
            colors_dict[char] = (rgb[0], rgb[1], rgb[2], alpha)
    return colors_dict


def _render_frame_to_ascii(frame: SpriteFrame, renderer: ASCIIRenderer) -> str:
    """Render a sprite frame to ASCII art.

    Args:
        frame: SpriteFrame object to render
        renderer: ASCIIRenderer instance

    Returns:
        str: ASCII representation of the frame, or empty string on error

    """
    try:
        pixels = frame.get_pixel_data()
        if not pixels:
            return ''

        width, height = frame.get_size()
        color_map = _build_color_to_glyph_map(pixels)
        pixels_str = _build_ascii_grid(pixels, width, height, color_map)
        colors_dict = _build_renderer_color_dict(pixels, color_map)

        try:
            return renderer.colorize_pixels(pixels_str, colors_dict)  # type: ignore[arg-type]
        except (AttributeError, KeyError, TypeError) as e:
            LOG.debug(f'Error colorizing pixels: {e}')
            return pixels_str

    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as e:
        LOG.debug(f'Error rendering frame to ASCII: {e}')
        return ''


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
                color_data.get('green', 0) if 'green' in color_data else color_data.get('g', 0)
            )
            b_val = int(
                color_data.get('blue', 0) if 'blue' in color_data else color_data.get('b', 0)
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


def _convert_sprite_to_alpha_format(sprite_data: dict[str, Any]) -> dict[str, Any]:
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
                converted_data['animations']
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
                    else color_data.get('a', 255)
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
                frame_data['colors']  # type: ignore[arg-type]
            )
        else:
            converted_animations[frame_name] = frame_data

    return converted_animations


def _parse_toml_sprite_data(config_file: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Parse a TOML sprite config file and extract sprite data.

    Args:
        config_file: Path to the TOML config file.

    Returns:
        Tuple of (config_data, sprite_data) dictionaries.

    """
    import tomllib

    with config_file.open(mode='rb') as f:
        config_data = tomllib.load(f)

    config_data = _normalize_toml_data(config_data)

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


def _sprite_has_per_pixel_alpha(sprite: AnimatedSprite | object) -> bool:
    """Check if an animated sprite has any non-opaque alpha pixels.

    Args:
        sprite: An AnimatedSprite object with _animations attribute.

    Returns:
        True if any pixel has alpha != 255.

    """
    if not hasattr(sprite, '_animations'):
        return False

    for frames in sprite._animations.values():  # type: ignore[union-attr]
        for frame in frames:  # type: ignore[reportUnknownVariableType]
            for pixel in frame.get_pixel_data():  # type: ignore[reportUnknownMemberType]
                if len(pixel) == RGBA_COMPONENT_COUNT and pixel[3] != MAX_COLOR_CHANNEL_VALUE:  # type: ignore[reportUnknownArgumentType]
                    return True
    return False


def _pixels_have_alpha(pixels: list[tuple[int, ...]]) -> bool:
    """Check if any pixels in a list have non-opaque alpha.

    Args:
        pixels: List of pixel tuples (RGB or RGBA).

    Returns:
        True if any pixel has alpha != 255.

    """
    for pixel in pixels:
        if len(pixel) == RGBA_COMPONENT_COUNT and pixel[3] != MAX_COLOR_CHANNEL_VALUE:
            return True
    return False


def _render_static_sprite_ascii(
    sprite: AnimatedSprite | BitmappySprite, renderer: ASCIIRenderer
) -> None:
    """Render ASCII output for a single-frame (static) sprite.

    Args:
        sprite: An AnimatedSprite with _animations.
        renderer: The ASCII renderer to use.

    """
    try:
        first_anim = next(iter(sprite._animations.values()))  # type: ignore[union-attr]
        first_frame = first_anim[0] if first_anim else None
        if first_frame:
            ascii_output = _render_frame_to_ascii(first_frame, renderer)
            if ascii_output:
                LOG.info(ascii_output)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as e:
        LOG.debug(f'Failed to render ASCII for single-frame sprite: {e}')


def _render_animated_sprite_ascii(
    sprite: AnimatedSprite | BitmappySprite, renderer: ASCIIRenderer
) -> None:
    """Render ASCII output for all animation frames side-by-side.

    Args:
        sprite: An AnimatedSprite with _animations.
        renderer: The ASCII renderer to use.

    """
    try:
        for anim_name, frames in sprite._animations.items():  # type: ignore[union-attr]
            if frames:
                LOG.info('  Animation: "%s" (%d frames)', anim_name, len(frames))  # type: ignore[arg-type]
                ascii_output = _render_frames_side_by_side(frames, renderer)  # type: ignore[arg-type]
                if ascii_output:
                    LOG.info(ascii_output)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError) as e:
        LOG.debug(f'Failed to render frames side-by-side: {e}')


def _get_sprite_color_count(sprite: AnimatedSprite | BitmappySprite) -> int:
    """Get the number of colors in a sprite's color map.

    Args:
        sprite: A sprite object.

    Returns:
        Number of colors.

    """
    if hasattr(sprite, 'color_map'):
        return len(sprite.color_map)  # type: ignore[union-attr]
    if hasattr(sprite, '_color_map'):
        return len(sprite._color_map)  # type: ignore[reportPrivateUsage]
    return 0


def _get_sprite_alpha_type(sprite: AnimatedSprite | BitmappySprite) -> str:
    """Determine the alpha type of a sprite (indexed or per-pixel).

    Args:
        sprite: A sprite object.

    Returns:
        Either "indexed" or "per-pixel".

    """
    if not hasattr(sprite, 'color_map'):
        return 'indexed'

    for color_value in sprite.color_map.values():  # type: ignore[union-attr]
        if isinstance(color_value, (list, tuple)) and len(color_value) >= RGBA_COMPONENT_COUNT:  # type: ignore[arg-type]
            alpha = color_value[3]  # type: ignore[index]
            if isinstance(alpha, (int, float)) and 0 <= alpha <= MAX_PER_PIXEL_ALPHA:
                return 'per-pixel'
    return 'indexed'


def _calculate_animation_duration(
    sprite: AnimatedSprite | BitmappySprite, sprite_type: str
) -> tuple[float, bool]:
    """Calculate total animation duration and loop status.

    Args:
        sprite: A sprite object.
        sprite_type: Either "static" or "animated".

    Returns:
        Tuple of (total_duration, is_looped).

    """
    total_duration = 0.0
    is_looped = False
    if sprite_type != 'animated' or not hasattr(sprite, '_animations'):
        return total_duration, is_looped

    for frames in sprite._animations.values():  # type: ignore[union-attr]
        if hasattr(sprite, 'is_looping') and sprite.is_looping:  # type: ignore[union-attr]
            is_looped = True
        for frame in frames:  # type: ignore[union-attr]
            total_duration += frame.duration if hasattr(frame, 'duration') else 0.5  # type: ignore[union-attr]

    return total_duration, is_looped  # type: ignore[return-value]


def _format_duration_string(sprite_type: str, total_duration: float, *, is_looped: bool) -> str:
    """Format a human-readable duration string.

    Args:
        sprite_type: Either "static" or "animated".
        total_duration: Total duration in seconds.
        is_looped: Whether the animation loops.

    Returns:
        Formatted duration string.

    """
    if sprite_type == 'static':
        return '∞'
    if is_looped:
        return f'{total_duration:.1f}s (∞)'
    if total_duration > 0:
        return f'{total_duration:.1f}s (1 time)'
    return '∞'


def _log_colorized_sprite_output(
    config_file: Path,
    config_data: dict[str, Any],
    sprite: AnimatedSprite | BitmappySprite,
    renderer: ASCIIRenderer,
) -> None:
    """Generate and log colorized ASCII output for a loaded sprite.

    Args:
        config_file: Path to the config file.
        config_data: Parsed TOML config data.
        sprite: The loaded sprite object.
        renderer: The ASCII renderer to use.

    """
    sprite_name = getattr(sprite, 'name', 'Unknown')

    if isinstance(sprite, AnimatedSprite):
        has_alpha = _sprite_has_per_pixel_alpha(sprite)
        is_static = sprite.is_static_sprite()
        frame_count = sprite.get_total_frame_count()
        animation_count = len(sprite._animations) if hasattr(sprite, '_animations') else 0  # type: ignore[reportPrivateUsage]

        if is_static:
            LOG.info(
                f'Loaded "{sprite_name}" (filename: {config_file.name}, type:'
                f' single-frame, per-pixel alpha: {has_alpha})'
            )
            _render_static_sprite_ascii(sprite, renderer)
        else:
            LOG.info(
                f'Loaded "{sprite_name}" (filename: {config_file.name}, type:'
                f' animated, animations: {animation_count}, per-pixel alpha:'
                f' {has_alpha})'
            )
            _render_animated_sprite_ascii(sprite, renderer)
    else:
        frame_count = 1
        has_alpha = _pixels_have_alpha(sprite.pixels) if hasattr(sprite, 'pixels') else False
        LOG.info(
            f'Loaded "{sprite_name}" (filename: {config_file.name}, type:'
            f' single-frame, per-pixel alpha: {has_alpha})'
        )

    sprite_type = 'animated' if isinstance(sprite, AnimatedSprite) else 'static'
    color_count = _get_sprite_color_count(sprite)
    alpha_type = _get_sprite_alpha_type(sprite)
    total_duration, is_looped = _calculate_animation_duration(sprite, sprite_type)
    duration_str = _format_duration_string(sprite_type, total_duration, is_looped=is_looped)

    colorized_output = renderer.render_sprite(config_data)
    LOG.debug(
        f'Generated colorized output for {config_file.name}: {len(colorized_output)} characters'
    )
    LOG.debug(f'\n🎨 Colorized ASCII Output for {config_file.name}:')
    LOG.debug(
        f'   Type: {sprite_type}, Frames: {frame_count}, Colors: {color_count},'
        f' Alpha: {alpha_type}, Duration: {duration_str}'
    )
    LOG.debug(colorized_output)
    LOG.debug(f'Successfully printed colorized output for {config_file.name}')


def _process_config_file(config_file: Path, training_data: list[dict[str, Any]]) -> None:
    """Process a single sprite config file and add it to training data.

    Args:
        config_file: Path to the config file.
        training_data: List to append training data to.

    """
    LOG.debug(f'Processing config file: {config_file}')
    try:
        if ai_training_state['format'] != 'toml':
            LOG.warning(f"Unsupported format '{ai_training_state['format']}' for {config_file}")
            return

        config_data, sprite_data = _parse_toml_sprite_data(config_file)
        converted_sprite_data = _convert_sprite_to_alpha_format(sprite_data)
        training_data.append(converted_sprite_data)

        try:
            from glitchygames.tools.ascii_renderer import ASCIIRenderer

            renderer = ASCIIRenderer()
            sprite = SpriteFactory.load_sprite(filename=str(config_file))
            _log_colorized_sprite_output(config_file, config_data, sprite, renderer)
        except (AttributeError, KeyError, TypeError, ValueError) as e:
            LOG.warning(f'Could not create colorized output for {config_file.name}: {e}')
            import traceback

            LOG.warning(f'Traceback: {traceback.format_exc()}')

    except (FileNotFoundError, PermissionError, ValueError, KeyError) as e:
        LOG.warning(f'Error loading sprite config {config_file}: {e}')


def load_ai_training_data() -> None:
    """Load AI training data from sprite config files.

    Raises:
        TypeError: If ai_training_state['data'] is not a list.

    """
    training_data = ai_training_state['data']
    if not isinstance(training_data, list):
        msg = "ai_training_state['data'] must be a list"
        raise TypeError(msg)

    LOG.info(f'Loading AI training data from: {SPRITE_CONFIG_DIR}')
    LOG.debug(f'Sprite config directory exists: {SPRITE_CONFIG_DIR.exists()}')

    if not SPRITE_CONFIG_DIR.exists():
        LOG.warning(f'Sprite config directory not found: {SPRITE_CONFIG_DIR}')
        LOG.info(f'Total AI training data loaded: {len(training_data)} sprites')
        return

    toml_files = list(SPRITE_CONFIG_DIR.glob('*.toml'))

    if toml_files:
        config_files = toml_files
        ai_training_state['format'] = 'toml'
        LOG.info(f'Found {len(config_files)} TOML sprite config files')
    else:
        config_files = []
        LOG.warning('No sprite config files found')

    for config_file in config_files:
        _process_config_file(config_file, training_data)

    LOG.info(f'Total AI training data loaded: {len(training_data)} sprites')


class GGUnhandledMenuItemError(Exception):
    """Glitchy Games Unhandled Menu Item Error."""


class BitmapPixelSprite(BitmappySprite):
    """Bitmap Pixel Sprite."""

    log = LOG
    PIXEL_CACHE: ClassVar[dict[tuple[tuple[int, ...], int], pygame.Surface]] = {}

    def __init__(
        self: Self,
        x: int = 0,
        y: int = 0,
        width: int = 1,
        height: int = 1,
        name: str | None = None,
        pixel_number: int = 0,
        border_thickness: int = 1,
        groups: pygame.sprite.LayeredDirty | None = None,  # type: ignore[type-arg]
    ) -> None:
        """Initialize the Bitmap Pixel Sprite."""
        super().__init__(x=x, y=y, width=width, height=height, name=name, groups=groups)  # type: ignore[arg-type]

        self.pixel_number = pixel_number
        self.pixel_width = width
        self.pixel_height = height
        self.border_thickness = border_thickness
        self.color = (96, 96, 96)
        self.pixel_color = (0, 0, 0, 255)
        self.x = x
        self.y = y

        self.rect = pygame.draw.rect(
            self.image, self.color, (self.x, self.y, self.width, self.height), self.border_thickness
        )

    @property
    def pixel_color(self: Self) -> tuple[int, int, int, int]:
        """Get the pixel color.

        Args:
            None

        Returns:
            tuple[int, int, int, int]: The pixel color with alpha.

        Raises:
            None

        """
        return self._pixel_color  # ty: ignore[invalid-return-type]

    @pixel_color.setter
    def pixel_color(
        self: Self, new_pixel_color: tuple[int, int, int] | tuple[int, int, int, int]
    ) -> None:
        """Set the pixel color.

        Args:
            new_pixel_color (tuple): The new pixel color (RGB or RGBA).

        Raises:
            None

        """
        # Convert RGB to RGBA if needed
        if len(new_pixel_color) == RGB_COMPONENT_COUNT:
            self._pixel_color = (new_pixel_color[0], new_pixel_color[1], new_pixel_color[2], 255)
        else:
            self._pixel_color = new_pixel_color
        self.dirty = 1

    @override
    def update(self: Self) -> None:
        """Update the sprite.

        Args:
            None

        Raises:
            None

        """
        cache_key = (self.pixel_color, self.border_thickness)
        cached_image = BitmapPixelSprite.PIXEL_CACHE.get(cache_key)

        if not cached_image:
            self.image = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            self.image.fill((0, 0, 0, 0))  # Start with transparent

            # Draw main pixel
            pygame.draw.rect(self.image, self.pixel_color, (0, 0, self.width, self.height))

            # Draw border if needed
            if self.border_thickness:
                pygame.draw.rect(
                    self.image, self.color, (0, 0, self.width, self.height), self.border_thickness
                )

            # Convert surface for better performance
            self.image = self.image.convert_alpha()
            BitmapPixelSprite.PIXEL_CACHE[cache_key] = self.image
        else:
            self.image = cached_image  # No need to copy since we converted the surface

        self.rect = self.image.get_rect(x=self.rect.x, y=self.rect.y)

    def on_pixel_update_event(self: Self, event: events.HashableEvent) -> None:
        """Handle the pixel update event.

        Args:
            event (pygame.event.Event): The pygame event.

        Raises:
            None

        """
        if self.callbacks:
            callback = self.callbacks.get('on_pixel_update_event', None)

            if callback:
                callback(event=event, trigger=self)

    @override
    def on_left_mouse_button_down_event(self: Self, event: events.HashableEvent) -> None:
        """Handle the left mouse button down event.

        Args:
            event (pygame.event.Event): The pygame event.

        Raises:
            None

        """
        self.dirty = 1
        self.on_pixel_update_event(event)


@dataclass
class AIRequest:
    """Data structure for AI requests."""

    prompt: str
    request_id: str
    messages: list[dict[str, str]]


@dataclass
class AIResponse:
    """Data structure for AI responses."""

    content: str | None
    error: str | None = None


@dataclass
class AIRequestState:
    """Tracks state of an AI request including retries."""

    original_prompt: str
    retry_count: int = 0
    last_error: str | None = None
    training_examples: list[dict[str, Any]] | None = None
    conversation_history: list[dict[str, str]] | None = None  # For multi-turn refinement
    last_sprite_content: str | None = None  # Last successfully generated sprite


def _setup_ai_worker_logging() -> logging.Logger:
    """Set up logging for AI worker process.

    Returns:
        logging.Logger: The result.

    """
    log = logging.getLogger('game.ai')

    if not log.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        log.addHandler(handler)

    log.info('AI worker process initializing...')
    log.debug(f'AI_MODEL: {AI_MODEL}')
    log.debug(f'AI_TIMEOUT: {AI_TIMEOUT}')
    return log


def _create_ollama_config(log: logging.Logger) -> dict[str, Any]:
    """Create ollama-specific configuration with appropriate timeouts.

    Returns:
        dict: The result.

    """
    if not AI_MODEL.startswith('ollama:'):
        return {}

    # Check if model is already downloaded to choose appropriate timeout
    model_status = _check_ollama_model_status(log)
    if model_status['downloaded']:
        timeout_value = AI_TIMEOUT  # Use normal timeout for downloaded models
        log.info(f'Model already downloaded, using {timeout_value}s timeout')
    else:
        timeout_value = AI_MODEL_DOWNLOAD_TIMEOUT  # Use longer timeout for download
        log.info(f'Model needs download, using {timeout_value}s timeout (30 minutes)')

    # Create ollama-specific configuration
    config = {
        'ollama': {
            'timeout': timeout_value,
            'request_timeout': timeout_value,
            'read_timeout': timeout_value,
        }
    }

    log.info(f'Created ollama config with {timeout_value}s timeout')
    return config


def _set_ollama_env_timeout(log: logging.Logger) -> None:
    """Set the OLLAMA_TIMEOUT environment variable based on model download status.

    Args:
        log: Logger instance.

    """
    import os

    if not AI_MODEL.startswith('ollama:'):
        return

    model_status = _check_ollama_model_status(log)
    if model_status['downloaded']:
        ollama_timeout = AI_TIMEOUT
        log.info(f'Model already downloaded, using {ollama_timeout}s timeout')
    else:
        ollama_timeout = AI_MODEL_DOWNLOAD_TIMEOUT
        log.info(f'Model needs download, using {ollama_timeout}s timeout (30 minutes)')

    os.environ['OLLAMA_TIMEOUT'] = str(ollama_timeout)
    log.info(f'Set OLLAMA_TIMEOUT environment variable to {ollama_timeout} seconds')


def _configure_ollama_provider(log: logging.Logger, client: Any) -> None:
    """Apply ollama-specific timeout configuration to the client's providers.

    Args:
        log: Logger instance.
        client: The AI client.

    """
    if not AI_MODEL.startswith('ollama:') or not hasattr(client, '_providers'):
        return

    log.info('Applying additional ollama-specific configuration...')
    timeout_value = AI_MODEL_DOWNLOAD_TIMEOUT

    for provider_name, provider in client._providers.items():
        if 'ollama' not in provider_name.lower():
            continue

        log.info(f'Configuring ollama provider: {provider_name}')

        if hasattr(provider, 'timeout'):
            provider.timeout = timeout_value
            log.info(f'Set ollama provider timeout to {timeout_value}s')

        if hasattr(provider, 'client') and hasattr(provider.client, 'timeout'):
            provider.client.timeout = timeout_value
            log.info(f'Set ollama HTTP client timeout to {timeout_value}s')

        if hasattr(provider, 'client'):
            for timeout_attr in ['request_timeout', 'read_timeout', 'connect_timeout']:
                if hasattr(provider.client, timeout_attr):
                    setattr(provider.client, timeout_attr, timeout_value)
                    log.info(f'Set ollama {timeout_attr} to {timeout_value}s')


def _get_provider_timeout_value(log: logging.Logger) -> int:
    """Get the appropriate timeout value based on model status.

    Args:
        log: Logger instance.

    Returns:
        The timeout value in seconds.

    """
    if AI_MODEL.startswith('ollama:'):
        model_status = _check_ollama_model_status(log)
        if not model_status['downloaded']:
            return AI_MODEL_DOWNLOAD_TIMEOUT
    return AI_TIMEOUT


def _configure_provider_client_timeout(
    log: logging.Logger, provider_name: str, provider: Any, timeout_value: int
) -> None:
    """Configure timeout on a provider's client and underlying HTTP client.

    Args:
        log: Logger instance.
        provider_name: Name of the provider.
        provider: The provider object.
        timeout_value: Timeout value in seconds.

    """
    if not hasattr(provider, 'client'):
        return

    log.debug(f'Provider client: {type(provider.client)}')
    log.debug(f'Provider client attributes: {dir(provider.client)}')

    if hasattr(provider.client, 'timeout'):
        old_timeout = getattr(provider.client, 'timeout', 'unknown')
        provider.client.timeout = timeout_value
        log.info(f'Set {timeout_value}s timeout for {provider_name} provider (was: {old_timeout})')
    elif hasattr(provider.client, '_client') and hasattr(provider.client._client, 'timeout'):
        old_timeout = getattr(provider.client._client, 'timeout', 'unknown')
        provider.client._client.timeout = timeout_value
        log.info(
            f'Set {timeout_value}s timeout for {provider_name} provider HTTP'
            f' client (was: {old_timeout})'
        )

    # Additional timeout configurations for ollama
    if AI_MODEL.startswith('ollama:'):
        for attr_name in ['request_timeout', 'read_timeout']:
            if hasattr(provider.client, attr_name):
                old_timeout = getattr(provider.client, attr_name, 'unknown')
                setattr(provider.client, attr_name, AI_TIMEOUT)
                log.info(f'Set {attr_name} for {provider_name} provider (was: {old_timeout})')


def _configure_client_timeouts(log: logging.Logger, client: Any) -> None:
    """Configure timeouts on all providers in the AI client.

    Args:
        log: Logger instance.
        client: The AI client.

    """
    try:
        log.debug(f'Client type: {type(client)}')
        log.debug(f'Client attributes: {dir(client)}')

        if not hasattr(client, '_providers'):
            log.warning('Client does not have _providers attribute')
            log.info(f'AI client initialized successfully with {AI_TIMEOUT}s timeout')
            return

        timeout_value = _get_provider_timeout_value(log)
        log.debug(f'Found {len(client._providers)} providers')

        for provider_name, provider in client._providers.items():
            log.debug(f'Provider {provider_name}: {type(provider)}')
            log.debug(f'Provider attributes: {dir(provider)}')
            _configure_provider_client_timeout(log, provider_name, provider, timeout_value)

        log.info(f'AI client initialized successfully with {AI_TIMEOUT}s timeout')
    except Exception as e:
        log.warning(f'Could not configure timeout: {e}')
        log.exception('Timeout configuration error details')
        log.info('AI client initialized with default timeout')


def _initialize_ai_client(log: logging.Logger) -> Any:
    """Initialize AI client.

    Returns:
        object: The result.

    """
    if ai is None:
        log.error('aisuite not available - AI features disabled')
        return None

    log.info('aisuite is available')
    log.debug(f'aisuite version: {getattr(ai, "__version__", "unknown")}')

    _set_ollama_env_timeout(log)

    log.info('Initializing AI client...')
    provider_config = _create_ollama_config(log)

    if provider_config:
        log.info(f'Initializing client with provider config: {provider_config}')
        client = ai.Client(provider_config)
    else:
        client = ai.Client()

    _configure_ollama_provider(log, client)
    _configure_client_timeouts(log, client)

    log.debug(f'Client type: {type(client)}')
    return client


def _check_ollama_model_status(log: logging.Logger) -> dict[str, Any]:
    """Check if the ollama model is already downloaded and ready.

    Returns:
        dict: The result.

    """
    if not AI_MODEL.startswith('ollama:'):
        return {'downloaded': True, 'reason': 'not_ollama'}

    try:
        import json
        import urllib.request

        # Extract model name from ollama:model_name format
        model_name = AI_MODEL.split(':', 1)[1]

        # Check if model exists locally
        request = urllib.request.Request('http://localhost:11434/api/tags')
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310  # nosec B310 -- hardcoded http://localhost URL
            if response.status == HTTPStatus.OK:
                data = json.loads(response.read().decode())
                models = data.get('models', [])
                for model in models:
                    if model_name in model.get('name', ''):
                        log.info(f'Model {model_name} is already downloaded')
                        return {'downloaded': True, 'reason': 'already_downloaded'}

                log.info(f'Model {model_name} needs to be downloaded')
                return {'downloaded': False, 'reason': 'needs_download'}
            log.warning(f'Could not check model status: HTTP {response.status}')
            return {'downloaded': False, 'reason': 'api_error'}

    except (OSError, ValueError, KeyError) as e:
        log.warning(f'Could not check ollama model status: {e}')
        return {'downloaded': False, 'reason': 'check_failed'}


def _log_capabilities_dump(log: logging.Logger, **fields: object) -> None:
    """Log a formatted model capabilities dump block.

    Args:
        log: Logger instance.
        **fields: Key-value pairs to include in the dump.

    """
    log.debug(f'\n{"=" * 60}')
    log.debug('MODEL CAPABILITIES DUMP')
    log.debug('=' * 60)
    log.debug(f'Model: {AI_MODEL}')
    for key, value in fields.items():
        log.debug(f'{key}: {value}')
    log.debug(f'{"=" * 60}\n')


def _parse_capabilities_response(log: logging.Logger, content: str) -> dict[str, Any]:
    """Parse model capabilities from response content.

    Args:
        log: Logger instance.
        content: The model's response content string.

    Returns:
        Dictionary of capabilities.

    """
    try:
        # Try to parse comma-separated values first
        if ',' in content.strip():
            parts = content.strip().split(',')
            if len(parts) == AI_CAPABILITY_RESPONSE_FIELD_COUNT:
                context_size = int(parts[0].strip())
                output_limit = int(parts[1].strip())
                log.info(f'Detected context size: {context_size}, output limit: {output_limit}')
                _log_capabilities_dump(
                    log,
                    **{
                        'Context Size': context_size,
                        'Max Output Tokens': output_limit,
                        'Model Response': content,
                    },
                )
                return {
                    'max_tokens': output_limit,
                    'context_size': context_size,
                    'output_limit': output_limit,
                }

        # Fallback to single number parsing
        max_tokens = int(content.strip())
        log.info(f'Detected max tokens: {max_tokens}')
        _log_capabilities_dump(log, **{'Max Output Tokens': max_tokens, 'Model Response': content})
        return {'max_tokens': max_tokens}
    except ValueError:
        log.warning(f'Could not parse max tokens from response: {content}')
        _log_capabilities_dump(
            log, **{'Max Output Tokens': 'Could not parse', 'Model Response': content}
        )
        return {'max_tokens': None, 'raw_response': content}


def _query_model_capabilities(log: logging.Logger, client: Any) -> dict[str, Any]:
    """Send a test request to query model capabilities.

    Args:
        log: Logger instance.
        client: The AI client.

    Returns:
        Dictionary of capabilities.

    """
    test_messages = [
        {
            'role': 'user',
            'content': (
                'Please tell me your capabilities:\n'
                '1. What is your maximum context window size (input tokens)?\n'
                '2. What is your maximum output token limit for a single response?\n'
                'Please respond with just two numbers separated by a comma, like: '
                'context_size,output_limit'
            ),
        }
    ]

    log.info('Querying model capabilities...')
    log.info('This may take a while if the model needs to be downloaded first...')

    start_time = time.time()
    response = client.chat.completions.create(
        model=AI_MODEL,
        messages=test_messages,
        max_tokens=256,
    )
    duration = time.time() - start_time

    log.info(f'Model capability query completed in {duration:.2f} seconds')
    if duration > MODEL_DOWNLOAD_TIME_THRESHOLD_SECONDS:
        log.info('Model was likely downloaded during this request')

    if hasattr(response, 'choices') and response.choices:
        content = response.choices[0].message.content
        log.info(f'Model response about capabilities: {content}')
        return _parse_capabilities_response(log, content)

    _log_capabilities_dump(log, **{'Max Tokens': 'Unknown (no response)'})
    return {'max_tokens': None}


def _get_model_capabilities(log: logging.Logger) -> dict[str, Any]:  # type: ignore[reportUnusedFunction]
    """Query the model's capabilities including max tokens.

    Returns:
        dict: The model capabilities.

    """
    try:
        model_status = _check_ollama_model_status(log)

        if not model_status['downloaded']:
            log.info(f'Model needs to be downloaded: {model_status["reason"]}')
            log.info(f'\n{"=" * 60}')
            log.info('MODEL DOWNLOAD DETECTED')
            log.info('=' * 60)
            log.info(f'Model: {AI_MODEL}')
            log.info('Status: Model needs to be downloaded')
            log.info('This may take several minutes depending on model size...')
            log.info(f'{"=" * 60}\n')

        client = _initialize_ai_client(log)

        if client is None:
            log.warning('AI client not available, using default capabilities')
            return {'max_tokens': 8192, 'num_ctx': 65536}

        return _query_model_capabilities(log, client)

    except (ValueError, ConnectionError, TimeoutError) as e:
        log.exception('Failed to query model capabilities')
        _log_capabilities_dump(log, **{'Max Tokens': 'Unknown (query failed)', 'Error': str(e)})
        return {'max_tokens': None}


def _create_ai_retry_decorator(
    log: logging.Logger,
) -> Callable[[Callable[..., object]], Callable[..., object]]:
    """Create a retry decorator for AI requests with exponential backoff.

    Returns:
        object: The result.

    """
    if backoff is None:
        # If backoff is not available, return a no-op decorator
        def no_op_decorator(func: Callable[..., object]) -> Callable[..., object]:
            return func

        return no_op_decorator

    def giveup_handler(details: dict[str, Any]) -> None:
        """Handle final failure after all retries."""
        log.error(
            f'AI request failed permanently after {details["tries"]} attempts:'
            f' {details["exception"]}'
        )

    def backoff_handler(details: dict[str, Any]) -> None:
        """Handle backoff between retries."""
        log.warning(
            f'AI request failed (attempt {details["tries"]}), retrying in {details["wait"]:.1f}s:'
            f' {details["exception"]}'
        )

    return backoff.on_exception(
        backoff.expo,
        (Exception,),  # Catch all exceptions for retry
        max_tries=AI_MAX_RETRIES,
        base=AI_BASE_DELAY,
        max_value=AI_MAX_DELAY,
        giveup=lambda e: isinstance(e, (ValueError, KeyboardInterrupt, SystemExit)),
        on_giveup=giveup_handler,  # type: ignore[arg-type]
        on_backoff=backoff_handler,  # type: ignore[arg-type]
    )


def _make_ai_api_call(request: AIRequest, client: Any, log: logging.Logger) -> Any:
    """Make the actual API call to the AI service.

    Returns:
        object: The result.

    """
    log.info('Making API call to AI service...')
    log.debug(f'Using model: {AI_MODEL}')
    log.debug(f'Request messages count: {len(request.messages)}')
    log.debug(f'Max input tokens: {AI_MAX_INPUT_TOKENS}')
    log.debug(f'Max context tokens: {AI_MAX_CONTEXT_SIZE}')

    start_time = time.time()

    try:
        # Try to pass timeout parameters directly to the API call
        api_kwargs = {
            'model': AI_MODEL,
            'messages': request.messages,
            'max_tokens': AI_MAX_OUTPUT_TOKENS,  # Use OUTPUT token limit for AI response
        }

        # Add timeout parameters if the client supports them
        if hasattr(client.chat.completions, 'create'):
            # Check if the create method accepts timeout parameters
            import inspect

            sig = inspect.signature(client.chat.completions.create)

            # Try multiple timeout parameter names
            timeout_params = ['timeout', 'request_timeout', 'client_timeout', 'api_timeout']
            timeout_added = False

            for param_name in timeout_params:
                if param_name in sig.parameters:
                    # Use longer timeout for ollama models
                    timeout_value = (
                        AI_MODEL_DOWNLOAD_TIMEOUT if AI_MODEL.startswith('ollama:') else AI_TIMEOUT
                    )
                    api_kwargs[param_name] = timeout_value
                    log.debug(f'Added {param_name}={timeout_value} to API call')
                    timeout_added = True
                    break

            if not timeout_added:
                log.warning('No timeout parameter found in API call signature')
                log.debug(f'Available parameters: {list(sig.parameters.keys())}')

        log.critical(f'API call kwargs: {api_kwargs}')
        response = client.chat.completions.create(**api_kwargs)
    except Exception:
        end_time = time.time()
        duration = end_time - start_time
        log.exception(f'API call failed after {duration:.2f} seconds')
        log.exception('API call failed with exception')
        raise

    end_time = time.time()
    duration = end_time - start_time
    log.info(f'AI response received from API in {duration:.2f} seconds')

    return response


def _process_ai_request(request: AIRequest, client: Any, log: logging.Logger) -> AIResponse:
    """Process a single AI request with retry logic.

    Returns:
        AIResponse: The result.

    """
    # Check if AI client is available
    if client is None:
        log.warning('AI client not available, returning empty response')
        return AIResponse(content='AI features not available')

    # Create retry decorator for this request
    retry_decorator = _create_ai_retry_decorator(log)

    # Apply retry decorator to the API call function
    @retry_decorator
    def _retryable_api_call() -> object:
        return _make_ai_api_call(request, client, log)

    try:
        response = _retryable_api_call()
        return _extract_response_content(response, log)
    except Exception:
        log.exception('AI request failed permanently')
        raise


def _score_size_match(requested_size: tuple[int, int], example: dict[str, Any]) -> int:
    """Score how well an example's size matches the requested size.

    Args:
        requested_size: Requested (width, height).
        example: Training example dict.

    Returns:
        Score: 5 for exact, 3 for close, 1 for same aspect ratio, 0 otherwise.

    """
    example_size = _extract_example_size(example)
    if not example_size:
        return 0

    req_width, req_height = requested_size
    ex_width, ex_height = example_size

    if req_width == ex_width and req_height == ex_height:
        return 5
    if (
        abs(req_width - ex_width) <= req_width * 0.25
        and abs(req_height - ex_height) <= req_height * 0.25
    ):
        return 3
    if abs((req_width / req_height) - (ex_width / ex_height)) < SPRITE_ASPECT_RATIO_TOLERANCE:
        return 1
    return 0


_ANIMATED_KEYWORDS = frozenset(['animated', 'animation', 'frame', 'walk', 'run', 'idle'])
_STATIC_KEYWORDS = frozenset(['static', 'single', 'one'])
_COLOR_KEYWORDS = frozenset([
    'red',
    'blue',
    'green',
    'yellow',
    'orange',
    'purple',
    'pink',
    'brown',
    'black',
    'white',
])


def _score_training_example(
    example: dict[str, Any],
    user_lower: str,
    user_words: set[str],
    *,
    wants_alpha: bool,
    requested_size: tuple[int, int] | None,
) -> int:
    """Score a single training example for relevance to user request.

    Args:
        example: Training example dict.
        user_lower: Lowercased user request.
        user_words: Set of words from the user request.
        wants_alpha: Whether the user wants alpha/transparency.
        requested_size: Requested (width, height) or None.

    Returns:
        Relevance score (higher is better).

    """
    score = 0
    name = example.get('name', '').lower()
    sprite_type = example.get('sprite_type', '').lower()
    has_alpha = example.get('has_alpha', False)

    # Animation type matching (+10 for exact match)
    if any(kw in user_lower for kw in _ANIMATED_KEYWORDS) and sprite_type == 'animated':
        score += 10
    if any(kw in user_lower for kw in _STATIC_KEYWORDS) and sprite_type == 'static':
        score += 10

    # Size matching
    if requested_size:
        score += _score_size_match(requested_size, example)

    # Name keyword matching (+5 per matching word)
    score += len(user_words & set(name.split())) * 5

    # Alpha usage matching
    if wants_alpha and has_alpha:
        score += 3
    elif not wants_alpha and not has_alpha:
        score += 1

    # Color keyword hints (+2 each)
    for color in _COLOR_KEYWORDS:
        if color in user_lower and color in name:
            score += 2

    return score


def _select_relevant_training_examples(  # type: ignore[reportUnusedFunction]
    user_request: str, max_examples: int = AI_MAX_TRAINING_EXAMPLES
) -> list[dict[str, Any]]:
    """Select the most relevant training examples based on user request.

    Returns:
        list: The result.

    """
    training_data = ai_training_state['data']
    if not isinstance(training_data, list):
        return []

    if len(training_data) <= max_examples:
        return training_data

    user_lower = user_request.lower()
    requested_size = get_sprite_size_hint(user_request)
    user_words = set(user_lower.split())
    wants_alpha = any(
        kw in user_lower for kw in ['alpha', 'transparent', 'transparency', 'translucent']
    )

    scored_examples: list[tuple[float, dict[str, Any]]] = []
    for example in training_data:
        score = _score_training_example(
            example,
            user_lower,
            user_words,
            wants_alpha=wants_alpha,
            requested_size=requested_size,
        )
        scored_examples.append((score, example))

    scored_examples.sort(key=operator.itemgetter(0), reverse=True)
    relevant_examples = [example for _, example in scored_examples[:max_examples]]

    if len(relevant_examples) < max_examples:
        remaining = [ex for _, ex in scored_examples if ex not in relevant_examples]
        relevant_examples.extend(remaining[: max_examples - len(relevant_examples)])

    return relevant_examples


def _extract_example_size(example: dict[str, Any]) -> tuple[int, int] | None:
    """Extract sprite dimensions from training example.

    Args:
        example: Training example dictionary

    Returns:
        (width, height) tuple or None if size cannot be determined

    """
    # Try to get size from pixels field (static sprites)
    if 'pixels' in example:
        pixels = example['pixels']
        if isinstance(pixels, str) and '\n' in pixels:
            lines = pixels.strip().split('\n')
            if lines:
                height = len(lines)
                width = len(lines[0])
                return (width, height)

    # Try to get size from first animation frame
    if example.get('animations'):
        first_anim = example['animations'][0]
        if first_anim.get('frame'):
            first_frame = first_anim['frame'][0]
            if 'pixels' in first_frame:
                pixels = first_frame['pixels']
                if isinstance(pixels, str) and '\n' in pixels:
                    lines = pixels.strip().split('\n')
                    if lines:
                        height = len(lines)
                        width = len(lines[0])
                        return (width, height)

    return None


def _build_retry_prompt(original_prompt: str, validation_error: str) -> str:
    """Build a targeted retry prompt based on validation error.

    Args:
        original_prompt: Original user request
        validation_error: Error message from validate_ai_response()

    Returns:
        Enhanced prompt with specific corrections

    """
    # Base prompt
    retry_prompt = original_prompt + '\n\n'

    # Add specific corrections based on error type
    error_lower = validation_error.lower()

    if 'missing [sprite] section' in error_lower:
        retry_prompt += 'CRITICAL: You must include a [sprite] section at the beginning.'
    elif 'missing [colors] section' in error_lower:
        retry_prompt += (
            'CRITICAL: You must include [colors] sections defining every color used in pixels.'
        )
    elif 'truncated' in error_lower or 'incomplete' in error_lower:
        retry_prompt += (
            'IMPORTANT: Previous response was cut off. '
            'Reduce detail, use fewer frames, or make it smaller to fit within token limits.'
        )
    elif 'mixed' in error_lower and 'format' in error_lower:
        retry_prompt += (
            "CRITICAL: For animated sprites, do NOT include 'pixels' in [sprite] section. "
            'Only include pixels in [[animation.frame]] sections.'
        )
    elif 'comma' in error_lower:
        retry_prompt += (
            'CRITICAL: Color values must use separate fields (red = X, green = Y, blue = Z), '
            'NOT comma-separated tuples.'
        )
    elif 'markdown' in error_lower:
        retry_prompt += (
            'CRITICAL: Return ONLY raw TOML, no markdown code blocks (```), no explanations.'
        )
    elif 'empty' in error_lower:
        retry_prompt += 'CRITICAL: You must generate sprite content, not an empty or error message.'
    else:
        # Generic retry message
        retry_prompt += (
            f'IMPORTANT: Previous attempt had an error: '
            f'{validation_error}. Please fix and try again.'
        )

    return retry_prompt


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


def _normalize_toml_data(config_data: dict[str, Any]) -> dict[str, Any]:
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


def _extract_response_content(response: object, log: logging.Logger) -> AIResponse:
    """Extract content from AI response.

    Returns:
        AIResponse: The result.

    """
    if not hasattr(response, 'choices') or not response.choices:  # type: ignore[union-attr]
        log.error('No choices in response or empty choices')
        return AIResponse(content=None, error='No choices in response')

    first_choice: Any = response.choices[0]  # type: ignore[union-attr]
    if not hasattr(first_choice, 'message'):  # type: ignore[arg-type]
        log.error("No 'message' attribute in choice")
        return AIResponse(content=None, error='No message in response choice')

    message = first_choice.message  # type: ignore[reportUnknownMemberType]
    if not hasattr(message, 'content'):  # type: ignore[arg-type]
        log.error("No 'content' attribute in message")
        return AIResponse(content=None, error='No content in response message')

    content = message.content  # type: ignore[reportUnknownMemberType]
    log.info(f'Response content length: {len(content) if content else 0}')  # type: ignore[arg-type]
    return AIResponse(content=content)  # type: ignore[arg-type]


def ai_worker(
    request_queue: multiprocessing.Queue[AIRequest | None],
    response_queue: multiprocessing.Queue[tuple[str, AIResponse]],
) -> None:
    """Worker process for handling AI requests.

    Args:
        request_queue: Queue to receive requests from
        response_queue: Queue to send responses to

    Raises:
        ImportError: If aisuite cannot be imported.
        ValueError: If the AI request contains invalid data.
        KeyError: If a required key is missing from the request or response.
        AttributeError: If an expected attribute is missing from an object.
        OSError: If an I/O error occurs during processing.

    """
    log = _setup_ai_worker_logging()

    try:
        client = _initialize_ai_client(log)
        request_count = 0

        request = None
        while True:
            try:
                request = request_queue.get()
                request_count += 1
                log.info(f'Processing AI request #{request_count}')

                if request is None:  # Shutdown signal
                    log.info('Received shutdown signal, closing AI worker')
                    break

                ai_response = _process_ai_request(request, client, log)
                response_data = (request.request_id, ai_response)
                response_queue.put(response_data)
                log.info('Response sent successfully')

            except (ValueError, KeyError, AttributeError, OSError) as e:
                log.exception('Error processing AI request')
                if request:
                    response_queue.put((request.request_id, AIResponse(content=None, error=str(e))))
    except ImportError:
        log.exception('Failed to import aisuite')
        raise
    except (OSError, ValueError, KeyError, AttributeError):
        log.exception('Fatal error in AI worker process')
        raise


class ScrollArrowSprite(BitmappySprite):
    """Sprite for scroll arrows."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 20,
        height: int = 20,
        groups: pygame.sprite.LayeredDirty | None = None,  # type: ignore[type-arg]
        direction: str = 'up',
    ) -> None:
        """Initialize the scroll arrow sprite."""
        super().__init__(x=x, y=y, width=width, height=height, groups=groups)  # type: ignore[arg-type]
        self.direction = direction
        self.name = f'Scroll {direction} Arrow'

        # Create arrow surface
        self.image = pygame.Surface((width, height))
        self.rect = self.image.get_rect(x=x, y=y)

        # Draw the arrow
        self._draw_arrow()

        # Initially hidden
        self.visible = False
        self.dirty = 1

    def _draw_arrow(self) -> None:
        """Draw the arrow on the surface."""
        self.image.fill((255, 255, 255))  # White background

        if self.direction == 'up':
            # Up arrow: triangle pointing up
            pygame.draw.polygon(self.image, (0, 0, 0), [(10, 5), (5, 15), (15, 15)])
        elif self.direction == 'down':
            # Down arrow: triangle pointing down
            pygame.draw.polygon(self.image, (0, 0, 0), [(10, 15), (5, 5), (15, 5)])
        elif self.direction == 'plus':
            # Plus sign for adding new frames
            pygame.draw.line(self.image, (0, 0, 0), (10, 5), (10, 15), 2)  # Vertical line
            pygame.draw.line(self.image, (0, 0, 0), (5, 10), (15, 10), 2)  # Horizontal line

    def set_direction(self, direction: str) -> None:
        """Change the arrow direction and redraw."""
        if self.direction != direction:
            self.direction = direction
            self._draw_arrow()
            self.dirty = 1


class FilmStripSprite(BitmappySprite):
    """Sprite wrapper for the film strip widget.

    CRITICAL ARCHITECTURE NOTE:
    This sprite is the bridge between the film strip widget and the pygame sprite system.
    It MUST be updated continuously (every frame) to ensure preview animations run smoothly.

    KEY RESPONSIBILITIES:
    1. Continuous Animation Updates:
       - Updates film_strip_widget.update_animations() every frame
       - Passes delta time from the scene for smooth animation timing
       - Ensures preview animations run independently of user interaction

    2. Dirty Flag Management:
       - Marks itself as dirty when animations are running
       - This triggers redraws in the sprite group system
       - Ensures visual updates when animation frames advance

    3. Rendering Coordination:
       - Calls force_redraw() when needed (dirty or animations running)
       - Manages the relationship between animation state and visual updates

    DEBUGGING NOTES:
    - If animations stop: Check that this sprite's update() is called every frame
    - If animations are choppy: Verify _last_dt contains reasonable values
    - If no visual updates: Check that dirty flag is being set when animations run
    - If wrong timing: Verify delta time is being passed from scene update loop
    """

    def __init__(
        self,
        film_strip_widget: FilmStripWidget,
        x: int = 0,
        y: int = 0,
        width: int = 800,
        height: int = 100,
        groups: pygame.sprite.LayeredDirty | None = None,  # type: ignore[type-arg]
    ) -> None:
        """Initialize the film strip sprite."""
        super().__init__(x=x, y=y, width=width, height=height, groups=groups)  # type: ignore[arg-type]
        self.film_strip_widget: FilmStripWidget | None = film_strip_widget
        self.parent_scene: BitmapEditorScene | None = None
        self.name = 'Film Strip'

        # Create initial surface with alpha support
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        self.rect = self.image.get_rect(x=x, y=y)

        # Force initial render
        self.dirty = 1

    @override
    def update(self) -> None:
        """Update the film strip sprite.

        CRITICAL: This method is called continuously by the scene update loop
        to ensure preview animations run smoothly. The key insight is that film
        strip sprites need to update every frame, not just when dirty, because
        they contain independent animation timing that must advance continuously.
        """
        # Check if this sprite has been killed - if so, don't update
        if not hasattr(self, 'groups') or not self.groups() or len(self.groups()) == 0:
            LOG.debug(
                f'DEBUG: FilmStripSprite update skipped - not in groups: {hasattr(self, "groups")},'
                f' groups: {self.groups() if hasattr(self, "groups") else "None"}'
            )
            # Clear the widget reference to prevent any lingering updates
            if hasattr(self, 'film_strip_widget'):
                self.film_strip_widget = None
            return

        # Debug: Track if this sprite is being updated
        if not hasattr(self, '_update_count'):
            self._update_count = 0
        self._update_count += 1

        # Debug: Print update count every 100 updates for initial strip
        if self._update_count % 100 == 0:
            pass  # Debug logging removed

        # Update animations first to advance frame timing
        # This is the core of the preview animation system - it advances the
        # animation frames based on delta time, allowing smooth preview playback
        if hasattr(self, 'film_strip_widget') and self.film_strip_widget:
            # Get delta time from the scene or use a default
            # DEBUGGING: If animations are choppy, check that _last_dt is being set
            # by the scene update loop and contains reasonable values (0.016 = 60fps)
            dt = getattr(self, '_last_dt', 0.016)  # Default to ~60 FPS
            self.film_strip_widget.update_animations(dt)

        # Check if animations are running and force redraw
        # This determines whether we need continuous updates for preview animations
        animations_running = (
            hasattr(self, 'film_strip_widget')
            and self.film_strip_widget is not None
            and hasattr(self.film_strip_widget, 'animated_sprite')
            and self.film_strip_widget.animated_sprite is not None
            and len(self.film_strip_widget.animated_sprite._animations) > 0  # type: ignore[reportPrivateUsage]
        )

        # Always redraw if dirty or if animations are running
        # This ensures the film strip redraws both for user interactions (dirty)
        # and for continuous animation updates (animations_running)
        should_redraw = self.dirty or animations_running

        if should_redraw:
            self.force_redraw()
            # CRITICAL: Always mark as dirty when animations are running for continuous updates
            # This ensures the sprite group will redraw this sprite every frame when
            # animations are present, creating the smooth preview effect
            if animations_running:
                self.dirty = 1  # Keep dirty for continuous animation updates
            else:
                self.dirty = 0  # Reset dirty when no animations (normal sprite behavior)

    def force_redraw(self) -> None:
        """Force a redraw of the film strip."""
        assert self.film_strip_widget is not None
        # Clear the surface with copper brown to match film strip
        self.image.fill((100, 70, 55))  # Copper brown background

        # Render the film strip widget
        self.film_strip_widget.render(self.image)

    @override
    def kill(self) -> None:
        """Kill the sprite and clean up the widget reference."""
        # Clear the widget reference to prevent any lingering updates
        if hasattr(self, 'film_strip_widget'):
            self.film_strip_widget = None
        # Call the parent kill method
        super().kill()

    @override
    def on_left_mouse_button_down_event(self, event: events.HashableEvent) -> None:
        """Handle mouse clicks on the film strip."""
        LOG.debug(f'FilmStripSprite: Mouse click at {event.pos}, rect: {self.rect}')
        if self.rect.collidepoint(event.pos) and self.film_strip_widget and self.visible:
            LOG.debug(
                'FilmStripSprite: Click is within bounds and sprite is visible, converting '
                'coordinates'
            )
            # Convert screen coordinates to film strip coordinates
            film_x = event.pos[0] - self.rect.x
            film_y = event.pos[1] - self.rect.y

            # Check for shift-click using pygame's current key state
            is_shift_click = (
                pygame.key.get_pressed()[pygame.K_LSHIFT]
                or pygame.key.get_pressed()[pygame.K_RSHIFT]
            )

            # Handle click in the film strip widget
            LOG.debug(
                f'FilmStripSprite: Calling handle_click with coordinates ({film_x}, {film_y}),'
                f' shift={is_shift_click}'
            )
            clicked_frame = self.film_strip_widget.handle_click(
                (film_x, film_y), is_shift_click=is_shift_click
            )
            LOG.debug(f'FilmStripSprite: Clicked frame: {clicked_frame}')

            if clicked_frame:
                animation, frame_idx = clicked_frame
                LOG.debug(f'FilmStripSprite: Loading frame {frame_idx} of animation {animation}')

                # Notify the canvas to change frame
                if hasattr(self, 'parent_canvas') and self.parent_canvas:
                    self.parent_canvas.show_frame(animation, frame_idx)

                # Notify the parent scene about the selection change
                if hasattr(self, 'parent_scene') and self.parent_scene:
                    self.parent_scene._on_film_strip_frame_selected(  # type: ignore[reportPrivateUsage]
                        self.film_strip_widget, animation, frame_idx
                    )
            else:
                LOG.debug('FilmStripSprite: No frame clicked, handle_click returned None')
        else:
            LOG.debug('FilmStripSprite: Click is outside bounds or no widget')

    @override
    def on_right_mouse_button_up_event(self, event: events.HashableEvent) -> bool | None:  # type: ignore[override]
        """Handle right mouse clicks on the film strip for onion skinning and color sampling.

        Returns:
            object: The result.

        """
        LOG.info(f'FilmStripSprite: Right mouse UP at {event.pos}, rect: {self.rect}')
        if self.rect.collidepoint(event.pos) and self.film_strip_widget and self.visible:
            LOG.info(
                'FilmStripSprite: Right click UP is within '
                'bounds and sprite is visible, '
                'converting coordinates'
            )
            # Convert screen coordinates to film strip coordinates
            film_x = event.pos[0] - self.rect.x
            film_y = event.pos[1] - self.rect.y

            # Check for shift-right-click (screen sampling)
            is_shift_click = (
                pygame.key.get_pressed()[pygame.K_LSHIFT]
                or pygame.key.get_pressed()[pygame.K_RSHIFT]
            )

            # First check if we clicked on a frame for color sampling
            clicked_frame = self.film_strip_widget.get_frame_at_position((film_x, film_y))
            if clicked_frame:
                animation, frame_idx = clicked_frame
                LOG.info(
                    f'FilmStripSprite: Right-clicked frame {animation}[{frame_idx}] for color'
                    f' sampling'
                )

                if is_shift_click:
                    # Shift-right-click: sample screen directly (RGB only)
                    LOG.info(
                        'FilmStripSprite: Shift-right-click detected - sampling screen directly'
                    )
                    if hasattr(self, 'parent_scene') and self.parent_scene:
                        self.parent_scene._sample_color_from_screen(event.pos)  # type: ignore[reportPrivateUsage]
                else:
                    # Regular right-click: sample from sprite frame pixel data (RGBA)
                    self._sample_color_from_frame(animation, frame_idx, film_x, film_y)
                LOG.info('FilmStripSprite: Color sampling completed, returning early')
                return True  # Event was handled

            # Handle right-click in the film strip widget for onion skinning
            LOG.debug(
                f'FilmStripSprite: Calling handle_click with coordinates ({film_x}, {film_y}),'
                f' right_click=True'
            )
            clicked_frame = self.film_strip_widget.handle_click(
                (film_x, film_y), is_right_click=True
            )
            LOG.debug(f'FilmStripSprite: Right-clicked frame: {clicked_frame}')
            return True  # Event was handled
        LOG.debug('FilmStripSprite: Right click UP is outside bounds or no widget')
        return False  # Event not handled

    def _get_frame_pixel_data(
        self, animation: str, frame_idx: int
    ) -> tuple[Any, list[tuple[int, ...]]] | None:
        """Get pixel data and frame object for a specific animation frame.

        Args:
            animation: Animation name.
            frame_idx: Frame index.

        Returns:
            Tuple of (frame, pixel_data) or None if unavailable.

        """
        assert self.film_strip_widget is not None
        if not self.film_strip_widget.animated_sprite:
            LOG.debug('FilmStripSprite: No animated sprite available for color sampling')
            return None

        frames = self.film_strip_widget.animated_sprite._animations.get(animation, [])  # type: ignore[reportPrivateUsage]
        if frame_idx >= len(frames):
            LOG.debug(f'FilmStripSprite: Frame index {frame_idx} out of range')
            return None

        frame = frames[frame_idx]

        if hasattr(frame, 'get_pixel_data'):
            pixel_data = frame.get_pixel_data()
        elif hasattr(frame, 'pixels'):
            pixel_data = frame.pixels
        else:
            LOG.debug('FilmStripSprite: Frame has no pixel data available')
            return None

        if not pixel_data:
            LOG.debug('FilmStripSprite: Frame pixel data is empty')
            return None

        return frame, pixel_data

    def _get_frame_dimensions(self, frame: SpriteFrame) -> tuple[int, int]:
        """Get the actual pixel dimensions of a frame.

        Args:
            frame: The sprite frame object.

        Returns:
            Tuple of (width, height).

        """
        if hasattr(frame, 'image') and frame.image:
            return frame.image.get_size()

        assert self.film_strip_widget is not None
        parent_canvas = self.film_strip_widget.parent_canvas
        width = parent_canvas.pixels_across if parent_canvas else 32
        height = parent_canvas.pixels_tall if parent_canvas else 32
        return width, height

    def _find_frame_layout(self, animation: str, frame_idx: int) -> pygame.Rect | None:
        """Find the screen layout rectangle for a specific animation frame.

        Args:
            animation: Animation name.
            frame_idx: Frame index.

        Returns:
            The frame layout Rect, or None if not found.

        """
        assert self.film_strip_widget is not None
        for (
            anim_name,
            frame_idx_check,
        ), frame_rect in self.film_strip_widget.frame_layouts.items():
            if anim_name == animation and frame_idx_check == frame_idx:
                return frame_rect

        LOG.debug(f'FilmStripSprite: Could not find frame layout for {animation}[{frame_idx}]')
        return None

    def _screen_to_pixel_coords(
        self,
        film_x: int,
        film_y: int,
        frame_layout: pygame.Rect,
        actual_width: int,
        actual_height: int,
    ) -> tuple[int, int] | None:
        """Convert film strip screen coordinates to pixel coordinates within a frame.

        Args:
            film_x: X coordinate within the film strip.
            film_y: Y coordinate within the film strip.
            frame_layout: The frame's screen layout Rect.
            actual_width: Actual pixel width of the frame.
            actual_height: Actual pixel height of the frame.

        Returns:
            Tuple of (pixel_x, pixel_y) or None if outside bounds.

        """
        relative_x = film_x - frame_layout.x
        relative_y = film_y - frame_layout.y

        if not (0 <= relative_x < frame_layout.width and 0 <= relative_y < frame_layout.height):
            LOG.debug('FilmStripSprite: Click outside frame bounds')
            return None

        # Account for frame border (4px on each side)
        frame_content_width = frame_layout.width - 8
        frame_content_height = frame_layout.height - 8

        pixel_x = int((relative_x - 4) * actual_width / frame_content_width)
        pixel_y = int((relative_y - 4) * actual_height / frame_content_height)

        pixel_x = max(0, min(pixel_x, actual_width - 1))
        pixel_y = max(0, min(pixel_y, actual_height - 1))
        return pixel_x, pixel_y

    def _update_color_sliders(self, red: int, green: int, blue: int, alpha: int) -> None:
        """Update parent scene color sliders with sampled RGBA values.

        Args:
            red: Red channel value.
            green: Green channel value.
            blue: Blue channel value.
            alpha: Alpha channel value.

        """
        if not (hasattr(self, 'parent_scene') and self.parent_scene):
            return

        for channel_name, channel_value in [('R', red), ('G', green), ('B', blue), ('A', alpha)]:
            trigger = events.HashableEvent(0, name=channel_name, value=channel_value)
            self.parent_scene.on_slider_event(event=events.HashableEvent(0), trigger=trigger)

        LOG.info(
            f'FilmStripSprite: Updated sliders with sampled color R:{red}, G:{green},'
            f' B:{blue}, A:{alpha}'
        )

    def _sample_color_from_frame(
        self, animation: str, frame_idx: int, film_x: int, film_y: int
    ) -> None:
        """Sample color from a sprite frame pixel data.

        Args:
            animation: Animation name
            frame_idx: Frame index
            film_x: X coordinate within the film strip
            film_y: Y coordinate within the film strip

        """
        try:
            result = self._get_frame_pixel_data(animation, frame_idx)
            if result is None:
                return

            frame, pixel_data = result
            actual_width, actual_height = self._get_frame_dimensions(frame)

            frame_layout = self._find_frame_layout(animation, frame_idx)
            if not frame_layout:
                return

            pixel_coords = self._screen_to_pixel_coords(
                film_x, film_y, frame_layout, actual_width, actual_height
            )
            if pixel_coords is None:
                return

            pixel_x, pixel_y = pixel_coords
            pixel_num = pixel_y * actual_width + pixel_x

            if pixel_num >= len(pixel_data):
                LOG.debug(
                    f'FilmStripSprite: Pixel index {pixel_num} out of range for pixel data length'
                    f' {len(pixel_data)}'
                )
                return

            color = pixel_data[pixel_num]
            if len(color) == RGBA_COMPONENT_COUNT:
                red, green, blue, alpha = color
            else:
                red, green, blue = color
                alpha = 255

            LOG.debug(
                f'FilmStripSprite: Sampled color from frame {animation}[{frame_idx}] pixel'
                f' ({pixel_x}, {pixel_y}) - R:{red}, G:{green}, B:{blue}, A:{alpha}'
            )

            self._update_color_sliders(red, green, blue, alpha)

        except Exception:
            LOG.exception('FilmStripSprite: Error sampling color from frame')

    @override
    def on_key_down_event(self, event: events.HashableEvent) -> bool | None:  # type: ignore[override]
        """Handle keyboard events for copy/paste functionality.

        Returns:
            object: The result.

        """
        if not self.film_strip_widget:
            return None

        # Check for Ctrl+C (copy)
        if event.key == pygame.K_c and (event.get('mod', 0) & pygame.KMOD_CTRL):
            LOG.debug('FilmStripSprite: Ctrl+C detected - copying current frame')
            success = self.film_strip_widget.copy_current_frame()
            if success:
                LOG.debug('FilmStripSprite: Frame copied successfully')
            else:
                LOG.debug('FilmStripSprite: Failed to copy frame')
            return True

        # Check for Ctrl+V (paste)
        if event.key == pygame.K_v and (event.get('mod', 0) & pygame.KMOD_CTRL):
            LOG.debug('FilmStripSprite: Ctrl+V detected - pasting to current frame')
            success = self.film_strip_widget.paste_to_current_frame()
            if success:
                LOG.debug('FilmStripSprite: Frame pasted successfully')
            else:
                LOG.debug('FilmStripSprite: Failed to paste frame')
            return True

        return False

    def set_parent_canvas(self, canvas: AnimatedCanvasSprite) -> None:
        """Set the parent canvas for frame changes."""
        self.parent_canvas = canvas

    def on_drop_file_event(self, event: events.HashableEvent) -> bool:
        """Handle drop file event on film strip.

        Args:
            event: The pygame event containing the dropped file information.

        Returns:
            True if the drop was handled, False otherwise.

        """
        # Get current mouse position since drop events don't include position
        mouse_pos = pygame.mouse.get_pos()

        # Check if the drop is within the film strip bounds
        if not self.rect.collidepoint(mouse_pos):
            return False

        # Get the file path from the event
        file_path = event.file
        LOG.debug(f'FilmStripSprite: File dropped on film strip: {file_path}')

        # Check if it's an image file we can handle
        if not file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
            LOG.debug(f'FilmStripSprite: Unsupported file type: {file_path}')
            return False

        # Convert screen coordinates to film strip coordinates
        film_x = mouse_pos[0] - self.rect.x
        film_y = mouse_pos[1] - self.rect.y

        assert self.film_strip_widget is not None
        # Check if drop is on a specific frame
        clicked_frame = self.film_strip_widget.get_frame_at_position((int(film_x), int(film_y)))

        if clicked_frame:
            # Drop on existing frame - replace its contents
            animation, frame_idx = clicked_frame
            LOG.debug(f'FilmStripSprite: Dropping on frame {animation}[{frame_idx}]')
            return self._replace_frame_with_image(file_path, animation, frame_idx)
        # Drop on film strip but not on a frame - insert new frame
        LOG.debug('FilmStripSprite: Dropping on film strip area, inserting new frame')
        return self._insert_image_as_new_frame(file_path, int(film_x), int(film_y))

    @override
    def on_mouse_motion_event(self, event: events.HashableEvent) -> None:
        """Handle mouse motion events for drag hover effects.

        Args:
            event: The pygame mouse motion event.

        """
        assert self.film_strip_widget is not None
        # Check if we're currently dragging a file (this would need to be tracked by the scene)
        # For now, we'll implement basic hover detection
        if self.rect.collidepoint(event.pos):
            # Convert screen coordinates to film strip coordinates
            film_x = event.pos[0] - self.rect.x
            film_y = event.pos[1] - self.rect.y

            # Handle all hover effects (frames, previews, removal buttons)
            self.film_strip_widget.handle_hover((film_x, film_y))

            # Check if hovering over a specific frame
            hovered_frame = self.film_strip_widget.get_frame_at_position((film_x, film_y))

            if hovered_frame:
                # Hovering over a frame - show frame hover effect
                self._show_frame_hover_effect(hovered_frame)
            else:
                # Check if hovering over preview area
                hovered_preview = self.film_strip_widget.get_preview_at_position((film_x, film_y))
                if hovered_preview:
                    # Hovering over preview - show preview hover effect
                    self._show_preview_hover_effect(hovered_preview)
                else:
                    # Not hovering over preview - clear preview hover if it was set
                    if self.film_strip_widget.hovered_preview is not None:
                        self.film_strip_widget.hovered_preview = None
                        self.film_strip_widget.mark_dirty()
                        self.dirty = 1
                    # Hovering over film strip area - show strip hover effect
                    self._show_strip_hover_effect()

            # Mark as dirty if any hover state changed
            self.dirty = 1
        else:
            # Not hovering over film strip - clear hover effects
            self._clear_hover_effects()

    def _show_frame_hover_effect(self, frame_info: tuple[str, int]) -> None:
        """Show visual feedback for hovering over a frame.

        Args:
            frame_info: Tuple of (animation, frame_idx) for the hovered frame.

        """
        assert self.film_strip_widget is not None
        animation, frame_idx = frame_info
        LOG.debug(f'FilmStripSprite: Hovering over frame {animation}[{frame_idx}]')

        # Set hover state in the film strip widget
        self.film_strip_widget.hovered_frame = frame_info
        # Keep strip hover active even when hovering over frame
        self.film_strip_widget.mark_dirty()

        # Mark this sprite as dirty to trigger redraw
        self.dirty = 1

    def _show_preview_hover_effect(self, animation_name: str) -> None:
        """Show visual feedback for hovering over a preview area.

        Args:
            animation_name: Name of the animation being previewed.

        """
        assert self.film_strip_widget is not None
        LOG.debug(f'FilmStripSprite: Hovering over preview {animation_name}')

        # Set hover state in the film strip widget
        self.film_strip_widget.hovered_preview = animation_name
        # Keep strip hover active even when hovering over preview
        self.film_strip_widget.mark_dirty()

        # Mark this sprite as dirty to trigger redraw
        self.dirty = 1

    def _show_strip_hover_effect(self) -> None:
        """Show visual feedback for hovering over the film strip area."""
        assert self.film_strip_widget is not None
        LOG.debug('FilmStripSprite: Hovering over film strip area')

        # Set hover state in the film strip widget
        self.film_strip_widget.hovered_frame = None
        self.film_strip_widget.is_hovering_strip = True
        self.film_strip_widget.mark_dirty()

        # Mark this sprite as dirty to trigger redraw
        self.dirty = 1

    def _clear_hover_effects(self) -> None:
        """Clear all hover effects."""
        assert self.film_strip_widget is not None
        # Clear hover state in the film strip widget
        self.film_strip_widget.hovered_frame = None
        self.film_strip_widget.hovered_preview = None
        self.film_strip_widget.is_hovering_strip = False
        self.film_strip_widget.hovered_removal_button = None
        self.film_strip_widget.mark_dirty()

        # Mark this sprite as dirty to trigger redraw
        self.dirty = 1

    def _convert_image_to_sprite_frame(self, file_path: str) -> SpriteFrame | None:
        """Convert an image file to a SpriteFrame.

        Args:
            file_path: Path to the image file to convert.

        Returns:
            SpriteFrame object or None if conversion failed.

        """
        try:
            # Load the image
            image = pygame.image.load(file_path)

            # Get current canvas size for resizing
            canvas_width, canvas_height = 32, 32  # Default fallback
            if hasattr(self, 'parent_canvas') and self.parent_canvas:
                canvas_width = self.parent_canvas.pixels_across
                canvas_height = self.parent_canvas.pixels_tall
            elif (
                hasattr(self, 'parent_scene')
                and self.parent_scene
                and hasattr(self.parent_scene, 'canvas')
            ):
                canvas_width = self.parent_scene.canvas.pixels_across
                canvas_height = self.parent_scene.canvas.pixels_tall

            # Resize image to match canvas size
            if image.get_size() != (canvas_width, canvas_height):
                image = pygame.transform.scale(image, (canvas_width, canvas_height))

            # Convert to RGBA if needed, preserving transparency
            if image.get_flags() & pygame.SRCALPHA:
                # Image already has alpha - keep it
                pass
            else:
                # Convert RGB to RGBA by adding alpha channel
                rgba_image = pygame.Surface((canvas_width, canvas_height), pygame.SRCALPHA)
                rgba_image.blit(image, (0, 0))
                image = rgba_image

            # Get pixel data with alpha support
            pixels: list[tuple[int, ...]] = []
            if image.get_flags() & pygame.SRCALPHA:
                # Image has alpha channel - use array4d to preserve alpha
                pixel_array: Any = pygame.surfarray.array4d(image)  # type: ignore[attr-defined]
                for y in range(canvas_height):
                    for x in range(canvas_width):
                        r, g, b, a = pixel_array[x, y]  # type: ignore[index]
                        pixels.append((int(r), int(g), int(b), int(a)))  # type: ignore[arg-type]
            else:
                # Image has no alpha channel - use array3d and add alpha
                pixel_array = pygame.surfarray.array3d(image)  # type: ignore[assignment]
                for y in range(canvas_height):
                    for x in range(canvas_width):
                        r, g, b = pixel_array[x, y]
                        pixels.append((int(r), int(g), int(b), 255))  # Add full alpha

            # Create a new SpriteFrame with the surface
            from glitchygames.sprites import SpriteFrame

            frame = SpriteFrame(image, duration=0.1)  # 0.1 second duration
            frame.set_pixel_data(pixels)

            LOG.debug('FilmStripSprite: Successfully converted image to sprite frame')
            return frame

        except (pygame.error, OSError, ValueError, AttributeError):
            LOG.exception(f'FilmStripSprite: Failed to convert image {file_path}')
            return None

    def _should_update_canvas_frame(self, animation: str, frame_idx: int) -> bool:
        """Check if the canvas should be updated for a given animation frame.

        Args:
            animation: Animation name.
            frame_idx: Frame index.

        Returns:
            True if the canvas should be updated.

        """
        if not (hasattr(self, 'parent_scene') and self.parent_scene):
            return False
        parent = self.parent_scene
        return bool(
            hasattr(parent, 'selected_animation')
            and hasattr(parent, 'selected_frame')
            and parent.selected_animation == animation
            and parent.selected_frame == frame_idx
            and hasattr(parent, 'canvas')
            and parent.canvas
        )

    def _replace_frame_with_image(self, file_path: str, animation: str, frame_idx: int) -> bool:
        """Replace an existing frame with image content.

        Args:
            file_path: Path to the image file.
            animation: Animation name.
            frame_idx: Frame index to replace.

        Returns:
            True if successful, False otherwise.

        """
        assert self.film_strip_widget is not None
        LOG.debug(f'FilmStripSprite: Replacing frame {animation}[{frame_idx}] with image')

        # Convert image to sprite frame
        new_frame = self._convert_image_to_sprite_frame(file_path)
        if not new_frame:
            return False

        # Get the current frame and replace it
        if not self.film_strip_widget.animated_sprite:
            LOG.error('FilmStripSprite: No animated sprite available')
            return False

        frames = self.film_strip_widget.animated_sprite._animations.get(animation, [])  # type: ignore[reportPrivateUsage]
        if frame_idx >= len(frames):
            LOG.error(f'FilmStripSprite: Frame index {frame_idx} out of range')
            return False

        # Replace the frame
        frames[frame_idx] = new_frame

        # Mark as dirty for redraw
        self.film_strip_widget.mark_dirty()

        # Update canvas if this is the current frame
        if self._should_update_canvas_frame(animation, frame_idx):
            assert self.parent_scene is not None
            self.parent_scene.canvas.show_frame(animation, frame_idx)

        LOG.debug(f'FilmStripSprite: Successfully replaced frame {animation}[{frame_idx}]')
        return True

    def _insert_image_as_new_frame(self, file_path: str, film_x: int, film_y: int) -> bool:
        """Insert image as a new frame in the film strip.

        Args:
            file_path: Path to the image file.
            film_x: X coordinate of drop position.
            film_y: Y coordinate of drop position.

        Returns:
            True if successful, False otherwise.

        """
        assert self.film_strip_widget is not None
        LOG.debug('FilmStripSprite: Inserting new frame from image')

        # Convert image to sprite frame
        new_frame = self._convert_image_to_sprite_frame(file_path)
        if not new_frame:
            return False

        # Determine which animation to add to
        current_animation = self.film_strip_widget.current_animation
        if not current_animation:
            LOG.error('FilmStripSprite: No current animation selected')
            return False

        # Determine insertion position based on drop location
        # For now, insert at the end of the animation
        # TODO: Could be enhanced to insert at specific position based on drop location
        assert self.film_strip_widget.animated_sprite is not None
        insert_index = len(self.film_strip_widget.animated_sprite._animations[current_animation])  # type: ignore[reportPrivateUsage]

        # Insert the frame
        self.film_strip_widget.animated_sprite.add_frame(current_animation, new_frame, insert_index)

        # Mark as dirty for redraw
        self.film_strip_widget.mark_dirty()

        # Notify the parent scene about the frame insertion
        if (
            hasattr(self, 'parent_scene')
            and self.parent_scene
            and hasattr(self.parent_scene, '_on_frame_inserted')
        ):
            self.parent_scene._on_frame_inserted(current_animation, insert_index)  # type: ignore[reportPrivateUsage]

        # Select the newly created frame
        self.film_strip_widget.set_current_frame(current_animation, insert_index)

        LOG.debug(
            'FilmStripSprite: Successfully inserted new frame at'
            f' {current_animation}[{insert_index}]'
        )
        return True


class AnimatedCanvasSprite(BitmappySprite):
    """Animated Canvas Sprite for editing animated sprites."""

    log = LOG

    def __init__(
        self,
        animated_sprite: AnimatedSprite,
        name: str = 'Animated Canvas',
        x: int = 0,
        y: int = 0,
        pixels_across: int = 32,
        pixels_tall: int = 32,
        pixel_width: int = 16,
        pixel_height: int = 16,
        groups: pygame.sprite.LayeredDirty | None = None,  # type: ignore[type-arg]
    ) -> None:
        """Initialize the Animated Canvas Sprite."""
        # Initialize dimensions and get canvas size
        width, height = self._initialize_dimensions(
            pixels_across, pixels_tall, pixel_width, pixel_height
        )

        # Initialize parent class first to create rect
        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            groups=groups,  # type: ignore[arg-type]
        )

        # Override pixels_across and pixels_tall with correct pixel dimensions
        # (BitmappySprite.__init__ sets them to screen dimensions)
        self.pixels_across = pixels_across
        self.pixels_tall = pixels_tall

        # Parent scene reference, set externally after construction
        self.parent_scene: BitmapEditorScene | None = None

        # Initialize sprite data and frame management
        self._initialize_sprite_data(animated_sprite)

        # Initialize pixel arrays and color settings
        self._initialize_pixel_arrays()

        # Initialize panning system
        self._initialize_simple_panning()

        # Initialize canvas surface and UI components
        self._initialize_canvas_surface(x, y, width, height, groups)  # type: ignore[arg-type]

        # Initialize hover tracking for pixel hover effects
        self.hovered_pixel: tuple[int, int] | None = None

        # Initialize hover tracking for canvas border effect
        self.is_hovered: bool = False

        # Mini view reference for synchronized pixel updates (set externally)
        self.mini_view: AnimatedCanvasSprite | None = None

    def _initialize_dimensions(
        self, pixels_across: int, pixels_tall: int, pixel_width: int, pixel_height: int
    ) -> tuple[int, int]:
        """Initialize canvas dimensions and pixel sizing.

        Args:
            pixels_across: Number of pixels across the canvas
            pixels_tall: Number of pixels tall the canvas
            pixel_width: Width of each pixel in screen coordinates
            pixel_height: Height of each pixel in screen coordinates

        Returns:
            Tuple of (width, height) for the canvas surface

        """
        self.pixels_across = pixels_across
        self.pixels_tall = pixels_tall
        self.pixel_width = pixel_width
        self.pixel_height = pixel_height
        width = self.pixels_across * self.pixel_width
        height = self.pixels_tall * self.pixel_height
        return width, height

    def _initialize_sprite_data(self, animated_sprite: AnimatedSprite) -> None:
        """Initialize animated sprite and frame data.

        Args:
            animated_sprite: The animated sprite to associate with this canvas

        """
        self.animated_sprite: AnimatedSprite = animated_sprite
        # Use the sprite's current animation if set and not empty, otherwise start empty
        if hasattr(animated_sprite, 'current_animation') and animated_sprite.current_animation:
            self.current_animation = animated_sprite.current_animation
        else:
            self.current_animation = ''  # Start with empty animation
        # Sync the canvas frame with the animated sprite's current frame
        self.current_frame = animated_sprite.current_frame
        self.log.debug(
            'Canvas initialized - animated_sprite.current_frame='
            f'{animated_sprite.current_frame}, canvas.current_frame={self.current_frame}'
        )

        # Initialize manual frame selection flag to allow automatic animation updates
        self._manual_frame_selected = False

        # Sync canvas pixels with the current frame
        self._update_canvas_from_current_frame()

    def _initialize_pixel_arrays(self) -> None:
        """Initialize pixel arrays and color settings."""
        # Initialize pixels with magenta as the transparent/background color (RGBA)
        self.pixels = [(255, 0, 255, 255) for _ in range(self.pixels_across * self.pixels_tall)]
        self.dirty_pixels = [True] * len(self.pixels)
        self.background_color = (128, 128, 128)
        self.active_color = (0, 0, 0, 255)
        # Set border thickness using the internal method
        self._update_border_thickness()

    def _update_border_thickness(self) -> None:
        """Update border thickness based on pixel size.

        For large sprites where pixel size becomes very small, use no border
        to prevent grid from consuming all space. This happens when the 320x320
        constraint kicks in, making pixel size 2x2 or smaller.

        For very large sprites (128x128), also disable borders to prevent visual clutter.
        """
        # Disable borders for very small pixels (2x2 or smaller) or very large sprites (128x128)
        should_disable_borders = (
            (
                self.pixel_width <= MIN_PIXEL_DISPLAY_SIZE
                and self.pixel_height <= MIN_PIXEL_DISPLAY_SIZE
            )  # Very small pixels
            or (
                self.pixels_across >= LARGE_SPRITE_DIMENSION
                or self.pixels_tall >= LARGE_SPRITE_DIMENSION
            )  # Very large sprites
        )

        old_border_thickness = getattr(self, 'border_thickness', 1)
        self.border_thickness = 0 if should_disable_borders else 1

        # Clear pixel cache if border thickness changed
        if old_border_thickness != self.border_thickness:
            BitmapPixelSprite.PIXEL_CACHE.clear()
            self.log.info(
                f'Cleared pixel cache due to border thickness change ({old_border_thickness} ->'
                f' {self.border_thickness})'
            )

        self.log.info(
            f'Border thickness set to {self.border_thickness} (pixel size:'
            f' {self.pixel_width}x{self.pixel_height}, sprite size:'
            f' {self.pixels_across}x{self.pixels_tall})'
        )

    def _compute_panned_pixels(self, frame_pixels: list[tuple[int, ...]]) -> list[tuple[int, ...]]:
        """Compute panned pixel data by shifting source coordinates.

        Args:
            frame_pixels: Original pixel data from the frame.

        Returns:
            New pixel list with panning offsets applied.

        """
        frame_width = len(frame_pixels) // self.pixels_tall if self.pixels_tall > 0 else 0
        transparent = (255, 0, 255)
        panned_pixels: list[tuple[int, ...]] = []

        for y in range(self.pixels_tall):
            for x in range(self.pixels_across):
                source_x = x - self.pan_offset_x
                source_y = y - self.pan_offset_y

                if not (0 <= source_x < frame_width and 0 <= source_y < self.pixels_tall):
                    panned_pixels.append(transparent)
                    continue

                source_index = source_y * frame_width + source_x
                if source_index < len(frame_pixels):
                    panned_pixels.append(frame_pixels[source_index])
                else:
                    panned_pixels.append(transparent)

        return panned_pixels

    def _pan_frame_data(self) -> None:
        """Pan the frame data directly by shifting pixels within the frame."""
        if not hasattr(self, 'animated_sprite') or not self.animated_sprite:
            return

        current_animation = self.current_animation
        current_frame = self.current_frame

        if current_animation not in self.animated_sprite.frames:
            return
        if current_frame >= len(self.animated_sprite.frames[current_animation]):
            return

        frame = self.animated_sprite._animations[current_animation][current_frame]  # type: ignore[reportPrivateUsage]
        if not (hasattr(frame, 'get_pixel_data') and hasattr(frame, 'set_pixel_data')):
            return

        frame_pixels = frame.get_pixel_data()
        panned_pixels = self._compute_panned_pixels(frame_pixels)

        frame.set_pixel_data(panned_pixels)
        self.pixels = panned_pixels.copy()
        self.dirty_pixels = [True] * len(self.pixels)

        # Clear surface cache
        if hasattr(self.animated_sprite, '_surface_cache'):
            cache_key = f'{current_animation}_{current_frame}'
            if cache_key in self.animated_sprite._surface_cache:  # type: ignore[reportPrivateUsage]
                del self.animated_sprite._surface_cache[cache_key]  # type: ignore[reportPrivateUsage]

        self.log.debug(f'Frame data panned: offset=({self.pan_offset_x}, {self.pan_offset_y})')

    def _initialize_simple_panning(self) -> None:
        """Initialize the simple panning system for the canvas."""
        # Frame-specific panning state - each frame has its own panning
        # Format: {frame_key: {'pan_x': int, 'pan_y': int,
        #          'original_pixels': list, 'active': bool}}
        self._frame_panning: dict[str, dict[str, Any]] = {}

        self.log.debug('Simple panning system initialized with frame-specific state')

    def _get_current_frame_key(self) -> str:
        """Get a unique key for the current frame.

        Returns:
            str: The current frame key.

        """
        return f'{self.current_animation}_{self.current_frame}'

    def _store_original_frame_data_for_frame(self, frame_key: str) -> None:
        """Store the original frame data for a specific frame."""
        if hasattr(self, 'pixels') and self.pixels:
            self._frame_panning[frame_key]['original_pixels'] = list(self.pixels)
            self.log.debug(f'Stored original frame data for {frame_key}')

    def _apply_panning_view_for_frame(self, frame_key: str) -> None:
        """Apply panning transformation for a specific frame."""
        frame_state = self._frame_panning[frame_key]
        if frame_state['original_pixels'] is None:
            return

        # Create panned view by shifting pixels
        panned_pixels: list[tuple[int, ...]] = []

        for y in range(self.pixels_tall):
            for x in range(self.pixels_across):
                # Calculate source coordinates (where to read from in original)
                source_x = x - frame_state['pan_x']
                source_y = y - frame_state['pan_y']

                # Check if source is within bounds
                if 0 <= source_x < self.pixels_across and 0 <= source_y < self.pixels_tall:
                    source_index = source_y * self.pixels_across + source_x
                    if source_index < len(frame_state['original_pixels']):
                        panned_pixels.append(frame_state['original_pixels'][source_index])
                    else:
                        panned_pixels.append((255, 0, 255))  # Transparent
                else:
                    panned_pixels.append((255, 0, 255))  # Transparent

        # Update canvas pixels with panned view
        self.pixels = panned_pixels
        self.dirty_pixels = [True] * len(self.pixels)

        self.log.debug(
            f'Applied panning view for {frame_key}: offset=({frame_state["pan_x"]},'
            f' {frame_state["pan_y"]})'
        )

    def reset_panning(self) -> None:
        """Reset panning for the current frame."""
        frame_key = self._get_current_frame_key()

        # Clear panning state for current frame
        if frame_key in self._frame_panning:
            self._frame_panning[frame_key] = {
                'pan_x': 0,
                'pan_y': 0,
                'original_pixels': None,
                'active': False,
            }

        # Reload the original frame data
        if hasattr(self, 'animated_sprite') and self.animated_sprite:
            current_animation = self.current_animation
            current_frame = self.current_frame

            if current_animation in self.animated_sprite.frames and current_frame < len(
                self.animated_sprite.frames[current_animation]
            ):
                frame = self.animated_sprite._animations[current_animation][current_frame]  # type: ignore[reportPrivateUsage]
                if hasattr(frame, 'get_pixel_data'):
                    self.pixels = frame.get_pixel_data().copy()
                    self.dirty_pixels = [True] * len(self.pixels)
                    self.dirty = 1

        self.log.debug(f'Panning reset for frame {frame_key}')

    def is_panning_active(self) -> bool:
        """Check if panning is active for the current frame.

        Returns:
            bool: True if is panning active, False otherwise.

        """
        frame_key = self._get_current_frame_key()
        if frame_key in self._frame_panning:
            return self._frame_panning[frame_key]['active']
        return False

    def _initialize_canvas_surface(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        groups: pygame.sprite.LayeredDirty | None,  # type: ignore[type-arg]
    ) -> None:
        """Initialize canvas surface and interface components.

        Args:
            x: X position of the canvas
            y: Y position of the canvas
            width: Width of the canvas surface
            height: Height of the canvas surface
            groups: Sprite groups to add components to

        """
        # Create initial surface
        self.image = pygame.Surface((self.width, self.height))
        self.rect = self.image.get_rect(x=x, y=y)

        # Initialize interface components for animated sprites
        self.canvas_interface = AnimatedCanvasInterface(self)
        # Sync the canvas interface with the canvas's current frame
        self.canvas_interface.set_current_frame(self.current_animation, self.current_frame)
        self.sprite_serializer = AnimatedSpriteSerializer()
        self.canvas_renderer = AnimatedCanvasRenderer(self)

        # Multiple film strips disabled - only showing first animation

        # Film strips will be created in the main scene after canvas setup

        # Film strip sprites are added to groups in _create_multiple_film_strips

        # Show the first frame
        self.show_frame(self.current_animation, self.current_frame)

        # Force initial draw
        self.dirty = 1
        self.force_redraw()

    def _get_current_frame_pixels(self) -> list[tuple[int, int, int, int]]:
        """Get pixel data from the current frame of the animated sprite as RGBA.

        Returns:
            list[tuple[int, int, int, int]]: The current frame pixels.

        """
        pixels = []

        if hasattr(self, 'animated_sprite') and self.animated_sprite:
            # Check if this is a static sprite (no frames)
            if (
                not hasattr(self.animated_sprite, '_animations')
                or not self.animated_sprite._animations  # type: ignore[reportPrivateUsage]
            ):
                # Static sprite - get pixels directly
                if hasattr(self.animated_sprite, 'get_pixel_data'):
                    pixels = self.animated_sprite.get_pixel_data()  # type: ignore[union-attr]
                    self.log.debug(
                        f'Got pixels from animated_sprite.get_pixel_data(): {len(pixels)} pixels, '  # type: ignore[arg-type]
                        f'first few: {pixels[:5]}'
                    )
                elif hasattr(self.animated_sprite, 'pixels'):
                    pixels = self.animated_sprite.pixels.copy()  # type: ignore[union-attr]
                    self.log.debug(
                        f'Got pixels from animated_sprite.pixels: {len(pixels)} pixels, '  # type: ignore[arg-type]
                        f'first few: {pixels[:5]}'
                    )

            # Animated sprite with frames
            current_animation = self.current_animation
            current_frame = self.current_frame
            self.log.debug(
                f"Getting frame pixels for animation '{current_animation}', frame {current_frame}"
            )

            if current_animation in self.animated_sprite._animations and current_frame < len(  # type: ignore[reportPrivateUsage]
                self.animated_sprite._animations[current_animation]  # type: ignore[reportPrivateUsage]
            ):
                frame = self.animated_sprite._animations[current_animation][current_frame]  # type: ignore[reportPrivateUsage]
                if hasattr(frame, 'get_pixel_data'):
                    pixels = frame.get_pixel_data()
                    self.log.debug(
                        f'Got pixels from frame.get_pixel_data(): {len(pixels)} pixels, '
                        f'first few: {pixels[:5]}'
                    )
                else:
                    self.log.warning('Frame has no get_pixel_data method')
            else:
                self.log.warning(
                    f"Animation '{current_animation}' or frame {current_frame} not found"
                )

        # Fallback to static pixels
        if not pixels:
            pixels = self.pixels.copy()
            self.log.debug(
                f'Using fallback canvas pixels: {len(pixels)} pixels, first few: {pixels[:5]}'
            )

        # Ensure all pixels are RGBA format
        rgba_pixels: list[tuple[int, ...]] = []
        for pixel in pixels:  # type: ignore[union-attr]
            if len(pixel) == RGBA_COMPONENT_COUNT:  # type: ignore[arg-type]
                rgba_pixels.append(pixel)  # type: ignore[arg-type]
            else:
                # Convert RGB to RGBA with full opacity
                rgba_pixels.append((pixel[0], pixel[1], pixel[2], 255))  # type: ignore[arg-type]

        return rgba_pixels  # type: ignore[return-value]

    def _update_canvas_from_current_frame(self) -> None:
        """Update the canvas pixels with the current frame data."""
        if hasattr(self, 'animated_sprite') and self.animated_sprite:
            # Use the canvas's current animation and frame (not the animated sprite's)
            current_animation = self.current_animation
            current_frame = self.current_frame
            self.log.info(f'DEBUG: Syncing canvas with frame {current_animation}[{current_frame}]')
            if current_animation in self.animated_sprite._animations and current_frame < len(  # type: ignore[reportPrivateUsage]
                self.animated_sprite._animations[current_animation]  # type: ignore[reportPrivateUsage]
            ):
                frame = self.animated_sprite._animations[current_animation][current_frame]  # type: ignore[reportPrivateUsage]
                if hasattr(frame, 'get_pixel_data'):
                    frame_pixels = frame.get_pixel_data()
                    self.log.info(
                        f'DEBUG: Frame pixels: {len(frame_pixels)} pixels, first few:'
                        f' {frame_pixels[:5]}'
                    )
                    self.log.info(
                        f'DEBUG: Frame pixel types: {[type(p) for p in frame_pixels[:3]]}'
                    )
                    self.log.info(
                        f'DEBUG: All frame pixels same color: {len(set(frame_pixels)) == 1}'
                    )
                    self.pixels = frame_pixels
                    self.dirty_pixels = [True] * len(self.pixels)
                    self.log.info(f'Updated canvas pixels from frame {current_frame}')
                    # Mark canvas dirty to ensure redraw applies per-pixel alpha on load
                    self.dirty = 1
                else:
                    self.log.info('DEBUG: Frame has no get_pixel_data method')
            else:
                self.log.info(
                    f"DEBUG: Animation '{current_animation}' or frame {current_frame} not found"
                )
        else:
            self.log.info('DEBUG: No animated_sprite available for canvas sync')

    def set_frame(self, frame_index: int) -> None:
        """Set the current frame index for the current animation."""
        if hasattr(self, 'animated_sprite') and self.animated_sprite:
            frames = self.animated_sprite._animations  # type: ignore[reportPrivateUsage]
            if self.current_animation in frames and 0 <= frame_index < len(
                frames[self.current_animation]
            ):
                # Store the current playing state
                was_playing = self.animated_sprite.is_playing

                # Pause the animation when manually selecting frames
                self.animated_sprite.pause()

                self.current_frame = frame_index
                self.animated_sprite.set_frame(frame_index)

                # Mark that user manually selected a frame
                self._manual_frame_selected = True

                # Update the canvas interface
                self.canvas_interface.set_current_frame(self.current_animation, frame_index)

                # Update the undo/redo manager with the current frame for frame-specific operations
                if (
                    hasattr(self, 'parent_scene')
                    and self.parent_scene
                    and hasattr(self.parent_scene, 'undo_redo_manager')
                ):
                    self.parent_scene.undo_redo_manager.set_current_frame(
                        self.current_animation, frame_index
                    )

                # Only restart animation if it was playing before
                if was_playing:
                    self.animated_sprite.play()
                    self._manual_frame_selected = False
                else:
                    # Keep it paused if it was already paused
                    self.log.debug(
                        f'Animation was paused, keeping it paused at frame {frame_index}'
                    )

                self.dirty = 1
                self.log.debug(
                    f'Set frame to {frame_index} for animation '
                    f"'{self.current_animation}' (was_playing: {was_playing})"
                )

    def _should_track_frame_selection(self) -> bool:
        """Check if frame selection changes should be tracked for undo/redo.

        Returns:
            True if frame selection should be tracked.

        """
        if not (hasattr(self, 'parent_scene') and self.parent_scene):
            return False
        parent = self.parent_scene
        if not hasattr(parent, 'undo_redo_manager'):
            return False
        return not (
            getattr(parent, '_applying_undo_redo', False)
            or getattr(parent, '_creating_frame', False)
            or getattr(parent, '_creating_animation', False)
        )

    def show_frame(self, animation: str, frame: int) -> None:
        """Show a specific frame of the animated sprite."""
        self.log.debug(f'show_frame called: animation={animation}, frame={frame}')
        frames = self.animated_sprite._animations  # type: ignore[reportPrivateUsage]
        if animation in frames and 0 <= frame < len(frames[animation]):
            self.current_animation = animation
            self.current_frame = frame
            self.log.debug(
                f'Canvas updated: current_animation={self.current_animation},'
                f' current_frame={self.current_frame}'
            )

            # Update the animated sprite to the new animation and frame
            if animation != self.animated_sprite.current_animation:
                self.animated_sprite.set_animation(animation)
            self.animated_sprite.set_frame(frame)

            # Update the canvas interface
            self.canvas_interface.set_current_frame(animation, frame)

            # Update the undo/redo manager with the current frame for frame-specific operations
            # Only track frame selection if we're not in the middle of an undo/redo operation
            # or creating a frame (which has its own undo tracking)
            # Also don't track frame selection if we're in the middle of film strip operations
            if self._should_track_frame_selection():
                # Track frame selection as a film strip operation instead of global
                assert self.parent_scene is not None
                self.parent_scene.film_strip_operation_tracker.add_frame_selection(animation, frame)

            # Force the canvas to redraw with the new frame
            self.force_redraw()

            # Notify the parent scene about the frame change
            if hasattr(self, 'parent_scene') and self.parent_scene:
                self.log.debug(f'Notifying parent scene about frame change: {animation}[{frame}]')
                self.parent_scene._update_film_strips_for_frame(animation, frame)  # type: ignore[reportPrivateUsage]
            else:
                self.log.debug('No parent scene found to notify about frame change')

            # Get the frame data
            frame_obj = frames[animation][frame]
            if hasattr(frame_obj, 'get_pixel_data'):
                self.pixels = frame_obj.get_pixel_data()
            else:
                # Fallback to frame pixels if available
                self.pixels = getattr(
                    frame_obj, 'pixels', [(255, 0, 255)] * (self.pixels_across * self.pixels_tall)
                )

            # Mark all pixels as dirty
            self.dirty_pixels = [True] * len(self.pixels)
            self.dirty = 1

            # Notify parent scene to update film strips
            if hasattr(self, 'parent_scene') and self.parent_scene:
                self.parent_scene._update_film_strips_for_frame(animation, frame)  # type: ignore[reportPrivateUsage]

            # Note: Live preview functionality is now integrated into the film strip

    def next_frame(self) -> None:
        """Move to the next frame in the current animation."""
        frames = self.animated_sprite._animations  # type: ignore[reportPrivateUsage]
        if self.current_animation in frames:
            frame_list = frames[self.current_animation]
            self.current_frame = (self.current_frame + 1) % len(frame_list)
            self.show_frame(self.current_animation, self.current_frame)

            # Notify the parent scene about the frame change
            if hasattr(self, 'parent_scene') and self.parent_scene:
                self.log.debug(
                    'Notifying parent scene about frame change:'
                    f' {self.current_animation}[{self.current_frame}]'
                )
                self.parent_scene._switch_to_film_strip(self.current_animation, self.current_frame)  # type: ignore[reportPrivateUsage]

    def previous_frame(self) -> None:
        """Move to the previous frame in the current animation."""
        frames = self.animated_sprite._animations  # type: ignore[reportPrivateUsage]
        if self.current_animation in frames:
            frame_list = frames[self.current_animation]
            self.current_frame = (self.current_frame - 1) % len(frame_list)
            self.show_frame(self.current_animation, self.current_frame)

            # Notify the parent scene about the frame change
            if hasattr(self, 'parent_scene') and self.parent_scene:
                self.log.debug(
                    'Notifying parent scene about frame change:'
                    f' {self.current_animation}[{self.current_frame}]'
                )
                self.parent_scene._switch_to_film_strip(self.current_animation, self.current_frame)  # type: ignore[reportPrivateUsage]

    def next_animation(self) -> None:
        """Move to the next animation."""
        self.log.debug(f'next_animation called, current_animation={self.current_animation}')
        frames = self.animated_sprite._animations  # type: ignore[reportPrivateUsage]
        animations = list(frames.keys())
        self.log.debug(f'Available animations: {animations}')
        if animations:
            current_index = animations.index(self.current_animation)
            next_index = (current_index + 1) % len(animations)
            next_animation = animations[next_index]

            # Preserve the current frame number when switching animations
            preserved_frame = self.current_frame
            # Ensure the frame number is within bounds for the new animation
            if next_animation in frames and len(frames[next_animation]) > 0:
                max_frame = len(frames[next_animation]) - 1
                preserved_frame = min(preserved_frame, max_frame)
            else:
                preserved_frame = 0
            self.log.debug(
                f'Moving from animation {self.current_animation} (index {current_index}) to'
                f' {next_animation} (index {next_index}), preserving frame {preserved_frame}'
            )
            self.show_frame(next_animation, preserved_frame)
            self.log.debug(
                f'After show_frame: current_animation={self.current_animation},'
                f' current_frame={self.current_frame}'
            )

            # Notify the parent scene to switch film strips
            if hasattr(self, 'parent_scene') and self.parent_scene:
                self.log.debug(f'Notifying parent scene to switch to film strip {next_animation}')
                self.parent_scene._switch_to_film_strip(next_animation, preserved_frame)  # type: ignore[reportPrivateUsage]

    def previous_animation(self) -> None:
        """Move to the previous animation."""
        self.log.debug(f'previous_animation called, current_animation={self.current_animation}')
        frames = self.animated_sprite._animations  # type: ignore[reportPrivateUsage]
        animations = list(frames.keys())
        self.log.debug(f'Available animations: {animations}')
        if animations:
            current_index = animations.index(self.current_animation)
            prev_index = (current_index - 1) % len(animations)
            prev_animation = animations[prev_index]

            # Preserve the current frame number when switching animations
            preserved_frame = self.current_frame
            # Ensure the frame number is within bounds for the new animation
            if prev_animation in frames and len(frames[prev_animation]) > 0:
                max_frame = len(frames[prev_animation]) - 1
                preserved_frame = min(preserved_frame, max_frame)
            else:
                preserved_frame = 0
            self.log.debug(
                f'Moving from animation {self.current_animation} (index {current_index}) to'
                f' {prev_animation} (index {prev_index}), preserving frame {preserved_frame}'
            )
            self.show_frame(prev_animation, preserved_frame)
            self.log.debug(
                f'After show_frame: current_animation={self.current_animation},'
                f' current_frame={self.current_frame}'
            )

            # Notify the parent scene to switch film strips
            if hasattr(self, 'parent_scene') and self.parent_scene:
                self.log.debug(f'Notifying parent scene to switch to film strip {prev_animation}')
                self.parent_scene._switch_to_film_strip(prev_animation, preserved_frame)  # type: ignore[reportPrivateUsage]

    def handle_keyboard_event(self, key: int) -> None:
        """Handle keyboard navigation events."""
        self.log.debug(f'Keyboard event received: key={key}')

        if key == pygame.K_LEFT:
            self.log.debug('LEFT arrow pressed')
            self.previous_frame()
        elif key == pygame.K_RIGHT:
            self.log.debug('RIGHT arrow pressed')
            self.next_frame()
        elif key == pygame.K_UP:
            self.log.debug('UP arrow pressed')
            self.previous_animation()
        elif key == pygame.K_DOWN:
            self.log.debug('DOWN arrow pressed')
            self.next_animation()
        elif pygame.K_0 <= key <= pygame.K_9:
            # Handle 0-9 keys for frame selection
            frame_index = key - pygame.K_0
            self.log.debug(f'Number key {frame_index} pressed')
            self.set_frame(frame_index)
        elif key == pygame.K_SPACE:
            # Toggle animation play/pause
            self.log.debug('SPACE key pressed')
            if hasattr(self, 'animated_sprite') and self.animated_sprite:
                current_state = self.animated_sprite.is_playing
                self.log.debug(f'Current animation state: is_playing={current_state}')
                if self.animated_sprite.is_playing:
                    self.animated_sprite.pause()
                    self.log.debug('Animation paused')
                else:
                    # Restart animation from current frame
                    self.animated_sprite.play()
                    self.log.debug('Animation restarted')
                self.log.debug(f'New animation state: is_playing={self.animated_sprite.is_playing}')

                # Note: Live preview functionality is now integrated into the film strip
        else:
            self.log.debug(f'Unhandled key: {key}')

    def copy_current_frame(self) -> None:
        """Copy the current frame to clipboard."""
        # Get the current frame data
        frames = self.animated_sprite._animations  # type: ignore[reportPrivateUsage]
        if self.current_animation in frames and self.current_frame < len(
            frames[self.current_animation]
        ):
            frame = frames[self.current_animation][self.current_frame]
            # Store the pixel data in a simple clipboard attribute
            self._clipboard = frame.get_pixel_data().copy()

    def paste_to_current_frame(self) -> None:
        """Paste clipboard content to current frame."""
        if hasattr(self, '_clipboard') and self._clipboard:
            # Get the current frame
            frames = self.animated_sprite._animations  # type: ignore[reportPrivateUsage]
            if self.current_animation in frames and self.current_frame < len(
                frames[self.current_animation]
            ):
                frame = frames[self.current_animation][self.current_frame]
                # Set the pixel data
                frame.set_pixel_data(self._clipboard)
                # Update the canvas pixels
                self.pixels = self._clipboard.copy()
                # Mark as dirty
                self.dirty_pixels = [True] * len(self.pixels)
                self.dirty = 1

    def save_animated_sprite(self, filename: str) -> None:
        """Save the animated sprite to a file."""
        if self.is_panning_active():
            # Save viewport only when panning is active
            self.log.info('Saving viewport only due to active panning')
            self._save_viewport_sprite(filename)
        else:
            # Save full sprite when not panning
            # Prefer canvas.animated_sprite if available
            sprite_to_save = None
            if hasattr(self, 'canvas') and self.canvas and hasattr(self.canvas, 'animated_sprite'):  # type: ignore[attr-defined]
                sprite_to_save = self.canvas.animated_sprite  # type: ignore[attr-defined]
            elif hasattr(self, 'animated_sprite'):
                sprite_to_save = self.animated_sprite

            if sprite_to_save:
                self.sprite_serializer.save(sprite_to_save, filename, DEFAULT_FILE_FORMAT)  # type: ignore[arg-type]
            else:
                self.log.error('No sprite found to save')

    @classmethod
    def from_file(
        cls,
        filename: str,
        x: int = 0,
        y: int = 0,
        pixels_across: int = 32,
        pixels_tall: int = 32,
        pixel_width: int = 16,
        pixel_height: int = 16,
        groups: pygame.sprite.LayeredDirty | None = None,  # type: ignore[type-arg]
    ) -> Self:
        """Create an AnimatedCanvasSprite from a file.

        Returns:
            AnimatedCanvasSprite: The newly created animated canvas sprite.

        Raises:
            ValueError: If the file does not contain animated sprite data.

        """
        # Load the animated sprite
        animated_sprite = SpriteFactory.load_sprite(filename=filename)

        if not hasattr(animated_sprite, 'frames'):
            raise ValueError(f'File {filename} does not contain animated sprite data')

        return cls(
            animated_sprite=animated_sprite,
            name='Animated Canvas',
            x=x,
            y=y,
            pixels_across=pixels_across,
            pixels_tall=pixels_tall,
            pixel_width=pixel_width,
            pixel_height=pixel_height,
            groups=groups,
        )

    def update_animation(self, dt: float) -> None:
        """Update the animated sprite with delta time."""
        if hasattr(self, 'animated_sprite') and self.animated_sprite:
            self.animated_sprite.update(dt)

    @override
    def update(self) -> None:
        """Update the canvas sprite."""
        # Animation timing is handled by the scene's update_animation method

        # Force redraw if dirty
        if self.dirty:
            self.force_redraw()
            self.dirty = 0

    def force_redraw(self) -> None:
        """Force a complete redraw of the canvas."""
        # Use the interface-based rendering while maintaining existing behavior
        self.image = self.canvas_renderer.force_redraw(self)

    @override
    def on_left_mouse_button_down_event(self, event: events.HashableEvent) -> None:
        """Handle the left mouse button down event."""
        # self.log.debug(f"AnimatedCanvasSprite mouse down event at {event.pos}, rect: {self.rect}")
        if self.rect.collidepoint(event.pos):
            x = (event.pos[0] - self.rect.x) // self.pixel_width
            y = (event.pos[1] - self.rect.y) // self.pixel_height
            # self.log.debug(f"AnimatedCanvasSprite clicked at pixel ({x}, {y})")

            # Mark that we're starting a potential drag operation
            self._drag_active = False  # Will be set to True on first drag event
            self._drag_pixels: dict[
                tuple[int, int], tuple[int, int, tuple[int, ...], tuple[int, ...]]
            ] = {}  # Track pixels changed during drag for batched updates

            # Check for control-click (flood fill mode)
            is_control_click = (
                pygame.key.get_pressed()[pygame.K_LCTRL] or pygame.key.get_pressed()[pygame.K_RCTRL]
            )

            if is_control_click:
                # Flood fill mode
                self.log.info(f'Control-click detected - performing flood fill at ({x}, {y})')
                self._flood_fill(x, y, self.active_color)  # type: ignore[arg-type]
            else:
                # Normal click mode
                # Mark that user is editing (manual frame selection)
                self._manual_frame_selected = True

                # Don't sync the canvas frame - keep it on the frame being edited
                # The canvas should stay on the current frame, only the live preview should animate

                # Use the interface to set the pixel
                self.canvas_interface.set_pixel_at(x, y, self.active_color)

            # Force redraw the canvas to show the changes
            self.force_redraw()

            # Note: Live preview functionality is now integrated into the film strip
        else:
            self.log.debug(
                f'AnimatedCanvasSprite click missed - pos {event.pos} not in rect {self.rect}'
            )

    def _cache_drag_frame(self) -> None:
        """Cache the current frame reference for the active drag operation."""
        if hasattr(self, '_drag_frame'):
            return
        if (
            hasattr(self, 'animated_sprite')
            and hasattr(self, 'current_animation')
            and hasattr(self, 'current_frame')
            and self.current_animation in self.animated_sprite.frames
        ):
            self._drag_frame = self.animated_sprite._animations[self.current_animation][  # type: ignore[reportPrivateUsage]
                self.current_frame
            ]
        else:
            self._drag_frame = None

    def _get_old_pixel_color(self, pixel_num: int) -> tuple[int, ...]:
        """Get the old color at a pixel position, preferring frame data over canvas.

        Args:
            pixel_num: Linear pixel index.

        Returns:
            The pixel color tuple.

        """
        old_color = self.pixels[pixel_num]
        if self._drag_frame is None:
            return old_color

        # Fast path: directly access frame.pixels to avoid array copy
        if hasattr(self._drag_frame, 'pixels') and pixel_num < len(self._drag_frame.pixels):
            return self._drag_frame.pixels[pixel_num]

        # Fallback: use get_pixel_data() copy (rare)
        frame_pixels = self._drag_frame.get_pixel_data()
        return frame_pixels[pixel_num] if pixel_num < len(frame_pixels) else (255, 0, 255, 255)

    def _update_drag_frame_pixel(self, pixel_num: int, color: tuple[int, ...]) -> None:
        """Update a single pixel in the drag frame with optimized paths.

        Args:
            pixel_num: Linear pixel index.
            color: New color tuple.

        """
        if self._drag_frame is None:
            return

        # Fast path: directly modify frame.pixels (avoids array copies)
        if hasattr(self._drag_frame, 'pixels'):
            if pixel_num < len(self._drag_frame.pixels):
                self._drag_frame.pixels[pixel_num] = color
                if not hasattr(self._drag_frame, '_image_stale'):
                    self._drag_frame._image_stale = True  # type: ignore[attr-defined]
            return

        # Fallback: slower get/set_pixel_data path
        frame_pixels = self._drag_frame.get_pixel_data()
        if pixel_num < len(frame_pixels):
            frame_pixels[pixel_num] = color
            self._drag_frame.set_pixel_data(frame_pixels)
            self._clear_surface_cache()

    def _clear_surface_cache(self) -> None:
        """Clear the surface cache entry for the current animation frame."""
        if hasattr(self, 'animated_sprite') and hasattr(self.animated_sprite, '_surface_cache'):
            cache_key = f'{self.current_animation}_{self.current_frame}'
            if cache_key in self.animated_sprite._surface_cache:  # type: ignore[reportPrivateUsage]
                del self.animated_sprite._surface_cache[cache_key]  # type: ignore[reportPrivateUsage]

    def _rebuild_frame_image_from_pixels(self, frame: SpriteFrame) -> None:
        """Rebuild a frame's image surface from its pixel data.

        Args:
            frame: The frame object with pixels and _image attributes.

        """
        if not (hasattr(frame, 'pixels') and hasattr(frame, '_image') and frame._image is not None):  # type: ignore[reportPrivateUsage]
            return

        width, height = frame._image.get_size()  # type: ignore[reportPrivateUsage]
        for i, pixel in enumerate(frame.pixels):
            if i < width * height:
                frame._image.set_at((i % width, i // width), pixel)  # type: ignore[reportPrivateUsage]

        # Clear stale flag since image is now up to date
        if hasattr(frame, '_image_stale'):
            del frame._image_stale  # type: ignore[attr-defined]

    @override
    def on_left_mouse_drag_event(self, event: events.HashableEvent, trigger: object) -> None:
        """Handle mouse drag events.

        Optimized path that updates visuals but defers expensive ops.
        """
        if not self.rect.collidepoint(event.pos):
            return

        x = (event.pos[0] - self.rect.x) // self.pixel_width
        y = (event.pos[1] - self.rect.y) // self.pixel_height

        if not (0 <= x < self.pixels_across and 0 <= y < self.pixels_tall):
            return

        self._drag_active = True
        if not hasattr(self, '_drag_pixels'):
            self._drag_pixels = {}  # Already typed in on_left_mouse_button_down_event

        self._cache_drag_frame()

        pixel_key = (x, y)
        pixel_num = y * self.pixels_across + x

        # Store pixel change with old color (only once per unique pixel during drag)
        if pixel_key not in self._drag_pixels:
            old_color = self._get_old_pixel_color(pixel_num)
            self._drag_pixels[pixel_key] = (x, y, old_color, self.active_color)

        # Update pixel data for immediate visual feedback
        self.pixels[pixel_num] = self.active_color
        self.dirty_pixels[pixel_num] = True

        # Update frame data immediately so renderer shows the change
        self._update_drag_frame_pixel(pixel_num, self.active_color)

        # Throttle full redraws during drag - only redraw every 3 drag events
        if not hasattr(self, '_drag_redraw_counter'):
            self._drag_redraw_counter = 0
        self._drag_redraw_counter += 1

        if self._drag_redraw_counter % 3 == 0:
            if self._drag_frame is not None:
                self._rebuild_frame_image_from_pixels(self._drag_frame)

            self.dirty = 1
            if hasattr(self, 'parent_scene') and self.parent_scene:
                self.parent_scene._update_film_strips_for_pixel_update()  # type: ignore[reportPrivateUsage]

    def _flush_batched_drag_pixels(self) -> None:
        """Apply all batched pixel changes from a drag operation to the sprite frame."""
        if not hasattr(self, 'animated_sprite'):
            return

        current_animation = self.current_animation
        current_frame_index = self.current_frame

        if current_animation not in self.animated_sprite.frames:
            return

        frame = self.animated_sprite._animations[current_animation][current_frame_index]  # type: ignore[reportPrivateUsage]
        frame_pixels = frame.get_pixel_data()

        for x, y, _old_color, new_color in self._drag_pixels.values():
            pixel_num = y * self.pixels_across + x
            if pixel_num < len(frame_pixels):
                frame_pixels[pixel_num] = new_color

        frame.set_pixel_data(frame_pixels)
        self._clear_surface_cache()

    def _sync_drag_frame_surface(self) -> None:
        """Sync the drag frame surface from pixels when fast-path was used."""
        if not (hasattr(self, '_drag_frame') and self._drag_frame is not None):
            return

        frame_obj = self._drag_frame
        if hasattr(frame_obj, 'pixels') and frame_obj.pixels:
            try:
                frame_obj.set_pixel_data(list(frame_obj.pixels))
            except (AttributeError, TypeError, ValueError) as sync_error:
                LOG.debug(f'Best-effort frame sync failed: {sync_error}')

    def _submit_drag_pixel_changes_to_undo(self) -> None:
        """Submit batched drag pixel changes to the undo/redo system."""
        if not (
            hasattr(self, 'parent_scene')
            and self.parent_scene
            and hasattr(self.parent_scene, 'canvas_operation_tracker')
            and not getattr(self.parent_scene, '_applying_undo_redo', False)
        ):
            return

        pixel_changes = list(self._drag_pixels.values())
        if not pixel_changes:
            return

        if not hasattr(self.parent_scene, '_current_pixel_changes'):
            self.parent_scene._current_pixel_changes = []  # type: ignore[reportPrivateUsage]
        self.parent_scene._current_pixel_changes.extend(pixel_changes)  # type: ignore[reportPrivateUsage]

        if hasattr(self.parent_scene, '_submit_pixel_changes_if_ready'):
            self.parent_scene._submit_pixel_changes_if_ready()  # type: ignore[reportPrivateUsage]

    def _cleanup_drag_state(self) -> None:
        """Clear all drag-related state and ensure frame image is up to date."""
        self._drag_active = False
        self._drag_pixels = {}  # Already typed in on_left_mouse_button_down_event
        if hasattr(self, '_drag_redraw_counter'):
            del self._drag_redraw_counter
        if hasattr(self, '_drag_frame'):
            if self._drag_frame is not None:
                self._rebuild_frame_image_from_pixels(self._drag_frame)
            if hasattr(self._drag_frame, '_image_stale'):
                del self._drag_frame._image_stale  # type: ignore[reportPrivateUsage]
            del self._drag_frame

    @override
    def on_left_mouse_button_up_event(self, event: events.HashableEvent) -> None:
        """Handle mouse button up - flush batched drag updates."""
        if not (hasattr(self, '_drag_active') and self._drag_active):
            return

        if hasattr(self, '_drag_pixels') and self._drag_pixels:
            self._flush_batched_drag_pixels()
        else:
            self._sync_drag_frame_surface()
            self._submit_drag_pixel_changes_to_undo()

            if hasattr(self, 'animated_sprite'):
                self._update_animated_sprite_frame()

            if hasattr(self, 'parent_scene') and self.parent_scene:
                self.parent_scene._update_film_strips_for_pixel_update()  # type: ignore[reportPrivateUsage]

        self._cleanup_drag_state()
        self.dirty = 1

    @override
    def on_mouse_motion_event(self, event: events.HashableEvent) -> None:
        """Handle mouse motion events."""
        if self.rect.collidepoint(event.pos):
            # Mouse is over canvas - set hover state
            if not self.is_hovered:
                self.is_hovered = True
                self.dirty = 1  # Mark for redraw to show canvas border
                # Hide mouse cursor when entering canvas
                pygame.mouse.set_visible(False)

            # Convert mouse position to pixel coordinates
            x = (event.pos[0] - self.rect.x) // self.pixel_width
            y = (event.pos[1] - self.rect.y) // self.pixel_height

            # Check if the coordinates are within valid range
            if 0 <= x < self.pixels_across and 0 <= y < self.pixels_tall:
                # Update hovered pixel for white border effect
                self.hovered_pixel = (x, y)
                self.dirty = 1  # Mark for redraw to show hover effect

            # Mouse is over canvas but outside pixel grid - clear pixel hover
            elif hasattr(self, 'hovered_pixel') and self.hovered_pixel is not None:
                self.hovered_pixel = None
                self.dirty = 1  # Mark for redraw to remove pixel hover effect
        else:
            # Mouse is outside canvas - clear all hover effects
            if self.is_hovered:
                self.is_hovered = False
                self.dirty = 1  # Mark for redraw to remove canvas border
                # Show mouse cursor when leaving canvas
                pygame.mouse.set_visible(True)

            if hasattr(self, 'hovered_pixel') and self.hovered_pixel is not None:
                self.hovered_pixel = None
                self.dirty = 1  # Mark for redraw to remove pixel hover effect

    def on_pixel_update_event(self, event: events.HashableEvent, trigger: object) -> None:
        """Handle pixel update events."""
        if hasattr(trigger, 'pixel_number'):
            pixel_num: int = trigger.pixel_number  # type: ignore[union-attr]
            new_color: tuple[int, ...] = trigger.pixel_color  # type: ignore[union-attr]
            # self.log.debug(f"Animated canvas updating pixel {pixel_num} to color {new_color}")

            self.pixels[pixel_num] = new_color
            self.dirty_pixels[pixel_num] = True
            self.dirty = 1

            # Notify parent scene to update film strips
            if hasattr(self, 'parent_scene') and self.parent_scene:
                self.parent_scene._update_film_strips_for_pixel_update()  # type: ignore[reportPrivateUsage]

            # Update the animated sprite's frame data
            if hasattr(self, 'animated_sprite'):
                self._update_animated_sprite_frame()

    def on_mouse_leave_window_event(self, event: events.HashableEvent) -> None:
        """Handle mouse leaving window event."""

    def on_mouse_enter_sprite_event(self, event: events.HashableEvent) -> None:
        """Handle mouse entering canvas."""

    def on_mouse_exit_sprite_event(self, event: events.HashableEvent) -> None:
        """Handle mouse exiting canvas."""

    def _sync_all_frames_pixel_data(self) -> None:
        """Ensure all frames have their pixel data synchronized from pixels to surface.

        This is critical before saving because get_pixel_data() may read from
        frame.pixels if it exists, but we need to ensure _image is also up to date.

        For frames that don't have pixels attribute, we extract from _image first,
        then sync to ensure consistency.

        CRITICAL: If ANY frame has alpha pixels, normalize ALL frames to RGBA format
        to ensure consistent color map matching during save.
        """
        if not hasattr(self, 'animated_sprite') or not self.animated_sprite:
            return

        try:
            # Sync frames using ONLY the raw pixel data in memory
            # Don't extract from _image - just use frame.pixels if it exists
            # set_pixel_data() will update _image to match pixels
            for frames in self.animated_sprite._animations.values():  # type: ignore[reportPrivateUsage]
                for frame in frames:
                    try:
                        # Only sync if frame already has pixels in memory
                        # Don't extract from _image - use the raw pixel data we have
                        if hasattr(frame, 'pixels') and frame.pixels:
                            # Just sync pixels to surface - set_pixel_data updates _image to match
                            # pixels
                            # This ensures _image matches what's in frame.pixels
                            frame.set_pixel_data(list(frame.pixels))
                        # If frame doesn't have pixels, leave it alone - it will use
                        # get_pixel_data()
                        # which will extract from _image when needed, preserving original indexed
                        # colors
                    except (AttributeError, TypeError, ValueError) as frame_sync_error:
                        # Best-effort sync; continue if frame cannot be updated
                        LOG.debug(f'Best-effort frame sync failed: {frame_sync_error}')
                        continue
        except (AttributeError, KeyError, TypeError) as sync_error:
            # Best-effort sync; continue even if some frames fail
            LOG.debug(f'Best-effort pixel-to-surface sync failed: {sync_error}')

    def on_save_file_event(self, filename: str) -> None:
        """Handle save file events.

        Raises:
            OSError: If an I/O error occurs while saving.
            ValueError: If the sprite data is invalid for saving.
            KeyError: If a required key is missing during serialization.

        """
        self.log.info(f'Starting save to file: {filename}')
        try:
            # CRITICAL: Sync all frame pixel data before saving
            # This ensures that any direct modifications to frame.pixels during drag
            # are properly reflected in the frame surface, which get_pixel_data() may read from
            self._sync_all_frames_pixel_data()

            # Detect file format from extension
            file_format = detect_file_format(filename)
            self.log.info(f'Detected file format: {file_format}')

            # Check if this is a single-frame animation (converted from static sprite)
            if self._is_single_frame_animation():
                self.log.info('Detected single-frame animation, saving as static sprite')
                self._save_as_static_sprite(filename, file_format)
            else:
                # Use the interface-based save method for multi-frame animations
                self.sprite_serializer.save(
                    self.animated_sprite,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
                    filename=filename,
                    file_format=file_format,
                )
        except (OSError, ValueError, KeyError):
            self.log.exception('Error saving file')
            raise

    def get_canvas_interface(self) -> AnimatedCanvasInterface:
        """Get the canvas interface for external access.

        Returns:
            AnimatedCanvasInterface: The canvas interface.

        """
        return self.canvas_interface

    def get_sprite_serializer(self) -> AnimatedSpriteSerializer:
        """Get the sprite serializer for external access.

        Returns:
            AnimatedSpriteSerializer: The sprite serializer.

        """
        return self.sprite_serializer

    def get_canvas_renderer(self) -> AnimatedCanvasRenderer:
        """Get the canvas renderer for external access.

        Returns:
            AnimatedCanvasRenderer: The canvas renderer.

        """
        return self.canvas_renderer

    def on_load_file_event(self, event: events.HashableEvent, trigger: object = None) -> None:
        """Handle load file event for animated sprites."""
        self.log.debug('=== Starting on_load_file_event for animated sprite ===')
        LOG.debug(f'DEBUG: Canvas on_load_file_event called with event: {event}')
        try:
            filename = event if isinstance(event, str) else event.text
            LOG.debug(f'DEBUG: Loading sprite from filename: {filename}')

            # Load the sprite from file
            loaded_sprite = self._load_sprite_from_file(filename)

            # Set the loaded sprite as the current animated sprite
            self.animated_sprite = loaded_sprite

            # Check if canvas needs resizing and resize if necessary
            self._check_and_resize_canvas(loaded_sprite)

            # Set up animation state
            self._setup_animation_state(loaded_sprite)

            # Update UI components
            self._update_ui_components(loaded_sprite)

            # Finalize the loading process
            self._finalize_sprite_loading(loaded_sprite, filename)

        except FileNotFoundError as e:
            self.log.exception('File not found')
            # Show user-friendly error message instead of crashing
            if hasattr(self, 'parent') and hasattr(self.parent, 'debug_text'):
                self.parent.debug_text.text = f'Error: File not found - {e}'
        except (OSError, ValueError, KeyError, TypeError, AttributeError, pygame.error) as e:
            self.log.exception('Error in on_load_file_event for animated sprite')
            self.log.exception(f'Exception type: {type(e).__name__}')
            import traceback

            self.log.exception(f'Traceback: {traceback.format_exc()}')
            # Show user-friendly error message instead of crashing
            if hasattr(self, 'parent') and hasattr(self.parent, 'debug_text'):
                self.parent.debug_text.text = f'Error loading sprite: {e}'

    def _load_sprite_from_file(self, filename: str) -> AnimatedSprite:
        """Load an animated sprite from a file.

        Args:
            filename: Path to the sprite file to load

        Returns:
            Loaded AnimatedSprite instance

        Raises:
            ValueError: If PNG conversion fails or other loading errors occur.

        """
        self.log.debug(f'Loading animated sprite from {filename}')

        # Check if this is a PNG file and convert it first
        if filename.lower().endswith('.png'):
            self.log.info('PNG file detected - converting to bitmappy format first')
            converted_toml_path = self._convert_png_to_bitmappy(filename)  # type: ignore[attr-defined]
            if converted_toml_path:
                filename = converted_toml_path  # type: ignore[assignment]
                self.log.info(f'Using converted TOML file: {filename}')
            else:
                raise ValueError('Failed to convert PNG to bitmappy format')

        # Detect file format and load the sprite
        file_format = detect_file_format(filename)  # type: ignore[arg-type]
        self.log.debug(f'Detected file format: {file_format}')

        # Create a new animated sprite and load it
        loaded_sprite = AnimatedSprite()
        loaded_sprite.load(filename)  # type: ignore[arg-type]

        # Debug: Check what was loaded
        self.log.debug(f'Loaded sprite has _animations: {hasattr(loaded_sprite, "_animations")}')
        if hasattr(loaded_sprite, '_animations'):
            self.log.debug(f'Loaded sprite _animations: {list(loaded_sprite._animations.keys())}')  # type: ignore[reportPrivateUsage]
            self.log.debug(f'Loaded sprite current_animation: {loaded_sprite.current_animation}')
            self.log.debug(f'Loaded sprite is_playing: {loaded_sprite.is_playing}')

        return loaded_sprite

    def _check_and_resize_canvas(self, loaded_sprite: AnimatedSprite) -> None:
        """Check if canvas needs resizing and resize if necessary.

        Args:
            loaded_sprite: The loaded sprite to check dimensions against

        """
        # Check if the loaded sprite has different dimensions than the canvas
        if (
            loaded_sprite._animations  # type: ignore[reportPrivateUsage]
            and loaded_sprite.current_animation in loaded_sprite._animations  # type: ignore[reportPrivateUsage]
        ):
            first_frame = loaded_sprite._animations[loaded_sprite.current_animation][0]  # type: ignore[reportPrivateUsage]
            sprite_width, sprite_height = first_frame.get_size()
            self.log.debug(f'Loaded sprite dimensions: {sprite_width}x{sprite_height}')
            self.log.debug(f'Canvas dimensions: {self.pixels_across}x{self.pixels_tall}')

            # If sprite has different dimensions than canvas, resize canvas to match
            if sprite_width != self.pixels_across or sprite_height != self.pixels_tall:
                self.log.info(
                    f'Resizing canvas from {self.pixels_across}x{self.pixels_tall} to '
                    f'{sprite_width}x{sprite_height}'
                )
                self._resize_canvas_to_sprite_size(sprite_width, sprite_height)
        else:
            # No frames or animation - but the animated sprite loader already converted it
            self.log.info('Using already-converted animated sprite from static sprite')

            # Check if we need to resize the canvas
            if hasattr(loaded_sprite, 'get_size'):
                sprite_width, sprite_height = loaded_sprite.get_size()  # type: ignore[union-attr]
                self.log.debug(f'Static sprite dimensions: {sprite_width}x{sprite_height}')
                self.log.debug(f'Canvas dimensions: {self.pixels_across}x{self.pixels_tall}')

                # If sprite has different dimensions than canvas, resize canvas to match
                if sprite_width != self.pixels_across or sprite_height != self.pixels_tall:
                    self.log.info(
                        f'Resizing canvas from {self.pixels_across}x{self.pixels_tall} to '
                        f'{sprite_width}x{sprite_height}'
                    )
                    self._resize_canvas_to_sprite_size(sprite_width, sprite_height)  # type: ignore[arg-type]

    def _update_ui_components(self, loaded_sprite: AnimatedSprite) -> None:
        """Update UI components after loading a sprite.

        Args:
            loaded_sprite: The loaded sprite to update UI components with

        """
        # Update multiple film strips
        if hasattr(self, 'film_strips') and self.film_strips:  # type: ignore[attr-defined]
            for film_strip in self.film_strips.values():  # type: ignore[attr-defined]
                film_strip.mark_dirty()  # type: ignore[union-attr]
        if hasattr(self, 'film_strip_sprites') and self.film_strip_sprites:  # type: ignore[attr-defined]
            for film_strip_sprite in self.film_strip_sprites.values():  # type: ignore[attr-defined]
                film_strip_sprite.dirty = 1

        # Note: Live preview functionality is now integrated into the film strip

        # Clear existing multiple film strips and recreate them
        if hasattr(self, 'film_strips') and self.film_strips:  # type: ignore[attr-defined]
            # Clear existing film strips
            for film_strip_sprite in self.film_strip_sprites.values():  # type: ignore[attr-defined]
                if hasattr(film_strip_sprite, 'groups') and film_strip_sprite.groups():  # type: ignore[union-attr]
                    for group in film_strip_sprite.groups():  # type: ignore[union-attr]
                        group.remove(film_strip_sprite)  # type: ignore[union-attr]
            self.film_strips.clear()  # type: ignore[attr-defined]
            self.film_strip_sprites.clear()  # type: ignore[attr-defined]

        # Film strips will be created by the parent scene

        # Notify parent scene about sprite load
        LOG.debug(
            f'DEBUG: Checking callbacks - hasattr(parent_scene): {hasattr(self, "parent_scene")},'
            f' hasattr(on_sprite_loaded): {hasattr(self, "on_sprite_loaded")}'
        )
        if hasattr(self, 'parent_scene') and self.parent_scene:
            self.log.debug('Calling parent scene _on_sprite_loaded')
            LOG.debug('DEBUG: Calling parent scene _on_sprite_loaded')
            self.parent_scene._on_sprite_loaded(loaded_sprite)  # type: ignore[reportPrivateUsage]
        elif hasattr(self, 'on_sprite_loaded') and self.on_sprite_loaded:  # type: ignore[attr-defined]
            self.log.debug('Calling on_sprite_loaded callback')
            LOG.debug('DEBUG: Calling on_sprite_loaded callback')
            self.on_sprite_loaded(loaded_sprite)  # type: ignore[attr-defined]
        else:
            LOG.debug(
                'DEBUG: No callback found - hasattr(parent_scene):'
                f' {hasattr(self, "parent_scene")}, hasattr(on_sprite_loaded):'
                f' {hasattr(self, "on_sprite_loaded")}'
            )
            self.log.debug('No parent scene or callback found')

    def _setup_animation_state(self, loaded_sprite: AnimatedSprite) -> None:
        """Set up animation state after loading a sprite.

        Args:
            loaded_sprite: The loaded sprite to set up animation for

        """
        # Update the canvas sprite's current animation to match the loaded sprite
        self.current_animation = loaded_sprite.current_animation
        self.log.debug(f'Updated canvas animation to: {self.current_animation}')

        # Debug: Print available animations
        available_animations = (
            list(loaded_sprite._animations.keys()) if hasattr(loaded_sprite, '_animations') else []  # type: ignore[reportPrivateUsage]
        )
        self.log.info(f'AVAILABLE ANIMATIONS: {available_animations}')
        self.log.info(f"CURRENT CANVAS ANIMATION: '{self.current_animation}'")

        # Start the animation after loading
        if loaded_sprite.current_animation:
            # Ensure looping is enabled before starting
            loaded_sprite._is_looping = True  # type: ignore[reportPrivateUsage]
            loaded_sprite.play()
            self.log.debug(
                f"Started animation '{loaded_sprite.current_animation}' using play() method"
            )
            # Verify animation state immediately after starting
            self.log.debug(
                f'Animation state after play(): is_playing={loaded_sprite.is_playing}, '
                f'is_looping={loaded_sprite._is_looping}, '  # type: ignore[reportPrivateUsage]
                f'current_frame={loaded_sprite.current_frame}'
            )

    def _finalize_sprite_loading(self, loaded_sprite: AnimatedSprite, filename: str) -> None:
        """Finalize sprite loading process.

        Args:
            loaded_sprite: The loaded sprite
            filename: The filename that was loaded

        """
        # Now copy the sprite data to canvas with the correct animation
        self._copy_sprite_to_canvas()
        self.dirty = 1
        self.force_redraw()

        # Force a complete redraw
        self.dirty = 1
        self.force_redraw()

        self.log.info(f'Successfully loaded animated sprite from {filename}')

        # Update AI textbox with sprite description or default prompt
        self.log.debug('Checking parent and debug_text access...')
        self.log.debug(f"hasattr(self, 'parent_scene'): {hasattr(self, 'parent_scene')}")
        if hasattr(self, 'parent_scene'):
            self.log.debug(
                "hasattr(self.parent_scene, 'debug_text'):"
                f' {hasattr(self.parent_scene, "debug_text")}'
            )
            self.log.debug(f'self.parent_scene type: {type(self.parent_scene)}')

        if hasattr(self, 'parent_scene') and hasattr(self.parent_scene, 'debug_text'):
            assert self.parent_scene is not None
            # Get description from loaded sprite, or use default prompt if empty
            description = getattr(loaded_sprite, 'description', '')
            self.log.debug(f"Loaded sprite description: '{description}'")
            self.log.debug(f'Description is not empty: {bool(description and description.strip())}')
            if description and description.strip():
                self.log.info(f"Setting AI textbox to description: '{description}'")
                self.parent_scene.debug_text.text = description
            else:
                self.log.info('Setting AI textbox to default prompt')
                self.parent_scene.debug_text.text = (
                    'Enter a description of the sprite you want to create:'
                )
        else:
            self.log.warning('Cannot access parent or debug_text - description not updated')

    def _resize_canvas_to_sprite_size(self, sprite_width: int, sprite_height: int) -> None:
        """Resize the canvas to match the sprite dimensions."""
        self.log.debug(f'Resizing canvas to {sprite_width}x{sprite_height}')

        # Update canvas dimensions
        self.pixels_across = sprite_width
        self.pixels_tall = sprite_height

        # Get screen dimensions directly from pygame display
        screen = pygame.display.get_surface()
        assert screen is not None
        screen_width = screen.get_width()
        screen_height = screen.get_height()

        # Recalculate pixel dimensions to fit the screen
        available_height = screen_height - 80 - 24  # Adjust for bottom margin and menu bar
        # ===== DEBUG: CANVAS SIZING CALCULATIONS =====
        LOG.debug('===== DEBUG: CANVAS SIZING CALCULATIONS =====')
        LOG.debug(f'Screen: {screen_width}x{screen_height}, Sprite: {sprite_width}x{sprite_height}')
        LOG.debug(f'Available height: {available_height}')
        LOG.debug(f'Height constraint: {available_height // sprite_height}')
        LOG.debug(f'Width constraint: {(screen_width * 1 // 2) // sprite_width}')
        LOG.debug(f'320x320 constraint: {320 // max(sprite_width, sprite_height)}')

        # For large sprites (128x128), ensure we get at least 2x2 pixel size
        if sprite_width >= LARGE_SPRITE_DIMENSION and sprite_height >= LARGE_SPRITE_DIMENSION:
            pixel_size = MIN_PIXEL_DISPLAY_SIZE  # Force 2x2 pixel size for 128x128
            LOG.debug('*** FORCING 2x2 pixel size for 128x128 sprite ***')
        else:
            pixel_size = min(
                available_height // sprite_height,
                (screen_width * 1 // 2) // sprite_width,
                # Maximum canvas size constraint: 320x320
                320 // max(sprite_width, sprite_height),
            )
            LOG.debug(f'Calculated pixel_size: {pixel_size}')
        # Ensure minimum pixel size of 1x1
        pixel_size = max(pixel_size, 1)

        LOG.debug(f'Final pixel_size: {pixel_size}')
        LOG.debug(f'Canvas will be: {sprite_width * pixel_size}x{sprite_height * pixel_size}')
        LOG.debug('===== END DEBUG =====\n')

        # Update pixel dimensions
        self.pixel_width = pixel_size
        self.pixel_height = pixel_size

        # Create new pixel arrays
        self.pixels = [(255, 0, 255, 255)] * (  # ty: ignore[invalid-assignment]
            sprite_width * sprite_height
        )  # Initialize with magenta
        self.dirty_pixels = [True] * (sprite_width * sprite_height)

        # Update surface dimensions
        actual_width = sprite_width * pixel_size
        actual_height = sprite_height * pixel_size
        LOG.debug('===== DEBUG: SURFACE CREATION =====')
        LOG.debug(f'Creating surface: {actual_width}x{actual_height}')
        LOG.debug(f'pixel_size: {pixel_size}, sprite: {sprite_width}x{sprite_height}')
        self.image = pygame.Surface((actual_width, actual_height))
        LOG.debug('Surface created successfully')
        LOG.debug('===== END DEBUG =====\n')
        self.rect = self.image.get_rect(x=self.rect.x, y=self.rect.y)

        # Update class dimensions

        # Update AI sprite positioning after canvas resize
        if hasattr(self, 'parent_scene') and self.parent_scene:
            self.parent_scene._update_ai_sprite_position()  # type: ignore[reportPrivateUsage]
        AnimatedCanvasSprite.WIDTH = sprite_width  # ty: ignore[unresolved-attribute]
        AnimatedCanvasSprite.HEIGHT = sprite_height  # ty: ignore[unresolved-attribute]

        self.log.info(
            f'Canvas resized to {sprite_width}x{sprite_height} with pixel size {pixel_size}'
        )

    def _convert_static_to_animated(
        self, static_sprite: BitmappySprite, width: int, height: int
    ) -> AnimatedSprite:
        """Convert a static sprite to an animated sprite with 1 frame.

        Returns:
            AnimatedSprite: The result.

        """
        # Create new animated sprite
        animated_sprite = AnimatedSprite()

        # Get pixel data from static sprite
        if hasattr(static_sprite, 'get_pixel_data'):
            pixel_data = static_sprite.get_pixel_data()  # type: ignore[union-attr]
            self.log.debug(
                f'Got pixel data from get_pixel_data(): {len(pixel_data)} pixels, '  # type: ignore[arg-type]
                f'first few: {pixel_data[:5]}'
            )
        elif hasattr(static_sprite, 'pixels'):
            pixel_data = static_sprite.pixels.copy()
            self.log.debug(
                f'Got pixel data from pixels attribute: {len(pixel_data)} pixels, '
                f'first few: {pixel_data[:5]}'
            )
        else:
            # Fallback - create magenta pixels
            pixel_data = [(255, 0, 255)] * (width * height)
            self.log.debug(f'Using fallback magenta pixels: {len(pixel_data)} pixels')

        # Create a single frame with the static sprite data
        frame = SpriteFrame(surface=pygame.Surface((width, height), pygame.SRCALPHA))
        frame.set_pixel_data(pixel_data)  # type: ignore[arg-type]

        # Get the animation name from the static sprite if available
        animation_name = 'idle'  # Default fallback
        if hasattr(static_sprite, 'name') and static_sprite.name:
            animation_name = static_sprite.name
        elif hasattr(static_sprite, 'animation_name') and static_sprite.animation_name:  # type: ignore[union-attr]
            animation_name = static_sprite.animation_name  # type: ignore[union-attr]

        # Add the frame to the animated sprite with the correct animation name
        animated_sprite.add_frame(animation_name, frame)  # type: ignore[arg-type]

        # Set the current animation to the actual animation name
        animated_sprite.frame_manager.current_animation = animation_name  # ty: ignore[invalid-assignment]
        animated_sprite.frame_manager.current_frame = 0

        # Debug: Verify the conversion worked
        self.log.debug(
            f'Converted static sprite to animated format with 1 frame: {len(pixel_data)} pixels'  # type: ignore[arg-type]
        )
        self.log.debug(f'Animated sprite has frames: {hasattr(animated_sprite, "frames")}')
        if hasattr(animated_sprite, 'frames'):
            self.log.debug(f'Available animations: {list(animated_sprite._animations.keys())}')  # type: ignore[reportPrivateUsage]
            if 'idle' in animated_sprite._animations:  # type: ignore[reportPrivateUsage]
                self.log.debug(
                    f'Idle animation has {len(animated_sprite._animations["idle"])} frames'  # type: ignore[reportPrivateUsage]
                )
                if animated_sprite._animations['idle']:  # type: ignore[reportPrivateUsage]
                    frame_pixels = animated_sprite._animations['idle'][0].get_pixel_data()  # type: ignore[reportPrivateUsage]
                    self.log.debug(
                        f'First frame pixels: {len(frame_pixels)} pixels, '
                        f'first few: {frame_pixels[:5]}'
                    )

        return animated_sprite

    def _is_single_frame_animation(self) -> bool:
        """Check if this is a single-frame animation (converted from static sprite).

        Returns:
            bool: True if the condition is met, False otherwise.

        """
        if not hasattr(self, 'animated_sprite') or not self.animated_sprite:
            return False

        # Check if there's only one animation with one frame
        if hasattr(self.animated_sprite, '_animations') and self.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
            animations = list(self.animated_sprite._animations.keys())  # type: ignore[reportPrivateUsage]
            if len(animations) == 1 and len(self.animated_sprite._animations[animations[0]]) == 1:  # type: ignore[reportPrivateUsage]
                return True

        return False

    def _save_as_static_sprite(self, filename: str, file_format: str) -> None:
        """Save a single-frame animation as a static sprite.

        Raises:
            ValueError: If there is no animated sprite, no animations, or no frames to save.

        """
        if not hasattr(self, 'animated_sprite') or not self.animated_sprite:
            raise ValueError('No animated sprite to save')

        # Get the single frame
        animations = list(self.animated_sprite._animations.keys())  # type: ignore[reportPrivateUsage]
        if not animations:
            raise ValueError('No animations found')

        animation_name = animations[0]
        frames = self.animated_sprite._animations[animation_name]  # type: ignore[reportPrivateUsage]
        if not frames:
            raise ValueError('No frames found in animation')

        frame = frames[0]  # Get the first (and only) frame

        # Create an AnimatedSprite from the frame (since everything is AnimatedSprite now)
        # Create a new AnimatedSprite with the frame data
        animated_sprite = AnimatedSprite()

        # Set up the frame data using the sprite's name or a default
        animation_name = getattr(frame, 'name', 'frame') or 'frame'
        animated_sprite._animations = {animation_name: [frame]}  # type: ignore[reportPrivateUsage]
        animated_sprite.frame_manager.current_animation = animation_name
        animated_sprite.frame_manager.current_frame = 0

        # Preserve the description from the original sprite
        if hasattr(self.animated_sprite, 'description'):
            animated_sprite.description = self.animated_sprite.description
            self.log.debug(f"Preserved description: '{animated_sprite.description}'")

        # Update the sprite's image to match the frame
        animated_sprite.image = frame.image.copy()
        animated_sprite.rect = animated_sprite.image.get_rect()

        # Save using the animated sprite's save method
        animated_sprite.save(filename, file_format)
        self.log.info(f'Saved single-frame animation as static sprite to {filename}')

    def _copy_sprite_to_canvas(self) -> None:
        """Copy the current frame of the animated sprite to the canvas."""
        if not hasattr(self, 'animated_sprite') or not self.animated_sprite:
            return

        # Get the current frame pixels from the animated sprite
        current_frame_pixels = self._get_current_frame_pixels()
        if current_frame_pixels:
            # Copy the pixels to the canvas
            self.pixels = current_frame_pixels.copy()  # ty: ignore[invalid-assignment]
            self.dirty_pixels = [True] * len(self.pixels)
            self.dirty = 1  # Mark canvas as dirty for redraw
            self.log.debug(f'Copied {len(current_frame_pixels)} pixels to canvas')
            self.log.debug(
                f'Canvas pixels after copy: {self.pixels[:5] if self.pixels else "None"}'
            )
        else:
            self.log.warning('No current frame pixels to copy to canvas')

    def _build_surface_from_canvas_pixels(self) -> pygame.Surface:
        """Build a pygame Surface from current canvas pixel data.

        Returns:
            A new Surface with canvas pixels rendered, with alpha support.

        """
        surface = pygame.Surface((self.pixels_across, self.pixels_tall), pygame.SRCALPHA)
        magenta_keys = {(255, 0, 255), (255, 0, 255, 255)}
        for y in range(self.pixels_tall):
            for x in range(self.pixels_across):
                pixel_num = y * self.pixels_across + x
                if pixel_num >= len(self.pixels):
                    continue
                color = self.pixels[pixel_num]
                # Handle transparency key specially - keep it opaque
                if color in magenta_keys:
                    surface.set_at((x, y), (255, 0, 255, 255))
                else:
                    surface.set_at((x, y), color)
        return surface

    def _update_animated_sprite_frame(self) -> None:
        """Update the animated sprite's current frame with canvas data."""
        if not (
            hasattr(self, 'animated_sprite')
            and hasattr(self, 'current_animation')
            and hasattr(self, 'current_frame')
        ):
            return

        current_anim = self.current_animation
        current_frame = self.current_frame

        if not (
            current_anim
            and current_frame is not None  # type: ignore[reportUnnecessaryComparison]
            and current_anim in self.animated_sprite._animations  # type: ignore[reportPrivateUsage]
            and 0 <= current_frame < len(self.animated_sprite._animations[current_anim])  # type: ignore[reportPrivateUsage]
            and hasattr(self.animated_sprite._animations[current_anim][current_frame], 'image')  # type: ignore[reportPrivateUsage]
        ):
            return

        frame = self.animated_sprite._animations[current_anim][current_frame]  # type: ignore[reportPrivateUsage]
        frame.image = self._build_surface_from_canvas_pixels()

        if hasattr(self, 'parent_scene') and self.parent_scene:
            self.parent_scene._update_film_strips_for_animated_sprite_update()  # type: ignore[reportPrivateUsage]

    def get_canvas_surface(self) -> pygame.Surface:
        """Get the current canvas surface for the film strip.

        Returns:
            pygame.Surface: The canvas surface.

        """
        # Create a surface from the current canvas pixels with alpha support
        surface = pygame.Surface((self.pixels_across, self.pixels_tall), pygame.SRCALPHA)
        for y in range(self.pixels_tall):
            for x in range(self.pixels_across):
                pixel_num = y * self.pixels_across + x
                if pixel_num < len(self.pixels):
                    color = self.pixels[pixel_num]
                    # Handle transparency key specially - make it transparent for film strip
                    if color in {(255, 0, 255), (255, 0, 255, 255)}:
                        surface.set_at((x, y), (255, 0, 255, 0))  # Transparent magenta
                    else:
                        surface.set_at((x, y), color)
        return surface

    def _flood_fill(self, start_x: int, start_y: int, fill_color: tuple[int, int, int]) -> None:
        """Perform flood fill algorithm starting from the given coordinates.

        Args:
            start_x: Starting X coordinate
            start_y: Starting Y coordinate
            fill_color: Color to fill with

        """
        # Check bounds
        if not (0 <= start_x < self.pixels_across and 0 <= start_y < self.pixels_tall):
            self.log.warning(f'Flood fill coordinates out of bounds: ({start_x}, {start_y})')
            return

        # Get the target color (the color we're replacing)
        target_color = self.canvas_interface.get_pixel_at(start_x, start_y)

        # If target color is the same as fill color, no work needed
        if target_color == fill_color:
            self.log.info('Target color same as fill color, no flood fill needed')
            return

        self.log.info(
            f'Flood fill: replacing {target_color} with {fill_color} starting at ({start_x},'
            f' {start_y})'
        )

        # Use iterative flood fill with a stack to avoid recursion depth issues
        stack = [(start_x, start_y)]
        filled_pixels = 0

        while stack:
            x, y = stack.pop()

            # Check bounds and color match
            if (
                0 <= x < self.pixels_across
                and 0 <= y < self.pixels_tall
                and self.canvas_interface.get_pixel_at(x, y) == target_color
            ):
                # Fill this pixel
                self.canvas_interface.set_pixel_at(x, y, fill_color)
                filled_pixels += 1

                # Add adjacent pixels to stack (4-connected)
                stack.extend([
                    (x + 1, y),  # Right
                    (x - 1, y),  # Left
                    (x, y + 1),  # Down
                    (x, y - 1),  # Up
                ])

        self.log.info(f'Flood fill completed: filled {filled_pixels} pixels')

    def _initialize_panning_system(self) -> None:
        """Initialize the panning system for the canvas."""
        # Panning state
        self.pan_offset_x = 0  # Horizontal pan offset in pixels
        self.pan_offset_y = 0  # Vertical pan offset in pixels

        # Buffer dimensions (larger than canvas to allow panning)
        # Add extra space around the canvas for panning
        self.buffer_width = self.pixels_across + 20  # Extra 10 pixels on each side
        self.buffer_height = self.pixels_tall + 20  # Extra 10 pixels on each side

        # Viewport dimensions (same as canvas dimensions)
        self.viewport_width = self.pixels_across
        self.viewport_height = self.pixels_tall

        # Panning state flag
        self._panning_active = False

        # Initialize buffer with transparent pixels
        self._buffer_pixels = [
            (255, 0, 255, 255) for _ in range(self.buffer_width * self.buffer_height)
        ]

        # Copy current canvas pixels to center of buffer
        if hasattr(self, 'pixels') and self.pixels:
            buffer_center_x = (self.buffer_width - self.pixels_across) // 2
            buffer_center_y = (self.buffer_height - self.pixels_tall) // 2

            for y in range(self.pixels_tall):
                for x in range(self.pixels_across):
                    buffer_x = buffer_center_x + x
                    buffer_y = buffer_center_y + y
                    buffer_index = buffer_y * self.buffer_width + buffer_x
                    canvas_index = y * self.pixels_across + x

                    if buffer_index < len(self._buffer_pixels) and canvas_index < len(self.pixels):
                        self._buffer_pixels[buffer_index] = self.pixels[canvas_index]  # type: ignore[index]

        self.log.debug(
            f'Panning system initialized: buffer={self.buffer_width}x{self.buffer_height},'
            f' viewport={self.viewport_width}x{self.viewport_height}'
        )

    def pan_canvas(self, delta_x: int, delta_y: int) -> None:
        """Pan the canvas by the given delta values.

        Args:
            delta_x: Horizontal panning delta (-1, 0, or 1)
            delta_y: Vertical panning delta (-1, 0, or 1)

        """
        # Get current frame key
        frame_key = self._get_current_frame_key()

        # Get current pan offset from frame state (or default to 0, 0)
        if frame_key in self._frame_panning:
            current_pan_x = self._frame_panning[frame_key]['pan_x']
            current_pan_y = self._frame_panning[frame_key]['pan_y']
        else:
            current_pan_x = 0
            current_pan_y = 0

        # Calculate new pan offset
        new_pan_x = current_pan_x + delta_x
        new_pan_y = current_pan_y + delta_y

        # Check if panning is within bounds
        if self._can_pan(new_pan_x, new_pan_y):
            # Initialize frame panning state if needed
            if frame_key not in self._frame_panning:
                self._frame_panning[frame_key] = {
                    'pan_x': 0,
                    'pan_y': 0,
                    'original_pixels': None,
                    'active': False,
                }

            frame_state = self._frame_panning[frame_key]
            frame_state['pan_x'] = new_pan_x
            frame_state['pan_y'] = new_pan_y
            frame_state['active'] = True

            # Store original frame data if this is the first pan for this frame
            if frame_state['original_pixels'] is None:
                self._store_original_frame_data_for_frame(frame_key)

            # Apply panning transformation to show panned view
            self._apply_panning_view_for_frame(frame_key)
            self.dirty = 1
        else:
            self.log.debug(f'Cannot pan to ({new_pan_x}, {new_pan_y}) - out of bounds.')

    def _store_original_frame_data(self) -> None:
        """Store the original frame data before any panning."""
        if hasattr(self, 'pixels') and self.pixels:
            self._original_frame_pixels = list(self.pixels)
            self.log.debug('Stored original frame data for panning')

    def _apply_panning_view(self) -> None:
        """Apply panning transformation to show the panned view."""
        if not hasattr(self, '_original_frame_pixels'):
            return

        # Create panned view by shifting pixels
        panned_pixels: list[tuple[int, ...]] = []

        for y in range(self.pixels_tall):
            for x in range(self.pixels_across):
                # Calculate source coordinates (where to read from in original)
                source_x = x - self.pan_offset_x
                source_y = y - self.pan_offset_y

                # Check if source is within bounds
                if 0 <= source_x < self.pixels_across and 0 <= source_y < self.pixels_tall:
                    source_index = source_y * self.pixels_across + source_x
                    if source_index < len(self._original_frame_pixels):
                        panned_pixels.append(self._original_frame_pixels[source_index])
                    else:
                        panned_pixels.append((255, 0, 255))  # Transparent
                else:
                    panned_pixels.append((255, 0, 255))  # Transparent

        # Update canvas pixels with panned view
        self.pixels = panned_pixels
        self.dirty_pixels = [True] * len(self.pixels)

        self.log.debug(f'Applied panning view: offset=({self.pan_offset_x}, {self.pan_offset_y})')

    def _can_pan(self, new_pan_x: int, new_pan_y: int) -> bool:
        """Check if the new pan offset is within the allowed bounds.

        Returns:
            bool: True if the condition is met, False otherwise.

        """
        # For now, allow panning within reasonable bounds
        # Later we can add more sophisticated bounds checking
        max_pan = 10  # Maximum pan distance
        return abs(new_pan_x) <= max_pan and abs(new_pan_y) <= max_pan

    def _update_viewport_pixels(self) -> None:
        """Update the viewport pixels based on current panning offset."""
        if not self._panning_active:
            return

        # Clear viewport pixels
        viewport_pixels: list[tuple[int, ...]] = []

        # Calculate buffer center offset
        buffer_center_x = (self.buffer_width - self.pixels_across) // 2
        buffer_center_y = (self.buffer_height - self.pixels_tall) // 2

        # Fill viewport with pixels from buffer at pan offset
        for y in range(self.pixels_tall):
            for x in range(self.pixels_across):
                buffer_x = buffer_center_x + x + self.pan_offset_x
                buffer_y = buffer_center_y + y + self.pan_offset_y

                # Check if buffer coordinates are within bounds
                if 0 <= buffer_x < self.buffer_width and 0 <= buffer_y < self.buffer_height:
                    pixel_index = buffer_y * self.buffer_width + buffer_x
                    if pixel_index < len(self._buffer_pixels):
                        viewport_pixels.append(self._buffer_pixels[pixel_index])
                    else:
                        viewport_pixels.append((255, 0, 255))  # Transparent
                else:
                    viewport_pixels.append((255, 0, 255))  # Transparent

        # Update canvas pixels with viewport data
        self.pixels = viewport_pixels
        self.dirty_pixels = [True] * len(self.pixels)

        # Force redraw to update the visual display including borders
        self.force_redraw()

    def _save_viewport_sprite(self, filename: str) -> None:
        """Save only the viewport area when panning is active."""
        from glitchygames.sprites.animated import AnimatedSprite

        # Create a new animated sprite with viewport data
        viewport_sprite = AnimatedSprite()
        viewport_sprite.name = self.animated_sprite.name + '_viewport'
        viewport_sprite.description = f'Viewport of {self.animated_sprite.name} (panned)'

        # Copy viewport data for each animation
        for anim_name, frames in self.animated_sprite._animations.items():  # type: ignore[reportPrivateUsage]
            viewport_frames: list[SpriteFrame] = []
            for frame in frames:
                viewport_frame = self._create_viewport_frame(frame)
                viewport_frames.append(viewport_frame)
            viewport_sprite.add_animation(anim_name, viewport_frames)

        # Save the newly created viewport sprite
        self.sprite_serializer.save(viewport_sprite, filename, DEFAULT_FILE_FORMAT)  # type: ignore[arg-type]
        self.log.info(f'Viewport sprite saved to {filename}')

    def _create_viewport_frame(self, original_frame: SpriteFrame) -> SpriteFrame:
        """Create a frame containing only the viewport data.

        Returns:
            SpriteFrame: The result.

        """
        from glitchygames.sprites.animated import SpriteFrame

        # Get viewport pixel data
        viewport_pixels = self._get_viewport_pixels_from_frame(original_frame)

        # Create new frame with viewport dimensions
        new_frame = SpriteFrame(
            surface=pygame.Surface((self.pixels_across, self.pixels_tall), pygame.SRCALPHA),
            duration=original_frame.duration,
        )

        # Set viewport pixel data
        new_frame.set_pixel_data(viewport_pixels)  # ty: ignore[invalid-argument-type]

        return new_frame

    def _get_viewport_pixels_from_frame(
        self, frame: SpriteFrame
    ) -> list[tuple[int, int, int, int]]:
        """Get viewport pixels from a frame based on current panning offset.

        Returns:
            list[tuple[int, int, int, int]]: The viewport pixels from frame.

        """
        # Get the frame's pixel data
        frame_pixels = frame.get_pixel_data()
        frame_width, frame_height = frame.get_size()

        # Get current frame panning offset
        frame_key = self._get_current_frame_key()
        if frame_key in self._frame_panning and self._frame_panning[frame_key]['active']:
            pan_offset_x = self._frame_panning[frame_key]['pan_x']
            pan_offset_y = self._frame_panning[frame_key]['pan_y']
        else:
            pan_offset_x = 0
            pan_offset_y = 0

        # Create viewport pixels
        viewport_pixels: list[tuple[int, ...]] = []
        for y in range(self.pixels_tall):
            for x in range(self.pixels_across):
                buffer_x = x + pan_offset_x
                buffer_y = y + pan_offset_y

                # Check if buffer coordinates are within frame bounds
                if 0 <= buffer_x < frame_width and 0 <= buffer_y < frame_height:
                    pixel_index = buffer_y * frame_width + buffer_x
                    if pixel_index < len(frame_pixels):
                        viewport_pixels.append(frame_pixels[pixel_index])
                    else:
                        viewport_pixels.append((255, 0, 255))  # Transparent
                else:
                    viewport_pixels.append((255, 0, 255))  # Transparent

        return viewport_pixels  # type: ignore[return-value]


class BitmapEditorScene(Scene):
    """Bitmap Editor Scene.

    The scene expects a 'size' option in the format "WIDTHxHEIGHT" (e.g., "800x600")
    when initialized. This corresponds to the -s command line parameter.
    """

    log = LOG

    # Set your game name/version here.
    NAME = 'Bitmappy'
    VERSION = '1.0'

    def _setup_menu_bar(self) -> None:
        """Set up the menu bar and menu items."""
        menu_bar_height = 24  # Taller menu bar

        # Different heights for icon vs text items
        icon_height = 16  # Smaller height for icon
        menu_item_height = menu_bar_height  # Full height for text items

        # Different vertical offsets for icon vs text
        icon_y = (menu_bar_height - icon_height) // 2 - 2  # Center the icon and move up 2px
        menu_item_y = 0  # Text items use full height

        # Create the menu bar using the UI library's MenuBar
        self.menu_bar = MenuBar(
            name='Menu Bar',
            x=0,
            y=0,
            width=self.screen_width,
            height=menu_bar_height,
            groups=self.all_sprites,
        )

        # Add the raspberry icon with its specific height
        icon_path = resource_path('glitcygames', 'assets', 'raspberry.toml')
        self.menu_icon = MenuItem(
            name=None,
            x=4,  # Add 4px offset from left edge
            y=icon_y,
            width=16,
            height=icon_height,  # Use icon-specific height
            filename=str(icon_path),
            groups=self.all_sprites,
        )
        self.menu_bar.add_menu(self.menu_icon)

        # Add all menus with full height
        menu_item_x = 0  # Start at left edge
        icon_width = 16  # Width of the raspberry icon
        menu_spacing = 2  # Reduced spacing between items
        menu_item_width = 48
        border_offset = self.menu_bar.border_width  # Usually 2px

        # Start after icon, compensating for border
        menu_item_x = (icon_width + menu_spacing) - border_offset

        new_menu = MenuItem(
            name='New',
            x=menu_item_x,
            y=menu_item_y - border_offset,  # Compensate for y border too
            width=menu_item_width,
            height=menu_item_height,
            groups=self.all_sprites,
        )
        self.menu_bar.add_menu(new_menu)

        # Move to next position
        menu_item_x += menu_item_width + menu_spacing

        save_menu = MenuItem(
            name='Save',
            x=menu_item_x,
            y=menu_item_y - border_offset,
            width=menu_item_width,
            height=menu_item_height,
            groups=self.all_sprites,
        )
        self.menu_bar.add_menu(save_menu)

        # Move to next position
        menu_item_x += menu_item_width + menu_spacing

        load_menu = MenuItem(
            name='Load',
            x=menu_item_x,
            y=menu_item_y - border_offset,
            width=menu_item_width,
            height=menu_item_height,
            groups=self.all_sprites,
        )
        self.menu_bar.add_menu(load_menu)

    def _setup_canvas(self, options: dict[str, Any]) -> None:
        """Set up the canvas sprite."""
        # Calculate canvas dimensions and pixel size
        pixels_across, pixels_tall, pixel_size = self._calculate_canvas_dimensions(options)

        # Create animated sprite with single frame
        animated_sprite = self._create_animated_sprite(pixels_across, pixels_tall)

        # Store the animated sprite as the shared instance
        self.animated_sprite = animated_sprite

        # Create the main canvas sprite
        self._create_canvas_sprite(animated_sprite, pixels_across, pixels_tall, pixel_size)

        # Finalize setup and start animation
        self._finalize_canvas_setup(animated_sprite, options)

    def _calculate_canvas_dimensions(self, options: dict[str, Any]) -> tuple[int, int, int]:
        """Calculate canvas dimensions and pixel size.

        Args:
            options: Dictionary containing canvas configuration

        Returns:
            Tuple of (pixels_across, pixels_tall, pixel_size)

        """
        menu_bar_height = 24
        bottom_margin = 80  # Space needed for sliders and color well
        available_height = (
            self.screen_height - bottom_margin - menu_bar_height
        )  # Use menu_bar_height instead of 32

        # Calculate pixel size to fit the canvas in the available space
        width, height = options['size'].split('x')
        pixels_across = int(width)
        pixels_tall = int(height)

        # ===== DEBUG: INITIAL CANVAS SIZING =====
        LOG.debug('===== DEBUG: INITIAL CANVAS SIZING =====')
        LOG.debug(
            f'Screen: {self.screen_width}x{self.screen_height}, Sprite:'
            f' {pixels_across}x{pixels_tall}'
        )
        LOG.debug(f'Available height: {available_height}')
        LOG.debug(f'Height constraint: {available_height // pixels_tall}')
        LOG.debug(f'Width constraint: {(self.screen_width * 1 // 2) // pixels_across}')
        LOG.debug(f'350px width constraint: {350 // pixels_across}')
        LOG.debug(f'320x320 constraint: {320 // max(pixels_across, pixels_tall)}')

        # Calculate pixel size based on available space
        pixel_size = min(
            available_height // pixels_tall,  # Height-based size
            # Width-based size (use 1/2 of screen width)
            (self.screen_width * 1 // 2) // pixels_across,
            # Maximum width constraint: 350px
            350 // pixels_across,
        )
        LOG.debug(f'Calculated pixel_size: {pixel_size}')

        # For very large sprites, ensure we get at least 2x2 pixel size
        if pixel_size < MIN_PIXEL_DISPLAY_SIZE:
            pixel_size = (
                MIN_PIXEL_DISPLAY_SIZE  # Force minimum 2x2 pixel size for very large sprites
            )
            LOG.debug('*** FORCING minimum 2x2 pixel size for large sprite ***')

        LOG.debug(f'Final pixel_size: {pixel_size}')
        LOG.debug(f'Canvas will be: {pixels_across * pixel_size}x{pixels_tall * pixel_size}')
        LOG.debug('===== END DEBUG =====\n')
        # Ensure minimum pixel size of 1x1
        pixel_size = max(pixel_size, 1)

        return pixels_across, pixels_tall, pixel_size

    @staticmethod
    def _create_animated_sprite(pixels_across: int, pixels_tall: int) -> AnimatedSprite:
        """Create animated sprite with single frame.

        Args:
            pixels_across: Number of pixels across the canvas
            pixels_tall: Number of pixels tall the canvas

        Returns:
            Configured AnimatedSprite instance

        """
        # Create single test frame with SRCALPHA for per-pixel alpha support
        surface1 = pygame.Surface((pixels_across, pixels_tall), pygame.SRCALPHA)
        surface1.fill(MAGENTA_TRANSPARENT)  # Magenta frame (transparent)
        frame1 = SpriteFrame(surface1)
        frame1.pixels = [MAGENTA_TRANSPARENT] * (pixels_across * pixels_tall)  # ty: ignore[invalid-assignment]

        # DEBUG: Log the first frame's pixel data
        LOG.info(f'DEBUG: First frame initialized with {len(frame1.pixels)} pixels')
        LOG.info(f'DEBUG: First few pixels: {frame1.pixels[:5]}')
        LOG.info(f'DEBUG: All pixels same color: {len(set(frame1.pixels)) == 1}')

        # Create animated sprite using proper initialization - single frame
        animated_sprite = AnimatedSprite()
        # Use the proper method to set up animations with single frame
        animation_name = 'strip_1'  # Use a generic name for new sprites
        animated_sprite._animations = {animation_name: [frame1]}  # type: ignore[reportPrivateUsage]
        animated_sprite._frame_interval = 0.5  # type: ignore[reportPrivateUsage]
        animated_sprite._is_looping = True  # type: ignore[reportPrivateUsage]  # Enable looping for the animation

        # Set up the frame manager properly
        animated_sprite.frame_manager.current_animation = animation_name
        animated_sprite.frame_manager.current_frame = 0

        # Initialize the sprite properly like a loaded sprite would be
        animated_sprite._update_surface_and_mark_dirty()  # type: ignore[reportPrivateUsage]

        # Start in a paused state initially
        animated_sprite.pause()

        return animated_sprite

    def _create_blank_frame(self, width: int, height: int, duration: float = 0.5) -> SpriteFrame:
        """Create a blank frame with magenta background and proper alpha support.

        This is the canonical method for creating blank frames to ensure consistency
        across the codebase and proper per-pixel alpha support.

        Args:
            width: Width of the frame in pixels
            height: Height of the frame in pixels
            duration: Frame duration in seconds (default: 0.5)

        Returns:
            A new SpriteFrame with magenta background and SRCALPHA support

        """
        from glitchygames.sprites.animated import SpriteFrame

        # Create surface with SRCALPHA to support per-pixel alpha transparency
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        surface.fill((255, 0, 255))  # Magenta background

        # Create the SpriteFrame
        frame = SpriteFrame(surface, duration=duration)

        # Initialize pixel data (magenta with full alpha)
        frame.pixels = [(255, 0, 255, 255)] * (width * height)  # ty: ignore[invalid-assignment]

        return frame

    def _create_canvas_sprite(
        self, animated_sprite: AnimatedSprite, pixels_across: int, pixels_tall: int, pixel_size: int
    ) -> None:
        """Create the main animated canvas sprite.

        Args:
            animated_sprite: The animated sprite to use
            pixels_across: Number of pixels across the canvas
            pixels_tall: Number of pixels tall the canvas
            pixel_size: Size of each pixel in screen coordinates

        """
        menu_bar_height = 24

        # Create the animated canvas with the calculated pixel dimensions
        self.canvas = AnimatedCanvasSprite(
            animated_sprite=animated_sprite,
            name='Animated Bitmap Canvas',
            x=0,
            y=menu_bar_height,  # Position canvas right below menu bar
            pixels_across=pixels_across,
            pixels_tall=pixels_tall,
            pixel_width=pixel_size,
            pixel_height=pixel_size,
            groups=self.all_sprites,
        )

        # Set parent scene reference for canvas
        self.canvas.parent_scene = self

        # Debug: Log canvas position and size
        self.log.info(
            'AnimatedCanvasSprite created at position '
            f'({self.canvas.rect.x}, {self.canvas.rect.y}) with size {self.canvas.rect.size}'
        )
        self.log.info(f'AnimatedCanvasSprite groups: {self.canvas.groups}')
        self.log.info(f'AnimatedCanvasSprite dirty: {self.canvas.dirty}')

    def _create_film_strips(self, groups: pygame.sprite.LayeredDirty | None) -> None:  # type: ignore[type-arg]
        """Create film strips for the current animated sprite - handles all loading scenarios."""
        self._log_film_strip_debug_state()

        if (
            not hasattr(self, 'canvas')
            or not self.canvas
            or not hasattr(self.canvas, 'animated_sprite')
            or not self.canvas.animated_sprite
        ):
            LOG.debug('DEBUG: _create_film_strips returning early - conditions not met')
            return

        animated_sprite = self.canvas.animated_sprite
        LOG.debug(f'DEBUG: _create_film_strips proceeding with animated_sprite: {animated_sprite}')

        self._ensure_default_animation_exists(animated_sprite)

        film_strip_x, film_strip_width = self._calculate_film_strip_dimensions()
        film_strip_y_start = self.canvas.rect.y  # Start at same vertical position as canvas

        # Calculate vertical spacing between strips
        strip_spacing = -19
        # Height of each film strip (increased by 20 pixels to
        # accommodate delete button and proper spacing)
        strip_height = 180

        # Create a separate film strip for each animation
        LOG.debug('DEBUG: Starting film strip creation loop')
        for strip_index, (anim_name, frames) in enumerate(animated_sprite._animations.items()):  # type: ignore[reportPrivateUsage]
            self._create_single_film_strip(  # type: ignore[arg-type]
                strip_index=strip_index,
                anim_name=anim_name,
                frames=frames,
                film_strip_x=film_strip_x,
                film_strip_y_start=int(film_strip_y_start),
                film_strip_width=film_strip_width,
                strip_height=strip_height,
                strip_spacing=strip_spacing,
                groups=groups,
            )

        # Create scroll arrows
        self._create_scroll_arrows()

        # CRITICAL: Ensure all film strip sprites are marked as dirty for initial render
        # This fixes the issue where film strips don't update on first load
        for film_strip_sprite in self.film_strip_sprites.values():
            film_strip_sprite.dirty = 2  # Full surface blit
            film_strip_sprite.force_redraw()

        # Update visibility to show only 2 strips at a time
        self._update_film_strip_visibility()

        # Select the first film strip and set its frame 0 as active
        LOG.debug('DEBUG: About to call _select_initial_film_strip')
        self._select_initial_film_strip()

        # OLD SYSTEM REMOVED - Using new multi-controller system instead

        LOG.debug('DEBUG: _create_film_strips completed successfully')

        # Reinitialize multi-controller system for existing controllers AFTER film strips are fully
        # set up
        # Pass preserved controller selections if available
        preserved_selections = getattr(self, '_preserved_controller_selections', None)
        self._reinitialize_multi_controller_system(preserved_selections)

    def _create_single_film_strip(
        self,
        *,
        strip_index: int,
        anim_name: str,
        frames: list[SpriteFrame],
        film_strip_x: int,
        film_strip_y_start: int,
        film_strip_width: int,
        strip_height: int,
        strip_spacing: int,
        groups: pygame.sprite.LayeredDirty | None,  # type: ignore[type-arg]
    ) -> None:
        """Create a single film strip widget and sprite for one animation.

        Args:
            strip_index: Index of this strip in the animation list
            anim_name: Name of the animation
            frames: List of animation frames
            film_strip_x: X position for the film strip
            film_strip_y_start: Starting Y position for film strips
            film_strip_width: Width of each film strip
            strip_height: Height of each film strip
            strip_spacing: Vertical spacing between strips
            groups: Sprite groups to add the film strip sprite to

        """
        LOG.debug(
            f'DEBUG: Creating film strip {strip_index} for animation {anim_name} with'
            f' {len(frames)} frames'
        )
        LOG.debug(
            f'Creating film strip {strip_index} for animation {anim_name} with {len(frames)} frames'
        )
        # Create a single animated sprite with just this animation
        # Use the proper constructor to ensure all attributes are initialized
        single_anim_sprite = AnimatedSprite()
        single_anim_sprite._animations = {anim_name: frames}  # type: ignore[reportPrivateUsage]
        single_anim_sprite._animation_order = [anim_name]  # type: ignore[reportPrivateUsage]  # Set animation order

        # Properly initialize the frame manager state
        single_anim_sprite.frame_manager.current_animation = anim_name
        single_anim_sprite.frame_manager.current_frame = 0

        # Set up the sprite to be ready for animation
        single_anim_sprite.set_animation(anim_name)
        single_anim_sprite.is_looping = True
        single_anim_sprite.play()

        # DEBUG: Log the sprite state
        LOG.debug(f'Created single_anim_sprite for {anim_name}:')
        LOG.debug(f'  _animations: {list(single_anim_sprite._animations.keys())}')  # type: ignore[reportPrivateUsage]
        LOG.debug(f'  _animation_order: {single_anim_sprite._animation_order}')  # type: ignore[reportPrivateUsage]
        LOG.debug(f'  current_animation: {single_anim_sprite.current_animation}')
        LOG.debug(f'  is_playing: {single_anim_sprite.is_playing}')
        LOG.debug(f'  is_looping: {single_anim_sprite.is_looping}')

        # Calculate Y position with scrolling
        base_y = film_strip_y_start + (strip_index * (strip_height + strip_spacing))
        scroll_y = base_y - (self.film_strip_scroll_offset * (strip_height + strip_spacing))

        # Create film strip widget for this animation
        film_strip = FilmStripWidget(
            x=film_strip_x, y=scroll_y, width=film_strip_width, height=strip_height
        )
        film_strip.set_animated_sprite(single_anim_sprite)
        film_strip.strip_index = strip_index  # type: ignore[attr-defined]  # Track which strip this is

        # CRITICAL FIX: Ensure all frames in the single animation sprite have proper image data
        # This fixes the issue where film strips show empty gray squares
        self._ensure_frames_have_image_data(single_anim_sprite)

        # Update the layout to calculate frame positions
        LOG.debug(f'Updating layout for film strip {strip_index} ({anim_name})')
        film_strip.update_layout()
        LOG.debug(
            f'Film strip {strip_index} layout updated, frame_layouts has'
            f' {len(film_strip.frame_layouts)} entries'
        )

        # Set parent scene reference for selection handling
        film_strip.parent_scene = self

        # Store the strip in the film strips dictionary
        self.film_strips[anim_name] = film_strip

        # Create film strip sprite for rendering
        film_strip_sprite = FilmStripSprite(
            film_strip_widget=film_strip,
            x=film_strip_x,
            y=scroll_y,
            width=film_strip_width,
            height=film_strip.rect.height,
            groups=groups,
        )

        # Debug: Check if film strip sprite was added to groups
        self.log.debug(
            f'Created film strip sprite for {anim_name}, groups: {film_strip_sprite.groups()}'
        )
        LOG.debug(
            f'DEBUG: Film strip sprite {anim_name} added to {len(film_strip_sprite.groups())}'
            f' groups: {film_strip_sprite.groups()}'
        )

        # Connect the film strip to the canvas
        film_strip_sprite.set_parent_canvas(self.canvas)
        film_strip.set_parent_canvas(self.canvas)

        # Set parent scene reference for the film strip sprite
        film_strip_sprite.parent_scene = self

        # Set parent scene reference for the film strip widget
        film_strip.parent_scene = self

        # Set up bidirectional reference between film strip widget and sprite
        film_strip.film_strip_sprite = film_strip_sprite
        film_strip_sprite.film_strip_widget = film_strip

        # Store the film strip sprite
        self.film_strip_sprites[anim_name] = film_strip_sprite

        # CRITICAL: Mark film strip sprite as dirty and force initial redraw
        # This ensures the film strip updates properly on first load
        film_strip_sprite.dirty = 2  # Full surface blit
        film_strip.mark_dirty()
        film_strip_sprite.force_redraw()

    def _log_film_strip_debug_state(self) -> None:
        """Log debug state for film strip creation diagnostics."""
        LOG.debug(f"DEBUG: hasattr(self, 'canvas'): {hasattr(self, 'canvas')}")
        if not hasattr(self, 'canvas'):
            return
        LOG.debug(f'DEBUG: self.canvas: {self.canvas}')
        if not self.canvas:
            return
        LOG.debug(
            "DEBUG: hasattr(self.canvas, 'animated_sprite'):"
            f' {hasattr(self.canvas, "animated_sprite")}'
        )
        if not hasattr(self.canvas, 'animated_sprite'):
            return
        LOG.debug(f'DEBUG: self.canvas.animated_sprite: {self.canvas.animated_sprite}')
        if not self.canvas.animated_sprite:
            return
        LOG.debug(
            "DEBUG: hasattr(self.canvas.animated_sprite, '_animations'):"
            f' {hasattr(self.canvas.animated_sprite, "_animations")}'
        )
        if hasattr(self.canvas.animated_sprite, '_animations'):
            LOG.debug(
                'DEBUG: self.canvas.animated_sprite._animations:'
                f' {self.canvas.animated_sprite._animations}'  # type: ignore[reportPrivateUsage]
            )

    def _ensure_default_animation_exists(self, animated_sprite: AnimatedSprite) -> None:
        """Ensure there's always at least one animation with one frame for film strip creation."""
        if hasattr(animated_sprite, '_animations') and animated_sprite._animations:  # type: ignore[reportPrivateUsage]
            return

        LOG.debug('DEBUG: No animations found, creating default animation with one frame')
        from glitchygames.sprites.animated import SpriteFrame

        frame_width = self.canvas.pixels_across
        frame_height = self.canvas.pixels_tall
        frame_surface = pygame.Surface((frame_width, frame_height))
        frame_surface.fill((255, 0, 255))  # Magenta background

        default_frame = SpriteFrame(frame_surface)
        default_frame.set_pixel_data([(255, 0, 255)] * (frame_width * frame_height))  # ty: ignore[invalid-argument-type]

        animated_sprite._animations = {'default': [default_frame]}  # type: ignore[reportPrivateUsage]
        animated_sprite._animation_order = ['default']  # type: ignore[reportPrivateUsage]
        animated_sprite.frame_manager.current_animation = 'default'
        animated_sprite.frame_manager.current_frame = 0

    def _calculate_film_strip_dimensions(self) -> tuple[int, int]:
        """Calculate the x position and width for film strips.

        Returns:
            Tuple of (film_strip_x, film_strip_width).

        """
        if hasattr(self, 'color_well') and self.color_well:
            film_strip_x = (
                self.color_well.rect.right + 1
            )  # Film strip left x = color well right x + 1
        else:
            film_strip_x = self.canvas.rect.right + 4  # 4 pixels to the right of canvas edge

        screen = pygame.display.get_surface()
        assert screen is not None
        screen_width = screen.get_width()
        available_width = screen_width - film_strip_x
        film_strip_width = max(300, available_width)

        return int(film_strip_x), int(film_strip_width)

    def _create_frame_image_from_pixels(self, frame: SpriteFrame, frame_idx: int) -> None:
        """Create a frame's image surface from its pixel data.

        Args:
            frame: The sprite frame object.
            frame_idx: Frame index for debug logging.

        """
        try:
            pixel_data = frame.get_pixel_data()
            if not pixel_data:
                return

            width, height = frame.get_size()
            surface = pygame.Surface((width, height), pygame.SRCALPHA)

            for i, color in enumerate(pixel_data):
                if i < width * height:
                    surface.set_at((i % width, i // width), color)

            frame.image = surface
            LOG.debug(f'DEBUG: Created image for frame {frame_idx} from pixel data')

        except (pygame.error, AttributeError, TypeError, ValueError, IndexError):
            LOG.exception(f'DEBUG: Failed to create image for frame {frame_idx}')

    def _create_default_magenta_frame(self, frame: SpriteFrame, frame_idx: int) -> None:
        """Create a default magenta frame image and pixel data.

        Args:
            frame: The sprite frame object.
            frame_idx: Frame index for debug logging.

        """
        try:
            width, height = frame.get_size()
            surface = pygame.Surface((width, height), pygame.SRCALPHA)
            surface.fill((255, 0, 255, 255))
            frame.image = surface

            pixel_data = [(255, 0, 255, 255)] * (width * height)
            frame.set_pixel_data(pixel_data)  # ty: ignore[invalid-argument-type]

            LOG.debug(f'DEBUG: Created default magenta frame for frame {frame_idx}')

        except (pygame.error, AttributeError, TypeError, ValueError):
            LOG.exception(f'DEBUG: Failed to create default frame for frame {frame_idx}')

    def _ensure_frames_have_image_data(self, animated_sprite: AnimatedSprite) -> None:
        """Ensure all frames in the animated sprite have proper image data.

        This fixes the issue where film strips show empty gray squares because
        frames don't have their image property properly set.
        """
        if not hasattr(animated_sprite, '_animations') or not animated_sprite._animations:  # type: ignore[reportPrivateUsage]
            return

        LOG.debug('DEBUG: Ensuring frames have image data')

        for anim_name, frames in animated_sprite._animations.items():  # type: ignore[reportPrivateUsage]
            LOG.debug(f"DEBUG: Checking animation '{anim_name}' with {len(frames)} frames")

            for frame_idx, frame in enumerate(frames):
                if not frame:
                    continue

                has_image = hasattr(frame, 'image') and frame.image is not None  # type: ignore[reportUnnecessaryComparison]
                has_pixel_data = (
                    hasattr(frame, 'get_pixel_data') and frame.get_pixel_data() is not None  # type: ignore[reportUnnecessaryComparison]
                )

                LOG.debug(
                    f'DEBUG: Frame {frame_idx}: has_image={has_image},'
                    f' has_pixel_data={has_pixel_data}'
                )

                if not has_image and has_pixel_data:
                    self._create_frame_image_from_pixels(frame, frame_idx)
                elif not has_image and not has_pixel_data:
                    self._create_default_magenta_frame(frame, frame_idx)

    def _select_initial_film_strip(self) -> None:
        """Select the first film strip and set its frame 0 as active on initialization."""
        if not hasattr(self, 'film_strips') or not self.film_strips:
            return

        # Get all animation names in order
        if hasattr(self, 'canvas') and self.canvas and hasattr(self.canvas, 'animated_sprite'):
            animation_names = list(self.canvas.animated_sprite._animations.keys())  # type: ignore[reportPrivateUsage]
        else:
            animation_names = list(self.film_strips.keys())

        if animation_names:
            first_animation = animation_names[0]

            # Select this animation and frame 0
            if hasattr(self, 'canvas') and self.canvas:
                self.canvas.show_frame(first_animation, 0)

            # Update global selection state
            self.selected_animation = first_animation
            self.selected_frame = 0

            # Mark all film strips as dirty so they redraw with correct selection state
            if hasattr(self, 'film_strips') and self.film_strips:
                for strip_widget in self.film_strips.values():
                    strip_widget.mark_dirty()

    def _update_film_strip_visibility(self) -> None:
        """Update which film strips are visible based on scroll offset."""
        if not hasattr(self, 'film_strips') or not self.film_strips:
            return

        # Get all animation names in order
        if hasattr(self, 'canvas') and self.canvas and hasattr(self.canvas, 'animated_sprite'):
            animation_names = list(self.canvas.animated_sprite._animations.keys())  # type: ignore[reportPrivateUsage]
        else:
            animation_names = list(self.film_strips.keys())

        # Show only the visible range of strips
        start_index = self.film_strip_scroll_offset
        end_index = min(start_index + self.max_visible_strips, len(animation_names))

        # Get canvas position for reference
        film_strip_y_start = (
            self.canvas.rect.y
            if hasattr(self, 'canvas') and self.canvas and self.canvas.rect is not None  # pyright: ignore[reportUnnecessaryComparison]
            else 0
        )
        strip_height = 145
        strip_spacing = -19

        # Hide all strips first
        for anim_name in self.film_strips:
            if hasattr(self, 'film_strip_sprites') and anim_name in self.film_strip_sprites:
                self.film_strip_sprites[anim_name].visible = False

        # Show only the visible strips and position them in fixed slots
        for i in range(start_index, end_index):
            if i < len(animation_names):
                anim_name = animation_names[i]
                if anim_name in self.film_strips and anim_name in self.film_strip_sprites:
                    film_strip = self.film_strips[anim_name]
                    film_strip_sprite = self.film_strip_sprites[anim_name]

                    # Position in fixed slot (0 or 1)
                    slot_index = i - start_index
                    fixed_y = film_strip_y_start + (slot_index * (strip_height + strip_spacing))

                    # Update positions
                    film_strip.rect.y = fixed_y
                    film_strip_sprite.rect.y = fixed_y
                    film_strip_sprite.visible = True

                    # Mark as dirty to ensure redraw
                    film_strip_sprite.dirty = 2
                    film_strip.mark_dirty()
                    # Force complete redraw to clear any old sprockets
                    film_strip._force_redraw = True  # type: ignore[reportPrivateUsage]

        # Update scroll arrows
        self._update_scroll_arrows()

    def _create_scroll_arrows(self) -> None:
        """Create scroll arrow sprites."""
        if not hasattr(self, 'canvas') or not self.canvas:
            return

        # Get canvas position for reference
        # Position film strip so its left x is 2 pixels to the right of color well's right edge
        if hasattr(self, 'color_well') and self.color_well:
            film_strip_x = (
                self.color_well.rect.right + 1
            )  # Film strip left x = color well right x + 1
        else:
            # Fallback: position to the right of the canvas
            film_strip_x = self.canvas.rect.right + 4  # 4 pixels to the right of canvas edge
        film_strip_y_start = self.canvas.rect.y if hasattr(self, 'canvas') and self.canvas else 0

        # Create up arrow (above first strip)
        up_arrow_y = film_strip_y_start - 30
        self.scroll_up_arrow = ScrollArrowSprite(
            x=int(film_strip_x) + 10,
            y=int(up_arrow_y),
            width=20,
            height=20,
            groups=self.all_sprites,
            direction='up',
        )

    def _update_scroll_arrows(self) -> None:
        """Update scroll arrow visibility based on scroll state."""
        if (
            not hasattr(self, 'canvas')
            or not self.canvas
            or not hasattr(self.canvas, 'animated_sprite')
        ):
            return

        # Show up arrow if we can scroll up
        if hasattr(self, 'scroll_up_arrow') and self.scroll_up_arrow:
            should_show = self.film_strip_scroll_offset > 0
            if self.scroll_up_arrow.visible != should_show:
                self.scroll_up_arrow.visible = should_show
                self.scroll_up_arrow.dirty = 1

    def _add_new_animation(self, insert_after_index: int | None = None) -> None:
        """Add a new animation (film strip) and scroll to it.

        Args:
            insert_after_index: Index to insert the new strip after (None for end)

        """
        if (
            not hasattr(self, 'canvas')
            or not self.canvas
            or not hasattr(self.canvas, 'animated_sprite')
        ):
            return

        # Create a new animation (film strip)
        new_animation_name = f'strip_{len(self.canvas.animated_sprite._animations) + 1}'  # type: ignore[reportPrivateUsage]

        # Create a blank frame for the new animation using the canonical helper
        if hasattr(self, 'canvas') and self.canvas:
            # Get the canvas pixel dimensions (same as original canvas)
            pixels_across = self.canvas.pixels_across
            pixels_tall = self.canvas.pixels_tall

            # Use the shared helper to create a blank frame with proper SRCALPHA support
            animated_frame = self._create_blank_frame(pixels_across, pixels_tall, duration=1.0)

            # Insert the new animation at the specified position
            if insert_after_index is not None:
                # Get current animations as a list to maintain order
                current_animations = list(self.canvas.animated_sprite._animations.items())  # type: ignore[reportPrivateUsage]

                # Create new ordered dict with the new animation inserted
                new_animations = {}
                for i, (anim_name, frames) in enumerate(current_animations):
                    new_animations[anim_name] = frames
                    if i == insert_after_index:
                        # Insert the new animation after this one
                        new_animations[new_animation_name] = [animated_frame]

                # If we didn't insert yet (insert_after_index >= len), add at end
                if insert_after_index >= len(current_animations):
                    new_animations[new_animation_name] = [animated_frame]

                # Replace the animations dict
                self.canvas.animated_sprite._animations = new_animations  # type: ignore[reportPrivateUsage]
            else:
                # Add at the end (original behavior)
                self.canvas.animated_sprite._animations[new_animation_name] = [animated_frame]  # type: ignore[reportPrivateUsage]

            # Track animation creation for undo/redo
            if hasattr(self, 'film_strip_operation_tracker'):
                # Set flag to prevent frame selection tracking during animation creation
                self._creating_animation = True
                try:
                    # Create animation data for undo/redo
                    animation_data = {
                        'frames': [
                            {
                                'width': animated_frame.image.get_width(),
                                'height': animated_frame.image.get_height(),
                                'pixels': animated_frame.pixels.copy()
                                if hasattr(animated_frame, 'pixels')
                                else [],
                                'duration': animated_frame.duration,
                            }
                        ],
                        'frame_count': 1,
                    }

                    # Track animation addition for undo/redo
                    self.film_strip_operation_tracker.add_animation_added(
                        new_animation_name, animation_data
                    )
                finally:
                    self._creating_animation = False

            # Recreate film strips to include the new animation
            self._on_sprite_loaded(self.canvas.animated_sprite)

            # Select, scroll to, and activate the new animation
            self._activate_new_animation(new_animation_name)

    def _activate_new_animation(self, new_animation_name: str) -> None:
        """Select, scroll to, and activate a newly created animation.

        Args:
            new_animation_name: Name of the newly created animation to activate

        """
        # Select the 0th frame of the new animation so the user can immediately start editing it
        LOG.debug(
            'BitmapEditorScene: Selecting frame 0 of newly created animation'
            f" '{new_animation_name}'"
        )
        # Set flag to prevent frame selection tracking during animation creation
        self._creating_frame = True
        try:
            self.canvas.show_frame(new_animation_name, 0)

            # Update the undo/redo manager with the current frame for frame-specific operations
            if hasattr(self, 'undo_redo_manager'):
                self.undo_redo_manager.set_current_frame(new_animation_name, 0)
                LOG.debug(
                    'BitmapEditorScene: Updated undo/redo manager to track frame 0 of'
                    f" '{new_animation_name}'"
                )
        finally:
            self._creating_frame = False

        # Scroll to the new animation (last one)
        total_animations = len(self.canvas.animated_sprite._animations)  # type: ignore[reportPrivateUsage]
        max_scroll = max(0, total_animations - self.max_visible_strips)
        self.film_strip_scroll_offset = max_scroll

        # Update visibility and scroll arrows with the new offset
        self._update_film_strip_visibility()
        self._update_scroll_arrows()

        # Select the new frame and notify the canvas
        self.selected_animation = new_animation_name
        self.selected_frame = 0

        # Notify the canvas to switch to the new frame
        if hasattr(self, 'canvas') and self.canvas:
            self._notify_canvas_of_new_animation(new_animation_name)

    def _notify_canvas_of_new_animation(self, new_animation_name: str) -> None:
        """Switch the canvas to display the new animation and force a redraw.

        Args:
            new_animation_name: Name of the animation to switch to

        """
        LOG.debug(f"DEBUG: Switching to new animation '{new_animation_name}', frame 0")
        LOG.debug(
            'DEBUG: Animated sprite current animation:'
            f' {self.canvas.animated_sprite.current_animation}'
        )
        LOG.debug(
            f'DEBUG: Animated sprite current frame: {self.canvas.animated_sprite.current_frame}'
        )
        self.canvas.show_frame(new_animation_name, 0)
        LOG.debug(
            'DEBUG: After switch - current animation:'
            f' {self.canvas.animated_sprite.current_animation}'
        )
        LOG.debug(
            f'DEBUG: After switch - current frame: {self.canvas.animated_sprite.current_frame}'
        )
        LOG.debug(f'DEBUG: New frame surface size: {self.canvas.animated_sprite.image.get_size()}')

        # Force the animated sprite to update its surface
        self.canvas.animated_sprite._update_surface_and_mark_dirty()  # type: ignore[reportPrivateUsage]

        # Force the canvas to redraw with the new frame
        self.canvas.dirty = 1
        self.canvas.force_redraw()

    def _delete_animation(self, animation_name: str, *, confirmed: bool = False) -> None:
        """Delete an animation (film strip).

        Args:
            animation_name: The name of the animation to delete
            confirmed: If True, skip confirmation dialog and delete immediately

        """
        if (
            not hasattr(self, 'canvas')
            or not self.canvas
            or not hasattr(self.canvas, 'animated_sprite')
        ):
            return

        # Check if we have more than one animation
        animations = list(self.canvas.animated_sprite._animations.keys())  # type: ignore[reportPrivateUsage]
        if len(animations) <= 1:
            self.log.warning('Cannot delete the last remaining animation')
            return

        # Show confirmation dialog unless already confirmed
        if not confirmed:
            self._show_delete_animation_confirmation(animation_name)
            return

        # Remove the animation from the sprite
        if animation_name not in self.canvas.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
            return

        # Get the position of the deleted animation before deletion
        all_animations = list(self.canvas.animated_sprite._animations.keys())  # type: ignore[reportPrivateUsage]
        deleted_index = all_animations.index(animation_name)

        # Capture animation data for undo/redo before deletion
        self._capture_animation_deletion_for_undo(animation_name)

        del self.canvas.animated_sprite._animations[animation_name]  # type: ignore[reportPrivateUsage]
        self.log.info(f'Deleted animation: {animation_name} at index {deleted_index}')

        # Switch to the first remaining animation and select the previous frame
        remaining_animations = list(self.canvas.animated_sprite._animations.keys())  # type: ignore[reportPrivateUsage]
        if remaining_animations:
            self._select_animation_after_deletion(remaining_animations, animation_name)
            return

        # No remaining animations - clear selection
        self._handle_no_remaining_animations(remaining_animations, all_animations, deleted_index)

    def _capture_animation_deletion_for_undo(self, animation_name: str) -> None:
        """Capture animation data for undo/redo before deletion.

        Args:
            animation_name: Name of the animation being deleted

        """
        if not hasattr(self, 'film_strip_operation_tracker'):
            return

        # Get the animation data before deletion
        animation = self.canvas.animated_sprite._animations[animation_name]  # type: ignore[reportPrivateUsage]
        animation_data: dict[str, Any] = {'frames': [], 'frame_count': len(animation)}

        # Capture frame data for each frame in the animation
        for frame in animation:
            frame_data = {
                'width': frame.image.get_width(),
                'height': frame.image.get_height(),
                'pixels': frame.pixels.copy() if hasattr(frame, 'pixels') else [],
                'duration': frame.duration,
            }
            animation_data['frames'].append(frame_data)

        # Track animation deletion for undo/redo
        self.film_strip_operation_tracker.add_animation_deleted(animation_name, animation_data)

    def _select_animation_after_deletion(
        self, remaining_animations: list[str], deleted_animation_name: str
    ) -> None:
        """Select a frame in the first remaining animation after a deletion.

        Args:
            remaining_animations: List of remaining animation names
            deleted_animation_name: Name of the animation that was deleted

        """
        new_animation = remaining_animations[0]

        # Try to select the previous frame in the remaining animation
        # If the deleted animation had frames, try to select a frame at a similar position
        if (
            hasattr(self, 'selected_frame')
            and self.selected_frame is not None
            and self.selected_frame > 0
        ):
            # Select the previous frame if available
            target_frame = max(0, self.selected_frame - 1)
        else:
            # If no previous frame, select the last frame of the remaining animation
            target_frame = max(0, len(self.canvas.animated_sprite._animations[new_animation]) - 1)  # type: ignore[reportPrivateUsage]

        # Ensure the target frame is within bounds
        max_frame = len(self.canvas.animated_sprite._animations[new_animation]) - 1  # type: ignore[reportPrivateUsage]
        target_frame = min(target_frame, max_frame)

        self.canvas.show_frame(new_animation, target_frame)

        # Update selection state
        self.selected_animation = new_animation
        self.selected_frame = target_frame

        self.log.info(
            f"Selected frame {target_frame} in animation '{new_animation}' after deleting"
            f" '{deleted_animation_name}'"
        )

        # Recreate film strips to reflect the deletion
        self.log.debug(
            'Recreating film strips after animation deletion. Remaining animations:'
            f' {remaining_animations}'
        )
        self._on_sprite_loaded(self.canvas.animated_sprite)

    def _handle_no_remaining_animations(
        self,
        remaining_animations: list[str],
        all_animations: list[str],
        deleted_index: int,
    ) -> None:
        """Handle post-deletion state when no animations remain (or updating scroll).

        Args:
            remaining_animations: List of remaining animation names (may be empty)
            all_animations: List of all animation names before deletion
            deleted_index: Index of the deleted animation in the original list

        """
        self.log.info('No remaining animations after deletion')
        self.selected_animation = None
        self.selected_frame = None

        # Force update of all film strip widgets to ensure they reflect the deletion
        if hasattr(self, 'film_strip_sprites') and self.film_strip_sprites:
            for film_strip_sprite in self.film_strip_sprites.values():
                if (
                    hasattr(film_strip_sprite, 'film_strip_widget')
                    and film_strip_sprite.film_strip_widget
                ):
                    # Force the film strip widget to update its layout
                    film_strip_sprite.film_strip_widget.update_layout()
                    film_strip_sprite.film_strip_widget._create_film_tabs()  # type: ignore[reportPrivateUsage]
                    film_strip_sprite.film_strip_widget.mark_dirty()
                    film_strip_sprite.dirty = 1

        # Ensure we show up to 2 strips after deletion
        if len(remaining_animations) <= MIN_FILM_STRIPS_FOR_PANEL_POSITIONING:
            # If we have 2 or fewer strips, show them all starting from index 0
            self.film_strip_scroll_offset = 0
        # If we deleted the last strip, show the previous 2 strips
        elif deleted_index == len(all_animations) - 1:
            # We deleted the last strip, show the previous 2 strips
            self.film_strip_scroll_offset = max(0, len(remaining_animations) - 2)
        else:
            # We deleted a strip that wasn't the last, show current and one more
            self.film_strip_scroll_offset = max(0, deleted_index - 1)

        # Update visibility and scroll arrows
        self._update_film_strip_visibility()
        self._update_scroll_arrows()

    def _show_delete_animation_confirmation(self, animation_name: str) -> None:
        """Show confirmation dialog before deleting an animation.

        Args:
            animation_name: Name of the animation to potentially delete

        """
        self.log.info(f'Showing delete confirmation dialog for animation: {animation_name}')

        from glitchygames.ui.dialogs import DeleteAnimationDialogScene

        # Create confirmation callback that deletes the animation
        def on_confirm() -> None:
            self.log.info(f'User confirmed deletion of animation: {animation_name}')
            self._delete_animation(animation_name, confirmed=True)

        # Create cancel callback that resets tab states
        def on_cancel() -> None:
            self.log.info(f'User cancelled deletion of animation: {animation_name}')
            # Reset all film strip tab states to unhighlight the delete button
            if hasattr(self, 'film_strip_sprites'):
                for film_strip_sprite in self.film_strip_sprites.values():
                    if (
                        hasattr(film_strip_sprite, 'film_strip_widget')
                        and film_strip_sprite.film_strip_widget is not None
                    ):
                        film_strip_sprite.film_strip_widget.reset_all_tab_states()
                        film_strip_sprite.dirty = 1  # Force redraw

        # Create the confirmation dialog scene
        confirmation_scene = DeleteAnimationDialogScene(
            previous_scene=self,
            animation_name=animation_name,
            on_confirm_callback=on_confirm,
            on_cancel_callback=on_cancel,
        )

        # Set the dialog's background to the screenshot
        confirmation_scene.background = self.screenshot

        # Switch to the confirmation dialog scene
        self.game_engine.scene_manager.switch_to_scene(confirmation_scene)  # type: ignore[union-attr]

    def _show_delete_frame_confirmation(self, animation_name: str, frame_index: int) -> None:
        """Show confirmation dialog before deleting a frame.

        Args:
            animation_name: Name of the animation containing the frame
            frame_index: Index of the frame to potentially delete

        """
        self.log.info(
            f'Showing delete frame confirmation dialog for {animation_name}[{frame_index}]'
        )

        from glitchygames.ui.dialogs import DeleteFrameDialogScene

        # Create confirmation callback that deletes the frame
        def on_confirm() -> None:
            self.log.info(
                f'User confirmed deletion of frame {frame_index} from animation: {animation_name}'
            )
            # Find the film strip widget for this animation and call its _remove_frame method
            if hasattr(self, 'film_strip_sprites') and animation_name in self.film_strip_sprites:
                film_strip_sprite = self.film_strip_sprites[animation_name]
                if (
                    hasattr(film_strip_sprite, 'film_strip_widget')
                    and film_strip_sprite.film_strip_widget is not None
                ):
                    film_strip_sprite.film_strip_widget._remove_frame(animation_name, frame_index)  # type: ignore[reportPrivateUsage]

        # Create cancel callback that resets removal button highlight
        def on_cancel() -> None:
            self.log.info(
                f'User cancelled deletion of frame {frame_index} from animation: {animation_name}'
            )
            # Reset the removal button highlight by clearing hover state
            if hasattr(self, 'film_strip_sprites') and animation_name in self.film_strip_sprites:
                film_strip_sprite = self.film_strip_sprites[animation_name]
                if (
                    hasattr(film_strip_sprite, 'film_strip_widget')
                    and film_strip_sprite.film_strip_widget is not None
                ):
                    film_strip_sprite.film_strip_widget.hovered_removal_button = None
                    film_strip_sprite.dirty = 1  # Force redraw

        # Create the confirmation dialog scene
        confirmation_scene = DeleteFrameDialogScene(
            previous_scene=self,
            animation_name=animation_name,
            frame_index=frame_index,
            on_confirm_callback=on_confirm,
            on_cancel_callback=on_cancel,
        )

        # Set the dialog's background to the screenshot
        confirmation_scene.background = self.screenshot

        # Switch to the confirmation dialog scene
        self.game_engine.scene_manager.switch_to_scene(confirmation_scene)  # type: ignore[union-attr]

    @staticmethod
    def _finalize_canvas_setup(animated_sprite: AnimatedSprite, options: dict[str, Any]) -> None:
        """Finalize canvas setup and start animation.

        Args:
            animated_sprite: The animated sprite to finalize
            options: Dictionary containing canvas configuration

        """
        # Start the animation after everything is set up
        animated_sprite.play()

        size_str = options.get('size')
        assert size_str is not None
        width, height = size_str.split('x')
        AnimatedCanvasSprite.WIDTH = int(width)  # ty: ignore[unresolved-attribute]
        AnimatedCanvasSprite.HEIGHT = int(height)  # ty: ignore[unresolved-attribute]

    def _setup_sliders_and_color_well(self) -> None:
        """Set up the color sliders and color well."""
        # First create the sliders
        slider_height = 9
        slider_width = 256
        slider_x = 13  # Moved 3 pixels to the right
        label_padding = 10  # Padding between slider and label
        well_padding = 20  # Padding between labels and color well

        # Create the sliders - positioned so blue slider bottom touches screen bottom
        # Account for bounding box height (slider_height + 4) in positioning
        # Blue slider bottom should be at screen_height - 2 (one pixel up from last visible row)
        bbox_height = slider_height + 4
        blue_slider_y = self.screen_height - slider_height - 2  # Bottom edge at screen_height - 2
        green_slider_y = blue_slider_y - bbox_height  # Use bounding box height for spacing
        red_slider_y = green_slider_y - bbox_height  # Use bounding box height for spacing
        alpha_slider_y = red_slider_y - bbox_height  # Alpha slider above red slider

        slider_y_positions = {
            'alpha': alpha_slider_y,
            'red': red_slider_y,
            'green': green_slider_y,
            'blue': blue_slider_y,
        }

        self._create_slider_labels(
            slider_x=slider_x,
            slider_height=slider_height,
            slider_y_positions=slider_y_positions,
        )

        self._create_slider_sprites(
            slider_x=slider_x,
            slider_width=slider_width,
            slider_height=slider_height,
            slider_y_positions=slider_y_positions,
        )

        self._create_slider_bounding_boxes(
            slider_x=slider_x,
            slider_width=slider_width,
            slider_height=slider_height,
            slider_y_positions=slider_y_positions,
        )

        # Create the color well positioned to the right of the text labels
        # Calculate x position to the right of the text labels
        # Text labels are at: slider_x + slider_width + label_padding
        text_label_x = slider_x + slider_width + label_padding
        color_well_x = text_label_x + well_padding  # Add padding after text labels

        self._create_color_well_and_tab_control(
            color_well_x=color_well_x,
            red_slider_y=red_slider_y,
            blue_slider_y=blue_slider_y,
            slider_height=slider_height,
        )

        self._configure_slider_text_boxes(
            text_label_x=text_label_x,
            color_well_x=color_well_x,
        )

        self._initialize_slider_values()

    def _create_slider_labels(
        self,
        *,
        slider_x: int,
        slider_height: int,
        slider_y_positions: dict[str, int],
    ) -> None:
        """Create text labels for each color slider.

        Args:
            slider_x: X position of sliders
            slider_height: Height of each slider
            slider_y_positions: Dict mapping color names to Y positions

        """
        # Create text labels for each slider
        label_x = (
            slider_x - 13
        )  # Position labels to the left of sliders (moved 7 pixels right total)
        label_width = 16  # Width for text labels
        label_height = 16  # Height for text labels

        from glitchygames.fonts import FontManager

        monospace_config = {'font_name': 'Courier', 'font_size': 14}

        # Alpha slider label
        self.alpha_label = TextSprite(
            text='A',
            x=label_x - 2,  # Move A label 2 pixels left (same as R and G)
            y=slider_y_positions['alpha'] + (slider_height - label_height) // 2,
            width=label_width,
            height=label_height,
            background_color=(0, 0, 0, 0),  # Transparent background
            text_color=(255, 255, 255),  # White text
            alpha=0,  # Transparent
            groups=self.all_sprites,
        )
        # Set monospaced font for the label
        self.alpha_label.font = FontManager.get_font(font_config=monospace_config)  # type: ignore[assignment]

        # Red slider label
        self.red_label = TextSprite(
            text='R',
            x=label_x - 2,  # Move R label 2 pixels left
            y=slider_y_positions['red'] + (slider_height - label_height) // 2,
            width=label_width,
            height=label_height,
            background_color=(0, 0, 0, 0),  # Transparent background
            text_color=(255, 255, 255),  # White text
            alpha=0,  # Transparent
            groups=self.all_sprites,
        )
        # Set monospaced font for the label
        self.red_label.font = FontManager.get_font(font_config=monospace_config)  # type: ignore[assignment]

        # Green slider label
        self.green_label = TextSprite(
            text='G',
            x=label_x - 2,  # Move G label 2 pixels left
            y=slider_y_positions['green'] + (slider_height - label_height) // 2,
            width=label_width,
            height=label_height,
            background_color=(0, 0, 0, 0),  # Transparent background
            text_color=(255, 255, 255),  # White text
            alpha=0,  # Transparent
            groups=self.all_sprites,
        )
        # Set monospaced font for the label
        self.green_label.font = FontManager.get_font(font_config=monospace_config)  # type: ignore[assignment]

        # Blue slider label
        self.blue_label = TextSprite(
            text='B',
            x=label_x - 1,  # Adjust B label 1 pixel left to align with R and G
            y=slider_y_positions['blue'] + (slider_height - label_height) // 2,
            width=label_width,
            height=label_height,
            background_color=(0, 0, 0, 0),  # Transparent background
            text_color=(255, 255, 255),  # White text
            alpha=0,  # Transparent
            groups=self.all_sprites,
        )
        # Set monospaced font for the label
        self.blue_label.font = FontManager.get_font(font_config=monospace_config)  # type: ignore[assignment]

    def _create_slider_sprites(
        self,
        *,
        slider_x: int,
        slider_width: int,
        slider_height: int,
        slider_y_positions: dict[str, int],
    ) -> None:
        """Create the ARGB slider sprites.

        Args:
            slider_x: X position of sliders
            slider_width: Width of each slider
            slider_height: Height of each slider
            slider_y_positions: Dict mapping color names to Y positions

        """
        self.alpha_slider = SliderSprite(
            name='A',
            x=slider_x,
            y=slider_y_positions['alpha'],
            width=slider_width,
            height=slider_height,
            parent=self,  # type: ignore[arg-type]
            groups=self.all_sprites,
        )

        self.red_slider = SliderSprite(
            name='R',
            x=slider_x,
            y=slider_y_positions['red'],
            width=slider_width,
            height=slider_height,
            parent=self,
            groups=self.all_sprites,
        )

        self.green_slider = SliderSprite(
            name='G',
            x=slider_x,
            y=slider_y_positions['green'],
            width=slider_width,
            height=slider_height,
            parent=self,
            groups=self.all_sprites,
        )

        self.blue_slider = SliderSprite(
            name='B',
            x=slider_x,
            y=slider_y_positions['blue'],
            width=slider_width,
            height=slider_height,
            parent=self,
            groups=self.all_sprites,
        )

    def _create_slider_bounding_boxes(
        self,
        *,
        slider_x: int,
        slider_width: int,
        slider_height: int,
        slider_y_positions: dict[str, int],
    ) -> None:
        """Create bounding boxes around the sliders for hover effects (initially hidden).

        Args:
            slider_x: X position of sliders
            slider_width: Width of each slider
            slider_height: Height of each slider
            slider_y_positions: Dict mapping color names to Y positions

        """
        bbox_configs = [
            ('alpha_slider_bbox', 'Alpha Slider BBox', slider_y_positions['alpha']),
            ('red_slider_bbox', 'Red Slider BBox', slider_y_positions['red']),
            ('green_slider_bbox', 'Green Slider BBox', slider_y_positions['green']),
            ('blue_slider_bbox', 'Blue Slider BBox', slider_y_positions['blue']),
        ]

        for attr_name, bbox_name, bbox_y in bbox_configs:
            bbox_sprite = BitmappySprite(
                x=slider_x - 2,
                y=bbox_y - 2,
                width=slider_width + 4,
                height=slider_height + 4,
                name=bbox_name,
                groups=self.all_sprites,
            )
            # Create transparent surface (no border initially)
            bbox_sprite.image = pygame.Surface(
                (slider_width + 4, slider_height + 4), pygame.SRCALPHA
            )
            bbox_sprite.visible = False  # Start hidden
            # Update bounding box position to match slider position
            bbox_sprite.rect.y = bbox_y - 2
            setattr(self, attr_name, bbox_sprite)

    def _create_color_well_and_tab_control(
        self,
        *,
        color_well_x: int,
        red_slider_y: int,
        blue_slider_y: int,
        slider_height: int,
    ) -> None:
        """Create the color well and format tab control.

        Args:
            color_well_x: X position for the color well
            red_slider_y: Y position of the red slider
            blue_slider_y: Y position of the blue slider
            slider_height: Height of each slider

        """
        # Position colorwell so its top y matches R slider's top y
        # and its bottom y is shorter than blue slider's bottom y
        blue_slider_bottom_y = blue_slider_y + slider_height
        color_well_y = red_slider_y - 5  # Add some padding above
        color_well_height = (
            blue_slider_bottom_y - color_well_y
        ) + 2  # 2 pixels taller than B slider's bottom y

        # Calculate canvas right edge position
        if hasattr(self, 'canvas') and self.canvas:
            canvas_right_x = self.canvas.pixels_across * self.canvas.pixel_width
        else:
            # Fallback for tests or when canvas isn't initialized yet
            canvas_right_x = self.screen_width - 20
        # Set colorwell width so its right edge aligns with canvas right edge
        color_well_width = canvas_right_x - color_well_x
        # Ensure minimum width to prevent invalid surface creation
        color_well_width = max(color_well_width, 50)
        # Ensure minimum height to prevent invalid surface creation (reduced from 50)
        color_well_height = max(color_well_height, 20)

        self.color_well = ColorWellSprite(
            name='Color Well',
            x=color_well_x,
            y=color_well_y,  # Top y matches R slider's top y
            width=color_well_width,
            height=color_well_height,  # Height spans from R top to G bottom
            parent=self,
            groups=self.all_sprites,
        )

        # Create tab control positioned above the color well
        tab_control_width = color_well_width  # Match the color well width
        tab_control_height = 20
        tab_control_x = (
            color_well_x + (color_well_width - tab_control_width) // 2
        )  # Center horizontally
        tab_control_y = (
            color_well_y - tab_control_height
        )  # Position so bottom touches top of color well

        self.tab_control = TabControlSprite(
            name='Format Tab Control',
            x=tab_control_x,
            y=tab_control_y,
            width=tab_control_width,
            height=tab_control_height,
            parent=self,  # type: ignore[arg-type]  # BitmapEditorScene implements TabProtocol
            groups=self.all_sprites,
        )

    def _configure_slider_text_boxes(
        self,
        *,
        text_label_x: int,
        color_well_x: int,
    ) -> None:
        """Configure slider text box widths and heights to fit the layout.

        Args:
            text_label_x: X position of the text labels
            color_well_x: X position of the color well

        """
        # Initialize slider input format (default to decimal)
        self.slider_input_format = '%d'

        # Update text box widths to fit between slider end and color well start
        text_box_width = color_well_x - text_label_x + 4  # Make 4 pixels wider
        # Shrink text boxes vertically by 4 pixels
        text_box_height = 16  # Original was 20, now 16 (4 pixels smaller)

        for slider in (self.alpha_slider, self.red_slider, self.green_slider, self.blue_slider):
            slider.text_sprite.width = text_box_width
            slider.text_sprite.height = text_box_height
            # Force text sprites to update with new dimensions
            slider.text_sprite.update_text(slider.text_sprite.text)

    def _initialize_slider_values(self) -> None:
        """Initialize slider default values and sync with color well."""
        self.alpha_slider.value = 255
        self.red_slider.value = 0
        self.blue_slider.value = 0
        self.green_slider.value = 0

        self.color_well.active_color = (
            self.red_slider.value,
            self.green_slider.value,
            self.blue_slider.value,
            self.alpha_slider.value,
        )

        if hasattr(self, 'canvas') and self.canvas:
            self.canvas.active_color = self.color_well.active_color  # type: ignore[assignment]

    def _setup_debug_text_box(self) -> None:
        """Set up the debug text box and AI label."""
        # Calculate debug text box position and size - align to bottom right corner
        debug_height = 186  # Fixed height for AI chat box

        # Calculate film strip left x position (should be less than color well's right x - 1)
        if hasattr(self, 'color_well') and self.color_well:
            film_strip_left_x = (
                self.color_well.rect.right + 1
            )  # Film strip left x = color well right x + 1
        else:
            # Fallback if color well not available
            film_strip_left_x = self.screen_width - 200

        # AI sprite box should be clamped to right side of screen and grow left
        # but not grow left more than the film strip left x
        debug_x = film_strip_left_x  # Start from film strip left x
        debug_width = self.screen_width - debug_x  # Extend to right edge of screen

        # Position below the 2nd film strip if it exists, otherwise clamp to bottom of screen
        if (
            hasattr(self, 'film_strips')
            and self.film_strips
            and len(self.film_strips) >= MIN_FILM_STRIPS_FOR_PANEL_POSITIONING
        ):
            # Find the bottom of the 2nd film strip
            second_strip_bottom = 0
            # Safely get the second film strip to handle race conditions during sprite loading
            try:
                # Convert to list to safely access by index
                film_strip_list = list(self.film_strips.values())
                if len(film_strip_list) >= MIN_FILM_STRIPS_FOR_PANEL_POSITIONING and hasattr(
                    film_strip_list[1], 'rect'
                ):
                    second_strip_bottom = film_strip_list[1].rect.bottom
            except (IndexError, KeyError, AttributeError):
                # Handle race condition where film strips are in transition
                second_strip_bottom = 0
            debug_y = second_strip_bottom + 30  # 30 pixels below the 2nd strip
            # Ensure it doesn't go above the bottom of the screen
            debug_y = min(debug_y, self.screen_height - debug_height)
        else:
            # Fallback: clamp to bottom of screen
            debug_y = self.screen_height - debug_height

        # Create the AI label
        label_height = 20
        self.ai_label = TextSprite(
            x=int(debug_x),
            y=debug_y - label_height,  # Position above the text box
            width=int(debug_width),
            height=label_height,
            text='AI Sprite',
            text_color=(255, 255, 255),  # White text
            background_color=(0, 0, 0),  # Solid black background like color well
            groups=self.all_sprites,
        )

        # Create the debug text box
        self.debug_text = MultiLineTextBox(
            name='Debug Output',
            x=int(debug_x),
            y=debug_y,
            width=int(debug_width),
            height=debug_height,
            text='',  # Changed to empty string
            parent=self,  # Pass self as parent
            groups=self.all_sprites,
        )

    def _update_ai_sprite_position(self) -> None:
        """Update AI sprite positioning when canvas changes."""
        if not hasattr(self, 'ai_label') or not hasattr(self, 'debug_text'):
            return  # AI sprites not initialized yet

        # Calculate new position using same logic as _setup_debug_text_box
        debug_height = 186  # Fixed height for AI chat box

        # Calculate film strip left x position (should be less than color well's right x - 1)
        if hasattr(self, 'color_well') and self.color_well:
            film_strip_left_x = (
                self.color_well.rect.right + 1
            )  # Film strip left x = color well right x + 1
        else:
            # Fallback if color well not available
            film_strip_left_x = self.screen_width - 200

        # AI sprite box should be clamped to right side of screen and grow left
        # but not grow left more than the film strip left x
        debug_x = film_strip_left_x  # Start from film strip left x
        debug_width = self.screen_width - debug_x  # Extend to right edge of screen

        # Position below the 2nd film strip if it exists, otherwise clamp to bottom of screen
        if (
            hasattr(self, 'film_strips')
            and self.film_strips
            and len(self.film_strips) >= MIN_FILM_STRIPS_FOR_PANEL_POSITIONING
        ):
            # Find the bottom of the 2nd film strip
            second_strip_bottom = 0
            # Safely get the second film strip to handle race conditions during sprite loading
            try:
                # Convert to list to safely access by index
                film_strip_list = list(self.film_strips.values())
                if len(film_strip_list) >= MIN_FILM_STRIPS_FOR_PANEL_POSITIONING and hasattr(
                    film_strip_list[1], 'rect'
                ):
                    second_strip_bottom = film_strip_list[1].rect.bottom
            except (IndexError, KeyError, AttributeError):
                # Handle race condition where film strips are in transition
                second_strip_bottom = 0
            debug_y = second_strip_bottom + 30  # 30 pixels below the 2nd strip
            # Ensure it doesn't go above the bottom of the screen
            debug_y = min(debug_y, self.screen_height - debug_height)
        else:
            # Fallback: clamp to bottom of screen
            debug_y = self.screen_height - debug_height

        # Update AI label position
        self.ai_label.rect.x = debug_x
        self.ai_label.rect.y = debug_y - 20  # Position above the text box
        self.ai_label.rect.width = debug_width
        self.ai_label.rect.height = 20

        # Update debug text position
        self.debug_text.rect.x = debug_x
        self.debug_text.rect.y = debug_y
        self.debug_text.rect.width = debug_width
        self.debug_text.rect.height = debug_height

    def _setup_voice_recognition(self) -> None:
        """Set up voice recognition for voice commands.

        **STATUS: DISABLED BY DEFAULT**

        This functionality is implemented but currently disabled in the setup() method
        (see line 6413-6414). Voice recognition requires:
        - A microphone to be connected and available
        - The glitchygames.events.voice module to be importable
        - Proper audio system configuration

        **Why Disabled:**
        - Voice recognition can be unreliable across different systems
        - Requires user permission for microphone access
        - May impact performance or cause issues on some platforms
        - Currently considered experimental/incomplete

        **Current Implementation:**
        When enabled, this method registers the following voice commands:
        - "clear the ai sprite box"
        - "clear ai sprite box"
        - "clear ai box"
        - "clear the ai sprite"
        - "clear ai sprite"
        - "clear the ai sprite window"
        - "clear ai sprite window"

        All commands trigger the _clear_ai_sprite_box() callback.

        **To Enable:**
        1. Uncomment the call to self._setup_voice_recognition() in setup() (line ~6414)
        2. Ensure VoiceEventManager is available (imports at lines 37-41)
        3. Test microphone access and speech recognition accuracy
        4. Verify no performance issues or crashes

        **Future Plans:**
        - Expand voice command vocabulary for more sprite editing operations
        - Add voice feedback/confirmation for commands
        - Integrate with scene manager for better coordination
        - Add configuration options for voice recognition sensitivity

        **Cleanup:**
        Always call _cleanup_voice_recognition() during scene teardown to properly
        release microphone resources and stop background threads.

        """
        try:
            if VoiceEventManager is None:
                self.log.info('Voice recognition not available')
                self.voice_manager = None
                return
            self.voice_manager = VoiceEventManager(logger=self.log)

            if self.voice_manager.is_available():
                # Register voice commands
                self.voice_manager.register_command(
                    'clear the ai sprite box', self._clear_ai_sprite_box
                )
                self.voice_manager.register_command(
                    'clear ai sprite box', self._clear_ai_sprite_box
                )
                self.voice_manager.register_command('clear ai box', self._clear_ai_sprite_box)
                # Add commands for what speech recognition actually hears
                self.voice_manager.register_command(
                    'clear the ai sprite', self._clear_ai_sprite_box
                )
                self.voice_manager.register_command('clear ai sprite', self._clear_ai_sprite_box)
                # Add command for "window" variation
                self.voice_manager.register_command(
                    'clear the ai sprite window', self._clear_ai_sprite_box
                )
                self.voice_manager.register_command(
                    'clear ai sprite window', self._clear_ai_sprite_box
                )

                # Start listening for voice commands
                self.voice_manager.start_listening()
                self.log.info('Voice recognition initialized and started')
            else:
                self.log.warning('Voice recognition not available - microphone not found')
                self.voice_manager = None

        except (ImportError, OSError, AttributeError, RuntimeError):
            self.log.exception('Failed to initialize voice recognition')
            self.voice_manager = None

    def _clear_ai_sprite_box(self) -> None:
        """Clear the AI sprite text box."""
        if hasattr(self, 'debug_text') and self.debug_text:
            self.debug_text.text = ''
            self.log.info('AI sprite box cleared via voice command')
        else:
            self.log.warning('Cannot clear AI sprite box - debug_text not available')

    def _is_mouse_in_film_strip_area(self, mouse_pos: tuple[int, int]) -> bool:
        """Check if mouse position is within the film strip area.

        Args:
            mouse_pos: (x, y) mouse position

        Returns:
            True if mouse is in film strip area, False otherwise

        """
        if not hasattr(self, 'film_strip_sprites') or not self.film_strip_sprites:
            self.log.debug(f'No film strip sprites available for mouse pos {mouse_pos}')
            return False

        # Check if mouse is within any film strip sprite bounds
        for anim_name, film_strip_sprite in self.film_strip_sprites.items():
            if film_strip_sprite.rect.collidepoint(mouse_pos):
                self.log.debug(
                    f"Mouse {mouse_pos} is in film strip '{anim_name}' at {film_strip_sprite.rect}"
                )
                return True

        self.log.debug(f'Mouse {mouse_pos} is not in any film strip area')
        return False

    def _handle_film_strip_drag_scroll(self, mouse_y: int) -> None:
        """Handle mouse drag scrolling for film strips.

        Args:
            mouse_y: Current mouse Y position

        """
        if not self.is_dragging_film_strips or self.film_strip_drag_start_y is None:
            self.log.debug('Not dragging film strips or no start Y')
            return

        # Calculate drag distance
        drag_distance = mouse_y - self.film_strip_drag_start_y
        self.log.debug(
            f'Drag distance: {drag_distance}, start Y: {self.film_strip_drag_start_y}, current Y:'
            f' {mouse_y}'
        )

        # Convert drag distance to scroll offset change
        # Each film strip is approximately 100 pixels tall, so we scroll by 1 for every 100 pixels
        strip_height = 100
        scroll_change = int(drag_distance / strip_height)

        # Calculate new scroll offset
        if self.film_strip_drag_start_offset is None:
            return
        new_offset = self.film_strip_drag_start_offset + scroll_change

        # Clamp to valid range
        if (
            hasattr(self, 'canvas')
            and self.canvas
            and hasattr(self.canvas, 'animated_sprite')
            and self.canvas.animated_sprite
        ):
            total_animations = len(self.canvas.animated_sprite._animations)  # type: ignore[reportPrivateUsage]
            max_scroll = max(0, total_animations - self.max_visible_strips)
            new_offset = max(0, min(new_offset, max_scroll))
            self.log.debug(
                f'Scroll change: {scroll_change}, new offset: {new_offset}, max scroll:'
                f' {max_scroll}'
            )

        # Update scroll offset if it changed
        if new_offset != self.film_strip_scroll_offset:
            self.log.debug(
                f'Updating scroll offset from {self.film_strip_scroll_offset} to {new_offset}'
            )
            self.film_strip_scroll_offset = new_offset
            self._update_film_strip_visibility()
            self._update_scroll_arrows()
        else:
            self.log.debug('No scroll offset change needed')

    def _setup_film_strips(self) -> None:
        """Set up film strips for the current animated sprite."""
        # Initialize film strip storage
        self.film_strips: dict[str, FilmStripWidget] = {}
        self.film_strip_sprites: dict[str, FilmStripSprite] = {}

        # Create film strips if we have an animated sprite
        LOG.debug('DEBUG: Checking conditions for _create_film_strips')
        LOG.debug(f'DEBUG: hasattr(animated_sprite): {hasattr(self, "animated_sprite")}')
        if hasattr(self, 'animated_sprite') and self.animated_sprite:
            LOG.debug(f'DEBUG: self.animated_sprite: {self.animated_sprite}')
            LOG.debug(
                f'DEBUG: hasattr(_animations): {hasattr(self.animated_sprite, "_animations")}'
            )
            if hasattr(self.animated_sprite, '_animations'):
                LOG.debug(f'DEBUG: _animations: {self.animated_sprite._animations}')  # type: ignore[reportPrivateUsage]
                if self.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
                    LOG.debug('DEBUG: About to call _create_film_strips (first call)')
                    self._create_film_strips(self.all_sprites)  # type: ignore[arg-type]
                    LOG.debug('DEBUG: Finished calling _create_film_strips (first call)')

        # Set up parent scene reference for canvas
        if hasattr(self, 'canvas') and self.canvas:
            self.canvas.parent_scene = self

    def _on_sprite_loaded(self, loaded_sprite: AnimatedSprite) -> None:
        """Handle when a new sprite is loaded - recreate film strips."""
        self.log.debug('=== _on_sprite_loaded called ===')
        LOG.debug(f'DEBUG: _on_sprite_loaded called with sprite: {loaded_sprite}')
        LOG.debug(f'DEBUG: Sprite has animations: {hasattr(loaded_sprite, "_animations")}')
        if hasattr(loaded_sprite, '_animations'):
            LOG.debug(f'DEBUG: Sprite animations: {list(loaded_sprite._animations.keys())}')  # type: ignore[reportPrivateUsage]

        # Preserve controller selections before clearing film strips
        preserved_controller_selections = {}
        if hasattr(self, 'controller_selections'):
            for controller_id, controller_selection in self.controller_selections.items():
                if controller_selection.is_active():
                    animation, frame = controller_selection.get_selection()
                    preserved_controller_selections[controller_id] = (animation, frame)

        # Store preserved selections for use in _create_film_strips
        self._preserved_controller_selections = preserved_controller_selections

        # Clear existing film strips
        LOG.debug(f'DEBUG: Checking film_strips - hasattr: {hasattr(self, "film_strips")}')
        if hasattr(self, 'film_strips') and self.film_strips:
            self.log.debug(f'Clearing {len(self.film_strips)} existing film strips')
            LOG.debug(f'DEBUG: Clearing {len(self.film_strips)} existing film strips')
            for film_strip_sprite in self.film_strip_sprites.values():
                film_strip_sprite.kill()
            self.film_strips.clear()
            self.film_strip_sprites.clear()

        # Create new film strips for the loaded sprite
        if loaded_sprite and loaded_sprite._animations:  # type: ignore[reportPrivateUsage]
            self.log.debug(
                f'Creating new film strips for loaded sprite with {len(loaded_sprite._animations)}'  # type: ignore[reportPrivateUsage]
                f' animations'
            )
            LOG.debug(
                f'DEBUG: _on_sprite_loaded recreating {len(loaded_sprite._animations)} film strips'  # type: ignore[reportPrivateUsage]
            )

            # Update the canvas to use the loaded sprite's animations
            if hasattr(self, 'canvas') and self.canvas:
                self.canvas.animated_sprite = loaded_sprite

                # CRITICAL FIX: Update the scene's animated_sprite reference to the loaded sprite
                # This ensures film strips use the correct sprite data
                self.animated_sprite = loaded_sprite

                # Check if canvas needs resizing and resize if necessary
                self.canvas._check_and_resize_canvas(loaded_sprite)  # type: ignore[reportPrivateUsage]

                # Set the canvas to show the first frame of the first animation
                first_animation = next(iter(loaded_sprite._animations.keys()))  # type: ignore[reportPrivateUsage]
                self.canvas.current_animation = first_animation
                self.canvas.current_frame = 0

                # Update the canvas interface to sync with the new sprite
                self.canvas.canvas_interface.set_current_frame(first_animation, 0)

                # Force the canvas to redraw with the new sprite
                self.canvas.force_redraw()

                # Note: The loaded sprite will be configured to play by the film strip widgets
                # The canvas should remain static for editing

                # Initialize pixels if needed (for mock sprites)
                self.log.debug(
                    f'Checking canvas pixels: has_pixels={hasattr(self.canvas, "pixels")},'
                    f' is_list={isinstance(getattr(self.canvas, "pixels", None), list)}'
                )
                if not hasattr(self.canvas, 'pixels') or not isinstance(self.canvas.pixels, list):  # type: ignore[reportUnnecessaryIsInstance]
                    self.log.debug('Initializing canvas pixels')
                    # Create a blank pixel array
                    pixel_count = self.canvas.pixels_across * self.canvas.pixels_tall
                    self.canvas.pixels = [(255, 0, 255, 255)] * pixel_count  # ty: ignore[invalid-assignment]  # Magenta background
                    self.canvas.dirty_pixels = [True] * pixel_count
                    self.log.debug(f'Canvas pixels initialized: len={len(self.canvas.pixels)}')

            LOG.debug('DEBUG: About to call _create_film_strips (second call)')
            self._create_film_strips(self.all_sprites)  # type: ignore[arg-type]
            LOG.debug('DEBUG: Finished calling _create_film_strips (second call)')
            self.log.debug('Film strips created for loaded sprite')

            # Initialize global selection to first frame of first animation
            first_animation = next(iter(loaded_sprite._animations.keys()))  # type: ignore[reportPrivateUsage]
            self.selected_animation = first_animation
            self.selected_frame = 0
            self.selected_strip = None  # Will be set when first frame is selected
        else:
            self.log.debug('No animations found in loaded sprite')

    def _on_film_strip_frame_selected(
        self, film_strip_widget: FilmStripWidget, animation: str, frame: int
    ) -> None:
        """Handle frame selection in a film strip."""
        # Find the strip name by looking up the film_strip_widget in film_strips
        strip_name = 'unknown'
        if hasattr(self, 'film_strips') and self.film_strips:
            for name, strip in self.film_strips.items():
                if strip == film_strip_widget:
                    strip_name = name
                    break
        LOG.debug(
            f"BitmapEditorScene: Frame selected - {animation}[{frame}] in strip '{strip_name}'"
        )

        # Update canvas to show the selected frame
        if hasattr(self, 'canvas') and self.canvas:
            LOG.debug(f'BitmapEditorScene: Updating canvas to show {animation}[{frame}]')
            self.canvas.show_frame(animation, frame)

        # Store global selection state
        self.selected_animation = animation
        self.selected_frame = frame

        # Update keyboard selection in all film strips using SelectionManager
        # OLD SYSTEM REMOVED - Using new multi-controller system instead
        # OLD SYSTEM DISABLED - Using new multi-controller system instead
        # The old SelectionManager system has been replaced by the new multi-controller system
        # Update film strip selection state
        self._update_film_strip_selection_state()
        self.selected_strip = film_strip_widget

        # OLD SYSTEM REMOVED - Using new multi-controller system instead

    def _get_sprite_to_update_for_rename(self) -> AnimatedSprite | None:
        """Determine which sprite object to update for animation rename.

        Prefers canvas.animated_sprite over self.animated_sprite.

        Returns:
            The sprite object to update, or None if no suitable sprite found.

        """
        if hasattr(self, 'canvas') and self.canvas and hasattr(self.canvas, 'animated_sprite'):
            self.log.debug('BitmapEditorScene: Using canvas.animated_sprite for rename')
            return self.canvas.animated_sprite
        if hasattr(self, 'animated_sprite') and self.animated_sprite:
            self.log.debug('BitmapEditorScene: Using self.animated_sprite for rename')
            return self.animated_sprite
        return None

    def _rename_animation_in_sprite(
        self, sprite_to_update: AnimatedSprite, old_name: str, new_name: str
    ) -> None:
        """Rename an animation within an animated sprite's internal data structures.

        Args:
            sprite_to_update: The animated sprite whose animation dict should be updated.
            old_name: The current animation name.
            new_name: The new animation name.

        """
        frames = sprite_to_update._animations[old_name]  # type: ignore[reportPrivateUsage]
        del sprite_to_update._animations[old_name]  # type: ignore[reportPrivateUsage]
        sprite_to_update._animations[new_name] = frames  # type: ignore[reportPrivateUsage]
        # Maintain animation order list if present
        if hasattr(sprite_to_update, '_animation_order'):
            order = list(getattr(sprite_to_update, '_animation_order', []))
            sprite_to_update._animation_order = [  # type: ignore[attr-defined]
                (new_name if name == old_name else name) for name in order
            ]

    def _rename_film_strip_widget_internals(
        self, strip_widget: FilmStripWidget, old_name: str, new_name: str
    ) -> None:
        """Update a FilmStripWidget's internal animated_sprite after animation rename.

        Args:
            strip_widget: The FilmStripWidget to update.
            old_name: The old animation name.
            new_name: The new animation name.

        """
        # CRITICAL: Update the FilmStripWidget's own animated_sprite
        if not (
            hasattr(strip_widget, 'animated_sprite')
            and strip_widget.animated_sprite
            and old_name in strip_widget.animated_sprite._animations  # type: ignore[reportPrivateUsage]
        ):
            return

        # Rename in the widget's sprite
        widget_frames = strip_widget.animated_sprite._animations[old_name]  # type: ignore[reportPrivateUsage]
        del strip_widget.animated_sprite._animations[old_name]  # type: ignore[reportPrivateUsage]
        strip_widget.animated_sprite._animations[new_name] = widget_frames  # type: ignore[reportPrivateUsage]

        # Update animation order
        if hasattr(strip_widget.animated_sprite, '_animation_order'):
            strip_widget.animated_sprite._animation_order = [new_name]  # type: ignore[reportPrivateUsage]

            # Update frame manager
            if strip_widget.animated_sprite.frame_manager.current_animation == old_name:
                strip_widget.animated_sprite.frame_manager.current_animation = new_name

            self.log.debug(
                f"Updated FilmStripWidget's internal sprite: '{old_name}' -> '{new_name}'"
            )

    def _update_film_strip_layout_after_rename(
        self, strip_widget: FilmStripWidget, new_name: str
    ) -> None:
        """Recalculate film strip layout and sprite dimensions after rename.

        Args:
            strip_widget: The FilmStripWidget to update.
            new_name: The new animation name.

        """
        try:
            # Recalculate layout to update animation_layouts with new name
            strip_widget.update_layout()
            # Update bounding box (rect) after layout recalculation
            if hasattr(strip_widget, '_update_height'):
                strip_widget._update_height()  # type: ignore[reportPrivateUsage]
            # Update film strip sprite rect if it exists
            if hasattr(self, 'film_strip_sprites') and new_name in self.film_strip_sprites:
                film_strip_sprite = self.film_strip_sprites[new_name]
                film_strip_sprite.rect.height = strip_widget.rect.height
                film_strip_sprite.rect.width = strip_widget.rect.width
                # Update sprite surface size
                film_strip_sprite.image = pygame.Surface(
                    (strip_widget.rect.width, strip_widget.rect.height), pygame.SRCALPHA
                )
                film_strip_sprite.dirty = 2
        except (AttributeError, KeyError, TypeError, pygame.error) as e:
            self.log.warning(f'FilmStripWidget layout update failed after rename: {e}')
        # Ensure redraw
        if hasattr(strip_widget, 'mark_dirty'):
            strip_widget.mark_dirty()

    def _rename_in_film_strips_dict(self, old_name: str, new_name: str) -> None:
        """Rename an animation in the film_strips and film_strip_sprites dictionaries.

        Args:
            old_name: The old animation name.
            new_name: The new animation name.

        """
        if not (hasattr(self, 'film_strips') and old_name in self.film_strips):
            return

        self.film_strips[new_name] = self.film_strips[old_name]
        del self.film_strips[old_name]

        # Update the specific FilmStripWidget's internal state
        strip_widget = self.film_strips[new_name]
        if getattr(strip_widget, 'current_animation', None) == old_name:
            strip_widget.current_animation = new_name

        self._rename_film_strip_widget_internals(strip_widget, old_name, new_name)

        # Update film_strip_sprites dictionary (keyed by animation name)
        if hasattr(self, 'film_strip_sprites') and old_name in self.film_strip_sprites:
            self.film_strip_sprites[new_name] = self.film_strip_sprites[old_name]
            del self.film_strip_sprites[old_name]
            self.log.debug(f"Updated film_strip_sprites dict: '{old_name}' -> '{new_name}'")

        self._update_film_strip_layout_after_rename(strip_widget, new_name)

    def _mark_all_film_strips_dirty(self) -> None:
        """Mark all film strips and their sprites as dirty for redraw."""
        if not (hasattr(self, 'film_strips') and self.film_strips):
            return

        for strip_name, strip_widget in self.film_strips.items():
            strip_widget.mark_dirty()
            # Mark the film strip sprite as dirty=2 for full surface blit
            if hasattr(self, 'film_strip_sprites') and strip_name in self.film_strip_sprites:
                self.film_strip_sprites[strip_name].dirty = 2

            # Mark the animated sprite as dirty to ensure animation updates
            if hasattr(strip_widget, 'animated_sprite') and strip_widget.animated_sprite:
                strip_widget.animated_sprite.dirty = 2

    def on_animation_rename(self, old_name: str, new_name: str) -> None:
        """Handle animation name changes from film strip editing."""
        self.log.debug(f"BitmapEditorScene: Animation renamed from '{old_name}' to '{new_name}'")

        sprite_to_update = self._get_sprite_to_update_for_rename()

        # Update the animated sprite's animation names
        if sprite_to_update:
            if old_name not in sprite_to_update._animations:  # type: ignore[reportPrivateUsage]
                self.log.warning(
                    f"BitmapEditorScene: Animation '{old_name}' not found for renaming"
                )
            else:
                self._rename_animation_in_sprite(sprite_to_update, old_name, new_name)

                # Update current animation if it was the renamed one
                if hasattr(self, 'selected_animation') and self.selected_animation == old_name:
                    self.selected_animation = new_name

                self._rename_in_film_strips_dict(old_name, new_name)

                # Force redraw of all film strips
                self._update_film_strips_for_animated_sprite_update()

                self.log.debug(
                    f"BitmapEditorScene: Successfully renamed animation '{old_name}' to"
                    f" '{new_name}'"
                )

        # Mark all film strips as dirty so they redraw with correct selection state
        self._mark_all_film_strips_dirty()

    def _on_frame_inserted(self, animation: str, frame_index: int) -> None:
        """Handle when a new frame is inserted into an animation.

        Args:
            animation: The animation name where the frame was inserted
            frame_index: The index where the frame was inserted

        """
        LOG.debug(f'BitmapEditorScene: Frame inserted at {animation}[{frame_index}]')

        # Update canvas to show the new frame if it's the current animation
        if hasattr(self, 'canvas') and self.canvas and self.selected_animation == animation:
            LOG.debug(
                f'BitmapEditorScene: Updating canvas to show new frame {animation}[{frame_index}]'
            )
            self.canvas.show_frame(animation, frame_index)
            self.selected_frame = frame_index

        # Update the selected_frame in the film strip widget for the current animation
        if hasattr(self, 'film_strips') and self.film_strips:
            for strip_name, strip_widget in self.film_strips.items():
                if strip_name == animation:
                    # Update the selected_frame in the film strip widget
                    strip_widget.selected_frame = frame_index
                    LOG.debug(
                        f'BitmapEditorScene: Updated film strip {strip_name} selected_frame to'
                        f' {frame_index}'
                    )

                strip_widget.mark_dirty()
                # Mark the film strip sprite as dirty=2 for full surface blit
                if hasattr(self, 'film_strip_sprites') and strip_name in self.film_strip_sprites:
                    self.film_strip_sprites[strip_name].dirty = 2

                # Mark the animated sprite as dirty to ensure animation updates
                if hasattr(strip_widget, 'animated_sprite') and strip_widget.animated_sprite:
                    strip_widget.animated_sprite.dirty = 2

    def _adjust_selected_frame_after_removal(self, animation: str, frame_index: int) -> None:
        """Adjust the selected frame index after a frame removal and update the canvas.

        Args:
            animation: The animation name where the frame was removed.
            frame_index: The index of the removed frame.

        """
        # If we removed a frame before or at the current position, adjust the selected frame
        if self.selected_frame is not None and self.selected_frame > 0:
            self.selected_frame -= 1
        else:
            # If we were at frame 0 and removed it, stay at frame 0 (which is now the next
            # frame)
            self.selected_frame = 0

        # Ensure the selected frame is within bounds
        if (
            hasattr(self, 'canvas')
            and self.canvas
            and hasattr(self.canvas, 'animated_sprite')
            and animation in self.canvas.animated_sprite._animations  # type: ignore[reportPrivateUsage]
        ):
            max_frame = len(self.canvas.animated_sprite._animations[animation]) - 1  # type: ignore[reportPrivateUsage]
            if self.selected_frame > max_frame:
                self.selected_frame = max(0, max_frame)

        # Update canvas to show the adjusted frame
        if hasattr(self, 'canvas') and self.canvas:
            LOG.debug(
                'BitmapEditorScene: Updating canvas to show adjusted frame'
                f' {animation}[{self.selected_frame}]'
            )
            try:
                self.canvas.show_frame(animation, self.selected_frame)
            except (IndexError, KeyError) as e:
                LOG.debug(f'BitmapEditorScene: Error updating canvas: {e}')
                # Fallback to frame 0 if there's an error
                self.selected_frame = 0
                if (
                    animation in self.canvas.animated_sprite._animations  # type: ignore[reportPrivateUsage]
                    and len(self.canvas.animated_sprite._animations[animation]) > 0  # type: ignore[reportPrivateUsage]
                ):
                    self.canvas.show_frame(animation, 0)

    def _on_frame_removed(self, animation: str, frame_index: int) -> None:
        """Handle when a frame is removed from an animation.

        Args:
            animation: The animation name where the frame was removed
            frame_index: The index where the frame was removed

        """
        LOG.debug(f'BitmapEditorScene: Frame removed at {animation}[{frame_index}]')

        # Adjust selected frame if necessary
        if (
            hasattr(self, 'selected_animation')
            and self.selected_animation == animation
            and hasattr(self, 'selected_frame')
            and self.selected_frame is not None
            and self.selected_frame >= frame_index
        ):
            self._adjust_selected_frame_after_removal(animation, frame_index)

        # Update the selected_frame in the film strip widget for the current animation
        if hasattr(self, 'film_strips') and self.film_strips:
            for strip_name, strip_widget in self.film_strips.items():
                if strip_name == animation:
                    # Update the selected_frame in the film strip widget
                    strip_widget.selected_frame = (  # type: ignore[attr-defined]
                        self.selected_frame if hasattr(self, 'selected_frame') else 0
                    )
                    LOG.debug(
                        f'BitmapEditorScene: Updated film strip {strip_name} selected_frame to'
                        f' {strip_widget.selected_frame}'
                    )

                strip_widget.mark_dirty()
                # Mark the film strip sprite as dirty=2 for full surface blit
                if hasattr(self, 'film_strip_sprites') and strip_name in self.film_strip_sprites:
                    self.film_strip_sprites[strip_name].dirty = 2

                # Mark the animated sprite as dirty to ensure animation updates
                if hasattr(strip_widget, 'animated_sprite') and strip_widget.animated_sprite:
                    strip_widget.animated_sprite.dirty = 2

    def _copy_current_frame(self) -> bool:
        """Copy the currently selected frame from the active film strip.

        Returns:
            bool: True if the condition is met, False otherwise.

        """
        LOG.debug('BitmapEditorScene: [SCENE COPY] _copy_current_frame called')

        if not hasattr(self, 'film_strips') or not self.film_strips:
            LOG.debug('BitmapEditorScene: [SCENE COPY] No film strips available for copying')
            return False

        LOG.debug(f'BitmapEditorScene: [SCENE COPY] Found {len(self.film_strips)} film strips')
        LOG.debug(
            'BitmapEditorScene: [SCENE COPY] Looking for animation:'
            f' {getattr(self, "selected_animation", "None")}'
        )

        # Find the active film strip (the one with the current animation)
        active_film_strip = None
        if hasattr(self, 'selected_animation') and self.selected_animation:
            for strip_name, film_strip in self.film_strips.items():
                LOG.debug(
                    f"BitmapEditorScene: [SCENE COPY] Checking film strip '{strip_name}' with"
                    f" animation '{getattr(film_strip, 'current_animation', 'None')}'"
                )
                if (
                    hasattr(film_strip, 'current_animation')
                    and film_strip.current_animation == self.selected_animation
                ):
                    active_film_strip = film_strip
                    LOG.debug(
                        f"BitmapEditorScene: [SCENE COPY] Found active film strip: '{strip_name}'"
                    )
                    break

        if not active_film_strip:
            LOG.debug('BitmapEditorScene: [SCENE COPY] No active film strip found for copying')
            return False

        LOG.debug('BitmapEditorScene: [SCENE COPY] Calling film strip copy method')
        # Call the film strip's copy method
        return active_film_strip.copy_current_frame()

    def _paste_to_current_frame(self) -> bool:
        """Paste the copied frame to the currently selected frame in the active film strip.

        Returns:
            bool: True if the condition is met, False otherwise.

        """
        LOG.debug('BitmapEditorScene: [SCENE PASTE] _paste_to_current_frame called')

        if not hasattr(self, 'film_strips') or not self.film_strips:
            LOG.debug('BitmapEditorScene: [SCENE PASTE] No film strips available for pasting')
            return False

        LOG.debug(f'BitmapEditorScene: [SCENE PASTE] Found {len(self.film_strips)} film strips')
        LOG.debug(
            'BitmapEditorScene: [SCENE PASTE] Looking for animation:'
            f' {getattr(self, "selected_animation", "None")}'
        )

        # Find the active film strip (the one with the current animation)
        active_film_strip = None
        if hasattr(self, 'selected_animation') and self.selected_animation:
            for strip_name, film_strip in self.film_strips.items():
                LOG.debug(
                    f"BitmapEditorScene: [SCENE PASTE] Checking film strip '{strip_name}' with"
                    f" animation '{getattr(film_strip, 'current_animation', 'None')}'"
                )
                if (
                    hasattr(film_strip, 'current_animation')
                    and film_strip.current_animation == self.selected_animation
                ):
                    active_film_strip = film_strip
                    LOG.debug(
                        f"BitmapEditorScene: [SCENE PASTE] Found active film strip: '{strip_name}'"
                    )
                    break

        if not active_film_strip:
            LOG.debug('BitmapEditorScene: [SCENE PASTE] No active film strip found for pasting')
            return False

        LOG.debug('BitmapEditorScene: [SCENE PASTE] Calling film strip paste method')
        # Call the film strip's paste method
        return active_film_strip.paste_to_current_frame()

    def _update_film_strip_selection_state(self) -> None:
        """Update the selection state of all film strips based on current selection."""
        if not hasattr(self, 'film_strips') or not self.film_strips:
            return

        current_animation = getattr(self, 'selected_animation', '')
        current_frame = getattr(self, 'selected_frame', 0)

        for strip_name, strip_widget in self.film_strips.items():
            # Each film strip should have its current_animation set to its own animation name
            # for proper sprocket rendering
            strip_widget.current_animation = strip_name

            if strip_name == current_animation:
                # This is the selected strip - mark it as selected
                strip_widget.is_selected = True
                strip_widget.selected_frame = current_frame
                LOG.debug(
                    f'BitmapEditorScene: Marking strip {strip_name} as selected with frame'
                    f' {current_frame}'
                )
            else:
                # This is not the selected strip - deselect it but preserve its selected_frame
                strip_widget.is_selected = False
                # Don't reset selected_frame - each strip maintains its own selection
                LOG.debug(
                    f'BitmapEditorScene: Deselecting strip {strip_name} (preserving'
                    f' selected_frame={strip_widget.selected_frame})'
                )

            # Mark the strip as dirty to trigger full redraw
            strip_widget.mark_dirty()
            # Also mark the film strip sprite as dirty=2 for full surface blit
            if hasattr(self, 'film_strip_sprites') and strip_name in self.film_strip_sprites:
                self.film_strip_sprites[strip_name].dirty = 2

            # Mark the animated sprite as dirty to ensure animation updates
            if hasattr(strip_widget, 'animated_sprite') and strip_widget.animated_sprite:
                strip_widget.animated_sprite.dirty = 2

    def _switch_to_film_strip(self, animation_name: str, frame: int = 0) -> None:
        """Switch to a specific film strip and frame, deselecting the previous one."""
        LOG.debug(f'BitmapEditorScene: Switching to film strip {animation_name}[{frame}]')

        # Deselect the current strip if there is one
        if hasattr(self, 'selected_strip') and self.selected_strip:
            LOG.debug('BitmapEditorScene: Deselecting current strip')
            self.selected_strip.is_selected = False
            self.selected_strip.current_animation = ''
            self.selected_strip.current_frame = 0
            self.selected_strip.mark_dirty()
            # Mark the film strip sprite as dirty=2 for full surface blit
            if hasattr(self, 'film_strip_sprites'):
                for strip_sprite in self.film_strip_sprites.values():
                    if strip_sprite.film_strip_widget == self.selected_strip:
                        strip_sprite.dirty = 2
                        break

            # Mark the animated sprite as dirty to ensure animation updates
            if (
                hasattr(self.selected_strip, 'animated_sprite')
                and self.selected_strip.animated_sprite
            ):
                self.selected_strip.animated_sprite.dirty = 2

        # Select the new strip
        if hasattr(self, 'film_strips') and animation_name in self.film_strips:
            new_strip = self.film_strips[animation_name]
            new_strip.is_selected = True
            # Set current_animation to the strip's own animation name for sprocket rendering
            new_strip.current_animation = animation_name
            new_strip.current_frame = frame
            new_strip.mark_dirty()

            # Mark the new film strip sprite as dirty=2 for full surface blit
            if hasattr(self, 'film_strip_sprites') and animation_name in self.film_strip_sprites:
                self.film_strip_sprites[animation_name].dirty = 2

            # Mark the animated sprite as dirty to ensure animation updates
            if hasattr(new_strip, 'animated_sprite') and new_strip.animated_sprite:
                new_strip.animated_sprite.dirty = 2

            # Update global selection state
            self.selected_animation = animation_name
            self.selected_frame = frame
            self.selected_strip = new_strip

            # Update canvas to show the selected frame
            if hasattr(self, 'canvas') and self.canvas:
                self.canvas.show_frame(animation_name, frame)

            LOG.debug(f'BitmapEditorScene: Selected strip {animation_name} with frame {frame}')
        else:
            LOG.debug(f'BitmapEditorScene: Film strip {animation_name} not found')

    def _scroll_to_current_animation(self) -> None:
        """Scroll the film strip view to show the selected animation.

        Shows the currently selected animation if it's not visible.
        """
        if (
            not hasattr(self, 'canvas')
            or not self.canvas
            or not hasattr(self.canvas, 'animated_sprite')
        ):
            return

        # Get the current animation name
        current_animation = self.canvas.current_animation
        if not current_animation:
            return

        # Get all animation names in order
        animation_names = list(self.canvas.animated_sprite._animations.keys())  # type: ignore[reportPrivateUsage]
        if current_animation not in animation_names:
            return

        # Find the index of the current animation
        current_index = animation_names.index(current_animation)

        # Calculate the scroll offset needed to show this animation
        # We want to show the current animation in the visible area
        if current_index < self.film_strip_scroll_offset:
            # Current animation is above the visible area, scroll up
            self.film_strip_scroll_offset = current_index
            self.log.debug(
                f'Scrolling up to show animation {current_animation} at index {current_index}'
            )
        elif current_index >= self.film_strip_scroll_offset + self.max_visible_strips:
            # Current animation is below the visible area, scroll down
            self.film_strip_scroll_offset = current_index - self.max_visible_strips + 1
            self.log.debug(
                f'Scrolling down to show animation {current_animation} at index {current_index}'
            )
        else:
            # Current animation is already visible, no scrolling needed
            self.log.debug(
                f'Animation {current_animation} is already visible at index {current_index}'
            )
            return

        # Update visibility and scroll arrows
        self._update_film_strip_visibility()
        self._update_scroll_arrows()

        # Update the film strip selection to show the current frame
        self._update_film_strip_selection()

    def scroll_film_strips_up(self) -> None:
        """Scroll film strips up (show earlier animations)."""
        if hasattr(self, 'film_strip_scroll_offset') and self.film_strip_scroll_offset > 0:
            self.film_strip_scroll_offset -= 1
            self._update_film_strip_visibility()

    def _select_first_visible_film_strip(self) -> None:
        """Select the first visible film strip and set its frame 0 as active."""
        if not hasattr(self, 'film_strips') or not self.film_strips:
            return

        # Get all animation names in order
        if hasattr(self, 'canvas') and self.canvas and hasattr(self.canvas, 'animated_sprite'):
            animation_names = list(self.canvas.animated_sprite._animations.keys())  # type: ignore[reportPrivateUsage]
        else:
            animation_names = list(self.film_strips.keys())

        # Find the first visible animation
        start_index = self.film_strip_scroll_offset
        if start_index < len(animation_names):
            first_visible_animation = animation_names[start_index]

            # Select this animation and frame 0
            if hasattr(self, 'canvas') and self.canvas:
                self.canvas.show_frame(first_visible_animation, 0)

            # Update the film strip widget to show the correct frame selection
            if first_visible_animation in self.film_strips:
                film_strip_widget = self.film_strips[first_visible_animation]
                film_strip_widget.set_current_frame(first_visible_animation, 0)

            # Update global selection state
            self.selected_animation = first_visible_animation
            self.selected_frame = 0

            # Mark all film strips as dirty so they redraw with correct selection state
            if hasattr(self, 'film_strips') and self.film_strips:
                for strip_widget in self.film_strips.values():
                    strip_widget.mark_dirty()

    def _navigate_frame(self, direction: int) -> None:
        """Navigate to the next or previous frame in the current animation.

        Args:
            direction: 1 for next frame, -1 for previous frame

        """
        if (
            not hasattr(self, 'canvas')
            or not self.canvas
            or not hasattr(self.canvas, 'animated_sprite')
        ):
            LOG.debug(
                'BitmapEditorScene: No canvas or animated sprite available for frame navigation'
            )
            return

        current_animation = self.canvas.current_animation
        if not current_animation:
            LOG.debug('BitmapEditorScene: No current animation selected for frame navigation')
            return

        # Get the current frame index
        current_frame = getattr(self, 'selected_frame', 0)

        # Get all frames for the current animation
        if current_animation not in self.canvas.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
            LOG.debug(
                f"BitmapEditorScene: Animation '{current_animation}' not found in animated sprite"
            )
            return

        frames = self.canvas.animated_sprite._animations[current_animation]  # type: ignore[reportPrivateUsage]
        total_frames = len(frames)

        if total_frames == 0:
            LOG.debug(f"BitmapEditorScene: Animation '{current_animation}' has no frames")
            return

        # Calculate new frame index with wrapping
        new_frame = (current_frame + direction) % total_frames

        LOG.debug(
            f'BitmapEditorScene: Navigating from frame {current_frame} to frame {new_frame} in'
            f" animation '{current_animation}' (total frames: {total_frames})"
        )

        # Update the canvas to show the new frame
        self.canvas.show_frame(current_animation, new_frame)

        # Update the film strip widget to show the correct frame selection
        if hasattr(self, 'film_strips') and current_animation in self.film_strips:
            film_strip_widget = self.film_strips[current_animation]
            film_strip_widget.set_current_frame(current_animation, new_frame)
            film_strip_widget.mark_dirty()

        # Update global selection state
        self.selected_animation = current_animation
        self.selected_frame = new_frame

        # Mark the film strip sprite as dirty for redraw
        if hasattr(self, 'film_strip_sprites') and current_animation in self.film_strip_sprites:
            self.film_strip_sprites[current_animation].dirty = 2

    def scroll_film_strips_down(self) -> None:
        """Scroll film strips down (show later animations)."""
        if hasattr(self, 'canvas') and self.canvas and hasattr(self.canvas, 'animated_sprite'):
            total_animations = len(self.canvas.animated_sprite._animations)  # type: ignore[reportPrivateUsage]
            max_scroll = max(0, total_animations - self.max_visible_strips)

            # Check if there are more strips below that we can scroll to
            if (
                hasattr(self, 'film_strip_scroll_offset')
                and self.film_strip_scroll_offset < max_scroll
            ):
                self.film_strip_scroll_offset += 1
                self._update_film_strip_visibility()

    def _select_last_visible_film_strip(self) -> None:
        """Select the last visible film strip and set its frame 0 as active."""
        if not hasattr(self, 'film_strips') or not self.film_strips:
            return

        # Get all animation names in order
        if hasattr(self, 'canvas') and self.canvas and hasattr(self.canvas, 'animated_sprite'):
            animation_names = list(self.canvas.animated_sprite._animations.keys())  # type: ignore[reportPrivateUsage]
        else:
            animation_names = list(self.film_strips.keys())

        # Find the last visible animation
        start_index = self.film_strip_scroll_offset
        end_index = min(start_index + self.max_visible_strips, len(animation_names))

        if end_index > start_index:
            last_visible_animation = animation_names[end_index - 1]

            # Select this animation and frame 0
            if hasattr(self, 'canvas') and self.canvas:
                self.canvas.show_frame(last_visible_animation, 0)

            # Update the film strip widget to show the correct frame selection
            if last_visible_animation in self.film_strips:
                film_strip_widget = self.film_strips[last_visible_animation]
                film_strip_widget.set_current_frame(last_visible_animation, 0)

            # Update global selection state
            self.selected_animation = last_visible_animation
            self.selected_frame = 0

            # Mark all film strips as dirty so they redraw with correct selection state
            if hasattr(self, 'film_strips') and self.film_strips:
                for strip_widget in self.film_strips.values():
                    strip_widget.mark_dirty()

    def _update_film_strips_for_frame(self, animation: str, frame: int) -> None:
        """Update film strips when frame changes."""
        self.log.debug(
            f'_update_film_strips_for_frame called: animation={animation}, frame={frame}'
        )
        if hasattr(self, 'film_strips') and self.film_strips:
            self.log.debug(
                f'Found {len(self.film_strips)} film strips: {list(self.film_strips.keys())}'
            )
            # Update the film strip for the current animation
            if animation in self.film_strips:
                film_strip = self.film_strips[animation]
                self.log.debug(f'Updating film strip for animation {animation}')
                # Directly update the selection without triggering handlers to avoid infinite loops
                film_strip.current_animation = animation
                film_strip.current_frame = frame
                film_strip.update_scroll_for_frame(frame)
                film_strip.update_layout()
                film_strip.mark_dirty()
                self.log.debug(
                    f'Film strip updated: current_animation={film_strip.current_animation},'
                    f' current_frame={film_strip.current_frame}'
                )
            else:
                self.log.debug(f'Animation {animation} not found in film strips')

            # Mark all film strip sprites as dirty
            if hasattr(self, 'film_strip_sprites') and self.film_strip_sprites:
                for film_strip_sprite in self.film_strip_sprites.values():
                    film_strip_sprite.dirty = 1

    def _update_film_strips_for_pixel_update(self) -> None:
        """Update film strips when pixel data changes."""
        if hasattr(self, 'film_strip_sprites') and self.film_strip_sprites:
            for film_strip_sprite in self.film_strip_sprites.values():
                film_strip_sprite.dirty = 1
        if hasattr(self, 'film_strips') and self.film_strips:
            for film_strip in self.film_strips.values():
                film_strip.mark_dirty()

        # Film strip animated sprites should use original animation frames, not canvas content

    def _update_film_strips_for_animated_sprite_update(self) -> None:
        """Update film strips when animated sprite frame data changes."""
        if hasattr(self, 'film_strips') and self.film_strips:
            for film_strip in self.film_strips.values():
                film_strip.update_layout()
                film_strip.mark_dirty()
        if hasattr(self, 'film_strip_sprites') and self.film_strip_sprites:
            for film_strip_sprite in self.film_strip_sprites.values():
                film_strip_sprite.dirty = 1

        # Also mark film strip sprites as dirty for animation updates
        self._mark_film_strip_sprites_dirty()

    def _mark_film_strip_sprites_dirty(self) -> None:
        """Mark all film strip sprites as dirty for animation updates.

        This is a backup mechanism to ensure film strip sprites are marked as dirty
        when animations are running. The primary dirty marking happens in the
        FilmStripSprite.update() method, but this provides an additional safety net.

        DEBUGGING NOTES:
        - If film strips don't redraw: Check that this method is being called
        - If animations are choppy: Verify dirty flag is being set consistently
        - If performance is poor: Consider reducing frequency of this call
        """
        if hasattr(self, 'film_strip_sprites') and self.film_strip_sprites:
            for film_strip_sprite in self.film_strip_sprites.values():
                film_strip_sprite.dirty = 1

    def _update_film_strip_selection(self) -> None:
        """Update film strip selection to show the current animation and frame."""
        if not hasattr(self, 'canvas') or not self.canvas:
            return

        # Get the current animation and frame
        current_animation = self.canvas.current_animation
        current_frame = self.canvas.current_frame

        # Update all film strips
        if hasattr(self, 'film_strips') and self.film_strips:
            for strip_name, strip_widget in self.film_strips.items():
                if strip_name == current_animation:
                    # This is the current animation - set it as selected
                    strip_widget.set_current_frame(current_animation, current_frame)
                    # Call the selection handler to update the scene state
                    self._on_film_strip_frame_selected(
                        strip_widget, current_animation, current_frame
                    )
                else:
                    # This is not the current animation - clear selection
                    strip_widget.current_animation = ''
                    strip_widget.current_frame = 0
                    strip_widget.mark_dirty()

    def __init__(
        self,
        options: dict[str, Any],
        groups: pygame.sprite.LayeredDirty | None = None,  # type: ignore[type-arg]
    ) -> None:
        """Initialize the Bitmap Editor Scene.

        Args:
            options: Dictionary of configuration options for the scene.
            groups: Optional pygame sprite groups for sprite management.

        Raises:
            None

        """
        if options is None:  # type: ignore[reportUnnecessaryComparison]
            options = {}

        # Set default size if not provided
        if 'size' not in options:
            options['size'] = '32x32'  # Default canvas size

        super().__init__(options=options, groups=groups)  # type: ignore[arg-type]

        # Initialize film strip scrolling attributes
        self.film_strip_scroll_offset = 0
        self.max_visible_strips = 2

        # Legacy film_strip_widget reference for backward compatibility
        # Used by _refresh_all_film_strip_widgets and undo/redo methods
        self.film_strip_widget: FilmStripWidget | None = None

        # Slider bounding box sprites for hover effects (set dynamically in _create_slider_bboxes)
        self.alpha_slider_bbox: BitmappySprite | None = None
        self.red_slider_bbox: BitmappySprite | None = None
        self.green_slider_bbox: BitmappySprite | None = None
        self.blue_slider_bbox: BitmappySprite | None = None

        # Pixel change tracking dict for deduplication (used alongside _current_pixel_changes list)
        self._current_pixel_changes_dict: dict[
            int, tuple[int, tuple[int, ...], tuple[int, ...]]
        ] = {}

        # Initialize scroll arrows
        self.scroll_up_arrow = None

        # Initialize mouse drag scrolling state
        self.film_strip_drag_start_y = None
        self.film_strip_drag_start_offset = None
        self.is_dragging_film_strips = False

        # Initialize selection state for multi-selection system
        self.selected_animation = ''
        self.selected_frame = 0

        # OLD SYSTEM REMOVED - Using new multi-controller system instead

        # Debug state tracking to prevent redundant logging
        self._last_debug_controller_animation = ''
        self._last_debug_controller_frame = -1
        self._last_debug_keyboard_animation = ''
        self._last_debug_keyboard_frame = -1

        # Initialize multi-controller system
        self.multi_controller_manager = MultiControllerManager()
        self.controller_selections: dict[int, ControllerSelection] = {}

        # Initialize mode switching system
        from glitchygames.tools.controller_mode_system import ModeSwitcher

        # Initialize undo/redo system
        self._init_undo_redo_system()

        self.mode_switcher = ModeSwitcher()
        self.visual_collision_manager = VisualCollisionManager()

        # Selected frame visibility toggle for canvas comparison
        self.selected_frame_visible = True

        # Controller input state tracking to prevent jittery behavior
        self._controller_axis_deadzone = (
            500  # Only respond to values beyond this threshold (for larger scale values)
        )
        self._controller_axis_hat_threshold = (
            500  # Threshold for hat-like behavior (0.5 in normalized scale)
        )
        self._controller_axis_last_values: dict[
            tuple[int, int], float
        ] = {}  # Track last axis values
        self._controller_axis_cooldown: dict[
            tuple[int, int], float
        ] = {}  # Track cooldown timers for each axis
        self._controller_axis_cooldown_duration = 0.2  # 200ms cooldown between actions

        # Set up all components
        self._setup_menu_bar()
        self._setup_canvas(options)
        self._setup_sliders_and_color_well()
        self._setup_debug_text_box()

        # Set up film strips after canvas is ready
        self._setup_film_strips()

        # Set up callback for when sprites are loaded
        if hasattr(self, 'canvas') and self.canvas:
            # Set up the callback on the canvas to call the main scene
            self.canvas.on_sprite_loaded = self._on_sprite_loaded  # type: ignore[attr-defined]
            self.log.debug('Set up on_sprite_loaded callback for canvas')
            LOG.debug('DEBUG: Set up on_sprite_loaded callback for canvas')

        # Controller selection will be initialized when START button is pressed

        # Query model capabilities for optimal token usage
        # try:
        #     capabilities = {
        #         "max_tokens": AI_MAX_INPUT_TOKENS,
        #         "context_size": AI_MAX_CONTEXT_SIZE
        #     }
        #     #capabilities = _get_model_capabilities(self.log)
        #     if capabilities.get("max_tokens"):
        #         self.log.info(f"Model max tokens detected: {capabilities['max_tokens']}")

        #         # Update AI_MAX_INPUT_TOKENS with detected capabilities
        #         global AI_MAX_INPUT_TOKENS
        #         old_max_tokens = AI_MAX_INPUT_TOKENS
        #         AI_MAX_INPUT_TOKENS = capabilities['max_tokens']
        #         self.log.info(f"Updated AI_MAX_INPUT_TOKENS from {old_max_tokens} to
        #         {AI_MAX_INPUT_TOKENS}")

        #         # Also log context size if available
        #         if capabilities.get("context_size"):
        #             self.log.info(f"Model context size: {capabilities['context_size']}")

        # except (ValueError, ConnectionError, TimeoutError) as e:
        #     self.log.warning(f"Could not query model capabilities: {e}")

        # Set up voice recognition
        # VOICE RECOGNITION IS CURRENTLY DISABLED
        # See _setup_voice_recognition() method documentation (line ~5382) for details
        # about why it's disabled and how to enable it in the future.
        #
        # To enable: Uncomment the following line after testing microphone access
        # and verifying speech recognition works reliably on your platform.
        # self._setup_voice_recognition()

        self.all_sprites.clear(self.screen, self.background)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]

        # TODO: Plumb this into the scene manager

    def _init_undo_redo_system(self) -> None:
        """Initialize the undo/redo system with all operation trackers and callbacks."""
        self.undo_redo_manager = UndoRedoManager(max_history=50)
        self.canvas_operation_tracker = CanvasOperationTracker(self.undo_redo_manager)
        self.film_strip_operation_tracker = FilmStripOperationTracker(self.undo_redo_manager)
        self.cross_area_operation_tracker = CrossAreaOperationTracker(self.undo_redo_manager)
        from glitchygames.tools.operation_history import ControllerPositionOperationTracker

        self.controller_position_operation_tracker = ControllerPositionOperationTracker(
            self.undo_redo_manager
        )

        self.undo_redo_manager.set_pixel_change_callback(self._apply_pixel_change_for_undo_redo)
        self.undo_redo_manager.set_film_strip_callbacks(
            add_frame_callback=self._add_frame_for_undo_redo,
            delete_frame_callback=self._delete_frame_for_undo_redo,
            reorder_frame_callback=self._reorder_frame_for_undo_redo,
            add_animation_callback=self._add_animation_for_undo_redo,
            delete_animation_callback=self._delete_animation_for_undo_redo,
        )
        self.undo_redo_manager.set_frame_selection_callback(
            self._apply_frame_selection_for_undo_redo
        )
        self.undo_redo_manager.set_controller_position_callback(
            self._apply_controller_position_for_undo_redo
        )
        self.undo_redo_manager.set_controller_mode_callback(
            self._apply_controller_mode_for_undo_redo
        )
        self.undo_redo_manager.set_frame_paste_callback(self._apply_frame_paste_for_undo_redo)

        self._current_pixel_changes: list[tuple[int, tuple[int, ...], tuple[int, ...]]] = []
        self._is_drag_operation: bool = False
        self._pixel_change_timer: float | None = None
        self._applying_undo_redo: bool = False
        self._frame_clipboard: dict[str, Any] | None = None

        # These are set up in the GameEngine class.
        if not hasattr(self, '_initialized'):
            self.log.info(f'Game Options: {self.options}')

            # Override font to use a cleaner system font
            self.options['font_name'] = 'arial'
            self.log.info(f'Font overridden to: {self.options["font_name"]}')
            self._initialized = True

    @override
    def on_menu_item_event(self: Self, event: events.HashableEvent) -> None:
        """Handle the menu item event.

        Args:
            event (pygame.event.Event): The pygame event.

        Raises:
            None

        """
        self.log.info(f'Scene got menu item event: {event}')
        if not event.menu.name:
            # This is for the system menu.
            self.log.info('System Menu Clicked')
        elif event.menu.name == 'New':
            self.on_new_canvas_dialog_event(event=event)
        elif event.menu.name == 'Save':
            self.on_save_dialog_event(event=event)
        elif event.menu.name == 'Load':
            self.on_load_dialog_event(event=event)
        elif event.menu.name == 'Quit':
            self.log.info('User quit from menu item.')
            self.scene_manager.quit()
        else:
            self.log.info(f'Unhandled Menu Item: {event.menu.name}')
        self.dirty = 1

    # NB: Keepings this around causes GG-7 not to manifest... curious.
    # This function is extraneous now that on_new_canvas_dialog_event exists.
    #
    # There is also some dialog drawing goofiness when keeping this which
    # goes away when we remove it.
    #
    # Keeping as a workaround for GG-7 for now.
    def _reset_canvas_for_new_file(self, width: int, height: int, pixel_size: int) -> None:
        """Reset canvas state for a new file with the given dimensions.

        Args:
            width: Canvas width in pixels.
            height: Canvas height in pixels.
            pixel_size: Display pixel size.

        """
        self.canvas.pixels_across = width
        self.canvas.pixels_tall = height
        self.canvas.pixel_width = pixel_size
        self.canvas.pixel_height = pixel_size

        self.canvas.pixels = [(255, 0, 255, 255)] * (width * height)  # ty: ignore[invalid-assignment]
        self.canvas.dirty_pixels = [True] * len(self.canvas.pixels)

        # Reset viewport/panning system
        if hasattr(self.canvas, 'reset_panning'):
            self.canvas.reset_panning()
        if hasattr(self.canvas, '_panning_active'):
            self.canvas._panning_active = False  # type: ignore[reportPrivateUsage]
        if hasattr(self.canvas, 'pan_offset_x'):
            self.canvas.pan_offset_x = 0
        if hasattr(self.canvas, 'pan_offset_y'):
            self.canvas.pan_offset_y = 0

    def _create_fresh_animated_sprite(self, width: int, height: int, pixel_size: int) -> None:
        """Create a fresh animated sprite and update the canvas.

        Args:
            width: Sprite width in pixels.
            height: Sprite height in pixels.
            pixel_size: Display pixel size.

        """
        from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame

        fresh_sprite = AnimatedSprite()
        fresh_sprite.name = 'new_canvas'
        fresh_sprite.description = 'New canvas sprite'

        fresh_frame = SpriteFrame(surface=pygame.Surface((width, height)))
        fresh_frame.set_pixel_data([(255, 0, 255)] * (width * height))  # ty: ignore[invalid-argument-type]

        fresh_sprite._animations['default'] = [fresh_frame]  # type: ignore[reportPrivateUsage]
        fresh_sprite.frame_manager.current_animation = 'default'
        fresh_sprite.frame_manager.current_frame = 0

        self.canvas.animated_sprite = fresh_sprite
        self.canvas.image = pygame.Surface((width * pixel_size, height * pixel_size))
        self.canvas.rect = self.canvas.image.get_rect(x=0, y=24)
        self.canvas._update_border_thickness()  # type: ignore[reportPrivateUsage]
        self.canvas.force_redraw()

    def _clear_film_strips_for_new_canvas(self) -> None:
        """Remove existing film strips and recreate for new canvas."""
        if hasattr(self, 'film_strips') and self.film_strips:
            self.log.info('Clearing existing film strips for new canvas')
            for film_strip_sprite in self.film_strip_sprites.values():
                if hasattr(film_strip_sprite, 'groups') and film_strip_sprite.groups():
                    for group in film_strip_sprite.groups():
                        group.remove(film_strip_sprite)
            self.film_strips.clear()
            self.film_strip_sprites.clear()

        self.log.info('Creating new film strip for new canvas')
        self._create_film_strips(self.all_sprites)  # type: ignore[arg-type]

    def on_new_file_event(self: Self, dimensions: str) -> None:
        """Handle the new file event.

        Args:
            dimensions (str): The canvas dimensions in WxH format.

        """
        self.log.info(f'Creating new canvas with dimensions: {dimensions}')

        try:
            width, height = map(int, dimensions.lower().split('x'))
            self.log.info(f'Parsed dimensions: {width}x{height}')

            available_height = self.screen_height - 80 - 24
            new_pixel_size = min(
                available_height // height,
                (self.screen_width * 1 // 2) // width,
                350 // width,
            )
            self.log.info(f'Calculated new pixel size: {new_pixel_size}')

            self._reset_canvas_for_new_file(width, height, new_pixel_size)
            self._create_fresh_animated_sprite(width, height, new_pixel_size)
            self._clear_film_strips_for_new_canvas()
            self._clear_ai_sprite_box()

            if hasattr(self, 'pending_ai_requests'):
                self.pending_ai_requests.clear()
                self.log.info('Cleared AI request cache for new canvas')

            self._update_ai_sprite_position()
            self.canvas.update()
            self.canvas.dirty = 1
            self.log.info(f'Canvas resized to {width}x{height} with pixel size {new_pixel_size}')

        except ValueError:
            self.log.exception(f"Invalid dimensions format '{dimensions}'")
            self.log.exception("Expected format: WxH (e.g., '32x32')")

        self.dirty = 1

    def on_new_canvas_dialog_event(self: Self, event: events.HashableEvent) -> None:
        """Handle the new canvas dialog event.

        Args:
            event (pygame.event.Event): The pygame event.

        Raises:
            None

        """
        # Create a fresh dialog scene each time
        new_canvas_dialog_scene = NewCanvasDialogScene(options=self.options, previous_scene=self)
        # Set the dialog's background to the screenshot
        new_canvas_dialog_scene.background = self.screenshot
        self.next_scene = new_canvas_dialog_scene
        self.dirty = 1

    def on_load_dialog_event(self: Self, event: events.HashableEvent) -> None:
        """Handle the load dialog event.

        Args:
            event (pygame.event.Event): The pygame event.

        Raises:
            None

        """
        # Create a fresh dialog scene each time
        load_dialog_scene = LoadDialogScene(options=self.options, previous_scene=self)
        # Set the dialog's background to the screenshot
        load_dialog_scene.background = self.screenshot
        self.next_scene = load_dialog_scene
        self.dirty = 1

    def on_save_dialog_event(self: Self, event: events.HashableEvent) -> None:
        """Handle the save dialog event.

        Args:
            event (pygame.event.Event): The pygame event.

        Raises:
            None

        """
        # Create a fresh dialog scene each time
        save_dialog_scene = SaveDialogScene(options=self.options, previous_scene=self)
        # Set the dialog's background to the screenshot
        save_dialog_scene.background = self.screenshot
        self.next_scene = save_dialog_scene
        self.dirty = 1

    def on_color_well_event(self: Self, event: events.HashableEvent, trigger: object) -> None:
        """Handle the color well event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Raises:
            None

        """
        self.log.info('COLOR WELL EVENT')

    def _sample_color_from_screen(self, screen_pos: tuple[int, int]) -> None:
        """Sample color directly from the screen (RGB only, ignores alpha).

        Args:
            screen_pos: Screen coordinates (x, y) to sample from

        """
        try:
            # Sample directly from the screen
            assert self.screen is not None
            color = self.screen.get_at(screen_pos)

            # Handle both RGB and RGBA screen formats
            if len(color) == RGBA_COMPONENT_COUNT:
                red, green, blue, _ = color  # Ignore alpha from screen
            else:
                red, green, blue = color
            alpha = 255  # Screen has no meaningful alpha, default to opaque

            self.log.info(
                f'Screen pixel sampled - Red: {red}, Green: {green}, Blue: {blue}, Alpha: {alpha}'
                f' (default)'
            )

            # Update all sliders with the sampled RGB values and default alpha
            trigger = events.HashableEvent(0, name='R', value=red)
            self.on_slider_event(event=events.HashableEvent(0), trigger=trigger)

            trigger = events.HashableEvent(0, name='G', value=green)
            self.on_slider_event(event=events.HashableEvent(0), trigger=trigger)

            trigger = events.HashableEvent(0, name='B', value=blue)
            self.on_slider_event(event=events.HashableEvent(0), trigger=trigger)

            trigger = events.HashableEvent(0, name='A', value=alpha)
            self.on_slider_event(event=events.HashableEvent(0), trigger=trigger)

            self.log.info(
                f'Updated sliders with screen color R:{red}, G:{green}, B:{blue}, A:{alpha}'
            )

        except Exception:
            self.log.exception('Error sampling color from screen')

    def on_slider_event(
        self: Self, event: events.HashableEvent, trigger: events.HashableEvent
    ) -> None:
        """Handle the slider event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Raises:
            None

        """
        value = trigger.value

        self.log.debug(f'Slider: event: {event}, trigger: {trigger} value: {value}')

        if value < MIN_COLOR_VALUE:
            value = MIN_COLOR_VALUE
            trigger.value = MIN_COLOR_VALUE  # type: ignore[misc]
        elif value > MAX_COLOR_VALUE:
            value = MAX_COLOR_VALUE
            trigger.value = MAX_COLOR_VALUE  # type: ignore[misc]

        if trigger.name == 'R':
            self.red_slider.value = value
            self.log.debug(f'Updated red slider to: {value}')
        elif trigger.name == 'G':
            self.green_slider.value = value
            self.log.debug(f'Updated green slider to: {value}')
        elif trigger.name == 'B':
            self.blue_slider.value = value
            self.log.debug(f'Updated blue slider to: {value}')
        elif trigger.name == 'A':
            self.alpha_slider.value = value
            self.log.debug(f'Updated alpha slider to: {value}')

        # Update slider text to reflect current tab format
        # This handles slider clicks - text input is handled by SliderSprite itself
        self._update_slider_text_format()

        # Debug: Log current slider values
        self.log.debug(
            f'Current slider values - R: {self.red_slider.value}, '
            f'G: {self.green_slider.value}, B: {self.blue_slider.value}, A:'
            f' {self.alpha_slider.value}'
        )

        self.color_well.active_color = (
            self.red_slider.value,
            self.green_slider.value,
            self.blue_slider.value,
            self.alpha_slider.value,
        )
        self.canvas.active_color = (  # type: ignore[assignment]
            self.red_slider.value,
            self.green_slider.value,
            self.blue_slider.value,
            self.alpha_slider.value,
        )

    @override
    def on_right_mouse_button_up_event(self: Self, event: events.HashableEvent) -> None:
        """Handle the right mouse button up event.

        Args:
            event (pygame.event.Event): The pygame event.

        Raises:
            None

        """
        # Check for shift-right-click (screen sampling)
        is_shift_click = (
            pygame.key.get_pressed()[pygame.K_LSHIFT] or pygame.key.get_pressed()[pygame.K_RSHIFT]
        )

        # First, check if any sprites have handled the event
        collided_sprites = self.sprites_at_position(pos=event.pos)
        for sprite in collided_sprites:
            if hasattr(sprite, 'on_right_mouse_button_up_event'):
                result = sprite.on_right_mouse_button_up_event(event)
                if result:  # Event was handled by sprite
                    return

        # If no sprite handled the event, proceed with scene-level handling
        # Check if the click is on the canvas to sample canvas pixel data
        if (
            hasattr(self, 'canvas')
            and self.canvas
            and self.canvas.rect is not None  # pyright: ignore[reportUnnecessaryComparison]
            and self.canvas.rect.collidepoint(event.pos)
        ):
            if is_shift_click:
                # Shift-right-click: sample screen directly (RGB only)
                self.log.info('Shift-right-click detected on canvas - sampling screen directly')
                self._sample_color_from_screen(event.pos)
                return
            # Regular right-click: sample from canvas pixel data (RGBA)
            canvas_x = (event.pos[0] - self.canvas.rect.x) // self.canvas.pixel_width
            canvas_y = (event.pos[1] - self.canvas.rect.y) // self.canvas.pixel_height

            # Check bounds
            if (
                0 <= canvas_x < self.canvas.pixels_across
                and 0 <= canvas_y < self.canvas.pixels_tall
            ):
                pixel_num = canvas_y * self.canvas.pixels_across + canvas_x
                if pixel_num < len(self.canvas.pixels):
                    color: tuple[int, ...] = self.canvas.pixels[pixel_num]  # type: ignore[assignment]

                    # Handle both RGB and RGBA pixel formats
                    if len(color) == RGBA_COMPONENT_COUNT:  # type: ignore[reportUnknownArgumentType]
                        red, green, blue, alpha = (
                            int(color[0]),  # pyright: ignore[reportUnknownArgumentType]
                            int(color[1]),  # pyright: ignore[reportUnknownArgumentType]
                            int(color[2]),  # pyright: ignore[reportUnknownArgumentType]
                            int(color[3]),  # pyright: ignore[reportUnknownArgumentType]
                        )
                    else:
                        red, green, blue = int(color[0]), int(color[1]), int(color[2])  # type: ignore[reportUnknownArgumentType]
                        alpha = 255  # Default to opaque for RGB pixels

                    self.log.info(
                        f'Canvas pixel sampled - Red: {red}, Green: {green}, Blue: {blue}, Alpha:'
                        f' {alpha}'
                    )

                    # Update all sliders with the sampled RGBA values
                    trigger = events.HashableEvent(0, name='R', value=red)
                    self.on_slider_event(event=event, trigger=trigger)

                    trigger = events.HashableEvent(0, name='G', value=green)
                    self.on_slider_event(event=event, trigger=trigger)

                    trigger = events.HashableEvent(0, name='B', value=blue)
                    self.on_slider_event(event=event, trigger=trigger)

                    trigger = events.HashableEvent(0, name='A', value=alpha)
                    self.on_slider_event(event=event, trigger=trigger)
                    return

        # Fallback to screen sampling (RGB only)
        try:
            assert self.screen is not None
            color = tuple(self.screen.get_at(event.pos))
            if len(color) == RGBA_COMPONENT_COUNT:
                red, green, blue, _ = color  # Ignore alpha from screen
            else:
                red, green, blue = color
            alpha = 255  # Screen has no alpha, default to opaque
            self.log.info(
                f'Screen pixel sampled - Red: {red}, Green: {green}, Blue: {blue}, Alpha: {alpha}'
                f' (default)'
            )

            # Update sliders with RGB values and default alpha
            trigger = events.HashableEvent(0, name='R', value=red)
            self.on_slider_event(event=event, trigger=trigger)

            trigger = events.HashableEvent(0, name='G', value=green)
            self.on_slider_event(event=event, trigger=trigger)

            trigger = events.HashableEvent(0, name='B', value=blue)
            self.on_slider_event(event=event, trigger=trigger)

            trigger = events.HashableEvent(0, name='A', value=alpha)
            self.on_slider_event(event=event, trigger=trigger)
        except IndexError:
            pass

    def _detect_clicked_slider(self, mouse_pos: tuple[int, int]) -> str | None:
        """Detect which slider text box was clicked.

        Args:
            mouse_pos: The mouse position (x, y)

        Returns:
            The name of the clicked slider ("red", "green", "blue") or None.

        """
        slider_names = ['red', 'green', 'blue']
        for name in slider_names:
            slider_attr = f'{name}_slider'
            if (
                hasattr(self, slider_attr)
                and hasattr(getattr(self, slider_attr), 'text_sprite')
                and getattr(self, slider_attr).text_sprite.rect.collidepoint(mouse_pos)
            ):
                return name
        return None

    def _commit_and_deactivate_slider(
        self, slider: SliderSprite, clicked_slider: str | None, slider_name: str
    ) -> None:
        """Commit the slider text value and deactivate the text sprite.

        Commits the current text input on a slider's text sprite, parsing as hex or
        decimal as appropriate, then deactivates the text sprite.

        Args:
            slider: The slider object with text_sprite attribute
            clicked_slider: Name of the slider that was clicked, or None
            slider_name: Name of this slider ("red", "green", "blue")

        """
        if not (
            hasattr(slider, 'text_sprite')
            and slider.text_sprite.active
            and (clicked_slider != slider_name or clicked_slider is None)
        ):
            return

        # Commit any uncommitted value before deactivating
        if not slider.text_sprite.text.strip():
            # If empty, restore original value
            slider.text_sprite.text = str(slider.original_value)
        else:
            # Try to commit the current text value - parse as hex if contains letters, otherwise
            # decimal
            try:
                text = slider.text_sprite.text.strip().lower()
                # Parse as hex if contains hex letters, otherwise decimal
                new_value = int(text, 16) if any(c in 'abcdef' for c in text) else int(text)

                if 0 <= new_value <= MAX_COLOR_CHANNEL_VALUE:
                    slider.value = new_value
                    # Update original value for future validations
                    slider.original_value = new_value
                    # Convert text to appropriate format based on selected tab
                    LOG.debug(f'DEBUG: Current slider_input_format: {self.slider_input_format}')
                    if self.slider_input_format == '%X':
                        slider.text_sprite.text = f'{new_value:02X}'
                        LOG.debug(
                            f'DEBUG: Converting {new_value} to hex: {slider.text_sprite.text}'
                        )
                    else:
                        slider.text_sprite.text = str(new_value)
                        LOG.debug(
                            f'DEBUG: Converting {new_value} to decimal: {slider.text_sprite.text}'
                        )
                    slider.text_sprite.update_text(slider.text_sprite.text)
                    slider.text_sprite.dirty = 2  # Force redraw
                else:
                    # Invalid range, restore original
                    slider.text_sprite.text = str(slider.original_value)
            except ValueError:
                # Invalid input, restore original
                slider.text_sprite.text = str(slider.original_value)

        slider.text_sprite.active = False
        slider.text_sprite.update_text(slider.text_sprite.text)

    @override
    def on_left_mouse_button_down_event(self: Self, event: events.HashableEvent) -> None:
        """Handle the left mouse button down event.

        Args:
            event (pygame.event.Event): The pygame event.

        Raises:
            None

        """
        sprites = self.sprites_at_position(pos=event.pos)

        # Check for clicks on scroll arrows first (only if visible)
        for sprite in sprites:
            if hasattr(sprite, 'direction') and hasattr(sprite, 'visible') and sprite.visible:
                LOG.debug(
                    f'Scroll arrow clicked: direction={sprite.direction}, visible={sprite.visible}'
                )
                if sprite.direction == 'up':
                    # Clicked on up arrow - navigate to previous animation and scroll if needed
                    LOG.debug('Navigating to previous animation')
                    if hasattr(self, 'canvas') and self.canvas:
                        self.canvas.previous_animation()
                        # Scroll to show the current animation if needed
                        self._scroll_to_current_animation()
                        # Update film strips to reflect the animation change
                        self._update_film_strips_for_animated_sprite_update()
                    return

        # Check if click is on any slider text box and deactivate others
        clicked_slider = self._detect_clicked_slider(event.pos)

        # Deactivate all slider text boxes except the one clicked (if any)
        # Also commit values when clicking outside of any slider text box
        for slider_name in ('red', 'green', 'blue'):
            slider_attr = f'{slider_name}_slider'
            if hasattr(self, slider_attr):
                self._commit_and_deactivate_slider(
                    getattr(self, slider_attr), clicked_slider, slider_name
                )

        # If a slider text box was clicked, also trigger the slider's normal behavior
        if clicked_slider is not None:
            slider_attr = f'{clicked_slider}_slider'
            if hasattr(self, slider_attr):
                getattr(self, slider_attr).on_left_mouse_button_down_event(event)

        # Handle other sprite clicks
        for sprite in sprites:
            sprite.on_left_mouse_button_down_event(event)

        # Check if click is in film strip area for drag scrolling (only if no sprite handled it)
        if self._is_mouse_in_film_strip_area(event.pos):
            self.is_dragging_film_strips = True
            self.film_strip_drag_start_y = event.pos[1]
            self.film_strip_drag_start_offset = self.film_strip_scroll_offset
            self.log.debug(
                f'Started film strip drag at Y={event.pos[1]},'
                f' offset={self.film_strip_scroll_offset}'
            )

    def on_tab_change_event(self, tab_format: str) -> None:
        """Handle tab control format change.

        Args:
            tab_format (str): The selected format ("%d" or "%H")

        """
        self.log.info(f'Tab control changed to format: {tab_format}')

        # Store the current format for slider text input
        self.slider_input_format = tab_format

        # Update slider text display format if they have values
        self._update_slider_text_format(tab_format)

    def _update_slider_text_format(self, tab_format: str | None = None) -> None:
        """Update slider text display format.

        Args:
            tab_format (str): The format to use ("%X" for hex, "%d" for decimal).
                             If None, uses the current slider_input_format.

        """
        if tab_format is None:
            tab_format = getattr(self, 'slider_input_format', '%d')

        if hasattr(self, 'red_slider') and hasattr(self.red_slider, 'text_sprite'):
            if tab_format == '%X':
                # Convert to hex
                self.red_slider.text_sprite.text = f'{self.red_slider.value:02X}'
            else:
                # Convert to decimal
                self.red_slider.text_sprite.text = str(self.red_slider.value)
            self.red_slider.text_sprite.update_text(self.red_slider.text_sprite.text)

        if hasattr(self, 'green_slider') and hasattr(self.green_slider, 'text_sprite'):
            if tab_format == '%X':
                # Convert to hex
                self.green_slider.text_sprite.text = f'{self.green_slider.value:02X}'
            else:
                # Convert to decimal
                self.green_slider.text_sprite.text = str(self.green_slider.value)
            self.green_slider.text_sprite.update_text(self.green_slider.text_sprite.text)

        if hasattr(self, 'blue_slider') and hasattr(self.blue_slider, 'text_sprite'):
            if tab_format == '%X':
                # Convert to hex
                self.blue_slider.text_sprite.text = f'{self.blue_slider.value:02X}'
            else:
                # Convert to decimal
                self.blue_slider.text_sprite.text = str(self.blue_slider.value)
            self.blue_slider.text_sprite.update_text(self.blue_slider.text_sprite.text)

    @override
    def on_left_mouse_button_up_event(self: Self, event: events.HashableEvent) -> None:
        """Handle the left mouse button up event.

        Args:
            event (pygame.event.Event): The pygame event.

        Raises:
            None

        """
        # Stop film strip drag scrolling if active
        if self.is_dragging_film_strips:
            self.is_dragging_film_strips = False
            self.film_strip_drag_start_y = None
            self.film_strip_drag_start_offset = None
            self.log.debug('Stopped film strip drag scrolling')

        sprites = self.sprites_at_position(pos=event.pos)

        for sprite in sprites:
            sprite.on_left_mouse_button_up_event(event)

    @override
    def on_left_mouse_drag_event(self: Self, event: events.HashableEvent, trigger: object) -> None:
        """Handle the left mouse drag event.

        Args:
            event (pygame.event.Event): The pygame event.
            trigger (object): The trigger object.

        Raises:
            None

        """
        # Handle film strip drag scrolling
        if self.is_dragging_film_strips:
            self.log.debug(f'Handling film strip drag at Y={event.pos[1]}')
            self._handle_film_strip_drag_scroll(event.pos[1])
            return  # Don't process other drag events when dragging film strips

        # Optimized: If dragging on canvas, skip expensive sprite collision detection
        # The canvas already handles its own drag events efficiently
        if (
            hasattr(self, 'canvas')
            and self.canvas is not None  # pyright: ignore[reportUnnecessaryComparison]
            and self.canvas.rect is not None  # pyright: ignore[reportUnnecessaryComparison]
            and self.canvas.rect.collidepoint(event.pos)
        ):
            # Directly call canvas drag handler - skip sprite iteration
            self.canvas.on_left_mouse_drag_event(event, trigger)
            return

        # Only do expensive sprite iteration if not dragging on canvas
        self.canvas.on_left_mouse_drag_event(event, trigger)

        try:
            sprites = self.sprites_at_position(pos=event.pos)

            for sprite in sprites:
                sprite.on_left_mouse_drag_event(event, trigger)
        except AttributeError:
            pass

    @override
    def on_mouse_button_up_event(self: Self, event: events.HashableEvent) -> None:  # type: ignore[override]
        """Handle mouse button up events."""
        # Check if debug text box should handle the event
        if (
            hasattr(self, 'debug_text')
            and self.debug_text is not None  # pyright: ignore[reportUnnecessaryComparison]
            and self.debug_text.rect is not None  # pyright: ignore[reportUnnecessaryComparison]
            and self.debug_text.rect.collidepoint(event.pos)
        ):
            self.debug_text.on_mouse_up_event(event)
            return

        # Submit collected pixel changes for undo/redo tracking
        self._submit_pixel_changes_if_ready()

        # Reset drag operation flag
        self._is_drag_operation = False

        # Always release all sliders on mouse up to prevent stickiness
        if (
            hasattr(self, 'red_slider')
            and hasattr(self.red_slider, 'dragging')
            and self.red_slider.dragging
        ):
            self.red_slider.dragging = False
            self.red_slider.on_left_mouse_button_up_event(event)
        if (
            hasattr(self, 'green_slider')
            and hasattr(self.green_slider, 'dragging')
            and self.green_slider.dragging
        ):
            self.green_slider.dragging = False
            self.green_slider.on_left_mouse_button_up_event(event)
        if (
            hasattr(self, 'blue_slider')
            and hasattr(self.blue_slider, 'dragging')
            and self.blue_slider.dragging
        ):
            self.blue_slider.dragging = False
            self.blue_slider.on_left_mouse_button_up_event(event)

        # Pass to other sprites
        for sprite in self.all_sprites:
            if hasattr(sprite, 'on_mouse_button_up_event') and sprite.rect.collidepoint(event.pos):
                sprite.on_mouse_button_up_event(event)

    @override
    def on_mouse_drag_event(self: Self, event: events.HashableEvent, trigger: object) -> None:
        """Handle mouse drag events.

        Args:
            event (pygame.event.Event): The event to handle
            trigger (object): The trigger object

        """
        for sprite in self.all_sprites:
            if hasattr(sprite, 'on_mouse_drag_event'):
                sprite.on_mouse_drag_event(event, trigger)

    @override
    def on_mouse_motion_event(self: Self, event: events.HashableEvent) -> None:  # type: ignore[override]
        """Handle mouse motion events.

        Args:
            event (pygame.event.Event): The event to handle

        """
        # Handle slider hover effects
        self._update_slider_hover_effects(event.pos)

        for sprite in self.all_sprites:
            if hasattr(sprite, 'on_mouse_motion_event'):
                sprite.on_mouse_motion_event(event)

    def _is_slider_hovered(self, slider_name: str, mouse_pos: tuple[int, int]) -> bool:
        """Check if the mouse is hovering over a slider.

        Args:
            slider_name: The slider attribute name (e.g., "alpha_slider")
            mouse_pos: The current mouse position (x, y)

        Returns:
            True if the mouse is hovering over the slider.

        """
        return hasattr(self, slider_name) and getattr(self, slider_name).rect.collidepoint(
            mouse_pos
        )

    def _is_slider_text_hovered(self, slider_name: str, mouse_pos: tuple[int, int]) -> bool:
        """Check if the mouse is hovering over a slider's text sprite.

        Uses absolute coordinates for text sprites.

        Args:
            slider_name: The slider attribute name (e.g., "alpha_slider")
            mouse_pos: The current mouse position (x, y)

        Returns:
            True if the mouse is hovering over the slider's text sprite.

        """
        if not hasattr(self, slider_name):
            return False
        slider = getattr(self, slider_name)
        return hasattr(slider, 'text_sprite') and slider.text_sprite.rect.collidepoint(mouse_pos)

    def _draw_alpha_slider_gradient_border(self, bbox: BitmappySprite) -> None:
        """Draw a gradient border on the alpha slider bounding box.

        The gradient goes from right (opaque) to left (transparent).

        Args:
            bbox: The alpha slider bounding box sprite

        """
        bbox.image.fill((0, 0, 0, 0))  # Clear surface

        # Draw individual pixels to create gradient effect
        width = bbox.rect.width
        height = bbox.rect.height

        # Draw border pixels with fixed gradient from right (255) to left (0)
        for x in range(int(width)):
            # Calculate opacity based on position: right side = 255, left side = 0
            pixel_alpha = int((255 * x) / width) if width > 0 else 0
            pixel_color = (pixel_alpha, 0, pixel_alpha, pixel_alpha)  # RGBA

            # Draw top and bottom border lines
            if x < width - 1:  # Don't draw the last pixel to avoid overlap
                bbox.image.set_at((x, 0), pixel_color)  # Top border
                bbox.image.set_at((x, height - 1), pixel_color)  # Bottom border

        # Draw left and right border lines
        for y in range(int(height)):
            # Left border (transparent)
            bbox.image.set_at((0, y), (0, 0, 0, 0))  # Transparent
            # Right border (opaque magenta)
            right_color = (255, 0, 255, 255)
            bbox.image.set_at((width - 1, y), right_color)

        bbox.visible = True
        bbox.dirty = 1

    def _update_slider_bbox_hover(
        self, bbox_attr: str, *, is_hovered: bool, border_color: tuple[int, int, int]
    ) -> None:
        """Update a slider bounding box border based on hover state.

        Args:
            bbox_attr: The bounding box attribute name (e.g., "red_slider_bbox")
            is_hovered: Whether the mouse is currently hovering over the slider
            border_color: The RGB color for the border

        """
        if not hasattr(self, bbox_attr):
            return

        bbox = getattr(self, bbox_attr)
        if is_hovered and not bbox.visible:
            bbox.image.fill((0, 0, 0, 0))  # Clear surface
            pygame.draw.rect(
                bbox.image,
                border_color,
                (0, 0, bbox.rect.width, bbox.rect.height),
                2,
            )
            bbox.visible = True
            bbox.dirty = 1
        elif not is_hovered and bbox.visible:
            bbox.image.fill((0, 0, 0, 0))  # Clear surface
            bbox.visible = False
            bbox.dirty = 1

    def _update_slider_text_hover_border(self, slider_name: str, *, is_text_hovered: bool) -> None:
        """Update a slider text sprite's white hover border.

        Args:
            slider_name: The slider attribute name (e.g., "red_slider")
            is_text_hovered: Whether the mouse is hovering over the text sprite

        """
        if not (hasattr(self, slider_name) and hasattr(getattr(self, slider_name), 'text_sprite')):
            return

        text_sprite = getattr(self, slider_name).text_sprite
        if is_text_hovered:
            # Add white border to text sprite
            if not hasattr(text_sprite, 'hover_border_added'):
                # Create a white border by drawing on the text sprite's image
                pygame.draw.rect(
                    text_sprite.image,
                    (255, 255, 255),
                    (0, 0, text_sprite.rect.width, text_sprite.rect.height),
                    2,
                )
                text_sprite.hover_border_added = True
                text_sprite.dirty = 1
        # Remove white border
        elif hasattr(text_sprite, 'hover_border_added') and text_sprite.hover_border_added:
            # Force text sprite to redraw without border
            text_sprite.update_text(text_sprite.text)
            text_sprite.hover_border_added = False
            text_sprite.dirty = 1

    def _update_slider_hover_effects(self, mouse_pos: tuple[int, int]) -> None:
        """Update slider hover effects based on mouse position.

        Args:
            mouse_pos: The current mouse position (x, y)

        """
        # Check if mouse is hovering over any slider
        alpha_hover = self._is_slider_hovered('alpha_slider', mouse_pos)
        red_hover = self._is_slider_hovered('red_slider', mouse_pos)
        green_hover = self._is_slider_hovered('green_slider', mouse_pos)
        blue_hover = self._is_slider_hovered('blue_slider', mouse_pos)

        # Update alpha slider border (uses gradient, not solid border)
        if hasattr(self, 'alpha_slider_bbox') and self.alpha_slider_bbox is not None:
            if alpha_hover and not self.alpha_slider_bbox.visible:
                self._draw_alpha_slider_gradient_border(self.alpha_slider_bbox)
            elif not alpha_hover and self.alpha_slider_bbox.visible:
                # Hide alpha border
                self.alpha_slider_bbox.image.fill((0, 0, 0, 0))  # Clear surface
                self.alpha_slider_bbox.visible = False
                self.alpha_slider_bbox.dirty = 1

        # Update colored slider borders
        self._update_slider_bbox_hover(
            'red_slider_bbox', is_hovered=red_hover, border_color=(255, 0, 0)
        )
        self._update_slider_bbox_hover(
            'green_slider_bbox', is_hovered=green_hover, border_color=(0, 255, 0)
        )
        self._update_slider_bbox_hover(
            'blue_slider_bbox', is_hovered=blue_hover, border_color=(0, 0, 255)
        )

        # Update text box hover effects (white borders)
        # Check if mouse is hovering over any slider text boxes (use absolute coordinates)
        slider_names = ['alpha_slider', 'red_slider', 'green_slider', 'blue_slider']
        for slider_name in slider_names:
            text_hovered = self._is_slider_text_hovered(slider_name, mouse_pos)
            self._update_slider_text_hover_border(slider_name, is_text_hovered=text_hovered)

    def _on_debug_text_change(self, new_text: str) -> None:
        """Handle debug text change.

        Args:
            new_text: The new text content

        """
        self._update_sprite_description(new_text)

    def _has_single_animation_canvas(self) -> bool:
        """Check if the canvas has exactly one animation.

        Returns:
            True if the canvas has a single animation.

        """
        if not (hasattr(self, 'canvas') and self.canvas):
            return False
        if not (hasattr(self.canvas, 'animated_sprite') and self.canvas.animated_sprite):
            return False
        return len(self.canvas.animated_sprite._animations) == 1  # type: ignore[reportPrivateUsage]

    @override
    def on_text_submit_event(self, text: str) -> None:
        """Handle text submission from MultiLineTextBox."""
        # Don't update sprite description here - only update when AI generation actually happens
        self.log.info(f"AI Sprite Generation Request: '{text}'")
        self.log.debug(f'Text length: {len(text)}')
        self.log.debug(f'Text type: {type(text)}')

        if not self.ai_request_queue:
            self.log.error('AI request queue is not available')
            if hasattr(self, 'debug_text'):
                self.debug_text.text = 'AI processing not available'
            return

        if hasattr(self, 'ai_process') and self.ai_process and not self.ai_process.is_alive():
            self.log.error('AI process is not alive')
            if hasattr(self, 'debug_text'):
                self.debug_text.text = 'AI process not available'
            return

        relevant_examples: Any = self._gather_training_examples_from_frame(text)  # type: ignore[attr-defined]
        refinement_result: Any = self._serialize_current_sprite_for_refinement()  # type: ignore[attr-defined]
        is_refinement = bool(refinement_result[0])  # type: ignore[reportUnknownArgumentType]
        last_sprite_content: str | None = (
            str(refinement_result[1]) if refinement_result[1] else None  # pyright: ignore[reportUnknownArgumentType]
        )
        conversation_history: list[dict[str, str]] | None = (
            list(refinement_result[2]) if refinement_result[2] else None  # pyright: ignore[reportUnknownArgumentType]
        )

        if is_refinement and last_sprite_content:
            messages = build_refinement_messages(
                user_request=text.strip(),
                last_sprite_content=last_sprite_content,
                conversation_history=conversation_history,
                include_size_hint=True,
                include_animation_hint=True,
            )
        else:
            messages = build_sprite_generation_messages(
                user_request=text.strip(),
                training_examples=relevant_examples,  # type: ignore[arg-type]
                max_examples=3,
                include_size_hint=True,
                include_animation_hint=True,
            )

        self._submit_ai_request(  # type: ignore[attr-defined]
            text, messages, relevant_examples, conversation_history, last_sprite_content
        )

    @override
    def setup(self) -> None:
        """Set up the bitmap editor scene."""
        super().setup()

        # Initialize AI processing components
        self.pending_ai_requests: dict[str, Any] = {}
        self.ai_request_queue: multiprocessing.Queue[AIRequest] | None = None
        self.ai_response_queue: multiprocessing.Queue[tuple[str, AIResponse]] | None = None
        self.ai_process: multiprocessing.Process | None = None

        # Initialize conversation tracking for multi-turn refinement
        self.last_successful_sprite_content = None
        self.last_conversation_history = None

        # Check if we're in the main process
        if multiprocessing.current_process().name == 'MainProcess':
            self.log.info('Initializing AI worker process...')

            try:
                self.ai_request_queue = multiprocessing.Queue()
                self.ai_response_queue = multiprocessing.Queue()

                self.ai_process = multiprocessing.Process(
                    target=ai_worker,
                    args=(self.ai_request_queue, self.ai_response_queue),
                    daemon=True,
                )

                self.ai_process.start()
                self.log.info(f'AI worker process started with PID: {self.ai_process.pid}')

            except (OSError, RuntimeError):
                self.log.exception('Error initializing AI worker process')
                self.ai_request_queue = None
                self.ai_response_queue = None
                self.ai_process = None
        else:
            self.log.warning('Not in main process, AI processing not available')

    def _process_ai_response(self, request_id: str, response: AIResponse) -> None:
        """Process an AI response with automatic validation-driven retry."""
        self.log.info(f'Got AI response for request {request_id}')

        # Handle empty response
        if response.content is None:
            self.log.error('AI response content is None, cannot save sprite')
            if hasattr(self, 'debug_text'):
                self.debug_text.text = 'AI response was empty'
            # Clean up
            if request_id in self.pending_ai_requests:
                del self.pending_ai_requests[request_id]
            return

        # Get request state
        if request_id not in self.pending_ai_requests:
            self.log.warning(f'Request {request_id} not found in pending requests')
            self._load_ai_sprite(request_id, response.content)
            return

        request_state = self.pending_ai_requests[request_id]

        # Validate the response
        is_valid, validation_error = validate_ai_response(response.content)

        if not is_valid:
            self.log.warning(f'AI response validation failed: {validation_error}')

            # Check if we can retry
            if request_state.retry_count < AI_VALIDATION_MAX_RETRIES:
                # Trigger retry with targeted prompt
                request_state.retry_count += 1
                request_state.last_error = validation_error

                self.log.info(
                    'Retrying request (attempt'
                    f' {request_state.retry_count + 1}/{AI_VALIDATION_MAX_RETRIES + 1})'
                )

                # Build retry prompt with specific corrections
                retry_prompt = _build_retry_prompt(request_state.original_prompt, validation_error)

                # Rebuild messages with retry prompt
                messages = build_sprite_generation_messages(
                    user_request=retry_prompt,
                    training_examples=request_state.training_examples,
                    max_examples=3,
                    include_size_hint=True,
                    include_animation_hint=True,
                )

                # Create new request with same ID
                retry_request = AIRequest(
                    prompt=str(messages),
                    request_id=request_id,  # Reuse same ID
                    messages=messages,
                )

                # Submit retry
                assert self.ai_request_queue is not None
                self.ai_request_queue.put(retry_request)

                # Update UI
                if hasattr(self, 'debug_text'):
                    self.debug_text.text = (
                        f'Retrying with corrections... (attempt'
                        f' {request_state.retry_count + 1}/{AI_VALIDATION_MAX_RETRIES + 1})\n'
                        f'Error: {validation_error}'
                    )

                # DON'T delete from pending_ai_requests - we're retrying
                return
            # Max retries reached, load anyway and show error
            self.log.error(
                f'Max retries ({AI_VALIDATION_MAX_RETRIES}) reached, loading sprite anyway'
            )
            if hasattr(self, 'debug_text'):
                self.debug_text.text = (
                    f'Failed after {AI_VALIDATION_MAX_RETRIES} retries:\n{validation_error}\n\n'
                    f'Attempting to load anyway...'
                )

        # Valid response or max retries reached - load the sprite
        self._load_ai_sprite(request_id, response.content)

        # Remove from pending requests
        if request_id in self.pending_ai_requests:
            del self.pending_ai_requests[request_id]

    def _log_ai_response_content(self, content: str) -> None:
        """Log AI response content for debugging."""
        # Count animations and frames in response
        anim_count = content.count('[[animation]]')
        frame_count = content.count('[[animation.frame]]')
        self.log.info(
            f'AI response received, content length: {len(content)}, {anim_count} animations,'
            f' {frame_count} frames'
        )

        # Debug: Dump the sprite content
        self.log.info('=== AI GENERATED SPRITE CONTENT ===')
        self.log.info(f'AI Generated Content:\n{content}')
        self.log.info('=== END SPRITE CONTENT ===')

    def _prepare_ai_content(self, request_id: str, content: str) -> str:
        """Clean AI response content and add description if needed.

        Returns:
            str: The resulting string.

        """
        # Check if this is an error message BEFORE cleaning
        if self._is_ai_error_message(content):
            self.log.warning('AI returned error/apology message, skipping processing')
            return content

        # Get the original user prompt from the request
        original_prompt = ''
        if request_id in self.pending_ai_requests:
            request_state = self.pending_ai_requests[request_id]
            original_prompt = request_state.original_prompt
            self.log.debug(f"Using original prompt: '{original_prompt}'")

        # Clean up any markdown formatting from AI response
        cleaned_content = self._clean_ai_response(content)

        # Check if this is an error message - if so, return it as-is
        if cleaned_content.strip() in {'AI features not available', 'AI features not available.'}:
            self.log.warning('AI returned error message, skipping TOML processing')
            return cleaned_content

        # Add description to the content if we have an original prompt
        if original_prompt and ai_training_state['format'] == 'toml':
            # Parse the TOML content with robust duplicate key handling
            try:
                data = parse_toml_robustly(cleaned_content, self.log)
                # Normalize the TOML data to convert escaped newlines to actual newlines
                data = _normalize_toml_data(data)
                if 'sprite' not in data:
                    data['sprite'] = {}
                data['sprite']['description'] = original_prompt

                # Manually construct TOML to preserve formatting instead of using toml.dumps()
                cleaned_content = self._construct_toml_with_preserved_formatting(data)
                self.log.debug(f"Added description to TOML content: '{original_prompt}'")
            except (KeyError, ValueError) as e:
                self.log.warning(f'Failed to add description to TOML content: {e}')

        return cleaned_content

    def _construct_toml_with_preserved_formatting(self, data: dict[str, Any]) -> str:
        """Construct TOML content while preserving original formatting for pixel data.

        Args:
            data: Parsed TOML data

        Returns:
            TOML content string with preserved formatting

        """
        lines: list[str] = []

        # Add sprite section
        if 'sprite' in data:
            lines.append('[sprite]')
            sprite_data = data['sprite']
            if 'name' in sprite_data:
                lines.append(f'name = "{sprite_data["name"]}"')
            if 'description' in sprite_data:
                lines.append(f'description = """{sprite_data["description"]}"""')
            if 'pixels' in sprite_data:
                lines.extend((
                    'pixels = """',
                    sprite_data['pixels'],
                    '"""',
                ))
            lines.append('')

        # Add animation sections
        if 'animation' in data:
            for animation in data['animation']:
                lines.extend([
                    '[[animation]]',
                    f'namespace = "{animation["namespace"]}"',
                    f'frame_interval = {animation["frame_interval"]}',
                    f'loop = {str(animation["loop"]).lower()}',
                    '',
                ])

                for frame in animation.get('frame', []):
                    lines.extend([
                        '[[animation.frame]]',
                        f'namespace = "{animation["namespace"]}"',
                        f'frame_index = {frame["frame_index"]}',
                        'pixels = """',
                        frame['pixels'],
                        '"""',
                        '',
                    ])

        # Add colors section
        if 'colors' in data:
            lines.append('[colors]')
            # Remove duplicate color keys by using a set to track seen keys
            seen_colors: set[str] = set()
            for color_key, color_data in data['colors'].items():
                if color_key not in seen_colors:
                    seen_colors.add(color_key)
                    lines.extend([
                        f'[colors."{color_key}"]',
                        f'red = {color_data["red"]}',
                        f'green = {color_data["green"]}',
                        f'blue = {color_data["blue"]}',
                        '',
                    ])
                else:
                    self.log.warning(f"Skipping duplicate color definition for '{color_key}'")

        return '\n'.join(lines)

    def _create_temp_file_from_content(self, content: str) -> str:
        """Create temporary file from AI content and return the path.

        Returns:
            str: The resulting string.

        """
        # Determine file extension based on training format
        file_extension = (
            f'.{ai_training_state["format"]}' if ai_training_state['format'] else '.toml'
        )

        with tempfile.NamedTemporaryFile(
            mode='w', suffix=file_extension, delete=False, encoding='utf-8'
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
            self.log.info(f'Saved AI response to temp file: {tmp_path}')
            return tmp_path

    def _load_animated_ai_sprite(self, tmp_path: str) -> None:
        """Load animated AI sprite into canvas."""
        self.log.info('Loading animated sprite into existing animated canvas...')

        mock_event = MockEvent(text=tmp_path)
        self.canvas.on_load_file_event(mock_event)  # type: ignore[arg-type]

        # Animation will be started by on_load_file_event, no need to start here
        self.log.info('AI animated sprite loaded successfully')

    def _load_static_ai_sprite(self, tmp_path: str) -> None:
        """Load static AI sprite into canvas."""
        self.log.info('Loading static sprite into animated canvas...')

        # Load the static sprite into the current animated canvas
        mock_event = MockEvent(text=tmp_path)
        self.canvas.on_load_file_event(mock_event)  # type: ignore[arg-type]

        # Animation will be started by on_load_file_event, no need to start here
        # Just verify the state after loading
        if hasattr(self.canvas, 'animated_sprite') and self.canvas.animated_sprite:
            self.log.debug(
                'AI sprite loaded - animated_sprite state: '
                f"current_animation='{self.canvas.animated_sprite.current_animation}', "
                f'is_playing={self.canvas.animated_sprite.is_playing}'
            )
            animations = (
                list(self.canvas.animated_sprite._animations.keys())  # type: ignore[reportPrivateUsage]
                if hasattr(self.canvas.animated_sprite, '_animations')
                else 'No _animations'
            )
            self.log.debug(f'AI sprite animations: {animations}')

            # Note: Live preview functionality is now integrated into the film strip

        # Force canvas redraw to show the new sprite
        self.canvas.dirty = 1
        self.canvas.force_redraw()

        # Also force a scene update to ensure everything is redrawn
        if hasattr(self, 'all_sprites'):
            for sprite in self.all_sprites:
                if hasattr(sprite, 'dirty'):
                    sprite.dirty = 1

        self.log.info('AI static sprite loaded successfully into animated canvas')

    def _update_ui_after_ai_load(self, request_id: str) -> None:
        """Update UI components after AI sprite load."""
        if hasattr(self, 'debug_text'):
            # Restore the original prompt text that was submitted
            if request_id in self.pending_ai_requests:
                request_state = self.pending_ai_requests[request_id]
                original_prompt = request_state.original_prompt
            else:
                original_prompt = 'Enter a description of the sprite you want to create:'

            self.debug_text.text = original_prompt

    def _cleanup_ai_request(self, request_id: str) -> None:
        """Clean up pending AI request."""
        # Clean up the pending request
        if request_id in self.pending_ai_requests:
            del self.pending_ai_requests[request_id]

    def _check_current_frame_has_content(self) -> bool:
        """Check if the current frame has any non-magenta pixels.

        Returns:
            True if frame has content (non-magenta pixels), False if all magenta

        """
        try:
            if not (hasattr(self, 'canvas') and hasattr(self.canvas, 'pixels')):
                self.log.debug('No canvas or canvas.pixels found, returning False')
                return False

            pixels = self.canvas.pixels
            self.log.debug(f'Checking frame content: {len(pixels)} pixels')
            if not pixels:
                self.log.debug('No pixels found, returning False')
                return False

            # Check if any pixel is not magenta (255, 0, 255)
            non_magenta_count = 0
            for i, pixel in enumerate(pixels):
                color: Any = self._pixel_to_rgb(pixel)  # type: ignore[attr-defined]
                if color != (255, 0, 255):
                    non_magenta_count += 1
                    if non_magenta_count <= DEBUG_LOG_FIRST_N_PIXELS:
                        self.log.debug(f'Found non-magenta pixel {i}: {color}')

            self.log.debug(
                f'Found {non_magenta_count} non-magenta pixels out of {len(pixels)} total'
            )
            return non_magenta_count > 0
        except (AttributeError, TypeError, IndexError):
            self.log.exception('Error checking frame content')
            return False

    def _save_current_frame_to_temp_toml(self) -> str | None:
        """Save the current frame to a temporary TOML file.

        Returns:
            Path to the temporary TOML file, or None if failed

        """
        try:
            import os
            import tempfile

            # Get current frame data
            if not hasattr(self, 'canvas') or not hasattr(self.canvas, 'pixels'):
                return None

            pixels = self.canvas.pixels
            if not pixels:
                return None

            # Create temporary file
            temp_fd, temp_path = tempfile.mkstemp(suffix='.toml', prefix='bitmappy_frame_')
            os.close(temp_fd)  # Close the file descriptor, we'll use the path

            # Generate TOML content with single-char glyphs only
            # This ensures the AI sees only single-character glyphs in the training data
            toml_content = self._generate_frame_toml_content(pixels, force_single_char_glyphs=True)

            # Write to temporary file
            Path(temp_path).write_text(toml_content, encoding='utf-8')

            self.log.info(f'Saved current frame to temporary TOML: {temp_path}')
            return temp_path

        except (OSError, ValueError, AttributeError, TypeError):
            self.log.exception('Error saving frame to temp TOML')
            return None

    def _save_current_strip_to_temp_toml(self) -> str | None:
        """Save the current animation strip to a temporary TOML file.

        Returns:
            Path to the temporary TOML file, or None if failed

        """
        try:
            import os
            import tempfile

            # Get current animation data
            if not hasattr(self, 'canvas') or not hasattr(self.canvas, 'animated_sprite'):
                return None

            animated_sprite = self.canvas.animated_sprite
            if not animated_sprite or not hasattr(animated_sprite, '_animations'):
                return None

            current_animation = getattr(self.canvas, 'current_animation', None)
            if not current_animation or current_animation not in animated_sprite._animations:  # type: ignore[reportPrivateUsage]
                return None

            # Create a new AnimatedSprite with just the current animation
            from glitchygames.sprites.animated import AnimatedSprite

            # Get the current animation frames
            current_frames = animated_sprite._animations[current_animation]  # type: ignore[reportPrivateUsage]

            # Create new sprite with the current animation
            new_sprite = AnimatedSprite()
            new_sprite.name = f'current_strip_{current_animation}'
            new_sprite.description = f'Current animation strip: {current_animation}'

            # Copy the animation data
            new_sprite._animations = {current_animation: current_frames}  # type: ignore[reportPrivateUsage]
            # Set the animation order to only include this animation
            new_sprite._animation_order = [current_animation]  # type: ignore[reportPrivateUsage]
            # The sprite will automatically play the first (and only) animation

            # Create temporary file
            temp_fd, temp_path = tempfile.mkstemp(suffix='.toml', prefix='bitmappy_strip_')
            os.close(temp_fd)  # Close the file descriptor, we'll use the path

            # Save the sprite to TOML using the existing save method
            new_sprite.save(temp_path)

            self.log.info(f'Saved current strip to temporary TOML: {temp_path}')
            return temp_path

        except (OSError, ValueError, AttributeError, KeyError, TypeError):
            self.log.exception('Error saving strip to temp TOML')
            return None

    def _generate_frame_toml_content(
        self, pixels: list[tuple[int, ...]], *, force_single_char_glyphs: bool = False
    ) -> str:
        """Generate TOML content for the current frame.

        Args:
            pixels: List of pixel colors
            force_single_char_glyphs: If True, limit to 64 single-character glyphs for AI training

        Returns:
            TOML content string

        """
        try:
            width = self.canvas.pixels_across
            height = self.canvas.pixels_tall

            unique_colors: Any = self._collect_unique_colors_from_pixels(pixels)  # type: ignore[attr-defined]

            if force_single_char_glyphs and len(unique_colors) > MAX_COLORS_FOR_AI_TRAINING:  # type: ignore[arg-type]
                self.log.info(f'Quantizing {len(unique_colors)} colors down to 64 for AI training')  # type: ignore[arg-type]
                unique_colors = self._quantize_colors_if_needed(pixels, 64)  # type: ignore[call-arg]

            color_to_glyph: Any = None
            sorted_colors: Any = None
            color_to_glyph, sorted_colors = self._build_color_to_glyph_mapping(  # type: ignore[call-arg, assignment]
                unique_colors,
                has_transparency=False,
                force_single_char_glyphs=force_single_char_glyphs,  # type: ignore[call-arg]
            )

            pixel_string: Any = self._build_pixel_string(  # type: ignore[attr-defined]
                pixels,
                width,
                height,
                color_to_glyph,
                sorted_colors,
                force_single_char_glyphs=force_single_char_glyphs,
            )

            # Generate color definitions using the consistent mapping
            color_definitions = ''
            for color in sorted_colors:  # type: ignore[union-attr]
                if isinstance(color, tuple) and len(color) >= RGB_COMPONENT_COUNT:  # type: ignore[arg-type]
                    r = int(color[0])  # type: ignore[reportUnknownArgumentType]
                    g = int(color[1])  # type: ignore[reportUnknownArgumentType]
                    b = int(color[2])  # type: ignore[reportUnknownArgumentType]
                    glyph: str = color_to_glyph[color]  # type: ignore[index]
                    color_definitions += (
                        f'[colors."{glyph}"]\nred = {r}\ngreen = {g}\nblue = {b}\n\n'
                    )

            # Always ensure block character is mapped to magenta for transparency
            if MAGENTA_TRANSPARENT in color_to_glyph:
                color_definitions += (
                    f'[colors."{TRANSPARENT_GLYPH}"]\nred = 255\ngreen = 0\nblue = 255\n\n'
                )

            # Build complete TOML
            return f"""[sprite]
name = "current_frame"
pixels = \"\"\"
{pixel_string}
\"\"\"

{color_definitions}"""

        except (AttributeError, IndexError, KeyError, TypeError, ValueError):
            self.log.exception('Error generating frame TOML content')
            return ''

    def _get_glyph_for_color(self, color: tuple[int, int, int] | int) -> str:
        """Get a glyph for a specific color.

        Args:
            color: RGB color tuple or integer color value

        Returns:
            Single character glyph from first 64 characters of SPRITE_GLYPHS

        """
        # Use only first 64 characters for consistent, manageable palette
        available_glyphs = SPRITE_GLYPHS[:64]
        # Simple hash-based assignment to ensure consistent glyph for same color
        color_hash = hash(color) % len(available_glyphs)
        return available_glyphs[color_hash]

    def _load_temp_toml_as_example(self, temp_toml_path: str) -> dict[str, Any] | None:
        """Load a temporary TOML file as a training example.

        Args:
            temp_toml_path: Path to the temporary TOML file

        Returns:
            Training example dict, or None if failed

        """
        try:
            import tomllib

            # Read the file as text first to preserve newlines
            file_content = Path(temp_toml_path).read_text(encoding='utf-8')

            # Extract pixel data directly from the text to preserve newlines
            pixels_data = ''
            in_pixels_section = False
            for line in file_content.split('\n'):
                if line.strip() == 'pixels = """':
                    in_pixels_section = True
                    continue
                if line.strip() == '"""' and in_pixels_section:
                    in_pixels_section = False
                    break
                if in_pixels_section:
                    pixels_data += line + '\n'

            # Remove the trailing newline
            pixels_data = pixels_data.removesuffix('\n')

            # Load the TOML file for other data (colors, etc.)
            with Path(temp_toml_path).open(mode='rb') as f:
                config_data = tomllib.load(f)

            # Convert to training example format
            sprite_data = {
                'name': config_data.get('sprite', {}).get('name', 'current_frame'),
                'sprite_type': 'static',
                'pixels': pixels_data,  # Use the directly extracted pixel data
                'colors': config_data.get('colors', {}),
            }

            # Clean up temporary file
            try:
                Path(temp_toml_path).unlink()
                self.log.debug(f'Cleaned up temporary file: {temp_toml_path}')
            except OSError as cleanup_error:
                self.log.warning(f'Failed to clean up temp file {temp_toml_path}: {cleanup_error}')

            self.log.info(f'Loaded current frame as training example: {sprite_data["name"]}')
            return sprite_data

        except (OSError, ValueError, KeyError, TypeError):
            self.log.exception('Error loading temp TOML as example')
            return None

    def _is_ai_error_message(self, content: str) -> bool:
        """Check if AI response is an error message rather than valid sprite code.

        Uses the AI module's validation function for comprehensive checking.

        Args:
            content: The AI response content to check

        Returns:
            True if the content appears to be an error/apology message

        """
        # Use the new AI module's validation function
        is_valid, error_msg = validate_ai_response(content)

        if not is_valid:
            self.log.warning(f'AI response validation failed: {error_msg}')
            return True

        return False

    def _get_original_prompt_for_request(self, request_id: str) -> str:
        """Get the original prompt associated with a pending AI request.

        Args:
            request_id: The AI request identifier.

        Returns:
            The original prompt string, or empty string if not found.

        """
        if request_id in self.pending_ai_requests:
            return self.pending_ai_requests[request_id].original_prompt
        return ''

    def _handle_ai_unavailable(self, request_id: str) -> None:
        """Handle AI returning an unavailable message.

        Args:
            request_id: The AI request identifier.

        """
        self.log.warning('AI returned error message, cannot load sprite')
        if hasattr(self, 'debug_text'):
            self.debug_text.text = 'AI features not available. Please check your AI configuration.'
        self._cleanup_ai_request(request_id)

    def _handle_ai_error_message(self, request_id: str, content: str) -> None:
        """Handle AI returning an error/apology message instead of sprite code.

        Args:
            request_id: The AI request identifier.
            content: The AI response content.

        """
        self.log.warning('AI returned error/apology message instead of sprite code')
        self.log.debug(f'Detected error message, content preview: {content[:100]}...')

        original_prompt = self._get_original_prompt_for_request(request_id)

        if hasattr(self, 'debug_text'):
            # Append the error message to the input box, with original prompt at the bottom
            current_text = getattr(self.debug_text, 'text', '')
            error_text = current_text + '\n\n' + content if current_text else content

            # Add original prompt at the bottom if we have it
            if original_prompt:
                error_text = error_text + '\n\n--- Original Prompt ---\n' + original_prompt

            self.debug_text.text = error_text
            self.log.info('Appended error message to debug_text input box')

        self._cleanup_ai_request(request_id)

    def _detect_and_load_ai_sprite(self, tmp_path: str) -> None:
        """Detect sprite type from a temp file and load it into the canvas.

        Args:
            tmp_path: Path to the temporary TOML file.

        """
        self.log.info('Detecting AI sprite type...')

        # Use SpriteFactory to detect the sprite type
        sprite = SpriteFactory.load_sprite(filename=tmp_path)
        is_animated = hasattr(sprite, '_animations') and sprite._animations  # type: ignore[reportPrivateUsage]
        self.log.info(f'AI sprite type: {"Animated" if is_animated else "Static"}')
        self.log.debug(f'AI sprite has _animations: {hasattr(sprite, "_animations")}')
        if hasattr(sprite, '_animations'):
            self.log.debug(f'AI sprite _animations: {list(sprite._animations.keys())}')  # type: ignore[reportPrivateUsage]
            self.log.debug(f'AI sprite current_animation: {sprite.current_animation}')
            self.log.debug(f'AI sprite is_playing: {sprite.is_playing}')

        if is_animated:
            self._load_animated_ai_sprite(tmp_path)
        else:
            self._load_static_ai_sprite(tmp_path)

    def _update_sprite_description(self, original_prompt: str) -> None:
        """Update the loaded sprite's description with the original AI prompt.

        Args:
            original_prompt: The original prompt used to generate the sprite.

        """
        if not (
            original_prompt
            and hasattr(self, 'canvas')
            and self.canvas
            and hasattr(self.canvas, 'animated_sprite')
            and self.canvas.animated_sprite
        ):
            return

        self.canvas.animated_sprite.description = original_prompt
        self.log.info(f"Updated sprite description with generation prompt: '{original_prompt}'")

    def _update_conversation_history(
        self, request_id: str, original_prompt: str, cleaned_content: str
    ) -> None:
        """Update conversation history for multi-turn AI refinement.

        Args:
            request_id: The AI request identifier.
            original_prompt: The original prompt sent to the AI.
            cleaned_content: The cleaned AI response content.

        """
        if request_id not in self.pending_ai_requests:
            return

        request_state = self.pending_ai_requests[request_id]
        # Build conversation history: previous history + new user request + assistant response
        new_history: list[dict[str, str]] = []
        if request_state.conversation_history:
            new_history.extend(request_state.conversation_history)

        # Add user's request
        new_history.extend((
            {'role': 'user', 'content': original_prompt},
            # Add assistant's response (cleaned sprite content)
            {'role': 'assistant', 'content': cleaned_content},
        ))

        # Save for next request
        self.last_conversation_history = new_history
        self.log.info(f'Updated conversation history (now {len(new_history)} messages)')

    def _handle_ai_sprite_load_error(
        self, sprite_error: Exception, request_id: str, content: str
    ) -> None:
        """Handle errors that occur during AI sprite loading.

        Args:
            sprite_error: The exception that occurred.
            request_id: The AI request identifier.
            content: The original AI response content.

        """
        self.log.error('Failed to load AI sprite', exc_info=sprite_error)

        original_prompt = self._get_original_prompt_for_request(request_id)

        if not hasattr(self, 'debug_text'):
            return

        # Show error with original prompt at the bottom
        error_text = f'Error loading AI sprite: {sprite_error}'
        if original_prompt:
            error_text = error_text + '\n\n--- Original Prompt ---\n' + original_prompt

        # Also include the AI response content for debugging
        error_text = error_text + '\n\n--- AI Response ---\n' + content

        self.debug_text.text = error_text

    def _load_ai_sprite(self, request_id: str, content: str) -> None:
        """Load sprite from AI content using SpriteFactory APIs."""
        # Log AI response content for debugging
        self._log_ai_response_content(content)

        # Check if this is an error message
        if content.strip() in {'AI features not available', 'AI features not available.'}:
            self._handle_ai_unavailable(request_id)
            return

        # Check if this looks like an error/apology message
        if self._is_ai_error_message(content):
            self._handle_ai_error_message(request_id, content)
            return

        # Prepare AI content (clean and add description if needed)
        cleaned_content = self._prepare_ai_content(request_id, content)
        original_prompt = self._get_original_prompt_for_request(request_id)

        # Create temporary file from content
        tmp_path = self._create_temp_file_from_content(cleaned_content)

        # Detect sprite type and load appropriately
        try:
            self._detect_and_load_ai_sprite(tmp_path)
            self._update_sprite_description(original_prompt)

            # Save successful sprite content for future refinements
            self.last_successful_sprite_content = cleaned_content
            self.log.info('Saved sprite content for potential refinement requests')

            self._update_conversation_history(request_id, original_prompt, cleaned_content)

            # Update UI components
            self._update_ui_after_ai_load(request_id)

            # Clean up pending request
            self._cleanup_ai_request(request_id)

        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            pygame.error,
        ) as sprite_error:
            self._handle_ai_sprite_load_error(sprite_error, request_id, content)
        # Note: Temp file is kept for debugging - remove this comment when done debugging

    def _clean_ai_response(self, content: str) -> str:
        """Clean up markdown formatting from AI response using AI module.

        Returns:
            str: The resulting string.

        """
        # Check if this is an error message instead of valid content
        if content.strip() in {'AI features not available', 'AI features not available.'}:
            self.log.warning('AI returned error message instead of sprite content')
            return content  # Return as-is for error handling upstream

        # Use the new AI module's cleaning function
        cleaned = ai_clean_response(content)
        self.log.info('Cleaned AI response using AI module')
        return cleaned or content

    def _update_film_strip_animation_timing(self) -> None:
        """Update film strip animations and mark sprites dirty for redraw."""
        # Update film strip animations
        # This ensures each film strip has its own independent animation timing
        if hasattr(self, 'film_strips') and self.film_strips:
            for film_strip in self.film_strips.values():
                if hasattr(film_strip, 'update_animations'):
                    film_strip.update_animations(self.dt)

        # Mark all film strip sprites as dirty for animation updates (every frame)
        # This ensures the sprite group redraws film strips when animations advance
        if hasattr(self, 'film_strip_sprites') and self.film_strip_sprites:
            for film_strip_sprite in self.film_strip_sprites.values():
                film_strip_sprite.dirty = 1

        # Also mark film strip sprites as dirty for continuous animation updates
        # This is a backup mechanism to ensure film strips stay dirty when needed
        self._mark_film_strip_sprites_dirty()

    def _update_animated_canvas(self) -> None:
        """Update the animated canvas with delta time, film strips, and frame transitions."""
        # Debug animation state
        if hasattr(self, '_debug_animation_counter'):
            self._debug_animation_counter += 1
        else:
            self._debug_animation_counter = 1

        # Log animation state approximately once per second, regardless of fps
        if not hasattr(self, '_last_animation_log_time'):
            self._last_animation_log_time = time.time()
        current_time = time.time()
        if current_time - self._last_animation_log_time >= 1.0:
            self._last_animation_log_time = current_time

        # Pass delta time to the canvas for animation updates
        self.canvas.update_animation(self.dt)

        self._update_film_strip_animation_timing()

        # Mark the main scene as dirty every frame to ensure sprite groups are updated
        self.dirty = 1

        # Render visual indicators for multi-controller system
        self._render_visual_indicators()

        # Check for frame transitions
        frame_index = self.canvas.animated_sprite.current_frame

        if not hasattr(self, '_last_animation_frame') or self._last_animation_frame != frame_index:
            self._last_animation_frame = frame_index

            # Don't update the canvas frame - it should stay on the frame being edited
            # Only the live preview should animate

            # Note: Live preview functionality is now integrated into the film strip

    def _check_ai_responses(self) -> None:
        """Check for and process any pending AI responses."""
        if not (hasattr(self, 'ai_response_queue') and self.ai_response_queue):
            return

        try:
            response_data = self.ai_response_queue.get_nowait()

            if response_data:
                request_id, response = response_data
                self._process_ai_response(request_id, response)

        except Empty:
            # This is normal - no responses available
            pass
        except (ValueError, TypeError, AttributeError, OSError):
            self.log.exception('Error processing AI response')

    @override
    def update(self) -> None:
        """Update scene state."""
        super().update()  # Call the base Scene.update() method

        # Update continuous slider adjustments
        self._update_slider_continuous_adjustments()

        # Update continuous canvas movements
        self._update_canvas_continuous_movements()

        # Check for single click timer
        self._check_single_click_timer()

        # Update the animated canvas with delta time
        if (
            hasattr(self, 'canvas')
            and hasattr(self.canvas, 'animated_sprite')
            and self.canvas.animated_sprite
        ):
            self._update_animated_canvas()

        # Check for AI responses
        self._check_ai_responses()

    def _shutdown_ai_worker(self) -> None:
        """Signal AI worker to shut down."""
        if hasattr(self, 'ai_request_queue') and self.ai_request_queue:
            try:
                self.log.info('Sending shutdown signal to AI worker...')
                self.ai_request_queue.put(None, timeout=1.0)  # type: ignore[arg-type]  # Sentinel for shutdown
                self.log.info('Shutdown signal sent successfully')
            except (OSError, ValueError):
                self.log.exception('Error sending shutdown signal')

    def _cleanup_ai_process(self) -> None:
        """Clean up AI process."""
        if not hasattr(self, 'ai_process') or not self.ai_process:
            return

        try:
            self.log.info('Waiting for AI process to finish...')
            self.ai_process.join(timeout=2.0)  # Increased timeout
            if self.ai_process.is_alive():
                self.log.info('AI process still alive, terminating...')
                self.ai_process.terminate()
                self.ai_process.join(timeout=1.0)  # Longer timeout for terminate
                if self.ai_process.is_alive():
                    self.log.info('AI process still alive, force killing...')
                    self.ai_process.kill()  # Force kill if still alive
                    self.ai_process.join(timeout=0.5)  # Final cleanup
            self.log.info('AI process cleanup completed')
        except (OSError, RuntimeError, AttributeError):
            self.log.exception('Error during AI process cleanup')
        finally:
            # Ensure process is cleaned up
            if hasattr(self, 'ai_process') and self.ai_process:
                try:
                    if self.ai_process.is_alive():
                        self.log.info('Force killing remaining AI process...')
                        self.ai_process.kill()
                except (OSError, AttributeError, RuntimeError):
                    self.log.debug('Error during final AI process cleanup (ignored)')

    def _cleanup_queues(self) -> None:
        """Clean up AI queues."""
        if hasattr(self, 'ai_request_queue') and self.ai_request_queue:
            try:
                self.ai_request_queue.close()
                self.log.info('AI request queue closed')
            except (OSError, ValueError):
                self.log.exception('Error closing request queue')

        if hasattr(self, 'ai_response_queue') and self.ai_response_queue:
            try:
                self.ai_response_queue.close()
                self.log.info('AI response queue closed')
            except (OSError, ValueError):
                self.log.exception('Error closing response queue')

    def _cleanup_voice_recognition(self) -> None:
        """Clean up voice recognition resources.

        **STATUS: Part of disabled voice recognition feature**

        This method is called during scene teardown to properly release microphone
        resources and stop any background threads used by voice recognition.

        **Important:** Always call this even if voice recognition was never enabled,
        as it safely handles the case where voice_manager is None.

        This method:
        - Stops the voice recognition listening thread (if active)
        - Releases microphone resources
        - Clears the voice_manager reference
        - Logs success or error status

        See _setup_voice_recognition() documentation for more information about
        the voice recognition feature status.
        """
        if hasattr(self, 'voice_manager') and self.voice_manager:
            try:
                self.log.info('Stopping voice recognition...')
                self.voice_manager.stop_listening()
                self.voice_manager = None
                self.log.info('Voice recognition stopped successfully')
            except (OSError, AttributeError, RuntimeError):
                self.log.exception('Error stopping voice recognition')

    @override
    def cleanup(self) -> None:
        """Clean up resources."""
        self.log.info('Starting AI cleanup...')

        self._shutdown_ai_worker()
        self._cleanup_ai_process()
        self._cleanup_queues()

        # Clean up voice recognition
        self._cleanup_voice_recognition()

        super().cleanup()

    @override
    def on_key_up_event(self, event: events.HashableEvent) -> None:
        """Handle key release events."""
        # Get modifier keys
        mod = event.mod if hasattr(event, 'mod') else 0

        # Check if this is a Ctrl+Shift+Arrow key release
        if (
            (mod & pygame.KMOD_CTRL)
            and (mod & pygame.KMOD_SHIFT)
            and hasattr(self, 'canvas')
            and self.canvas
            and event.key in {pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN}
        ):
            self.log.debug('Ctrl+Shift+Arrow key released - committing panned buffer')
            self._commit_panned_buffer()
            return

        # Call parent class handler
        super().on_key_up_event(event)

    def _build_surface_from_canvas_pixels(self) -> pygame.Surface:
        """Build a pygame Surface from the current canvas pixel data.

        Returns:
            A new SRCALPHA surface with the canvas pixels rendered onto it.

        """
        surface = pygame.Surface(
            (self.canvas.pixels_across, self.canvas.pixels_tall), pygame.SRCALPHA
        )
        for y in range(self.canvas.pixels_tall):
            for x in range(self.canvas.pixels_across):
                pixel_num = y * self.canvas.pixels_across + x
                if pixel_num < len(self.canvas.pixels):
                    color = self.canvas.pixels[pixel_num]
                    surface.set_at((x, y), color)
        return surface

    def _commit_panned_frame_pixels(self, current_animation: str, current_frame: int) -> None:
        """Commit panned pixel data to the animation frame and its surface.

        Args:
            current_animation: Name of the current animation.
            current_frame: Index of the current frame.

        """
        frame = self.canvas.animated_sprite._animations[current_animation][current_frame]  # type: ignore[reportPrivateUsage]
        if not hasattr(frame, 'pixels'):
            return

        # The current self.canvas.pixels already has the panned view
        frame.pixels = list(self.canvas.pixels)

        # Also update the frame.image surface for film strip thumbnails with alpha support
        frame.image = self._build_surface_from_canvas_pixels()
        self.log.debug(
            f'Committed panned pixels and image to frame {current_animation}[{current_frame}]'
        )

    def _commit_panned_film_strip_frame(self, current_animation: str, current_frame: int) -> None:
        """Commit panned pixel data to the film strip's animation frame.

        Args:
            current_animation: Name of the current animation.
            current_frame: Index of the current frame.

        """
        if not (
            hasattr(self, 'film_strips')
            and self.film_strips
            and current_animation in self.film_strips
        ):
            return

        film_strip = self.film_strips[current_animation]
        if not (
            hasattr(film_strip, 'animated_sprite')
            and film_strip.animated_sprite
            and current_animation in film_strip.animated_sprite._animations  # type: ignore[reportPrivateUsage]
            and current_frame < len(film_strip.animated_sprite._animations[current_animation])  # type: ignore[reportPrivateUsage]
        ):
            return

        # Update the film strip's animated sprite frame data
        film_strip_frame = film_strip.animated_sprite._animations[current_animation][current_frame]  # type: ignore[reportPrivateUsage]
        if not hasattr(film_strip_frame, 'pixels'):
            return

        film_strip_frame.pixels = list(self.canvas.pixels)

        # Also update the film strip frame's image surface with alpha support
        film_strip_frame.image = self._build_surface_from_canvas_pixels()
        self.log.debug(
            'Updated film strip animated sprite frame'
            f' {current_animation}[{current_frame}] with pixels and image'
        )

    def _commit_panned_buffer(self) -> None:
        """Commit the panned buffer back to the real frame data."""
        if not hasattr(self, 'canvas') or not self.canvas:
            return

        # Get current frame key
        frame_key = self.canvas._get_current_frame_key()  # type: ignore[reportPrivateUsage]

        # Check if this frame has active panning
        if frame_key not in self.canvas._frame_panning:  # type: ignore[reportPrivateUsage]
            self.log.debug('No panning state for current frame')
            return

        frame_state = self.canvas._frame_panning[frame_key]  # type: ignore[reportPrivateUsage]
        if not frame_state['active']:
            self.log.debug('No active panning to commit')
            return

        # Commit the current panned pixels back to the frame
        if not (hasattr(self.canvas, 'animated_sprite') and self.canvas.animated_sprite):
            self.log.debug('Panned buffer committed, panning state preserved for continued panning')
            return

        current_animation = self.canvas.current_animation
        current_frame = self.canvas.current_frame

        if not (
            current_animation in self.canvas.animated_sprite._animations  # type: ignore[reportPrivateUsage]
            and current_frame < len(self.canvas.animated_sprite._animations[current_animation])  # type: ignore[reportPrivateUsage]
        ):
            self.log.debug('Panned buffer committed, panning state preserved for continued panning')
            return

        self._commit_panned_frame_pixels(current_animation, current_frame)
        self._commit_panned_film_strip_frame(current_animation, current_frame)

        # Update the film strip to reflect the pixel data changes
        self._update_film_strips_for_animated_sprite_update()
        self.log.debug(f'Updated film strip for frame {current_animation}[{current_frame}]')

        # Keep the panning state active so user can continue panning
        # Don't clear _original_frame_pixels, pan_offset_x, pan_offset_y, or _panning_active
        # The viewport will continue to show the panned view

        self.log.debug('Panned buffer committed, panning state preserved for continued panning')

    def _handle_slider_text_input(self, event: events.HashableEvent) -> bool | None:
        """Handle text input for active slider text boxes.

        Args:
            event: The key down event.

        Returns:
            True if escape was pressed (consume event), None if handled but not escape,
            or False if no slider text box was active.

        """
        sliders = ['red_slider', 'green_slider', 'blue_slider', 'alpha_slider']
        for slider_name in sliders:
            slider = getattr(self, slider_name, None)
            if slider is not None and hasattr(slider, 'text_sprite') and slider.text_sprite.active:
                slider.text_sprite.on_key_down_event(event)
                # If escape was pressed, consume the event to prevent game quit
                if event.key == pygame.K_ESCAPE:
                    return True
                return None
        return False

    def _handle_film_strip_text_input(self, event: events.HashableEvent) -> bool | None:
        """Handle text input for film strips in text editing mode.

        Args:
            event: The key down event.

        Returns:
            True if escape was pressed (consume event), None if handled but not escape,
            or False if no film strip was in editing mode.

        """
        if not hasattr(self, 'film_strips'):
            return False

        for film_strip in self.film_strips.values():
            if (
                hasattr(film_strip, 'editing_animation')
                and film_strip.editing_animation
                and film_strip.handle_keyboard_input(event)
            ):
                # If escape was pressed, consume the event to prevent game quit
                if event.key == pygame.K_ESCAPE:
                    return True
                return None
        return False

    def _handle_ctrl_key_shortcuts(self, event: events.HashableEvent, mod: int) -> bool:
        """Handle Ctrl-based keyboard shortcuts (undo, redo, copy, paste, panning).

        Args:
            event: The key down event.
            mod: The modifier key bitmask.

        Returns:
            True if the event was handled, False otherwise.

        """
        if not (mod & pygame.KMOD_CTRL):
            return False

        if event.key == pygame.K_z:
            if mod & pygame.KMOD_SHIFT:
                self.log.debug('Ctrl+Shift+Z pressed - redo')
                self._handle_redo()
            else:
                self.log.debug('Ctrl+Z pressed - undo')
                self._handle_undo()
            return True

        if event.key == pygame.K_y:
            self.log.debug('Ctrl+Y pressed - redo')
            self._handle_redo()
            return True

        if event.key == pygame.K_c:
            self.log.debug('Ctrl+C pressed - copying frame')
            self._handle_copy_frame()
            return True

        if event.key == pygame.K_v:
            self.log.debug('Ctrl+V pressed - pasting frame')
            self._handle_paste_frame()
            return True

        # Handle panning with Ctrl+Shift+Arrow keys
        if (mod & pygame.KMOD_SHIFT) and hasattr(self, 'canvas') and self.canvas:
            panning_map = {
                pygame.K_LEFT: (-1, 0, 'LEFT'),
                pygame.K_RIGHT: (1, 0, 'RIGHT'),
                pygame.K_UP: (0, -1, 'UP'),
                pygame.K_DOWN: (0, 1, 'DOWN'),
            }
            if event.key in panning_map:
                delta_x, delta_y, direction = panning_map[event.key]
                self.log.debug(
                    f'Ctrl+Shift+{direction} arrow pressed - panning {direction.lower()}'
                )
                self._handle_canvas_panning(delta_x, delta_y)
                return True

        return False

    def _is_any_controller_in_slider_mode(self) -> bool:
        """Check if any controller is currently in slider mode.

        Returns:
            True if at least one controller is in a slider mode.

        """
        if not hasattr(self, 'mode_switcher'):
            return False

        for controller_id in self.mode_switcher.controller_modes:
            controller_mode = self.mode_switcher.get_controller_mode(controller_id)
            if controller_mode and controller_mode.value in {
                'r_slider',
                'g_slider',
                'b_slider',
            }:
                return True
        return False

    def _handle_arrow_key_navigation(self, event: events.HashableEvent) -> bool:
        """Handle UP/DOWN arrow keys for animation navigation.

        Args:
            event: The key down event.

        Returns:
            True if the event was handled, False otherwise.

        """
        if event.key == pygame.K_UP:
            self.log.debug('UP arrow pressed - navigating to previous animation')
            if hasattr(self, 'canvas') and self.canvas:
                self.canvas.previous_animation()
                self._scroll_to_current_animation()
            return True

        if event.key == pygame.K_DOWN:
            self.log.debug('DOWN arrow pressed - navigating to next animation')
            if hasattr(self, 'canvas') and self.canvas:
                self.canvas.next_animation()
                self._scroll_to_current_animation()
            return True

        return False

    def _route_to_canvas_or_parent(self, event: events.HashableEvent) -> None:
        """Route keyboard event to canvas or fall back to parent handler.

        Args:
            event: The key down event.

        """
        # Check if any film strip is in text editing mode before routing to canvas
        if hasattr(self, 'film_strips'):
            for film_strip in self.film_strips.values():
                if hasattr(film_strip, 'editing_animation') and film_strip.editing_animation:
                    return

        if hasattr(self, 'canvas') and hasattr(self.canvas, 'handle_keyboard_event'):
            self.log.debug('Routing keyboard event to canvas')
            self.canvas.handle_keyboard_event(event.key)
        else:
            # Fall back to parent class handling
            self.log.debug('No canvas found, using parent class handling')
            super().on_key_down_event(event)

    @override
    def on_key_down_event(self, event: events.HashableEvent) -> None:
        """Handle keyboard events for frame navigation and text input."""
        self.log.debug(f'Key down event received: key={event.key}')

        # Check if debug text box is active and handle text input
        if hasattr(self, 'debug_text') and self.debug_text.active:
            self.debug_text.on_key_down_event(event)
            return None

        # Check if any slider text box is active and handle text input
        slider_result = self._handle_slider_text_input(event)
        if slider_result is not False:
            return slider_result  # type: ignore[return-value]

        # Check if any film strip is in text editing mode and handle text input
        film_strip_result = self._handle_film_strip_text_input(event)
        if film_strip_result is not False:
            return film_strip_result  # type: ignore[return-value]

        # Handle onion skinning keyboard shortcuts
        if event.key == pygame.K_o:
            self.log.debug('O key pressed - toggling global onion skinning')
            from .onion_skinning import get_onion_skinning_manager

            onion_manager = get_onion_skinning_manager()
            new_state = onion_manager.toggle_global_onion_skinning()
            self.log.debug(f'Onion skinning {"enabled" if new_state else "disabled"}')
            # Force canvas redraw to show/hide onion skinning
            if hasattr(self, 'canvas') and self.canvas:
                self.canvas.force_redraw()
            return None

        # Handle undo/redo and Ctrl-based keyboard shortcuts
        # Get modifier keys from HashableEvent (which wraps pygame events)
        mod = getattr(event, 'mod', 0)
        if self._handle_ctrl_key_shortcuts(event, mod):
            return None

        # Handle slider mode navigation with arrow keys
        if self._is_any_controller_in_slider_mode():
            if event.key == pygame.K_UP:
                self.log.debug('UP arrow pressed - navigating to previous slider mode')
                self._handle_slider_mode_navigation('up')
                return None
            if event.key == pygame.K_DOWN:
                self.log.debug('DOWN arrow pressed - navigating to next slider mode')
                self._handle_slider_mode_navigation('down')
            return None

        # Handle animation navigation and film strip scrolling (UP/DOWN arrows)
        if self._handle_arrow_key_navigation(event):
            return None

        # Route to canvas or parent (only if not in slider mode)
        if not self._is_any_controller_in_slider_mode():
            self._route_to_canvas_or_parent(event)

        return None

    def _handle_undo(self) -> None:
        """Handle undo operation."""
        if not hasattr(self, 'undo_redo_manager'):
            self.log.warning('Undo/redo manager not initialized')
            return

        # Get current frame information
        current_animation = None
        current_frame = None
        if hasattr(self, 'canvas') and self.canvas:
            current_animation = getattr(self.canvas, 'current_animation', None)
            current_frame = getattr(self.canvas, 'current_frame', None)

        # Try frame-specific undo first if we have a current frame
        if current_animation is not None and current_frame is not None:
            if self.undo_redo_manager.can_undo_frame(current_animation, current_frame):
                success = self.undo_redo_manager.undo_frame(current_animation, current_frame)
                if success:
                    self.log.info(
                        f'Frame-specific undo successful for {current_animation}[{current_frame}]'
                    )
                    # Force canvas redraw to show the undone changes
                    if hasattr(self, 'canvas') and self.canvas:
                        self.canvas.force_redraw()
                    return
                self.log.warning(
                    f'Frame-specific undo failed for {current_animation}[{current_frame}]'
                )
            else:
                self.log.warning('No frame-specific undo operations available')

        # Fall back to global undo for film strip operations
        if self.undo_redo_manager.can_undo():
            success = self.undo_redo_manager.undo()
            if success:
                self.log.info('Global undo successful')

                # CRITICAL: Ensure canvas state is valid after film strip operations
                self._synchronize_canvas_state_after_undo()

                # Force canvas redraw to show the undone changes
                if hasattr(self, 'canvas') and self.canvas:
                    self.canvas.force_redraw()
            else:
                self.log.warning('Global undo failed')
        else:
            self.log.debug('No operations available to undo')

    def _synchronize_canvas_state_after_undo(self) -> None:
        """Synchronize canvas state after undo operations to prevent invalid states.

        This method ensures that:
        1. The canvas is pointing to a valid animation
        2. The canvas is pointing to a valid frame index
        3. The canvas state is consistent with the current animation structure
        """
        if not hasattr(self, 'canvas') or not self.canvas:
            self.log.warning('No canvas available for state synchronization')
            return

        if not hasattr(self.canvas, 'animated_sprite') or not self.canvas.animated_sprite:
            self.log.warning('No animated sprite available for state synchronization')
            return

        animations = self.canvas.animated_sprite._animations  # type: ignore[reportPrivateUsage]
        current_animation = getattr(self.canvas, 'current_animation', None)
        current_frame = getattr(self.canvas, 'current_frame', None)

        self.log.debug(
            f'Canvas state before sync: animation={current_animation}, frame={current_frame}'
        )
        self.log.debug(f'Available animations: {list(animations.keys())}')

        # Check if current animation still exists
        if current_animation not in animations:
            self.log.warning(
                f"Current animation '{current_animation}' no longer exists, switching to first"
                f' available'
            )
            if animations:
                # Switch to the first available animation
                first_animation = next(iter(animations.keys()))
                self.canvas.show_frame(first_animation, 0)
                self.log.info(f"Switched to animation '{first_animation}', frame 0")
                return
            self.log.error('No animations available - this should not happen')
            return

        # Check if current frame index is valid
        frames = animations[current_animation]
        if current_frame is None or current_frame < 0 or current_frame >= len(frames):
            self.log.warning(
                f"Current frame {current_frame} is invalid for animation '{current_animation}' with"
                f' {len(frames)} frames'
            )
            # Switch to the last valid frame
            valid_frame = max(0, len(frames) - 1)
            self.canvas.show_frame(current_animation, valid_frame)
            self.log.info(f"Switched to frame {valid_frame} of animation '{current_animation}'")
            return

        # If we get here, the canvas state is valid
        self.log.debug(
            f"Canvas state is valid: animation='{current_animation}', frame={current_frame}"
        )

        # Force a complete canvas refresh to ensure everything is in sync
        self.canvas.force_redraw()

        # Update film strips to reflect the current state
        if hasattr(self, '_update_film_strips_for_frame'):
            self._update_film_strips_for_frame(current_animation, current_frame)

    def _handle_redo(self) -> None:
        """Handle redo operation."""
        if not hasattr(self, 'undo_redo_manager'):
            self.log.warning('Undo/redo manager not initialized')
            return

        # Get current frame information
        current_animation = None
        current_frame = None
        if hasattr(self, 'canvas') and self.canvas:
            current_animation = getattr(self.canvas, 'current_animation', None)
            current_frame = getattr(self.canvas, 'current_frame', None)

        # Try frame-specific redo first if we have a current frame
        if current_animation is not None and current_frame is not None:
            if self.undo_redo_manager.can_redo_frame(current_animation, current_frame):
                success = self.undo_redo_manager.redo_frame(current_animation, current_frame)
                if success:
                    self.log.info(
                        f'Frame-specific redo successful for {current_animation}[{current_frame}]'
                    )
                    # Force canvas redraw to show the redone changes
                    if hasattr(self, 'canvas') and self.canvas:
                        self.canvas.force_redraw()
                    return
                self.log.warning(
                    f'Frame-specific redo failed for {current_animation}[{current_frame}]'
                )
            else:
                self.log.warning('No frame-specific redo operations available')

        # Fall back to global redo for film strip operations
        if self.undo_redo_manager.can_redo():
            success = self.undo_redo_manager.redo()
            if success:
                self.log.info('Global redo successful')

                # CRITICAL: Ensure canvas state is valid after film strip operations
                self._synchronize_canvas_state_after_undo()

                # Force canvas redraw to show the redone changes
                if hasattr(self, 'canvas') and self.canvas:
                    self.canvas.force_redraw()
            else:
                self.log.warning('Global redo failed')
        else:
            self.log.debug('No operations available to redo')

    def _handle_canvas_panning(self, delta_x: int, delta_y: int) -> None:
        """Handle canvas panning with the given delta values.

        Args:
            delta_x: Horizontal panning delta (-1, 0, or 1)
            delta_y: Vertical panning delta (-1, 0, or 1)

        """
        if not hasattr(self, 'canvas') or not self.canvas:
            self.log.warning('No canvas available for panning')
            return

        # Delegate to canvas panning method
        if hasattr(self.canvas, 'pan_canvas'):
            self.canvas.pan_canvas(delta_x, delta_y)
        else:
            self.log.warning('Canvas does not support panning')

    def _handle_copy_frame(self) -> None:
        """Handle copying the current frame to clipboard."""
        if not hasattr(self, 'canvas') or not self.canvas:
            self.log.warning('No canvas available for frame copying')
            return

        if not hasattr(self, 'selected_animation') or not hasattr(self, 'selected_frame'):
            self.log.warning('No frame selected for copying')
            return

        animation = self.selected_animation
        frame = self.selected_frame

        if animation is None or frame is None:
            self.log.warning('No animation or frame selected for copying')
            return

        if not hasattr(self.canvas, 'animated_sprite') or not self.canvas.animated_sprite:
            self.log.warning('No animated sprite available for frame copying')
            return

        # Get the frame data
        if animation not in self.canvas.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
            self.log.warning(f"Animation '{animation}' not found for copying")
            return

        frames = self.canvas.animated_sprite._animations[animation]  # type: ignore[reportPrivateUsage]
        if frame >= len(frames):
            self.log.warning(f"Frame {frame} not found in animation '{animation}'")
            return

        frame_obj = frames[frame]

        # Create a deep copy of the frame data for the clipboard

        # Get pixel data
        pixels = frame_obj.get_pixel_data()

        # Get frame dimensions
        width, height = frame_obj.get_size()

        # Get frame duration
        duration = frame_obj.duration

        # Store frame data in clipboard
        self._frame_clipboard = {
            'pixels': pixels.copy(),
            'width': width,
            'height': height,
            'duration': duration,
            'animation': animation,
            'frame': frame,
        }

        self.log.debug(f"Copied frame {frame} from animation '{animation}' to clipboard")

    def _handle_paste_frame(self) -> None:
        """Handle pasting a frame from clipboard to the current frame."""
        if not hasattr(self, 'canvas') or not self.canvas:
            self.log.warning('No canvas available for frame pasting')
            return

        if not hasattr(self, 'selected_animation') or not hasattr(self, 'selected_frame'):
            self.log.warning('No frame selected for pasting')
            return

        if not self._frame_clipboard:
            self.log.warning('No frame data in clipboard to paste')
            return

        animation = self.selected_animation
        frame = self.selected_frame

        if animation is None or frame is None:
            self.log.warning('No animation or frame selected for pasting')
            return

        if not hasattr(self.canvas, 'animated_sprite') or not self.canvas.animated_sprite:
            self.log.warning('No animated sprite available for frame pasting')
            return

        # Get the target frame
        if animation not in self.canvas.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
            self.log.warning(f"Animation '{animation}' not found for pasting")
            return

        frames = self.canvas.animated_sprite._animations[animation]  # type: ignore[reportPrivateUsage]
        if frame >= len(frames):
            self.log.warning(f"Frame {frame} not found in animation '{animation}'")
            return

        target_frame = frames[frame]

        # Check if dimensions match
        clipboard_width = self._frame_clipboard['width']
        clipboard_height = self._frame_clipboard['height']
        target_width, target_height = target_frame.get_size()

        if clipboard_width != target_width or clipboard_height != target_height:
            self.log.warning(
                'Cannot paste frame: dimension mismatch (clipboard:'
                f' {clipboard_width}x{clipboard_height}, target: {target_width}x{target_height})'
            )
            return

        # Create undo/redo operation for the paste
        from glitchygames.tools.undo_redo_manager import OperationType

        # Store original frame data for undo
        original_pixels = target_frame.get_pixel_data()
        original_duration = target_frame.duration

        # Apply the paste operation
        self._apply_frame_paste_for_undo_redo(
            animation, frame, self._frame_clipboard['pixels'], self._frame_clipboard['duration']
        )

        # Add to undo stack
        self.undo_redo_manager.add_operation(
            operation_type=OperationType.FRAME_PASTE,
            description=(
                f'Paste frame from'
                f' {self._frame_clipboard["animation"]}[{self._frame_clipboard["frame"]}] to'
                f' {animation}[{frame}]'
            ),
            undo_data={
                'animation': animation,
                'frame': frame,
                'pixels': original_pixels,
                'duration': original_duration,
            },
            redo_data={
                'animation': animation,
                'frame': frame,
                'pixels': self._frame_clipboard['pixels'],
                'duration': self._frame_clipboard['duration'],
            },
        )

        # Update canvas display
        if hasattr(self.canvas, 'force_redraw'):
            self.canvas.force_redraw()

        self.log.debug(f'Pasted frame from clipboard to {animation}[{frame}]')

    def _apply_frame_paste_for_undo_redo(
        self, animation: str, frame: int, pixels: list[tuple[int, ...]], duration: float
    ) -> bool:
        """Apply frame paste for undo/redo operations.

        Args:
            animation: Name of the animation
            frame: Frame index
            pixels: Pixel data to apply
            duration: Frame duration

        Returns:
            True if successful, False otherwise

        """
        try:
            if (
                not hasattr(self, 'canvas')
                or not self.canvas
                or not hasattr(self.canvas, 'animated_sprite')
            ):
                self.log.warning('Canvas or animated sprite not available for frame paste')
                return False

            # Get the target frame
            if animation not in self.canvas.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
                self.log.warning(f"Animation '{animation}' not found for frame paste")
                return False

            frames = self.canvas.animated_sprite._animations[animation]  # type: ignore[reportPrivateUsage]
            if frame >= len(frames):
                self.log.warning(f"Frame {frame} not found in animation '{animation}'")
                return False

            target_frame = frames[frame]

            # Apply the pixel data and duration
            target_frame.set_pixel_data(pixels)
            target_frame.duration = duration

            # Update the canvas pixels if this is the currently displayed frame
            if (
                hasattr(self, 'selected_animation')
                and hasattr(self, 'selected_frame')
                and self.selected_animation == animation
                and self.selected_frame == frame
                and hasattr(self.canvas, 'pixels')
            ):
                self.canvas.pixels = pixels.copy()
                if hasattr(self.canvas, 'dirty_pixels'):
                    self.canvas.dirty_pixels = [True] * len(pixels)
                if hasattr(self.canvas, 'dirty'):
                    self.canvas.dirty = 1

            self.log.debug(f'Applied frame paste to {animation}[{frame}]')
            return True

        except (AttributeError, IndexError, KeyError, TypeError, ValueError):
            self.log.exception('Error applying frame paste')
            return False

    def _apply_pixel_change_for_undo_redo(
        self, x: int, y: int, color: tuple[int, int, int]
    ) -> None:
        """Apply a pixel change for undo/redo operations.

        Args:
            x: X coordinate of the pixel
            y: Y coordinate of the pixel
            color: Color to set the pixel to

        """
        if hasattr(self, 'canvas') and self.canvas and hasattr(self.canvas, 'canvas_interface'):
            # Set flag to prevent undo tracking during undo/redo operations
            self._applying_undo_redo = True
            try:
                # Use the canvas interface to set the pixel
                self.canvas.canvas_interface.set_pixel_at(x, y, color)
                self.log.debug(f'Applied undo/redo pixel change at ({x}, {y}) to color {color}')
            finally:
                # Always reset the flag
                self._applying_undo_redo = False
        else:
            self.log.warning('Canvas or canvas interface not available for undo/redo')

    def _apply_frame_selection_for_undo_redo(self, animation: str, frame: int) -> bool:
        """Apply a frame selection for undo/redo operations.

        Args:
            animation: Name of the animation to select
            frame: Frame index to select

        Returns:
            True if the frame selection was applied successfully, False otherwise

        """
        try:
            if hasattr(self, 'canvas') and self.canvas:
                # Set flag to prevent undo tracking during undo/redo operations
                self._applying_undo_redo = True
                try:
                    # Switch to the specified frame
                    self.canvas.show_frame(animation, frame)
                    self.log.debug(f'Applied undo/redo frame selection: {animation}[{frame}]')
                    return True
                finally:
                    # Always reset the flag
                    self._applying_undo_redo = False
            else:
                self.log.warning('Canvas not available for frame selection undo/redo')
                return False
        except (AttributeError, IndexError, KeyError, TypeError, ValueError):
            self.log.exception('Error applying frame selection undo/redo')
            return False

    def _refresh_all_film_strip_widgets(self, animation_name: str | None = None) -> None:
        """Refresh all film strip widgets to reflect current animation data.

        Args:
            animation_name: If provided, also update frame selection for this animation.

        """
        if hasattr(self, 'film_strip_widget') and self.film_strip_widget:
            self.film_strip_widget._initialize_preview_animations()  # type: ignore[reportPrivateUsage]
            self.film_strip_widget.update_layout()
            self.film_strip_widget._create_film_tabs()  # type: ignore[reportPrivateUsage]
            self.film_strip_widget.mark_dirty()

        if not (hasattr(self, 'film_strip_sprites') and self.film_strip_sprites):
            return

        for film_strip_sprite in self.film_strip_sprites.values():
            if not (
                hasattr(film_strip_sprite, 'film_strip_widget')
                and film_strip_sprite.film_strip_widget
            ):
                continue

            # Completely refresh the film strip widget to ensure it shows current data
            film_strip_sprite.film_strip_widget._initialize_preview_animations()  # type: ignore[reportPrivateUsage]
            film_strip_sprite.film_strip_widget._calculate_layout()  # type: ignore[reportPrivateUsage]
            film_strip_sprite.film_strip_widget.update_layout()
            film_strip_sprite.film_strip_widget._create_film_tabs()  # type: ignore[reportPrivateUsage]
            film_strip_sprite.film_strip_widget.mark_dirty()
            film_strip_sprite.dirty = 1

            # Update the film strip to show the current frame selection
            if (
                animation_name
                and hasattr(self.canvas, 'current_animation')
                and hasattr(self.canvas, 'current_frame')
                and self.canvas.current_animation == animation_name
            ):
                film_strip_sprite.film_strip_widget.set_frame_index(self.canvas.current_frame)

    def _add_frame_for_undo_redo(
        self, frame_index: int, animation_name: str, frame_data: dict[str, Any]
    ) -> bool:
        """Add a frame for undo/redo operations.

        Args:
            frame_index: Index where the frame should be added
            animation_name: Name of the animation
            frame_data: Data about the frame to add

        Returns:
            True if the frame was added successfully, False otherwise

        """
        import pygame

        from glitchygames.sprites.animated import SpriteFrame

        try:
            if (
                not hasattr(self, 'canvas')
                or not self.canvas
                or not hasattr(self.canvas, 'animated_sprite')
            ):
                self.log.warning('Canvas or animated sprite not available for frame addition')
                return False

            # Create a new frame from the frame data
            # Create surface from frame data
            surface = pygame.Surface((frame_data['width'], frame_data['height']))
            if frame_data.get('pixels'):
                # Convert pixel data to surface
                pixel_array = pygame.PixelArray(surface)
                for i, pixel in enumerate(frame_data['pixels']):
                    if i < len(pixel_array.flat):  # type: ignore[union-attr]
                        pixel_array.flat[i] = pixel  # type: ignore[union-attr]
                del pixel_array  # Release the pixel array

            # Create the frame object
            new_frame = SpriteFrame(surface=surface, duration=frame_data.get('duration', 1.0))

            # Add the frame to the animation
            self.canvas.animated_sprite.add_frame(animation_name, new_frame, frame_index)

            # Update the canvas's selected frame index if necessary
            if self.canvas.animated_sprite.frame_manager.current_animation == animation_name:
                # If we're adding a frame at or before the current position, increment the frame
                # index
                if self.canvas.animated_sprite.frame_manager.current_frame >= frame_index:
                    self.canvas.animated_sprite.frame_manager.current_frame += 1

                # Ensure the frame index is within bounds
                max_frame = len(self.canvas.animated_sprite._animations[animation_name]) - 1  # type: ignore[reportPrivateUsage]
                if self.canvas.animated_sprite.frame_manager.current_frame > max_frame:
                    self.canvas.animated_sprite.frame_manager.current_frame = max(0, max_frame)

                # Update the canvas to show the correct frame
                self.canvas.show_frame(
                    animation_name, self.canvas.animated_sprite.frame_manager.current_frame
                )

            self._refresh_all_film_strip_widgets(animation_name)

            # Notify the scene about the frame insertion for proper UI updates
            self._on_frame_inserted(animation_name, frame_index)

            self.log.debug(
                f"Added frame {frame_index} to animation '{animation_name}' for undo/redo"
            )
            return True

        except (AttributeError, IndexError, KeyError, TypeError, ValueError, pygame.error):
            self.log.exception('Error adding frame for undo/redo')
            return False

    def _stop_animation_and_adjust_frame_before_deletion(
        self, animation_name: str, frame_index: int
    ) -> None:
        """Stop animation playback and adjust the frame index before frame deletion.

        Args:
            animation_name: Name of the animation being modified.
            frame_index: Index of the frame about to be deleted.

        """
        if not (
            hasattr(self.canvas.animated_sprite, 'frame_manager')
            and self.canvas.animated_sprite.frame_manager.current_animation == animation_name
        ):
            return

        self.canvas.animated_sprite._is_playing = False  # type: ignore[reportPrivateUsage]

        # Adjust current frame index if necessary
        if self.canvas.animated_sprite.frame_manager.current_frame >= frame_index:
            if self.canvas.animated_sprite.frame_manager.current_frame > 0:
                self.canvas.animated_sprite.frame_manager.current_frame -= 1
            else:
                self.canvas.animated_sprite.frame_manager.current_frame = 0

    def _adjust_canvas_frame_after_deletion(self, animation_name: str, frame_index: int) -> None:
        """Adjust canvas frame selection after a frame has been deleted.

        Args:
            animation_name: Name of the animation that was modified.
            frame_index: Index of the frame that was deleted.

        """
        if self.canvas.animated_sprite.frame_manager.current_animation != animation_name:
            return

        # Adjust the canvas's current frame index to select the previous frame
        if self.canvas.animated_sprite.frame_manager.current_frame >= frame_index:
            if self.canvas.animated_sprite.frame_manager.current_frame > 0:
                # Select the previous frame
                self.canvas.animated_sprite.frame_manager.current_frame -= 1
                self.log.debug(
                    'Selected previous frame'
                    f' {self.canvas.animated_sprite.frame_manager.current_frame}'
                    ' after frame deletion'
                )
            else:
                # If we were at frame 0 and removed it, stay at frame 0 (which is
                # now the next frame)
                self.canvas.animated_sprite.frame_manager.current_frame = 0
                self.log.debug('Stayed at frame 0 after deleting frame 0')

        # Ensure the frame index is within bounds
        max_frame = len(self.canvas.animated_sprite._animations[animation_name]) - 1  # type: ignore[reportPrivateUsage]
        if self.canvas.animated_sprite.frame_manager.current_frame > max_frame:
            self.canvas.animated_sprite.frame_manager.current_frame = max(0, max_frame)

        # Update the canvas to show the correct frame
        self.canvas.show_frame(
            animation_name, self.canvas.animated_sprite.frame_manager.current_frame
        )

    def _delete_frame_for_undo_redo(self, frame_index: int, animation_name: str) -> bool:
        """Delete a frame for undo/redo operations.

        Args:
            frame_index: Index of the frame to delete
            animation_name: Name of the animation

        Returns:
            True if the frame was deleted successfully, False otherwise

        """
        try:
            if (
                not hasattr(self, 'canvas')
                or not self.canvas
                or not hasattr(self.canvas, 'animated_sprite')
            ):
                self.log.warning('Canvas or animated sprite not available for frame deletion')
                return False

            if animation_name not in self.canvas.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
                self.log.warning(f"Animation '{animation_name}' not found")
                return False

            frames = self.canvas.animated_sprite._animations[animation_name]  # type: ignore[reportPrivateUsage]
            if not (0 <= frame_index < len(frames)):
                self.log.warning(
                    f"Frame index {frame_index} out of range for animation '{animation_name}'"
                )
                return False

            # Stop animation to prevent race conditions during frame deletion
            self._stop_animation_and_adjust_frame_before_deletion(animation_name, frame_index)

            frames.pop(frame_index)

            # Update the canvas's selected frame index if necessary and select the previous frame
            self._adjust_canvas_frame_after_deletion(animation_name, frame_index)

            self._refresh_all_film_strip_widgets(animation_name)

            # Notify the scene about the frame removal for proper UI updates
            self._on_frame_removed(animation_name, frame_index)

            self.log.debug(
                f"Deleted frame {frame_index} from animation '{animation_name}' for undo/redo"
            )
            return True

        except (AttributeError, IndexError, KeyError, TypeError, ValueError):
            self.log.exception('Error deleting frame for undo/redo')
            return False

    def _reorder_frame_for_undo_redo(
        self, old_index: int, new_index: int, animation_name: str
    ) -> bool:
        """Reorder frames for undo/redo operations.

        Args:
            old_index: Original index of the frame
            new_index: New index of the frame
            animation_name: Name of the animation

        Returns:
            True if the frame was reordered successfully, False otherwise

        """
        try:
            if (
                not hasattr(self, 'canvas')
                or not self.canvas
                or not hasattr(self.canvas, 'animated_sprite')
            ):
                self.log.warning('Canvas or animated sprite not available for frame reordering')
                return False

            # Reorder frames in the animation
            if animation_name in self.canvas.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
                frames = self.canvas.animated_sprite._animations[animation_name]  # type: ignore[reportPrivateUsage]
                if 0 <= old_index < len(frames) and 0 <= new_index < len(frames):
                    # Move the frame from old_index to new_index
                    frame = frames.pop(old_index)
                    frames.insert(new_index, frame)

                    # Update the film strip if it exists
                    if hasattr(self, 'film_strip_widget') and self.film_strip_widget:
                        self.film_strip_widget._initialize_preview_animations()  # type: ignore[reportPrivateUsage]
                        self.film_strip_widget.update_layout()
                        self.film_strip_widget._create_film_tabs()  # type: ignore[reportPrivateUsage]
                        self.film_strip_widget.mark_dirty()

                    self.log.debug(
                        f'Reordered frame from {old_index} to {new_index} in animation'
                        f" '{animation_name}' for undo/redo"
                    )
                    return True
                self.log.warning(f"Frame indices out of range for animation '{animation_name}'")
                return False
            self.log.warning(f"Animation '{animation_name}' not found")
            return False

        except (AttributeError, IndexError, KeyError, TypeError):
            self.log.exception('Error reordering frame for undo/redo')
            return False

    def _add_animation_for_undo_redo(
        self, animation_name: str, animation_data: dict[str, Any]
    ) -> bool:
        """Add an animation for undo/redo operations.

        Args:
            animation_name: Name of the animation to add
            animation_data: Data about the animation to add

        Returns:
            True if the animation was added successfully, False otherwise

        """
        import pygame

        from glitchygames.sprites.animated import SpriteFrame

        try:
            if (
                not hasattr(self, 'canvas')
                or not self.canvas
                or not hasattr(self.canvas, 'animated_sprite')
            ):
                self.log.warning('Canvas or animated sprite not available for animation addition')
                return False

            # Create the animation with its frames
            for frame_data in animation_data.get('frames', []):
                # Create surface from frame data
                surface = pygame.Surface((frame_data['width'], frame_data['height']))
                if frame_data.get('pixels'):
                    # Convert pixel data to surface
                    pixel_array = pygame.PixelArray(surface)
                    for i, pixel in enumerate(frame_data['pixels']):
                        if i < len(pixel_array.flat):  # type: ignore[union-attr]
                            pixel_array.flat[i] = pixel  # type: ignore[union-attr]
                    del pixel_array  # Release the pixel array

                # Create the frame object
                new_frame = SpriteFrame(surface=surface, duration=frame_data.get('duration', 1.0))

                # Add the frame to the animation
                self.canvas.animated_sprite._animations[animation_name] = (  # type: ignore[reportPrivateUsage]
                    self.canvas.animated_sprite._animations.get(animation_name, [])  # type: ignore[reportPrivateUsage]
                )
                self.canvas.animated_sprite._animations[animation_name].append(new_frame)  # type: ignore[reportPrivateUsage]

            # Update the film strip if it exists
            if hasattr(self, 'film_strip_widget') and self.film_strip_widget:
                self.film_strip_widget._initialize_preview_animations()  # type: ignore[reportPrivateUsage]
                self.film_strip_widget.update_layout()
                self.film_strip_widget._create_film_tabs()  # type: ignore[reportPrivateUsage]
                self.film_strip_widget.mark_dirty()

            # Force update of all film strip widgets
            if hasattr(self, 'film_strip_sprites') and self.film_strip_sprites:
                for film_strip_sprite in self.film_strip_sprites.values():
                    if (
                        hasattr(film_strip_sprite, 'film_strip_widget')
                        and film_strip_sprite.film_strip_widget
                    ):
                        # Completely refresh the film strip widget to ensure it shows current data
                        film_strip_sprite.film_strip_widget._initialize_preview_animations()  # type: ignore[reportPrivateUsage]
                        film_strip_sprite.film_strip_widget._calculate_layout()  # type: ignore[reportPrivateUsage]
                        film_strip_sprite.film_strip_widget.update_layout()
                        film_strip_sprite.film_strip_widget._create_film_tabs()  # type: ignore[reportPrivateUsage]
                        film_strip_sprite.film_strip_widget.mark_dirty()
                        film_strip_sprite.dirty = 1

            self.log.debug(f"Added animation '{animation_name}' for undo/redo")
            return True

        except (AttributeError, IndexError, KeyError, TypeError, ValueError, pygame.error):
            self.log.exception('Error adding animation for undo/redo')
            return False

    def _delete_animation_for_undo_redo(self, animation_name: str) -> bool:
        """Delete an animation for undo/redo operations.

        Args:
            animation_name: Name of the animation to delete

        Returns:
            True if the animation was deleted successfully, False otherwise

        """
        try:
            if (
                not hasattr(self, 'canvas')
                or not self.canvas
                or not hasattr(self.canvas, 'animated_sprite')
            ):
                self.log.warning('Canvas or animated sprite not available for animation deletion')
                return False

            # Remove the animation
            if animation_name in self.canvas.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
                del self.canvas.animated_sprite._animations[animation_name]  # type: ignore[reportPrivateUsage]

                # Update the film strip if it exists
                if hasattr(self, 'film_strip_widget') and self.film_strip_widget:
                    self.film_strip_widget._initialize_preview_animations()  # type: ignore[reportPrivateUsage]
                    self.film_strip_widget.update_layout()
                    self.film_strip_widget._create_film_tabs()  # type: ignore[reportPrivateUsage]
                    self.film_strip_widget.mark_dirty()

                # Force update of all film strip widgets
                if hasattr(self, 'film_strip_sprites') and self.film_strip_sprites:
                    for film_strip_sprite in self.film_strip_sprites.values():
                        if (
                            hasattr(film_strip_sprite, 'film_strip_widget')
                            and film_strip_sprite.film_strip_widget
                        ):
                            # Completely refresh the film strip widget to ensure it shows current
                            # data
                            film_strip_sprite.film_strip_widget._initialize_preview_animations()  # type: ignore[reportPrivateUsage]
                            film_strip_sprite.film_strip_widget._calculate_layout()  # type: ignore[reportPrivateUsage]
                            film_strip_sprite.film_strip_widget.update_layout()
                            film_strip_sprite.film_strip_widget._create_film_tabs()  # type: ignore[reportPrivateUsage]
                            film_strip_sprite.film_strip_widget.mark_dirty()
                            film_strip_sprite.dirty = 1

                # CRITICAL: Recreate film strips to reflect the deleted animation
                self._on_sprite_loaded(self.canvas.animated_sprite)

                self.log.debug(f"Deleted animation '{animation_name}' for undo/redo")
                return True
            self.log.warning(f"Animation '{animation_name}' not found")
            return False

        except (AttributeError, KeyError, TypeError):
            self.log.exception('Error deleting animation for undo/redo')
            return False

    def _apply_controller_position_for_undo_redo(
        self, controller_id: int, position: tuple[int, int], mode: str | None = None
    ) -> bool:
        """Apply a controller position change for undo/redo operations.

        Args:
            controller_id: ID of the controller
            position: New position (x, y)
            mode: Controller mode (optional)

        Returns:
            True if the position was applied successfully, False otherwise

        """
        try:
            # Set flag to prevent undo tracking during undo/redo operations
            self._applying_undo_redo = True
            try:
                # Update controller position in mode switcher
                if hasattr(self, 'mode_switcher') and self.mode_switcher:
                    self.mode_switcher.save_controller_position(controller_id, position)

                    # Update visual indicator
                    if hasattr(self, '_update_controller_canvas_visual_indicator'):
                        self._update_controller_canvas_visual_indicator(controller_id)

                    self.log.debug(
                        f'Applied undo/redo controller position: {controller_id} -> {position}'
                    )
                    return True
                self.log.warning('Mode switcher not available for controller position undo/redo')
                return False
            finally:
                # Always reset the flag
                self._applying_undo_redo = False
        except (AttributeError, KeyError, TypeError):
            self.log.exception('Error applying controller position undo/redo')
            return False

    def _apply_controller_mode_for_undo_redo(self, controller_id: int, mode: str) -> bool:
        """Apply a controller mode change for undo/redo operations.

        Args:
            controller_id: ID of the controller
            mode: New controller mode

        Returns:
            True if the mode was applied successfully, False otherwise

        """
        try:
            # Set flag to prevent undo tracking during undo/redo operations
            self._applying_undo_redo = True
            try:
                # Update controller mode in mode switcher
                if hasattr(self, 'mode_switcher') and self.mode_switcher:
                    from glitchygames.tools.controller_mode_system import ControllerMode

                    # Convert string to ControllerMode enum
                    try:
                        controller_mode = ControllerMode(mode)
                    except ValueError:
                        self.log.warning(f'Invalid controller mode: {mode}')
                        return False

                    # Switch to the new mode
                    import time

                    current_time = time.time()
                    self.mode_switcher.controller_modes[controller_id].switch_to_mode(
                        controller_mode, current_time
                    )

                    # Update visual indicator
                    if hasattr(self, '_update_controller_visual_indicator_for_mode'):
                        self._update_controller_visual_indicator_for_mode(
                            controller_id, controller_mode
                        )

                    self.log.debug(f'Applied undo/redo controller mode: {controller_id} -> {mode}')
                    return True
                self.log.warning('Mode switcher not available for controller mode undo/redo')
                return False
            finally:
                # Always reset the flag
                self._applying_undo_redo = False
        except (AttributeError, KeyError, TypeError, ValueError):
            self.log.exception('Error applying controller mode undo/redo')
            return False

    def _submit_pixel_changes_if_ready(self) -> None:
        """Submit collected pixel changes if they're ready (single click or drag ended)."""
        # Convert dict to list format for submission (dict is used for efficient O(1) deduplication
        # during drag)
        pixel_changes_list = []
        if hasattr(self, '_current_pixel_changes_dict') and self._current_pixel_changes_dict:
            # Convert dict values to list format
            pixel_changes_list = list(self._current_pixel_changes_dict.values())
            # Clear the dict after conversion
            self._current_pixel_changes_dict.clear()
        elif hasattr(self, '_current_pixel_changes') and self._current_pixel_changes:
            # Fallback to list if dict doesn't exist (backward compatibility)
            pixel_changes_list = self._current_pixel_changes

        if pixel_changes_list and hasattr(self, 'canvas_operation_tracker'):
            pixel_count = len(pixel_changes_list)

            # Get current frame information for frame-specific tracking
            current_animation = None
            current_frame = None
            if hasattr(self, 'canvas') and self.canvas:
                current_animation = getattr(self.canvas, 'current_animation', None)
                current_frame = getattr(self.canvas, 'current_frame', None)

            # Use frame-specific tracking if we have frame information
            if current_animation is not None and current_frame is not None:
                self.canvas_operation_tracker.add_frame_pixel_changes(
                    current_animation,
                    current_frame,
                    pixel_changes_list,  # type: ignore[arg-type]
                )
                self.log.debug(
                    f'Submitted {pixel_count} pixel changes for frame'
                    f' {current_animation}[{current_frame}] undo/redo tracking'
                )
            else:
                # Fall back to global tracking
                self.canvas_operation_tracker.add_pixel_changes(pixel_changes_list)  # type: ignore[arg-type]
                self.log.debug(
                    f'Submitted {pixel_count} pixel changes for global undo/redo tracking'
                )

            # Clear both collections after submission
            if hasattr(self, '_current_pixel_changes'):
                self._current_pixel_changes = []
            if hasattr(self, '_current_pixel_changes_dict'):
                self._current_pixel_changes_dict.clear()

    def _check_single_click_timer(self) -> None:
        """Check if we should submit a single click based on timer."""
        # Check dict first (new optimized path), then fallback to list
        pixel_count = 0
        if hasattr(self, '_current_pixel_changes_dict') and self._current_pixel_changes_dict:
            pixel_count = len(self._current_pixel_changes_dict)
        elif hasattr(self, '_current_pixel_changes') and self._current_pixel_changes:
            pixel_count = len(self._current_pixel_changes)

        if (
            pixel_count == 1  # Only for single pixels
            and hasattr(self, '_pixel_change_timer')
            and self._pixel_change_timer
        ):
            import time

            current_time = time.time()
            # If more than 0.1 seconds have passed since the first pixel change, submit it
            if current_time - self._pixel_change_timer > PIXEL_CHANGE_DEBOUNCE_SECONDS:
                self._submit_pixel_changes_if_ready()
                self._pixel_change_timer = None

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> None:
        """Add command line arguments.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Raises:
            None

        """
        parser.add_argument(
            '-v', '--version', action='store_true', help='print the game version and exit'
        )
        parser.add_argument('-s', '--size', default='32x32')

    @override
    def _handle_scene_key_events(self, event: events.HashableEvent) -> None:
        """Handle scene-level key events."""
        self.log.debug(f'Scene-level key event: {event.key}')

        # Call our custom keyboard handler
        self.on_key_down_event(event)

    @override
    def on_drop_file_event(self, event: events.HashableEvent) -> None:  # type: ignore[override]
        """Handle drop file event.

        Args:
            event: The pygame event containing the dropped file information.

        """
        # Get the file path from the event
        file_path = event.file
        self.log.info(f'File dropped: {file_path}')

        # Get file size
        try:
            file_size = Path(file_path).stat().st_size
            self.log.info(f'File size: {file_size} bytes')
        except OSError:
            self.log.exception('Could not get file size')
            return

        # First, check if any film strip sprites can handle the drop
        if self._try_film_strip_drop(event):
            return

        # If no film strip handled it, check if drop is on the canvas
        self._try_canvas_drop(file_path)

    def _try_film_strip_drop(self, event: events.HashableEvent) -> bool:
        """Try to handle a file drop via film strip sprites.

        Args:
            event: The pygame event containing the dropped file information.

        Returns:
            True if a film strip handled the drop, False otherwise.

        """
        if not hasattr(self, 'film_strip_sprites') or not self.film_strip_sprites:
            return False

        for strip_name, film_strip_sprite in self.film_strip_sprites.items():
            if not hasattr(film_strip_sprite, 'on_drop_file_event'):
                continue
            try:
                if film_strip_sprite.on_drop_file_event(event):
                    self.log.info(f"Film strip '{strip_name}' handled the drop")
                    return True
            except (AttributeError, TypeError, ValueError, OSError, pygame.error):
                self.log.exception('Error in film strip drop handler')
                continue
        return False

    def _try_canvas_drop(self, file_path: str) -> None:
        """Try to handle a file drop on the canvas.

        Args:
            file_path: Path to the dropped file.

        """
        # Get current mouse position since drop events don't include position
        mouse_pos = pygame.mouse.get_pos()
        if not (
            hasattr(self, 'canvas')
            and self.canvas is not None  # pyright: ignore[reportUnnecessaryComparison]
            and self.canvas.rect is not None  # pyright: ignore[reportUnnecessaryComparison]
            and self.canvas.rect.collidepoint(mouse_pos)
        ):
            self.log.info(f'Drop not on canvas or film strip - ignoring drop at {mouse_pos}')
            return

        self.log.info(f'Drop detected on canvas at {mouse_pos}')
        if file_path.lower().endswith('.png'):
            self.log.info('PNG file detected - converting to bitmappy format')
            converted_toml_path = self._convert_png_to_bitmappy(file_path)
            if converted_toml_path:
                # Auto-load the converted TOML file
                self._load_converted_sprite(converted_toml_path)
            else:
                self.log.error('Failed to convert PNG to bitmappy format')
        elif file_path.lower().endswith('.toml'):
            self.log.info('TOML file detected - loading directly')
            # Load the TOML file directly
            self._load_converted_sprite(file_path)
        else:
            self.log.info(f'Unsupported file type dropped on canvas: {file_path}')

    def _convert_png_to_bitmappy(self, file_path: str) -> str | None:
        """Convert a PNG file to bitmappy TOML format.

        Args:
            file_path: Path to the PNG file to convert.

        Returns:
            Path to the converted TOML file, or None if conversion failed.

        """
        try:
            image, width, height = self._load_and_resize_png(file_path)
            pixel_array: Any = pygame.surfarray.array3d(image)  # type: ignore[reportUnknownMemberType]
            self.log.info(f'Pixel array shape: {pixel_array.shape}')

            has_transparency, original_image = self._detect_png_transparency(image, file_path)
            unique_colors, sample_count, transparent_pixels = self._sample_png_colors(
                pixel_array,
                width,
                height,
                has_transparency=has_transparency,
                original_image=original_image,
            )

            if has_transparency:
                self.log.info(
                    f'Found {transparent_pixels} transparent pixels, mapped to magenta'
                    f' (255, 0, 255)'
                )
            self.log.info(
                f'Sampled {sample_count} pixels, found {len(unique_colors)} unique colors'
            )

            unique_colors = self._quantize_colors_if_needed(
                unique_colors, has_transparency=has_transparency
            )
            color_mapping = self._build_color_to_glyph_mapping(
                unique_colors, has_transparency=has_transparency
            )

            pixel_string = self._generate_pixel_string(
                pixel_array,
                width,
                height,
                has_transparency=has_transparency,
                original_image=original_image,
                color_mapping=color_mapping,
            )

            toml_content = self._generate_toml_content(file_path, pixel_string, color_mapping)
            output_path = self._save_and_validate_toml(file_path, toml_content)

            self.log.info(f'Successfully converted PNG to bitmappy format: {output_path}')
            return str(output_path)

        except (OSError, ValueError, TypeError, AttributeError, pygame.error):
            self.log.exception('Error converting PNG to bitmappy format')
            return None

    def _load_and_resize_png(self, file_path: str) -> tuple[pygame.Surface, int, int]:
        """Load a PNG image and resize it to match the canvas size.

        Args:
            file_path: Path to the PNG file.

        Returns:
            Tuple of (image surface, width, height).

        """
        self.log.info(f'Loading PNG image: {file_path}')
        image = pygame.image.load(file_path)
        width, height = image.get_size()
        self.log.info(f'Image dimensions: {width}x{height}')

        # Get current canvas size for resizing
        canvas_width, canvas_height = 32, 32  # Default fallback
        if hasattr(self, 'canvas') and self.canvas:
            canvas_width = self.canvas.pixels_across
            canvas_height = self.canvas.pixels_tall
            self.log.info(f'Using current canvas size: {canvas_width}x{canvas_height}')
        else:
            self.log.info('No canvas found, using default size: 32x32')

        # Check if image needs resizing to match canvas size
        if width != canvas_width or height != canvas_height:
            self.log.info(
                f'Resizing image from {width}x{height} to {canvas_width}x{canvas_height} to'
                f' match canvas'
            )
            image = pygame.transform.scale(image, (canvas_width, canvas_height))
            width, height = canvas_width, canvas_height
            self.log.info(f'Resized image to {width}x{height}')

        # Convert to RGB if needed, handling transparency
        if image.get_flags() & pygame.SRCALPHA:
            rgb_image = pygame.Surface((width, height))
            rgb_image.fill((255, 255, 255))  # White background
            rgb_image.blit(image, (0, 0))
            image = rgb_image
            self.log.info('Converted image with alpha channel to RGB')

        return image, width, height

    def _detect_png_transparency(
        self, image: pygame.Surface, file_path: str
    ) -> tuple[bool, pygame.Surface | None]:
        """Detect whether the original PNG image has transparency.

        Args:
            image: The converted RGB image surface.
            file_path: Path to the original PNG file.

        Returns:
            Tuple of (has_transparency, original_image_with_alpha_or_None).

        """
        if not (image.get_flags() & pygame.SRCALPHA):
            return False, None

        original_image = pygame.image.load(file_path)
        if original_image.get_flags() & pygame.SRCALPHA:
            self.log.info(
                'Image has transparency - will map transparent pixels to magenta (255, 0, 255)'
            )
            return True, original_image
        return False, None

    def _sample_png_colors(
        self,
        pixel_array: np.ndarray[Any, Any],
        width: int,
        height: int,
        *,
        has_transparency: bool,
        original_image: pygame.Surface | None,
    ) -> tuple[set[tuple[int, int, int]], int, int]:
        """Sample pixels from the image to find unique colors.

        Args:
            pixel_array: The numpy pixel array from the image.
            width: Image width.
            height: Image height.
            has_transparency: Whether the image has transparency.
            original_image: The original image with alpha channel, or None.

        Returns:
            Tuple of (unique_colors set, sample_count, transparent_pixel_count).

        """
        # Use a more efficient approach for large images
        sample_step = max(1, (width * height) // 10000)  # Sample up to 10k pixels
        self.log.info(f'Sampling every {sample_step} pixels for color analysis')

        unique_colors: set[tuple[int, int, int]] = set()
        sample_count = 0
        transparent_pixels = 0

        for y in range(0, height, sample_step):
            for x in range(0, width, sample_step):
                r, g, b = pixel_array[x, y]
                # Ensure we're working with Python ints, not numpy types
                color = (int(r), int(g), int(b))
                unique_colors.add(color)
                sample_count += 1

                # Check for transparency if we have the original image
                if has_transparency and original_image is not None:
                    original_pixel = original_image.get_at((x, y))
                    if original_pixel.a < ALPHA_TRANSPARENCY_THRESHOLD:
                        transparent_pixels += 1
                        # Map transparent pixels to magenta
                        unique_colors.discard(color)
                        unique_colors.add((255, 0, 255))

        return unique_colors, sample_count, transparent_pixels

    def _quantize_colors_if_needed(
        self, unique_colors: set[tuple[int, int, int]], *, has_transparency: bool
    ) -> set[tuple[int, int, int]]:
        """Quantize colors if there are too many for the palette.

        Args:
            unique_colors: Set of unique RGB color tuples.
            has_transparency: Whether the image has transparency.

        Returns:
            Possibly reduced set of unique colors.

        """
        reserved_for_transparency = 1 if has_transparency else 0
        max_colors = 1000
        available_colors = max_colors - reserved_for_transparency

        if len(unique_colors) <= available_colors:
            return unique_colors

        self.log.info('Too many colors detected, using color quantization...')
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
            if (
                closest_group is None or min_distance > COLOR_QUANTIZATION_GROUP_DISTANCE_THRESHOLD
            ):  # Lower threshold for better color separation
                if len(color_groups) < available_colors:
                    color_groups[color] = [color]
                else:
                    # Add to closest existing group
                    color_groups[closest_group].append(color)  # type: ignore[index]
            else:
                color_groups[closest_group].append(color)

        # Create representative colors for each group
        representative_colors = [
            group_color for group_color, colors in color_groups.items() if colors
        ]
        result = set(representative_colors)
        self.log.info(f'Quantized to {len(result)} representative colors')
        self.log.info(
            f'Available colors: {available_colors}, Color groups created: {len(color_groups)}'
        )
        return result

    @staticmethod
    def _color_distance(color_1: tuple[int, int, int], color_2: tuple[int, int, int]) -> float:
        """Calculate squared Euclidean distance between two RGB colors.

        Args:
            color_1: First RGB color tuple.
            color_2: Second RGB color tuple.

        Returns:
            Squared Euclidean distance as a float.

        """
        return sum((int(a) - int(b)) ** 2 for a, b in zip(color_1, color_2, strict=True))

    def _build_color_to_glyph_mapping(
        self,
        unique_colors: set[tuple[int, int, int]],
        *,
        has_transparency: bool,
    ) -> dict[tuple[int, int, int], str]:
        """Build a mapping from RGB colors to glyph characters.

        Args:
            unique_colors: Set of unique RGB color tuples.
            has_transparency: Whether the image has transparency.

        Returns:
            Dictionary mapping RGB tuples to glyph strings.

        """
        max_glyphs = 1000
        available_glyphs = list(SPRITE_GLYPHS[:max_glyphs])
        reserved_for_transparency = 1 if has_transparency else 0
        available_color_count = len(available_glyphs) - reserved_for_transparency

        self.log.info(
            f'Mapping colors: {len(unique_colors)} unique colors to {available_color_count}'
            f' available glyphs'
        )
        if has_transparency:
            self.log.info('Reserved 1 glyph for transparency')

        color_mapping: dict[tuple[int, int, int], str] = {}
        glyph_index = 0

        # First, ensure magenta (transparency) gets a glyph if we have transparency
        if has_transparency and (255, 0, 255) in unique_colors:
            color_mapping[255, 0, 255] = '\u2588'  # Use block character for transparency
            self.log.info("Reserved glyph '\u2588' for transparency (magenta)")

        # Map other colors to available glyphs
        for color in sorted(unique_colors):
            if color == (255, 0, 255) and has_transparency:
                continue  # Already handled above

            if glyph_index < available_color_count:
                color_mapping[color] = available_glyphs[glyph_index]
                glyph_index += 1
            else:
                # Map to closest existing color
                closest_color = min(
                    color_mapping.keys(),
                    key=lambda c: self._color_distance(color, c),
                )
                color_mapping[color] = color_mapping[closest_color]

        self.log.info(f'Final color mapping: {len(color_mapping)} colors mapped to glyphs')
        return color_mapping

    def _generate_pixel_string(
        self,
        pixel_array: np.ndarray[Any, Any],
        width: int,
        height: int,
        *,
        has_transparency: bool,
        original_image: pygame.Surface | None,
        color_mapping: dict[tuple[int, int, int], str],
    ) -> str:
        """Generate the pixel string for TOML output from pixel data.

        Args:
            pixel_array: The numpy pixel array from the image.
            width: Image width.
            height: Image height.
            has_transparency: Whether the image has transparency.
            original_image: The original image with alpha channel, or None.
            color_mapping: Mapping from RGB tuples to glyph characters.

        Returns:
            The pixel string with newlines between rows.

        """
        self.log.info('Generating pixel string...')
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
                        color_key = (255, 0, 255)

                # If color is not in mapping, find closest mapped color
                if color_key not in color_mapping:
                    closest_color = min(
                        color_mapping.keys(),
                        key=lambda c: self._color_distance(color_key, c),
                    )
                    color_mapping[color_key] = color_mapping[closest_color]
                    self.log.debug(f'Mapped unmapped color {color_key} to {closest_color}')

                row_chars.append(color_mapping[color_key])
            rows.append(''.join(row_chars))

            # Log progress for large images
            if height > PROGRESS_LOG_MIN_HEIGHT and y % (height // 10) == 0:
                self.log.info(f'Progress: {y}/{height} rows processed')

        return '\n'.join(rows)

    def _generate_toml_content(
        self,
        file_path: str,
        pixel_string: str,
        color_mapping: dict[tuple[int, int, int], str],
    ) -> str:
        """Generate the TOML file content from pixel string and color mapping.

        Args:
            file_path: Original PNG file path (used for naming).
            pixel_string: The pixel string with glyph characters.
            color_mapping: Mapping from RGB tuples to glyph characters.

        Returns:
            The complete TOML content string.

        Raises:
            ValueError: If no color definitions were generated.

        """
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
        self.log.info(f'Unique glyphs to define: {sorted(unique_glyphs)}')

        for glyph in sorted(unique_glyphs):
            # Find the first color that maps to this glyph
            for color, mapped_glyph in color_mapping.items():
                if mapped_glyph == glyph:
                    r, g, b = color
                    # Quote the glyph to handle special characters like '.'
                    toml_content += f'[colors."{glyph}"]\nred = {r}\ngreen = {g}\nblue = {b}\n\n'
                    self.log.info(f'Defined color {glyph}: RGB({r}, {g}, {b})')
                    break

        if not unique_glyphs:
            self.log.error('No colors to define - this will cause display issues!')
            raise ValueError('No colors found in the converted sprite')

        self.log.info(f'Generated {len(unique_glyphs)} color definitions')
        return toml_content

    def _save_and_validate_toml(self, file_path: str, toml_content: str) -> Path:
        """Save the TOML content to a file and validate its structure.

        Args:
            file_path: Original PNG file path (used to derive output path).
            toml_content: The complete TOML content string.

        Returns:
            The output path of the saved TOML file.

        """
        output_path = Path(file_path).with_suffix('.toml')
        Path(output_path).write_text(toml_content, encoding='utf-8')

        self.log.info('Validating generated TOML file...')
        self._validate_toml_content(output_path)

        return output_path

    def _validate_toml_content(self, output_path: Path) -> None:
        """Validate that a generated TOML file has required sections.

        Args:
            output_path: Path to the TOML file to validate.

        Raises:
            ValueError: If the TOML file is missing required sections.

        """
        with output_path.open(encoding='utf-8') as f:
            content = f.read()

        if '[sprite]' not in content:
            self.log.error('TOML file missing [sprite] section!')
            raise ValueError('Generated TOML file has no [sprite] section')

        if '[colors]' not in content:
            self.log.error('TOML file missing [colors] section!')
            raise ValueError('Generated TOML file has no [colors] section')

        color_count = content.count('[colors."')
        if color_count == 0:
            self.log.error('TOML file has no color definitions!')
            raise ValueError('Generated TOML file has no color definitions')

        self.log.info(f'TOML validation passed: {color_count} colors defined')

    def _load_converted_sprite(self, toml_path: str) -> None:
        """Load a converted TOML sprite into the editor.

        Args:
            toml_path: Path to the converted TOML file.

        """
        try:
            self.log.info('=== STARTING _load_converted_sprite ===')
            canvas_sprite = self._find_canvas_sprite()

            if not canvas_sprite:
                self.log.warning('Could not find canvas sprite to load converted file')
                return

            self._load_sprite_into_canvas(canvas_sprite, toml_path)  # type: ignore[arg-type]
            self._transfer_loaded_sprite_pixels(canvas_sprite)  # type: ignore[arg-type]
            self._finalize_sprite_load(canvas_sprite)  # type: ignore[arg-type]

        except (
            OSError,
            ValueError,
            AttributeError,
            TypeError,
            KeyError,
            pygame.error,
        ):
            self.log.exception('Error loading converted sprite into editor')

    def _find_canvas_sprite(self) -> object | None:
        """Find the canvas sprite in the scene that can handle file loading.

        Returns:
            The canvas sprite if found, or None.

        """
        self.log.info(f'Searching for canvas sprite in {len(self.all_sprites)} sprites...')
        for i, sprite in enumerate(self.all_sprites):
            self.log.info(
                f'Sprite {i}: {type(sprite)} - has on_load_file_event:'
                f' {hasattr(sprite, "on_load_file_event")}'
            )
            if hasattr(sprite, 'on_load_file_event'):
                self.log.info(f'Found canvas sprite: {type(sprite)}')
                return sprite
        return None

    def _load_sprite_into_canvas(self, canvas_sprite: AnimatedCanvasSprite, toml_path: str) -> None:
        """Load a TOML sprite file into the canvas sprite.

        Args:
            canvas_sprite: The canvas sprite to load into.
            toml_path: Path to the TOML file.

        """
        self.log.info(f'Loading converted sprite: {toml_path}')
        self.log.info(f'Found canvas sprite: {type(canvas_sprite)}')

        # Create a mock event for loading
        mock_event = MockEvent(text=toml_path)
        self.log.info('Calling on_load_file_event...')
        canvas_sprite.on_load_file_event(mock_event)  # type: ignore[arg-type]
        self.log.info('on_load_file_event completed')

        # Update border thickness after loading (in case canvas was resized)
        self.log.info('Updating border thickness after sprite load...')
        canvas_sprite._update_border_thickness()  # type: ignore[reportPrivateUsage]

        # Force a complete redraw to apply the new border settings
        self.log.info('Forcing canvas redraw with new border settings...')
        canvas_sprite.force_redraw()

    def _transfer_loaded_sprite_pixels(self, canvas_sprite: AnimatedCanvasSprite) -> None:
        """Transfer pixel data from a loaded animated sprite to the canvas.

        Args:
            canvas_sprite: The canvas sprite containing the loaded animation.

        """
        self.log.info(f'Canvas sprite type: {type(canvas_sprite)}')
        self.log.info(
            f'Canvas sprite has animated_sprite: {hasattr(canvas_sprite, "animated_sprite")}'
        )
        if hasattr(canvas_sprite, 'animated_sprite'):
            self.log.info(f'animated_sprite value: {canvas_sprite.animated_sprite}')
        if not (hasattr(canvas_sprite, 'animated_sprite') and canvas_sprite.animated_sprite):
            return

        self.log.info(f'Animated sprite loaded: {canvas_sprite.animated_sprite}')
        if not hasattr(canvas_sprite.animated_sprite, '_animations'):
            return

        animations = list(canvas_sprite.animated_sprite._animations.keys())  # type: ignore[reportPrivateUsage]
        self.log.info(f'Animations: {animations}')
        if not animations:
            return

        first_anim = animations[0]
        frames = canvas_sprite.animated_sprite._animations[first_anim]  # type: ignore[reportPrivateUsage]
        self.log.info(f"First animation '{first_anim}' has {len(frames)} frames")
        if not frames:
            return

        first_frame = frames[0]
        self.log.info(f'First frame size: {first_frame.get_size()}')
        self._apply_frame_pixels_to_canvas(canvas_sprite, first_frame)

    def _apply_frame_pixels_to_canvas(
        self, canvas_sprite: AnimatedCanvasSprite, first_frame: SpriteFrame
    ) -> None:
        """Apply pixel data from a frame to the canvas.

        Args:
            canvas_sprite: The canvas sprite to update.
            first_frame: The first frame of the animation to extract pixels from.

        """
        self.log.info('Transferring pixel data from loaded sprite to canvas...')
        if not (hasattr(first_frame, 'image') and first_frame.image):
            return

        frame_surface = first_frame.image
        frame_width, frame_height = frame_surface.get_size()
        self.log.info(f'Frame surface size: {frame_width}x{frame_height}')

        # Convert the frame surface to pixel data
        pixel_data: list[tuple[int, ...]] = []
        for y in range(frame_height):
            for x in range(frame_width):
                color = frame_surface.get_at((x, y))
                # Handle transparency key specially - keep it opaque for canvas
                if len(color) == RGBA_COMPONENT_COUNT:
                    r, g, b, a = color
                    if (r, g, b) == (255, 0, 255) and a == 0:
                        # Transparent magenta should be opaque magenta for canvas
                        pixel_data.append((255, 0, 255, 255))
                    else:
                        pixel_data.append((r, g, b, a))
                else:
                    pixel_data.append((color.r, color.g, color.b, 255))

        # Update canvas pixels
        canvas_sprite.pixels = pixel_data
        canvas_sprite.dirty_pixels = [True] * len(pixel_data)
        self.log.info(f'Transferred {len(pixel_data)} pixels to canvas')

        # Update mini view pixels too
        if hasattr(canvas_sprite, 'mini_view') and canvas_sprite.mini_view is not None:
            canvas_sprite.mini_view.pixels = pixel_data.copy()
            canvas_sprite.mini_view.dirty_pixels = [True] * len(pixel_data)
            self.log.info('Updated mini view pixels')

    def _finalize_sprite_load(self, canvas_sprite: AnimatedCanvasSprite) -> None:
        """Finalize sprite loading by forcing redraws and initializing onion skinning.

        Args:
            canvas_sprite: The canvas sprite that was loaded.

        """
        # Force canvas redraw to show the new sprite
        self.log.info('Forcing canvas redraw after loading...')
        canvas_sprite.dirty = 1
        canvas_sprite.force_redraw()

        # Update mini view if it exists
        if hasattr(canvas_sprite, 'mini_view') and canvas_sprite.mini_view is not None:
            self.log.info('Updating mini view...')
            canvas_sprite.mini_view.pixels = canvas_sprite.pixels.copy()
            canvas_sprite.mini_view.dirty_pixels = [True] * len(canvas_sprite.pixels)
            canvas_sprite.mini_view.dirty = 1
            canvas_sprite.mini_view.force_redraw()

        # Initialize onion skinning for the loaded sprite
        if hasattr(canvas_sprite, 'animated_sprite') and canvas_sprite.animated_sprite:
            self._initialize_onion_skinning_for_sprite(canvas_sprite.animated_sprite)

        self.log.info('Converted sprite loaded successfully into editor')

    def _initialize_onion_skinning_for_sprite(self, loaded_sprite: AnimatedSprite) -> None:
        """Initialize onion skinning for a newly loaded sprite.

        Args:
            loaded_sprite: The loaded animated sprite

        """
        try:
            from .onion_skinning import get_onion_skinning_manager

            onion_manager = get_onion_skinning_manager()

            # Clear any existing onion skinning state for this sprite
            if hasattr(loaded_sprite, '_animations') and loaded_sprite._animations:  # type: ignore[reportPrivateUsage]
                for animation_name in loaded_sprite._animations:  # type: ignore[reportPrivateUsage]
                    onion_manager.clear_animation_onion_skinning(animation_name)
                    self.log.debug(f'Cleared onion skinning state for animation: {animation_name}')

            # Initialize onion skinning for all animations in the loaded sprite
            if hasattr(loaded_sprite, '_animations') and loaded_sprite._animations:  # type: ignore[reportPrivateUsage]
                for animation_name, frames in loaded_sprite._animations.items():  # type: ignore[reportPrivateUsage]
                    # Enable onion skinning for all frames except the first one
                    frame_states = {}
                    for frame_idx in range(len(frames)):
                        # Enable onion skinning for all frames except frame 0
                        frame_states[frame_idx] = frame_idx != 0

                    onion_manager.set_animation_onion_state(animation_name, frame_states)  # type: ignore[arg-type]
                    self.log.debug(
                        f"Initialized onion skinning for animation '{animation_name}' with"
                        f' {len(frames)} frames'
                    )

            # Ensure global onion skinning is enabled
            if not onion_manager.is_global_onion_skinning_enabled():
                onion_manager.toggle_global_onion_skinning()
                self.log.debug('Enabled global onion skinning for new sprite')

            self.log.info('Onion skinning initialized for loaded sprite')

        except (ImportError, AttributeError, KeyError, TypeError):
            self.log.exception('Failed to initialize onion skinning for loaded sprite')

    def handle_event(self, event: events.HashableEvent) -> None:
        """Handle pygame events."""
        # Debug logging for keyboard events
        if event.type == pygame.KEYDOWN:
            self.log.debug(f'KEYDOWN event received in handle_event: key={event.key}')

        # Handle confirmation dialog clicks first (highest priority)
        if (
            event.type == pygame.MOUSEBUTTONDOWN
            and hasattr(self, 'confirmation_dialog')
            and self.confirmation_dialog
        ):
            mouse_pos = pygame.mouse.get_pos()
            if self.confirmation_dialog.rect.collidepoint(mouse_pos):
                # Convert to dialog-relative coordinates
                dialog_relative_pos = (
                    mouse_pos[0] - self.confirmation_dialog.rect.x,
                    mouse_pos[1] - self.confirmation_dialog.rect.y,
                )
                if self.confirmation_dialog.handle_mouse_down(dialog_relative_pos):
                    self.confirmation_dialog = None  # Clear reference after handling
                    return  # Event handled, don't pass to other handlers

        super().handle_event(event)  # type: ignore[arg-type]

        if event.type == pygame.WINDOWLEAVE:
            # Notify sprites that mouse left window
            for sprite in self.all_sprites:
                if hasattr(sprite, 'on_mouse_leave_window_event'):
                    sprite.on_mouse_leave_window_event(event)

    def deflate(self: Self) -> dict[str, Any]:
        """Deflate a sprite to a Bitmappy config file.

        Returns:
            dict: The result.

        Raises:
            StopIteration: If the RGB triplet generator produces no data.

        """
        try:
            self.log.debug(f'Starting deflate for {self.name}')
            self.log.debug(f'Image dimensions: {self.image.get_size()}')

            # Note: This deflate method is incomplete - configparser was removed
            # as we only support TOML format now. This needs to be reimplemented
            # to generate TOML output using the toml library.
            config: dict[str, Any] = {}

            # Get the raw pixel data and log its size
            pixel_string = pygame.image.tobytes(self.image, 'RGB')
            self.log.debug(f'Raw pixel string length: {len(pixel_string)}')

            # Log the first few bytes of pixel data
            self.log.debug(f'First 12 bytes of pixel data: {list(pixel_string[:12])}')

            # Create the generator and log initial state
            raw_pixels = rgb_triplet_generator(pixel_data=pixel_string)
            self.log.debug('Created RGB triplet generator')

            # Try to get the first triplet
            try:
                first_triplet = next(raw_pixels)
                self.log.debug(f'First RGB triplet: {first_triplet}')
                # Reset generator
                raw_pixels = rgb_triplet_generator(pixel_data=pixel_string)
            except StopIteration:
                self.log.exception('Generator empty on first triplet!')
                raise

            # Now proceed with the rest of deflate
            raw_pixels = list(raw_pixels)
            self.log.debug(f'Converted {len(raw_pixels)} RGB triplets to list')

            # Continue with original deflate code...
            colors = set(raw_pixels)
            self.log.debug(f'Found {len(colors)} unique colors')

        except Exception:
            self.log.exception('Error in deflate')
            raise
        else:
            return config

    # Controller Support Methods
    @override
    def on_controller_button_down_event(self, event: events.HashableEvent) -> None:
        """Handle controller button down events for multi-controller system.

        Args:
            event (pygame.event.Event): The controller button down event.

        """
        # Scan for controllers and update manager
        self.multi_controller_manager.scan_for_controllers()

        # Get controller info
        instance_id = event.instance_id
        controller_info = self.multi_controller_manager.get_controller_info(instance_id)

        if not controller_info:
            return

        LOG.debug(f'Controller button down: {event.button}')

        # Handle controller assignment on first button press
        if controller_info.status.value == 'connected':
            controller_id = self.multi_controller_manager.assign_controller(instance_id)
            if controller_id is not None:
                # Create controller selection for this controller
                self.controller_selections[controller_id] = ControllerSelection(
                    controller_id, instance_id
                )

        # Get controller ID for this instance
        controller_id = self.multi_controller_manager.get_controller_id(instance_id)
        if controller_id is None:
            return

        # Get or create controller selection
        if controller_id not in self.controller_selections:
            self.controller_selections[controller_id] = ControllerSelection(
                controller_id, instance_id
            )

        controller_selection = self.controller_selections[controller_id]

        # Update controller activity
        self.multi_controller_manager.update_controller_activity(instance_id)
        controller_selection.update_activity()

        # Handle button presses

        # Get controller mode for mode-specific handling
        controller_mode = self.mode_switcher.get_controller_mode(controller_id)

        # Handle mode-specific button presses
        if controller_mode and controller_mode.value == 'canvas':
            self._handle_canvas_button_press(controller_id, event.button)
        elif controller_mode and controller_mode.value in {'r_slider', 'g_slider', 'b_slider'}:
            self._handle_slider_button_press(controller_id, event.button)
        else:
            # Default to film strip mode handling
            self._handle_film_strip_button_press(controller_id, event.button)

    def _handle_film_strip_button_press(self, controller_id: int, button: int) -> None:
        """Handle button presses for film strip mode."""
        button_handlers = {
            pygame.CONTROLLER_BUTTON_A: (
                'selecting current frame',
                lambda: self._multi_controller_select_current_frame(controller_id),
            ),
            pygame.CONTROLLER_BUTTON_B: (
                'UNDO',
                self._handle_undo,
            ),
            pygame.CONTROLLER_BUTTON_Y: (
                'toggling onion skinning',
                lambda: self._multi_controller_toggle_onion_skinning(controller_id),
            ),
            pygame.CONTROLLER_BUTTON_DPAD_LEFT: (
                'previous frame',
                lambda: self._multi_controller_previous_frame(controller_id),
            ),
            pygame.CONTROLLER_BUTTON_DPAD_RIGHT: (
                'next frame',
                lambda: self._multi_controller_next_frame(controller_id),
            ),
            pygame.CONTROLLER_BUTTON_DPAD_UP: (
                'previous animation',
                lambda: self._multi_controller_previous_animation(controller_id),
            ),
            pygame.CONTROLLER_BUTTON_DPAD_DOWN: (
                'next animation',
                lambda: self._multi_controller_next_animation(controller_id),
            ),
            pygame.CONTROLLER_BUTTON_START: (
                'activate controller',
                lambda: self._multi_controller_activate(controller_id),
            ),
            pygame.CONTROLLER_BUTTON_LEFTSHOULDER: (
                'moving indicator left',
                lambda: self._multi_controller_previous_frame(controller_id),
            ),
            pygame.CONTROLLER_BUTTON_RIGHTSHOULDER: (
                'moving indicator right',
                lambda: self._multi_controller_next_frame(controller_id),
            ),
        }

        if button == pygame.CONTROLLER_BUTTON_X:
            # X button (Square): RESERVED for redo operations (only when selected frame is visible)
            if self.selected_frame_visible:
                LOG.debug(f'Controller {controller_id}: X button pressed - REDO')
                self._handle_redo()
            else:
                LOG.debug(
                    f'Controller {controller_id}: X button pressed - DISABLED (selected frame'
                    f' hidden)'
                )
            return

        if button in button_handlers:
            description, handler = button_handlers[button]
            LOG.debug(f'Controller {controller_id}: button pressed - {description}')
            handler()
        else:
            # Unhandled buttons
            LOG.debug(f'Controller {controller_id}: button {button} pressed - UNHANDLED')

    def _handle_canvas_button_press(self, controller_id: int, button: int) -> None:
        """Handle button presses for canvas mode."""
        if button == pygame.CONTROLLER_BUTTON_A:
            self._handle_canvas_a_button(controller_id)
        elif button == pygame.CONTROLLER_BUTTON_B:
            LOG.debug(f'Controller {controller_id}: B button pressed - UNDO')
            self._handle_undo()
        elif button == pygame.CONTROLLER_BUTTON_Y:
            self._handle_canvas_y_button(controller_id)
        elif button == pygame.CONTROLLER_BUTTON_X:
            self._handle_canvas_x_button(controller_id)
        elif button == pygame.CONTROLLER_BUTTON_DPAD_LEFT:
            LOG.debug(
                f'Controller {controller_id}: D-pad left pressed - start continuous movement left'
            )
            self._start_canvas_continuous_movement(controller_id, -1, 0)
        elif button == pygame.CONTROLLER_BUTTON_DPAD_RIGHT:
            LOG.debug(
                f'Controller {controller_id}: D-pad right pressed - start continuous movement right'
            )
            self._start_canvas_continuous_movement(controller_id, 1, 0)
        elif button == pygame.CONTROLLER_BUTTON_DPAD_UP:
            LOG.debug(
                f'Controller {controller_id}: D-pad up pressed - start continuous movement up'
            )
            self._start_canvas_continuous_movement(controller_id, 0, -1)
        elif button == pygame.CONTROLLER_BUTTON_DPAD_DOWN:
            LOG.debug(
                f'Controller {controller_id}: D-pad down pressed - start continuous movement down'
            )
            self._start_canvas_continuous_movement(controller_id, 0, 1)
        elif button == pygame.CONTROLLER_BUTTON_LEFTSHOULDER:
            self._handle_canvas_shoulder_button(controller_id, is_left=True)
        elif button == pygame.CONTROLLER_BUTTON_RIGHTSHOULDER:
            self._handle_canvas_shoulder_button(controller_id, is_left=False)
        else:
            self.log.debug(
                f'DEBUG: Controller {controller_id}: Button {button} not handled in canvas mode'
            )
            LOG.debug(f'Controller {controller_id}: Button {button} not handled in canvas mode')

    def _handle_canvas_a_button(self, controller_id: int) -> None:
        """Handle A button press in canvas mode (start drag/paint)."""
        if not self.selected_frame_visible:
            LOG.debug(
                f'Controller {controller_id}: A button pressed - DISABLED (selected frame hidden)'
            )
            return

        LOG.debug(f'Controller {controller_id}: A button pressed - starting controller drag')

        # Initialize controller drag tracking if not exists
        if not hasattr(self, 'controller_drags'):
            self.controller_drags: dict[int, dict[str, Any]] = {}

        # Start drag operation for this controller
        self.controller_drags[controller_id] = {
            'active': True,
            'start_position': self.mode_switcher.get_controller_position(controller_id),
            'pixels_drawn': [],
            'start_time': time.time(),
        }

        # Paint at the current position
        self._canvas_paint_at_controller_position(controller_id)

    def _handle_canvas_x_button(self, controller_id: int) -> None:
        """Handle X button press in canvas mode (redo)."""
        if self.selected_frame_visible:
            LOG.debug(f'Controller {controller_id}: X button pressed - REDO')
            self._handle_redo()
        else:
            LOG.debug(
                f'Controller {controller_id}: X button pressed - DISABLED (selected frame hidden)'
            )

    def _handle_canvas_y_button(self, controller_id: int) -> None:
        """Handle Y button press in canvas mode (toggle visibility or fill direction)."""
        LOG.debug(
            f'Controller {controller_id}: Y button pressed - toggling selected frame visibility'
        )
        self._multi_controller_toggle_selected_frame_visibility(controller_id)

    def _handle_canvas_shoulder_button(self, controller_id: int, *, is_left: bool) -> None:
        """Handle shoulder button press in canvas mode (move/paint 8 pixels).

        Args:
            controller_id: The controller ID.
            is_left: True for left shoulder, False for right shoulder.

        """
        if not (
            hasattr(self, 'controller_selections') and controller_id in self.controller_selections
        ):
            return

        fill_direction = self.controller_selections[controller_id].get_fill_direction()
        a_button_held = self._is_controller_button_held(controller_id, pygame.CONTROLLER_BUTTON_A)
        direction_label = 'LEFT' if is_left else 'RIGHT'
        distance = -8 if is_left else 8

        if fill_direction == 'HORIZONTAL':
            if a_button_held:
                LOG.debug(
                    f'Controller {controller_id}: {direction_label} SHOULDER + A - paint 8 pixels'
                    f' {"left" if is_left else "right"}'
                )
                self._canvas_paint_horizontal_line(controller_id, distance)
            else:
                LOG.debug(
                    f'Controller {controller_id}: {direction_label} SHOULDER - jump 8 pixels'
                    f' {"left" if is_left else "right"}'
                )
                self._canvas_jump_horizontal(controller_id, distance)
        elif a_button_held:
            LOG.debug(
                f'Controller {controller_id}: {direction_label} SHOULDER + A - paint 8 pixels'
                f' {"up" if is_left else "down"}'
            )
            self._canvas_paint_vertical_line(controller_id, distance)
        else:
            LOG.debug(
                f'Controller {controller_id}: {direction_label} SHOULDER - jump 8 pixels'
                f' {"up" if is_left else "down"}'
            )
            self._canvas_jump_vertical(controller_id, distance)

    def _handle_slider_button_press(self, controller_id: int, button: int) -> None:
        """Handle button presses for slider mode."""
        self.log.debug(
            f'DEBUG: _handle_slider_button_press called for controller {controller_id}, button'
            f' {button}'
        )

        if button == pygame.CONTROLLER_BUTTON_A:
            # A button: No action in slider mode
            self.log.debug(
                f'DEBUG: Controller {controller_id}: A button pressed - no action in slider mode'
            )
            LOG.debug(f'Controller {controller_id}: A button pressed - no action in slider mode')
        elif button == pygame.CONTROLLER_BUTTON_DPAD_LEFT:
            # D-pad left: Start continuous decrease
            self.log.debug(
                f'DEBUG: Controller {controller_id}: D-pad left pressed - start continuous decrease'
            )
            LOG.debug(f'Controller {controller_id}: D-pad left pressed - start continuous decrease')
            self._start_slider_continuous_adjustment(controller_id, -1)
        elif button == pygame.CONTROLLER_BUTTON_DPAD_RIGHT:
            # D-pad right: Start continuous increase
            self.log.debug(
                f'DEBUG: Controller {controller_id}: D-pad right pressed - start continuous'
                f' increase'
            )
            LOG.debug(
                f'Controller {controller_id}: D-pad right pressed - start continuous increase'
            )
            self._start_slider_continuous_adjustment(controller_id, 1)
        elif button == pygame.CONTROLLER_BUTTON_DPAD_UP:
            # D-pad up: Navigate to previous slider mode (B -> G -> R)
            self.log.debug(
                f'DEBUG: Controller {controller_id}: D-pad up pressed - navigate to previous slider'
                f' mode'
            )
            LOG.debug(
                f'Controller {controller_id}: D-pad up pressed - navigate to previous slider mode'
            )
            self._handle_slider_mode_navigation('up', controller_id)
        elif button == pygame.CONTROLLER_BUTTON_DPAD_DOWN:
            # D-pad down: Navigate to next slider mode (R -> G -> B)
            self.log.debug(
                f'DEBUG: Controller {controller_id}: D-pad down pressed - navigate to next slider'
                f' mode'
            )
            LOG.debug(
                f'Controller {controller_id}: D-pad down pressed - navigate to next slider mode'
            )
            self._handle_slider_mode_navigation('down', controller_id)
        elif button == pygame.CONTROLLER_BUTTON_LEFTSHOULDER:
            # Left shoulder (L1): Start continuous decrease by 8
            self.log.debug(
                f'DEBUG: Controller {controller_id}: Left shoulder pressed - start continuous'
                f' decrease by 8'
            )
            LOG.debug(
                f'Controller {controller_id}: Left shoulder pressed - start continuous decrease by'
                f' 8'
            )
            self._start_slider_continuous_adjustment(controller_id, -8)
        elif button == pygame.CONTROLLER_BUTTON_RIGHTSHOULDER:
            # Right shoulder (R1): Start continuous increase by 8
            self.log.debug(
                f'DEBUG: Controller {controller_id}: Right shoulder pressed - start continuous'
                f' increase by 8'
            )
            LOG.debug(
                f'Controller {controller_id}: Right shoulder pressed - start continuous increase by'
                f' 8'
            )
            self._start_slider_continuous_adjustment(controller_id, 8)
        else:
            # Other buttons not handled in slider mode (including B button)
            self.log.debug(
                f'DEBUG: Controller {controller_id}: Button {button} not handled in slider mode'
            )
            LOG.debug(f'Controller {controller_id}: Button {button} not handled in slider mode')

    @override
    def on_controller_button_up_event(self, event: events.HashableEvent) -> None:
        """Handle controller button up events.

        Args:
            event (pygame.event.Event): The controller button up event.

        """
        instance_id = event.instance_id

        # Get controller ID for this instance
        controller_id = self.multi_controller_manager.get_controller_id(instance_id)
        if controller_id is None:
            return

        # Handle button releases for continuous slider adjustment (D-pad and shoulder buttons)
        if event.button in {
            pygame.CONTROLLER_BUTTON_DPAD_LEFT,
            pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
            pygame.CONTROLLER_BUTTON_LEFTSHOULDER,
            pygame.CONTROLLER_BUTTON_RIGHTSHOULDER,
        }:
            self._stop_slider_continuous_adjustment(controller_id)

            # Update color well when slider adjustment is finished (only if controller is in slider
            # mode)
            controller_mode = self.mode_switcher.get_controller_mode(controller_id)
            if controller_mode and controller_mode.value in {'r_slider', 'g_slider', 'b_slider'}:
                self._update_color_well_from_sliders()

        # Handle button releases for continuous canvas movement (D-pad buttons)
        if event.button in {
            pygame.CONTROLLER_BUTTON_DPAD_LEFT,
            pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
            pygame.CONTROLLER_BUTTON_DPAD_UP,
            pygame.CONTROLLER_BUTTON_DPAD_DOWN,
        }:
            self._stop_canvas_continuous_movement(controller_id)

        # Handle A button release in canvas mode (end controller drag)
        if event.button == pygame.CONTROLLER_BUTTON_A:
            self._handle_controller_drag_end(controller_id)

    def _handle_controller_drag_end(self, controller_id: int) -> None:
        """Handle the end of a controller drag operation.

        Args:
            controller_id: The controller that released the A button.

        """
        if not (hasattr(self, 'controller_drags') and controller_id in self.controller_drags):
            return

        drag_info = self.controller_drags[controller_id]
        if not drag_info['active']:
            return

        # End the drag operation
        drag_info['active'] = False
        drag_info['end_time'] = time.time()
        drag_info['end_position'] = self.mode_switcher.get_controller_position(controller_id)

        self.log.debug(
            f'DEBUG: Controller {controller_id}: Drag operation drew'
            f' {len(drag_info["pixels_drawn"])} pixels'
        )

        if not drag_info['pixels_drawn']:
            return

        LOG.debug(
            f'Controller {controller_id}: Drag operation completed with'
            f' {len(drag_info["pixels_drawn"])} pixels drawn'
        )

        pixel_changes = self._collect_drag_pixel_changes(controller_id, drag_info)
        self._submit_drag_pixel_changes(controller_id, pixel_changes)

    def _collect_drag_pixel_changes(
        self, controller_id: int, drag_info: dict[str, Any]
    ) -> list[tuple[int, tuple[int, ...], tuple[int, ...]]]:
        """Collect pixel changes from a drag operation, merging with pending changes.

        Args:
            controller_id: The controller ID.
            drag_info: The drag operation info dict.

        Returns:
            List of (x, y, old_color, new_color) tuples.

        """
        # Convert controller drag pixels to undo/redo format
        pixel_changes: list[tuple[int, tuple[int, ...], tuple[int, ...]]] = []
        for pixel_info in drag_info['pixels_drawn']:
            position = pixel_info['position']
            color = pixel_info['color']
            old_color = pixel_info.get('old_color', (0, 0, 0))  # Use stored old color
            x, y = position[0], position[1]
            pixel_changes.append((x, y, old_color, color))  # type: ignore[arg-type]

        # Debug: Show undo stack before merging
        if hasattr(self, 'undo_redo_manager') and self.undo_redo_manager:
            self.log.debug(
                'DEBUG: Undo stack before merging has'
                f' {len(self.undo_redo_manager.undo_stack)} operations'
            )
            for i, op in enumerate(self.undo_redo_manager.undo_stack):
                self.log.debug(f'DEBUG:   Operation {i}: {op.operation_type} - {op.description}')

        # Absorb any pending single pixel operation from canvas interface
        # This merges the initial A button pixel with the drag pixels
        if hasattr(self, '_current_pixel_changes') and self._current_pixel_changes:
            self.log.debug(
                f'DEBUG: Absorbing {len(self._current_pixel_changes)} pending pixel(s)'
                f' from canvas interface'
            )
            self.log.debug(f'DEBUG: Pending pixels: {self._current_pixel_changes}')
            # Add the pending pixels to the beginning of the controller drag pixels
            pixel_changes = self._current_pixel_changes + pixel_changes
            self.log.debug(f'DEBUG: Merged pixel_changes now has {len(pixel_changes)} pixels')
            # Clear the pending pixels to prevent duplicate undo operation
            self._current_pixel_changes = []

            # Remove the old single pixel entry from the undo stack
            # This prevents having two separate undo operations
            if hasattr(self, 'undo_redo_manager') and self.undo_redo_manager:
                if self.undo_redo_manager.undo_stack:
                    removed_operation = self.undo_redo_manager.undo_stack.pop()
                    self.log.debug(
                        'DEBUG: Removed single pixel operation from undo stack:'
                        f' {removed_operation.operation_type}'
                    )
                    self.log.debug(
                        'DEBUG: Undo stack after removal has'
                        f' {len(self.undo_redo_manager.undo_stack)} operations'
                    )
                else:
                    self.log.debug('DEBUG: No operations in undo stack to remove')
        else:
            self.log.debug('DEBUG: No pending pixels to absorb from canvas interface')

        return pixel_changes

    def _submit_drag_pixel_changes(
        self, controller_id: int, pixel_changes: list[tuple[int, tuple[int, ...], tuple[int, ...]]]
    ) -> None:
        """Submit collected drag pixel changes to the undo/redo system.

        Args:
            controller_id: The controller ID.
            pixel_changes: List of (x, y, old_color, new_color) tuples.

        """
        if not pixel_changes or not hasattr(self, 'canvas_operation_tracker'):
            return

        # Get current frame information for frame-specific tracking
        current_animation = None
        current_frame = None
        if hasattr(self, 'canvas') and self.canvas:
            current_animation = getattr(self.canvas, 'current_animation', None)
            current_frame = getattr(self.canvas, 'current_frame', None)

        # Use frame-specific tracking if we have frame information
        if current_animation is not None and current_frame is not None:
            self.canvas_operation_tracker.add_frame_pixel_changes(
                current_animation,
                current_frame,
                pixel_changes,  # type: ignore[arg-type]
            )
            LOG.debug(
                f'Controller {controller_id}: Submitted {len(pixel_changes)} pixel'
                f' changes for frame {current_animation}[{current_frame}] undo/redo'
            )
        else:
            # Fall back to global tracking
            self.canvas_operation_tracker.add_pixel_changes(pixel_changes)  # type: ignore[arg-type]
            LOG.debug(
                f'Controller {controller_id}: Submitted {len(pixel_changes)} pixel'
                f' changes for global undo/redo'
            )

    def _canvas_paint_at_controller_position(
        self, controller_id: int, *, force: bool = False
    ) -> None:
        """Paint at the controller's current canvas position.

        Args:
            controller_id: The ID of the controller
            force: If True, always paint regardless of current pixel color

        """
        # Get controller's canvas position
        position = self.mode_switcher.get_controller_position(controller_id)
        if not position or not position.is_valid:
            self.log.debug(f'DEBUG: Controller {controller_id} has no valid canvas position')
            return

        # Get current color from the color picker
        current_color = self._get_current_color()
        self.log.debug(f'DEBUG: _canvas_paint_at_controller_position() got color: {current_color}')

        # Check if pixel is already the selected color (debouncing)
        if not force:
            current_pixel_color = self._get_canvas_pixel_color(
                position.position[0], position.position[1]
            )
            if current_pixel_color == current_color:
                self.log.debug(
                    f'DEBUG: Pixel at {position.position} is already {current_color}, skipping'
                    f' paint'
                )
                return

        # Get the old color BEFORE changing the pixel for undo functionality
        old_color = self._get_canvas_pixel_color(position.position[0], position.position[1])
        if old_color is None:
            old_color = (0, 0, 0)

        # Paint at the position
        self._set_canvas_pixel(position.position[0], position.position[1], current_color)

        # Track this pixel in the controller drag operation
        self._track_controller_drag_pixel(
            controller_id, position.position, current_color, old_color
        )

        self.log.debug(
            f'DEBUG: Painted at canvas position {position.position} with color {current_color}'
        )

    def _get_canvas_pixel_color(self, x: int, y: int) -> tuple[int, ...] | None:
        """Get the color of a pixel on the canvas.

        Args:
            x: X coordinate.
            y: Y coordinate.

        Returns:
            The pixel color tuple, or None if unavailable.

        """
        if not (hasattr(self, 'canvas') and self.canvas):
            return None

        if hasattr(self.canvas, 'canvas_interface'):
            try:
                return self.canvas.canvas_interface.get_pixel_at(x, y)
            except (IndexError, AttributeError, TypeError) as pixel_error:
                LOG.debug(f'Could not get pixel color: {pixel_error}')
                return (0, 0, 0)

        if 0 <= x < self.canvas.pixels_across and 0 <= y < self.canvas.pixels_tall:
            pixel_num = y * self.canvas.pixels_across + x
            return self.canvas.pixels[pixel_num]
        return None

    def _set_canvas_pixel(self, x: int, y: int, color: tuple[int, ...]) -> None:
        """Set a pixel color on the canvas.

        Args:
            x: X coordinate.
            y: Y coordinate.
            color: The color tuple to set.

        """
        if not (hasattr(self, 'canvas') and self.canvas):
            return

        if hasattr(self.canvas, 'canvas_interface'):
            self.canvas.canvas_interface.set_pixel_at(x, y, color)  # type: ignore[arg-type]
        elif 0 <= x < self.canvas.pixels_across and 0 <= y < self.canvas.pixels_tall:
            pixel_num = y * self.canvas.pixels_across + x
            self.canvas.pixels[pixel_num] = color
            self.canvas.dirty_pixels[pixel_num] = True
            self.canvas.dirty = 1

    def _track_controller_drag_pixel(
        self,
        controller_id: int,
        position: tuple[int, int],
        current_color: tuple[int, ...],
        old_color: tuple[int, ...],
    ) -> None:
        """Track a painted pixel in the controller drag operation for undo.

        Args:
            controller_id: The controller ID.
            position: The (x, y) position of the painted pixel.
            current_color: The new color that was painted.
            old_color: The original color before painting.

        """
        if not (hasattr(self, 'controller_drags') and controller_id in self.controller_drags):
            self.log.debug(
                f'DEBUG: No controller drags or controller {controller_id} not in controller_drags'
            )
            return

        drag_info = self.controller_drags[controller_id]
        if not drag_info['active']:
            self.log.debug(f'DEBUG: Controller drag not active for controller {controller_id}')
            return

        pixel_info = {
            'position': position,
            'color': current_color,
            'old_color': old_color,  # Store the original color for undo
            'timestamp': time.time(),
        }
        drag_info['pixels_drawn'].append(pixel_info)
        self.log.debug(
            f'DEBUG: Controller drag tracking pixel at {position}, total'
            f' pixels: {len(drag_info["pixels_drawn"])}'
        )

    def _canvas_erase_at_controller_position(self, controller_id: int) -> None:
        """Erase at the controller's current canvas position."""
        # Get controller's canvas position
        position = self.mode_switcher.get_controller_position(controller_id)
        if not position or not position.is_valid:
            self.log.debug(f'DEBUG: Controller {controller_id} has no valid canvas position')
            return

        # Erase at the position (paint with background color)
        if hasattr(self, 'canvas') and self.canvas:
            background_color = (0, 0, 0)  # Black background
            # Use the canvas interface to set the pixel
            if hasattr(self.canvas, 'canvas_interface'):
                self.canvas.canvas_interface.set_pixel_at(
                    position.position[0], position.position[1], background_color
                )
            else:
                # Fallback: directly set pixel if interface not available
                x, y = position.position[0], position.position[1]
                if 0 <= x < self.canvas.pixels_across and 0 <= y < self.canvas.pixels_tall:
                    pixel_num = y * self.canvas.pixels_across + x
                    self.canvas.pixels[pixel_num] = background_color
                    self.canvas.dirty_pixels[pixel_num] = True
                    self.canvas.dirty = 1
            self.log.debug(f'DEBUG: Erased at canvas position {position.position}')

    def _canvas_move_cursor(self, controller_id: int, dx: int, dy: int) -> None:
        """Move the controller's canvas cursor."""
        # Get current position
        position = self.mode_switcher.get_controller_position(controller_id)
        if not position:
            # Initialize at (0, 0) if no position
            old_position = (0, 0)
            new_position = (0, 0)
        else:
            old_position = position.position
            new_position = (position.position[0] + dx, position.position[1] + dy)

        # Clamp to canvas bounds
        if hasattr(self, 'canvas') and self.canvas:
            canvas_width = getattr(self.canvas, 'width', 32)
            canvas_height = getattr(self.canvas, 'height', 32)
            new_position = (
                max(0, min(canvas_width - 1, new_position[0])),
                max(0, min(canvas_height - 1, new_position[1])),
            )

        # Track controller position change for undo/redo (only if position actually changed and not
        # in continuous movement)
        if (
            old_position != new_position
            and not getattr(self, '_applying_undo_redo', False)
            and not self._is_controller_in_continuous_movement(controller_id)
            and hasattr(self, 'controller_position_operation_tracker')
        ):
            # Get current mode for context
            current_mode = self.mode_switcher.get_controller_mode(controller_id)
            mode_str = current_mode.value if current_mode else None

            self.controller_position_operation_tracker.add_controller_position_change(
                controller_id, old_position, new_position, mode_str, mode_str
            )

        # Update position
        self.mode_switcher.save_controller_position(controller_id, new_position)

        # If controller is in an active drag operation, paint at the new position
        # (the paint method will check if the pixel needs painting)
        if hasattr(self, 'controller_drags') and controller_id in self.controller_drags:
            drag_info = self.controller_drags[controller_id]
            if drag_info['active']:
                self.log.debug(
                    f'DEBUG: Controller {controller_id}: In active drag, painting at new position'
                    f' {new_position}'
                )
                self._canvas_paint_at_controller_position(controller_id)

        # Update visual indicator
        self._update_controller_canvas_visual_indicator(controller_id)

        self.log.debug(f'DEBUG: Controller {controller_id} canvas cursor moved to {new_position}')

    def _is_controller_in_continuous_movement(self, controller_id: int) -> bool:
        """Check if a controller is currently in continuous movement mode.

        Returns:
            bool: True if the condition is met, False otherwise.

        """
        # Check for canvas continuous movement
        if (
            hasattr(self, 'canvas_continuous_movements')
            and controller_id in self.canvas_continuous_movements
        ):
            return True

        # Check for slider continuous adjustment
        return bool(
            hasattr(self, 'slider_continuous_adjustments')
            and controller_id in self.slider_continuous_adjustments
        )

    def _update_controller_canvas_visual_indicator(self, controller_id: int) -> None:
        """Update the visual indicator for a controller's canvas position."""
        # Get controller info
        controller_info = self.multi_controller_manager.get_controller_info(controller_id)
        if not controller_info:
            return

        # Get current canvas position
        position = self.mode_switcher.get_controller_position(controller_id)
        if not position:
            return

        # Update visual indicator
        if hasattr(self, 'visual_collision_manager'):
            # Remove old indicator
            self.visual_collision_manager.remove_controller_indicator(controller_id)

            # Add new canvas indicator
            from glitchygames.tools.visual_collision_manager import LocationType

            self.visual_collision_manager.add_controller_indicator(
                controller_id,
                controller_info.instance_id,
                controller_info.color,
                position.position,
                LocationType.CANVAS,
            )

    def _get_current_color(self) -> tuple[int, ...]:
        """Get the current color from the color picker.

        Returns:
            tuple: The current color.

        """
        # Get color from sliders if available
        if (
            hasattr(self, 'red_slider')
            and hasattr(self, 'green_slider')
            and hasattr(self, 'blue_slider')
        ):
            try:
                red = int(self.red_slider.value)
                green = int(self.green_slider.value)
                blue = int(self.blue_slider.value)
                self.log.debug(
                    f'DEBUG: _get_current_color() returning color from sliders: ({red}, {green},'
                    f' {blue})'
                )
                return (red, green, blue)
            except (ValueError, AttributeError) as e:
                self.log.debug(f'DEBUG: _get_current_color() error getting slider values: {e}')

        # Default to white if sliders not available
        self.log.debug('DEBUG: _get_current_color() sliders not available, returning white')
        return (255, 255, 255)

    # Slider Mode Implementation Methods
    def _update_color_well_from_sliders(self) -> None:
        """Update the color well with current slider values."""
        self.log.debug('DEBUG: _update_color_well_from_sliders called')
        if hasattr(self, 'color_well') and self.color_well:
            # Get current slider values
            red_value = self.red_slider.value if hasattr(self, 'red_slider') else 0
            green_value = self.green_slider.value if hasattr(self, 'green_slider') else 0
            blue_value = self.blue_slider.value if hasattr(self, 'blue_slider') else 0
            alpha_value = self.alpha_slider.value if hasattr(self, 'alpha_slider') else 0

            self.log.debug(
                f'DEBUG: Slider values - R:{red_value}, G:{green_value}, B:{blue_value},'
                f' A:{alpha_value}'
            )
            self.log.debug(f'DEBUG: Color well before update: {self.color_well.active_color}')

            # Update color well
            self.color_well.active_color = (red_value, green_value, blue_value, alpha_value)

            # Force color well to redraw
            if hasattr(self.color_well, 'dirty'):
                self.color_well.dirty = 1

            # Also dirty the main scene to ensure redraw
            self.dirty = 1

            # Force color well to update its display
            if hasattr(self.color_well, 'force_redraw'):
                self.color_well.force_redraw()  # type: ignore[union-attr]

            self.log.debug(
                f'DEBUG: Updated color well to ({red_value}, {green_value}, {blue_value})'
            )
        else:
            self.log.debug('DEBUG: No color_well found or color_well is None')

    def _handle_slider_mode_navigation(
        self, direction: str, controller_id: int | None = None
    ) -> None:
        """Handle arrow key navigation between slider modes."""
        if not hasattr(self, 'mode_switcher'):
            return

        # If no specific controller provided, find the first controller in slider mode (for keyboard
        # navigation)
        if controller_id is None:
            target_controller_id = None
            for cid in self.mode_switcher.controller_modes:
                controller_mode = self.mode_switcher.get_controller_mode(cid)
                if controller_mode and controller_mode.value in {
                    'r_slider',
                    'g_slider',
                    'b_slider',
                }:
                    target_controller_id = cid
                    break
        else:
            # Use the specific controller (for D-pad navigation)
            target_controller_id = controller_id

        if target_controller_id is None:
            return

        current_mode = self.mode_switcher.get_controller_mode(target_controller_id)
        if not current_mode:
            return

        # Define the slider mode cycle
        slider_cycle = [ControllerMode.R_SLIDER, ControllerMode.G_SLIDER, ControllerMode.B_SLIDER]

        # Find current position in cycle
        if current_mode not in slider_cycle:
            return

        current_index = slider_cycle.index(current_mode)

        # Calculate new index based on direction
        if direction == 'up':
            # B -> G -> R
            new_index = (current_index - 1) % len(slider_cycle)
        else:  # direction == "down"
            # R -> G -> B
            new_index = (current_index + 1) % len(slider_cycle)

        new_mode = slider_cycle[new_index]

        # Switch to new mode
        current_time = time.time()
        self.mode_switcher.controller_modes[target_controller_id].switch_to_mode(
            new_mode, current_time
        )

        self.log.debug(
            f'DEBUG: Slider mode navigation - switched controller {target_controller_id} from'
            f' {current_mode.value} to {new_mode.value}'
        )
        self.log.debug(
            f'Slider mode navigation - switched controller {target_controller_id} from'
            f' {current_mode.value} to {new_mode.value}'
        )

    def _slider_adjust_value(self, controller_id: int, delta: int) -> None:
        """Adjust the current slider's value."""
        self.log.debug(
            f'DEBUG: _slider_adjust_value called for controller {controller_id}, delta {delta}'
        )

        # Get the controller's current mode to determine which slider
        if hasattr(self, 'mode_switcher'):
            controller_mode = self.mode_switcher.get_controller_mode(controller_id)
            self.log.debug(
                f'DEBUG: Controller {controller_id} mode:'
                f' {controller_mode.value if controller_mode else "None"}'
            )

            # Adjust the appropriate slider based on mode
            if controller_mode and controller_mode.value == 'r_slider':
                old_value = self.red_slider.value
                new_value = max(0, min(255, old_value + delta))
                self.log.debug(f'DEBUG: R slider: {old_value} -> {new_value}')
                # Update the slider value
                self.red_slider.value = new_value
                # Create a trigger event to properly update the color well
                trigger = events.HashableEvent(0, name='R', value=new_value)
                self.on_slider_event(events.HashableEvent(0), trigger)
                self.log.debug(f'DEBUG: Adjusted R slider to {new_value}')
            elif controller_mode and controller_mode.value == 'g_slider':
                old_value = self.green_slider.value
                new_value = max(0, min(255, old_value + delta))
                self.log.debug(f'DEBUG: G slider: {old_value} -> {new_value}')
                # Update the slider value
                self.green_slider.value = new_value
                # Create a trigger event to properly update the color well
                trigger = events.HashableEvent(0, name='G', value=new_value)
                self.on_slider_event(events.HashableEvent(0), trigger)
                self.log.debug(f'DEBUG: Adjusted G slider to {new_value}')
            elif controller_mode and controller_mode.value == 'b_slider':
                old_value = self.blue_slider.value
                new_value = max(0, min(255, old_value + delta))
                self.log.debug(f'DEBUG: B slider: {old_value} -> {new_value}')
                # Update the slider value
                self.blue_slider.value = new_value
                # Create a trigger event to properly update the color well
                trigger = events.HashableEvent(0, name='B', value=new_value)
                self.on_slider_event(events.HashableEvent(0), trigger)
                self.log.debug(f'DEBUG: Adjusted B slider to {new_value}')
            else:
                self.log.debug(
                    'DEBUG: No matching slider mode for'
                    f' {controller_mode.value if controller_mode else "None"}'
                )
        else:
            self.log.debug('DEBUG: No mode_switcher found')

    def _start_slider_continuous_adjustment(self, controller_id: int, direction: int) -> None:
        """Start continuous slider adjustment with acceleration."""
        if not hasattr(self, 'slider_continuous_adjustments'):
            self.slider_continuous_adjustments: dict[int, dict[str, Any]] = {}

        # Do the first tick immediately for responsive feel
        self._slider_adjust_value(controller_id, direction)

        # Initialize continuous adjustment for this controller
        # Set last_adjustment to current time so the next adjustment waits for the full interval
        current_time = time.time()
        self.slider_continuous_adjustments[controller_id] = {
            'direction': direction,
            'start_time': current_time,
            'last_adjustment': current_time,
            'acceleration_level': 0,
        }
        self.log.debug(
            f'DEBUG: Started continuous slider adjustment for controller {controller_id}, direction'
            f' {direction} (immediate first tick)'
        )

    def _stop_slider_continuous_adjustment(self, controller_id: int) -> None:
        """Stop continuous slider adjustment."""
        if (
            hasattr(self, 'slider_continuous_adjustments')
            and controller_id in self.slider_continuous_adjustments
        ):
            del self.slider_continuous_adjustments[controller_id]
            self.log.debug(
                f'DEBUG: Stopped continuous slider adjustment for controller {controller_id}'
            )

    def _update_slider_continuous_adjustments(self) -> None:
        """Update continuous slider adjustments with acceleration."""
        if not hasattr(self, 'slider_continuous_adjustments'):
            return

        current_time = time.time()

        for controller_id, adjustment_data in list(self.slider_continuous_adjustments.items()):
            # Calculate time since start and since last adjustment
            time_since_start = current_time - adjustment_data['start_time']
            time_since_last = current_time - adjustment_data['last_adjustment']

            # Calculate acceleration level (0-3)
            # 0-0.8s: level 0 (1 tick per 0.15s) - longer delay for precision
            # 0.8-1.5s: level 1 (2 ticks per 0.1s)
            # 1.5-2.5s: level 2 (4 ticks per 0.05s)
            # 2.5s+: level 3 (8 ticks per 0.025s)
            if time_since_start < CONTROLLER_ACCEL_LEVEL1_TIME:
                acceleration_level = 0
                interval = 0.15  # ~6.7 ticks per second
            elif time_since_start < CONTROLLER_ACCEL_LEVEL2_TIME:
                acceleration_level = 1
                interval = 0.1  # 10 ticks per second
            elif time_since_start < CONTROLLER_ACCEL_LEVEL3_TIME:
                acceleration_level = 2
                interval = 0.05  # 20 ticks per second
            else:
                acceleration_level = 3
                interval = 0.025  # 40 ticks per second

            # Update acceleration level if changed
            if acceleration_level != adjustment_data['acceleration_level']:
                adjustment_data['acceleration_level'] = acceleration_level
                self.log.debug(
                    f'DEBUG: Controller {controller_id} slider acceleration level'
                    f' {acceleration_level}'
                )

            # Check if enough time has passed for next adjustment
            if time_since_last >= interval:
                # Calculate delta based on acceleration level (1, 2, 4, 8)
                delta = adjustment_data['direction'] * (2**acceleration_level)
                delta = max(-8, min(8, delta))  # Cap at ±8

                # Apply the adjustment
                self._slider_adjust_value(controller_id, delta)

                # Update color well during continuous adjustment
                controller_mode = self.mode_switcher.get_controller_mode(controller_id)
                self.log.debug(
                    f'DEBUG: Continuous adjustment - controller {controller_id} mode:'
                    f' {controller_mode.value if controller_mode else "None"}'
                )
                if controller_mode and controller_mode.value in {
                    'r_slider',
                    'g_slider',
                    'b_slider',
                }:
                    self.log.debug(
                        'DEBUG: Calling _update_color_well_from_sliders during continuous '
                        'adjustment'
                    )
                    self._update_color_well_from_sliders()
                else:
                    self.log.debug('DEBUG: Not updating color well - controller not in slider mode')

                # Update last adjustment time
                adjustment_data['last_adjustment'] = current_time

    def _start_canvas_continuous_movement(self, controller_id: int, dx: int, dy: int) -> None:
        """Start continuous canvas movement with acceleration."""
        if not hasattr(self, 'canvas_continuous_movements'):
            self.canvas_continuous_movements: dict[int, dict[str, Any]] = {}

        # Do the first movement immediately for responsive feel
        self._canvas_move_cursor(controller_id, dx, dy)

        # Get starting position for undo/redo tracking
        start_position = self.mode_switcher.get_controller_position(controller_id)
        start_x, start_y = start_position.position if start_position else (0, 0)

        # Initialize continuous movement for this controller
        current_time = time.time()
        self.canvas_continuous_movements[controller_id] = {
            'dx': dx,
            'dy': dy,
            'start_time': current_time,
            'last_movement': current_time,
            'acceleration_level': 0,
            'start_x': start_x,
            'start_y': start_y,
        }
        self.log.debug(
            f'DEBUG: Started continuous canvas movement for controller {controller_id}, direction'
            f' ({dx}, {dy}) (immediate first movement)'
        )

    def _stop_canvas_continuous_movement(self, controller_id: int) -> None:
        """Stop continuous canvas movement."""
        if (
            hasattr(self, 'canvas_continuous_movements')
            and controller_id in self.canvas_continuous_movements
        ):
            # Track the final position change for undo/redo
            if hasattr(self, 'controller_position_operation_tracker'):
                # Get the starting position from the movement data
                movement_data = self.canvas_continuous_movements[controller_id]
                start_position = (movement_data.get('start_x', 0), movement_data.get('start_y', 0))

                # Get current position
                current_position = self.mode_switcher.get_controller_position(controller_id)
                current_pos = current_position.position if current_position else (0, 0)

                # Only track if position actually changed
                if start_position != current_pos:
                    current_mode = self.mode_switcher.get_controller_mode(controller_id)
                    mode_str = current_mode.value if current_mode else None

                    self.controller_position_operation_tracker.add_controller_position_change(
                        controller_id, start_position, current_pos, mode_str, mode_str
                    )

            del self.canvas_continuous_movements[controller_id]
            self.log.debug(
                f'DEBUG: Stopped continuous canvas movement for controller {controller_id}'
            )

    def _update_canvas_continuous_movements(self) -> None:
        """Update continuous canvas movements with acceleration."""
        if not hasattr(self, 'canvas_continuous_movements'):
            return

        current_time = time.time()

        for controller_id, movement_data in list(self.canvas_continuous_movements.items()):
            # Calculate time since start and since last movement
            time_since_start = current_time - movement_data['start_time']
            time_since_last = current_time - movement_data['last_movement']

            # Calculate acceleration level (same as sliders)
            if time_since_start < CONTROLLER_ACCEL_LEVEL1_TIME:
                acceleration_level = 0
                interval = 0.15  # ~6.7 movements per second
            elif time_since_start < CONTROLLER_ACCEL_LEVEL2_TIME:
                acceleration_level = 1
                interval = 0.1  # 10 movements per second
            elif time_since_start < CONTROLLER_ACCEL_LEVEL3_TIME:
                acceleration_level = 2
                interval = 0.05  # 20 movements per second
            else:
                acceleration_level = 3
                interval = 0.025  # 40 movements per second

            # Update acceleration level if changed
            if acceleration_level != movement_data['acceleration_level']:
                movement_data['acceleration_level'] = acceleration_level
                self.log.debug(
                    f'DEBUG: Controller {controller_id} canvas movement acceleration level'
                    f' {acceleration_level}'
                )

            # Check if enough time has passed for next movement
            if time_since_last >= interval:
                # Calculate movement delta based on acceleration level (1, 2, 4, 8)
                dx = movement_data['dx'] * (2**acceleration_level)
                dy = movement_data['dy'] * (2**acceleration_level)
                dx = max(-8, min(8, dx))  # Cap at ±8
                dy = max(-8, min(8, dy))  # Cap at ±8

                # Apply the movement
                self._canvas_move_cursor(controller_id, dx, dy)

                # If this controller has an active drag operation, paint at the new position
                if (
                    hasattr(self, 'controller_drags')
                    and controller_id in self.controller_drags
                    and self.controller_drags[controller_id]['active']
                ):
                    self._canvas_paint_at_controller_position(controller_id)

                # Update last movement time
                movement_data['last_movement'] = current_time

    def _canvas_paint_horizontal_line(self, controller_id: int, distance: int) -> None:
        """Paint a horizontal line of pixels starting from the controller's current position."""
        self.log.debug(
            f'DEBUG: _canvas_paint_horizontal_line called for controller {controller_id}, distance'
            f' {distance}'
        )

        # Get controller position from mode switcher
        position = self.mode_switcher.get_controller_position(controller_id)
        if not position or not position.is_valid:
            self.log.debug(f'DEBUG: No valid position found for controller {controller_id}')
            return

        start_x, start_y = position.position
        current_color = self._get_current_color()

        self.log.debug(
            f'DEBUG: Painting horizontal line from ({start_x}, {start_y}) with distance {distance},'
            f' color {current_color}'
        )

        canvas_width, canvas_height = self._get_canvas_dimensions()
        self.log.debug(f'DEBUG: Canvas dimensions: {canvas_width}x{canvas_height}')

        # Paint pixels in a horizontal line
        for i in range(abs(distance)):
            pixel_x = start_x + i if distance > 0 else start_x - i
            pixel_y = start_y

            # Clamp coordinates to canvas bounds
            if canvas_width > 0:
                pixel_x = max(0, min(pixel_x, canvas_width - 1))
            if canvas_height > 0:
                pixel_y = max(0, min(pixel_y, canvas_height - 1))

            self._paint_and_track_pixel(controller_id, pixel_x, pixel_y, current_color)

        # Force canvas redraw
        if hasattr(self, 'canvas') and self.canvas:
            self.canvas.force_redraw()

        # Update controller position to the end of the line (clamped to canvas bounds)
        end_x = start_x + distance
        if canvas_width > 0:
            end_x = max(0, min(end_x, canvas_width - 1))
        if canvas_height > 0:
            start_y = max(0, min(start_y, canvas_height - 1))

        self.mode_switcher.save_controller_position(controller_id, (end_x, start_y))
        self.log.debug(
            f'DEBUG: Updated controller {controller_id} position to ({end_x}, {start_y}) (clamped'
            f' to canvas bounds)'
        )

    def _canvas_paint_vertical_line(self, controller_id: int, distance: int) -> None:
        """Paint a vertical line of pixels starting from the controller's current position."""
        self.log.debug(
            f'DEBUG: _canvas_paint_vertical_line called for controller {controller_id}, distance'
            f' {distance}'
        )

        # Get controller position from mode switcher
        position = self.mode_switcher.get_controller_position(controller_id)
        if not position or not position.is_valid:
            self.log.debug(f'DEBUG: No valid position found for controller {controller_id}')
            return

        start_x, start_y = position.position
        current_color = self._get_current_color()

        self.log.debug(
            f'DEBUG: Painting vertical line from ({start_x}, {start_y}) with distance {distance},'
            f' color {current_color}'
        )

        canvas_width, canvas_height = self._get_canvas_dimensions()
        self.log.debug(f'DEBUG: Canvas dimensions: {canvas_width}x{canvas_height}')

        # Paint pixels in a vertical line
        for i in range(abs(distance)):
            pixel_y = start_y + i if distance > 0 else start_y - i
            pixel_x = start_x

            # Clamp coordinates to canvas bounds
            if canvas_width > 0:
                pixel_x = max(0, min(pixel_x, canvas_width - 1))
            if canvas_height > 0:
                pixel_y = max(0, min(pixel_y, canvas_height - 1))

            self._paint_and_track_pixel(controller_id, pixel_x, pixel_y, current_color)

        # Force canvas redraw
        if hasattr(self, 'canvas') and self.canvas:
            self.canvas.force_redraw()

        # Update controller position to the end of the line (clamped to canvas bounds)
        end_y = start_y + distance
        if canvas_width > 0:
            start_x = max(0, min(start_x, canvas_width - 1))
        if canvas_height > 0:
            end_y = max(0, min(end_y, canvas_height - 1))

        self.mode_switcher.save_controller_position(controller_id, (start_x, end_y))
        self.log.debug(
            f'DEBUG: Updated controller {controller_id} position to ({start_x}, {end_y}) (clamped'
            f' to canvas bounds)'
        )

    def _get_canvas_dimensions(self) -> tuple[int, int]:
        """Get the canvas dimensions.

        Returns:
            Tuple of (width, height), or (0, 0) if no canvas is available.

        """
        if hasattr(self, 'canvas') and self.canvas:
            return (
                getattr(self.canvas, 'pixels_across', 0),
                getattr(self.canvas, 'pixels_tall', 0),
            )
        return (0, 0)

    def _paint_and_track_pixel(
        self, controller_id: int, pixel_x: int, pixel_y: int, current_color: tuple[int, ...]
    ) -> None:
        """Paint a pixel and track it in the controller drag operation.

        Args:
            controller_id: The controller ID.
            pixel_x: X coordinate.
            pixel_y: Y coordinate.
            current_color: The color to paint.

        """
        old_color = self._get_canvas_pixel_color(pixel_x, pixel_y)
        if old_color is None:
            old_color = (0, 0, 0)

        if hasattr(self, 'canvas') and self.canvas and hasattr(self.canvas, 'canvas_interface'):
            self.canvas.canvas_interface.set_pixel_at(pixel_x, pixel_y, current_color)  # type: ignore[arg-type]
            self.log.debug(
                f'DEBUG: Painted pixel at ({pixel_x}, {pixel_y}) with color {current_color}'
            )
            self._track_controller_drag_pixel(
                controller_id, (pixel_x, pixel_y), current_color, old_color
            )
        else:
            self.log.debug('DEBUG: No canvas or canvas_interface available')

    def _is_controller_button_held(self, controller_id: int, button: int) -> bool:
        """Check if a controller button is currently held down.

        Returns:
            bool: True if the condition is met, False otherwise.

        """
        try:
            # Get the controller instance
            controller = pygame.joystick.Joystick(controller_id)
            return controller.get_button(button)
        except (pygame.error, ValueError):
            return False

    def _canvas_jump_horizontal(self, controller_id: int, distance: int) -> None:
        """Jump horizontally without painting pixels."""
        self.log.debug(
            f'DEBUG: _canvas_jump_horizontal called for controller {controller_id}, distance'
            f' {distance}'
        )

        # Get controller position from mode switcher
        position = self.mode_switcher.get_controller_position(controller_id)
        if not position or not position.is_valid:
            self.log.debug(f'DEBUG: No valid position found for controller {controller_id}')
            return

        start_x, start_y = position.position

        # Get canvas dimensions for boundary checking
        canvas_width = 0
        if hasattr(self, 'canvas') and self.canvas:
            canvas_width = getattr(self.canvas, 'pixels_across', 0)

        # Calculate new position
        end_x = start_x + distance

        # Clamp to canvas bounds
        if canvas_width > 0:
            end_x = max(0, min(end_x, canvas_width - 1))

        # Update controller position
        self.mode_switcher.save_controller_position(controller_id, (end_x, start_y))
        self.log.debug(
            f'DEBUG: Controller {controller_id} jumped from ({start_x}, {start_y}) to ({end_x},'
            f' {start_y})'
        )

    def _canvas_jump_vertical(self, controller_id: int, distance: int) -> None:
        """Jump vertically without painting pixels."""
        self.log.debug(
            f'DEBUG: _canvas_jump_vertical called for controller {controller_id}, distance'
            f' {distance}'
        )

        # Get controller position from mode switcher
        position = self.mode_switcher.get_controller_position(controller_id)
        if not position or not position.is_valid:
            self.log.debug(f'DEBUG: No valid position found for controller {controller_id}')
            return

        start_x, start_y = position.position

        # Get canvas dimensions for boundary checking
        canvas_height = 0
        if hasattr(self, 'canvas') and self.canvas:
            canvas_height = getattr(self.canvas, 'pixels_tall', 0)

        # Calculate new position
        end_y = start_y + distance

        # Clamp to canvas bounds
        if canvas_height > 0:
            end_y = max(0, min(end_y, canvas_height - 1))

        # Update controller position
        self.mode_switcher.save_controller_position(controller_id, (start_x, end_y))
        self.log.debug(
            f'DEBUG: Controller {controller_id} jumped from ({start_x}, {start_y}) to ({start_x},'
            f' {end_y})'
        )

    def _slider_previous(self, controller_id: int) -> None:
        """Move to the previous slider (now handled by L2/R2 mode switching)."""
        self.log.debug(f'DEBUG: Controller {controller_id} moved to previous slider')
        # This is now handled by L2/R2 mode switching, so this is just for D-pad compatibility

    def _slider_next(self, controller_id: int) -> None:
        """Move to the next slider (now handled by L2/R2 mode switching)."""
        self.log.debug(f'DEBUG: Controller {controller_id} moved to next slider')
        # This is now handled by L2/R2 mode switching, so this is just for D-pad compatibility

    @override
    def on_joy_button_down_event(self, event: events.HashableEvent) -> None:
        """Handle joystick button down events (for controllers detected as joysticks).

        Args:
            event (pygame.event.Event): The joystick button down event.

        """
        # print(f"DEBUG: Joystick button down event received: button={event.button}")
        # print(f"DEBUG: Joystick instance_id: {getattr(event, 'instance_id', 'N/A')}")
        # print(f"DEBUG: Joystick joy: {getattr(event, 'joy', 'N/A')}")
        # print(f"DEBUG: This could be the source of the reset behavior!")
        # LOG.debug(f"Joystick button down: {event.button}")

        # Map joystick buttons to controller actions
        # Button 9 is likely LEFT SHOULDER button, not START
        if event.button == JOYSTICK_LEFT_SHOULDER_BUTTON:  # LEFT SHOULDER button
            # print("DEBUG: Joystick LEFT SHOULDER button pressed - UNHANDLED")
            # Left shoulder button: Currently unhandled to prevent reset behavior
            # controller_id = getattr(event, 'instance_id', 0)
            # self._multi_controller_activate(controller_id)
            pass
        elif event.button == 0:  # A button
            # print("DEBUG: Joystick A button pressed - selecting current frame with
            # multi-controller system")
            # Use new multi-controller system instead of old single-controller system
            controller_id = getattr(event, 'instance_id', 0)
            self._multi_controller_select_current_frame(controller_id)
        elif event.button == 1:  # B button
            # print("DEBUG: Joystick B button pressed - cancel")
            self._controller_cancel()
        else:
            # Unknown joystick button - this might be the shoulder button!
            # print(f"DEBUG: Joystick UNKNOWN button {event.button} pressed - UNHANDLED")
            # print(f"DEBUG: This could be the left shoulder button causing the reset!")
            # LOG.debug(f"Joystick unknown button: {event.button}")
            pass

    @override
    def on_joy_button_up_event(self, event: events.HashableEvent) -> None:
        """Handle joystick button up events.

        Args:
            event (pygame.event.Event): The joystick button up event.

        """
        # print(f"DEBUG: Joystick button up event received: button={event.button}")
        # LOG.debug(f"Joystick button up: {event.button}")

    @override
    def on_joy_hat_motion_event(self, event: events.HashableEvent) -> None:  # type: ignore[override]
        """Handle joystick hat motion events - requires threshold to prevent jittery behavior.

        Args:
            event (pygame.event.Event): The joystick hat motion event.

        """
        self.log.debug(f'DEBUG: Joystick hat motion: hat={event.hat}, value={event.value}')

        # Only respond to strong hat inputs (threshold > 0.5)
        # Hat values can be either:
        # - Integer bitmask: 0=center, 1=up, 2=right, 4=down, 8=left, etc.
        # - Tuple (x, y): (0,0)=center, (0,1)=up, (1,0)=right, (0,-1)=down, (-1,0)=left
        if isinstance(event.value, tuple):
            # For tuple, calculate magnitude
            hat_magnitude: float = (event.value[0] ** 2 + event.value[1] ** 2) ** 0.5  # type: ignore[index]
            if hat_magnitude < HAT_INPUT_MAGNITUDE_THRESHOLD:
                LOG.debug('DEBUG: Joystick hat motion below threshold, ignoring')
                return
        # For integer bitmask, use abs
        elif abs(event.value) < HAT_INPUT_MAGNITUDE_THRESHOLD:
            LOG.debug('DEBUG: Joystick hat motion below threshold, ignoring')
            return

        # Map hat directions to controller actions
        if event.value == 1:  # type: ignore[comparison-overlap]  # Up
            LOG.debug('DEBUG: Joystick hat up - DISABLED (use multi-controller system)')
            # OLD SYSTEM DISABLED - Use multi-controller system instead
            return
        if event.value == JOYSTICK_HAT_RIGHT:  # type: ignore[comparison-overlap]  # Right
            LOG.debug('DEBUG: Joystick hat right - DISABLED (use multi-controller system)')
            # OLD SYSTEM DISABLED - Use multi-controller system instead
            return
        if event.value == JOYSTICK_HAT_DOWN:  # type: ignore[comparison-overlap]  # Down
            LOG.debug('DEBUG: Joystick hat down - DISABLED (use multi-controller system)')
            # OLD SYSTEM DISABLED - Use multi-controller system instead
            return
        if event.value == JOYSTICK_HAT_LEFT:  # type: ignore[comparison-overlap]  # Left
            LOG.debug('DEBUG: Joystick hat left - DISABLED (use multi-controller system)')
            # OLD SYSTEM DISABLED - Use multi-controller system instead
            return

    @override
    def on_joy_axis_motion_event(self, event: events.HashableEvent) -> None:  # type: ignore[override]
        """Handle joystick axis motion events - disabled to prevent jittery behavior.

        Args:
            event (pygame.event.Event): The joystick axis motion event.

        """
        # Handle trigger axis motion for mode switching (axes 4 and 5)
        if event.axis in {4, 5}:  # TRIGGERLEFT and TRIGGERRIGHT
            self.log.debug(
                f'DEBUG: Trigger axis motion detected: axis={event.axis}, value={event.value}'
            )
            self._handle_trigger_axis_motion(event)
            return

        self.log.debug(
            f'DEBUG: Joystick axis motion (DISABLED): axis={event.axis}, value={event.value}'
        )
        # Disabled to prevent jittery behavior

    @override
    def on_joy_ball_motion_event(self, event: events.HashableEvent) -> None:  # type: ignore[override]
        """Handle joystick ball motion events - disabled to prevent jittery behavior.

        Args:
            event (pygame.event.Event): The joystick ball motion event.

        """
        self.log.debug(
            f'DEBUG: Joystick ball motion (DISABLED): ball={event.ball}, rel={event.rel}'
        )
        # Disabled to prevent jittery behavior

    @override
    def on_controller_axis_motion_event(self, event: events.HashableEvent) -> None:  # type: ignore[override]
        """Handle controller axis motion events.

        Args:
            event (pygame.event.Event): The controller axis motion event.

        """
        # Handle trigger axis motion for mode switching
        if event.axis in {pygame.CONTROLLER_AXIS_TRIGGERLEFT, pygame.CONTROLLER_AXIS_TRIGGERRIGHT}:
            self._handle_trigger_axis_motion(event)
            return

        # Stick axis motion disabled to prevent jittery behavior.
        # Re-enable by calling self._handle_stick_axis_motion(event) here.
        return

    def _handle_stick_axis_motion(self, event: events.HashableEvent) -> None:
        """Handle stick axis motion events (currently disabled).

        Args:
            event (pygame.event.Event): The controller axis motion event.

        """
        self.log.debug(f'DEBUG: Controller axis motion: axis={event.axis}, value={event.value}')
        self.log.debug(f'DEBUG: LEFT_X axis constant: {pygame.CONTROLLER_AXIS_LEFTX}')
        self.log.debug(f'DEBUG: LEFT_Y axis constant: {pygame.CONTROLLER_AXIS_LEFTY}')
        self.log.debug(f'DEBUG: RIGHT_X axis constant: {pygame.CONTROLLER_AXIS_RIGHTX}')
        self.log.debug(f'DEBUG: RIGHT_Y axis constant: {pygame.CONTROLLER_AXIS_RIGHTY}')
        self.log.debug(
            'DEBUG: Controller selection active:'
            f' {getattr(self, "controller_selection_active", False)}'
        )

        # Left stick for fine frame navigation (only if controller selection is active)
        if not hasattr(self, 'controller_selection_active') or not self.controller_selection_active:  # type: ignore[attr-defined]
            LOG.debug('DEBUG: Controller selection not active, ignoring analog stick input')
            return

        import time

        current_time = time.time()

        if event.axis == pygame.CONTROLLER_AXIS_LEFTX:
            self._handle_left_stick_x_axis(event, current_time)
        elif event.axis == pygame.CONTROLLER_AXIS_LEFTY:
            self._handle_left_stick_y_axis(event, current_time)

    def _handle_left_stick_x_axis(self, event: events.HashableEvent, current_time: float) -> None:
        """Handle left stick X axis motion.

        Args:
            event: The axis motion event.
            current_time: Current timestamp.

        """
        if not self._check_axis_deadzone_and_cooldown(event, current_time):
            return

        if event.value < -self._controller_axis_hat_threshold:
            LOG.debug('DEBUG: Left stick left - DISABLED (use multi-controller system)')
            return
        if event.value > self._controller_axis_hat_threshold:
            LOG.debug('DEBUG: Left stick right - DISABLED (use multi-controller system)')
            return

        self._controller_axis_last_values[event.axis] = event.value

    def _handle_left_stick_y_axis(self, event: events.HashableEvent, current_time: float) -> None:
        """Handle left stick Y axis motion.

        Args:
            event: The axis motion event.
            current_time: Current timestamp.

        """
        if not self._check_axis_deadzone_and_cooldown(event, current_time):
            return

        if event.value < -self._controller_axis_hat_threshold:
            LOG.debug('DEBUG: Left stick up - DISABLED (use multi-controller system)')
            return
        if event.value > self._controller_axis_hat_threshold:
            LOG.debug('DEBUG: Left stick down - DISABLED (use multi-controller system)')
            return

        self._controller_axis_last_values[event.axis] = event.value

    def _check_axis_deadzone_and_cooldown(
        self, event: events.HashableEvent, current_time: float
    ) -> bool:
        """Check deadzone, cooldown, and direction change for an axis event.

        Args:
            event: The axis motion event.
            current_time: Current timestamp.

        Returns:
            True if the event should be processed, False if it should be ignored.

        """
        # Apply deadzone
        if abs(event.value) < self._controller_axis_deadzone:
            self._controller_axis_cooldown[event.axis] = 0
            self._controller_axis_last_values[event.axis] = 0
            return False

        # Check cooldown
        if (
            event.axis in self._controller_axis_cooldown
            and current_time - self._controller_axis_cooldown[event.axis]
            < self._controller_axis_cooldown_duration
        ):
            return False

        # Check if direction changed (prevents rapid back-and-forth)
        last_value = self._controller_axis_last_values.get(event.axis, 0)
        if (last_value < 0 and event.value > 0) or (last_value > 0 and event.value < 0):
            self._controller_axis_cooldown[event.axis] = current_time
            self._controller_axis_last_values[event.axis] = event.value
            return False

        return True

    def _handle_trigger_axis_motion(self, event: events.HashableEvent) -> None:
        """Handle trigger axis motion for mode switching.

        Args:
            event (pygame.event.Event): The controller/joystick axis motion event.

        """
        controller_id = self._get_controller_id_from_event(event)
        if controller_id is None:
            self.log.debug('DEBUG: No controller ID found for event')
            return

        # Register controller with mode switcher if not already registered
        if controller_id not in self.mode_switcher.controller_modes:
            from glitchygames.tools.controller_mode_system import ControllerMode

            self.mode_switcher.register_controller(controller_id, ControllerMode.FILM_STRIP)
            self.log.debug(f'DEBUG: Registered controller {controller_id} with mode switcher')

        import time

        current_time = time.time()

        l2_value, r2_value = self._read_trigger_values(event, controller_id)

        # Handle mode switching
        new_mode = self.mode_switcher.handle_trigger_input(
            controller_id, l2_value, r2_value, current_time
        )

        if new_mode:
            self.log.debug(f'DEBUG: Controller {controller_id} switched to mode: {new_mode.value}')
            self._track_controller_mode_change(controller_id, new_mode)
            self._update_controller_visual_indicator_for_mode(controller_id, new_mode)
        else:
            self.log.debug(
                f'DEBUG: No mode switch for controller {controller_id} - L2: {l2_value:.2f}, R2:'
                f' {r2_value:.2f}'
            )

    def _get_controller_id_from_event(self, event: events.HashableEvent) -> int | None:
        """Extract the controller ID from a controller or joystick event.

        Args:
            event: The pygame event.

        Returns:
            The controller ID, or None if not found.

        """
        if hasattr(event, 'instance_id') and event.instance_id is not None:
            instance_id = event.instance_id
            controller_id = self.multi_controller_manager.get_controller_id(instance_id)
            self.log.debug(
                f'DEBUG: Controller event - instance_id={instance_id},'
                f' controller_id={controller_id}'
            )
            return controller_id

        # Joystick event - use device index directly
        device_index = event.joy
        self.log.debug(
            f'DEBUG: Joystick event - using device index {device_index} as controller ID'
            f' {device_index}'
        )
        return device_index

    def _read_trigger_values(
        self, event: events.HashableEvent, controller_id: int
    ) -> tuple[float, float]:
        """Read L2 and R2 trigger values from a controller or joystick event.

        Args:
            event: The pygame event.
            controller_id: The controller ID.

        Returns:
            Tuple of (l2_value, r2_value) normalized to 0.0..1.0 range.

        """
        if hasattr(event, 'instance_id'):
            return self._read_controller_trigger_values(event, controller_id)
        return self._read_joystick_trigger_values(event, controller_id)

    def _read_controller_trigger_values(
        self, event: events.HashableEvent, controller_id: int
    ) -> tuple[float, float]:
        """Read trigger values from a controller event.

        Args:
            event: The pygame controller event.
            controller_id: The controller ID.

        Returns:
            Tuple of (l2_value, r2_value) normalized to 0.0..1.0 range.

        """
        if not hasattr(self, 'multi_controller_manager'):
            return 0.0, 0.0

        controller_info = self.multi_controller_manager.get_controller_info(event.instance_id)
        self.log.debug(
            f'DEBUG: Controller info lookup - instance_id={event.instance_id},'
            f' controller_info={controller_info}'
        )
        if not controller_info:
            self.log.debug(f'DEBUG: No controller info found for instance_id={event.instance_id}')
            return 0.0, 0.0

        try:
            controller = pygame.joystick.Joystick(event.instance_id)
            # Convert pygame trigger values (-1.0 to 1.0) to our expected range (0.0 to 1.0)
            l2_raw = controller.get_axis(pygame.CONTROLLER_AXIS_TRIGGERLEFT)
            r2_raw = controller.get_axis(pygame.CONTROLLER_AXIS_TRIGGERRIGHT)
            l2_value = (l2_raw + 1.0) / 2.0
            r2_value = (r2_raw + 1.0) / 2.0
            self.log.debug(
                f'DEBUG: Controller {controller_id} triggers - L2: {l2_value:.2f}, R2:'
                f' {r2_value:.2f}'
            )
            return l2_value, r2_value
        except (pygame.error, OSError, AttributeError) as e:
            self.log.debug(
                f'DEBUG: Error getting controller object for instance_id={event.instance_id}: {e}'
            )
            return 0.0, 0.0

    def _read_joystick_trigger_values(
        self, event: events.HashableEvent, controller_id: int
    ) -> tuple[float, float]:
        """Read trigger values from a joystick event.

        Args:
            event: The pygame joystick event.
            controller_id: The controller ID.

        Returns:
            Tuple of (l2_value, r2_value) normalized to 0.0..1.0 range.

        """
        self.log.debug(
            f'DEBUG: Processing joystick event for controller {controller_id}, joy={event.joy}'
        )
        try:
            joystick = pygame.joystick.Joystick(event.joy)
            self.log.debug(f'DEBUG: Created joystick object for joy {event.joy}')
            l2_raw = joystick.get_axis(4)  # TRIGGERLEFT
            r2_raw = joystick.get_axis(5)  # TRIGGERRIGHT

            # Convert joystick raw values to 0.0..1.0 range
            # Joystick values are typically in the range -32768 to 32767
            # We need to normalize them to 0.0 to 1.0
            l2_value = max(0.0, min(1.0, (l2_raw + 32768.0) / 65535.0))
            r2_value = max(0.0, min(1.0, (r2_raw + 32768.0) / 65535.0))

            self.log.debug(
                f'DEBUG: Joystick {controller_id} raw values - L2: {l2_raw:.2f}, R2: {r2_raw:.2f}'
            )
            self.log.debug(
                f'DEBUG: Joystick {controller_id} triggers - L2: {l2_value:.2f}, R2: {r2_value:.2f}'
            )
            return l2_value, r2_value
        except (pygame.error, OSError, AttributeError) as e:
            self.log.debug(f'DEBUG: Error getting joystick trigger values: {e}')
            return 0.0, 0.0

    def _track_controller_mode_change(self, controller_id: int, new_mode: ControllerMode) -> None:
        """Track a controller mode change for undo/redo.

        Args:
            controller_id: The controller ID.
            new_mode: The new ControllerMode.

        """
        if getattr(self, '_applying_undo_redo', False):
            return
        if not hasattr(self, 'controller_position_operation_tracker'):
            return

        old_mode = self.mode_switcher.get_controller_mode(controller_id)
        if old_mode:
            self.controller_position_operation_tracker.add_controller_mode_change(
                controller_id, old_mode.value, new_mode.value
            )

    def _update_controller_visual_indicator_for_mode(
        self, controller_id: int, new_mode: ControllerMode
    ) -> None:
        """Update visual indicator for controller's new mode.

        Args:
            controller_id: Controller ID
            new_mode: New mode (ControllerMode enum)

        """
        self.log.debug(
            f'DEBUG: Updating visual indicator for controller {controller_id} to mode'
            f' {new_mode.value} (selected controller)'
        )

        # Get controller info
        controller_info = self.multi_controller_manager.get_controller_info(controller_id)
        if not controller_info:
            self.log.debug(f'DEBUG: No controller info found for controller {controller_id}')
            return

        # Get location type for new mode
        location_type = self.mode_switcher.get_controller_location_type(controller_id)
        if not location_type:
            self.log.debug(f'DEBUG: No location type found for controller {controller_id}')
            return

        self.log.debug(f'DEBUG: Location type for controller {controller_id}: {location_type}')

        position = self._get_controller_mode_position(controller_id, new_mode)

        self._update_visual_collision_indicator(
            controller_id, controller_info, position, location_type
        )
        self._mark_dirty_for_mode_change(controller_id, location_type)  # type: ignore[arg-type]

    def _get_controller_mode_position(
        self, controller_id: int, new_mode: ControllerMode
    ) -> tuple[int, int]:
        """Get the position for a controller in its new mode.

        Args:
            controller_id: Controller ID.
            new_mode: New mode (ControllerMode enum).

        Returns:
            The (x, y) position tuple.

        """
        position_data = self.mode_switcher.get_controller_position(controller_id)
        if position_data and position_data.is_valid:
            self.log.debug(
                f'DEBUG: Using saved position for controller {controller_id}:'
                f' {position_data.position}'
            )
            return position_data.position

        # Default position based on mode
        if new_mode.value == 'canvas':
            position = (0, 0)  # Start at top-left of canvas
        elif new_mode.value in {'r_slider', 'g_slider', 'b_slider'}:
            position = (0, 0)  # Start at top of slider
        else:  # film_strip
            position = (100, 100)  # Default position
        self.log.debug(f'DEBUG: Using default position for controller {controller_id}: {position}')
        return position

    def _update_visual_collision_indicator(
        self,
        controller_id: int,
        controller_info: Any,
        position: tuple[int, int],
        location_type: Any,
    ) -> None:
        """Update the visual collision manager indicator for a controller.

        Args:
            controller_id: Controller ID.
            controller_info: Controller info object with instance_id and color.
            position: The (x, y) position.
            location_type: The LocationType for the indicator.

        """
        if not hasattr(self, 'visual_collision_manager'):
            self.log.debug('DEBUG: No visual_collision_manager found')
            return

        self.log.debug(
            f'DEBUG: Adding new indicator for controller {controller_id} at {position} with'
            f' location type {location_type}'
        )
        # Remove any existing indicator for this controller first
        self.visual_collision_manager.remove_controller_indicator(controller_id)
        # Add new indicator for the new mode
        self.visual_collision_manager.add_controller_indicator(
            controller_id,
            controller_info.instance_id,
            controller_info.color,
            position,
            location_type,
        )
        self.log.debug(
            f'DEBUG: Updated visual indicator for controller {controller_id} at {position}'
        )

    def _mark_dirty_for_mode_change(self, controller_id: int, location_type: str) -> None:
        """Mark appropriate areas as dirty after a controller mode change.

        Args:
            controller_id: Controller ID.
            location_type: The LocationType for the new mode.

        """
        from glitchygames.tools.visual_collision_manager import LocationType

        if location_type == LocationType.CANVAS:
            if hasattr(self, 'canvas'):
                self.canvas.force_redraw()
                self.log.debug(f'DEBUG: Forced canvas redraw for controller {controller_id}')
        elif location_type == LocationType.SLIDER:
            if hasattr(self, 'red_slider'):
                self.red_slider.text_sprite.dirty = 2
            if hasattr(self, 'green_slider'):
                self.green_slider.text_sprite.dirty = 2
            if hasattr(self, 'blue_slider'):
                self.blue_slider.text_sprite.dirty = 2
            self.dirty = 1
            self.log.debug(
                f'DEBUG: Marked sliders and scene as dirty for controller {controller_id}'
            )
        elif location_type == LocationType.FILM_STRIP:
            if hasattr(self, 'film_strips'):
                for strip_widget in self.film_strips.values():
                    strip_widget.mark_dirty()
            self.log.debug(f'DEBUG: Marked film strips as dirty for controller {controller_id}')

        # Also mark film strips as dirty to ensure old triangles are removed
        # This is needed because film strips use controller_selections, not
        # VisualCollisionManager
        if hasattr(self, 'film_strips'):
            for strip_widget in self.film_strips.values():
                strip_widget.mark_dirty()
            self.log.debug('DEBUG: Marked film strips as dirty to remove old indicators')

        # Also force canvas redraw to ensure old canvas indicators are removed
        # This is needed because canvas visual indicators are drawn on the canvas surface
        if hasattr(self, 'canvas'):
            self.canvas.force_redraw()
            self.log.debug('DEBUG: Forced canvas redraw to remove old indicators')

    def _render_visual_indicators(self) -> None:
        """Render visual indicators for multi-controller system."""
        # Initialize controller selections if needed
        if not hasattr(self, 'controller_selections'):
            self.controller_selections = {}

        # Initialize mode switcher if needed
        if not hasattr(self, 'mode_switcher'):
            from glitchygames.tools.controller_mode_system import ModeSwitcher

            self.mode_switcher = ModeSwitcher()

        # Initialize multi-controller manager if needed
        if not hasattr(self, 'multi_controller_manager'):
            from glitchygames.tools.multi_controller_manager import MultiControllerManager

            self.multi_controller_manager = MultiControllerManager()

        # Scan for new controllers
        if hasattr(self, 'multi_controller_manager'):
            self.multi_controller_manager.scan_for_controllers()

        # Register any new controllers
        self._register_new_controllers()

        # Initialize slider indicators dictionary if needed
        if not hasattr(self, 'slider_indicators'):
            self.slider_indicators: dict[int, BitmappySprite] = {}

        # Get the screen surface
        screen = pygame.display.get_surface()
        if not screen:
            return

        # Update all slider indicators with collision avoidance
        self._update_all_slider_indicators()

        # Update film strip controller selections
        self._update_film_strip_controller_selections()

        # Update canvas indicators
        self._update_canvas_indicators()

    def _create_slider_indicator_sprite(
        self, controller_id: int, color: tuple[int, ...], slider_rect: pygame.FRect | pygame.Rect
    ) -> BitmappySprite:
        """Create a proper Bitmappy sprite for slider indicator.

        Returns:
            BitmappySprite: The result.

        """
        # Create a circular indicator sprite
        indicator_size = 16
        center_x = slider_rect.x + slider_rect.width / 2
        center_y = slider_rect.y + slider_rect.height / 2

        # Create the sprite
        indicator = BitmappySprite(
            name=f'SliderIndicator_{controller_id}',
            x=center_x - indicator_size // 2,
            y=center_y - indicator_size // 2,
            width=indicator_size,
            height=indicator_size,
            groups=self.all_sprites,
        )

        # Make the background transparent
        indicator.image.set_colorkey((0, 0, 0))  # Make black transparent
        indicator.image.fill((0, 0, 0))  # Fill with black first

        # Draw the indicator on the sprite surface
        pygame.draw.circle(indicator.image, color, (indicator_size // 2, indicator_size // 2), 8)
        pygame.draw.circle(
            indicator.image, (255, 255, 255), (indicator_size // 2, indicator_size // 2), 8, 2
        )

        return indicator

    def _update_slider_indicator(self, controller_id: int, color: tuple[int, ...]) -> None:
        """Update or create slider indicator for a controller."""
        # Remove any existing indicator for this controller
        self._remove_slider_indicator(controller_id)

        # Get the controller's current mode to determine which slider
        if hasattr(self, 'mode_switcher'):
            controller_mode = self.mode_switcher.get_controller_mode(controller_id)

            # Create indicator on the appropriate slider based on mode
            if (
                controller_mode
                and controller_mode.value == 'r_slider'
                and hasattr(self, 'red_slider')
            ):
                indicator = self._create_slider_indicator_sprite(
                    controller_id,
                    color,
                    self.red_slider.rect,
                )
                self.slider_indicators[controller_id] = indicator

            elif (
                controller_mode
                and controller_mode.value == 'g_slider'
                and hasattr(self, 'green_slider')
            ):
                indicator = self._create_slider_indicator_sprite(
                    controller_id,
                    color,
                    self.green_slider.rect,
                )
                self.slider_indicators[controller_id] = indicator

            elif (
                controller_mode
                and controller_mode.value == 'b_slider'
                and hasattr(self, 'blue_slider')
            ):
                indicator = self._create_slider_indicator_sprite(
                    controller_id,
                    color,
                    self.blue_slider.rect,
                )
                self.slider_indicators[controller_id] = indicator

    def _update_all_slider_indicators(self) -> None:
        """Update all slider indicators with collision avoidance."""
        # Clear all existing slider indicators
        for controller_id in list(self.slider_indicators.keys()):
            self._remove_slider_indicator(controller_id)

        slider_groups = self._group_controllers_by_slider()

        # Create indicators for each slider with collision avoidance
        for slider_mode, controllers in slider_groups.items():
            if controllers and len(controllers) > 0:
                self._create_slider_indicators_with_collision_avoidance(slider_mode, controllers)

    def _group_controllers_by_slider(self) -> dict[str, list[dict[str, Any]]]:
        """Group active controllers by their slider mode.

        Returns:
            Dict mapping slider mode strings to lists of controller info dicts.

        """
        slider_groups: dict[str, list[dict[str, Any]]] = {
            'r_slider': [],
            'g_slider': [],
            'b_slider': [],
        }

        for controller_id, controller_selection in self.controller_selections.items():
            if not (controller_selection.is_active() and hasattr(self, 'mode_switcher')):
                continue

            controller_mode = self.mode_switcher.get_controller_mode(controller_id)
            if not (controller_mode and controller_mode.value in slider_groups):
                continue

            controller_info = self._find_controller_info(controller_id)
            if controller_info:
                slider_groups[controller_mode.value].append({
                    'controller_id': controller_id,
                    'color': controller_info.color,
                })

        return slider_groups

    def _create_slider_indicators_with_collision_avoidance(
        self, slider_mode: str, controllers: list[dict[str, Any]]
    ) -> None:
        """Create slider indicators with collision avoidance for multiple controllers."""
        # Get the appropriate slider
        slider = None
        if slider_mode == 'r_slider' and hasattr(self, 'red_slider'):
            slider = self.red_slider
        elif slider_mode == 'g_slider' and hasattr(self, 'green_slider'):
            slider = self.green_slider
        elif slider_mode == 'b_slider' and hasattr(self, 'blue_slider'):
            slider = self.blue_slider

        if not slider:
            return

        # Sort controllers by color priority (same as film strip)
        def get_color_priority(controller: dict[str, object]) -> int:
            color = controller['color']
            if color == (255, 0, 0):  # Red
                return 0
            if color == (0, 255, 0):  # Green
                return 1
            if color == (0, 0, 255):  # Blue
                return 2
            if color == (255, 255, 0):  # Yellow
                return 3
            return 999  # Unknown colors go last

        controllers.sort(key=get_color_priority)

        # Calculate positioning with collision avoidance
        indicator_size = 16
        indicator_spacing = 20  # Space between indicator centers

        # Calculate total width needed for all indicators
        total_width = (len(controllers) - 1) * indicator_spacing

        # Calculate starting position to center the group
        slider_rect = slider.rect
        assert slider_rect is not None
        start_x = slider_rect.centerx - (total_width // 2)
        center_y = slider_rect.centery

        # Create indicators with proper spacing
        current_x = start_x
        for controller in controllers:
            # Create indicator at calculated position
            indicator = BitmappySprite(
                name=f'SliderIndicator_{controller["controller_id"]}',
                x=int(current_x - indicator_size // 2),
                y=int(center_y - indicator_size // 2),
                width=indicator_size,
                height=indicator_size,
                groups=self.all_sprites,
            )

            # Make the background transparent
            indicator.image.set_colorkey((0, 0, 0))
            indicator.image.fill((0, 0, 0))

            # Draw the indicator
            pygame.draw.circle(
                indicator.image, controller['color'], (indicator_size // 2, indicator_size // 2), 8
            )
            pygame.draw.circle(
                indicator.image, (255, 255, 255), (indicator_size // 2, indicator_size // 2), 8, 2
            )

            # Store the indicator
            self.slider_indicators[controller['controller_id']] = indicator

            # Move to next position
            current_x += indicator_spacing

    def _update_film_strip_controller_selections(self) -> None:
        """Update film strip controller selections for all animations."""
        if not hasattr(self, 'film_strip_controller_selections'):
            self.film_strip_controller_selections: dict[str, Any] = {}

        self.film_strip_controller_selections.clear()

        if not hasattr(self, 'controller_selections'):
            return

        for controller_id, controller_selection in self.controller_selections.items():
            self._process_film_strip_controller_selection(controller_id, controller_selection)

    def _process_film_strip_controller_selection(
        self, controller_id: int, controller_selection: ControllerSelection
    ) -> None:
        """Process a single controller selection for film strip mode.

        Args:
            controller_id: The controller ID.
            controller_selection: The controller selection object.

        """
        if not controller_selection.is_active():
            return

        controller_mode = None
        if hasattr(self, 'mode_switcher'):
            controller_mode = self.mode_switcher.get_controller_mode(controller_id)

        if not (controller_mode and controller_mode.value == 'film_strip'):
            return

        animation, frame = controller_selection.get_selection()

        controller_info = self._find_controller_info(controller_id)
        if not controller_info:
            return

        # Only include controllers that have been properly initialized (not default gray)
        if not animation or controller_info.color == (128, 128, 128):
            return

        # Group by animation
        if animation not in self.film_strip_controller_selections:
            self.film_strip_controller_selections[animation] = {}

        self.film_strip_controller_selections[animation][controller_id] = {
            'controller_id': controller_id,
            'frame': frame,
            'color': controller_info.color,
        }

    def _find_controller_info(self, controller_id: int) -> Any:
        """Find controller info by controller ID.

        Args:
            controller_id: The controller ID to look up.

        Returns:
            The controller info object, or None if not found.

        """
        if not hasattr(self, 'multi_controller_manager'):
            return None

        for info in self.multi_controller_manager.controllers.values():
            if info.controller_id == controller_id:
                return info
        return None

    def _update_canvas_indicators(self) -> None:
        """Update canvas indicators for controllers in canvas mode."""
        if not hasattr(self, 'canvas') or not self.canvas:
            return

        canvas_controllers = self._collect_canvas_controllers()

        if canvas_controllers:
            self.canvas_controller_indicators = canvas_controllers
            if hasattr(self.canvas, 'canvas_interface'):
                self.canvas.canvas_interface.controller_indicators = canvas_controllers  # type: ignore[attr-defined]
            self.canvas.force_redraw()
        else:
            self.canvas_controller_indicators = []
            if hasattr(self.canvas, 'canvas_interface'):
                self.canvas.canvas_interface.controller_indicators = []  # type: ignore[attr-defined]

    def _collect_canvas_controllers(self) -> list[dict[str, Any]]:
        """Collect all active controllers in canvas mode with their positions.

        Returns:
            List of dicts with controller_id, position, and color.

        """
        canvas_controllers: list[dict[str, Any]] = []
        for controller_id, controller_selection in self.controller_selections.items():
            if not controller_selection.is_active():
                continue

            controller_mode = None
            if hasattr(self, 'mode_switcher'):
                controller_mode = self.mode_switcher.get_controller_mode(controller_id)

            if not (controller_mode and controller_mode.value == 'canvas'):
                continue

            controller_info = self._find_controller_info(controller_id)
            if not controller_info:
                continue

            position = self.mode_switcher.get_controller_position(controller_id)
            if position and position.is_valid:
                canvas_controllers.append({
                    'controller_id': controller_id,
                    'position': position.position,
                    'color': controller_info.color,
                })
        return canvas_controllers

    def _register_new_controllers(self) -> None:
        """Register any new controllers that have been detected."""
        if not hasattr(self, 'multi_controller_manager'):
            return

        # Check for any controllers that aren't registered yet
        for instance_id, controller_info in self.multi_controller_manager.controllers.items():
            controller_id = controller_info.controller_id
            if controller_id not in self.controller_selections:
                # Register new controller
                from glitchygames.tools.controller_selection import ControllerSelection

                self.controller_selections[controller_id] = ControllerSelection(
                    controller_id, instance_id
                )

                # Activate the controller
                self.controller_selections[controller_id].activate()

                # Register with mode switcher
                if hasattr(self, 'mode_switcher'):
                    from glitchygames.tools.controller_mode_system import ControllerMode

                    self.mode_switcher.register_controller(controller_id, ControllerMode.FILM_STRIP)

                self.log.debug(
                    f'BitmapEditorScene: Registered and activated new controller {controller_id}'
                    f' (instance {instance_id})'
                )

    def _remove_slider_indicator(self, controller_id: int) -> None:
        """Remove slider indicator for a controller."""
        if hasattr(self, 'slider_indicators') and controller_id in self.slider_indicators:
            indicator = self.slider_indicators[controller_id]
            # Remove from sprite groups
            if hasattr(self, 'all_sprites'):
                self.all_sprites.remove(indicator)
            # Remove from tracking
            del self.slider_indicators[controller_id]

    @override
    def render(self, screen: pygame.Surface) -> None:
        """Render the scene with visual indicators."""
        # Call the parent render method first
        super().render(screen)

        # Then render visual indicators on top
        self._render_visual_indicators()

    def _draw_visual_indicator(self, screen: pygame.Surface, indicator: VisualIndicator) -> None:
        """Draw a single visual indicator on the screen."""
        if not indicator.is_visible:
            self.log.debug(
                f'DEBUG: Indicator for controller {indicator.controller_id} is not visible'
            )
            return

        # Calculate final position with offset
        final_x = indicator.position[0] + indicator.offset[0]
        final_y = indicator.position[1] + indicator.offset[1]

        self.log.debug(
            f'DEBUG: Drawing indicator for controller {indicator.controller_id} at ({final_x},'
            f' {final_y}) with shape {indicator.shape.value}'
        )

        # Draw based on shape
        if indicator.shape.value == 'triangle':
            # Draw triangle (film strip indicator)
            points = [
                (final_x, final_y - indicator.size // 2),
                (final_x - indicator.size // 2, final_y + indicator.size // 2),
                (final_x + indicator.size // 2, final_y + indicator.size // 2),
            ]
            pygame.draw.polygon(screen, indicator.color, points)
        elif indicator.shape.value == 'square':
            # Draw square (canvas indicator)
            rect = pygame.Rect(
                final_x - indicator.size // 2,
                final_y - indicator.size // 2,
                indicator.size,
                indicator.size,
            )
            pygame.draw.rect(screen, indicator.color, rect)
        elif indicator.shape.value == 'circle':
            # Draw circle (slider indicator)
            pygame.draw.circle(screen, indicator.color, (final_x, final_y), indicator.size // 2)

    def _select_current_frame(self) -> None:
        """Select the currently highlighted frame."""
        if not hasattr(self, 'selected_animation') or not hasattr(self, 'selected_frame'):
            return

        # Find the active film strip
        if hasattr(self, 'film_strips') and self.film_strips:
            for strip_name, strip_widget in self.film_strips.items():
                if strip_name == self.selected_animation:
                    # Trigger frame selection
                    self._on_film_strip_frame_selected(
                        strip_widget,
                        self.selected_animation,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
                        self.selected_frame,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
                    )
                    break

    def _controller_cancel(self) -> None:
        """Handle controller cancel action."""
        # For now, just log the action
        LOG.debug('Controller cancel action')

    def _controller_select_current_frame(self) -> None:
        """Deprecate old single-controller system in favor of multi-controller system."""
        LOG.debug(
            '_controller_select_current_frame called but DISABLED - use multi-controller system '
            'instead'
        )
        # OLD SYSTEM DISABLED - Use multi-controller system instead

    def _controller_previous_frame(self) -> None:
        """Deprecate old single-controller system in favor of multi-controller system."""
        LOG.debug(
            '_controller_previous_frame called but DISABLED - use multi-controller system instead'
        )
        # OLD SYSTEM DISABLED - Use multi-controller system instead

    def _controller_next_frame(self) -> None:
        """Deprecate old single-controller system in favor of multi-controller system."""
        LOG.debug(
            '_controller_next_frame called but DISABLED - use multi-controller system instead'
        )
        # OLD SYSTEM DISABLED - Use multi-controller system instead

    def _controller_previous_animation(self) -> None:
        """Deprecate old single-controller system in favor of multi-controller system."""
        LOG.debug(
            '_controller_previous_animation called but DISABLED - use multi-controller system '
            'instead'
        )
        # OLD SYSTEM DISABLED - Use multi-controller system instead

    def _controller_next_animation(self) -> None:
        """Deprecate old single-controller system in favor of multi-controller system."""
        LOG.debug(
            '_controller_next_animation called but DISABLED - use multi-controller system instead'
        )
        # OLD SYSTEM DISABLED - Use multi-controller system instead

    def _scroll_to_controller_animation(self, animation_name: str) -> None:
        """Scroll film strips to show the specified animation for multi-controller system."""
        if not hasattr(self, 'film_strips') or not self.film_strips:
            return

        # Get all animation names in order
        animation_names = list(self.film_strips.keys())
        if animation_name not in animation_names:
            return

        # Find the index of the target animation
        target_index = animation_names.index(animation_name)

        # Calculate the scroll offset needed to show this animation
        # We want to show the target animation in the visible area
        if target_index < self.film_strip_scroll_offset:
            # Target animation is above the visible area, scroll up
            self.film_strip_scroll_offset = target_index
        elif target_index >= self.film_strip_scroll_offset + self.max_visible_strips:
            # Target animation is below the visible area, scroll down
            self.film_strip_scroll_offset = target_index - self.max_visible_strips + 1

        # Update visibility and scroll arrows
        self._update_film_strip_visibility()
        self._update_scroll_arrows()

        self.log.debug(
            f"DEBUG: Scrolled to show animation '{animation_name}' at index {target_index}, scroll"
            f' offset: {self.film_strip_scroll_offset}'
        )

    def _validate_controller_selection(self) -> None:
        """Deprecate old single-controller system in favor of multi-controller system."""
        LOG.debug(
            '_validate_controller_selection called but DISABLED - use multi-controller system '
            'instead'
        )
        # OLD SYSTEM DISABLED - Use multi-controller system instead

    def _initialize_controller_selection(self) -> None:
        """Deprecate old single-controller system in favor of multi-controller system."""
        LOG.debug(
            '_initialize_controller_selection called but DISABLED - use multi-controller system '
            'instead'
        )
        # OLD SYSTEM DISABLED - Use multi-controller system instead

    def _controller_select_frame(self, animation: str, frame: int) -> None:
        """Deprecate old single-controller system in favor of multi-controller system.

        This method is kept for compatibility but should not be used.
        Use the new multi-controller system instead.
        """
        self.log.debug(
            'DEBUG: _controller_select_frame called but DISABLED - use multi-controller system '
            'instead'
        )
        # OLD SYSTEM DISABLED - Use multi-controller system instead

    # Multi-Controller System Methods
    def _multi_controller_activate(self, controller_id: int) -> None:
        """Activate a controller for navigation.

        Args:
            controller_id: Controller ID to activate

        """
        if controller_id not in self.controller_selections:
            self.log.debug(f'DEBUG: Controller {controller_id} not found for activation')
            return

        controller_selection = self.controller_selections[controller_id]
        controller_selection.activate()

        # Assign color based on activation order using singleton
        from .multi_controller_manager import MultiControllerManager

        manager = MultiControllerManager.get_instance()
        self.log.debug(f'DEBUG: About to assign color to controller {controller_id}')
        self.log.debug(
            f'DEBUG: Available controllers in manager: {list(manager.controllers.keys())}'
        )
        for instance_id, info in manager.controllers.items():
            self.log.debug(
                f'DEBUG: Controller instance_id={instance_id}, controller_id={info.controller_id},'
                f' color={info.color}'
            )
        manager.assign_color_to_controller(controller_id)

        # Initialize to first available animation if not set
        if (
            not controller_selection.get_animation()
            and hasattr(self, 'film_strips')
            and self.film_strips
        ):
            first_animation = next(iter(self.film_strips.keys()))
            controller_selection.set_selection(first_animation, 0)
            self.log.debug(
                f"DEBUG: Controller {controller_id} initialized to '{first_animation}', frame 0"
            )

        # Update visual collision manager
        self._update_controller_visual_indicator(controller_id)

        # Mark all film strips as dirty to update colors
        if hasattr(self, 'film_strips') and self.film_strips:
            for film_strip in self.film_strips.values():
                film_strip.mark_dirty()
        if hasattr(self, 'film_strip_sprites') and self.film_strip_sprites:
            for film_strip_sprite in self.film_strip_sprites.values():
                film_strip_sprite.dirty = 1

        self.log.debug(f'DEBUG: Controller {controller_id} activated')

    def _multi_controller_previous_frame(self, controller_id: int) -> None:
        """Move to previous frame for a controller.

        Args:
            controller_id: Controller ID

        """
        if controller_id not in self.controller_selections:
            self.log.debug(f'DEBUG: Controller {controller_id} not found for previous frame')
            return

        controller_selection = self.controller_selections[controller_id]
        animation, frame = controller_selection.get_selection()

        if not animation or animation not in self.film_strips:
            self.log.debug(
                f'DEBUG: Controller {controller_id} has no valid animation for previous frame'
            )
            return

        strip_widget = self.film_strips[animation]
        if hasattr(strip_widget, 'animated_sprite') and strip_widget.animated_sprite:
            frame_count = strip_widget.animated_sprite.current_animation_frame_count
            new_frame = (frame - 1) % frame_count
            controller_selection.set_frame(new_frame)

            # Scroll the film strip to show the selected frame if it's off-screen
            if hasattr(strip_widget, 'update_scroll_for_frame'):
                strip_widget.update_scroll_for_frame(new_frame)
                self.log.debug(
                    f'DEBUG: Controller {controller_id} previous frame: Scrolled film strip to show'
                    f' frame {new_frame}'
                )

            # Update visual indicator
            self._update_controller_visual_indicator(controller_id)

            self.log.debug(
                f'DEBUG: Controller {controller_id} previous frame: {frame} -> {new_frame}'
            )

    def _multi_controller_next_frame(self, controller_id: int) -> None:
        """Move to next frame for a controller.

        Args:
            controller_id: Controller ID

        """
        if controller_id not in self.controller_selections:
            self.log.debug(f'DEBUG: Controller {controller_id} not found for next frame')
            return

        controller_selection = self.controller_selections[controller_id]
        animation, frame = controller_selection.get_selection()

        if not animation or animation not in self.film_strips:
            self.log.debug(
                f'DEBUG: Controller {controller_id} has no valid animation for next frame'
            )
            return

        strip_widget = self.film_strips[animation]
        if hasattr(strip_widget, 'animated_sprite') and strip_widget.animated_sprite:
            frame_count = strip_widget.animated_sprite.current_animation_frame_count
            new_frame = (frame + 1) % frame_count
            controller_selection.set_frame(new_frame)

            # Scroll the film strip to show the selected frame if it's off-screen
            if hasattr(strip_widget, 'update_scroll_for_frame'):
                strip_widget.update_scroll_for_frame(new_frame)
                self.log.debug(
                    f'DEBUG: Controller {controller_id} next frame: Scrolled film strip to show'
                    f' frame {new_frame}'
                )

            # Update visual indicator
            self._update_controller_visual_indicator(controller_id)

            self.log.debug(f'DEBUG: Controller {controller_id} next frame: {frame} -> {new_frame}')

    def _multi_controller_previous_animation(self, controller_id: int) -> None:
        """Move to previous animation for a controller.

        Args:
            controller_id: Controller ID

        """
        if controller_id not in self.controller_selections:
            self.log.debug(f'DEBUG: Controller {controller_id} not found for previous animation')
            return

        controller_selection = self.controller_selections[controller_id]
        current_animation, _current_frame = controller_selection.get_selection()

        if not hasattr(self, 'film_strips') or not self.film_strips:
            self.log.debug(
                f'DEBUG: No film strips available for controller {controller_id} previous animation'
            )
            return

        # Get all animation names in order
        animation_names = list(self.film_strips.keys())
        if not animation_names:
            self.log.debug(
                f'DEBUG: No animations available for controller {controller_id} previous animation'
            )
            return

        # Find current animation index
        try:
            current_index = animation_names.index(current_animation)
        except ValueError:
            current_index = 0

        # Move to previous animation
        new_index = (current_index - 1) % len(animation_names)
        new_animation = animation_names[new_index]

        # Try to preserve the frame index from the previous animation
        prev_strip_animated_sprite = self.film_strips[new_animation].animated_sprite
        assert prev_strip_animated_sprite is not None
        target_frame = controller_selection.preserve_frame_for_animation(
            new_animation,
            prev_strip_animated_sprite.current_animation_frame_count,
        )

        self.log.debug(
            f"DEBUG: Controller {controller_id} previous animation: Moving to '{new_animation}',"
            f' frame {target_frame}'
        )
        controller_selection.set_selection(new_animation, target_frame)

        # Scroll the film strip view to show the selected animation if it's off-screen
        self._scroll_to_controller_animation(new_animation)

        # Update visual indicator
        self._update_controller_visual_indicator(controller_id)

    def _multi_controller_next_animation(self, controller_id: int) -> None:
        """Move to next animation for a controller.

        Args:
            controller_id: Controller ID

        """
        if controller_id not in self.controller_selections:
            self.log.debug(f'DEBUG: Controller {controller_id} not found for next animation')
            return

        controller_selection = self.controller_selections[controller_id]
        current_animation, _current_frame = controller_selection.get_selection()

        if not hasattr(self, 'film_strips') or not self.film_strips:
            self.log.debug(
                f'DEBUG: No film strips available for controller {controller_id} next animation'
            )
            return

        # Get all animation names in order
        animation_names = list(self.film_strips.keys())
        if not animation_names:
            self.log.debug(
                f'DEBUG: No animations available for controller {controller_id} next animation'
            )
            return

        # Find current animation index
        try:
            current_index = animation_names.index(current_animation)
        except ValueError:
            current_index = 0

        # Move to next animation
        new_index = (current_index + 1) % len(animation_names)
        new_animation = animation_names[new_index]

        # Try to preserve the frame index from the previous animation
        next_strip_animated_sprite = self.film_strips[new_animation].animated_sprite
        assert next_strip_animated_sprite is not None
        target_frame = controller_selection.preserve_frame_for_animation(
            new_animation,
            next_strip_animated_sprite.current_animation_frame_count,
        )

        self.log.debug(
            f"DEBUG: Controller {controller_id} next animation: Moving to '{new_animation}', frame"
            f' {target_frame}'
        )
        controller_selection.set_selection(new_animation, target_frame)

        # Scroll the film strip view to show the selected animation if it's off-screen
        self._scroll_to_controller_animation(new_animation)

        # Update visual indicator
        self._update_controller_visual_indicator(controller_id)

    def _update_controller_visual_indicator(self, controller_id: int) -> None:
        """Update visual indicator for a controller.

        Args:
            controller_id: Controller ID

        """
        if controller_id not in self.controller_selections:
            return

        controller_selection = self.controller_selections[controller_id]
        animation, _frame = controller_selection.get_selection()

        if not animation or animation not in self.film_strips:
            return

        # Get controller color
        controller_info = None
        for info in self.multi_controller_manager.controllers.values():
            if info.controller_id == controller_id:
                controller_info = info
                break

        if not controller_info:
            return

        # Calculate position (this would need to be implemented based on your UI layout)
        # For now, we'll use a placeholder position
        position = (100 + controller_id * 50, 100)

        # Add or update visual indicator
        if controller_id not in self.visual_collision_manager.indicators:
            self.visual_collision_manager.add_controller_indicator(
                controller_id, controller_info.instance_id, controller_info.color, position
            )
        else:
            self.visual_collision_manager.update_controller_position(controller_id, position)

    def _multi_controller_toggle_onion_skinning(self, controller_id: int) -> None:
        """Toggle onion skinning for the controller's selected frame.

        Args:
            controller_id: Controller ID to toggle onion skinning for

        """
        if controller_id not in self.controller_selections:
            self.log.debug(f'DEBUG: Controller {controller_id} not found for onion skinning toggle')
            return

        controller_selection = self.controller_selections[controller_id]
        animation, frame = controller_selection.get_selection()

        if not animation or frame is None:  # type: ignore[reportUnnecessaryComparison]
            self.log.debug(
                f'DEBUG: Controller {controller_id} has no valid selection for onion skinning'
                f' toggle'
            )
            return

        # Get onion skinning manager
        from .onion_skinning import get_onion_skinning_manager

        onion_manager = get_onion_skinning_manager()

        # Toggle onion skinning for this frame
        is_enabled = onion_manager.toggle_frame_onion_skinning(animation, frame)
        status = 'enabled' if is_enabled else 'disabled'

        self.log.debug(
            f'DEBUG: Controller {controller_id}: Onion skinning {status} for {animation}[{frame}]'
        )
        LOG.debug(f'Controller {controller_id}: Onion skinning {status} for {animation}[{frame}]')

        # Force redraw of the canvas to show the change
        if hasattr(self, 'canvas') and self.canvas:
            self.canvas.force_redraw()

    def _multi_controller_toggle_selected_frame_visibility(self, controller_id: int) -> None:
        """Toggle visibility of the selected frame on the canvas for comparison.

        Args:
            controller_id: Controller ID (not used but kept for consistency)

        """
        # Toggle the selected frame visibility
        self.selected_frame_visible = not self.selected_frame_visible
        status = 'visible' if self.selected_frame_visible else 'hidden'

        self.log.debug(f'DEBUG: Controller {controller_id}: Selected frame {status} on canvas')
        LOG.debug(f'Controller {controller_id}: Selected frame {status} on canvas')

        # Force redraw of the canvas to show the change
        if hasattr(self, 'canvas') and self.canvas:
            self.canvas.force_redraw()

    def _multi_controller_select_current_frame(self, controller_id: int) -> None:
        """Select the current frame that the controller is pointing to.

        Args:
            controller_id: The ID of the controller.

        """
        self.log.debug(
            f'DEBUG: _multi_controller_select_current_frame called for controller {controller_id}'
        )

        if controller_id not in self.controller_selections:
            self.log.debug(f'DEBUG: Controller {controller_id} not found in selections')
            return

        controller_selection = self.controller_selections[controller_id]
        if not controller_selection.is_active():
            self.log.debug(f'DEBUG: Controller {controller_id} is not active')
            return

        animation, frame = controller_selection.get_selection()
        self.log.debug(
            f"DEBUG: Controller {controller_id} selecting frame {frame} in animation '{animation}'"
        )
        self.log.debug(
            'DEBUG: Current global selection before update:'
            f" animation='{getattr(self, 'selected_animation', 'None')}',"
            f' frame={getattr(self, "selected_frame", "None")}'
        )

        # Update the canvas to show this frame
        if animation in self.film_strips:
            strip_widget = self.film_strips[animation]
            if hasattr(strip_widget, 'animated_sprite') and strip_widget.animated_sprite:
                if animation in strip_widget.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
                    if frame < len(strip_widget.animated_sprite._animations[animation]):  # type: ignore[reportPrivateUsage]
                        # Update the canvas to show this frame using the same mechanism as keyboard
                        # selection
                        self.log.debug(
                            f"DEBUG: Updating canvas to show animation '{animation}', frame {frame}"
                        )
                        self.canvas.show_frame(animation, frame)

                        # Store global selection state (same as keyboard selection)
                        self.log.debug(
                            f"DEBUG: Setting global selection state to animation '{animation}',"
                            f' frame {frame}'
                        )
                        self.selected_animation = animation
                        self.selected_frame = frame

                        # Update film strip selection state (same as keyboard selection)
                        self.log.debug('DEBUG: Calling _update_film_strip_selection_state()')
                        self._update_film_strip_selection_state()

                        self.log.debug(
                            'DEBUG: Controller selection updated keyboard selection to animation'
                            f" '{animation}', frame {frame}"
                        )
                        self.log.debug(
                            f"DEBUG: Final global selection: animation='{self.selected_animation}',"
                            f' frame={self.selected_frame}'
                        )
                    else:
                        self.log.debug(
                            f"DEBUG: Frame {frame} is out of bounds for animation '{animation}'"
                            f' (max:'
                            f' {len(strip_widget.animated_sprite._animations[animation]) - 1})'  # type: ignore[reportPrivateUsage]
                        )
                else:
                    self.log.debug(
                        f"DEBUG: Animation '{animation}' not found in"
                        f' strip_widget.animated_sprite._animations'
                    )
            else:
                self.log.debug(
                    'DEBUG: strip_widget has no animated_sprite or animated_sprite is None'
                )
        else:
            self.log.debug(f"DEBUG: Animation '{animation}' not found in film_strips")

    def _multi_controller_cancel(self, controller_id: int) -> None:
        """Cancel controller selection.

        Args:
            controller_id: The ID of the controller.

        """
        if controller_id not in self.controller_selections:
            return

        controller_selection = self.controller_selections[controller_id]
        controller_selection.deactivate()
        self.log.debug(f'DEBUG: Controller {controller_id} cancelled')

    def _reinitialize_multi_controller_system(
        self, preserved_controller_selections: dict[int, tuple[str, int]] | None = None
    ) -> None:
        """Reinitialize the multi-controller system when film strips are reconstructed.

        This ensures that existing controller selections are preserved and properly
        initialized when film strips are recreated (e.g., when loading an animation file).

        Args:
            preserved_controller_selections: Optional dict of preserved controller selections
                from before film strip reconstruction.

        """
        import sys

        if 'pytest' not in sys.modules:
            LOG.debug('DEBUG: Reinitializing multi-controller system')
            self.log.debug(
                f'DEBUG: Current controller_selections: {list(self.controller_selections.keys())}'
            )
            self.log.debug(
                f'DEBUG: Current film_strips: {
                    list(self.film_strips.keys())
                    if hasattr(self, "film_strips") and self.film_strips
                    else "None"
                }'
            )

        if not self.controller_selections:
            if 'pytest' not in sys.modules:
                LOG.debug('DEBUG: controller_selections is empty - scene was likely recreated')
            return

        active_controllers = self._get_active_controllers(preserved_controller_selections)
        self.log.debug(f'DEBUG: Found {len(active_controllers)} active controllers to preserve')

        self.multi_controller_manager.scan_for_controllers()
        self.log.debug(
            f'DEBUG: Found {len(self.multi_controller_manager.controllers)} controllers in manager'
        )

        self._reinitialize_controller_selections(active_controllers)

        self.log.debug(
            f'DEBUG: Multi-controller system reinitialized with {len(self.controller_selections)}'
            f' controller selections'
        )

    def _get_active_controllers(
        self, preserved_controller_selections: dict[int, tuple[str, int]] | None
    ) -> dict[int, tuple[str, int]]:
        """Get the active controller state, either preserved or current.

        Args:
            preserved_controller_selections: Optional preserved selections.

        Returns:
            Dict mapping controller_id to (animation, frame) tuples.

        """
        if preserved_controller_selections is not None:
            self.log.debug(
                f'DEBUG: Using preserved controller selections: {preserved_controller_selections}'
            )
            return preserved_controller_selections

        active_controllers: dict[int, tuple[str, int]] = {}
        self.log.debug(
            f'DEBUG: Checking {len(self.controller_selections)} existing controller selections'
        )
        for controller_id, controller_selection in self.controller_selections.items():
            is_active = controller_selection.is_active()
            self.log.debug(f'DEBUG: Controller {controller_id} is_active: {is_active}')
            if is_active:
                animation, frame = controller_selection.get_selection()
                active_controllers[controller_id] = (animation, frame)
                self.log.debug(
                    f'DEBUG: Storing active controller {controller_id} with animation'
                    f" '{animation}', frame {frame}"
                )
        return active_controllers

    def _reinitialize_controller_selections(
        self, active_controllers: dict[int, tuple[str, int]]
    ) -> None:
        """Reinitialize controller selections from the multi-controller manager.

        Args:
            active_controllers: Dict mapping controller_id to (animation, frame) tuples.

        """
        for instance_id, controller_info in self.multi_controller_manager.controllers.items():
            self.log.debug(
                f'DEBUG: Processing controller {instance_id}, status:'
                f' {controller_info.status.value}'
            )
            if controller_info.status.value not in {'connected', 'assigned', 'active'}:
                continue

            controller_id = controller_info.controller_id
            self._ensure_controller_selection_exists(controller_id, instance_id)
            self._restore_controller_active_state(controller_id, active_controllers)

    def _ensure_controller_selection_exists(self, controller_id: int, instance_id: int) -> None:
        """Ensure a controller selection exists for the given controller.

        Args:
            controller_id: The controller ID.
            instance_id: The instance ID for creating new selections.

        """
        if controller_id not in self.controller_selections:
            self.controller_selections[controller_id] = ControllerSelection(
                controller_id, instance_id
            )
            self.log.debug(
                f'DEBUG: Created new controller selection for controller {controller_id} (inactive)'
            )
        else:
            controller_selection = self.controller_selections[controller_id]
            controller_selection.update_activity()
            self.log.debug(
                f'DEBUG: Updated existing controller selection for controller {controller_id}'
            )

    def _restore_controller_active_state(
        self, controller_id: int, active_controllers: dict[int, tuple[str, int]]
    ) -> None:
        """Restore a controller's active state after reinitialization.

        Args:
            controller_id: The controller ID.
            active_controllers: Dict mapping controller_id to (animation, frame) tuples.

        """
        controller_selection = self.controller_selections[controller_id]

        if controller_id not in active_controllers:
            self.log.debug(
                f'DEBUG: Controller {controller_id} was not active before reconstruction,'
                f' keeping it inactive'
            )
            return

        if not self.film_strips:
            self.log.debug(f'DEBUG: No film strips available for active controller {controller_id}')
            return

        # Always reset to first strip and frame 0 when loading new files
        # since animation names and structure will be different
        first_animation = next(iter(self.film_strips.keys()))
        controller_selection.set_selection(first_animation, 0)
        controller_selection.activate()
        self.log.debug(
            f'DEBUG: Reset active controller {controller_id} to first animation'
            f" '{first_animation}', frame 0 (ignoring previous selection)"
        )
        self.log.debug(
            f'DEBUG: Controller {controller_id} is now active: {controller_selection.is_active()}'
        )
        self.log.debug(
            f'DEBUG: Controller {controller_id} selection: {controller_selection.get_selection()}'
        )
        self.log.debug(f'DEBUG: Available film strips: {list(self.film_strips.keys())}')


def main() -> None:
    """Run the main function.

    Raises:
        None

    """
    LOG.setLevel(logging.INFO)

    # Set up signal handling to prevent multiprocessing issues on macOS
    def signal_handler(signum: int) -> None:
        """Handle shutdown signals gracefully."""
        LOG.info(f'Received signal {signum}, shutting down gracefully...')
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)  # type: ignore[arg-type]
    signal.signal(signal.SIGTERM, signal_handler)  # type: ignore[arg-type]

    # Set multiprocessing start method to avoid macOS issues
    with contextlib.suppress(RuntimeError):
        multiprocessing.set_start_method('spawn', force=True)

    icon_path = Path(__file__).parent / 'resources' / 'bitmappy.png'

    # Initialize the game engine first to set up display
    engine = GameEngine(game=BitmapEditorScene, icon=icon_path)

    # Load AI training data after engine initialization
    load_ai_training_data()

    # Start the engine
    engine.start()


if __name__ == '__main__':
    main()
