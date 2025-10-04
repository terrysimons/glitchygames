#!/usr/bin/env python3
# ruff: noqa: FBT001, FBT002
"""Glitchy Games Engine sprite module."""

from __future__ import annotations

import collections
import configparser
import logging
from pathlib import Path
from typing import Any, ClassVar, Self, cast

import pygame
import toml
import yaml
from glitchygames.events import MouseEvents
from glitchygames.interfaces import SpriteInterface

# Import animated sprite classes
from .animated import AnimatedSprite, AnimatedSpriteInterface, SpriteFrame
from .constants import DEFAULT_FILE_FORMAT, SPRITE_GLYPHS

# Public API
__all__ = [
    "AnimatedSprite",
    "AnimatedSpriteInterface", 
    "BitmappySprite",
    "DEFAULT_FILE_FORMAT",
    "SpriteFactory",
    "SpriteFrame",
    "SPRITE_GLYPHS",
]

LOG = logging.getLogger("game.sprites")
LOG.addHandler(logging.NullHandler())

# Configure logger
LOG = logging.getLogger("game.sprites")
LOG.setLevel(logging.DEBUG)

# Add console handler if none exists
if not LOG.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    LOG.addHandler(ch)


# Configure logger
LOG = logging.getLogger("game.sprites")
LOG.setLevel(logging.DEBUG)

# Add console handler if none exists
if not LOG.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    LOG.addHandler(ch)


