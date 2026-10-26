"""Test suite for AI integration with both selected frame and selected strip.

This module tests that the AI receives both the current frame and the current
animation strip as context when generating sprites.
"""

import queue
from pathlib import Path

import pygame
import pytest

from bitmappy.editor import BitmapEditorScene
from glitchygames.sprites import AnimatedSprite, SpriteFrame
from test_bitmappy_film_strip_base import FRAME_SIZE, FilmStripTestBase

ANIMATION_NAME = 'walk'
RED = (255, 0, 0)
GREEN = (0, 255, 0)


class TestAISStripIntegration:
    """Test AI integration with both selected frame and selected strip."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Keep the mocker fixture for the tests (the real display is already open)."""
        self._mocker = mocker

    def _setup_ai_integration(self, scene: BitmapEditorScene) -> None:
        """Initialize AI integration manager on a mocked scene."""
        from bitmappy.ai_manager import AIManager

        ai_manager = AIManager.__new__(AIManager)
        ai_manager.editor = scene
        ai_manager.log = scene.log
        ai_manager.pending_ai_requests = {}
        ai_manager.ai_request_queue = None
        ai_manager.ai_response_queue = None
        ai_manager.ai_process = None
        ai_manager.last_successful_sprite_content = None
        ai_manager.last_conversation_history = None
        scene._ai_integration = ai_manager  # type: ignore[attr-defined]

    def test_save_current_strip_to_temp_toml(self, mocker):
        """Test that current strip is saved to temporary TOML file."""
        mocker.patch.object(BitmapEditorScene, '__init__', return_value=None)
        scene = BitmapEditorScene({})
        scene.log = self._mocker.Mock()
        self._setup_ai_integration(scene)

        # Mock canvas with animated sprite
        scene.canvas = self._mocker.Mock()
        scene.canvas.animated_sprite = self._mocker.Mock()
        scene.canvas.current_animation = 'test_animation'

        # Mock animation data
        mock_frame1 = self._mocker.Mock()
        mock_frame1.pixels = [(255, 0, 0), (0, 255, 0)]  # Red, Green
        mock_frame2 = self._mocker.Mock()
        mock_frame2.pixels = [(0, 0, 255), (255, 255, 0)]  # Blue, Yellow

        scene.canvas.animated_sprite._animations = {'test_animation': [mock_frame1, mock_frame2]}

        # Mock the AnimatedSprite.save method
        mock_sprite_class = mocker.patch('glitchygames.sprites.animated.AnimatedSprite')
        mock_sprite_instance = self._mocker.Mock()
        mock_sprite_class.return_value = mock_sprite_instance
        mock_sprite_instance.save = self._mocker.Mock()

        # Test the method
        temp_path = scene._ai_integration._save_current_strip_to_temp_toml()

        # Verify temp file was created
        assert temp_path is not None
        assert Path(temp_path).exists()
        assert temp_path.endswith('.toml')
        assert 'bitmappy_strip_' in temp_path

        # Verify save was called
        mock_sprite_instance.save.assert_called_once_with(temp_path)

        # Clean up
        if temp_path and Path(temp_path).exists():
            Path(temp_path).unlink()

    def test_save_current_strip_handles_missing_animation(self, mocker):
        """Test that saving strip handles missing animation gracefully."""
        mocker.patch.object(BitmapEditorScene, '__init__', return_value=None)
        scene = BitmapEditorScene({})
        scene.log = self._mocker.Mock()
        self._setup_ai_integration(scene)

        # Mock canvas without current animation
        scene.canvas = self._mocker.Mock()
        scene.canvas.animated_sprite = self._mocker.Mock()
        scene.canvas.current_animation = None

        # Test the method
        temp_path = scene._ai_integration._save_current_strip_to_temp_toml()

        # Should return None for missing animation
        assert temp_path is None


class TestAIContextFromEditor(FilmStripTestBase):
    """Test the AI context a real editor sends for its selected frame and strip."""

    def create_scene_with_red_green_strip(self):
        """Load a red frame then a green frame into a real editor, with the red one shown.

        Returns:
            BitmapEditorScene: The editor, with an in-process AI request queue.

        """
        animated_sprite = AnimatedSprite()
        frames = []
        for frame_color in (RED, GREEN):
            frame_surface = pygame.Surface((FRAME_SIZE, FRAME_SIZE))
            frame_surface.fill(frame_color)
            frames.append(SpriteFrame(frame_surface, duration=0.5))
        animated_sprite.add_animation(ANIMATION_NAME, frames)

        scene = self.create_optimized_scene()
        scene.film_strip_coordinator.on_sprite_loaded(animated_sprite)
        # Stands in for the worker process's multiprocessing.Queue (AIManager.setup)
        scene._ai_integration.ai_request_queue = queue.Queue()
        return scene

    @staticmethod
    def submitted_training_examples(scene):
        """Take the one submitted AI request and return its training examples.

        Returns:
            list[dict]: The training examples recorded for the request.

        """
        ai_manager = scene._ai_integration
        request = ai_manager.ai_request_queue.get_nowait()
        assert ai_manager.ai_request_queue.empty()
        return ai_manager.pending_ai_requests[request.request_id].training_examples

    def test_ai_integration_with_frame_and_strip(self):
        """Test that a request carries the shown frame and its animation strip as context."""
        scene = self.create_scene_with_red_green_strip()
        assert scene.canvas.current_animation == ANIMATION_NAME
        assert scene.canvas.current_frame == 0

        scene.on_text_submit_event('Create a new sprite')

        frame_example, strip_example = self.submitted_training_examples(scene)
        assert frame_example['name'] == 'selected_frame'
        assert strip_example['name'] == 'selected_strip'
        frame_colors = {
            (color['red'], color['green'], color['blue'])
            for color in frame_example['colors'].values()
        }
        strip_colors = {
            (color['red'], color['green'], color['blue'])
            for color in strip_example['colors'].values()
        }
        # The frame is the red one on the canvas; the strip holds both frames' colours
        assert frame_colors == {RED}
        assert strip_colors == {RED, GREEN}

    def test_ai_strip_context_includes_every_frame(self):
        """Test that the strip example's pixels include the second (green) frame."""
        scene = self.create_scene_with_red_green_strip()

        scene.on_text_submit_event('Create a new sprite')

        _frame_example, strip_example = self.submitted_training_examples(scene)
        green_glyphs = [
            glyph
            for glyph, color in strip_example['colors'].items()
            if (color['red'], color['green'], color['blue']) == GREEN
        ]
        assert len(green_glyphs) == 1
        assert green_glyphs[0] in strip_example['pixels']

    def test_ai_integration_fallback_to_regular_examples(self, mocker):
        """Test that the request falls back to regular examples if the context cannot be saved."""
        scene = self.create_scene_with_red_green_strip()
        ai_manager = scene._ai_integration
        mocker.patch.object(ai_manager, '_save_current_frame_to_temp_toml', return_value=None)
        mocker.patch.object(ai_manager, '_save_current_strip_to_temp_toml', return_value=None)
        regular_examples = [{'name': 'regular_example', 'sprite_type': 'static', 'pixels': '#'}]
        mocker.patch(
            'bitmappy.ai_manager.select_relevant_training_examples',
            return_value=regular_examples,
        )

        scene.on_text_submit_event('Create a new sprite')

        assert self.submitted_training_examples(scene) == regular_examples
