"""Scene management for glitchygames."""

import logging
from typing import Dict, List, Optional, Set, Tuple, Union

import pygame

LOG = logging.getLogger('game')

class Scene:
    """Base class for game scenes.
    
    A scene represents a distinct state or screen in a game,
    such as a main menu, level, or game over screen.
    """
    
    # Class attributes that can be overridden by subclasses
    NAME = "Unnamed Scene"
    VERSION = "0.0.0"
    
    def __init__(self, options=None, groups=None):
        """Initialize the scene.
        
        Args:
            options: Command line options
            groups: Sprite groups to use
        """
        self.options = options
        self.groups = groups or {}
        self.engine = None
        self.screen = None
        self.background_color = (0, 0, 0)  # Default to black
        self.sprites = pygame.sprite.Group()
        self.clock = pygame.time.Clock()
        self.running = True
        
        # Event handling tracking
        self._handled_events = set()
        
    def init(self):
        """Initialize the scene. Called after the scene is created."""
        pass
        
    def update(self):
        """Update the scene state. Called once per frame."""
        # Update all sprites
        self.sprites.update()
        
    def draw(self, surface):
        """Draw the scene to the given surface.
        
        Args:
            surface: Surface to draw on
        """
        # Clear the screen
        surface.fill(self.background_color)
        
        # Draw all sprites
        self.sprites.draw(surface)
        
    def process_events(self, event):
        """Process a pygame event.
        
        This method can be overridden by subclasses to handle events directly.
        If not overridden, the engine will route events to specific handlers.
        
        Args:
            event: Pygame event to process
        """
        pass
        
    def on_key_down(self, event):
        """Handle key down events.
        
        Args:
            event: Pygame KEYDOWN event
        """
        self._handled_events.add(pygame.KEYDOWN)
        
    def on_key_up(self, event):
        """Handle key up events.
        
        Args:
            event: Pygame KEYUP event
        """
        self._handled_events.add(pygame.KEYUP)
        
    def on_mouse_motion(self, event):
        """Handle mouse motion events.
        
        Args:
            event: Pygame MOUSEMOTION event
        """
        self._handled_events.add(pygame.MOUSEMOTION)
        
    def on_mouse_down(self, event):
        """Handle mouse button down events.
        
        Args:
            event: Pygame MOUSEBUTTONDOWN event
        """
        self._handled_events.add(pygame.MOUSEBUTTONDOWN)
        
    def on_mouse_up(self, event):
        """Handle mouse button up events.
        
        Args:
            event: Pygame MOUSEBUTTONUP event
        """
        self._handled_events.add(pygame.MOUSEBUTTONUP)
        
    def on_joy_axis(self, event):
        """Handle joystick axis motion events.
        
        Args:
            event: Pygame JOYAXISMOTION event
        """
        self._handled_events.add(pygame.JOYAXISMOTION)
        
    def on_joy_ball(self, event):
        """Handle joystick ball motion events.
        
        Args:
            event: Pygame JOYBALLMOTION event
        """
        self._handled_events.add(pygame.JOYBALLMOTION)
        
    def on_joy_hat(self, event):
        """Handle joystick hat motion events.
        
        Args:
            event: Pygame JOYHATMOTION event
        """
        self._handled_events.add(pygame.JOYHATMOTION)
        
    def on_joy_button_down(self, event):
        """Handle joystick button down events.
        
        Args:
            event: Pygame JOYBUTTONDOWN event
        """
        self._handled_events.add(pygame.JOYBUTTONDOWN)
        
    def on_joy_button_up(self, event):
        """Handle joystick button up events.
        
        Args:
            event: Pygame JOYBUTTONUP event
        """
        self._handled_events.add(pygame.JOYBUTTONUP)
        
    def on_fps_update(self, fps):
        """Handle FPS updates.
        
        Args:
            fps: Current frames per second
        """
        pass
        
    @classmethod
    def args(cls, parser):
        """Add command line arguments for this scene.
        
        Args:
            parser: ArgumentParser to add arguments to
        """
        pass