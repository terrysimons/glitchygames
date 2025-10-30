#!/usr/bin/env python3
"""Mouse manager."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import argparse

import pygame
from glitchygames.events import MouseEvents, ResourceManager

# from glitchygames.sprites import collided_sprites

LOG = logging.getLogger("game.mouse")
LOG.addHandler(logging.NullHandler())

# TODO @<terry.simons@gmail.com>: Add pygame 2 MOUSEWHEEL event handling.
# TODO: No better pygame names?
MOUSE_BUTTON_LEFT = 1
MOUSE_BUTTON_WHEEL = 2
MOUSE_BUTTON_RIGHT = 3
MOUSE_WHEEL_SCROLL_UP = 4
MOUSE_WHEEL_SCROLL_DOWN = 5


class MouseManager(ResourceManager):
    """Mouse manager event handler."""

    class MouseProxy(MouseEvents, ResourceManager):
        """Mouse manager event proxy."""

        def __init__(self: Self, game: object = None) -> None:
            """Initialize the mouse manager event proxy.

            Args:
                game (object): The game instance.

            Returns:
                None

            """
            super().__init__(game)
            self.mouse_state = {}
            self.mouse_dragging = False
            self.mouse_dropping = False
            self.current_focus = None
            self.previous_focus = None
            self.focus_locked = False

            self.game = game
            self.proxies = [self.game, pygame.mouse]

        def on_mouse_motion_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the mouse motion event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.mouse_state[event.type] = event
            self.game.on_mouse_motion_event(event)

            sprite = collided_sprites(self.game, event=event, index=-1)

            if sprite:
                self.log.debug(f"{type(self)}: Mouse Motion: {event}")
                sprite[0].on_mouse_motion_event(event)

                # # See if we're focused on the same sprite.
                # if self.current_focus != collided_sprite:
                #     # Newly focused object can "see" what the previously focused object was.
                #     #
                #     # Will be "None" if nothing is focused.
                #     #
                #     # We can use this to enable drag and drop.
                #     #
                #     # This will take care of the unfocus event, too.
                #     self.on_mouse_focus_event(event, collided_sprite)
                #     collided_sprite.on_mouse_enter_event(event)
                # else:
                #     # Otherwise, pass motion event to the focused sprite
                #     # so it can handle sub-components if it wants to.
                # self.current_focus.on_mouse_motion_event(event)
            # elif self.current_focus:
            #     # If we're focused on a sprite but the collide sprites list is empty, then
            #     # we're moving from a focus to empty space, and we should send an unfocus event.
            #     self.current_focus.on_mouse_exit_event(event)
            #     self.on_mouse_unfocus_event(event, self.current_focus)

            # Caller can check the buttons.
            # Note: This probably doesn't work right because
            # we aren't keeping track of button states.
            # We should be looking at all mouse states and emitting appropriately.
            for trigger in self.mouse_state.values():
                if trigger.type == pygame.MOUSEBUTTONDOWN:
                    self.on_mouse_drag_event(event, trigger)
                    self.mouse_dragging = True

        def on_mouse_drag_event(
            self: Self, event: pygame.event.Event, trigger: pygame.event.Event
        ) -> None:
            """Handle the mouse drag event.

            Args:
                event (pygame.event.Event): The event to handle.
                trigger (pygame.event.Event): The triggering event.

            Returns:
                None

            """
            self.log.debug(f"{type(self)}: Mouse Drag: {event}")
            self.game.on_mouse_drag_event(event, trigger)

            # if self.focus_locked:
            #     if self.current_focus:
            #         self.current_focus.on_mouse_drag_event(event, trigger)
            #     elif self.previous_focus:
            #         self.previous_focus.on_mouse_drag_event(event, trigger)

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

        def on_mouse_drop_event(
            self: Self, event: pygame.event.Event, trigger: pygame.event.Event
        ) -> None:
            """Handle the mouse drop event.

            Args:
                event (pygame.event.Event): The event to handle.
                trigger (pygame.event.Event): The triggering event.

            Returns:
                None

            """
            self.log.debug(f"{type(self)}: Mouse Drop: {event} {trigger}")
            self.mouse_dropping = True
            self.game.on_mouse_drop_event(event, trigger)

            # if self.focus_locked:
            #     if self.current_focus:
            #         self.current_focus.on_mouse_drop_event(event, trigger)
            #     elif self.previous_focus:
            #         self.previous_focus.on_mouse_drop_event(event, trigger)

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

        def on_left_mouse_drag_event(
            self: Self, event: pygame.event.Event, trigger: pygame.event.Event
        ) -> None:
            """Handle the left mouse drag event.

            Args:
                event (pygame.event.Event): The event to handle.
                trigger (pygame.event.Event): The triggering event.

            Returns:
                None

            """
            self.game.on_left_mouse_drag_event(event, trigger)

            # if self.focus_locked:
            #     if self.current_focus:
            #         self.current_focus.on_left_mouse_drag_event(event, trigger)
            #     elif self.previous_focus:
            #         self.previous_focus.on_left_mouse_drag_event(event, trigger)

        def on_left_mouse_drop_event(
            self: Self, event: pygame.event.Event, trigger: pygame.event.Event
        ) -> None:
            """Handle the left mouse drop event.

            Args:
                event (pygame.event.Event): The event to handle.
                trigger (pygame.event.Event): The triggering event.

            Returns:
                None

            """
            self.game.on_left_mouse_drag_up_event(event, trigger)

            # if self.focus_locked:
            #     if self.current_focus:
            #         self.current_focus.on_left_mouse_drop_event(event, trigger)
            #     elif self.previous_focus:
            #         self.previous_focus.on_left_mouse_drop_event(event, trigger)

        def on_middle_mouse_drag_event(
            self: Self, event: pygame.event.Event, trigger: pygame.event.Event
        ) -> None:
            """Handle the middle mouse drag event.

            Args:
                event (pygame.event.Event): The event to handle.
                trigger (pygame.event.Event): The triggering event.

            Returns:
                None

            """
            self.game.on_middle_mouse_drag_down_event(event, trigger)

            # if self.focus_locked:
            #     if self.current_focus:
            #         self.current_focus.on_middle_mouse_drag_event(event, trigger)
            #     elif self.previous_focus:
            #         self.previous_focus.on_middle_mouse_drag_event(event, trigger)

        def on_middle_mouse_drop_event(
            self: Self, event: pygame.event.Event, trigger: pygame.event.Event
        ) -> None:
            """Handle the middle mouse drop event.

            Args:
                event (pygame.event.Event): The event to handle.
                trigger (pygame.event.Event): The triggering event.

            Returns:
                None

            """
            self.game.on_middle_mouse_drag_up_event(event, trigger)

            # if self.focus_locked:
            #     if self.current_focus:
            #         self.current_focus.on_middle_mouse_drop_event(event, trigger)
            #     elif self.previous_focus:
            #         self.previous_focus.on_middle_mouse_drop_event(event, trigger)

        def on_right_mouse_drag_event(
            self: Self, event: pygame.event.Event, trigger: pygame.event.Event
        ) -> None:
            """Handle the right mouse drag event.

            Args:
                event (pygame.event.Event): The event to handle.
                trigger (pygame.event.Event): The triggering event.

            Returns:
                None

            """
            self.game.on_right_mouse_drag_down_event(event, trigger)

            # if self.focus_locked:
            #     if self.current_focus:
            #         self.current_focus.on_right_mouse_drag_event(event, trigger)
            #     elif self.previous_focus:
            #         self.previous_focus.on_right_mouse_drag_event(event, trigger)

        def on_right_mouse_drop_event(
            self: Self, event: pygame.event.Event, trigger: pygame.event.Event
        ) -> None:
            """Handle the right mouse drop event.

            Args:
                event (pygame.event.Event): The event to handle.
                trigger (pygame.event.Event): The triggering event.

            Returns:
                None

            """
            self.game.on_right_mouse_drag_up_event(event, trigger)

            # if self.focus_locked:
            #     if self.current_focus:
            #         self.current_focus.on_right_mouse_drop_event(event, trigger)
            #     elif self.previous_focus:
            #         self.previous_focus.on_right_mouse_drop_event(event, trigger)

        def on_mouse_focus_event(
            self: Self, event: pygame.event.Event, entering_focus: object
        ) -> None:
            """Handle the mouse focus event.

            Args:
                event (pygame.event.Event): The event to handle.
                entering_focus (object): The object entering focus.

            Returns:
                None

            """
            # Send a leave focus event for the old focus.
            # if not self.focus_locked:
            self.on_mouse_unfocus_event(event, self.current_focus)

            # We've entered a new object.
            self.current_focus = entering_focus

            # Send an enter event for the new focus.
            entering_focus.on_mouse_focus_event(event, self.current_focus)

            self.log.info(f"Entered Focus: {self.current_focus}")
            # else:
            #     self.log.info(f'Focus Locked: {self.previous_focus}')

        def on_mouse_unfocus_event(
            self: Self, event: pygame.event.Event, leaving_focus: object
        ) -> None:
            """Handle the mouse unfocus event.

            Args:
                event (pygame.event.Event): The event to handle.
                leaving_focus (object): The object leaving focus.

            Returns:
                None

            """
            self.previous_focus = leaving_focus

            if leaving_focus:
                leaving_focus.on_mouse_unfocus_event(event)
                self.current_focus = None

                self.log.info(f"Left Focus: {self.previous_focus}")

        def on_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the mouse button up event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

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
                # The mouse up location is also the trigger.
                self.mouse_dragging = False
                self.game.on_mouse_drop_event(event=event, trigger=event)

            # Whatever was locked gets unlocked.
            # self.focus_locked = False

        def on_left_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the left mouse button up event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_left_mouse_button_up_event(event)

        def on_middle_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the middle mouse button up event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_middle_mouse_button_up_event(event)

        def on_right_mouse_button_up_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the right mouse button up event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_right_mouse_button_up_event(event)

        def on_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the mouse button down event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.mouse_state[event.button] = event

            # Whatever was clicked on gets lock.
            # if self.current_focus:
            #     # TODO: Fix - Disabling for debugging.
            #     self.focus_locked = False

            if event.button == MOUSE_BUTTON_LEFT:
                self.on_left_mouse_button_down_event(event)
            if event.button == MOUSE_BUTTON_WHEEL:
                self.on_middle_mouse_button_down_event(event)
            if event.button == MOUSE_BUTTON_RIGHT:
                self.on_right_mouse_button_down_event(event)
            if event.button == MOUSE_WHEEL_SCROLL_UP:
                self.on_mouse_scroll_down_event(event)
            if event.button == MOUSE_WHEEL_SCROLL_DOWN:
                self.on_mouse_scroll_up_event(event)

            self.game.on_mouse_button_down_event(event)

        def on_left_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the left mouse button down event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_left_mouse_button_down_event(event)

        def on_middle_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the middle mouse button down event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_middle_mouse_button_down_event(event)

        def on_right_mouse_button_down_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the right mouse button down event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_right_mouse_button_down_event(event)

        def on_mouse_scroll_down_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the mouse scroll down event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_mouse_scroll_down_event(event)

        def on_mouse_scroll_up_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the mouse scroll up event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_mouse_scroll_up_event(event)

        def on_mouse_wheel_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the mouse wheel event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_mouse_wheel_event(event)

    def __init__(self: Self, game: object = None) -> None:
        """Initialize the mouse manager.

        Args:
            game (object): The game instance.

        Returns:
            None

        """
        super().__init__(game=game)
        self.proxies = [MouseManager.MouseProxy(game=game)]

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add arguments to the argument parser.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            None

        """
        group = parser.add_argument_group("Mouse Options")  # noqa: F841

        return parser


