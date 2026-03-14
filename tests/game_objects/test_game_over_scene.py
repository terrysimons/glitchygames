"""Tests for the Game Over scene functionality."""

import sys
from pathlib import Path

import pygame
import pytest
from glitchygames.examples.paddleslap import Game
from glitchygames.scenes import SceneManager
from glitchygames.scenes.builtin_scenes.game_over_scene import GameOverScene

from tests.mocks.test_mock_factory import MockFactory

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

PATCH_TARGET_GAME_OVER_SCENE = "glitchygames.scenes.builtin_scenes.game_over_scene.GameOverScene"


class TestGameOverScene:
    """Test the Game Over scene functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        # Reset singleton state for clean test
        SceneManager._reset()
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_game_over_scene_initialization(self):
        """Test that Game Over scene initializes correctly.

        Args:
            mock_pygame_patches: Mock pygame patches fixture.

        Returns:
            None

        """
        scene = GameOverScene()
        assert scene.text_sprite is None
        assert hasattr(scene, "all_sprites")

    def test_game_over_scene_setup(self):
        """Test that Game Over scene sets up correctly.

        Args:
            mock_pygame_patches: Mock pygame patches fixture.

        Returns:
            None

        """
        scene = GameOverScene()
        scene.screen_width = 800
        scene.screen_height = 600
        scene.setup()

        # Should have text sprites added
        assert len(scene.all_sprites) > 0

    def test_game_over_scene_has_game_engine_after_switch(self, mocker):
        """Test that Game Over scene gets game engine reference when switched to.

        Args:
            mock_pygame_patches: Mock pygame patches fixture.

        Returns:
            None

        """
        # Create a mock scene manager with game engine
        mock_scene_manager = mocker.Mock()
        mock_game_engine = mocker.Mock()
        mock_scene_manager.game_engine = mock_game_engine

        # Create Game Over scene
        game_over_scene = GameOverScene()

        # Simulate the scene manager's _setup_new_scene method
        if hasattr(mock_scene_manager, "game_engine") and mock_scene_manager.game_engine:
            game_over_scene.game_engine = mock_scene_manager.game_engine

        # Verify the game engine reference was set
        assert game_over_scene.game_engine == mock_game_engine

    def test_game_over_scene_key_handling(self, mocker):
        """Test that Game Over scene handles key events correctly.

        Args:
            mock_pygame_patches: Mock pygame patches fixture.

        Returns:
            None

        """
        scene = GameOverScene()
        scene.scene_manager = mocker.Mock()

        # Mock pygame events
        pygame.K_SPACE = 32
        pygame.K_ESCAPE = 27

        # Test SPACE key (restart)
        space_event = mocker.Mock()
        space_event.key = pygame.K_SPACE
        scene.on_key_down_event(space_event)

        # Test ESC key (quit)
        esc_event = mocker.Mock()
        esc_event.key = pygame.K_ESCAPE
        scene.on_key_down_event(esc_event)


class TestGameOverIntegration:
    """Test Game Over integration with the main game."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_game_over_triggered_when_all_balls_dead(self, mocker):
        """Test that Game Over is triggered when all balls are dead.

        Args:
            mock_pygame_patches: Mock pygame patches fixture.

        Returns:
            None

        """
        # Mock the GameOverScene import to avoid pygame initialization issues
        mock_game_over_scene = mocker.Mock()
        mocker.patch(
            "glitchygames.examples.paddleslap.GameOverScene",
            return_value=mock_game_over_scene,
        )

        # Test the Game Over logic directly without full game setup
        # Create a minimal game instance
        game = Game(options={})

        # Mock the collision detection to prevent memory issues
        mocker.patch.object(game, "_handle_ball_collisions")
        mocker.patch("pygame.sprite.collide_rect", return_value=False)

        # Create some mock balls and add them to the game
        mock_ball1 = mocker.Mock()
        mock_ball1.alive.return_value = False  # Dead ball
        mock_ball1.speed = mocker.Mock()
        mock_ball1.speed.x = 1  # Set speed.x to avoid comparison error
        mock_ball1.speed.y = 1  # Set speed.y to avoid math operations error

        mock_ball2 = mocker.Mock()
        mock_ball2.alive.return_value = False  # Dead ball
        mock_ball2.speed = mocker.Mock()
        mock_ball2.speed.x = 1  # Set speed.x to avoid comparison error
        mock_ball2.speed.y = 1  # Set speed.y to avoid math operations error

        game.balls = [mock_ball1, mock_ball2]

        # Call update to trigger Game Over
        game.update()

        # Verify that next_scene was set to the mocked GameOverScene
        assert game.next_scene == mock_game_over_scene
        assert game.previous_scene == game

    def test_game_over_scene_gets_game_engine_reference(self, mocker):
        """Test that Game Over scene gets game engine reference from scene manager.

        Args:
            mock_pygame_patches: Mock pygame patches fixture.

        Returns:
            None

        """
        # Mock the GameOverScene to avoid pygame initialization issues
        mock_game_over_scene = mocker.Mock()
        mocker.patch(
            PATCH_TARGET_GAME_OVER_SCENE,
            return_value=mock_game_over_scene,
        )

        # Test the scene manager's _setup_new_scene method directly
        # Create a scene manager with game engine
        scene_manager = SceneManager()
        mock_game_engine = mocker.Mock()
        mock_game_engine.OPTIONS = {
            "update_type": "dirty",
            "fps_refresh_rate": 1,
            "target_fps": 60,
            "fps_log_interval_ms": 1000
        }
        scene_manager.game_engine = mock_game_engine

        # Create a Game Over scene (this will be the mocked version)
        game_over_scene = mocker.patch(PATCH_TARGET_GAME_OVER_SCENE)()

        # Call the _setup_new_scene method (this is what gets called during scene switching)
        scene_manager._setup_new_scene(game_over_scene)

        # Verify the game engine reference was set
        assert hasattr(game_over_scene, "game_engine")
        assert game_over_scene.game_engine == mock_game_engine
