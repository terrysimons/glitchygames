"""Test suite for Canvas Interface refactoring.

This module tests the new canvas interfaces that allow the bitmap editor to work
with animated sprites through a unified API.

Tests cover:
- AnimatedCanvasInterface functionality
- AnimatedSpriteSerializer operations
- AnimatedCanvasRenderer rendering
- AnimatedCanvasSprite functionality
"""

import sys
from pathlib import Path

import pygame
import pytest

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from glitchygames.tools.bitmappy import AnimatedCanvasSprite
from glitchygames.tools.canvas_interfaces import (
    AnimatedCanvasInterface,
    AnimatedCanvasRenderer,
    AnimatedSpriteSerializer,
)

from tests.mocks.test_mock_factory import MockFactory

# Constants for test values
CANVAS_SIZE = 8
CANVAS_PIXEL_COUNT = 64  # 8x8 = 64 pixels
PIXEL_SIZE = 16
SMALL_CANVAS_SIZE = 4
SMALL_CANVAS_PIXEL_COUNT = 16  # 4x4 = 16 pixels


class TestAnimatedCanvasInterfaces:
    """Test suite for animated canvas interface functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up test fixtures using centralized mocks."""
        self._mocker = mocker
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

        # Create a test animated sprite
        self.animated_sprite = AnimatedSprite()

        # Create a SpriteFrame with pixel data
        surface = pygame.Surface((8, 8))
        frame = SpriteFrame(surface)
        # Set pixel data for the frame
        pixel_data = [
            (255, 0, 0) if i % 2 == 0 else (0, 255, 0) for i in range(64)
        ]  # Red/Green pattern
        frame.set_pixel_data(pixel_data)

        # Add a simple animation with the SpriteFrame
        self.animated_sprite.add_animation("idle", [frame])

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

    def test_animated_canvas_interface_creation(self):
        """Test that animated canvas interface is created correctly."""
        interface = self.canvas.get_canvas_interface()
        assert isinstance(interface, AnimatedCanvasInterface)

    def test_animated_canvas_interface_dimensions(self):
        """Test animated canvas interface dimension methods."""
        interface = self.canvas.get_canvas_interface()

        # Test getting dimensions
        width, height = interface.get_dimensions()
        assert width == CANVAS_SIZE
        assert height == CANVAS_SIZE

    def test_animated_canvas_interface_pixel_operations(self):
        """Test animated canvas interface pixel manipulation."""
        interface = self.canvas.get_canvas_interface()

        # Test setting and getting individual pixels
        interface.set_pixel_at(0, 0, (255, 0, 0))  # Red pixel
        interface.set_pixel_at(1, 1, (0, 255, 0))  # Green pixel

        red_pixel = interface.get_pixel_at(0, 0)
        green_pixel = interface.get_pixel_at(1, 1)

        assert red_pixel == (255, 0, 0, 255)
        assert green_pixel == (0, 255, 0, 255)

    def test_animated_sprite_serializer_creation(self):
        """Test that animated sprite serializer is created correctly."""
        serializer = self.canvas.get_sprite_serializer()
        assert isinstance(serializer, AnimatedSpriteSerializer)

    def test_animated_canvas_renderer_creation(self):
        """Test that animated canvas renderer is created correctly."""
        renderer = self.canvas.get_canvas_renderer()
        assert isinstance(renderer, AnimatedCanvasRenderer)

    def test_animated_canvas_renderer_pixel_size(self):
        """Test animated canvas renderer pixel size method."""
        renderer = self.canvas.get_canvas_renderer()
        pixel_width, pixel_height = renderer.get_pixel_size()

        assert pixel_width == PIXEL_SIZE
        assert pixel_height == PIXEL_SIZE

    def test_animated_canvas_renderer_rendering(self):
        """Test animated canvas renderer rendering methods."""
        renderer = self.canvas.get_canvas_renderer()

        # Test rendering
        surface = renderer.render(self.canvas)
        assert surface.get_size() == (128, 128)  # 8*16 x 8*16

        # Test force redraw
        redraw_surface = renderer.force_redraw(self.canvas)
        assert redraw_surface.get_size() == (128, 128)

    def test_animated_canvas_functionality(self):
        """Test that AnimatedCanvasSprite functionality works."""
        # Test that animated canvas attributes exist
        assert hasattr(self.canvas, "animated_sprite")
        assert hasattr(self.canvas, "current_animation")
        assert hasattr(self.canvas, "current_frame")
        assert hasattr(self.canvas, "pixels")
        assert hasattr(self.canvas, "pixels_across")
        assert hasattr(self.canvas, "pixels_tall")

        # Test that animated canvas methods exist
        assert hasattr(self.canvas, "force_redraw")
        assert hasattr(self.canvas, "show_frame")
        assert hasattr(self.canvas, "update_animation")

        # Test setting pixels
        self.canvas.pixels[0] = (255, 0, 0)  # Red pixel
        self.canvas.pixels[1] = (0, 255, 0)  # Green pixel

        # Test that the interface reflects the changes
        interface = self.canvas.get_canvas_interface()
        red_pixel = interface.get_pixel_at(0, 0)
        green_pixel = interface.get_pixel_at(1, 0)

        assert red_pixel == (255, 0, 0, 255)
        assert green_pixel == (0, 255, 0, 255)

    def test_interface_integration(self):
        """Test that all animated interfaces work together correctly."""
        # Get all interface components
        interface = self.canvas.get_canvas_interface()
        renderer = self.canvas.get_canvas_renderer()

        # Test that they all work together
        interface.set_pixel_at(2, 2, (0, 0, 255))  # Blue pixel
        surface = renderer.render(self.canvas)

        # Verify the pixel was set correctly
        blue_pixel = interface.get_pixel_at(2, 2)
        assert blue_pixel == (0, 0, 255, 255)

        # Verify the surface was rendered
        assert surface is not None
        assert surface.get_size() == (128, 128)


