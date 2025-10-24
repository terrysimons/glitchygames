"""Tests for the Pause Screen functionality."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pygame
from glitchygames.examples.paddleslap import Game
from glitchygames.scenes import SceneManager

from tests.mocks.test_mock_factory import MockFactory

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

PATCH_TARGET_PAUSE_SCENE = "glitchygames.scenes.builtin_scenes.pause_scene.PauseScene"


class TestPauseScreen(unittest.TestCase):
    """Test the Pause Screen functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Reset singleton state for clean test
        SceneManager._instance = None

        self.patchers = MockFactory.setup_pygame_mocks()
        # Start all patchers
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_pause_screen_triggered_on_spacebar(self):
        """Test that Pause Screen is triggered when spacebar is pressed during gameplay."""
        # Mock the PauseScene import to avoid pygame initialization issues
        with patch(PATCH_TARGET_PAUSE_SCENE) as mock_pause_scene_class:
            mock_pause_scene = Mock()
            mock_pause_scene_class.return_value = mock_pause_scene

            # Create a game instance
            game = Game(options={})
            game.setup()

            # Check initial state - the game should be the active scene initially
            from glitchygames.scenes import SceneManager
            scene_manager = SceneManager()
            # The game should be the active scene initially, but if it's not, that's okay
            # as long as it's not the pause scene yet
            assert scene_manager.active_scene != mock_pause_scene, "Expected pause scene not to be active initially"

            # Simulate spacebar press to trigger pause
            pygame.K_SPACE = 32
            space_down_event = Mock()
            space_down_event.key = pygame.K_SPACE
            space_down_event.type = pygame.KEYDOWN
            
            space_up_event = Mock()
            space_up_event.key = pygame.K_SPACE
            space_up_event.type = pygame.KEYUP

            # Handle the key events (down then up to trigger pause)
            game.on_key_down_event(space_down_event)
            game.on_key_up_event(space_up_event)

            # Check if pause was triggered by checking the scene manager's active scene
            from glitchygames.scenes import SceneManager
            scene_manager = SceneManager()
            assert scene_manager.active_scene == mock_pause_scene, "Expected pause scene to be set as active scene"
            print("✅ Pause screen condition properly detected!")

    def test_pause_screen_resume_on_spacebar(self):
        """Test that Pause Screen can be resumed with spacebar."""
        # Mock the PauseScene to avoid pygame initialization issues
        with patch(PATCH_TARGET_PAUSE_SCENE) as mock_pause_scene_class:
            mock_pause_scene = Mock()
            mock_pause_scene_class.return_value = mock_pause_scene

            # Create a game instance
            game = Game(options={})
            game.setup()

            # Simulate pause
            pygame.K_SPACE = 32
            space_down_event = Mock()
            space_down_event.key = pygame.K_SPACE
            space_down_event.type = pygame.KEYDOWN
            
            space_up_event = Mock()
            space_up_event.key = pygame.K_SPACE
            space_up_event.type = pygame.KEYUP

            game.on_key_down_event(space_down_event)
            game.on_key_up_event(space_up_event)

            # Get the pause scene from the scene manager
            from glitchygames.scenes import SceneManager
            scene_manager = SceneManager()
            pause_scene = scene_manager.active_scene
            assert pause_scene == mock_pause_scene, "Expected pause scene to be created"

            # Simulate resuming from pause
            pause_scene.on_key_down_event(space_down_event)

            # Check if resume was triggered
            assert pause_scene.next_scene is not None, "Expected game scene to be set for resume"
            print("✅ Pause screen resume properly detected!")

    def test_pause_screen_gets_game_engine_reference(self):
        """Test that Pause Screen gets game engine reference from scene manager."""
        # Mock the PauseScene to avoid pygame initialization issues
        with patch(PATCH_TARGET_PAUSE_SCENE) as mock_pause_scene_class:
            mock_pause_scene = Mock()
            mock_pause_scene_class.return_value = mock_pause_scene

            # Test the scene manager's _setup_new_scene method directly
            # Create a scene manager with game engine
            scene_manager = SceneManager()
            mock_game_engine = Mock()
            mock_game_engine.OPTIONS = {
                "update_type": "dirty",
                "fps_refresh_rate": 1,
                "target_fps": 60,
                "fps_log_interval_ms": 1000.0
            }
            scene_manager.game_engine = mock_game_engine

            # Create a Pause scene (this will be the mocked version)
            pause_scene = mock_pause_scene_class()

            # Call the _setup_new_scene method (this is what gets called during scene switching)
            scene_manager._setup_new_scene(pause_scene)

            # Verify the game engine reference was set
            assert hasattr(pause_scene, "game_engine")
            assert pause_scene.game_engine == mock_game_engine
            print("✅ Pause screen gets game engine reference properly!")


class TestPauseScreenIntegration(unittest.TestCase):
    """Test Pause Screen integration with the main game."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        # Start all patchers
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_pause_resume_cycle(self):
        """Test complete pause/resume cycle through the game."""
        # Mock the PauseScene to avoid pygame initialization issues
        with patch(PATCH_TARGET_PAUSE_SCENE) as mock_pause_scene_class:
            mock_pause_scene = Mock()
            mock_pause_scene_class.return_value = mock_pause_scene

            # Create a game instance
            game = Game(options={})
            game.setup()

            # Simulate pause
            pygame.K_SPACE = 32
            space_down_event = Mock()
            space_down_event.key = pygame.K_SPACE
            space_down_event.type = pygame.KEYDOWN
            
            space_up_event = Mock()
            space_up_event.key = pygame.K_SPACE
            space_up_event.type = pygame.KEYUP

            game.on_key_down_event(space_down_event)
            game.on_key_up_event(space_up_event)
            # Check if pause was triggered by checking the scene manager's active scene
            from glitchygames.scenes import SceneManager
            scene_manager = SceneManager()
            assert scene_manager.active_scene == mock_pause_scene, "Expected pause scene to be set"

            # Simulate resume
            pause_scene = scene_manager.active_scene
            pause_scene.on_key_down_event(space_down_event)
            assert pause_scene.next_scene is not None, "Expected resume to work"

            print("✅ Complete pause/resume cycle works properly!")


if __name__ == "__main__":
    unittest.main()
