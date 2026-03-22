"""Pixel operations and ASCII rendering for the Bitmappy editor."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from glitchygames.color import MAX_COLOR_CHANNEL_VALUE, RGBA_COMPONENT_COUNT
from glitchygames.sprites.animated import SpriteFrame

from .constants import LOG

if TYPE_CHECKING:
    from glitchygames.tools.ascii_renderer import ASCIIRenderer


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


def render_frames_side_by_side(
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
        ascii_output = render_frame_to_ascii(frame, renderer)
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
        LOG.debug(f'render_frame_to_ascii: Found {len(unique_colors)} unique colors')
        LOG.debug(
            f'render_frame_to_ascii: First unique color: {next(iter(unique_colors.keys()))} ->'
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


def render_frame_to_ascii(frame: SpriteFrame, renderer: ASCIIRenderer) -> str:
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
