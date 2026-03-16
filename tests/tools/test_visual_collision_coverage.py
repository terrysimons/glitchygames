"""Tests to increase coverage for glitchygames/tools/visual_collision_manager.py.

Targets uncovered lines focused on collision detection, visualization,
and edge cases in indicator management.
"""

from glitchygames.tools.visual_collision_manager import (
    IndicatorShape,
    LocationType,
    VisualCollisionManager,
)


class TestVisualCollisionManagerAddIndicator:
    """Test adding indicators with different location types."""

    def test_add_canvas_indicator(self):
        """Test adding a canvas indicator sets correct shape and transparency."""
        manager = VisualCollisionManager()
        indicator = manager.add_controller_indicator(
            controller_id=0,
            instance_id=0,
            color=(255, 0, 0),
            position=(10, 10),
            location_type=LocationType.CANVAS,
        )

        assert indicator.shape == IndicatorShape.SQUARE
        assert abs(indicator.transparency - 0.5) < 1e-9
        assert 0 in manager.canvas_indicators

    def test_add_slider_indicator(self):
        """Test adding a slider indicator sets correct shape and transparency."""
        manager = VisualCollisionManager()
        indicator = manager.add_controller_indicator(
            controller_id=1,
            instance_id=1,
            color=(0, 255, 0),
            position=(20, 20),
            location_type=LocationType.SLIDER,
        )

        assert indicator.shape == IndicatorShape.CIRCLE
        assert abs(indicator.transparency - 0.8) < 1e-9
        assert 1 in manager.slider_indicators

    def test_add_film_strip_indicator(self):
        """Test adding a film strip indicator sets correct shape and transparency."""
        manager = VisualCollisionManager()
        indicator = manager.add_controller_indicator(
            controller_id=2,
            instance_id=2,
            color=(0, 0, 255),
            position=(30, 30),
            location_type=LocationType.FILM_STRIP,
        )

        assert indicator.shape == IndicatorShape.TRIANGLE
        assert abs(indicator.transparency - 1.0) < 1e-9
        assert 2 in manager.film_strip_indicators


class TestVisualCollisionManagerRemove:
    """Test removing indicators."""

    def test_remove_film_strip_indicator(self):
        """Test removing a film strip indicator."""
        manager = VisualCollisionManager()
        manager.add_controller_indicator(0, 0, (255, 0, 0), (10, 10), LocationType.FILM_STRIP)

        manager.remove_controller_indicator(0)

        assert 0 not in manager.indicators
        assert 0 not in manager.film_strip_indicators

    def test_remove_canvas_indicator(self):
        """Test removing a canvas indicator."""
        manager = VisualCollisionManager()
        manager.add_controller_indicator(0, 0, (255, 0, 0), (10, 10), LocationType.CANVAS)

        manager.remove_controller_indicator(0)

        assert 0 not in manager.indicators
        assert 0 not in manager.canvas_indicators

    def test_remove_slider_indicator(self):
        """Test removing a slider indicator."""
        manager = VisualCollisionManager()
        manager.add_controller_indicator(0, 0, (255, 0, 0), (10, 10), LocationType.SLIDER)

        manager.remove_controller_indicator(0)

        assert 0 not in manager.indicators
        assert 0 not in manager.slider_indicators

    def test_remove_indicator_for_specific_location(self):
        """Test removing an indicator from a specific location type."""
        manager = VisualCollisionManager()
        manager.add_controller_indicator(0, 0, (255, 0, 0), (10, 10), LocationType.FILM_STRIP)

        manager.remove_controller_indicator_for_location(0, LocationType.FILM_STRIP)

        assert 0 not in manager.film_strip_indicators

    def test_remove_nonexistent_indicator(self):
        """Test removing a nonexistent indicator does not raise."""
        manager = VisualCollisionManager()
        manager.remove_controller_indicator(999)  # Should not raise


class TestVisualCollisionManagerPositioning:
    """Test position management and collision avoidance."""

    def test_update_controller_position(self):
        """Test updating controller position."""
        manager = VisualCollisionManager()
        manager.add_controller_indicator(0, 0, (255, 0, 0), (10, 10))

        manager.update_controller_position(0, (50, 50))

        assert manager.indicators[0].position == (50, 50)

    def test_update_nonexistent_controller_position(self):
        """Test updating position of nonexistent controller."""
        manager = VisualCollisionManager()
        manager.update_controller_position(999, (50, 50))  # Should not raise

    def test_get_final_position_with_offset(self):
        """Test getting final position includes offset."""
        manager = VisualCollisionManager()
        manager.add_controller_indicator(0, 0, (255, 0, 0), (10, 20))
        manager.indicators[0].offset = (5, 10)

        final_pos = manager.get_final_position(0)

        assert final_pos == (15, 30)

    def test_get_final_position_nonexistent(self):
        """Test getting final position of nonexistent controller."""
        manager = VisualCollisionManager()
        assert manager.get_final_position(999) == (0, 0)

    def test_collision_avoidance_with_multiple_indicators(self):
        """Test collision avoidance applies offsets when indicators overlap."""
        manager = VisualCollisionManager()

        # Add two indicators at the same position
        manager.add_controller_indicator(0, 0, (255, 0, 0), (10, 10), LocationType.FILM_STRIP)
        manager.add_controller_indicator(1, 1, (0, 255, 0), (10, 10), LocationType.FILM_STRIP)

        # At least one should have a non-zero offset
        offsets = [
            manager.film_strip_indicators[cid].offset
            for cid in [0, 1]
            if cid in manager.film_strip_indicators
        ]
        assert any(offset != (0, 0) for offset in offsets)

    def test_calculate_offsets_for_many_indicators(self):
        """Test offset calculation for more indicators than predefined patterns."""
        manager = VisualCollisionManager()

        # Request offsets for more than the predefined pattern count
        offsets = manager._calculate_offsets(15)

        assert len(offsets) == 15
        # All offsets should be tuples of two ints
        for offset in offsets:
            assert len(offset) == 2


