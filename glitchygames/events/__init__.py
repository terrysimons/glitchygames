#!/usr/bin/env python3
"""Glitchy Games event module.

This module contains the event substrate for handling
higher level events in the game engine.

Many events are 1:1 with pygame events, but some are
synthesized.  For example, a mouse drop event is
a synthesized event that is triggered by a mouse
button down event followed by a mouse motion event
followed by a mouse button up event.
"""
from __future__ import annotations

import abc
import inspect
import logging
import re
from typing import TYPE_CHECKING, ClassVar, NoReturn, Self

import pygame

if TYPE_CHECKING:
    from collections.abc import Callable

LOG: logging.Logger = logging.getLogger('game.events')
LOG.addHandler(logging.NullHandler())

def supported_events(like: str = '.*') -> list:
    """Return a list of supported events.

    This method is crucial for allowing the game engine
    to support both older versions of pygame and newer
    versions.  It allows us to enumerate supported pygame
    events and initialize them dynamically.

    This ensures that the game engine will work with
    many versions of pygame.

    We enumerate all pygame event IDs and then use the pygame.event.event_name()
    method to get the event name.  We then use a regular expression to
    match the event name against the like parameter.

    Args:
        like: A regular expression to match against the event names.

    Returns:
        A list of pygame events whose names match the regular expression.
    """
    # Get a list of all of the events
    # by name, but ignore duplicates.
    event_names = (
        pygame.event.event_name(event_num) for event_num in range(pygame.NUMEVENTS)
    )
    event_names: set[str] = set(event_names) - set('Unknown')

    # Pygame 2.5.1 and maybe others have a bug where the event name lookup
    # is wrong.
    #
    # The error is:
    #
    # AttributeError: module 'pygame' has no attribute 'CONTROLLERDEVICEMAPPED'.
    # Did you mean: 'CONTROLLERDEVICEREMAPPED'?
    #
    # This is a workaround for that.
    #
    # The controller documentation also indicates that it should be CONTROLLERDEVICEREMAPPED
    patched_event_names = {
        'APPDIDENTERBACKGROUND': 'APP_DIDENTERBACKGROUND',
        'APPDIDENTERFOREGROUND': 'APP_DIDENTERFOREGROUND',
        'APPLOWMEMORY': 'APP_LOWMEMORY',
        'APPWILLENTERBACKGROUND': 'APP_WILLENTERBACKGROUND',
        'APPWILLENTERFOREGROUND': 'APP_WILLENTERFOREGROUND',
        'APPTERMINATING': 'APP_TERMINATING',
        'CONTROLLERDEVICEMAPPED': 'CONTROLLERDEVICEREMAPPED',
        'RENDERDEVICERESET': 'RENDER_DEVICE_RESET',
        'RENDERTARGETSRESET': 'RENDER_TARGETS_RESET',
        'UNKNOWN': 'K_UNKNOWN'
    }

    event_list = []

    for event_name in list(event_names):
        # If there's a patched event name, use it, otherwise use event_name
        #
        # This works around a pygame bug for CONTROLLERDEVICEREMAPPED
        patched_event_name = patched_event_names.get(event_name.upper(), event_name)
        LOG.info(f'Adding Event: {patched_event_name}')

        if re.match(like, patched_event_name.upper()):
            event_list.append(getattr(pygame, patched_event_name.upper()))

    return event_list


# Pygame USEREVENTs
FPSEVENT = pygame.USEREVENT + 1
GAMEEVENT = pygame.USEREVENT + 2
MENUEVENT = pygame.USEREVENT + 3

AUDIO_EVENTS = supported_events(like='AUDIO.*?')
CONTROLLER_EVENTS = supported_events(like='CONTROLLER.*?')
DROP_EVENTS = supported_events(like='DROP.*?')
TOUCH_EVENTS = supported_events(like='(FINGER|MULTI).*?')
JOYSTICK_EVENTS = supported_events(like='JOY.*?')
KEYBOARD_EVENTS = supported_events(like='KEY.*?')
MIDI_EVENTS = supported_events(like='MIDI.*?')
MOUSE_EVENTS = supported_events(like='MOUSE.*?')
TEXT_EVENTS = supported_events(like='TEXT.*?')
WINDOW_EVENTS = supported_events(like='WINDOW.*?')
ALL_EVENTS = supported_events()
GAME_EVENTS = list(
    set(ALL_EVENTS) -
    set(AUDIO_EVENTS) -
    set(CONTROLLER_EVENTS) -
    set(DROP_EVENTS) -
    set(TOUCH_EVENTS) -
    set(JOYSTICK_EVENTS) -
    set(KEYBOARD_EVENTS) -
    set(MIDI_EVENTS) -
    set(MOUSE_EVENTS) -
    set(TEXT_EVENTS) -
    set(WINDOW_EVENTS)
)

