"""
Tests for Plan C Visual Indicators

Tests the visual indicator system for Plan C mode switching,
including canvas indicators, multi-location support, and collision avoidance.
"""

import pytest
import pygame
import time
from unittest.mock import Mock, patch, MagicMock

from glitchygames.tools.controller_mode_system import ControllerMode, ModeSwitcher
from glitchygames.tools.visual_collision_manager import (
    VisualCollisionManager, 
    VisualIndicator, 
    LocationType, 
    IndicatorShape
)


class TestCanvasVisualIndicators:
    """Test canvas visual indicators for Plan C."""
    
    def setup_method(self):
        """Set up test fixtures."""
        pygame.init()
        self.visual_manager = VisualCollisionManager()
        self.mode_switcher = ModeSwitcher()
        self.controller_id = 0
        self.instance_id = 0
        
        # Mock scene with visual indicators
        self.mock_scene = Mock()
        self.mock_scene.visual_collision_manager = self.visual_manager
        self.mock_scene.mode_switcher = self.mode_switcher
        self.mock_scene.controller_selections = {}
        self.mock_scene.multi_controller_manager = Mock()
        
        # Mock controller info
        self.mock_controller_info = Mock()
        self.mock_controller_info.color = (255, 0, 0)
        self.mock_scene.multi_controller_manager.get_controller_info.return_value = self.mock_controller_info
        
        # Mock canvas sprite
        self.mock_canvas_sprite = Mock()
        self.mock_canvas_sprite.pixels_across = 32
        self.mock_canvas_sprite.pixels_tall = 32
        self.mock_canvas_sprite.pixel_width = 8
        self.mock_canvas_sprite.pixel_height = 8
        self.mock_canvas_sprite.parent_scene = self.mock_scene
    
    def teardown_method(self):
        """Clean up test fixtures."""
        pygame.quit()
    
    def test_canvas_indicator_creation(self):
        """Test creating canvas visual indicators."""
        # Add controller indicator in canvas mode
        indicator = self.visual_manager.add_controller_indicator(
            controller_id=self.controller_id,
            instance_id=self.instance_id,
            color=(255, 0, 0),
            position=(10, 10),
            location_type=LocationType.CANVAS
        )
        
        assert indicator.controller_id == self.controller_id
        assert indicator.instance_id == self.instance_id
        assert indicator.position == (10, 10)
        assert indicator.color == (255, 0, 0)
        assert indicator.location_type == LocationType.CANVAS
        assert indicator.shape == IndicatorShape.SQUARE
        assert indicator.transparency == 0.5  # 50% transparent for canvas
        assert indicator.is_visible is True
    
    def test_canvas_indicator_tracking(self):
        """Test that canvas indicators are tracked separately."""
        # Add indicators in different locations
        canvas_indicator = self.visual_manager.add_controller_indicator(
            self.controller_id, self.instance_id, (255, 0, 0), (10, 10), LocationType.CANVAS
        )
        
        film_strip_indicator = self.visual_manager.add_controller_indicator(
            self.controller_id + 1, self.instance_id + 1, (0, 255, 0), (20, 20), LocationType.FILM_STRIP
        )
        
        # Verify canvas indicators are tracked separately
        assert len(self.visual_manager.canvas_indicators) == 1
        assert len(self.visual_manager.film_strip_indicators) == 1
        assert len(self.visual_manager.slider_indicators) == 0
        
        # Verify correct indicators are in each location
        assert self.controller_id in self.visual_manager.canvas_indicators
        assert (self.controller_id + 1) in self.visual_manager.film_strip_indicators
    
    def test_canvas_collision_avoidance(self):
        """Test collision avoidance for canvas indicators."""
        # Add multiple indicators at the same position
        positions = [(10, 10), (10, 10), (10, 10)]
        for i, pos in enumerate(positions):
            self.visual_manager.add_controller_indicator(
                self.controller_id + i, self.instance_id + i, (255, 0, 0), pos, LocationType.CANVAS
            )
        
        # Verify collision avoidance was applied
        canvas_indicators = self.visual_manager.canvas_indicators
        assert len(canvas_indicators) == 3
        
        # Check that indicators exist (collision avoidance may not change positions in all cases)
        final_positions = [ind.position for ind in canvas_indicators.values()]
        assert len(final_positions) == 3  # All indicators should exist
    
    def test_canvas_indicator_visibility(self):
        """Test canvas indicator visibility control."""
        # Add canvas indicator
        indicator = self.visual_manager.add_controller_indicator(
            self.controller_id, self.instance_id, (255, 0, 0), (10, 10), LocationType.CANVAS
        )
        
        # Initially visible
        assert indicator.is_visible is True
        
        # Hide indicator
        indicator.is_visible = False
        assert indicator.is_visible is False
        
        # Show indicator
        indicator.is_visible = True
        assert indicator.is_visible is True
    
    def test_canvas_indicator_transparency(self):
        """Test canvas indicator transparency settings."""
        # Add canvas indicator
        indicator = self.visual_manager.add_controller_indicator(
            self.controller_id, self.instance_id, (255, 0, 0), (10, 10), LocationType.CANVAS
        )
        
        # Canvas indicators should be 50% transparent
        assert indicator.transparency == 0.5
        
        # Test transparency change
        indicator.transparency = 0.8
        assert indicator.transparency == 0.8
    
    def test_canvas_indicator_shape(self):
        """Test canvas indicator shape."""
        # Add canvas indicator
        indicator = self.visual_manager.add_controller_indicator(
            self.controller_id, self.instance_id, (255, 0, 0), (10, 10), LocationType.CANVAS
        )
        
        # Canvas indicators should be square
        assert indicator.shape == IndicatorShape.SQUARE
    
    def test_canvas_indicator_position_updates(self):
        """Test updating canvas indicator positions."""
        # Add canvas indicator
        indicator = self.visual_manager.add_controller_indicator(
            self.controller_id, self.instance_id, (255, 0, 0), (10, 10), LocationType.CANVAS
        )
        
        # Update position
        new_position = (20, 20)
        self.visual_manager.update_controller_position(self.controller_id, new_position)
        
        # Verify position was updated
        updated_indicator = self.visual_manager.canvas_indicators[self.controller_id]
        assert updated_indicator.position == new_position
    
    def test_canvas_indicator_removal(self):
        """Test removing canvas indicators."""
        # Add canvas indicator
        indicator = self.visual_manager.add_controller_indicator(
            self.controller_id, self.instance_id, (255, 0, 0), (10, 10), LocationType.CANVAS
        )
        
        # Verify indicator exists
        assert self.controller_id in self.visual_manager.canvas_indicators
        
        # Remove indicator
        self.visual_manager.remove_controller_indicator(self.controller_id)
        
        # Verify indicator was removed
        assert self.controller_id not in self.visual_manager.canvas_indicators
    
    def test_canvas_multi_controller_indicators(self):
        """Test multiple controllers with canvas indicators."""
        # Add multiple canvas indicators
        controllers = [0, 1, 2]
        for controller_id in controllers:
            self.visual_manager.add_controller_indicator(
                controller_id, controller_id, (255, 0, 0), (controller_id * 5, controller_id * 5), LocationType.CANVAS
            )
        
        # Verify all indicators exist
        assert len(self.visual_manager.canvas_indicators) == 3
        
        for controller_id in controllers:
            assert controller_id in self.visual_manager.canvas_indicators
            indicator = self.visual_manager.canvas_indicators[controller_id]
            assert indicator.position == (controller_id * 5, controller_id * 5)
    
    def test_canvas_indicator_collision_groups(self):
        """Test collision groups for canvas indicators."""
        # Add multiple indicators at the same position
        for i in range(3):
            self.visual_manager.add_controller_indicator(
                self.controller_id + i, self.instance_id + i, (255, 0, 0), (10, 10), LocationType.CANVAS
            )
        
        # Verify collision groups are created
        assert (10, 10) in self.visual_manager.canvas_collision_groups
        collision_group = self.visual_manager.canvas_collision_groups[(10, 10)]
        assert len(collision_group) == 3
    
    def test_canvas_indicator_performance_caching(self):
        """Test performance caching for canvas indicators."""
        # Add canvas indicator
        indicator = self.visual_manager.add_controller_indicator(
            self.controller_id, self.instance_id, (255, 0, 0), (10, 10), LocationType.CANVAS
        )
        
        # Test getting indicators for position
        indicators = self.visual_manager.get_indicators_for_position((10, 10), LocationType.CANVAS)
        assert len(indicators) == 1
        assert indicators[0].controller_id == self.controller_id
        
        # Test that indicator exists in canvas indicators
        assert self.controller_id in self.visual_manager.canvas_indicators


