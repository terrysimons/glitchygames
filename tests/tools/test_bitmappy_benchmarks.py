"""Bitmappy's benchmarks (split from tests/benchmarks/test_benchmarks.py; they move with Bitmappy).

Run benchmarks:
    pytest tests/tools/test_bitmappy_benchmarks.py --benchmark-only
    nox -s performance_test
"""

from glitchygames.bitmappy.controllers.selection import ControllerSelection
from glitchygames.bitmappy.indicators.collision import VisualCollisionManager


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
