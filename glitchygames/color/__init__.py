"""Color utilities for glitchygames."""

import colorsys
from typing import Dict, List, Tuple, Union

# Define some common colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
CYAN = (0, 255, 255)
MAGENTA = (255, 0, 255)
GRAY = (128, 128, 128)
LIGHT_GRAY = (192, 192, 192)
DARK_GRAY = (64, 64, 64)

# Define color palettes
PALETTE_GRAYSCALE = [
    (0, 0, 0),       # Black
    (64, 64, 64),    # Dark Gray
    (128, 128, 128), # Gray
    (192, 192, 192), # Light Gray
    (255, 255, 255), # White
]

PALETTE_RGB = [
    (255, 0, 0),     # Red
    (0, 255, 0),     # Green
    (0, 0, 255),     # Blue
]

PALETTE_RAINBOW = [
    (255, 0, 0),     # Red
    (255, 127, 0),   # Orange
    (255, 255, 0),   # Yellow
    (0, 255, 0),     # Green
    (0, 0, 255),     # Blue
    (75, 0, 130),    # Indigo
    (148, 0, 211),   # Violet
]

def rgb_to_hsv(rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
    """Convert RGB color to HSV.
    
    Args:
        rgb: RGB color tuple (0-255)
        
    Returns:
        HSV color tuple (0-1)
    """
    r, g, b = rgb
    return colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)

def hsv_to_rgb(hsv: Tuple[float, float, float]) -> Tuple[int, int, int]:
    """Convert HSV color to RGB.
    
    Args:
        hsv: HSV color tuple (0-1)
        
    Returns:
        RGB color tuple (0-255)
    """
    h, s, v = hsv
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))

def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    """Convert RGB color to hex string.
    
    Args:
        rgb: RGB color tuple (0-255)
        
    Returns:
        Hex color string (#RRGGBB)
    """
    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"

def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex color string to RGB.
    
    Args:
        hex_color: Hex color string (#RRGGBB or RRGGBB)
        
    Returns:
        RGB color tuple (0-255)
    """
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def interpolate(color1: Tuple[int, int, int], color2: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    """Interpolate between two colors.
    
    Args:
        color1: First RGB color tuple (0-255)
        color2: Second RGB color tuple (0-255)
        factor: Interpolation factor (0-1)
        
    Returns:
        Interpolated RGB color tuple (0-255)
    """
    r1, g1, b1 = color1
    r2, g2, b2 = color2
    r = int(r1 + (r2 - r1) * factor)
    g = int(g1 + (g2 - g1) * factor)
    b = int(b1 + (b2 - b1) * factor)
    return (r, g, b)

def generate_palette(start_color: Tuple[int, int, int], end_color: Tuple[int, int, int], steps: int) -> List[Tuple[int, int, int]]:
    """Generate a color palette by interpolating between two colors.
    
    Args:
        start_color: Starting RGB color tuple (0-255)
        end_color: Ending RGB color tuple (0-255)
        steps: Number of colors to generate
        
    Returns:
        List of RGB color tuples
    """
    palette = []
    for i in range(steps):
        factor = i / (steps - 1) if steps > 1 else 0
        palette.append(interpolate(start_color, end_color, factor))
    return palette

def generate_rainbow_palette(steps: int) -> List[Tuple[int, int, int]]:
    """Generate a rainbow color palette.
    
    Args:
        steps: Number of colors to generate
        
    Returns:
        List of RGB color tuples
    """
    palette = []
    for i in range(steps):
        h = i / steps
        r, g, b = colorsys.hsv_to_rgb(h, 1.0, 1.0)
        palette.append((int(r * 255), int(g * 255), int(b * 255)))
    return palette

def darken(color: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    """Darken a color.
    
    Args:
        color: RGB color tuple (0-255)
        factor: Darkening factor (0-1)
        
    Returns:
        Darkened RGB color tuple (0-255)
    """
    r, g, b = color
    return (
        int(r * (1 - factor)),
        int(g * (1 - factor)),
        int(b * (1 - factor))
    )

def lighten(color: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    """Lighten a color.
    
    Args:
        color: RGB color tuple (0-255)
        factor: Lightening factor (0-1)
        
    Returns:
        Lightened RGB color tuple (0-255)
    """
    r, g, b = color
    return (
        int(r + (255 - r) * factor),
        int(g + (255 - g) * factor),
        int(b + (255 - b) * factor)
    )