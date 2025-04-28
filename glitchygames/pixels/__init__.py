"""Pixel manipulation utilities for glitchygames."""

from typing import List, Tuple

import pygame

def rgb_to_565(r: int, g: int, b: int) -> int:
    """Convert RGB color to 16-bit RGB565 format.
    
    Args:
        r: Red component (0-255)
        g: Green component (0-255)
        b: Blue component (0-255)
        
    Returns:
        16-bit RGB565 color value
    """
    r = (r >> 3) & 0x1F  # 5 bits
    g = (g >> 2) & 0x3F  # 6 bits
    b = (b >> 3) & 0x1F  # 5 bits
    
    return (r << 11) | (g << 5) | b
    
def rgb565_to_rgb(color: int) -> Tuple[int, int, int]:
    """Convert 16-bit RGB565 color to RGB.
    
    Args:
        color: 16-bit RGB565 color value
        
    Returns:
        RGB color tuple (0-255)
    """
    r = ((color >> 11) & 0x1F) << 3
    g = ((color >> 5) & 0x3F) << 2
    b = (color & 0x1F) << 3
    
    # Add back some of the lost precision
    r |= r >> 5
    g |= g >> 6
    b |= b >> 5
    
    return (r, g, b)
    
def surface_to_rgb565(surface: pygame.Surface) -> List[int]:
    """Convert a pygame surface to RGB565 pixel data.
    
    Args:
        surface: Pygame surface
        
    Returns:
        List of 16-bit RGB565 color values
    """
    width, height = surface.get_size()
    pixels = []
    
    for y in range(height):
        for x in range(width):
            r, g, b, _ = surface.get_at((x, y))
            pixels.append(rgb_to_565(r, g, b))
            
    return pixels
    
def rgb565_to_surface(pixels: List[int], width: int, height: int) -> pygame.Surface:
    """Convert RGB565 pixel data to a pygame surface.
    
    Args:
        pixels: List of 16-bit RGB565 color values
        width: Surface width
        height: Surface height
        
    Returns:
        Pygame surface
    """
    surface = pygame.Surface((width, height))
    
    for y in range(height):
        for x in range(width):
            index = y * width + x
            if index < len(pixels):
                r, g, b = rgb565_to_rgb(pixels[index])
                surface.set_at((x, y), (r, g, b))
                
    return surface
    
def get_pixel_array(surface: pygame.Surface) -> pygame.PixelArray:
    """Get a pixel array from a surface for fast pixel manipulation.
    
    Args:
        surface: Pygame surface
        
    Returns:
        Pygame PixelArray
    """
    return pygame.PixelArray(surface)
    
def create_pixel_surface(width: int, height: int, color: Tuple[int, int, int] = (0, 0, 0)) -> pygame.Surface:
    """Create a new surface for pixel manipulation.
    
    Args:
        width: Surface width
        height: Surface height
        color: Background color
        
    Returns:
        Pygame surface
    """
    surface = pygame.Surface((width, height))
    surface.fill(color)
    return surface