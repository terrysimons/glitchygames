"""Sprite utilities for glitchygames."""

import json
import logging
import os
from typing import Dict, List, Optional, Tuple, Union

import pygame

from glitchygames.movement import Vector2D

LOG = logging.getLogger('game')

class Sprite(pygame.sprite.Sprite):
    """Base class for sprites in glitchygames."""
    
    def __init__(self, image=None, position=(0, 0), velocity=(0, 0), *groups):
        """Initialize the sprite.
        
        Args:
            image: Surface or path to image file
            position: Initial position (x, y)
            velocity: Initial velocity (vx, vy)
            *groups: Sprite groups to add this sprite to
        """
        super().__init__(*groups)
        
        self.position = Vector2D.from_tuple(position)
        self.velocity = Vector2D.from_tuple(velocity)
        self.acceleration = Vector2D(0, 0)
        self.rotation = 0  # Rotation in degrees
        self.scale = 1.0   # Scale factor
        
        # Load image if provided
        if image is not None:
            if isinstance(image, str):
                self.load_image(image)
            else:
                self.image = image
                self.original_image = self.image.copy()
                self.rect = self.image.get_rect()
        else:
            self.image = None
            self.original_image = None
            self.rect = pygame.Rect(0, 0, 0, 0)
            
        # Update rect position
        self.update_rect()
        
    def load_image(self, path: str):
        """Load an image from a file.
        
        Args:
            path: Path to image file
        """
        try:
            self.image = pygame.image.load(path).convert_alpha()
            self.original_image = self.image.copy()
            self.rect = self.image.get_rect()
        except pygame.error as e:
            LOG.error("Failed to load image %s: %s", path, e)
            # Create a placeholder image
            self.image = pygame.Surface((32, 32), pygame.SRCALPHA)
            self.image.fill((255, 0, 255))  # Magenta for missing textures
            self.original_image = self.image.copy()
            self.rect = self.image.get_rect()
            
    def update_rect(self):
        """Update the rect position based on the sprite's position."""
        if self.rect:
            self.rect.center = (int(self.position.x), int(self.position.y))
            
    def update_image(self):
        """Update the sprite's image based on rotation and scale."""
        if self.original_image:
            if self.rotation != 0 or self.scale != 1.0:
                # Apply rotation and scaling
                width = int(self.original_image.get_width() * self.scale)
                height = int(self.original_image.get_height() * self.scale)
                if width > 0 and height > 0:
                    scaled = pygame.transform.scale(self.original_image, (width, height))
                    self.image = pygame.transform.rotate(scaled, self.rotation)
                    self.rect = self.image.get_rect(center=self.rect.center)
            else:
                self.image = self.original_image.copy()
                
    def update(self):
        """Update the sprite's state.
        
        This method is called once per frame by the sprite group.
        """
        # Apply velocity to position
        self.position.x += self.velocity.x
        self.position.y += self.velocity.y
        
        # Apply acceleration to velocity
        self.velocity.x += self.acceleration.x
        self.velocity.y += self.acceleration.y
        
        # Update rect position
        self.update_rect()
        
    def draw(self, surface: pygame.Surface):
        """Draw the sprite on a surface.
        
        Args:
            surface: Surface to draw on
        """
        if self.image:
            surface.blit(self.image, self.rect)
            
    def set_position(self, x: float, y: float):
        """Set the sprite's position.
        
        Args:
            x: X coordinate
            y: Y coordinate
        """
        self.position.x = x
        self.position.y = y
        self.update_rect()
        
    def set_velocity(self, vx: float, vy: float):
        """Set the sprite's velocity.
        
        Args:
            vx: X velocity
            vy: Y velocity
        """
        self.velocity.x = vx
        self.velocity.y = vy
        
    def set_acceleration(self, ax: float, ay: float):
        """Set the sprite's acceleration.
        
        Args:
            ax: X acceleration
            ay: Y acceleration
        """
        self.acceleration.x = ax
        self.acceleration.y = ay
        
    def set_rotation(self, angle: float):
        """Set the sprite's rotation.
        
        Args:
            angle: Rotation angle in degrees
        """
        self.rotation = angle % 360
        self.update_image()
        
    def set_scale(self, scale: float):
        """Set the sprite's scale.
        
        Args:
            scale: Scale factor
        """
        self.scale = max(0.1, scale)  # Prevent negative or zero scale
        self.update_image()
        
    def collide_with(self, other) -> bool:
        """Check if this sprite collides with another sprite.
        
        Args:
            other: Other sprite to check collision with
            
        Returns:
            True if sprites collide, False otherwise
        """
        return pygame.sprite.collide_rect(self, other)
        
    def distance_to(self, other) -> float:
        """Calculate distance to another sprite.
        
        Args:
            other: Other sprite
            
        Returns:
            Distance between sprite centers
        """
        dx = self.position.x - other.position.x
        dy = self.position.y - other.position.y
        return math.sqrt(dx * dx + dy * dy)

