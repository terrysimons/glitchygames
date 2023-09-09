#!/usr/bin/env python3
# ruff: noqa: FBT001, FBT002
"""Glitchy Games Engine sprite module."""
from __future__ import annotations

import collections
import configparser
import logging
from pathlib import Path
from typing import ClassVar, Self, cast

import pygame

from glitchygames.events import MouseEvents
from glitchygames.interfaces import SpriteInterface
from glitchygames.pixels import rgb_triplet_generator

LOG = logging.getLogger('game.sprites')
LOG.addHandler(logging.NullHandler())


class RootSprite(MouseEvents, SpriteInterface, pygame.sprite.DirtySprite):
    """A root sprite class.  All Glitchy Games sprites inherit from this class."""

    def __init__(
            self: Self,
            groups: pygame.sprite.LayeredDirty | None = None
        ) -> None:
        """Initialize a RootSprite.

        Args:
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

        Returns:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(groups)
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.image = None


class Sprite(RootSprite):
    """A convenience class for handling all of the common sprite behaviors."""

    log = LOG
    USE_GFXDRAW: ClassVar = False
    PROXIES: ClassVar = [pygame.sprite]
    SPRITE_BREAKPOINTS: ClassVar = None  # None means no breakpoints.  Empty list means all.
    SPRITE_COUNTERS: ClassVar = collections.OrderedDict()
    SPRITE_COUNT = 0

    @classmethod
    def break_when(cls: Self, sprite_type: object | None = None) -> None:
        """Register a breakpoint for a sprite type.

        Args:
            sprite_type (object | None): The sprite type to break on.
            None means break on any sprite.

        Returns:
            None
        """
        # None means disabled.
        # [] means any.
        if cls.SPRITE_BREAKPOINTS is None:
            cls.SPRITE_BREAKPOINTS = []

        # If none, break always.
        if sprite_type is not None:
            LOG.info(f'Register break when sprite_type=={cls}')
            cls.SPRITE_BREAKPOINTS.append(str(cls))
        else:
            LOG.info('Register break when sprite_type==<any>')

    def __init__(self: Self, x: int, y: int, width: int, height: int, name: str | None = None,
                 parent: object | None = None,
                 groups: pygame.sprite.LayeredDirty | None = None) -> None:
        """Initialize a Sprite.

        Args:
            x (int): The x coordinate of the sprite.
            y (int): The y coordinate of the sprite.
            width (int): The width of the sprite.
            height (int): The height of the sprite.
            name (str | None): The name of the sprite.
            parent (object | None): The parent of the sprite.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

        Returns:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(groups)
        # This is the stuff pygame really cares about.
        self.image = pygame.Surface((width, height))
        self.rect = self.image.get_rect()

        self.dt = 0
        self.dt_timer = 0

        self.rect.x = x
        self.rect.y = y
        self.rect.width = int(width)
        self.rect.height = int(height)

        self.name = name
        self.parent = parent
        self.proxies = [self]

        # For debugging sanity.
        if not name:
            self.name = type(self)

        if not self.width:
            self.log.error(f'{type(self)} has 0 Width')

        if not self.height:
            self.log.error(f'{type(self)} has 0 Height')

        # Sprites can register callbacks for any event type.
        self.callbacks = {}

        # Each sprite maintains a reference to the screen.
        self.screen = pygame.display.get_surface()
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()

        groups.add(self)

        # Add ourselves to the sprite counters.
        my_type = str(type(self))

        if my_type in self.SPRITE_COUNTERS:
            self.SPRITE_COUNTERS[my_type]['count'] += 1
            self.SPRITE_COUNTERS[my_type]['pixels'] = \
                self.width * self.height + self.SPRITE_COUNTERS[my_type]['pixels']
        else:
            self.SPRITE_COUNTERS[my_type] = collections.OrderedDict()
            self.SPRITE_COUNTERS[my_type]['count'] = 1
            self.SPRITE_COUNTERS[my_type]['pixels'] = 0
        self.SPRITE_COUNT += 1

        # None means disabled.
        if self.SPRITE_BREAKPOINTS is not None:
            # Empty list means all.
            if len(self.SPRITE_BREAKPOINTS) == 0:
                self.log.info(f'Break when sprite_type=={type(self)}')
                # This breakpoint is intentional
                breakpoint()  # noqa: T100
            else:
                for sprite_type in self.SPRITE_BREAKPOINTS:
                    # This breakpoint is intentional
                    breakpoint()  # noqa: T100
                    if str(type(self)) == sprite_type:
                        self.log.info('Break when sprite_type==<any>')

                        # This breakpoint is intentional
                        breakpoint()  # noqa: T100

    @property
    def width(self: Self) -> int:
        """Return the width of the sprite.

        Args:
            None

        Returns:
            int: The width of the sprite.
        """
        return self.rect.width

    @width.setter
    def width(self: Self, new_width: int) -> None:
        """Set the width of the sprite.

        Args:
            new_width (int): The new width of the sprite.

        Returns:
            None
        """
        self.rect.width = new_width
        self.dirty = 1 if not self.dirty else self.dirty

    @property
    def height(self: Self) -> int:
        """Return the height of the sprite.

        Args:
            None

        Returns:
            int: The height of the sprite.
        """
        return self.rect.height

    @height.setter
    def height(self: Self, new_height: int) -> None:
        """Set the height of the sprite.

        Args:
            new_height (int): The new height of the sprite.

        Returns:
            None
        """
        self.rect.height = new_height
        self.dirty = 1 if not self.dirty else self.dirty

    def dt_tick(self: Self, dt: float) -> None:
        """Update the sprite's delta time.

        Args:
            dt (float): The new delta time.

        Returns:
            None
        """
        self.dt = dt
        self.dt_timer += self.dt

    def update(self: Self) -> None:
        """Update the sprite.

        Args:
            None

        Returns:
            None
        """

    def on_joy_axis_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a joystick axis motion event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # JOYAXISMOTION    joy, axis, value
        self.log.debug(f'{type(self)}: {event}')

    def on_joy_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a joystick button down event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # JOYBUTTONDOWN    joy, button
        self.log.debug(f'{type(self)}: {event}')

    def on_joy_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a joystick button up event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # JOYBUTTONUP      joy, button
        self.log.debug(f'{type(self)}: {event}')

    def on_joy_hat_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a joystick hat motion event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # JOYHATMOTION     joy, hat, value
        self.log.debug(f'{type(self)}: {event}')

    def on_joy_ball_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a joystick ball motion event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # JOYBALLMOTION    joy, ball, rel
        self.log.debug(f'{type(self)}: {event}')

    def on_mouse_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a mouse motion event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # MOUSEMOTION      pos, rel, buttons
        self.log.debug(f'Mouse Motion Event: {type(self)}: {event}')

    def on_mouse_focus_event(self: Self, event: pygame.event.Event, old_focus: object) -> None:
        """Handle a mouse focus event.

        Args:
            event (pygame.event.Event): The event to handle.
            old_focus (object): The old focus.

        Returns:
            None
        """
        # Custom Event
        self.log.debug(f'Mouse Focus Event: {type(self)}: {event}, Old Focus: {old_focus}')

    def on_mouse_unfocus_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a mouse unfocus event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # Custom Event
        self.log.debug(f'Mouse Unfocus Event: {type(self)}: {event}')

    def on_mouse_enter_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a mouse enter event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # Custom Event
        self.log.debug(f'Mouse Enter Event: {type(self)}: {event}')

    def on_mouse_exit_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a mouse exit event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # Custom Event
        self.log.debug(f'Mouse Exit Event: {type(self)}: {event}')

    def on_mouse_drag_down_event(self: Self, event: pygame.event.Event,
                                 trigger: object | None) -> None:
        """Handle a mouse drag down event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None
        """
        self.log.debug(f'Mouse Drag Down Event: {type(self)}: event: {event}, trigger: {trigger}')

    def on_left_mouse_drag_down_event(self: Self, event: pygame.event.Event,
                                      trigger: object | None) -> None:
        """Handle a left mouse drag down event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None
        """
        self.log.debug(
            'Left Mouse Drag Down Event: '
            f'{type(self)}: event: {event}, trigger: {trigger}'
        )

    def on_left_mouse_drag_up_event(self: Self, event: pygame.event.Event,
                                    trigger: object | None) -> None:
        """Handle a left mouse drag up event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None
        """
        self.log.debug(
            'Left Mouse Drag Up Event: '
            f'{type(self)}: event: {event}, trigger: {trigger}'
        )

    def on_middle_mouse_drag_down_event(self: Self, event: pygame.event.Event,
                                        trigger: object | None) -> None:
        """Handle a middle mouse drag down event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None
        """
        self.log.debug(
            'Middle Mouse Drag Down Event: '
            f'{type(self)}: event: {event}, trigger: {trigger}'
        )

    def on_middle_mouse_drag_up_event(self: Self, event: pygame.event.Event,
                                      trigger: object | None) -> None:
        """Handle a middle mouse drag up event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None
        """
        self.log.debug(
            'Middle Mouse Drag Up Event: '
            f'{type(self)}: event: {event}, trigger: {trigger}'
        )

    def on_right_mouse_drag_down_event(self: Self, event: pygame.event.Event,
                                       trigger: object | None) -> None:
        """Handle a right mouse drag down event.

        Args:
        event (pygame.event.Event): The event to handle.
        trigger (object | None): The object that triggered the event.

        Returns:
            None
        """
        self.log.debug(
            'Right Mouse Drag Down Event: '
            f'{type(self)}: event: {event}, trigger: {trigger}'
        )

    def on_right_mouse_drag_up_event(self: Self, event: pygame.event.Event,
                                     trigger: object | None) -> None:
        """Handle a right mouse drag up event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None
        """
        self.log.debug(
            'Right Mouse Drag Up Event: '
            f'{type(self)}: event: {event}, trigger: {trigger}'
        )

    def on_mouse_drag_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a mouse drag up event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'Mouse Drag Up Event: {type(self)}: {event}')

    def on_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a mouse button up event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # MOUSEBUTTONUP    pos, button
        self.log.debug(f'{type(self)}: {event}')

    def on_left_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a left mouse button up event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # MOUSEBUTTONUP    pos, button

        if self.callbacks:
            callback = self.callbacks.get('on_left_mouse_button_up_event', None)
            if callback:
                callback(event=event, trigger=self)
        else:
            self.log.debug(
                f'{type(self)}: '
                f'Left Mouse Button Up Event: {event} @ {self}'
            )

    def on_middle_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a middle mouse button up event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # MOUSEBUTTONUP    pos, button
        self.log.debug(f'{type(self)}: Middle Mouse Button Up Event: {event}')

    def on_right_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a right mouse button up event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # MOUSEBUTTONUP    pos, button
        if self.callbacks:
            callback = self.callbacks.get('on_right_mouse_button_up_event', None)
            if callback:
                callback(event=event, trigger=self)
        else:
            self.log.debug(
                f'{type(self)}: '
                f'Right Mouse Button Up Event: {event} @ {self}'
            )

    def on_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a mouse button down event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # MOUSEBUTTONDOWN  pos, button
        self.log.debug(f'{type(self)}: {event} @ {self}')

    def on_left_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a left mouse button down event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # MOUSEBUTTONDOWN  pos, button
        callback = 'on_left_mouse_button_down_event'

        if self.callbacks:
            callback = self.callbacks.get('on_left_mouse_button_down_event', None)
            if callback:
                callback(event=event, trigger=self)
        else:
            self.log.debug(f'{type(self)}: Left Mouse Button Down Event: {event} @ {self}')

    def on_middle_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a middle mouse button down event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # MOUSEBUTTONDOWN  pos, button
        self.log.debug(f'{type(self)}: Middle Mouse Button Down Event: {event}')

    def on_right_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a right mouse button down event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # MOUSEBUTTONDOWN  pos, button
        if self.callbacks:
            callback = self.callbacks.get('on_right_mouse_button_down_event', None)
            if callback:
                callback(event=event, trigger=self)
        else:
            self.log.debug(f'{type(self)}: Right Mouse Button Down Event: {event} @ self')

    def on_mouse_scroll_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a mouse scroll down event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # MOUSEBUTTONDOWN  pos, button
        self.log.debug(f'{type(self)}: Mouse Scroll Down Event: {event}')

    def on_mouse_scroll_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a mouse scroll up event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # MOUSEBUTTONDOWN  pos, button
        self.log.debug(f'{type(self)}: Mouse Scroll Up Event: {event}')

    def on_mouse_chord_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a mouse chord up event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)}: Mouse Chord Up Event: {event}')

    def on_mouse_chord_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a mouse chord down event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        self.log.debug(f'{type(self)}: Mouse Chord Down Event: {event}')

    def on_key_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a key down event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # KEYDOWN          unicode, key, mod
        self.log.debug(f'{type(self)}: {event}')

    def on_key_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a key up event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # KEYUP            key, mod
        self.log.debug(f'{type(self)}: {event}')

    def on_key_chord_down_event(self: Self, event: pygame.event.Event, keys: list) -> None:
        """Handle a key chord down event.

        Args:
            event (pygame.event.Event): The event to handle.
            keys (list): The keys that were pressed.

        Returns:
            None
        """
        self.log.debug(f'{type(self)}: {event}, {keys}')

    def on_key_chord_up_event(self: Self, event: pygame.event.Event, keys: list) -> None:
        """Handle a key chord up event.

        Args:
            event (pygame.event.Event): The event to handle.
            keys (list): The keys that were pressed.

        Returns:
            None
        """
        self.log.debug(f'{type(self)} KEYCHORDUP: {event}, {keys}')

    def on_quit_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a quit event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # QUIT             none
        self.log.debug(f'{type(self)}: {event}')
        self.terminate()

    def on_active_event(self: Self, event: pygame.event.Event) -> None:
        """Handle an active event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # ACTIVEEVENT      gain, state
        self.log.debug(f'{type(self)}: {event}')

    def on_video_resize_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a video resize event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # VIDEORESIZE      size, w, h
        self.log.debug(f'{type(self)}: {event}')

    def on_video_expose_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a video expose event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # VIDEOEXPOSE      none
        self.log.debug(f'{type(self)}: {event}')

    def on_sys_wm_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a sys wm event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # SYSWMEVENT
        self.log.debug(f'{type(self)}: {event}')

    def on_user_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a user event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None
        """
        # USEREVENT        code
        self.log.debug(f'{type(self)}: {event}')

    # def __getattr__(self, attr):
    #    import pdb; pdb.set_trace()

    #    # Try each proxy in turn
    #    for proxy in type(self).PROXIES:
    #        try:
    #            it = getattr(super(), attr)
    #            import pdb; pdb.set_trace()
    #            return getattr(proxy, attr)
    #        except AttributeError:
    #            log.error(f'No proxies for {type(self)}.{attr}')

    def __str__(self: Self) -> str:
        """Returns a string representation of the sprite."""
        return f'{type(self)} "{self.name}" ({self!r})'


