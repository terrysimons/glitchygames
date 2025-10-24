"""
Multi-Controller Performance Optimizations

This module provides performance optimizations for the multi-controller system,
including caching, memory management, and performance monitoring.
"""

import time
import threading
from typing import Dict, List, Optional, Tuple, Any
from collections import deque
from dataclasses import dataclass
import weakref


@dataclass
class PerformanceMetrics:
    """Performance metrics for multi-controller system."""
    operation_count: int = 0
    total_time: float = 0.0
    average_time: float = 0.0
    max_time: float = 0.0
    min_time: float = float('inf')
    last_operation: float = 0.0


class PerformanceMonitor:
    """Performance monitoring for multi-controller system."""
    
    def __init__(self):
        """Initialize performance monitor."""
        self.metrics: Dict[str, PerformanceMetrics] = {}
        self.operation_history: Dict[str, deque] = {}
        self.lock = threading.Lock()
        
    def record_operation(self, operation: str, duration: float) -> None:
        """Record an operation and its duration.
        
        Args:
            operation: Operation name
            duration: Operation duration in seconds
        """
        with self.lock:
            if operation not in self.metrics:
                self.metrics[operation] = PerformanceMetrics()
                self.operation_history[operation] = deque(maxlen=1000)
            
            metrics = self.metrics[operation]
            metrics.operation_count += 1
            metrics.total_time += duration
            metrics.average_time = metrics.total_time / metrics.operation_count
            metrics.max_time = max(metrics.max_time, duration)
            metrics.min_time = min(metrics.min_time, duration)
            metrics.last_operation = time.time()
            
            # Add to history
            self.operation_history[operation].append(duration)
    
    def get_operation_stats(self, operation: str) -> Optional[PerformanceMetrics]:
        """Get performance statistics for an operation.
        
        Args:
            operation: Operation name
            
        Returns:
            PerformanceMetrics or None if operation not found
        """
        with self.lock:
            return self.metrics.get(operation)
    
    def get_all_stats(self) -> Dict[str, PerformanceMetrics]:
        """Get performance statistics for all operations.
        
        Returns:
            Dict of operation names to performance metrics
        """
        with self.lock:
            return self.metrics.copy()
    
    def reset_stats(self, operation: Optional[str] = None) -> None:
        """Reset performance statistics.
        
        Args:
            operation: Specific operation to reset, or None for all
        """
        with self.lock:
            if operation:
                if operation in self.metrics:
                    del self.metrics[operation]
                if operation in self.operation_history:
                    del self.operation_history[operation]
            else:
                self.metrics.clear()
                self.operation_history.clear()


class CachedPositionManager:
    """Cached position management for visual indicators."""
    
    def __init__(self, cache_size: int = 1000):
        """Initialize cached position manager.
        
        Args:
            cache_size: Maximum cache size
        """
        self.cache: Dict[Tuple[int, int, int], Tuple[int, int]] = {}
        self.cache_size = cache_size
        self.access_times: Dict[Tuple[int, int, int], float] = {}
        self.lock = threading.Lock()
        
    def get_position(self, controller_id: int, animation: str, frame: int) -> Optional[Tuple[int, int]]:
        """Get cached position.
        
        Args:
            controller_id: Controller ID
            animation: Animation name
            frame: Frame number
            
        Returns:
            Cached position or None if not found
        """
        key = (controller_id, hash(animation), frame)
        
        with self.lock:
            if key in self.cache:
                self.access_times[key] = time.time()
                return self.cache[key]
        
        return None
    
    def set_position(self, controller_id: int, animation: str, frame: int, position: Tuple[int, int]) -> None:
        """Set cached position.
        
        Args:
            controller_id: Controller ID
            animation: Animation name
            frame: Frame number
            position: Position to cache
        """
        key = (controller_id, hash(animation), frame)
        
        with self.lock:
            # Check cache size
            if len(self.cache) >= self.cache_size:
                self._evict_oldest()
            
            self.cache[key] = position
            self.access_times[key] = time.time()
    
    def _evict_oldest(self) -> None:
        """Evict oldest cache entry."""
        if not self.access_times:
            return
        
        oldest_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
        del self.cache[oldest_key]
        del self.access_times[oldest_key]
    
    def clear_cache(self) -> None:
        """Clear all cached positions."""
        with self.lock:
            self.cache.clear()
            self.access_times.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dict with cache statistics
        """
        with self.lock:
            return {
                'cache_size': len(self.cache),
                'max_cache_size': self.cache_size,
                'cache_utilization': len(self.cache) / self.cache_size
            }


class MemoryManager:
    """Memory management for multi-controller system."""
    
    def __init__(self):
        """Initialize memory manager."""
        self.weak_refs: Dict[int, weakref.ref] = {}
        self.memory_usage: Dict[str, int] = {}
        self.cleanup_threshold = 1000  # Cleanup when this many objects exist
        
    def register_object(self, obj_id: int, obj: Any) -> None:
        """Register an object for memory management.
        
        Args:
            obj_id: Object ID
            obj: Object to register
        """
        self.weak_refs[obj_id] = weakref.ref(obj)
    
    def cleanup_dead_objects(self) -> int:
        """Clean up dead objects.
        
        Returns:
            Number of objects cleaned up
        """
        cleaned_count = 0
        dead_objects = []
        
        for obj_id, weak_ref in self.weak_refs.items():
            if weak_ref() is None:
                dead_objects.append(obj_id)
        
        for obj_id in dead_objects:
            del self.weak_refs[obj_id]
            cleaned_count += 1
        
        return cleaned_count
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory statistics.
        
        Returns:
            Dict with memory statistics
        """
        return {
            'registered_objects': len(self.weak_refs),
            'cleanup_threshold': self.cleanup_threshold,
            'needs_cleanup': len(self.weak_refs) > self.cleanup_threshold
        }


