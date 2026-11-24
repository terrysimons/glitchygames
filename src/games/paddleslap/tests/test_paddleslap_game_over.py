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
from tests.state.recording_saves import saves_holding

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


# A saved table the game cannot read (game code plan, sub-plan 2): refused by default
REFUSED_TABLE = {'scores': [{'score': 50}, {'floor': 3}]}


def test_a_refused_high_score_table_still_shows_this_rally_and_saves_nothing(caplog):
    """The default policy leaves the file as it is, logs once, and the screen gets the rally."""
    saves = saves_holding(REFUSED_TABLE)
    game = object.__new__(Game)
    game.saves, game.rally_count, game.options = saves, 40, {}

    with caplog.at_level(logging.ERROR, logger='glitchygames.state.high_scores'):
        shown = game._save_high_score()

    assert shown == [{'score': 40}]
    assert [call[0] for call in saves.calls] == ['load']
    assert len([record for record in caplog.records if record.levelno == logging.ERROR]) == 1


def test_dropping_invalid_high_scores_saves_the_rally_among_the_valid_ones():
    """--invalid-high-scores drop: the unreadable entry goes, the rest and the rally stay."""
    saves = saves_holding(REFUSED_TABLE)
    game = object.__new__(Game)
    game.saves, game.rally_count, game.options = saves, 40, {'invalid_high_scores': 'drop'}

    assert game._save_high_score() == [{'score': 50}, {'score': 40}]
    assert saves.calls[-1] == ('save', 'high_scores', {'scores': [{'score': 50}, {'score': 40}]})
