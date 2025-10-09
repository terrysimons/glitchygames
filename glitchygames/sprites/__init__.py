#!/usr/bin/env python3
# ruff: noqa: FBT001, FBT002
"""Glitchy Games Engine sprite module."""

from __future__ import annotations

import collections
import logging
from pathlib import Path
from typing import Any, ClassVar, Self, cast

import pygame
import toml
from glitchygames.events import MouseEvents
from glitchygames.interfaces import SpriteInterface

# Import animated sprite classes
from .animated import AnimatedSprite, AnimatedSpriteInterface, SpriteFrame
from .constants import DEFAULT_FILE_FORMAT, SPRITE_GLYPHS

# Public API
__all__ = [  # noqa: RUF022
    "AnimatedSprite",
    "AnimatedSpriteInterface",
    "BitmappySprite",
    "SpriteFactory",
    "SpriteFrame",
    "DEFAULT_FILE_FORMAT",
    "SPRITE_GLYPHS",
]

LOG = logging.getLogger("game.sprites")
# LOG.addHandler(logging.NullHandler())

# Configure logger
# LOG = logging.getLogger("game.sprites")

# Add console handler if none exists
# if not LOG.handlers:
#     ch = logging.StreamHandler()
#     ch.setLevel(logging.DEBUG)
#     formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
#     ch.setFormatter(formatter)
#     LOG.addHandler(ch)


# Configure logger
# LOG = logging.getLogger("game.sprites")
# LOG.setLevel(logging.DEBUG)

# Add console handler if none exists
# if not LOG.handlers:
#     ch = logging.StreamHandler()
#     ch.setLevel(logging.DEBUG)
#     formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
#     ch.setFormatter(formatter)
#     LOG.addHandler(ch)


