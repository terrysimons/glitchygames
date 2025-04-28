"""Color utilities for glitchygames."""

import colorsys
from typing import Dict, List, Tuple, Union

# Type aliases
RGB = Tuple[int, int, int]
RGBA = Tuple[int, int, int, int]
Color = Union[RGB, RGBA]

# Common color palettes
PICO8_PALETTE = {
    'black': (0, 0, 0),
    'dark_blue': (29, 43, 83),
    'dark_purple': (126, 37, 83),
    'dark_green': (0, 135, 81),
    'brown': (171, 82, 54),
    'dark_gray': (95, 87, 79),
    'light_gray': (194, 195, 199),
    'white': (255, 241, 232),
    'red': (255, 0, 77),
    'orange': (255, 163, 0),
    'yellow': (255, 236, 39),
    'green': (0, 228, 54),
    'blue': (41, 173, 255),
    'lavender': (131, 118, 156),
    'pink': (255, 119, 168),
    'light_peach': (255, 204, 170),
}

# Web safe colors
WEB_SAFE = {
    'aqua': (0, 255, 255),
    'black': (0, 0, 0),
    'blue': (0, 0, 255),
    'fuchsia': (255, 0, 255),
    'gray': (128, 128, 128),
    'green': (0, 128, 0),
    'lime': (0, 255, 0),
    'maroon': (128, 0, 0),
    'navy': (0, 0, 128),
    'olive': (128, 128, 0),
    'purple': (128, 0, 128),
    'red': (255, 0, 0),
    'silver': (192, 192, 192),
    'teal': (0, 128, 128),
    'white': (255, 255, 255),
    'yellow': (255, 255, 0),
}

def rgb_to_hsv(rgb: RGB) -> Tuple[float, float, float]:
    """Convert RGB color to HSV.
    
    Args:
        rgb: RGB color tuple (0-255)
        
    Returns:
        HSV color tuple (0-1)
    """
    r, g, b = rgb
    return colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    
def hsv_to_rgb(hsv: Tuple[float, float, float]) -> RGB:
    """Convert HSV color to RGB.
    
    Args:
        hsv: HSV color tuple (0-1)
        
    Returns:
        RGB color tuple (0-255)
    """
    h, s, v = hsv
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))
    
def rgb_to_hex(rgb: RGB) -> str:
    """Convert RGB color to hex string.
    
    Args:
        rgb: RGB color tuple (0-255)
        
    Returns:
        Hex color string (#RRGGBB)
    """
    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"
    
def hex_to_rgb(hex_color: str) -> RGB:
    """Convert hex color string to RGB.
    
    Args:
        hex_color: Hex color string (#RRGGBB or #RGB)
        
    Returns:
        RGB color tuple (0-255)
    """
    hex_color = hex_color.lstrip('#')
    
    if len(hex_color) == 3:
        hex_color = ''.join(c + c for c in hex_color)
        
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
def blend_colors(color1: RGB, color2: RGB, factor: float = 0.5) -> RGB:
    """Blend two colors together.
    
    Args:
        color1: First RGB color tuple
        color2: Second RGB color tuple
        factor: Blend factor (0.0 = color1, 1.0 = color2)
        
    Returns:
        Blended RGB color tuple
    """
    r1, g1, b1 = color1
    r2, g2, b2 = color2
    
    r = int(r1 + (r2 - r1) * factor)
    g = int(g1 + (g2 - g1) * factor)
    b = int(b1 + (b2 - b1) * factor)
    
    return (r, g, b)
    
def generate_palette(base_color: RGB, count: int = 5, 
                     saturation: float = 1.0, 
                     value: float = 1.0) -> List[RGB]:
    """Generate a color palette based on a base color.
    
    Args:
        base_color: Base RGB color
        count: Number of colors to generate
        saturation: Saturation value (0-1)
        value: Value/brightness (0-1)
        
    Returns:
        List of RGB color tuples
    """
    h, _, _ = rgb_to_hsv(base_color)
    palette = []
    
    for i in range(count):
        # Rotate hue around the color wheel
        new_h = (h + i / count) % 1.0
        palette.append(hsv_to_rgb((new_h, saturation, value)))
        
    return palette