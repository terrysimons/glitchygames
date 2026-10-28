"""Bitmappy's benchmarks (split from tests/benchmarks/test_benchmarks.py; they move with Bitmappy).

Run benchmarks:
    pytest src/apps/bitmappy/tests/test_bitmappy_benchmarks.py --benchmark-only
    nox -s performance_test
"""

from concurrent.futures import ThreadPoolExecutor

import pygame
import pytest

from bitmappy import SPRITE_CONFIG_DIR
from bitmappy.controllers.manager import ControllerInfo, ControllerStatus, MultiControllerManager
from bitmappy.controllers.selection import ControllerSelection
from bitmappy.indicators.collision import VisualCollisionManager
from glitchygames.display_mode import set_display_mode
from glitchygames.sprites import SpriteFactory


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


# ---------------------------------------------------------------------------
# Stress and performance workloads (timings moved out of the normal suite)
# ---------------------------------------------------------------------------
def _fresh_managers():
    """Reset the manager singleton and return a clean manager and visual manager.

    Returns:
        The (MultiControllerManager, VisualCollisionManager) pair.

    """
    MultiControllerManager._instance = None
    MultiControllerManager._initialized = False
    return MultiControllerManager(), VisualCollisionManager()


def _add_selections(*, manager, count, activate):
    """Give the manager ``count`` real controllers, each with a selection.

    Returns:
        The selections by controller id.

    """
    selections = {}
    for index in range(count):
        manager.controllers[index] = ControllerInfo(
            controller_id=index % manager.MAX_CONTROLLERS,
            instance_id=index,
            status=ControllerStatus.CONNECTED,
        )
        manager.assigned_controllers[index] = index
        selections[index] = ControllerSelection(index, index)
        if activate:
            selections[index].activate()
    return selections


