"""Tests for the Pause Screen functionality.

Real scenes (PaddleSlap's Game and the real PauseScene) run on the real SceneManager and draw
onto the real display. The only stand-in is the game engine: PauseScene reads two things from
it (its options and its game), so a namespace holding them takes its place.
"""

import logging
import sys
import types
from pathlib import Path

import pygame
import pytest

from glitchygames import events
from glitchygames.scenes import Scene, SceneManager
from glitchygames.scenes.builtin_scenes.pause_scene import PauseScene
from glitchygames.testing.keys import qwerty_scancode
from paddleslap import Game

LOG = logging.getLogger(__name__)

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

ENGINE_OPTIONS = {
    'update_type': 'update',
    'fps_refresh_rate': 1,
    'target_fps': 60,
    'fps_log_interval_ms': 1000.0,
}


@pytest.fixture(autouse=True)
def isolated_scene_manager(mocker, tmp_path):
    """Give each test a fresh SceneManager, its own save directory and restored options.

    Setting a scene manager's game_engine copies the engine's OPTIONS onto the SceneManager
    class, so the class attribute is put back afterwards. PaddleSlap opens its save store when
    it is built; the saves go to a temporary directory, never the user's.

    Yields:
        SceneManager: The fresh scene manager.

    """
    mocker.patch.object(SceneManager, 'OPTIONS', SceneManager.OPTIONS)
    mocker.patch(
        'glitchygames.state.manager.get_save_directory',
        side_effect=lambda app_name: tmp_path / app_name,
    )
    SceneManager._reset()
    yield SceneManager()
    SceneManager._reset()
    pygame.event.clear(eventtype=pygame.QUIT)


def _engine_for(game: Scene) -> types.SimpleNamespace:
    """Return a stand-in game engine holding the options and the game PauseScene reads.

    Returns:
        types.SimpleNamespace: The engine stand-in.

    """
    return types.SimpleNamespace(OPTIONS=dict(ENGINE_OPTIONS), game=game)


def _key_event(*, event_type: int, key: int) -> events.HashableEvent:
    """Return a real key event for the key, with its US QWERTY scancode.

    Returns:
        events.HashableEvent: The KEYDOWN or KEYUP event.

    """
    return events.HashableEvent(
        event_type, key=key, scancode=qwerty_scancode(key=key), mod=pygame.KMOD_NONE
    )


# A gamepad's two event layers (glitchygames/input/input_devices.py, rule 1): a mapped pad's
# buttons arrive as controller events, any other device's (or every device's in joystick mode)
# as joystick events, by the same button numbers
GAMEPAD_LAYERS = ('controller', 'joystick')


def _gamepad_button(scene: Scene, *, layer: str, button: int, pressed: bool) -> None:
    """Give the scene a real button press or release from a gamepad on one event layer."""
    if layer == 'controller':
        event_type = pygame.CONTROLLERBUTTONDOWN if pressed else pygame.CONTROLLERBUTTONUP
        event = events.HashableEvent(event_type, instance_id=0, button=button)
        if pressed:
            scene.on_controller_button_down_event(event)
        else:
            scene.on_controller_button_up_event(event)
        return
    event_type = pygame.JOYBUTTONDOWN if pressed else pygame.JOYBUTTONUP
    event = events.HashableEvent(event_type, instance_id=0, joy=0, button=button)
    if pressed:
        scene.on_joy_button_down_event(event)
    else:
        scene.on_joy_button_up_event(event)


def _press_and_release(scene: Scene, key: int) -> None:
    """Send a key-down then a key-up of the key to the scene."""
    scene.on_key_down_event(_key_event(event_type=pygame.KEYDOWN, key=key))
    scene.on_key_up_event(_key_event(event_type=pygame.KEYUP, key=key))


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


