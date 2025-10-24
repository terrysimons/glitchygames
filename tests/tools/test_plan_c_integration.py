"""
Integration tests for Plan C: Collaborative Multi-Controller Editing System.

This module tests the complete Plan C workflow including:
- Multi-location visual indicators (film strip, canvas, sliders)
- Mode switching between locations
- Canvas input mapping and painting
- Controller collaboration scenarios
"""

import pytest
import time
from unittest.mock import Mock, patch

from glitchygames.tools.controller_mode_system import (
    ControllerMode, ModeSwitcher, TriggerDetector
)
from glitchygames.tools.visual_collision_manager import (
    VisualCollisionManager, LocationType, IndicatorShape
)
from glitchygames.tools.multi_controller_manager import MultiControllerManager
from glitchygames.tools.controller_selection import ControllerSelection


class TestPlanCIntegration:
    """Integration tests for Plan C collaborative editing system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mode_switcher = ModeSwitcher()
        self.visual_manager = VisualCollisionManager()
        self.multi_controller_manager = MultiControllerManager()
        
        # Mock pygame for testing
        self.mock_pygame = Mock()
        self.mock_pygame.CONTROLLER_AXIS_TRIGGERLEFT = 4
        self.mock_pygame.CONTROLLER_AXIS_TRIGGERRIGHT = 5
        self.mock_pygame.CONTROLLER_BUTTON_A = 0
        self.mock_pygame.CONTROLLER_BUTTON_B = 1
        self.mock_pygame.CONTROLLER_BUTTON_DPAD_LEFT = 11
        self.mock_pygame.CONTROLLER_BUTTON_DPAD_RIGHT = 12
        self.mock_pygame.CONTROLLER_BUTTON_DPAD_UP = 13
        self.mock_pygame.CONTROLLER_BUTTON_DPAD_DOWN = 14
        self.mock_pygame.CONTROLLER_BUTTON_LEFTSHOULDER = 4
        self.mock_pygame.CONTROLLER_BUTTON_RIGHTSHOULDER = 5
    
    def test_multi_controller_collaboration_workflow(self):
        """Test complete multi-controller collaboration workflow."""
        # Register two controllers
        controller1_id = 0
        controller2_id = 1
        
        self.mode_switcher.register_controller(controller1_id, ControllerMode.FILM_STRIP)
        self.mode_switcher.register_controller(controller2_id, ControllerMode.CANVAS)
        
        # Controller 1: Film strip mode
        film_indicator = self.visual_manager.add_controller_indicator(
            controller1_id, 0, (255, 0, 0), (10, 10), LocationType.FILM_STRIP
        )
        assert film_indicator.shape == IndicatorShape.TRIANGLE
        assert film_indicator.transparency == 1.0
        assert film_indicator.location_type == LocationType.FILM_STRIP
        
        # Controller 2: Canvas mode
        canvas_indicator = self.visual_manager.add_controller_indicator(
            controller2_id, 1, (0, 255, 0), (50, 50), LocationType.CANVAS
        )
        assert canvas_indicator.shape == IndicatorShape.SQUARE
        assert canvas_indicator.transparency == 0.5
        assert canvas_indicator.location_type == LocationType.CANVAS
        
        # Verify both indicators exist
        film_indicators = self.visual_manager.get_indicators_by_location(LocationType.FILM_STRIP)
        canvas_indicators = self.visual_manager.get_indicators_by_location(LocationType.CANVAS)
        
        assert controller1_id in film_indicators
        assert controller2_id in canvas_indicators
        assert len(film_indicators) == 1
        assert len(canvas_indicators) == 1
    
    def test_mode_switching_with_visual_updates(self):
        """Test mode switching with proper visual indicator updates."""
        controller_id = 0
        current_time = time.time()
        
        # Start in film strip mode
        self.mode_switcher.register_controller(controller_id, ControllerMode.FILM_STRIP)
        
        # Add film strip indicator
        film_indicator = self.visual_manager.add_controller_indicator(
            controller_id, 0, (255, 0, 0), (10, 10), LocationType.FILM_STRIP
        )
        
        # Switch to canvas mode
        new_mode = self.mode_switcher.handle_trigger_input(
            controller_id, 0.0, 1.0, current_time
        )
        assert new_mode == ControllerMode.CANVAS
        
        # Remove old indicator and add new one
        self.visual_manager.remove_controller_indicator(controller_id)
        canvas_indicator = self.visual_manager.add_controller_indicator(
            controller_id, 0, (255, 0, 0), (50, 50), LocationType.CANVAS
        )
        
        # Verify canvas indicator properties
        assert canvas_indicator.shape == IndicatorShape.SQUARE
        assert canvas_indicator.transparency == 0.5
        assert canvas_indicator.location_type == LocationType.CANVAS
        
        # Verify film strip indicator is gone
        film_indicators = self.visual_manager.get_indicators_by_location(LocationType.FILM_STRIP)
        canvas_indicators = self.visual_manager.get_indicators_by_location(LocationType.CANVAS)
        
        assert controller_id not in film_indicators
        assert controller_id in canvas_indicators
    
    def test_canvas_painting_collaboration(self):
        """Test multiple controllers painting on canvas simultaneously."""
        controller1_id = 0
        controller2_id = 1
        
        # Both controllers in canvas mode
        self.mode_switcher.register_controller(controller1_id, ControllerMode.CANVAS)
        self.mode_switcher.register_controller(controller2_id, ControllerMode.CANVAS)
        
        # Add canvas indicators for both controllers
        indicator1 = self.visual_manager.add_controller_indicator(
            controller1_id, 0, (255, 0, 0), (10, 10), LocationType.CANVAS
        )
        indicator2 = self.visual_manager.add_controller_indicator(
            controller2_id, 1, (0, 255, 0), (20, 20), LocationType.CANVAS
        )
        
        # Verify both indicators are canvas indicators
        assert indicator1.shape == IndicatorShape.SQUARE
        assert indicator1.transparency == 0.5
        assert indicator2.shape == IndicatorShape.SQUARE
        assert indicator2.transparency == 0.5
        
        # Verify both controllers can paint simultaneously
        canvas_indicators = self.visual_manager.get_indicators_by_location(LocationType.CANVAS)
        assert len(canvas_indicators) == 2
        assert controller1_id in canvas_indicators
        assert controller2_id in canvas_indicators
    
    def test_mixed_mode_collaboration(self):
        """Test collaboration with controllers in different modes."""
        controller1_id = 0  # Film strip
        controller2_id = 1   # Canvas
        controller3_id = 2  # Slider
        
        # Register controllers in different modes
        self.mode_switcher.register_controller(controller1_id, ControllerMode.FILM_STRIP)
        self.mode_switcher.register_controller(controller2_id, ControllerMode.CANVAS)
        self.mode_switcher.register_controller(controller3_id, ControllerMode.SLIDER)
        
        # Add indicators for each mode
        film_indicator = self.visual_manager.add_controller_indicator(
            controller1_id, 0, (255, 0, 0), (10, 10), LocationType.FILM_STRIP
        )
        canvas_indicator = self.visual_manager.add_controller_indicator(
            controller2_id, 1, (0, 255, 0), (50, 50), LocationType.CANVAS
        )
        slider_indicator = self.visual_manager.add_controller_indicator(
            controller3_id, 2, (0, 0, 255), (100, 100), LocationType.SLIDER
        )
        
        # Verify each indicator has correct properties
        assert film_indicator.shape == IndicatorShape.TRIANGLE
        assert film_indicator.transparency == 1.0
        assert film_indicator.location_type == LocationType.FILM_STRIP
        
        assert canvas_indicator.shape == IndicatorShape.SQUARE
        assert canvas_indicator.transparency == 0.5
        assert canvas_indicator.location_type == LocationType.CANVAS
        
        assert slider_indicator.shape == IndicatorShape.CIRCLE
        assert slider_indicator.transparency == 0.8
        assert slider_indicator.location_type == LocationType.SLIDER
        
        # Verify indicators are in correct location groups
        film_indicators = self.visual_manager.get_indicators_by_location(LocationType.FILM_STRIP)
        canvas_indicators = self.visual_manager.get_indicators_by_location(LocationType.CANVAS)
        slider_indicators = self.visual_manager.get_indicators_by_location(LocationType.SLIDER)
        
        assert len(film_indicators) == 1
        assert len(canvas_indicators) == 1
        assert len(slider_indicators) == 1
        
        assert controller1_id in film_indicators
        assert controller2_id in canvas_indicators
        assert controller3_id in slider_indicators
    
    def test_controller_mode_switching_workflow(self):
        """Test complete controller mode switching workflow."""
        controller_id = 0
        current_time = time.time()
        
        # Start in film strip mode
        self.mode_switcher.register_controller(controller_id, ControllerMode.FILM_STRIP)
        
        # Test mode cycling: FILM_STRIP -> CANVAS -> SLIDER -> FILM_STRIP
        # FILM_STRIP -> CANVAS
        new_mode = self.mode_switcher.handle_trigger_input(
            controller_id, 0.0, 1.0, current_time
        )
        assert new_mode == ControllerMode.CANVAS
        
        # Release trigger
        self.mode_switcher.handle_trigger_input(
            controller_id, 0.0, 0.0, current_time + 0.1
        )
        
        # CANVAS -> SLIDER
        new_mode = self.mode_switcher.handle_trigger_input(
            controller_id, 0.0, 1.0, current_time + 0.2
        )
        assert new_mode == ControllerMode.SLIDER
        
        # Release trigger
        self.mode_switcher.handle_trigger_input(
            controller_id, 0.0, 0.0, current_time + 0.3
        )
        
        # SLIDER -> FILM_STRIP (wraps around)
        new_mode = self.mode_switcher.handle_trigger_input(
            controller_id, 0.0, 1.0, current_time + 0.4
        )
        assert new_mode == ControllerMode.FILM_STRIP
        
        # Verify mode history
        mode_state = self.mode_switcher.controller_modes[controller_id]
        assert len(mode_state.mode_history) >= 4  # Initial + 3 switches
        assert mode_state.mode_history[-1] == ControllerMode.FILM_STRIP
    
    def test_visual_collision_avoidance_multi_location(self):
        """Test collision avoidance across multiple locations."""
        # Add indicators at same position in different locations
        indicator1 = self.visual_manager.add_controller_indicator(
            0, 0, (255, 0, 0), (10, 10), LocationType.FILM_STRIP
        )
        indicator2 = self.visual_manager.add_controller_indicator(
            1, 1, (0, 255, 0), (10, 10), LocationType.CANVAS
        )
        indicator3 = self.visual_manager.add_controller_indicator(
            2, 2, (0, 0, 255), (10, 10), LocationType.SLIDER
        )
        
        # Indicators in different locations should not collide
        # (they're in different visual spaces)
        assert indicator1.offset == (0, 0)  # No collision avoidance needed
        assert indicator2.offset == (0, 0)  # No collision avoidance needed
        assert indicator3.offset == (0, 0)  # No collision avoidance needed
        
        # But indicators in same location should avoid collision
        indicator4 = self.visual_manager.add_controller_indicator(
            3, 3, (255, 255, 0), (10, 10), LocationType.FILM_STRIP
        )
        
        # Second indicator in same location should be offset
        assert indicator4.offset != (0, 0)
    
    def test_trigger_detection_integration(self):
        """Test trigger detection integration with mode switching."""
        controller_id = 0
        current_time = time.time()
        
        self.mode_switcher.register_controller(controller_id, ControllerMode.FILM_STRIP)
        
        # Test L2 trigger (previous mode)
        new_mode = self.mode_switcher.handle_trigger_input(
            controller_id, 1.0, 0.0, current_time
        )
        assert new_mode == ControllerMode.SLIDER  # FILM_STRIP -> SLIDER (previous)
        
        # Test R2 trigger (next mode)
        self.mode_switcher.handle_trigger_input(
            controller_id, 0.0, 0.0, current_time + 0.1
        )
        
        new_mode = self.mode_switcher.handle_trigger_input(
            controller_id, 0.0, 1.0, current_time + 0.2
        )
        assert new_mode == ControllerMode.FILM_STRIP  # SLIDER -> FILM_STRIP (next)
    
    def test_position_tracking_across_modes(self):
        """Test position tracking across different modes."""
        controller_id = 0
        current_time = time.time()
        
        self.mode_switcher.register_controller(controller_id, ControllerMode.FILM_STRIP)
        
        # Save position for film strip mode
        self.mode_switcher.save_controller_position(controller_id, (10, 20), 5, "animation1")
        
        # Switch to canvas mode
        self.mode_switcher.handle_trigger_input(
            controller_id, 0.0, 1.0, current_time
        )
        self.mode_switcher.save_controller_position(controller_id, (50, 60), 3, "animation2")
        
        # Switch to slider mode
        self.mode_switcher.handle_trigger_input(
            controller_id, 0.0, 1.0, current_time + 0.1
        )
        self.mode_switcher.save_controller_position(controller_id, (100, 200), 1, "animation3")
        
        # Switch back to film strip mode
        self.mode_switcher.handle_trigger_input(
            controller_id, 0.0, 1.0, current_time + 0.2
        )
        
        # Verify current position (should be film strip position)
        film_position = self.mode_switcher.get_controller_position(controller_id)
        print(f"DEBUG: Current mode: {self.mode_switcher.get_controller_mode(controller_id)}")
        print(f"DEBUG: Film position: {film_position.position}, frame: {film_position.frame}, animation: {film_position.animation}")
        assert film_position.position == (10, 20)
        assert film_position.frame == 5
        assert film_position.animation == "animation1"
        
        # Verify mode-specific positions are preserved
        mode_state = self.mode_switcher.controller_modes[controller_id]
        canvas_position = mode_state.get_position_for_mode(ControllerMode.CANVAS)
        slider_position = mode_state.get_position_for_mode(ControllerMode.SLIDER)
        
        assert canvas_position.position == (50, 60)
        assert canvas_position.frame == 3
        assert canvas_position.animation == "animation2"
        
        assert slider_position.position == (100, 200)
        assert slider_position.frame == 1
        assert slider_position.animation == "animation3"
    
    def test_error_handling_integration(self):
        """Test error handling in integrated system."""
        # Test unregistered controller
        result = self.mode_switcher.handle_trigger_input(
            999, 0.0, 1.0, time.time()
        )
        assert result is None
        
        # Test invalid controller ID
        with pytest.raises(KeyError):
            self.mode_switcher.get_controller_mode(999)
        
        # Test controller removal
        controller_id = 0
        self.mode_switcher.register_controller(controller_id, ControllerMode.FILM_STRIP)
        self.visual_manager.add_controller_indicator(
            controller_id, 0, (255, 0, 0), (10, 10), LocationType.FILM_STRIP
        )
        
        # Remove controller
        self.mode_switcher.unregister_controller(controller_id)
        self.visual_manager.remove_controller_indicator(controller_id)
        
        # Verify removal
        assert controller_id not in self.mode_switcher.controller_modes
        film_indicators = self.visual_manager.get_indicators_by_location(LocationType.FILM_STRIP)
        assert controller_id not in film_indicators


class TestPlanCPerformance:
    """Performance tests for Plan C system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mode_switcher = ModeSwitcher()
        self.visual_manager = VisualCollisionManager()
    
    def test_performance_with_many_controllers(self):
        """Test performance with many controllers."""
        import time
        
        start_time = time.time()
        
        # Register many controllers
        for i in range(10):
            self.mode_switcher.register_controller(i, ControllerMode.FILM_STRIP)
            self.visual_manager.add_controller_indicator(
                i, i, (255, 0, 0), (i * 10, i * 10), LocationType.FILM_STRIP
            )
        
        # Switch modes for all controllers
        current_time = time.time()
        for i in range(10):
            self.mode_switcher.handle_trigger_input(
                i, 0.0, 1.0, current_time + i * 0.01
            )
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Should complete in reasonable time (< 1 second)
        assert elapsed < 1.0
        
        # Verify all controllers switched to canvas mode
        for i in range(10):
            mode = self.mode_switcher.get_controller_mode(i)
            assert mode == ControllerMode.CANVAS
    
    def test_memory_usage_with_large_indicators(self):
        """Test memory usage with large number of indicators."""
        # Add many indicators
        for i in range(100):
            self.visual_manager.add_controller_indicator(
                i, i, (255, 0, 0), (i % 10, i // 10), LocationType.FILM_STRIP
            )
        
        # Verify all indicators exist
        film_indicators = self.visual_manager.get_indicators_by_location(LocationType.FILM_STRIP)
        assert len(film_indicators) == 100
        
        # Test collision avoidance with many indicators
        # This should not cause performance issues
        for i in range(100, 110):
            indicator = self.visual_manager.add_controller_indicator(
                i, i, (0, 255, 0), (5, 5), LocationType.FILM_STRIP
            )
            # Should have collision avoidance applied for most indicators
            # (first one at position 5,5 might not need offset if no collision)
            if i > 100:  # Skip first one as it might not need offset
                assert indicator.offset != (0, 0)
