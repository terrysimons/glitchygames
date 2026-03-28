"""Tests for multi-controller performance and coverage."""

import time

import pytest

from glitchygames.bitmappy.controllers.performance import (
    CachedPositionManager,
    MemoryManager,
    MultiControllerPerformanceOptimizer,
    OptimizedVisualCollisionManager,
    PerformanceMetrics,
    PerformanceMonitor,
)
from glitchygames.bitmappy.controllers.selection import ControllerSelection
from glitchygames.bitmappy.indicators.collision import VisualCollisionManager


class TestPerformanceMetrics:
    """Tests for the PerformanceMetrics dataclass."""

    def test_default_values(self):
        """Test default initialization values."""
        metrics = PerformanceMetrics()
        assert metrics.operation_count == 0
        assert metrics.total_time == pytest.approx(0.0)
        assert metrics.average_time == pytest.approx(0.0)
        assert metrics.max_time == pytest.approx(0.0)
        assert metrics.min_time == float('inf')
        assert metrics.last_operation == pytest.approx(0.0)


class TestPerformanceMonitor:
    """Tests for the PerformanceMonitor class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.monitor = PerformanceMonitor()

    def test_initialization(self):
        """Test monitor initializes with empty state."""
        assert self.monitor.metrics == {}
        assert self.monitor.operation_history == {}

    def test_record_single_operation(self):
        """Test recording a single operation."""
        self.monitor.record_operation('test_op', 0.5)

        stats = self.monitor.get_operation_stats('test_op')
        assert stats is not None
        assert stats.operation_count == 1
        assert stats.total_time == pytest.approx(0.5)
        assert stats.average_time == pytest.approx(0.5)
        assert stats.max_time == pytest.approx(0.5)
        assert stats.min_time == pytest.approx(0.5)

    def test_record_multiple_operations(self):
        """Test recording multiple operations updates stats correctly."""
        self.monitor.record_operation('test_op', 0.1)
        self.monitor.record_operation('test_op', 0.3)
        self.monitor.record_operation('test_op', 0.2)

        stats = self.monitor.get_operation_stats('test_op')
        assert stats is not None
        assert stats.operation_count == 3
        assert stats.total_time == pytest.approx(0.6)
        assert stats.average_time == pytest.approx(0.2)
        assert stats.max_time == pytest.approx(0.3)
        assert stats.min_time == pytest.approx(0.1)

    def test_get_operation_stats_unknown(self):
        """Test getting stats for unknown operation returns None."""
        result = self.monitor.get_operation_stats('nonexistent')
        assert result is None

    def test_get_all_stats(self):
        """Test getting all operation stats."""
        self.monitor.record_operation('op_a', 0.1)
        self.monitor.record_operation('op_b', 0.2)

        all_stats = self.monitor.get_all_stats()
        assert 'op_a' in all_stats
        assert 'op_b' in all_stats
        assert len(all_stats) == 2

    def test_reset_specific_operation(self):
        """Test resetting stats for a specific operation."""
        self.monitor.record_operation('op_a', 0.1)
        self.monitor.record_operation('op_b', 0.2)

        self.monitor.reset_stats('op_a')

        assert self.monitor.get_operation_stats('op_a') is None
        assert self.monitor.get_operation_stats('op_b') is not None

    def test_reset_all_stats(self):
        """Test resetting all stats."""
        self.monitor.record_operation('op_a', 0.1)
        self.monitor.record_operation('op_b', 0.2)

        self.monitor.reset_stats()

        assert self.monitor.get_all_stats() == {}

    def test_reset_nonexistent_operation(self):
        """Test resetting a nonexistent operation does not raise."""
        self.monitor.reset_stats('nonexistent')
        # Should not raise

    def test_operation_history_is_bounded(self):
        """Test that operation history has a maximum length."""
        for i in range(1100):
            self.monitor.record_operation('test_op', float(i))

        assert len(self.monitor.operation_history['test_op']) <= 1000

    def test_last_operation_timestamp(self):
        """Test that last_operation time is recorded."""
        before = time.time()
        self.monitor.record_operation('test_op', 0.1)
        after = time.time()

        stats = self.monitor.get_operation_stats('test_op')
        assert stats is not None
        assert before <= stats.last_operation <= after


class TestCachedPositionManager:
    """Tests for the CachedPositionManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cache = CachedPositionManager(cache_size=5)

    def test_initialization(self):
        """Test cache initializes empty."""
        assert self.cache.cache == {}
        assert self.cache.cache_size == 5

    def test_set_and_get_position(self):
        """Test setting and retrieving a cached position."""
        self.cache.set_position(0, 'walk', 1, (100, 200))
        result = self.cache.get_position(0, 'walk', 1)
        assert result == (100, 200)

    def test_get_nonexistent_position(self):
        """Test getting a position that is not cached returns None."""
        result = self.cache.get_position(0, 'walk', 1)
        assert result is None

    def test_cache_eviction_when_full(self):
        """Test that oldest entry is evicted when cache is full."""
        # Fill cache to capacity
        for i in range(5):
            self.cache.set_position(i, 'anim', 0, (i * 10, i * 10))

        # Add one more to trigger eviction
        self.cache.set_position(5, 'anim', 0, (50, 50))

        # Cache should still be at capacity
        stats = self.cache.get_cache_stats()
        assert stats['cache_size'] <= 5

    def test_clear_cache(self):
        """Test clearing the cache."""
        self.cache.set_position(0, 'walk', 0, (10, 20))
        self.cache.set_position(1, 'run', 0, (30, 40))

        self.cache.clear_cache()

        assert self.cache.get_position(0, 'walk', 0) is None
        assert self.cache.get_position(1, 'run', 0) is None

    def test_get_cache_stats(self):
        """Test getting cache statistics."""
        self.cache.set_position(0, 'walk', 0, (10, 20))

        stats = self.cache.get_cache_stats()
        assert stats['cache_size'] == 1
        assert stats['max_cache_size'] == 5
        assert stats['cache_utilization'] == pytest.approx(0.2)

    def test_access_time_updated_on_get(self):
        """Test that access time is updated when position is retrieved."""
        self.cache.set_position(0, 'walk', 0, (10, 20))
        initial_time = self.cache.access_times.copy()

        # Small delay to ensure time difference
        time.sleep(0.01)

        self.cache.get_position(0, 'walk', 0)

        # Access time should be updated for the accessed key
        key = (0, hash('walk'), 0)
        assert self.cache.access_times[key] >= initial_time[key]

    def test_evict_oldest_empty_cache(self):
        """Test evicting from an empty cache does not raise."""
        self.cache._evict_oldest()
        # Should not raise


