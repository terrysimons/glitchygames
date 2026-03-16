"""Coverage tests for glitchygames/events/joystick.py.

This module targets uncovered proxy/forwarding methods in JoystickEventProxy
and the JoystickEventManager's routing methods.
"""

import math
import sys
from pathlib import Path

import pygame

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import HashableEvent


class TestJoystickEventProxyDirectMethods:
    """Test JoystickEventProxy forwarding methods directly with mocked joystick."""

    def _create_mock_proxy(self, mocker):
        """Create a JoystickEventProxy with a fully mocked underlying joystick.

        Returns:
            Tuple of (proxy, mock_game, mock_joystick).
        """
        from glitchygames.events.joystick import JoystickEventManager

        mock_joystick = mocker.Mock()
        mock_joystick.init.return_value = None
        mock_joystick.get_init.return_value = True
        mock_joystick.get_name.return_value = 'Test Joystick'
        mock_joystick.get_guid.return_value = 'test-guid-1234'
        mock_joystick.get_power_level.return_value = 'full'
        mock_joystick.get_numaxes.return_value = 4
        mock_joystick.get_numballs.return_value = 1
        mock_joystick.get_numbuttons.return_value = 10
        mock_joystick.get_numhats.return_value = 1
        mock_joystick.get_axis.return_value = 0.0
        mock_joystick.get_ball.return_value = (0, 0)
        mock_joystick.get_button.return_value = 0
        mock_joystick.get_hat.return_value = (0, 0)

        mock_joystick_class = mocker.Mock()
        mock_joystick_class.return_value = mock_joystick
        mock_joystick_class.from_instance_id = mocker.Mock(return_value=mock_joystick)
        mocker.patch('pygame.joystick.Joystick', mock_joystick_class)

        mock_game = mocker.Mock()
        proxy = JoystickEventManager.JoystickEventProxy(
            game=mock_game, joystick_id=0, instance_id=0
        )
        return proxy, mock_game, mock_joystick

    def test_proxy_axis_motion_updates_and_forwards(self, mock_pygame_patches, mocker):
        """Axis motion should update axes state and forward to game."""
        proxy, mock_game, _ = self._create_mock_proxy(mocker)

        event = HashableEvent(pygame.JOYAXISMOTION, axis=1, value=0.75)
        proxy.on_joy_axis_motion_event(event)

        assert math.isclose(proxy._axes[1], 0.75)
        mock_game.on_joy_axis_motion_event.assert_called_once_with(event)

    def test_proxy_button_down_updates_and_forwards(self, mock_pygame_patches, mocker):
        """Button down should set button state to 1 and forward to game."""
        proxy, mock_game, _ = self._create_mock_proxy(mocker)

        event = HashableEvent(pygame.JOYBUTTONDOWN, button=3)
        proxy.on_joy_button_down_event(event)

        assert proxy._buttons[3] == 1
        mock_game.on_joy_button_down_event.assert_called_once_with(event)

    def test_proxy_button_down_negative_is_noop(self, mock_pygame_patches, mocker):
        """Button down with negative index should return early."""
        proxy, mock_game, _ = self._create_mock_proxy(mocker)

        event = HashableEvent(pygame.JOYBUTTONDOWN, button=-1)
        proxy.on_joy_button_down_event(event)

        mock_game.on_joy_button_down_event.assert_not_called()

    def test_proxy_button_down_extends_list(self, mock_pygame_patches, mocker):
        """Button down with index beyond list should extend storage."""
        proxy, _mock_game, _ = self._create_mock_proxy(mocker)

        original_length = len(proxy._buttons)
        event = HashableEvent(pygame.JOYBUTTONDOWN, button=original_length + 5)
        proxy.on_joy_button_down_event(event)

        assert len(proxy._buttons) > original_length
        assert proxy._buttons[original_length + 5] == 1

    def test_proxy_button_up_updates_and_forwards(self, mock_pygame_patches, mocker):
        """Button up should set button state to 0 and forward to game."""
        proxy, mock_game, _ = self._create_mock_proxy(mocker)

        proxy._buttons[3] = 1

        event = HashableEvent(pygame.JOYBUTTONUP, button=3)
        proxy.on_joy_button_up_event(event)

        assert proxy._buttons[3] == 0
        mock_game.on_joy_button_up_event.assert_called_once_with(event)

    def test_proxy_button_up_negative_is_noop(self, mock_pygame_patches, mocker):
        """Button up with negative index should return early."""
        proxy, mock_game, _ = self._create_mock_proxy(mocker)

        event = HashableEvent(pygame.JOYBUTTONUP, button=-1)
        proxy.on_joy_button_up_event(event)

        mock_game.on_joy_button_up_event.assert_not_called()

    def test_proxy_button_up_extends_list(self, mock_pygame_patches, mocker):
        """Button up with index beyond list should extend storage."""
        proxy, _mock_game, _ = self._create_mock_proxy(mocker)

        original_length = len(proxy._buttons)
        event = HashableEvent(pygame.JOYBUTTONUP, button=original_length + 3)
        proxy.on_joy_button_up_event(event)

        assert len(proxy._buttons) > original_length
        assert proxy._buttons[original_length + 3] == 0

    def test_proxy_hat_motion_updates_and_forwards(self, mock_pygame_patches, mocker):
        """Hat motion should update hats state and forward to game."""
        proxy, mock_game, _ = self._create_mock_proxy(mocker)

        event = HashableEvent(pygame.JOYHATMOTION, hat=0, value=(1, 0))
        proxy.on_joy_hat_motion_event(event)

        assert proxy._hats[0] == (1, 0)
        mock_game.on_joy_hat_motion_event.assert_called_once_with(event)

    def test_proxy_ball_motion_updates_and_forwards(self, mock_pygame_patches, mocker):
        """Ball motion should update balls state and forward to game."""
        proxy, mock_game, _ = self._create_mock_proxy(mocker)

        event = HashableEvent(pygame.JOYBALLMOTION, ball=0, rel=(5, -3))
        proxy.on_joy_ball_motion_event(event)

        assert proxy._balls[0] == (5, -3)
        mock_game.on_joy_ball_motion_event.assert_called_once_with(event)

    def test_proxy_device_added_forwards(self, mock_pygame_patches, mocker):
        """Device added should forward to game."""
        proxy, mock_game, _ = self._create_mock_proxy(mocker)

        event = HashableEvent(pygame.JOYDEVICEADDED, device_index=0, guid='test')
        proxy.on_joy_device_added_event(event)

        mock_game.on_joy_device_added_event.assert_called_once_with(event)

    def test_proxy_device_removed_forwards(self, mock_pygame_patches, mocker):
        """Device removed should forward to game."""
        proxy, mock_game, _ = self._create_mock_proxy(mocker)

        event = HashableEvent(pygame.JOYDEVICEREMOVED, device_index=0)
        proxy.on_joy_device_removed_event(event)

        mock_game.on_joy_device_removed_event.assert_called_once_with(event)

    def test_proxy_get_name(self, mock_pygame_patches, mocker):
        """get_name should return the joystick name."""
        proxy, _, _ = self._create_mock_proxy(mocker)

        name = proxy.get_name()
        assert name == 'Test Joystick'

    def test_proxy_get_name_fallback_on_error(self, mock_pygame_patches, mocker):
        """get_name should fall back to cached name on pygame.error."""
        proxy, _, mock_joystick = self._create_mock_proxy(mocker)

        mock_joystick.get_name.side_effect = pygame.error('joystick disconnected')

        name = proxy.get_name()
        assert name == 'Test Joystick'

    def test_proxy_get_init(self, mock_pygame_patches, mocker):
        """get_init should return the cached init status."""
        proxy, _, _ = self._create_mock_proxy(mocker)

        assert proxy.get_init() is True

    def test_proxy_get_numaxes(self, mock_pygame_patches, mocker):
        """get_numaxes should return the number of axes."""
        proxy, _, _ = self._create_mock_proxy(mocker)

        assert proxy.get_numaxes() == 4

    def test_proxy_get_numballs(self, mock_pygame_patches, mocker):
        """get_numballs should return the number of trackballs."""
        proxy, _, _ = self._create_mock_proxy(mocker)

        assert proxy.get_numballs() == 1

    def test_proxy_get_numbuttons(self, mock_pygame_patches, mocker):
        """get_numbuttons should return the number of buttons."""
        proxy, _, _ = self._create_mock_proxy(mocker)

        assert proxy.get_numbuttons() == 10

    def test_proxy_get_numhats(self, mock_pygame_patches, mocker):
        """get_numhats should return the number of hats."""
        proxy, _, _ = self._create_mock_proxy(mocker)

        assert proxy.get_numhats() == 1

    def test_proxy_str_representation(self, mock_pygame_patches, mocker):
        """str() should return a multi-line joystick info string."""
        proxy, _, _ = self._create_mock_proxy(mocker)

        result = str(proxy)
        assert 'Joystick Name:' in result
        assert 'Joystick Id:' in result
        assert 'Joystick Inited:' in result
        assert 'Joystick Axis Count:' in result
        assert 'Joystick Trackball Count:' in result
        assert 'Joystick Button Count:' in result
        assert 'Joystick Hat Count:' in result

    def test_proxy_repr(self, mock_pygame_patches, mocker):
        """repr() should return repr of underlying joystick."""
        proxy, _, _ = self._create_mock_proxy(mocker)

        result = repr(proxy)
        assert isinstance(result, str)

    def _create_mock_joystick_class(self, mocker, mock_joystick):
        """Create and patch a mock Joystick class that handles from_instance_id."""
        mock_joystick_class = mocker.Mock()
        mock_joystick_class.return_value = mock_joystick
        mock_joystick_class.from_instance_id = mocker.Mock(return_value=mock_joystick)
        mocker.patch('pygame.joystick.Joystick', mock_joystick_class)

    def test_proxy_instance_id_preferred_over_joystick_id(self, mock_pygame_patches, mocker):
        """When instance_id is provided, it should be used as _id."""
        from glitchygames.events.joystick import JoystickEventManager

        mock_joystick = mocker.Mock()
        mock_joystick.init.return_value = None
        mock_joystick.get_init.return_value = True
        mock_joystick.get_name.return_value = 'Test'
        mock_joystick.get_guid.return_value = 'guid'
        mock_joystick.get_power_level.return_value = 'full'
        mock_joystick.get_numaxes.return_value = 2
        mock_joystick.get_numballs.return_value = 0
        mock_joystick.get_numbuttons.return_value = 4
        mock_joystick.get_numhats.return_value = 1
        mock_joystick.get_axis.return_value = 0.0
        mock_joystick.get_ball.return_value = (0, 0)
        mock_joystick.get_button.return_value = 0
        mock_joystick.get_hat.return_value = (0, 0)

        self._create_mock_joystick_class(mocker, mock_joystick)

        mock_game = mocker.Mock()
        proxy = JoystickEventManager.JoystickEventProxy(
            game=mock_game, joystick_id=5, instance_id=42
        )

        assert proxy._id == 42
        assert proxy._device_id == 5

    def test_proxy_guid_attribute_error_fallback(self, mock_pygame_patches, mocker):
        """When get_guid raises AttributeError, _guid should be None."""
        from glitchygames.events.joystick import JoystickEventManager

        mock_joystick = mocker.Mock()
        mock_joystick.init.return_value = None
        mock_joystick.get_init.return_value = True
        mock_joystick.get_name.return_value = 'Test'
        mock_joystick.get_guid.side_effect = AttributeError
        mock_joystick.get_power_level.return_value = 'full'
        mock_joystick.get_numaxes.return_value = 2
        mock_joystick.get_numballs.return_value = 0
        mock_joystick.get_numbuttons.return_value = 4
        mock_joystick.get_numhats.return_value = 1
        mock_joystick.get_axis.return_value = 0.0
        mock_joystick.get_button.return_value = 0
        mock_joystick.get_hat.return_value = (0, 0)

        mocker.patch('pygame.joystick.Joystick', return_value=mock_joystick)

        mock_game = mocker.Mock()
        proxy = JoystickEventManager.JoystickEventProxy(game=mock_game, joystick_id=0)

        assert proxy._guid is None

    def test_proxy_power_level_attribute_error_fallback(self, mock_pygame_patches, mocker):
        """When get_power_level raises AttributeError, _power_level should be None."""
        from glitchygames.events.joystick import JoystickEventManager

        mock_joystick = mocker.Mock()
        mock_joystick.init.return_value = None
        mock_joystick.get_init.return_value = True
        mock_joystick.get_name.return_value = 'Test'
        mock_joystick.get_guid.return_value = 'guid'
        mock_joystick.get_power_level.side_effect = AttributeError
        mock_joystick.get_numaxes.return_value = 2
        mock_joystick.get_numballs.return_value = 0
        mock_joystick.get_numbuttons.return_value = 4
        mock_joystick.get_numhats.return_value = 1
        mock_joystick.get_axis.return_value = 0.0
        mock_joystick.get_button.return_value = 0
        mock_joystick.get_hat.return_value = (0, 0)

        mocker.patch('pygame.joystick.Joystick', return_value=mock_joystick)

        mock_game = mocker.Mock()
        proxy = JoystickEventManager.JoystickEventProxy(game=mock_game, joystick_id=0)

        assert proxy._power_level is None


