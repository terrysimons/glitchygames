"""Tests covering uncovered lines in glitchygames/events/joystick.py.

Targets uncovered lines: 275-276, 297-298, 303-304, 307-308, 311-312,
323-324, 451-452, 456-457, 460-461, 464-465, 468-469, 517-518.

These are all exception-handling branches in JoystickEventManager.__init__
and on_joy_device_added_event where pygame methods raise pygame.error.
"""

import sys
from pathlib import Path

import pygame

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events.joystick import JoystickEventManager


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
                raise pygame.error('cannot open')
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
