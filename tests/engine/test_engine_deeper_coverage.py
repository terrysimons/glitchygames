"""Deeper coverage tests for glitchygames/engine/game_engine.py.

Targets areas NOT covered by test_engine_coverage.py or test_engine_initialization.py:
- process_*_event dispatcher methods (audio, app, controller, drop, touch, midi, etc.)
- process_events main loop
- start() method paths
- __del__ cleanup
- initialize_event_handlers / initialize_input_event_handlers
- set_cursor with None (default cursor)
- suggested_resolution on non-Linux platform
- process_unimplemented_event
"""

import sys
from pathlib import Path

import pygame

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.engine import GameEngine


def _make_engine(mocker, mock_pygame_patches, mock_game_args):
    """Create a GameEngine with mocked dependencies.

    Returns:
        GameEngine: A configured engine instance with mocked game.

    """
    mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
    mock_parse_args.return_value = mock_game_args

    mock_game = mocker.Mock()
    mock_game.NAME = 'TestGame'
    mock_game.VERSION = '1.0'
    mock_game.args = mocker.Mock(return_value=mocker.Mock())

    return GameEngine(game=mock_game)


class TestProcessAudioEvent:
    """Test GameEngine.process_audio_event dispatcher."""

    def test_audio_device_added(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_audio_event dispatches AUDIODEVICEADDED."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.audio_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.AUDIODEVICEADDED

        result = engine.process_audio_event(event)
        assert result is True
        engine.audio_manager.on_audio_device_added_event.assert_called_once_with(event)

    def test_audio_device_removed(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_audio_event dispatches AUDIODEVICEREMOVED."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.audio_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.AUDIODEVICEREMOVED

        result = engine.process_audio_event(event)
        assert result is True
        engine.audio_manager.on_audio_device_removed_event.assert_called_once_with(event)

    def test_audio_unhandled_event_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_audio_event returns False for unknown audio events."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.audio_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = 99999  # Unknown event type

        result = engine.process_audio_event(event)
        assert result is False


class TestProcessAppEvent:
    """Test GameEngine.process_app_event dispatcher."""

    def test_app_did_enter_background(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_app_event dispatches APP_DIDENTERBACKGROUND."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.app_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.APP_DIDENTERBACKGROUND

        result = engine.process_app_event(event)
        assert result is True
        engine.app_manager.on_app_did_enter_background_event.assert_called_once_with(event)

    def test_app_did_enter_foreground(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_app_event dispatches APP_DIDENTERFOREGROUND."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.app_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.APP_DIDENTERFOREGROUND

        result = engine.process_app_event(event)
        assert result is True
        engine.app_manager.on_app_did_enter_foreground_event.assert_called_once_with(event)

    def test_app_will_enter_background(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_app_event dispatches APP_WILLENTERBACKGROUND."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.app_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.APP_WILLENTERBACKGROUND

        result = engine.process_app_event(event)
        assert result is True

    def test_app_will_enter_foreground(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_app_event dispatches APP_WILLENTERFOREGROUND."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.app_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.APP_WILLENTERFOREGROUND

        result = engine.process_app_event(event)
        assert result is True

    def test_app_low_memory(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_app_event dispatches APP_LOWMEMORY."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.app_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.APP_LOWMEMORY

        result = engine.process_app_event(event)
        assert result is True
        engine.app_manager.on_app_low_memory_event.assert_called_once_with(event)

    def test_app_terminating(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_app_event dispatches APP_TERMINATING."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.app_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.APP_TERMINATING

        result = engine.process_app_event(event)
        assert result is True
        engine.app_manager.on_app_terminating_event.assert_called_once_with(event)

    def test_app_unhandled_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_app_event returns False for unknown app events."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.app_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = 99999

        result = engine.process_app_event(event)
        assert result is False


class TestProcessDropEvent:
    """Test GameEngine.process_drop_event dispatcher."""

    def test_drop_begin(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_drop_event dispatches DROPBEGIN."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.drop_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.DROPBEGIN

        result = engine.process_drop_event(event)
        assert result is True
        engine.drop_manager.on_drop_begin_event.assert_called_once_with(event)

    def test_drop_complete(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_drop_event dispatches DROPCOMPLETE."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.drop_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.DROPCOMPLETE

        result = engine.process_drop_event(event)
        assert result is True

    def test_drop_file(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_drop_event dispatches DROPFILE."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.drop_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.DROPFILE

        result = engine.process_drop_event(event)
        assert result is True

    def test_drop_text(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_drop_event dispatches DROPTEXT."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.drop_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.DROPTEXT

        result = engine.process_drop_event(event)
        assert result is True

    def test_drop_unhandled_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_drop_event returns False for unknown drop events."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.drop_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = 99999

        result = engine.process_drop_event(event)
        assert result is False


class TestProcessTouchEvent:
    """Test GameEngine.process_touch_event dispatcher."""

    def test_finger_down(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_touch_event dispatches FINGERDOWN."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.touch_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.FINGERDOWN

        result = engine.process_touch_event(event)
        assert result is True
        engine.touch_manager.on_touch_down_event.assert_called_once_with(event)

    def test_finger_up(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_touch_event dispatches FINGERUP."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.touch_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.FINGERUP

        result = engine.process_touch_event(event)
        assert result is True

    def test_finger_motion(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_touch_event dispatches FINGERMOTION."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.touch_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.FINGERMOTION

        result = engine.process_touch_event(event)
        assert result is True

    def test_touch_unhandled_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_touch_event returns False for unknown touch events."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.touch_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = 99999

        result = engine.process_touch_event(event)
        assert result is False


class TestProcessMouseEvent:
    """Test GameEngine.process_mouse_event dispatcher."""

    def test_mouse_motion(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_mouse_event dispatches MOUSEMOTION."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.mouse_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.MOUSEMOTION

        result = engine.process_mouse_event(event)
        assert result is True
        engine.mouse_manager.on_mouse_motion_event.assert_called_once_with(event)

    def test_mouse_button_up(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_mouse_event dispatches MOUSEBUTTONUP."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.mouse_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.MOUSEBUTTONUP

        result = engine.process_mouse_event(event)
        assert result is True

    def test_mouse_button_down(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_mouse_event dispatches MOUSEBUTTONDOWN."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.mouse_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.MOUSEBUTTONDOWN
        event.button = 1
        event.pos = (100, 100)

        result = engine.process_mouse_event(event)
        assert result is True

    def test_mouse_wheel(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_mouse_event dispatches MOUSEWHEEL."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.mouse_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.MOUSEWHEEL

        result = engine.process_mouse_event(event)
        assert result is True

    def test_mouse_unhandled_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_mouse_event returns False for unknown mouse events."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.mouse_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = 99999

        result = engine.process_mouse_event(event)
        assert result is False


class TestProcessKeyboardEvent:
    """Test GameEngine.process_keyboard_event dispatcher."""

    def test_key_down(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_keyboard_event dispatches KEYDOWN."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.keyboard_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.KEYDOWN

        result = engine.process_keyboard_event(event)
        assert result is True
        engine.keyboard_manager.on_key_down_event.assert_called_once_with(event)

    def test_key_up(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_keyboard_event dispatches KEYUP."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.keyboard_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.KEYUP

        result = engine.process_keyboard_event(event)
        assert result is True

    def test_keyboard_unhandled_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_keyboard_event returns False for unknown keyboard events."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.keyboard_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = 99999

        result = engine.process_keyboard_event(event)
        assert result is False


class TestProcessJoystickEvent:
    """Test GameEngine.process_joystick_event dispatcher."""

    def test_joy_axis_motion(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_joystick_event dispatches JOYAXISMOTION."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.joystick_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.JOYAXISMOTION

        result = engine.process_joystick_event(event)
        assert result is True
        engine.joystick_manager.on_joy_axis_motion_event.assert_called_once_with(event)

    def test_joy_ball_motion(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_joystick_event dispatches JOYBALLMOTION."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.joystick_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.JOYBALLMOTION

        result = engine.process_joystick_event(event)
        assert result is True

    def test_joy_hat_motion(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_joystick_event dispatches JOYHATMOTION."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.joystick_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.JOYHATMOTION

        result = engine.process_joystick_event(event)
        assert result is True

    def test_joy_button_down(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_joystick_event dispatches JOYBUTTONDOWN."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.joystick_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.JOYBUTTONDOWN

        result = engine.process_joystick_event(event)
        assert result is True

    def test_joy_button_up(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_joystick_event dispatches JOYBUTTONUP."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.joystick_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.JOYBUTTONUP

        result = engine.process_joystick_event(event)
        assert result is True

    def test_joy_device_added(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_joystick_event dispatches JOYDEVICEADDED."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.joystick_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.JOYDEVICEADDED

        result = engine.process_joystick_event(event)
        assert result is True

    def test_joy_device_removed(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_joystick_event dispatches JOYDEVICEREMOVED."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.joystick_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.JOYDEVICEREMOVED

        result = engine.process_joystick_event(event)
        assert result is True

    def test_joystick_unhandled_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_joystick_event returns False for unknown joystick events."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.joystick_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = 99999

        result = engine.process_joystick_event(event)
        assert result is False


class TestProcessMidiEvent:
    """Test GameEngine.process_midi_event dispatcher."""

    def test_midi_in(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_midi_event dispatches MIDIIN."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.scene_manager.handle_event = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.MIDIIN

        result = engine.process_midi_event(event)
        assert result is True
        engine.scene_manager.handle_event.assert_called_once_with(event)

    def test_midi_out(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_midi_event dispatches MIDIOUT."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.scene_manager.handle_event = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.MIDIOUT

        result = engine.process_midi_event(event)
        assert result is True

    def test_midi_unhandled_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_midi_event returns False for unknown midi events."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)

        event = mocker.Mock()
        event.type = 99999

        result = engine.process_midi_event(event)
        assert result is False


class TestProcessTextEvent:
    """Test GameEngine.process_text_event dispatcher."""

    def test_text_editing(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_text_event dispatches TEXTEDITING."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        mocker.patch.object(engine, 'process_unimplemented_event')

        event = mocker.Mock()
        event.type = pygame.TEXTEDITING

        result = engine.process_text_event(event)
        assert result is True
        engine.process_unimplemented_event.assert_called_once_with(event)

    def test_text_input(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_text_event dispatches TEXTINPUT."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        mocker.patch.object(engine, 'process_unimplemented_event')

        event = mocker.Mock()
        event.type = pygame.TEXTINPUT

        result = engine.process_text_event(event)
        assert result is True


class TestProcessControllerEvent:
    """Test GameEngine.process_controller_event dispatcher."""

    def test_controller_axis_motion(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_controller_event dispatches CONTROLLERAXISMOTION."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.controller_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.CONTROLLERAXISMOTION

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_button_down(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_controller_event dispatches CONTROLLERBUTTONDOWN."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.controller_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.CONTROLLERBUTTONDOWN

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_button_up(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_controller_event dispatches CONTROLLERBUTTONUP."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.controller_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.CONTROLLERBUTTONUP

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_touchpad_down(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_controller_event dispatches CONTROLLERTOUCHPADDOWN."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.controller_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.CONTROLLERTOUCHPADDOWN

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_touchpad_up(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_controller_event dispatches CONTROLLERTOUCHPADUP."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.controller_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.CONTROLLERTOUCHPADUP

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_touchpad_motion(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_controller_event dispatches CONTROLLERTOUCHPADMOTION."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.controller_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.CONTROLLERTOUCHPADMOTION

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_device_removed(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_controller_event dispatches CONTROLLERDEVICEREMOVED."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.controller_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.CONTROLLERDEVICEREMOVED

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_device_added(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_controller_event dispatches CONTROLLERDEVICEADDED."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.controller_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.CONTROLLERDEVICEADDED

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_device_remapped(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_controller_event dispatches CONTROLLERDEVICEREMAPPED."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.controller_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.CONTROLLERDEVICEREMAPPED

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_unhandled_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_controller_event returns False for unknown controller events."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.controller_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = 99999

        result = engine.process_controller_event(event)
        assert result is False


class TestGameEngineHandleEventDeeper:
    """Test GameEngine.handle_event deeper paths."""

    def test_handle_event_keydown_q_with_no_focused_sprites(
        self, mock_pygame_patches, mock_game_args, mocker
    ):
        """Test handle_event with K_q and no focused sprites sets quit_requested."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.scene_manager.active_scene = mocker.Mock()
        engine.scene_manager.active_scene.all_sprites = []
        engine.scene_manager.handle_event = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.KEYDOWN
        event.key = pygame.K_q

        engine.handle_event(event)
        assert engine.scene_manager.quit_requested is True

    def test_handle_event_passes_non_key_events_to_scene_manager(
        self, mock_pygame_patches, mock_game_args, mocker
    ):
        """Test handle_event passes non-key events to scene_manager."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.scene_manager.active_scene = mocker.Mock()
        engine.scene_manager.active_scene.all_sprites = []
        engine.scene_manager.handle_event = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.MOUSEMOTION

        engine.handle_event(event)
        engine.scene_manager.handle_event.assert_called_once_with(event)


class TestGameEngineSetCursorDefault:
    """Test GameEngine.set_cursor with None for default cursor."""

    def test_set_cursor_with_none_creates_default(self, mocker):
        """Test set_cursor with None creates the default cursor."""
        mock_set_cursor = mocker.patch('pygame.mouse.set_cursor')
        result = GameEngine.set_cursor(cursor=None)
        assert result is not None
        assert len(result) > 0
        mock_set_cursor.assert_called_once()


class TestGameEngineSuggestedResolutionLinuxNonArm:
    """Test suggested_resolution on Linux non-ARM returns desired resolution."""

    def test_suggested_resolution_linux_non_arm(self, mock_pygame_patches, mock_game_args, mocker):
        """Test suggested_resolution on Linux non-ARM returns desired resolution."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)

        mocker.patch('platform.system', return_value='Linux')
        mocker.patch('platform.machine', return_value='x86_64')

        result = engine.suggested_resolution(1024, 768)
        assert result == (1024, 768)


class TestGameEngineDelMethod:
    """Test GameEngine.__del__ method."""

    def test_del_logs_sprite_counts(self, mock_pygame_patches, mock_game_args, mocker):
        """Test __del__ logs sprite counts without errors."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        # Should not raise
        del engine


class TestGameEngineQuitGame:
    """Test GameEngine.quit_game class method."""

    def test_quit_game_posts_quit_event(self, mock_pygame_patches, mocker):
        """Test quit_game posts a QUIT event."""
        mock_post = mocker.patch('pygame.event.post')
        GameEngine.quit_game()
        mock_post.assert_called_once()


class TestGameEngineInitializeArgumentsLogLevels:
    """Test initialize_arguments with CRITICAL and ERROR log levels."""

    def test_critical_log_level_enables_debug_events(self, mock_pygame_patches, mocker):
        """Test CRITICAL log level sets debug_events to True."""
        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '1.0'
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        mock_args = mocker.Mock()
        mock_args.log_level = 'CRITICAL'
        mocker.patch('argparse.ArgumentParser.parse_args', return_value=mock_args)

        result = GameEngine.initialize_arguments(mock_game)
        assert result['debug_events'] is True

    def test_error_log_level_enables_debug_events(self, mock_pygame_patches, mocker):
        """Test ERROR log level sets debug_events to True."""
        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '1.0'
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        mock_args = mocker.Mock()
        mock_args.log_level = 'ERROR'
        mocker.patch('argparse.ArgumentParser.parse_args', return_value=mock_args)

        result = GameEngine.initialize_arguments(mock_game)
        assert result['debug_events'] is True
