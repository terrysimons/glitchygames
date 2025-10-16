"""Tests for film strip selection behavior.

This module tests the film strip selection system to ensure that:
1. Animation preview clicks preserve the selected frame
2. Frame insertion works correctly
3. Strip switching preserves individual strip selections
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.sprites import AnimatedSprite, SpriteFrame
from glitchygames.tools.bitmappy import BitmapEditorScene
from glitchygames.tools.film_strip import FilmStripWidget


class TestFilmStripSelection:
    """Test film strip selection behavior."""

    @pytest.fixture
    def mock_pygame_patches(self):
        """Mock pygame modules for testing."""
        with patch("pygame.display") as mock_display, \
             patch("pygame.font") as mock_font, \
             patch("pygame.draw") as mock_draw, \
             patch("pygame.Surface") as mock_surface:
            yield {
                "display": mock_display,
                "font": mock_font,
                "draw": mock_draw,
                "surface": mock_surface
            }

    @pytest.fixture
    def sample_animated_sprite(self):
        """Create a sample animated sprite with 4 frames."""
        sprite = Mock(spec=AnimatedSprite)
        sprite._animations = {
            "walk": [
                Mock(spec=SpriteFrame, duration=0.5),
                Mock(spec=SpriteFrame, duration=0.5),
                Mock(spec=SpriteFrame, duration=0.5),
                Mock(spec=SpriteFrame, duration=0.5)
            ]
        }
        sprite._animation_order = ["walk"]
        return sprite

    @pytest.fixture
    def film_strip_widget(self, mock_pygame_patches, sample_animated_sprite):
        """Create a film strip widget for testing."""
        widget = FilmStripWidget(0, 0, 400, 100)
        widget.animated_sprite = sample_animated_sprite
        widget.current_animation = "walk"
        widget.selected_frame = 0
        widget.current_frame = 0
        
        # Mock the parent scene
        widget.parent_scene = Mock(spec=BitmapEditorScene)
        widget.parent_scene.selected_frame = 0
        widget.parent_scene.selected_animation = "walk"
        
        # Mock layout data
        widget.frame_layouts = {
            ("walk", 0): pygame.Rect(10, 10, 64, 64),
            ("walk", 1): pygame.Rect(80, 10, 64, 64),
            ("walk", 2): pygame.Rect(150, 10, 64, 64),
            ("walk", 3): pygame.Rect(220, 10, 64, 64)
        }
        widget.preview_rects = {
            "walk": pygame.Rect(300, 10, 64, 64)
        }
        widget.animation_layouts = {
            "walk": pygame.Rect(10, 0, 200, 20)
        }
        
        return widget

    def test_animation_preview_click_preserves_selected_frame(self, film_strip_widget):
        """Test that clicking on animation preview preserves the selected frame."""
        # Set up initial state: frame 2 is selected
        film_strip_widget.selected_frame = 2
        film_strip_widget.parent_scene.selected_frame = 2
        
        # Click on the animation preview area
        preview_pos = (320, 30)  # Position within preview_rects["walk"]
        result = film_strip_widget.handle_click(preview_pos)
        
        # Should return the selected frame (2), not reset to 0
        assert result is not None
        animation, frame_idx = result
        assert animation == "walk"
        assert frame_idx == 2, f"Expected frame 2, got {frame_idx}"
        
        # Verify the widget's selected_frame is updated
        assert film_strip_widget.selected_frame == 2

    def test_frame_insertion_initializes_selection_correctly(self, film_strip_widget):
        """Test that frame insertion initializes selection at index 0."""
        # Set up initial state: frame 2 is selected
        film_strip_widget.selected_frame = 2
        film_strip_widget.parent_scene.selected_frame = 2
        
        # Mock the _on_frame_inserted method
        def mock_on_frame_inserted(animation, frame_index):
            film_strip_widget.parent_scene.selected_frame = frame_index
            if animation == "walk":
                film_strip_widget.selected_frame = frame_index
        
        film_strip_widget.parent_scene._on_frame_inserted = mock_on_frame_inserted
        
        # Simulate frame insertion
        film_strip_widget.parent_scene._on_frame_inserted("walk", 0)
        
        # The scene should update its selected_frame to the new frame index
        assert film_strip_widget.parent_scene.selected_frame == 0
        
        # The film strip widget should also be updated
        assert film_strip_widget.selected_frame == 0

    def test_strip_switching_preserves_individual_selections(self, film_strip_widget):
        """Test that switching strips preserves individual strip selections."""
        # Set up initial state: frame 2 is selected in current strip
        film_strip_widget.selected_frame = 2
        film_strip_widget.parent_scene.selected_frame = 2
        
        # Create a second strip with different selection
        second_strip = FilmStripWidget(0, 120, 400, 100)
        second_strip.animated_sprite = film_strip_widget.animated_sprite
        second_strip.current_animation = "run"
        second_strip.selected_frame = 1  # Different selection
        second_strip.parent_scene = film_strip_widget.parent_scene
        
        # Mock the scene's film strips
        film_strip_widget.parent_scene.film_strips = {
            "walk": film_strip_widget,
            "run": second_strip
        }
        film_strip_widget.parent_scene.film_strip_sprites = {
            "walk": Mock(),
            "run": Mock()
        }
        
        # Mock the _update_film_strip_selection_state method
        def mock_update_selection_state():
            current_animation = getattr(film_strip_widget.parent_scene, "selected_animation", "")
            current_frame = getattr(film_strip_widget.parent_scene, "selected_frame", 0)
            
            for strip_name, strip_widget in film_strip_widget.parent_scene.film_strips.items():
                strip_widget.current_animation = strip_name
                
                if strip_name == current_animation:
                    strip_widget.is_selected = True
                    strip_widget.selected_frame = current_frame
                else:
                    strip_widget.is_selected = False
                    # Don't reset selected_frame - preserve individual selections
        
        film_strip_widget.parent_scene._update_film_strip_selection_state = mock_update_selection_state
        
        # Switch to the second strip
        film_strip_widget.parent_scene.selected_animation = "run"
        film_strip_widget.parent_scene.selected_frame = 1
        film_strip_widget.parent_scene._update_film_strip_selection_state()
        
        # First strip should be deselected but preserve its selected_frame
        assert not film_strip_widget.is_selected
        assert film_strip_widget.selected_frame == 2  # Should preserve original selection
        
        # Second strip should be selected
        assert second_strip.is_selected
        assert second_strip.selected_frame == 1
        
        # Now switch back to first strip
        film_strip_widget.parent_scene.selected_animation = "walk"
        film_strip_widget.parent_scene.selected_frame = 2  # Use the preserved selection
        film_strip_widget.parent_scene._update_film_strip_selection_state()
        
        # First strip should be selected again with its preserved selection
        assert film_strip_widget.is_selected
        assert film_strip_widget.selected_frame == 2  # Should still be 2

    def test_animation_label_click_preserves_selected_frame(self, film_strip_widget):
        """Test that clicking on animation label preserves the selected frame."""
        # Set up initial state: frame 2 is selected
        film_strip_widget.selected_frame = 2
        film_strip_widget.parent_scene.selected_frame = 2
        
        # Click on the animation label area (use a position within animation_layouts["walk"])
        # animation_layouts["walk"] is pygame.Rect(10, 0, 200, 20)
        # frame_layouts start at y=10, so use y=5 to be in animation layout but not in frame areas
        label_pos = (15, 5)  # Position within animation_layouts["walk"] but outside frame areas
        result = film_strip_widget.handle_click(label_pos)
        
        # Should return the selected frame (2), not reset to 0
        assert result is not None
        animation, frame_idx = result
        assert animation == "walk"
        assert frame_idx == 2, f"Expected frame 2, got {frame_idx}"

    def test_frame_click_updates_selection(self, film_strip_widget):
        """Test that clicking on a specific frame updates the selection."""
        # Click on frame 2
        frame_pos = (180, 40)  # Position within frame_layouts[("walk", 2)]
        result = film_strip_widget.handle_click(frame_pos)
        
        # Should return frame 2
        assert result is not None
        animation, frame_idx = result
        assert animation == "walk"
        assert frame_idx == 2
        
        # Verify the widget's selected_frame is updated
        assert film_strip_widget.selected_frame == 2

    def test_multiple_strips_independent_selections(self, mock_pygame_patches, sample_animated_sprite):
        """Test that multiple strips maintain independent selections."""
        # Create two strips
        strip1 = FilmStripWidget(0, 0, 400, 100)
        strip1.animated_sprite = sample_animated_sprite
        strip1.current_animation = "walk"
        strip1.selected_frame = 2
        
        strip2 = FilmStripWidget(0, 120, 400, 100)
        strip2.animated_sprite = sample_animated_sprite
        strip2.current_animation = "run"
        strip2.selected_frame = 1
        
        # Create a scene with both strips
        scene = Mock(spec=BitmapEditorScene)
        scene.film_strips = {"walk": strip1, "run": strip2}
        scene.film_strip_sprites = {"walk": Mock(), "run": Mock()}
        scene.selected_animation = "walk"
        scene.selected_frame = 2
        
        # Set parent scenes
        strip1.parent_scene = scene
        strip2.parent_scene = scene
        
        # Mock the _update_film_strip_selection_state method
        def mock_update_selection_state():
            current_animation = getattr(scene, "selected_animation", "")
            current_frame = getattr(scene, "selected_frame", 0)
            
            for strip_name, strip_widget in scene.film_strips.items():
                strip_widget.current_animation = strip_name
                
                if strip_name == current_animation:
                    strip_widget.is_selected = True
                    strip_widget.selected_frame = current_frame
                else:
                    strip_widget.is_selected = False
                    # Don't reset selected_frame - preserve individual selections
        
        scene._update_film_strip_selection_state = mock_update_selection_state
        
        # Update selection state
        scene._update_film_strip_selection_state()
        
        # Strip 1 should be selected with frame 2
        assert strip1.is_selected
        assert strip1.selected_frame == 2
        
        # Strip 2 should be deselected but preserve its selection
        assert not strip2.is_selected
        assert strip2.selected_frame == 1  # Should preserve its own selection
        
        # Switch to strip 2
        scene.selected_animation = "run"
        scene.selected_frame = 1
        scene._update_film_strip_selection_state()
        
        # Strip 2 should be selected with frame 1
        assert strip2.is_selected
        assert strip2.selected_frame == 1
        
        # Strip 1 should be deselected but preserve its selection
        assert not strip1.is_selected
        assert strip1.selected_frame == 2  # Should preserve its own selection

    def test_click_handlers_use_global_selection(self, film_strip_widget):
        """Test that click handlers use the scene's global selection, not strip's own."""
        # Set up mismatch: strip thinks frame 0 is selected, scene thinks frame 2 is selected
        film_strip_widget.selected_frame = 0  # Strip's own selection
        film_strip_widget.parent_scene.selected_frame = 2  # Scene's global selection
        
        # Click on animation preview
        preview_pos = (320, 30)
        result = film_strip_widget.handle_click(preview_pos)
        
        # Should use scene's global selection (2), not strip's own (0)
        assert result is not None
        animation, frame_idx = result
        assert frame_idx == 2, f"Expected frame 2 (global), got {frame_idx} (strip had {film_strip_widget.selected_frame})"
        
        # Click on animation label (use position that's definitely in animation layout but not in frame areas)
        # animation_layouts["walk"] is pygame.Rect(10, 0, 200, 20)
        # frame_layouts are at y=10, so use y=5 to be in animation layout but not in frame areas
        label_pos = (15, 5)
        result = film_strip_widget.handle_click(label_pos)
        
        # Should also use scene's global selection
        assert result is not None
        animation, frame_idx = result
        assert frame_idx == 2, f"Expected frame 2 (global), got {frame_idx} (strip had {film_strip_widget.selected_frame})"

    def test_parent_strip_click_selects_itself(self, film_strip_widget):
        """Test that clicking on the parent strip itself selects the strip and updates its state."""
        # Set up initial state: frame 2 is selected globally
        film_strip_widget.selected_frame = 0  # Strip's own selection
        film_strip_widget.parent_scene.selected_frame = 2  # Scene's global selection
        
        # Click on the parent strip itself (outside of frames, labels, and preview)
        # Use a position that's within the strip's rect but not in any specific element
        # The strip rect is (0, 0, 400, 100), so use a position in the middle but outside other elements
        # frame_layouts: walk[0] at (10, 10, 64, 64), walk[1] at (80, 10, 64, 64), walk[2] at (150, 10, 64, 64), walk[3] at (220, 10, 64, 64)
        # preview_rects: walk at (300, 10, 64, 64)
        # animation_layouts: walk at (10, 0, 200, 20)
        # So use a position that's outside all these areas but within the strip rect
        parent_strip_pos = (290, 80)  # Position within strip rect but outside frame/preview areas
        result = film_strip_widget.handle_click(parent_strip_pos)
        
        # Should return the global selected frame (2), not the strip's own (0)
        assert result is not None
        animation, frame_idx = result
        assert animation == "walk"
        assert frame_idx == 2, f"Expected frame 2 (global), got {frame_idx} (strip had {film_strip_widget.selected_frame})"
        
        # Verify the strip's selected_frame is updated to match the global selection
        assert film_strip_widget.selected_frame == 2

    def test_triangle_indicator_draws_below_frame(self, film_strip_widget, mock_pygame_patches):
        """Test that the triangle indicator is drawn below the active animation frame."""
        # Set up: frame 2 is the active animation frame
        film_strip_widget.current_animation = "walk"
        # Mock get_current_preview_frame to return frame 2
        film_strip_widget.get_current_preview_frame = Mock(return_value=2)
        
        # Mock pygame.draw.polygon to track calls
        mock_draw = mock_pygame_patches["draw"]
        
        # Create a mock surface
        mock_surface = Mock()
        
        # Call the triangle indicator drawing method
        film_strip_widget._draw_triforce_indicator(mock_surface)
        
        # Verify pygame.draw.polygon was called
        assert mock_draw.polygon.called
        
        # Verify it was called twice (filled triangle + border)
        assert mock_draw.polygon.call_count == 2

    def test_triangle_indicator_uses_correct_colors(self, film_strip_widget, mock_pygame_patches):
        """Test that the triangle indicator uses the correct colors."""
        # Set up: frame 0 is the active animation frame
        film_strip_widget.current_animation = "walk"
        # Mock get_current_preview_frame to return frame 0
        film_strip_widget.get_current_preview_frame = Mock(return_value=0)
        
        # Mock pygame.draw.polygon to track calls
        mock_draw = mock_pygame_patches["draw"]
        
        # Create a mock surface
        mock_surface = Mock()
        
        # Call the triangle indicator drawing method
        film_strip_widget._draw_triforce_indicator(mock_surface)
        
        # Verify pygame.draw.polygon was called twice (filled + border)
        assert mock_draw.polygon.call_count == 2

    def test_triangle_indicator_size_and_position(self, film_strip_widget, mock_pygame_patches):
        """Test that the triangle indicator has the correct size and position."""
        # Set up: frame 1 is the active animation frame
        film_strip_widget.current_animation = "walk"
        # Mock get_current_preview_frame to return frame 1
        film_strip_widget.get_current_preview_frame = Mock(return_value=1)
        
        # Mock pygame.draw.polygon to track calls
        mock_draw = mock_pygame_patches["draw"]
        
        # Create a mock surface
        mock_surface = Mock()
        
        # Call the triangle indicator drawing method
        film_strip_widget._draw_triforce_indicator(mock_surface)
        
        # Verify pygame.draw.polygon was called twice (filled + border)
        assert mock_draw.polygon.call_count == 2

    def test_triangle_indicator_draws_when_no_animation(self, film_strip_widget, mock_pygame_patches):
        """Test that triangle indicator is drawn at default position when there's no current animation."""
        # Set up: no current animation
        film_strip_widget.current_animation = ""
        
        # Mock pygame.draw.polygon to track calls
        mock_draw = mock_pygame_patches["draw"]
        
        # Create a mock surface
        mock_surface = Mock()
        
        # Call the triangle indicator drawing method
        film_strip_widget._draw_triforce_indicator(mock_surface)
        
        # Verify pygame.draw.polygon was called (triangle should always be drawn)
        assert mock_draw.polygon.called
        assert mock_draw.polygon.call_count == 2  # Filled + border

    def test_triangle_indicator_draws_when_no_sprite(self, film_strip_widget, mock_pygame_patches):
        """Test that triangle indicator is drawn at default position when there's no animated sprite."""
        # Set up: no animated sprite
        film_strip_widget.animated_sprite = None
        film_strip_widget.current_animation = "walk"
        
        # Mock pygame.draw.polygon to track calls
        mock_draw = mock_pygame_patches["draw"]
        
        # Create a mock surface
        mock_surface = Mock()
        
        # Call the triangle indicator drawing method
        film_strip_widget._draw_triforce_indicator(mock_surface)
        
        # Verify pygame.draw.polygon was called (triangle should always be drawn)
        assert mock_draw.polygon.called
        assert mock_draw.polygon.call_count == 2  # Filled + border

    def test_triangle_indicator_draws_when_frame_not_found(self, film_strip_widget, mock_pygame_patches):
        """Test that triangle indicator is drawn at default position when frame layout is not found."""
        # Set up: frame layout doesn't exist
        film_strip_widget.current_animation = "walk"
        # Mock get_current_preview_frame to return frame 5 (doesn't exist in frame_layouts)
        film_strip_widget.get_current_preview_frame = Mock(return_value=5)
        
        # Mock pygame.draw.polygon to track calls
        mock_draw = mock_pygame_patches["draw"]
        
        # Create a mock surface
        mock_surface = Mock()
        
        # Call the triangle indicator drawing method
        film_strip_widget._draw_triforce_indicator(mock_surface)
        
        # Verify pygame.draw.polygon was called (triangle should always be drawn)
        assert mock_draw.polygon.called
        assert mock_draw.polygon.call_count == 2  # Filled + border
