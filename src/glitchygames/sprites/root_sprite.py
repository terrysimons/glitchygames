"""Root sprite class for Glitchy Games Engine.

This module contains the base RootSprite class that all Glitchy Games sprites
inherit from.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Self, cast, override

import pygame

from glitchygames.events import KeyboardEvents, MouseEvents
from glitchygames.interfaces import SpriteInterface

if TYPE_CHECKING:
    from glitchygames.events.base import (
        HashableEvent,
        KeyEvent,
        MouseButtonEvent,
        MouseMotionEvent,
        MouseWheelEvent,
    )

LOG = logging.getLogger('game.sprites')


class RootSprite(MouseEvents, KeyboardEvents, SpriteInterface, pygame.sprite.DirtySprite):  # ruff: ignore[too-many-public-methods]
    """A root sprite class.  All Glitchy Games sprites inherit from this class.

    It carries the mouse and keyboard protocols, every handler silent unless a subclass overrides
    it, so the engine's dispatchers can call any handler on any sprite
    (tests/test_sprite_classes_are_root_sprites.py keeps every sprite class on it).
    """

    log = LOG

    # Override pygame's optional property typing — GlitchyGames sprites always
    # have a valid image and rect after __init__, so the getter return types
    # narrow out None.  Setters keep the parent's wider parameter types to
    # satisfy LSP.

    @property
    @override
    def image(self) -> pygame.Surface:
        """The sprite image (always non-None for GlitchyGames sprites)."""
        return self._gg_image

    @image.setter
    def image(self, value: pygame.Surface | None) -> None:
        self._gg_image = cast('pygame.Surface', value)

    @property
    @override
    def rect(self) -> pygame.FRect | pygame.Rect:
        """The sprite rect (always non-None for GlitchyGames sprites)."""
        return self._gg_rect

    @rect.setter
    def rect(self, value: pygame.FRect | pygame.Rect | None) -> None:
        self._gg_rect = cast('pygame.FRect | pygame.Rect', value)

    def __init__(self: Self, groups: pygame.sprite.LayeredDirty[Any] | None = None) -> None:
        """Initialize a RootSprite.

        Args:
            groups (pygame.sprite.LayeredDirty[Any] | None): The sprite groups to add the sprite to.

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        super().__init__(groups)
        self._gg_rect = pygame.Rect(0, 0, 0, 0)
        self._gg_image = pygame.Surface((0, 0))  # Non-null placeholder; subclasses replace

    # The mouse and keyboard protocols: every handler, silent unless a subclass overrides it,
    # so the dispatchers can call any handler on any sprite (moved up from Sprite, 2026-11-15:
    # AnimatedSprite stood outside RootSprite with none, and the pointer over one ended the game)

    @override
    def on_mouse_motion_event(self: Self, event: MouseMotionEvent) -> None:
        """Handle a mouse motion event.

        Args:
            event (MouseMotionEvent): The event to handle.

        """

    @override
    def on_mouse_focus_event(self: Self, event: HashableEvent, entering_focus: object) -> None:
        """Handle a mouse focus event.

        Args:
            event (HashableEvent): The event to handle.
            entering_focus (object): The object entering focus.

        """
        # Custom Event
        self.log.debug(
            'Mouse Focus Event: %s: %s, Entering Focus: %s',
            type(self),
            event,
            entering_focus,
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
        self.log.debug('Mouse Unfocus Event: %s: %s', type(self), event)

    @override
    def on_mouse_button_up_event(self: Self, event: MouseButtonEvent) -> None:
        """Handle a mouse button up event.

        Args:
            event (MouseButtonEvent): The event to handle.

        """
        # MOUSEBUTTONUP    pos, button
        self.log.debug('%s: %s', type(self), event)

    @override
    def on_left_mouse_button_up_event(self: Self, event: MouseButtonEvent) -> None:
        """Handle a left mouse button up event.

        Args:
            event (MouseButtonEvent): The event to handle.

        """
        # MOUSEBUTTONUP    pos, button

        self.log.debug('%s: Left Mouse Button Up Event: %s @ %s', type(self), event, self)

    @override
    def on_middle_mouse_button_up_event(self: Self, event: MouseButtonEvent) -> None:
        """Handle a middle mouse button up event.

        Args:
            event (MouseButtonEvent): The event to handle.

        """
        # MOUSEBUTTONUP    pos, button
        self.log.debug('%s: Middle Mouse Button Up Event: %s', type(self), event)

    @override
    def on_right_mouse_button_up_event(self: Self, event: MouseButtonEvent) -> None:
        """Handle a right mouse button up event.

        Args:
            event (MouseButtonEvent): The event to handle.

        """
        # MOUSEBUTTONUP    pos, button
        self.log.debug('%s: Right Mouse Button Up Event: %s @ %s', type(self), event, self)

    @override
    def on_mouse_button_down_event(self: Self, event: MouseButtonEvent) -> None:
        """Handle a mouse button down event.

        Args:
            event (MouseButtonEvent): The event to handle.

        """
        # MOUSEBUTTONDOWN  pos, button
        self.log.debug('%s: %s @ %s', type(self), event, self)

    @override
    def on_left_mouse_button_down_event(self: Self, event: MouseButtonEvent) -> None:
        """Handle a left mouse button down event.

        Args:
            event (MouseButtonEvent): The event to handle.

        """
        # MOUSEBUTTONDOWN  pos, button
        self.log.debug('%s: Left Mouse Button Down Event: %s @ %s', type(self), event, self)

    @override
    def on_middle_mouse_button_down_event(self: Self, event: MouseButtonEvent) -> None:
        """Handle a middle mouse button down event.

        Args:
            event (MouseButtonEvent): The event to handle.

        """
        # MOUSEBUTTONDOWN  pos, button
        self.log.debug('%s: Middle Mouse Button Down Event: %s', type(self), event)

    @override
    def on_right_mouse_button_down_event(self: Self, event: MouseButtonEvent) -> None:
        """Handle a right mouse button down event.

        Args:
            event (MouseButtonEvent): The event to handle.

        """
        # MOUSEBUTTONDOWN  pos, button
        self.log.debug('%s: Right Mouse Button Down Event: %s @ %s', type(self), event, self)

    @override
    def on_mouse_scroll_down_event(self: Self, event: MouseButtonEvent) -> None:
        """Handle a mouse scroll down event.

        Args:
            event (MouseButtonEvent): The event to handle.

        """
        # MOUSEBUTTONDOWN  pos, button
        self.log.debug('%s: Mouse Scroll Down Event: %s', type(self), event)

    @override
    def on_mouse_scroll_up_event(self: Self, event: MouseButtonEvent) -> None:
        """Handle a mouse scroll up event.

        Args:
            event (MouseButtonEvent): The event to handle.

        """
        # MOUSEBUTTONDOWN  pos, button
        self.log.debug('%s: Mouse Scroll Up Event: %s', type(self), event)

    @override
    def on_key_down_event(self: Self, event: KeyEvent) -> None:
        """Handle a key down event.

        Args:
            event (KeyEvent): The event to handle.

        """
        # KEYDOWN          unicode, key, mod
        self.log.debug('%s: %s', type(self), event)

    @override
    def on_key_up_event(self: Self, event: KeyEvent) -> None:
        """Handle a key up event.

        Args:
            event (KeyEvent): The event to handle.

        """
        # KEYUP            key, mod
        self.log.debug('%s: %s', type(self), event)

    @override
    def on_key_chord_down_event(self: Self, event: KeyEvent, keys: tuple[KeyEvent, ...]) -> None:
        """Handle a key chord down event.

        Args:
            event (KeyEvent): The event to handle.
            keys (tuple[KeyEvent, ...]): The KEYDOWN events of the keys held, in the order
                they were pressed.

        """
        self.log.debug('%s: %s, %s', type(self), event, keys)

    @override
    def on_key_chord_up_event(self: Self, event: KeyEvent, keys: tuple[KeyEvent, ...]) -> None:
        """Handle a key chord up event.

        Args:
            event (KeyEvent): The event to handle.
            keys (tuple[KeyEvent, ...]): The KEYDOWN events of the keys held, in the order
                they were pressed.

        """
        self.log.debug('%s KEYCHORDUP: %s, %s', type(self), event, keys)

    @override
    def on_left_mouse_drag_event(
        self: Self, event: MouseMotionEvent, trigger: MouseButtonEvent
    ) -> None:
        """Handle a left mouse drag event.

        Args:
            event (MouseMotionEvent): The event to handle.
            trigger (MouseButtonEvent): The event that triggered the drag.

        """

    @override
    def on_middle_mouse_drag_event(
        self: Self,
        event: MouseMotionEvent,
        trigger: MouseButtonEvent,
    ) -> None:
        """Handle a middle mouse drag event.

        Args:
            event (MouseMotionEvent): The event to handle.
            trigger (MouseButtonEvent): The event that triggered the drag.

        """

    @override
    def on_right_mouse_drag_event(
        self: Self, event: MouseMotionEvent, trigger: MouseButtonEvent
    ) -> None:
        """Handle a right mouse drag event.

        Args:
            event (MouseMotionEvent): The event to handle.
            trigger (MouseButtonEvent): The event that triggered the drag.

        """

    @override
    def on_left_mouse_drop_event(
        self: Self, event: MouseButtonEvent, trigger: MouseButtonEvent
    ) -> None:
        """Handle a left mouse drop event.

        Args:
            event (MouseButtonEvent): The event to handle.
            trigger (MouseButtonEvent): The event that triggered the drop.

        """
        self.log.debug(
            '%s: Left Mouse Drop Event: %s @ %s for %s', type(self), event, self, trigger
        )

    @override
    def on_middle_mouse_drop_event(
        self: Self,
        event: MouseButtonEvent,
        trigger: MouseButtonEvent,
    ) -> None:
        """Handle a middle mouse drop event.

        Args:
            event (MouseButtonEvent): The event to handle.
            trigger (MouseButtonEvent): The event that triggered the drop.

        """
        self.log.debug(
            '%s: Middle Mouse Drop Event: %s @ %s for %s', type(self), event, self, trigger
        )

    @override
    def on_right_mouse_drop_event(
        self: Self, event: MouseButtonEvent, trigger: MouseButtonEvent
    ) -> None:
        """Handle a right mouse drop event.

        Args:
            event (MouseButtonEvent): The event to handle.
            trigger (MouseButtonEvent): The event that triggered the drop.

        """
        self.log.debug(
            '%s: Right Mouse Drop Event: %s @ %s for %s', type(self), event, self, trigger
        )

    @override
    def on_mouse_drag_event(self: Self, event: MouseMotionEvent, trigger: MouseButtonEvent) -> None:
        """Handle a mouse drag event.

        Args:
            event (MouseMotionEvent): The event to handle.
            trigger (MouseButtonEvent): The event that triggered the drag.

        """

    @override
    def on_mouse_drop_event(self: Self, event: MouseButtonEvent, trigger: MouseButtonEvent) -> None:
        """Handle a mouse drop event.

        Args:
            event (MouseButtonEvent): The event to handle.
            trigger (MouseButtonEvent): The event that triggered the drop.

        """
        self.log.debug('%s: Mouse Drop Event: %s @ %s for %s', type(self), event, self, trigger)

    @override
    def on_mouse_wheel_event(self: Self, event: MouseWheelEvent) -> None:
        """Handle a mouse wheel event.

        Args:
            event (MouseWheelEvent): The event to handle.

        """
        self.log.debug('%s: Mouse Wheel Event: %s @ %s', type(self), event, self)
