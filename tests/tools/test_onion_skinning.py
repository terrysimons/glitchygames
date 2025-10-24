#!/usr/bin/env python3
"""Tests for onion skinning functionality."""

import pytest
import pygame
from unittest.mock import Mock, patch

from glitchygames.tools.onion_skinning import OnionSkinningManager, get_onion_skinning_manager
from glitchygames.tools.onion_skinning_renderer import render_onion_skinning_frames


class TestOnionSkinningManager:
    """Test cases for OnionSkinningManager."""
    
    def test_initialization(self):
        """Test that OnionSkinningManager initializes correctly."""
        manager = OnionSkinningManager()
        
        assert manager.onion_skinning_enabled == {}
        assert manager.global_onion_skinning_enabled is True
        assert manager.onion_transparency == 0.5
    
    def test_toggle_frame_onion_skinning(self):
        """Test toggling onion skinning for a specific frame."""
        manager = OnionSkinningManager()
        
        # Initially disabled
        assert not manager.is_frame_onion_skinned("animation1", 0)
        
        # Toggle on
        result = manager.toggle_frame_onion_skinning("animation1", 0)
        assert result is True
        assert manager.is_frame_onion_skinned("animation1", 0)
        
        # Toggle off
        result = manager.toggle_frame_onion_skinning("animation1", 0)
        assert result is False
        assert not manager.is_frame_onion_skinned("animation1", 0)
    
    def test_multiple_frames_same_animation(self):
        """Test onion skinning for multiple frames in the same animation."""
        manager = OnionSkinningManager()
        
        # Enable onion skinning for frames 0 and 2
        manager.toggle_frame_onion_skinning("animation1", 0)
        manager.toggle_frame_onion_skinning("animation1", 2)
        
        assert manager.is_frame_onion_skinned("animation1", 0)
        assert not manager.is_frame_onion_skinned("animation1", 1)
        assert manager.is_frame_onion_skinned("animation1", 2)
    
    def test_multiple_animations(self):
        """Test onion skinning across multiple animations."""
        manager = OnionSkinningManager()
        
        # Enable onion skinning for different animations
        manager.toggle_frame_onion_skinning("animation1", 0)
        manager.toggle_frame_onion_skinning("animation2", 1)
        
        assert manager.is_frame_onion_skinned("animation1", 0)
        assert manager.is_frame_onion_skinned("animation2", 1)
        assert not manager.is_frame_onion_skinned("animation1", 1)
        assert not manager.is_frame_onion_skinned("animation2", 0)
    
    def test_get_onion_skinned_frames(self):
        """Test getting all onion skinned frames for an animation."""
        manager = OnionSkinningManager()
        
        # Enable onion skinning for frames 0, 2, and 4
        manager.toggle_frame_onion_skinning("animation1", 0)
        manager.toggle_frame_onion_skinning("animation1", 2)
        manager.toggle_frame_onion_skinning("animation1", 4)
        
        # Get onion skinned frames (excluding current frame 1)
        onion_frames = manager.get_onion_skinned_frames("animation1", 1)
        assert onion_frames == {0, 2, 4}
        
        # Get onion skinned frames (excluding current frame 0)
        onion_frames = manager.get_onion_skinned_frames("animation1", 0)
        assert onion_frames == {2, 4}
    
    def test_global_onion_skinning_toggle(self):
        """Test global onion skinning toggle."""
        manager = OnionSkinningManager()
        
        # Enable a frame
        manager.toggle_frame_onion_skinning("animation1", 0)
        assert manager.is_frame_onion_skinned("animation1", 0)
        
        # Disable global onion skinning
        manager.toggle_global_onion_skinning()
        assert not manager.global_onion_skinning_enabled
        assert not manager.is_frame_onion_skinned("animation1", 0)
        
        # Re-enable global onion skinning
        manager.toggle_global_onion_skinning()
        assert manager.global_onion_skinning_enabled
        assert manager.is_frame_onion_skinned("animation1", 0)
    
    def test_set_transparency(self):
        """Test setting onion skinning transparency."""
        manager = OnionSkinningManager()
        
        # Test valid transparency values
        manager.set_transparency(0.3)
        assert manager.onion_transparency == 0.3
        
        manager.set_transparency(0.8)
        assert manager.onion_transparency == 0.8
        
        # Test clamping
        manager.set_transparency(1.5)
        assert manager.onion_transparency == 1.0
        
        manager.set_transparency(-0.5)
        assert manager.onion_transparency == 0.0
    
    def test_clear_animation_onion_skinning(self):
        """Test clearing onion skinning for an animation."""
        manager = OnionSkinningManager()
        
        # Enable onion skinning for multiple frames
        manager.toggle_frame_onion_skinning("animation1", 0)
        manager.toggle_frame_onion_skinning("animation1", 1)
        manager.toggle_frame_onion_skinning("animation2", 0)
        
        # Clear animation1
        manager.clear_animation_onion_skinning("animation1")
        
        assert not manager.is_frame_onion_skinned("animation1", 0)
        assert not manager.is_frame_onion_skinned("animation1", 1)
        assert manager.is_frame_onion_skinned("animation2", 0)  # animation2 should be unaffected
    
    def test_get_animation_onion_state(self):
        """Test getting onion skinning state for an animation."""
        manager = OnionSkinningManager()
        
        # Enable onion skinning for some frames
        manager.toggle_frame_onion_skinning("animation1", 0)
        manager.toggle_frame_onion_skinning("animation1", 2)
        
        state = manager.get_animation_onion_state("animation1")
        expected = {0: True, 2: True}
        assert state == expected
    
    def test_set_animation_onion_state(self):
        """Test setting onion skinning state for an animation."""
        manager = OnionSkinningManager()
        
        # Set state for animation1
        state = {0: True, 1: False, 2: True}
        manager.set_animation_onion_state("animation1", state)
        
        assert manager.is_frame_onion_skinned("animation1", 0)
        assert not manager.is_frame_onion_skinned("animation1", 1)
        assert manager.is_frame_onion_skinned("animation1", 2)


