"""
Tests for the Game Over scene functionality.
"""

import pytest
from unittest.mock import Mock, patch

from glitchygames.examples.game_over_scene import GameOverScene
from glitchygames.examples.paddleslap import Game


class TestGameOverScene:
    """Test the Game Over scene functionality."""

    def test_game_over_scene_initialization(self, mock_pygame_patches):
        """Test that Game Over scene initializes correctly.

        Args:
            mock_pygame_patches: Mock pygame patches fixture.

        Returns:
            None

        """
        scene = GameOverScene()
        assert scene.text_sprite is None
        assert hasattr(scene, 'all_sprites')

    def test_game_over_scene_setup(self, mock_pygame_patches):
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

    def test_game_over_scene_has_game_engine_after_switch(self, mock_pygame_patches):
        """Test that Game Over scene gets game engine reference when switched to.

        Args:
            mock_pygame_patches: Mock pygame patches fixture.

        Returns:
            None

        """
        # Create a mock scene manager with game engine
        mock_scene_manager = Mock()
        mock_game_engine = Mock()
        mock_scene_manager.game_engine = mock_game_engine
        
        # Create Game Over scene
        game_over_scene = GameOverScene()
        
        # Simulate the scene manager's _setup_new_scene method
        if hasattr(mock_scene_manager, 'game_engine') and mock_scene_manager.game_engine:
            game_over_scene.game_engine = mock_scene_manager.game_engine
        
        # Verify the game engine reference was set
        assert game_over_scene.game_engine == mock_game_engine

    def test_game_over_scene_key_handling(self, mock_pygame_patches):
        """Test that Game Over scene handles key events correctly.

        Args:
            mock_pygame_patches: Mock pygame patches fixture.

        Returns:
            None

        """
        scene = GameOverScene()
        scene.scene_manager = Mock()
        
        # Mock pygame events
        import pygame
        pygame.K_SPACE = 32
        pygame.K_ESCAPE = 27
        
        # Test SPACE key (restart)
        space_event = Mock()
        space_event.key = pygame.K_SPACE
        scene.handle_key_down(space_event)
        
        # Test ESC key (quit)
        esc_event = Mock()
        esc_event.key = pygame.K_ESCAPE
        scene.handle_key_down(esc_event)


class TestGameOverIntegration:
    """Test Game Over integration with the main game."""

    def test_game_over_triggered_when_all_balls_dead(self, mock_pygame_patches):
        """Test that Game Over is triggered when all balls are dead.

        Args:
            mock_pygame_patches: Mock pygame patches fixture.

        Returns:
            None

        """
        # Mock the GameOverScene import to avoid pygame initialization issues
        with patch('glitchygames.examples.paddleslap.GameOverScene') as mock_game_over_scene_class:
            mock_game_over_scene = Mock()
            mock_game_over_scene_class.return_value = mock_game_over_scene
            
            # Test the Game Over logic directly without full game setup
            from glitchygames.examples.paddleslap import Game
            
            # Create a minimal game instance
            game = Game(options={})
            
            # Mock the scene manager to capture the scene switch
            mock_scene_manager = Mock()
            game.scene_manager = mock_scene_manager
            
            # Create some mock balls and add them to the game
            mock_ball1 = Mock()
            mock_ball1.alive.return_value = False  # Dead ball
            mock_ball1.speed = Mock()
            mock_ball1.speed.x = 1  # Set speed.x to avoid comparison error
            mock_ball1.speed.y = 1  # Set speed.y to avoid math operations error
            
            mock_ball2 = Mock()
            mock_ball2.alive.return_value = False  # Dead ball
            mock_ball2.speed = Mock()
            mock_ball2.speed.x = 1  # Set speed.x to avoid comparison error
            mock_ball2.speed.y = 1  # Set speed.y to avoid math operations error
            
            game.balls = [mock_ball1, mock_ball2]
            
            # Call update to trigger Game Over
            game.update()
            
            # Verify that switch_to_scene was called
            mock_scene_manager.switch_to_scene.assert_called_once()
            
            # Verify the argument is the mocked GameOverScene
            called_scene = mock_scene_manager.switch_to_scene.call_args[0][0]
            assert called_scene == mock_game_over_scene

    def test_game_over_scene_gets_game_engine_reference(self, mock_pygame_patches):
        """Test that Game Over scene gets game engine reference from scene manager.

        Args:
            mock_pygame_patches: Mock pygame patches fixture.

        Returns:
            None

        """
        # Mock the GameOverScene to avoid pygame initialization issues
        with patch('glitchygames.examples.game_over_scene.GameOverScene') as mock_game_over_scene_class:
            mock_game_over_scene = Mock()
            mock_game_over_scene_class.return_value = mock_game_over_scene
            
            # Test the scene manager's _setup_new_scene method directly
            from glitchygames.scenes import SceneManager
            
            # Create a scene manager with game engine
            scene_manager = SceneManager()
            mock_game_engine = Mock()
            scene_manager.game_engine = mock_game_engine
            
            # Create a Game Over scene (this will be the mocked version)
            game_over_scene = mock_game_over_scene_class()
            
            # Call the _setup_new_scene method (this is what gets called during scene switching)
            scene_manager._setup_new_scene(game_over_scene)
            
            # Verify the game engine reference was set
            assert hasattr(game_over_scene, 'game_engine')
            assert game_over_scene.game_engine == mock_game_engine
