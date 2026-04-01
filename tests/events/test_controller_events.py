"""Tests for controller event functionality.

This module tests controller event interfaces, stubs, event handling,
ControllerEventProxy forwarding and routing methods, and
ControllerEventManager initialization.
"""

import math
import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import (
    ControllerEvents,
    ControllerEventStubs,
    HashableEvent,
    UnhandledEventError,
)
from glitchygames.events.controller import ControllerEventManager
from tests.mocks.test_mock_factory import MockFactory


def _setup_controller_patches(mocker, controller_count=0):
    """Set up common pygame._sdl2.controller patches.

    Args:
        mocker: pytest-mock mocker fixture
        controller_count: Number of controllers to report

    """
    mocker.patch('pygame._sdl2.controller.init')
    mocker.patch('pygame._sdl2.controller.get_init', return_value=True)
    mocker.patch('pygame._sdl2.controller.get_count', return_value=controller_count)
    mocker.patch('pygame._sdl2.controller.is_controller', return_value=False)


class TestControllerEventProxyMethods:
    """Test ControllerEventProxy forwarding methods via the manager."""

    def _create_manager_with_mock_controller(self, mocker):
        """Create a ControllerEventManager with a mock controller at instance_id=0.

        The ControllerEventProxy requires a real SDL controller, so we mock it
        by inserting a mock proxy directly into the controllers dict. Patches
        the controller module to avoid real SDL calls.

        Returns:
            Tuple of (manager, mock_game, mock_proxy).
        """
        mock_game = mocker.Mock()
        _setup_controller_patches(mocker, controller_count=0)
        manager = ControllerEventManager(game=mock_game)

        # Create a mock controller proxy with all the forwarding methods
        mock_proxy = mocker.Mock()
        manager.controllers[0] = mock_proxy

        return manager, mock_game, mock_proxy

    def test_axis_motion_routes_to_controller_proxy(self, mock_pygame_patches, mocker):
        """Axis motion event should be routed to the correct controller proxy."""
        manager, _mock_game, mock_proxy = self._create_manager_with_mock_controller(mocker)

        event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=0, value=0.5, instance_id=0)
        manager.on_controller_axis_motion_event(event)

        mock_proxy.on_controller_axis_motion_event.assert_called_once_with(event)

    def test_button_down_routes_to_controller_proxy(self, mock_pygame_patches, mocker):
        """Button down event should be routed to the correct controller proxy."""
        manager, _mock_game, mock_proxy = self._create_manager_with_mock_controller(mocker)

        event = HashableEvent(pygame.CONTROLLERBUTTONDOWN, button=0, instance_id=0)
        manager.on_controller_button_down_event(event)

        mock_proxy.on_controller_button_down_event.assert_called_once_with(event)

    def test_button_up_routes_to_controller_proxy(self, mock_pygame_patches, mocker):
        """Button up event should be routed to the correct controller proxy."""
        manager, _mock_game, mock_proxy = self._create_manager_with_mock_controller(mocker)

        event = HashableEvent(pygame.CONTROLLERBUTTONUP, button=0, instance_id=0)
        manager.on_controller_button_up_event(event)

        mock_proxy.on_controller_button_up_event.assert_called_once_with(event)

    def test_device_added_creates_and_routes(self, mock_pygame_patches, mocker):
        """Device added event should create a new proxy and forward the event."""
        mock_game = mocker.Mock()
        _setup_controller_patches(mocker, controller_count=0)
        manager = ControllerEventManager(game=mock_game)

        # Mock the ControllerEventProxy constructor to avoid real SDL calls
        mock_proxy_instance = mocker.Mock()
        mocker.patch(
            'glitchygames.events.controller.ControllerEventManager.ControllerEventProxy',
            return_value=mock_proxy_instance,
        )

        event = HashableEvent(pygame.CONTROLLERDEVICEADDED, device_index=0, guid='test-guid')
        manager.on_controller_device_added_event(event)

        assert 0 in manager.controllers
        mock_proxy_instance.on_controller_device_added_event.assert_called_once_with(event)

    def test_device_remapped_routes_to_controller_proxy(self, mock_pygame_patches, mocker):
        """Device remapped event should be routed to the correct controller proxy."""
        manager, _mock_game, mock_proxy = self._create_manager_with_mock_controller(mocker)

        event = HashableEvent(pygame.CONTROLLERDEVICEREMAPPED, device_index=0)
        # The manager uses event.device_index for remapped events
        manager.controllers[0] = mock_proxy
        manager.on_controller_device_remapped_event(event)

        mock_proxy.on_controller_device_remapped_event.assert_called_once_with(event)

    def test_device_removed_routes_and_deletes(self, mock_pygame_patches, mocker):
        """Device removed event should forward to proxy, then delete it."""
        manager, _mock_game, mock_proxy = self._create_manager_with_mock_controller(mocker)

        event = HashableEvent(pygame.CONTROLLERDEVICEREMOVED, instance_id=0)
        manager.on_controller_device_removed_event(event)

        mock_proxy.on_controller_device_removed_event.assert_called_once_with(event)
        assert 0 not in manager.controllers

    def test_device_removed_missing_instance_is_noop(self, mock_pygame_patches, mocker):
        """Device removed for unknown instance_id should not crash."""
        mock_game = mocker.Mock()
        _setup_controller_patches(mocker, controller_count=0)
        manager = ControllerEventManager(game=mock_game)

        event = HashableEvent(pygame.CONTROLLERDEVICEREMOVED, instance_id=999)
        # Should not raise
        manager.on_controller_device_removed_event(event)

    def test_touchpad_down_routes_to_controller_proxy(self, mock_pygame_patches, mocker):
        """Touchpad down event should be routed to the correct controller proxy."""
        manager, _mock_game, mock_proxy = self._create_manager_with_mock_controller(mocker)

        event = HashableEvent(
            pygame.CONTROLLERTOUCHPADDOWN,
            touchpad=0,
            finger=0,
            x=100,
            y=100,
            instance_id=0,
        )
        manager.on_controller_touchpad_down_event(event)

        mock_proxy.on_controller_touchpad_down_event.assert_called_once_with(event)

    def test_touchpad_motion_routes_to_controller_proxy(self, mock_pygame_patches, mocker):
        """Touchpad motion event should be routed to the correct controller proxy."""
        manager, _mock_game, mock_proxy = self._create_manager_with_mock_controller(mocker)

        event = HashableEvent(
            pygame.CONTROLLERTOUCHPADMOTION,
            touchpad=0,
            finger=0,
            x=100,
            y=100,
            instance_id=0,
        )
        manager.on_controller_touchpad_motion_event(event)

        mock_proxy.on_controller_touchpad_motion_event.assert_called_once_with(event)

    def test_touchpad_up_routes_to_controller_proxy(self, mock_pygame_patches, mocker):
        """Touchpad up event should be routed to the correct controller proxy."""
        manager, _mock_game, mock_proxy = self._create_manager_with_mock_controller(mocker)

        event = HashableEvent(
            pygame.CONTROLLERTOUCHPADUP,
            touchpad=0,
            finger=0,
            x=100,
            y=100,
            instance_id=0,
        )
        manager.on_controller_touchpad_up_event(event)

        mock_proxy.on_controller_touchpad_up_event.assert_called_once_with(event)


