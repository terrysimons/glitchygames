#!/usr/bin/env python3
"""
Terminal utilities for colorized ASCII output.

This module provides terminal capability detection and color mapping
for the BitmappySprite ASCII renderer.
"""

import os
import sys
from typing import Dict, Tuple, Optional


class TerminalCapability:
    """Terminal color capability levels."""
    MONOCHROME = "mono"
    COLOR_8 = "8_color"
    COLOR_256 = "256_color"
    TRUE_COLOR = "true_color"


class TerminalDetector:
    """Detects terminal color capabilities."""
    
    def __init__(self):
        self._capability = None
        self._color_support = None
    
    def detect_capability(self) -> str:
        """Detect terminal color capability.
        
        Returns:
            str: Terminal capability level
        """
        if self._capability is not None:
            return self._capability
            
        # Check environment variables
        term = os.environ.get('TERM', '').lower()
        colorterm = os.environ.get('COLORTERM', '').lower()
        
        # Check for true color support
        if any(term in ['truecolor', '24bit', 'direct'] for term in [term, colorterm]):
            self._capability = TerminalCapability.TRUE_COLOR
        elif '256' in colorterm or '256color' in term:
            self._capability = TerminalCapability.COLOR_256
        elif any(term in ['xterm', 'screen', 'tmux', 'rxvt'] for term in [term]):
            self._capability = TerminalCapability.COLOR_256
        elif any(term in ['linux', 'vt100', 'vt220'] for term in [term]):
            self._capability = TerminalCapability.COLOR_8
        else:
            # Default to 8-color for most terminals
            self._capability = TerminalCapability.COLOR_8
            
        return self._capability
    
    def has_color_support(self) -> bool:
        """Check if terminal supports colors.
        
        Returns:
            bool: True if colors are supported
        """
        if self._color_support is not None:
            return self._color_support
            
        # Check if stdout is a TTY
        if not sys.stdout.isatty():
            self._color_support = False
            return False
            
        # Check for NO_COLOR environment variable
        if os.environ.get('NO_COLOR'):
            self._color_support = False
            return False
            
        # Check capability
        capability = self.detect_capability()
        self._color_support = capability != TerminalCapability.MONOCHROME
        return self._color_support


class ColorMapper:
    """Maps RGB colors to terminal color codes."""
    
    def __init__(self):
        self.detector = TerminalDetector()
        self._color_cache: Dict[Tuple[int, int, int], str] = {}
        self._capability = None
    
    def _get_capability(self) -> str:
        """Get terminal capability, with caching."""
        if self._capability is None:
            self._capability = self.detector.detect_capability()
        return self._capability
    
    def _rgb_to_8_color(self, r: int, g: int, b: int) -> str:
        """Convert RGB to 8-color terminal code."""
        # Map to closest 8-color palette
        if r < 128 and g < 128 and b < 128:
            return '\033[30m'  # Black
        elif r >= 128 and g < 128 and b < 128:
            return '\033[31m'  # Red
        elif r < 128 and g >= 128 and b < 128:
            return '\033[32m'  # Green
        elif r >= 128 and g >= 128 and b < 128:
            return '\033[33m'  # Yellow
        elif r < 128 and g < 128 and b >= 128:
            return '\033[34m'  # Blue
        elif r >= 128 and g < 128 and b >= 128:
            return '\033[35m'  # Magenta
        elif r < 128 and g >= 128 and b >= 128:
            return '\033[36m'  # Cyan
        else:
            return '\033[37m'  # White
    
    def _rgb_to_256_color(self, r: int, g: int, b: int) -> str:
        """Convert RGB to 256-color terminal code."""
        # Use 6x6x6 color cube (216 colors) + 16 basic colors
        if r == g == b and r < 8:
            # Grayscale ramp
            gray_index = 232 + int((r / 255) * 23)
            return f'\033[38;5;{gray_index}m'
        elif r == g == b and r >= 8:
            # Extended grayscale
            gray_index = 232 + int((r / 255) * 23)
            return f'\033[38;5;{gray_index}m'
        else:
            # Color cube
            r_index = int((r / 255) * 5)
            g_index = int((g / 255) * 5)
            b_index = int((b / 255) * 5)
            color_index = 16 + (r_index * 36) + (g_index * 6) + b_index
            return f'\033[38;5;{color_index}m'
    
    def _rgb_to_true_color(self, r: int, g: int, b: int) -> str:
        """Convert RGB to true color terminal code."""
        return f'\033[38;2;{r};{g};{b}m'
    
    def get_color_code(self, r: int, g: int, b: int) -> str:
        """Get terminal color code for RGB color.
        
        Args:
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)
            
        Returns:
            str: Terminal color escape sequence
        """
        color_key = (r, g, b)
        
        # Check cache first
        if color_key in self._color_cache:
            return self._color_cache[color_key]
        
        # Check if colors are supported
        if not self.detector.has_color_support():
            self._color_cache[color_key] = ''
            return ''
        
        # Generate color code based on capability
        capability = self._get_capability()
        
        if capability == TerminalCapability.TRUE_COLOR:
            color_code = self._rgb_to_true_color(r, g, b)
        elif capability == TerminalCapability.COLOR_256:
            color_code = self._rgb_to_256_color(r, g, b)
        elif capability == TerminalCapability.COLOR_8:
            color_code = self._rgb_to_8_color(r, g, b)
        else:
            color_code = ''
        
        # Cache the result
        self._color_cache[color_key] = color_code
        return color_code
    
    def get_reset_code(self) -> str:
        """Get terminal reset code.
        
        Returns:
            str: Reset escape sequence
        """
        if not self.detector.has_color_support():
            return ''
        return '\033[0m'
    
    def clear_cache(self):
        """Clear the color cache."""
        self._color_cache.clear()
        self._capability = None
