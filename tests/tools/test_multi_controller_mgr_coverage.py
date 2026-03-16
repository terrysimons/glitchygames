"""Tests to increase coverage for glitchygames/tools/multi_controller_manager.py.

Targets uncovered lines in controller management.
"""

import time

from glitchygames.tools.multi_controller_manager import (
    ControllerStatus,
    MultiControllerManager,
)


class TestMultiControllerManagerCleanup:
    """Test cleanup_inactive_controllers method."""

    def setup_method(self):
        """Reset the singleton before each test."""
        MultiControllerManager._instance = None
        MultiControllerManager._initialized = False

    def test_cleanup_inactive_controllers(self):
        """Test that inactive controllers are cleaned up."""
        manager = MultiControllerManager()

        # Manually add a controller with old activity
        from glitchygames.tools.multi_controller_manager import ControllerInfo

        controller = ControllerInfo(
            controller_id=0,
            instance_id=100,
            status=ControllerStatus.ACTIVE,
            assigned_time=time.time() - 100,
            last_activity=time.time() - 100,  # Very old activity
        )
        manager.controllers[100] = controller
        manager.assigned_controllers[100] = 0

        manager.cleanup_inactive_controllers()

        # Controller should be demoted to CONNECTED
        assert manager.controllers[100].status == ControllerStatus.CONNECTED
        assert 100 not in manager.assigned_controllers

    def test_cleanup_does_not_affect_active_controllers(self):
        """Test that recently active controllers are not cleaned up."""
        manager = MultiControllerManager()

        from glitchygames.tools.multi_controller_manager import ControllerInfo

        controller = ControllerInfo(
            controller_id=0,
            instance_id=100,
            status=ControllerStatus.ACTIVE,
            assigned_time=time.time(),
            last_activity=time.time(),  # Very recent activity
        )
        manager.controllers[100] = controller
        manager.assigned_controllers[100] = 0

        manager.cleanup_inactive_controllers()

        # Controller should remain ACTIVE
        assert manager.controllers[100].status == ControllerStatus.ACTIVE
        assert 100 in manager.assigned_controllers


class TestMultiControllerManagerAssignment:
    """Test controller assignment flow."""

    def setup_method(self):
        """Reset the singleton before each test."""
        MultiControllerManager._instance = None
        MultiControllerManager._initialized = False

    def test_assign_controller_unregistered(self):
        """Test assigning an unregistered controller returns None."""
        manager = MultiControllerManager()
        result = manager.assign_controller(999)
        assert result is None

    def test_assign_controller_already_assigned(self):
        """Test assigning an already-assigned controller returns its ID."""
        manager = MultiControllerManager()

        from glitchygames.tools.multi_controller_manager import ControllerInfo

        controller = ControllerInfo(
            controller_id=0,
            instance_id=100,
            status=ControllerStatus.CONNECTED,
        )
        manager.controllers[100] = controller

        # Assign once
        first_result = manager.assign_controller(100)
        assert first_result == 0

        # Assign again - should return same ID
        second_result = manager.assign_controller(100)
        assert second_result == 0

    def test_assign_controller_not_connected_status(self):
        """Test assigning a controller not in CONNECTED status returns None."""
        manager = MultiControllerManager()

        from glitchygames.tools.multi_controller_manager import ControllerInfo

        controller = ControllerInfo(
            controller_id=0,
            instance_id=100,
            status=ControllerStatus.ACTIVE,
        )
        manager.controllers[100] = controller

        result = manager.assign_controller(100)
        assert result is None


class TestMultiControllerManagerActivation:
    """Test controller activation."""

    def setup_method(self):
        """Reset the singleton before each test."""
        MultiControllerManager._instance = None
        MultiControllerManager._initialized = False

    def test_activate_unassigned_controller(self):
        """Test activating an unassigned controller returns False."""
        manager = MultiControllerManager()
        result = manager.activate_controller(999)
        assert result is False

    def test_activate_assigned_controller(self):
        """Test activating an assigned controller returns True."""
        manager = MultiControllerManager()

        from glitchygames.tools.multi_controller_manager import ControllerInfo

        controller = ControllerInfo(
            controller_id=0,
            instance_id=100,
            status=ControllerStatus.CONNECTED,
        )
        manager.controllers[100] = controller
        manager.assign_controller(100)

        result = manager.activate_controller(100)
        assert result is True
        assert manager.controllers[100].status == ControllerStatus.ACTIVE


class TestMultiControllerManagerQueries:
    """Test query methods."""

    def setup_method(self):
        """Reset the singleton before each test."""
        MultiControllerManager._instance = None
        MultiControllerManager._initialized = False

    def test_get_controller_color_nonexistent(self):
        """Test getting color for nonexistent controller."""
        manager = MultiControllerManager()
        assert manager.get_controller_color(999) is None

    def test_is_controller_active_nonexistent(self):
        """Test checking active status of nonexistent controller."""
        manager = MultiControllerManager()
        assert manager.is_controller_active(999) is False

    def test_update_controller_activity(self):
        """Test updating controller activity timestamp."""
        manager = MultiControllerManager()

        from glitchygames.tools.multi_controller_manager import ControllerInfo

        controller = ControllerInfo(
            controller_id=0,
            instance_id=100,
            status=ControllerStatus.ACTIVE,
            last_activity=0,
        )
        manager.controllers[100] = controller

        manager.update_controller_activity(100)

        assert controller.last_activity is not None
        assert controller.last_activity > 0

    def test_get_active_controllers(self):
        """Test getting list of active controllers."""
        manager = MultiControllerManager()

        from glitchygames.tools.multi_controller_manager import ControllerInfo

        manager.controllers[100] = ControllerInfo(
            controller_id=0,
            instance_id=100,
            status=ControllerStatus.ACTIVE,
        )
        manager.controllers[200] = ControllerInfo(
            controller_id=1,
            instance_id=200,
            status=ControllerStatus.CONNECTED,
        )

        active = manager.get_active_controllers()
        assert len(active) == 1
        assert 100 in active

    def test_get_controller_status_summary(self):
        """Test controller status summary."""
        manager = MultiControllerManager()

        from glitchygames.tools.multi_controller_manager import ControllerInfo

        manager.controllers[100] = ControllerInfo(
            controller_id=0,
            instance_id=100,
            status=ControllerStatus.ACTIVE,
        )

        summary = manager.get_controller_status_summary()

        assert summary['total_connected'] == 1
        assert 100 in summary['controllers']
        assert summary['controllers'][100]['status'] == 'active'

    def test_assign_color_to_controller(self):
        """Test assigning a color to a controller."""
        manager = MultiControllerManager()

        from glitchygames.tools.multi_controller_manager import ControllerInfo

        manager.controllers[100] = ControllerInfo(
            controller_id=0,
            instance_id=100,
            status=ControllerStatus.CONNECTED,
            color=(128, 128, 128),
        )

        manager.assign_color_to_controller(0)

        # Color should now be one of the CONTROLLER_COLORS
        assert manager.controllers[100].color in MultiControllerManager.CONTROLLER_COLORS
