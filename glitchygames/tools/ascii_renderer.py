#!/usr/bin/env python3
"""ASCII renderer for BitmappySprite colorized terminal output.

This module provides ASCII rendering capabilities for displaying
BitmappySprite objects with colorized terminal output.
"""

from typing import Any, cast

from glitchygames.color import ALPHA_TRANSPARENCY_THRESHOLD, MAX_COLOR_CHANNEL_VALUE

from .terminal_utils import ColorMapper, TerminalDetector


class ASCIIRenderer:
    """Renders BitmappySprite objects as colorized ASCII art."""

    def __init__(self) -> None:
        """Initialize the ASCII renderer with color mapping and terminal detection."""
        self.color_mapper = ColorMapper()
        self.detector = TerminalDetector()
        self._render_cache: dict[str, str] = {}

    def _get_transparency_char(self) -> str:
        """Get character for transparent pixels.

        Returns:
            str: Character to use for transparent pixels

        """
        if self.detector.has_color_support():
            return '█'  # Full block for transparency
        return ' '  # Space for monochrome

    def _get_pixel_char(self, char: str) -> str:
        """Get ASCII character for pixel.

        Args:
            char: Character from sprite pixels

        Returns:
            str: ASCII character to display

        """
        # Always render pixels as a solid block; color comes from the pixel's mapped RGB
        return '█'

    def extract_colors_from_toml(
        self, toml_data: dict[str, Any],
    ) -> dict[str, tuple[int, int, int, int]]:
        """Extract color mappings from TOML data with alpha channel support.

        Args:
            toml_data: Parsed TOML data

        Returns:
            Dict mapping characters to RGBA tuples

        """
        colors: dict[str, tuple[int, int, int, int]] = {}

        if 'colors' in toml_data:
            colors_section: dict[str, Any] = toml_data['colors']

            for key, value in colors_section.items():
                if (
                    isinstance(value, dict)
                    and 'red' in value
                    and 'green' in value
                    and 'blue' in value
                ):
                    color_data = cast('dict[str, int]', value)
                    r: int = color_data['red']
                    g: int = color_data['green']
                    b: int = color_data['blue']

                    # Check for magenta transparency (255, 0, 255) = alpha 0
                    if r == MAX_COLOR_CHANNEL_VALUE and g == 0 and b == MAX_COLOR_CHANNEL_VALUE:
                        a: int = 0  # Fully transparent
                    else:
                        # Default alpha to 255 (opaque) if not specified
                        a = color_data.get('alpha', color_data.get('a', 255))

                    colors[key] = (r, g, b, a)

        return colors

    def extract_pixels_from_toml(self, toml_data: dict[str, Any]) -> str | None:
        """Extract pixels string from TOML data.

        Args:
            toml_data: Parsed TOML data

        Returns:
            str: Pixels string or None if not found

        """
        # Check for static sprite pixels
        if 'sprite' in toml_data and 'pixels' in toml_data['sprite']:
            return toml_data['sprite']['pixels']

        # Check for animated sprite pixels (first frame)
        if 'animation' in toml_data and len(toml_data['animation']) > 0:
            first_anim = toml_data['animation'][0]
            if 'frame' in first_anim and len(first_anim['frame']) > 0:
                first_frame = first_anim['frame'][0]
                if 'pixels' in first_frame:
                    return first_frame['pixels']

        return None

    def colorize_pixels(self, pixels: str, colors: dict[str, tuple[int, int, int, int]]) -> str:
        """Colorize pixels string with terminal colors and alpha channel support.

        Args:
            pixels: Raw pixels string
            colors: Color mapping dictionary with RGBA tuples

        Returns:
            str: Colorized pixels string

        """
        if not self.detector.has_color_support():
            return pixels

        lines = pixels.strip().split('\n')
        colorized_lines: list[str] = []

        for line in lines:
            colorized_line = ''
            for char in line:
                if char in colors:
                    r, g, b, a = colors[char]

                    # Handle alpha transparency
                    if a == 0:
                        # Fully transparent - draw as light grey for contrast
                        display_char = self._get_transparency_char()
                        # Use light grey background (192, 192, 192) for better contrast
                        color_code = self.color_mapper.get_color_code(192, 192, 192)
                    elif a < MAX_COLOR_CHANNEL_VALUE:
                        # Semi-transparent - use a lighter version or special character
                        if a < ALPHA_TRANSPARENCY_THRESHOLD:  # Very transparent
                            display_char = self._get_transparency_char()
                        else:  # Semi-transparent
                            display_char = self._get_pixel_char(char)

                        # Adjust color intensity based on alpha
                        adjusted_r = int(r * (a / 255))
                        adjusted_g = int(g * (a / 255))
                        adjusted_b = int(b * (a / 255))
                        color_code = self.color_mapper.get_color_code(
                            adjusted_r, adjusted_g, adjusted_b,
                        )
                    else:
                        # Fully opaque
                        color_code = self.color_mapper.get_color_code(r, g, b)
                        display_char = self._get_pixel_char(char)

                    reset_code = self.color_mapper.get_reset_code()
                    colorized_line += f'{color_code}{display_char}{reset_code}'
                else:
                    colorized_line += self._colorize_non_mapped_char(char, colors)

            colorized_lines.append(colorized_line)

        return '\n'.join(colorized_lines)

    def _colorize_non_mapped_char(
        self, char: str, colors: dict[str, tuple[int, int, int, int]],
    ) -> str:
        """Colorize a character not found in the color map.

        Handles transparency (magenta) detection for '.' characters
        and passes through unknown characters unchanged.

        Args:
            char: The character to colorize
            colors: Color mapping dictionary with RGBA tuples

        Returns:
            str: Colorized character string or raw character

        """
        # Handle transparency (magenta) or unknown characters
        if char == '.' and any(rgb[:3] == (255, 0, 255) for rgb in colors.values()):
            # This is transparency - draw as light grey for contrast
            display_char = self._get_transparency_char()
            # Use light grey background (192, 192, 192) for better contrast
            color_code = self.color_mapper.get_color_code(192, 192, 192)
            reset_code = self.color_mapper.get_reset_code()
            return f'{color_code}{display_char}{reset_code}'
        return char

    def _colorize_colors_section(self, colors: dict[str, tuple[int, int, int]]) -> str:
        """Colorize the colors section output using proper Bitmappy format.

        Args:
            colors: Color mapping dictionary

        Returns:
            str: Colorized colors section in proper Bitmappy format

        """
        if not self.detector.has_color_support():
            # Return plain TOML format using proper Bitmappy structure
            lines = ['[colors]']
            for char, (r, g, b) in colors.items():
                lines.extend([
                    f'[colors."{char}"]',
                    f'red = {r}',
                    f'green = {g}',
                    f'blue = {b}',
                    '',
                ])
            return '\n'.join(lines)

        lines = ['[colors]']
        for char, (r, g, b) in colors.items():
            color_code = self.color_mapper.get_color_code(r, g, b)
            reset_code = self.color_mapper.get_reset_code()

            # Colorize the character key
            colorized_char = f'{color_code}{char}{reset_code}'
            lines.extend([
                f'[colors."{colorized_char}"]',
                f'red = {r}',
                f'green = {g}',
                f'blue = {b}',
                '',
            ])

        return '\n'.join(lines)

    def render_sprite(self, sprite_data: dict[str, Any]) -> str:
        """Render a sprite as colorized ASCII.

        Args:
            sprite_data: TOML data for the sprite

        Returns:
            str: Colorized ASCII representation

        """
        # Create cache key
        cache_key = str(hash(str(sprite_data)))
        if cache_key in self._render_cache:
            return self._render_cache[cache_key]

        # Extract data
        colors = self.extract_colors_from_toml(sprite_data)
        pixels = self.extract_pixels_from_toml(sprite_data)

        if not pixels:
            return 'No pixels data found'

        # Build output
        output_lines: list[str] = []

        # Add sprite section
        if 'sprite' in sprite_data:
            sprite_section = sprite_data['sprite']
            output_lines.append('[sprite]')

            if 'name' in sprite_section:
                output_lines.append(f'name = "{sprite_section["name"]}"')

            if pixels:
                output_lines.append('pixels = """')
                colorized_pixels = self.colorize_pixels(pixels, colors)
                output_lines.extend((colorized_pixels, '"""'))

        # Skip colors section - just show the colorized pixels

        result = '\n'.join(output_lines)

        # Cache the result
        self._render_cache[cache_key] = result
        return result

    def clear_cache(self) -> None:
        """Clear the render cache."""
        self._render_cache.clear()
        self.color_mapper.clear_cache()
