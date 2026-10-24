#!/usr/bin/env python3
"""Mouse manager."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar, Self, cast, override

if TYPE_CHECKING:
    import argparse

import pygame

from glitchygames.events import (
    MOUSE_EVENTS,
    HashableEvent,
    MouseButtonEvent,
    MouseEvents,
    MouseMotionEvent,
    MouseWheelEvent,
    ResourceManager,
)

LOG = logging.getLogger('game.mouse')
LOG.addHandler(logging.NullHandler())

# Pygame uses integer constants for mouse buttons with no named aliases.
# MOUSEWHEEL events are handled via on_mouse_wheel_event().
MOUSE_BUTTON_LEFT = 1
MOUSE_BUTTON_WHEEL = 2
MOUSE_BUTTON_RIGHT = 3
MOUSE_WHEEL_SCROLL_UP = 4
MOUSE_WHEEL_SCROLL_DOWN = 5


class MouseEventManager(ResourceManager):
    """Mouse manager event handler."""

    class MouseEventProxy(MouseEvents, ResourceManager):  # ruff: ignore[too-many-public-methods] - one handler per mouse event type
        """Mouse manager event proxy."""

        # A proxy belongs to its manager: each construction is a new one (ResourceManager)
        SHARES_INSTANCE: ClassVar[bool] = False

        def __init__(self: Self, game: object = None) -> None:
            """Initialize the mouse manager event proxy.

            Args:
                game (object): The game instance.

            """
            super().__init__(game)
            self.mouse_state: dict[int, Any] = {}
            self.mouse_dragging = False
            self.mouse_dropping = False
            self.current_focus: Any = None
            self.previous_focus: Any = None
            self.focus_locked = False

            self.game: Any = game
            self.proxies = [self.game, pygame.mouse]

        @override
        def on_mouse_motion_event(self: Self, event: MouseMotionEvent) -> None:
            """Handle the mouse motion event.

            Args:
                event (MouseMotionEvent): The event to handle.

            """
            self.mouse_state[event.type] = event
            self.game.on_mouse_motion_event(event)

            sprite = collided_sprites(self.game, event=event, index=-1)

            # Focus follows the topmost sprite under the mouse: the sprite entered is focused
            # (and the one left unfocused) before it gets the motion (BUGS.md #199: the focus
            # handlers were never called)
            sprite_under_mouse = sprite[0] if sprite else None
            if sprite_under_mouse is not self.current_focus:
                if sprite_under_mouse is None:
                    self.on_mouse_unfocus_event(event, self.current_focus)
                else:
                    self.on_mouse_focus_event(event, sprite_under_mouse)

            if sprite:
                self.log.debug('%s: Mouse Motion: %s', type(self), event)
                sprite[0].on_mouse_motion_event(event)

            # Caller can check the buttons.
            # Note: This probably doesn't work right because
            # we aren't keeping track of button states.
            # We should be looking at all mouse states and emitting appropriately.
            # A snapshot: a drag handler may press or release a button (changing mouse_state)
            for trigger in tuple(self.mouse_state.values()):
                if trigger.type == pygame.MOUSEBUTTONDOWN:
                    self.on_mouse_drag_event(event, trigger)
                    self.mouse_dragging = True

        @override
        def on_mouse_drag_event(
            self: Self, event: MouseMotionEvent, trigger: MouseButtonEvent
        ) -> None:
            """Handle the mouse drag event.

            Args:
                event (MouseMotionEvent): The event to handle.
                trigger (MouseButtonEvent): The triggering event.

            """
            self.game.on_mouse_drag_event(event, trigger)

            if trigger.button == MOUSE_BUTTON_LEFT:
                self.on_left_mouse_drag_event(event, trigger)
            if trigger.button == MOUSE_BUTTON_WHEEL:
                self.on_middle_mouse_drag_event(event, trigger)
            if trigger.button == MOUSE_BUTTON_RIGHT:
                self.on_right_mouse_drag_event(event, trigger)
            if trigger.button == MOUSE_WHEEL_SCROLL_UP:
                # This doesn't really make sense.
                pass
            if trigger.button == MOUSE_WHEEL_SCROLL_DOWN:
                # This doesn't really make sense.
                pass

        @override
        def on_mouse_drop_event(
            self: Self, event: MouseButtonEvent, trigger: MouseButtonEvent
        ) -> None:
            """Handle the mouse drop event.

            Args:
                event (MouseButtonEvent): The event to handle.
                trigger (MouseButtonEvent): The triggering event.

            """
            self.log.debug('%s: Mouse Drop: %s %s', type(self), event, trigger)
            self.mouse_dropping = True
            self.game.on_mouse_drop_event(event, trigger)

            if trigger.button == MOUSE_BUTTON_LEFT:
                self.on_left_mouse_drop_event(event, trigger)
            if trigger.button == MOUSE_BUTTON_WHEEL:
                self.on_middle_mouse_drop_event(event, trigger)
            if trigger.button == MOUSE_BUTTON_RIGHT:
                self.on_right_mouse_drop_event(event, trigger)
            if trigger.button == MOUSE_WHEEL_SCROLL_UP:
                # This doesn't really make sense.
                pass
            if trigger.button == MOUSE_WHEEL_SCROLL_DOWN:
                # This doesn't really make sense.
                pass

            self.mouse_dropping = False

        @override
        def on_left_mouse_drag_event(
            self: Self,
            event: MouseMotionEvent,
            trigger: MouseButtonEvent,
        ) -> None:
            """Handle the left mouse drag event.

            Args:
                event (MouseMotionEvent): The event to handle.
                trigger (MouseButtonEvent): The triggering event.

            """
            self.game.on_left_mouse_drag_event(event, trigger)

        @override
        def on_left_mouse_drop_event(
            self: Self,
            event: MouseButtonEvent,
            trigger: MouseButtonEvent,
        ) -> None:
            """Handle the left mouse drop event.

            Args:
                event (MouseButtonEvent): The event to handle.
                trigger (MouseButtonEvent): The triggering event.

            """
            self.game.on_left_mouse_drop_event(event, trigger)

        @override
        def on_middle_mouse_drag_event(
            self: Self,
            event: MouseMotionEvent,
            trigger: MouseButtonEvent,
        ) -> None:
            """Handle the middle mouse drag event.

            Args:
                event (MouseMotionEvent): The event to handle.
                trigger (MouseButtonEvent): The triggering event.

            """
            self.game.on_middle_mouse_drag_event(event, trigger)

        @override
        def on_middle_mouse_drop_event(
            self: Self,
            event: MouseButtonEvent,
            trigger: MouseButtonEvent,
        ) -> None:
            """Handle the middle mouse drop event.

            Args:
                event (MouseButtonEvent): The event to handle.
                trigger (MouseButtonEvent): The triggering event.

            """
            self.game.on_middle_mouse_drop_event(event, trigger)

        @override
        def on_right_mouse_drag_event(
            self: Self,
            event: MouseMotionEvent,
            trigger: MouseButtonEvent,
        ) -> None:
            """Handle the right mouse drag event.

            Args:
                event (MouseMotionEvent): The event to handle.
                trigger (MouseButtonEvent): The triggering event.

            """
            self.game.on_right_mouse_drag_event(event, trigger)

        @override
        def on_right_mouse_drop_event(
            self: Self,
            event: MouseButtonEvent,
            trigger: MouseButtonEvent,
        ) -> None:
            """Handle the right mouse drop event.

            Args:
                event (MouseButtonEvent): The event to handle.
                trigger (MouseButtonEvent): The triggering event.

            """
            self.game.on_right_mouse_drop_event(event, trigger)

        @override
        def on_mouse_focus_event(self: Self, event: HashableEvent, entering_focus: object) -> None:
            """Handle the mouse focus event.

            Args:
                event (pygame.event.Event): The event to handle.
                entering_focus (object): The object entering focus.

            """
            # Send a leave focus event for the old focus.
            self.on_mouse_unfocus_event(event, self.current_focus)

            # We've entered a new object.
            self.current_focus = entering_focus

            # Send an enter event for the new focus.
            entering_focus.on_mouse_focus_event(event, self.current_focus)  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]  # ty: ignore[unresolved-attribute]

            self.log.info('Entered Focus: %s', self.current_focus)

        @override
        def on_mouse_unfocus_event(self: Self, event: HashableEvent, leaving_focus: object) -> None:
            """Handle the mouse unfocus event.

            Args:
                event (pygame.event.Event): The event to handle.
                leaving_focus (object): The object leaving focus.

            """
            self.previous_focus = leaving_focus

            if leaving_focus:
                leaving_focus.on_mouse_unfocus_event(event)  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]  # ty: ignore[unresolved-attribute]
                self.current_focus = None

                self.log.info('Left Focus: %s', self.previous_focus)

        @override
        def on_mouse_button_up_event(self: Self, event: MouseButtonEvent) -> None:
            """Handle the mouse button up event.

            Args:
                event (MouseButtonEvent): The event to handle.

            """
            self.mouse_state[event.button] = event

            # First dispatch to specific button handlers to allow widgets to react
            if event.button == MOUSE_BUTTON_LEFT:
                self.on_left_mouse_button_up_event(event)
            if event.button == MOUSE_BUTTON_WHEEL:
                self.on_middle_mouse_button_up_event(event)
            if event.button == MOUSE_BUTTON_RIGHT:
                self.on_right_mouse_button_up_event(event)

            # Then dispatch the generic scene-level handler to keep symmetry
            # with mouse down and ensure scene-wide focus/overlay bookkeeping runs
            self.game.on_mouse_button_up_event(event)
            if event.button == MOUSE_WHEEL_SCROLL_UP:
                # This doesn't really make sense.
                pass
            if event.button == MOUSE_WHEEL_SCROLL_DOWN:
                # This doesn't really make sense.
                pass

            if self.mouse_dragging:
                # The mouse up location is also the trigger. Through this proxy's own drop
                # handler, which also calls the released button's drop handler (BUGS.md #199:
                # calling only the game's generic one, the button-specific ones never ran)
                self.mouse_dragging = False
                self.on_mouse_drop_event(event, event)

        @override
        def on_left_mouse_button_up_event(self: Self, event: MouseButtonEvent) -> None:
            """Handle the left mouse button up event.

            Args:
                event (MouseButtonEvent): The event to handle.

            """
            self.mouse_state[event.button] = event
            self.game.on_left_mouse_button_up_event(event)

        @override
        def on_middle_mouse_button_up_event(self: Self, event: MouseButtonEvent) -> None:
            """Handle the middle mouse button up event.

            Args:
                event (MouseButtonEvent): The event to handle.

            """
            self.game.on_middle_mouse_button_up_event(event)

        @override
        def on_right_mouse_button_up_event(self: Self, event: MouseButtonEvent) -> None:
            """Handle the right mouse button up event.

            Args:
                event (MouseButtonEvent): The event to handle.

            """
            self.game.on_right_mouse_button_up_event(event)

        @override
        def on_mouse_button_down_event(self: Self, event: MouseButtonEvent) -> None:
            """Handle the mouse button down event.

            Args:
                event (MouseButtonEvent): The event to handle.

            """
            self.mouse_state[event.button] = event
            # Scene-first: let scene clear focus/overlays before per-sprite handlers
            self.game.on_mouse_button_down_event(event)

            if event.button == MOUSE_BUTTON_LEFT:
                self.on_left_mouse_button_down_event(event)
            if event.button == MOUSE_BUTTON_WHEEL:
                self.on_middle_mouse_button_down_event(event)
            if event.button == MOUSE_BUTTON_RIGHT:
                self.on_right_mouse_button_down_event(event)
            # Button 4 is the wheel turned up, 5 down (BUGS.md #199: they were swapped)
            if event.button == MOUSE_WHEEL_SCROLL_UP:
                self.on_mouse_scroll_up_event(event)
            if event.button == MOUSE_WHEEL_SCROLL_DOWN:
                self.on_mouse_scroll_down_event(event)

        @override
        def on_left_mouse_button_down_event(self: Self, event: MouseButtonEvent) -> None:
            """Handle the left mouse button down event.

            Args:
                event (MouseButtonEvent): The event to handle.

            """
            self.game.on_left_mouse_button_down_event(event)

        @override
        def on_middle_mouse_button_down_event(self: Self, event: MouseButtonEvent) -> None:
            """Handle the middle mouse button down event.

            Args:
                event (MouseButtonEvent): The event to handle.

            """
            self.game.on_middle_mouse_button_down_event(event)

        @override
        def on_right_mouse_button_down_event(self: Self, event: MouseButtonEvent) -> None:
            """Handle the right mouse button down event.

            Args:
                event (MouseButtonEvent): The event to handle.

            """
            self.game.on_right_mouse_button_down_event(event)

        @override
        def on_mouse_scroll_down_event(self: Self, event: MouseButtonEvent) -> None:
            """Handle the mouse scroll down event.

            Args:
                event (MouseButtonEvent): The event to handle.

            """
            self.game.on_mouse_scroll_down_event(event)

        @override
        def on_mouse_scroll_up_event(self: Self, event: MouseButtonEvent) -> None:
            """Handle the mouse scroll up event.

            Args:
                event (MouseButtonEvent): The event to handle.

            """
            self.game.on_mouse_scroll_up_event(event)

        @override
        def on_mouse_wheel_event(self: Self, event: MouseWheelEvent) -> None:
            """Handle the mouse wheel event.

            Args:
                event (MouseWheelEvent): The event to handle.

            """
            self.game.on_mouse_wheel_event(event)

    def __init__(self: Self, game: object = None) -> None:
        """Initialize the mouse manager.

        Args:
            game (object): The game instance.

        """
        super().__init__(game=game)
        pygame.event.set_allowed(MOUSE_EVENTS)
        self.proxies = [MouseEventManager.MouseEventProxy(game=game)]

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add arguments to the argument parser.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            argparse.ArgumentParser: The result.

        """
        _group = parser.add_argument_group('Mouse Options')

        return parser