class TestJoystickEventManagerRouting:
    """Test JoystickEventManager event routing with mock joystick proxies."""

    def _create_manager_with_mock_joystick(self, mocker):
        """Create a JoystickEventManager with a mock joystick at instance_id=0.

        Returns:
            Tuple of (manager, mock_game, mock_proxy).
        """
        from glitchygames.events.joystick import JoystickEventManager

        mock_game = mocker.Mock()
        manager = JoystickEventManager(game=mock_game)

        mock_proxy = mocker.Mock()
        manager.joysticks[0] = mock_proxy

        return manager, mock_game, mock_proxy

    def test_axis_motion_routes_via_instance_id(self, mock_pygame_patches, mocker):
        """Axis motion event should route to the correct joystick via instance_id."""
        manager, _, mock_proxy = self._create_manager_with_mock_joystick(mocker)

        event = HashableEvent(pygame.JOYAXISMOTION, axis=0, value=0.5, instance_id=0)
        manager.on_joy_axis_motion_event(event)

        mock_proxy.on_joy_axis_motion_event.assert_called_once_with(event)

    def test_axis_motion_routes_via_joy_fallback(self, mock_pygame_patches, mocker):
        """Axis motion should fall back to event.joy when instance_id is missing."""
        manager, _, mock_proxy = self._create_manager_with_mock_joystick(mocker)

        event = HashableEvent(pygame.JOYAXISMOTION, axis=0, value=0.5, joy=0)
        manager.on_joy_axis_motion_event(event)

        mock_proxy.on_joy_axis_motion_event.assert_called_once_with(event)

    def test_button_down_routes_via_instance_id(self, mock_pygame_patches, mocker):
        """Button down event should route to the correct joystick."""
        manager, _, mock_proxy = self._create_manager_with_mock_joystick(mocker)

        event = HashableEvent(pygame.JOYBUTTONDOWN, button=0, instance_id=0)
        manager.on_joy_button_down_event(event)

        mock_proxy.on_joy_button_down_event.assert_called_once_with(event)

    def test_button_down_routes_via_joy_fallback(self, mock_pygame_patches, mocker):
        """Button down should fall back to event.joy when instance_id is missing."""
        manager, _, mock_proxy = self._create_manager_with_mock_joystick(mocker)

        event = HashableEvent(pygame.JOYBUTTONDOWN, button=0, joy=0)
        manager.on_joy_button_down_event(event)

        mock_proxy.on_joy_button_down_event.assert_called_once_with(event)

    def test_button_up_routes_via_instance_id(self, mock_pygame_patches, mocker):
        """Button up event should route to the correct joystick."""
        manager, _, mock_proxy = self._create_manager_with_mock_joystick(mocker)

        event = HashableEvent(pygame.JOYBUTTONUP, button=0, instance_id=0)
        manager.on_joy_button_up_event(event)

        mock_proxy.on_joy_button_up_event.assert_called_once_with(event)

    def test_button_up_routes_via_joy_fallback(self, mock_pygame_patches, mocker):
        """Button up should fall back to event.joy when instance_id is missing."""
        manager, _, mock_proxy = self._create_manager_with_mock_joystick(mocker)

        event = HashableEvent(pygame.JOYBUTTONUP, button=0, joy=0)
        manager.on_joy_button_up_event(event)

        mock_proxy.on_joy_button_up_event.assert_called_once_with(event)

    def test_hat_motion_routes_via_instance_id(self, mock_pygame_patches, mocker):
        """Hat motion event should route to the correct joystick."""
        manager, _, mock_proxy = self._create_manager_with_mock_joystick(mocker)

        event = HashableEvent(pygame.JOYHATMOTION, hat=0, value=(1, 0), instance_id=0)
        manager.on_joy_hat_motion_event(event)

        mock_proxy.on_joy_hat_motion_event.assert_called_once_with(event)

    def test_hat_motion_routes_via_joy_fallback(self, mock_pygame_patches, mocker):
        """Hat motion should fall back to event.joy when instance_id is missing."""
        manager, _, mock_proxy = self._create_manager_with_mock_joystick(mocker)

        event = HashableEvent(pygame.JOYHATMOTION, hat=0, value=(1, 0), joy=0)
        manager.on_joy_hat_motion_event(event)

        mock_proxy.on_joy_hat_motion_event.assert_called_once_with(event)

    def test_ball_motion_routes_via_instance_id(self, mock_pygame_patches, mocker):
        """Ball motion event should route to the correct joystick."""
        manager, _, mock_proxy = self._create_manager_with_mock_joystick(mocker)

        event = HashableEvent(pygame.JOYBALLMOTION, ball=0, rel=(5, -3), instance_id=0)
        manager.on_joy_ball_motion_event(event)

        mock_proxy.on_joy_ball_motion_event.assert_called_once_with(event)

    def test_ball_motion_routes_via_joy_fallback(self, mock_pygame_patches, mocker):
        """Ball motion should fall back to event.joy when instance_id is missing."""
        manager, _, mock_proxy = self._create_manager_with_mock_joystick(mocker)

        event = HashableEvent(pygame.JOYBALLMOTION, ball=0, rel=(5, -3), joy=0)
        manager.on_joy_ball_motion_event(event)

        mock_proxy.on_joy_ball_motion_event.assert_called_once_with(event)

    def test_device_added_creates_proxy(self, mock_pygame_patches, mocker):
        """Device added should create a new joystick proxy."""
        from glitchygames.events.joystick import JoystickEventManager

        mock_game = mocker.Mock()
        manager = JoystickEventManager(game=mock_game)

        # Mock the joystick so JoystickEventProxy init works
        mock_joystick = mocker.Mock()
        mock_joystick.init.return_value = None
        mock_joystick.get_init.return_value = True
        mock_joystick.get_name.return_value = 'New Joystick'
        mock_joystick.get_guid.return_value = 'guid'
        mock_joystick.get_power_level.return_value = 'full'
        mock_joystick.get_numaxes.return_value = 2
        mock_joystick.get_numballs.return_value = 0
        mock_joystick.get_numbuttons.return_value = 4
        mock_joystick.get_numhats.return_value = 1
        mock_joystick.get_axis.return_value = 0.0
        mock_joystick.get_button.return_value = 0
        mock_joystick.get_hat.return_value = (0, 0)
        mock_joystick.get_instance_id.return_value = 42
        mock_joystick.get_id.return_value = 0

        mocker.patch('pygame.joystick.Joystick', return_value=mock_joystick)

        event = HashableEvent(pygame.JOYDEVICEADDED, device_index=0, guid='guid')
        manager.on_joy_device_added_event(event)

        assert 42 in manager.joysticks

    def test_device_added_duplicate_skipped(self, mock_pygame_patches, mocker):
        """Device added for existing instance_id should skip duplicate creation."""
        from glitchygames.events.joystick import JoystickEventManager

        mock_game = mocker.Mock()
        manager = JoystickEventManager(game=mock_game)

        # Pre-add a joystick at instance_id=42
        existing_proxy = mocker.Mock()
        manager.joysticks[42] = existing_proxy

        mock_joystick = mocker.Mock()
        mock_joystick.init.return_value = None
        mock_joystick.get_instance_id.return_value = 42
        mock_joystick.get_name.return_value = 'Test'
        mock_joystick.get_guid.return_value = 'guid'
        mock_joystick.get_id.return_value = 0

        mocker.patch('pygame.joystick.Joystick', return_value=mock_joystick)

        event = HashableEvent(pygame.JOYDEVICEADDED, device_index=0, guid='guid')
        manager.on_joy_device_added_event(event)

        # The existing proxy should not be replaced
        assert manager.joysticks[42] is existing_proxy

    def test_device_removed_notifies_and_deletes(self, mock_pygame_patches, mocker):
        """Device removed should notify proxy then remove it."""
        manager, _, mock_proxy = self._create_manager_with_mock_joystick(mocker)

        event = HashableEvent(pygame.JOYDEVICEREMOVED, instance_id=0)
        manager.on_joy_device_removed_event(event)

        mock_proxy.on_joy_device_removed_event.assert_called_once_with(event)
        assert 0 not in manager.joysticks

    def test_device_removed_missing_instance_is_noop(self, mock_pygame_patches, mocker):
        """Device removed for unknown instance_id should not crash."""
        from glitchygames.events.joystick import JoystickEventManager

        mock_game = mocker.Mock()
        manager = JoystickEventManager(game=mock_game)

        event = HashableEvent(pygame.JOYDEVICEREMOVED, instance_id=999)
        # Should not raise
        manager.on_joy_device_removed_event(event)

    def test_device_added_pygame_error_fallback(self, mock_pygame_patches, mocker):
        """Device added with pygame error should fall back to device_index."""
        from glitchygames.events.joystick import JoystickEventManager

        mock_game = mocker.Mock()
        manager = JoystickEventManager(game=mock_game)

        # First Joystick call for debug info raises pygame.error
        # Second call for stable instance_id also raises
        mock_joystick = mocker.Mock()
        mock_joystick.init.side_effect = pygame.error('no joystick')

        mocker.patch('pygame.joystick.Joystick', return_value=mock_joystick)

        event = HashableEvent(pygame.JOYDEVICEADDED, device_index=7, guid='guid')

        # The first Joystick(7) call in debug section may raise, then the init
        # call for instance_id derivation raises, so it falls back to device_index
        # Since the proxy creation will also fail, let's mock the proxy constructor
        mock_proxy_instance = mocker.Mock()
        mocker.patch(
            'glitchygames.events.joystick.JoystickEventManager.JoystickEventProxy',
            return_value=mock_proxy_instance,
        )

        manager.on_joy_device_added_event(event)

        # Should have created a proxy with device_index as key
        assert 7 in manager.joysticks

    def test_manager_args_classmethod(self, mock_pygame_patches, mocker):
        """args() classmethod should return the parser with Joystick Options group."""
        import argparse

        from glitchygames.events.joystick import JoystickEventManager

        parser = argparse.ArgumentParser()
        result = JoystickEventManager.args(parser)
        assert result is parser
