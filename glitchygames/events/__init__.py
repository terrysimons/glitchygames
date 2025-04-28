"""Event handling for glitchygames."""

import logging
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

import pygame

LOG = logging.getLogger('game')

# Map pygame event types to handler method names
EVENT_HANDLER_MAP = {
    pygame.KEYDOWN: 'on_key_down_event',
    pygame.KEYUP: 'on_key_up_event',
    pygame.MOUSEBUTTONDOWN: 'on_mouse_button_down_event',
    pygame.MOUSEBUTTONUP: 'on_mouse_button_up_event',
    pygame.MOUSEMOTION: 'on_mouse_motion_event',
    pygame.JOYAXISMOTION: 'on_joy_axis_motion_event',
    pygame.JOYBUTTONDOWN: 'on_joy_button_down_event',
    pygame.JOYBUTTONUP: 'on_joy_button_up_event',
    pygame.JOYHATMOTION: 'on_joy_hat_motion_event',
    pygame.VIDEORESIZE: 'on_video_resize_event',
    pygame.QUIT: 'on_quit_event',
}

class EventDispatcher:
    """Dispatches pygame events to handler methods."""
    
    def __init__(self, target, suppress_unhandled=False):
        """Initialize the event dispatcher.
        
        Args:
            target: The object to dispatch events to
            suppress_unhandled: Whether to suppress unhandled events
        """
        self.target = target
        self.suppress_unhandled = suppress_unhandled
        self._handler_cache = {}
        
    def dispatch(self, event):
        """Dispatch an event to the appropriate handler.
        
        Args:
            event: The pygame event to dispatch
            
        Returns:
            True if the event was handled, False otherwise
        """
        # Get the handler method name for this event type
        handler_name = EVENT_HANDLER_MAP.get(event.type)
        
        if handler_name is None:
            # Try to get the handler name from the event name
            try:
                event_name = pygame.event.event_name(event.type).lower()
                handler_name = f"on_{event_name}_event"
            except (ValueError, AttributeError):
                LOG.debug("Unknown event type: %s", event.type)
                return False
                
        # Check if we have a handler for this event
        if handler_name in self._handler_cache:
            handler = self._handler_cache[handler_name]
            if handler is not None:
                handler(event)
                return True
            return False
            
        # Look up the handler method
        handler = getattr(self.target, handler_name, None)
        
        # Cache the result (even if it's None)
        self._handler_cache[handler_name] = handler
        
        if handler is not None and callable(handler):
            handler(event)
            return True
            
        return False
        
    def process_events(self):
        """Process all pending pygame events.
        
        Returns:
            True if the game should continue, False if it should quit
        """
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
                
            # Special case for ESC and Q keys
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE or event.key == pygame.K_q:
                    return False
                    
            # Dispatch the event
            handled = self.dispatch(event)
            
            if not handled and self.suppress_unhandled:
                LOG.warning("Unhandled event: %s", event)
                
        return True