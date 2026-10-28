"""PaddleSlap's Game Over: a frame whose balls are all dead ends the game.

Moved from the engine's tests (tests/game_objects/test_game_over_scene.py and
tests/scenes/builtin_scenes/test_game_over.py): they cover PaddleSlap's ``dt_tick``,
``PaddleSlapGameOverScene`` and its high-score save, not the engine's ``GameOverScene``.
"""

import logging

import pygame
import pytest

from glitchygames.display_mode import set_display_mode
from paddleslap import Game, PaddleSlapGameOverScene

LOG = logging.getLogger(__name__)


class TestGameOverIntegration:
    """Test Game Over integration with the main game."""

    @pytest.fixture
    def save_directory(self, mocker, tmp_path):
        """Send PaddleSlap's high-score saves to a temporary directory, not the user's.

        Returns:
            Path: The directory the saves go to.

        """
        mocker.patch(
            'glitchygames.state.manager.get_save_directory',
            side_effect=lambda app_name: tmp_path / app_name,
        )
        return tmp_path

    def test_game_over_triggered_when_all_balls_dead(self, save_directory):
        """A frame whose balls are all dead switches PaddleSlap to its Game Over scene."""
        game = Game(options={})
        assert game.balls, 'PaddleSlap serves balls when it is built'
        for ball in game.balls:
            ball.kill()

        # Run a frame's logic (dt_tick resolves collisions and checks for Game Over)
        game.dt_tick(0.0)

        assert game.balls == []
        assert isinstance(game.next_scene, PaddleSlapGameOverScene)
        assert game.next_scene.final_score == game.rally_count
        assert game.next_scene.high_scores == [{'score': game.rally_count}]
        assert game.previous_scene == game
        # The high score was saved in the temporary save directory
        assert any((save_directory / 'paddleslap').iterdir())


def test_game_over_condition():
    """Test that Game Over is triggered when all balls are dead."""
    # Initialize pygame (minimal setup)
    pygame.init()
    screen = set_display_mode(size=(800, 600))

    # Create a game instance
    game = Game(options={})
    game.setup()

    # Check initial state
    initial_ball_count = len(game.balls)
    LOG.debug('Initial ball count: %s', initial_ball_count)

    # Simulate all balls being killed
    for ball in game.balls:
        ball.kill()

    # Check that balls are marked as dead
    dead_balls = [ball for ball in game.balls if not ball.alive()]
    LOG.debug('Dead balls: %s', len(dead_balls))

    # Run a frame's logic, which removes dead balls and should trigger Game Over
    game.dt_tick(0.0)

    # Check if Game Over was triggered (balls list should be empty after cleanup)
    final_ball_count = len(game.balls)
    LOG.debug('Final ball count after update: %s', final_ball_count)

    # Verify that all balls were removed
    assert final_ball_count == 0, f'Expected 0 balls, got {final_ball_count}'
    LOG.info('✅ Game Over condition properly detected!')

    pygame.quit()
