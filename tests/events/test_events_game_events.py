"""Tests for game event functionality.

This module tests game event interfaces, stubs, and event handling.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import (
    GameEvents,
    HashableEvent,
    UnhandledEventError,
)

from tests.mocks.test_mock_factory import MockFactory


class TestGameEvents:
    """Test GameEvents interface functionality."""

    def test_game_events_interface(self, mock_pygame_patches):
        """Test GameEvents interface methods."""
        # Test that GameEvents has required abstract methods
        assert hasattr(GameEvents, "on_active_event")
        assert hasattr(GameEvents, "on_fps_event")
        assert hasattr(GameEvents, "on_game_event")
        assert hasattr(GameEvents, "on_menu_item_event")
        assert hasattr(GameEvents, "on_sys_wm_event")
        assert hasattr(GameEvents, "on_user_event")
        assert hasattr(GameEvents, "on_video_expose_event")
        assert hasattr(GameEvents, "on_video_resize_event")
        assert hasattr(GameEvents, "on_quit_event")
        assert hasattr(GameEvents, "on_render_device_reset_event")
        assert hasattr(GameEvents, "on_render_targets_reset_event")
        assert hasattr(GameEvents, "on_clipboard_update_event")
        assert hasattr(GameEvents, "on_locale_changed_event")

    def test_game_event_stubs_implementation(self, mock_pygame_patches):
        """Test GameEventStubs implementation."""
        # Use centralized mock for scene without event handlers (stub behavior)
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={}  # No event handlers - will fall back to stubs
        )

        # Test that stub methods can be called
        event = HashableEvent(pygame.QUIT)
        # Use pytest logger wrapper to suppress logs during successful runs
        with patch("glitchygames.events.LOG") as mock_log:
            with pytest.raises(UnhandledEventError):
                scene.on_quit_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

            # Verify the ERROR log message was called
            mock_log.error.assert_called_once()
            # Check that the log message contains the expected content
            call_args = mock_log.error.call_args[0][0]
            assert "Unhandled Event: args: Quit" in call_args

    def test_clipboard_update_event_stub(self, mock_pygame_patches):
        """Test clipboard update event stub implementation."""
        # Use centralized mock for scene without event handlers (stub behavior)
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={}  # No event handlers - will fall back to stubs
        )

        # Test that stub method can be called
        event = HashableEvent(pygame.CLIPBOARDUPDATE)
        # Use pytest logger wrapper to suppress logs during successful runs
        with patch("glitchygames.events.LOG") as mock_log:
            with pytest.raises(UnhandledEventError):
                scene.on_clipboard_update_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

            # Verify the ERROR log message was called
            mock_log.error.assert_called_once()
            # Check that the log message contains the expected content
            call_args = mock_log.error.call_args[0][0]
            assert "Unhandled Event: args: ClipboardUpdate" in call_args

    def test_locale_changed_event_stub(self, mock_pygame_patches):
        """Test locale changed event stub implementation."""
        # Use centralized mock for scene without event handlers (stub behavior)
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={}  # No event handlers - will fall back to stubs
        )

        # Test that stub method can be called
        event = HashableEvent(pygame.LOCALECHANGED)
        # Use pytest logger wrapper to suppress logs during successful runs
        with patch("glitchygames.events.LOG") as mock_log:
            with pytest.raises(UnhandledEventError):
                scene.on_locale_changed_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

            # Verify the ERROR log message was called
            mock_log.error.assert_called_once()
            # Check that the log message contains the expected content
            call_args = mock_log.error.call_args[0][0]
            assert "Unhandled Event: args: LocaleChanged" in call_args

    def test_quit_event(self, mock_pygame_patches):
        """Test quit event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_quit_event": lambda event: (scene.game_events_received.append(("quit", event)), True)[1]
            }
        )

        # Test quit event
        event = HashableEvent(pygame.QUIT)
        result = scene.on_quit_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == "quit"
        assert scene.game_events_received[0][1].type == pygame.QUIT

    def test_active_event(self, mock_pygame_patches):
        """Test active event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_active_event": lambda event: (scene.game_events_received.append(("active", event)), True)[1]
            }
        )

        # Test active event
        event = HashableEvent(pygame.ACTIVEEVENT, gain=1, state=1)
        result = scene.on_active_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == "active"
        assert scene.game_events_received[0][1].type == pygame.ACTIVEEVENT
        assert scene.game_events_received[0][1].gain == 1
        assert scene.game_events_received[0][1].state == 1

    def test_fps_event(self, mock_pygame_patches):
        """Test FPS event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_fps_event": lambda event: (scene.game_events_received.append(("fps", event)), True)[1]
            }
        )

        # Test FPS event
        event = HashableEvent(pygame.USEREVENT + 1)  # FPSEVENT
        result = scene.on_fps_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == "fps"
        assert scene.game_events_received[0][1].type == pygame.USEREVENT + 1

    def test_game_event(self, mock_pygame_patches):
        """Test game event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_game_event": lambda event: (scene.game_events_received.append(("game", event)), True)[1]
            }
        )

        # Test game event
        event = HashableEvent(pygame.USEREVENT + 2)  # GAMEEVENT
        result = scene.on_game_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == "game"
        assert scene.game_events_received[0][1].type == pygame.USEREVENT + 2

    def test_menu_item_event(self, mock_pygame_patches):
        """Test menu item event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_menu_item_event": lambda event: (scene.game_events_received.append(("menu_item", event)), True)[1]
            }
        )

        # Test menu item event
        event = HashableEvent(pygame.USEREVENT + 3)  # MENUEVENT
        result = scene.on_menu_item_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == "menu_item"
        assert scene.game_events_received[0][1].type == pygame.USEREVENT + 3

    def test_sys_wm_event(self, mock_pygame_patches):
        """Test system WM event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_sys_wm_event": lambda event: (scene.game_events_received.append(("sys_wm", event)), True)[1]
            }
        )

        # Test sys WM event
        event = HashableEvent(pygame.SYSWMEVENT)
        result = scene.on_sys_wm_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == "sys_wm"
        assert scene.game_events_received[0][1].type == pygame.SYSWMEVENT

    def test_user_event(self, mock_pygame_patches):
        """Test user event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_user_event": lambda event: (scene.game_events_received.append(("user", event)), True)[1]
            }
        )

        # Test user event
        event = HashableEvent(pygame.USEREVENT, code=1)
        result = scene.on_user_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == "user"
        assert scene.game_events_received[0][1].type == pygame.USEREVENT
        assert scene.game_events_received[0][1].code == 1

    def test_video_expose_event(self, mock_pygame_patches):
        """Test video expose event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_video_expose_event": lambda event: (scene.game_events_received.append(("video_expose", event)), True)[1]
            }
        )

        # Test video expose event
        event = HashableEvent(pygame.VIDEOEXPOSE)
        result = scene.on_video_expose_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == "video_expose"
        assert scene.game_events_received[0][1].type == pygame.VIDEOEXPOSE

    def test_video_resize_event(self, mock_pygame_patches):
        """Test video resize event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_video_resize_event": lambda event: (scene.game_events_received.append(("video_resize", event)), True)[1]
            }
        )

        # Test video resize event
        event = HashableEvent(pygame.VIDEORESIZE, w=800, h=600)
        result = scene.on_video_resize_event(event)

        # Event should be handled successfully
        assert result is True
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == "video_resize"
        assert scene.game_events_received[0][1].type == pygame.VIDEORESIZE
        assert scene.game_events_received[0][1].w == 800
        assert scene.game_events_received[0][1].h == 600

    def test_active_event_gain_states(self, mock_pygame_patches):
        """Test active event with different gain states."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_active_event": lambda event: (scene.game_events_received.append(("active", event)), True)[1]
            }
        )

        # Test different gain states
        gain_states = [
            (1, 1),   # Gained focus
            (0, 1),   # Lost focus
            (1, 2),   # Gained mouse
            (0, 2),   # Lost mouse
            (1, 4),   # Gained keyboard
            (0, 4),   # Lost keyboard
        ]

        for gain, state in gain_states:
            event = HashableEvent(pygame.ACTIVEEVENT, gain=gain, state=state)
            result = scene.on_active_event(event)

            # Event should be handled successfully
            assert result is True
            assert len(scene.game_events_received) == 1
            assert scene.game_events_received[0][0] == "active"
            assert scene.game_events_received[0][1].type == pygame.ACTIVEEVENT
            assert scene.game_events_received[0][1].gain == gain
            assert scene.game_events_received[0][1].state == state

            # Clear for next iteration
            scene.game_events_received.clear()

    def test_user_events_with_different_codes(self, mock_pygame_patches):
        """Test user events with different codes."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_user_event": lambda event: (scene.game_events_received.append(("user", event)), True)[1]
            }
        )

        # Test different user event codes
        for code in range(10):
            event = HashableEvent(pygame.USEREVENT, code=code)
            result = scene.on_user_event(event)

            # Event should be handled successfully
            assert result is True
            assert len(scene.game_events_received) == 1
            assert scene.game_events_received[0][0] == "user"
            assert scene.game_events_received[0][1].type == pygame.USEREVENT
            assert scene.game_events_received[0][1].code == code

            # Clear for next iteration
            scene.game_events_received.clear()

    def test_video_resize_with_different_dimensions(self, mock_pygame_patches):
        """Test video resize events with different dimensions."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_video_resize_event": lambda event: (scene.game_events_received.append(("video_resize", event)), True)[1]
            }
        )

        # Test different window dimensions
        dimensions = [
            (640, 480),   # VGA
            (800, 600),   # SVGA
            (1024, 768),  # XGA
            (1280, 720),  # HD
            (1920, 1080),  # Full HD
            (2560, 1440),  # 2K
            (3840, 2160),  # 4K
        ]

        for w, h in dimensions:
            event = HashableEvent(pygame.VIDEORESIZE, w=w, h=h)
            result = scene.on_video_resize_event(event)

            # Event should be handled successfully
            assert result is True
            assert len(scene.game_events_received) == 1
            assert scene.game_events_received[0][0] == "video_resize"
            assert scene.game_events_received[0][1].type == pygame.VIDEORESIZE
            assert scene.game_events_received[0][1].w == w
            assert scene.game_events_received[0][1].h == h

            # Clear for next iteration
            scene.game_events_received.clear()

    def test_custom_game_events(self, mock_pygame_patches):
        """Test custom game events."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_game_event": lambda event: (scene.game_events_received.append(("game", event)), True)[1]
            }
        )

        # Test custom game events
        custom_events = [
            HashableEvent(pygame.USEREVENT + 10, event_type="level_complete"),
            HashableEvent(pygame.USEREVENT + 11, event_type="player_died"),
            HashableEvent(pygame.USEREVENT + 12, event_type="power_up_collected"),
            HashableEvent(pygame.USEREVENT + 13, event_type="enemy_spawned"),
            HashableEvent(pygame.USEREVENT + 14, event_type="score_updated"),
        ]

        for event in custom_events:
            result = scene.on_game_event(event)

            # Event should be handled successfully
            assert result is True
            assert len(scene.game_events_received) == 1
            assert scene.game_events_received[0][0] == "game"
            assert scene.game_events_received[0][1].type == event.type
            assert scene.game_events_received[0][1].event_type == event.event_type

            # Clear for next iteration
            scene.game_events_received.clear()

    def test_menu_events_with_different_items(self, mock_pygame_patches):
        """Test menu events with different menu items."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_menu_item_event": lambda event: (scene.game_events_received.append(("menu", event)), True)[1]
            }
        )

        # Test different menu items
        menu_items = [
            "New Game",
            "Load Game",
            "Save Game",
            "Settings",
            "Help",
            "About",
            "Exit",
        ]

        for item in menu_items:
            event = HashableEvent(pygame.USEREVENT + 3, menu_item=item)
            result = scene.on_menu_item_event(event)

            # Event should be handled successfully
            assert result is True
            assert len(scene.game_events_received) == 1
            assert scene.game_events_received[0][0] == "menu"
            assert scene.game_events_received[0][1].type == pygame.USEREVENT + 3
            assert scene.game_events_received[0][1].menu_item == item

            # Clear for next iteration
            scene.game_events_received.clear()

    def test_render_device_reset_event(self, mock_pygame_patches):
        """Test render device reset event."""
        # Use centralized mock for scene with event handlers
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_render_device_reset_event": lambda event: (scene.game_events_received.append(("render_device_reset", event)), None)[1]
            }
        )

        # Test render device reset event
        event = HashableEvent(pygame.RENDER_DEVICE_RESET)
        result = scene.on_render_device_reset_event(event)

        # Verify the event was processed
        assert result is None
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == "render_device_reset"
        assert scene.game_events_received[0][1].type == pygame.RENDER_DEVICE_RESET

    def test_render_targets_reset_event(self, mock_pygame_patches):
        """Test render targets reset event."""
        # Use centralized mock for scene with event handlers
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_render_targets_reset_event": lambda event: (scene.game_events_received.append(("render_targets_reset", event)), None)[1]
            }
        )

        # Test render targets reset event
        event = HashableEvent(pygame.RENDER_TARGETS_RESET)
        result = scene.on_render_targets_reset_event(event)

        # Verify the event was processed
        assert result is None
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == "render_targets_reset"
        assert scene.game_events_received[0][1].type == pygame.RENDER_TARGETS_RESET

    def test_clipboard_update_event(self, mock_pygame_patches):
        """Test clipboard update event."""
        # Use centralized mock for scene with event handlers
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_clipboard_update_event": lambda event: (scene.game_events_received.append(("clipboard_update", event)), None)[1]
            }
        )

        # Test clipboard update event
        event = HashableEvent(pygame.CLIPBOARDUPDATE)
        result = scene.on_clipboard_update_event(event)

        # Verify the event was processed
        assert result is None
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == "clipboard_update"
        assert scene.game_events_received[0][1].type == pygame.CLIPBOARDUPDATE

    def test_locale_changed_event(self, mock_pygame_patches):
        """Test locale changed event."""
        # Use centralized mock for scene with event handlers
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_locale_changed_event": lambda event: (scene.game_events_received.append(("locale_changed", event)), None)[1]
            }
        )

        # Test locale changed event
        event = HashableEvent(pygame.LOCALECHANGED)
        result = scene.on_locale_changed_event(event)

        # Verify the event was processed
        assert result is None
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == "locale_changed"
        assert scene.game_events_received[0][1].type == pygame.LOCALECHANGED

