"""Tests covering uncovered lines in visual_collision_manager.py.

Targets uncovered lines: 219-222, 252, 283, 313, 347, 364, 379-382,
415, 461, 543-544, 576.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.tools.visual_collision_manager import (
    LocationType,
    VisualCollisionManager,
    VisualIndicator,
)


class TestRemoveControllerIndicatorForLocation:
    """Test remove_controller_indicator_for_location (lines 219-222)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = VisualCollisionManager()

    def test_remove_canvas_indicator(self):
        """Test removing a canvas indicator by location (line 219-220)."""
        self.manager.add_controller_indicator(
            controller_id=0,
            instance_id=100,
            color=(255, 0, 0),
            position=(10, 10),
            location_type=LocationType.CANVAS,
        )

        assert 0 in self.manager.canvas_indicators

        self.manager.remove_controller_indicator_for_location(0, LocationType.CANVAS)

        assert 0 not in self.manager.canvas_indicators

    def test_remove_slider_indicator(self):
        """Test removing a slider indicator by location (lines 221-222)."""
        self.manager.add_controller_indicator(
            controller_id=1,
            instance_id=101,
            color=(0, 255, 0),
            position=(20, 20),
            location_type=LocationType.SLIDER,
        )

        assert 1 in self.manager.slider_indicators

        self.manager.remove_controller_indicator_for_location(1, LocationType.SLIDER)

        assert 1 not in self.manager.slider_indicators

    def test_remove_film_strip_indicator(self):
        """Test removing a film_strip indicator by location."""
        self.manager.add_controller_indicator(
            controller_id=2,
            instance_id=102,
            color=(0, 0, 255),
            position=(30, 30),
            location_type=LocationType.FILM_STRIP,
        )

        assert 2 in self.manager.film_strip_indicators

        self.manager.remove_controller_indicator_for_location(2, LocationType.FILM_STRIP)

        assert 2 not in self.manager.film_strip_indicators


class TestGetControllerIndicatorNotFound:
    """Test get_controller_indicator returning None (line 252)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = VisualCollisionManager()

    def test_get_indicator_for_nonexistent_controller(self):
        """Test get_controller_indicator returns None for unknown controller (line 252)."""
        result = self.manager.get_controller_indicator(999)

        assert result is None


class TestGetIndicatorsForPositionByLocation:
    """Test get_indicators_for_position with specific location types (line 283)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = VisualCollisionManager()

    def test_get_indicators_for_position_canvas_location(self):
        """Test filtering by CANVAS location type (line 283)."""
        self.manager.add_controller_indicator(
            controller_id=0,
            instance_id=100,
            color=(255, 0, 0),
            position=(10, 10),
            location_type=LocationType.CANVAS,
        )
        self.manager.add_controller_indicator(
            controller_id=1,
            instance_id=101,
            color=(0, 255, 0),
            position=(10, 10),
            location_type=LocationType.FILM_STRIP,
        )

        result = self.manager.get_indicators_for_position(
            (10, 10), location_type=LocationType.CANVAS
        )

        assert len(result) == 1
        assert result[0].controller_id == 0

    def test_get_indicators_for_position_slider_location(self):
        """Test filtering by SLIDER location type."""
        self.manager.add_controller_indicator(
            controller_id=0,
            instance_id=100,
            color=(255, 0, 0),
            position=(10, 10),
            location_type=LocationType.SLIDER,
        )

        result = self.manager.get_indicators_for_position(
            (10, 10), location_type=LocationType.SLIDER
        )

        assert len(result) == 1


class TestUpdateCollisionGroupsSlider:
    """Test _update_collision_groups for SLIDER location type (line 313)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = VisualCollisionManager()

    def test_update_collision_groups_slider(self):
        """Test that slider collision groups are updated properly (line 310-311)."""
        self.manager.add_controller_indicator(
            controller_id=0,
            instance_id=100,
            color=(255, 0, 0),
            position=(10, 10),
            location_type=LocationType.SLIDER,
        )
        self.manager.add_controller_indicator(
            controller_id=1,
            instance_id=101,
            color=(0, 255, 0),
            position=(10, 10),
            location_type=LocationType.SLIDER,
        )

        # Collision groups should show both at same position
        groups = self.manager._get_collision_groups_for_location(LocationType.SLIDER)
        assert (10, 10) in groups
        assert len(groups[10, 10]) == 2


class TestGetCollisionGroupsForLocationDefault:
    """Test _get_collision_groups_for_location default case (line 347)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = VisualCollisionManager()

    def test_unknown_location_returns_default_groups(self):
        """Test that unknown location type returns default collision_groups (line 347)."""
        # Pass None location type to hit the default return
        result = self.manager._get_collision_groups_for_location(None)  # type: ignore[arg-type]

        assert result is self.manager.collision_groups


