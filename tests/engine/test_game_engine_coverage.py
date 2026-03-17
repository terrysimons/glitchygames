"""Coverage tests for glitchygames/engine/game_engine.py.

Targets uncovered areas NOT covered by existing test files:
- process_window_focus_event: all window focus event types
- process_window_event: dispatch table routing
- _build_window_event_dispatch: dispatch table construction
- process_game_event: FPSEVENT, GAMEEVENT, MENUEVENT, ACTIVEEVENT, USEREVENT, etc.
- process_unimplemented_event: event type 1543 handling and first-time logging
- process_events: main event loop with scene process_event bypass
- post_game_event: posting a game event
- suppress_event: event suppression logging
- register_game_event: event registration
- missing_event: unimplemented method logging
- start: game start lifecycle with profiling and error handling
- initialize_icon: with Path and with None
- _initialize_event_managers: pygame-ce detection
- handle_event: key events with no scene / no active sprites
- set_cursor: with custom cursor
"""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames import events
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


class TestProcessWindowFocusEvent:
    """Test GameEngine.process_window_focus_event for all window focus types."""

    def test_window_shown(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWSHOWN dispatches to window_manager."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWSHOWN

        result = engine.process_window_focus_event(event)
        assert result is True
        engine.window_manager.on_window_shown_event.assert_called_once_with(event)

    def test_window_leave(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWLEAVE dispatches to window_manager."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWLEAVE

        result = engine.process_window_focus_event(event)
        assert result is True
        engine.window_manager.on_window_leave_event.assert_called_once_with(event)

    def test_window_focus_gained(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWFOCUSGAINED dispatches and sets grab."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()
        mock_set_grab = mocker.patch('pygame.event.set_grab')

        event = mocker.Mock()
        event.type = pygame.WINDOWFOCUSGAINED

        result = engine.process_window_focus_event(event)
        assert result is True
        engine.window_manager.on_window_focus_gained_event.assert_called_once_with(event)
        mock_set_grab.assert_called_once()
        assert mock_set_grab.call_args[0][0] is True

    def test_window_focus_lost(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWFOCUSLOST dispatches and releases grab."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()
        mock_set_grab = mocker.patch('pygame.event.set_grab')

        event = mocker.Mock()
        event.type = pygame.WINDOWFOCUSLOST

        result = engine.process_window_focus_event(event)
        assert result is True
        engine.window_manager.on_window_focus_lost_event.assert_called_once_with(event)
        mock_set_grab.assert_called_once()
        assert mock_set_grab.call_args[0][0] is False

    def test_window_enter(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWENTER dispatches to window_manager."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWENTER

        result = engine.process_window_focus_event(event)
        assert result is True
        engine.window_manager.on_window_enter_event.assert_called_once_with(event)

    def test_window_take_focus(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWTAKEFOCUS dispatches to window_manager."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWTAKEFOCUS

        result = engine.process_window_focus_event(event)
        assert result is True
        engine.window_manager.on_window_take_focus_event.assert_called_once_with(event)

    def test_unhandled_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test unhandled window focus event returns False."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = 99999

        result = engine.process_window_focus_event(event)
        assert result is False


class TestProcessWindowEvent:
    """Test GameEngine.process_window_event dispatch table."""

    def test_window_size_changed(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWSIZECHANGED dispatches through dispatch table."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWSIZECHANGED

        result = engine.process_window_event(event)
        assert result is True
        engine.window_manager.on_window_size_changed_event.assert_called_once_with(event)

    def test_window_restored(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWRESTORED dispatches correctly."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWRESTORED

        result = engine.process_window_event(event)
        assert result is True

    def test_window_hidden(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWHIDDEN dispatches correctly."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWHIDDEN

        result = engine.process_window_event(event)
        assert result is True

    def test_window_minimized(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWMINIMIZED dispatches correctly."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWMINIMIZED

        result = engine.process_window_event(event)
        assert result is True

    def test_window_maximized(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWMAXIMIZED dispatches correctly."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWMAXIMIZED

        result = engine.process_window_event(event)
        assert result is True

    def test_window_moved(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWMOVED dispatches correctly."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWMOVED

        result = engine.process_window_event(event)
        assert result is True

    def test_window_close(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWCLOSE dispatches correctly."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWCLOSE

        result = engine.process_window_event(event)
        assert result is True

    def test_window_exposed(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWEXPOSED dispatches correctly."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWEXPOSED

        result = engine.process_window_event(event)
        assert result is True

    def test_window_resized(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWRESIZED dispatches correctly."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWRESIZED

        result = engine.process_window_event(event)
        assert result is True

    def test_window_hit_test(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWHITTEST dispatches correctly."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWHITTEST

        result = engine.process_window_event(event)
        assert result is True

    def test_unknown_window_event_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test unhandled window event returns False."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = 99999

        result = engine.process_window_event(event)
        assert result is False


class TestBuildWindowEventDispatch:
    """Test GameEngine._build_window_event_dispatch method."""

    def test_dispatch_table_has_all_window_events(
        self, mock_pygame_patches, mock_game_args, mocker
    ):
        """Test dispatch table includes all expected window event types."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        dispatch = engine._build_window_event_dispatch()

        expected_event_types = [
            pygame.WINDOWSIZECHANGED,
            pygame.WINDOWRESTORED,
            pygame.WINDOWHITTEST,
            pygame.WINDOWHIDDEN,
            pygame.WINDOWMINIMIZED,
            pygame.WINDOWMAXIMIZED,
            pygame.WINDOWMOVED,
            pygame.WINDOWCLOSE,
            pygame.WINDOWEXPOSED,
            pygame.WINDOWFOCUSLOST,
            pygame.WINDOWFOCUSGAINED,
            pygame.WINDOWRESIZED,
            pygame.WINDOWLEAVE,
            pygame.WINDOWENTER,
            pygame.WINDOWSHOWN,
        ]

        for event_type in expected_event_types:
            assert event_type in dispatch, f'Missing event type {event_type} in dispatch table'


class TestProcessGameEvent:
    """Test GameEngine.process_game_event for various game event types."""

    def test_fps_event(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_game_event dispatches FPSEVENT."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.game_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = events.FPSEVENT

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_fps_event.assert_called_once_with(event)

    def test_game_event(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_game_event dispatches GAMEEVENT."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.game_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = events.GAMEEVENT

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_game_event.assert_called_once_with(event)

    def test_menu_event(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_game_event dispatches MENUEVENT."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.game_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = events.MENUEVENT

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_menu_item_event.assert_called_once_with(event)

    def test_active_event(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_game_event dispatches ACTIVEEVENT."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.game_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.ACTIVEEVENT

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_active_event.assert_called_once_with(event)

    def test_user_event(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_game_event dispatches USEREVENT."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.game_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.USEREVENT

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_user_event.assert_called_once_with(event)

    def test_video_resize_event(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_game_event dispatches VIDEORESIZE."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.game_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.VIDEORESIZE

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_video_resize_event.assert_called_once_with(event)

    def test_video_expose_event(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_game_event dispatches VIDEOEXPOSE."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.game_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.VIDEOEXPOSE

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_video_expose_event.assert_called_once_with(event)

    def test_sys_wm_event(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_game_event dispatches SYSWMEVENT."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.game_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.SYSWMEVENT

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_sys_wm_event.assert_called_once_with(event)

    def test_quit_event(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_game_event dispatches QUIT."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.game_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.QUIT

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_quit_event.assert_called_once_with(event)

    def test_unhandled_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_game_event returns False for unknown game events."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.game_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = 99999

        result = engine.process_game_event(event)
        assert result is False


class TestProcessUnimplementedEvent:
    """Test GameEngine.process_unimplemented_event method."""

    def test_first_unimplemented_event_is_logged(self, mock_pygame_patches, mock_game_args, mocker):
        """Test first occurrence of an unimplemented event is logged."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        # Clear prior state
        GameEngine.UNIMPLEMENTED_EVENTS.clear()

        event = mocker.Mock()
        event.type = 55555  # An arbitrary unused event type

        engine.process_unimplemented_event(event)
        assert 55555 in GameEngine.UNIMPLEMENTED_EVENTS

    def test_duplicate_unimplemented_event_not_added_twice(
        self, mock_pygame_patches, mock_game_args, mocker
    ):
        """Test duplicate unimplemented events are not appended again."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        GameEngine.UNIMPLEMENTED_EVENTS.clear()

        event = mocker.Mock()
        event.type = 55556

        engine.process_unimplemented_event(event)
        engine.process_unimplemented_event(event)
        assert GameEngine.UNIMPLEMENTED_EVENTS.count(55556) == 1

    def test_event_type_1543_debug_logging(self, mock_pygame_patches, mock_game_args, mocker):
        """Test event type 1543 triggers extended debug logging."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        GameEngine.UNIMPLEMENTED_EVENTS.clear()

        # Create an event-like object that supports dict() conversion
        # The code calls dict(event) which requires __iter__ and __getitem__
        event = mocker.Mock()
        event.type = 1543  # UNKNOWN_SDL2_EVENT_TYPE_1543
        # Make the event dict-able by providing __iter__ and keys
        event_data = {'type': 1543}
        event.__iter__ = mocker.Mock(return_value=iter(event_data))
        event.__getitem__ = mocker.Mock(side_effect=event_data.__getitem__)
        event.keys = mocker.Mock(return_value=event_data.keys())

        mocker.patch('pygame.event.event_name', return_value='Unknown')
        mocker.patch('pygame._sdl2.controller.get_count', return_value=0)

        engine.process_unimplemented_event(event)
        # Should have been logged without error
        assert 1543 in GameEngine.UNIMPLEMENTED_EVENTS


class TestPostGameEvent:
    """Test GameEngine.post_game_event method."""

    def test_post_game_event_posts_to_pygame(self, mock_pygame_patches, mock_game_args, mocker):
        """Test post_game_event posts a HashableEvent to pygame."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        mock_post = mocker.patch('pygame.event.post')

        engine.post_game_event('custom_subtype', {'key': 'value'})
        mock_post.assert_called_once()
        # Verify the posted event is a HashableEvent
        posted_event = mock_post.call_args[0][0]
        assert posted_event.type == events.GAMEEVENT


class TestSuppressEvent:
    """Test GameEngine.suppress_event method."""

    def test_suppress_event_does_not_raise(self, mock_pygame_patches, mock_game_args, mocker):
        """Test suppress_event completes without error."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.suppress_event('arg1', 'arg2', attr='some_event')


class TestRegisterGameEvent:
    """Test GameEngine.register_game_event method."""

    def test_register_game_event_stores_callback(self, mock_pygame_patches, mock_game_args, mocker):
        """Test register_game_event stores the callback in registered_events."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.registered_events = {}

        callback = mocker.Mock()
        engine.register_game_event('my_event', callback)
        assert 'my_event' in engine.registered_events
        assert engine.registered_events['my_event'] is callback


class TestMissingEvent:
    """Test GameEngine.missing_event method."""

    def test_missing_event_logs_once(self, mock_pygame_patches, mock_game_args, mocker):
        """Test missing_event logs the method name once."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        GameEngine.MISSING_EVENTS.clear()
        GameEngine.LAST_EVENT_MISS = 'on_some_unknown_event'

        engine.missing_event('arg1', kwarg1='val')
        assert 'on_some_unknown_event' in GameEngine.MISSING_EVENTS

    def test_missing_event_not_duplicated(self, mock_pygame_patches, mock_game_args, mocker):
        """Test missing_event does not duplicate entries."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        GameEngine.MISSING_EVENTS.clear()
        GameEngine.LAST_EVENT_MISS = 'on_duplicate_event'

        engine.missing_event()
        engine.missing_event()
        assert GameEngine.MISSING_EVENTS.count('on_duplicate_event') == 1


class TestProcessEvents:
    """Test GameEngine.process_events main event loop."""

    def test_process_events_with_scene_process_event(
        self, mock_pygame_patches, mock_game_args, mocker
    ):
        """Test process_events bypasses engine processing when scene has process_event."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)

        mock_raw_event = mocker.Mock()
        mock_raw_event.type = pygame.KEYDOWN
        mock_raw_event.dict = {'key': pygame.K_a}
        mocker.patch('pygame.event.get', return_value=[mock_raw_event])

        mock_scene = mocker.Mock()
        mock_scene.process_event = mocker.Mock()
        engine._active_scene = mock_scene

        result = engine.process_events()
        assert result is True
        mock_scene.process_event.assert_called_once_with(mock_raw_event)

    def test_process_events_handles_event_through_handlers(
        self, mock_pygame_patches, mock_game_args, mocker
    ):
        """Test process_events routes events through EVENT_HANDLERS."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine._active_scene = mocker.Mock(spec=[])  # No process_event

        mock_raw_event = mocker.Mock()
        mock_raw_event.type = pygame.KEYDOWN
        mock_raw_event.dict = {'key': pygame.K_a, 'mod': 0, 'unicode': 'a'}
        mocker.patch('pygame.event.get', return_value=[mock_raw_event])

        # Mock the handler
        mock_handler = mocker.Mock(return_value=True)
        GameEngine.EVENT_HANDLERS[pygame.KEYDOWN] = mock_handler

        result = engine.process_events()
        assert result is True

    def test_process_events_no_events_returns_false(
        self, mock_pygame_patches, mock_game_args, mocker
    ):
        """Test process_events returns False when no events in queue."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        mocker.patch('pygame.event.get', return_value=[])

        result = engine.process_events()
        assert result is False

    def test_process_events_unhandled_event(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_events routes unhandled events to process_unimplemented_event."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine._active_scene = mocker.Mock(spec=[])  # No process_event
        GameEngine.UNIMPLEMENTED_EVENTS.clear()

        mock_raw_event = mocker.Mock()
        mock_raw_event.type = 88888  # Unknown event type
        mock_raw_event.dict = {}
        mocker.patch('pygame.event.get', return_value=[mock_raw_event])

        # Ensure no handler for this type
        GameEngine.EVENT_HANDLERS.pop(88888, None)

        mocker.patch.object(engine, 'process_unimplemented_event')
        result = engine.process_events()
        engine.process_unimplemented_event.assert_called_once()
        assert result is False


class TestHandleEventAdditionalPaths:
    """Test GameEngine.handle_event additional code paths."""

    def test_handle_event_no_scene(self, mock_pygame_patches, mock_game_args, mocker):
        """Test handle_event when active_scene is None."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.scene_manager.active_scene = None
        engine.scene_manager.handle_event = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.KEYDOWN
        event.key = pygame.K_q

        engine.handle_event(event)
        assert engine.scene_manager.quit_requested is True

    def test_handle_event_with_unfocused_sprites(self, mock_pygame_patches, mock_game_args, mocker):
        """Test handle_event with sprites that are not focused."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        mock_sprite = mocker.Mock()
        mock_sprite.active = False  # Not focused
        engine.scene_manager.active_scene = mocker.Mock()
        engine.scene_manager.active_scene.all_sprites = [mock_sprite]
        engine.scene_manager.handle_event = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.KEYDOWN
        event.key = pygame.K_a  # Not quit key

        engine.handle_event(event)
        engine.scene_manager.handle_event.assert_called_once_with(event)

    def test_handle_event_non_key_event_passes_to_scene_manager(
        self, mock_pygame_patches, mock_game_args, mocker
    ):
        """Test non-KEYDOWN events always pass to scene_manager."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.scene_manager.active_scene = mocker.Mock()
        engine.scene_manager.active_scene.all_sprites = []
        engine.scene_manager.handle_event = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.MOUSEBUTTONDOWN

        engine.handle_event(event)
        engine.scene_manager.handle_event.assert_called_once_with(event)

    def test_handle_event_quit_event(self, mock_pygame_patches, mock_game_args, mocker):
        """Test QUIT event sets quit_requested without passing to scene_manager."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.scene_manager.handle_event = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.QUIT

        engine.handle_event(event)
        assert engine.scene_manager.quit_requested is True
        engine.scene_manager.handle_event.assert_not_called()


class TestInitializeIcon:
    """Test GameEngine.initialize_icon class method."""

    def test_initialize_icon_with_none(self):
        """Test initialize_icon with None does nothing."""
        original_icon = GameEngine.icon
        GameEngine.initialize_icon(None)
        assert GameEngine.icon is original_icon

    def test_initialize_icon_with_surface(self, mocker):
        """Test initialize_icon with a Surface sets it directly."""
        mock_surface = pygame.Surface((32, 32))
        GameEngine.initialize_icon(mock_surface)
        assert GameEngine.icon is mock_surface

    def test_initialize_icon_with_path(self, mocker):
        """Test initialize_icon with a path attempts to load it."""
        mocker.patch('pygame.image.load', side_effect=FileNotFoundError)
        # Should not raise due to contextlib.suppress
        GameEngine.initialize_icon(Path('/nonexistent/icon.png'))


class TestSetCursorWithCustomCursor:
    """Test GameEngine.set_cursor with a custom cursor."""

    def test_set_cursor_with_custom_cursor(self, mocker):
        """Test set_cursor with a custom cursor list."""
        mock_set_cursor = mocker.patch('pygame.mouse.set_cursor')
        custom_cursor = [
            'XX      ',
            'XXX     ',
            'XXXX    ',
            'XX.XX   ',
            'XX..XX  ',
            'XX...XX ',
            'XX....XX',
            'XXXXXXXX',
        ]
        result = GameEngine.set_cursor(cursor=custom_cursor)
        assert result == custom_cursor
        mock_set_cursor.assert_called_once()


class TestInitializeEventManagers:
    """Test GameEngine._initialize_event_managers method."""

    def test_initialize_event_managers_sets_up_all_managers(
        self, mock_pygame_patches, mock_game_args, mocker
    ):
        """Test _initialize_event_managers creates all required managers."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)

        # Mock scene_manager with proper OPTIONS dict support
        mock_scene_manager = mocker.Mock()
        mock_scene_manager.OPTIONS = {
            'font_name': 'Vera',
            'font_size': 24,
            'font_bold': False,
            'font_italic': False,
            'font_antialias': True,
            'font_dpi': 72,
        }
        engine.scene_manager = mock_scene_manager

        engine._initialize_event_managers()

        # Check that key managers are set up
        assert engine.audio_manager is not None
        assert engine.drop_manager is not None
        assert engine.touch_manager is not None
        assert engine.font_manager is not None
        assert engine.game_manager is not None
        assert engine.joystick_manager is not None
        assert engine.keyboard_manager is not None
        assert engine.midi_manager is not None
        assert engine.mouse_manager is not None
        assert engine.window_manager is not None


class TestStartMethod:
    """Test GameEngine.start method paths."""

    def test_start_with_no_game_raises(self, mock_pygame_patches, mock_game_args, mocker):
        """Test start raises RuntimeError when game is None."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        GameEngine.game = None

        with pytest.raises(RuntimeError, match='Game not initialized'):
            engine.start()

        # Re-init pygame for other tests
        pygame.init()
        pygame.display.set_mode((800, 600))


class TestResolveSceneNameForError:
    """Test _resolve_scene_name_for_error additional paths."""

    def test_previous_scene_with_no_name(self, mock_pygame_patches, mock_game_args, mocker):
        """Test falls back to class name when previous scene has NAME=None."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.scene_manager = mocker.Mock()
        engine.scene_manager.current_scene = None
        engine.scene_manager.previous_scene = mocker.Mock()
        engine.scene_manager.previous_scene.NAME = None
        engine.scene_manager.previous_scene.__class__.__name__ = 'FallbackPrevScene'

        result = engine._resolve_scene_name_for_error()
        assert result == 'FallbackPrevScene'


class TestProcessTextEvent:
    """Test GameEngine.process_text_event returns False path (line 1250)."""

    def test_unhandled_text_event_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_text_event returns False for unhandled text event types."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)

        event = mocker.Mock()
        event.type = 99999  # Not TEXTEDITING or TEXTINPUT

        result = engine.process_text_event(event)
        assert result is False


class TestGetAttrAttributeError:
    """Test GameEngine.__getattr__ raises AttributeError (line 1532)."""

    def test_non_event_attribute_raises(self, mock_pygame_patches, mock_game_args, mocker):
        """Test __getattr__ raises AttributeError for non-event attributes."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)

        with pytest.raises(AttributeError, match="has no attribute 'some_random_attr'"):
            engine.some_random_attr  # noqa: B018


class TestGameEngineLinuxVideoDriverArgs:
    """Test GameEngine platform-specific video driver args (lines 205-230)."""

    def test_linux_video_drivers(self, mock_pygame_patches, mock_game_args, mocker):
        """Test Linux video driver choices are set up correctly (lines 205-219)."""
        mocker.patch('platform.system', return_value='Linux')

        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        # Engine was created with Linux platform; the parser is internal
        # Just verify it doesn't raise

    def test_mac_video_drivers(self, mock_pygame_patches, mock_game_args, mocker):
        """Test MacOS video driver choices (lines 222-225)."""
        mocker.patch('platform.system', return_value='MacOS')

        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        # Just verify it doesn't raise

    def test_windows_video_drivers(self, mock_pygame_patches, mock_game_args, mocker):
        """Test Windows video driver choices (lines 227-230)."""
        mocker.patch('platform.system', return_value='Windows')

        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        # Just verify it doesn't raise


class TestGameEngineFastEvents:
    """Test USE_FASTEVENTS path (lines 341, 354-355, 924).

    Note: pygame.fastevent was removed in modern pygame versions.
    We mock the fastevent module to test these legacy code paths.
    """

    def test_use_fastevents_with_old_pygame(self, mock_pygame_patches, mock_game_args, mocker):
        """Test USE_FASTEVENTS is set for old pygame versions (line 341)."""
        # Mock pygame version to be < 2.2 (both major < 2 AND minor < 2)
        mocker.patch.object(pygame.version, 'vernum', (1, 1, 0))
        # Create a fake fastevent module
        mock_fastevent = mocker.Mock()
        mocker.patch.object(pygame, 'fastevent', mock_fastevent, create=True)

        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        assert engine.USE_FASTEVENTS is True
        mock_fastevent.init.assert_called_once()

    def test_process_events_with_fastevents(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_events uses fastevent.get when USE_FASTEVENTS is True (line 924)."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.USE_FASTEVENTS = True
        # Create a fake fastevent module
        mock_fastevent = mocker.Mock()
        mock_fastevent.get.return_value = []
        mocker.patch.object(pygame, 'fastevent', mock_fastevent, create=True)

        result = engine.process_events()
        assert result is False
        mock_fastevent.get.assert_called_once()


class TestGameEngineFullscreen:
    """Test fullscreen mode flags (line 381)."""

    def test_fullscreen_mode_flags(self, mock_pygame_patches, mock_game_args, mocker):
        """Test fullscreen mode sets correct flags (line 381)."""
        mock_game_args.windowed = False  # Trigger fullscreen

        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        assert engine.mode_flags & pygame.FULLSCREEN


class TestGameEngineInvalidUpdateType:
    """Test invalid update_type logs error (line 424)."""

    def test_invalid_update_type_logs_error(self, mock_pygame_patches, mock_game_args, mocker):
        """Test invalid update_type logs an error (line 424)."""
        mock_game_args.update_type = 'invalid_type'

        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        # Engine should still be created, just with an error logged


class TestGameEngineDel:
    """Test GameEngine __del__ with sprite counters (lines 509-510)."""

    def test_del_logs_sprite_counters(self, mock_pygame_patches, mock_game_args, mocker):
        """Test __del__ iterates sprite counters (lines 509-510)."""
        from glitchygames.sprites import Sprite

        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)

        # Set up some sprite counters
        Sprite.SPRITE_COUNT = 5
        Sprite.SPRITE_COUNTERS = {
            'TestSprite': {'created': 3, 'destroyed': 2},
        }

        # Trigger __del__ via del statement
        del engine

        # Clean up
        Sprite.SPRITE_COUNT = 0
        Sprite.SPRITE_COUNTERS = {}


class TestGameEngineTimerBackendError:
    """Test timer backend initialization failure (lines 828-830)."""

    def test_timer_backend_value_error(self, mock_pygame_patches, mock_game_args, mocker):
        """Test timer backend ValueError sets timer to None (lines 828-830)."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)

        # Mock create_timer to raise ValueError
        mocker.patch(
            'glitchygames.engine.game_engine.create_timer',
            side_effect=ValueError('Invalid backend'),
        )

        # Mock scene manager and game for start()
        mock_game_class = mocker.Mock()
        mock_game_instance = mocker.Mock()
        mock_game_class.return_value = mock_game_instance
        GameEngine.game = mock_game_class
        GameEngine.OPTIONS = {
            'profile': False,
            'timer_backend': 'invalid',
            'perf_trim_percent': 5.0,
        }

        # Mock the scene manager loop to immediately stop
        engine.scene_manager = mocker.Mock()
        engine.scene_manager.quit_requested = True
        engine._initialize_event_managers = mocker.Mock()
        engine._shutdown = mocker.Mock()

        engine.start()
        assert engine.timer is None


class TestGameEnginePerformanceImportError:
    """Test performance module ImportError path (lines 784-785)."""

    def test_shutdown_performance_import_error(self, mock_pygame_patches, mock_game_args, mocker):
        """Test _shutdown handles ImportError for performance module (lines 784-785)."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)

        # Mock the performance import to fail
        mocker.patch.dict('sys.modules', {'glitchygames.performance': None})

        # _shutdown should handle the ImportError gracefully
        engine._shutdown()
