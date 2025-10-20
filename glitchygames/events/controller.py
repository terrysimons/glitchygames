#!/usr/bin/env python3
"""Controller Events.

This is a simple controller event class that can be used to handle controller events.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar, LiteralString, Self

if TYPE_CHECKING:
    import argparse

import pygame
import pygame._sdl2.controller
from glitchygames.events import ControllerEvents, ResourceManager

# Pygame has a bug where _sdl2 isn't visible in certain contexts
pygame.controller = pygame._sdl2.controller

LOG: logging.Logger = logging.getLogger("game.controllers")
LOG.addHandler(logging.NullHandler())


class ControllerManager(ControllerEvents, ResourceManager):
    """Manage controller events."""

    log: logging.Logger = LOG

    class ControllerProxy(ControllerEvents, ResourceManager):
        """Proxy class for controller events."""

        log: logging.Logger = LOG

        AXIS: ClassVar = [
            pygame.CONTROLLER_AXIS_LEFTX,
            pygame.CONTROLLER_AXIS_LEFTY,
            pygame.CONTROLLER_AXIS_RIGHTX,
            pygame.CONTROLLER_AXIS_RIGHTY,
            pygame.CONTROLLER_AXIS_TRIGGERLEFT,
            pygame.CONTROLLER_AXIS_TRIGGERRIGHT,
        ]

        BUTTONS: ClassVar = [
            pygame.CONTROLLER_BUTTON_A,
            pygame.CONTROLLER_BUTTON_B,
            pygame.CONTROLLER_BUTTON_X,
            pygame.CONTROLLER_BUTTON_Y,
            pygame.CONTROLLER_BUTTON_DPAD_UP,
            pygame.CONTROLLER_BUTTON_DPAD_DOWN,
            pygame.CONTROLLER_BUTTON_DPAD_LEFT,
            pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
            pygame.CONTROLLER_BUTTON_LEFTSHOULDER,
            pygame.CONTROLLER_BUTTON_RIGHTSHOULDER,
            pygame.CONTROLLER_BUTTON_LEFTSTICK,
            pygame.CONTROLLER_BUTTON_RIGHTSTICK,
            pygame.CONTROLLER_BUTTON_BACK,
            pygame.CONTROLLER_BUTTON_GUIDE,
            pygame.CONTROLLER_BUTTON_START,
        ]

        def __init__(self: Self, game: object = None, controller_id: int = -1) -> None:
            """Initialize the controller proxy.

            Args:
                game (object): The game object.
                controller_id (int): The controller id.

            Returns:
                None

            """
            super().__init__(game)

            self._id = controller_id
            self.controller = pygame._sdl2.controller.Controller(self._id)
            self.controller.init()
            self._name = pygame._sdl2.controller.name_forindex(self._id)
            self._init = self.controller.get_init()
            self._attached = self.controller.attached()

            self._numaxes = len(self.AXIS)
            # Start with hardcoded button count, but allow dynamic growth
            self._numbuttons = len(self.BUTTONS)
            self._mapping = self.controller.get_mapping()

            # Initialize button state.
            self._axes = [self.controller.get_axis(i) for i in range(self._numaxes)]

            self._buttons = [self.controller.get_button(i) for i in range(self._numbuttons)]

            self.game = game
            self.proxies = [self.game, self.controller]

        def on_controller_axis_motion_event(self: Self, event: pygame.event.Event) -> None:
            """Handle controller axis motion events.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self._axes[event.axis] = event.value
            self.game.on_controller_axis_motion_event(event)

        def on_controller_button_down_event(self: Self, event: pygame.event.Event) -> None:
            """Handle controller button down events.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.log.debug(f"CONTROLLERBUTTONDOWN triggered: {event}")
            # Ensure storage accommodates this button index
            if event.button < 0:
                return
            if event.button >= len(self._buttons):
                self._buttons.extend([0] * (event.button + 1 - len(self._buttons)))
            self._buttons[event.button] = 1
            self.game.on_controller_button_down_event(event)

        def on_controller_button_up_event(self: Self, event: pygame.event.Event) -> None:
            """Handle controller button up events.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.log.debug(f"CONTROLLERBUTTONUP triggered: {event}")
            if event.button < 0:
                return
            if event.button >= len(self._buttons):
                self._buttons.extend([0] * (event.button + 1 - len(self._buttons)))
            self._buttons[event.button] = 0
            self.game.on_controller_button_up_event(event)

        def on_controller_device_added_event(self: Self, event: pygame.event.Event) -> None:
            """Handle controller device added events.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            # CONTROLLERDEVICEADDED device_index, guid
            self.game.on_controller_device_added_event(event)

        def on_controller_device_remapped_event(self: Self, event: pygame.event.Event) -> None:
            """Handle controller device remapped events.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_controller_device_remapped_event(event)

        def on_controller_device_removed_event(self: Self, event: pygame.event.Event) -> None:
            """Handle controller device removed events.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            # CONTROLLERDEVICEREMOVED instance_id
            self.game.on_controller_device_removed_event(event)

        def on_controller_touchpad_down_event(self: Self, event: pygame.event.Event) -> None:
            """Handle controller touchpad down events.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_controller_touchpad_down_event(event)

        def on_controller_touchpad_motion_event(self: Self, event: pygame.event.Event) -> None:
            """Handle controller touchpad motion events.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_controller_touchpad_motion_event(event)

        def on_controller_touchpad_up_event(self: Self, event: pygame.event.Event) -> None:
            """Handle controller touchpad up events.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_controller_touchpad_up_event(event)

        def __str__(self: Self) -> LiteralString:
            """Return a string representation of the controller.

            Returns:
                str: A string representation of the controller.

            """
            controller_info = [
                f"Controller Name: {pygame._sdl2.controller.name_forindex(self._id)}",
                f"\tController Id: {self._id}",
                f"\tController Inited: {self.controller.get_init()}",
                f"\tController Axis Count: {self._numaxes}",
                f"\tController Button Count: {self._numbuttons}",
            ]

            return "\n".join(controller_info)

        def __repr__(self: Self) -> str:
            """Return a string representation of the controller object.

            Returns:
                str: A string representation of the controller object.

            """
            return repr(self.controller)

    def __init__(self: Self, game: object = None) -> None:
        """Initialize the ControllerManager.

        Args:
            game (object): The game object.

        Returns:
            None

        """
        super().__init__(game=game)
        self.controllers = {}
        self.proxies = []
        self.game = game

        # This must be called before other controller methods,
        # and is safe to call more than once.
        pygame._sdl2.controller.init()

        self.log.debug(f"Controller Module Inited: {pygame._sdl2.controller.get_init()}")

        self.log.info(f"Enumerating {pygame._sdl2.controller.get_count()} controllers.")

        for controller_id in range(pygame._sdl2.controller.get_count()):
            if not pygame._sdl2.controller.is_controller(controller_id):
                self.log.warning(f"Controller #{controller_id} is not a controller.")
                continue

            self.log.info(
                f"Controller #{controller_id}: "
                f"{pygame._sdl2.controller.name_forindex(controller_id)}"
            )

            controller_proxy = ControllerManager.ControllerProxy(
                controller_id=controller_id, game=game
            )
            self.controllers[controller_id] = controller_proxy

            # The controller proxy overrides the controller object
            self.log.info(f"Added Controller: {controller_proxy}")

        self.proxies = [self.game]

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add controller options to the parser.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            argparse.ArgumentParser: The argument parser.

        """
        group = parser.add_argument_group("Controller Options")  # noqa: F841

        return parser

    def on_controller_axis_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller axis motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        self.log.debug(f"CONTROLLERAXISMOTION triggered: on_controller_axis_motion_event({event})")
        self.controllers[event.instance_id].on_controller_axis_motion_event(event)

    def on_controller_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        self.log.debug(
            f"CONTROLLERBUTTONDOWNEVENT triggered: on_controller_button_down_event({event})"
        )
        self.controllers[event.instance_id].on_controller_button_down_event(event)

    def on_controller_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        self.log.debug(f"CONTROLLERBUTTONUPEVENT triggered: on_controller_button_up_event({event})")
        self.controllers[event.instance_id].on_controller_button_up_event(event)

    def on_controller_device_added_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller device added events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # CONTROLLERDEVICEADDED device_index, guid

        # Note: There is a bug in pygame where a reinitialized
        # controller object due to hotplug ends up with an incorrect
        # device_index.
        controller_proxy = ControllerManager.ControllerProxy(
            controller_id=event.device_index, game=self.game
        )
        self.controllers[event.device_index] = controller_proxy

        # The controller proxy overrides the controller object
        self.log.debug(f"Added Controller #{event.device_index}: {controller_proxy}")
        self.log.debug(
            f"CONTROLLERDEVICEADDED triggered: on_controller_device_added_event({event})"
        )

        # Need to notify the game after the controller exists
        self.controllers[event.device_index].on_controller_device_added_event(event)

    def on_controller_device_remapped_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller device remapped events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        self.log.debug(
            f"CONTROLLERDEVICEREMAPPED triggered: on_controller_device_remapped_event({event}"
        )
        self.controllers[event.device_index].on_controller_device_remapped_event(event)

    def on_controller_device_removed_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller device removed events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # CONTROLLERDEVICEREMOVED instance_id
        self.controllers[event.instance_id].on_controller_device_removed_event(event)
        del self.controllers[event.instance_id]
        self.log.debug(f"Removed Controller #{event.instance_id}")
        self.log.debug(f"CONTROLLERDEVICEREMOVED triggered: on_controller_device_removed({event})")

    def on_controller_touchpad_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller touchpad down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        self.log.debug(
            f"CONTROLLERTOUCHDPADDOWN triggered: on_controller_touchpad_down_event({event})"
        )
        self.controllers[event.instance_id].on_controller_touchpad_down_event(event)

    def on_controller_touchpad_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller touchpad motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        self.log.debug(
            f"CONTROLLERTOUCHPADMOTION triggered: on_controller_touchpad_motion_event({event})"
        )
        self.controllers[event.instance_id].on_controller_touchpad_motion_event(event)

    def on_controller_touchpad_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle controller touchpad up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        self.log.debug(f"CONTROLLERTOUCHPADUP triggered: on_controller_touchpad_up_event({event})")
        self.controllers[event.instance_id].on_controller_touchpad_up_event(event)
