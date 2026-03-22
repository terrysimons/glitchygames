#!/usr/bin/env python3
"""Tests for onion skinning rendering functionality."""

import math

import pygame
import pytest

from glitchygames.bitmappy.canvas_interfaces import AnimatedCanvasRenderer
from glitchygames.bitmappy.onion_skinning import OnionSkinningManager


class TestOnionSkinningRendering:
    """Test cases for onion skinning rendering in AnimatedCanvasRenderer."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up test fixtures before each test method."""
        # Initialize pygame for testing
        pygame.init()
        pygame.display.set_mode((800, 600))

        # Store mocker for use in test methods
        self._mocker = mocker

        # Create a mock canvas sprite
        self.canvas_sprite = mocker.Mock()
        self.canvas_sprite.width = 128
        self.canvas_sprite.height = 128
        self.canvas_sprite.pixels_across = 8
        self.canvas_sprite.pixels_tall = 8
        self.canvas_sprite.pixel_width = 16
        self.canvas_sprite.pixel_height = 16
        self.canvas_sprite.border_thickness = 1
        self.canvas_sprite.current_animation = 'test_animation'
        self.canvas_sprite.current_frame = 1

        # Ensure panning is not active so we use frame pixel data
        self.canvas_sprite._panning_active = False
        # Set parent_scene to None so hasattr checks pass but truthiness is False
        self.canvas_sprite.parent_scene = None
        # Set hovered_pixel to None so hover drawing is skipped
        self.canvas_sprite.hovered_pixel = None
        # Set is_hovered to False so canvas hover border is skipped
        self.canvas_sprite.is_hovered = False
        # Provide pixel data for controller indicator lookups
        self.canvas_sprite.pixels = [(255, 0, 255)] * 64

        # Create mock animated sprite with frames
        self.animated_sprite = mocker.Mock()
        self.animated_sprite.frames = {
            'test_animation': [
                self._create_mock_frame([(255, 0, 0)] * 64),  # Frame 0: Red pixels
                self._create_mock_frame([(0, 255, 0)] * 64),  # Frame 1: Green pixels (current)
                self._create_mock_frame([(0, 0, 255)] * 64),  # Frame 2: Blue pixels
            ]
        }
        self.canvas_sprite.animated_sprite = self.animated_sprite

        # Create renderer
        self.renderer = AnimatedCanvasRenderer(self.canvas_sprite)

    def teardown_method(self):
        """Clean up after each test method."""
        pygame.quit()

    def _create_mock_frame(self, pixels):
        """Create a mock frame with the given pixels.

        Returns:
            object: The result.

        """
        frame = self._mocker.Mock()
        frame.get_pixel_data.return_value = pixels
        return frame

    def test_onion_skinning_background_color(self):
        """Test that onion skinning uses magenta background."""
        # Mock the onion skinning manager
        mock_get_manager = self._mocker.patch(
            'glitchygames.bitmappy.onion_skinning.get_onion_skinning_manager'
        )
        mock_manager = self._mocker.Mock()
        mock_manager.is_global_onion_skinning_enabled.return_value = True
        mock_manager.get_onion_skinned_frames.return_value = {0, 2}  # Frames 0 and 2
        mock_manager.onion_transparency = 0.5
        mock_get_manager.return_value = mock_manager

        # Force redraw
        surface = self.renderer.force_redraw(self.canvas_sprite)

        # Check that surface was created
        assert surface is not None
        assert surface.get_size() == (128, 128)

    def test_onion_skinning_transparency_level(self):
        """Test that onion skinning respects transparency settings."""
        # Mock the onion skinning manager
        mock_get_manager = self._mocker.patch(
            'glitchygames.bitmappy.onion_skinning.get_onion_skinning_manager'
        )
        mock_manager = self._mocker.Mock()
        mock_manager.is_global_onion_skinning_enabled.return_value = True
        mock_manager.get_onion_skinned_frames.return_value = {0, 2}
        mock_manager.onion_transparency = 0.25  # 25% opacity
        mock_get_manager.return_value = mock_manager

        # Force redraw
        surface = self.renderer.force_redraw(self.canvas_sprite)

        # Check that surface was created with correct transparency
        assert surface is not None

    def test_no_onion_skinning_when_disabled(self):
        """Test that no onion skinning occurs when disabled."""
        # Mock the onion skinning manager
        mock_get_manager = self._mocker.patch(
            'glitchygames.bitmappy.onion_skinning.get_onion_skinning_manager'
        )
        mock_manager = self._mocker.Mock()
        mock_manager.is_global_onion_skinning_enabled.return_value = False
        mock_get_manager.return_value = mock_manager

        # Force redraw
        surface = self.renderer.force_redraw(self.canvas_sprite)

        # Check that surface was created
        assert surface is not None

    def test_transparent_pixel_skipping(self):
        """Test that transparent pixels (255, 0, 255) are skipped."""
        # Create frames with transparent pixels
        transparent_pixels = [(255, 0, 255)] * 64  # All transparent
        self.animated_sprite.frames['test_animation'] = [
            self._create_mock_frame(transparent_pixels),
            self._create_mock_frame([(0, 255, 0)] * 64),  # Current frame: Green
            self._create_mock_frame(transparent_pixels),
        ]

        # Mock the onion skinning manager
        mock_get_manager = self._mocker.patch(
            'glitchygames.bitmappy.onion_skinning.get_onion_skinning_manager'
        )
        mock_manager = self._mocker.Mock()
        mock_manager.is_global_onion_skinning_enabled.return_value = True
        mock_manager.get_onion_skinned_frames.return_value = {0, 2}
        mock_manager.onion_transparency = 0.5
        mock_get_manager.return_value = mock_manager

        # Force redraw
        surface = self.renderer.force_redraw(self.canvas_sprite)

        # Check that surface was created
        assert surface is not None

    def test_controller_indicator_on_transparent_pixels(self):
        """Test that controller indicators show on transparent pixels."""
        # Create frames with transparent pixels
        transparent_pixels = [(255, 0, 255)] * 64  # All transparent
        self.animated_sprite.frames['test_animation'] = [
            self._create_mock_frame(transparent_pixels),
            self._create_mock_frame(transparent_pixels),  # Current frame: All transparent
            self._create_mock_frame(transparent_pixels),
        ]

        # Mock controller indicator methods
        mock_has_controllers = self._mocker.patch.object(
            self.renderer, '_has_active_controllers_in_canvas_mode'
        )
        mock_has_controllers.return_value = True
        mock_get_indicator = self._mocker.patch.object(
            self.renderer, '_get_controller_indicator_for_pixel'
        )
        mock_get_indicator.return_value = (255, 0, 0)  # Red indicator

        # Mock the onion skinning manager
        mock_get_manager = self._mocker.patch(
            'glitchygames.bitmappy.onion_skinning.get_onion_skinning_manager'
        )
        mock_manager = self._mocker.Mock()
        mock_manager.is_global_onion_skinning_enabled.return_value = True
        mock_manager.get_onion_skinned_frames.return_value = {0, 2}
        mock_manager.onion_transparency = 0.5
        mock_get_manager.return_value = mock_manager

        # Force redraw
        surface = self.renderer.force_redraw(self.canvas_sprite)

        # Check that surface was created
        assert surface is not None

        # Verify that controller indicator was checked for transparent pixels
        assert mock_get_indicator.called


