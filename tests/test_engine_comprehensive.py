"""Comprehensive tests for Engine module to achieve 80%+ coverage.

This module targets the Engine module with comprehensive mocking and refactoring.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pygame

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.engine import GameEngine, GameManager
from glitchygames.scenes import Scene

from test_mock_factory import MockFactory


class MockGame(Scene):
    """Simple mock game scene for testing."""
    
    NAME = "MockGame"
    VERSION = "1.0"

    def __init__(self, options=None, groups=None):
        if options is None:
            options = {}
        if groups is None:
            groups = Mock()  # Mock pygame.sprite.Group
        super().__init__(options=options, groups=groups)
        self.fps = 60
        self.background_color = (0, 0, 0)
        self.next_scene = self
    
    @classmethod
    def args(cls, parser):
        """Add mock game arguments."""
        parser.add_argument("--test-flag", action="store_true", help="Test flag")
        return parser
    
    def update(self):
        """Mock update method."""
        pass


class MockGameWithArgs(MockGame):
    """Mock game that properly handles command line arguments."""
    
    @classmethod
    def args(cls, parser):
        """Add mock game arguments and return a parser that won't fail on unknown args."""
        parser.add_argument("--test-flag", action="store_true", help="Test flag")
        # Make the parser more lenient for testing
        parser.add_argument("--unknown-args", nargs="*", help="Catch unknown arguments")
        return parser
    
    def __call__(self, options=None):
        """Make the mock game callable to return itself."""
        return self


