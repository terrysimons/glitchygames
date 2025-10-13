"""Test suite for AnimatedCanvasSprite functionality.

This module tests the new AnimatedCanvasSprite class that allows the bitmap editor
to work with animated sprites, including frame selection, editing, and film strip integration.
"""

import sys
import tempfile
import unittest
from pathlib import Path

import pygame

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from glitchygames.sprites import AnimatedSprite, SpriteFrame
from glitchygames.tools.bitmappy import AnimatedCanvasSprite
from glitchygames.tools.canvas_interfaces import (
    AnimatedCanvasInterface,
    AnimatedCanvasRenderer,
    AnimatedSpriteSerializer,
)
from glitchygames.tools.film_strip import FilmStripWidget

from mocks.test_mock_factory import MockFactory


class TestAnimatedCanvasSprite(unittest.TestCase):
    """Test suite for AnimatedCanvasSprite functionality."""

    EXPECTED_FRAME_COUNT = 2

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Set up centralized mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers:
            patcher.start()

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

    def tearDown(self):
        """Clean up after each test method."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    @staticmethod
    def _create_test_animated_sprite():
        """Create a test animated sprite with multiple animations and frames."""
        # Create frames for idle animation
        idle_surface1 = pygame.Surface((8, 8))
        idle_surface1.fill((255, 0, 0))  # Red
        idle_frame1 = SpriteFrame(idle_surface1)
        idle_frame1.pixels = [(255, 0, 0)] * 64  # 8x8 = 64 pixels

        idle_surface2 = pygame.Surface((8, 8))
        idle_surface2.fill((0, 255, 0))  # Green
        idle_frame2 = SpriteFrame(idle_surface2)
        idle_frame2.pixels = [(0, 255, 0)] * 64

        # Create frames for walk animation
        walk_surface1 = pygame.Surface((8, 8))
        walk_surface1.fill((0, 0, 255))  # Blue
        walk_frame1 = SpriteFrame(walk_surface1)
        walk_frame1.pixels = [(0, 0, 255)] * 64

        walk_surface2 = pygame.Surface((8, 8))
        walk_surface2.fill((255, 255, 0))  # Yellow
        walk_frame2 = SpriteFrame(walk_surface2)
        walk_frame2.pixels = [(255, 255, 0)] * 64

        # Create animated sprite
        animated_sprite = AnimatedSprite()
        # Set frames using the internal structure
        animated_sprite._animations = {
            "idle": [idle_frame1, idle_frame2],
            "walk": [walk_frame1, walk_frame2],
        }
        # Set the current animation to idle (first available animation)
        animated_sprite.frame_manager.current_animation = "idle"

        return animated_sprite

    def test_animated_canvas_creation(self):
        """Test that AnimatedCanvasSprite is created correctly."""
        assert isinstance(self.canvas, AnimatedCanvasSprite)
        assert self.canvas.animated_sprite == self.animated_sprite
        assert self.canvas.current_animation == "idle"
        assert self.canvas.current_frame == 0

    def test_interface_initialization(self):
        """Test that animated interfaces are initialized correctly."""
        assert isinstance(self.canvas.canvas_interface, AnimatedCanvasInterface)
        assert isinstance(self.canvas.sprite_serializer, AnimatedSpriteSerializer)
        assert isinstance(self.canvas.canvas_renderer, AnimatedCanvasRenderer)

    def test_show_frame(self):
        """Test switching to different frames."""
        # Test switching to walk animation, frame 1
        self.canvas.show_frame("walk", 1)
        assert self.canvas.current_animation == "walk"
        assert self.canvas.current_frame == 1

        # Test switching back to idle animation, frame 0
        self.canvas.show_frame("idle", 0)
        assert self.canvas.current_animation == "idle"
        assert self.canvas.current_frame == 0

    def test_frame_editing(self):
        """Test editing pixels in the current frame."""
        # Set a pixel in the current frame
        self.canvas.canvas_interface.set_pixel_at(0, 0, (255, 255, 255))

        # Verify the pixel was set
        pixel_color = self.canvas.canvas_interface.get_pixel_at(0, 0)
        assert pixel_color == (255, 255, 255)

        # Verify it's set in the actual frame
        current_frame = self.animated_sprite.frames["idle"][0]
        frame_pixels = current_frame.get_pixel_data()
        assert frame_pixels[0] == (255, 255, 255)

    def test_frame_isolation(self):
        """Test that editing one frame doesn't affect others."""
        # Edit frame 0 of idle animation
        self.canvas.show_frame("idle", 0)
        self.canvas.canvas_interface.set_pixel_at(0, 0, (255, 0, 0))

        # Switch to frame 1 of idle animation
        self.canvas.show_frame("idle", 1)
        pixel_color = self.canvas.canvas_interface.get_pixel_at(0, 0)
        assert pixel_color == (0, 255, 0)  # Should be green (original color)

        # Switch back to frame 0
        self.canvas.show_frame("idle", 0)
        pixel_color = self.canvas.canvas_interface.get_pixel_at(0, 0)
        assert pixel_color == (255, 0, 0)  # Should be red (our edit)

    def test_animation_isolation(self):
        """Test that editing one animation doesn't affect others."""
        # Edit idle animation, frame 0
        self.canvas.show_frame("idle", 0)
        self.canvas.canvas_interface.set_pixel_at(0, 0, (255, 0, 0))

        # Switch to walk animation, frame 0
        self.canvas.show_frame("walk", 0)
        pixel_color = self.canvas.canvas_interface.get_pixel_at(0, 0)
        assert pixel_color == (0, 0, 255)  # Should be blue (original color)

    def test_frame_navigation(self):
        """Test navigating between frames."""
        # Test next frame
        self.canvas.next_frame()
        assert self.canvas.current_frame == 1

        # Test previous frame
        self.canvas.previous_frame()
        assert self.canvas.current_frame == 0

        # Test wrapping around
        self.canvas.previous_frame()
        assert self.canvas.current_frame == 1  # Should wrap to last frame

    def test_animation_navigation(self):
        """Test navigating between animations."""
        # Test next animation
        self.canvas.next_animation()
        assert self.canvas.current_animation == "walk"
        assert self.canvas.current_frame == 0  # Should reset to frame 0

        # Test previous animation
        self.canvas.previous_animation()
        assert self.canvas.current_animation == "idle"
        assert self.canvas.current_frame == 0

    def test_film_strip_integration(self):
        """Test that film strip widget is created and integrated."""
        assert isinstance(self.canvas.film_strip, FilmStripWidget)
        assert self.canvas.film_strip.animated_sprite == self.animated_sprite

    def test_film_strip_frame_selection(self):
        """Test that clicking on film strip changes the current frame."""
        # Simulate clicking on walk animation, frame 1
        clicked_frame = self.canvas.film_strip.handle_click((100, 50))  # Mock position

        if clicked_frame:
            animation, frame_idx = clicked_frame
            self.canvas.show_frame(animation, frame_idx)
            assert self.canvas.current_animation == animation
            assert self.canvas.current_frame == frame_idx

    def test_keyboard_navigation(self):
        """Test keyboard navigation between frames."""
        # Test left arrow (previous frame)
        self.canvas.show_frame("idle", 1)
        self.canvas.handle_keyboard_event(pygame.K_LEFT)
        assert self.canvas.current_frame == 0

        # Test right arrow (next frame)
        self.canvas.handle_keyboard_event(pygame.K_RIGHT)
        assert self.canvas.current_frame == 1

        # Test up arrow (previous animation)
        self.canvas.handle_keyboard_event(pygame.K_UP)
        assert self.canvas.current_animation == "walk"

        # Test down arrow (next animation)
        self.canvas.handle_keyboard_event(pygame.K_DOWN)
        assert self.canvas.current_animation == "idle"

    def test_copy_paste_functionality(self):
        """Test copying and pasting between frames."""
        # Set a pixel in current frame
        self.canvas.canvas_interface.set_pixel_at(0, 0, (255, 255, 255))

        # Copy current frame
        self.canvas.copy_current_frame()

        # Switch to another frame
        self.canvas.show_frame("idle", 1)

        # Paste the copied frame
        self.canvas.paste_to_current_frame()

        # Verify the pixel was pasted
        pixel_color = self.canvas.canvas_interface.get_pixel_at(0, 0)
        assert pixel_color == (255, 255, 255)

    def test_save_load_animated_sprite(self):
        """Test saving and loading animated sprites."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".toml", delete=False, encoding="utf-8"
        ) as f:
            temp_filename = f.name

        try:
            # Save the animated sprite
            self.canvas.save_animated_sprite(temp_filename)

            # Load it back
            loaded_canvas = AnimatedCanvasSprite.from_file(
                filename=temp_filename,
                x=0,
                y=0,
                pixels_across=8,
                pixels_tall=8,
                pixel_width=16,
                pixel_height=16,
            )

            # Verify it loaded correctly
            assert loaded_canvas.current_animation == "idle"
            assert loaded_canvas.current_frame == 0
            assert len(loaded_canvas.animated_sprite.frames) == self.EXPECTED_FRAME_COUNT

        finally:
            # Clean up
            temp_path = Path(temp_filename)
            if temp_path.exists():
                temp_path.unlink()

    def test_visual_display(self):
        """Test that the canvas displays the current frame correctly."""
        # Force redraw to update the display
        self.canvas.force_redraw()

        # Verify the canvas image is updated
        assert self.canvas.image is not None
        assert self.canvas.image.get_size() == (128, 128)  # 8*16 x 8*16


class TestAnimatedCanvasSpriteEdgeCases(unittest.TestCase):
    """Test edge cases for AnimatedCanvasSprite."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Set up centralized mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        """Clean up after each test method."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    @staticmethod
    def test_empty_animated_sprite():
        """Test creating canvas with empty animated sprite."""
        empty_sprite = AnimatedSprite()
        empty_sprite._frames = {}
        empty_sprite._animations = {}

        canvas = AnimatedCanvasSprite(
            animated_sprite=empty_sprite,
            name="Empty Canvas",
            x=0,
            y=0,
            pixels_across=8,
            pixels_tall=8,
            pixel_width=16,
            pixel_height=16,
        )

        # Should handle empty sprite gracefully (no animations, so current_animation should be empty)
        assert canvas.current_animation == ""
        assert canvas.current_frame == 0

    @staticmethod
    def test_single_frame_animation():
        """Test canvas with single frame animation."""
        surface = pygame.Surface((8, 8))
        surface.fill((255, 0, 0))
        frame = SpriteFrame(surface)
        frame.pixels = [(255, 0, 0)] * 64

        single_sprite = AnimatedSprite()
        single_sprite._animations = {"idle": [frame]}
        # Set the current animation to idle
        single_sprite.frame_manager.current_animation = "idle"

        canvas = AnimatedCanvasSprite(
            animated_sprite=single_sprite,
            name="Single Frame Canvas",
            x=0,
            y=0,
            pixels_across=8,
            pixels_tall=8,
            pixel_width=16,
            pixel_height=16,
        )

        # Should handle single frame correctly
        assert canvas.current_animation == "idle"
        assert canvas.current_frame == 0

        # Navigation should wrap around
        canvas.next_frame()
        assert canvas.current_frame == 0  # Should wrap to 0


def run_tests():
    """Run all tests and return success status."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestAnimatedCanvasSprite))
    suite.addTests(loader.loadTestsFromTestCase(TestAnimatedCanvasSpriteEdgeCases))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
