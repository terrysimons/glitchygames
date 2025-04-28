"""Pixel manipulation utilities for glitchygames."""

from typing import List, Tuple

import pygame

def rgb565_to_rgb888(color: int) -> Tuple[int, int, int]:
    """Convert RGB565 color to RGB888.
    
    Args:
        color: RGB565 color (16-bit)
        
    Returns:
        RGB888 color tuple (0-255)
    """
    r = (color >> 11) & 0x1F
    g = (color >> 5) & 0x3F
    b = color & 0x1F
    
    # Scale to 0-255
    r = (r * 255 + 15) // 31
    g = (g * 255 + 31) // 63
    b = (b * 255 + 15) // 31
    
    return (r, g, b)

def rgb888_to_rgb565(color: Tuple[int, int, int]) -> int:
    """Convert RGB888 color to RGB565.
    
    Args:
        color: RGB888 color tuple (0-255)
        
    Returns:
        RGB565 color (16-bit)
    """
    r, g, b = color
    
    # Scale to RGB565 ranges
    r = (r * 31 + 127) // 255
    g = (g * 63 + 127) // 255
    b = (b * 31 + 127) // 255
    
    return (r << 11) | (g << 5) | b

def get_pixel(surface: pygame.Surface, x: int, y: int) -> Tuple[int, int, int, int]:
    """Get the color of a pixel.
    
    Args:
        surface: Surface to get pixel from
        x: X coordinate
        y: Y coordinate
        
    Returns:
        RGBA color tuple (0-255)
    """
    return surface.get_at((x, y))

def set_pixel(surface: pygame.Surface, x: int, y: int, color: Tuple[int, int, int, int]):
    """Set the color of a pixel.
    
    Args:
        surface: Surface to set pixel on
        x: X coordinate
        y: Y coordinate
        color: RGBA color tuple (0-255)
    """
    surface.set_at((x, y), color)

def create_pixel_array(width: int, height: int, color: Tuple[int, int, int, int] = (0, 0, 0, 255)) -> pygame.Surface:
    """Create a new surface with the given dimensions.
    
    Args:
        width: Width of the surface
        height: Height of the surface
        color: Default color for the surface
        
    Returns:
        New surface
    """
    surface = pygame.Surface((width, height), pygame.SRCALPHA)
    surface.fill(color)
    return surface

def blit_pixel_array(surface: pygame.Surface, pixel_array: pygame.Surface, x: int, y: int):
    """Blit a pixel array onto a surface.
    
    Args:
        surface: Surface to blit onto
        pixel_array: Pixel array to blit
        x: X coordinate
        y: Y coordinate
    """
    surface.blit(pixel_array, (x, y))

def create_pixel_mask(width: int, height: int, transparent_color: Tuple[int, int, int]) -> pygame.Surface:
    """Create a mask surface with the given dimensions.
    
    Args:
        width: Width of the mask
        height: Height of the mask
        transparent_color: Color to use for transparency
        
    Returns:
        New mask surface
    """
    mask = pygame.Surface((width, height))
    mask.fill(transparent_color)
    mask.set_colorkey(transparent_color)
    return mask

def apply_pixel_mask(surface: pygame.Surface, mask: pygame.Surface):
    """Apply a mask to a surface.
    
    Args:
        surface: Surface to apply mask to
        mask: Mask to apply
    """
    surface.blit(mask, (0, 0))

def create_gradient(width: int, height: int, start_color: Tuple[int, int, int], end_color: Tuple[int, int, int], vertical: bool = False) -> pygame.Surface:
    """Create a gradient surface.
    
    Args:
        width: Width of the gradient
        height: Height of the gradient
        start_color: Starting color
        end_color: Ending color
        vertical: Whether to create a vertical gradient
        
    Returns:
        Gradient surface
    """
    surface = pygame.Surface((width, height), pygame.SRCALPHA)
    
    r1, g1, b1 = start_color
    r2, g2, b2 = end_color
    
    if vertical:
        for y in range(height):
            factor = y / (height - 1) if height > 1 else 0
            r = int(r1 + (r2 - r1) * factor)
            g = int(g1 + (g2 - g1) * factor)
            b = int(b1 + (b2 - b1) * factor)
            pygame.draw.line(surface, (r, g, b), (0, y), (width - 1, y))
    else:
        for x in range(width):
            factor = x / (width - 1) if width > 1 else 0
            r = int(r1 + (r2 - r1) * factor)
            g = int(g1 + (g2 - g1) * factor)
            b = int(b1 + (b2 - b1) * factor)
            pygame.draw.line(surface, (r, g, b), (x, 0), (x, height - 1))
    
    return surface