class TestAnimatedCanvasInterfaceEdgeCases:
    """Test edge cases for animated canvas interfaces."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up test fixtures using centralized mocks."""
        self._mocker = mocker
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

        # Create a test animated sprite
        self.animated_sprite = AnimatedSprite()

        # Create a SpriteFrame with pixel data
        surface = pygame.Surface((4, 4))
        frame = SpriteFrame(surface)
        # Set pixel data for the frame
        pixel_data = [
            (255, 0, 0) if i % 2 == 0 else (0, 255, 0) for i in range(16)
        ]  # Red/Green pattern
        frame.set_pixel_data(pixel_data)

        # Add a simple animation with the SpriteFrame
        self.animated_sprite.add_animation("idle", [frame])

        self.canvas = AnimatedCanvasSprite(
            animated_sprite=self.animated_sprite,
            name="Test Animated Canvas",
            x=0,
            y=0,
            pixels_across=4,
            pixels_tall=4,
            pixel_width=16,
            pixel_height=16,
        )

    def test_out_of_bounds_pixel_access(self):
        """Test accessing pixels outside canvas bounds."""
        interface = self.canvas.get_canvas_interface()

        # Test out-of-bounds access
        out_of_bounds_pixel = interface.get_pixel_at(10, 10)
        assert out_of_bounds_pixel == (255, 0, 255, 255)  # Should return magenta

    def test_out_of_bounds_pixel_setting(self):
        """Test setting pixels outside canvas bounds."""
        interface = self.canvas.get_canvas_interface()

        # Test setting out-of-bounds pixel (should not crash)
        interface.set_pixel_at(10, 10, (255, 0, 0))

        # Verify the canvas wasn't corrupted
        assert len(self.canvas.pixels) == SMALL_CANVAS_PIXEL_COUNT  # 4x4 = 16 pixels


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
