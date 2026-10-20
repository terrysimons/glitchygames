#!/usr/bin/env python3
"""Joystick Event Manager."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

if TYPE_CHECKING:
    import argparse

import pygame

from glitchygames.events import JOYSTICK_EVENTS, HashableEvent, JoystickEvents, ResourceManager
from glitchygames.input.state import current_input
from glitchygames.sources import active_sources

LOG = logging.getLogger('game.joysticks')
LOG.addHandler(logging.NullHandler())


class JoystickEventManager(JoystickEvents, ResourceManager):
    """Manage joystick events."""

    log: ClassVar[logging.Logger] = LOG
    # Interiting from object is default in Python 3.
    # Linters complain if you do it.
    #
    # This isn't a ResourceManager like other proxies, because
    # there can be multiple joysticks, so having one instance
    # won't work.

    class JoystickEventProxy(JoystickEvents):
        """Joystick event proxy."""

        log: ClassVar[logging.Logger] = LOG

        def __init__(
            self: Self,
            game: object = None,
            joystick_id: int = -1,
            instance_id: int | None = None,
        ) -> None:
            """Initialize the joystick event proxy.

            Args:
                game (object): The game object.
                joystick_id (int): The joystick id.
                instance_id (int | None): The instance id.

            """
            # Prefer stable instance_id when available
            self._id = instance_id if instance_id is not None else joystick_id
            # Store the device index for reference
            self._device_id = joystick_id
            # Devices are opened only through the devices door (glitchygames/input/devices.py);
            # a device it already opened for this instance id is reused, not opened again
            devices = active_sources().devices()
            opened = (
                None
                if instance_id is None
                else devices.joystick_for_instance(instance_id=instance_id)
            )
            self.joystick: Any = (
                opened if opened is not None else devices.open_joystick(device_index=joystick_id)
            )
            # The snapshot (glitchygames/input/state.py) keys positions by the opened device's
            # instance id
            self._instance_id: int = int(self.joystick.get_instance_id())
            self.joystick.init()
            self._init = self.joystick.get_init()
            self._name = self.joystick.get_name()

            try:
                self._guid = self.joystick.get_guid()
            except AttributeError:
                self._guid = None

            try:
                self._power_level = self.joystick.get_power_level()
            except AttributeError:
                self._power_level = None

            self._numaxes = self.joystick.get_numaxes()
            self._numballs = self.joystick.get_numballs()
            self._numbuttons = self.joystick.get_numbuttons()
            self._numhats = self.joystick.get_numhats()

            # Initialize button state from the frame's input snapshot, never from the device
            # mid-frame, so live play and a replay start from the same positions.
            # A hot-plugged device is not in this frame's snapshot (it was opened after the
            # pump), so its caches start zeroed: intended (snapshot-only reads), do not read
            # the device instead.
            snapshot = current_input()
            self._axes = [
                snapshot.axis(device_id=self._instance_id, axis=axis)
                for axis in range(self.get_numaxes())
            ]

            # Trackballs are not in the snapshot (they report relative motion): they start still
            self._balls = [(0, 0) for _ball in range(self.get_numballs())]

            self._buttons = [
                snapshot.button(device_id=self._instance_id, button=button)
                for button in range(self.get_numbuttons())
            ]

            self._hats = [
                snapshot.hat(device_id=self._instance_id, hat=hat)
                for hat in range(self.get_numhats())
            ]

            self.game: Any = game
            self.proxies: list[Any] = [self.game, self.joystick]

        # Define some high level APIs
        @override
        def on_joy_axis_motion_event(self: Self, event: HashableEvent) -> None:
            """Handle joystick axis motion events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            # JOYAXISMOTION    joy, axis, value
            self._axes[event.axis] = event.value
            self.game.on_joy_axis_motion_event(event)

        @override
        def on_joy_button_down_event(self: Self, event: HashableEvent) -> None:
            """Handle joystick button down events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            # JOYBUTTONDOWN    joy, button
            # Ensure storage accommodates this button index
            if event.button < 0:
                return
            if event.button >= len(self._buttons):
                self._buttons.extend([False] * (event.button + 1 - len(self._buttons)))
            self._buttons[event.button] = True
            self.game.on_joy_button_down_event(event)

        @override
        def on_joy_button_up_event(self: Self, event: HashableEvent) -> None:
            """Handle joystick button up events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            # JOYBUTTONUP      joy, button
            if event.button < 0:
                return
            if event.button >= len(self._buttons):
                self._buttons.extend([False] * (event.button + 1 - len(self._buttons)))
            self._buttons[event.button] = False
            self.game.on_joy_button_up_event(event)

        @override
        def on_joy_hat_motion_event(self: Self, event: HashableEvent) -> None:
            """Handle joystick hat motion events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            # JOYHATMOTION     joy, hat, value
            self._hats[event.hat] = event.value
            self.game.on_joy_hat_motion_event(event)

        @override
        def on_joy_ball_motion_event(self: Self, event: HashableEvent) -> None:
            """Handle joystick ball motion events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            # JOYBALLMOTION    joy, ball, rel
            self._balls[event.ball] = event.rel
            self.game.on_joy_ball_motion_event(event)

        @override
        def on_joy_device_added_event(self: Self, event: HashableEvent) -> None:
            """Handle joystick device added events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            # JOYDEVICEADDED device_index, guid
            self.game.on_joy_device_added_event(event)

        @override
        def on_joy_device_removed_event(self: Self, event: HashableEvent) -> None:
            """Handle joystick device removed events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            # JOYDEVICEREMOVED device_index
            self.game.on_joy_device_removed_event(event)

        # We can't make these properties, because then they
        # wouldn't be callable as functions.
        def get_name(self: Self) -> str:
            """Get the joystick name.

            Returns:
                str: The joystick name.

            """
            try:
                # Prefer live name from the underlying joystick to avoid stale cached values
                return self.joystick.get_name()
            except pygame.error:
                return self._name

        def get_init(self: Self) -> bool:
            """Get the joystick init status.

            Returns:
                bool: The joystick init status.

            """
            return self._init

        def get_numaxes(self: Self) -> int:
            """Get the number of axes.

            Returns:
                int: The number of axes.

            """
            return self._numaxes

        def get_numballs(self: Self) -> int:
            """Get the number of trackballs.

            Returns:
                int: The number of trackballs.

            """
            return self._numballs

        def get_numbuttons(self: Self) -> int:
            """Get the number of buttons.

            Returns:
                int: The number of buttons.

            """
            return self._numbuttons

        def get_numhats(self: Self) -> int:
            """Get the number of hats.

            Returns:
                int: The number of hats.

            """
            return self._numhats

        @override
        def __str__(self: Self) -> str:
            """Get the joystick info.

            Returns:
                str: The joystick info.

            """
            joystick_info = [
                f'Joystick Name: {self.get_name()}',
                f'\tJoystick Id: {self._device_id}',
                f'\tJoystick Inited: {self.get_init()}',
                f'\tJoystick Axis Count: {self.get_numaxes()}',
                f'\tJoystick Trackball Count: {self.get_numballs()}',
                f'\tJoystick Button Count: {self.get_numbuttons()}',
                f'\tJoystick Hat Count: {self.get_numhats()}',
            ]

            return '\n'.join(joystick_info)

        @override
        def __repr__(self: Self) -> str:
            """Get the joystick representation.

            Returns:
                str: The joystick representation.

            """
            return repr(self.joystick)

    def __init__(self: Self, game: object = None) -> None:
        """Initialize the joystick event manager.

        Args:
            game (object): The game object.

        """
        super().__init__(game=game)
        try:
            pygame.event.set_allowed(JOYSTICK_EVENTS)
        except pygame.error:
            LOG.debug('Failed to set allowed joystick events: pygame not fully initialized')
        self.joysticks: dict[int, Any] = {}
        self.game: Any = game

        # This must be called before other joystick methods,
        # and is safe to call more than once.
        pygame.joystick.init()

        self.log.info(f'Joystick Module Inited: {pygame.joystick.get_init()}')
        self.log.debug(f'JoystickEventManager init id(self)={id(self)}')

        # Joystick Setup, through the devices door (glitchygames/input/devices.py)
        devices = active_sources().devices()
        joystick_count = devices.joystick_count()
        self.log.info(f'Joystick Count: {joystick_count}')

        for pygame_joystick_index in range(joystick_count):
            try:
                joystick = devices.open_joystick(device_index=pygame_joystick_index)
            except pygame.error:
                # Unplugged between the count and the open; skip it, keep the others
                self.log.warning(
                    'Joystick %d vanished before it could be opened',
                    pygame_joystick_index,
                    exc_info=True,
                )
                continue
            joystick.init()

            # Deep debug: capture both index and instance identity at init time
            try:
                reported_device_id = joystick.get_id() if hasattr(joystick, 'get_id') else None
            except pygame.error:
                reported_device_id = None
            try:
                reported_instance_id = (
                    joystick.get_instance_id() if hasattr(joystick, 'get_instance_id') else None
                )
            except pygame.error:
                reported_instance_id = None
            try:
                reported_name = joystick.get_name() if hasattr(joystick, 'get_name') else None
            except pygame.error:
                reported_name = None
            try:
                reported_guid = joystick.get_guid() if hasattr(joystick, 'get_guid') else None
            except pygame.error:
                reported_guid = None
            self.log.debug(
                'INIT MAP index=%s get_id=%s instance_id=%s name=%s guid=%s',
                pygame_joystick_index,
                reported_device_id,
                reported_instance_id,
                reported_name,
                reported_guid,
            )

            # Use stable instance_id as the key when available
            try:
                instance_id = joystick.get_instance_id()
            except AttributeError:
                instance_id = pygame_joystick_index
            joystick_proxy = JoystickEventManager.JoystickEventProxy(
                joystick_id=pygame_joystick_index,
                instance_id=instance_id,
                game=self.game,
            )
            self.joysticks[instance_id] = joystick_proxy
            # The joystick proxy overrides the joystick object
            self.log.info('Added Joystick: %s', joystick_proxy)

        self.proxies = [self.game]

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add joystick-specific arguments to the global parser.

        This class method will get called automatically by the GameEngine class.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            argparse.ArgumentParser

        """
        _group = parser.add_argument_group('Joystick Options')

        return parser

    # Define some high level APIs
    #
    # Note that we can't pass these through the way
    # we do for other event types because
    # we need to know which joystick the event is intended for.
    @override
    def on_joy_axis_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick axis motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # JOYAXISMOTION    joy, axis, value
        try:
            joystick_id = event.instance_id
        except AttributeError:
            joystick_id = event.joy

        self.log.debug('JOYAXISMOTION triggered: on_joy_axis_motion_event(%s)', event)
        self.joysticks[joystick_id].on_joy_axis_motion_event(event)

    @override
    def on_joy_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # JOYBUTTONDOWN    joy, button
        try:
            joystick_id = event.instance_id
        except AttributeError:
            joystick_id = event.joy

        self.log.debug('JOYBUTTONDOWN triggered: on_joy_button_down_event(%s)', event)
        self.joysticks[joystick_id].on_joy_button_down_event(event)

    @override
    def on_joy_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # JOYBUTTONUP      joy, button
        try:
            joystick_id = event.instance_id
        except AttributeError:
            joystick_id = event.joy

        self.log.debug('JOYBUTTONUP triggered: on_joy_button_up_event(%s)', event)
        self.joysticks[joystick_id].on_joy_button_up_event(event)

    @override
    def on_joy_hat_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick hat motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # JOYHATMOTION     joy, hat, value
        try:
            joystick_id = event.instance_id
        except AttributeError:
            joystick_id = event.joy

        self.log.debug('JOYHATMOTION triggered: on_joy_hat_motion_event(%s)', event)
        self.joysticks[joystick_id].on_joy_hat_motion_event(event)

    @override
    def on_joy_ball_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick ball motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # JOYBALLMOTION    joy, ball, rel
        try:
            joystick_id = event.instance_id
        except AttributeError:
            joystick_id = event.joy

        self.log.debug('JOYBALLMOTION triggered: on_joy_ball_motion_event(%s)', event)
        self.joysticks[joystick_id].on_joy_ball_motion_event(event)

    def _log_joystick_debug_info(
        self: Self, added_device_index: int, *, joystick: Any | None
    ) -> None:
        """Log debug info for a newly added joystick device.

        Args:
            added_device_index: The device index of the added joystick.
            joystick: The joystick opened for it (None when it could not be opened).

        """
        if joystick is None:
            self.log.debug('DEVICEADDED could not open Joystick(%s)', added_device_index)
        else:
            try:
                joystick_name = joystick.get_name()
            except pygame.error:
                joystick_name = None
            try:
                joystick_guid = joystick.get_guid()
            except pygame.error:
                joystick_guid = None
            try:
                joystick_device_id = joystick.get_id()
            except pygame.error:
                joystick_device_id = None
            try:
                joystick_instance_id = joystick.get_instance_id()
            except pygame.error:
                joystick_instance_id = None
            self.log.debug(
                'DEVICEADDED index=%s get_id=%s instance_id=%s name=%s guid=%s',
                added_device_index,
                joystick_device_id,
                joystick_instance_id,
                joystick_name,
                joystick_guid,
            )

    def _resolve_instance_id(self: Self, device_index: int) -> int | None:
        """Determine the stable instance_id for a joystick device (opening it, once).

        Args:
            device_index: The device index from the event.

        Returns:
            The resolved instance_id, or None when the device could not be opened. The caller
            then keys the device by its device index, but never looks that index up as an
            instance id: another device may have that instance id.

        """
        try:
            opened_joystick = active_sources().devices().open_joystick(device_index=device_index)
            opened_joystick.init()
            return int(opened_joystick.get_instance_id())
        except pygame.error:
            LOG.debug(
                'Failed to get instance_id for device_index=%s, using device_index as key',
                device_index,
            )
            return None

    @override
    def on_joy_device_added_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick device added events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # JOYDEVICEADDED device_index, guid

        # Deep debug: inspect the joystick reported at this device_index
        added_device_index: int | None = getattr(event, 'device_index', None)
        self.log.debug(
            f'on_joy_device_added_event id(self)={id(self)} device_index={added_device_index}'
        )
        if added_device_index is None:
            self.log.debug('DEVICEADDED event has no device_index attribute')
            return

        # Determine stable instance_id for the new device (this opens it, once). When it could
        # not be opened, the device index is only the tracking key: it is never looked up as an
        # instance id, and the proxy opens the device by its device index.
        instance_id = self._resolve_instance_id(added_device_index)
        tracking_key = instance_id if instance_id is not None else added_device_index

        self._log_joystick_debug_info(
            added_device_index,
            joystick=(
                None
                if instance_id is None
                else active_sources().devices().joystick_for_instance(instance_id=instance_id)
            ),
        )

        # Check if already tracked
        if tracking_key in self.joysticks:
            self.log.debug('Instance #%s already exists, skipping duplicate creation', tracking_key)
            return

        try:
            joystick_proxy = JoystickEventManager.JoystickEventProxy(
                joystick_id=added_device_index,
                instance_id=instance_id,
                game=self.game,
            )
        except pygame.error:
            # Unplugged again before it could be opened: there is nothing to track
            self.log.warning(
                'Joystick at device index %s vanished before it could be opened',
                added_device_index,
                exc_info=True,
            )
            return
        self.log.debug(
            'Created JoystickProxy with'
            f' device_index={added_device_index},'
            f' instance_id={instance_id},'
            f' _device_id={joystick_proxy._device_id}',  # pyright: ignore[reportPrivateUsage]
        )
        self.joysticks[tracking_key] = joystick_proxy

        # The joystick proxy overrides the joystick object
        self.log.debug(f'Added Joystick #{added_device_index}: {joystick_proxy}')
        self.log.debug('JOYDEVICEADDED triggered: on_joy_device_added(%s)', event)

        # Need to notify the game after the joystick exists
        self.joysticks[tracking_key].on_joy_device_added_event(event)

    @override
    def on_joy_device_removed_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick device removed events.

        Args:
            event (pygame.event.Event): The event to handle.

        """
        # JOYDEVICEREMOVED instance_id
        self.log.debug(f'Removed Joystick #{event.instance_id}')
        self.log.debug('JOYDEVICEREMOVED triggered: on_joy_device_removed(%s)', event)

        # The devices door stops polling it (tracked here or not)
        active_sources().devices().forget_device(instance_id=event.instance_id)

        # Need to notify the game first.
        if event.instance_id in self.joysticks:
            self.joysticks[event.instance_id].on_joy_device_removed_event(event)
            self.joysticks.pop(event.instance_id, None)
