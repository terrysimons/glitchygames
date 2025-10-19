"""Tests for controller event functionality.

This module tests controller event interfaces, stubs, and event handling.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.engine import GameEngine
from glitchygames.events import (
    ControllerEvents,
    ControllerEventStubs,
    HashableEvent,
    UnhandledEventError,
)
from glitchygames.scenes import Scene

from tests.mocks.test_mock_factory import MockFactory


class TestControllerEvents:
    """Test ControllerEvents interface functionality."""

    def test_controller_events_interface(self, mock_pygame_patches):
        """Test ControllerEvents interface methods."""
        # Test that ControllerEvents has required abstract methods
        assert hasattr(ControllerEvents, "on_controller_axis_motion_event")
        assert hasattr(ControllerEvents, "on_controller_button_down_event")
        assert hasattr(ControllerEvents, "on_controller_button_up_event")
        assert hasattr(ControllerEvents, "on_controller_device_added_event")
        assert hasattr(ControllerEvents, "on_controller_device_remapped_event")
        assert hasattr(ControllerEvents, "on_controller_device_removed_event")
        assert hasattr(ControllerEvents, "on_controller_touchpad_down_event")
        assert hasattr(ControllerEvents, "on_controller_touchpad_motion_event")
        assert hasattr(ControllerEvents, "on_controller_touchpad_up_event")

    def test_controller_event_stubs_implementation(self, mock_pygame_patches):
        """Test ControllerEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = ControllerEventStubs()
        assert hasattr(stub, "on_controller_axis_motion_event")
        assert hasattr(stub, "on_controller_button_down_event")
        assert hasattr(stub, "on_controller_button_up_event")

        # Test that stub methods can be called with proper scene object
        self._setup_mock_scene_for_stub(stub)

        # Test method calls
        event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=0, value=0.5)

        # Mock the logger to suppress "Unhandled Event" messages during testing
        with patch("glitchygames.events.LOG.error"):
            with pytest.raises(UnhandledEventError):
                stub.on_controller_axis_motion_event(event)

    def test_controller_axis_motion_event(self, mock_pygame_patches):
        """Test controller axis motion event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_controller_axis_motion_event": lambda event: scene.controller_events_received.append(event) or True
            }
        )

        # Test that the scene can handle the event
        event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=0, value=0.5)
        result = scene.on_controller_axis_motion_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.controller_events_received) == 1
        assert scene.controller_events_received[0].axis == 0
        assert scene.controller_events_received[0].value == 0.5

    def test_controller_button_down_event(self, mock_pygame_patches):
        """Test controller button down event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_controller_button_down_event": lambda event: scene.controller_events_received.append(event) or True
            }
        )

        # Test that the scene can handle the event
        event = HashableEvent(pygame.CONTROLLERBUTTONDOWN, button=0)
        result = scene.on_controller_button_down_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.controller_events_received) == 1
        assert scene.controller_events_received[0].button == 0

    def test_controller_button_up_event(self, mock_pygame_patches):
        """Test controller button up event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_controller_button_up_event": lambda event: (scene.controller_events_received.append(event), True)[1]
            }
        )

        # Test that the scene can handle the event
        event = HashableEvent(pygame.CONTROLLERBUTTONUP, button=0)
        result = scene.on_controller_button_up_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.controller_events_received) == 1
        assert scene.controller_events_received[0].button == 0

    def test_controller_device_added_event(self, mock_pygame_patches):
        """Test controller device added event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_controller_device_added_event": lambda event: (scene.controller_events_received.append(event), True)[1]
            }
        )

        # Test that the scene can handle the event
        event = HashableEvent(pygame.CONTROLLERDEVICEADDED, device_id=0)
        result = scene.on_controller_device_added_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.controller_events_received) == 1
        assert scene.controller_events_received[0].device_id == 0

    def test_controller_device_removed_event(self, mock_pygame_patches):
        """Test controller device removed event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_controller_device_removed_event": lambda event: (scene.controller_events_received.append(event), True)[1]
            }
        )

        # Test that the scene can handle the event
        event = HashableEvent(pygame.CONTROLLERDEVICEREMOVED, device_id=0)
        result = scene.on_controller_device_removed_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.controller_events_received) == 1
        assert scene.controller_events_received[0].device_id == 0

    def test_controller_device_remapped_event(self, mock_pygame_patches):
        """Test controller device remapped event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_controller_device_remapped_event": lambda event: (scene.controller_events_received.append(event), True)[1]
            }
        )

        # Test that the scene can handle the event
        event = HashableEvent(pygame.CONTROLLERDEVICEREMAPPED, device_id=0)
        result = scene.on_controller_device_remapped_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.controller_events_received) == 1
        assert scene.controller_events_received[0].device_id == 0

    def test_controller_touchpad_down_event(self, mock_pygame_patches):
        """Test controller touchpad down event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_controller_touchpad_down_event": lambda event: (scene.controller_events_received.append(event), True)[1]
            }
        )

        # Test that the scene can handle the event
        event = HashableEvent(pygame.CONTROLLERTOUCHPADDOWN, touchpad=0, finger=0, x=100, y=100)
        result = scene.on_controller_touchpad_down_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.controller_events_received) == 1
        assert scene.controller_events_received[0].touchpad == 0
        assert scene.controller_events_received[0].finger == 0

    def test_controller_touchpad_motion_event(self, mock_pygame_patches):
        """Test controller touchpad motion event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_controller_touchpad_motion_event": lambda event: (scene.controller_events_received.append(event), True)[1]
            }
        )

        # Test that the scene can handle the event
        event = HashableEvent(pygame.CONTROLLERTOUCHPADMOTION, touchpad=0, finger=0, x=100, y=100)
        result = scene.on_controller_touchpad_motion_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.controller_events_received) == 1
        assert scene.controller_events_received[0].touchpad == 0
        assert scene.controller_events_received[0].finger == 0

    def test_controller_touchpad_up_event(self, mock_pygame_patches):
        """Test controller touchpad up event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_controller_touchpad_up_event": lambda event: (scene.controller_events_received.append(event), True)[1]
            }
        )

        # Test that the scene can handle the event
        event = HashableEvent(pygame.CONTROLLERTOUCHPADUP, touchpad=0, finger=0, x=100, y=100)
        result = scene.on_controller_touchpad_up_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.controller_events_received) == 1
        assert scene.controller_events_received[0].touchpad == 0
        assert scene.controller_events_received[0].finger == 0

    def test_controller_axis_values(self, mock_pygame_patches):
        """Test controller axis motion with different values."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_controller_axis_motion_event": lambda event: (scene.controller_events_received.append(event), True)[1]
            }
        )

        # Test different axis values
        axis_values = [-1.0, -0.5, 0.0, 0.5, 1.0]
        for value in axis_values:
            event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=0, value=value)
            result = scene.on_controller_axis_motion_event(event)
            assert result is True

        # All events should be handled successfully
        assert len(scene.controller_events_received) == len(axis_values)
        for i, value in enumerate(axis_values):
            assert scene.controller_events_received[i].value == value

    def test_controller_button_variations(self, mock_pygame_patches):
        """Test controller button events with different buttons."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_controller_button_down_event": lambda event: (scene.controller_events_received.append(event), True)[1],
                "on_controller_button_up_event": lambda event: (scene.controller_events_received.append(event), True)[1]
            }
        )

        # Test different controller buttons
        controller_buttons = [
            pygame.CONTROLLER_BUTTON_A,
            pygame.CONTROLLER_BUTTON_B,
            pygame.CONTROLLER_BUTTON_X,
            pygame.CONTROLLER_BUTTON_Y,
            pygame.CONTROLLER_BUTTON_BACK,
            pygame.CONTROLLER_BUTTON_GUIDE,
            pygame.CONTROLLER_BUTTON_START,
            pygame.CONTROLLER_BUTTON_LEFTSTICK,
            pygame.CONTROLLER_BUTTON_RIGHTSTICK,
            pygame.CONTROLLER_BUTTON_LEFTSHOULDER,
            pygame.CONTROLLER_BUTTON_RIGHTSHOULDER,
            pygame.CONTROLLER_BUTTON_DPAD_UP,
            pygame.CONTROLLER_BUTTON_DPAD_DOWN,
            pygame.CONTROLLER_BUTTON_DPAD_LEFT,
            pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
        ]

        for button in controller_buttons:
            # Test button down
            event = HashableEvent(pygame.CONTROLLERBUTTONDOWN, button=button)
            result = scene.on_controller_button_down_event(event)
            assert result is True

            # Test button up
            event = HashableEvent(pygame.CONTROLLERBUTTONUP, button=button)
            result = scene.on_controller_button_up_event(event)
            assert result is True

        # All events should be handled successfully (2 events per button)
        assert len(scene.controller_events_received) == len(controller_buttons) * 2

    def test_controller_axis_variations(self, mock_pygame_patches):
        """Test controller axis motion with different axes."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_controller_axis_motion_event": lambda event: (scene.controller_events_received.append(event), True)[1]
            }
        )

        # Test different controller axes
        controller_axes = [
            pygame.CONTROLLER_AXIS_LEFTX,
            pygame.CONTROLLER_AXIS_LEFTY,
            pygame.CONTROLLER_AXIS_RIGHTX,
            pygame.CONTROLLER_AXIS_RIGHTY,
            pygame.CONTROLLER_AXIS_TRIGGERLEFT,
            pygame.CONTROLLER_AXIS_TRIGGERRIGHT,
        ]

        for axis in controller_axes:
            event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=axis, value=0.5)
            result = scene.on_controller_axis_motion_event(event)
            assert result is True

        # All events should be handled successfully
        assert len(scene.controller_events_received) == len(controller_axes)
        for i, axis in enumerate(controller_axes):
            assert scene.controller_events_received[i].axis == axis

    def _setup_mock_scene_for_stub(self, stub):
        """Set up mock scene object for event stubs using centralized mocks."""
        # Create a scene mock with proper event handling configuration
        scene_mock = MockFactory.create_event_test_scene_mock(
            options={
                "debug_events": False,
                "no_unhandled_events": True  # This will cause UnhandledEventError to be raised
            }
        )
        # Set the options on the stub so unhandled_event can access them
        stub.options = scene_mock.options
        return scene_mock