# TODO: Make this a singleton.
# We're making this a singleton class becasue
# pygame doesn't understand multiple cursors
# and so there is only ever 1 x/y coordinate sprite
# for the mouse at any given time.
class MousePointer:
    """Mouse pointer sprite."""

    def __init__(self: Self, pos: tuple, size: tuple = (1, 1)) -> None:
        """Initialize the mouse pointer sprite.

        Args:
            pos (tuple): The position of the mouse pointer.
            size (tuple): The size of the mouse pointer.

        Returns:
            None

        """
        super().__init__()

        self.pos = pos
        self.size = size
        self.rect = pygame.Rect(self.pos, self.size)

    @property
    def x(self: Self) -> int:
        """Get the x coordinate of the mouse pointer.

        Returns:
            int

        """
        return self.pos[0]

    @x.setter
    def x(self: Self, new_x: int) -> None:
        """Set the x coordinate of the mouse pointer.

        Args:
            new_x (int): The new x coordinate.

        Returns:
            None

        """
        self.pos[0] = new_x

    @property
    def y(self: Self) -> int:
        """Get the y coordinate of the mouse pointer.

        Returns:
            int

        """
        return self.pos[1]

    @y.setter
    def y(self: Self, new_y: int) -> None:
        """Set the y coordinate of the mouse pointer.

        Args:
            new_y (int): The new y coordinate.

        Returns:
            None

        """
        self.pos[1] = new_y


def collided_sprites(scene: object, event: pygame.event.Event, index: int | None = None) -> list:
    """Get the list of collided sprites.

    Args:
        scene (object): The scene to check.
        event (pygame.event.Event): The event to check.
        index (int): The index of the sprite to return.

    Returns:
        list: The list of collided sprites.

    """
    mouse = MousePointer(pos=event.pos)

    sprites = pygame.sprite.spritecollide(sprite=mouse, group=scene.all_sprites, dokill=False)

    if sprites:
        if index is None:
            return sprites

        return [sprites[index]]

    return []
