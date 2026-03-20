"""Tests for multi-controller performance optimizations."""

import time

import pytest

from glitchygames.tools.multi_controller_performance import (
    CachedPositionManager,
    MemoryManager,
    PerformanceMetrics,
    PerformanceMonitor,
)


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
