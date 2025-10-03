"""
Canvas interfaces for supporting multiple sprite types in the bitmap editor.

This module defines the abstract interfaces that allow the bitmap editor to work
with both static BitmappySprites and animated sprites through a unified API.
"""

from abc import ABC, abstractmethod
from typing import Any, Protocol
import pygame


class CanvasInterface(Protocol):
    """Interface for canvas operations that work with any sprite type."""
    
    def get_pixel_data(self) -> list[tuple[int, int, int]]:
        """Get the current pixel data as a list of RGB tuples."""
        ...
    
    def set_pixel_data(self, pixels: list[tuple[int, int, int]]) -> None:
        """Set the pixel data from a list of RGB tuples."""
        ...
    
    def get_dimensions(self) -> tuple[int, int]:
        """Get the canvas dimensions as (width, height) in pixels."""
        ...
    
    def get_pixel_at(self, x: int, y: int) -> tuple[int, int, int]:
        """Get the color of a pixel at the given coordinates."""
        ...
    
    def set_pixel_at(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        """Set the color of a pixel at the given coordinates."""
        ...
    
    def get_surface(self) -> pygame.Surface:
        """Get the current rendered surface."""
        ...
    
    def mark_dirty(self) -> None:
        """Mark the canvas as needing a redraw."""
        ...


class SpriteSerializer(ABC):
    """Abstract base class for sprite serialization."""
    
    @abstractmethod
    def save(self, sprite: Any, filename: str, file_format: str = "ini") -> None:
        """Save a sprite to a file.
        
        Args:
            sprite: The sprite to save
            filename: Path where to save the file
            file_format: Format to save in ("ini" or "yaml")
        """
        pass
    
    @abstractmethod
    def load(self, filename: str) -> Any:
        """Load a sprite from a file.
        
        Args:
            filename: Path to the sprite file
            
        Returns:
            The loaded sprite
        """
        pass


class CanvasRenderer(ABC):
    """Abstract base class for canvas rendering."""
    
    @abstractmethod
    def render(self, sprite: Any) -> pygame.Surface:
        """Render a sprite to a surface.
        
        Args:
            sprite: The sprite to render
            
        Returns:
            The rendered surface
        """
        pass
    
    @abstractmethod
    def force_redraw(self, sprite: Any) -> pygame.Surface:
        """Force a complete redraw of the sprite.
        
        Args:
            sprite: The sprite to redraw
            
        Returns:
            The redrawn surface
        """
        pass
    
    @abstractmethod
    def get_pixel_size(self) -> tuple[int, int]:
        """Get the size of individual pixels in the renderer.
        
        Returns:
            Tuple of (pixel_width, pixel_height)
        """
        pass


class StaticCanvasInterface:
    """Canvas interface implementation for static BitmappySprites."""
    
    def __init__(self, canvas_sprite):
        """Initialize with a CanvasSprite instance."""
        self.canvas_sprite = canvas_sprite
    
    def get_pixel_data(self) -> list[tuple[int, int, int]]:
        """Get the current pixel data as a list of RGB tuples."""
        return self.canvas_sprite.pixels.copy()
    
    def set_pixel_data(self, pixels: list[tuple[int, int, int]]) -> None:
        """Set the pixel data from a list of RGB tuples."""
        self.canvas_sprite.pixels = pixels.copy()
        # Mark all pixels as dirty
        self.canvas_sprite.dirty_pixels = [True] * len(pixels)
        self.canvas_sprite.dirty = 1
    
    def get_dimensions(self) -> tuple[int, int]:
        """Get the canvas dimensions as (width, height) in pixels."""
        return (self.canvas_sprite.pixels_across, self.canvas_sprite.pixels_tall)
    
    def get_pixel_at(self, x: int, y: int) -> tuple[int, int, int]:
        """Get the color of a pixel at the given coordinates."""
        if 0 <= x < self.canvas_sprite.pixels_across and 0 <= y < self.canvas_sprite.pixels_tall:
            pixel_num = y * self.canvas_sprite.pixels_across + x
            return self.canvas_sprite.pixels[pixel_num]
        return (255, 0, 255)  # Return magenta for out-of-bounds
    
    def set_pixel_at(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        """Set the color of a pixel at the given coordinates."""
        if 0 <= x < self.canvas_sprite.pixels_across and 0 <= y < self.canvas_sprite.pixels_tall:
            pixel_num = y * self.canvas_sprite.pixels_across + x
            self.canvas_sprite.pixels[pixel_num] = color
            self.canvas_sprite.dirty_pixels[pixel_num] = True
            self.canvas_sprite.dirty = 1
    
    def get_surface(self) -> pygame.Surface:
        """Get the current rendered surface."""
        return self.canvas_sprite.image
    
    def mark_dirty(self) -> None:
        """Mark the canvas as needing a redraw."""
        self.canvas_sprite.dirty = 1


class StaticSpriteSerializer(SpriteSerializer):
    """Serializer for static BitmappySprites."""
    
    def save(self, sprite: Any, filename: str, file_format: str = "ini") -> None:
        """Save a static sprite to a file."""
        # Delegate to the sprite's save method
        sprite.save(filename, file_format)
    
    def load(self, filename: str) -> Any:
        """Load a static sprite from a file."""
        # This will be handled by the CanvasSprite's load method
        # which maintains the existing event callback structure
        pass


class StaticCanvasRenderer(CanvasRenderer):
    """Renderer for static BitmappySprites."""
    
    def __init__(self, canvas_sprite):
        """Initialize with a CanvasSprite instance."""
        self.canvas_sprite = canvas_sprite
    
    def render(self, sprite: Any) -> pygame.Surface:
        """Render a static sprite to a surface."""
        # Use the force_redraw method to avoid recursion
        return self.force_redraw(sprite)
    
    def force_redraw(self, sprite: Any) -> pygame.Surface:
        """Force a complete redraw of the static sprite."""
        # Directly implement the redraw logic to avoid recursion
        self.canvas_sprite.image.fill(self.canvas_sprite.background_color)

        # Draw all pixels, regardless of dirty state
        for i, pixel in enumerate(self.canvas_sprite.pixels):
            x = (i % self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_width
            y = (i // self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_height
            pygame.draw.rect(self.canvas_sprite.image, pixel, (x, y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height))
            pygame.draw.rect(
                self.canvas_sprite.image,
                (64, 64, 64),
                (x, y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height),
                self.canvas_sprite.border_thickness,
            )
            self.canvas_sprite.dirty_pixels[i] = False

        return self.canvas_sprite.image
    
    def get_pixel_size(self) -> tuple[int, int]:
        """Get the size of individual pixels in the renderer."""
        return (self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height)