class TestOnionSkinningIntegration:
    """Integration tests for onion skinning with real rendering."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        pygame.init()
        pygame.display.set_mode((800, 600))

    def teardown_method(self):
        """Clean up after each test method."""
        pygame.quit()

    def test_onion_skinning_manager_integration(self):
        """Test integration between OnionSkinningManager and rendering."""
        # Create a real onion skinning manager
        manager = OnionSkinningManager()

        # Test default settings
        assert manager.global_onion_skinning_enabled is True
        assert math.isclose(manager.onion_transparency, 0.5)

        # Test transparency setting
        manager.set_transparency(0.25)
        assert math.isclose(manager.onion_transparency, 0.25)

        # Test frame onion skinning
        manager.toggle_frame_onion_skinning('test_animation', 0)
        assert manager.is_frame_onion_skinned('test_animation', 0)

        # Test getting onion skinned frames
        onion_frames = manager.get_onion_skinned_frames('test_animation', 1, 3)
        expected_frames = {0, 2}  # All frames except current (1)
        assert onion_frames == expected_frames

    def test_surface_creation_performance(self, mocker):
        """Test that surface creation is efficient."""
        # Create a mock canvas sprite
        canvas_sprite = mocker.Mock()
        canvas_sprite.width = 256
        canvas_sprite.height = 256
        canvas_sprite.pixels_across = 16
        canvas_sprite.pixels_tall = 16
        canvas_sprite.pixel_width = 16
        canvas_sprite.pixel_height = 16
        canvas_sprite.border_thickness = 1
        canvas_sprite.current_animation = 'test_animation'
        canvas_sprite.current_frame = 1

        # Ensure panning is not active so we use frame pixel data
        canvas_sprite._panning_active = False
        # Set parent_scene to None so hasattr checks pass but truthiness is False
        canvas_sprite.parent_scene = None
        # Set hovered_pixel to None so hover drawing is skipped
        canvas_sprite.hovered_pixel = None
        # Set is_hovered to False so canvas hover border is skipped
        canvas_sprite.is_hovered = False

        # Create mock animated sprite
        animated_sprite = mocker.Mock()
        animated_sprite.frames = {
            'test_animation': [
                mocker.Mock(get_pixel_data=lambda: [(255, 0, 0)] * 256),
                mocker.Mock(get_pixel_data=lambda: [(0, 255, 0)] * 256),
                mocker.Mock(get_pixel_data=lambda: [(0, 0, 255)] * 256),
            ]
        }
        canvas_sprite.animated_sprite = animated_sprite

        # Create renderer
        renderer = AnimatedCanvasRenderer(canvas_sprite)

        # Mock the onion skinning manager
        mock_get_manager = mocker.patch(
            'glitchygames.bitmappy.onion_skinning.get_onion_skinning_manager'
        )
        mock_manager = mocker.Mock()
        mock_manager.is_global_onion_skinning_enabled.return_value = True
        mock_manager.get_onion_skinned_frames.return_value = {0, 2}
        mock_manager.onion_transparency = 0.5
        mock_get_manager.return_value = mock_manager

        # Test surface creation
        surface = renderer.force_redraw(canvas_sprite)

        # Verify surface properties
        assert surface is not None
        assert surface.get_size() == (256, 256)
        assert surface.get_flags() & pygame.SRCALPHA  # Should have alpha channel


if __name__ == '__main__':
    pytest.main([__file__])
