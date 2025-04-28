"""Interfaces for glitchygames components."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union

import pygame

class SpriteInterface(ABC):
    """Interface for sprites."""
    
    @abstractmethod
    def update(self):
        """Update the sprite's state."""
        pass
        
    @abstractmethod
    def draw(self, surface: pygame.Surface):
        """Draw the sprite to the surface.
        
        Args:
            surface: Surface to draw on
        """
        pass
        
class SceneInterface(ABC):
    """Interface for scenes."""
    
    @abstractmethod
    def init(self):
        """Initialize the scene."""
        pass
        
    @abstractmethod
    def update(self):
        """Update the scene state."""
        pass
        
    @abstractmethod
    def draw(self, surface: pygame.Surface):
        """Draw the scene to the surface.
        
        Args:
            surface: Surface to draw on
        """
        pass
        
    @abstractmethod
    def cleanup(self):
        """Clean up resources used by the scene."""
        pass