GAME_EVENTS.extend(
    [
        FPSEVENT,
        GAMEEVENT,
        MENUEVENT
    ]
)

def unhandled_event(*args, **kwargs) -> NoReturn:
    """Handle unhandled events.

    This method is called when an event is not handled by
    any of the event handlers.

    This is helpful for us to debug events that we haven't
    implemented yet.

    Args:
        *args: The positional arguments.
        **kwargs: The keyword arguments.

    Returns:
        None

    Raises:
        AttributeError: If the event is not handled.
    """
    LOG.error(f'Unhandled Event: args: {args}, kwargs: {kwargs}')
    raise AttributeError(f'Unhandled Event: args: {args}, kwargs: {kwargs}')


# Interiting from object is default in Python 3.
# Linters complain if you do it.
class ResourceManager:
    """Singleton aggregator base class for event proxies.

    A ResourceManager subclass will generally pass all
    requests through to its proxy object(s), however, for
    certain types of resources such as joysticks, the
    subclass will manage things itself.  This architecture
    reduces code footprint, and allows maxium flexibility
    when needed, at the expense of a bit of abstraction.

    Unless you're implementing a new pygame event manager,
    you probably don't need to worry about this.

    Any subclass of ResourceManager will become
    a singleton class automatically.  This ensures that
    there is only ever a single manager for any given
    resource.

    For instance, a second instantiation of MouseManager
    would return the same MouseManager object that the
    GameEngine created to process mouse events with.

    This behavior allows easy access to resource managers
    anywhere in the game without needing an explicit copy
    of the game object, althogh since GameEngine is also
    a subclass of EventManager, it too is a ResourceManager
    which can be gotten to from anywhere, since it's a singleton.
    """

    log: logging.Logger = LOG

    __instances__: ClassVar = {}

    def __new__(cls: Self, *args, **kwargs) -> object:
        """Create a new instance of the class.

        This method is called when a new instance of the class

        Args:
            cls: The class.
            *args: The positional arguments.
            **kwargs: The keyword arguments.

        Returns:
            The new instance of the class.

        Raises:
            AttributeError: If the event is not handled by any proxy.
        """
        if cls not in cls.__instances__:
            cls.__instances__[cls] = object.__new__(cls)
            LOG.debug(f'Created Resource Manager: {cls}')
            cls.__instances__[cls].args = args
            cls.__instances__[cls].kwargs = kwargs

        return cls.__instances__[cls]

    def __init__(self: Self, game: object) -> None:
        """Initialize the resource manager.

        Args:
            game: The game instance.

        Returns:
            None
        """
        super().__init__()
        self.proxies = []

    def __getattr__(self: Self, attr: str) -> Callable:
        """Get an attribute.

        This method is called when an attribute is not found.

        Args:
            attr: The attribute to get.

        Returns:
            The attribute.

        Raises:
            AttributeError: If the attribute is not found.
        """
        # Try each proxy in turn
        try:
            for proxy in self.proxies:
                return getattr(proxy, attr)
        except AttributeError:
            self.log.exception(f'No proxies for {type(self)}.{attr}')
            raise

        raise AttributeError(f'No proxies for {type(self)}.{attr}')

