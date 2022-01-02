#!/usr/bin/env python
# -*- coding: utf-8 -*-

import inspect
import logging
import re

import pygame

LOG = logging.getLogger('game.events')
LOG.addHandler(logging.NullHandler())


def supported_events(like='.*'):
    # Get a list of all of the events
    # by name, but ignore duplicates.
    event_names = [*set(pygame.event.event_name(event_num)
                        for event_num in range(0, pygame.NUMEVENTS))]
    event_names = set(event_names) - set('Unknown')
    event_list = []

    for event_name in list(event_names):
        try:
            if re.match(like, event_name.upper()):
                event_list.append(getattr(pygame, event_name.upper()))
        except AttributeError as e:
            LOG.error(f'Failed to init: {e}')

    return event_list


# Pygame USEREVENTs
FPSEVENT = pygame.USEREVENT + 1
GAMEEVENT = pygame.USEREVENT + 2
MENUEVENT = pygame.USEREVENT + 3

AUDIO_EVENTS = supported_events(like='AUDIO.*?')
# TODO: CONTROLLER_EVENTS = supported_events(like='CONTROLLER.*?')
DROP_EVENTS = supported_events(like='DROP.*?')
FINGER_EVENTS = supported_events(like='(FINGER|MULTI).*?')
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
    set(DROP_EVENTS) -
    set(FINGER_EVENTS) -
    set(JOYSTICK_EVENTS) -
    set(KEYBOARD_EVENTS) -
    set(MIDI_EVENTS) -
    set(MOUSE_EVENTS) -
    set(TEXT_EVENTS) -
    set(WINDOW_EVENTS)
)

GAME_EVENTS.append(FPSEVENT)
GAME_EVENTS.append(GAMEEVENT)
GAME_EVENTS.append(MENUEVENT)


def unhandled_event(*args, **kwargs):
    LOG.error(f'Unhandled Event: args: {args}, kwargs: {kwargs}')
    raise AttributeError(f'Unhandled Event: args: {args}, kwargs: {kwargs}')


