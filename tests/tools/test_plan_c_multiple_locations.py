"""
Tests for Plan C multiple location support in VisualCollisionManager.

This module tests the extended VisualCollisionManager that supports
multiple location types (FILM_STRIP, CANVAS, SLIDER) with different
visual properties and collision handling.
"""

import pytest
import pygame
from unittest.mock import Mock, patch

from glitchygames.tools.visual_collision_manager import (
    VisualCollisionManager, LocationType, IndicatorShape, VisualIndicator
)


class TestMultipleLocationSupport:
    """Test multiple location support in VisualCollisionManager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.visual_manager = VisualCollisionManager()

    def test_location_type_enum(self):
        """Test that LocationType enum has correct values."""
        assert LocationType.FILM_STRIP.value == "film_strip"
        assert LocationType.CANVAS.value == "canvas"
        assert LocationType.SLIDER.value == "slider"

    def test_add_film_strip_indicator(self):
        """Test adding film strip indicator with correct properties."""
        indicator = self.visual_manager.add_controller_indicator(
            controller_id=0,
            instance_id=0,
            color=(255, 0, 0),
            position=(10, 20),
            location_type=LocationType.FILM_STRIP
        )

        assert indicator.controller_id == 0
        assert indicator.position == (10, 20)
        assert indicator.color == (255, 0, 0)
        assert indicator.shape == IndicatorShape.TRIANGLE
        assert indicator.transparency == 1.0
        assert indicator.location_type == LocationType.FILM_STRIP

    def test_add_canvas_indicator(self):
        """Test adding canvas indicator with correct properties."""
        indicator = self.visual_manager.add_controller_indicator(
            controller_id=1,
            instance_id=1,
            color=(0, 255, 0),
            position=(30, 40),
            location_type=LocationType.CANVAS
        )

        assert indicator.controller_id == 1
        assert indicator.position == (30, 40)
        assert indicator.color == (0, 255, 0)
        assert indicator.shape == IndicatorShape.SQUARE
        assert indicator.transparency == 0.5
        assert indicator.location_type == LocationType.CANVAS

    def test_add_slider_indicator(self):
        """Test adding slider indicator with correct properties."""
        indicator = self.visual_manager.add_controller_indicator(
            controller_id=2,
            instance_id=2,
            color=(0, 0, 255),
            position=(50, 60),
            location_type=LocationType.SLIDER
        )

        assert indicator.controller_id == 2
        assert indicator.position == (50, 60)
        assert indicator.color == (0, 0, 255)
        assert indicator.shape == IndicatorShape.CIRCLE
        assert indicator.transparency == 0.8
        assert indicator.location_type == LocationType.SLIDER

    def test_location_specific_tracking(self):
        """Test that indicators are tracked in location-specific dictionaries."""
        # Add indicators for different locations
        film_indicator = self.visual_manager.add_controller_indicator(
            0, 0, (255, 0, 0), (10, 10), LocationType.FILM_STRIP
        )
        canvas_indicator = self.visual_manager.add_controller_indicator(
            1, 1, (0, 255, 0), (20, 20), LocationType.CANVAS
        )
        slider_indicator = self.visual_manager.add_controller_indicator(
            2, 2, (0, 0, 255), (30, 30), LocationType.SLIDER
        )

        # Check location-specific tracking
        assert 0 in self.visual_manager.film_strip_indicators
        assert 1 in self.visual_manager.canvas_indicators
        assert 2 in self.visual_manager.slider_indicators

        # Check main indicators dict still works
        assert 0 in self.visual_manager.indicators
        assert 1 in self.visual_manager.indicators
        assert 2 in self.visual_manager.indicators

    def test_get_indicators_by_location(self):
        """Test getting indicators by location type."""
        # Add indicators for different locations
        self.visual_manager.add_controller_indicator(
            0, 0, (255, 0, 0), (10, 10), LocationType.FILM_STRIP
        )
        self.visual_manager.add_controller_indicator(
            1, 1, (0, 255, 0), (20, 20), LocationType.CANVAS
        )
        self.visual_manager.add_controller_indicator(
            2, 2, (0, 0, 255), (30, 30), LocationType.SLIDER
        )

        # Test getting indicators by location (returns dict, not list)
        film_indicators = self.visual_manager.get_indicators_by_location(LocationType.FILM_STRIP)
        canvas_indicators = self.visual_manager.get_indicators_by_location(LocationType.CANVAS)
        slider_indicators = self.visual_manager.get_indicators_by_location(LocationType.SLIDER)

        assert len(film_indicators) == 1
        assert len(canvas_indicators) == 1
        assert len(slider_indicators) == 1

        assert film_indicators[0].controller_id == 0
        assert canvas_indicators[1].controller_id == 1
        assert slider_indicators[2].controller_id == 2

    def test_collision_avoidance_per_location(self):
        """Test that collision avoidance works per location type."""
        # Add multiple indicators at same position for different locations
        self.visual_manager.add_controller_indicator(
            0, 0, (255, 0, 0), (10, 10), LocationType.FILM_STRIP
        )
        self.visual_manager.add_controller_indicator(
            1, 1, (0, 255, 0), (10, 10), LocationType.FILM_STRIP
        )
        self.visual_manager.add_controller_indicator(
            2, 2, (0, 0, 255), (10, 10), LocationType.CANVAS
        )

        # Check that film strip indicators have collision avoidance
        film_indicators = self.visual_manager.get_indicators_by_location(LocationType.FILM_STRIP)
        assert len(film_indicators) == 2
        
        # First indicator should have no offset
        assert film_indicators[0].offset == (0, 0)
        # Second indicator should have offset
        assert film_indicators[1].offset != (0, 0)

        # Canvas indicator should be independent
        canvas_indicators = self.visual_manager.get_indicators_by_location(LocationType.CANVAS)
        assert len(canvas_indicators) == 1
        assert canvas_indicators[2].offset == (0, 0)

    def test_remove_controller_indicator_multiple_locations(self):
        """Test removing indicators from multiple locations."""
        # Add indicators for different locations with different controller IDs
        self.visual_manager.add_controller_indicator(
            0, 0, (255, 0, 0), (10, 10), LocationType.FILM_STRIP
        )
        self.visual_manager.add_controller_indicator(
            1, 1, (0, 255, 0), (20, 20), LocationType.CANVAS
        )
        self.visual_manager.add_controller_indicator(
            2, 2, (0, 0, 255), (30, 30), LocationType.SLIDER
        )

        # Remove controllers from all locations
        self.visual_manager.remove_controller_indicator(0)
        self.visual_manager.remove_controller_indicator(1)
        self.visual_manager.remove_controller_indicator(2)

        # Check that all indicators are removed
        assert 0 not in self.visual_manager.film_strip_indicators
        assert 1 not in self.visual_manager.canvas_indicators
        assert 2 not in self.visual_manager.slider_indicators
        assert 0 not in self.visual_manager.indicators
        assert 1 not in self.visual_manager.indicators
        assert 2 not in self.visual_manager.indicators

    def test_update_collision_groups_per_location(self):
        """Test that collision groups are updated per location."""
        # Add indicators for different locations
        self.visual_manager.add_controller_indicator(
            0, 0, (255, 0, 0), (10, 10), LocationType.FILM_STRIP
        )
        self.visual_manager.add_controller_indicator(
            1, 1, (0, 255, 0), (20, 20), LocationType.CANVAS
        )

        # Check that location-specific collision groups are updated
        assert len(self.visual_manager.film_strip_collision_groups) > 0
        assert len(self.visual_manager.canvas_collision_groups) > 0

        # Check that groups contain the right indicators
        film_group = self.visual_manager.film_strip_collision_groups
        canvas_group = self.visual_manager.canvas_collision_groups

        # Check that positions are tracked
        assert (10, 10) in film_group
        assert (20, 20) in canvas_group

    def test_mixed_location_collision_scenarios(self):
        """Test collision scenarios with mixed location types."""
        # Add indicators at same position for different locations
        self.visual_manager.add_controller_indicator(
            0, 0, (255, 0, 0), (10, 10), LocationType.FILM_STRIP
        )
        self.visual_manager.add_controller_indicator(
            1, 1, (0, 255, 0), (10, 10), LocationType.CANVAS
        )
        self.visual_manager.add_controller_indicator(
            2, 2, (0, 0, 255), (10, 10), LocationType.SLIDER
        )

        # All indicators should be at the same position
        film_indicators = self.visual_manager.get_indicators_by_location(LocationType.FILM_STRIP)
        canvas_indicators = self.visual_manager.get_indicators_by_location(LocationType.CANVAS)
        slider_indicators = self.visual_manager.get_indicators_by_location(LocationType.SLIDER)

        assert film_indicators[0].position == (10, 10)
        assert canvas_indicators[1].position == (10, 10)
        assert slider_indicators[2].position == (10, 10)

        # But they should have different visual properties
        assert film_indicators[0].shape == IndicatorShape.TRIANGLE
        assert canvas_indicators[1].shape == IndicatorShape.SQUARE
        assert slider_indicators[2].shape == IndicatorShape.CIRCLE

        assert film_indicators[0].transparency == 1.0
        assert canvas_indicators[1].transparency == 0.5
        assert slider_indicators[2].transparency == 0.8

    def test_get_indicators_for_position_with_location_filter(self):
        """Test getting indicators for a position with location filtering."""
        # Add indicators at same position for different locations
        self.visual_manager.add_controller_indicator(
            0, 0, (255, 0, 0), (10, 10), LocationType.FILM_STRIP
        )
        self.visual_manager.add_controller_indicator(
            1, 1, (0, 255, 0), (10, 10), LocationType.CANVAS
        )

        # Test filtering by location
        film_indicators = self.visual_manager.get_indicators_for_position(
            (10, 10), location_type=LocationType.FILM_STRIP
        )
        canvas_indicators = self.visual_manager.get_indicators_for_position(
            (10, 10), location_type=LocationType.CANVAS
        )

        assert len(film_indicators) == 1
        assert len(canvas_indicators) == 1
        assert film_indicators[0].controller_id == 0
        assert canvas_indicators[0].controller_id == 1

    def test_visual_properties_per_location(self):
        """Test that visual properties are set correctly per location type."""
        # Test all location types
        locations = [
            (LocationType.FILM_STRIP, IndicatorShape.TRIANGLE, 1.0),
            (LocationType.CANVAS, IndicatorShape.SQUARE, 0.5),
            (LocationType.SLIDER, IndicatorShape.CIRCLE, 0.8)
        ]

        for i, (location_type, expected_shape, expected_transparency) in enumerate(locations):
            indicator = self.visual_manager.add_controller_indicator(
                i, i, (255, 0, 0), (10, 10), location_type
            )

            assert indicator.shape == expected_shape
            assert indicator.transparency == expected_transparency
            assert indicator.location_type == location_type

    def test_collision_groups_independence(self):
        """Test that collision groups are independent between locations."""
        # Add indicators at same position for different locations
        self.visual_manager.add_controller_indicator(
            0, 0, (255, 0, 0), (10, 10), LocationType.FILM_STRIP
        )
        self.visual_manager.add_controller_indicator(
            1, 1, (0, 255, 0), (10, 10), LocationType.FILM_STRIP
        )
        self.visual_manager.add_controller_indicator(
            2, 2, (0, 0, 255), (10, 10), LocationType.CANVAS
        )

        # Film strip indicators should have collision avoidance
        film_indicators = self.visual_manager.get_indicators_by_location(LocationType.FILM_STRIP)
        assert len(film_indicators) == 2
        assert film_indicators[0].offset == (0, 0)  # First indicator
        assert film_indicators[1].offset != (0, 0)  # Second indicator has offset

        # Canvas indicator should be independent
        canvas_indicators = self.visual_manager.get_indicators_by_location(LocationType.CANVAS)
        assert len(canvas_indicators) == 1
        assert canvas_indicators[2].offset == (0, 0)  # No collision with film strip
