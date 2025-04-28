"""Scene management for glitchygames."""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import pygame

LOG = logging.getLogger('game')

class Scene:
    """Base class for all game scenes.
    
    A scene represents a distinct screen or state in the game,
    such as a main menu, level, or game over screen.
    """
    
    # Class attributes that can be overridden by subclasses
    NAME = "Unnamed Scene"
    VERSION = "0.0.0"
    
    def __init__(self, options, groups=None):
        """Initialize the scene.
        
        Args:
            options: Command line options
            groups: Sprite groups to use
        """
        self.options = options
        self.groups = groups or {}
        self.engine = None  # Set by GameEngine
        self.screen = None  # Set by GameEngine
        self.background_color = (0, 0, 0)  # Default to black
        
        # Performance tracking
        self.frame_count = 0
        self.last_update_time = pygame.time.get_ticks()
        
        LOG.debug("Initialized scene: %s", self.__class__.__name__)
        
    def init(self):
        """Initialize the scene. Called after the engine is set up."""
        pass
        
    def update(self):
        """Update the scene state. Called once per frame."""
        self.frame_count += 1
        
        # Update all sprite groups
        for group in self.groups.values():
            group.update()
            
    def draw(self, surface):
        """Draw the scene to the given surface.
        
        Args:
            surface: The surface to draw on
        """
        # Clear the screen with the background color
        surface.fill(self.background_color)
        
        # Draw all sprite groups
        for group in self.groups.values():
            group.draw(surface)
            
    def cleanup(self):
        """Clean up resources used by the scene."""
        pass
        
    def on_key_down_event(self, event):
        """Handle key down events.
        
        Args:
            event: The pygame event
        """
        pass
        
    def on_key_up_event(self, event):
        """Handle key up events.
        
        Args:
            event: The pygame event
        """
        pass
        
    def on_mouse_button_down_event(self, event):
        """Handle mouse button down events.
        
        Args:
            event: The pygame event
        """
        pass
        
    def on_mouse_button_up_event(self, event):
        """Handle mouse button up events.
        
        Args:
            event: The pygame event
        """
        pass
        
    def on_mouse_motion_event(self, event):
        """Handle mouse motion events.
        
        Args:
            event: The pygame event
        """
        pass
        
    def on_joy_axis_motion_event(self, event):
        """Handle joystick axis motion events.
        
        Args:
            event: The pygame event
        """
        pass
        
    def on_joy_button_down_event(self, event):
        """Handle joystick button down events.
        
        Args:
            event: The pygame event
        """
        pass
        
    def on_joy_button_up_event(self, event):
        """Handle joystick button up events.
        
        Args:
            event: The pygame event
        """
        pass
        
    def on_joy_hat_motion_event(self, event):
        """Handle joystick hat motion events.
        
        Args:
            event: The pygame event
        """
        pass
        
    def on_video_resize_event(self, event):
        """Handle video resize events.
        
        Args:
            event: The pygame event
        """
        pass
        
    @classmethod
    def args(cls, parser):
        """Add scene-specific command line arguments.
        
        Args:
            parser: The argument parser to add arguments to
        """
        pass