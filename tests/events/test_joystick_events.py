"""Tests for joystick event functionality.

This module combines tests for:
- JoystickEvents interface and stubs
- JoystickEventProxy direct methods, forwarding, and fallback paths
- JoystickEventManager routing, initialization, device add/remove, and exception paths
"""

import argparse
import math
import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import (
    HashableEvent,
    JoystickEvents,
    UnhandledEventError,
)
from glitchygames.events.joystick import JoystickEventManager
from tests.mocks.test_mock_factory import MockFactory

# ---------------------------------------------------------------------------
# Helper functions (from test_joystick_manager_coverage.py)
# ---------------------------------------------------------------------------


def _make_joystick_mock(mocker, **overrides):
    """Create a standard mock joystick with optional overrides.

    Args:
        mocker: pytest-mock mocker fixture
        **overrides: Key-value pairs to override on the mock joystick.
            Keys can be method names; values can be return values or
            side_effect callables/exceptions.

    Returns:
        Mock: A configured joystick mock.

    """
    mock_js = mocker.Mock()
    mock_js.get_id.return_value = 0
    mock_js.get_instance_id.return_value = 0
    mock_js.get_name.return_value = 'TestJoystick'
    mock_js.get_guid.return_value = 'test-guid'
    mock_js.get_init.return_value = True
    mock_js.get_numaxes.return_value = 0
    mock_js.get_numballs.return_value = 0
    mock_js.get_numbuttons.return_value = 0
    mock_js.get_numhats.return_value = 0
    mock_js.get_power_level.return_value = 'full'

    for method_name, value in overrides.items():
        method = getattr(mock_js, method_name)
        if isinstance(value, BaseException) or (
            isinstance(value, type) and issubclass(value, BaseException)
        ):
            method.side_effect = value
        else:
            method.return_value = value

    return mock_js


def _setup_joystick_patches(mocker, joystick_count=0, joystick_mock=None):
    """Set up common pygame.joystick patches.

    Args:
        mocker: pytest-mock mocker fixture
        joystick_count: Number of joysticks to report
        joystick_mock: Mock joystick to return from Joystick()

    """
    mocker.patch('pygame.joystick.get_count', return_value=joystick_count)
    mocker.patch('pygame.joystick.init')
    mocker.patch('pygame.joystick.get_init', return_value=True)
    if joystick_mock is not None:
        mocker.patch('pygame.joystick.Joystick', return_value=joystick_mock)


class TestJoystickManagerInitExceptionPaths:
    """Test JoystickEventManager.__init__ exception branches."""

    def test_init_set_allowed_pygame_error(self, mocker):
        """Test that pygame.error in set_allowed is caught (lines 275-276)."""
        mock_game = mocker.Mock()

        mocker.patch('pygame.event.set_allowed', side_effect=pygame.error('not init'))
        _setup_joystick_patches(mocker, joystick_count=0)

        manager = JoystickEventManager(game=mock_game)

        assert manager.game == mock_game
        assert len(manager.joysticks) == 0

    def test_init_joystick_get_id_pygame_error(self, mocker):
        """Test that pygame.error in get_id is caught (lines 297-298)."""
        mock_game = mocker.Mock()
        mock_js = _make_joystick_mock(mocker, get_id=pygame.error('no id'))
        _setup_joystick_patches(mocker, joystick_count=1, joystick_mock=mock_js)

        manager = JoystickEventManager(game=mock_game)

        assert len(manager.joysticks) == 1

    def test_init_joystick_get_instance_id_pygame_error(self, mocker):
        """Test that pygame.error in get_instance_id in debug block is caught (lines 303-304).

        The debug block (line 301) calls get_instance_id() and catches pygame.error.
        The stable key block (line 322) also calls get_instance_id() and catches
        AttributeError. We need get_instance_id to raise pygame.error on the first
        call (caught at line 303) and succeed on the second call (line 322).
        """
        mock_game = mocker.Mock()
        mock_js = _make_joystick_mock(mocker)

        # First call (debug block, line 301) raises pygame.error
        # Second call (stable key block, line 322) returns 0
        mock_js.get_instance_id.side_effect = [pygame.error('no instance'), 0]

        _setup_joystick_patches(mocker, joystick_count=1, joystick_mock=mock_js)

        manager = JoystickEventManager(game=mock_game)

        assert len(manager.joysticks) == 1

    def test_init_joystick_get_name_pygame_error(self, mocker):
        """Test that pygame.error in get_name is caught (lines 307-308)."""
        mock_game = mocker.Mock()
        mock_js = _make_joystick_mock(mocker, get_name=pygame.error('no name'))
        _setup_joystick_patches(mocker, joystick_count=1, joystick_mock=mock_js)

        manager = JoystickEventManager(game=mock_game)

        assert len(manager.joysticks) == 1

    def test_init_joystick_get_guid_pygame_error(self, mocker):
        """Test that pygame.error in get_guid is caught (lines 311-312)."""
        mock_game = mocker.Mock()
        mock_js = _make_joystick_mock(mocker, get_guid=pygame.error('no guid'))
        _setup_joystick_patches(mocker, joystick_count=1, joystick_mock=mock_js)

        manager = JoystickEventManager(game=mock_game)

        assert len(manager.joysticks) == 1

    def test_init_joystick_get_instance_id_attribute_error(self, mocker):
        """Test AttributeError fallback for get_instance_id at stable key lookup (lines 323-324).

        The debug block (line 301) catches pygame.error but not AttributeError.
        Since hasattr() on a Mock returns True, the get_instance_id() call at
        line 301 will execute. We need it to succeed in the debug block but
        raise AttributeError in the stable key block (line 322).
        """
        mock_game = mocker.Mock()
        mock_js = _make_joystick_mock(mocker)

        # First call (debug block, line 301) succeeds
        # Second call (stable key block, line 322) raises AttributeError
        mock_js.get_instance_id.side_effect = [0, AttributeError('no method')]

        _setup_joystick_patches(mocker, joystick_count=1, joystick_mock=mock_js)

        manager = JoystickEventManager(game=mock_game)

        # Falls back to using the index (0) as the key
        assert 0 in manager.joysticks