class TestOnionSkinningRenderer:
    """Test cases for onion skinning renderer."""
    
    def test_render_onion_skinning_frames_no_frames(self):
        """Test rendering when no onion skinning frames are enabled."""
        # Mock canvas sprite
        canvas_sprite = Mock()
        canvas_sprite.width = 64
        canvas_sprite.height = 64
        canvas_sprite.pixels_across = 8
        canvas_sprite.pixels_tall = 8
        canvas_sprite.pixel_width = 8
        canvas_sprite.pixel_height = 8
        canvas_sprite.image = Mock()
        
        # Mock frames
        frames = {
            "animation1": [
                Mock(get_pixel_data=lambda: [(255, 0, 0)] * 64),
                Mock(get_pixel_data=lambda: [(0, 255, 0)] * 64),
            ]
        }
        
        # Mock onion manager to return no onion frames
        with patch('glitchygames.tools.onion_skinning.get_onion_skinning_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.get_onion_skinned_frames.return_value = set()
            mock_get_manager.return_value = mock_manager
            
            # Should not raise any exceptions
            render_onion_skinning_frames(canvas_sprite, "animation1", 0, frames)
    
    def test_render_onion_skinning_frames_with_frames(self):
        """Test rendering when onion skinning frames are enabled."""
        # Mock canvas sprite
        canvas_sprite = Mock()
        canvas_sprite.width = 64
        canvas_sprite.height = 64
        canvas_sprite.pixels_across = 8
        canvas_sprite.pixels_tall = 8
        canvas_sprite.pixel_width = 8
        canvas_sprite.pixel_height = 8
        canvas_sprite.image = Mock()
        
        # Mock frames
        frames = {
            "animation1": [
                Mock(get_pixel_data=lambda: [(255, 0, 0)] * 64),
                Mock(get_pixel_data=lambda: [(0, 255, 0)] * 64),
            ]
        }
        
        # Mock onion manager to return onion frames
        with patch('glitchygames.tools.onion_skinning.get_onion_skinning_manager') as mock_get_manager:
            mock_manager = Mock()
            mock_manager.get_onion_skinned_frames.return_value = {1}  # Frame 1 should be onion skinned
            mock_manager.onion_transparency = 0.5
            mock_get_manager.return_value = mock_manager
            
            # Should not raise any exceptions
            render_onion_skinning_frames(canvas_sprite, "animation1", 0, frames)
            
            # Verify that blit was called on the canvas image
            canvas_sprite.image.blit.assert_called_once()


class TestOnionSkinningIntegration:
    """Integration tests for onion skinning functionality."""
    
    def test_global_manager_singleton(self):
        """Test that get_onion_skinning_manager returns a singleton."""
        manager1 = get_onion_skinning_manager()
        manager2 = get_onion_skinning_manager()
        
        assert manager1 is manager2
    
    def test_manager_state_persistence(self):
        """Test that manager state persists across calls."""
        manager = get_onion_skinning_manager()
        
        # Enable onion skinning for a frame
        manager.toggle_frame_onion_skinning("test_animation", 0)
        
        # Get manager again and check state
        manager2 = get_onion_skinning_manager()
        assert manager2.is_frame_onion_skinned("test_animation", 0)
    
    def test_error_handling(self):
        """Test error handling in onion skinning operations."""
        manager = OnionSkinningManager()
        
        # Test with invalid animation names
        assert not manager.is_frame_onion_skinned("nonexistent", 0)
        
        # Test with negative frame indices
        assert not manager.is_frame_onion_skinned("animation1", -1)
        
        # Test transparency clamping
        manager.set_transparency(2.0)
        assert manager.onion_transparency == 1.0
        
        manager.set_transparency(-1.0)
        assert manager.onion_transparency == 0.0


if __name__ == "__main__":
    pytest.main([__file__])