class RootSprite(MouseEvents, SpriteInterface, pygame.sprite.DirtySprite):
    """A root sprite class.  All Glitchy Games sprites inherit from this class."""

    log = LOG

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
        x: int = 0,
        y: int = 0,
        width: int = 32,
        height: int = 32,
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
        self.filename = filename or ""
        self.focusable = focusable
        # self.width = width
        # self.height = height

        # Initialize pixel data attributes
        self.pixels = []
        self.pixels_across = width
        self.pixels_tall = height

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

        # Use the factory to load sprite (always returns AnimatedSprite now)
        try:
            animated_sprite = SpriteFactory.load_sprite(filename=filename)

            # Convert AnimatedSprite to BitmappySprite format
            # Get the current frame surface from the animated sprite
            current_frame = animated_sprite.get_current_frame()
            if current_frame and hasattr(current_frame, "surface"):
                self.image = current_frame.surface
            else:
                # Fallback: create surface from animated sprite's image
                self.image = animated_sprite.image.copy()

            self.rect = self.image.get_rect()
            self.name = animated_sprite.name
            self.width = self.rect.width
            self.height = self.rect.height

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
        else:
            raise ValueError(f"Unsupported file format: {file_format}. Only TOML format is supported.")


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
        """Save a static sprite to a file (legacy method).

        Currently only supports TOML format. To add new formats:
        1. Add format detection in _detect_file_format()
        2. Add save logic here (e.g., _save_json(), _save_xml())
        3. Add load methods in _load_static_only()
        4. Update tests
        See LOADER_README.md for detailed implementation guide.
        """
        try:
            self.log.debug(f"Starting static-only save in {file_format} format to {filename}")
            config = self.deflate(file_format=file_format)
            self.log.debug(f"Got config from deflate: {config}")

            if file_format == "toml":
                self.log.debug("About to write TOML")
                with Path(filename).open("w", encoding="utf-8") as toml_file:
                    toml.dump(config, toml_file)
                self.log.debug("TOML write complete")
            else:
                self._raise_unsupported_format_error(file_format)

            self.log.debug(f"Successfully saved to {filename}")

        except Exception:
            self.log.exception("Error in save")
            raise

    def deflate(self: Self, file_format: str = "toml") -> dict:
        """Deflate a sprite to a configuration format.

        Currently only supports TOML format. To add new formats:
        1. Add format detection in _detect_file_format()
        2. Add deflate logic here (e.g., _deflate_json(), _deflate_xml())
        3. Add inflate methods in _load_static_only()
        4. Update tests
        See LOADER_README.md for detailed implementation guide.
        """
        try:
            self.log.debug(f"Starting deflate for {self.name} in {file_format} format")

            # Ensure pixels attribute exists
            if not hasattr(self, 'pixels'):
                self.pixels = []

            # Validate pixels list
            pixels_across = getattr(self, 'pixels_across', self.width)
            pixels_tall = getattr(self, 'pixels_tall', self.height)
            expected_pixels = pixels_across * pixels_tall
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
            self.log.debug(f"Expected pixels: {pixels_across * pixels_tall}")
            self.log.debug(f"Sample pixels: {self.pixels[:10]}")

            # Check if there are too many colors
            if len(unique_colors) > len(SPRITE_GLYPHS):
                raise ValueError(f"Too many colors: {len(unique_colors)} > {len(SPRITE_GLYPHS)}")

            # Create color to character mapping using the helper method
            color_map = self._create_color_map()

            # Process pixels row by row
            pixel_rows = self._process_pixel_rows(color_map, pixels_across, pixels_tall)

            # Create configuration based on format
            if file_format == "toml":
                config = self._create_toml_config(pixel_rows, color_map)
            else:
                self._raise_unsupported_format_error(file_format)

        except Exception:
            self.log.exception("Error in deflate")
            raise
        else:
            # Return the successfully created configuration
            return config

    def _process_pixel_rows(self, color_map: dict, pixels_across: int = None, pixels_tall: int = None) -> list[str]:
        """Process pixels into rows of characters.

        Args:
            color_map: Mapping of colors to characters
            pixels_across: Number of pixels across (optional, uses self.pixels_across if not provided)
            pixels_tall: Number of pixels tall (optional, uses self.pixels_tall if not provided)

        Returns:
            List of pixel rows as strings

        """
        if pixels_across is None:
            pixels_across = getattr(self, 'pixels_across', self.width)
        if pixels_tall is None:
            pixels_tall = getattr(self, 'pixels_tall', self.height)

        pixel_rows = []
        for y in range(pixels_tall):
            row = ""
            for x in range(pixels_across):
                pixel_color = self.pixels[y * pixels_across + x]
                # Find the character for this color
                char = "."
                for ch, color in color_map.items():
                    if color == pixel_color:
                        char = ch
                        break
                else:
                    self.log.error(f"Color {pixel_color} not found in color_map")
                row += char
            pixel_rows.append(row)
            self.log.debug(f"Row {y}: '{row}' (len={len(row)})")
        return pixel_rows

    def _create_toml_config(self, pixel_rows: list[str] = None, color_map: dict = None) -> dict:
        """Create TOML configuration.

        Args:
            pixel_rows: List of pixel rows as strings (optional, will be generated if not provided)
            color_map: Mapping of colors to characters (optional, will be generated if not provided)

        Returns:
            TOML configuration dictionary

        To add new formats, create similar methods like _create_json_config(), _create_xml_config()
        See LOADER_README.md for detailed implementation guide.

        """
        # Generate pixel_rows and color_map if not provided
        if pixel_rows is None:
            if not hasattr(self, 'pixels') or not self.pixels:
                pixel_rows = []
            else:
                # Create color map if not provided
                if color_map is None:
                    color_map = self._create_color_map()

                # Process pixels into rows
                pixel_rows = []
                # Use height and width if pixels_tall/pixels_across not available
                pixels_tall = getattr(self, 'pixels_tall', self.height)
                pixels_across = getattr(self, 'pixels_across', self.width)

                for y in range(pixels_tall):
                    row = ""
                    for x in range(pixels_across):
                        pixel_index = y * pixels_across + x
                        if pixel_index < len(self.pixels):
                            pixel_color = self.pixels[pixel_index]
                            if pixel_color in color_map:
                                row += color_map[pixel_color]
                            else:
                                row += "."  # Default character for missing colors
                        else:
                            row += "."  # Default character for missing pixels
                    pixel_rows.append(row)

        if color_map is None:
            color_map = self._create_color_map()

        pixels_str = "\n".join(pixel_rows)
        return {
            "sprite": {"name": self.name or "unnamed", "pixels": pixels_str},
            "colors": {
                char: {"red": color[0], "green": color[1], "blue": color[2]}
                for char, color in color_map.items()
            },
        }

    @staticmethod
    def _raise_unsupported_format_error(file_format: str) -> None:
        """Raise an error for unsupported file format."""
        raise ValueError(f"Unsupported format: {file_format}")

    @staticmethod
    def _raise_too_many_colors_error(max_colors: int) -> None:
        """Raise an error for too many colors."""
        raise ValueError(f"Too many colors (max {max_colors})")

    def _create_color_map(self: Self) -> dict:
        """Create a color map from the sprite's pixels.

        Returns:
            dict: Mapping of colors to characters
        """
        if not hasattr(self, 'pixels') or not self.pixels:
            return {}

        # Get unique colors from the pixels list
        unique_colors = set(self.pixels)
        color_map = {}

        # Filter out dangerous characters that could break file formats
        dangerous_chars = {"\n", "\r", "\t", "\0", "\b", "\f", "\v", "\a"}
        printable_chars = "".join(c for c in SPRITE_GLYPHS if c not in dangerous_chars)

        # Assign characters sequentially from SPRITE_CHARS
        for char_index, color in enumerate(unique_colors):
            if char_index >= len(printable_chars):
                break
            char = printable_chars[char_index]
            # Double-check that the character is safe
            if char in dangerous_chars or not char.isprintable():
                char = "."
            color_map[char] = color

        # Always include the magenta padding color (255, 0, 255) with a special character
        padding_color = (255, 0, 255)
        if padding_color in unique_colors and padding_color not in color_map.values():
            # Use a special character for padding (like 'X' or '#')
            padding_char = "X" if "X" not in color_map else "#"
            color_map[padding_char] = padding_color

        return color_map

    def _inflate_toml(self: Self, filename: str) -> dict:
        """Inflate a sprite from a TOML file.

        Args:
            filename: Path to the TOML file

        Returns:
            dict: Sprite data dictionary
        """
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

            # Convert rows to pixels
            pixels = []
            for y, row in enumerate(rows):
                for x, char in enumerate(row):
                    if char in color_map:
                        pixels.append(color_map[char])
                    else:
                        # Default color for unknown characters
                        pixels.append((255, 0, 255))

            return {
                'pixels': pixels,
                'width': width,
                'height': height,
                'name': name
            }

        except Exception:
            self.log.exception("Error in TOML inflate")
            raise

    def inflate(self: Self, filename: str) -> dict:
        """Inflate a sprite from a file.

        Args:
            filename: Path to the sprite file

        Returns:
            dict: Sprite data dictionary
        """
        # Detect file format and handle accordingly
        file_format = SpriteFactory._detect_file_format(filename)

        if file_format == "toml":
            return self._inflate_toml(filename)
        else:
            raise ValueError(f"Unsupported format: {file_format}")

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
        x: int = 0,
        y: int = 0,
        width: int = 32,
        height: int = 32,
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
        x: int = 0,
        y: int = 0,
        width: int = 32,
        height: int = 32,
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
    def load_sprite(*, filename: str | None = None) -> AnimatedSprite:
        """Load a sprite file, always returning an AnimatedSprite.

        Static sprites are automatically converted to single-frame animations
        for consistent internal representation.

        Args:
            filename: Path to sprite file. If None, loads default sprite (raspberry.toml).

        Returns:
            AnimatedSprite (static sprites are converted to single-frame animations).

        Raises:
            ValueError: If file format is invalid or contains mixed content.

        """
        # Handle default sprite loading
        if filename is None:
            filename = SpriteFactory._get_default_sprite_path()

        # Validate file content before loading
        analysis = SpriteFactory._analyze_file(filename)

        # Check if file has valid content
        if not (
            analysis["has_sprite_pixels"]
            or analysis["has_animation_sections"]
            or analysis["has_frame_sections"]
        ):
            raise ValueError("Invalid sprite file")

        # Check for mixed content (both static and animated data)
        if analysis["has_sprite_pixels"] and (
            analysis["has_animation_sections"] or analysis["has_frame_sections"]
        ):
            raise ValueError("Invalid sprite file")

        # Always return AnimatedSprite - it handles both static and animated content
        return AnimatedSprite(filename, groups=None)

    @staticmethod
    def _detect_file_format(filename) -> str:
        """Detect file format based on extension."""
        # Convert Path objects to strings
        filename_str = str(filename)

        if filename_str.endswith('.toml'):
            return 'toml'
        elif filename_str.endswith('.yaml') or filename_str.endswith('.yml'):
            return 'yaml'
        else:
            return 'unknown'

    @staticmethod
    def _analyze_file(filename) -> dict:
        """Analyze file content to determine sprite type.

        Currently only supports TOML format. To add new formats:
        1. Add format detection in _detect_file_format()
        2. Add analysis method here (e.g., _analyze_json_file())
        3. Add save/load methods in BitmappySprite and AnimatedSprite
        4. Update tests
        See LOADER_README.md for detailed implementation guide.
        """
        file_format = SpriteFactory._detect_file_format(filename)

        if file_format == "toml":
            return SpriteFactory._analyze_toml_file(filename)

        raise ValueError(f"Unsupported format: {file_format}. Only TOML is currently supported.")

    @staticmethod
    def _analyze_toml_file(filename) -> dict:
        """Analyze TOML file content to determine sprite type."""
        with Path(filename).open("r", encoding="utf-8") as f:
            data = toml.load(f)

        has_sprite_pixels = False
        has_animation_sections = False
        has_frame_sections = False

        # Check for sprite.pixels (ignore empty strings and empty lists)
        if "sprite" in data and "pixels" in data["sprite"]:
            pixels = data["sprite"]["pixels"]
            if isinstance(pixels, str) and pixels.strip():
                has_sprite_pixels = True
            elif isinstance(pixels, list) and pixels:
                has_sprite_pixels = True

        # Check for animation sections (both keys and arrays of tables)
        if "animation" in data or "animations" in data:
            has_animation_sections = True
        elif isinstance(data.get("animation"), list) and data["animation"]:
            has_animation_sections = True

        # Check for frame sections (both keys and arrays of tables)
        if "frame" in data:
            has_frame_sections = True
        elif isinstance(data.get("frame"), list) and data["frame"]:
            has_frame_sections = True

        # Check for nested frame sections within animation arrays
        if isinstance(data.get("animation"), list):
            for animation in data["animation"]:
                if isinstance(animation, dict) and "frame" in animation:
                    has_frame_sections = True
                    break

        return {
            "has_sprite_pixels": has_sprite_pixels,
            "has_animation_sections": has_animation_sections,
            "has_frame_sections": has_frame_sections,
        }

    @staticmethod
    def _get_toml_data(filename) -> dict:
        """Get raw TOML data from file."""
        with Path(filename).open("r", encoding="utf-8") as f:
            return toml.load(f)

    @staticmethod
    def _determine_type(analysis: dict) -> str:
        """Determine sprite type based on file analysis."""
        # Prioritize animations over static content
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
        sprite.save(filename, file_format)


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

    max_colors = 8  # Limit to 8 colors
    for i, color in enumerate(unique_colors):
        if i < max_colors:
            color_map[str(i)] = {
                "red": color[0],
                "green": color[1],
                "blue": color[2],
            }

    return color_map


# Add methods to BitmappySprite class
BitmappySprite._get_pixel_string = _get_pixel_string
BitmappySprite._get_color_map = _get_color_map

