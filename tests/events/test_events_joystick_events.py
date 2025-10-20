"""Tests for joystick event functionality.

This module tests joystick event interfaces, stubs, and event handling.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import (
    HashableEvent,
    JoystickEvents,
    UnhandledEventError,
)

from tests.mocks.test_mock_factory import MockFactory


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
        # Use centralized mock for scene without event handlers (stub behavior)
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={}  # No event handlers - will fall back to stubs
        )

        # Test that stub methods can be called
        event = HashableEvent(pygame.JOYAXISMOTION, axis=0, value=0.5)
        # Mock the logger to suppress "Unhandled Event" messages during testing
        with patch("glitchygames.events.LOG.error"):
            with pytest.raises(UnhandledEventError):
                scene.on_joy_axis_motion_event(event)
        # Expected to call unhandled_event and raise UnhandledEventError

    def test_joy_axis_motion_event(self, mock_pygame_patches):
        """Test joystick axis motion event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_joy_axis_motion_event": lambda event: (scene.joystick_events_received.append(event), True)[1]
            }
        )

        # Test that the scene can handle the event
        event = HashableEvent(pygame.JOYAXISMOTION, axis=0, value=0.5)
        result = scene.on_joy_axis_motion_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.joystick_events_received) == 1
        assert scene.joystick_events_received[0].axis == 0
        assert scene.joystick_events_received[0].value == 0.5

    def test_joy_button_down_event(self, mock_pygame_patches):
        """Test joystick button down event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_joy_button_down_event": lambda event: (scene.joystick_events_received.append(event), True)[1]
            }
        )

        # Test that the scene can handle the event
        event = HashableEvent(pygame.JOYBUTTONDOWN, button=0)
        result = scene.on_joy_button_down_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.joystick_events_received) == 1
        assert scene.joystick_events_received[0].button == 0

    def test_joy_button_up_event(self, mock_pygame_patches):
        """Test joystick button up event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_joy_button_up_event": lambda event: (scene.joystick_events_received.append(event), True)[1]
            }
        )

        # Test that the scene can handle the event
        event = HashableEvent(pygame.JOYBUTTONUP, button=0)
        result = scene.on_joy_button_up_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.joystick_events_received) == 1
        assert scene.joystick_events_received[0].button == 0

    def test_joy_hat_motion_event(self, mock_pygame_patches):
        """Test joystick hat motion event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_joy_hat_motion_event": lambda event: (scene.joystick_events_received.append(event), True)[1]
            }
        )

        # Test that the scene can handle the event
        event = HashableEvent(pygame.JOYHATMOTION, hat=0, value=1)
        result = scene.on_joy_hat_motion_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.joystick_events_received) == 1
        assert scene.joystick_events_received[0].hat == 0
        assert scene.joystick_events_received[0].value == 1

    def test_joy_ball_motion_event(self, mock_pygame_patches):
        """Test joystick ball motion event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_joy_ball_motion_event": lambda event: (scene.joystick_events_received.append(event), True)[1]
            }
        )

        # Test ball motion
        event = HashableEvent(pygame.JOYBALLMOTION, ball=0, rel=(10, 10))
        result = scene.on_joy_ball_motion_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.joystick_events_received) == 1
        assert scene.joystick_events_received[0].type == pygame.JOYBALLMOTION
        assert scene.joystick_events_received[0].ball == 0
        assert scene.joystick_events_received[0].rel == (10, 10)

    def test_joy_device_added_event(self, mock_pygame_patches):
        """Test joystick device added event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_joy_device_added_event": lambda event: (scene.joystick_device_events.append(("added", event)), True)[1]
            }
        )

        # Test that the scene can handle the event
        event = HashableEvent(pygame.JOYDEVICEADDED, device_id=0)
        result = scene.on_joy_device_added_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.joystick_device_events) == 1
        assert scene.joystick_device_events[0][0] == "added"
        assert scene.joystick_device_events[0][1].device_id == 0

    def test_joy_device_removed_event(self, mock_pygame_patches):
        """Test joystick device removed event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_joy_device_removed_event": lambda event: (scene.joystick_device_events.append(("removed", event)), True)[1]
            }
        )

        # Test device removed
        event = HashableEvent(pygame.JOYDEVICEREMOVED, device_id=0)
        result = scene.on_joy_device_removed_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.joystick_device_events) == 1
        assert scene.joystick_device_events[0][0] == "removed"
        assert scene.joystick_device_events[0][1].type == pygame.JOYDEVICEREMOVED
        assert scene.joystick_device_events[0][1].device_id == 0

    def test_multiple_axis_events(self, mock_pygame_patches):
        """Test multiple axis motion events."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_joy_axis_motion_event": lambda event: (scene.joystick_events_received.append(event), True)[1]
            }
        )

        # Test different axes
        for axis in range(4):  # Test first 4 axes
            event = HashableEvent(pygame.JOYAXISMOTION, axis=axis, value=0.5)
            result = scene.on_joy_axis_motion_event(event)

            # Event should be handled successfully
            assert result is True
            assert len(scene.joystick_events_received) == 1
            assert scene.joystick_events_received[0].type == pygame.JOYAXISMOTION
            assert scene.joystick_events_received[0].axis == axis
            assert scene.joystick_events_received[0].value == 0.5

            # Clear for next iteration
            scene.joystick_events_received.clear()

    def test_multiple_button_events(self, mock_pygame_patches):
        """Test multiple button events."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_joy_button_down_event": lambda event: (scene.joystick_events_received.append(("button_down", event)), True)[1],
                "on_joy_button_up_event": lambda event: (scene.joystick_events_received.append(("button_up", event)), True)[1]
            }
        )

        # Test different buttons
        for button in range(8):  # Test first 8 buttons
            # Test button down
            event = HashableEvent(pygame.JOYBUTTONDOWN, button=button)
            result = scene.on_joy_button_down_event(event)

            # Event should be handled successfully
            assert result is True
            assert len(scene.joystick_events_received) == 1
            assert scene.joystick_events_received[0][0] == "button_down"
            assert scene.joystick_events_received[0][1].type == pygame.JOYBUTTONDOWN
            assert scene.joystick_events_received[0][1].button == button

            # Clear for next iteration
            scene.joystick_events_received.clear()

            # Test button up
            event = HashableEvent(pygame.JOYBUTTONUP, button=button)
            result = scene.on_joy_button_up_event(event)

            # Event should be handled successfully
            assert result is True
            assert len(scene.joystick_events_received) == 1
            assert scene.joystick_events_received[0][0] == "button_up"
            assert scene.joystick_events_received[0][1].type == pygame.JOYBUTTONUP
            assert scene.joystick_events_received[0][1].button == button

            # Clear for next iteration
            scene.joystick_events_received.clear()

    def test_hat_directions(self, mock_pygame_patches):
        """Test joystick hat direction events."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_joy_hat_motion_event": lambda event: (scene.joystick_events_received.append(event), True)[1]
            }
        )

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
            result = scene.on_joy_hat_motion_event(event)

            # Event should be handled successfully
            assert result is True
            assert len(scene.joystick_events_received) == 1
            assert scene.joystick_events_received[0].type == pygame.JOYHATMOTION
            assert scene.joystick_events_received[0].hat == 0
            assert scene.joystick_events_received[0].value == direction

            # Clear for next iteration
            scene.joystick_events_received.clear()


class TestJoystickManager:
    """Test JoystickManager in isolation."""

    def test_joystick_manager_initialization(self, mock_pygame_patches):
        """Test JoystickManager initializes correctly."""
        from glitchygames.events.joystick import JoystickManager

        mock_game = Mock()
        manager = JoystickManager(game=mock_game)

        assert manager.game == mock_game
        assert hasattr(manager, "on_joystick_axis_motion_event")
        assert hasattr(manager, "on_joystick_button_down_event")

    def test_joystick_manager_events(self, mock_pygame_patches):
        """Test joystick event handling through manager."""
        from glitchygames.events.joystick import JoystickManager

        mock_game = Mock()
        manager = JoystickManager(game=mock_game)

        # Test axis motion
        axis_event = HashableEvent(pygame.JOYAXISMOTION, joy=0, axis=0, value=0.5)
        manager.on_joystick_axis_motion_event(axis_event)

        # Test button down
        down_event = HashableEvent(pygame.JOYBUTTONDOWN, joy=0, button=0)
        manager.on_joystick_button_down_event(down_event)

        # Test button up
        up_event = HashableEvent(pygame.JOYBUTTONUP, joy=0, button=0)
        manager.on_joystick_button_up_event(up_event)

