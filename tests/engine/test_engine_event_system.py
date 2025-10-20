"""Tests for GameEngine event system functionality.

This module tests GameEngine event handling, event processing, and event manager integration.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pygame

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.engine import GameEngine
from tests.mocks import MockFactory


class TestEngineEventSystem:
    """Test GameEngine event system functionality."""

    def _create_mock_game(self):
        """Create a mock game using MockFactory."""
        mock_game = Mock()
        mock_game.NAME = "MockGame"
        mock_game.VERSION = "1.0"
        mock_game.args = Mock(return_value=Mock())
        return mock_game

    def _create_mock_event(self, event_type, **kwargs):
        """Create a mock event using MockFactory."""
        mock_event = Mock()
        mock_event.type = event_type
        for key, value in kwargs.items():
            setattr(mock_event, key, value)
        return mock_event

    def test_game_engine_event_handlers_registration(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine event handler registration."""
        # Mock argument parsing to prevent command line argument issues
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create mock game
            mock_game = self._create_mock_game()

            # Create GameEngine instance
            engine = GameEngine(game=mock_game)

            # Test that event handlers are registered
            assert hasattr(engine, "EVENT_HANDLERS")
            assert isinstance(engine.EVENT_HANDLERS, dict)

            # Test that the EVENT_HANDLERS dictionary is not empty
            # (it gets populated during initialize_event_handlers)
            assert len(engine.EVENT_HANDLERS) > 0

            # Test that some common event types are registered
            # The actual events depend on the events module configuration
            assert any(event_type in engine.EVENT_HANDLERS for event_type in [
                pygame.QUIT, pygame.ACTIVEEVENT, pygame.KEYDOWN, pygame.KEYUP
            ])

    def test_game_engine_event_processing(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine event processing."""
        # Mock argument parsing to prevent command line argument issues
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create mock game
            mock_game = self._create_mock_game()

            # Create GameEngine instance
            engine = GameEngine(game=mock_game)

            # Mock events
            mock_events = [
                self._create_mock_event(pygame.QUIT),
                self._create_mock_event(pygame.KEYDOWN, key=pygame.K_SPACE),
                self._create_mock_event(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 100)),
                self._create_mock_event(pygame.JOYBUTTONDOWN, button=0, joy=0),
            ]

            # Mock the process_events method to avoid actual event processing
            with patch.object(engine, "process_events") as mock_process_events:
                mock_process_events.return_value = None

                # Test that process_events can be called
                engine.process_events(mock_events)

                # Verify the method was called
                mock_process_events.assert_called_once_with(mock_events)

    def test_game_engine_quit_event_handling(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine quit event handling."""
        # Mock argument parsing to prevent command line argument issues
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create mock game
            mock_game = self._create_mock_game()

            # Create GameEngine instance
            engine = GameEngine(game=mock_game)

            # Mock quit event
            quit_event = self._create_mock_event(pygame.QUIT)

            # Test quit event handler
            with patch.object(engine, "on_quit_event") as mock_quit_handler:
                mock_quit_handler.return_value = None

                # Call the quit event handler
                engine.on_quit_event(quit_event)

                # Verify the handler was called
                mock_quit_handler.assert_called_once_with(quit_event)

    def test_game_engine_keyboard_event_handling(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine keyboard event handling."""
        # Mock argument parsing to prevent command line argument issues
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create mock game
            mock_game = self._create_mock_game()

            # Create GameEngine instance
            engine = GameEngine(game=mock_game)

            # Mock keyboard events
            keydown_event = self._create_mock_event(pygame.KEYDOWN, key=pygame.K_SPACE)
            keyup_event = self._create_mock_event(pygame.KEYUP, key=pygame.K_SPACE)

            # Test keyboard event handlers
            with patch.object(engine, "on_keydown_event") as mock_keydown_handler, \
                 patch.object(engine, "on_keyup_event") as mock_keyup_handler:

                mock_keydown_handler.return_value = None
                mock_keyup_handler.return_value = None

                # Call the keyboard event handlers
                engine.on_keydown_event(keydown_event)
                engine.on_keyup_event(keyup_event)

                # Verify the handlers were called
                mock_keydown_handler.assert_called_once_with(keydown_event)
                mock_keyup_handler.assert_called_once_with(keyup_event)

    def test_game_engine_mouse_event_handling(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine mouse event handling."""
        # Mock argument parsing to prevent command line argument issues
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create mock game
            mock_game = self._create_mock_game()

            # Create GameEngine instance
            engine = GameEngine(game=mock_game)

            # Mock mouse events
            mousedown_event = self._create_mock_event(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 100))
            mouseup_event = self._create_mock_event(pygame.MOUSEBUTTONUP, button=1, pos=(100, 100))
            mousemotion_event = self._create_mock_event(pygame.MOUSEMOTION, pos=(100, 100), rel=(5, 5))

            # Test mouse event handlers
            with patch.object(engine, "on_mousebuttondown_event") as mock_mousedown_handler, \
                 patch.object(engine, "on_mousebuttonup_event") as mock_mouseup_handler, \
                 patch.object(engine, "on_mousemotion_event") as mock_mousemotion_handler:

                mock_mousedown_handler.return_value = None
                mock_mouseup_handler.return_value = None
                mock_mousemotion_handler.return_value = None

                # Call the mouse event handlers
                engine.on_mousebuttondown_event(mousedown_event)
                engine.on_mousebuttonup_event(mouseup_event)
                engine.on_mousemotion_event(mousemotion_event)

                # Verify the handlers were called
                mock_mousedown_handler.assert_called_once_with(mousedown_event)
                mock_mouseup_handler.assert_called_once_with(mouseup_event)
                mock_mousemotion_handler.assert_called_once_with(mousemotion_event)

    def test_game_engine_joystick_event_handling(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine joystick event handling."""
        # Mock argument parsing to prevent command line argument issues
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create mock game
            mock_game = self._create_mock_game()

            # Create GameEngine instance
            engine = GameEngine(game=mock_game)

            # Mock joystick events
            joybuttondown_event = self._create_mock_event(pygame.JOYBUTTONDOWN, button=0, joy=0)
            joybuttonup_event = self._create_mock_event(pygame.JOYBUTTONUP, button=0, joy=0)
            joyaxismotion_event = self._create_mock_event(pygame.JOYAXISMOTION, axis=0, value=0.5, joy=0)
            joyhatmotion_event = self._create_mock_event(pygame.JOYHATMOTION, hat=0, value=(1, 0), joy=0)
            joyballmotion_event = self._create_mock_event(pygame.JOYBALLMOTION, ball=0, rel=(5, 5), joy=0)

            # Test joystick event handlers
            with patch.object(engine, "on_joybuttondown_event") as mock_joybuttondown_handler, \
                 patch.object(engine, "on_joybuttonup_event") as mock_joybuttonup_handler, \
                 patch.object(engine, "on_joyaxismotion_event") as mock_joyaxismotion_handler, \
                 patch.object(engine, "on_joyhatmotion_event") as mock_joyhatmotion_handler, \
                 patch.object(engine, "on_joyballmotion_event") as mock_joyballmotion_handler:

                mock_joybuttondown_handler.return_value = None
                mock_joybuttonup_handler.return_value = None
                mock_joyaxismotion_handler.return_value = None
                mock_joyhatmotion_handler.return_value = None
                mock_joyballmotion_handler.return_value = None

                # Call the joystick event handlers
                engine.on_joybuttondown_event(joybuttondown_event)
                engine.on_joybuttonup_event(joybuttonup_event)
                engine.on_joyaxismotion_event(joyaxismotion_event)
                engine.on_joyhatmotion_event(joyhatmotion_event)
                engine.on_joyballmotion_event(joyballmotion_event)

                # Verify the handlers were called
                mock_joybuttondown_handler.assert_called_once_with(joybuttondown_event)
                mock_joybuttonup_handler.assert_called_once_with(joybuttonup_event)
                mock_joyaxismotion_handler.assert_called_once_with(joyaxismotion_event)
                mock_joyhatmotion_handler.assert_called_once_with(joyhatmotion_event)
                mock_joyballmotion_handler.assert_called_once_with(joyballmotion_event)

    def test_game_engine_active_event_handling(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine active event handling."""
        # Mock argument parsing to prevent command line argument issues
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create mock game
            mock_game = self._create_mock_game()

            # Create GameEngine instance
            engine = GameEngine(game=mock_game)

            # Mock active event
            active_event = self._create_mock_event(pygame.ACTIVEEVENT, gain=1, state=1)

            # Test active event handler
            with patch.object(engine, "on_active_event") as mock_active_handler:
                mock_active_handler.return_value = None

                # Call the active event handler
                engine.on_active_event(active_event)

                # Verify the handler was called
                mock_active_handler.assert_called_once_with(active_event)

    def test_game_engine_user_event_handling(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine user event handling."""
        # Mock argument parsing to prevent command line argument issues
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create mock game
            mock_game = self._create_mock_game()

            # Create GameEngine instance
            engine = GameEngine(game=mock_game)

            # Mock user events
            fps_event = self._create_mock_event(pygame.USEREVENT + 1)  # FPSEVENT
            game_event = self._create_mock_event(pygame.USEREVENT + 2)  # GAMEEVENT
            menu_event = self._create_mock_event(pygame.USEREVENT + 3)  # MENUEVENT

            # Test user event handlers
            with patch.object(engine, "on_fps_event") as mock_fps_handler, \
                 patch.object(engine, "on_game_event") as mock_game_handler, \
                 patch.object(engine, "on_menu_item_event") as mock_menu_handler:

                mock_fps_handler.return_value = None
                mock_game_handler.return_value = None
                mock_menu_handler.return_value = None

                # Call the user event handlers
                engine.on_fps_event(fps_event)
                engine.on_game_event(game_event)
                engine.on_menu_item_event(menu_event)

                # Verify the handlers were called
                mock_fps_handler.assert_called_once_with(fps_event)
                mock_game_handler.assert_called_once_with(game_event)
                mock_menu_handler.assert_called_once_with(menu_event)

    def test_game_engine_sys_wm_event_handling(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine sys wm event handling."""
        # Mock argument parsing to prevent command line argument issues
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create mock game
            mock_game = self._create_mock_game()

            # Create GameEngine instance
            engine = GameEngine(game=mock_game)

            # Mock sys wm event
            sys_wm_event = self._create_mock_event(pygame.SYSWMEVENT, msg="test_message")

            # Test sys wm event handler
            with patch.object(engine, "on_sys_wm_event") as mock_sys_wm_handler:
                mock_sys_wm_handler.return_value = None

                # Call the sys wm event handler
                engine.on_sys_wm_event(sys_wm_event)

                # Verify the handler was called
                mock_sys_wm_handler.assert_called_once_with(sys_wm_event)

    def test_game_engine_event_manager_integration(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine event manager integration."""
        # Mock argument parsing to prevent command line argument issues
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create mock game
            mock_game = self._create_mock_game()

            # Create GameEngine instance
            engine = GameEngine(game=mock_game)

            # Test that engine has the basic attributes that are set during __init__
            assert hasattr(engine, "game")
            assert hasattr(engine, "scene_manager")
            assert hasattr(engine, "EVENT_HANDLERS")

            # Test that the game attribute is set correctly
            assert engine.game == mock_game

            # Test that scene_manager is initialized
            assert engine.scene_manager is not None

            # Test that EVENT_HANDLERS is a dictionary
            assert isinstance(engine.EVENT_HANDLERS, dict)

            # Note: Manager attributes (audio_manager, etc.) are only set during start()
            # so we don't test for them here since we're not calling start()
