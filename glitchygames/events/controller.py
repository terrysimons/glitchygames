#!/usr/bin/env python3
"""Controller Events.

This is a simple controller event class that can be used to handle controller events.
"""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

if TYPE_CHECKING:
    import argparse

    from glitchygames.input.devices import OpenedController

import pygame

from glitchygames.events import (
    CONTROLLER_EVENTS,
    ControllerAxisEvent,
    ControllerButtonEvent,
    ControllerDeviceAddedEvent,
    ControllerDeviceEvent,
    ControllerEvents,
    ControllerTouchpadEvent,
    HashableEvent,
    ResourceManager,
)
from glitchygames.input.devices import sdl_controller_module
from glitchygames.input.state import current_input
from glitchygames.sources import active_sources


def alias_controller_module() -> bool:
    """Expose pygame._sdl2.controller as pygame.controller, where this pygame build has it.

    Pygame has a bug where _sdl2 isn't visible in certain contexts. Stock Pyodide's pygame-ce
    has no controller module at all (input/devices.py ``sdl_controller_module``).

    Returns:
        True when the alias was set.

    """
    controller_module = sdl_controller_module()
    if controller_module is None:
        return False
    pygame.controller = controller_module  # type: ignore[attr-defined] # ty: ignore[unresolved-attribute]
    return True


alias_controller_module()

LOG: logging.Logger = logging.getLogger('game.controllers')
LOG.addHandler(logging.NullHandler())