# We intentionally don't implement any methods here.
class EventInterface(metaclass=abc.ABCMeta):  # noqa: B024
    """Abstract base class for event interfaces."""

    @classmethod
    def __subclasshook__(cls: Self, subclass: object) -> bool:
        """Override the default __subclasshook__ to create an interface."""
        # Note: This accounts for under/dunder methods in addition to regular methods.
        interface_attributes = set(cls.__abstractmethods__)
        subclass_attributes = set(subclass.__abstractmethods__)

        interface_is_implemented = False
        methods = []
        for attribute in sorted(interface_attributes):
            if hasattr(subclass, attribute) and attribute not in subclass_attributes:
                if callable(getattr(subclass, attribute)):
                    cls.log.info(f'{subclass.__name__}.{attribute} -> ✅ (callable)')
                else:
                    cls.log.info(f'{subclass.__name__}.{attribute} -> ✅ (attribute))')
                methods.append(True)
            else:
                cls.log.info(f'{subclass.__name__}.{attribute} -> ❌ (unimplemented)')
                methods.append(False)

        # all([]) returns True, so mask it
        #
        # This protects against an empty attribute list
        # which would be a misconfiguration of the interface
        if len(methods) and all(methods):
            interface_is_implemented = all(methods)

        return interface_is_implemented


# Mixin
class AudioEvents(EventInterface):
    """Mixin for audio events."""

    @abc.abstractmethod
    def on_audio_device_added_event(self: Self, event: pygame.event.Event) -> None:
        """Handle audio device added events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # AUDIODEVICEADDED   which, iscapture

    @abc.abstractmethod
    def on_audio_device_removed_event(self: Self, event: pygame.event.Event) -> None:
        """Handle audio device removed events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # AUDIODEVICEREMOVED which, iscapture


# Mixin
class ControllerEvents(EventInterface):
    """Mixin for controller events."""
    @abc.abstractmethod
    def on_controller_axis_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller axis motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # CONTROLLERAXISMOTION joy, axis, value

    @abc.abstractmethod
    def on_controller_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # CONTROLLERBUTTONDOWN joy, button

    @abc.abstractmethod
    def on_controller_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # CONTROLLERBUTTONUP   joy, button

    @abc.abstractmethod
    def on_controller_device_added_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller device added events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # CONTROLLERDEVICEADDED device_index, guid

    @abc.abstractmethod
    def on_controller_device_remapped_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller device remapped events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # CONTROLLERDEVICEREMAPPED device_index

    @abc.abstractmethod
    def on_controller_device_removed_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller device removed events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # CONTROLLERDEVICEREMOVED device_index

    @abc.abstractmethod
    def on_controller_touchpad_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller touchpad down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # CONTROLLERTOUCHPADDOWN joy, touchpad

    @abc.abstractmethod
    def on_controller_touchpad_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller touchpad motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # CONTROLLERTOUCHPADMOTION joy, touchpad

    @abc.abstractmethod
    def on_controller_touchpad_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller touchpad up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # CONTROLLERTOUCHPADUP joy, touchpad


# Mixin
class DropEvents(EventInterface):
    """Mixin for drop events."""

    @abc.abstractmethod
    def on_drop_begin_event(self: Self, event: pygame.event.Event) -> None:
        """Handle drop begin event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # DROPBEGIN        none

    @abc.abstractmethod
    def on_drop_file_event(self: Self, event: pygame.event.Event) -> None:
        """Handle drop file event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # DROPFILE         file

    @abc.abstractmethod
    def on_drop_text_event(self: Self, event: pygame.event.Event) -> None:
        """Handle drop text event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # DROPTEXT         text

    @abc.abstractmethod
    def on_drop_complete_event(self: Self, event: pygame.event.Event) -> None:
        """Handle drop complete event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # DROPCOMPLETE     none


# Mixin
class TouchEvents(EventInterface):
    """Mixin for touch events."""

    @abc.abstractmethod
    def on_touch_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle finger down event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # FINGERDOWN       finger_id, x, y, dx, dy, pressure

    @abc.abstractmethod
    def on_touch_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle finger motion event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # FINGERMOTION     finger_id, x, y, dx, dy, pressure

    @abc.abstractmethod
    def on_touch_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle finger up event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # FINGERUP         finger_id, x, y, dx, dy, pressure

    @abc.abstractmethod
    def on_multi_touch_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle multi finger down event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # MULTIFINGERDOWN  touch_id, x, y, dx, dy, pressure

    @abc.abstractmethod
    def on_multi_touch_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle multi finger motion event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # MULTIFINGERMOTION touch_id, x, y, dx, dy, pressure

    @abc.abstractmethod
    def on_multi_touch_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle multi finger up event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # MULTIFINGERUP    touch_id, x, y, dx, dy, pressure