class TestControllerEventProxyDirectMethods:
    """Test the ControllerEventProxy methods directly with a fully mocked proxy."""

    def _create_mock_proxy(self, mocker):
        """Create a mock ControllerEventProxy bypassing SDL controller init.

        Returns:
            Tuple of (proxy, mock_game).
        """
        # Mock the SDL controller so ControllerEventProxy.__init__ doesn't fail
        mock_controller = mocker.Mock()
        mock_controller.get_init.return_value = True
        mock_controller.attached.return_value = True
        mock_controller.get_axis.return_value = 0
        mock_controller.get_button.return_value = 0
        mock_controller.get_mapping.return_value = {}

        # pygame._sdl2.controller is a C module - mock the whole module reference
        # used by controller.py (which aliases it as pygame.controller)
        mock_controller_module = mocker.Mock()
        mock_controller_module.Controller.return_value = mock_controller
        mock_controller_module.name_forindex.return_value = 'Test Controller'
        mocker.patch.object(pygame, '_sdl2', mocker.Mock(controller=mock_controller_module))
        mocker.patch.object(pygame, 'controller', mock_controller_module)

        mock_game = mocker.Mock()
        proxy = ControllerEventManager.ControllerEventProxy(game=mock_game, controller_id=0)
        return proxy, mock_game

    def test_proxy_axis_motion_updates_axes_and_forwards(self, mock_pygame_patches, mocker):
        """Axis motion should update internal state and forward to game."""
        proxy, mock_game = self._create_mock_proxy(mocker)

        event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=0, value=12345)
        proxy.on_controller_axis_motion_event(event)

        assert proxy._axes[0] == 12345
        mock_game.on_controller_axis_motion_event.assert_called_once_with(event)

    def test_proxy_button_down_updates_state_and_forwards(self, mock_pygame_patches, mocker):
        """Button down should set button state to 1 and forward to game."""
        proxy, mock_game = self._create_mock_proxy(mocker)

        event = HashableEvent(pygame.CONTROLLERBUTTONDOWN, button=2)
        proxy.on_controller_button_down_event(event)

        assert proxy._buttons[2] == 1
        mock_game.on_controller_button_down_event.assert_called_once_with(event)

    def test_proxy_button_down_negative_button_is_noop(self, mock_pygame_patches, mocker):
        """Button down with negative button index should return early."""
        proxy, mock_game = self._create_mock_proxy(mocker)

        event = HashableEvent(pygame.CONTROLLERBUTTONDOWN, button=-1)
        proxy.on_controller_button_down_event(event)

        mock_game.on_controller_button_down_event.assert_not_called()

    def test_proxy_button_down_extends_buttons_list(self, mock_pygame_patches, mocker):
        """Button down with index beyond list should extend storage."""
        proxy, mock_game = self._create_mock_proxy(mocker)

        original_length = len(proxy._buttons)
        event = HashableEvent(pygame.CONTROLLERBUTTONDOWN, button=original_length + 5)
        proxy.on_controller_button_down_event(event)

        assert len(proxy._buttons) > original_length
        assert proxy._buttons[original_length + 5] == 1
        mock_game.on_controller_button_down_event.assert_called_once_with(event)

    def test_proxy_button_up_updates_state_and_forwards(self, mock_pygame_patches, mocker):
        """Button up should set button state to 0 and forward to game."""
        proxy, mock_game = self._create_mock_proxy(mocker)

        # First press button down
        proxy._buttons[2] = 1

        event = HashableEvent(pygame.CONTROLLERBUTTONUP, button=2)
        proxy.on_controller_button_up_event(event)

        assert proxy._buttons[2] == 0
        mock_game.on_controller_button_up_event.assert_called_once_with(event)

    def test_proxy_button_up_negative_button_is_noop(self, mock_pygame_patches, mocker):
        """Button up with negative button index should return early."""
        proxy, mock_game = self._create_mock_proxy(mocker)

        event = HashableEvent(pygame.CONTROLLERBUTTONUP, button=-1)
        proxy.on_controller_button_up_event(event)

        mock_game.on_controller_button_up_event.assert_not_called()

    def test_proxy_button_up_extends_buttons_list(self, mock_pygame_patches, mocker):
        """Button up with index beyond list should extend storage."""
        proxy, mock_game = self._create_mock_proxy(mocker)

        original_length = len(proxy._buttons)
        event = HashableEvent(pygame.CONTROLLERBUTTONUP, button=original_length + 3)
        proxy.on_controller_button_up_event(event)

        assert len(proxy._buttons) > original_length
        assert proxy._buttons[original_length + 3] == 0
        mock_game.on_controller_button_up_event.assert_called_once_with(event)

    def test_proxy_device_added_forwards(self, mock_pygame_patches, mocker):
        """Device added should forward to game."""
        proxy, mock_game = self._create_mock_proxy(mocker)

        event = HashableEvent(pygame.CONTROLLERDEVICEADDED, device_index=0, guid='test')
        proxy.on_controller_device_added_event(event)

        mock_game.on_controller_device_added_event.assert_called_once_with(event)

    def test_proxy_device_remapped_forwards(self, mock_pygame_patches, mocker):
        """Device remapped should forward to game."""
        proxy, mock_game = self._create_mock_proxy(mocker)

        event = HashableEvent(pygame.CONTROLLERDEVICEREMAPPED, device_index=0)
        proxy.on_controller_device_remapped_event(event)

        mock_game.on_controller_device_remapped_event.assert_called_once_with(event)

    def test_proxy_device_removed_forwards(self, mock_pygame_patches, mocker):
        """Device removed should forward to game."""
        proxy, mock_game = self._create_mock_proxy(mocker)

        event = HashableEvent(pygame.CONTROLLERDEVICEREMOVED, instance_id=0)
        proxy.on_controller_device_removed_event(event)

        mock_game.on_controller_device_removed_event.assert_called_once_with(event)

    def test_proxy_touchpad_down_forwards(self, mock_pygame_patches, mocker):
        """Touchpad down should forward to game."""
        proxy, mock_game = self._create_mock_proxy(mocker)

        event = HashableEvent(pygame.CONTROLLERTOUCHPADDOWN, touchpad=0, finger=0, x=50, y=50)
        proxy.on_controller_touchpad_down_event(event)

        mock_game.on_controller_touchpad_down_event.assert_called_once_with(event)

    def test_proxy_touchpad_motion_forwards(self, mock_pygame_patches, mocker):
        """Touchpad motion should forward to game."""
        proxy, mock_game = self._create_mock_proxy(mocker)

        event = HashableEvent(pygame.CONTROLLERTOUCHPADMOTION, touchpad=0, finger=0, x=60, y=60)
        proxy.on_controller_touchpad_motion_event(event)

        mock_game.on_controller_touchpad_motion_event.assert_called_once_with(event)

    def test_proxy_touchpad_up_forwards(self, mock_pygame_patches, mocker):
        """Touchpad up should forward to game."""
        proxy, mock_game = self._create_mock_proxy(mocker)

        event = HashableEvent(pygame.CONTROLLERTOUCHPADUP, touchpad=0, finger=0, x=70, y=70)
        proxy.on_controller_touchpad_up_event(event)

        mock_game.on_controller_touchpad_up_event.assert_called_once_with(event)

    def test_proxy_str_representation(self, mock_pygame_patches, mocker):
        """str() should return a multi-line controller info string."""
        proxy, _mock_game = self._create_mock_proxy(mocker)

        result = str(proxy)
        assert 'Controller Name:' in result
        assert 'Controller Id:' in result
        assert 'Controller Inited:' in result
        assert 'Controller Axis Count:' in result
        assert 'Controller Button Count:' in result

    def test_proxy_repr(self, mock_pygame_patches, mocker):
        """repr() should return repr of the underlying controller."""
        proxy, _mock_game = self._create_mock_proxy(mocker)

        result = repr(proxy)
        # Should not raise and should return a string
        assert isinstance(result, str)


