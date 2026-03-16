"""Tests to increase coverage for glitchygames/scenes/builtin_scenes/pause_scene.py.

Targets uncovered lines: 25-46, 59-61, 65-82, 91-98, 107-113.
"""

import pygame

from glitchygames.scenes import Scene
from glitchygames.scenes.builtin_scenes.pause_scene import PauseOverlay, PauseScene


class TestPauseOverlay:
    """Test PauseOverlay initialization (lines 25-46)."""

    def test_pause_overlay_creation(self, mock_pygame_patches, mocker):
        """Test PauseOverlay creates overlay with screenshot."""
        # Create a mock game scene
        mock_game = mocker.Mock()
        mock_game.screen_width = 800
        mock_game.screen_height = 600

        # Create a real screenshot surface
        screenshot = pygame.Surface((800, 600))
        screenshot.fill((100, 100, 100))

        overlay = PauseOverlay(mock_game, screenshot)

        assert overlay.image is not None
        assert overlay.rect is not None
        assert overlay.dirty == 1
        assert overlay.rect.width == 800
        assert overlay.rect.height == 600


class TestPauseScene:
    """Test PauseScene functionality (lines 59-61, 65-82, 91-98, 107-113)."""

    def test_pause_scene_initialization(self, mock_pygame_patches, mocker):
        """Test PauseScene initialization (lines 59-61)."""
        scene = PauseScene()

        assert scene.overlay is None
        assert scene._space_pressed is False

    def test_pause_scene_setup_with_previous_scene(self, mock_pygame_patches, mocker):
        """Test PauseScene setup creates overlay from previous scene (lines 65-82)."""
        # Create a previous scene with a screenshot
        previous_scene = Scene()
        previous_scene._screenshot = pygame.Surface((800, 600))

        # Create a mock game engine
        mock_engine = mocker.Mock()
        mock_engine.game = mocker.Mock()
        mock_engine.game.screen_width = 800
        mock_engine.game.screen_height = 600

        # Set up scene manager
        scene = PauseScene()
        scene.scene_manager.previous_scene = previous_scene
        scene.scene_manager._game_engine = mock_engine

        scene.setup()

        assert scene.overlay is not None

    def test_pause_scene_setup_without_previous_scene(self, mock_pygame_patches, mocker):
        """Test PauseScene setup fallback when no previous scene (lines 73-77)."""
        mock_engine = mocker.Mock()
        mock_engine.game = mocker.Mock()
        mock_engine.game.screen_width = 800
        mock_engine.game.screen_height = 600

        scene = PauseScene()
        scene.scene_manager.previous_scene = None
        scene.scene_manager._game_engine = mock_engine

        scene.setup()

        assert scene.overlay is not None

    def test_on_key_down_space(self, mock_pygame_patches, mocker):
        """Test space key press tracking (lines 91-93)."""
        scene = PauseScene()
        event = mocker.Mock()
        event.key = pygame.K_SPACE

        scene.on_key_down_event(event)

        assert scene._space_pressed is True

    def test_on_key_down_escape(self, mock_pygame_patches, mocker):
        """Test escape key calls quit (lines 94-96)."""
        scene = PauseScene()
        scene.scene_manager.quit = mocker.Mock()

        event = mocker.Mock()
        event.key = pygame.K_ESCAPE

        scene.on_key_down_event(event)

        scene.scene_manager.quit.assert_called_once()

    def test_on_key_down_other_key(self, mock_pygame_patches, mocker):
        """Test other keys are passed to super (lines 97-98)."""
        scene = PauseScene()
        event = mocker.Mock()
        event.key = pygame.K_a

        # Should not raise, delegates to parent
        scene.on_key_down_event(event)
        assert scene._space_pressed is False

    def test_on_key_up_space_after_press_resumes(self, mock_pygame_patches, mocker):
        """Test space key up after press triggers resume (lines 107-111)."""
        scene = PauseScene()

        # Set up a previous scene for resume to work
        previous_scene = Scene()
        scene.scene_manager.previous_scene = previous_scene

        # Simulate space press then release
        scene._space_pressed = True

        event = mocker.Mock()
        event.key = pygame.K_SPACE

        scene.on_key_up_event(event)

        assert scene._space_pressed is False

    def test_on_key_up_space_without_press(self, mock_pygame_patches, mocker):
        """Test space key up without prior press does nothing (lines 107, 112-113)."""
        scene = PauseScene()
        scene._space_pressed = False

        event = mocker.Mock()
        event.key = pygame.K_SPACE

        # Should not trigger resume since _space_pressed is False
        scene.on_key_up_event(event)
        assert scene._space_pressed is False

    def test_on_key_up_other_key(self, mock_pygame_patches, mocker):
        """Test other key up delegates to parent (lines 112-113)."""
        scene = PauseScene()

        event = mocker.Mock()
        event.key = pygame.K_a

        # Should not raise
        scene.on_key_up_event(event)
