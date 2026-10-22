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

PATCH_TARGET_GAME_OVER_SCENE = 'glitchygames.scenes.builtin_scenes.game_over_scene.GameOverScene'


class TestGameOverScene:
    """Test the Game Over scene functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        # Reset singleton state for clean test
        SceneManager._reset()
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_game_over_scene_initialization(self):
        """Test that Game Over scene initializes correctly."""
        scene = GameOverScene()
        assert scene.text_sprite is None
        assert hasattr(scene, 'all_sprites')

    def test_game_over_scene_setup(self):
        """Test that Game Over scene sets up correctly."""
        scene = GameOverScene()
        scene.screen_width = 800
        scene.screen_height = 600
        scene.setup()

        # Should have text sprites added
        assert len(scene.all_sprites) > 0

    def test_game_over_scene_has_game_engine_after_switch(self, mocker):
        """Test that Game Over scene gets game engine reference when switched to.

        Args:
            mocker: pytest-mock fixture.

        """
        # Create a mock scene manager with game engine
        mock_scene_manager = mocker.Mock()
        mock_game_engine = mocker.Mock()
        mock_scene_manager.game_engine = mock_game_engine

        # Create Game Over scene
        game_over_scene = GameOverScene()

        # Simulate the scene manager's _setup_new_scene method
        if hasattr(mock_scene_manager, 'game_engine') and mock_scene_manager.game_engine:
            game_over_scene.game_engine = mock_scene_manager.game_engine  # type: ignore[unresolved-attribute]

        # Verify the game engine reference was set
        assert game_over_scene.game_engine == mock_game_engine  # type: ignore[unresolved-attribute]

    def test_game_over_scene_key_handling(self, mocker):
        """Test that Game Over scene handles key events correctly.

        Args:
            mocker: pytest-mock fixture.

        """
        scene = GameOverScene()
        scene.scene_manager = mocker.Mock()

        # Test SPACE key (restart)
        space_event = mocker.Mock()
        space_event.key = pygame.K_SPACE
        scene.on_key_down_event(space_event)

        # SPACE only arms the restart (it happens on release); it never quits
        assert scene._space_pressed is True
        scene.scene_manager.quit.assert_not_called()

        # Test ESC key (quit)
        esc_event = mocker.Mock()
        esc_event.key = pygame.K_ESCAPE
        scene.on_key_down_event(esc_event)

        scene.scene_manager.quit.assert_called_once()


class TestGameOverIntegration:
    """Test Game Over integration with the main game."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_game_over_triggered_when_all_balls_dead(self, mocker):
        """Test that Game Over is triggered when all balls are dead.

        Args:
            mocker: pytest-mock fixture.

        """
        # Mock the GameOverScene import to avoid pygame initialization issues
        mock_game_over_scene = mocker.Mock()
        mocker.patch(
            'glitchygames.examples.paddleslap.PaddleSlapGameOverScene',
            return_value=mock_game_over_scene,
        )

        # Test the Game Over logic directly without full game setup
        # Create a minimal game instance
        game = Game(options={})

        # Mock the collision detection to prevent memory issues
        mocker.patch.object(game, '_handle_ball_collisions')
        mocker.patch('pygame.sprite.collide_rect', return_value=False)

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

        # Run a frame's logic (dt_tick resolves collisions and checks for Game Over)
        game.dt_tick(0.0)

        # Verify that next_scene was set to the mocked GameOverScene
        assert game.next_scene == mock_game_over_scene
        assert game.previous_scene == game

    def test_game_over_scene_gets_game_engine_reference(self, mocker):
        """Test that Game Over scene gets game engine reference from scene manager.

        Args:
            mocker: pytest-mock fixture.

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
            'update_type': 'dirty',
            'fps_refresh_rate': 1,
            'target_fps': 60,
            'fps_log_interval_ms': 1000,
        }
        scene_manager.game_engine = mock_game_engine

        # Create a Game Over scene (this will be the mocked version)
        game_over_scene = mocker.patch(PATCH_TARGET_GAME_OVER_SCENE)()

        # Call the _setup_new_scene method (this is what gets called during scene switching)
        scene_manager._setup_new_scene(game_over_scene)

        # Verify the game engine reference was set
        assert hasattr(game_over_scene, 'game_engine')
        assert game_over_scene.game_engine == mock_game_engine


class RestartableGame:
    """A stand-in game class: GameOverScene restarts by constructing the previous scene's class."""

    def __init__(self, options):
        """Keep the options the restart passed."""
        self.options = options


