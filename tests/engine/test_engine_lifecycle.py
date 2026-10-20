"""Tests for GameEngine lifecycle functionality.

This module tests GameEngine start/stop, game loop, and quit functionality.
"""

import logging
import signal
import sys
from pathlib import Path

import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.engine import GameEngine
from glitchygames.engine import game_engine as game_engine_module
from glitchygames.exit_codes import ExitCode
from glitchygames.scenes import Scene
from tests.mocks import MockFactory


class TestEngineLifecycle:
    """Test GameEngine lifecycle functionality."""

    def test_game_engine_quit_game(self, mock_pygame_patches, mock_game_args, mocker):
        """Test GameEngine.quit_game method."""
        # Mock argument parsing to prevent command line argument issues
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        # Create a simple mock game using the centralized mock
        mock_game = mocker.Mock()
        mock_game.NAME = 'MockGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        # Create GameEngine instance with mock game
        engine = GameEngine(game=mock_game)

        # Test quit_game method
        engine.quit_game()

        # Verify the method completes without error
        assert True  # If we get here, the method worked

    def test_game_engine_start_with_mock_game(self, mock_pygame_patches, mock_game_args, mocker):
        """Test GameEngine.start with mock game."""
        # Mock argument parsing to prevent command line argument issues
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        # Create GameEngine instance with mock game
        mock_game = mocker.Mock()
        mock_game.NAME = 'MockGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        engine = GameEngine(game=mock_game)

        # Mock the start method to avoid actual engine startup
        mock_start = mocker.patch.object(engine, 'start')
        mock_start.side_effect = SystemExit

        # Test that start method can be called
        with pytest.raises(SystemExit) as exit_info:
            engine.start()
        assert exit_info.value.code is None

        # Verify the start method was called
        mock_start.assert_called_once()

    def test_game_engine_start_with_profiling(self, mock_pygame_patches, mock_game_args, mocker):
        """Test GameEngine.start with profiling enabled."""
        # Mock argument parsing to prevent command line argument issues
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_args = mock_game_args
        mock_args.profile = True  # Enable profiling
        mock_parse_args.return_value = mock_args

        # Create GameEngine instance with mock game
        mock_game = mocker.Mock()
        mock_game.NAME = 'MockGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        engine = GameEngine(game=mock_game)

        # Mock the start method to avoid actual engine startup
        mock_start = mocker.patch.object(engine, 'start')
        mock_start.side_effect = SystemExit

        # Test that start method can be called with profiling
        with pytest.raises(SystemExit) as exit_info:
            engine.start()
        assert exit_info.value.code is None

        # Verify the start method was called
        mock_start.assert_called_once()

    def test_game_engine_start_with_exception(self, mock_pygame_patches, mock_game_args, mocker):
        """Test GameEngine.start with exception handling."""
        # Mock argument parsing to prevent command line argument issues
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        # Create GameEngine instance with mock game
        mock_game = mocker.Mock()
        mock_game.NAME = 'MockGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        engine = GameEngine(game=mock_game)

        # Mock the start method to raise an exception
        mock_start = mocker.patch.object(engine, 'start')
        mock_start.side_effect = RuntimeError('Test exception')

        # Test that start method handles exceptions
        with pytest.raises(RuntimeError):
            engine.start()

        # Verify the start method was called
        mock_start.assert_called_once()

    def test_start_method_with_mocked_managers(self, mock_pygame_patches, mock_game_args, mocker):
        """Test GameEngine.start method with mocked managers."""

        # Create a mock game class
        class MockGame:
            NAME = 'MockGame'
            VERSION = '1.0'
            TARGET_FPS = None

            @classmethod
            def args(cls, parser):
                return parser

        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        # Create engine with mock game
        engine = GameEngine(game=MockGame)  # type: ignore[invalid-argument-type]

        # Use centralized mock factory for joystick manager
        mock_joystick_manager_instance = MockFactory.create_joystick_manager_mock(joystick_count=0)
        mock_joystick_manager_class = mocker.Mock(return_value=mock_joystick_manager_instance)

        # Mock all the manager classes
        mocker.patch.multiple(
            'glitchygames.engine.game_engine',
            AudioEventManager=mocker.Mock,
            DropEventManager=mocker.Mock,
            ControllerEventManager=mocker.Mock,
            TouchEventManager=mocker.Mock,
            FontManager=mocker.Mock,
            GameEventManager=mocker.Mock,
            JoystickEventManager=mock_joystick_manager_class,
            KeyboardEventManager=mocker.Mock,
            MidiEventManager=mocker.Mock,
            MouseEventManager=mocker.Mock,
            WindowEventManager=mocker.Mock,
        )
        mock_game_class = mocker.patch.object(engine, 'game')
        mock_game_instance = mocker.Mock()
        mock_game_class.return_value = mock_game_instance

        # Mock scene manager
        engine.scene_manager = mocker.Mock()
        engine.scene_manager.switch_to_scene = mocker.Mock()
        engine.scene_manager.start = mocker.Mock()

        # Set up joysticks list properly - this will be overridden by start()
        engine.joysticks = []
        engine.joystick_count = 0

        # Test start method - should not crash
        engine.start()

        # Verify game was initialized
        mock_game_class.assert_called_once()

    def test_start_method_with_profiling(self, mock_pygame_patches, mock_game_args, mocker):
        """Test GameEngine.start method with profiling enabled."""

        # Create a mock game class
        class MockGame:
            NAME = 'MockGame'
            VERSION = '1.0'
            TARGET_FPS = None

            @classmethod
            def args(cls, parser):
                return parser

        # Enable profiling in args
        mock_game_args.profile = True

        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        # Create engine with mock game
        engine = GameEngine(game=MockGame)  # type: ignore[invalid-argument-type]

        # Use centralized mock factory for joystick manager
        mock_joystick_manager_instance = MockFactory.create_joystick_manager_mock(joystick_count=0)
        mock_joystick_manager_class = mocker.Mock(return_value=mock_joystick_manager_instance)

        # Mock all the manager classes
        mocker.patch.multiple(
            'glitchygames.engine.game_engine',
            AudioEventManager=mocker.Mock,
            DropEventManager=mocker.Mock,
            ControllerEventManager=mocker.Mock,
            TouchEventManager=mocker.Mock,
            FontManager=mocker.Mock,
            GameEventManager=mocker.Mock,
            JoystickEventManager=mock_joystick_manager_class,
            KeyboardEventManager=mocker.Mock,
            MidiEventManager=mocker.Mock,
            MouseEventManager=mocker.Mock,
            WindowEventManager=mocker.Mock,
        )
        mock_game_class = mocker.patch.object(engine, 'game')
        mock_game_instance = mocker.Mock()
        mock_game_class.return_value = mock_game_instance

        # Mock scene manager
        engine.scene_manager = mocker.Mock()
        engine.scene_manager.switch_to_scene = mocker.Mock()
        engine.scene_manager.start = mocker.Mock()

        # Mock joystick manager
        engine.joystick_manager = mocker.Mock()
        engine.joystick_manager.joysticks = {}  # Empty dictionary (no joysticks connected)

        # Set up joysticks list properly
        engine.joysticks = []
        engine.joystick_count = 0

        # Mock cProfile to avoid actual profiling
        mock_profile = mocker.patch('cProfile.Profile')
        mock_profile_instance = mocker.Mock()
        mock_profile.return_value = mock_profile_instance

        # Test start method with profiling
        engine.start()

        # Verify game was initialized
        mock_game_class.assert_called_once()

    def test_start_method_exception_handling(self, mock_pygame_patches, mock_game_args, mocker):
        """Test GameEngine.start method exception handling."""

        # Create a mock game class
        class MockGame:
            NAME = 'MockGame'
            VERSION = '1.0'
            TARGET_FPS = None

            @classmethod
            def args(cls, parser):
                return parser

        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        # Create engine with mock game
        engine = GameEngine(game=MockGame)  # type: ignore[invalid-argument-type]

        # Use centralized mock factory for joystick manager
        mock_joystick_manager_instance = MockFactory.create_joystick_manager_mock(joystick_count=0)
        mock_joystick_manager_class = mocker.Mock(return_value=mock_joystick_manager_instance)

        # Mock all the manager classes to raise exceptions
        mocker.patch.multiple(
            'glitchygames.engine.game_engine',
            AudioEventManager=mocker.Mock(side_effect=Exception('AudioEventManager failed')),
            DropEventManager=mocker.Mock,
            ControllerEventManager=mocker.Mock,
            TouchEventManager=mocker.Mock,
            FontManager=mocker.Mock,
            GameEventManager=mocker.Mock,
            JoystickEventManager=mock_joystick_manager_class,
            KeyboardEventManager=mocker.Mock,
            MidiEventManager=mocker.Mock,
            MouseEventManager=mocker.Mock,
            WindowEventManager=mocker.Mock,
        )
        mock_game_class = mocker.patch.object(engine, 'game')
        mock_game_instance = mocker.Mock()
        mock_game_class.return_value = mock_game_instance

        # Mock scene manager
        engine.scene_manager = mocker.Mock()
        engine.scene_manager.switch_to_scene = mocker.Mock()
        engine.scene_manager.start = mocker.Mock()

        # Set up joysticks list properly
        engine.joysticks = []
        engine.joystick_count = 0

        # An uncaught exception is logged with its traceback, then the run exits as an internal
        # error once the teardown has run
        mock_log = mocker.patch('glitchygames.engine.LOG.exception')
        with pytest.raises(SystemExit) as exit_info:
            engine.start()
        assert exit_info.value.code == ExitCode.INTERNAL_ERROR
        mock_log.assert_called_once()

        # Verify game was initialized
        mock_game_class.assert_called_once()

    def test_start_method_error_message_with_previous_scene(
        self,
        mock_pygame_patches,
        mock_game_args,
        mocker,
    ):
        """Test GameEngine.start method error message shows previous scene when current is None."""

        # Create a mock game class
        class MockGame:
            NAME = 'MockGame'
            VERSION = '1.0'
            TARGET_FPS = None

            @classmethod
            def args(cls, parser):
                return parser

        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        # Create engine with mock game
        engine = GameEngine(game=MockGame)  # type: ignore[invalid-argument-type]

        # Use centralized mock factory for joystick manager
        mock_joystick_manager_instance = MockFactory.create_joystick_manager_mock(joystick_count=0)
        mock_joystick_manager_class = mocker.Mock(return_value=mock_joystick_manager_instance)

        # Mock all the manager classes
        mocker.patch.multiple(
            'glitchygames.engine.game_engine',
            AudioEventManager=mocker.Mock,
            DropEventManager=mocker.Mock,
            ControllerEventManager=mocker.Mock,
            TouchEventManager=mocker.Mock,
            FontManager=mocker.Mock,
            GameEventManager=mocker.Mock,
            JoystickEventManager=mock_joystick_manager_class,
            KeyboardEventManager=mocker.Mock,
            MidiEventManager=mocker.Mock,
            MouseEventManager=mocker.Mock,
            WindowEventManager=mocker.Mock,
        )
        mock_game_class = mocker.patch.object(engine, 'game')
        mock_game_instance = mocker.Mock()
        mock_game_class.return_value = mock_game_instance

        # Mock scene manager with current_scene=None and previous_scene set
        engine.scene_manager = mocker.Mock()
        engine.scene_manager.current_scene = None
        engine.scene_manager.previous_scene = mocker.Mock()
        engine.scene_manager.previous_scene.NAME = 'PreviousScene'
        engine.scene_manager.switch_to_scene = mocker.Mock()
        engine.scene_manager.start = mocker.Mock(side_effect=RuntimeError('Test exception'))

        # Set up joysticks list properly
        engine.joysticks = []
        engine.joystick_count = 0

        # Test start method with exception handling
        mock_log = mocker.patch('glitchygames.engine.LOG.exception')
        with pytest.raises(SystemExit) as exit_info:
            engine.start()
        assert exit_info.value.code == ExitCode.INTERNAL_ERROR
        # Verify the exception was logged with previous scene info
        mock_log.assert_called_once()
        # Log uses %s format: ("Runtime error ... '%s'", scene_name)
        format_args = mock_log.call_args[0]
        assert 'PreviousScene' in format_args[1]

    def test_start_method_error_message_with_current_scene(
        self,
        mock_pygame_patches,
        mock_game_args,
        mocker,
    ):
        """Test GameEngine.start method error message shows current scene when available."""

        # Create a mock game class
        class MockGame:
            NAME = 'MockGame'
            VERSION = '1.0'
            TARGET_FPS = None

            @classmethod
            def args(cls, parser):
                return parser

        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        # Create engine with mock game
        engine = GameEngine(game=MockGame)  # type: ignore[invalid-argument-type]

        # Use centralized mock factory for joystick manager
        mock_joystick_manager_instance = MockFactory.create_joystick_manager_mock(joystick_count=0)
        mock_joystick_manager_class = mocker.Mock(return_value=mock_joystick_manager_instance)

        # Mock all the manager classes
        mocker.patch.multiple(
            'glitchygames.engine.game_engine',
            AudioEventManager=mocker.Mock,
            DropEventManager=mocker.Mock,
            ControllerEventManager=mocker.Mock,
            TouchEventManager=mocker.Mock,
            FontManager=mocker.Mock,
            GameEventManager=mocker.Mock,
            JoystickEventManager=mock_joystick_manager_class,
            KeyboardEventManager=mocker.Mock,
            MidiEventManager=mocker.Mock,
            MouseEventManager=mocker.Mock,
            WindowEventManager=mocker.Mock,
        )
        mock_game_class = mocker.patch.object(engine, 'game')
        mock_game_instance = mocker.Mock()
        mock_game_class.return_value = mock_game_instance

        # Mock scene manager with current_scene set
        engine.scene_manager = mocker.Mock()
        engine.scene_manager.current_scene = mocker.Mock()
        engine.scene_manager.current_scene.NAME = 'CurrentScene'
        engine.scene_manager.switch_to_scene = mocker.Mock()
        engine.scene_manager.start = mocker.Mock(side_effect=RuntimeError('Test exception'))

        # Set up joysticks list properly
        engine.joysticks = []
        engine.joystick_count = 0

        # Test start method with exception handling
        mock_log = mocker.patch('glitchygames.engine.LOG.exception')
        with pytest.raises(SystemExit) as exit_info:
            engine.start()
        assert exit_info.value.code == ExitCode.INTERNAL_ERROR
        # Verify the exception was logged with current scene info
        mock_log.assert_called_once()
        # Log uses %s format: ("Runtime error ... '%s'", scene_name)
        format_args = mock_log.call_args[0]
        assert 'CurrentScene' in format_args[1]

    def test_start_method_error_message_with_no_scenes(
        self,
        mock_pygame_patches,
        mock_game_args,
        mocker,
    ):
        """Test GameEngine.start method error message shows None when both scenes are None."""

        # Create a mock game class
        class MockGame:
            NAME = 'MockGame'
            VERSION = '1.0'
            TARGET_FPS = None

            @classmethod
            def args(cls, parser):
                return parser

        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        # Create engine with mock game
        engine = GameEngine(game=MockGame)  # type: ignore[invalid-argument-type]

        # Use centralized mock factory for joystick manager
        mock_joystick_manager_instance = MockFactory.create_joystick_manager_mock(joystick_count=0)
        mock_joystick_manager_class = mocker.Mock(return_value=mock_joystick_manager_instance)

        # Mock all the manager classes
        mocker.patch.multiple(
            'glitchygames.engine.game_engine',
            AudioEventManager=mocker.Mock,
            DropEventManager=mocker.Mock,
            ControllerEventManager=mocker.Mock,
            TouchEventManager=mocker.Mock,
            FontManager=mocker.Mock,
            GameEventManager=mocker.Mock,
            JoystickEventManager=mock_joystick_manager_class,
            KeyboardEventManager=mocker.Mock,
            MidiEventManager=mocker.Mock,
            MouseEventManager=mocker.Mock,
            WindowEventManager=mocker.Mock,
        )
        mock_game_class = mocker.patch.object(engine, 'game')
        mock_game_instance = mocker.Mock()
        mock_game_class.return_value = mock_game_instance

        # Mock scene manager with both scenes None
        engine.scene_manager = mocker.Mock()
        engine.scene_manager.current_scene = None
        engine.scene_manager.previous_scene = None
        engine.scene_manager.switch_to_scene = mocker.Mock()
        engine.scene_manager.start = mocker.Mock(side_effect=RuntimeError('Test exception'))

        # Set up joysticks list properly
        engine.joysticks = []
        engine.joystick_count = 0

        # Test start method with exception handling
        mock_log = mocker.patch('glitchygames.engine.LOG.exception')
        with pytest.raises(SystemExit) as exit_info:
            engine.start()
        assert exit_info.value.code == ExitCode.INTERNAL_ERROR
        # Verify the exception was logged with None
        mock_log.assert_called_once()
        # Log uses %s format: ("Runtime error ... '%s'", scene_name)
        format_args = mock_log.call_args[0]
        assert format_args[1] == 'None'


