"""Sprite utilities for glitchygames."""

import json
import logging
import os
from typing import Dict, List, Optional, Tuple, Union

import pygame

from glitchygames.interfaces import SpriteInterface

LOG = logging.getLogger('game')

class Sprite(pygame.sprite.Sprite, SpriteInterface):
    """Extended sprite class with additional functionality."""
    
    def __init__(self, 
                 image: Optional[Union[str, pygame.Surface]] = None,
                 position: Tuple[int, int] = (0, 0),
                 velocity: Tuple[int, int] = (0, 0),
                 *groups):
        """Initialize the sprite.
        
        Args:
            image: Image path or surface
            position: Initial position (x, y)
            velocity: Initial velocity (dx, dy)
            *groups: Sprite groups to add this sprite to
        """
        pygame.sprite.Sprite.__init__(self, *groups)
        
        self.position = list(position)
        self.velocity = list(velocity)
        self.acceleration = [0, 0]
        self.angle = 0
        self.scale = 1.0
        self.visible = True
        self.active = True
        
        # Load the image if provided
        if image is not None:
            self.set_image(image)
        else:
            self.image = None
            self.rect = pygame.Rect(0, 0, 0, 0)
            
        # Update the rect position
        self.update_rect()
        
    def set_image(self, image: Union[str, pygame.Surface]):
        """Set the sprite's image.
        
        Args:
            image: Image path or surface
        """
        if isinstance(image, str):
            try:
                self.image = pygame.image.load(image).convert_alpha()
            except pygame.error as e:
                LOG.error("Failed to load image %s: %s", image, e)
                # Create a placeholder image
                self.image = pygame.Surface((32, 32))
                self.image.fill((255, 0, 255))  # Magenta for missing textures
        else:
            self.image = image
            
        # Update the rect
        self.rect = self.image.get_rect()
        self.update_rect()
        
    def update_rect(self):
        """Update the sprite's rect based on position."""
        if hasattr(self, 'rect') and self.rect:
            self.rect.x = int(self.position[0])
            self.rect.y = int(self.position[1])
            
    def update(self):
        """Update the sprite's state."""
        if not self.active:
            return
            
        # Apply acceleration to velocity
        self.velocity[0] += self.acceleration[0]
        self.velocity[1] += self.acceleration[1]
        
        # Apply velocity to position
        self.position[0] += self.velocity[0]
        self.position[1] += self.velocity[1]
        
        # Update the rect
        self.update_rect()
        
    def draw(self, surface: pygame.Surface):
        """Draw the sprite to the surface.
        
        Args:
            surface: Surface to draw on
        """
        if not self.visible or self.image is None:
            return
            
        # Apply transformations if needed
        if self.angle != 0 or self.scale != 1.0:
            # Scale and rotate the image
            scaled_image = pygame.transform.rotozoom(
                self.image, self.angle, self.scale)
            # Get the rect for the transformed image
            scaled_rect = scaled_image.get_rect(center=self.rect.center)
            # Draw the transformed image
            surface.blit(scaled_image, scaled_rect)
        else:
            # Draw the image normally
            surface.blit(self.image, self.rect)
            
class SpriteSheet:
    """Sprite sheet utility for loading multiple sprites from a single image."""
    
    def __init__(self, image_path: str):
        """Initialize the sprite sheet.
        
        Args:
            image_path: Path to the sprite sheet image
        """
        try:
            self.sheet = pygame.image.load(image_path).convert_alpha()
        except pygame.error as e:
            LOG.error("Failed to load sprite sheet %s: %s", image_path, e)
            # Create a placeholder image
            self.sheet = pygame.Surface((64, 64))
            self.sheet.fill((255, 0, 255))  # Magenta for missing textures
            
    def get_image(self, x: int, y: int, width: int, height: int) -> pygame.Surface:
        """Get a single sprite from the sheet.
        
        Args:
            x: X coordinate in the sheet
            y: Y coordinate in the sheet
            width: Width of the sprite
            height: Height of the sprite
            
        Returns:
            Surface with the extracted sprite
        """
        # Create a new surface
        image = pygame.Surface((width, height), pygame.SRCALPHA)
        
        # Copy the sprite from the sheet
        image.blit(self.sheet, (0, 0), (x, y, width, height))
        
        return image
        
    def get_grid(self, sprite_width: int, sprite_height: int, 
                 margin: int = 0, spacing: int = 0) -> List[pygame.Surface]:
        """Get all sprites in a grid layout.
        
        Args:
            sprite_width: Width of each sprite
            sprite_height: Height of each sprite
            margin: Margin around the sprites
            spacing: Spacing between sprites
            
        Returns:
            List of sprite surfaces
        """
        sprites = []
        sheet_width, sheet_height = self.sheet.get_size()
        
        # Calculate how many sprites fit in the sheet
        cols = (sheet_width - margin) // (sprite_width + spacing)
        rows = (sheet_height - margin) // (sprite_height + spacing)
        
        for row in range(rows):
            for col in range(cols):
                # Calculate the position of the sprite
                x = margin + col * (sprite_width + spacing)
                y = margin + row * (sprite_height + spacing)
                
                # Get the sprite
                sprite = self.get_image(x, y, sprite_width, sprite_height)
                sprites.append(sprite)
                
        return sprites
        
    @staticmethod
    def load_from_json(json_path: str) -> Dict[str, pygame.Surface]:
        """Load sprites from a JSON sprite sheet definition.
        
        Args:
            json_path: Path to the JSON file
            
        Returns:
            Dictionary of named sprites
        """
        try:
            # Load the JSON file
            with open(json_path, 'r') as f:
                data = json.load(f)
                
            # Get the image path
            image_path = data.get('image')
            if not image_path:
                LOG.error("No image path in sprite sheet JSON: %s", json_path)
                return {}
                
            # Make the path relative to the JSON file
            if not os.path.isabs(image_path):
                image_path = os.path.join(os.path.dirname(json_path), image_path)
                
            # Load the sprite sheet
            sheet = SpriteSheet(image_path)
            
            # Load the sprites
            sprites = {}
            for name, sprite_data in data.get('sprites', {}).items():
                x = sprite_data.get('x', 0)
                y = sprite_data.get('y', 0)
                width = sprite_data.get('width', 0)
                height = sprite_data.get('height', 0)
                
                sprites[name] = sheet.get_image(x, y, width, height)
                
            return sprites
            
        except Exception as e:
            LOG.error("Failed to load sprite sheet JSON %s: %s", json_path, e)
            return {}