def _paused_game(scene_manager: SceneManager) -> tuple[Game, PauseScene]:
    """Start PaddleSlap, pause it with SPACE and switch to the pause scene, as the loop would.

    Returns:
        tuple[Game, PauseScene]: The paused game and the active pause scene.

    """
    game = Game(options={})
    scene_manager.game_engine = _engine_for(game)
    scene_manager.switch_to_scene(game)
    _press_and_release(game, pygame.K_SPACE)
    assert isinstance(game.next_scene, PauseScene), 'Expected the pause scene to be requested'
    scene_manager.switch_to_scene(game.next_scene)
    pause_scene = scene_manager.active_scene
    assert isinstance(pause_scene, PauseScene)
    return game, pause_scene


class TestPauseScreen:
    """Test the Pause Screen functionality."""

    def test_pause_screen_triggered_on_spacebar(self, isolated_scene_manager):
        """SPACE pressed and released during gameplay requests the pause scene."""
        game = Game(options={})
        isolated_scene_manager.game_engine = _engine_for(game)
        isolated_scene_manager.switch_to_scene(game)
        assert isolated_scene_manager.active_scene is game

        _press_and_release(game, pygame.K_SPACE)

        # The pause is requested for the end of the frame (after rendering), not switched mid-frame
        assert isinstance(game.next_scene, PauseScene), 'Expected the pause scene to be requested'
        assert isolated_scene_manager.active_scene is game
        _draw_the_active_scene(isolated_scene_manager)
        LOG.info('Pause screen condition properly detected')

    def test_pause_screen_resume_on_spacebar(self, isolated_scene_manager):
        """SPACE pressed and released on the pause screen switches back to the paused game."""
        game, pause_scene = _paused_game(isolated_scene_manager)
        assert isolated_scene_manager.previous_scene is game

        _press_and_release(pause_scene, pygame.K_SPACE)

        assert isolated_scene_manager.active_scene is game, 'Expected the game to resume'
        _draw_the_active_scene(isolated_scene_manager)
        LOG.info('Pause screen resume properly detected')

    def test_pause_screen_gets_game_engine_reference(self, isolated_scene_manager):
        """Switching to the pause scene hands it the scene manager's game engine."""
        game = Game(options={})
        game_engine = _engine_for(game)
        isolated_scene_manager.game_engine = game_engine
        isolated_scene_manager.switch_to_scene(game)
        pause_scene = PauseScene()

        # Every switch sets the new scene up through _setup_new_scene
        isolated_scene_manager._setup_new_scene(pause_scene)

        assert pause_scene.game_engine is game_engine
        assert pause_scene.overlay is not None  # setup() ran and built the overlay
        _draw_the_active_scene(isolated_scene_manager)
        LOG.info('Pause screen gets game engine reference properly')


class TestPauseScreenIntegration:
    """Test Pause Screen integration with the main game."""

    def test_pause_resume_cycle(self, isolated_scene_manager):
        """Pause, draw the pause screen on the display, then resume the same game."""
        game, pause_scene = _paused_game(isolated_scene_manager)
        display = pygame.display.get_surface()
        assert pause_scene.overlay is not None
        assert pause_scene.overlay.rect.size == display.get_size()

        pause_scene.update()
        pause_scene.render(display)

        # The display shows exactly the overlay (the dimmed game with PAUSED on it)
        assert pygame.image.tobytes(display, 'RGB') == pygame.image.tobytes(
            pause_scene.overlay.image, 'RGB'
        )
        # The paused game stays the scene the debug overlay inspects
        assert pause_scene.debug_subject is game

        _press_and_release(pause_scene, pygame.K_SPACE)

        assert isolated_scene_manager.active_scene is game, 'Expected resume to work'
        _draw_the_active_scene(isolated_scene_manager)
        LOG.info('Complete pause/resume cycle works properly')