class StartExitStatusGame(Scene):
    """The game class GameEngine is built with in TestStartExitStatus (never instantiated)."""

    NAME = 'StartExitStatusGame'
    VERSION = '1.0'


def engine_whose_run_raises(
    *, mocker, mock_game_args, run_error: BaseException | None
) -> GameEngine:
    """Build a GameEngine whose scene manager raises ``run_error`` (None: returns) when started.

    Returns:
        The engine, with its event managers mocked and ``_shutdown`` spied on.

    """
    mocker.patch('argparse.ArgumentParser.parse_args', return_value=mock_game_args)
    engine = GameEngine(game=StartExitStatusGame)
    mocker.patch.object(engine, '_initialize_event_managers')
    mocker.patch.object(engine, 'game')
    engine.scene_manager = mocker.Mock()
    engine.scene_manager.start = mocker.Mock(side_effect=run_error)
    mocker.spy(engine, '_shutdown')
    return engine


class TestStartExitStatus:
    """How GameEngine.start() ends: crashes exit as internal errors, deliberate exits pass."""

    def test_an_uncaught_exception_exits_as_an_internal_error_after_teardown(
        self, mock_pygame_patches, mock_game_args, mocker, caplog
    ):
        run_error = RuntimeError('the game broke')
        engine = engine_whose_run_raises(
            mocker=mocker, mock_game_args=mock_game_args, run_error=run_error
        )
        with caplog.at_level(logging.INFO), pytest.raises(SystemExit) as exit_info:
            engine.start()
        assert exit_info.value.code == ExitCode.INTERNAL_ERROR
        assert exit_info.value.__cause__ is run_error
        assert f'Exiting with {ExitCode.INTERNAL_ERROR.describe()}' in caplog.text
        engine._shutdown.assert_called_once_with(run_ended_by=ExitCode.INTERNAL_ERROR.describe())
        crash_records = [record for record in caplog.records if record.exc_info is not None]
        assert len(crash_records) == 1
        assert crash_records[0].exc_info[1] is run_error

    def test_a_deliberate_system_exit_passes_through_unchanged(
        self, mock_pygame_patches, mock_game_args, mocker
    ):
        engine = engine_whose_run_raises(
            mocker=mocker,
            mock_game_args=mock_game_args,
            run_error=SystemExit(ExitCode.REPLAY_DIVERGED),
        )
        with pytest.raises(SystemExit) as exit_info:
            engine.start()
        assert exit_info.value.code == ExitCode.REPLAY_DIVERGED
        engine._shutdown.assert_called_once_with(
            run_ended_by=ExitCode.describe_status(ExitCode.REPLAY_DIVERGED)
        )

    def test_a_keyboard_interrupt_exits_as_interrupted_after_teardown(
        self, mock_pygame_patches, mock_game_args, mocker, caplog
    ):
        """Ctrl-C is never an internal error: it exits INTERRUPTED once teardown has run."""
        engine = engine_whose_run_raises(
            mocker=mocker, mock_game_args=mock_game_args, run_error=KeyboardInterrupt()
        )
        with caplog.at_level(logging.INFO), pytest.raises(SystemExit) as exit_info:
            engine.start()
        assert exit_info.value.code == ExitCode.INTERRUPTED
        engine._shutdown.assert_called_once_with(run_ended_by=ExitCode.INTERRUPTED.describe())
        assert f'Exiting with {ExitCode.INTERRUPTED.describe()}' in caplog.text
        assert all(record.exc_info is None for record in caplog.records)

    def test_signal_handlers_are_restored_even_when_the_teardown_does_not(
        self, mock_pygame_patches, mock_game_args, mocker
    ):
        """start() restores what it installed itself, so a mocked _shutdown leaks nothing."""
        handlers_before = {
            signal_number: signal.getsignal(signal_number)
            for signal_number in game_engine_module.terminating_signals()
        }
        engine = engine_whose_run_raises(
            mocker=mocker, mock_game_args=mock_game_args, run_error=None
        )
        mocker.patch.object(engine, '_shutdown')
        engine.start()
        assert {
            signal_number: signal.getsignal(signal_number) for signal_number in handlers_before
        } == handlers_before

    @pytest.mark.parametrize(
        'run_error', [None, RuntimeError('the game broke')], ids=['clean run', 'crashed run']
    )
    def test_a_teardown_failure_exits_as_an_internal_error(
        self, mock_pygame_patches, mock_game_args, mocker, caplog, run_error
    ):
        """A _shutdown that raises never leaves Python to exit 1; every error is logged."""
        teardown_error = RuntimeError('the teardown broke')
        engine = engine_whose_run_raises(
            mocker=mocker, mock_game_args=mock_game_args, run_error=run_error
        )
        mocker.patch.object(engine, '_shutdown', side_effect=teardown_error)
        with caplog.at_level(logging.INFO), pytest.raises(SystemExit) as exit_info:
            engine.start()
        assert exit_info.value.code == ExitCode.INTERNAL_ERROR
        assert exit_info.value.__cause__ is teardown_error
        logged_errors = [record.exc_info[1] for record in caplog.records if record.exc_info]
        expected_errors = [teardown_error] if run_error is None else [run_error, teardown_error]
        assert logged_errors == expected_errors
        assert f'Exiting with {ExitCode.INTERNAL_ERROR.describe()}' in caplog.text