class RootSprite(MouseEvents, SpriteInterface, pygame.sprite.DirtySprite):
    """A root sprite class.  All Glitchy Games sprites inherit from this class."""

    def __init__(self: Self, groups: pygame.sprite.LayeredDirty | None = None) -> None:
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
    def break_when(cls: Any, sprite_type: object | None = None) -> None:
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
            LOG.info(f"Register break when sprite_type=={cls}")
            cls.SPRITE_BREAKPOINTS.append(str(cls))
        else:
            LOG.info("Register break when sprite_type==<any>")

    def __init__(
        self: Self,
        x: int,
        y: int,
        width: int,
        height: int,
        name: str | None = None,
        parent: object | None = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
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
            self.log.error(f"{type(self)} has 0 Width")

        if not self.height:
            self.log.error(f"{type(self)} has 0 Height")

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
            self.SPRITE_COUNTERS[my_type]["count"] += 1
            self.SPRITE_COUNTERS[my_type]["pixels"] = (
                self.width * self.height + self.SPRITE_COUNTERS[my_type]["pixels"]
            )
        else:
            self.SPRITE_COUNTERS[my_type] = collections.OrderedDict()
            self.SPRITE_COUNTERS[my_type]["count"] = 1
            self.SPRITE_COUNTERS[my_type]["pixels"] = 0
        self.SPRITE_COUNT += 1

        # None means disabled.
        if self.SPRITE_BREAKPOINTS is not None:
            # Empty list means all.
            if len(self.SPRITE_BREAKPOINTS) == 0:
                self.log.info(f"Break when sprite_type=={type(self)}")
                # This breakpoint is intentional
                breakpoint()  # noqa: T100
            else:
                for sprite_type in self.SPRITE_BREAKPOINTS:
                    # This breakpoint is intentional
                    breakpoint()  # noqa: T100
                    if str(type(self)) == sprite_type:
                        self.log.info("Break when sprite_type==<any>")

                        # This breakpoint is intentional
                        breakpoint()  # noqa: T100

    @property
    def width(self: Self) -> int:
        """Return the width of the sprite.

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
        self.log.debug(f"{type(self)}: {event}")

    def on_joy_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a joystick button down event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # JOYBUTTONDOWN    joy, button
        self.log.debug(f"{type(self)}: {event}")

    def on_joy_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a joystick button up event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # JOYBUTTONUP      joy, button
        self.log.debug(f"{type(self)}: {event}")

    def on_joy_hat_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a joystick hat motion event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # JOYHATMOTION     joy, hat, value
        self.log.debug(f"{type(self)}: {event}")

    def on_joy_ball_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a joystick ball motion event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # JOYBALLMOTION    joy, ball, rel
        self.log.debug(f"{type(self)}: {event}")

    def on_mouse_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a mouse motion event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # MOUSEMOTION      pos, rel, buttons
        self.log.debug(f"Mouse Motion Event: {type(self)}: {event}")

    def on_mouse_focus_event(self: Self, event: pygame.event.Event, old_focus: object) -> None:
        """Handle a mouse focus event.

        Args:
            event (pygame.event.Event): The event to handle.
            old_focus (object): The old focus.

        Returns:
            None

        """
        # Custom Event
        self.log.debug(f"Mouse Focus Event: {type(self)}: {event}, Old Focus: {old_focus}")

    def on_mouse_unfocus_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a mouse unfocus event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # Custom Event
        self.log.debug(f"Mouse Unfocus Event: {type(self)}: {event}")

    def on_mouse_enter_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a mouse enter event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # Custom Event
        self.log.debug(f"Mouse Enter Event: {type(self)}: {event}")

    def on_mouse_exit_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a mouse exit event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # Custom Event
        self.log.debug(f"Mouse Exit Event: {type(self)}: {event}")

    def on_mouse_drag_down_event(
        self: Self, event: pygame.event.Event, trigger: object | None
    ) -> None:
        """Handle a mouse drag down event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(f"Mouse Drag Down Event: {type(self)}: event: {event}, trigger: {trigger}")

    def on_left_mouse_drag_down_event(
        self: Self, event: pygame.event.Event, trigger: object | None
    ) -> None:
        """Handle a left mouse drag down event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(
            f"Left Mouse Drag Down Event: {type(self)}: event: {event}, trigger: {trigger}"
        )

    def on_left_mouse_drag_up_event(
        self: Self, event: pygame.event.Event, trigger: object | None
    ) -> None:
        """Handle a left mouse drag up event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(
            f"Left Mouse Drag Up Event: {type(self)}: event: {event}, trigger: {trigger}"
        )

    def on_middle_mouse_drag_down_event(
        self: Self, event: pygame.event.Event, trigger: object | None
    ) -> None:
        """Handle a middle mouse drag down event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(
            f"Middle Mouse Drag Down Event: {type(self)}: event: {event}, trigger: {trigger}"
        )

    def on_middle_mouse_drag_up_event(
        self: Self, event: pygame.event.Event, trigger: object | None
    ) -> None:
        """Handle a middle mouse drag up event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(
            f"Middle Mouse Drag Up Event: {type(self)}: event: {event}, trigger: {trigger}"
        )

    def on_right_mouse_drag_down_event(
        self: Self, event: pygame.event.Event, trigger: object | None
    ) -> None:
        """Handle a right mouse drag down event.

        Args:
        event (pygame.event.Event): The event to handle.
        trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(
            f"Right Mouse Drag Down Event: {type(self)}: event: {event}, trigger: {trigger}"
        )

    def on_right_mouse_drag_up_event(
        self: Self, event: pygame.event.Event, trigger: object | None
    ) -> None:
        """Handle a right mouse drag up event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(
            f"Right Mouse Drag Up Event: {type(self)}: event: {event}, trigger: {trigger}"
        )

    def on_mouse_drag_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a mouse drag up event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        self.log.debug(f"Mouse Drag Up Event: {type(self)}: {event}")

    def on_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a mouse button up event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # MOUSEBUTTONUP    pos, button
        self.log.debug(f"{type(self)}: {event}")

    def on_left_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a left mouse button up event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # MOUSEBUTTONUP    pos, button

        if self.callbacks:
            callback = self.callbacks.get("on_left_mouse_button_up_event", None)
            if callback:
                callback(event=event, trigger=self)
        else:
            self.log.debug(f"{type(self)}: Left Mouse Button Up Event: {event} @ {self}")

    def on_middle_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a middle mouse button up event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # MOUSEBUTTONUP    pos, button
        self.log.debug(f"{type(self)}: Middle Mouse Button Up Event: {event}")

    def on_right_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a right mouse button up event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # MOUSEBUTTONUP    pos, button
        if self.callbacks:
            callback = self.callbacks.get("on_right_mouse_button_up_event", None)
            if callback:
                callback(event=event, trigger=self)
        else:
            self.log.debug(f"{type(self)}: Right Mouse Button Up Event: {event} @ {self}")

    def on_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a mouse button down event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # MOUSEBUTTONDOWN  pos, button
        self.log.debug(f"{type(self)}: {event} @ {self}")

    def on_left_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a left mouse button down event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # MOUSEBUTTONDOWN  pos, button
        callback = "on_left_mouse_button_down_event"

        if self.callbacks:
            callback = self.callbacks.get("on_left_mouse_button_down_event", None)
            if callback:
                callback(event=event, trigger=self)
        else:
            self.log.debug(f"{type(self)}: Left Mouse Button Down Event: {event} @ {self}")

    def on_middle_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a middle mouse button down event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # MOUSEBUTTONDOWN  pos, button
        self.log.debug(f"{type(self)}: Middle Mouse Button Down Event: {event}")

    def on_right_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a right mouse button down event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # MOUSEBUTTONDOWN  pos, button
        if self.callbacks:
            callback = self.callbacks.get("on_right_mouse_button_down_event", None)
            if callback:
                callback(event=event, trigger=self)
        else:
            self.log.debug(f"{type(self)}: Right Mouse Button Down Event: {event} @ self")

    def on_mouse_scroll_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a mouse scroll down event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # MOUSEBUTTONDOWN  pos, button
        self.log.debug(f"{type(self)}: Mouse Scroll Down Event: {event}")

    def on_mouse_scroll_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a mouse scroll up event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # MOUSEBUTTONDOWN  pos, button
        self.log.debug(f"{type(self)}: Mouse Scroll Up Event: {event}")

    def on_mouse_chord_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a mouse chord up event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        self.log.debug(f"{type(self)}: Mouse Chord Up Event: {event}")

    def on_mouse_chord_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a mouse chord down event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        self.log.debug(f"{type(self)}: Mouse Chord Down Event: {event}")

    def on_key_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a key down event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # KEYDOWN          unicode, key, mod
        self.log.debug(f"{type(self)}: {event}")

    def on_key_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a key up event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # KEYUP            key, mod
        self.log.debug(f"{type(self)}: {event}")

    def on_key_chord_down_event(self: Self, event: pygame.event.Event, keys: list) -> None:
        """Handle a key chord down event.

        Args:
            event (pygame.event.Event): The event to handle.
            keys (list): The keys that were pressed.

        Returns:
            None

        """
        self.log.debug(f"{type(self)}: {event}, {keys}")

    def on_key_chord_up_event(self: Self, event: pygame.event.Event, keys: list) -> None:
        """Handle a key chord up event.

        Args:
            event (pygame.event.Event): The event to handle.
            keys (list): The keys that were pressed.

        Returns:
            None

        """
        self.log.debug(f"{type(self)} KEYCHORDUP: {event}, {keys}")

    def on_quit_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a quit event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # QUIT             none
        self.log.debug(f"{type(self)}: {event}")
        self.terminate()

    def on_active_event(self: Self, event: pygame.event.Event) -> None:
        """Handle an active event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # ACTIVEEVENT      gain, state
        self.log.debug(f"{type(self)}: {event}")

    def on_video_resize_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a video resize event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # VIDEORESIZE      size, w, h
        self.log.debug(f"{type(self)}: {event}")

    def on_video_expose_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a video expose event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # VIDEOEXPOSE      none
        self.log.debug(f"{type(self)}: {event}")

    def on_sys_wm_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a sys wm event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # SYSWMEVENT
        self.log.debug(f"{type(self)}: {event}")

    def on_user_event(self: Self, event: pygame.event.Event) -> None:
        """Handle a user event.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # USEREVENT        code
        self.log.debug(f"{type(self)}: {event}")

    def on_left_mouse_drag_event(
        self: Self, event: pygame.event.Event, trigger: object | None
    ) -> None:
        """Handle a left mouse drag event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(f"{type(self)}: Left Mouse Drag Event: {event} @ {self} for {trigger}")

    def on_middle_mouse_drag_event(
        self: Self, event: pygame.event.Event, trigger: object | None
    ) -> None:
        """Handle a middle mouse drag event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(f"{type(self)}: Middle Mouse Drag Event: {event} @ {self} for {trigger}")

    def on_right_mouse_drag_event(
        self: Self, event: pygame.event.Event, trigger: object | None
    ) -> None:
        """Handle a right mouse drag event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(f"{type(self)}: Right Mouse Drag Event: {event} @ {self} for {trigger}")

    def on_left_mouse_drop_event(
        self: Self, event: pygame.event.Event, trigger: object | None
    ) -> None:
        """Handle a left mouse drop event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(f"{type(self)}: Left Mouse Drop Event: {event} @ {self} for {trigger}")

    def on_middle_mouse_drop_event(
        self: Self, event: pygame.event.Event, trigger: object | None
    ) -> None:
        """Handle a middle mouse drop event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(f"{type(self)}: Middle Mouse Drop Event: {event} @ {self} for {trigger}")

    def on_right_mouse_drop_event(
        self: Self, event: pygame.event.Event, trigger: object | None
    ) -> None:
        """Handle a right mouse drop event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(f"{type(self)}: Right Mouse Drop Event: {event} @ {self} for {trigger}")

    def on_mouse_drag_event(self: Self, event: pygame.event.Event, trigger: object | None) -> None:
        """Handle a mouse drag event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(f"{type(self)}: Mouse Drag Event: {event} @ {self} for {trigger}")

    def on_mouse_drop_event(self: Self, event: pygame.event.Event, trigger: object | None) -> None:
        """Handle a mouse drop event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(f"{type(self)}: Mouse Drop Event: {event} @ {self} for {trigger}")

    def on_mouse_wheel_event(self: Self, event: pygame.event.Event, trigger: object | None) -> None:
        """Handle a mouse wheel event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(f"{type(self)}: Mouse Wheel Event: {event} @ {self} for {trigger}")

    # def __getattr__(self: Self,attr):
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
        """Return a string representation of the sprite."""
        return f'{type(self)} "{self.name}" ({self!r})'


class BitmappySprite(Sprite):
    """A sprite that loads from a Bitmappy config file."""

    DEBUG = False
    DEFAULT_SURFACE_W = 42
    DEFAULT_SURFACE_H = 42
    DEFAULT_SURFACE = pygame.Surface((DEFAULT_SURFACE_W, DEFAULT_SURFACE_H))

    # Define valid characters for sprite format - no '#' since it conflicts with YAML comments
    SPRITE_CHARS = ".XO@$%&=+abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def __init__(
        self: Self,
        x: int,
        y: int,
        width: int,
        height: int,
        name: str | None = None,
        filename: str | None = None,
        focusable: bool = False,
        parent: object = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
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
            x=x, y=y, width=width, height=height, name=name, parent=parent, groups=groups
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

    def load(self: Self, filename: str | None = None) -> tuple[pygame.Surface, pygame.Rect, str]:
        """Load a sprite from a Bitmappy config file using the factory."""
        self.log.debug(f"=== Starting load from {filename} ===")

        # Use the factory to determine sprite type and load appropriately
        try:
            sprite = SpriteFactory.load_sprite(filename=filename)

            # If it's an AnimatedSprite, we can't load it into a BitmappySprite
            if hasattr(sprite, "animations"):  # It's an AnimatedSprite
                BitmappySprite._raise_animated_sprite_error(filename)

            # It's a BitmappySprite, copy its properties
            self.image = sprite.image
            self.rect = sprite.rect
            self.name = sprite.name
            self.width = sprite.width
            self.height = sprite.height

            return (self.image, self.rect, self.name)
        except ValueError as e:
            # If factory fails, fall back to old static-only loading
            self.log.debug(f"Factory failed, falling back to static-only loading: {e}")
            return self._load_static_only(filename)

    @staticmethod
    def _raise_animated_sprite_error(filename: str) -> None:
        """Raise an error for animated sprite files."""
        raise ValueError(
            f"File {filename} contains animated sprite data. "
            f"Use AnimatedSprite class instead of BitmappySprite."
        )

    def _load_static_only(self: Self, filename: str) -> tuple[pygame.Surface, pygame.Rect, str]:
        """Load a static sprite from a Bitmappy config file (legacy method)."""
        self.log.debug(f"=== Starting static-only load from {filename} ===")

        # Detect file format and handle accordingly
        file_format = SpriteFactory._detect_file_format(filename)

        if file_format == "toml":
            return self._load_static_toml(filename)
        return self._load_static_ini(filename)

    def _load_static_ini(self: Self, filename: str) -> tuple[pygame.Surface, pygame.Rect, str]:
        """Load a static sprite from an INI file."""
        config = configparser.RawConfigParser(
            dict_type=collections.OrderedDict, empty_lines_in_values=True, strict=True
        )

        # Read the raw file content first
        raw_content = Path(filename).read_text(encoding="utf-8")
        self.log.debug(f"Raw file content ({len(raw_content)} bytes):\n{raw_content}")

        # Try parsing with configparser
        config.read_string(raw_content)
        self.log.debug(f"ConfigParser sections: {config.sections()}")

        try:
            name = config.get(section="sprite", option="name")
            self.log.debug(f"Sprite name: {name}")

            # Get raw pixel data with explicit raw=True to preserve newlines
            pixel_text = config.get(section="sprite", option="pixels", raw=True)
            self.log.debug(f"Raw pixel text ({len(pixel_text)} bytes):\n{pixel_text}")

            # Split into rows and process each row
            rows = []
            for i, raw_row in enumerate(pixel_text.split("\n")):
                row = raw_row.strip()
                if row:  # Only add non-empty rows
                    rows.append(row)
                    self.log.debug(f"Row {i}: '{row}' (len={len(row)})")

            self.log.debug(f"Total rows processed: {len(rows)}")

            # Calculate dimensions
            width = len(rows[0]) if rows else 0
            height = len(rows)
            self.log.debug(f"Calculated dimensions: {width}x{height}")

            # Get color definitions with detailed logging
            color_map = {}
            for section in config.sections():
                if len(section) == 1:  # Color sections are single characters
                    red = config.getint(section=section, option="red")
                    green = config.getint(section=section, option="green")
                    blue = config.getint(section=section, option="blue")
                    color_map[section] = (red, green, blue)
                    self.log.debug(f"Color map entry: '{section}' -> RGB({red}, {green}, {blue})")

            self.log.debug(f"Total colors in map: {len(color_map)}")

            # Create image and rect
            self.log.debug("Creating image and rect...")
            (image, rect) = self.inflate(
                width=width, height=height, pixels=rows, color_map=color_map
            )
            self.log.debug(f"Created image size: {image.get_size()}")
            self.log.debug(f"Created rect: {rect}")

        except Exception:
            self.log.exception("Error in load")
            raise
        else:
            # Return the successfully loaded sprite data
            return (image, rect, name)

    def _load_static_toml(self: Self, filename: str) -> tuple[pygame.Surface, pygame.Rect, str]:
        """Load a static sprite from a TOML file."""
        # Read the raw file content first
        raw_content = Path(filename).read_text(encoding="utf-8")
        self.log.debug(f"Raw file content ({len(raw_content)} bytes):\n{raw_content}")

        # Parse TOML
        data = toml.loads(raw_content)
        self.log.debug(f"TOML data keys: {list(data.keys())}")

        try:
            name = data["sprite"]["name"]
            self.log.debug(f"Sprite name: {name}")

            # Get pixel data
            pixel_text = data["sprite"]["pixels"]
            self.log.debug(f"Raw pixel text ({len(pixel_text)} bytes):\n{pixel_text}")

            # Split into rows and process each row
            rows = []
            for i, raw_row in enumerate(pixel_text.split("\n")):
                row = raw_row.strip()
                if row:  # Only add non-empty rows
                    rows.append(row)
                    self.log.debug(f"Row {i}: '{row}' (len={len(row)})")

            self.log.debug(f"Total rows processed: {len(rows)}")

            # Calculate dimensions
            width = len(rows[0]) if rows else 0
            height = len(rows)
            self.log.debug(f"Calculated dimensions: {width}x{height}")

            # Get color definitions
            color_map = {}
            if "colors" in data:
                for color_key, color_data in data["colors"].items():
                    red = color_data["red"]
                    green = color_data["green"]
                    blue = color_data["blue"]
                    color_map[color_key] = (red, green, blue)
                    self.log.debug(f"Color map entry: '{color_key}' -> RGB({red}, {green}, {blue})")

            self.log.debug(f"Total colors in map: {len(color_map)}")

            # Create image and rect
            self.log.debug("Creating image and rect...")
            (image, rect) = self.inflate(
                width=width, height=height, pixels=rows, color_map=color_map
            )
            self.log.debug(f"Created image size: {image.get_size()}")
            self.log.debug(f"Created rect: {rect}")

        except Exception:
            self.log.exception("Error in TOML load")
            raise
        else:
            # Return the successfully loaded sprite data
            return (image, rect, name)

    @classmethod
    def inflate(
        cls: Any, width: int, height: int, pixels: list, color_map: dict
    ) -> tuple[pygame.Surface, pygame.Rect]:
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

    def save(self: Self, filename: str, file_format: str = DEFAULT_FILE_FORMAT) -> None:
        """Save a sprite to a file using the factory for backwards compatibility."""
        self.log.debug(f"Starting save in {file_format} format to {filename}")

        # Use the factory to save the sprite
        SpriteFactory.save_sprite(sprite=self, filename=filename, file_format=file_format)

        self.log.debug(f"Successfully saved to {filename}")

    def _save(self: Self, filename: str, file_format: str = DEFAULT_FILE_FORMAT) -> None:
        """Save static sprite to file."""
        self._save_static_only(filename, file_format)

    def _load(self: Self, filename: str) -> tuple[pygame.Surface, pygame.Rect, str]:
        """Load static sprite from file."""
        return self._load_static_only(filename)

    def _save_static_only(
        self: Self, filename: str, file_format: str = DEFAULT_FILE_FORMAT
    ) -> None:
        """Save a static sprite to a file (legacy method)."""
        try:
            self.log.debug(f"Starting static-only save in {file_format} format to {filename}")
            config = self.deflate(file_format=file_format)
            self.log.debug(f"Got config from deflate: {config}")

            if file_format == "yaml":

                class BlockLiteralDumper(yaml.SafeDumper):
                    def represent_scalar(self, tag, value, style=None):
                        if isinstance(value, str) and "\n" in value:
                            style = "|"
                            # Ensure consistent indentation
                            value = "\n" + value.rstrip()
                        return super().represent_scalar(tag, value, style)

                self.log.debug("About to dump YAML")
                with Path(filename).open("w", encoding="utf-8") as yaml_file:
                    yaml.dump(
                        config,
                        yaml_file,
                        default_flow_style=False,
                        Dumper=BlockLiteralDumper,
                        indent=2,
                    )
                self.log.debug("YAML dump complete")
            elif file_format == "ini":
                self.log.debug("About to write INI")
                with Path(filename).open("w", encoding="utf-8") as ini_file:
                    config.write(ini_file)
                self.log.debug("INI write complete")
            else:
                self._raise_unsupported_format_error(file_format)

            self.log.debug(f"Successfully saved to {filename}")

        except Exception:
            self.log.exception("Error in save")
            raise

    def deflate(self: Self, file_format: str = "yaml") -> dict | configparser.ConfigParser:
        """Deflate a sprite to a configuration format."""
        try:
            self.log.debug(f"Starting deflate for {self.name} in {file_format} format")

            # Validate pixels list
            expected_pixels = self.pixels_across * self.pixels_tall
            if len(self.pixels) != expected_pixels:
                self.log.error(
                    f"Pixels list length mismatch: {len(self.pixels)} vs expected {expected_pixels}"
                )
                # Pad with default color if too short
                if len(self.pixels) < expected_pixels:
                    self.pixels.extend([(255, 0, 255)] * (expected_pixels - len(self.pixels)))
                # Truncate if too long
                elif len(self.pixels) > expected_pixels:
                    self.pixels = self.pixels[:expected_pixels]

            # Get unique colors from the pixels list
            unique_colors = set(self.pixels)
            self.log.debug(f"Found {len(unique_colors)} unique colors")
            self.log.debug(f"Pixels list length: {len(self.pixels)}")
            self.log.debug(f"Expected pixels: {self.pixels_across * self.pixels_tall}")
            self.log.debug(f"Sample pixels: {self.pixels[:10]}")

            # Create color to character mapping
            color_map = {}
            # This gives us 128 colors per sprite and the characters were selected
            # carefully to support various text formats such as JSON, YAML, and INI.

            # Filter out dangerous characters that could break file formats
            dangerous_chars = {"\n", "\r", "\t", "\0", "\b", "\f", "\v", "\a"}
            printable_chars = "".join(c for c in SPRITE_GLYPHS if c not in dangerous_chars)
            self.log.debug(
                f"Filtered printable chars: '{printable_chars}' (length: {len(printable_chars)})"
            )

            # Assign characters sequentially from SPRITE_GLYPHS
            for char_index, color in enumerate(unique_colors):
                if char_index >= len(printable_chars):
                    self._raise_too_many_colors_error(len(printable_chars))
                char = printable_chars[char_index]
                # Double-check that the character is safe
                if char in dangerous_chars or not char.isprintable():
                    self.log.error(
                        f"Unsafe character '{char}' (ord={ord(char)}) detected, using '.' instead"
                    )
                    char = "."
                color_map[color] = char
                self.log.debug(
                    f"Color {color} -> char '{color_map[color]}' (ord={ord(color_map[color])})"
                )

            # Process pixels row by row
            pixel_rows = self._process_pixel_rows(color_map)

            # Create configuration based on format
            if file_format == "yaml":
                config = self._create_yaml_config(pixel_rows, color_map)
            else:  # ini format
                config = self._create_ini_config(pixel_rows, color_map)

        except Exception:
            self.log.exception("Error in deflate")
            raise
        else:
            # Return the successfully created configuration
            return config

    def _process_pixel_rows(self, color_map: dict) -> list[str]:
        """Process pixels into rows of characters.

        Args:
            color_map: Mapping of colors to characters

        Returns:
            List of pixel rows as strings

        """
        pixel_rows = []
        for y in range(self.pixels_tall):
            row = ""
            for x in range(self.pixels_across):
                pixel_color = self.pixels[y * self.pixels_across + x]
                if pixel_color not in color_map:
                    self.log.error(f"Color {pixel_color} not found in color_map")
                    # Use a default character for missing colors
                    row += "."
                    continue
                row += color_map[pixel_color]
            pixel_rows.append(row)
            self.log.debug(f"Row {y}: '{row}' (len={len(row)})")
        return pixel_rows

    def _create_yaml_config(self, pixel_rows: list[str], color_map: dict) -> dict:
        """Create YAML configuration.

        Args:
            pixel_rows: List of pixel rows as strings
            color_map: Mapping of colors to characters

        Returns:
            YAML configuration dictionary

        """
        pixels_str = "\n".join(pixel_rows)
        return {
            "sprite": {"name": self.name or "unnamed", "pixels": pixels_str},
            "colors": {
                char: {"red": color[0], "green": color[1], "blue": color[2]}
                for color, char in color_map.items()
            },
        }

    def _create_ini_config(
        self, pixel_rows: list[str], color_map: dict
    ) -> configparser.ConfigParser:
        """Create INI configuration.

        Args:
            pixel_rows: List of pixel rows as strings
            color_map: Mapping of colors to characters

        Returns:
            INI configuration parser

        """
        config = configparser.ConfigParser()
        config.add_section("sprite")
        config.set("sprite", "name", self.name or "unnamed")
        # Add proper indentation to match original format
        pixels_str = pixel_rows[0]  # First line has no indentation
        for row in pixel_rows[1:]:  # Subsequent lines have tab indentation
            pixels_str += "\n\t" + row
        config.set("sprite", "pixels", pixels_str)

        # Add a section for each color
        for color, char in color_map.items():
            config.add_section(char)
            config.set(char, "red", str(color[0]))
            config.set(char, "green", str(color[1]))
            config.set(char, "blue", str(color[2]))

        return config

    @staticmethod
    def _raise_unsupported_format_error(file_format: str) -> None:
        """Raise an error for unsupported file format."""
        raise ValueError(f"Unsupported format: {file_format}")

    @staticmethod
    def _raise_too_many_colors_error(max_colors: int) -> None:
        """Raise an error for too many colors."""
        raise ValueError(f"Too many colors (max {max_colors})")

    def on_left_mouse_drag_event(
        self: Self, event: pygame.event.Event, trigger: object | None
    ) -> None:
        """Handle a left mouse drag event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(f"{type(self)}: Left Mouse Drag Event: {event} @ {self} for {trigger}")

    def on_middle_mouse_drag_event(
        self: Self, event: pygame.event.Event, trigger: object | None
    ) -> None:
        """Handle a middle mouse drag event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(f"{type(self)}: Middle Mouse Drag Event: {event} @ {self} for {trigger}")

    def on_right_mouse_drag_event(
        self: Self, event: pygame.event.Event, trigger: object | None
    ) -> None:
        """Handle a right mouse drag event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(f"{type(self)}: Right Mouse Drag Event: {event} @ {self} for {trigger}")

    def on_left_mouse_drop_event(
        self: Self, event: pygame.event.Event, trigger: object | None
    ) -> None:
        """Handle a left mouse drop event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(f"{type(self)}: Left Mouse Drop Event: {event} @ {self} for {trigger}")

    def on_middle_mouse_drop_event(
        self: Self, event: pygame.event.Event, trigger: object | None
    ) -> None:
        """Handle a middle mouse drop event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(f"{type(self)}: Middle Mouse Drop Event: {event} @ {self} for {trigger}")

    def on_right_mouse_drop_event(
        self: Self, event: pygame.event.Event, trigger: object | None
    ) -> None:
        """Handle a right mouse drop event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(f"{type(self)}: Right Mouse Drop Event: {event} @ {self} for {trigger}")

    def on_mouse_drag_event(self: Self, event: pygame.event.Event, trigger: object | None) -> None:
        """Handle a mouse drag event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(f"{type(self)}: Mouse Drag Event: {event} @ {self} for {trigger}")

    def on_mouse_drop_event(self: Self, event: pygame.event.Event, trigger: object | None) -> None:
        """Handle a mouse drop event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(f"{type(self)}: Mouse Drop Event: {event} @ {self} for {trigger}")

    def on_mouse_wheel_event(self: Self, event: pygame.event.Event, trigger: object | None) -> None:
        """Handle a mouse wheel event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        Returns:
            None

        """
        self.log.debug(f"{type(self)}: Mouse Wheel Event: {event} @ {self} for {trigger}")

    def on_mouse_chord_down_event(self: Self, event: pygame.event.Event, keys: list) -> None:
        """Handle a mouse chord down event.

        Args:
            event (pygame.event.Event): The event to handle.
            keys (list): The keys that were pressed.

        Returns:
            None

        """
        self.log.debug(f"{type(self)}: Mouse Chord Down Event: {event} @ {self} for {keys}")

    def on_mouse_chord_up_event(self: Self, event: pygame.event.Event, keys: list) -> None:
        """Handle a mouse chord up event.

        Args:
            event (pygame.event.Event): The event to handle.
            keys (list): The keys that were pressed.

        Returns:
            None

        """
        self.log.debug(f"{type(self)}: Mouse Chord Up Event: {event} @ {self} for {keys}")


class Singleton:
    """A generic singleton class."""

    __instance__ = None

    def __new__(cls: Any, *args, **kwargs) -> Self:
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

    def __new__(cls: Any, *args, **kwargs) -> Self:
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

    def __init__(
        self: Self,
        x: int,
        y: int,
        width: int,
        height: int,
        name: str | None = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
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

    def __new__(cls: Any, *args, **kwargs) -> Self:
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

    def __init__(
        self: Self,
        x: int,
        y: int,
        width: int,
        height: int,
        name: str | None = None,
        groups: pygame.sprite.LayeredDirty | None = None,
    ) -> None:
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
            x=x, y=y, width=width, height=height, name=name, focusable=True, groups=groups
        )


class SpriteFactory:
    """Factory class for loading sprites with automatic type detection."""

    @staticmethod
    def load_sprite(*, filename: str | None = None) -> BitmappySprite | AnimatedSprite:
        """Load a sprite file, automatically detecting whether it's static or animated.

        Args:
            filename: Path to sprite file. If None, loads default sprite (raspberry.toml).

        Returns:
            BitmappySprite or AnimatedSprite based on file content.

        Raises:
            ValueError: If file format is invalid or contains mixed content.

        """
        # Handle default sprite loading
        if filename is None:
            filename = SpriteFactory._get_default_sprite_path()

        analysis = SpriteFactory._analyze_file(filename)
        sprite_type = SpriteFactory._determine_type(analysis)

        if sprite_type == "static":
            # Create BitmappySprite without calling load to avoid recursion
            sprite = BitmappySprite(x=0, y=0, width=32, height=32, filename=None)
            # Now manually load the file using the internal load method
            image, rect, name = sprite._load(filename)
            sprite.image = image
            sprite.rect = rect
            sprite.name = name
            sprite.width = rect.width
            sprite.height = rect.height
            return sprite
        if sprite_type == "animated":
            # Use the imported AnimatedSprite class with proper sprite group integration
            return AnimatedSprite(filename, groups=None)
        raise ValueError(f"Invalid sprite file format: {filename}")

    @staticmethod
    def _detect_file_format(filename: str) -> str:
        """Detect file format based on file extension."""
        filename_str = str(filename)
        filename_lower = filename_str.lower()
        if filename_lower.endswith((".yaml", ".yml")):
            return "yaml"
        if filename_lower.endswith(".ini"):
            return "ini"
        return "toml"  # Default to toml

    @staticmethod
    def _analyze_file(filename: str) -> dict:
        """Analyze file content to determine sprite type."""
        file_format = SpriteFactory._detect_file_format(filename)

        if file_format == "toml":
            return SpriteFactory._analyze_toml_file(filename)
        return SpriteFactory._analyze_ini_file(filename)

    @staticmethod
    def _analyze_ini_file(filename: str) -> dict:
        """Analyze INI file content to determine sprite type."""
        config = configparser.ConfigParser()
        config.read(filename)

        has_sprite_pixels = False
        has_animation_sections = False
        has_frame_sections = False

        # Check for [sprite] pixels
        if "sprite" in config and "pixels" in config["sprite"]:
            has_sprite_pixels = True

        # Check for [animation] sections
        if any(section.startswith("animation") for section in config.sections()):
            has_animation_sections = True

        # Check for [frame] sections
        if any(section.startswith("frame") for section in config.sections()):
            has_frame_sections = True

        return {
            "has_sprite_pixels": has_sprite_pixels,
            "has_animation_sections": has_animation_sections,
            "has_frame_sections": has_frame_sections,
        }

    @staticmethod
    def _analyze_toml_file(filename: str) -> dict:
        """Analyze TOML file content to determine sprite type."""
        with Path(filename).open("r", encoding="utf-8") as f:
            data = toml.load(f)

        has_sprite_pixels = False
        has_animation_sections = False
        has_frame_sections = False

        # Check for sprite.pixels (ignore empty strings)
        if "sprite" in data and "pixels" in data["sprite"] and data["sprite"]["pixels"].strip():
            has_sprite_pixels = True

        # Check for animation sections
        if "animation" in data:
            has_animation_sections = True

        # Check for frame sections within animations
        if "animation" in data:
            for anim in data["animation"]:
                if "frame" in anim:
                    has_frame_sections = True
                    break

        return {
            "has_sprite_pixels": has_sprite_pixels,
            "has_animation_sections": has_animation_sections,
            "has_frame_sections": has_frame_sections,
        }

    @staticmethod
    def _determine_type(analysis: dict) -> str:
        """Determine sprite type based on file analysis."""
        if analysis["has_sprite_pixels"] and analysis["has_frame_sections"]:
            return "error"  # Mixed content - invalid
        if analysis["has_frame_sections"] or analysis["has_animation_sections"]:
            return "animated"
        if analysis["has_sprite_pixels"]:
            return "static"
        return "error"  # No recognizable content

    @staticmethod
    def _get_default_sprite_path() -> str:
        """Get the path to the default sprite (raspberry.toml)."""
        # Get the path to the assets directory
        assets_dir = Path(__file__).parent / ".." / "assets"
        return str(assets_dir / "raspberry.toml")

    @staticmethod
    def save_sprite(
        *,
        sprite: BitmappySprite | AnimatedSprite,
        filename: str,
        file_format: str = DEFAULT_FILE_FORMAT,
    ) -> None:
        """Save a sprite to a file with automatic type detection.

        Args:
            sprite: The sprite to save (BitmappySprite or AnimatedSprite).
            filename: Path where to save the sprite file.
            file_format: Output format ("ini", "yaml", or "toml"). Defaults to "toml".

        Raises:
            NotImplementedError: If saving animated sprites (not yet implemented).
            ValueError: If file_format is not supported.

        """
        if hasattr(sprite, "animations"):  # It's an AnimatedSprite
            SpriteFactory._save_animated_sprite(sprite, filename, file_format)
        else:  # It's a BitmappySprite
            SpriteFactory._save_static_sprite(sprite, filename, file_format)

    @staticmethod
    def _save_static_sprite(sprite: BitmappySprite, filename: str, file_format: str) -> None:
        """Save a static sprite to a file."""
        sprite._save(filename, file_format)

    @staticmethod
    def _save_animated_sprite(sprite: AnimatedSprite, filename: str, file_format: str) -> None:
        """Save an animated sprite to a file."""
        sprite._save(filename, file_format)


# Add helper methods to BitmappySprite for AI training data extraction
def _get_pixel_string(self: Self) -> str:
    """Get pixel data as a string for AI training."""
    if not hasattr(self, "pixels") or not self.pixels:
        return ""

    # Convert pixels to character representation
    pixel_string = ""
    for y in range(self.pixels_tall):
        for x in range(self.pixels_across):
            pixel_index = y * self.pixels_across + x
            if pixel_index < len(self.pixels):
                # For now, just use a placeholder - this would need proper character mapping
                pixel_string += "."
            else:
                pixel_string += "."
        if y < self.pixels_tall - 1:  # Don't add newline after last row
            pixel_string += "\n"

    return pixel_string


def _get_color_map(self: Self) -> dict:
    """Get color mapping for AI training."""
    if not hasattr(self, "pixels") or not self.pixels:
        return {}

    # Get unique colors and create mapping
    unique_colors = list(set(self.pixels))
    color_map = {}

    MAX_COLORS = 8  # Limit to 8 colors
    for i, color in enumerate(unique_colors):
        if i < MAX_COLORS:
            color_map[str(i)] = {
                "red": color[0],
                "green": color[1],
                "blue": color[2],
            }

    return color_map


# Add methods to BitmappySprite class
BitmappySprite._get_pixel_string = _get_pixel_string
BitmappySprite._get_color_map = _get_color_map