class BitmappySprite(Sprite):
    """A sprite that loads from a Bitmappy config file."""
    DEBUG = False

    DEFAULT_SURFACE_W = 42
    DEFAULT_SURFACE_H = 42
    DEFAULT_SURFACE = pygame.Surface((DEFAULT_SURFACE_W, DEFAULT_SURFACE_H))

    def __init__(self: Self, x: int, y: int, width: int, height: int, name: str | None = None,
                 filename: str | None = None, focusable: bool = False, parent: object = None,
                 groups: pygame.sprite.LayeredDirty | None = None) -> None:
        """Subclass to load sprite files.

        Args:
            x: the x coordinate of the sprite.
            y: the y coordinate of the sprite.
            width: the width of the sprite.
            height: the height of the sprite.
            name: optional, the name of the sprite.
            filename: optional, the BitmappySprite config to load.
            focusable: optional, whether or not the sprite can receive focus.
            parent: optional, the parent of the sprite.
            groups: optional, the sprite groups to add the sprite to.

        Returns:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            parent=parent,
            groups=groups
        )
        self.filename = filename
        self.focusable = focusable
        # self.width = width
        # self.height = height

        # Try to load a file if one was specified, otherwise
        # if a width and height is specified, make a surface.
        if filename:
            (self.image, self.rect, self.name) = self.load(filename=filename)
            self.width = self.rect.width
            self.height = self.rect.height

        elif self.width and self.height:
            self.image = pygame.Surface((self.width, self.height))
            self.image.convert()
        else:
            raise pygame.error(f"Can't create Surface(({self.width}, {self.height})).")

        self.rect = self.image.get_rect()
        self.parent = parent
        self.rect.x = x
        self.rect.y = y
        self.proxies = [self.parent]

    def load(self: Self, filename: str) -> tuple[pygame.Surface, pygame.Rect, str]:
        """Load a sprite from a Bitmappy config file.

        Args:
            filename: the filename of the Bitmappy config file.

        Returns:
            A tuple containing the sprite's image, rect, and name.

        Raises:
            configparser.NoSectionError: if the config file is missing a section.
            configparser.NoOptionError: if the config file is missing an option.
        """
        config = configparser.ConfigParser(dict_type=collections.OrderedDict,
                                           empty_lines_in_values=True,
                                           strict=True)

        config.read(filename)

        # [sprite]
        # name = <name>
        try:
            name = config.get(section='sprite', option='name')
        except configparser.NoSectionError:
            return (self.DEFAULT_SURFACE, self.DEFAULT_SURFACE.get_rect(), 'No Section')

        # pixels = <pixels>
        try:
            pixels = config.get(section='sprite', option='pixels').split('\n')
        except configparser.NoSectionError:
            return (self.DEFAULT_SURFACE, self.DEFAULT_SURFACE.get_rect(), 'No Section')
        except configparser.NoOptionError:
            return (self.DEFAULT_SURFACE, self.DEFAULT_SURFACE.get_rect(), 'No Option')

        # Set our sprite's length and width.
        width = 0
        height = 0
        index = -1

        # This is a bit of a cleanup in case the config contains something like:
        #
        # pixels = \n
        #  .........
        #
        while not width:
            index += 1

            # Width of the first row.  Each row is expected to be identical.
            width = len(pixels[0])

            # The total # of rows is our height
            height = len(pixels)

        # Trim any dead whitespace.
        # We're off by one since we increment the index above
        pixels = pixels[index:]

        color_map = {}
        for section in config.sections():
            # This is checking the length of the section's name.
            # Colors are length 1.  This works with unicode, too.
            if len(section) == 1:
                red = config.getint(section=section, option='red')
                green = config.getint(section=section, option='green')
                blue = config.getint(section=section, option='blue')

                color_map[section] = (red, green, blue)

        (image, rect) = self.inflate(width=width,
                                     height=height,
                                     pixels=pixels,
                                     color_map=color_map)

        return (image, rect, name)

    def inflate(self: Self, width: int, height: int, pixels: list,
                color_map: dict) -> tuple[pygame.Surface, pygame.Rect]:
        """Inflate a sprite from a list of pixels.

        Args:
            width: the width of the sprite.
            height: the height of the sprite.
            pixels: the list of pixels.
            color_map: the color map.

        Returns:
            A tuple containing the sprite's image and rect.

        Raises:
            None
        """
        image = pygame.Surface((width, height))
        image.convert()

        raw_pixels = []
        for y, row in enumerate(pixels):
            for x, pixel in enumerate(row):
                color = color_map[pixel]
                raw_pixels.append(color)
                pygame.draw.rect(image, color, (x, y, 1, 1))

        return (image, image.get_rect())

    def save(self: Self, filename: str) -> None:
        """Save a sprite to a Bitmappy config file.

        Args:
            filename: the filename of the Bitmappy config file.

        Returns:
            None

        Raises:
            None
        """
        config = self.deflate()

        with Path.open(filename, 'w') as deflated_sprite:
            config.write(deflated_sprite)

    def deflate(self: Self) -> dict:
        """Deflate a sprite to a Bitmappy config file.

        Args:
            None

        Returns:
            A dict containing the sprite's config.

        Raises:
            None
        """
        config = configparser.ConfigParser(dict_type=collections.OrderedDict,
                                           empty_lines_in_values=True,
                                           strict=True)

        # Get the set of distinct pixels.
        color_map = {}
        pixels = []

        raw_pixels = rgb_triplet_generator(
            pixel_data=pygame.image.tostring(self.image, 'RGB')
        )

        # We're utilizing the generator to give us RGB triplets.
        # We need a list here becasue we'll use set() to pull out the
        # unique values, but we also need to consume the list again
        # down below, so we can't solely use a generator.
        raw_pixels = list(raw_pixels)

        # This gives us the unique rgb triplets in the image.
        colors = set(raw_pixels)

        config.add_section('sprite')
        config.set('sprite', 'name', self.name)

        # Generate the color key
        color_key = chr(47)
        for color in colors:
            # Characters above doublequote.
            color_key = chr(ord(color_key) + 1)
            config.add_section(color_key)

            color_map[color] = color_key

            self.log.debug(f'Key: {color} -> {color_key}')

            red = color[0]
            config.set(color_key, 'red', str(red))

            green = color[1]
            config.set(color_key, 'green', str(green))

            blue = color[2]
            config.set(color_key, 'blue', str(blue))

        x = 0
        row = []
        while raw_pixels:
            row.append(color_map[raw_pixels.pop(0)])
            x += 1

            if x % self.rect.width == 0:
                self.log.debug(f'Row: {row}')
                pixels.append(''.join(row))
                row = []
                x = 0

        self.log.debug(pixels)

        config.set('sprite', 'pixels', '\n'.join(pixels))

        self.log.debug(f'Deflated Sprite: {config}')

        return config

class Singleton:
    """A generic singleton class."""
    __instance__ = None

    def __new__(cls: Self, *args, **kwargs) -> Self:
        """Create a new instance of the Singleton.

        Args:
            *args: The arguments to pass to the constructor.
            **kwargs: The keyword arguments to pass to the constructor.

        Returns:
            Singleton: The instance of the Singleton.
        """
        if cls.__instance__ is None:
            cls.__instance__ = object.__new__(cls)
        cls.__instance__.args = args
        cls.__instance__.kwargs = kwargs
        return cast(Singleton, cls.__instance__)

# This is a root class for sprites that should be singletons, like
#  MousePointer class.
class SingletonBitmappySprite(BitmappySprite):
    """A singleton class for handling singleton sprites, like mouse pointers."""

    __instance__ = None

    def __new__(cls: Self, *args, **kwargs) -> Self:
        """Create a new instance of the SingletonBitmappySprite.

        Args:
            *args: The arguments to pass to the constructor.
            **kwargs: The keyword arguments to pass to the constructor.

        Returns:
            SingletonBitmappySprite: The instance of the SingletonBitmappySprite.
        """
        if cls.__instance__ is None:
            cls.__instance__ = object.__new__(cls)
        cls.__instance__.args = args
        cls.__instance__.kwargs = kwargs
        return cast(SingletonBitmappySprite, cls.__instance__)

    def __init__(self: Self, x: int, y: int, width: int, height: int, name: str | None = None,
                 groups: pygame.sprite.LayeredDirty | None = None) -> None:
        """Initialize the SingletonBitmappySprite.

        Args:
            x (int): The x coordinate of the sprite.
            y (int): The y coordinate of the sprite.
            width (int): The width of the sprite.
            height (int): The height of the sprite.
            name (str): The name of the sprite.
            groups (pygame.sprite.LayeredDirty): The sprite groups to add the sprite to.

        Returns:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(x=x, y=y, width=width, height=height, name=name, groups=groups)


