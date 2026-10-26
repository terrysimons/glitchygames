"""Tests for the Game Over scene functionality."""

import types

import pygame
import pytest

from glitchygames.events import HashableEvent
from glitchygames.scenes import Scene, SceneManager
from glitchygames.scenes.builtin_scenes.game_over_scene import GameOverScene
from glitchygames.testing.keys import qwerty_scancode
from paddleslap import Game, PaddleSlapGameOverScene


def _key_event(*, event_type: int, key: int) -> pygame.event.Event:
    """Return a real key event for the key, with its US QWERTY scancode.

    Returns:
        pygame.event.Event: The KEYDOWN or KEYUP event.

    """
    return pygame.event.Event(
        event_type, key=key, scancode=qwerty_scancode(key=key), mod=pygame.KMOD_NONE
    )


def _take_quit_events() -> list[pygame.event.Event]:
    """Remove and return the QUIT events waiting in pygame's real event queue.

    Returns:
        list[pygame.event.Event]: The QUIT events.

    """
    return pygame.event.get(eventtype=pygame.QUIT)


# A gamepad's two event layers (glitchygames/input/input_devices.py, rule 1): a mapped pad's
# buttons arrive as controller events, any other device's (or every device's in joystick mode)
# as joystick events, by the same button numbers
GAMEPAD_LAYERS = ('controller', 'joystick')


def _gamepad_button(scene: Scene, *, layer: str, button: int, pressed: bool) -> None:
    """Give the scene a real button press or release from a gamepad on one event layer."""
    if layer == 'controller':
        event_type = pygame.CONTROLLERBUTTONDOWN if pressed else pygame.CONTROLLERBUTTONUP
        event = HashableEvent(event_type, instance_id=0, button=button)
        if pressed:
            scene.on_controller_button_down_event(event)
        else:
            scene.on_controller_button_up_event(event)
        return
    event_type = pygame.JOYBUTTONDOWN if pressed else pygame.JOYBUTTONUP
    event = HashableEvent(event_type, instance_id=0, joy=0, button=button)
    if pressed:
        scene.on_joy_button_down_event(event)
    else:
        scene.on_joy_button_up_event(event)


def _draw_the_active_scene(scene_manager: SceneManager) -> None:
    """Draw the active scene's frame on the display, as the next frame of the loop would.

    The test display rule (tests/display_canvas.py): a switch leaves only the scene's (black)
    background on the display; drawing the frame makes the test end on what the scene shows.
    """
    scene = scene_manager.active_scene
    assert scene is not None
    display = pygame.display.get_surface()
    assert display is not None
    scene.update()
    scene.render(display)


class RecordingDisplayScene(Scene):
    """A real scene that a GameOverScene can follow (and restart)."""

    NAME = 'RecordingDisplayScene'


class TestGameOverScene:
    """Test the Game Over scene functionality."""

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

    def test_game_over_scene_draws_its_title_on_the_display(self):
        """Drawing the set-up scene puts the red GAME OVER title on the real display."""
        display = pygame.display.get_surface()
        display.fill((0, 0, 0))
        scene = GameOverScene()
        scene.screen_width = 800
        scene.screen_height = 600
        scene.setup()
        assert scene.text_sprite is not None

        for sprite in scene.all_sprites:
            display.blit(sprite.image, sprite.rect)

        title_area = display.subsurface(scene.text_sprite.rect)
        red_title_pixels = pygame.transform.threshold(
            None,
            title_area,
            search_color=(255, 0, 0),
            threshold=(60, 60, 60, 255),
            set_behavior=0,
        )
        assert red_title_pixels > 0
        # The title is centred horizontally, a quarter of the way down
        assert scene.text_sprite.rect.centerx == pytest.approx(400, abs=1)
        assert scene.text_sprite.rect.centery == pytest.approx(150, abs=1)

    def test_game_over_scene_key_handling(self):
        """SPACE arms the restart without quitting; ESC posts a real QUIT event."""
        scene = GameOverScene()
        _take_quit_events()

        # Test SPACE key (restart)
        scene.on_key_down_event(_key_event(event_type=pygame.KEYDOWN, key=pygame.K_SPACE))

        # SPACE only arms the restart (it happens on release); it never quits
        assert scene._space_pressed is True
        assert _take_quit_events() == []

        # Test ESC key (quit): the scene manager posts QUIT to pygame's queue
        scene.on_key_down_event(_key_event(event_type=pygame.KEYDOWN, key=pygame.K_ESCAPE))

        assert len(_take_quit_events()) == 1


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

    def test_game_over_scene_gets_game_engine_reference(self, mocker):
        """Switching to a Game Over scene hands it the scene manager's game engine."""
        # Setting a scene's engine copies the engine's OPTIONS onto the SceneManager class
        mocker.patch.object(SceneManager, 'OPTIONS', SceneManager.OPTIONS)
        scene_manager = SceneManager()
        # A stand-in engine holding only the options a scene reads from it
        game_engine = types.SimpleNamespace(
            OPTIONS={
                'update_type': 'dirty',
                'fps_refresh_rate': 1,
                'target_fps': 60,
                'fps_log_interval_ms': 1000,
            }
        )
        scene_manager.game_engine = game_engine
        game_over_scene = GameOverScene()

        # Every switch sets the new scene up through _setup_new_scene
        scene_manager._setup_new_scene(game_over_scene)

        assert game_over_scene.game_engine is game_engine
        assert game_over_scene.text_sprite is not None  # setup() ran