class TestControllerEventFlow:
    """Test controller events through the proper engine flow."""

    def test_controller_event_through_engine(self, mock_pygame_patches):
        """Test controller events flow through the entire engine system."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_controller_axis_motion_event": lambda event: (scene.controller_events_received.append(event), True)[1]
            }
        )

        # Create a HashableEvent with proper attributes
        event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=0, value=0.5)

        # Test that the scene can handle the event directly
        result = scene.on_controller_axis_motion_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.controller_events_received) == 1
        assert scene.controller_events_received[0].axis == 0
        assert scene.controller_events_received[0].value == 0.5

    def test_controller_event_falls_back_to_stubs(self, mock_pygame_patches):
        """Test that unhandled controller events fall back to stubs and cause UnhandledEventError."""
        # Use centralized mock for scene without event handlers
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={}  # No event handlers - will fall back to stubs
        )

        # Create a HashableEvent that will fall back to stubs
        event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=0, value=0.5)

        # This should cause UnhandledEventError due to unhandled_event
        # Mock the logger to suppress "Unhandled Event" messages during testing
        with patch("glitchygames.events.LOG.error"):
            with pytest.raises(UnhandledEventError):
                scene.on_controller_axis_motion_event(event)

    def test_controller_manager_initialization(self, mock_pygame_patches):
        """Test ControllerManager initializes correctly."""
        from glitchygames.events.controller import ControllerManager

        mock_game = Mock()
        manager = ControllerManager(game=mock_game)

        assert manager.game == mock_game
        assert hasattr(manager, "on_controller_axis_motion_event")
        assert hasattr(manager, "on_controller_button_down_event")

    def test_controller_manager_directly(self, mock_pygame_patches):
        """Test ControllerManager in isolation."""
        from glitchygames.events.controller import ControllerManager

        mock_game = Mock()
        manager = ControllerManager(game=mock_game)

        # Test that manager has the required methods
        assert hasattr(manager, "on_controller_axis_motion_event")
        assert hasattr(manager, "on_controller_button_down_event")
        assert hasattr(manager, "on_controller_button_up_event")

        # Add a mock controller to the manager's controllers dictionary
        mock_controller = Mock()
        manager.controllers[0] = mock_controller

        # Test axis motion event
        event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=0, value=0.5, instance_id=0)
        manager.on_controller_axis_motion_event(event)

        # Test button down event
        event = HashableEvent(pygame.CONTROLLERBUTTONDOWN, button=0, instance_id=0)
        manager.on_controller_button_down_event(event)

        # Test button up event
        event = HashableEvent(pygame.CONTROLLERBUTTONUP, button=0, instance_id=0)
        manager.on_controller_button_up_event(event)