# This is a root class for focusable sprites that should be singletons, like
# the MenuBar class.
class FocusableSingletonBitmappySprite(BitmappySprite):
    """A singleton class for handling all of the focusable sprite behaviors."""

    __instance__ = None

    def __new__(cls: Self, *args, **kwargs) -> Self:
        """Create a new instance of the FocusableSingletonBitmappySprite.

        Args:
            *args: The arguments to pass to the constructor.
            **kwargs: The keyword arguments to pass to the constructor.

        Returns:
            FocusableSingletonBitmappySprite: The instance of the FocusableSingletonBitmappySprite.
        """
        if cls.__instance__ is None:
            cls.__instance__ = object.__new__(cls)
        cls.__instance__.args = args
        cls.__instance__.kwargs = kwargs
        return cast(FocusableSingletonBitmappySprite, cls.__instance__)

    def __init__(self: Self, x: int, y: int, width: int, height: int, name: str | None = None,
                 groups: pygame.sprite.LayeredDirty | None = None) -> None:
        """Initialize the FocusableSingletonBitmappySprite.

        Args:
            x (int): The x coordinate of the sprite.
            y (int): The y coordinate of the sprite.
            width (int): The width of the sprite.
            height (int): The height of the sprite.
            name (str): The name of the sprite.
            groups (pygame.sprite.LayeredDirty): The sprite groups to add the sprite to.

        Returns:
            None
        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(
            x=x, y=y, width=width, height=height,
            name=name, focusable=True, groups=groups
        )