# MousePointer is intentionally not a singleton: each call site creates
# a short-lived instance for collision detection at a specific position.
# Pygame only tracks one system cursor, so there is only ever one real
# mouse position at any given time.
class MousePointer:
    """Mouse pointer sprite."""

    def __init__(self: Self, pos: tuple[int, int], size: tuple[int, int] = (1, 1)) -> None:
        """Initialize the mouse pointer sprite.

        Args:
            pos (tuple): The position of the mouse pointer.
            size (tuple): The size of the mouse pointer.

        """
        super().__init__()

        self.pos: list[int] = list(pos)
        self.size = size
        self.rect = pygame.Rect(self.pos, self.size)

    @property
    def x(self: Self) -> int:
        """The x coordinate of the mouse pointer.

        Returns:
            int

        """
        return self.pos[0]

    @x.setter
    def x(self: Self, new_x: int) -> None:
        """Set the x coordinate of the mouse pointer.

        Args:
            new_x (int): The new x coordinate.

        """
        self.pos[0] = new_x

    @property
    def y(self: Self) -> int:
        """The y coordinate of the mouse pointer.

        Returns:
            int

        """
        return self.pos[1]

    @y.setter
    def y(self: Self, new_y: int) -> None:
        """Set the y coordinate of the mouse pointer.

        Args:
            new_y (int): The new y coordinate.

        """
        self.pos[1] = new_y


def collided_sprites(scene: object, event: HashableEvent, index: int | None = None) -> list[Any]:
    """Get the list of collided sprites.

    Args:
        scene (object): The scene to check.
        event (pygame.event.Event): The event to check.
        index (int): The index of the sprite to return.

    Returns:
        list: The list of collided sprites.

    """
    mouse = MousePointer(pos=event.pos)

    all_sprites = cast('Any', scene).all_sprites
    sprites: list[Any] = pygame.sprite.spritecollide(
        sprite=mouse,
        group=all_sprites,
        dokill=False,
    )

    if sprites:
        if index is None:
            return sprites

        return [sprites[index]]

    return []
