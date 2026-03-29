"""Tests to increase coverage for glitchygames/tools/controller_selection.py.

Targets uncovered lines in selection state management.
"""

from glitchygames.bitmappy.controllers.selection import ControllerSelection


class TestControllerSelectionFillDirection:
    """Test fill direction methods."""

    def test_set_fill_direction_horizontal(self):
        """Test setting fill direction to HORIZONTAL."""
        selection = ControllerSelection(controller_id=0, instance_id=0)

        selection.set_fill_direction('HORIZONTAL')

        assert selection.get_fill_direction() == 'HORIZONTAL'

    def test_set_fill_direction_vertical(self):
        """Test setting fill direction to VERTICAL."""
        selection = ControllerSelection(controller_id=0, instance_id=0)

        selection.set_fill_direction('VERTICAL')

        assert selection.get_fill_direction() == 'VERTICAL'

    def test_set_fill_direction_invalid(self):
        """Test setting invalid fill direction does nothing."""
        selection = ControllerSelection(controller_id=0, instance_id=0)
        original = selection.get_fill_direction()

        selection.set_fill_direction('DIAGONAL')

        assert selection.get_fill_direction() == original


class TestControllerSelectionCloneState:
    """Test clone_state_to method."""

    def test_clone_active_state(self):
        """Test cloning active controller state to another controller."""
        source = ControllerSelection(controller_id=0, instance_id=0)
        target = ControllerSelection(controller_id=1, instance_id=1)

        source.set_selection('walk', 3)
        source.activate()

        source.clone_state_to(target)

        animation, frame = target.get_selection()
        assert animation == 'walk'
        assert frame == 3
        assert target.is_active() is True

    def test_clone_inactive_state(self):
        """Test cloning inactive controller state."""
        source = ControllerSelection(controller_id=0, instance_id=0)
        target = ControllerSelection(controller_id=1, instance_id=1)

        source.set_selection('idle', 0)
        source.deactivate()

        # Activate target first, then clone inactive source
        target.activate()
        source.clone_state_to(target)

        assert target.is_active() is False


class TestControllerSelectionResetToDefault:
    """Test reset_to_default method."""

    def test_reset_clears_all_state(self):
        """Test reset_to_default restores default values."""
        selection = ControllerSelection(controller_id=0, instance_id=0)
        selection.set_selection('walk', 5)
        selection.activate()

        selection.reset_to_default()

        assert not selection.get_animation()
        assert selection.get_frame() == 0
        assert selection.is_active() is False
        assert len(selection.get_navigation_history()) == 0


class TestControllerSelectionNavigationHistory:
    """Test navigation history management."""

    def test_clear_navigation_history(self):
        """Test clearing navigation history."""
        selection = ControllerSelection(controller_id=0, instance_id=0)
        selection.set_animation('walk')
        selection.set_animation('run')

        selection.clear_navigation_history()

        assert len(selection.get_navigation_history()) == 0

    def test_navigation_history_records_changes(self):
        """Test that animation changes are recorded in history."""
        selection = ControllerSelection(controller_id=0, instance_id=0)
        selection.set_animation('walk')
        selection.set_animation('run')

        history = selection.get_navigation_history()
        # History records both the initial empty->walk and walk->run transitions
        assert len(history) == 2
        assert not history[0]['animation']
        assert history[1]['animation'] == 'walk'


class TestControllerSelectionPreserveFrame:
    """Test preserve_frame_for_animation method."""

    def test_preserve_frame_from_history(self):
        """Test frame preservation uses history for known animations."""
        selection = ControllerSelection(controller_id=0, instance_id=0)
        selection.set_selection('walk', 3)
        selection.set_selection('run', 0)

        # Now switch back to 'walk' - should use frame 3 from history
        frame = selection.preserve_frame_for_animation('walk', 10)
        assert frame == 3

    def test_preserve_frame_clamps_to_range(self):
        """Test frame preservation clamps when target exceeds range."""
        selection = ControllerSelection(controller_id=0, instance_id=0)
        selection.set_frame(20)

        frame = selection.preserve_frame_for_animation('new_anim', 5)
        assert frame == 4  # max(0, 5 - 1)

    def test_preserve_frame_clamps_negative(self):
        """Test frame preservation handles negative frame index."""
        selection = ControllerSelection(controller_id=0, instance_id=0)
        selection.state.selected_frame = -1

        frame = selection.preserve_frame_for_animation('new_anim', 5)
        assert frame == 0


class TestControllerSelectionStateSummary:
    """Test get_state_summary method."""

    def test_state_summary_contains_expected_keys(self):
        """Test state summary includes all expected fields."""
        selection = ControllerSelection(controller_id=0, instance_id=0)

        summary = selection.get_state_summary()

        assert summary['controller_id'] == 0
        assert summary['instance_id'] == 0
        assert 'selected_animation' in summary
        assert 'selected_frame' in summary
        assert 'is_active' in summary
        assert 'activity_age' in summary
        assert 'navigation_history_count' in summary
        assert 'creation_time' in summary


class TestControllerSelectionActivity:
    """Test activity tracking."""

    def test_update_activity(self):
        """Test update_activity updates the timestamp."""
        selection = ControllerSelection(controller_id=0, instance_id=0)
        selection.update_activity()

        age = selection.get_activity_age()
        assert age < 1.0  # Should be very recent

    def test_get_activity_age(self):
        """Test get_activity_age returns a non-negative value."""
        selection = ControllerSelection(controller_id=0, instance_id=0)
        age = selection.get_activity_age()
        assert age >= 0.0