class AnimatedSprite(Sprite):
    """Sprite with animation support."""
    
    def __init__(self, frames=None, frame_duration=100, *args, **kwargs):
        """Initialize the animated sprite.
        
        Args:
            frames: List of surfaces or paths to image files
            frame_duration: Duration of each frame in milliseconds
            *args: Arguments to pass to Sprite constructor
            **kwargs: Keyword arguments to pass to Sprite constructor
        """
        super().__init__(*args, **kwargs)
        
        self.frames = []
        self.frame_duration = frame_duration
        self.current_frame = 0
        self.animation_time = 0
        self.playing = True
        self.loop = True
        
        # Load frames if provided
        if frames:
            self.load_frames(frames)
            
    def load_frames(self, frames):
        """Load animation frames.
        
        Args:
            frames: List of surfaces or paths to image files
        """
        self.frames = []
        
        for frame in frames:
            if isinstance(frame, str):
                try:
                    image = pygame.image.load(frame).convert_alpha()
                    self.frames.append(image)
                except pygame.error as e:
                    LOG.error("Failed to load frame %s: %s", frame, e)
            else:
                self.frames.append(frame)
                
        if self.frames:
            self.image = self.frames[0]
            self.original_image = self.image.copy()
            self.rect = self.image.get_rect()
            self.update_rect()
            
    def update(self):
        """Update the sprite's state."""
        super().update()
        
        # Update animation
        if self.playing and self.frames:
            self.animation_time += pygame.time.get_ticks()
            
            if self.animation_time >= self.frame_duration:
                self.animation_time = 0
                self.current_frame += 1
                
                if self.current_frame >= len(self.frames):
                    if self.loop:
                        self.current_frame = 0
                    else:
                        self.current_frame = len(self.frames) - 1
                        self.playing = False
                        
                self.image = self.frames[self.current_frame]
                self.original_image = self.image.copy()
                self.update_image()
                
    def play(self, loop=True):
        """Start playing the animation.
        
        Args:
            loop: Whether to loop the animation
        """
        self.playing = True
        self.loop = loop
        
    def stop(self):
        """Stop playing the animation."""
        self.playing = False
        
    def reset(self):
        """Reset the animation to the first frame."""
        self.current_frame = 0
        self.animation_time = 0
        if self.frames:
            self.image = self.frames[0]
            self.original_image = self.image.copy()
            self.update_image()

class SpriteSheet:
    """Utility class for loading sprite sheets."""
    
    def __init__(self, image_path: str):
        """Initialize the sprite sheet.
        
        Args:
            image_path: Path to sprite sheet image
        """
        try:
            self.sheet = pygame.image.load(image_path).convert_alpha()
        except pygame.error as e:
            LOG.error("Failed to load sprite sheet %s: %s", image_path, e)
            # Create a placeholder image
            self.sheet = pygame.Surface((64, 64), pygame.SRCALPHA)
            self.sheet.fill((255, 0, 255))  # Magenta for missing textures
            
    def get_image(self, x: int, y: int, width: int, height: int) -> pygame.Surface:
        """Get a single image from the sprite sheet.
        
        Args:
            x: X coordinate of the image
            y: Y coordinate of the image
            width: Width of the image
            height: Height of the image
            
        Returns:
            Image surface
        """
        image = pygame.Surface((width, height), pygame.SRCALPHA)
        image.blit(self.sheet, (0, 0), (x, y, width, height))
        return image
        
    def get_images(self, rects: List[Tuple[int, int, int, int]]) -> List[pygame.Surface]:
        """Get multiple images from the sprite sheet.
        
        Args:
            rects: List of (x, y, width, height) tuples
            
        Returns:
            List of image surfaces
        """
        return [self.get_image(x, y, width, height) for x, y, width, height in rects]
        
    def get_strip(self, x: int, y: int, width: int, height: int, count: int, spacing: int = 0) -> List[pygame.Surface]:
        """Get a strip of images from the sprite sheet.
        
        Args:
            x: X coordinate of the first image
            y: Y coordinate of the first image
            width: Width of each image
            height: Height of each image
            count: Number of images
            spacing: Spacing between images
            
        Returns:
            List of image surfaces
        """
        images = []
        for i in range(count):
            images.append(self.get_image(x + i * (width + spacing), y, width, height))
        return images
        
    def get_grid(self, x: int, y: int, width: int, height: int, columns: int, rows: int, spacing_x: int = 0, spacing_y: int = 0) -> List[pygame.Surface]:
        """Get a grid of images from the sprite sheet.
        
        Args:
            x: X coordinate of the first image
            y: Y coordinate of the first image
            width: Width of each image
            height: Height of each image
            columns: Number of columns
            rows: Number of rows
            spacing_x: Horizontal spacing between images
            spacing_y: Vertical spacing between images
            
        Returns:
            List of image surfaces
        """
        images = []
        for row in range(rows):
            for col in range(columns):
                images.append(self.get_image(
                    x + col * (width + spacing_x),
                    y + row * (height + spacing_y),
                    width, height
                ))
        return images