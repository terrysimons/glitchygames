#!/usr/bin/env python3
"""Joystick Event Manager."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import argparse

import pygame
from glitchygames.events import JoystickEvents, ResourceManager

LOG = logging.getLogger("game.joysticks")
LOG.addHandler(logging.NullHandler())


class JoystickManager(JoystickEvents, ResourceManager):
    """Manage joystick events."""

    log = LOG
    # Interiting from object is default in Python 3.
    # Linters complain if you do it.
    #
    # This isn't a ResourceManager like other proxies, because
    # there can be multiple joysticks, so having one instance
    # won't work.

    class JoystickProxy(JoystickEvents):
        """Joystick event proxy."""

        log = LOG

        def __init__(self: Self, game: object = None, joystick_id: int = -1, instance_id: int | None = None) -> None:
            """Initialize the joystick event proxy.

            Args:
                game (object): The game object.
                joystick_id (int): The joystick id.

            Returns:
                None

            """
            # Prefer stable instance_id when available
            self._id = instance_id if instance_id is not None else joystick_id
            # Store the device index for reference
            self._device_id = joystick_id
            try:
                if instance_id is not None and hasattr(pygame.joystick.Joystick, "from_instance_id"):
                    self.joystick = pygame.joystick.Joystick.from_instance_id(self._id)
                else:
                    self.joystick = pygame.joystick.Joystick(joystick_id)
            except Exception:
                # Fallback to index
                self.joystick = pygame.joystick.Joystick(joystick_id)
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

            # Initialize button state.
            self._axes = [self.joystick.get_axis(i) for i in range(self.get_numaxes())]

            self._balls = [self.joystick.get_ball(i) for i in range(self.get_numballs())]

            self._buttons = [self.joystick.get_button(i) for i in range(self.get_numbuttons())]

            self._hats = [self.joystick.get_hat(i) for i in range(self.get_numhats())]

            self.game = game
            self.proxies = [self.game, self.joystick]

        # Define some high level APIs
        def on_joy_axis_motion_event(self: Self, event: pygame.event.Event) -> None:
            """Handle joystick axis motion events.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            # JOYAXISMOTION    joy, axis, value
            self._axes[event.axis] = event.value
            self.game.on_joy_axis_motion_event(event)

        def on_joy_button_down_event(self: Self, event: pygame.event.Event) -> None:
            """Handle joystick button down events.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            # JOYBUTTONDOWN    joy, button
            # Ensure storage accommodates this button index
            if event.button < 0:
                return
            if event.button >= len(self._buttons):
                self._buttons.extend([0] * (event.button + 1 - len(self._buttons)))
            self._buttons[event.button] = 1
            self.game.on_joy_button_down_event(event)

        def on_joy_button_up_event(self: Self, event: pygame.event.Event) -> None:
            """Handle joystick button up events.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            # JOYBUTTONUP      joy, button
            if event.button < 0:
                return
            if event.button >= len(self._buttons):
                self._buttons.extend([0] * (event.button + 1 - len(self._buttons)))
            self._buttons[event.button] = 0
            self.game.on_joy_button_up_event(event)

        def on_joy_hat_motion_event(self: Self, event: pygame.event.Event) -> None:
            """Handle joystick hat motion events.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            # JOYHATMOTION     joy, hat, value
            self._hats[event.hat] = event.value
            self.game.on_joy_hat_motion_event(event)

        def on_joy_ball_motion_event(self: Self, event: pygame.event.Event) -> None:
            """Handle joystick ball motion events.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            # JOYBALLMOTION    joy, ball, rel
            self._balls[event.ball] = event.rel
            self.game.on_joy_ball_motion_event(event)

        def on_joy_device_added_event(self: Self, event: pygame.event.Event) -> None:
            """Handle joystick device added events.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            # JOYDEVICEADDED device_index, guid
            self.game.on_joy_device_added_event(event)

        def on_joy_device_removed_event(self: Self, event: pygame.event.Event) -> None:
            """Handle joystick device removed events.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

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
            except Exception:
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

        def __str__(self: Self) -> str:
            """Get the joystick info.

            Returns:
                str: The joystick info.

            """
            joystick_info = [
                f"Joystick Name: {self.get_name()}",
                f"\tJoystick Id: {self._device_id}",
                f"\tJoystick Inited: {self.get_init()}",
                f"\tJoystick Axis Count: {self.get_numaxes()}",
                f"\tJoystick Trackball Count: {self.get_numballs()}",
                f"\tJoystick Button Count: {self.get_numbuttons()}",
                f"\tJoystick Hat Count: {self.get_numhats()}",
            ]

            return "\n".join(joystick_info)

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

        Returns:
            None

        """
        super().__init__(game=game)
        self.joysticks = {}
        self.game = game

        # This must be called before other joystick methods,
        # and is safe to call more than once.
        pygame.joystick.init()

        self.log.info(f"Joystick Module Inited: {pygame.joystick.get_init()}")
        self.log.debug(f"JoystickManager init id(self)={id(self)}")

        # Joystick Setup
        self.log.info(f"Joystick Count: {pygame.joystick.get_count()}")
        joysticks = [pygame.joystick.Joystick(x) for x in range(pygame.joystick.get_count())]

        for pygame_joystick_index, joystick in enumerate(joysticks):
            joystick.init()

            # Deep debug: capture both index and instance identity at init time
            try:
                idx_get_id = joystick.get_id() if hasattr(joystick, "get_id") else None
            except Exception:
                idx_get_id = None
            try:
                idx_instance = joystick.get_instance_id() if hasattr(joystick, "get_instance_id") else None
            except Exception:
                idx_instance = None
            try:
                idx_name = joystick.get_name() if hasattr(joystick, "get_name") else None
            except Exception:
                idx_name = None
            try:
                idx_guid = joystick.get_guid() if hasattr(joystick, "get_guid") else None
            except Exception:
                idx_guid = None
            self.log.debug(
                f"INIT MAP index={pygame_joystick_index} get_id={idx_get_id} instance_id={idx_instance} name={idx_name} guid={idx_guid}"
            )

            # Use stable instance_id as the key when available
            try:
                instance_id = joystick.get_instance_id()
            except AttributeError:
                instance_id = pygame_joystick_index
            joystick_proxy = JoystickManager.JoystickProxy(
                joystick_id=pygame_joystick_index, instance_id=instance_id, game=self.game
            )
            self.joysticks[instance_id] = joystick_proxy

            # The joystick proxy overrides the joystick object
            self.log.info(f"Added Joystick: {joystick_proxy}")

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
        group = parser.add_argument_group("Joystick Options")  # noqa: F841

        return parser

    # Define some high level APIs
    #
    # Note that we can't pass these through the way
    # we do for other event types because
    # we need to know which joystick the event is intended for.
    def on_joy_axis_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle joystick axis motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # JOYAXISMOTION    joy, axis, value
        try:
            joystick_id = event.instance_id
        except AttributeError:
            joystick_id = event.joy

        self.log.debug(f"JOYAXISMOTION triggered: on_joy_axis_motion_event({event})")
        self.joysticks[joystick_id].on_joy_axis_motion_event(event)

    def on_joy_button_down_event(self: Self, event: pygame.event.Event) -> None:
        """Handle joystick button down events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # JOYBUTTONDOWN    joy, button
        try:
            joystick_id = event.instance_id
        except AttributeError:
            joystick_id = event.joy

        self.log.debug(f"JOYBUTTONDOWN triggered: on_joy_button_down_event({event})")
        self.joysticks[joystick_id].on_joy_button_down_event(event)

    def on_joy_button_up_event(self: Self, event: pygame.event.Event) -> None:
        """Handle joystick button up events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # JOYBUTTONUP      joy, button
        try:
            joystick_id = event.instance_id
        except AttributeError:
            joystick_id = event.joy

        self.log.debug(f"JOYBUTTONUP triggered: on_joy_button_up_event({event})")
        self.joysticks[joystick_id].on_joy_button_up_event(event)

    def on_joy_hat_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle joystick hat motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # JOYHATMOTION     joy, hat, value
        try:
            joystick_id = event.instance_id
        except AttributeError:
            joystick_id = event.joy

        self.log.debug(f"JOYHATMOTION triggered: on_joy_hat_motion_event({event})")
        self.joysticks[joystick_id].on_joy_hat_motion_event(event)

    def on_joy_ball_motion_event(self: Self, event: pygame.event.Event) -> None:
        """Handle joystick ball motion events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # JOYBALLMOTION    joy, ball, rel
        try:
            joystick_id = event.instance_id
        except AttributeError:
            joystick_id = event.joy

        self.log.debug(f"JOYBALLMOTION triggered: on_joy_ball_motion_event({event})")
        self.joysticks[joystick_id].on_joy_ball_motion_event(event)

    def on_joy_device_added_event(self: Self, event: pygame.event.Event) -> None:
        """Handle joystick device added events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # JOYDEVICEADDED device_index, guid

        # Deep debug: inspect the joystick reported at this device_index
        added_idx = getattr(event, "device_index", None)
        self.log.debug(f"on_joy_device_added_event id(self)={id(self)} device_index={added_idx}")
        js = None
        try:
            js = pygame.joystick.Joystick(added_idx)
        except Exception as e:
            self.log.debug(f"DEVICEADDED could not open Joystick({added_idx}): {e}")
        if js is not None:
            try:
                js_name = js.get_name()
            except Exception:
                js_name = None
            try:
                js_guid = js.get_guid()
            except Exception:
                js_guid = None
            try:
                js_get_id = js.get_id()
            except Exception:
                js_get_id = None
            try:
                js_instance = js.get_instance_id()
            except Exception:
                js_instance = None
            self.log.debug(
                f"DEVICEADDED index={added_idx} get_id={js_get_id} instance_id={js_instance} name={js_name} guid={js_guid}"
            )

        # Determine stable instance_id for the new device
        try:
            js_inst = pygame.joystick.Joystick(event.device_index)
            js_inst.init()
            instance_id = js_inst.get_instance_id() if hasattr(js_inst, "get_instance_id") else event.device_index
        except Exception:
            instance_id = event.device_index

        # Check if already tracked
        if instance_id in self.joysticks:
            self.log.debug(f"Instance #{instance_id} already exists, skipping duplicate creation")
            return

        joystick_proxy = JoystickManager.JoystickProxy(
            joystick_id=event.device_index, instance_id=instance_id, game=self.game
        )
        self.log.debug(f"Created JoystickProxy with device_index={event.device_index}, instance_id={instance_id}, _device_id={joystick_proxy._device_id}")
        self.joysticks[instance_id] = joystick_proxy

        # The joystick proxy overrides the joystick object
        self.log.debug(f"Added Joystick #{event.device_index}: {joystick_proxy}")
        self.log.debug(f"JOYDEVICEADDED triggered: on_joy_device_added({event})")

        # Need to notify the game after the joystick exists, using stable instance_id
        if instance_id in self.joysticks:
            self.joysticks[instance_id].on_joy_device_added_event(event)
        else:
            # Fallback safety: if instance_id could not be derived, try device_index
            if hasattr(event, "device_index") and event.device_index in self.joysticks:
                self.joysticks[event.device_index].on_joy_device_added_event(event)

    def on_joy_device_removed_event(self: Self, event: pygame.event.Event) -> None:
        """Handle joystick device removed events.

        Args:
            event (pygame.event.Event): The event to handle.

        Returns:
            None

        """
        # JOYDEVICEREMOVED instance_id
        self.log.debug(f"Removed Joystick #{event.instance_id}")
        self.log.debug(f"JOYDEVICEREMOVED triggered: on_joy_device_removed({event})")

        # Need to notify the game first.
        if event.instance_id in self.joysticks:
            self.joysticks[event.instance_id].on_joy_device_removed_event(event)
            self.joysticks.pop(event.instance_id, None)