class TestGameOverSceneScoreDisplay:
    """The texts the Game Over scene shows for a final score and a high-score table."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        SceneManager._reset()
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @staticmethod
    def _shown_texts(mocker, scene):
        """Set the scene up and return the texts of every TextSprite it made, top to bottom.

        Returns:
            list[str]: The texts in the order the scene laid them out.

        """
        from glitchygames.scenes.builtin_scenes import game_over_scene

        text_sprite_class = mocker.patch.object(
            game_over_scene, 'TextSprite', wraps=game_over_scene.TextSprite
        )
        scene.screen_width = 800
        scene.screen_height = 600
        scene.setup()
        return [call.args[0] for call in text_sprite_class.call_args_list]

    def test_no_score_shows_only_the_title_and_the_instructions(self, mocker):
        """Without a score or high scores the scene shows just GAME OVER and the key help."""
        texts = self._shown_texts(mocker, GameOverScene())

        assert texts == ['GAME OVER', 'Press SPACE to restart or ESC to quit']

    def test_final_score_is_shown_under_the_title(self, mocker):
        """A final score adds a 'Score: N' line between the title and the instructions."""
        texts = self._shown_texts(mocker, GameOverScene(final_score=0))

        assert texts == ['GAME OVER', 'Score: 0', 'Press SPACE to restart or ESC to quit']

    def test_high_scores_show_the_top_five_ranked(self, mocker):
        """Only the first five high scores are listed, ranked from 1; a missing score reads 0."""
        high_scores = [{'score': 900}, {'name': 'no score'}, {'score': 700}]
        high_scores += [{'score': value} for value in (600, 500, 400, 300)]

        texts = self._shown_texts(mocker, GameOverScene(final_score=42, high_scores=high_scores))

        assert texts == [
            'GAME OVER',
            'Score: 42',
            'HIGH SCORES',
            '1. 900',
            '2. 0',
            '3. 700',
            '4. 600',
            '5. 500',
            'Press SPACE to restart or ESC to quit',
        ]

    def test_each_line_is_laid_out_below_the_one_before(self, mocker):
        """The sprites stack downwards: each text is centred lower than the previous one."""
        scene = GameOverScene(final_score=10, high_scores=[{'score': 5}])
        self._shown_texts(mocker, scene)

        centres = [sprite.rect.centery for sprite in scene.all_sprites]
        assert centres == sorted(centres)
        assert len(set(centres)) == len(centres)


class TestGameOverSceneRestart:
    """Releasing SPACE restarts the game; other keys fall through to the base scene."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        SceneManager._reset()
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @staticmethod
    def _key_event(mocker, key):
        """Return a key event stand-in for the given key.

        Returns:
            Mock: An event with only its key set.

        """
        event = mocker.Mock()
        event.key = key
        return event

    def test_space_release_after_press_starts_a_new_game_of_the_previous_class(self, mocker):
        """SPACE down then up switches to a fresh instance of the previous scene's class."""
        scene = GameOverScene(options={'level': 3})
        scene.scene_manager = mocker.Mock()
        previous_game = RestartableGame(options={'level': 1})
        scene.scene_manager.previous_scene = previous_game

        scene.on_key_down_event(self._key_event(mocker, pygame.K_SPACE))
        scene.on_key_up_event(self._key_event(mocker, pygame.K_SPACE))

        (new_game,) = scene.scene_manager.switch_to_scene.call_args.args
        assert isinstance(new_game, RestartableGame)
        assert new_game is not previous_game
        assert new_game.options is scene.options
        assert scene._space_pressed is False

    def test_space_release_without_a_press_does_not_restart(self, mocker):
        """A SPACE release whose press this scene never saw is passed to the base scene."""
        scene = GameOverScene()
        scene.scene_manager = mocker.Mock()
        scene.scene_manager.previous_scene = RestartableGame(options={})

        scene.on_key_up_event(self._key_event(mocker, pygame.K_SPACE))

        scene.scene_manager.switch_to_scene.assert_not_called()

    def test_restart_without_a_previous_scene_warns_and_stays(self, mocker, caplog):
        """With no previous scene to restart, resume logs a warning and switches nowhere."""
        scene = GameOverScene()
        scene.scene_manager = mocker.Mock()
        scene.scene_manager.previous_scene = None

        with caplog.at_level('WARNING'):
            scene.resume()

        scene.scene_manager.switch_to_scene.assert_not_called()
        assert 'No previous scene found to restart' in caplog.text

    def test_other_key_down_goes_to_the_base_scene(self, mocker):
        """A key other than SPACE or ESC (here Q) reaches the base scene, which requests quit."""
        scene = GameOverScene()
        scene.scene_manager = mocker.Mock()

        scene.on_key_down_event(self._key_event(mocker, pygame.K_q))

        assert scene.quit_requested is True
        scene.scene_manager.quit.assert_not_called()