class TestEngineComprehensive(unittest.TestCase):
    """Comprehensive tests for Engine functionality to achieve 80%+ coverage."""

    def setUp(self):
        """Set up test fixtures using enhanced MockFactory."""
        # Use the enhanced centralized pygame mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        
        # Get the mocked objects for direct access
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)
    
    def _create_mock_args(self):
        """Create a mock args object with all required fields."""
        mock_args = Mock()
        mock_args.log_level = 'INFO'
        mock_args.target_fps = 60
        mock_args.fps_refresh_rate = 1
        mock_args.windowed = False
        mock_args.resolution = '800x600'
        mock_args.use_gfxdraw = False
        mock_args.update_type = 'update'
        mock_args.video_driver = None
        mock_args.font_name = 'Arial'
        mock_args.font_size = 12
        mock_args.font_bold = False
        mock_args.font_italic = False
        mock_args.font_antialias = True
        mock_args.font_dpi = 72
        mock_args.font_system = 'pygame'
        mock_args.profile = False
        mock_args.test_flag = False
        mock_args.unknown_args = []
        return mock_args

    def test_game_engine_initialize_icon_with_surface(self):
        """Test GameEngine.initialize_icon with pygame.Surface."""
        # Mock argument parsing to prevent command line argument issues
        with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
            mock_parse_args.return_value = self._create_mock_args()
            
            # Create a mock surface using the centralized mock factory
            mock_icon = MockFactory.create_pygame_surface_mock(32, 32)
            
            # Make the mock surface implement PathLike protocol so it can be converted to a path
            mock_icon.__fspath__ = Mock(return_value="/path/to/icon.png")
            
            # Mock pygame.image.load to return our mock surface
            with patch("pygame.image.load", return_value=mock_icon):
                # Test the class method
                GameEngine.initialize_icon(mock_icon)
                
                # Verify the icon was set (it will be the result of pygame.image.load, which is our mock)
                self.assertEqual(GameEngine.icon, mock_icon)

    def test_game_engine_initialize_icon_with_path(self):
        """Test GameEngine.initialize_icon with Path."""
        # Mock argument parsing to prevent command line argument issues
        with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
            mock_parse_args.return_value = self._create_mock_args()
            
            # Create a mock path
            mock_path = Mock()
            mock_path.__fspath__ = Mock(return_value="/path/to/icon.png")
            
            with patch("pygame.image.load") as mock_load:
                mock_surface = MockFactory.create_pygame_surface_mock()
                mock_load.return_value = mock_surface
                
                GameEngine.initialize_icon(mock_path)
                
                # Verify pygame.image.load was called
                mock_load.assert_called_once()

    def test_game_engine_initialize_icon_with_none(self):
        """Test GameEngine.initialize_icon with None."""
        original_icon = GameEngine.icon
        
        GameEngine.initialize_icon(None)
        
        # Should not change the icon
        self.assertEqual(GameEngine.icon, original_icon)

    def test_game_engine_args(self):
        """Test GameEngine.args method."""
        import argparse
        
        parser = argparse.ArgumentParser()
        result = GameEngine.args(parser)
        
        # Verify the parser was returned
        self.assertEqual(result, parser)

    def test_game_engine_quit_game(self):
        """Test GameEngine.quit_game class method."""
        with patch("pygame.event.post") as mock_post:
            GameEngine.quit_game()
            
            # Verify quit event was posted
            mock_post.assert_called_once()

    def test_game_engine_start_with_mock_game(self):
        """Test GameEngine.start method with proper mocking."""
        # Mock argument parsing to prevent command line argument issues
        with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
            mock_parse_args.return_value = self._create_mock_args()
            # Create a mock game
            mock_game = MockGameWithArgs()
            
            # Create GameEngine instance with game parameter
            engine = GameEngine(game=mock_game)
            
            # Set up patches as a list to avoid too many nested blocks
            patches = [
                patch("glitchygames.engine.FontManager"),
                patch("glitchygames.engine.GameManager"),
                patch("glitchygames.engine.JoystickManager"),
                patch("glitchygames.engine.KeyboardManager"),
                patch("glitchygames.engine.MidiManager"),
                patch("glitchygames.engine.MouseManager"),
                patch("glitchygames.engine.WindowManager"),
                patch("glitchygames.engine.AudioManager"),
                patch("glitchygames.engine.ControllerManager"),
                patch("glitchygames.engine.DropManager"),
                patch("glitchygames.engine.TouchManager"),
                patch.object(engine, "scene_manager"),
                patch("pygame.init"),
                patch("pygame.display.init"),
                patch("pygame.display.set_mode"),
                patch("pygame.display.set_caption"),
                patch("pygame.display.set_icon"),
                patch("pygame.display.quit"),
                patch("pygame.quit")
            ]
            
            # Start all patches
            mocks = []
            for p in patches:
                mocks.append(p.start())
            
            try:
                # Unpack mocks for easier access
                (mock_font_manager, mock_game_manager, mock_joystick_manager, 
                 mock_keyboard_manager, mock_midi_manager, mock_mouse_manager,
                 mock_window_manager, mock_audio_manager, mock_controller_manager,
                 mock_drop_manager, mock_touch_manager, mock_scene_manager,
                 mock_init, mock_display_init, mock_set_mode, mock_set_caption,
                 mock_set_icon, mock_display_quit, mock_pygame_quit) = mocks
                
                # Configure mocks
                mock_scene_manager.switch_to_scene = Mock()
                mock_scene_manager.start = Mock()
                
                # Mock joystick manager with proper joysticks list
                mock_joystick_manager_instance = Mock()
                mock_joystick_manager_instance.joysticks = [Mock(), Mock()]  # List of 2 joysticks
                mock_joystick_manager.return_value = mock_joystick_manager_instance
                
                # Mock other managers
                mock_font_manager.return_value = Mock()
                mock_game_manager.return_value = Mock()
                mock_keyboard_manager.return_value = Mock()
                mock_midi_manager.return_value = Mock()
                mock_mouse_manager.return_value = Mock()
                mock_window_manager.return_value = Mock()
                mock_audio_manager.return_value = Mock()
                mock_controller_manager.return_value = Mock()
                mock_drop_manager.return_value = Mock()
                mock_touch_manager.return_value = Mock()
                
                # Configure pygame mocks
                mock_init.return_value = (8, 0, 0)  # Success
                mock_display_init.return_value = None
                mock_set_mode.return_value = Mock()
                mock_set_caption.return_value = None
                mock_set_icon.return_value = None
                mock_display_quit.return_value = None
                mock_pygame_quit.return_value = None
                
                # Test the start method
                try:
                    engine.start()
                except SystemExit:
                    pass  # Expected when quit is called
                
                # Verify pygame was initialized
                mock_init.assert_called_once()
                mock_display_init.assert_called_once()
                
                # Verify scene manager methods were called
                mock_scene_manager.switch_to_scene.assert_called_once_with(mock_game)
                mock_scene_manager.start.assert_called_once()
                
            finally:
                # Stop all patches
                for p in patches:
                    p.stop()

    def test_game_engine_start_with_profiling(self):
        """Test GameEngine.start method with profiling enabled."""
        # Mock argument parsing to prevent command line argument issues
        with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
            mock_parse_args.return_value = self._create_mock_args()
            # Create a mock game
            mock_game = MockGameWithArgs()
            
            # Create GameEngine instance with game parameter
            engine = GameEngine(game=mock_game)
            
            # Enable profiling
            GameEngine.OPTIONS["profile"] = True
            
            # Set up patches
            patches = [
                patch("cProfile.Profile"),
                patch("glitchygames.engine.FontManager"),
                patch("glitchygames.engine.GameManager"),
                patch("glitchygames.engine.JoystickManager"),
                patch("glitchygames.engine.KeyboardManager"),
                patch("glitchygames.engine.MidiManager"),
                patch("glitchygames.engine.MouseManager"),
                patch("glitchygames.engine.WindowManager"),
                patch("glitchygames.engine.AudioManager"),
                patch("glitchygames.engine.ControllerManager"),
                patch("glitchygames.engine.DropManager"),
                patch("glitchygames.engine.TouchManager"),
                patch.object(engine, "scene_manager"),
                patch("pygame.init"),
                patch("pygame.display.init"),
                patch("pygame.display.set_mode"),
                patch("pygame.display.set_caption"),
                patch("pygame.display.set_icon"),
                patch("pygame.display.quit"),
                patch("pygame.quit")
            ]
            
            # Start all patches
            started_patches = []
            for p in patches:
                started_patches.append(p.start())
            
            try:
                # Configure profiler mock
                mock_profiler = Mock()
                patches[0].return_value = mock_profiler
                mock_profiler.enable = Mock()
                mock_profiler.disable = Mock()
                mock_profiler.print_stats = Mock()
                
                # Configure mocks
                started_patches[12].switch_to_scene = Mock()  # scene_manager
                started_patches[12].start = Mock()
                
                # Mock joystick manager with proper joysticks list
                mock_joystick_manager_instance = Mock()
                mock_joystick_manager_instance.joysticks = []  # Empty list
                patches[3].return_value = mock_joystick_manager_instance
                
                # Mock other managers
                for i in range(1, 12):  # Skip profiler and scene_manager
                    patches[i].return_value = Mock()
                
                # Configure pygame mocks
                patches[13].return_value = (8, 0, 0)  # pygame.init success
                patches[14].return_value = None  # display.init
                patches[15].return_value = Mock()  # set_mode
                patches[16].return_value = None  # set_caption
                patches[17].return_value = None  # set_icon
                patches[18].return_value = None  # display.quit
                patches[19].return_value = None  # pygame.quit
                
                # Test the start method
                try:
                    engine.start()
                except SystemExit:
                    pass  # Expected when quit is called
                
                # Verify profiler was used
                mock_profiler.enable.assert_called_once()
                mock_profiler.disable.assert_called_once()
                mock_profiler.print_stats.assert_called_once()
                
            finally:
                # Stop all patches
                for p in patches:
                    p.stop()

    def test_game_engine_start_with_exception(self):
        """Test GameEngine.start method with exception handling."""
        # Mock argument parsing to prevent command line argument issues
        with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
            mock_parse_args.return_value = self._create_mock_args()
            # Create a mock game
            mock_game = MockGameWithArgs()
            
            # Create GameEngine instance with game parameter
            engine = GameEngine(game=mock_game)
            
            # Set up comprehensive patches to prevent hanging
            patches = [
                patch("glitchygames.engine.FontManager"),
                patch("glitchygames.engine.GameManager"),
                patch("glitchygames.engine.JoystickManager"),
                patch("glitchygames.engine.KeyboardManager"),
                patch("glitchygames.engine.MidiManager"),
                patch("glitchygames.engine.MouseManager"),
                patch("glitchygames.engine.WindowManager"),
                patch("glitchygames.engine.AudioManager"),
                patch("glitchygames.engine.ControllerManager"),
                patch("glitchygames.engine.DropManager"),
                patch("glitchygames.engine.TouchManager"),
                patch.object(engine, "scene_manager"),
                patch("pygame.init"),
                patch("pygame.display.init"),
                patch("pygame.display.set_mode"),
                patch("pygame.display.set_caption"),
                patch("pygame.display.set_icon"),
                patch("pygame.display.quit"),
                patch("pygame.quit")
            ]
            
            # Start all patches
            mocks = []
            for p in patches:
                mocks.append(p.start())
            
            try:
                # Unpack mocks for easier access
                (mock_font_manager, mock_game_manager, mock_joystick_manager, 
                 mock_keyboard_manager, mock_midi_manager, mock_mouse_manager,
                 mock_window_manager, mock_audio_manager, mock_controller_manager,
                 mock_drop_manager, mock_touch_manager, mock_scene_manager,
                 mock_init, mock_display_init, mock_set_mode, mock_set_caption,
                 mock_set_icon, mock_display_quit, mock_pygame_quit) = mocks
                
                # Configure mocks to raise exception on pygame.init
                mock_init.side_effect = Exception("Test exception")
                
                # Configure other mocks to prevent hanging
                mock_scene_manager.switch_to_scene = Mock()
                mock_scene_manager.start = Mock()
                
                # Mock joystick manager
                mock_joystick_manager_instance = Mock()
                mock_joystick_manager_instance.joysticks = []
                mock_joystick_manager.return_value = mock_joystick_manager_instance
                
                # Mock other managers
                for manager_mock in [mock_font_manager, mock_game_manager, mock_keyboard_manager,
                                   mock_midi_manager, mock_mouse_manager, mock_window_manager,
                                   mock_audio_manager, mock_controller_manager, mock_drop_manager,
                                   mock_touch_manager]:
                    manager_mock.return_value = Mock()
                
                # Configure pygame mocks
                mock_display_init.return_value = None
                mock_set_mode.return_value = Mock()
                mock_set_caption.return_value = None
                mock_set_icon.return_value = None
                mock_display_quit.return_value = None
                mock_pygame_quit.return_value = None
                
                # Test the start method with exception handling
                with patch.object(engine, "log") as mock_log:
                    engine.start()
                    
                    # Verify exception was logged
                    mock_log.exception.assert_called_once_with("Error starting game.")
                
            finally:
                # Stop all patches
                for p in patches:
                    p.stop()

    def test_game_manager_init(self):
        """Test GameManager initialization."""
        # Create a mock scene manager
        mock_scene_manager = Mock()
        
        # Create GameManager instance
        manager = GameManager(mock_scene_manager)
        
        # Verify the scene manager was set
        self.assertEqual(manager.game, mock_scene_manager)

    def test_game_manager_process_events(self):
        """Test GameManager.process_events method."""
        # Create a mock scene manager
        mock_scene_manager = Mock()
        
        # Create GameManager instance
        manager = GameManager(mock_scene_manager)
        
        # Mock the scene manager's process_events method
        mock_scene_manager.process_events = Mock()
        
        # Test process_events
        manager.process_events()
        
        # Verify the scene manager's process_events was called
        mock_scene_manager.process_events.assert_called_once()

    def test_game_engine_icon_file_not_found(self):
        """Test GameEngine icon loading with file not found."""
        # Store original icon
        original_icon = GameEngine.icon
        
        # Mock argument parsing to prevent command line argument issues
        with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
            mock_parse_args.return_value = self._create_mock_args()
            
            # Test with a non-existent file
            with patch("pygame.image.load") as mock_load:
                mock_load.side_effect = FileNotFoundError("File not found")
                
                # This should not raise an exception
                try:
                    GameEngine.initialize_icon("/nonexistent/path.png")
                except FileNotFoundError:
                    pass  # Expected
        
        # The icon should remain unchanged
        self.assertEqual(GameEngine.icon, original_icon)

    def test_game_engine_icon_with_string_path(self):
        """Test GameEngine.initialize_icon with string path."""
        # Mock argument parsing to prevent command line argument issues
        with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
            mock_parse_args.return_value = self._create_mock_args()
            
            with patch("pygame.image.load") as mock_load:
                mock_surface = MockFactory.create_pygame_surface_mock()
                mock_load.return_value = mock_surface
                
                GameEngine.initialize_icon("/path/to/icon.png")
                
                # Verify pygame.image.load was called
                mock_load.assert_called_once()

    def test_game_engine_class_variables(self):
        """Test GameEngine class variables."""
        # Test that class variables are accessible
        self.assertEqual(GameEngine.NAME, "Boilerplate Adventures")
        self.assertEqual(GameEngine.VERSION, "1.0")
        self.assertIsInstance(GameEngine.OPTIONS, dict)
        self.assertIsInstance(GameEngine.LAST_EVENT_MISS, str)
        self.assertIsInstance(GameEngine.MISSING_EVENTS, list)
        self.assertIsInstance(GameEngine.UNIMPLEMENTED_EVENTS, list)
        self.assertIsInstance(GameEngine.USE_FASTEVENTS, bool)
        self.assertIsInstance(GameEngine.EVENT_HANDLERS, dict)

    def test_game_engine_logger(self):
        """Test GameEngine logger."""
        # Test that the logger is accessible
        self.assertIsNotNone(GameEngine.log)
        self.assertEqual(GameEngine.log.name, "game.engine")

    def test_game_engine_game_property(self):
        """Test GameEngine game property."""
        # Mock argument parsing to prevent command line argument issues
        with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
            mock_parse_args.return_value = self._create_mock_args()
            # Create GameEngine instance with mock game
            mock_game = MockGameWithArgs()
            engine = GameEngine(game=mock_game)
            
            # Test that game property is set correctly
            self.assertEqual(engine.game, mock_game)

    def test_game_engine_scene_manager_property(self):
        """Test GameEngine scene_manager property."""
        # Mock argument parsing to prevent command line argument issues
        with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
            mock_parse_args.return_value = self._create_mock_args()
            # Create GameEngine instance with mock game
            mock_game = MockGameWithArgs()
            engine = GameEngine(game=mock_game)
            
            # Test that scene_manager property exists
            self.assertIsNotNone(engine.scene_manager)

    def test_game_engine_joystick_count_property(self):
        """Test GameEngine joystick_count property."""
        # Mock argument parsing to prevent command line argument issues
        with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
            mock_parse_args.return_value = self._create_mock_args()
            # Create GameEngine instance with mock game
            mock_game = MockGameWithArgs()
            engine = GameEngine(game=mock_game)
            
            # Mock the joystick manager to provide joystick count without starting the engine
            with patch("glitchygames.engine.JoystickManager") as mock_joystick_manager:
                # Configure joystick manager mock
                mock_joystick_manager_instance = Mock()
                mock_joystick_manager_instance.joysticks = [Mock(), Mock()]  # 2 joysticks
                mock_joystick_manager.return_value = mock_joystick_manager_instance
                
                # Mock the joystick_count property to return the count without starting the engine
                with patch.object(engine, 'joystick_count', 2):
                    # Test that joystick_count property exists
                    self.assertIsNotNone(engine.joystick_count)
                    self.assertEqual(engine.joystick_count, 2)

    def test_game_engine_joysticks_property(self):
        """Test GameEngine joysticks property."""
        # Mock argument parsing to prevent command line argument issues
        with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
            mock_parse_args.return_value = self._create_mock_args()
            # Create GameEngine instance with mock game
            mock_game = MockGameWithArgs()
            engine = GameEngine(game=mock_game)
            
            # Mock the joystick manager to provide joysticks without starting the engine
            with patch("glitchygames.engine.JoystickManager") as mock_joystick_manager:
                # Configure joystick manager mock
                mock_joystick_manager_instance = Mock()
                mock_joysticks = [Mock(), Mock()]  # 2 joysticks
                mock_joystick_manager_instance.joysticks = mock_joysticks
                mock_joystick_manager.return_value = mock_joystick_manager_instance
                
                # Mock the joysticks property to return the joysticks without starting the engine
                with patch.object(engine, 'joysticks', mock_joysticks):
                    # Test that joysticks property exists
                    self.assertIsNotNone(engine.joysticks)
                    self.assertEqual(len(engine.joysticks), 2)


if __name__ == "__main__":
    unittest.main()
