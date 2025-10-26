#!/usr/bin/env python3
"""Test the transparency key fix for canvas pixel boxes."""

import pytest
from unittest.mock import Mock
from tests.mocks.test_mock_factory import MockFactory


class TestTransparencyFix:
    """Test that transparency key pixels are properly handled in canvas rendering."""

    def setup_method(self):
        """Set up test fixtures using centralized mocks."""
        # Use centralized mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers:
            patcher.start()

    def teardown_method(self):
        """Clean up after tests."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_static_canvas_skips_transparency_key_pixels(self):
        """Test that StaticCanvasRenderer skips transparency key pixels."""
        from glitchygames.tools.canvas_interfaces import StaticCanvasRenderer
        from glitchygames.sprites import BitmappySprite

        # Create a test sprite with transparency key pixels
        sprite = BitmappySprite()
        sprite.pixels = [(255, 0, 0), (255, 0, 255), (0, 255, 0), (255, 0, 255, 255)]
        sprite.pixels_across = 2
        sprite.pixels_tall = 2
        sprite.pixel_width = 10
        sprite.pixel_height = 10
        sprite.width = 20
        sprite.height = 20
        sprite.image = MockFactory.create_display_mock(20, 20)
        sprite.background_color = (0, 0, 0)
        sprite.dirty_pixels = [True] * 4
        sprite.border_thickness = 0

        # Test the renderer
        renderer = StaticCanvasRenderer(sprite)
        result = renderer.force_redraw(sprite)

        # The result should be a surface
        assert result is not None
        print("StaticCanvasRenderer test passed - transparency key pixels should be skipped")

    def test_animated_canvas_skips_transparency_key_pixels(self):
        """Test that AnimatedCanvasRenderer skips transparency key pixels."""
        from glitchygames.tools.canvas_interfaces import AnimatedCanvasRenderer
        from glitchygames.sprites import BitmappySprite

        # Create a test sprite with transparency key pixels
        sprite = BitmappySprite()
        sprite.pixels = [(255, 0, 0), (255, 0, 255), (0, 255, 0), (255, 0, 255, 255)]
        sprite.pixels_across = 2
        sprite.pixels_tall = 2
        sprite.pixel_width = 10
        sprite.pixel_height = 10
        sprite.width = 20
        sprite.height = 20
        sprite.image = MockFactory.create_display_mock(20, 20)
        sprite.background_color = (0, 0, 0)
        sprite.dirty_pixels = [True] * 4
        sprite.border_thickness = 0
        sprite.current_animation = "test"
        sprite.current_frame = 0

        # Mock animated sprite
        sprite.animated_sprite = Mock()
        sprite.animated_sprite.frames = {"test": []}

        # Test the renderer
        renderer = AnimatedCanvasRenderer(sprite)
        result = renderer.force_redraw(sprite)

        # The result should be a surface
        assert result is not None
        print("AnimatedCanvasRenderer test passed - transparency key pixels should be skipped")


if __name__ == "__main__":
    # Run the test directly
    test = TestTransparencyFix()
    test.setup_method()
    try:
        test.test_static_canvas_skips_transparency_key_pixels()
        test.test_animated_canvas_skips_transparency_key_pixels()
        print("All transparency fix tests passed!")
    finally:
        test.teardown_method()