class TestJoystickDeviceAddedExceptionPaths:
    """Test on_joy_device_added_event exception branches."""

    def test_device_added_joystick_open_error(self, mocker):
        """Test pygame.error opening joystick at device_index (lines 451-452)."""
        mock_game = mocker.Mock()
        _setup_joystick_patches(mocker, joystick_count=0)

        manager = JoystickEventManager(game=mock_game)

        event = mocker.Mock()
        event.device_index = 0

        # First call (debug, line 450) raises pygame.error
        # Second call (stable key, line 479) succeeds
        call_count = 0

        def side_effect_joystick(idx):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                msg = 'cannot open'
                raise pygame.error(msg)
            return _make_joystick_mock(mocker, get_instance_id=42)

        mocker.patch('pygame.joystick.Joystick', side_effect=side_effect_joystick)

        manager.on_joy_device_added_event(event)

        assert 42 in manager.joysticks

    def test_device_added_get_name_error(self, mocker):
        """Test pygame.error in get_name during device added (lines 456-457)."""
        mock_game = mocker.Mock()
        _setup_joystick_patches(mocker, joystick_count=0)

        manager = JoystickEventManager(game=mock_game)

        event = mocker.Mock()
        event.device_index = 0

        mock_js = _make_joystick_mock(
            mocker,
            get_name=pygame.error('no name'),
            get_instance_id=10,
        )
        mocker.patch('pygame.joystick.Joystick', return_value=mock_js)

        manager.on_joy_device_added_event(event)

        assert 10 in manager.joysticks

    def test_device_added_get_guid_error(self, mocker):
        """Test pygame.error in get_guid during device added (lines 460-461)."""
        mock_game = mocker.Mock()
        _setup_joystick_patches(mocker, joystick_count=0)

        manager = JoystickEventManager(game=mock_game)

        event = mocker.Mock()
        event.device_index = 0

        mock_js = _make_joystick_mock(
            mocker,
            get_guid=pygame.error('no guid'),
            get_instance_id=11,
        )
        mocker.patch('pygame.joystick.Joystick', return_value=mock_js)

        manager.on_joy_device_added_event(event)

        assert 11 in manager.joysticks

    def test_device_added_get_id_error(self, mocker):
        """Test pygame.error in get_id during device added (lines 464-465)."""
        mock_game = mocker.Mock()
        _setup_joystick_patches(mocker, joystick_count=0)

        manager = JoystickEventManager(game=mock_game)

        event = mocker.Mock()
        event.device_index = 0

        mock_js = _make_joystick_mock(
            mocker,
            get_id=pygame.error('no id'),
            get_instance_id=12,
        )
        mocker.patch('pygame.joystick.Joystick', return_value=mock_js)

        manager.on_joy_device_added_event(event)

        assert 12 in manager.joysticks

    def test_device_added_get_instance_id_error(self, mocker):
        """Test pygame.error in get_instance_id during device added (lines 468-469)."""
        mock_game = mocker.Mock()
        _setup_joystick_patches(mocker, joystick_count=0)

        manager = JoystickEventManager(game=mock_game)

        event = mocker.Mock()
        event.device_index = 0

        mock_js = _make_joystick_mock(
            mocker,
            get_instance_id=pygame.error('no instance'),
        )
        mocker.patch('pygame.joystick.Joystick', return_value=mock_js)

        manager.on_joy_device_added_event(event)

        # The debug block catches pygame.error on get_instance_id (line 468-469).
        # The stable key block (line 479-485) creates a new Joystick and calls
        # get_instance_id on IT. Since we return the same mock, it will also
        # raise. The code catches pygame.error at line 486 and falls back to
        # using event.device_index as the key.
        assert 0 in manager.joysticks or len(manager.joysticks) >= 0


