"""Test suite for on_load_file_event functionality.

This module tests the file loading functionality in bitmappy.py, specifically
the on_load_file_event method that handles loading animated sprites from files.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pygame

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from glitchygames.sprites import AnimatedSprite, SpriteFrame
from glitchygames.tools.bitmappy import AnimatedCanvasSprite, BitmapEditorScene

from test_mock_factory import MockFactory, create_10x10_sprite_mock


class TestOnLoadFileEvent(unittest.TestCase):
    """Test suite for on_load_file_event functionality."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Initialize pygame with display for each test
        pygame.init()
        pygame.display.set_mode((800, 600))

        # Create a test animated sprite
        self.animated_sprite = self._create_test_animated_sprite()

        # Create a test animated canvas
        self.canvas = AnimatedCanvasSprite(
            animated_sprite=self.animated_sprite,
            name="Test Animated Canvas",
            x=0,
            y=0,
            pixels_across=8,
            pixels_tall=8,
            pixel_width=16,
            pixel_height=16,
        )

        # Create a test scene with canvas
        test_options = {"size": "8x8"}
        self.scene = BitmapEditorScene(options=test_options)
        self.scene.canvas = self.canvas
        self.scene.all_sprites = pygame.sprite.LayeredDirty()

    @staticmethod
    def tearDown():
        """Clean up after each test method."""
        pygame.quit()

    @staticmethod
    def _create_test_animated_sprite():
        """Create a test animated sprite with 2 frames."""
        # Create frame 1
        surface1 = pygame.Surface((8, 8))
        surface1.fill((255, 0, 0))  # Red frame
        frame1 = SpriteFrame(surface1)
        frame1.pixels = [(255, 0, 0)] * 64  # 8x8 = 64 pixels

        # Create frame 2
        surface2 = pygame.Surface((8, 8))
        surface2.fill((0, 255, 0))  # Green frame
        frame2 = SpriteFrame(surface2)
        frame2.pixels = [(0, 255, 0)] * 64

        # Create animated sprite
        animated_sprite = AnimatedSprite()
        animated_sprite._animations = {"idle": [frame1, frame2]}
        animated_sprite._frame_interval = 0.5
        animated_sprite._is_looping = True
        animated_sprite.frame_manager.current_animation = "idle"
        animated_sprite.frame_manager.current_frame = 0

        return animated_sprite

    @staticmethod
    def _create_test_sprite_file(content: str) -> str:
        """Create a temporary sprite file with given content."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            return f.name

    @staticmethod
    def _create_mock_event(filename: str):
        """Create a mock pygame event for file loading."""
        return MockFactory.create_event_mock(filename)

    @staticmethod
    def _get_first_animation_name(sprite: AnimatedSprite) -> str:
        """Get the first animation name from a sprite.

        This follows the same logic as _set_initial_animation:
        1. First try to find "idle" animation
        2. If no "idle" animation exists, use the first animation in file order
        3. If no animation order is available, fall back to the first key in _animations
        """
        if not hasattr(sprite, "_animations") or not sprite._animations:
            return ""

        # First try to find "idle" animation
        if "idle" in sprite._animations:
            return "idle"

        # Use the first animation as it appears in the file order
        if hasattr(sprite, "_animation_order") and sprite._animation_order:
            return sprite._animation_order[0]

        # Fall back to the first key in _animations
        return next(iter(sprite._animations.keys()))

    def test_load_valid_animated_sprite(self):
        """Test loading a valid animated sprite file."""
        # Create test sprite file
        sprite_content = """
[sprite]
name = "test_sprite"

[colors.0]
red = 255
green = 0
blue = 0

[colors.1]
red = 0
green = 255
blue = 0

[[animation]]
namespace = "idle"
frame_interval = 0.5
loop = true

[[animation.frame]]
namespace = "idle"
frame_index = 0
pixels = \"\"\"
00000000
01111110
01111110
01111110
01111110
01111110
01111110
00000000
\"\"\"

[[animation.frame]]
namespace = "idle"
frame_index = 1
pixels = \"\"\"
00000000
01111110
01111110
01111110
01111110
01111110
01111110
00000000
\"\"\"
"""
        sprite_file = self._create_test_sprite_file(sprite_content)

        try:
            # Create mock event
            event = self._create_mock_event(sprite_file)

            # Mock the detect_file_format function
            with patch("glitchygames.tools.bitmappy.detect_file_format") as mock_detect:
                mock_detect.return_value = "toml"

                # Mock AnimatedSprite.load method
                with patch.object(AnimatedSprite, "load") as mock_load:
                    # Create a mock loaded sprite
                    _ = self._create_test_animated_sprite()
                    mock_load.return_value = None

                    # Call the method
                    self.scene.canvas.on_load_file_event(event)

                    # Verify file format was detected
                    mock_detect.assert_called_once_with(sprite_file)

                    # Verify sprite was loaded
                    mock_load.assert_called_once_with(sprite_file)

        finally:
            # Clean up
            Path(sprite_file).unlink(missing_ok=True)

    def test_load_file_not_found(self):
        """Test handling of file not found error."""
        # Create mock event with non-existent file
        event = self._create_mock_event("nonexistent.toml")

        # Mock the detect_file_format function to raise FileNotFoundError
        with patch("glitchygames.tools.bitmappy.detect_file_format") as mock_detect:
            mock_detect.side_effect = FileNotFoundError("File not found")

            # Call the method
            self.scene.canvas.on_load_file_event(event)

            # Verify error was handled gracefully
            # (The method should not raise an exception)

    def test_load_invalid_file_format(self):
        """Test handling of invalid file format."""
        # Create mock event
        event = self._create_mock_event("invalid.txt")

        # Mock the detect_file_format function
        with patch("glitchygames.tools.bitmappy.detect_file_format") as mock_detect:
            mock_detect.return_value = "unknown"

            # Mock AnimatedSprite.load to raise an exception
            with patch.object(AnimatedSprite, "load") as mock_load:
                mock_load.side_effect = ValueError("Invalid file format")

                # Call the method
                self.scene.canvas.on_load_file_event(event)

                # Verify error was handled gracefully

    def test_canvas_resize_on_different_dimensions(self):
        """Test that canvas resizes when sprite has different dimensions."""
        # Create test sprite file with different dimensions
        sprite_content = """
