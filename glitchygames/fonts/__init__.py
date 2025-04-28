"""Font utilities for glitchygames."""

import logging
import os
from typing import Dict, Optional, Tuple

import pygame

LOG = logging.getLogger('game')

# Cache for loaded fonts
_font_cache = {}

def init_fonts():
    """Initialize the font system."""
    pygame.font.init()
    
def get_font(name: Optional[str] = None, 
             size: int = 16, 
             bold: bool = False, 
             italic: bool = False,
             antialias: bool = True,
             dpi: Optional[int] = None) -> pygame.font.Font:
    """Get a font object, using the cache if possible.
    
    Args:
        name: Font name or path
        size: Font size in points
        bold: Whether the font should be bold
        italic: Whether the font should be italic
        antialias: Whether to use antialiasing
        dpi: DPI for the font
        
    Returns:
        Pygame font object
    """
    # Create a cache key
    cache_key = (name, size, bold, italic, dpi)
    
    # Check if the font is already in the cache
    if cache_key in _font_cache:
        return _font_cache[cache_key]
        
    # Load the font
    try:
        if name is None:
            # Use the default font
            font = pygame.font.SysFont(None, size, bold, italic)
        elif os.path.exists(name):
            # Load from file
            font = pygame.font.Font(name, size)
            if bold:
                font.set_bold(True)
            if italic:
                font.set_italic(True)
        else:
            # Try to load a system font
            font = pygame.font.SysFont(name, size, bold, italic)
            
        # Set DPI if provided
        if dpi is not None:
            # Note: Pygame doesn't directly support DPI setting
            # This is a placeholder for future implementation
            pass
            
        # Cache the font
        _font_cache[cache_key] = font
        return font
        
    except Exception as e:
        LOG.error("Failed to load font %s: %s", name, e)
        # Fall back to default font
        font = pygame.font.SysFont(None, size, bold, italic)
        _font_cache[cache_key] = font
        return font
        
def render_text(text: str, 
                font: Optional[pygame.font.Font] = None,
                color: Tuple[int, int, int] = (255, 255, 255),
                background: Optional[Tuple[int, int, int]] = None,
                antialias: bool = True) -> pygame.Surface:
    """Render text to a surface.
    
    Args:
        text: Text to render
        font: Font to use (or None for default)
        color: Text color
        background: Background color (or None for transparent)
        antialias: Whether to use antialiasing
        
    Returns:
        Surface with rendered text
    """
    if font is None:
        font = get_font()
        
    return font.render(text, antialias, color, background)
    
def get_text_size(text: str, font: Optional[pygame.font.Font] = None) -> Tuple[int, int]:
    """Get the size of rendered text.
    
    Args:
        text: Text to measure
        font: Font to use (or None for default)
        
    Returns:
        (width, height) of the rendered text
    """
    if font is None:
        font = get_font()
        
    return font.size(text)
    
def clear_cache():
    """Clear the font cache."""
    global _font_cache
    _font_cache = {}