"""Tests for joystick event functionality.

This module tests joystick event interfaces, stubs, and event handling.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import (
    HashableEvent,
    JoystickEvents,
    JoystickEventStubs,
)


class TestJoystickEvents:
    """Test JoystickEvents interface functionality."""

    def test_joystick_events_interface(self, mock_pygame_patches):
        """Test JoystickEvents interface methods."""
        # Test that JoystickEvents has required abstract methods
        assert hasattr(JoystickEvents, "on_joy_axis_motion_event")
        assert hasattr(JoystickEvents, "on_joy_button_down_event")
        assert hasattr(JoystickEvents, "on_joy_button_up_event")
        assert hasattr(JoystickEvents, "on_joy_device_added_event")
        assert hasattr(JoystickEvents, "on_joy_device_removed_event")
        assert hasattr(JoystickEvents, "on_joy_hat_motion_event")
        assert hasattr(JoystickEvents, "on_joy_ball_motion_event")

    def test_joystick_event_stubs_implementation(self, mock_pygame_patches):
        """Test JoystickEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = JoystickEventStubs()
        assert hasattr(stub, "on_joy_axis_motion_event")
        assert hasattr(stub, "on_joy_button_down_event")
        assert hasattr(stub, "on_joy_button_up_event")

        # Test that stub methods can be called with proper game object
        self._setup_mock_game_for_stub(stub)

        # Test method calls
        event = HashableEvent(pygame.JOYAXISMOTION, axis=0, value=0.5)
        with pytest.raises((Exception, SystemExit)) as exc_info:
            stub.on_joy_axis_motion_event(event)
        # Expected to call unhandled_event
        # Exception was raised as expected

    def test_joy_axis_motion_event(self, mock_pygame_patches):
        """Test joystick axis motion event handling."""
        stub = JoystickEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test axis motion
        event = HashableEvent(pygame.JOYAXISMOTION, axis=0, value=0.5)
        with pytest.raises((Exception, SystemExit)) as exc_info:
            stub.on_joy_axis_motion_event(event)
        # Exception was raised as expected

    def test_joy_button_down_event(self, mock_pygame_patches):
        """Test joystick button down event handling."""
        stub = JoystickEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test button down
        event = HashableEvent(pygame.JOYBUTTONDOWN, button=0)
        with pytest.raises((Exception, SystemExit)) as exc_info:
            stub.on_joy_button_down_event(event)
        # Exception was raised as expected

    def test_joy_button_up_event(self, mock_pygame_patches):
        """Test joystick button up event handling."""
        stub = JoystickEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test button up
        event = HashableEvent(pygame.JOYBUTTONUP, button=0)
        with pytest.raises((Exception, SystemExit)) as exc_info:
            stub.on_joy_button_up_event(event)
        # Exception was raised as expected

    def test_joy_hat_motion_event(self, mock_pygame_patches):
        """Test joystick hat motion event handling."""
        stub = JoystickEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test hat motion
        event = HashableEvent(pygame.JOYHATMOTION, hat=0, value=1)
        with pytest.raises((Exception, SystemExit)) as exc_info:
            stub.on_joy_hat_motion_event(event)
        # Exception was raised as expected

    def test_joy_ball_motion_event(self, mock_pygame_patches):
        """Test joystick ball motion event handling."""
        stub = JoystickEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test ball motion
        event = HashableEvent(pygame.JOYBALLMOTION, ball=0, rel=(10, 10))
        with pytest.raises((Exception, SystemExit)) as exc_info:
            stub.on_joy_ball_motion_event(event)
        # Exception was raised as expected

    def test_joy_device_added_event(self, mock_pygame_patches):
        """Test joystick device added event handling."""
        stub = JoystickEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test device added
        event = HashableEvent(pygame.JOYDEVICEADDED, device_id=0)
        with pytest.raises((Exception, SystemExit)) as exc_info:
            stub.on_joy_device_added_event(event)
        # Exception was raised as expected

    def test_joy_device_removed_event(self, mock_pygame_patches):
        """Test joystick device removed event handling."""
        stub = JoystickEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test device removed
        event = HashableEvent(pygame.JOYDEVICEREMOVED, device_id=0)
        with pytest.raises((Exception, SystemExit)) as exc_info:
            stub.on_joy_device_removed_event(event)
        # Exception was raised as expected

    def test_multiple_axis_events(self, mock_pygame_patches):
        """Test multiple axis motion events."""
        stub = JoystickEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test different axes
        for axis in range(4):  # Test first 4 axes
            event = HashableEvent(pygame.JOYAXISMOTION, axis=axis, value=0.5)
            with pytest.raises((Exception, SystemExit)) as exc_info:
                stub.on_joy_axis_motion_event(event)
            # Exception was raised as expected

    def test_multiple_button_events(self, mock_pygame_patches):
        """Test multiple button events."""
        stub = JoystickEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test different buttons
        for button in range(8):  # Test first 8 buttons
            # Test button down
            event = HashableEvent(pygame.JOYBUTTONDOWN, button=button)
            with pytest.raises((Exception, SystemExit)) as exc_info:
                stub.on_joy_button_down_event(event)
            # Exception was raised as expected

            # Test button up
            event = HashableEvent(pygame.JOYBUTTONUP, button=button)
            with pytest.raises((Exception, SystemExit)) as exc_info:
                stub.on_joy_button_up_event(event)
            # Exception was raised as expected

    def test_hat_directions(self, mock_pygame_patches):
        """Test joystick hat direction events."""
        stub = JoystickEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test different hat directions
        hat_directions = [
            0,   # CENTER
            1,   # UP
            2,   # RIGHT
            4,   # DOWN
            8,   # LEFT
            3,   # UP + RIGHT
            6,   # RIGHT + DOWN
            12,  # DOWN + LEFT
            9,   # LEFT + UP
        ]

        for direction in hat_directions:
            event = HashableEvent(pygame.JOYHATMOTION, hat=0, value=direction)
            with pytest.raises((Exception, SystemExit)) as exc_info:
                stub.on_joy_hat_motion_event(event)
            # Exception was raised as expected

    def _setup_mock_game_for_stub(self, stub):
        """Set up mock game object for event stubs."""
        mock_game = Mock()
        mock_game.options = {
            "debug_events": False,
            "no_unhandled_events": True
        }
        stub.options = mock_game.options
        return mock_game