# Mixin
# TODO: Add a glitchy games event index to allow
# games to easily extend pygame further without impacting
# the core engine.
class GameEvents(EventInterface):
    """Mixin for glitchy game events.

    This includes built-ins like QUIT, and synthesized
    events like FPS and GAME events.

    It's sort of a catch-all for event types that didn't have
    a good home otherwise.
    """

    @abc.abstractmethod
    def on_active_event(self: Self, event: pygame.event.Event) -> None:
        """Handle active events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # ACTIVEEVENT      gain, state

    @abc.abstractmethod
    def on_fps_event(self: Self, event: pygame.event.Event) -> None:
        """Handle FPS events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # FPSEVENT is pygame.USEREVENT + 1

    @abc.abstractmethod
    def on_game_event(self: Self, event: pygame.event.Event) -> None:
        """Handle game events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # GAMEEVENT is pygame.USEREVENT + 2

    @abc.abstractmethod
    def on_menu_item_event(self: Self, event: pygame.event.Event) -> None:
        """Handle menu item events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # MENUEVENT is pygame.USEREVENT + 3

    @abc.abstractmethod
    def on_sys_wm_event(self: Self, event: pygame.event.Event) -> None:
        """Handle sys wm events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # SYSWMEVENT

    @abc.abstractmethod
    def on_user_event(self: Self, event: pygame.event.Event) -> None:
        """Handle user events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # USEREVENT        code

    @abc.abstractmethod
    def on_video_expose_event(self: Self, event: pygame.event.Event) -> None:
        """Handle video expose events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # VIDEOEXPOSE      none

    @abc.abstractmethod
    def on_video_resize_event(self: Self, event: pygame.event.Event) -> None:
        """Handle video resize events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # VIDEORESIZE      size, w, h

    @abc.abstractmethod
    def on_quit_event(self: Self, event: pygame.event.Event) -> None:
        """Handle quit events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # QUIT             none


# Mixin
class FontEvents(EventInterface):
    """Mixin for font events."""

    @abc.abstractmethod
    def on_font_changed_event(self: Self, event: pygame.event.Event) -> None:
        """Handle font changed events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # FONTS_CHANGED

# Mixin
class KeyboardEvents(EventInterface):
    """Mixin for keyboard events."""

    @abc.abstractmethod
    def on_key_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle key down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # KEYDOWN          unicode, key, mod

    @abc.abstractmethod
    def on_key_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle key up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # KEYUP            key, mod

    @abc.abstractmethod
    def on_key_chord_up_event(self: Self, event: pygame.event.Event, keys: list) -> None:
        """Handle key chord up events.

        Args:
            event (pygame.event.Event): The event to handle.
            keys (list): The keys in the chord.

        Returns:
            None
        """
        # Synthesized event.

    @abc.abstractmethod
    def on_key_chord_down_event(self: Self, event: pygame.event.Event, keys: list) -> None:
        """Handle key chord down events.

        Args:
            event (pygame.event.Event): The event to handle.
            keys (list): The keys in the chord.

        Returns:
            None
        """
        # Synthesized event.

# Mixin
class JoystickEvents(EventInterface):
    """Mixin for joystick events."""

    @abc.abstractmethod
    def on_joy_axis_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle joystick axis motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # JOYAXISMOTION    joy, axis, value

    @abc.abstractmethod
    def on_joy_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle joystick button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # JOYBUTTONDOWN    joy, button

    @abc.abstractmethod
    def on_joy_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle joystick button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # JOYBUTTONUP      joy, button

    @abc.abstractmethod
    def on_joy_hat_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle joystick hat motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # JOYHATMOTION     joy, hat, value

    @abc.abstractmethod
    def on_joy_ball_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle joystick ball motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # JOYBALLMOTION    joy, ball, rel

    @abc.abstractmethod
    def on_joy_device_added_event(self: Self, event: pygame.event.Event) -> None:
        """Handle joystick device added events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # JOYDEVICEADDED device_index, guid

    @abc.abstractmethod
    def on_joy_device_removed_event(self: Self, event: pygame.event.Event) -> None:
        """Handle joystick device removed events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # JOYDEVICEREMOVED device_index


# Mixin
class MidiEvents(EventInterface):
    """Mixin for midi events."""