class TestPauseSceneBehaviour:
    """The pause scene's own setup fallback, key handling and focus auto-resume."""

    @staticmethod
    def _pause_scene_after(scene_manager: SceneManager, previous_scene: Scene | None):
        """Make previous_scene (if any) then a new PauseScene the active scene.

        Returns:
            PauseScene: The active pause scene, set up.

        """
        engine_game = Scene()
        engine_game.screen_width = 64
        engine_game.screen_height = 48
        scene_manager.game_engine = _engine_for(engine_game)
        if previous_scene is not None:
            scene_manager.switch_to_scene(previous_scene)
        pause_scene = PauseScene()
        scene_manager.switch_to_scene(pause_scene)
        return pause_scene

    def test_setup_without_a_previous_scene_warns_and_uses_a_black_backdrop(
        self, isolated_scene_manager, caplog
    ):
        """With nothing paused, setup warns and still builds an overlay of the screen's size."""
        with caplog.at_level(logging.WARNING):
            pause_scene = self._pause_scene_after(isolated_scene_manager, previous_scene=None)

        assert 'No previous scene found' in caplog.text
        assert pause_scene.overlay is not None
        assert pause_scene.overlay in pause_scene.all_sprites
        assert pause_scene.overlay.rect.size == pygame.display.get_surface().get_size()
        # Nothing was paused, so the debug overlay inspects the pause scene itself
        assert pause_scene.debug_subject is pause_scene
        _draw_the_active_scene(isolated_scene_manager)

    def test_escape_quits(self, isolated_scene_manager):
        """ESC on the pause screen quits: the scene manager posts QUIT to the real queue."""
        pause_scene = self._pause_scene_after(isolated_scene_manager, previous_scene=None)
        pygame.event.clear(eventtype=pygame.QUIT)

        pause_scene.on_key_down_event(_key_event(event_type=pygame.KEYDOWN, key=pygame.K_ESCAPE))

        assert len(pygame.event.get(eventtype=pygame.QUIT)) == 1
        _draw_the_active_scene(isolated_scene_manager)

    def test_other_key_down_goes_to_the_base_scene(self, isolated_scene_manager):
        """A key other than SPACE or ESC (here Q) reaches the base scene: no quit on the press.

        The base scene quits on Q's release (BUGS.md #203: its press set a dead flag).
        """
        pause_scene = self._pause_scene_after(isolated_scene_manager, previous_scene=None)
        pygame.event.clear(eventtype=pygame.QUIT)

        pause_scene.on_key_down_event(_key_event(event_type=pygame.KEYDOWN, key=pygame.K_q))

        assert pygame.event.get(eventtype=pygame.QUIT) == []
        assert pause_scene._space_pressed is False
        _draw_the_active_scene(isolated_scene_manager)

    def test_space_release_after_press_resumes_the_paused_scene(self, isolated_scene_manager):
        """SPACE down then up switches back to the scene that was paused."""
        paused_game = Scene()
        pause_scene = self._pause_scene_after(isolated_scene_manager, previous_scene=paused_game)

        _press_and_release(pause_scene, pygame.K_SPACE)

        assert isolated_scene_manager.active_scene is paused_game
        assert pause_scene._space_pressed is False

    def test_space_release_without_a_press_does_not_resume(self, isolated_scene_manager):
        """A SPACE release whose press the pause scene never saw does not resume."""
        pause_scene = self._pause_scene_after(isolated_scene_manager, previous_scene=Scene())

        pause_scene.on_key_up_event(_key_event(event_type=pygame.KEYUP, key=pygame.K_SPACE))

        assert isolated_scene_manager.active_scene is pause_scene
        _draw_the_active_scene(isolated_scene_manager)

    def test_focus_gained_right_after_pausing_does_not_resume(self, isolated_scene_manager):
        """The focus pair the scene switch itself causes (within 0.5 s) is ignored."""
        pause_scene = self._pause_scene_after(isolated_scene_manager, previous_scene=Scene())
        pause_scene.dt_timer = 0.5

        pause_scene.on_window_focus_gained_event(events.HashableEvent(pygame.WINDOWFOCUSGAINED))

        assert isolated_scene_manager.active_scene is pause_scene
        _draw_the_active_scene(isolated_scene_manager)

    def test_focus_gained_later_resumes_the_paused_scene(self, isolated_scene_manager):
        """Regaining window focus more than 0.5 s after pausing resumes the game."""
        paused_game = Scene()
        pause_scene = self._pause_scene_after(isolated_scene_manager, previous_scene=paused_game)
        pause_scene.dt_timer = 0.51

        pause_scene.on_window_focus_gained_event(events.HashableEvent(pygame.WINDOWFOCUSGAINED))

        assert isolated_scene_manager.active_scene is paused_game