class TestVisualCollisionManagerQueries:
    """Test indicator query methods."""

    def test_get_indicators_for_position_all_types(self):
        """Test getting indicators at a position across all types."""
        manager = VisualCollisionManager()
        manager.add_controller_indicator(0, 0, (255, 0, 0), (10, 10), LocationType.FILM_STRIP)
        manager.add_controller_indicator(1, 1, (0, 255, 0), (10, 10), LocationType.CANVAS)

        result = manager.get_indicators_for_position((10, 10))

        assert len(result) == 2

    def test_get_indicators_for_position_specific_type(self):
        """Test getting indicators at a position for specific type."""
        manager = VisualCollisionManager()
        manager.add_controller_indicator(0, 0, (255, 0, 0), (10, 10), LocationType.FILM_STRIP)
        manager.add_controller_indicator(1, 1, (0, 255, 0), (10, 10), LocationType.CANVAS)

        result = manager.get_indicators_for_position((10, 10), LocationType.FILM_STRIP)
        assert len(result) == 1

    def test_get_indicators_for_position_slider(self):
        """Test getting slider indicators at a position."""
        manager = VisualCollisionManager()
        manager.add_controller_indicator(0, 0, (255, 0, 0), (10, 10), LocationType.SLIDER)

        result = manager.get_indicators_for_position((10, 10), LocationType.SLIDER)
        assert len(result) == 1

    def test_get_visible_indicators(self):
        """Test getting visible indicators."""
        manager = VisualCollisionManager()
        manager.add_controller_indicator(0, 0, (255, 0, 0), (10, 10))
        manager.add_controller_indicator(1, 1, (0, 255, 0), (20, 20))

        manager.set_indicator_visibility(1, visible=False)

        visible = manager.get_visible_indicators()
        assert len(visible) == 1

    def test_get_indicators_by_location_slider(self):
        """Test getting indicators by slider location."""
        manager = VisualCollisionManager()
        manager.add_controller_indicator(0, 0, (255, 0, 0), (10, 10), LocationType.SLIDER)

        result = manager.get_indicators_by_location(LocationType.SLIDER)
        assert len(result) == 1

    def test_get_collision_summary(self):
        """Test collision summary generation."""
        manager = VisualCollisionManager()
        manager.add_controller_indicator(0, 0, (255, 0, 0), (10, 10))

        summary = manager.get_collision_summary()

        assert summary['total_indicators'] == 1
        assert 'collision_groups' in summary
        assert 'position_cache_size' in summary


class TestVisualCollisionManagerModifiers:
    """Test indicator modification methods."""

    def test_set_indicator_color(self):
        """Test setting indicator color."""
        manager = VisualCollisionManager()
        manager.add_controller_indicator(0, 0, (255, 0, 0), (10, 10))

        manager.set_indicator_color(0, (0, 255, 0))

        assert manager.indicators[0].color == (0, 255, 0)

    def test_set_indicator_shape(self):
        """Test setting indicator shape."""
        manager = VisualCollisionManager()
        manager.add_controller_indicator(0, 0, (255, 0, 0), (10, 10))

        manager.set_indicator_shape(0, IndicatorShape.DIAMOND)

        assert manager.indicators[0].shape == IndicatorShape.DIAMOND

    def test_set_indicator_size(self):
        """Test setting indicator size."""
        manager = VisualCollisionManager()
        manager.add_controller_indicator(0, 0, (255, 0, 0), (10, 10))

        manager.set_indicator_size(0, 20)

        assert manager.indicators[0].size == 20

    def test_clear_all_indicators(self):
        """Test clearing all indicators."""
        manager = VisualCollisionManager()
        manager.add_controller_indicator(0, 0, (255, 0, 0), (10, 10))
        manager.add_controller_indicator(1, 1, (0, 255, 0), (20, 20))

        manager.clear_all_indicators()

        assert len(manager.indicators) == 0

    def test_optimize_positioning(self):
        """Test optimize_positioning recalculates collision avoidance."""
        manager = VisualCollisionManager()
        manager.add_controller_indicator(0, 0, (255, 0, 0), (10, 10))
        manager.add_controller_indicator(1, 1, (0, 255, 0), (10, 10))

        # Manually populate cache with stale data
        manager.position_cache[99, 99] = [(0, 0)]

        manager.optimize_positioning()

        # Stale cache entry should be cleared
        assert (99, 99) not in manager.position_cache