class OptimizedVisualCollisionManager:
    """Optimized visual collision manager with performance improvements."""
    
    def __init__(self, base_manager):
        """Initialize optimized visual collision manager.
        
        Args:
            base_manager: Base visual collision manager
        """
        self.base_manager = base_manager
        self.position_cache = CachedPositionManager()
        self.performance_monitor = PerformanceMonitor()
        self.memory_manager = MemoryManager()
        
        # Performance optimization flags
        self.enable_caching = True
        self.enable_optimization = True
        self.update_throttle = 0.016  # 60 FPS max
        
        # Throttling
        self.last_update_time = 0
        self.pending_updates: Dict[int, Tuple[int, int]] = {}
        
    def add_controller_indicator(self, controller_id: int, instance_id: int, 
                                color: Tuple[int, int, int], position: Tuple[int, int]) -> None:
        """Add controller indicator with performance optimization.
        
        Args:
            controller_id: Controller ID
            instance_id: Instance ID
            color: Color tuple
            position: Position tuple
        """
        start_time = time.time()
        
        # Use base manager
        self.base_manager.add_controller_indicator(controller_id, instance_id, color, position)
        
        # Cache position if enabled
        if self.enable_caching:
            self.position_cache.set_position(controller_id, "default", 0, position)
        
        # Record performance
        duration = time.time() - start_time
        self.performance_monitor.record_operation('add_controller_indicator', duration)
    
    def update_controller_position(self, controller_id: int, position: Tuple[int, int]) -> None:
        """Update controller position with performance optimization.
        
        Args:
            controller_id: Controller ID
            position: New position
        """
        start_time = time.time()
        
        # Throttle updates
        current_time = time.time()
        if current_time - self.last_update_time < self.update_throttle:
            # Store pending update
            self.pending_updates[controller_id] = position
            return
        
        # Process pending updates
        if self.pending_updates:
            for cid, pos in self.pending_updates.items():
                self.base_manager.update_controller_position(cid, pos)
            self.pending_updates.clear()
        
        # Update position
        self.base_manager.update_controller_position(controller_id, position)
        
        # Cache position if enabled
        if self.enable_caching:
            self.position_cache.set_position(controller_id, "default", 0, position)
        
        self.last_update_time = current_time
        
        # Record performance
        duration = time.time() - start_time
        self.performance_monitor.record_operation('update_controller_position', duration)
    
    def optimize_positioning(self) -> None:
        """Optimize positioning with performance monitoring.
        
        Returns:
            Optimization results
        """
        start_time = time.time()
        
        # Use base manager optimization
        self.base_manager.optimize_positioning()
        
        # Clean up memory if needed
        if self.memory_manager.get_memory_stats()['needs_cleanup']:
            cleaned = self.memory_manager.cleanup_dead_objects()
            print(f"DEBUG: Cleaned up {cleaned} dead objects")
        
        # Record performance
        duration = time.time() - start_time
        self.performance_monitor.record_operation('optimize_positioning', duration)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics.
        
        Returns:
            Dict with performance statistics
        """
        stats = {
            'performance_metrics': self.performance_monitor.get_all_stats(),
            'cache_stats': self.position_cache.get_cache_stats(),
            'memory_stats': self.memory_manager.get_memory_stats(),
            'pending_updates': len(self.pending_updates)
        }
        
        return stats
    
    def reset_performance_stats(self) -> None:
        """Reset performance statistics."""
        self.performance_monitor.reset_stats()
        self.position_cache.clear_cache()
    
    def set_performance_options(self, enable_caching: bool = True, 
                               enable_optimization: bool = True,
                               update_throttle: float = 0.016) -> None:
        """Set performance optimization options.
        
        Args:
            enable_caching: Enable position caching
            enable_optimization: Enable optimization features
            update_throttle: Update throttle in seconds
        """
        self.enable_caching = enable_caching
        self.enable_optimization = enable_optimization
        self.update_throttle = update_throttle


class MultiControllerPerformanceOptimizer:
    """Main performance optimizer for multi-controller system."""
    
    def __init__(self, manager, visual_manager, controller_selections):
        """Initialize performance optimizer.
        
        Args:
            manager: MultiControllerManager instance
            visual_manager: VisualCollisionManager instance
            controller_selections: Controller selections dict
        """
        self.manager = manager
        self.visual_manager = visual_manager
        self.controller_selections = controller_selections
        
        # Performance components
        self.performance_monitor = PerformanceMonitor()
        self.memory_manager = MemoryManager()
        self.optimized_visual_manager = OptimizedVisualCollisionManager(visual_manager)
        
        # Optimization settings
        self.auto_cleanup_interval = 300  # 5 minutes
        self.last_cleanup_time = time.time()
        
    def optimize_system(self) -> Dict[str, Any]:
        """Optimize the entire multi-controller system.
        
        Returns:
            Dict with optimization results
        """
        start_time = time.time()
        results = {
            'controllers_cleaned': 0,
            'memory_cleaned': 0,
            'cache_cleared': 0,
            'performance_improved': False
        }
        
        # Clean up inactive controllers
        results['controllers_cleaned'] = self._cleanup_inactive_controllers()
        
        # Clean up memory
        results['memory_cleaned'] = self.memory_manager.cleanup_dead_objects()
        
        # Clear old caches
        self.optimized_visual_manager.position_cache.clear_cache()
        results['cache_cleared'] = 1
        
        # Optimize visual manager
        self.optimized_visual_manager.optimize_positioning()
        
        # Check if performance improved
        if any(results[key] > 0 for key in ['controllers_cleaned', 'memory_cleaned', 'cache_cleared']):
            results['performance_improved'] = True
        
        # Record performance
        duration = time.time() - start_time
        self.performance_monitor.record_operation('optimize_system', duration)
        
        return results
    
    def _cleanup_inactive_controllers(self) -> int:
        """Clean up inactive controllers.
        
        Returns:
            Number of controllers cleaned up
        """
        cleaned_count = 0
        inactive_controllers = []
        
        for controller_id, selection in self.controller_selections.items():
            if not selection.is_active():
                inactive_controllers.append(controller_id)
        
        for controller_id in inactive_controllers:
            # Remove from visual manager
            if controller_id in self.visual_manager.indicators:
                self.visual_manager.remove_controller_indicator(controller_id)
            
            # Remove from controller selections
            del self.controller_selections[controller_id]
            
            cleaned_count += 1
        
        return cleaned_count
    
    def get_system_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive system performance statistics.
        
        Returns:
            Dict with system performance statistics
        """
        return {
            'performance_metrics': self.performance_monitor.get_all_stats(),
            'visual_manager_stats': self.optimized_visual_manager.get_performance_stats(),
            'memory_stats': self.memory_manager.get_memory_stats(),
            'controller_count': len(self.controller_selections),
            'active_controllers': sum(1 for s in self.controller_selections.values() if s.is_active())
        }
    
    def auto_optimize_if_needed(self) -> bool:
        """Automatically optimize if needed.
        
        Returns:
            True if optimization was performed
        """
        current_time = time.time()
        
        if current_time - self.last_cleanup_time > self.auto_cleanup_interval:
            self.optimize_system()
            self.last_cleanup_time = current_time
            return True
        
        return False
