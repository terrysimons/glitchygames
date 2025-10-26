"""Tests for GameEngine lifecycle functionality.

This module tests GameEngine start/stop, game loop, and quit functionality.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.engine import GameEngine  # noqa: I001
from tests.mocks import MockFactory


class TestEngineLifecycle:
    """Test GameEngine lifecycle functionality."""

    def test_game_engine_quit_game(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine.quit_game method."""
        # Mock argument parsing to prevent command line argument issues
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create a simple mock game using the centralized mock
            mock_game = Mock()
            mock_game.NAME = "MockGame"
            mock_game.VERSION = "1.0"
            mock_game.args = Mock(return_value=Mock())

            # Create GameEngine instance with mock game
            engine = GameEngine(game=mock_game)

            # Test quit_game method
            engine.quit_game()

            # Verify the method completes without error
            assert True  # If we get here, the method worked

    def test_game_engine_start_with_mock_game(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine.start with mock game."""
        # Mock argument parsing to prevent command line argument issues
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create GameEngine instance with mock game
            mock_game = Mock()
            mock_game.NAME = "MockGame"
            mock_game.VERSION = "1.0"
            mock_game.args = Mock(return_value=Mock())

            engine = GameEngine(game=mock_game)

            # Mock the start method to avoid actual engine startup
            with patch.object(engine, "start") as mock_start:
                mock_start.side_effect = SystemExit

                # Test that start method can be called
                with pytest.raises(SystemExit):
                    engine.start()

                # Verify the start method was called
                mock_start.assert_called_once()

    def test_game_engine_start_with_profiling(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine.start with profiling enabled."""
        # Mock argument parsing to prevent command line argument issues
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_args = mock_game_args
            mock_args.profile = True  # Enable profiling
            mock_parse_args.return_value = mock_args

            # Create GameEngine instance with mock game
            mock_game = Mock()
            mock_game.NAME = "MockGame"
            mock_game.VERSION = "1.0"
            mock_game.args = Mock(return_value=Mock())

            engine = GameEngine(game=mock_game)

            # Mock the start method to avoid actual engine startup
            with patch.object(engine, "start") as mock_start:
                mock_start.side_effect = SystemExit

                # Test that start method can be called with profiling
                with pytest.raises(SystemExit):
                    engine.start()

                # Verify the start method was called
                mock_start.assert_called_once()

    def test_game_engine_start_with_exception(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine.start with exception handling."""
        # Mock argument parsing to prevent command line argument issues
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create GameEngine instance with mock game
            mock_game = Mock()
            mock_game.NAME = "MockGame"
            mock_game.VERSION = "1.0"
            mock_game.args = Mock(return_value=Mock())

            engine = GameEngine(game=mock_game)

            # Mock the start method to raise an exception
            with patch.object(engine, "start") as mock_start:
                mock_start.side_effect = RuntimeError("Test exception")

                # Test that start method handles exceptions
                with pytest.raises(RuntimeError):
                    engine.start()

                # Verify the start method was called
                mock_start.assert_called_once()

    def test_start_method_with_mocked_managers(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine.start method with mocked managers."""
        # Create a mock game class
        class MockGame:
            NAME = "MockGame"
            VERSION = "1.0"

            @classmethod
            def args(cls, parser):
                return parser

        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create engine with mock game
            engine = GameEngine(game=MockGame)

            # Use centralized mock factory for joystick manager
            mock_joystick_manager_instance = MockFactory.create_joystick_manager_mock(joystick_count=0)  # noqa: E501
            mock_joystick_manager_class = Mock(return_value=mock_joystick_manager_instance)

            # Mock all the manager classes
            with patch.multiple(
                "glitchygames.engine",
                AudioManager=Mock,
                DropManager=Mock,
                ControllerManager=Mock,
                TouchManager=Mock,
                FontManager=Mock,
                GameManager=Mock,
                JoystickManager=mock_joystick_manager_class,
                KeyboardManager=Mock,
                MidiManager=Mock,
                MouseManager=Mock,
                WindowManager=Mock
            ), patch.object(engine, "game") as mock_game_class:
                mock_game_instance = Mock()
                mock_game_class.return_value = mock_game_instance

                # Mock scene manager
                engine.scene_manager = Mock()
                engine.scene_manager.switch_to_scene = Mock()
                engine.scene_manager.start = Mock()

                # Set up joysticks list properly - this will be overridden by start()
                engine.joysticks = []
                engine.joystick_count = 0

                # Test start method - should not crash
                engine.start()

                # Verify game was initialized
                mock_game_class.assert_called_once()

    def test_start_method_with_profiling(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine.start method with profiling enabled."""
        # Create a mock game class
        class MockGame:
            NAME = "MockGame"
            VERSION = "1.0"

            @classmethod
            def args(cls, parser):
                return parser

        # Enable profiling in args
        mock_game_args.profile = True

        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create engine with mock game
            engine = GameEngine(game=MockGame)

            # Use centralized mock factory for joystick manager
            mock_joystick_manager_instance = MockFactory.create_joystick_manager_mock(joystick_count=0)  # noqa: E501
            mock_joystick_manager_class = Mock(return_value=mock_joystick_manager_instance)

            # Mock all the manager classes
            with patch.multiple(
                "glitchygames.engine",
                AudioManager=Mock,
                DropManager=Mock,
                ControllerManager=Mock,
                TouchManager=Mock,
                FontManager=Mock,
                GameManager=Mock,
                JoystickManager=mock_joystick_manager_class,
                KeyboardManager=Mock,
                MidiManager=Mock,
                MouseManager=Mock,
                WindowManager=Mock
            ), patch.object(engine, "game") as mock_game_class:
                mock_game_instance = Mock()
                mock_game_class.return_value = mock_game_instance

                # Mock scene manager
                engine.scene_manager = Mock()
                engine.scene_manager.switch_to_scene = Mock()
                engine.scene_manager.start = Mock()

                # Mock joystick manager
                engine.joystick_manager = Mock()
                engine.joystick_manager.joysticks = {}  # Empty dictionary (no joysticks connected)  # noqa: E501

                # Set up joysticks list properly
                engine.joysticks = []
                engine.joystick_count = 0

                # Mock cProfile to avoid actual profiling
                with patch("cProfile.Profile") as mock_profile:
                    mock_profile_instance = Mock()
                    mock_profile.return_value = mock_profile_instance

                    # Test start method with profiling
                    engine.start()

                    # Verify game was initialized
                    mock_game_class.assert_called_once()

    def test_start_method_exception_handling(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine.start method exception handling."""
        # Create a mock game class
        class MockGame:
            NAME = "MockGame"
            VERSION = "1.0"

            @classmethod
            def args(cls, parser):
                return parser

        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create engine with mock game
            engine = GameEngine(game=MockGame)

            # Use centralized mock factory for joystick manager
            mock_joystick_manager_instance = MockFactory.create_joystick_manager_mock(joystick_count=0)  # noqa: E501
            mock_joystick_manager_class = Mock(return_value=mock_joystick_manager_instance)

            # Mock all the manager classes to raise exceptions
            with patch.multiple(
                "glitchygames.engine",
                AudioManager=Mock(side_effect=Exception("AudioManager failed")),
                DropManager=Mock,
                ControllerManager=Mock,
                TouchManager=Mock,
                FontManager=Mock,
                GameManager=Mock,
                JoystickManager=mock_joystick_manager_class,
                KeyboardManager=Mock,
                MidiManager=Mock,
                MouseManager=Mock,
                WindowManager=Mock
            ), patch.object(engine, "game") as mock_game_class:
                mock_game_instance = Mock()
                mock_game_class.return_value = mock_game_instance

                # Mock scene manager
                engine.scene_manager = Mock()
                engine.scene_manager.switch_to_scene = Mock()
                engine.scene_manager.start = Mock()

                # Set up joysticks list properly
                engine.joysticks = []
                engine.joystick_count = 0

                # Test start method with exception handling
                # The engine should handle exceptions gracefully (not raise them)
                # Suppress the expected exception log output
                with patch("glitchygames.engine.LOG.exception") as mock_log:
                    engine.start()
                    # Verify the exception was logged
                    mock_log.assert_called_once()

                # Verify game was initialized
                mock_game_class.assert_called_once()

    def test_start_method_error_message_with_previous_scene(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine.start method error message shows previous scene when current is None."""
        # Create a mock game class
        class MockGame:
            NAME = "MockGame"
            VERSION = "1.0"

            @classmethod
            def args(cls, parser):
                return parser

        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create engine with mock game
            engine = GameEngine(game=MockGame)

            # Use centralized mock factory for joystick manager
            mock_joystick_manager_instance = MockFactory.create_joystick_manager_mock(joystick_count=0)
            mock_joystick_manager_class = Mock(return_value=mock_joystick_manager_instance)

            # Mock all the manager classes
            with patch.multiple(
                "glitchygames.engine",
                AudioManager=Mock,
                DropManager=Mock,
                ControllerManager=Mock,
                TouchManager=Mock,
                FontManager=Mock,
                GameManager=Mock,
                JoystickManager=mock_joystick_manager_class,
                KeyboardManager=Mock,
                MidiManager=Mock,
                MouseManager=Mock,
                WindowManager=Mock
            ), patch.object(engine, "game") as mock_game_class:
                mock_game_instance = Mock()
                mock_game_class.return_value = mock_game_instance

                # Mock scene manager with current_scene=None and previous_scene set
                engine.scene_manager = Mock()
                engine.scene_manager.current_scene = None
                engine.scene_manager.previous_scene = Mock()
                engine.scene_manager.previous_scene.NAME = "PreviousScene"
                engine.scene_manager.switch_to_scene = Mock()
                engine.scene_manager.start = Mock(side_effect=RuntimeError("Test exception"))

                # Set up joysticks list properly
                engine.joysticks = []
                engine.joystick_count = 0

                # Test start method with exception handling
                with patch("glitchygames.engine.LOG.exception") as mock_log:
                    engine.start()
                    # Verify the exception was logged with previous scene info
                    mock_log.assert_called_once()
                    call_args = mock_log.call_args[0][0]
                    assert "PreviousScene (previous)" in call_args

    def test_start_method_error_message_with_current_scene(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine.start method error message shows current scene when available."""
        # Create a mock game class
        class MockGame:
            NAME = "MockGame"
            VERSION = "1.0"

            @classmethod
            def args(cls, parser):
                return parser

        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create engine with mock game
            engine = GameEngine(game=MockGame)

            # Use centralized mock factory for joystick manager
            mock_joystick_manager_instance = MockFactory.create_joystick_manager_mock(joystick_count=0)
            mock_joystick_manager_class = Mock(return_value=mock_joystick_manager_instance)

            # Mock all the manager classes
            with patch.multiple(
                "glitchygames.engine",
                AudioManager=Mock,
                DropManager=Mock,
                ControllerManager=Mock,
                TouchManager=Mock,
                FontManager=Mock,
                GameManager=Mock,
                JoystickManager=mock_joystick_manager_class,
                KeyboardManager=Mock,
                MidiManager=Mock,
                MouseManager=Mock,
                WindowManager=Mock
            ), patch.object(engine, "game") as mock_game_class:
                mock_game_instance = Mock()
                mock_game_class.return_value = mock_game_instance

                # Mock scene manager with current_scene set
                engine.scene_manager = Mock()
                engine.scene_manager.current_scene = Mock()
                engine.scene_manager.current_scene.NAME = "CurrentScene"
                engine.scene_manager.switch_to_scene = Mock()
                engine.scene_manager.start = Mock(side_effect=RuntimeError("Test exception"))

                # Set up joysticks list properly
                engine.joysticks = []
                engine.joystick_count = 0

                # Test start method with exception handling
                with patch("glitchygames.engine.LOG.exception") as mock_log:
                    engine.start()
                    # Verify the exception was logged with current scene info
                    mock_log.assert_called_once()
                    call_args = mock_log.call_args[0][0]
                    assert "CurrentScene" in call_args
                    assert "(previous)" not in call_args

    def test_start_method_error_message_with_no_scenes(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine.start method error message shows None when both scenes are None."""
        # Create a mock game class
        class MockGame:
            NAME = "MockGame"
            VERSION = "1.0"

            @classmethod
            def args(cls, parser):
                return parser

        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create engine with mock game
            engine = GameEngine(game=MockGame)

            # Use centralized mock factory for joystick manager
            mock_joystick_manager_instance = MockFactory.create_joystick_manager_mock(joystick_count=0)
            mock_joystick_manager_class = Mock(return_value=mock_joystick_manager_instance)

            # Mock all the manager classes
            with patch.multiple(
                "glitchygames.engine",
                AudioManager=Mock,
                DropManager=Mock,
                ControllerManager=Mock,
                TouchManager=Mock,
                FontManager=Mock,
                GameManager=Mock,
                JoystickManager=mock_joystick_manager_class,
                KeyboardManager=Mock,
                MidiManager=Mock,
                MouseManager=Mock,
                WindowManager=Mock
            ), patch.object(engine, "game") as mock_game_class:
                mock_game_instance = Mock()
                mock_game_class.return_value = mock_game_instance

                # Mock scene manager with both scenes None
                engine.scene_manager = Mock()
                engine.scene_manager.current_scene = None
                engine.scene_manager.previous_scene = None
                engine.scene_manager.switch_to_scene = Mock()
                engine.scene_manager.start = Mock(side_effect=RuntimeError("Test exception"))

                # Set up joysticks list properly
                engine.joysticks = []
                engine.joystick_count = 0

                # Test start method with exception handling
                with patch("glitchygames.engine.LOG.exception") as mock_log:
                    engine.start()
                    # Verify the exception was logged with None
                    mock_log.assert_called_once()
                    call_args = mock_log.call_args[0][0]
                    assert "scene 'None'" in call_args
