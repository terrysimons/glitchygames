"""General-purpose Sprite class for Glitchy Games Engine.

This module contains the Sprite class which extends RootSprite with coordinates,
event handling, delta time tracking, and debugging support.
"""

from __future__ import annotations

import collections
import logging
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

if TYPE_CHECKING:
    from glitchygames.events.base import HashableEvent

import pygame

from .root_sprite import RootSprite

LOG = logging.getLogger('game.sprites')

# Error message constants for TRY003 compliance
_ERR_CANNOT_CREATE_SURFACE = "Can't create Surface(({width}, {height}))."


class Sprite(RootSprite):  # noqa: PLR0904
    """A convenience class for handling all of the common sprite behaviors."""

    log = LOG
    USE_GFXDRAW: ClassVar = False
    PROXIES: ClassVar = [pygame.sprite]
    # None means no breakpoints.  Empty list means all.
    SPRITE_BREAKPOINTS: ClassVar[list[str] | None] = None
    SPRITE_COUNTERS: ClassVar[collections.OrderedDict[str, dict[str, int | float]]] = (
        collections.OrderedDict()
    )
    SPRITE_COUNT = 0

    @classmethod
    def break_when(cls: type[Sprite], sprite_type: object | None = None) -> None:
        """Register a breakpoint for a sprite type.

        Args:
            sprite_type (object | None): The sprite type to break on.
                None means break on any sprite.

        """
        # None means disabled.
        # [] means any.
        if cls.SPRITE_BREAKPOINTS is None:
            cls.SPRITE_BREAKPOINTS = []  # pyright: ignore[reportConstantRedefinition]

        # If none, break always.
        if sprite_type is not None:
            LOG.info('Register break when sprite_type==%s', cls)
            cls.SPRITE_BREAKPOINTS.append(str(cls))
        else:
            LOG.info('Register break when sprite_type==<any>')

    def __init__(  # noqa: PLR0913
        self: Self,
        x: float,
        y: float,
        width: float,
        height: float,
        *,
        name: str | None = None,
        parent: object | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
    ) -> None:
        """Initialize a Sprite.

        Args:
            x (int | float): The x coordinate of the sprite.
            y (int | float): The y coordinate of the sprite.
            width (int | float): The width of the sprite.
            height (int | float): The height of the sprite.
            name (str | None): The name of the sprite.
            parent (object | None): The parent of the sprite.
            groups (pygame.sprite.LayeredDirty | None): The sprite groups to add the sprite to.

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
        # Typed as Any so widget subclasses can access parent-specific attributes
        # without needing casts. The actual parent type is enforced by each widget's
        # __init__ parameter (using Protocol types like _SliderParent, _HasRect, etc.)
        self.parent: Any = parent
        self.proxies = [self]

        # For debugging sanity.
        if not name:
            self.name = type(self)

        if not self.width:
            self.log.error(f'{type(self)} has 0 Width')

        if not self.height:
            self.log.error(f'{type(self)} has 0 Height')

        # Sprites can register callbacks for any event type.
        self.callbacks: dict[str, Any] = {}

        # Each sprite maintains a reference to the screen.
        self.screen = pygame.display.get_surface()
        assert self.screen is not None, (
            'Display surface must be initialized before creating sprites'
        )
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()

        groups.add(self)

        # Add ourselves to the sprite counters.
        my_type = str(type(self))

        if my_type in self.SPRITE_COUNTERS:
            self.SPRITE_COUNTERS[my_type]['count'] += 1
            self.SPRITE_COUNTERS[my_type]['pixels'] = (
                self.width * self.height + self.SPRITE_COUNTERS[my_type]['pixels']
            )
        else:
            self.SPRITE_COUNTERS[my_type] = collections.OrderedDict()
            self.SPRITE_COUNTERS[my_type]['count'] = 1
            self.SPRITE_COUNTERS[my_type]['pixels'] = 0
        self.SPRITE_COUNT += 1  # pyright: ignore[reportConstantRedefinition]

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
    def width(self: Self) -> int | float:
        """Return the width of the sprite.

        Returns:
            int | float: The width of the sprite.

        """
        return self.rect.width

    @width.setter
    def width(self: Self, new_width: float) -> None:
        """Set the width of the sprite.

        Args:
            new_width (int | float): The new width of the sprite.

        """
        self.rect.width = new_width
        self.dirty = 1 if not self.dirty else self.dirty

    @property
    def height(self: Self) -> int | float:
        """Return the height of the sprite.

        Returns:
            int | float: The height of the sprite.

        """
        return self.rect.height

    @height.setter
    def height(self: Self, new_height: float) -> None:
        """Set the height of the sprite.

        Args:
            new_height (int | float): The new height of the sprite.

        """
        self.rect.height = new_height
        self.dirty = 1 if not self.dirty else self.dirty

    def dt_tick(self: Self, dt: float) -> None:
        """Update the sprite's delta time.

        Args:
            dt (float): The new delta time.

        """
        self.dt = dt
        self.dt_timer += self.dt

    @override
    def update(self: Self) -> None:
        """Update the sprite."""

    def on_joy_axis_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle a joystick axis motion event.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # JOYAXISMOTION    joy, axis, value
        self.log.debug(f'{type(self)}: {event}')

    def on_joy_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle a joystick button down event.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # JOYBUTTONDOWN    joy, button
        self.log.debug(f'{type(self)}: {event}')

    def on_joy_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle a joystick button up event.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # JOYBUTTONUP      joy, button
        self.log.debug(f'{type(self)}: {event}')

    def on_joy_hat_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle a joystick hat motion event.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # JOYHATMOTION     joy, hat, value
        self.log.debug(f'{type(self)}: {event}')

    def on_joy_ball_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle a joystick ball motion event.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # JOYBALLMOTION    joy, ball, rel
        self.log.debug(f'{type(self)}: {event}')

    @override
    def on_mouse_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle a mouse motion event.

        Args:
            event (HashableEvent): The event to handle.

        """
        # MOUSEMOTION      pos, rel, buttons
        self.log.debug(f'Mouse Motion Event: {type(self)}: {event}')

    @override
    def on_mouse_focus_event(self: Self, event: HashableEvent, entering_focus: object) -> None:
        """Handle a mouse focus event.

        Args:
            event (HashableEvent): The event to handle.
            entering_focus (object): The object entering focus.

        """
        # Custom Event
        self.log.debug(
            f'Mouse Focus Event: {type(self)}: {event}, Entering Focus: {entering_focus}',
        )

    @override
    def on_mouse_unfocus_event(
        self: Self,
        event: HashableEvent,
        leaving_focus: object = None,
    ) -> None:
        """Handle a mouse unfocus event.

        Args:
            event (HashableEvent): The event to handle.
            leaving_focus (object): The object leaving focus.

        """
        # Custom Event
        self.log.debug(f'Mouse Unfocus Event: {type(self)}: {event}')

    def on_mouse_enter_event(self: Self, event: HashableEvent) -> None:
        """Handle a mouse enter event.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # Custom Event
        self.log.debug(f'Mouse Enter Event: {type(self)}: {event}')

    def on_mouse_exit_event(self: Self, event: HashableEvent) -> None:
        """Handle a mouse exit event.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # Custom Event
        self.log.debug(f'Mouse Exit Event: {type(self)}: {event}')

    def on_mouse_drag_down_event(self: Self, event: HashableEvent, trigger: object | None) -> None:
        """Handle a mouse drag down event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        """
        self.log.debug(f'Mouse Drag Down Event: {type(self)}: event: {event}, trigger: {trigger}')

    def on_left_mouse_drag_down_event(
        self: Self,
        event: HashableEvent,
        trigger: object | None,
    ) -> None:
        """Handle a left mouse drag down event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        """
        self.log.debug(
            f'Left Mouse Drag Down Event: {type(self)}: event: {event}, trigger: {trigger}',
        )

    def on_left_mouse_drag_up_event(
        self: Self,
        event: HashableEvent,
        trigger: object | None,
    ) -> None:
        """Handle a left mouse drag up event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        """
        self.log.debug(
            f'Left Mouse Drag Up Event: {type(self)}: event: {event}, trigger: {trigger}',
        )

    def on_middle_mouse_drag_down_event(
        self: Self,
        event: HashableEvent,
        trigger: object | None,
    ) -> None:
        """Handle a middle mouse drag down event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        """
        self.log.debug(
            f'Middle Mouse Drag Down Event: {type(self)}: event: {event}, trigger: {trigger}',
        )

    def on_middle_mouse_drag_up_event(
        self: Self,
        event: HashableEvent,
        trigger: object | None,
    ) -> None:
        """Handle a middle mouse drag up event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        """
        self.log.debug(
            f'Middle Mouse Drag Up Event: {type(self)}: event: {event}, trigger: {trigger}',
        )

    def on_right_mouse_drag_down_event(
        self: Self,
        event: HashableEvent,
        trigger: object | None,
    ) -> None:
        """Handle a right mouse drag down event.

        Args:
        event (pygame.event.Event): The event to handle.
        trigger (object | None): The object that triggered the event.

        """
        self.log.debug(
            f'Right Mouse Drag Down Event: {type(self)}: event: {event}, trigger: {trigger}',
        )

    def on_right_mouse_drag_up_event(
        self: Self,
        event: HashableEvent,
        trigger: object | None,
    ) -> None:
        """Handle a right mouse drag up event.

        Args:
            event (pygame.event.Event): The event to handle.
            trigger (object | None): The object that triggered the event.

        """
        self.log.debug(
            f'Right Mouse Drag Up Event: {type(self)}: event: {event}, trigger: {trigger}',
        )

    def on_mouse_drag_up_event(self: Self, event: HashableEvent) -> None:
        """Handle a mouse drag up event.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.debug(f'Mouse Drag Up Event: {type(self)}: {event}')

    @override
    def on_mouse_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle a mouse button up event.

        Args:
            event (HashableEvent): The event to handle.

        """
        # MOUSEBUTTONUP    pos, button
        self.log.debug(f'{type(self)}: {event}')

    @override
    def on_left_mouse_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle a left mouse button up event.

        Args:
            event (HashableEvent): The event to handle.

        """
        # MOUSEBUTTONUP    pos, button

        if self.callbacks:
            callback = self.callbacks.get('on_left_mouse_button_up_event', None)
            if callback:
                callback(event=event, trigger=self)
        else:
            self.log.debug(f'{type(self)}: Left Mouse Button Up Event: {event} @ {self}')

    @override
    def on_middle_mouse_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle a middle mouse button up event.

        Args:
            event (HashableEvent): The event to handle.

        """
        # MOUSEBUTTONUP    pos, button
        self.log.debug(f'{type(self)}: Middle Mouse Button Up Event: {event}')

    @override
    def on_right_mouse_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle a right mouse button up event.

        Args:
            event (HashableEvent): The event to handle.

        """
        # MOUSEBUTTONUP    pos, button
        if self.callbacks:
            callback = self.callbacks.get('on_right_mouse_button_up_event', None)
            if callback:
                callback(event=event, trigger=self)
        else:
            self.log.debug(f'{type(self)}: Right Mouse Button Up Event: {event} @ {self}')

    @override
    def on_mouse_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle a mouse button down event.

        Args:
            event (HashableEvent): The event to handle.

        """
        # MOUSEBUTTONDOWN  pos, button
        self.log.debug(f'{type(self)}: {event} @ {self}')

    @override
    def on_left_mouse_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle a left mouse button down event.

        Args:
            event (HashableEvent): The event to handle.

        """
        # MOUSEBUTTONDOWN  pos, button
        callback = 'on_left_mouse_button_down_event'

        if self.callbacks:
            callback = self.callbacks.get('on_left_mouse_button_down_event', None)
            if callback:
                callback(event=event, trigger=self)
        else:
            self.log.debug(f'{type(self)}: Left Mouse Button Down Event: {event} @ {self}')

    @override
    def on_middle_mouse_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle a middle mouse button down event.

        Args:
            event (HashableEvent): The event to handle.

        """
        # MOUSEBUTTONDOWN  pos, button
        self.log.debug(f'{type(self)}: Middle Mouse Button Down Event: {event}')

    @override
    def on_right_mouse_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle a right mouse button down event.

        Args:
            event (HashableEvent): The event to handle.

        """
        # MOUSEBUTTONDOWN  pos, button
        if self.callbacks:
            callback = self.callbacks.get('on_right_mouse_button_down_event', None)
            if callback:
                callback(event=event, trigger=self)
        else:
            self.log.debug(f'{type(self)}: Right Mouse Button Down Event: {event} @ self')

    @override
    def on_mouse_scroll_down_event(self: Self, event: HashableEvent) -> None:
        """Handle a mouse scroll down event.

        Args:
            event (HashableEvent): The event to handle.

        """
        # MOUSEBUTTONDOWN  pos, button
        self.log.debug(f'{type(self)}: Mouse Scroll Down Event: {event}')

    @override
    def on_mouse_scroll_up_event(self: Self, event: HashableEvent) -> None:
        """Handle a mouse scroll up event.

        Args:
            event (HashableEvent): The event to handle.

        """
        # MOUSEBUTTONDOWN  pos, button
        self.log.debug(f'{type(self)}: Mouse Scroll Up Event: {event}')

    def on_mouse_chord_up_event(self: Self, event: HashableEvent) -> None:
        """Handle a mouse chord up event.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.debug(f'{type(self)}: Mouse Chord Up Event: {event}')

    def on_mouse_chord_down_event(self: Self, event: HashableEvent) -> None:
        """Handle a mouse chord down event.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.debug(f'{type(self)}: Mouse Chord Down Event: {event}')

    def on_key_down_event(self: Self, event: HashableEvent) -> None:
        """Handle a key down event.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # KEYDOWN          unicode, key, mod
        self.log.debug(f'{type(self)}: {event}')

    def on_key_up_event(self: Self, event: HashableEvent) -> None:
        """Handle a key up event.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # KEYUP            key, mod
        self.log.debug(f'{type(self)}: {event}')

    def on_key_chord_down_event(self: Self, event: HashableEvent, keys: list[int]) -> None:
        """Handle a key chord down event.

        Args:
            event (pygame.event.Event): The event to handle.
            keys (list[int]): The keys that were pressed.

        """
        self.log.debug(f'{type(self)}: {event}, {keys}')

    def on_key_chord_up_event(self: Self, event: HashableEvent, keys: list[int]) -> None:
        """Handle a key chord up event.

        Args:
            event (pygame.event.Event): The event to handle.
            keys (list[int]): The keys that were pressed.

        """
        self.log.debug(f'{type(self)} KEYCHORDUP: {event}, {keys}')

    def on_quit_event(self: Self, event: HashableEvent) -> None:
        """Handle a quit event.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # QUIT             none
        self.log.debug(f'{type(self)}: {event}')
        # terminate() is provided by Scene subclasses via SceneInterface,
        # not directly on Sprite. Cast to Any to allow dynamic dispatch.
        game: Any = self
        game.terminate()  # ty: ignore[unresolved-attribute]

    def on_active_event(self: Self, event: HashableEvent) -> None:
        """Handle an active event.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # ACTIVEEVENT      gain, state
        self.log.debug(f'{type(self)}: {event}')

    def on_video_resize_event(self: Self, event: HashableEvent) -> None:
        """Handle a video resize event.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # VIDEORESIZE      size, w, h
        self.log.debug(f'{type(self)}: {event}')

    def on_video_expose_event(self: Self, event: HashableEvent) -> None:
        """Handle a video expose event.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # VIDEOEXPOSE      none
        self.log.debug(f'{type(self)}: {event}')

    def on_sys_wm_event(self: Self, event: HashableEvent) -> None:
        """Handle a sys wm event.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # SYSWMEVENT
        self.log.debug(f'{type(self)}: {event}')

    def on_user_event(self: Self, event: HashableEvent) -> None:
        """Handle a user event.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # USEREVENT        code
        self.log.debug(f'{type(self)}: {event}')

    @override
    def on_left_mouse_drag_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle a left mouse drag event.

        Args:
            event (HashableEvent): The event to handle.
            trigger (HashableEvent): The event that triggered the drag.

        """
        self.log.debug(f'{type(self)}: Left Mouse Drag Event: {event} @ {self} for {trigger}')

    @override
    def on_middle_mouse_drag_event(
        self: Self,
        event: HashableEvent,
        trigger: HashableEvent,
    ) -> None:
        """Handle a middle mouse drag event.

        Args:
            event (HashableEvent): The event to handle.
            trigger (HashableEvent): The event that triggered the drag.

        """
        self.log.debug(f'{type(self)}: Middle Mouse Drag Event: {event} @ {self} for {trigger}')

    @override
    def on_right_mouse_drag_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle a right mouse drag event.

        Args:
            event (HashableEvent): The event to handle.
            trigger (HashableEvent): The event that triggered the drag.

        """
        self.log.debug(f'{type(self)}: Right Mouse Drag Event: {event} @ {self} for {trigger}')

    @override
    def on_left_mouse_drop_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle a left mouse drop event.

        Args:
            event (HashableEvent): The event to handle.
            trigger (HashableEvent): The event that triggered the drop.

        """
        self.log.debug(f'{type(self)}: Left Mouse Drop Event: {event} @ {self} for {trigger}')

    @override
    def on_middle_mouse_drop_event(
        self: Self,
        event: HashableEvent,
        trigger: HashableEvent,
    ) -> None:
        """Handle a middle mouse drop event.

        Args:
            event (HashableEvent): The event to handle.
            trigger (HashableEvent): The event that triggered the drop.

        """
        self.log.debug(f'{type(self)}: Middle Mouse Drop Event: {event} @ {self} for {trigger}')

    @override
    def on_right_mouse_drop_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle a right mouse drop event.

        Args:
            event (HashableEvent): The event to handle.
            trigger (HashableEvent): The event that triggered the drop.

        """
        self.log.debug(f'{type(self)}: Right Mouse Drop Event: {event} @ {self} for {trigger}')

    @override
    def on_mouse_drag_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle a mouse drag event.

        Args:
            event (HashableEvent): The event to handle.
            trigger (HashableEvent): The event that triggered the drag.

        """
        self.log.debug(f'{type(self)}: Mouse Drag Event: {event} @ {self} for {trigger}')

    @override
    def on_mouse_drop_event(self: Self, event: HashableEvent, trigger: HashableEvent) -> None:
        """Handle a mouse drop event.

        Args:
            event (HashableEvent): The event to handle.
            trigger (HashableEvent): The event that triggered the drop.

        """
        self.log.debug(f'{type(self)}: Mouse Drop Event: {event} @ {self} for {trigger}')

    @override
    def on_mouse_wheel_event(self: Self, event: HashableEvent) -> None:
        """Handle a mouse wheel event.

        Args:
            event (HashableEvent): The event to handle.

        """
        self.log.debug(f'{type(self)}: Mouse Wheel Event: {event} @ {self}')

    @override
    def __str__(self: Self) -> str:
        """Return a string representation of the sprite.

        Returns:
            str: The string representation.

        """
        return f'{type(self)} "{self.name}" ({self!r})'
