"""Font utilities for glitchygames."""

import logging
import os
from typing import Dict, Optional, Tuple

import pygame

LOG = logging.getLogger('game')

class FontManager:
    """Manages fonts for the game."""
    
    def __init__(self):
        """Initialize the font manager."""
        self.fonts = {}
        self.default_font = None
        
    def load_font(self, name: str, path: str, size: int = 24, bold: bool = False, italic: bool = False, antialias: bool = True) -> pygame.font.Font:
        """Load a font from a file.
        
        Args:
            name: Name to identify the font
            path: Path to font file
            size: Font size
            bold: Whether the font is bold
            italic: Whether the font is italic
            antialias: Whether to use antialiasing
            
        Returns:
            Loaded font
        """
        try:
            font = pygame.font.Font(path, size)
            font.set_bold(bold)
            font.set_italic(italic)
            
            self.fonts[name] = {
                'font': font,
                'path': path,
                'size': size,
                'bold': bold,
                'italic': italic,
                'antialias': antialias
            }
            
            # Set as default if this is the first font
            if self.default_font is None:
                self.default_font = name
                
            return font
        except pygame.error as e:
            LOG.error("Failed to load font %s: %s", path, e)
            return pygame.font.Font(None, size)
            
    def get_font(self, name: Optional[str] = None, size: Optional[int] = None) -> pygame.font.Font:
        """Get a loaded font.
        
        Args:
            name: Name of the font (uses default if None)
            size: Font size (uses original size if None)
            
        Returns:
            Font object
        """
        if name is None:
            name = self.default_font
            
        if name not in self.fonts:
            LOG.warning("Font %s not found, using default", name)
            return pygame.font.Font(None, size or 24)
            
        font_info = self.fonts[name]
        
        if size is not None and size != font_info['size']:
            # Create a new font with the requested size
            try:
                font = pygame.font.Font(font_info['path'], size)
                font.set_bold(font_info['bold'])
                font.set_italic(font_info['italic'])
                return font
            except pygame.error as e:
                LOG.error("Failed to resize font %s: %s", name, e)
                return font_info['font']
        else:
            return font_info['font']
            
    def render_text(self, text: str, name: Optional[str] = None, size: Optional[int] = None, color: Tuple[int, int, int] = (255, 255, 255), antialias: Optional[bool] = None) -> pygame.Surface:
        """Render text with a font.
        
        Args:
            text: Text to render
            name: Name of the font (uses default if None)
            size: Font size (uses original size if None)
            color: Text color
            antialias: Whether to use antialiasing (uses font setting if None)
            
        Returns:
            Rendered text surface
        """
        font = self.get_font(name, size)
        
        if name is None:
            name = self.default_font
            
        if antialias is None and name in self.fonts:
            antialias = self.fonts[name]['antialias']
        elif antialias is None:
            antialias = True
            
        return font.render(text, antialias, color)
        
    def get_text_size(self, text: str, name: Optional[str] = None, size: Optional[int] = None) -> Tuple[int, int]:
        """Get the size of rendered text.
        
        Args:
            text: Text to measure
            name: Name of the font (uses default if None)
            size: Font size (uses original size if None)
            
        Returns:
            (width, height) of the rendered text
        """
        font = self.get_font(name, size)
        return font.size(text)

# Create a global font manager instance
font_manager = FontManager()

def load_font(name: str, path: str, size: int = 24, bold: bool = False, italic: bool = False, antialias: bool = True) -> pygame.font.Font:
    """Load a font from a file.
    
    Args:
        name: Name to identify the font
        path: Path to font file
        size: Font size
        bold: Whether the font is bold
        italic: Whether the font is italic
        antialias: Whether to use antialiasing
        
    Returns:
        Loaded font
    """
    return font_manager.load_font(name, path, size, bold, italic, antialias)

def get_font(name: Optional[str] = None, size: Optional[int] = None) -> pygame.font.Font:
    """Get a loaded font.
    
    Args:
        name: Name of the font (uses default if None)
        size: Font size (uses original size if None)
        
    Returns:
        Font object
    """
    return font_manager.get_font(name, size)

def render_text(text: str, name: Optional[str] = None, size: Optional[int] = None, color: Tuple[int, int, int] = (255, 255, 255), antialias: Optional[bool] = None) -> pygame.Surface:
    """Render text with a font.
    
    Args:
        text: Text to render
        name: Name of the font (uses default if None)
        size: Font size (uses original size if None)
        color: Text color
        antialias: Whether to use antialiasing (uses font setting if None)
        
    Returns:
        Rendered text surface
    """
    return font_manager.render_text(text, name, size, color, antialias)

def get_text_size(text: str, name: Optional[str] = None, size: Optional[int] = None) -> Tuple[int, int]:
    """Get the size of rendered text.
    
    Args:
        text: Text to measure
        name: Name of the font (uses default if None)
        size: Font size (uses original size if None)
        
    Returns:
        (width, height) of the rendered text
    """
    return font_manager.get_text_size(text, name, size)