#!/usr/bin/env python3
"""Controller Events.

This is a simple controller event class that can be used to handle controller events.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

if TYPE_CHECKING:
    import argparse

import pygame
import pygame._sdl2.controller

from glitchygames.events import CONTROLLER_EVENTS, ControllerEvents, HashableEvent, ResourceManager

# Pygame has a bug where _sdl2 isn't visible in certain contexts
pygame.controller = pygame._sdl2.controller  # type: ignore[attr-defined] # ty: ignore[unresolved-attribute]

LOG: logging.Logger = logging.getLogger('game.controllers')
LOG.addHandler(logging.NullHandler())


class ControllerEventManager(ControllerEvents, ResourceManager):
    """Manage controller events."""

    log: ClassVar[logging.Logger] = LOG

    class ControllerEventProxy(ControllerEvents, ResourceManager):
        """Proxy class for controller events."""

        log: ClassVar[logging.Logger] = LOG

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

            """
            super().__init__(game)

            self._id = controller_id
            self.controller = pygame._sdl2.controller.Controller(self._id)
            self.controller.init()
            self._name: Any = pygame._sdl2.controller.name_forindex(self._id)  # type: ignore[attr-defined] # ty: ignore[unresolved-attribute]
            self._init = self.controller.get_init()
            self._attached = self.controller.attached()

            self._numaxes = len(self.AXIS)
            # Start with hardcoded button count, but allow dynamic growth
            self._numbuttons = len(self.BUTTONS)
            self._mapping = self.controller.get_mapping()

            # Initialize button state.
            self._axes = [self.controller.get_axis(i) for i in range(self._numaxes)]

            self._buttons = [self.controller.get_button(i) for i in range(self._numbuttons)]

            self.game: Any = game
            self.proxies = [self.game, self.controller]

        @override
        def on_controller_axis_motion_event(self: Self, event: HashableEvent) -> None:
            """Handle controller axis motion events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            self._axes[event.axis] = event.value
            self.game.on_controller_axis_motion_event(event)

        @override
        def on_controller_button_down_event(self: Self, event: HashableEvent) -> None:
            """Handle controller button down events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            self.log.debug('CONTROLLERBUTTONDOWN triggered: %s', event)
            # Ensure storage accommodates this button index
            if event.button < 0:
                return
            if event.button >= len(self._buttons):
                self._buttons.extend([False] * (event.button + 1 - len(self._buttons)))
            self._buttons[event.button] = True
            self.game.on_controller_button_down_event(event)

        @override
        def on_controller_button_up_event(self: Self, event: HashableEvent) -> None:
            """Handle controller button up events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            self.log.debug('CONTROLLERBUTTONUP triggered: %s', event)
            if event.button < 0:
                return
            if event.button >= len(self._buttons):
                self._buttons.extend([False] * (event.button + 1 - len(self._buttons)))
            self._buttons[event.button] = False
            self.game.on_controller_button_up_event(event)

        @override
        def on_controller_device_added_event(self: Self, event: HashableEvent) -> None:
            """Handle controller device added events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            # CONTROLLERDEVICEADDED device_index, guid
            self.game.on_controller_device_added_event(event)

        @override
        def on_controller_device_remapped_event(self: Self, event: HashableEvent) -> None:
            """Handle controller device remapped events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            self.game.on_controller_device_remapped_event(event)

        @override
        def on_controller_device_removed_event(self: Self, event: HashableEvent) -> None:
            """Handle controller device removed events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            # CONTROLLERDEVICEREMOVED instance_id
            self.game.on_controller_device_removed_event(event)

        @override
        def on_controller_touchpad_down_event(self: Self, event: HashableEvent) -> None:
            """Handle controller touchpad down events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            self.game.on_controller_touchpad_down_event(event)

        @override
        def on_controller_touchpad_motion_event(self: Self, event: HashableEvent) -> None:
            """Handle controller touchpad motion events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            self.game.on_controller_touchpad_motion_event(event)

        @override
        def on_controller_touchpad_up_event(self: Self, event: HashableEvent) -> None:
            """Handle controller touchpad up events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            self.game.on_controller_touchpad_up_event(event)

        @override
        def __str__(self: Self) -> str:
            """Return a string representation of the controller.

            Returns:
                str: A string representation of the controller.

            """
            controller_info = [
                f'Controller Name: {pygame._sdl2.controller.name_forindex(self._id)}',  # type: ignore[attr-defined] # ty: ignore[unresolved-attribute]
                f'\tController Id: {self._id}',
                f'\tController Inited: {self.controller.get_init()}',
                f'\tController Axis Count: {self._numaxes}',
                f'\tController Button Count: {self._numbuttons}',
            ]

            return '\n'.join(controller_info)

        @override
        def __repr__(self: Self) -> str:
            """Return a string representation of the controller object.

            Returns:
                str: A string representation of the controller object.

            """
            return repr(self.controller)

    def __init__(self: Self, game: object = None) -> None:
        """Initialize the ControllerEventManager.

        Args:
            game (object): The game object.

        """
        super().__init__(game=game)
        # Ensure controller events are enabled
        try:
            pygame.event.set_allowed(CONTROLLER_EVENTS)
        except pygame.error:
            LOG.debug('Failed to set allowed controller events: pygame not fully initialized')
        self.controllers: dict[int, Any] = {}
        self.proxies: list[Any] = []
        self.game: Any = game

        # This must be called before other controller methods,
        # and is safe to call more than once.
        pygame._sdl2.controller.init()

        self.log.debug(f'Controller Module Inited: {pygame._sdl2.controller.get_init()}')

        self.log.info(f'Enumerating {pygame._sdl2.controller.get_count()} controllers.')

        for controller_id in range(pygame._sdl2.controller.get_count()):
            if not pygame._sdl2.controller.is_controller(controller_id):
                self.log.warning('Controller #%s is not a controller.', controller_id)
                continue

            self.log.info(
                f'Controller #{controller_id}: '
                f'{pygame._sdl2.controller.name_forindex(controller_id)}',  # type: ignore[attr-defined] # ty: ignore[unresolved-attribute]
            )

            controller_proxy = ControllerEventManager.ControllerEventProxy(
                controller_id=controller_id,
                game=game,
            )
            self.controllers[controller_id] = controller_proxy

            # The controller proxy overrides the controller object
            self.log.info('Added Controller: %s', controller_proxy)

        self.proxies = [self.game]

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add controller options to the parser.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            argparse.ArgumentParser: The argument parser.

        """
        group = parser.add_argument_group('Controller Options')

        group.add_argument(
            '--input-mode',
            choices=['joystick', 'controller'],
            default='controller',
            help='Choose input event family to use (default: controller)',
        )

        return parser

    @override
    def on_controller_axis_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle controller axis motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.debug('CONTROLLERAXISMOTION triggered: on_controller_axis_motion_event(%s)', event)
        self.controllers[event.instance_id].on_controller_axis_motion_event(event)

    @override
    def on_controller_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle controller button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.debug(
            'CONTROLLERBUTTONDOWNEVENT triggered: on_controller_button_down_event(%s)',
            event,
        )
        self.controllers[event.instance_id].on_controller_button_down_event(event)

    @override
    def on_controller_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle controller button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.debug(
            'CONTROLLERBUTTONUPEVENT triggered: on_controller_button_up_event(%s)',
            event,
        )
        self.controllers[event.instance_id].on_controller_button_up_event(event)

    @override
    def on_controller_device_added_event(self: Self, event: HashableEvent) -> None:
        """Handle controller device added events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # CONTROLLERDEVICEADDED device_index, guid

        # Note: There is a bug in pygame where a reinitialized
        # controller object due to hotplug ends up with an incorrect
        # device_index.
        controller_proxy = ControllerEventManager.ControllerEventProxy(
            controller_id=event.device_index,
            game=self.game,
        )
        self.controllers[event.device_index] = controller_proxy

        # The controller proxy overrides the controller object
        self.log.debug(f'Added Controller #{event.device_index}: {controller_proxy}')
        self.log.debug(
            'CONTROLLERDEVICEADDED triggered: on_controller_device_added_event(%s)',
            event,
        )

        # Need to notify the game after the controller exists
        self.controllers[event.device_index].on_controller_device_added_event(event)

    @override
    def on_controller_device_remapped_event(self: Self, event: HashableEvent) -> None:
        """Handle controller device remapped events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.debug(
            'CONTROLLERDEVICEREMAPPED triggered: on_controller_device_remapped_event(%s',
            event,
        )
        self.controllers[event.device_index].on_controller_device_remapped_event(event)

    @override
    def on_controller_device_removed_event(self: Self, event: HashableEvent) -> None:
        """Handle controller device removed events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # CONTROLLERDEVICEREMOVED instance_id
        if event.instance_id in self.controllers:
            self.controllers[event.instance_id].on_controller_device_removed_event(event)
            del self.controllers[event.instance_id]
            self.log.debug(f'Removed Controller #{event.instance_id}')
            self.log.debug(
                'CONTROLLERDEVICEREMOVED triggered: on_controller_device_removed(%s)',
                event,
            )

    @override
    def on_controller_touchpad_down_event(self: Self, event: HashableEvent) -> None:
        """Handle controller touchpad down events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.debug(
            'CONTROLLERTOUCHDPADDOWN triggered: on_controller_touchpad_down_event(%s)',
            event,
        )
        self.controllers[event.instance_id].on_controller_touchpad_down_event(event)

    @override
    def on_controller_touchpad_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle controller touchpad motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.debug(
            'CONTROLLERTOUCHPADMOTION triggered: on_controller_touchpad_motion_event(%s)',
            event,
        )
        self.controllers[event.instance_id].on_controller_touchpad_motion_event(event)

    @override
    def on_controller_touchpad_up_event(self: Self, event: HashableEvent) -> None:
        """Handle controller touchpad up events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.debug('CONTROLLERTOUCHPADUP triggered: on_controller_touchpad_up_event(%s)', event)
        self.controllers[event.instance_id].on_controller_touchpad_up_event(event)
