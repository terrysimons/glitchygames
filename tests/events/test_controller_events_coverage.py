"""Coverage tests for glitchygames/events/controller.py.

This module targets uncovered proxy/forwarding methods in ControllerEventProxy
and the ControllerEventManager's routing methods.
"""

import sys
from pathlib import Path

import pygame

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import HashableEvent


class TestControllerEventProxyMethods:
    """Test ControllerEventProxy forwarding methods via the manager."""

    def _create_manager_with_mock_controller(self, mocker):
        """Create a ControllerEventManager with a mock controller at instance_id=0.

        The ControllerEventProxy requires a real SDL controller, so we mock it
        by inserting a mock proxy directly into the controllers dict.

        Returns:
            Tuple of (manager, mock_game, mock_proxy).
        """
        from glitchygames.events.controller import ControllerEventManager

        mock_game = mocker.Mock()
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
        from glitchygames.events.controller import ControllerEventManager

        mock_game = mocker.Mock()
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
        from glitchygames.events.controller import ControllerEventManager

        mock_game = mocker.Mock()
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
        from glitchygames.events.controller import ControllerEventManager

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
