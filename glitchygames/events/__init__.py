"""Event handling for glitchygames."""

import logging
from typing import Callable, Dict, List, Optional, Set, Tuple, Union

import pygame

LOG = logging.getLogger('game')

# Map pygame event types to human-readable names
EVENT_NAMES = {
    pygame.QUIT: "QUIT",
    pygame.ACTIVEEVENT: "ACTIVEEVENT",
    pygame.KEYDOWN: "KEYDOWN",
    pygame.KEYUP: "KEYUP",
    pygame.MOUSEMOTION: "MOUSEMOTION",
    pygame.MOUSEBUTTONDOWN: "MOUSEBUTTONDOWN",
    pygame.MOUSEBUTTONUP: "MOUSEBUTTONUP",
    pygame.JOYAXISMOTION: "JOYAXISMOTION",
    pygame.JOYBALLMOTION: "JOYBALLMOTION",
    pygame.JOYHATMOTION: "JOYHATMOTION",
    pygame.JOYBUTTONDOWN: "JOYBUTTONDOWN",
    pygame.JOYBUTTONUP: "JOYBUTTONUP",
    pygame.VIDEORESIZE: "VIDEORESIZE",
    pygame.VIDEOEXPOSE: "VIDEOEXPOSE",
    pygame.USEREVENT: "USEREVENT",
}

# Map pygame event types to handler method names
EVENT_HANDLERS = {
    pygame.KEYDOWN: 'on_key_down',
    pygame.KEYUP: 'on_key_up',
    pygame.MOUSEMOTION: 'on_mouse_motion',
    pygame.MOUSEBUTTONDOWN: 'on_mouse_down',
    pygame.MOUSEBUTTONUP: 'on_mouse_up',
    pygame.JOYAXISMOTION: 'on_joy_axis',
    pygame.JOYBALLMOTION: 'on_joy_ball',
    pygame.JOYHATMOTION: 'on_joy_hat',
    pygame.JOYBUTTONDOWN: 'on_joy_button_down',
    pygame.JOYBUTTONUP: 'on_joy_button_up',
}

def get_event_name(event_type: int) -> str:
    """Get the name of an event type.
    
    Args:
        event_type: Pygame event type
        
    Returns:
        Human-readable name of the event type
    """
    if event_type in EVENT_NAMES:
        return EVENT_NAMES[event_type]
    
    # Handle user events
    if event_type >= pygame.USEREVENT:
        return f"USEREVENT+{event_type - pygame.USEREVENT}"
        
    return f"UNKNOWN({event_type})"

def get_handler_name(event_type: int) -> Optional[str]:
    """Get the handler method name for an event type.
    
    Args:
        event_type: Pygame event type
        
    Returns:
        Handler method name or None if no handler is defined
    """
    return EVENT_HANDLERS.get(event_type)

class EventDispatcher:
    """Dispatches events to handlers.
    
    This class provides a more flexible way to handle events than
    the default pygame event system. It allows registering multiple
    handlers for each event type and dispatching events to all
    registered handlers.
    """
    
    def __init__(self):
        """Initialize the event dispatcher."""
        self.handlers = {}
        
    def register(self, event_type: int, handler: Callable):
        """Register a handler for an event type.
        
        Args:
            event_type: Pygame event type
            handler: Function to call when the event occurs
        """
        if event_type not in self.handlers:
            self.handlers[event_type] = []
            
        self.handlers[event_type].append(handler)
        
    def unregister(self, event_type: int, handler: Callable):
        """Unregister a handler for an event type.
        
        Args:
            event_type: Pygame event type
            handler: Function to unregister
        """
        if event_type in self.handlers and handler in self.handlers[event_type]:
            self.handlers[event_type].remove(handler)
            
    def dispatch(self, event):
        """Dispatch an event to all registered handlers.
        
        Args:
            event: Pygame event to dispatch
        """
        if event.type in self.handlers:
            for handler in self.handlers[event.type]:
                handler(event)