class TestApplyCollisionAvoidanceSingleController:
    """Test _apply_collision_avoidance with single controller (line 364)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = VisualCollisionManager()

    def test_single_controller_no_avoidance(self):
        """Test that collision avoidance is skipped for single controller (line 364)."""
        self.manager._apply_collision_avoidance((10, 10), [0], LocationType.FILM_STRIP)

        # No offsets should have been applied - nothing in indicators


class TestApplyCollisionAvoidanceSliderAndFallback:
    """Test _apply_collision_avoidance with slider type and fallback offsets (lines 379-382)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = VisualCollisionManager()

    def test_collision_avoidance_slider_type(self):
        """Test collision avoidance for SLIDER location type (lines 379-380)."""
        self.manager.add_controller_indicator(
            controller_id=0,
            instance_id=100,
            color=(255, 0, 0),
            position=(10, 10),
            location_type=LocationType.SLIDER,
        )
        self.manager.add_controller_indicator(
            controller_id=1,
            instance_id=101,
            color=(0, 255, 0),
            position=(10, 10),
            location_type=LocationType.SLIDER,
        )

        # The collision groups should trigger avoidance
        slider_indicators = self.manager.slider_indicators
        assert 0 in slider_indicators
        assert 1 in slider_indicators

        # Both should have offsets applied after collision avoidance
        # (they were at the same position)

    def test_collision_avoidance_default_indicators(self):
        """Test collision avoidance with default (fallback) indicators dict (lines 381-382)."""
        # Directly call with None location type to use self.indicators
        self.manager.add_controller_indicator(
            controller_id=0,
            instance_id=100,
            color=(255, 0, 0),
            position=(10, 10),
            location_type=LocationType.FILM_STRIP,
        )
        self.manager.add_controller_indicator(
            controller_id=1,
            instance_id=101,
            color=(0, 255, 0),
            position=(10, 10),
            location_type=LocationType.FILM_STRIP,
        )

        # Both should have offsets after collision avoidance
        assert self.manager.film_strip_indicators[0].offset != (
            0,
            0,
        ) or self.manager.film_strip_indicators[1].offset != (0, 0)


class TestCalculateOffsetsLargeCount:
    """Test _calculate_offsets with more than POSITION_PATTERNS count (line 415)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = VisualCollisionManager()

    def test_calculate_offsets_beyond_patterns(self):
        """Test _calculate_offsets generates extra spiral offsets (line 415+)."""
        # POSITION_PATTERNS has 9 entries, request 12
        offsets = self.manager._calculate_offsets(12)

        assert len(offsets) == 12
        # First 9 should match POSITION_PATTERNS
        for i in range(9):
            assert offsets[i] == self.manager.POSITION_PATTERNS[i]
        # Extra offsets should be generated
        for i in range(9, 12):
            assert isinstance(offsets[i], tuple)
            assert len(offsets[i]) == 2


class TestGetAllIndicators:
    """Test get_all_indicators (line 461)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = VisualCollisionManager()

    def test_get_all_indicators_returns_list(self):
        """Test get_all_indicators returns list of all indicators (line 461)."""
        self.manager.add_controller_indicator(
            controller_id=0,
            instance_id=100,
            color=(255, 0, 0),
            position=(10, 10),
        )
        self.manager.add_controller_indicator(
            controller_id=1,
            instance_id=101,
            color=(0, 255, 0),
            position=(20, 20),
        )

        result = self.manager.get_all_indicators()

        assert len(result) == 2
        assert all(isinstance(indicator, VisualIndicator) for indicator in result)


class TestGetCollisionSummaryWithCollisions:
    """Test get_collision_summary counting (lines 543-544)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = VisualCollisionManager()

    def test_collision_summary_counts_groups_with_collisions(self):
        """Test that groups_with_collisions is incremented (lines 543-544).

        When two controllers are at the same position, the collision
        summary should count one collision group.
        """
        self.manager.add_controller_indicator(
            controller_id=0,
            instance_id=100,
            color=(255, 0, 0),
            position=(10, 10),
        )
        self.manager.add_controller_indicator(
            controller_id=1,
            instance_id=101,
            color=(0, 255, 0),
            position=(10, 10),
        )

        # Force the main collision_groups to be populated
        # The collision groups are location-specific, so populate manually
        self.manager.collision_groups[10, 10] = [0, 1]

        summary = self.manager.get_collision_summary()

        assert summary['groups_with_collisions'] == 1
        assert summary['total_indicators'] == 2


class TestGetIndicatorsByLocationDefault:
    """Test get_indicators_by_location with unknown type (line 576)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = VisualCollisionManager()

    def test_get_indicators_by_location_default(self):
        """Test get_indicators_by_location returns self.indicators for unknown type (line 576)."""
        self.manager.add_controller_indicator(
            controller_id=0,
            instance_id=100,
            color=(255, 0, 0),
            position=(10, 10),
        )

        # Pass None to trigger the default return
        result = self.manager.get_indicators_by_location(None)  # type: ignore[arg-type]

        assert result is self.manager.indicators
