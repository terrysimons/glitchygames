"""Pixel utility functions for sprite animation.

This module contains helper functions for pixel color manipulation, alpha channel
detection, and color map lookups used by the animation system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

import pygame

from glitchygames.color import (
    MAGENTA_TRANSPARENCY_KEY,
    MAX_COLOR_CHANNEL_VALUE,
    RGB_COMPONENT_COUNT,
    RGBA_COMPONENT_COUNT,
)

# Constants
PIXEL_ARRAY_SHAPE_DIMENSIONS = 3

# Error message templates
ERR_COLOR_NOT_FOUND = 'Color {} not found in color map. Available colors: {}'
ERR_COLOR_NOT_FOUND_WITH_RGBA = 'Color {} (or RGBA {}) not found in color map. Available colors: {}'


def needs_alpha_channel(pixels: Sequence[tuple[int, ...]]) -> bool:
    """Check if pixel data needs alpha channel support.

    Args:
        pixels: List of pixel tuples (RGB or RGBA)

    Returns:
        True if any pixel has non-opaque alpha or if pixels are RGBA format

    """
    for pixel in pixels:
        if len(pixel) == RGBA_COMPONENT_COUNT:
            # RGBA format - check if alpha is not 255 (fully opaque)
            _r, _g, _b, a = pixel
            if a != MAX_COLOR_CHANNEL_VALUE:
                return True
        elif len(pixel) == RGB_COMPONENT_COUNT:
            # RGB format - check if it's the transparent color (255, 0, 255)
            if pixel == MAGENTA_TRANSPARENCY_KEY:
                return True
    return False


def convert_pixels_to_rgb_if_possible(
    pixels: Sequence[tuple[int, ...]],
) -> list[tuple[int, ...]]:
    """Convert RGBA pixels to RGB if all alphas are opaque.

    Args:
        pixels: List of pixel tuples (RGB or RGBA)

    Returns:
        List of RGB tuples, converting RGBA to RGB if all alphas are opaque

    """
    # Check if we need alpha
    if not needs_alpha_channel(pixels):
        # Convert RGBA to RGB, keeping only opaque pixels
        rgb_pixels: list[tuple[int, ...]] = []
        for pixel in pixels:
            if len(pixel) == RGBA_COMPONENT_COUNT:
                r, g, b, a = pixel
                if a == MAX_COLOR_CHANNEL_VALUE:  # Only keep fully opaque pixels
                    rgb_pixels.append((r, g, b))
                else:
                    # Use magenta for transparent pixels
                    rgb_pixels.append(MAGENTA_TRANSPARENCY_KEY)
            else:
                rgb_pixels.append(pixel)
        return rgb_pixels
    # Keep as RGBA
    return list(pixels)


def convert_pixels_to_rgba_if_needed(
    pixels: Sequence[tuple[int, ...]],
) -> list[tuple[int, ...]]:
    """Convert RGB pixels to RGBA if needed for consistency.

    Args:
        pixels: List of pixel tuples (RGB or RGBA)

    Returns:
        List of RGBA tuples

    """
    rgba_pixels: list[tuple[int, ...]] = []
    for pixel in pixels:
        if len(pixel) == RGB_COMPONENT_COUNT:
            r, g, b = pixel
            if pixel == (255, 0, 255):
                # Transparency key - keep it opaque for proper handling
                rgba_pixels.append((r, g, b, 255))
            else:
                # Opaque color - set alpha to 255
                rgba_pixels.append((r, g, b, 255))
        else:
            rgba_pixels.append(pixel)
    return rgba_pixels


def lookup_pixel_char(
    pixel: tuple[int, ...],
    color_map: dict[tuple[int, ...], str],
    *,
    map_uses_alpha: bool,
) -> str:
    """Look up the character for a pixel in the color map.

    Handles RGBA/RGB normalization and magenta transparency.

    Returns:
        The character mapped to this pixel color.

    Raises:
        KeyError: If the pixel color is not found in the color map.

    """
    if len(pixel) == RGBA_COMPONENT_COUNT:
        return lookup_rgba_pixel_char(pixel, color_map, map_uses_alpha=map_uses_alpha)
    # RGB pixel - look up magenta in whichever format the color map uses
    if pixel == MAGENTA_TRANSPARENCY_KEY:
        return _lookup_magenta_char(color_map)
    if map_uses_alpha:
        # Try RGBA version first, then fall back to RGB
        lookup_rgba = (pixel[0], pixel[1], pixel[2], 255)
        if lookup_rgba in color_map:
            return color_map[lookup_rgba]
        if pixel in color_map:
            return color_map[pixel]
        raise KeyError(
            ERR_COLOR_NOT_FOUND_WITH_RGBA.format(pixel, lookup_rgba, list(color_map.keys())),
        )
    return lookup_in_map(pixel, color_map)


def lookup_rgba_pixel_char(
    pixel: tuple[int, ...],
    color_map: dict[tuple[int, ...], str],
    *,
    map_uses_alpha: bool,
) -> str:
    """Look up the character for an RGBA pixel in the color map.

    Returns:
        The character mapped to this RGBA pixel color.

    Raises:
        KeyError: If the pixel color is not found in the color map.

    """
    r, g, b, a = pixel
    # Magenta: look up in whichever format the color map uses
    if (r, g, b) == MAGENTA_TRANSPARENCY_KEY:
        return _lookup_magenta_char(color_map)
    if map_uses_alpha:
        # Map has some RGBA keys (magenta), but may have RGB keys for other colors.
        if a == MAX_COLOR_CHANNEL_VALUE:
            # Try RGB version first
            if (r, g, b) in color_map:
                return color_map[r, g, b]
            if (r, g, b, a) in color_map:
                return color_map[r, g, b, a]
            raise KeyError(
                ERR_COLOR_NOT_FOUND_WITH_RGBA.format(
                    (r, g, b),
                    (r, g, b, a),
                    list(color_map.keys()),
                ),
            )
        # Pixel has transparency, must use RGBA
        return lookup_in_map((r, g, b, a), color_map)
    # Non-alpha map: collapse to RGB for opaque, map transparent to magenta
    if a != MAX_COLOR_CHANNEL_VALUE:
        return _lookup_magenta_char(color_map)
    return lookup_in_map((r, g, b), color_map)


def _lookup_magenta_char(color_map: dict[tuple[int, ...], str]) -> str:
    """Look up magenta in the color map, trying both RGB and RGBA keys.

    Returns:
        The character mapped to magenta.

    Raises:
        KeyError: If magenta is not found in either format.
    """
    if (255, 0, 255, 255) in color_map:
        return color_map[255, 0, 255, 255]
    if (255, 0, 255) in color_map:
        return color_map[255, 0, 255]
    raise KeyError(
        ERR_COLOR_NOT_FOUND.format((255, 0, 255), list(color_map.keys())),
    )


def lookup_in_map(lookup: tuple[int, ...], color_map: dict[tuple[int, ...], str]) -> str:
    """Look up a color tuple in the color map.

    Returns:
        The character mapped to this color.

    Raises:
        KeyError: If the color is not found in the color map.

    """
    if lookup not in color_map:
        raise KeyError(
            ERR_COLOR_NOT_FOUND.format(lookup, list(color_map.keys())),
        )
    return color_map[lookup]


def normalize_pixel_for_color_map(pixel: tuple[int, ...], *, needs_alpha: bool) -> tuple[int, ...]:
    """Normalize a pixel tuple for use as a color map key.

    Returns:
        Normalized color tuple.

    """
    if len(pixel) == RGBA_COMPONENT_COUNT:
        r, g, b, a = pixel
        is_magenta = (r, g, b) == MAGENTA_TRANSPARENCY_KEY
        if needs_alpha:
            # RGBA mode: magenta is (255,0,255,255), others keep their alpha
            return (255, 0, 255, 255) if is_magenta else (r, g, b, a)
        # RGB/indexed mode: collapse to 3-tuple
        if is_magenta or a != MAX_COLOR_CHANNEL_VALUE:
            return MAGENTA_TRANSPARENCY_KEY
        return (r, g, b)
    # RGB pixel: promote magenta to RGBA only for alpha-mode sprites
    if needs_alpha and pixel == MAGENTA_TRANSPARENCY_KEY:
        return (255, 0, 255, 255)
    return pixel


def extract_pixel_colors(
    pixel_lines: list[str],
    width: int,
    height: int,
    color_map: dict[str, tuple[int, ...]],
) -> list[tuple[int, ...]]:
    """Extract pixel colors from pixel lines using the color map.

    Returns:
        List of color tuples.

    """
    pixels: list[tuple[int, ...]] = []
    for y, row in enumerate(pixel_lines):
        for x, char in enumerate(row):
            if x < width and y < height:
                color = color_map.get(char, (255, 0, 255))  # Default to magenta
                pixels.append(color)
            else:
                pixels.append((255, 0, 255))
    return pixels


def is_pixel_transparent(
    char: str,
    color_map: dict[str, tuple[int, ...]],
) -> bool:
    """Check if a pixel character represents a transparent pixel.

    A pixel is transparent if:
    - Its color is RGB magenta (255, 0, 255) -- the indexed transparency key
    - Its color is RGBA with alpha == 0 -- fully transparent per-pixel alpha
    - Its color is RGBA magenta (255, 0, 255, 255) -- magenta stored as RGBA
    - The character has no color map entry (defaults to magenta)

    Semi-transparent pixels (alpha 1-254) are treated as OPAQUE for bounding
    box purposes since they are visually present.

    Args:
        char: Single character from the pixel grid.
        color_map: Maps characters to RGB or RGBA color tuples.

    Returns:
        True if the pixel is fully transparent.

    """
    color = color_map.get(char, MAGENTA_TRANSPARENCY_KEY)
    if len(color) == RGBA_COMPONENT_COUNT:
        red, green, blue, alpha = color
        # Fully transparent per-pixel alpha
        if alpha == 0:
            return True
        # Magenta stored as RGBA (opaque magenta = transparency key)
        # Semi-transparent (alpha 1-254) or opaque non-magenta = visible
        return (red, green, blue) == MAGENTA_TRANSPARENCY_KEY and alpha == MAX_COLOR_CHANNEL_VALUE
    # RGB: only magenta is transparent
    return color == MAGENTA_TRANSPARENCY_KEY


def is_color_transparent(color: tuple[int, ...]) -> bool:
    """Check if a color tuple represents a transparent pixel.

    Same logic as is_pixel_transparent but operates on resolved color
    tuples rather than character lookups. Useful when working with raw
    pixel data from surfaces.

    Args:
        color: RGB or RGBA color tuple.

    Returns:
        True if the color is fully transparent.

    """
    if len(color) == RGBA_COMPONENT_COUNT:
        red, green, blue, alpha = color
        if alpha == 0:
            return True
        return (red, green, blue) == MAGENTA_TRANSPARENCY_KEY and alpha == MAX_COLOR_CHANNEL_VALUE
    return color == MAGENTA_TRANSPARENCY_KEY


def compute_bounding_box_from_pixels(
    pixels: Sequence[tuple[int, ...]],
    width: int,
    height: int,
) -> dict[str, int] | None:
    """Compute the smallest bounding box from a flat list of pixel color tuples.

    Works directly on pixel data (RGB/RGBA tuples) without needing a
    color map. Suitable for use in the save pipeline where pixel data
    is already resolved.

    Args:
        pixels: Flat list of color tuples, row-major order.
        width: Frame width in pixels.
        height: Frame height in pixels.

    Returns:
        Dict with offset_x, offset_y, width, height keys, or None if
        the frame is fully transparent.

    """
    expected_pixel_count = width * height
    min_x = float('inf')
    min_y = float('inf')
    max_x = float('-inf')
    max_y = float('-inf')

    for index, color in enumerate(pixels[:expected_pixel_count]):
        if not is_color_transparent(color):
            x = index % width
            y = index // width
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)

    if min_x == float('inf'):
        return None

    return {
        'offset_x': int(min_x),
        'offset_y': int(min_y),
        'width': int(max_x - min_x + 1),
        'height': int(max_y - min_y + 1),
    }


def compute_bounding_box(
    pixel_lines: list[str],
    color_map: dict[str, tuple[int, ...]],
) -> dict[str, int] | None:
    """Compute the smallest bounding box enclosing all opaque pixels.

    Iterates through the pixel grid and finds the tightest rectangle
    that contains all non-transparent pixels.

    Args:
        pixel_lines: List of pixel row strings from a TOML sprite frame.
        color_map: Maps characters to RGB or RGBA color tuples.

    Returns:
        Dict with offset_x, offset_y, width, height keys matching the
        hitbox TOML format, or None if the frame is fully transparent.

    """
    min_x = float('inf')
    min_y = float('inf')
    max_x = float('-inf')
    max_y = float('-inf')

    for y, row in enumerate(pixel_lines):
        for x, char in enumerate(row):
            if not is_pixel_transparent(char, color_map):
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)

    if min_x == float('inf'):
        # Fully transparent frame -- no opaque pixels found
        return None

    return {
        'offset_x': int(min_x),
        'offset_y': int(min_y),
        'width': int(max_x - min_x + 1),
        'height': int(max_y - min_y + 1),
    }


def compute_envelope_bounding_box(
    bounding_boxes: list[dict[str, int]],
) -> dict[str, int] | None:
    """Compute the union envelope of multiple bounding boxes.

    Returns the smallest rectangle that encompasses all provided
    bounding boxes. Useful for computing a sprite-level hitbox
    that covers all animation frames.

    Args:
        bounding_boxes: List of per-frame bounding box dicts, each with
            offset_x, offset_y, width, height keys.

    Returns:
        Union bounding box dict, or None if the input list is empty.

    """
    if not bounding_boxes:
        return None

    envelope_min_x = min(bounding_box['offset_x'] for bounding_box in bounding_boxes)
    envelope_min_y = min(bounding_box['offset_y'] for bounding_box in bounding_boxes)
    envelope_max_x = max(
        bounding_box['offset_x'] + bounding_box['width'] for bounding_box in bounding_boxes
    )
    envelope_max_y = max(
        bounding_box['offset_y'] + bounding_box['height'] for bounding_box in bounding_boxes
    )

    return {
        'offset_x': envelope_min_x,
        'offset_y': envelope_min_y,
        'width': envelope_max_x - envelope_min_x,
        'height': envelope_max_y - envelope_min_y,
    }


def create_alpha_surface(
    width: int,
    height: int,
    pixel_lines: list[str],
    color_map: dict[str, tuple[int, ...]],
) -> pygame.Surface:
    """Create a per-pixel alpha surface from TOML pixel data.

    Returns:
        pygame.Surface with SRCALPHA.

    """
    surface = pygame.Surface((width, height), pygame.SRCALPHA)
    surface.fill((255, 0, 255, 0))  # Transparent background

    for y, row in enumerate(pixel_lines):
        for x, char in enumerate(row):
            if x < width and y < height:
                color = color_map.get(char, (255, 0, 255))  # Default to magenta
                # Ensure color is RGBA for alpha surface
                if len(color) == RGB_COMPONENT_COUNT:
                    color = (
                        color[0],
                        color[1],
                        color[2],
                        MAX_COLOR_CHANNEL_VALUE,
                    )  # Add full alpha
                elif len(color) == RGBA_COMPONENT_COUNT and color == (255, 0, 255, 255):
                    color = (255, 0, 255, 255)  # Keep magenta opaque for transparency key
                surface.set_at((x, y), color)
    return surface


def create_indexed_surface(
    width: int,
    height: int,
    pixel_lines: list[str],
    color_map: dict[str, tuple[int, ...]],
) -> pygame.Surface:
    """Create an RGB indexed transparency surface from TOML pixel data.

    Returns:
        pygame.Surface with magenta as transparency key.

    """
    surface = pygame.Surface((width, height))
    surface.fill((255, 0, 255))  # Magenta background for transparency

    for y, row in enumerate(pixel_lines):
        for x, char in enumerate(row):
            if x < width and y < height:
                color = color_map.get(char, (255, 0, 255))  # Default to magenta
                # Convert to RGB for indexed transparency
                if len(color) == RGBA_COMPONENT_COUNT:
                    r, g, b, a = color
                    if a == MAX_COLOR_CHANNEL_VALUE:  # Only keep fully opaque pixels
                        surface.set_at((x, y), (r, g, b))
                    else:
                        surface.set_at((x, y), (255, 0, 255))  # Transparent
                else:
                    surface.set_at((x, y), color)
    return surface
