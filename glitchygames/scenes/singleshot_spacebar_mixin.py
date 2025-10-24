"""Mixin for handling spacebar press/release pattern."""

from typing import Self
import pygame


class SpacebarMixin:
    """Mixin that provides spacebar press/release functionality.
    
    This mixin handles the common pattern of:
    1. Track spacebar press (key down)
    2. Act on spacebar release (key up)
    
    Scenes can inherit from this mixin and implement on_spacebar_release()
    to define what happens when spacebar is released.
    """
    
    def __init__(self: Self, *args, **kwargs) -> None:
        """Initialize the spacebar mixin."""
        super().__init__(*args, **kwargs)
        self._space_pressed = False
    
    def on_key_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle key down events for spacebar tracking.
        
        Args:
            event: The key down event.
        """
        if event.key == pygame.K_SPACE:
            # Track that spacebar is pressed (but don't act on it yet)
            self._space_pressed = True
        else:
            # Let the parent class handle other keys
            super().on_key_down_event(event)
    
    def on_key_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle key up events for spacebar action.
        
        Args:
            event: The key up event.
        """
        if event.key == pygame.K_SPACE and self._space_pressed:
            # Spacebar was pressed and now released - trigger action
            self._space_pressed = False
            self.on_spacebar_release()
        else:
            # Let the parent class handle other keys
            super().on_key_up_event(event)
    
    def on_spacebar_release(self: Self) -> None:
        """Called when spacebar is released.
        
        Override this method in subclasses to define what happens
        when spacebar is released.
        
        Default implementation does nothing.
        """
        pass