# Interiting from object is default in Python 3.
# Linters complain if you do it.
class ResourceManager:
    """
    Singleton aggregator base class for event proxies.

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
    log = LOG

    __instances__ = {}

    def __new__(cls, *args, **kwargs):
        if cls not in cls.__instances__:
            cls.__instances__[cls] = object.__new__(cls)
            LOG.debug(f'Created Resource Manager: {cls}')
            cls.__instances__[cls].args = args
            cls.__instances__[cls].kwargs = kwargs

        return cls.__instances__[cls]

    def __init__(self, game):  # noqa: W0613
        super().__init__()
        self.proxies = []

    def __getattr__(self, attr):
        # Try each proxy in turn
        for proxy in self.proxies:
            try:
                return getattr(proxy, attr)
            except AttributeError:
                self.log.error(f'No proxies for {type(self)}.{attr}')
                raise


# Mixin
class AudioEvents:
    def on_audio_device_added_event(self, event):
        # AUDIODEVICEADDED   which, iscapture
        pass

    def on_audio_device_removed_event(self, event):
        # AUDIODEVICEREMOVED which, iscapture
        pass


# Mixin
class DropEvents:
    def on_drop_begin_event(self, event):
        pass

    def on_drop_file_event(self, event):
        pass

    def on_drop_text_event(self, event):
        pass

    def on_drop_complete_event(self, event):
        pass


# Mixin
class GameEvents:
    def on_active_event(self, event):
        # ACTIVEEVENT      gain, state
        pass

    def on_fps_event(self, event):
        # FPSEVENT is pygame.USEREVENT + 1
        pass

    def on_game_event(self, event):
        # GAMEEVENT is pygame.USEREVENT + 2
        pass

    def on_menu_item_event(self, event):
        # MENUEVENT is pygame.USEREVENT + 3
        pass

    def on_sys_wm_event(self, event):
        # SYSWMEVENT
        pass

    def on_user_event(self, event):
        # USEREVENT        code
        pass

    def on_video_expose_event(self, event):
        # VIDEOEXPOSE      none
        pass

    def on_video_resize_event(self, event):
        # VIDEORESIZE      size, w, h
        pass

    def on_quit_event(self, event):
        # QUIT             none
        pass


# Mixin
class FontEvents:
    pass


# Mixin
class KeyboardEvents:
    def on_key_down_event(self, event):
        # KEYDOWN          unicode, key, mod
        pass

    def on_key_up_event(self, event):
        # KEYUP            key, mod
        pass

    def on_key_chord_up_event(self, event, keys):
        # Synthesized event.
        pass

    def on_key_chord_down_event(self, event, keys):
        # Synthesized event.
        pass


# Mixin
class JoystickEvents:
    def on_axis_motion_event(self, event):
        # JOYAXISMOTION    joy, axis, value
        pass

    def on_button_down_event(self, event):
        # JOYBUTTONDOWN    joy, button
        pass

    def on_button_up_event(self, event):
        # JOYBUTTONUP      joy, button
        pass

    def on_hat_motion_event(self, event):
        # JOYHATMOTION     joy, hat, value
        pass

    def on_ball_motion_event(self, event):
        # JOYBALLMOTION    joy, ball, rel
        pass


# Mixin
class MouseEvents:
    def on_mouse_motion_event(self, event):
        # MOUSEMOTION      pos, rel, buttons
        pass

    def on_mouse_drag_event(self, event, trigger):
        # Synthesized event.
        pass

    def on_mouse_drop_event(self, event, trigger):
        # Synthesized event.
        pass

    def on_left_mouse_drag_event(self, event, trigger):
        # Synthesized event.
        pass

    def on_left_mouse_drop_event(self, event, trigger):
        # Synthesized event.
        pass

    def on_middle_mouse_drag_event(self, event, trigger):
        # Synthesized event.
        pass

    def on_middle_mouse_drop_event(self, event, trigger):
        # Synthesized event.
        pass

    def on_right_mouse_drag_event(self, event, trigger):
        # Synthesized event.
        pass

    def on_right_mouse_drop_event(self, event, trigger):
        # Synthesized event.
        pass

    def on_mouse_focus_event(self, event, entering_focus):
        # Synthesized event.
        pass

    def on_mouse_unfocus_event(self, event, leaving_focus):
        # Synthesized event.
        pass

    def on_mouse_button_up_event(self, event):
        # MOUSEBUTTONUP    pos, button
        pass

    def on_left_mouse_button_up_event(self, event):
        # Left Mouse Button Up pos, button
        pass

    def on_middle_mouse_button_up_event(self, event):
        # Middle Mouse Button Up pos, button
        pass

    def on_right_mouse_button_up_event(self, event):
        # Right Mouse Button Up pos, button
        pass

    def on_mouse_button_down_event(self, event):
        # MOUSEBUTTONDOWN  pos, button
        pass

    def on_left_mouse_button_down_event(self, event):
        # Left Mouse Button Down pos, button
        pass

    def on_middle_mouse_button_down_event(self, event):
        # Middle Mouse Button Down pos, button
        pass

    def on_right_mouse_button_down_event(self, event):
        # Right Mouse Button Down pos, button
        pass

    def on_mouse_scroll_down_event(self, event):
        # This is a synthesized event.
        pass

    def on_mouse_scroll_up_event(self, event):
        # This is a synthesized event.
        pass

    def on_mouse_wheel_event(self, event):
        # MOUSEWHEEL flipped, y, x, touch, window
        pass


class WindowEvents:
    def on_window_close_event(self, event):
        pass

    def on_window_enter_event(self, event):
        pass

    def on_window_exposed_event(self, event):
        pass

    def on_window_focus_gained_event(self, event):
        pass

    def on_window_focus_lost_event(self, event):
        pass

    def on_window_hidden_event(self, event):
        pass

    def on_window_hit_test_event(self, event):
        pass

    def on_window_leave_event(self, event):
        pass

    def on_window_maximized_event(self, event):
        pass

    def on_window_minimized_event(self, event):
        pass

    def on_window_moved_event(self, event):
        pass

    def on_window_resized_event(self, event):
        pass

    def on_window_restored_event(self, event):
        pass

    def on_window_shown_event(self, event):
        pass

    def on_window_size_changed_event(self, event):
        pass

    def on_window_take_focus_event(self, event):
        pass


# Mixin for all events
class EventInterface(AudioEvents,
                     DropEvents,
                     FontEvents,
                     GameEvents,
                     JoystickEvents,
                     KeyboardEvents,
                     MouseEvents,
                     WindowEvents):
    pass


class EventManager(ResourceManager):
    log = LOG
    # Interiting from object is default in Python 3.
    # Linters complain if you do it.
    #
    # This isn't a ResourceManager like other proxies, because
    # it's the fallthrough event object, so we don't have a proxy.

    class EventProxy():
        log = LOG
        def __init__(self, event_source):  # noqa: W0613
            """
            Catch-all event sink for unhandled game events across all ResourceManagers.

            New EventProxy subclass on_*_event() methods must be added here to avoid crashing.

            Args:
            ----
            event_source -

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

        def unhandled_event(self, *args, **kwargs):  # noqa: W0613
            # inspect.stack()[1] is the call frame above us, so this should be reasonable.
            event_handler = inspect.stack()[1].function

            event = kwargs.get('event')

            event_trigger = kwargs.get('trigger', None)

            self.log.debug(
                f'Unhandled Event {event_handler}: '
                f'{self.event_source}->{event} Event Trigger: {event_trigger}'
            )

        def __getattr__(self, attr):
            return self.unhandled_event

    def __init__(self, game=None):
        """
        Root ResourceManager for other managers.

        EventManager is a special event handler which can proxy pygame
        events.  GameEngine and SceneRoot interit from EventManager,
        which enables us to catch unhandled events.

        New event handling classes should inherit from this
        and add their on_*_event(self, event) handlers to
        the EventProxy class contained herein.

        Args:
        ----
        game - The game instance.

        """
        super().__init__(game)
        self.proxies = [EventManager.EventProxy(event_source=self)]
