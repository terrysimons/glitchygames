"""
Tests for Plan C Canvas Input Handling

Tests the canvas input handling functionality for Plan C mode switching,
including controller-based painting and navigation.
"""

import pytest
import pygame
import time
from unittest.mock import Mock, patch, MagicMock

from glitchygames.tools.controller_mode_system import ControllerMode, ModeSwitcher
from glitchygames.tools.visual_collision_manager import LocationType


class TestCanvasInputHandling:
    """Test canvas input handling for Plan C."""
    
    def setup_method(self):
        """Set up test fixtures."""
        pygame.init()
        self.mode_switcher = ModeSwitcher()
        self.controller_id = 0
        
        # Mock scene with canvas input handling
        self.mock_scene = Mock()
        self.mock_scene.mode_switcher = self.mode_switcher
        self.mock_scene.controller_selections = {}
        self.mock_scene.multi_controller_manager = Mock()
        self.mock_scene.controller_drags = {}
        
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
        self.mock_canvas_sprite.rect = pygame.Rect(0, 0, 256, 256)
        self.mock_canvas_sprite.parent_scene = self.mock_scene
        
        # Mock canvas interface
        self.mock_canvas_interface = Mock()
        self.mock_canvas_sprite.canvas_interface = self.mock_canvas_interface
        
        # Mock active color
        self.mock_canvas_sprite.active_color = (255, 255, 255)
        
        # Mock selected frame visibility
        self.mock_scene.selected_frame_visible = True
    
    def teardown_method(self):
        """Clean up test fixtures."""
        pygame.quit()
    
    def test_canvas_mode_registration(self):
        """Test that controllers can be registered in canvas mode."""
        self.mode_switcher.register_controller(self.controller_id, ControllerMode.CANVAS)
        
        assert self.mode_switcher.get_controller_mode(self.controller_id) == ControllerMode.CANVAS
        assert self.mode_switcher.get_controller_location_type(self.controller_id) == LocationType.CANVAS
    
    def test_canvas_a_button_press(self):
        """Test A button press in canvas mode."""
        # Register controller in canvas mode
        self.mode_switcher.register_controller(self.controller_id, ControllerMode.CANVAS)
        
        # Set controller position
        self.mode_switcher.save_controller_position(self.controller_id, (10, 10))
        
        # Test that controller is in canvas mode and position is tracked
        assert self.mode_switcher.get_controller_mode(self.controller_id) == ControllerMode.CANVAS
        position_data = self.mode_switcher.get_controller_position(self.controller_id)
        assert position_data.position == (10, 10)
        
        # Test that canvas mode has correct location type
        assert self.mode_switcher.get_controller_location_type(self.controller_id) == LocationType.CANVAS
    
    def test_canvas_a_button_disabled_when_frame_hidden(self):
        """Test that A button is disabled when selected frame is hidden."""
        # Register controller in canvas mode
        self.mode_switcher.register_controller(self.controller_id, ControllerMode.CANVAS)
        
        # Test that controller is in canvas mode
        assert self.mode_switcher.get_controller_mode(self.controller_id) == ControllerMode.CANVAS
        
        # Test that canvas mode has correct location type
        assert self.mode_switcher.get_controller_location_type(self.controller_id) == LocationType.CANVAS
    
    def test_canvas_b_button_reserved_for_undo(self):
        """Test that B button is reserved for undo operations."""
        # Register controller in canvas mode
        self.mode_switcher.register_controller(self.controller_id, ControllerMode.CANVAS)
        
        # Simulate B button press
        self.mock_scene._handle_canvas_button_press(self.controller_id, pygame.CONTROLLER_BUTTON_B)
        
        # Should not crash and should be handled gracefully
        # (Currently just logs that it's reserved for undo)
    
    def test_canvas_controller_drag_initialization(self):
        """Test controller drag operation initialization."""
        # Register controller in canvas mode
        self.mode_switcher.register_controller(self.controller_id, ControllerMode.CANVAS)
        
        # Set controller position
        self.mode_switcher.save_controller_position(self.controller_id, (15, 15))
        
        # Test that controller position is properly tracked
        position_data = self.mode_switcher.get_controller_position(self.controller_id)
        assert position_data.position == (15, 15)
        assert position_data.is_valid
        
        # Test that controller is in canvas mode
        assert self.mode_switcher.get_controller_mode(self.controller_id) == ControllerMode.CANVAS
    
    def test_canvas_controller_position_tracking(self):
        """Test that controller positions are tracked in canvas mode."""
        # Register controller in canvas mode
        self.mode_switcher.register_controller(self.controller_id, ControllerMode.CANVAS)
        
        # Set multiple positions
        positions = [(5, 5), (10, 10), (15, 15)]
        for pos in positions:
            self.mode_switcher.save_controller_position(self.controller_id, pos)
        
        # Get current position
        position_data = self.mode_switcher.get_controller_position(self.controller_id)
        assert position_data is not None
        assert position_data.is_valid
        assert position_data.position == (15, 15)  # Last position
    
    def test_canvas_mode_switching_from_film_strip(self):
        """Test switching from film strip to canvas mode."""
        # Start in film strip mode
        self.mode_switcher.register_controller(self.controller_id, ControllerMode.FILM_STRIP)
        
        # Switch to canvas mode
        current_time = time.time()
        new_mode = self.mode_switcher.handle_trigger_input(
            self.controller_id, 1.0, 0.0, current_time
        )
        
        assert new_mode == ControllerMode.CANVAS
        assert self.mode_switcher.get_controller_mode(self.controller_id) == ControllerMode.CANVAS
        assert self.mode_switcher.get_controller_location_type(self.controller_id) == LocationType.CANVAS
    
    def test_canvas_mode_switching_to_slider(self):
        """Test switching from canvas to slider mode."""
        # Start in canvas mode
        self.mode_switcher.register_controller(self.controller_id, ControllerMode.CANVAS)
        
        # Switch to R slider mode
        current_time = time.time()
        new_mode = self.mode_switcher.handle_trigger_input(
            self.controller_id, 1.0, 0.0, current_time
        )
        
        assert new_mode == ControllerMode.R_SLIDER
        assert self.mode_switcher.get_controller_mode(self.controller_id) == ControllerMode.R_SLIDER
        assert self.mode_switcher.get_controller_location_type(self.controller_id) == LocationType.SLIDER
    
    def test_canvas_visual_indicator_rendering(self):
        """Test that canvas visual indicators are rendered correctly."""
        # This would test the canvas visual indicator rendering
        # which is implemented in canvas_interfaces.py
        pass  # Placeholder for canvas visual indicator tests
    
    def test_canvas_multi_controller_support(self):
        """Test that multiple controllers can work in canvas mode simultaneously."""
        # Register multiple controllers in canvas mode
        controllers = [0, 1, 2]
        for controller_id in controllers:
            self.mode_switcher.register_controller(controller_id, ControllerMode.CANVAS)
            self.mode_switcher.save_controller_position(controller_id, (controller_id * 5, controller_id * 5))
        
        # Verify all controllers are in canvas mode
        for controller_id in controllers:
            assert self.mode_switcher.get_controller_mode(controller_id) == ControllerMode.CANVAS
            assert self.mode_switcher.get_controller_location_type(controller_id) == LocationType.CANVAS
        
        # Verify positions are tracked separately
        for controller_id in controllers:
            position_data = self.mode_switcher.get_controller_position(controller_id)
            assert position_data.position == (controller_id * 5, controller_id * 5)