class TestControllerEvents:
    """Test ControllerEvents interface functionality."""

    def test_controller_events_interface(self, mock_pygame_patches):
        """Test ControllerEvents interface methods."""
        # Test that ControllerEvents has required abstract methods
        assert hasattr(ControllerEvents, 'on_controller_axis_motion_event')
        assert hasattr(ControllerEvents, 'on_controller_button_down_event')
        assert hasattr(ControllerEvents, 'on_controller_button_up_event')
        assert hasattr(ControllerEvents, 'on_controller_device_added_event')
        assert hasattr(ControllerEvents, 'on_controller_device_remapped_event')
        assert hasattr(ControllerEvents, 'on_controller_device_removed_event')
        assert hasattr(ControllerEvents, 'on_controller_touchpad_down_event')
        assert hasattr(ControllerEvents, 'on_controller_touchpad_motion_event')
        assert hasattr(ControllerEvents, 'on_controller_touchpad_up_event')

    def test_controller_event_stubs_implementation(self, mock_pygame_patches, mocker):
        """Test ControllerEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = ControllerEventStubs()
        assert hasattr(stub, 'on_controller_axis_motion_event')
        assert hasattr(stub, 'on_controller_button_down_event')
        assert hasattr(stub, 'on_controller_button_up_event')

        # Test that stub methods can be called with proper scene object
        self._setup_mock_scene_for_stub(stub)

        # Test method calls
        event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=0, value=0.5)

        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_controller_axis_motion_event(event)

    def test_controller_axis_motion_event(self, mock_pygame_patches):
        """Test controller axis motion event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_controller_axis_motion_event': lambda event: (
                    scene.controller_events_received.append(event) or True
                ),
            },
        )

        # Test that the scene can handle the event
        event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=0, value=0.5)
        result = scene.on_controller_axis_motion_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.controller_events_received) == 1
        assert scene.controller_events_received[0].axis == 0
        assert math.isclose(scene.controller_events_received[0].value, 0.5)

    def test_controller_button_down_event(self, mock_pygame_patches):
        """Test controller button down event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_controller_button_down_event': lambda event: (
                    scene.controller_events_received.append(event) or True
                ),
            },
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
                'on_controller_button_up_event': lambda event: (
                    scene.controller_events_received.append(event),
                    True,
                )[1],
            },
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
                'on_controller_device_added_event': lambda event: (
                    scene.controller_events_received.append(event),
                    True,
                )[1],
            },
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
                'on_controller_device_removed_event': lambda event: (
                    scene.controller_events_received.append(event),
                    True,
                )[1],
            },
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
                'on_controller_device_remapped_event': lambda event: (
                    scene.controller_events_received.append(event),
                    True,
                )[1],
            },
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
                'on_controller_touchpad_down_event': lambda event: (
                    scene.controller_events_received.append(event),
                    True,
                )[1],
            },
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
                'on_controller_touchpad_motion_event': lambda event: (
                    scene.controller_events_received.append(event),
                    True,
                )[1],
            },
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
                'on_controller_touchpad_up_event': lambda event: (
                    scene.controller_events_received.append(event),
                    True,
                )[1],
            },
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
                'on_controller_axis_motion_event': lambda event: (
                    scene.controller_events_received.append(event),
                    True,
                )[1],
            },
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
                'on_controller_button_down_event': lambda event: (
                    scene.controller_events_received.append(event),
                    True,
                )[1],
                'on_controller_button_up_event': lambda event: (
                    scene.controller_events_received.append(event),
                    True,
                )[1],
            },
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
                'on_controller_axis_motion_event': lambda event: (
                    scene.controller_events_received.append(event),
                    True,
                )[1],
            },
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
        """Set up mock scene object for event stubs using centralized mocks.

        Returns:
            object: The result.

        """
        # Create a scene mock with proper event handling configuration
        scene_mock = MockFactory.create_event_test_scene_mock(
            options={
                'debug_events': False,
                'no_unhandled_events': True,  # This will cause UnhandledEventError to be raised
            },
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
                'on_controller_axis_motion_event': lambda event: (
                    scene.controller_events_received.append(event),
                    True,
                )[1],
            },
        )

        # Create a HashableEvent with proper attributes
        event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=0, value=0.5)

        # Test that the scene can handle the event directly
        result = scene.on_controller_axis_motion_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.controller_events_received) == 1
        assert scene.controller_events_received[0].axis == 0
        assert math.isclose(scene.controller_events_received[0].value, 0.5)

    def test_controller_event_falls_back_to_stubs(self, mock_pygame_patches, mocker):
        """Test unhandled controller events fall back to stubs.

        Verifies that they cause UnhandledEventError.
        """
        # Use centralized mock for scene without event handlers
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={},  # No event handlers - will fall back to stubs
        )

        # Create a HashableEvent that will fall back to stubs
        event = HashableEvent(pygame.CONTROLLERAXISMOTION, axis=0, value=0.5)

        # This should cause UnhandledEventError due to unhandled_event
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            scene.on_controller_axis_motion_event(event)

    def test_controller_manager_initialization(self, mock_pygame_patches, mocker):
        """Test ControllerEventManager initializes correctly."""
        mock_game = mocker.Mock()
        _setup_controller_patches(mocker, controller_count=0)
        manager = ControllerEventManager(game=mock_game)

        assert manager.game == mock_game
        assert hasattr(manager, 'on_controller_axis_motion_event')
        assert hasattr(manager, 'on_controller_button_down_event')

    def test_controller_manager_directly(self, mock_pygame_patches, mocker):
        """Test ControllerEventManager in isolation."""
        mock_game = mocker.Mock()
        _setup_controller_patches(mocker, controller_count=0)
        manager = ControllerEventManager(game=mock_game)

        # Test that manager has the required methods
        assert hasattr(manager, 'on_controller_axis_motion_event')
        assert hasattr(manager, 'on_controller_button_down_event')
        assert hasattr(manager, 'on_controller_button_up_event')

        # Add a mock controller to the manager's controllers dictionary
        mock_controller = mocker.Mock()
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