class TestPauseSceneGamepad:
    """A gamepad resumes or quits from the pause screen (BUGS.md #209 item 10)."""

    @staticmethod
    def _pause_scene_after(scene_manager: SceneManager, previous_scene: Scene) -> PauseScene:
        """Make the pause scene the active scene, with previous_scene as the one paused.

        Returns:
            PauseScene: The set-up pause scene.

        """
        scene_manager.game_engine = _engine_for(game=previous_scene)
        scene_manager.switch_to_scene(previous_scene)
        pause_scene = PauseScene()
        scene_manager.switch_to_scene(pause_scene)
        return pause_scene

    @pytest.mark.parametrize('layer', GAMEPAD_LAYERS)
    @pytest.mark.parametrize('button', [pygame.CONTROLLER_BUTTON_START, pygame.CONTROLLER_BUTTON_A])
    def test_start_or_a_released_after_its_press_resumes(
        self, isolated_scene_manager, layer, button
    ):
        """Start or A, pressed and released on the pause screen, resumes the paused game."""
        paused_game = Scene()
        pause_scene = self._pause_scene_after(isolated_scene_manager, previous_scene=paused_game)

        _gamepad_button(pause_scene, layer=layer, button=button, pressed=True)
        assert isolated_scene_manager.active_scene is pause_scene
        _gamepad_button(pause_scene, layer=layer, button=button, pressed=False)

        assert isolated_scene_manager.active_scene is paused_game

    @pytest.mark.parametrize('layer', GAMEPAD_LAYERS)
    def test_a_release_whose_press_came_before_the_pause_does_not_resume(
        self, isolated_scene_manager, layer
    ):
        """The release of the Start press that paused the game must not resume it at once."""
        pause_scene = self._pause_scene_after(isolated_scene_manager, previous_scene=Scene())

        _gamepad_button(
            pause_scene, layer=layer, button=pygame.CONTROLLER_BUTTON_START, pressed=False
        )

        assert isolated_scene_manager.active_scene is pause_scene
        _draw_the_active_scene(isolated_scene_manager)

    @pytest.mark.parametrize('layer', GAMEPAD_LAYERS)
    @pytest.mark.parametrize('button', [pygame.CONTROLLER_BUTTON_B, pygame.CONTROLLER_BUTTON_BACK])
    def test_b_or_back_quits(self, isolated_scene_manager, layer, button):
        """B or Back quits on its press, as ESC does: one QUIT event."""
        pause_scene = self._pause_scene_after(isolated_scene_manager, previous_scene=Scene())
        pygame.event.clear(eventtype=pygame.QUIT)

        _gamepad_button(pause_scene, layer=layer, button=button, pressed=True)

        assert len(pygame.event.get(eventtype=pygame.QUIT)) == 1
        _draw_the_active_scene(isolated_scene_manager)

    @pytest.mark.parametrize('layer', GAMEPAD_LAYERS)
    def test_another_button_does_nothing(self, isolated_scene_manager, layer):
        """Any other button neither resumes nor quits."""
        pause_scene = self._pause_scene_after(isolated_scene_manager, previous_scene=Scene())
        pygame.event.clear(eventtype=pygame.QUIT)

        _gamepad_button(pause_scene, layer=layer, button=pygame.CONTROLLER_BUTTON_X, pressed=True)
        _gamepad_button(pause_scene, layer=layer, button=pygame.CONTROLLER_BUTTON_X, pressed=False)

        assert isolated_scene_manager.active_scene is pause_scene
        assert pygame.event.get(eventtype=pygame.QUIT) == []
        _draw_the_active_scene(isolated_scene_manager)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
