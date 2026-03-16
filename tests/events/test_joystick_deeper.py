"""Deeper coverage tests for glitchygames/events/joystick.py.

Targets areas NOT covered by test_joystick_events_coverage.py:
- JoystickEventProxy initialization without instance_id (joystick_id only)
- JoystickEventProxy fallback when from_instance_id fails
- JoystickEventManager.__init__ with existing joysticks
- JoystickEventManager.on_joy_device_added_event fallback to device_index
- JoystickEventManager event routing via joy attribute (additional fallback cases)
"""

import sys
from pathlib import Path

import pygame

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import HashableEvent
from glitchygames.events.joystick import JoystickEventManager


class TestJoystickEventProxyWithoutInstanceId:
    """Test JoystickEventProxy initialization without instance_id."""

    def test_proxy_uses_joystick_id_when_no_instance_id(self, mock_pygame_patches, mocker):
        """Test proxy uses joystick_id as _id when instance_id is None."""
        mock_joystick = mocker.Mock()
        mock_joystick.init.return_value = None
        mock_joystick.get_init.return_value = True
        mock_joystick.get_name.return_value = 'NoInstance Joystick'
        mock_joystick.get_guid.return_value = 'guid-no-instance'
        mock_joystick.get_power_level.return_value = 'full'
        mock_joystick.get_numaxes.return_value = 2
        mock_joystick.get_numballs.return_value = 0
        mock_joystick.get_numbuttons.return_value = 4
        mock_joystick.get_numhats.return_value = 1
        mock_joystick.get_axis.return_value = 0.0
        mock_joystick.get_ball.return_value = (0, 0)
        mock_joystick.get_button.return_value = 0
        mock_joystick.get_hat.return_value = (0, 0)

        mocker.patch('pygame.joystick.Joystick', return_value=mock_joystick)

        mock_game = mocker.Mock()
        proxy = JoystickEventManager.JoystickEventProxy(game=mock_game, joystick_id=3)

        # When instance_id is None (default), should use joystick_id
        assert proxy._id == 3
        assert proxy._device_id == 3


class TestJoystickEventProxyFromInstanceIdFallback:
    """Test JoystickEventProxy falls back when from_instance_id raises error."""

    def test_proxy_falls_back_to_joystick_index_on_error(self, mock_pygame_patches, mocker):
        """Test proxy falls back to Joystick(joystick_id) when from_instance_id fails."""
        mock_joystick = mocker.Mock()
        mock_joystick.init.return_value = None
        mock_joystick.get_init.return_value = True
        mock_joystick.get_name.return_value = 'Fallback Joystick'
        mock_joystick.get_guid.return_value = 'guid-fallback'
        mock_joystick.get_power_level.return_value = 'full'
        mock_joystick.get_numaxes.return_value = 2
        mock_joystick.get_numballs.return_value = 0
        mock_joystick.get_numbuttons.return_value = 4
        mock_joystick.get_numhats.return_value = 1
        mock_joystick.get_axis.return_value = 0.0
        mock_joystick.get_ball.return_value = (0, 0)
        mock_joystick.get_button.return_value = 0
        mock_joystick.get_hat.return_value = (0, 0)

        mock_joystick_class = mocker.Mock()
        # from_instance_id raises error, regular constructor works
        mock_joystick_class.from_instance_id = mocker.Mock(side_effect=pygame.error('no joystick'))
        mock_joystick_class.return_value = mock_joystick
        mocker.patch('pygame.joystick.Joystick', mock_joystick_class)

        mock_game = mocker.Mock()
        proxy = JoystickEventManager.JoystickEventProxy(
            game=mock_game, joystick_id=0, instance_id=99
        )

        # Should still work even though from_instance_id failed
        assert proxy._id == 99
        assert proxy.get_name() == 'Fallback Joystick'


class TestJoystickEventManagerInitWithJoysticks:
    """Test JoystickEventManager.__init__ when joysticks are present."""

    def test_init_creates_proxies_for_each_joystick(self, mock_pygame_patches, mocker):
        """Test __init__ creates proxy for each connected joystick."""
        mock_joystick = mocker.Mock()
        mock_joystick.init.return_value = None
        mock_joystick.get_init.return_value = True
        mock_joystick.get_name.return_value = 'Test Controller'
        mock_joystick.get_guid.return_value = 'guid-test'
        mock_joystick.get_power_level.return_value = 'full'
        mock_joystick.get_numaxes.return_value = 2
        mock_joystick.get_numballs.return_value = 0
        mock_joystick.get_numbuttons.return_value = 4
        mock_joystick.get_numhats.return_value = 1
        mock_joystick.get_axis.return_value = 0.0
        mock_joystick.get_ball.return_value = (0, 0)
        mock_joystick.get_button.return_value = 0
        mock_joystick.get_hat.return_value = (0, 0)
        mock_joystick.get_id.return_value = 0
        mock_joystick.get_instance_id.return_value = 100

        mocker.patch('pygame.joystick.Joystick', return_value=mock_joystick)
        mocker.patch('pygame.joystick.get_count', return_value=1)
        mocker.patch('pygame.joystick.get_init', return_value=True)

        mock_game = mocker.Mock()
        manager = JoystickEventManager(game=mock_game)

        # Should have created proxy for the joystick
        assert 100 in manager.joysticks


