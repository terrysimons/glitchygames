"""Test suite for AI integration with both selected frame and selected strip.

This module tests that the AI receives both the current frame and the current
animation strip as context when generating sprites.
"""

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pygame
from glitchygames.tools.bitmappy import BitmapEditorScene

from tests.mocks import MockFactory

# Test constants to avoid magic values
TEST_SIZE_2 = 2


class TestAISStripIntegration(unittest.TestCase):
    """Test AI integration with both selected frame and selected strip."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()

        # Initialize pygame for real font operations
        pygame.init()
        pygame.display.set_mode((800, 600), pygame.HIDDEN)

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)
        pygame.quit()

    def test_save_current_strip_to_temp_toml(self):
        """Test that current strip is saved to temporary TOML file."""
        with patch.object(BitmapEditorScene, "__init__", return_value=None):
            scene = BitmapEditorScene({})
            scene.log = Mock()

            # Mock canvas with animated sprite
            scene.canvas = Mock()
            scene.canvas.animated_sprite = Mock()
            scene.canvas.current_animation = "test_animation"

            # Mock animation data
            mock_frame1 = Mock()
            mock_frame1.pixels = [(255, 0, 0), (0, 255, 0)]  # Red, Green
            mock_frame2 = Mock()
            mock_frame2.pixels = [(0, 0, 255), (255, 255, 0)]  # Blue, Yellow

            scene.canvas.animated_sprite._animations = {
                "test_animation": [mock_frame1, mock_frame2]
            }

            # Mock the AnimatedSprite.save method
            with patch("glitchygames.sprites.animated.AnimatedSprite") as mock_sprite_class:
                mock_sprite_instance = Mock()
                mock_sprite_class.return_value = mock_sprite_instance
                mock_sprite_instance.save = Mock()

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

    def test_save_current_strip_handles_missing_animation(self):
        """Test that saving strip handles missing animation gracefully."""
        with patch.object(BitmapEditorScene, "__init__", return_value=None):
            scene = BitmapEditorScene({})
            scene.log = Mock()

            # Mock canvas without current animation
            scene.canvas = Mock()
            scene.canvas.animated_sprite = Mock()
            scene.canvas.current_animation = None

            # Test the method
            temp_path = scene._save_current_strip_to_temp_toml()

            # Should return None for missing animation
            assert temp_path is None

    def test_ai_integration_with_frame_and_strip(self):
        """Test that AI integration provides both frame and strip context."""
        with patch.object(BitmapEditorScene, "__init__", return_value=None):
            scene = BitmapEditorScene({})
            scene.log = Mock()
            scene.ai_request_queue = Mock()
            scene.ai_request_queue.put = Mock()
            scene.pending_ai_requests = {}

            # Mock canvas with content
            scene.canvas = Mock()
            scene.canvas.pixels = [(255, 0, 0), (0, 255, 0)]  # Non-magenta pixels
            scene.canvas.animated_sprite = Mock()
            scene.canvas.current_animation = "test_animation"

            # Mock animation data
            mock_frame1 = Mock()
            mock_frame1.pixels = [(255, 0, 0), (0, 255, 0)]
            mock_frame2 = Mock()
            mock_frame2.pixels = [(0, 0, 255), (255, 255, 0)]

            scene.canvas.animated_sprite._animations = {
                "test_animation": [mock_frame1, mock_frame2]
            }

            # Mock the helper methods
            scene._check_current_frame_has_content = Mock(return_value=True)
            scene._save_current_frame_to_temp_toml = Mock(return_value="/tmp/frame.toml")  # noqa: S108
            scene._save_current_strip_to_temp_toml = Mock(return_value="/tmp/strip.toml")  # noqa: S108
            scene._load_temp_toml_as_example = Mock(side_effect=[
                {"name": "selected_frame", "sprite_type": "static", "pixels": "test_frame"},
                {"name": "selected_strip", "sprite_type": "animated", "pixels": "test_strip"}
            ])

            # Mock debug_text
            scene.debug_text = Mock()
            scene.debug_text.text = "test"

            # Mock the missing constants and functions
            with patch("glitchygames.tools.bitmappy.AI_TRAINING_FORMAT", "toml"), \
                 patch("glitchygames.tools.bitmappy.SPRITE_GLYPHS", "0123456789ABCDEF"), \
                 patch("glitchygames.tools.bitmappy.COMPLETE_TOML_FORMAT", "test format"), \
                 patch("glitchygames.tools.bitmappy._select_relevant_training_examples") as mock_select:  # noqa: E501

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

    def test_ai_integration_fallback_to_regular_examples(self):
        """Test that AI integration falls back to regular examples if context fails."""
        with patch.object(BitmapEditorScene, "__init__", return_value=None):
            scene = BitmapEditorScene({})
            scene.log = Mock()
            scene.ai_request_queue = Mock()
            scene.ai_request_queue.put = Mock()
            scene.pending_ai_requests = {}

            # Mock canvas with content
            scene.canvas = Mock()
            scene.canvas.pixels = [(255, 0, 0), (0, 255, 0)]  # Non-magenta pixels

            # Mock the helper methods to fail
            scene._check_current_frame_has_content = Mock(return_value=True)
            scene._save_current_frame_to_temp_toml = Mock(return_value=None)
            scene._save_current_strip_to_temp_toml = Mock(return_value=None)

            # Mock debug_text
            scene.debug_text = Mock()
            scene.debug_text.text = "test"

            # Mock the missing constants and functions
            with patch("glitchygames.tools.bitmappy.AI_TRAINING_FORMAT", "toml"), \
                 patch("glitchygames.tools.bitmappy.SPRITE_GLYPHS", "0123456789ABCDEF"), \
                 patch("glitchygames.tools.bitmappy.COMPLETE_TOML_FORMAT", "test format"), \
                 patch("glitchygames.tools.bitmappy._select_relevant_training_examples") as mock_select:  # noqa: E501

                mock_select.return_value = []

                # Test AI request submission
                scene.on_text_submit_event("Create a new sprite")

                # Verify fallback to regular examples
                scene._save_current_frame_to_temp_toml.assert_called_once()
                scene._save_current_strip_to_temp_toml.assert_called_once()

                # Verify AI request was still submitted
                scene.ai_request_queue.put.assert_called_once()


if __name__ == "__main__":
    unittest.main()