class TestStressWorkloadBenchmarks:
    """Time the workloads that test_bitmappy_multi_controller_stress.py (and siblings) run.

    Each of those tests used to assert a wall-clock limit, which failed intermittently on a
    loaded machine. The normal suite now checks only their outcomes; the timings are here, under
    ``nox -s performance-test``. One benchmark covers every test that measured the same work.
    The ``time.sleep`` calls the stress tests use to provoke thread switches are left out:
    sleeping is not the code under measurement.
    """

    def test_selection_and_position_updates(self, benchmark):
        """Selection and position updates across controllers.

        Covers the stress tests ``test_maximum_controller_stress``,
        ``test_performance_with_extreme_operations`` and ``test_performance_integration``.
        """

        def setup():
            manager, visual_manager = _fresh_managers()
            selections = _add_selections(manager=manager, count=10, activate=True)
            return (selections, visual_manager), {}

        def workload(selections, visual_manager):
            for _ in range(1000):
                for index in range(10):
                    selections[index].set_selection(f'animation_{index}', index % 20)
                    visual_manager.update_controller_position(index, (index * 10, index * 10))
            return selections

        selections = benchmark.pedantic(workload, setup=setup, rounds=5)
        assert selections[9].get_selection() == ('animation_9', 9)

    def test_rapid_controller_switching(self, benchmark):
        """Activate and select across 4 controllers 1000 times.

        Covers ``test_rapid_controller_switching_stress``.
        """

        def setup():
            manager, _visual_manager = _fresh_managers()
            return (_add_selections(manager=manager, count=4, activate=False),), {}

        def workload(selections):
            for cycle in range(1000):
                for index in range(4):
                    selections[index].activate()
                    selections[index].set_selection(f'animation_{index}', cycle)
            return selections

        selections = benchmark.pedantic(workload, setup=setup, rounds=5)
        assert selections[3].get_selection() == ('animation_3', 999)

    def test_navigation_history(self, benchmark):
        """10000 selection changes on one controller.

        Covers ``test_memory_stress_with_navigation_history``.
        """

        def setup():
            selection = ControllerSelection(0, 0)
            selection.activate()
            return (selection,), {}

        def workload(selection):
            for index in range(10000):
                selection.set_selection(f'animation_{index % 100}', index % 50)
            return selection

        selection = benchmark.pedantic(workload, setup=setup, rounds=5)
        assert selection.get_selection() == ('animation_99', 49)

    def test_collision_adds_and_updates(self, benchmark):
        """50 indicators at one position, then 5000 position updates.

        Covers ``test_visual_collision_stress``, ``test_performance_with_many_indicators`` and
        ``test_collision_calculation_performance``.
        """

        def setup():
            _manager, visual_manager = _fresh_managers()
            return (visual_manager,), {}

        def workload(visual_manager):
            for index in range(50):
                visual_manager.add_controller_indicator(
                    controller_id=index,
                    instance_id=index,
                    color=(255, 0, 0),
                    position=(100, 100),
                )
            for _ in range(100):
                for index in range(50):
                    visual_manager.update_controller_position(index, (100 + index, 100 + index))
            return visual_manager

        visual_manager = benchmark.pedantic(workload, setup=setup, rounds=5)
        assert len(visual_manager.indicators) == 50

    def test_concurrent_selection_updates(self, benchmark):
        """8 threads x 100 selection updates (``test_concurrent_operations_stress``)."""

        def setup():
            manager, _visual_manager = _fresh_managers()
            return (_add_selections(manager=manager, count=8, activate=True),), {}

        def worker(selections, controller_id):
            for _ in range(100):
                selections[controller_id].set_selection(
                    f'animation_{controller_id}',
                    controller_id,
                )

        def workload(selections):
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = [executor.submit(worker, selections, index) for index in range(8)]
                for future in futures:
                    future.result()
            return selections

        selections = benchmark.pedantic(workload, setup=setup, rounds=5)
        assert selections[7].get_selection() == ('animation_7', 7)

    def test_add_and_remove_cycles(self, benchmark):
        """100 cycles of adding and removing 5 controllers (``test_system_resilience_stress``)."""

        def setup():
            return _fresh_managers(), {}

        def workload(manager, visual_manager):
            for cycle in range(100):
                for index in range(5):
                    instance_id = index + cycle * 5
                    manager.controllers[instance_id] = ControllerInfo(
                        controller_id=index % manager.MAX_CONTROLLERS,
                        instance_id=instance_id,
                        status=ControllerStatus.CONNECTED,
                    )
                    manager.assigned_controllers[instance_id] = index
                    visual_manager.add_controller_indicator(
                        controller_id=index,
                        instance_id=instance_id,
                        color=(255, 0, 0),
                        position=(index * 10, index * 10),
                    )
                for index in range(5):
                    instance_id = index + cycle * 5
                    del manager.controllers[instance_id]
                    del manager.assigned_controllers[instance_id]
                    visual_manager.remove_controller_indicator(index)
            return manager, visual_manager

        manager, visual_manager = benchmark.pedantic(workload, setup=setup, rounds=5)
        assert len(manager.controllers) == 0
        assert len(visual_manager.indicators) == 0

    def test_mixed_workload(self, benchmark):
        """Navigation, indicator and activity operations together.

        Covers ``test_mixed_workload_stress``.
        """

        def setup():
            manager, visual_manager = _fresh_managers()
            selections = _add_selections(manager=manager, count=10, activate=True)
            return (manager, visual_manager, selections), {}

        def workload(manager, visual_manager, selections):
            for cycle in range(100):
                for index in range(10):
                    selections[index].set_selection(f'animation_{index}', cycle % 50)
                    visual_manager.add_controller_indicator(
                        controller_id=index,
                        instance_id=index,
                        color=(255, 0, 0),
                        position=(index * 10, cycle * 10),
                    )
                    manager.update_controller_activity(index)
                if cycle % 10 == 0:
                    visual_manager.clear_all_indicators()
            return selections

        selections = benchmark.pedantic(workload, setup=setup, rounds=5)
        assert selections[9].get_selection() == ('animation_9', 49)

    def test_animation_loading_with_active_controllers(self, benchmark):
        """Reposition active controllers' indicators, then optimize.

        Covers ``test_load_animation_performance_impact``.
        """
        manager, visual_manager = _fresh_managers()
        selections = _add_selections(manager=manager, count=4, activate=True)
        for index in range(4):
            visual_manager.add_controller_indicator(
                controller_id=index,
                instance_id=index,
                color=(255, 0, 0),
                position=(100 + index * 10, 100 + index * 10),
            )

        def load_animation():
            for controller_id, selection in selections.items():
                if selection.is_active():
                    _animation, frame = selection.get_selection()
                    visual_manager.update_controller_position(
                        controller_id,
                        (100 + controller_id * 50, 100 + frame * 20),
                    )
            visual_manager.optimize_positioning()

        benchmark(load_animation)
        assert len(visual_manager.indicators) == 4

    def test_controller_activity_updates(self, benchmark):
        """One controller's activity stamped repeatedly (``test_rapid_event_processing``)."""
        manager, _visual_manager = _fresh_managers()
        manager.controllers[0] = ControllerInfo(
            controller_id=0,
            instance_id=0,
            status=ControllerStatus.ACTIVE,
        )
        benchmark(manager.update_controller_activity, 0)
        assert manager.controllers[0].last_activity is not None

    def test_singleton_lookup_and_color_assignment(self, benchmark):
        """The singleton lookup and the color assignment.

        Covers ``test_singleton_performance`` and ``test_color_assignment_efficiency``.
        """
        manager, _visual_manager = _fresh_managers()
        for index in range(4):
            manager.controllers[index] = ControllerInfo(
                controller_id=index,
                instance_id=index,
                status=ControllerStatus.CONNECTED,
                color=(128, 128, 128),
            )

        def lookup_and_assign():
            assert MultiControllerManager.get_instance() is manager
            for index in range(4):
                manager.assign_color_to_controller(index)

        benchmark(lookup_and_assign)
        assert manager.controllers[0].color == (255, 0, 0)


@pytest.fixture
def display():
    """Give the sprite loader a real display (as test_bitmappy_sprite_library.py does)."""
    pygame.init()
    if pygame.display.get_surface() is None:
        set_display_mode(size=(96, 64))


@pytest.mark.usefixtures('display')
class TestSpriteLibraryBenchmarks:
    """Time loading and rendering sample library sprites (``test_sprite_performance``)."""

    @pytest.mark.parametrize(
        'sprite_name',
        ['battle_axe.toml', 'berry_bush.toml', 'big_heart.toml', 'book.toml', 'colors.toml'],
    )
    def test_sprite_load_and_render(self, benchmark, sprite_name):
        """Load a library sprite and blit it onto a fresh surface."""
        sprite_file = SPRITE_CONFIG_DIR / sprite_name
        assert sprite_file.exists(), f'The named sample {sprite_name} is not in the library'

        def load_and_render():
            sprite = SpriteFactory.load_sprite(filename=str(sprite_file))
            surface = pygame.Surface(sprite.image.get_size(), depth=32)
            surface.blit(sprite.image, (0, 0))
            return surface

        surface = benchmark(load_and_render)
        assert surface.get_width() > 0