class TestMemoryManager:
    """Tests for the MemoryManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.memory_manager = MemoryManager()

    def test_initialization(self):
        """Test memory manager initializes correctly."""
        assert self.memory_manager.weak_refs == {}
        assert self.memory_manager.cleanup_threshold == 1000

    def test_register_object(self):
        """Test registering an object for tracking."""
        # weakref.ref requires objects that support weak references (not plain dicts)
        test_object = type('WeakRefable', (), {'key': 'value'})()
        self.memory_manager.register_object(1, test_object)

        assert 1 in self.memory_manager.weak_refs
        assert self.memory_manager.weak_refs[1]() is test_object

    def test_cleanup_dead_objects(self):
        """Test cleaning up objects that have been garbage collected."""
        # Create and register an object, then let it be collected
        test_object = type('TempObj', (), {})()
        self.memory_manager.register_object(1, test_object)

        # The object is still alive
        cleaned = self.memory_manager.cleanup_dead_objects()
        assert cleaned == 0

        # Delete the reference so it can be garbage collected
        del test_object

        # Now cleanup should find the dead reference
        cleaned = self.memory_manager.cleanup_dead_objects()
        assert cleaned == 1
        assert 1 not in self.memory_manager.weak_refs

    def test_get_memory_stats(self):
        """Test getting memory statistics."""
        test_object = type('WeakRefable', (), {'key': 'value'})()
        self.memory_manager.register_object(1, test_object)

        stats = self.memory_manager.get_memory_stats()
        assert stats['registered_objects'] == 1
        assert stats['cleanup_threshold'] == 1000
        assert stats['needs_cleanup'] is False

    def test_needs_cleanup_flag(self):
        """Test the needs_cleanup flag triggers at threshold."""
        self.memory_manager.cleanup_threshold = 2

        obj1 = type('TempObj1', (), {})()
        obj2 = type('TempObj2', (), {})()
        obj3 = type('TempObj3', (), {})()
        self.memory_manager.register_object(1, obj1)
        self.memory_manager.register_object(2, obj2)
        self.memory_manager.register_object(3, obj3)

        stats = self.memory_manager.get_memory_stats()
        assert stats['needs_cleanup'] is True


@pytest.fixture
def visual_collision_manager():
    """Create a VisualCollisionManager instance for testing.

    Returns:
        VisualCollisionManager instance.

    """
    return VisualCollisionManager()


@pytest.fixture
def optimized_visual_manager(visual_collision_manager):
    """Create an OptimizedVisualCollisionManager instance for testing.

    Returns:
        OptimizedVisualCollisionManager wrapping the base manager.

    """
    return OptimizedVisualCollisionManager(visual_collision_manager)


@pytest.fixture
def controller_selections():
    """Create a dict of ControllerSelection instances for testing.

    Returns:
        Dict mapping controller IDs to ControllerSelection instances.

    """
    selections = {}
    for controller_id in range(2):
        selection = ControllerSelection(
            controller_id=controller_id,
            instance_id=controller_id,
        )
        selections[controller_id] = selection
    return selections


@pytest.fixture
def multi_controller_manager(mocker):
    """Create a mock MultiControllerManager for testing.

    Returns:
        Mock MultiControllerManager instance.

    """
    return mocker.Mock()


@pytest.fixture
def performance_optimizer(
    multi_controller_manager,
    visual_collision_manager,
    controller_selections,
):
    """Create a MultiControllerPerformanceOptimizer instance for testing.

    Returns:
        MultiControllerPerformanceOptimizer configured with test fixtures.

    """
    return MultiControllerPerformanceOptimizer(
        manager=multi_controller_manager,
        visual_manager=visual_collision_manager,
        controller_selections=controller_selections,
    )


class TestOptimizedVisualCollisionManagerInit:
    """Tests for OptimizedVisualCollisionManager initialization."""

    def test_initialization(self, visual_collision_manager):
        """Test that the optimized manager initializes with correct defaults."""
        optimized_manager = OptimizedVisualCollisionManager(visual_collision_manager)

        assert optimized_manager.base_manager is visual_collision_manager
        assert optimized_manager.enable_caching is True
        assert optimized_manager.enable_optimization is True
        assert optimized_manager.update_throttle == pytest.approx(0.016)
        assert optimized_manager.last_update_time == 0
        assert optimized_manager.pending_updates == {}

    def test_has_performance_components(self, optimized_visual_manager):
        """Test that performance components are initialized."""
        assert isinstance(optimized_visual_manager.position_cache, CachedPositionManager)
        assert isinstance(optimized_visual_manager.performance_monitor, PerformanceMonitor)
        assert isinstance(optimized_visual_manager.memory_manager, MemoryManager)


class TestOptimizedVisualCollisionManagerAddIndicator:
    """Tests for add_controller_indicator on OptimizedVisualCollisionManager."""

    def test_add_controller_indicator_delegates_to_base(self, optimized_visual_manager):
        """Test that add_controller_indicator calls the base manager."""
        optimized_visual_manager.add_controller_indicator(
            controller_id=0,
            instance_id=0,
            color=(255, 0, 0),
            position=(10, 20),
        )

        # Verify the base manager received the indicator
        assert 0 in optimized_visual_manager.base_manager.indicators

    def test_add_controller_indicator_caches_position(self, optimized_visual_manager):
        """Test that position is cached when caching is enabled."""
        optimized_visual_manager.add_controller_indicator(
            controller_id=0,
            instance_id=0,
            color=(255, 0, 0),
            position=(10, 20),
        )

        cached_position = optimized_visual_manager.position_cache.get_position(0, 'default', 0)
        assert cached_position == (10, 20)

    def test_add_controller_indicator_no_cache_when_disabled(self, optimized_visual_manager):
        """Test that position is not cached when caching is disabled."""
        optimized_visual_manager.enable_caching = False

        optimized_visual_manager.add_controller_indicator(
            controller_id=0,
            instance_id=0,
            color=(255, 0, 0),
            position=(10, 20),
        )

        cached_position = optimized_visual_manager.position_cache.get_position(0, 'default', 0)
        assert cached_position is None

    def test_add_controller_indicator_records_performance(self, optimized_visual_manager):
        """Test that performance is recorded for add_controller_indicator."""
        optimized_visual_manager.add_controller_indicator(
            controller_id=0,
            instance_id=0,
            color=(255, 0, 0),
            position=(10, 20),
        )

        stats = optimized_visual_manager.performance_monitor.get_operation_stats(
            'add_controller_indicator',
        )
        assert stats is not None
        assert stats.operation_count == 1


class TestOptimizedVisualCollisionManagerUpdatePosition:
    """Tests for update_controller_position on OptimizedVisualCollisionManager."""

    def test_update_position_not_throttled(self, optimized_visual_manager):
        """Test update when not throttled (first update or past throttle window)."""
        # Add an indicator first
        optimized_visual_manager.add_controller_indicator(
            controller_id=0,
            instance_id=0,
            color=(255, 0, 0),
            position=(10, 20),
        )

        # First update should go through since last_update_time is 0
        optimized_visual_manager.update_controller_position(0, (30, 40))

        # Performance should be recorded
        stats = optimized_visual_manager.performance_monitor.get_operation_stats(
            'update_controller_position',
        )
        assert stats is not None
        assert stats.operation_count == 1

    def test_update_position_throttled(self, optimized_visual_manager):
        """Test that updates are throttled when occurring too rapidly."""
        optimized_visual_manager.add_controller_indicator(
            controller_id=0,
            instance_id=0,
            color=(255, 0, 0),
            position=(10, 20),
        )

        # Force last_update_time to be very recent (simulate recent update)
        optimized_visual_manager.last_update_time = time.time()

        # This update should be throttled (stored as pending)
        optimized_visual_manager.update_controller_position(0, (30, 40))

        # Should be in pending updates
        assert 0 in optimized_visual_manager.pending_updates
        assert optimized_visual_manager.pending_updates[0] == (30, 40)

    def test_pending_updates_processed_on_next_unthrottled_update(self, optimized_visual_manager):
        """Test that pending updates are processed when throttle window passes."""
        optimized_visual_manager.add_controller_indicator(
            controller_id=0,
            instance_id=0,
            color=(255, 0, 0),
            position=(10, 20),
        )
        optimized_visual_manager.add_controller_indicator(
            controller_id=1,
            instance_id=1,
            color=(0, 255, 0),
            position=(50, 60),
        )

        # Force a recent update time to trigger throttling
        optimized_visual_manager.last_update_time = time.time()

        # These should be throttled
        optimized_visual_manager.update_controller_position(0, (30, 40))
        assert len(optimized_visual_manager.pending_updates) == 1

        # Now set last_update_time far enough in the past to bypass throttle
        optimized_visual_manager.last_update_time = 0

        # This update should process pending updates first, then the new one
        optimized_visual_manager.update_controller_position(1, (70, 80))

        # Pending updates should be cleared
        assert len(optimized_visual_manager.pending_updates) == 0

    def test_update_position_caches_when_enabled(self, optimized_visual_manager):
        """Test that position update is cached when caching enabled."""
        optimized_visual_manager.add_controller_indicator(
            controller_id=0,
            instance_id=0,
            color=(255, 0, 0),
            position=(10, 20),
        )

        # Ensure update goes through (not throttled)
        optimized_visual_manager.last_update_time = 0
        optimized_visual_manager.update_controller_position(0, (50, 60))

        cached_position = optimized_visual_manager.position_cache.get_position(0, 'default', 0)
        assert cached_position == (50, 60)

    def test_update_position_no_cache_when_disabled(self, optimized_visual_manager):
        """Test that position update is not cached when caching disabled."""
        optimized_visual_manager.enable_caching = False

        optimized_visual_manager.add_controller_indicator(
            controller_id=0,
            instance_id=0,
            color=(255, 0, 0),
            position=(10, 20),
        )

        # Clear any cache that was set during add
        optimized_visual_manager.position_cache.clear_cache()

        optimized_visual_manager.last_update_time = 0
        optimized_visual_manager.update_controller_position(0, (50, 60))

        cached_position = optimized_visual_manager.position_cache.get_position(0, 'default', 0)
        assert cached_position is None


class TestOptimizedVisualCollisionManagerOptimize:
    """Tests for optimize_positioning on OptimizedVisualCollisionManager."""

    def test_optimize_positioning_calls_base_manager(self, optimized_visual_manager):
        """Test that optimize_positioning delegates to the base manager."""
        # Should not raise
        optimized_visual_manager.optimize_positioning()

        stats = optimized_visual_manager.performance_monitor.get_operation_stats(
            'optimize_positioning',
        )
        assert stats is not None
        assert stats.operation_count == 1

    def test_optimize_positioning_cleans_up_memory_when_needed(self, optimized_visual_manager):
        """Test that memory cleanup is triggered when threshold exceeded."""
        # Lower the threshold to trigger cleanup
        optimized_visual_manager.memory_manager.cleanup_threshold = 0

        optimized_visual_manager.optimize_positioning()

        stats = optimized_visual_manager.performance_monitor.get_operation_stats(
            'optimize_positioning',
        )
        assert stats.operation_count == 1


class TestOptimizedVisualCollisionManagerStats:
    """Tests for statistics and configuration on OptimizedVisualCollisionManager."""

    def test_get_performance_stats(self, optimized_visual_manager):
        """Test getting comprehensive performance statistics."""
        stats = optimized_visual_manager.get_performance_stats()

        assert 'performance_metrics' in stats
        assert 'cache_stats' in stats
        assert 'memory_stats' in stats
        assert 'pending_updates' in stats
        assert stats['pending_updates'] == 0

    def test_get_performance_stats_after_operations(self, optimized_visual_manager):
        """Test that stats reflect performed operations."""
        optimized_visual_manager.add_controller_indicator(
            controller_id=0,
            instance_id=0,
            color=(255, 0, 0),
            position=(10, 20),
        )

        stats = optimized_visual_manager.get_performance_stats()

        assert stats['cache_stats']['cache_size'] == 1

    def test_reset_performance_stats(self, optimized_visual_manager):
        """Test resetting performance statistics."""
        optimized_visual_manager.add_controller_indicator(
            controller_id=0,
            instance_id=0,
            color=(255, 0, 0),
            position=(10, 20),
        )

        optimized_visual_manager.reset_performance_stats()

        stats = optimized_visual_manager.get_performance_stats()
        assert stats['performance_metrics'] == {}
        assert stats['cache_stats']['cache_size'] == 0

    def test_set_performance_options(self, optimized_visual_manager):
        """Test setting performance optimization options."""
        optimized_visual_manager.set_performance_options(
            enable_caching=False,
            enable_optimization=False,
            update_throttle=0.033,
        )

        assert optimized_visual_manager.enable_caching is False
        assert optimized_visual_manager.enable_optimization is False
        assert optimized_visual_manager.update_throttle == pytest.approx(0.033)

    def test_set_performance_options_defaults(self, optimized_visual_manager):
        """Test that set_performance_options has correct defaults."""
        optimized_visual_manager.set_performance_options()

        assert optimized_visual_manager.enable_caching is True
        assert optimized_visual_manager.enable_optimization is True
        assert optimized_visual_manager.update_throttle == pytest.approx(0.016)


class TestMultiControllerPerformanceOptimizerInit:
    """Tests for MultiControllerPerformanceOptimizer initialization."""

    def test_initialization(self, performance_optimizer, multi_controller_manager):
        """Test that the optimizer initializes with correct components."""
        assert performance_optimizer.manager is multi_controller_manager
        assert isinstance(performance_optimizer.performance_monitor, PerformanceMonitor)
        assert isinstance(performance_optimizer.memory_manager, MemoryManager)
        assert isinstance(
            performance_optimizer.optimized_visual_manager,
            OptimizedVisualCollisionManager,
        )
        assert performance_optimizer.auto_cleanup_interval == 300


class TestMultiControllerPerformanceOptimizerOptimize:
    """Tests for optimize_system on MultiControllerPerformanceOptimizer."""

    def test_optimize_system_returns_results(self, performance_optimizer):
        """Test that optimize_system returns a results dictionary."""
        results = performance_optimizer.optimize_system()

        assert 'controllers_cleaned' in results
        assert 'memory_cleaned' in results
        assert 'cache_cleared' in results
        assert 'performance_improved' in results
        assert results['cache_cleared'] == 1

    def test_optimize_system_performance_improved_flag(self, performance_optimizer):
        """Test that performance_improved is True when any cleanup occurred."""
        results = performance_optimizer.optimize_system()

        # cache_cleared is always 1, so performance_improved should always be True
        assert results['performance_improved'] is True

    def test_optimize_system_records_performance(self, performance_optimizer):
        """Test that optimization is recorded in performance metrics."""
        performance_optimizer.optimize_system()

        stats = performance_optimizer.performance_monitor.get_operation_stats('optimize_system')
        assert stats is not None
        assert stats.operation_count == 1

    def test_optimize_system_cleans_inactive_controllers(
        self,
        performance_optimizer,
        controller_selections,
    ):
        """Test that inactive controllers are cleaned up."""
        # All controllers start as inactive (is_active defaults to False)
        results = performance_optimizer.optimize_system()

        assert results['controllers_cleaned'] == 2
        assert len(performance_optimizer.controller_selections) == 0

    def test_optimize_system_keeps_active_controllers(
        self,
        performance_optimizer,
        controller_selections,
    ):
        """Test that active controllers are not cleaned up."""
        # Mark controller 0 as active
        controller_selections[0].state.is_active = True

        results = performance_optimizer.optimize_system()

        # Only controller 1 (inactive) should be cleaned
        assert results['controllers_cleaned'] == 1
        assert 0 in performance_optimizer.controller_selections
        assert 1 not in performance_optimizer.controller_selections


class TestMultiControllerPerformanceOptimizerCleanupInactive:
    """Tests for _cleanup_inactive_controllers."""

    def test_cleanup_removes_indicators_from_visual_manager(
        self,
        performance_optimizer,
        visual_collision_manager,
        controller_selections,
    ):
        """Test that cleanup removes indicators from the visual collision manager."""
        # Add indicators for controllers
        visual_collision_manager.add_controller_indicator(
            controller_id=0,
            instance_id=0,
            color=(255, 0, 0),
            position=(10, 10),
        )

        # Controller 0 is inactive by default, so it should be cleaned up
        cleaned_count = performance_optimizer._cleanup_inactive_controllers()

        assert cleaned_count == 2
        assert 0 not in visual_collision_manager.indicators

    def test_cleanup_no_inactive_controllers(self, performance_optimizer, controller_selections):
        """Test cleanup when all controllers are active."""
        for selection in controller_selections.values():
            selection.state.is_active = True

        cleaned_count = performance_optimizer._cleanup_inactive_controllers()

        assert cleaned_count == 0
        assert len(performance_optimizer.controller_selections) == 2


class TestMultiControllerPerformanceOptimizerStats:
    """Tests for get_system_performance_stats."""

    def test_get_system_performance_stats(self, performance_optimizer, controller_selections):
        """Test getting comprehensive system stats."""
        # Mark one controller as active
        controller_selections[0].state.is_active = True

        stats = performance_optimizer.get_system_performance_stats()

        assert 'performance_metrics' in stats
        assert 'visual_manager_stats' in stats
        assert 'memory_stats' in stats
        assert stats['controller_count'] == 2
        assert stats['active_controllers'] == 1

    def test_get_system_performance_stats_all_active(
        self,
        performance_optimizer,
        controller_selections,
    ):
        """Test system stats when all controllers are active."""
        for selection in controller_selections.values():
            selection.state.is_active = True

        stats = performance_optimizer.get_system_performance_stats()

        assert stats['active_controllers'] == 2

    def test_get_system_performance_stats_none_active(self, performance_optimizer):
        """Test system stats when no controllers are active."""
        stats = performance_optimizer.get_system_performance_stats()

        assert stats['active_controllers'] == 0


class TestMultiControllerPerformanceOptimizerAutoOptimize:
    """Tests for auto_optimize_if_needed."""

    def test_auto_optimize_when_interval_passed(self, performance_optimizer):
        """Test that auto optimization triggers when interval has passed."""
        # Set last cleanup time far in the past
        performance_optimizer.last_cleanup_time = time.time() - 600

        result = performance_optimizer.auto_optimize_if_needed()

        assert result is True

    def test_auto_optimize_skips_when_interval_not_passed(self, performance_optimizer):
        """Test that auto optimization is skipped when interval has not passed."""
        # Set last cleanup time to now
        performance_optimizer.last_cleanup_time = time.time()

        result = performance_optimizer.auto_optimize_if_needed()

        assert result is False

    def test_auto_optimize_updates_last_cleanup_time(self, performance_optimizer):
        """Test that last_cleanup_time is updated after optimization."""
        performance_optimizer.last_cleanup_time = time.time() - 600
        before_time = time.time()

        performance_optimizer.auto_optimize_if_needed()

        assert performance_optimizer.last_cleanup_time >= before_time


class TestCachedPositionManagerEdgeCases:
    """Additional edge case tests for CachedPositionManager."""

    def test_overwrite_existing_position(self):
        """Test that setting a position for an existing key overwrites it."""
        cache = CachedPositionManager(cache_size=5)
        cache.set_position(0, 'walk', 0, (10, 20))
        cache.set_position(0, 'walk', 0, (30, 40))

        result = cache.get_position(0, 'walk', 0)
        assert result == (30, 40)

    def test_different_animations_same_controller(self):
        """Test caching positions for different animations on same controller."""
        cache = CachedPositionManager(cache_size=10)
        cache.set_position(0, 'walk', 0, (10, 20))
        cache.set_position(0, 'run', 0, (30, 40))

        assert cache.get_position(0, 'walk', 0) == (10, 20)
        assert cache.get_position(0, 'run', 0) == (30, 40)

    def test_different_frames_same_animation(self):
        """Test caching positions for different frames of same animation."""
        cache = CachedPositionManager(cache_size=10)
        cache.set_position(0, 'walk', 0, (10, 20))
        cache.set_position(0, 'walk', 1, (30, 40))

        assert cache.get_position(0, 'walk', 0) == (10, 20)
        assert cache.get_position(0, 'walk', 1) == (30, 40)

    def test_eviction_removes_least_recently_accessed(self):
        """Test that LRU eviction removes the oldest-accessed entry."""
        cache = CachedPositionManager(cache_size=3)

        cache.set_position(0, 'anim', 0, (10, 10))
        cache.set_position(1, 'anim', 0, (20, 20))
        cache.set_position(2, 'anim', 0, (30, 30))

        # Access controller 0 to make it recently used
        cache.get_position(0, 'anim', 0)

        # Adding a 4th should evict controller 1 (oldest access)
        cache.set_position(3, 'anim', 0, (40, 40))

        # Controller 0 should still be cached (was recently accessed)
        assert cache.get_position(0, 'anim', 0) is not None
        # Controller 3 was just added
        assert cache.get_position(3, 'anim', 0) == (40, 40)


class TestMemoryManagerEdgeCases:
    """Additional edge case tests for MemoryManager."""

    def test_cleanup_with_no_registered_objects(self):
        """Test cleanup when no objects have been registered."""
        memory_manager = MemoryManager()
        cleaned = memory_manager.cleanup_dead_objects()
        assert cleaned == 0

    def test_register_multiple_objects(self):
        """Test registering multiple objects."""
        memory_manager = MemoryManager()
        object_a = type('ObjA', (), {})()
        object_b = type('ObjB', (), {})()

        memory_manager.register_object(1, object_a)
        memory_manager.register_object(2, object_b)

        stats = memory_manager.get_memory_stats()
        assert stats['registered_objects'] == 2

    def test_cleanup_partial_dead_objects(self):
        """Test cleanup when only some objects are dead."""
        memory_manager = MemoryManager()

        alive_object = type('AliveObj', (), {})()
        dead_object = type('DeadObj', (), {})()

        memory_manager.register_object(1, alive_object)
        memory_manager.register_object(2, dead_object)

        # Kill one reference
        del dead_object

        cleaned = memory_manager.cleanup_dead_objects()
        assert cleaned == 1
        assert 1 in memory_manager.weak_refs
        assert 2 not in memory_manager.weak_refs