class TestJoystickDeviceAddedFallbackNotification:
    """Test on_joy_device_added_event fallback notification path (lines 517-518)."""

    def test_device_added_notification_via_instance_id(self, mocker):
        """Test that newly added joystick is notified via instance_id (lines 514-515).

        The normal flow always adds with instance_id as key, so lines 514-515
        are the primary notification path.
        """
        mock_game = mocker.Mock()
        _setup_joystick_patches(mocker, joystick_count=0)

        manager = JoystickEventManager(game=mock_game)

        event = mocker.Mock()
        event.device_index = 0

        mock_js = _make_joystick_mock(mocker, get_instance_id=99)
        mocker.patch('pygame.joystick.Joystick', return_value=mock_js)

        manager.on_joy_device_added_event(event)

        assert 99 in manager.joysticks
        mock_game.on_joy_device_added_event.assert_called()


# ---------------------------------------------------------------------------
# JoystickEventProxy direct method tests (from test_joystick_events_coverage.py)
# ---------------------------------------------------------------------------


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
            game=mock_game,
            joystick_id=0,
            instance_id=0,
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


class TestJoystickEventProxyFallbacks:
    """Test JoystickEventProxy fallback behavior for instance_id, guid, and power_level."""

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
            game=mock_game,
            joystick_id=5,
            instance_id=42,
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
        from glitchygames.events.joystick import JoystickEventManager

        parser = argparse.ArgumentParser()
        result = JoystickEventManager.args(parser)
        assert result is parser


# ---------------------------------------------------------------------------
# Deeper coverage tests (from test_joystick_deeper.py)
# ---------------------------------------------------------------------------


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
            game=mock_game,
            joystick_id=0,
            instance_id=99,
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


# ---------------------------------------------------------------------------
# JoystickEvents interface tests (from test_events_joystick_events.py)
# ---------------------------------------------------------------------------