# Mixin
class MouseEvents(EventInterface):
    """Mixin for mouse events."""

    @abc.abstractmethod
    def on_mouse_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle mouse motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # MOUSEMOTION      pos, rel, buttons

    @abc.abstractmethod
    def on_mouse_drag_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle mouse drag events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        # Synthesized event.

    @abc.abstractmethod
    def on_mouse_drop_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle mouse drop events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        # Synthesized event.

    @abc.abstractmethod
    def on_left_mouse_drag_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle left mouse drag events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        # Synthesized event.

    @abc.abstractmethod
    def on_left_mouse_drop_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle left mouse drop events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        # Synthesized event.

    @abc.abstractmethod
    def on_middle_mouse_drag_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle middle mouse drag events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        # Synthesized event.

    @abc.abstractmethod
    def on_middle_mouse_drop_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle middle mouse drop events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        # Synthesized event.

    @abc.abstractmethod
    def on_right_mouse_drag_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle right mouse drag events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        # Synthesized event.

    @abc.abstractmethod
    def on_right_mouse_drop_event(self: Self, event: pygame.event.Event, trigger: object) -> None:
        """Handle right mouse drop events.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        # Synthesized event.

    @abc.abstractmethod
    def on_mouse_focus_event(self: Self, event: pygame.event.Event,
                             entering_focus: object) -> None:
        """Handle mouse focus events.

        Args:
            event (pygame.event.Event): The event to handle.
            entering_focus (object): The object that is entering focus.

        Returns:
            None
        """
        # Synthesized event.

    @abc.abstractmethod
    def on_mouse_unfocus_event(self: Self, event: pygame.event.Event,
                               leaving_focus: object) -> None:
        """Handle mouse unfocus events.

        Args:
            event (pygame.event.Event): The event to handle.
            leaving_focus (object): The object that is leaving focus.

        Returns:
            None
        """
        # Synthesized event.

    @abc.abstractmethod
    def on_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle mouse button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # MOUSEBUTTONUP    pos, button

    @abc.abstractmethod
    def on_left_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle left mouse button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # Left Mouse Button Up pos, button

    @abc.abstractmethod
    def on_middle_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle middle mouse button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # Middle Mouse Button Up pos, button

    @abc.abstractmethod
    def on_right_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle right mouse button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # Right Mouse Button Up pos, button

    @abc.abstractmethod
    def on_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle mouse button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # MOUSEBUTTONDOWN  pos, button

    @abc.abstractmethod
    def on_left_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle left mouse button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # Left Mouse Button Down pos, button

    @abc.abstractmethod
    def on_middle_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle middle mouse button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # Middle Mouse Button Down pos, button

    @abc.abstractmethod
    def on_right_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle right mouse button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # Right Mouse Button Down pos, button

    @abc.abstractmethod
    def on_mouse_scroll_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle mouse scroll down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # This is a synthesized event.

    @abc.abstractmethod
    def on_mouse_scroll_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle mouse scroll up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # This is a synthesized event.

    @abc.abstractmethod
    def on_mouse_wheel_event(self: Self, event: pygame.event.Event) -> None:
        """Handle mouse wheel events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # MOUSEWHEEL flipped, y, x, touch, window


class TextEvents(EventInterface):
    """Mixin for text events."""

    @abc.abstractmethod
    def on_text_editing_event(self: Self, event: pygame.event.Event) -> None:
        """Handle text editing events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # TEXTEDITING      text, start, length

    @abc.abstractmethod
    def on_text_input_event(self: Self, event: pygame.event.Event) -> None:
        """Handle text input events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # TEXTINPUT        text