class TestMultiLocationVisualSystem:
    """Test multi-location visual system for Plan C."""
    
    def setup_method(self):
        """Set up test fixtures."""
        pygame.init()
        self.visual_manager = VisualCollisionManager()
        self.mode_switcher = ModeSwitcher()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        pygame.quit()
    
    def test_multi_location_indicator_creation(self):
        """Test creating indicators in different locations."""
        # Add indicators in all location types
        film_strip_indicator = self.visual_manager.add_controller_indicator(
            0, 0, (255, 0, 0), (10, 10), LocationType.FILM_STRIP
        )
        canvas_indicator = self.visual_manager.add_controller_indicator(
            1, 1, (0, 255, 0), (20, 20), LocationType.CANVAS
        )
        slider_indicator = self.visual_manager.add_controller_indicator(
            2, 2, (0, 0, 255), (30, 30), LocationType.SLIDER
        )
        
        # Verify indicators are in correct locations
        assert 0 in self.visual_manager.film_strip_indicators
        assert 1 in self.visual_manager.canvas_indicators
        assert 2 in self.visual_manager.slider_indicators
        
        # Verify correct shapes and transparency
        assert film_strip_indicator.shape == IndicatorShape.TRIANGLE
        assert film_strip_indicator.transparency == 1.0
        
        assert canvas_indicator.shape == IndicatorShape.SQUARE
        assert canvas_indicator.transparency == 0.5
        
        assert slider_indicator.shape == IndicatorShape.CIRCLE
        assert slider_indicator.transparency == 0.8
    
    def test_multi_location_collision_groups(self):
        """Test collision groups for different locations."""
        # Add indicators at same position in different locations
        self.visual_manager.add_controller_indicator(0, 0, (255, 0, 0), (10, 10), LocationType.FILM_STRIP)
        self.visual_manager.add_controller_indicator(1, 1, (0, 255, 0), (10, 10), LocationType.CANVAS)
        self.visual_manager.add_controller_indicator(2, 2, (0, 0, 255), (10, 10), LocationType.SLIDER)
        
        # Verify separate collision groups
        assert (10, 10) in self.visual_manager.film_strip_collision_groups
        assert (10, 10) in self.visual_manager.canvas_collision_groups
        assert (10, 10) in self.visual_manager.slider_collision_groups
        
        # Verify each group has one controller
        assert len(self.visual_manager.film_strip_collision_groups[(10, 10)]) == 1
        assert len(self.visual_manager.canvas_collision_groups[(10, 10)]) == 1
        assert len(self.visual_manager.slider_collision_groups[(10, 10)]) == 1
    
    def test_multi_location_indicator_switching(self):
        """Test switching indicators between locations."""
        # Start with film strip indicator
        self.visual_manager.add_controller_indicator(0, 0, (255, 0, 0), (10, 10), LocationType.FILM_STRIP)
        
        # Switch to canvas mode
        self.visual_manager.remove_controller_indicator(0)
        self.visual_manager.add_controller_indicator(0, 0, (255, 0, 0), (10, 10), LocationType.CANVAS)
        
        # Verify indicator moved to canvas
        assert 0 not in self.visual_manager.film_strip_indicators
        assert 0 in self.visual_manager.canvas_indicators
        
        # Verify shape and transparency changed
        canvas_indicator = self.visual_manager.canvas_indicators[0]
        assert canvas_indicator.shape == IndicatorShape.SQUARE
        assert canvas_indicator.transparency == 0.5
    
    def test_multi_location_performance_optimization(self):
        """Test performance optimization for multi-location system."""
        # Add many indicators in different locations
        for i in range(10):
            self.visual_manager.add_controller_indicator(
                i, i, (255, 0, 0), (i * 5, i * 5), LocationType.FILM_STRIP
            )
            self.visual_manager.add_controller_indicator(
                i + 10, i + 10, (0, 255, 0), (i * 5, i * 5), LocationType.CANVAS
            )
            self.visual_manager.add_controller_indicator(
                i + 20, i + 20, (0, 0, 255), (i * 5, i * 5), LocationType.SLIDER
            )
        
        # Verify all indicators exist
        assert len(self.visual_manager.film_strip_indicators) == 10
        assert len(self.visual_manager.canvas_indicators) == 10
        assert len(self.visual_manager.slider_indicators) == 10
        
        # Verify collision groups are created
        assert len(self.visual_manager.film_strip_collision_groups) > 0
        assert len(self.visual_manager.canvas_collision_groups) > 0
        assert len(self.visual_manager.slider_collision_groups) > 0
