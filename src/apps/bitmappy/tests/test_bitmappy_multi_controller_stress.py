"""Multi-Controller System Stress Tests.

This module provides stress tests and performance benchmarks for the
multi-controller system under extreme conditions.
"""

import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from bitmappy.controllers.manager import (
    ControllerInfo,
    ControllerStatus,
    MultiControllerManager,
)
from bitmappy.controllers.selection import ControllerSelection
from bitmappy.indicators.collision import VisualCollisionManager


class TestMultiControllerStress:
    """Stress tests for multi-controller system."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up test fixtures."""
        self._mocker = mocker
        # Reset singleton for clean tests
        MultiControllerManager._instance = None
        MultiControllerManager._initialized = False
        self.manager = MultiControllerManager()
        self.visual_manager = VisualCollisionManager()
        self.controller_selections: dict[int, ControllerSelection] = {}

    def test_maximum_controller_stress(self):
        """Test system behavior with maximum number of controllers."""
        # Add maximum controllers
        for i in range(self.manager.MAX_CONTROLLERS):
            instance_id = i
            self.manager.controllers[instance_id] = self._mocker.Mock()
            self.manager.assigned_controllers[instance_id] = i
            self.controller_selections[i] = ControllerSelection(i, instance_id)
            self.controller_selections[i].activate()

            # Add visual indicators
            self.visual_manager.add_controller_indicator(
                controller_id=i,
                instance_id=instance_id,
                color=(255, 0, 0),
                position=(i * 5, i * 5),
            )

        # Test rapid operations on all controllers
        for _ in range(100):
            for i in range(self.manager.MAX_CONTROLLERS):
                self.controller_selections[i].set_selection(f'animation_{i}', i)
                self.visual_manager.update_controller_position(i, (i * 10, i * 10))

        # Verify all controllers are still functional
        for i in range(self.manager.MAX_CONTROLLERS):
            assert self.controller_selections[i].is_active()
            animation, frame = self.controller_selections[i].get_selection()
            assert animation == f'animation_{i}'
            assert frame == i

    def test_rapid_controller_switching_stress(self):
        """Test rapid switching between controllers."""
        # Set up controllers
        for i in range(4):
            instance_id = i
            self.manager.controllers[instance_id] = self._mocker.Mock()
            self.manager.assigned_controllers[instance_id] = i
            self.controller_selections[i] = ControllerSelection(i, instance_id)

        # Rapidly switch between controllers
        for cycle in range(1000):
            for i in range(4):
                self.controller_selections[i].activate()
                self.controller_selections[i].set_selection(f'animation_{i}', cycle)
                time.sleep(0.0001)  # Very small delay

        # Verify final states
        for i in range(4):
            assert self.controller_selections[i].is_active()
            animation, frame = self.controller_selections[i].get_selection()
            assert animation == f'animation_{i}'
            assert frame == 999  # Last cycle

    def test_memory_stress_with_navigation_history(self):
        """Test memory usage with extensive navigation history."""
        # Set up controller
        self.controller_selections[0] = ControllerSelection(0, 0)
        self.controller_selections[0].activate()

        # Generate extensive navigation history
        for i in range(10000):
            self.controller_selections[0].set_selection(f'animation_{i % 100}', i % 50)

        # Verify navigation history
        history = self.controller_selections[0].get_navigation_history()
        assert len(history) > 0

        # Verify current state
        animation, frame = self.controller_selections[0].get_selection()
        assert animation == 'animation_99'  # Last animation
        assert frame == 49  # Last frame

    def test_visual_collision_stress(self):
        """Test visual collision system under stress."""
        # Add many controllers at same position
        for i in range(50):
            self.visual_manager.add_controller_indicator(
                controller_id=i,
                instance_id=i,
                color=(255, 0, 0),
                position=(100, 100),  # Same position
            )

        # Verify collision avoidance was applied
        assert (100, 100) in self.visual_manager.film_strip_collision_groups
        assert len(self.visual_manager.film_strip_collision_groups[100, 100]) == 50

        # Test rapid position updates
        for _ in range(100):
            for i in range(50):
                self.visual_manager.update_controller_position(i, (100 + i, 100 + i))

        # Indicator 0 stays at the shared position; every other indicator moved to its own
        assert len(self.visual_manager.indicators) == 50
        assert len(self.visual_manager.film_strip_collision_groups) == 50
        assert (100, 100) in self.visual_manager.film_strip_collision_groups
        assert self.visual_manager.get_controller_indicator(7).position == (107, 107)

    def test_concurrent_operations_stress(self):
        """Test concurrent operations on multiple controllers."""
        # Set up controllers
        for i in range(8):
            instance_id = i
            self.manager.controllers[instance_id] = self._mocker.Mock()
            self.manager.assigned_controllers[instance_id] = i
            self.controller_selections[i] = ControllerSelection(i, instance_id)
            self.controller_selections[i].activate()

        def controller_worker(controller_id: int, iterations: int):
            """Worker function for concurrent operations."""
            for _ in range(iterations):
                self.controller_selections[controller_id].set_selection(
                    f'animation_{controller_id}',
                    controller_id,
                )
                time.sleep(0.001)

        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = []
            for i in range(8):
                future = executor.submit(controller_worker, i, 100)
                futures.append(future)

            # Wait for all operations to complete
            for future in futures:
                future.result()

        # Verify all controllers are still functional
        for i in range(8):
            assert self.controller_selections[i].is_active()
            animation, frame = self.controller_selections[i].get_selection()
            assert animation == f'animation_{i}'
            assert frame == i

    def test_system_resilience_stress(self):
        """Test system resilience under extreme conditions."""
        # Rapidly add and remove controllers
        for cycle in range(100):
            # Add controllers
            for i in range(5):
                instance_id = i + cycle * 5
                self.manager.controllers[instance_id] = self._mocker.Mock()
                self.manager.assigned_controllers[instance_id] = i

                self.visual_manager.add_controller_indicator(
                    controller_id=i,
                    instance_id=instance_id,
                    color=(255, 0, 0),
                    position=(i * 10, i * 10),
                )

            # Remove controllers
            for i in range(5):
                instance_id = i + cycle * 5
                if instance_id in self.manager.controllers:
                    del self.manager.controllers[instance_id]
                if instance_id in self.manager.assigned_controllers:
                    del self.manager.assigned_controllers[instance_id]

                self.visual_manager.remove_controller_indicator(i)

        # System should still be functional
        assert len(self.manager.controllers) == 0
        assert len(self.visual_manager.indicators) == 0

    def test_memory_leak_prevention(self):
        """Test that system doesn't leak memory over time."""
        # Perform many operations that could cause memory leaks
        for cycle in range(1000):
            # Add and remove controllers
            for i in range(3):
                instance_id = i + cycle * 3
                self.manager.controllers[instance_id] = self._mocker.Mock()
                self.manager.assigned_controllers[instance_id] = i

                self.visual_manager.add_controller_indicator(
                    controller_id=i,
                    instance_id=instance_id,
                    color=(255, 0, 0),
                    position=(i * 5, i * 5),
                )

                # Perform operations
                self.visual_manager.update_controller_position(i, (i * 10, i * 10))
                self.visual_manager.remove_controller_indicator(i)

            # Clean up
            for i in range(3):
                instance_id = i + cycle * 3
                if instance_id in self.manager.controllers:
                    del self.manager.controllers[instance_id]
                if instance_id in self.manager.assigned_controllers:
                    del self.manager.assigned_controllers[instance_id]

        # System should still be functional
        assert len(self.manager.controllers) == 0
        assert len(self.visual_manager.indicators) == 0

    def test_bulk_assignment_and_indicator_outcomes(self):
        """A bulk run of assignments and indicator adds ends in the right state.

        This was ``test_performance_benchmarks``, which asserted wall-clock limits. A time limit
        is a load test, not a behavior test: it failed on a loaded machine and passed alone. The
        timing now lives in ``test_bitmappy_benchmarks.py`` (``--benchmark-only``); this test
        keeps the same work and checks what it produced.
        """
        controller_count = 1000
        for instance_id in range(controller_count):
            # A real ControllerInfo: a Mock's status is never CONNECTED, so assign_controller
            # would answer None and the old test measured a no-op.
            self.manager.controllers[instance_id] = ControllerInfo(
                controller_id=instance_id % self.manager.MAX_CONTROLLERS,
                instance_id=instance_id,
                status=ControllerStatus.CONNECTED,
            )
            assert self.manager.assign_controller(instance_id) == (
                instance_id % self.manager.MAX_CONTROLLERS
            )

        assert len(self.manager.controllers) == controller_count
        assert len(self.manager.assigned_controllers) == controller_count
        assert all(
            info.status == ControllerStatus.ASSIGNED for info in self.manager.controllers.values()
        )

        for index in range(controller_count):
            self.visual_manager.add_controller_indicator(
                controller_id=index,
                instance_id=index,
                color=(255, 0, 0),
                position=(index, index),
            )
        assert len(self.visual_manager.indicators) == controller_count

        # 100 positions, each shared by 10 indicators: the collision groups hold all ten.
        for index in range(100):
            for offset in range(10):
                self.visual_manager.add_controller_indicator(
                    controller_id=index * 10 + offset,
                    instance_id=index * 10 + offset,
                    color=(255, 0, 0),
                    position=(index, index),
                )
        assert len(self.visual_manager.indicators) == controller_count
        assert len(self.visual_manager.film_strip_collision_groups) == 100
        assert all(
            len(group) == 10 for group in self.visual_manager.film_strip_collision_groups.values()
        )

    def test_error_recovery_stress(self):
        """Operations on an unknown controller answer "not found" and change nothing, every time.

        Each call must neither raise nor create state for the unknown id (a swallowing try here
        used to let any exception pass as "handled gracefully").
        """
        unknown_id = 999
        for _ in range(1000):
            # Invalid controller operations
            assert self.manager.is_controller_active(unknown_id) is False
            assert self.manager.get_controller_info(unknown_id) is None
            assert self.manager.activate_controller(unknown_id) is False

            # Invalid visual operations
            assert self.visual_manager.get_final_position(unknown_id) == (0, 0)
            self.visual_manager.remove_controller_indicator(unknown_id)
            self.visual_manager.update_controller_position(unknown_id, (0, 0))

        # System should still be functional: nothing was created for the unknown id
        assert unknown_id not in self.manager.controllers
        assert unknown_id not in self.manager.assigned_controllers
        assert self.visual_manager.get_controller_indicator(unknown_id) is None
        assert self.visual_manager.get_all_indicators() == []

    def test_mixed_workload_stress(self):
        """Test mixed workload under stress."""
        # Set up controllers
        for i in range(10):
            instance_id = i
            self.manager.controllers[instance_id] = self._mocker.Mock()
            self.manager.assigned_controllers[instance_id] = i
            self.controller_selections[i] = ControllerSelection(i, instance_id)
            self.controller_selections[i].activate()

        # Mixed operations
        for cycle in range(100):
            # Navigation operations
            for i in range(10):
                self.controller_selections[i].set_selection(f'animation_{i}', cycle % 50)

            # Visual operations
            for i in range(10):
                self.visual_manager.add_controller_indicator(
                    controller_id=i,
                    instance_id=i,
                    color=(255, 0, 0),
                    position=(i * 10, cycle * 10),
                )

            # Manager operations
            for i in range(10):
                self.manager.update_controller_activity(i)

            # Clean up visual indicators
            if cycle % 10 == 0:
                self.visual_manager.clear_all_indicators()

        # Verify final state
        for i in range(10):
            assert self.controller_selections[i].is_active()
            animation, frame = self.controller_selections[i].get_selection()
            assert animation == f'animation_{i}'
            assert frame == 49  # Last cycle: 99 % 50 = 49