class WindowEvents(EventInterface):
    """Mixin for window events."""

    @abc.abstractmethod
    def on_window_close_event(self: Self, event: pygame.event.Event) -> None:
        """Handle window close events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWCLOSE      none

    @abc.abstractmethod
    def on_window_enter_event(self: Self, event: pygame.event.Event) -> None:
        """Handle window enter events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWENTER      none

    @abc.abstractmethod
    def on_window_exposed_event(self: Self, event: pygame.event.Event) -> None:
        """Handle window exposed events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWEXPOSED    none

    @abc.abstractmethod
    def on_window_focus_gained_event(self: Self, event: pygame.event.Event) -> None:
        """Handle window focus gained events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWFOCUSGAINED none

    @abc.abstractmethod
    def on_window_focus_lost_event(self: Self, event: pygame.event.Event) -> None:
        """Handle window focus lost events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWFOCUSLOST  none

    @abc.abstractmethod
    def on_window_hidden_event(self: Self, event: pygame.event.Event) -> None:
        """Handle window hidden events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWHIDDEN     none

    @abc.abstractmethod
    def on_window_hit_test_event(self: Self, event: pygame.event.Event) -> None:
        """Handle window hit test events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWHITTEST    none

    @abc.abstractmethod
    def on_window_leave_event(self: Self, event: pygame.event.Event) -> None:
        """Handle window leave events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWLEAVE      none

    @abc.abstractmethod
    def on_window_maximized_event(self: Self, event: pygame.event.Event) -> None:
        """Handle window maximized events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWMAXIMIZED  none

    @abc.abstractmethod
    def on_window_minimized_event(self: Self, event: pygame.event.Event) -> None:
        """Handle window minimized events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWMINIMIZED  none

    @abc.abstractmethod
    def on_window_moved_event(self: Self, event: pygame.event.Event) -> None:
        """Handle window moved events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWMOVED      none

    @abc.abstractmethod
    def on_window_resized_event(self: Self, event: pygame.event.Event) -> None:
        """Handle window resized events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWRESIZED    size, w, h

    @abc.abstractmethod
    def on_window_restored_event(self: Self, event: pygame.event.Event) -> None:
        """Handle window restored events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWRESTORED   none

    @abc.abstractmethod
    def on_window_shown_event(self: Self, event: pygame.event.Event) -> None:
        """Handle window shown events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWSHOWN      none

    @abc.abstractmethod
    def on_window_size_changed_event(self: Self, event: pygame.event.Event) -> None:
        """Handle window size changed events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWSIZECHANGED size, w, h

    @abc.abstractmethod
    def on_window_take_focus_event(self: Self, event: pygame.event.Event) -> None:
        """Handle window take focus events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # WINDOWTAKEFOCUS  none


# Mixin for all events
class AllEvents(AudioEvents,
                ControllerEvents,
                DropEvents,
                TouchEvents,
                FontEvents,
                GameEvents,
                JoystickEvents,
                KeyboardEvents,
                MidiEvents,
                MouseEvents,
                TextEvents,
                WindowEvents):
    """Mixin for all events."""


class EventManager(ResourceManager):
    """Root event manager."""

    log: logging.Logger = LOG
    # Interiting from object is default in Python 3.
    # Linters complain if you do it.
    #
    # This isn't a ResourceManager like other proxies, because
    # it's the fallthrough event object, so we don't have a proxy.

    class EventProxy:
        """Proxy for events."""

        log: logging.Logger = LOG

        def __init__(self: Self, event_source: object) -> None:
            """Initialize the event proxy.

            Args:
                event_source: The event source.

            Returns:
                None
            """
            super().__init__()
            # No proxies for the root class.
            self.proxies = []

            # This is used for leave objects which
            # don't have their own proxies.
            #
            # Subclassed managers that set their own proxy
            # will not have this.
            self.event_source = event_source

        def unhandled_event(self: Self, *args, **kwargs) -> None:
            """Handle unhandled events.

            Args:
                *args: The positional arguments.
                **kwargs: The keyword arguments.

            Returns:
                None
            """
            # inspect.stack()[1] is the call frame above us, so this should be reasonable.
            event_handler = inspect.stack()[1].function

            event = kwargs.get('event')

            event_trigger = kwargs.get('trigger', None)

            self.log.debug(
                f'Unhandled Event {event_handler}: '
                f'{self.event_source}->{event} Event Trigger: {event_trigger}'
            )

        def __getattr__(self: Self, attr: str) -> Callable:
            """Get an attribute.

            This method is called when an attribute is not found.

            Args:
                attr: The attribute to get.

            Returns:
                The attribute.
            """
            return self.unhandled_event

    def __init__(self: Self, game: object = None) -> None:
        """Initialize the event manager.

        Args:
            game: The game instance.

        Returns:
            None
        """
        super().__init__(game)
        self.proxies = [EventManager.EventProxy(event_source=self)]
