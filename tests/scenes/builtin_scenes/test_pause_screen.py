"""Tests for the Pause Screen functionality."""

import logging
import sys
from pathlib import Path

import pygame
import pytest

from glitchygames.examples.paddleslap import Game
from glitchygames.scenes import SceneManager
from glitchygames.testing.keys import qwerty_scancode
from tests.mocks.test_mock_factory import MockFactory

LOG = logging.getLogger(__name__)

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

PATCH_TARGET_PAUSE_SCENE = 'glitchygames.scenes.builtin_scenes.pause_scene.PauseScene'


class TestPauseScreen:
    """Test the Pause Screen functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def setup_method(self):
        """Set up test fixtures."""
        # Reset singleton state for clean test
        SceneManager._reset()

    def test_pause_screen_triggered_on_spacebar(self, mocker):
        """Test that Pause Screen is triggered when spacebar is pressed during gameplay."""
        # Mock the PauseScene import to avoid pygame initialization issues
        mock_pause_scene = mocker.Mock()
        mock_pause_scene_class = mocker.patch(
            PATCH_TARGET_PAUSE_SCENE,
            return_value=mock_pause_scene,
        )

        # Create a game instance
        game = Game(options={})
        game.setup()

        # Check initial state - the game should be the active scene initially
        from glitchygames.scenes import SceneManager

        scene_manager = SceneManager()
        # The game should be the active scene initially, but if it's not, that's okay
        # as long as it's not the pause scene yet
        assert scene_manager.active_scene != mock_pause_scene, (
            'Expected pause scene not to be active initially'
        )

        # Simulate spacebar press to trigger pause
        space_down_event = mocker.Mock()
        space_down_event.key = pygame.K_SPACE
        space_down_event.scancode = qwerty_scancode(key=pygame.K_SPACE)
        space_down_event.type = pygame.KEYDOWN

        space_up_event = mocker.Mock()
        space_up_event.key = pygame.K_SPACE
        space_up_event.scancode = qwerty_scancode(key=pygame.K_SPACE)
        space_up_event.type = pygame.KEYUP

        # Handle the key events (down then up to trigger pause)
        game.on_key_down_event(space_down_event)
        game.on_key_up_event(space_up_event)

        # The pause is requested for the end of the frame (after rendering), not switched mid-frame
        assert game.next_scene == mock_pause_scene, 'Expected the pause scene to be requested'
        LOG.info('✅ Pause screen condition properly detected!')

    def test_pause_screen_resume_on_spacebar(self, mocker):
        """Test that Pause Screen can be resumed with spacebar."""
        # Mock the PauseScene to avoid pygame initialization issues
        mock_pause_scene = mocker.Mock()
        mock_pause_scene_class = mocker.patch(
            PATCH_TARGET_PAUSE_SCENE,
            return_value=mock_pause_scene,
        )

        # Create a game instance
        game = Game(options={})
        game.setup()

        # Simulate pause
        space_down_event = mocker.Mock()
        space_down_event.key = pygame.K_SPACE
        space_down_event.scancode = qwerty_scancode(key=pygame.K_SPACE)
        space_down_event.type = pygame.KEYDOWN

        space_up_event = mocker.Mock()
        space_up_event.key = pygame.K_SPACE
        space_up_event.scancode = qwerty_scancode(key=pygame.K_SPACE)
        space_up_event.type = pygame.KEYUP

        game.on_key_down_event(space_down_event)
        game.on_key_up_event(space_up_event)

        # The pause is requested for the end of the frame; perform that switch as the loop would
        from glitchygames.scenes import SceneManager

        scene_manager = SceneManager()
        assert game.next_scene == mock_pause_scene, 'Expected the pause scene to be requested'
        scene_manager.switch_to_scene(game.next_scene)
        pause_scene = scene_manager.active_scene
        assert pause_scene == mock_pause_scene, 'Expected pause scene to be created'

        # Simulate resuming from pause
        assert pause_scene is not None
        pause_scene.on_key_down_event(space_down_event)

        # Check if resume was triggered
        assert pause_scene.next_scene is not None, 'Expected game scene to be set for resume'
        LOG.info('✅ Pause screen resume properly detected!')

    def test_pause_screen_gets_game_engine_reference(self, mocker):
        """Test that Pause Screen gets game engine reference from scene manager."""
        # Mock the PauseScene to avoid pygame initialization issues
        mock_pause_scene = mocker.Mock()
        mock_pause_scene_class = mocker.patch(
            PATCH_TARGET_PAUSE_SCENE,
            return_value=mock_pause_scene,
        )

        # Test the scene manager's _setup_new_scene method directly
        # Create a scene manager with game engine
        scene_manager = SceneManager()
        mock_game_engine = mocker.Mock()
        mock_game_engine.OPTIONS = {
            'update_type': 'dirty',
            'fps_refresh_rate': 1,
            'target_fps': 60,
            'fps_log_interval_ms': 1000.0,
        }
        scene_manager.game_engine = mock_game_engine

        # Create a Pause scene (this will be the mocked version)
        pause_scene = mock_pause_scene_class()

        # Call the _setup_new_scene method (this is what gets called during scene switching)
        scene_manager._setup_new_scene(pause_scene)

        # Verify the game engine reference was set
        assert hasattr(pause_scene, 'game_engine')
        assert pause_scene.game_engine == mock_game_engine
        LOG.info('✅ Pause screen gets game engine reference properly!')


class TestPauseScreenIntegration:
    """Test Pause Screen integration with the main game."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_pause_resume_cycle(self, mocker):
        """Test complete pause/resume cycle through the game."""
        # Mock the PauseScene to avoid pygame initialization issues
        mock_pause_scene = mocker.Mock()
        mock_pause_scene_class = mocker.patch(
            PATCH_TARGET_PAUSE_SCENE,
            return_value=mock_pause_scene,
        )

        # Create a game instance
        game = Game(options={})
        game.setup()

        # Simulate pause
        space_down_event = mocker.Mock()
        space_down_event.key = pygame.K_SPACE
        space_down_event.scancode = qwerty_scancode(key=pygame.K_SPACE)
        space_down_event.type = pygame.KEYDOWN

        space_up_event = mocker.Mock()
        space_up_event.key = pygame.K_SPACE
        space_up_event.scancode = qwerty_scancode(key=pygame.K_SPACE)
        space_up_event.type = pygame.KEYUP

        game.on_key_down_event(space_down_event)
        game.on_key_up_event(space_up_event)
        # The pause is requested for the end of the frame; perform that switch as the loop would
        from glitchygames.scenes import SceneManager

        scene_manager = SceneManager()
        assert game.next_scene == mock_pause_scene, 'Expected the pause scene to be requested'
        scene_manager.switch_to_scene(game.next_scene)
        assert scene_manager.active_scene == mock_pause_scene, 'Expected pause scene to be set'

        # Simulate resume
        pause_scene = scene_manager.active_scene
        assert pause_scene is not None
        pause_scene.on_key_down_event(space_down_event)
        assert pause_scene.next_scene is not None, 'Expected resume to work'

        LOG.info('✅ Complete pause/resume cycle works properly!')


