"""Bitmappy's benchmarks (split from tests/benchmarks/test_benchmarks.py; they move with Bitmappy).

Run benchmarks:
    pytest src/apps/bitmappy/tests/test_bitmappy_benchmarks.py --benchmark-only
    nox -s performance_test
"""

from bitmappy.controllers.manager import ControllerInfo, ControllerStatus, MultiControllerManager
from bitmappy.controllers.selection import ControllerSelection
from bitmappy.indicators.collision import VisualCollisionManager


# ---------------------------------------------------------------------------
# Controller selection benchmarks
# ---------------------------------------------------------------------------
class TestControllerSelectionBenchmarks:
    """Benchmark ControllerSelection operations."""

    def test_selection_set_and_get(self, benchmark):
        """Benchmark rapid selection changes."""
        selection = ControllerSelection(0, 0)
        selection.activate()

        call_count = 0

        def set_selection():
            nonlocal call_count
            selection.set_selection(f'animation_{call_count % 10}', call_count % 50)
            call_count += 1

        benchmark(set_selection)

    def test_selection_frame_preservation(self, benchmark):
        """Benchmark frame preservation during animation switching."""
        selection = ControllerSelection(0, 0)
        selection.activate()

        # Build up navigation history
        for i in range(20):
            selection.set_selection(f'animation_{i % 5}', i % 10)

        call_count = 0

        def preserve_frame():
            nonlocal call_count
            selection.preserve_frame_for_animation(
                f'animation_{call_count % 5}',
                available_frames=20,
            )
            call_count += 1

        benchmark(preserve_frame)

    def test_selection_navigation_history(self, benchmark):
        """Benchmark navigation history retrieval with deep history."""
        selection = ControllerSelection(0, 0)
        selection.activate()

        # Build deep history
        for i in range(100):
            selection.set_selection(f'animation_{i % 10}', i % 50)

        benchmark(selection.get_navigation_history)

    def test_selection_state_summary(self, benchmark):
        """Benchmark state summary generation."""
        selection = ControllerSelection(0, 0)
        selection.activate()
        selection.set_selection('idle', 5)

        benchmark(selection.get_state_summary)


# ---------------------------------------------------------------------------
# Visual collision manager benchmarks
# ---------------------------------------------------------------------------
class TestVisualCollisionBenchmarks:
    """Benchmark VisualCollisionManager operations."""

    def test_add_single_indicator(self, benchmark):
        """Benchmark adding a single controller indicator."""
        manager = VisualCollisionManager()

        call_count = 0

        def add_indicator():
            nonlocal call_count
            manager.add_controller_indicator(
                controller_id=call_count % 4,
                instance_id=call_count % 4,
                color=(255, 0, 0),
                position=(call_count * 10, 0),
            )
            call_count += 1

        benchmark(add_indicator)

    def test_collision_detection_4_controllers(self, benchmark):
        """Benchmark collision group update with 4 controllers at same position."""
        manager = VisualCollisionManager()
        for i in range(4):
            manager.add_controller_indicator(
                controller_id=i,
                instance_id=i,
                color=(255, 0, 0),
                position=(100, 100),
            )

        def update_positions():
            for i in range(4):
                manager.update_controller_position(i, (100, 100))

        benchmark(update_positions)

    def test_position_update_no_collision(self, benchmark):
        """Benchmark position updates when controllers are far apart."""
        manager = VisualCollisionManager()
        for i in range(4):
            manager.add_controller_indicator(
                controller_id=i,
                instance_id=i,
                color=(255, 0, 0),
                position=(i * 100, i * 100),
            )

        call_count = 0

        def update_position():
            nonlocal call_count
            controller_id = call_count % 4
            manager.update_controller_position(
                controller_id,
                (controller_id * 100 + call_count, controller_id * 100),
            )
            call_count += 1

        benchmark(update_position)


# ---------------------------------------------------------------------------
# Bulk workload benchmark
# ---------------------------------------------------------------------------
class TestBulkWorkloadBenchmarks:
    """Time the bulk assignment and indicator workload of the stress test."""

    def test_bulk_assignment_and_indicators(self, benchmark):
        """Benchmark 1000 assignments, 1000 indicator adds and 1000 colliding indicator adds.

        This is the timing that ``test_performance_benchmarks`` in
        ``test_bitmappy_multi_controller_stress.py`` used to assert as wall-clock limits
        (2 s per phase). Those limits failed intermittently on a loaded machine, so the normal
        suite now checks only the outcome
        (``test_bulk_assignment_and_indicator_outcomes``) and the time is measured here, under
        ``nox -s performance-test``. Keep this workload equal to that test's.
        """
        controller_count = 1000

        def fresh_state():
            MultiControllerManager._instance = None
            MultiControllerManager._initialized = False
            return (MultiControllerManager(), VisualCollisionManager()), {}

        def bulk_workload(manager, visual_manager):
            for instance_id in range(controller_count):
                manager.controllers[instance_id] = ControllerInfo(
                    controller_id=instance_id % manager.MAX_CONTROLLERS,
                    instance_id=instance_id,
                    status=ControllerStatus.CONNECTED,
                )
                manager.assign_controller(instance_id)
            for index in range(controller_count):
                visual_manager.add_controller_indicator(
                    controller_id=index,
                    instance_id=index,
                    color=(255, 0, 0),
                    position=(index, index),
                )
            for index in range(100):
                for offset in range(10):
                    visual_manager.add_controller_indicator(
                        controller_id=index * 10 + offset,
                        instance_id=index * 10 + offset,
                        color=(255, 0, 0),
                        position=(index, index),
                    )
            return manager, visual_manager

        manager, visual_manager = benchmark.pedantic(
            bulk_workload,
            setup=fresh_state,
            rounds=5,
        )

        # The benchmark still proves the work happened (outcome only, never time).
        assert len(manager.assigned_controllers) == controller_count
        assert len(visual_manager.film_strip_collision_groups) == 100