class ControllerEventManager(ControllerEvents, ResourceManager):
    """Manage controller events."""

    log: ClassVar[logging.Logger] = LOG

    class ControllerEventProxy(ControllerEvents, ResourceManager):
        """Proxy class for controller events."""

        # A proxy belongs to its manager: each construction is a new one (ResourceManager)
        SHARES_INSTANCE: ClassVar[bool] = False

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
            # Devices are opened only through the devices door (glitchygames/input/devices.py)
            self.controller: OpenedController = (
                active_sources().devices().open_controller(device_index=self._id)
            )
            # The snapshot (glitchygames/input/state.py) keys positions by instance id, and the
            # manager keys its controllers by it (the id every controller event carries)
            self._instance_id: int = int(self.controller.as_joystick().get_instance_id())
            self.controller.init()
            self._name: str = self.controller.name
            self._init = self.controller.get_init()
            self._attached = self.controller.attached()

            self._numaxes = len(self.AXIS)
            # Start with hardcoded button count, but allow dynamic growth
            self._numbuttons = len(self.BUTTONS)
            self._mapping = self.controller.get_mapping()

            # Initialize button state from the frame's input snapshot (the controller layer, by
            # CONTROLLER_AXIS_* / CONTROLLER_BUTTON_* id), never from the device mid-frame, so
            # live play and a replay start from the same positions.
            # A hot-plugged controller is not in this frame's snapshot (it was opened after the
            # pump), so its caches start zeroed: intended (snapshot-only reads), do not read
            # the device instead.
            snapshot = current_input()
            self._axes = [
                snapshot.controller_axis(device_id=self._instance_id, axis=axis)
                for axis in range(self._numaxes)
            ]

            self._buttons = [
                snapshot.controller_button(device_id=self._instance_id, button=button)
                for button in range(self._numbuttons)
            ]

            self.game: Any = game
            self.proxies = [self.game, self.controller]

        @property
        def instance_id(self: Self) -> int:
            """The SDL instance id every event of this controller carries."""
            return self._instance_id

        @property
        def device_index(self: Self) -> int:
            """The SDL device index the controller was opened at."""
            return self._id

        @override
        def on_controller_axis_motion_event(self: Self, event: ControllerAxisEvent) -> None:
            """Handle controller axis motion events.

            Args:
                event (ControllerAxisEvent): The event to handle.

            """
            self._axes[event.axis] = event.value
            self.game.on_controller_axis_motion_event(event)

        @override
        def on_controller_button_down_event(self: Self, event: ControllerButtonEvent) -> None:
            """Handle controller button down events.

            Args:
                event (ControllerButtonEvent): The event to handle.

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
        def on_controller_button_up_event(self: Self, event: ControllerButtonEvent) -> None:
            """Handle controller button up events.

            Args:
                event (ControllerButtonEvent): The event to handle.

            """
            self.log.debug('CONTROLLERBUTTONUP triggered: %s', event)
            if event.button < 0:
                return
            if event.button >= len(self._buttons):
                self._buttons.extend([False] * (event.button + 1 - len(self._buttons)))
            self._buttons[event.button] = False
            self.game.on_controller_button_up_event(event)

        @override
        def on_controller_device_added_event(self: Self, event: ControllerDeviceAddedEvent) -> None:
            """Handle controller device added events.

            Args:
                event (ControllerDeviceAddedEvent): The event to handle.

            """
            # CONTROLLERDEVICEADDED device_index, guid
            self.game.on_controller_device_added_event(event)

        @override
        def on_controller_device_remapped_event(self: Self, event: ControllerDeviceEvent) -> None:
            """Handle controller device remapped events.

            Args:
                event (ControllerDeviceEvent): The event to handle.

            """
            self.game.on_controller_device_remapped_event(event)

        @override
        def on_controller_device_removed_event(self: Self, event: ControllerDeviceEvent) -> None:
            """Handle controller device removed events.

            Args:
                event (ControllerDeviceEvent): The event to handle.

            """
            # CONTROLLERDEVICEREMOVED instance_id
            self.game.on_controller_device_removed_event(event)

        @override
        def on_controller_touchpad_down_event(self: Self, event: ControllerTouchpadEvent) -> None:
            """Handle controller touchpad down events.

            Args:
                event (ControllerTouchpadEvent): The event to handle.

            """
            self.game.on_controller_touchpad_down_event(event)

        @override
        def on_controller_touchpad_motion_event(self: Self, event: ControllerTouchpadEvent) -> None:
            """Handle controller touchpad motion events.

            Args:
                event (ControllerTouchpadEvent): The event to handle.

            """
            self.game.on_controller_touchpad_motion_event(event)

        @override
        def on_controller_touchpad_up_event(self: Self, event: ControllerTouchpadEvent) -> None:
            """Handle controller touchpad up events.

            Args:
                event (ControllerTouchpadEvent): The event to handle.

            """
            self.game.on_controller_touchpad_up_event(event)

        @override
        def on_controller_sensor_update_event(self: Self, event: HashableEvent) -> None:
            """Handle controller sensor update events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            self.game.on_controller_sensor_update_event(event)

        def rumble(
            self: Self,
            low_frequency: float = 0.0,
            high_frequency: float = 0.0,
            duration: int = 0,
        ) -> bool:
            """Trigger haptic rumble on this controller.

            Args:
                low_frequency: Low-frequency motor intensity (0.0 to 1.0).
                high_frequency: High-frequency motor intensity (0.0 to 1.0).
                duration: Duration in milliseconds (0 = infinite).

            Returns:
                True if rumble is supported and was started.

            """
            try:
                return bool(self.controller.rumble(low_frequency, high_frequency, duration))
            except pygame.error, AttributeError:
                return False

        def stop_rumble(self: Self) -> None:
            """Stop any active rumble on this controller."""
            with contextlib.suppress(pygame.error, AttributeError):
                self.controller.stop_rumble()

        def set_led(self: Self, red: int, green: int, blue: int) -> bool:
            """Set the controller's LED color (DualSense, DualShock 4).

            Args:
                red: Red intensity (0-255).
                green: Green intensity (0-255).
                blue: Blue intensity (0-255).

            Returns:
                True if LED color was set successfully.

            """
            try:
                return bool(self.controller.set_led((red, green, blue)))
            except pygame.error, AttributeError:
                return False

        @override
        def __str__(self: Self) -> str:
            """Return a string representation of the controller.

            Returns:
                str: A string representation of the controller.

            """
            controller_info = [
                f'Controller Name: {self._name}',
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
        # By instance id: the id every controller event carries (a device index is only valid
        # until a device is plugged in or out; BUGS.md #181)
        self.controllers: dict[int, ControllerEventManager.ControllerEventProxy] = {}
        self.proxies: list[Any] = []
        self.game: Any = game

        # This must be called before other controller methods,
        # and is safe to call more than once. A pygame build without the controller module has
        # nothing to initialize: its devices door reports no controllers (input/devices.py)
        controller_module = sdl_controller_module()
        if controller_module is None:
            self.log.info('Controller Module unavailable in this pygame build: no controllers')
        else:
            controller_module.init()
            self.log.debug('Controller Module Inited: %s', controller_module.get_init())

        # Enumerated through the devices door (glitchygames/input/devices.py)
        devices = active_sources().devices()
        controller_count = devices.controller_count()
        self.log.info('Enumerating %s controllers.', controller_count)

        for controller_id in range(controller_count):
            if not devices.is_controller(device_index=controller_id):
                self.log.warning('Controller #%s is not a controller.', controller_id)
                continue

            controller_proxy = ControllerEventManager.ControllerEventProxy(
                controller_id=controller_id,
                game=game,
            )
            self.controllers[controller_proxy.instance_id] = controller_proxy

            self.log.info(
                'Controller #%d (instance %d): %s',
                controller_id,
                controller_proxy.instance_id,
                controller_proxy,
            )

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
            choices=['auto', 'joystick', 'controller'],
            default='auto',
            help=(
                'Which gamepads the game sees (default: auto, every device; a mapped pad sends'
                ' controller events, any other device joystick events; joystick: every device'
                ' sends joystick events; controller: mapped pads only)'
            ),
        )

        return parser

    @override
    def on_controller_axis_motion_event(self: Self, event: ControllerAxisEvent) -> None:
        """Handle controller axis motion events.

        Args:
            event (ControllerAxisEvent): The event to handle.

        """
        self.log.debug('CONTROLLERAXISMOTION triggered: on_controller_axis_motion_event(%s)', event)
        self.controllers[event.instance_id].on_controller_axis_motion_event(event)

    @override
    def on_controller_button_down_event(self: Self, event: ControllerButtonEvent) -> None:
        """Handle controller button down events.

        Args:
            event (ControllerButtonEvent): The event to handle.

        """
        self.log.debug(
            'CONTROLLERBUTTONDOWNEVENT triggered: on_controller_button_down_event(%s)',
            event,
        )
        self.controllers[event.instance_id].on_controller_button_down_event(event)

    @override
    def on_controller_button_up_event(self: Self, event: ControllerButtonEvent) -> None:
        """Handle controller button up events.

        Args:
            event (ControllerButtonEvent): The event to handle.

        """
        self.log.debug(
            'CONTROLLERBUTTONUPEVENT triggered: on_controller_button_up_event(%s)',
            event,
        )
        self.controllers[event.instance_id].on_controller_button_up_event(event)

    @override
    def on_controller_device_added_event(self: Self, event: ControllerDeviceAddedEvent) -> None:
        """Handle controller device added events.

        Args:
            event (ControllerDeviceAddedEvent): The event to handle.

        """
        # CONTROLLERDEVICEADDED device_index, guid

        # Note: There is a bug in pygame where a reinitialized
        # controller object due to hotplug ends up with an incorrect
        # device_index.
        # The event names the device index; every later event names the instance id, so the
        # controller is tracked by the instance id it opens with (BUGS.md #181)
        try:
            controller_proxy = ControllerEventManager.ControllerEventProxy(
                controller_id=event.device_index,
                game=self.game,
            )
        except pygame.error:
            # Unplugged again before it could be opened: there is nothing to track
            self.log.warning(
                'Controller at device index %s vanished before it could be opened',
                event.device_index,
                exc_info=True,
            )
            return
        tracked_proxy = self.controllers.get(controller_proxy.instance_id)
        if tracked_proxy is not None:
            # SDL reports a pad connected at startup twice: in the startup count (opened in
            # __init__) and as an added event on the first pump. Keep the proxy the game may
            # already have set state on; the second open shares SDL's reference-counted handle
            self.log.debug(
                'Controller instance %s is already tracked; keeping its proxy',
                controller_proxy.instance_id,
            )
            tracked_proxy.on_controller_device_added_event(event)
            return
        self.controllers[controller_proxy.instance_id] = controller_proxy

        # The controller proxy overrides the controller object
        self.log.debug(
            'Added Controller #%s (instance %s): %s',
            event.device_index,
            controller_proxy.instance_id,
            controller_proxy,
        )
        self.log.debug(
            'CONTROLLERDEVICEADDED triggered: on_controller_device_added_event(%s)',
            event,
        )

        # Need to notify the game after the controller exists
        controller_proxy.on_controller_device_added_event(event)

    @override
    def on_controller_device_remapped_event(self: Self, event: ControllerDeviceEvent) -> None:
        """Handle controller device remapped events.

        Args:
            event (ControllerDeviceEvent): The event to handle.

        """
        self.log.debug(
            'CONTROLLERDEVICEREMAPPED triggered: on_controller_device_remapped_event(%s)',
            event,
        )
        # A remapped event carries the instance id (pygame's event docs), not a device index
        if event.instance_id in self.controllers:
            self.controllers[event.instance_id].on_controller_device_remapped_event(event)

    @override
    def on_controller_device_removed_event(self: Self, event: ControllerDeviceEvent) -> None:
        """Handle controller device removed events.

        Args:
            event (ControllerDeviceEvent): The event to handle.

        """
        # CONTROLLERDEVICEREMOVED instance_id
        # The devices door stops polling it (tracked here or not)
        active_sources().devices().forget_device(instance_id=event.instance_id)
        if event.instance_id in self.controllers:
            self.controllers[event.instance_id].on_controller_device_removed_event(event)
            del self.controllers[event.instance_id]
            self.log.debug('Removed Controller #%s', event.instance_id)
            self.log.debug(
                'CONTROLLERDEVICEREMOVED triggered: on_controller_device_removed(%s)',
                event,
            )

    @override
    def on_controller_touchpad_down_event(self: Self, event: ControllerTouchpadEvent) -> None:
        """Handle controller touchpad down events.

        Args:
            event (ControllerTouchpadEvent): The event to handle.

        """
        self.log.debug(
            'CONTROLLERTOUCHDPADDOWN triggered: on_controller_touchpad_down_event(%s)',
            event,
        )
        self.controllers[event.instance_id].on_controller_touchpad_down_event(event)

    @override
    def on_controller_touchpad_motion_event(self: Self, event: ControllerTouchpadEvent) -> None:
        """Handle controller touchpad motion events.

        Args:
            event (ControllerTouchpadEvent): The event to handle.

        """
        self.log.debug(
            'CONTROLLERTOUCHPADMOTION triggered: on_controller_touchpad_motion_event(%s)',
            event,
        )
        self.controllers[event.instance_id].on_controller_touchpad_motion_event(event)

    @override
    def on_controller_touchpad_up_event(self: Self, event: ControllerTouchpadEvent) -> None:
        """Handle controller touchpad up events.

        Args:
            event (ControllerTouchpadEvent): The event to handle.

        """
        self.log.debug('CONTROLLERTOUCHPADUP triggered: on_controller_touchpad_up_event(%s)', event)
        self.controllers[event.instance_id].on_controller_touchpad_up_event(event)

    @override
    def on_controller_sensor_update_event(self: Self, event: HashableEvent) -> None:
        """Handle controller sensor update events (gyroscope, accelerometer).

        Args:
            event (pygame.event.Event): The event to handle.

        """
        self.log.debug(
            'CONTROLLERSENSORUPDATE triggered: on_controller_sensor_update_event(%s)',
            event,
        )
        if event.instance_id in self.controllers:
            self.controllers[event.instance_id].on_controller_sensor_update_event(event)

    # --- Output features (rumble, LED) ---
    # These are controller-only. Not available in joystick mode.
    # Speaker and microphone are not exposed by pygame-ce.

    def rumble(
        self: Self,
        instance_id: int,
        low_frequency: float = 0.0,
        high_frequency: float = 0.0,
        duration: int = 0,
    ) -> bool:
        """Trigger haptic rumble on a controller.

        Args:
            instance_id: The controller instance ID.
            low_frequency: Low-frequency motor intensity (0.0 to 1.0).
            high_frequency: High-frequency motor intensity (0.0 to 1.0).
            duration: Duration in milliseconds (0 = infinite).

        Returns:
            True if rumble was started.

        """
        proxy = self.controllers.get(instance_id)
        if proxy is None:
            return False
        return proxy.rumble(
            low_frequency=low_frequency,
            high_frequency=high_frequency,
            duration=duration,
        )

    def stop_rumble(self: Self, instance_id: int) -> None:
        """Stop rumble on a controller.

        Args:
            instance_id: The controller instance ID.

        """
        proxy = self.controllers.get(instance_id)
        if proxy is not None:
            proxy.stop_rumble()

    def set_led(self: Self, instance_id: int, red: int, green: int, blue: int) -> bool:
        """Set a controller's LED color.

        Only supported on DualSense and DualShock 4 controllers.

        Args:
            instance_id: The controller instance ID.
            red: Red intensity (0-255).
            green: Green intensity (0-255).
            blue: Blue intensity (0-255).

        Returns:
            True if the LED color was set.

        """
        proxy = self.controllers.get(instance_id)
        if proxy is None:
            return False
        return proxy.set_led(red=red, green=green, blue=blue)