class TestJoystickEventManagerDeviceAddedFallbackIndex:
    """Test on_joy_device_added_event device_index fallback path."""

    def test_device_added_with_instance_id(self, mock_pygame_patches, mocker):
        """Test device added uses instance_id from get_instance_id."""
        mock_game = mocker.Mock()
        manager = JoystickEventManager(game=mock_game)

        mock_joystick = mocker.Mock()
        mock_joystick.init.return_value = None
        mock_joystick.get_init.return_value = True
        mock_joystick.get_name.return_value = 'New Joystick'
        mock_joystick.get_guid.return_value = 'guid-new'
        mock_joystick.get_power_level.return_value = 'full'
        mock_joystick.get_numaxes.return_value = 2
        mock_joystick.get_numballs.return_value = 0
        mock_joystick.get_numbuttons.return_value = 4
        mock_joystick.get_numhats.return_value = 1
        mock_joystick.get_axis.return_value = 0.0
        mock_joystick.get_ball.return_value = (0, 0)
        mock_joystick.get_button.return_value = 0
        mock_joystick.get_hat.return_value = (0, 0)
        mock_joystick.get_id.return_value = 5
        mock_joystick.get_instance_id.return_value = 50

        mocker.patch('pygame.joystick.Joystick', return_value=mock_joystick)

        event = HashableEvent(pygame.JOYDEVICEADDED, device_index=5, guid='guid-new')
        manager.on_joy_device_added_event(event)

        # Should have created proxy using instance_id as key
        assert 50 in manager.joysticks


class TestJoystickEventManagerRoutingFallbacks:
    """Test JoystickEventManager routing fallback from instance_id to joy attribute."""

    def _create_manager(self, mocker):
        """Create a JoystickEventManager with mock joystick at id 0.

        Returns:
            tuple: A (manager, mock_proxy) pair for the joystick at id 0.

        """
        mock_game = mocker.Mock()
        manager = JoystickEventManager(game=mock_game)
        mock_proxy = mocker.Mock()
        manager.joysticks[0] = mock_proxy
        return manager, mock_proxy

    def test_hat_motion_routes_via_joy(self, mock_pygame_patches, mocker):
        """Test hat motion falls back to event.joy."""
        manager, mock_proxy = self._create_manager(mocker)
        event = HashableEvent(pygame.JOYHATMOTION, hat=0, value=(0, 1), joy=0)
        manager.on_joy_hat_motion_event(event)
        mock_proxy.on_joy_hat_motion_event.assert_called_once_with(event)

    def test_ball_motion_routes_via_joy(self, mock_pygame_patches, mocker):
        """Test ball motion falls back to event.joy."""
        manager, mock_proxy = self._create_manager(mocker)
        event = HashableEvent(pygame.JOYBALLMOTION, ball=0, rel=(1, -1), joy=0)
        manager.on_joy_ball_motion_event(event)
        mock_proxy.on_joy_ball_motion_event.assert_called_once_with(event)

    def test_button_up_routes_via_joy(self, mock_pygame_patches, mocker):
        """Test button up falls back to event.joy."""
        manager, mock_proxy = self._create_manager(mocker)
        event = HashableEvent(pygame.JOYBUTTONUP, button=2, joy=0)
        manager.on_joy_button_up_event(event)
        mock_proxy.on_joy_button_up_event.assert_called_once_with(event)


class TestJoystickEventManagerDeviceRemovedEdge:
    """Test on_joy_device_removed_event edge cases."""

    def test_device_removed_clears_proxy(self, mock_pygame_patches, mocker):
        """Test device removed properly clears the proxy from joysticks dict."""
        mock_game = mocker.Mock()
        manager = JoystickEventManager(game=mock_game)
        mock_proxy = mocker.Mock()
        manager.joysticks[42] = mock_proxy

        event = HashableEvent(pygame.JOYDEVICEREMOVED, instance_id=42)
        manager.on_joy_device_removed_event(event)

        mock_proxy.on_joy_device_removed_event.assert_called_once_with(event)
        assert 42 not in manager.joysticks

    def test_device_removed_nonexistent_is_safe(self, mock_pygame_patches, mocker):
        """Test device removed for nonexistent instance_id does not crash."""
        mock_game = mocker.Mock()
        manager = JoystickEventManager(game=mock_game)

        event = HashableEvent(pygame.JOYDEVICEREMOVED, instance_id=12345)
        # Should not raise
        manager.on_joy_device_removed_event(event)