class RestartableGame(Scene):
    """A real game scene: GameOverScene restarts by constructing the previous scene's class."""

    NAME = 'RestartableGame'


class TestGameOverSceneScoreDisplay:
    """The texts the Game Over scene shows for a final score and a high-score table."""

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

    @staticmethod
    def _game_over_after(previous_game: Scene, game_over: GameOverScene) -> SceneManager:
        """Make previous_game then game_over the real scene manager's active scene.

        Returns:
            SceneManager: The manager, with game_over active and previous_game previous.

        """
        scene_manager = SceneManager()
        scene_manager.switch_to_scene(previous_game)
        scene_manager.switch_to_scene(game_over)
        return scene_manager

    def test_space_release_after_press_starts_a_new_game_of_the_previous_class(self):
        """SPACE down then up switches to a fresh instance of the previous scene's class."""
        scene = GameOverScene(options={'level': 3})
        previous_game = RestartableGame(options={'level': 1})
        scene_manager = self._game_over_after(previous_game, scene)

        scene.on_key_down_event(_key_event(event_type=pygame.KEYDOWN, key=pygame.K_SPACE))
        scene.on_key_up_event(_key_event(event_type=pygame.KEYUP, key=pygame.K_SPACE))

        new_game = scene_manager.active_scene
        assert isinstance(new_game, RestartableGame)
        assert new_game is not previous_game
        assert new_game.options is scene.options
        assert scene._space_pressed is False

    def test_space_release_without_a_press_does_not_restart(self):
        """A SPACE release whose press this scene never saw is passed to the base scene."""
        scene = GameOverScene()
        scene_manager = self._game_over_after(RestartableGame(options={}), scene)

        scene.on_key_up_event(_key_event(event_type=pygame.KEYUP, key=pygame.K_SPACE))

        assert scene_manager.active_scene is scene
        _draw_the_active_scene(scene_manager)

    @pytest.mark.parametrize('layer', GAMEPAD_LAYERS)
    @pytest.mark.parametrize('button', [pygame.CONTROLLER_BUTTON_START, pygame.CONTROLLER_BUTTON_A])
    def test_start_or_a_released_after_its_press_restarts(self, layer, button):
        """Start or A, pressed and released, starts a new game (BUGS.md #209 item 10)."""
        scene = GameOverScene(options={})
        previous_game = RestartableGame(options={})
        scene_manager = self._game_over_after(previous_game, scene)

        _gamepad_button(scene, layer=layer, button=button, pressed=True)
        assert scene_manager.active_scene is scene
        _gamepad_button(scene, layer=layer, button=button, pressed=False)

        new_game = scene_manager.active_scene
        assert isinstance(new_game, RestartableGame)
        assert new_game is not previous_game

    @pytest.mark.parametrize('layer', GAMEPAD_LAYERS)
    def test_a_release_whose_press_came_before_game_over_does_not_restart(self, layer):
        """A button held when the game ended (a jump) must not restart on its release."""
        scene = GameOverScene()
        scene_manager = self._game_over_after(RestartableGame(options={}), scene)

        _gamepad_button(scene, layer=layer, button=pygame.CONTROLLER_BUTTON_A, pressed=False)

        assert scene_manager.active_scene is scene
        _draw_the_active_scene(scene_manager)

    @pytest.mark.parametrize('layer', GAMEPAD_LAYERS)
    @pytest.mark.parametrize('button', [pygame.CONTROLLER_BUTTON_B, pygame.CONTROLLER_BUTTON_BACK])
    def test_b_or_back_quits(self, layer, button):
        """B or Back quits on its press, as ESC does: one QUIT event."""
        scene = GameOverScene()
        scene_manager = self._game_over_after(RestartableGame(options={}), scene)
        _take_quit_events()

        _gamepad_button(scene, layer=layer, button=button, pressed=True)

        assert len(_take_quit_events()) == 1
        _draw_the_active_scene(scene_manager)

    @pytest.mark.parametrize('layer', GAMEPAD_LAYERS)
    def test_another_button_does_nothing(self, layer):
        """Any other button neither restarts nor quits."""
        scene = GameOverScene()
        scene_manager = self._game_over_after(RestartableGame(options={}), scene)
        _take_quit_events()

        _gamepad_button(scene, layer=layer, button=pygame.CONTROLLER_BUTTON_X, pressed=True)
        _gamepad_button(scene, layer=layer, button=pygame.CONTROLLER_BUTTON_X, pressed=False)

        assert scene_manager.active_scene is scene
        assert _take_quit_events() == []
        _draw_the_active_scene(scene_manager)

    def test_restart_without_a_previous_scene_warns_and_stays(self, caplog):
        """With no previous scene to restart, resume logs a warning and switches nowhere."""
        scene = GameOverScene()
        scene_manager = SceneManager()
        scene_manager.switch_to_scene(scene)
        assert scene_manager.previous_scene is None

        with caplog.at_level('WARNING'):
            scene.resume()

        assert scene_manager.active_scene is scene
        assert 'No previous scene found to restart' in caplog.text
        _draw_the_active_scene(scene_manager)

    def test_other_key_down_goes_to_the_base_scene(self):
        """A key other than SPACE or ESC (here Q) reaches the base scene: no quit on the press."""
        scene = GameOverScene()
        _take_quit_events()

        scene.on_key_down_event(_key_event(event_type=pygame.KEYDOWN, key=pygame.K_q))

        # Q quits on its release (BUGS.md #203: its press set a flag nothing read)
        assert _take_quit_events() == []
