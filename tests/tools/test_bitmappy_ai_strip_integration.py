"""Test suite for AI integration with both selected frame and selected strip.

This module tests that the AI receives both the current frame and the current
animation strip as context when generating sprites.
"""

from pathlib import Path
import pytest
import pygame
from glitchygames.tools.bitmappy import BitmapEditorScene

from tests.mocks import MockFactory

# Test constants to avoid magic values
TEST_SIZE_2 = 2


class TestAISStripIntegration:
    """Test AI integration with both selected frame and selected strip."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        self._mocker = mocker
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def setup_method(self):
        """Set up test fixtures."""
        # Initialize pygame for real font operations
        pygame.init()
        pygame.display.set_mode((800, 600), pygame.HIDDEN)

    def test_save_current_strip_to_temp_toml(self, mocker):
        """Test that current strip is saved to temporary TOML file."""
        mocker.patch.object(BitmapEditorScene, "__init__", return_value=None)
        scene = BitmapEditorScene({})
        scene.log = self._mocker.Mock()

        # Mock canvas with animated sprite
        scene.canvas = self._mocker.Mock()
        scene.canvas.animated_sprite = self._mocker.Mock()
        scene.canvas.current_animation = "test_animation"

        # Mock animation data
        mock_frame1 = self._mocker.Mock()
        mock_frame1.pixels = [(255, 0, 0), (0, 255, 0)]  # Red, Green
        mock_frame2 = self._mocker.Mock()
        mock_frame2.pixels = [(0, 0, 255), (255, 255, 0)]  # Blue, Yellow

        scene.canvas.animated_sprite._animations = {
            "test_animation": [mock_frame1, mock_frame2]
        }

        # Mock the AnimatedSprite.save method
        mock_sprite_class = mocker.patch("glitchygames.sprites.animated.AnimatedSprite")
        mock_sprite_instance = self._mocker.Mock()
        mock_sprite_class.return_value = mock_sprite_instance
        mock_sprite_instance.save = self._mocker.Mock()

        # Test the method
        temp_path = scene._save_current_strip_to_temp_toml()

        # Verify temp file was created
        assert temp_path is not None
        assert Path(temp_path).exists()
        assert temp_path.endswith(".toml")
        assert "bitmappy_strip_" in temp_path

        # Verify save was called
        mock_sprite_instance.save.assert_called_once_with(temp_path)

        # Clean up
        if temp_path and Path(temp_path).exists():
            Path(temp_path).unlink()

    def test_save_current_strip_handles_missing_animation(self, mocker):
        """Test that saving strip handles missing animation gracefully."""
        mocker.patch.object(BitmapEditorScene, "__init__", return_value=None)
        scene = BitmapEditorScene({})
        scene.log = self._mocker.Mock()

        # Mock canvas without current animation
        scene.canvas = self._mocker.Mock()
        scene.canvas.animated_sprite = self._mocker.Mock()
        scene.canvas.current_animation = None

        # Test the method
        temp_path = scene._save_current_strip_to_temp_toml()

        # Should return None for missing animation
        assert temp_path is None

    @pytest.mark.skip(reason="Not yet implemented")
    def test_ai_integration_with_frame_and_strip(self, mocker):
        """Test that AI integration provides both frame and strip context."""
        mocker.patch.object(BitmapEditorScene, "__init__", return_value=None)
        scene = BitmapEditorScene({})
        scene.log = self._mocker.Mock()
        scene.ai_request_queue = self._mocker.Mock()
        scene.ai_request_queue.put = self._mocker.Mock()
        scene.pending_ai_requests = {}

        # Mock canvas with content
        scene.canvas = self._mocker.Mock()
        scene.canvas.pixels = [(255, 0, 0), (0, 255, 0)]  # Non-magenta pixels
        scene.canvas.animated_sprite = self._mocker.Mock()
        scene.canvas.current_animation = "test_animation"

        # Mock animation data
        mock_frame1 = self._mocker.Mock()
        mock_frame1.pixels = [(255, 0, 0), (0, 255, 0)]
        mock_frame2 = self._mocker.Mock()
        mock_frame2.pixels = [(0, 0, 255), (255, 255, 0)]

        scene.canvas.animated_sprite._animations = {
            "test_animation": [mock_frame1, mock_frame2]
        }

        # Mock the helper methods
        scene._check_current_frame_has_content = self._mocker.Mock(return_value=True)
        scene._save_current_frame_to_temp_toml = self._mocker.Mock(return_value="/tmp/frame.toml")  # noqa: S108
        scene._save_current_strip_to_temp_toml = self._mocker.Mock(return_value="/tmp/strip.toml")  # noqa: S108
        scene._load_temp_toml_as_example = self._mocker.Mock(side_effect=[
            {"name": "selected_frame", "sprite_type": "static", "pixels": "test_frame"},
            {"name": "selected_strip", "sprite_type": "animated", "pixels": "test_strip"}
        ])

        # Mock debug_text
        scene.debug_text = self._mocker.Mock()
        scene.debug_text.text = "test"

        # Mock the missing constants and functions
        mocker.patch("glitchygames.tools.bitmappy.AI_TRAINING_FORMAT", "toml")
        mocker.patch("glitchygames.tools.bitmappy.SPRITE_GLYPHS", "0123456789ABCDEF")
        mocker.patch("glitchygames.tools.bitmappy.COMPLETE_TOML_FORMAT", "test format")
        mock_select = mocker.patch("glitchygames.tools.bitmappy._select_relevant_training_examples")

        mock_select.return_value = []

        # Test AI request submission
        scene.on_text_submit_event("Create a new sprite")

        # Verify both frame and strip were saved
        scene._save_current_frame_to_temp_toml.assert_called_once()
        scene._save_current_strip_to_temp_toml.assert_called_once()

        # Verify both examples were loaded
        assert scene._load_temp_toml_as_example.call_count == TEST_SIZE_2

        # Verify AI request was submitted
        scene.ai_request_queue.put.assert_called_once()

    @pytest.mark.skip(reason="Not yet implemented")
    def test_ai_integration_fallback_to_regular_examples(self, mocker):
        """Test that AI integration falls back to regular examples if context fails."""
        mocker.patch.object(BitmapEditorScene, "__init__", return_value=None)
        scene = BitmapEditorScene({})
        scene.log = self._mocker.Mock()
        scene.ai_request_queue = self._mocker.Mock()
        scene.ai_request_queue.put = self._mocker.Mock()
        scene.pending_ai_requests = {}

        # Mock canvas with content
        scene.canvas = self._mocker.Mock()
        scene.canvas.pixels = [(255, 0, 0), (0, 255, 0)]  # Non-magenta pixels

        # Mock the helper methods to fail
        scene._check_current_frame_has_content = self._mocker.Mock(return_value=True)
        scene._save_current_frame_to_temp_toml = self._mocker.Mock(return_value=None)
        scene._save_current_strip_to_temp_toml = self._mocker.Mock(return_value=None)

        # Mock debug_text
        scene.debug_text = self._mocker.Mock()
        scene.debug_text.text = "test"

        # Mock the missing constants and functions
        mocker.patch("glitchygames.tools.bitmappy.AI_TRAINING_FORMAT", "toml")
        mocker.patch("glitchygames.tools.bitmappy.SPRITE_GLYPHS", "0123456789ABCDEF")
        mocker.patch("glitchygames.tools.bitmappy.COMPLETE_TOML_FORMAT", "test format")
        mock_select = mocker.patch("glitchygames.tools.bitmappy._select_relevant_training_examples")

        mock_select.return_value = []

        # Test AI request submission
        scene.on_text_submit_event("Create a new sprite")

        # Verify fallback to regular examples
        scene._save_current_frame_to_temp_toml.assert_called_once()
        scene._save_current_strip_to_temp_toml.assert_called_once()

        # Verify AI request was still submitted
        scene.ai_request_queue.put.assert_called_once()