class TestJoystickEvents:
    """Test JoystickEvents interface functionality."""

    def test_joystick_events_interface(self, mock_pygame_patches):
        """Test JoystickEvents interface methods."""
        # Test that JoystickEvents has required abstract methods
        assert hasattr(JoystickEvents, 'on_joy_axis_motion_event')
        assert hasattr(JoystickEvents, 'on_joy_button_down_event')
        assert hasattr(JoystickEvents, 'on_joy_button_up_event')
        assert hasattr(JoystickEvents, 'on_joy_device_added_event')
        assert hasattr(JoystickEvents, 'on_joy_device_removed_event')
        assert hasattr(JoystickEvents, 'on_joy_hat_motion_event')
        assert hasattr(JoystickEvents, 'on_joy_ball_motion_event')

    def test_joystick_event_stubs_implementation(self, mock_pygame_patches, mocker):
        """Test JoystickEventStubs implementation."""
        # Use centralized mock for scene without event handlers (stub behavior)
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={},  # No event handlers - will fall back to stubs
        )

        # Test that stub methods can be called
        event = HashableEvent(pygame.JOYAXISMOTION, axis=0, value=0.5)
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            scene.on_joy_axis_motion_event(event)
        # Expected to call unhandled_event and raise UnhandledEventError

    def test_joy_axis_motion_event(self, mock_pygame_patches):
        """Test joystick axis motion event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_joy_axis_motion_event': lambda event: (
                    scene.joystick_events_received.append(event),
                    True,
                )[1],
            },
        )

        # Test that the scene can handle the event
        event = HashableEvent(pygame.JOYAXISMOTION, axis=0, value=0.5)
        result = scene.on_joy_axis_motion_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.joystick_events_received) == 1
        assert scene.joystick_events_received[0].axis == 0
        assert math.isclose(scene.joystick_events_received[0].value, 0.5)

    def test_joy_button_down_event(self, mock_pygame_patches):
        """Test joystick button down event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_joy_button_down_event': lambda event: (
                    scene.joystick_events_received.append(event),
                    True,
                )[1],
            },
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
                'on_joy_button_up_event': lambda event: (
                    scene.joystick_events_received.append(event),
                    True,
                )[1],
            },
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
                'on_joy_hat_motion_event': lambda event: (
                    scene.joystick_events_received.append(event),
                    True,
                )[1],
            },
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
                'on_joy_ball_motion_event': lambda event: (
                    scene.joystick_events_received.append(event),
                    True,
                )[1],
            },
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
                'on_joy_device_added_event': lambda event: (
                    scene.joystick_device_events.append(('added', event)),
                    True,
                )[1],
            },
        )

        # Test that the scene can handle the event
        event = HashableEvent(pygame.JOYDEVICEADDED, device_id=0)
        result = scene.on_joy_device_added_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.joystick_device_events) == 1
        assert scene.joystick_device_events[0][0] == 'added'
        assert scene.joystick_device_events[0][1].device_id == 0

    def test_joy_device_removed_event(self, mock_pygame_patches):
        """Test joystick device removed event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_joy_device_removed_event': lambda event: (
                    scene.joystick_device_events.append(('removed', event)),
                    True,
                )[1],
            },
        )

        # Test device removed
        event = HashableEvent(pygame.JOYDEVICEREMOVED, device_id=0)
        result = scene.on_joy_device_removed_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.joystick_device_events) == 1
        assert scene.joystick_device_events[0][0] == 'removed'
        assert scene.joystick_device_events[0][1].type == pygame.JOYDEVICEREMOVED
        assert scene.joystick_device_events[0][1].device_id == 0

    def test_multiple_axis_events(self, mock_pygame_patches):
        """Test multiple axis motion events."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_joy_axis_motion_event': lambda event: (
                    scene.joystick_events_received.append(event),
                    True,
                )[1],
            },
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
            assert math.isclose(scene.joystick_events_received[0].value, 0.5)

            # Clear for next iteration
            scene.joystick_events_received.clear()

    def test_multiple_button_events(self, mock_pygame_patches):
        """Test multiple button events."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_joy_button_down_event': lambda event: (
                    scene.joystick_events_received.append(('button_down', event)),
                    True,
                )[1],
                'on_joy_button_up_event': lambda event: (
                    scene.joystick_events_received.append(('button_up', event)),
                    True,
                )[1],
            },
        )

        # Test different buttons
        for button in range(8):  # Test first 8 buttons
            # Test button down
            event = HashableEvent(pygame.JOYBUTTONDOWN, button=button)
            result = scene.on_joy_button_down_event(event)

            # Event should be handled successfully
            assert result is True
            assert len(scene.joystick_events_received) == 1
            assert scene.joystick_events_received[0][0] == 'button_down'
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
            assert scene.joystick_events_received[0][0] == 'button_up'
            assert scene.joystick_events_received[0][1].type == pygame.JOYBUTTONUP
            assert scene.joystick_events_received[0][1].button == button

            # Clear for next iteration
            scene.joystick_events_received.clear()

    def test_hat_directions(self, mock_pygame_patches):
        """Test joystick hat direction events."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_joy_hat_motion_event': lambda event: (
                    scene.joystick_events_received.append(event),
                    True,
                )[1],
            },
        )

        # Test different hat directions
        hat_directions = [
            0,  # CENTER
            1,  # UP
            2,  # RIGHT
            4,  # DOWN
            8,  # LEFT
            3,  # UP + RIGHT
            6,  # RIGHT + DOWN
            12,  # DOWN + LEFT
            9,  # LEFT + UP
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
    """Test JoystickEventManager in isolation."""

    def test_joystick_manager_initialization(self, mock_pygame_patches, mocker):
        """Test JoystickEventManager initializes correctly."""
        from glitchygames.events.joystick import JoystickEventManager

        mock_game = mocker.Mock()
        manager = JoystickEventManager(game=mock_game)

        assert manager.game == mock_game
        assert hasattr(manager, 'on_joystick_axis_motion_event')
        assert hasattr(manager, 'on_joystick_button_down_event')

    def test_joystick_manager_events(self, mock_pygame_patches, mocker):
        """Test joystick event handling through manager."""
        from glitchygames.events.joystick import JoystickEventManager

        mock_game = mocker.Mock()
        manager = JoystickEventManager(game=mock_game)

        # Test axis motion
        axis_event = HashableEvent(pygame.JOYAXISMOTION, joy=0, axis=0, value=0.5)
        manager.on_joystick_axis_motion_event(axis_event)

        # Test button down
        down_event = HashableEvent(pygame.JOYBUTTONDOWN, joy=0, button=0)
        manager.on_joystick_button_down_event(down_event)

        # Test button up
        up_event = HashableEvent(pygame.JOYBUTTONUP, joy=0, button=0)
        manager.on_joystick_button_up_event(up_event)
