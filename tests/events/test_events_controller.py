"""Tests for controller event functionality.

This module tests controller event interfaces, stubs, and event handling.
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
    ControllerEvents,
    ControllerEventStubs,
)

from test_mock_factory import MockFactory


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
        
        # Test that stub methods can be called with proper game object
        self._setup_mock_game_for_stub(stub)
        
        # Test method calls
        event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=0, value=0.5)
        try:
            stub.on_controller_axis_motion_event(event)
        except Exception as e:
            # Expected to call unhandled_event
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_controller_axis_motion_event(self, mock_pygame_patches):
        """Test controller axis motion event handling."""
        stub = ControllerEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test axis motion
        event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=0, value=0.5)
        try:
            stub.on_controller_axis_motion_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_controller_button_down_event(self, mock_pygame_patches):
        """Test controller button down event handling."""
        stub = ControllerEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test button down
        event = HashableEvent(pygame.CONTROLLERBUTTONDOWN, button=0)
        try:
            stub.on_controller_button_down_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_controller_button_up_event(self, mock_pygame_patches):
        """Test controller button up event handling."""
        stub = ControllerEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test button up
        event = HashableEvent(pygame.CONTROLLERBUTTONUP, button=0)
        try:
            stub.on_controller_button_up_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_controller_device_added_event(self, mock_pygame_patches):
        """Test controller device added event handling."""
        stub = ControllerEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test device added
        event = HashableEvent(pygame.CONTROLLERDEVICEADDED, device_id=0)
        try:
            stub.on_controller_device_added_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_controller_device_removed_event(self, mock_pygame_patches):
        """Test controller device removed event handling."""
        stub = ControllerEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test device removed
        event = HashableEvent(pygame.CONTROLLERDEVICEREMOVED, device_id=0)
        try:
            stub.on_controller_device_removed_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_controller_device_remapped_event(self, mock_pygame_patches):
        """Test controller device remapped event handling."""
        stub = ControllerEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test device remapped
        event = HashableEvent(pygame.CONTROLLERDEVICEREMAPPED, device_id=0)
        try:
            stub.on_controller_device_remapped_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_controller_touchpad_down_event(self, mock_pygame_patches):
        """Test controller touchpad down event handling."""
        stub = ControllerEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test touchpad down
        event = HashableEvent(pygame.CONTROLLERTOUCHPADDOWN, touchpad=0, finger=0, x=100, y=100)
        try:
            stub.on_controller_touchpad_down_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_controller_touchpad_motion_event(self, mock_pygame_patches):
        """Test controller touchpad motion event handling."""
        stub = ControllerEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test touchpad motion
        event = HashableEvent(pygame.CONTROLLERTOUCHPADMOTION, touchpad=0, finger=0, x=100, y=100)
        try:
            stub.on_controller_touchpad_motion_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_controller_touchpad_up_event(self, mock_pygame_patches):
        """Test controller touchpad up event handling."""
        stub = ControllerEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test touchpad up
        event = HashableEvent(pygame.CONTROLLERTOUCHPADUP, touchpad=0, finger=0, x=100, y=100)
        try:
            stub.on_controller_touchpad_up_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_controller_axis_values(self, mock_pygame_patches):
        """Test controller axis motion with different values."""
        stub = ControllerEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test different axis values
        axis_values = [-1.0, -0.5, 0.0, 0.5, 1.0]
        for value in axis_values:
            event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=0, value=value)
            try:
                stub.on_controller_axis_motion_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_controller_button_variations(self, mock_pygame_patches):
        """Test controller button events with different buttons."""
        stub = ControllerEventStubs()
        self._setup_mock_game_for_stub(stub)
        
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
            try:
                stub.on_controller_button_down_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)
            
            # Test button up
            event = HashableEvent(pygame.CONTROLLERBUTTONUP, button=button)
            try:
                stub.on_controller_button_up_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_controller_axis_variations(self, mock_pygame_patches):
        """Test controller axis motion with different axes."""
        stub = ControllerEventStubs()
        self._setup_mock_game_for_stub(stub)
        
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
            try:
                stub.on_controller_axis_motion_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def _setup_mock_game_for_stub(self, stub):
        """Helper method to setup mock game object for event stubs."""
        mock_game = Mock()
        mock_game.options = {
            "debug_events": False,
            "no_unhandled_events": False
        }
        stub.options = mock_game.options
        return mock_game