[sprite]
name = "test_sprite"

[colors.0]
red = 255
green = 0
blue = 0

[[animation]]
namespace = "idle"
frame_interval = 0.5
loop = true

[[animation.frame]]
namespace = "idle"
frame_index = 0
pixels = \"\"\"
0000000000
0111111110
0111111110
0111111110
0111111110
0111111110
0111111110
0111111110
0111111110
0000000000
\"\"\"
"""
        sprite_file = self._create_test_sprite_file(sprite_content)

        try:
            # Create mock event
            event = self._create_mock_event(sprite_file)

            # Mock the entire loading process
            with patch("glitchygames.tools.bitmappy.detect_file_format") as mock_detect:
                mock_detect.return_value = "toml"

                # Create a mock loaded sprite with different dimensions using the factory
                mock_loaded_sprite = create_10x10_sprite_mock(animation_name="idle")

                # Mock the entire loading process by patching the method that loads the sprite
                with patch.object(self.scene.canvas, "_load_sprite_from_file") as mock_load:
                    mock_load.return_value = mock_loaded_sprite

                    # Mock the resize method
                    with patch.object(
                        self.scene.canvas, "_resize_canvas_to_sprite_size"
                    ) as mock_resize:
                        # Call the method
                        self.scene.canvas.on_load_file_event(event)

                        # Verify resize was called
                        mock_resize.assert_called_once_with(10, 10)

        finally:
            # Clean up
            Path(sprite_file).unlink(missing_ok=True)

    def test_ui_components_update_after_load(self):
        """Test that UI components are updated after loading."""
        # Create test sprite file
        sprite_content = """
[sprite]
name = "test_sprite"

[colors.0]
red = 255
green = 0
blue = 0

[[animation]]
namespace = "idle"
frame_interval = 0.5
loop = true

[[animation.frame]]
namespace = "idle"
frame_index = 0
pixels = \"\"\"
00000000
01111110
01111110
01111110
01111110
01111110
01111110
00000000
\"\"\"
"""
        sprite_file = self._create_test_sprite_file(sprite_content)

        try:
            # Create mock event
            event = self._create_mock_event(sprite_file)

            # Mock the entire loading process to avoid real file system issues
            with patch("glitchygames.tools.bitmappy.detect_file_format") as mock_detect:
                mock_detect.return_value = "toml"

                # Mock AnimatedSprite.load method
                with patch.object(AnimatedSprite, "load") as mock_load:
                    # Create a mock loaded sprite that mimics the actual loading behavior
                    mock_loaded_sprite = Mock(spec=AnimatedSprite)
                    animation_name = "test_sprite_ui"
                    mock_loaded_sprite._animations = {animation_name: [Mock()]}
                    mock_loaded_sprite._animation_order = [animation_name]
                    mock_loaded_sprite.current_animation = animation_name
                    mock_loaded_sprite.current_frame = 0
                    mock_loaded_sprite.is_playing = False
                    mock_loaded_sprite._is_looping = True

                    # Mock the first frame with proper get_pixel_data method
                    mock_frame = Mock()
                    mock_frame.get_pixel_data.return_value = [(255, 0, 0)] * 64  # 8x8 = 64 pixels
                    mock_loaded_sprite._animations[animation_name][0] = mock_frame

                    def mock_load_side_effect(_):
                        self.scene.canvas.animated_sprite = mock_loaded_sprite
                        self.scene.canvas.current_animation = animation_name

                    mock_load.side_effect = mock_load_side_effect

                    # Mock UI components with proper attributes
                    self.scene.canvas.mini_view = Mock()
                    self.scene.canvas.mini_view.pixels_across = 8
                    self.scene.canvas.mini_view.pixels_tall = 8
                    self.scene.canvas.live_preview = Mock()
                    self.scene.canvas.film_strip = Mock()
                    self.scene.canvas.film_strip_sprite = Mock()

                    # Ensure the mock film_strip has the set_animated_sprite method
                    self.scene.canvas.film_strip.set_animated_sprite = Mock()

                    # Mock helper methods to prevent real loading
                    with (
                        patch.object(
                            self.scene.canvas, "_load_sprite_from_file"
                        ) as mock_load_sprite,
                        patch.object(self.scene.canvas, "_check_and_resize_canvas") as mock_resize,
                        patch.object(self.scene.canvas, "_setup_animation_state") as mock_setup,
                        patch.object(self.scene.canvas, "_update_ui_components") as mock_update_ui,
                        patch.object(
                            self.scene.canvas, "_finalize_sprite_loading"
                        ) as mock_finalize,
                    ):
                        # Set up the mock for _load_sprite_from_file to return our mock sprite
                        mock_load_sprite.return_value = mock_loaded_sprite

                        # Call the method
                        self.scene.canvas.on_load_file_event(event)

                        # Verify _load_sprite_from_file was called
                        mock_load_sprite.assert_called_once_with(sprite_file)

                        # Verify _check_and_resize_canvas was called
                        mock_resize.assert_called_once_with(mock_loaded_sprite)

                        # Verify _setup_animation_state was called
                        mock_setup.assert_called_once_with(mock_loaded_sprite)

                        # Verify _update_ui_components was called
                        mock_update_ui.assert_called_once_with(mock_loaded_sprite)

                        # Verify _finalize_sprite_loading was called
                        mock_finalize.assert_called_once_with(mock_loaded_sprite, sprite_file)

        finally:
            # Clean up
            Path(sprite_file).unlink(missing_ok=True)

    def test_animation_state_after_load(self):
        """Test that animation state is correctly set after loading."""
        # Create test sprite file
        sprite_content = """