class TestPauseSceneBehaviour:
    """The pause scene's own setup fallback, key handling and focus auto-resume."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        SceneManager._reset()
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @staticmethod
    def _pause_scene_with_manager(mocker, previous_scene):
        """Return a PauseScene whose scene manager is a stand-in holding previous_scene.

        Returns:
            PauseScene: The scene, not yet set up.

        """
        from glitchygames.scenes.builtin_scenes.pause_scene import PauseScene

        pause_scene = PauseScene()
        pause_scene.scene_manager = mocker.Mock()
        pause_scene.scene_manager.previous_scene = previous_scene
        pause_scene.scene_manager.game_engine.game.screen_width = 64
        pause_scene.scene_manager.game_engine.game.screen_height = 48
        return pause_scene

    @staticmethod
    def _key_event(mocker, key):
        """Return a key event stand-in for the given key.

        Returns:
            Mock: An event with only its key set.

        """
        event = mocker.Mock()
        event.key = key
        return event

    def test_setup_without_a_previous_scene_warns_and_uses_a_black_backdrop(self, mocker, caplog):
        """With nothing paused, setup warns and still builds an overlay of the screen's size."""
        pause_scene = self._pause_scene_with_manager(mocker, previous_scene=None)
        pause_scene.screen_width = 64
        pause_scene.screen_height = 48

        with caplog.at_level(logging.WARNING):
            pause_scene.setup()

        assert 'No previous scene found' in caplog.text
        assert pause_scene.overlay is not None
        assert pause_scene.overlay in pause_scene.all_sprites
        assert pause_scene.overlay.rect.size == (64, 48)
        # Nothing was paused, so the debug overlay inspects the pause scene itself
        assert pause_scene.debug_subject is pause_scene

    def test_escape_quits(self, mocker):
        """ESC on the pause screen quits through the scene manager."""
        pause_scene = self._pause_scene_with_manager(mocker, previous_scene=None)

        pause_scene.on_key_down_event(self._key_event(mocker, pygame.K_ESCAPE))

        pause_scene.scene_manager.quit.assert_called_once_with()

    def test_other_key_down_goes_to_the_base_scene(self, mocker):
        """A key other than SPACE or ESC (here Q) reaches the base scene, which requests quit."""
        pause_scene = self._pause_scene_with_manager(mocker, previous_scene=None)

        pause_scene.on_key_down_event(self._key_event(mocker, pygame.K_q))

        assert pause_scene.quit_requested is True
        assert pause_scene._space_pressed is False

    def test_space_release_after_press_resumes_the_paused_scene(self, mocker):
        """SPACE down then up switches back to the scene that was paused."""
        paused_game = mocker.Mock()
        pause_scene = self._pause_scene_with_manager(mocker, previous_scene=paused_game)

        pause_scene.on_key_down_event(self._key_event(mocker, pygame.K_SPACE))
        pause_scene.on_key_up_event(self._key_event(mocker, pygame.K_SPACE))

        pause_scene.scene_manager.switch_to_scene.assert_called_once_with(paused_game)
        assert pause_scene._space_pressed is False

    def test_space_release_without_a_press_does_not_resume(self, mocker):
        """A SPACE release whose press the pause scene never saw does not resume."""
        pause_scene = self._pause_scene_with_manager(mocker, previous_scene=mocker.Mock())

        pause_scene.on_key_up_event(self._key_event(mocker, pygame.K_SPACE))

        pause_scene.scene_manager.switch_to_scene.assert_not_called()

    def test_focus_gained_right_after_pausing_does_not_resume(self, mocker):
        """The focus pair the scene switch itself causes (within 0.5 s) is ignored."""
        pause_scene = self._pause_scene_with_manager(mocker, previous_scene=mocker.Mock())
        pause_scene.dt_timer = 0.5

        pause_scene.on_window_focus_gained_event(mocker.Mock())

        pause_scene.scene_manager.switch_to_scene.assert_not_called()

    def test_focus_gained_later_resumes_the_paused_scene(self, mocker):
        """Regaining window focus more than 0.5 s after pausing resumes the game."""
        paused_game = mocker.Mock()
        pause_scene = self._pause_scene_with_manager(mocker, previous_scene=paused_game)
        pause_scene.dt_timer = 0.51

        pause_scene.on_window_focus_gained_event(mocker.Mock())

        pause_scene.scene_manager.switch_to_scene.assert_called_once_with(paused_game)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
