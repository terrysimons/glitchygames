#!/usr/bin/env python3
"""
ASCII renderer for BitmappySprite colorized terminal output.

This module provides ASCII rendering capabilities for displaying
BitmappySprite objects with colorized terminal output.
"""

import toml
from typing import Dict, Tuple, Optional, Any
from .terminal_utils import ColorMapper, TerminalDetector


class ASCIIRenderer:
    """Renders BitmappySprite objects as colorized ASCII art."""
    
    def __init__(self):
        self.color_mapper = ColorMapper()
        self.detector = TerminalDetector()
        self._render_cache: Dict[str, str] = {}
    
    def _get_transparency_char(self) -> str:
        """Get character for transparent pixels.
        
        Returns:
            str: Character to use for transparent pixels
        """
        if self.detector.has_color_support():
            return '█'  # Full block for transparency
        else:
            return ' '  # Space for monochrome
    
    def _get_pixel_char(self, char: str) -> str:
        """Get ASCII character for pixel.
        
        Args:
            char: Character from sprite pixels
            
        Returns:
            str: ASCII character to display
        """
        # Use the original character for most pixels
        # This preserves the sprite's character mapping
        return char
    
    def _extract_colors_from_toml(self, toml_data: Dict[str, Any]) -> Dict[str, Tuple[int, int, int, int]]:
        """Extract color mappings from TOML data with alpha channel support.
        
        Args:
            toml_data: Parsed TOML data
            
        Returns:
            Dict mapping characters to RGBA tuples
        """
        colors = {}
        
        if 'colors' in toml_data:
            colors_section = toml_data['colors']
            
            for key, value in colors_section.items():
                if isinstance(value, dict) and 'red' in value and 'green' in value and 'blue' in value:
                    r = int(value['red'])
                    g = int(value['green'])
                    b = int(value['blue'])
                    
                    # Check for magenta transparency (255, 0, 255) = alpha 0
                    if r == 255 and g == 0 and b == 255:
                        a = 0  # Fully transparent
                    else:
                        # Default alpha to 255 (opaque) if not specified
                        a = int(value.get('alpha', value.get('a', 255)))
                    
                    colors[key] = (r, g, b, a)
        
        return colors
    
    def _extract_pixels_from_toml(self, toml_data: Dict[str, Any]) -> Optional[str]:
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
    
    def _colorize_pixels(self, pixels: str, colors: Dict[str, Tuple[int, int, int, int]]) -> str:
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
        colorized_lines = []
        
        for line in lines:
            colorized_line = ""
            for char in line:
                if char in colors:
                    r, g, b, a = colors[char]
                    
                    # Handle alpha transparency
                    if a == 0:
                        # Fully transparent - draw as light grey for contrast
                        display_char = self._get_transparency_char()
                        # Use light grey background (192, 192, 192) for better contrast
                        color_code = self.color_mapper.get_color_code(192, 192, 192)
                    elif a < 255:
                        # Semi-transparent - use a lighter version or special character
                        if a < 128:  # Very transparent
                            display_char = self._get_transparency_char()
                        else:  # Semi-transparent
                            display_char = self._get_pixel_char(char)
                        
                        # Adjust color intensity based on alpha
                        adjusted_r = int(r * (a / 255))
                        adjusted_g = int(g * (a / 255))
                        adjusted_b = int(b * (a / 255))
                        color_code = self.color_mapper.get_color_code(adjusted_r, adjusted_g, adjusted_b)
                    else:
                        # Fully opaque
                        color_code = self.color_mapper.get_color_code(r, g, b)
                        display_char = self._get_pixel_char(char)
                    
                    reset_code = self.color_mapper.get_reset_code()
                    colorized_line += f"{color_code}{display_char}{reset_code}"
                else:
                    # Handle transparency (magenta) or unknown characters
                    if char == '.':
                        # Check if this is transparency
                        if any(rgb[:3] == (255, 0, 255) for rgb in colors.values()):
                            # This is transparency - draw as light grey for contrast
                            display_char = self._get_transparency_char()
                            # Use light grey background (192, 192, 192) for better contrast
                            color_code = self.color_mapper.get_color_code(192, 192, 192)
                            reset_code = self.color_mapper.get_reset_code()
                            colorized_line += f"{color_code}{display_char}{reset_code}"
                        else:
                            colorized_line += char
                    else:
                        colorized_line += char
            
            colorized_lines.append(colorized_line)
        
        return '\n'.join(colorized_lines)
    
    def _colorize_colors_section(self, colors: Dict[str, Tuple[int, int, int]]) -> str:
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
                lines.append(f'[colors."{char}"]')
                lines.append(f'red = {r}')
                lines.append(f'green = {g}')
                lines.append(f'blue = {b}')
                lines.append('')
            return '\n'.join(lines)
        
        lines = ['[colors]']
        for char, (r, g, b) in colors.items():
            color_code = self.color_mapper.get_color_code(r, g, b)
            reset_code = self.color_mapper.get_reset_code()
            
            # Colorize the character key
            colorized_char = f"{color_code}{char}{reset_code}"
            lines.append(f'[colors."{colorized_char}"]')
            lines.append(f'red = {r}')
            lines.append(f'green = {g}')
            lines.append(f'blue = {b}')
            lines.append('')
        
        return '\n'.join(lines)
    
    def render_sprite(self, sprite_data: Dict[str, Any]) -> str:
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
        colors = self._extract_colors_from_toml(sprite_data)
        pixels = self._extract_pixels_from_toml(sprite_data)
        
        if not pixels:
            return "No pixels data found"
        
        # Build output
        output_lines = []
        
        # Add sprite section
        if 'sprite' in sprite_data:
            sprite_section = sprite_data['sprite']
            output_lines.append('[sprite]')
            
            if 'name' in sprite_section:
                output_lines.append(f'name = "{sprite_section["name"]}"')
            
            if pixels:
                output_lines.append('pixels = """')
                colorized_pixels = self._colorize_pixels(pixels, colors)
                output_lines.append(colorized_pixels)
                output_lines.append('"""')
        
        # Skip colors section - just show the colorized pixels
        
        result = '\n'.join(output_lines)
        
        # Cache the result
        self._render_cache[cache_key] = result
        return result
    
    def clear_cache(self):
        """Clear the render cache."""
        self._render_cache.clear()
        self.color_mapper.clear_cache()
