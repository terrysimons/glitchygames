#!/usr/bin/env python
# -*- coding: utf-8 -*-

import inspect
import logging

log = logging.getLogger('game.events')
log.addHandler(logging.NullHandler())

def unhandled_event(*args, **kwargs):
    #log.info(f'Unhandled Event: args: {args}, kwargs: {kwargs}')
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
    when needed, at the expense of a bit of over abstracting.

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

    __instances__ = {}

    def __new__(cls, *args, **kwargs):
        if cls not in cls.__instances__:
            cls.__instances__[cls] = object.__new__(cls)
            log.debug(f'Created Resource Manager: {cls}')
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
                log.error(f'No proxies for {type(self)}.{attr}')

# Mixin
class FontEvents():
    pass

# Mixin
class KeyboardEvents():
    def on_key_down_event(self, event):
        unhandled_event(target=self, event=event)

    def on_key_up_event(self, event):
        unhandled_event(target=self, event=event)

    def on_key_chord_down_event(self, event):
        unhandled_event(target=self, event=event)        

    def on_key_chord_down_event(self, event):
        unhandled_event(target=self, event=event)


# Mixin
class MouseEvents():
    def on_mouse_motion_event(self, event):
        # MOUSEMOTION      pos, rel, buttons
        #unhandled_event(target=self, event=event)
        pass

    def on_mouse_drag_event(self, event, trigger):
        # Synthesized event.
        #unhandled_event(target=self, event=event, trigger=trigger)
        pass

    def on_mouse_drop_event(self, event, trigger):
        # Synthesized event.
        #unhandled_event(target=self, event=event, trigger=trigger)
        pass

    def on_left_mouse_drag_event(self, event, trigger):
        # Synthesized event.
        #unhandled_event(target=self, event=event, trigger=trigger)
        pass

    def on_left_mouse_drop_event(self, event, trigger):
        # Synthesized event.
        #unhandled_event(target=self, event=event, trigger=trigger)
        pass

    def on_middle_mouse_drag_event(self, event, trigger):
        # Synthesized event.
        #unhandled_event(target=self, event=event, trigger=trigger)
        pass

    def on_middle_mouse_drop_event(self, event, trigger):
        # Synthesized event.
        #unhandled_event(target=self, event=event, trigger=trigger)
        pass

    def on_right_mouse_drag_event(self, event, trigger):
        # Synthesized event.
        #unhandled_event(target=self, event=event, trigger=trigger)
        pass

    def on_right_mouse_drop_event(self, event, trigger):
        # Synthesized event.
        #unhandled_event(target=self, event=event, trigger=trigger)
        pass

    def on_mouse_focus_event(self, event, entering_focus):
        # Synthesized event.
        #unhandled_event(target=self, event=event, entering_focus=entering_focus)
        pass

    def on_mouse_unfocus_event(self, event, leaving_focus):
        # Synthesized event.
        #unhandled_event(event, leaving_focus=leaving_focus)
        pass

    def on_mouse_button_up_event(self, event):
        # MOUSEBUTTONUP    pos, button
        #unhandled_event(target=self, event=event)
        pass

    def on_left_mouse_button_up_event(self, event):
        # Left Mouse Button Up pos, button
        #unhandled_event(target=self, event=event)
        pass

    def on_middle_mouse_button_up_event(self, event):
        # Middle Mouse Button Up pos, button
        #unhandled_event(target=self, event=event)
        pass

    def on_right_mouse_button_up_event(self, event):
        # Right Mouse Button Up pos, button
        #unhandled_event(target=self, event=event)
        pass

    def on_mouse_button_down_event(self, event):
        # MOUSEBUTTONDOWN  pos, button
        #unhandled_event(target=self, event=event)
        pass

    def on_left_mouse_button_down_event(self, event):
        # Left Mouse Button Down pos, button
        #unhandled_event(target=self, event=event)
        pass

    def on_middle_mouse_button_down_event(self, event):
        # Middle Mouse Button Down pos, button
        #unhandled_event(target=self, event=event)
        pass

    def on_right_mouse_button_down_event(self, event):
        # Right Mouse Button Down pos, button
        #unhandled_event(target=self, event=event)
        pass

    def on_mouse_scroll_down_event(self, event):
        # This is a synthesized event.
        #unhandled_event(target=self, event=event)
        pass

    def on_mouse_scroll_up_event(self, event):
        # This is a synthesized event.
        #unhandled_event(target=self, event=event)
        pass

# Mixin
class JoystickEvents():
    def on_axis_motion_event(self, event):
        # JOYAXISMOTION    joy, axis, value
        unhandled_event(target=self, event=event)

    def on_button_down_event(self, event):
        # JOYBUTTONDOWN    joy, button
        unhandled_event(target=self, event=event)

    def on_button_up_event(self, event):
        # JOYBUTTONUP      joy, button
        unhandled_event(target=self, event=event)

    def on_hat_motion_event(self, event):
        # JOYHATMOTION     joy, hat, value
        unhandled_event(target=self, event=event)

    def on_ball_motion_event(self, event):
        # JOYBALLMOTION    joy, ball, rel
        unhandled_event(target=self, event=event)

class EventManager(ResourceManager):
    # Interiting from object is default in Python 3.
    # Linters complain if you do it.
    #
    # This isn't a ResourceManager like other proxies, because
    # it's the fallthrough event object, so we don't have a proxy.
    class EventProxy():
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

            log.debug(f'Unhandled Event {event_handler}: '
                      f'{self.event_source}->{event} Event Trigger: {event_trigger}')

            #unhandled_event(*args, **kwargs)

        #def on_active_event(self, event):
            # ACTIVEEVENT      gain, state
            #unhandled_event(source=self.event_source, target=self, event=event)
        #    pass

        #def on_key_up_event(self, event):
            # KEYUP            key, mod
        #    unhandled_event(target=self, event=event)

        #def on_key_down_event(self, event):
            # KEYDOWN            key, mod
        #    unhandled_event(target=self, event=event)

        #def on_key_chord_down_event(self, event, trigger):
            # This is a synthesized event.
        #    unhandled_event(target=self, event=event, trigger=trigger)

        #def on_key_chord_up_event(self, event, trigger):
            # This is a synthesized event.
        #    unhandled_event(target=self, event=event, trigger=trigger)
        #def __getattribute__(self, attr):
        #    log.info(f'__getattribute__: {attr}')
        #    import pdb; pdb.set_trace()

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

