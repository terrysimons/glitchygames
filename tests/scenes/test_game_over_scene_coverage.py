"""Tests to increase coverage for glitchygames/scenes/builtin_scenes/game_over_scene.py.

Targets uncovered lines: 67-68, 85, 94-100, 110-120.
"""

import pygame

from glitchygames.scenes import Scene
from glitchygames.scenes.builtin_scenes.game_over_scene import GameOverScene, TextSprite


class TestGameOverSceneUpdate:
    """Test GameOverScene.update() method (lines 67-68)."""

    def test_update_calls_super(self, mock_pygame_patches, mocker):
        """Test update() calls parent update method."""
        scene = GameOverScene()
        scene.all_sprites.clear = mocker.Mock()
        scene.all_sprites.draw = mocker.Mock(return_value=[])

        # Should not raise
        scene.update()

    def test_update_after_setup(self, mock_pygame_patches, mocker):
        """Test update() after setup with sprites added."""
        scene = GameOverScene()
        scene.setup()

        # update calls super().update() which processes sprites
        scene.update()

        # text_sprite should exist after setup
        assert scene.text_sprite is not None


class TestGameOverSceneKeyHandling:
    """Test GameOverScene key event handling (lines 85, 94-100)."""

    def test_on_key_down_escape_quits(self, mock_pygame_patches, mocker):
        """Test escape key calls quit (line 85)."""
        scene = GameOverScene()
        scene.scene_manager.quit = mocker.Mock()

        event = mocker.Mock()
        event.key = pygame.K_ESCAPE

        scene.on_key_down_event(event)

        scene.scene_manager.quit.assert_called_once()

    def test_on_key_down_other_key_delegates(self, mock_pygame_patches, mocker):
        """Test other key delegates to parent."""
        scene = GameOverScene()

        event = mocker.Mock()
        event.key = pygame.K_a

        # Should not raise - delegates to parent Scene.on_key_down_event
        scene.on_key_down_event(event)

    def test_on_key_up_space_after_press(self, mock_pygame_patches, mocker):
        """Test space key up triggers resume (lines 94-97)."""
        scene = GameOverScene()

        # Set up previous scene for resume to work
        previous_scene = Scene()
        scene.scene_manager.previous_scene = previous_scene

        scene._space_pressed = True

        event = mocker.Mock()
        event.key = pygame.K_SPACE

        # Patch switch_to_scene to prevent actual scene switch
        scene.scene_manager.switch_to_scene = mocker.Mock()

        scene.on_key_up_event(event)

        assert scene._space_pressed is False

    def test_on_key_up_space_without_press(self, mock_pygame_patches, mocker):
        """Test space key up without prior press does nothing (lines 94, 98-100)."""
        scene = GameOverScene()
        scene._space_pressed = False

        event = mocker.Mock()
        event.key = pygame.K_SPACE

        scene.on_key_up_event(event)
        assert scene._space_pressed is False

    def test_on_key_up_other_key_delegates(self, mock_pygame_patches, mocker):
        """Test non-space key up delegates to parent (lines 98-100)."""
        scene = GameOverScene()

        event = mocker.Mock()
        event.key = pygame.K_a

        # Should not raise
        scene.on_key_up_event(event)


class TestGameOverSceneResume:
    """Test GameOverScene.resume() method (lines 110-120)."""

    def test_resume_creates_new_game_instance(self, mock_pygame_patches, mocker):
        """Test resume() creates a new game from previous scene class (lines 110-118)."""
        scene = GameOverScene()

        # Create a mock previous scene
        mock_previous = mocker.Mock(spec=Scene)
        mock_previous.options = {'debug_events': False}
        scene.scene_manager.previous_scene = mock_previous
        scene.scene_manager.switch_to_scene = mocker.Mock()

        scene.resume()

        # type(mock_previous) was called to create new instance
        scene.scene_manager.switch_to_scene.assert_called_once()

    def test_resume_without_previous_scene(self, mock_pygame_patches, mocker):
        """Test resume() warns when no previous scene (lines 119-120)."""
        scene = GameOverScene()
        scene.scene_manager.previous_scene = None
        scene.scene_manager.switch_to_scene = mocker.Mock()

        # Should not raise, just logs a warning
        scene.resume()

        scene.scene_manager.switch_to_scene.assert_not_called()


class TestTextSprite:
    """Test TextSprite creation."""

    def test_text_sprite_creation(self, mock_pygame_patches):
        """Test TextSprite renders text and positions correctly."""
        sprite = TextSprite(
            'Test Text',
            (400, 300),
            color=(255, 0, 0),
            font_size=24,
        )

        assert sprite.image is not None
        assert sprite.rect is not None
        # Position should be centered around (400, 300)
        assert sprite.rect.x < 400
        assert sprite.rect.y < 300