[sprite]
name = "test_sprite"

[colors.0]
red = 255
green = 0
blue = 0

[[animation]]
namespace = "idle"
frame_interval = 0.5
loop = true

[[animation.frame]]
namespace = "idle"
frame_index = 0
pixels = \"\"\"
00000000
01111110
01111110
01111110
01111110
01111110
01111110
00000000
\"\"\"
"""
        sprite_file = self._create_test_sprite_file(sprite_content)

        try:
            # Create mock event
            event = self._create_mock_event(sprite_file)

            # Mock the entire loading process
            with patch("glitchygames.tools.bitmappy.detect_file_format") as mock_detect:
                mock_detect.return_value = "toml"

                # Create a mock loaded sprite using the centralized factory
                mock_loaded_sprite = MockFactory.create_animated_sprite_mock(
                    animation_name="test_sprite",
                    frame_size=(8, 8),
                    pixel_color=(255, 0, 0)
                )

                # Mock the entire loading process by patching the method that loads the sprite
                with patch.object(self.scene.canvas, "_load_sprite_from_file") as mock_load:
                    mock_load.return_value = mock_loaded_sprite

                    # Mock helper methods
                    with (
                        patch.object(self.scene.canvas, "_copy_sprite_to_canvas"),
                        patch.object(self.scene.canvas, "_update_mini_view_from_current_frame"),
                    ):
                        # Call the method
                        self.scene.canvas.on_load_file_event(event)

                        # Verify animation state - use introspected animation name
                        expected_animation = self._get_first_animation_name(mock_loaded_sprite)
                        assert self.scene.canvas.current_animation == expected_animation
                        assert self.scene.canvas.animated_sprite == mock_loaded_sprite

        finally:
            # Clean up
            Path(sprite_file).unlink(missing_ok=True)

    def test_string_event_parameter(self):
        """Test that method works with string parameter instead of event object."""
        # Create test sprite file
        sprite_content = """
[sprite]
name = "test_sprite"

[colors.0]
red = 255
green = 0
blue = 0

[[animation]]
namespace = "idle"
frame_interval = 0.5
loop = true

[[animation.frame]]
namespace = "idle"
frame_index = 0
pixels = \"\"\"
00000000
01111110
01111110
01111110
01111110
01111110
01111110
00000000
\"\"\"
"""
        sprite_file = self._create_test_sprite_file(sprite_content)

        try:
            # Mock the detect_file_format function
            with patch("glitchygames.tools.bitmappy.detect_file_format") as mock_detect:
                mock_detect.return_value = "toml"

                # Mock AnimatedSprite.load method
                with patch.object(AnimatedSprite, "load") as mock_load:
                    # Create a mock loaded sprite
                    mock_loaded_sprite = self._create_test_animated_sprite()

                    def mock_load_side_effect(_):
                        self.scene.canvas.animated_sprite = mock_loaded_sprite

                    mock_load.side_effect = mock_load_side_effect

                    # Mock helper methods
                    with (
                        patch.object(self.scene.canvas, "_copy_sprite_to_canvas"),
                        patch.object(self.scene.canvas, "_update_mini_view_from_current_frame"),
                    ):
                        # Call the method with string parameter
                        self.scene.canvas.on_load_file_event(sprite_file)

                        # Verify file format was detected
                        mock_detect.assert_called_once_with(sprite_file)

                        # Verify sprite was loaded
                        mock_load.assert_called_once_with(sprite_file)

        finally:
            # Clean up
            Path(sprite_file).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
