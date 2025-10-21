"""Adaptive delta time adjustment based on performance."""

import time
from typing import Self


class AdaptiveClamping:
    """Singleton class for performance-based delta time adjustment.
    
    This class automatically adjusts delta time to maintain consistent game speed
    regardless of frame rate, supporting infinite frame rates with smooth performance.
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls: type[Self]) -> Self:
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self: Self) -> None:
        """Initialize the adaptive clamping system."""
        if not self._initialized:
            self._dt_history = []
            self._fps_history = []
            self._fps_histogram = {}  # Bucket FPS values for efficient storage
            self._last_performance_log_time = 0.0
            self._fps_log_interval_ms = 1000.0  # Default 1 second
            self._per_scene_data = {}  # Track performance per scene
            self._current_scene = None
            self._target_fps = 0.0  # 0 means unlimited FPS
            self._frame_times = []  # Track actual frame times for spare time calculation
            self._initialized = True
    
    def get_adaptive_dt(self: Self, dt: float) -> float:
        """Get adaptively adjusted delta time based on performance.
        
        This method automatically adjusts dt to maintain consistent game speed
        regardless of frame rate, supporting infinite frame rates.
        
        Args:
            dt (float): The raw delta time.
            
        Returns:
            float: The adjusted delta time.
        """
        # Track recent delta times for performance analysis
        self._dt_history.append(dt)
        if len(self._dt_history) > 60:  # Keep last 60 frames
            self._dt_history.pop(0)
        
        # Note: FPS tracking is now handled by FPS events, not here
        # This prevents double-counting and ensures we use the accurate FPS from pygame.clock
        
        # Calculate average performance
        if len(self._dt_history) >= 10:
            avg_dt = sum(self._dt_history) / len(self._dt_history)
            avg_fps = 1.0 / avg_dt if avg_dt > 0 else 60
            
            # Use a target FPS of 60 for consistent game speed
            # This ensures the game runs at the same speed regardless of actual FPS
            target_dt = 1.0 / 60.0  # 60 FPS target
            
            # Smooth adjustment: blend between current dt and target dt
            # This prevents jarring changes while maintaining consistent speed
            smoothing_factor = 0.1  # How quickly to adjust (0.1 = 10% per frame)
            adjusted_dt = dt * (1 - smoothing_factor) + target_dt * smoothing_factor
            
            # Only log significant adjustments at the configured interval
            current_time = time.perf_counter()
            log_interval_seconds = self._fps_log_interval_ms / 1000.0
            if (abs(adjusted_dt - dt) > 0.001 and 
                current_time - self._last_performance_log_time >= log_interval_seconds):
                print(f"PERFORMANCE: Adjusted dt from {dt:.6f} to {adjusted_dt:.6f} (avg_fps={avg_fps:.1f})")
                self._last_performance_log_time = current_time
            
            return adjusted_dt
        
        return dt
    
    def set_fps_log_interval(self: Self, interval_ms: float) -> None:
        """Set the FPS log interval in milliseconds.
        
        Args:
            interval_ms (float): Log interval in milliseconds.
        """
        self._fps_log_interval_ms = interval_ms
    
    def set_target_fps(self: Self, target_fps: float) -> None:
        """Set the target FPS for performance grading.
        
        Args:
            target_fps (float): Target FPS (0 means unlimited).
        """
        self._target_fps = target_fps
    
    def set_current_scene(self: Self, scene_name: str) -> None:
        """Set the current scene for per-scene tracking.
        
        Args:
            scene_name (str): Name of the current scene.
        """
        if scene_name != self._current_scene:
            # Save current scene data if switching - ACCUMULATE, don't overwrite
            if self._current_scene and self._current_scene in self._per_scene_data:
                # Append to existing scene data instead of overwriting
                self._per_scene_data[self._current_scene]['fps_history'].extend(self._fps_history)
                
                # Merge histograms instead of overwriting
                for fps_int, count in self._fps_histogram.items():
                    if fps_int in self._per_scene_data[self._current_scene]['fps_histogram']:
                        self._per_scene_data[self._current_scene]['fps_histogram'][fps_int] += count
                    else:
                        self._per_scene_data[self._current_scene]['fps_histogram'][fps_int] = count
            
            # Initialize new scene data
            if scene_name not in self._per_scene_data:
                self._per_scene_data[scene_name] = {
                    'fps_history': [],
                    'fps_histogram': {}
                }
            
            # Load scene data
            self._fps_history = self._per_scene_data[scene_name]['fps_history']
            self._fps_histogram = self._per_scene_data[scene_name]['fps_histogram']
            self._current_scene = scene_name
    
    def track_fps_from_event(self: Self, fps: float, frame_time: float = None) -> None:
        """Track FPS from FPS events (more accurate than dt-based calculation).
        
        Args:
            fps (float): The current FPS value from pygame.clock.get_fps().
            frame_time (float, optional): Actual frame time in seconds for spare time calculation.
        """
        # This is the primary FPS tracking method - called from FPS events
        self._fps_history.append(fps)
        if len(self._fps_history) > 10000:  # Keep last 10,000 FPS readings (~83s at 120fps, ~42s at 240fps)
            self._fps_history.pop(0)
        
        # Track frame times for spare time calculation (only for capped FPS)
        if frame_time is not None and self._target_fps > 0:
            self._frame_times.append(frame_time)
            if len(self._frame_times) > 1000:  # Keep last 1000 frame times
                self._frame_times.pop(0)
            # Debug: print spare time info occasionally
            if len(self._frame_times) % 100 == 0 and len(self._frame_times) > 0:
                target_frame_time = 1.0 / self._target_fps
                avg_frame_time = sum(self._frame_times) / len(self._frame_times)
                spare_time = target_frame_time - avg_frame_time
                print(f"DEBUG: Target: {target_frame_time*1000:.1f}ms, Actual: {avg_frame_time*1000:.1f}ms, Spare: {spare_time*1000:.1f}ms")
        
        # Also populate histogram buckets for real-time tracking
        # Round FPS to nearest integer for histogram bucketing
        fps_int = int(round(fps))
        if fps_int in self._fps_histogram:
            self._fps_histogram[fps_int] += 1
        else:
            self._fps_histogram[fps_int] = 1
    
    def _track_fps(self: Self, fps: float) -> None:
        """Track FPS in histogram buckets for efficient storage.
        
        Args:
            fps (float): The current FPS value.
        """
        # Also keep recent FPS for immediate stats
        self._fps_history.append(fps)
        if len(self._fps_history) > 10000:  # Keep last 10,000 FPS readings (~83s at 120fps, ~42s at 240fps)
            self._fps_history.pop(0)
    
    def get_performance_stats(self: Self) -> dict:
        """Get current performance statistics.
        
        Returns:
            dict: Performance statistics including average FPS and history.
        """
        if len(self._dt_history) < 2:
            return {"avg_fps": 60.0, "history_length": 0}
        
        avg_dt = sum(self._dt_history) / len(self._dt_history)
        avg_fps = 1.0 / avg_dt if avg_dt > 0 else 60.0
        
        return {
            "avg_fps": avg_fps,
            "history_length": len(self._dt_history),
            "recent_dt": self._dt_history[-5:] if len(self._dt_history) >= 5 else self._dt_history
        }
    
    def reset(self: Self) -> None:
        """Reset performance tracking."""
        self._dt_history = []
        self._fps_history = []
        self._fps_histogram = {}
        print("PERFORMANCE: Reset performance tracking")
    
    def get_shutdown_stats(self: Self) -> dict:
        """Get comprehensive performance statistics for shutdown reporting.
        
        Returns:
            dict: Complete performance statistics with histogram data.
        """
        if not self._fps_history:
            return {"message": "Not enough data"}
        
        # Calculate basic stats
        fps_values = [fps for fps in self._fps_history if fps > 0]  # Filter out invalid FPS
        if not fps_values:
            return {"message": "No valid FPS data collected"}
        
        # Sort for percentile calculations
        fps_values.sort()
        total_frames = len(fps_values)
        
        # Calculate percentiles (drop top and bottom 5%)
        drop_count = max(1, int(total_frames * 0.05))
        trimmed_fps = fps_values[drop_count:-drop_count] if len(fps_values) > 2 * drop_count else fps_values
        
        # Create histogram from trimmed FPS data to match the percentage calculations
        fps_histogram = {}
        if trimmed_fps:
            # Count FPS values in the trimmed data
            for fps in trimmed_fps:
                fps_int = int(round(fps))
                bucket_key = f"{fps_int}"
                if bucket_key in fps_histogram:
                    fps_histogram[bucket_key] += 1
                else:
                    fps_histogram[bucket_key] = 1
        
        stats = {
            "total_frames": total_frames,
            "trimmed_frames": len(trimmed_fps),
            "avg_fps": sum(trimmed_fps) / len(trimmed_fps),
            "min_fps": min(trimmed_fps),
            "max_fps": max(trimmed_fps),
            "median_fps": trimmed_fps[len(trimmed_fps) // 2],
            "fps_histogram": dict(sorted(fps_histogram.items())),
            "performance_grade": self._calculate_performance_grade(trimmed_fps)
        }
        
        return stats
    
    def get_per_scene_shutdown_stats(self: Self) -> dict:
        """Get comprehensive performance statistics per scene for shutdown reporting.
        
        Returns:
            dict: Per-scene performance statistics with histogram data.
        """
        per_scene_stats = {}
        
        for scene_name, scene_data in self._per_scene_data.items():
            fps_history = scene_data['fps_history']
            fps_histogram = scene_data['fps_histogram']
            
            if not fps_history:
                per_scene_stats[scene_name] = {"message": "Not enough data"}
                continue
            
            # Calculate basic stats for this scene
            fps_values = [fps for fps in fps_history if fps > 0]
            if not fps_values:
                per_scene_stats[scene_name] = {"message": "No valid FPS data collected"}
                continue
            
            # Sort for percentile calculations
            fps_values.sort()
            total_frames = len(fps_values)
            
            # Calculate percentiles (drop top and bottom 5%)
            drop_count = max(1, int(total_frames * 0.05))
            trimmed_fps = fps_values[drop_count:-drop_count] if len(fps_values) > 2 * drop_count else fps_values
            
            # Create histogram from trimmed FPS data to match the percentage calculations
            scene_histogram = {}
            if trimmed_fps:
                # Count FPS values in the trimmed data
                for fps in trimmed_fps:
                    fps_int = int(round(fps))
                    bucket_key = f"{fps_int}"
                    if bucket_key in scene_histogram:
                        scene_histogram[bucket_key] += 1
                    else:
                        scene_histogram[bucket_key] = 1
            
            per_scene_stats[scene_name] = {
                "total_frames": total_frames,
                "trimmed_frames": len(trimmed_fps),
                "avg_fps": sum(trimmed_fps) / len(trimmed_fps) if trimmed_fps else 0,
                "min_fps": min(trimmed_fps) if trimmed_fps else 0,
                "max_fps": max(trimmed_fps) if trimmed_fps else 0,
                "median_fps": trimmed_fps[len(trimmed_fps) // 2] if trimmed_fps else 0,
                "fps_histogram": scene_histogram,
                "performance_grade": self._calculate_performance_grade(trimmed_fps)
            }
        
        return per_scene_stats
    
    def _calculate_performance_grade(self: Self, fps_values: list[float]) -> str:
        """Calculate a performance grade based on FPS distribution relative to target FPS.
        
        Args:
            fps_values: List of FPS values.
            
        Returns:
            str: Performance grade (A+, A, B, C, D, F).
        """
        if not fps_values:
            return "N/A"
        
        avg_fps = sum(fps_values) / len(fps_values)
        
        # If target FPS is 0 (unlimited), use absolute grading
        if self._target_fps == 0:
            if avg_fps >= 120:
                return "A+ (Excellent)"
            elif avg_fps >= 90:
                return "A (Very Good)"
            elif avg_fps >= 60:
                return "B (Good)"
            elif avg_fps >= 45:
                return "C (Fair)"
            elif avg_fps >= 30:
                return "D (Poor)"
            else:
                return "F (Very Poor)"
        
        # For target FPS > 0, grade relative to target
        fps_ratio = avg_fps / self._target_fps
        
        if fps_ratio >= 1.0:
            return "A+ (Excellent)"  # Meeting or exceeding target
        elif fps_ratio >= 0.95:
            return "A (Very Good)"   # 95%+ of target
        elif fps_ratio >= 0.90:
            return "B (Good)"        # 90%+ of target
        elif fps_ratio >= 0.80:
            return "C (Fair)"      # 80%+ of target
        elif fps_ratio >= 0.70:
            return "D (Poor)"        # 70%+ of target
        else:
            return "F (Very Poor)"   # <70% of target
    
    def get_spare_time_stats(self: Self) -> dict:
        """Calculate spare time statistics for capped frame rates.
        
        Returns:
            dict: Spare time statistics including average spare time and capacity.
        """
        print(f"DEBUG: target_fps={self._target_fps}, frame_times_count={len(self._frame_times)}")
        if self._target_fps == 0 or not self._frame_times:
            return {"message": "Not applicable for unlimited FPS"}
        
        target_frame_time = 1.0 / self._target_fps
        avg_frame_time = sum(self._frame_times) / len(self._frame_times)
        avg_spare_time = target_frame_time - avg_frame_time
        spare_capacity_percent = (avg_spare_time / target_frame_time) * 100
        
        return {
            "target_frame_time_ms": target_frame_time * 1000,
            "avg_frame_time_ms": avg_frame_time * 1000,
            "avg_spare_time_ms": avg_spare_time * 1000,
            "spare_capacity_percent": spare_capacity_percent,
            "could_tick_times": target_frame_time / avg_frame_time if avg_frame_time > 0 else 0
        }
    
    def print_shutdown_report(self: Self) -> None:
        """Print a comprehensive performance report at shutdown."""
        stats = self.get_shutdown_stats()
        
        if "message" in stats:
            # Skip global report if not enough data - per-scene reports are more useful
            return
        
        print("\n" + "="*80)
        print("🎮 GAME PERFORMANCE REPORT")
        print("="*80)
        print(f"📊 Total Frames: {stats['total_frames']:,}")
        print(f"📈 Analyzed Frames: {stats['trimmed_frames']:,} (dropped top/bottom 5%)")
        print(f"⚡ Average FPS: {stats['avg_fps']:.1f}")
        print(f"📉 Minimum FPS: {stats['min_fps']:.1f}")
        print(f"📈 Maximum FPS: {stats['max_fps']:.1f}")
        print(f"📊 Median FPS: {stats['median_fps']:.1f}")
        print(f"🏆 Performance Grade: {stats['performance_grade']}")
        
        # Add spare time information for capped FPS
        print(f"DEBUG: Calling get_spare_time_stats() for global report")
        spare_stats = self.get_spare_time_stats()
        print(f"DEBUG: global spare_stats = {spare_stats}")
        if "message" not in spare_stats:
            print(f"⏱️  Target Frame Time: {spare_stats['target_frame_time_ms']:.1f}ms")
            print(f"⏱️  Average Frame Time: {spare_stats['avg_frame_time_ms']:.1f}ms")
            print(f"⏱️  Spare Time: {spare_stats['avg_spare_time_ms']:.1f}ms ({spare_stats['spare_capacity_percent']:.1f}% capacity)")
            print(f"🔄 Could Tick: {spare_stats['could_tick_times']:.1f}x faster")
        
        # Print FPS histogram (horizontal)
        if stats['fps_histogram']:
            print(f"\n📊 FPS Distribution:")
            max_count = max(stats['fps_histogram'].values())
            max_bar_length = 30  # Maximum bar length for 80-char display
            
            # Show all 20 buckets, arranged in bell curve shape by frame count
            all_buckets = []
            
            for bucket in stats['fps_histogram'].keys():
                count = stats['fps_histogram'][bucket]
                percentage = (count / stats['trimmed_frames']) * 100 if stats['trimmed_frames'] > 0 else 0
                all_buckets.append((bucket, count, percentage))
            
            # Sort by frame count to create bell curve arrangement
            # Highest frame counts in center, tapering off to sides
            all_buckets.sort(key=lambda x: x[1], reverse=True)  # Sort by frame count (descending)
            
            # Rearrange to bell curve: highest in center, tapering off
            bell_curve_buckets = []
            left_side = []
            right_side = []
            
            for i, (bucket, count, percentage) in enumerate(all_buckets):
                if i % 2 == 0:
                    left_side.append((bucket, count, percentage))
                else:
                    right_side.append((bucket, count, percentage))
            
            # Combine: left side (reversed) + right side = bell curve
            bell_curve_buckets = left_side[::-1] + right_side
            all_buckets = bell_curve_buckets
            
            # Calculate available space for bars (accounting for prefix text)
            # Format: "  XXX-XXX FPS: XXXXX frames (XX.X%) "
            # Worst case: "  Other FPS:   10000 frames (100.0%) "
            prefix_length = 40  # Conservative estimate for prefix text
            max_bar_length = 80 - prefix_length  # Maximum bar length (40 chars)
            
            # Cap bar length to prevent wrapping
            def calculate_bar_length(count, max_count):
                bar_length = int((count / max_count) * max_bar_length) if max_count > 0 else 0
                return min(bar_length, max_bar_length)  # Cap at maximum
            
            # Print all 20 buckets
            for bucket, count, percentage in all_buckets:
                bar_length = calculate_bar_length(count, max_count)
                bar = "█" * bar_length
                if isinstance(bucket, str):
                    # Single FPS value bucket
                    print(f"  {bucket:>3s} FPS: {count:5d} frames ({percentage:5.1f}%) {bar}")
                elif isinstance(bucket, tuple):
                    # FPS range bucket
                    print(f"  {bucket[0]:3d}-{bucket[1]:3d} FPS: {count:5d} frames ({percentage:5.1f}%) {bar}")
                else:
                    # Legacy single number bucket
                    print(f"  {bucket:3d}-{bucket+4:3d} FPS: {count:5d} frames ({percentage:5.1f}%) {bar}")
        
        print("="*80)
    
    def print_per_scene_shutdown_report(self: Self) -> None:
        """Print a comprehensive performance report per scene at shutdown."""
        per_scene_stats = self.get_per_scene_shutdown_stats()
        
        # Filter out "Unknown" scenes
        filtered_stats = {name: stats for name, stats in per_scene_stats.items() if name != "Unknown"}
        
        if not filtered_stats:
            print("\n" + "="*80)
            print("🎮 PER-SCENE PERFORMANCE REPORT")
            print("="*80)
            print("No scene performance data collected")
            print("="*80)
            return
        
        print("\n" + "="*80)
        print("🎮 PER-SCENE PERFORMANCE REPORT")
        print("="*80)
        
        for scene_name, stats in filtered_stats.items():
            print(f"\n📊 Scene: {scene_name}")
            print("-" * 40)
            
            if "message" in stats:
                print(f"   {stats['message']}")
                continue
            
            print(f"📊 Total Frames: {stats['total_frames']:,}")
            print(f"📈 Analyzed Frames: {stats['trimmed_frames']:,} (dropped top/bottom 5%)")
            print(f"⚡ Average FPS: {stats['avg_fps']:.1f}")
            print(f"📉 Minimum FPS: {stats['min_fps']:.1f}")
            print(f"📈 Maximum FPS: {stats['max_fps']:.1f}")
            print(f"📊 Median FPS: {stats['median_fps']:.1f}")
            print(f"🏆 Performance Grade: {stats['performance_grade']}")
            
            # Add spare time information for capped FPS
            print(f"DEBUG: Calling get_spare_time_stats() for scene {scene_name}")
            spare_stats = self.get_spare_time_stats()
            print(f"DEBUG: spare_stats = {spare_stats}")
            if "message" not in spare_stats:
                print(f"⏱️  Target Frame Time: {spare_stats['target_frame_time_ms']:.1f}ms")
                print(f"⏱️  Average Frame Time: {spare_stats['avg_frame_time_ms']:.1f}ms")
                print(f"⏱️  Spare Time: {spare_stats['avg_spare_time_ms']:.1f}ms ({spare_stats['spare_capacity_percent']:.1f}% capacity)")
                print(f"🔄 Could Tick: {spare_stats['could_tick_times']:.1f}x faster")
            
            # Print FPS histogram for this scene
            if stats['fps_histogram']:
                print(f"\n📊 FPS Distribution:")
                max_count = max(stats['fps_histogram'].values())
                max_bar_length = 30
                
                # Show all buckets, arranged in bell curve shape by frame count
                all_buckets = []
                
                for bucket in stats['fps_histogram'].keys():
                    count = stats['fps_histogram'][bucket]
                    percentage = (count / stats['trimmed_frames']) * 100 if stats['trimmed_frames'] > 0 else 0
                    all_buckets.append((bucket, count, percentage))
                
                # Sort by frame count to create bell curve arrangement
                all_buckets.sort(key=lambda x: x[1], reverse=True)
                
                # Rearrange to bell curve: highest in center, tapering off
                bell_curve_buckets = []
                left_side = []
                right_side = []
                
                for i, (bucket, count, percentage) in enumerate(all_buckets):
                    if i % 2 == 0:
                        left_side.append((bucket, count, percentage))
                    else:
                        right_side.append((bucket, count, percentage))
                
                # Combine: left side (reversed) + right side = bell curve
                bell_curve_buckets = left_side[::-1] + right_side
                all_buckets = bell_curve_buckets
                
                # Calculate available space for bars
                prefix_length = 40
                max_bar_length = 80 - prefix_length
                
                def calculate_bar_length(count, max_count):
                    bar_length = int((count / max_count) * max_bar_length) if max_count > 0 else 0
                    return min(bar_length, max_bar_length)
                
                # Print all buckets with proper column alignment
                for bucket, count, percentage in all_buckets:
                    bar_length = calculate_bar_length(count, max_count)
                    bar = "█" * bar_length
                    if isinstance(bucket, str):
                        # Single FPS value
                        fps_range = f"{bucket:>3s} FPS"
                        print(f"  {fps_range:15s} {count:5d} frames ({percentage:5.1f}%) {bar}")
                    elif isinstance(bucket, tuple):
                        # Fixed-width columns: FPS range (15 chars), frames (8 chars), percentage (10 chars)
                        fps_range = f"{bucket[0]:3d}-{bucket[1]:3d} FPS"
                        print(f"  {fps_range:15s} {count:5d} frames ({percentage:5.1f}%) {bar}")
                    else:
                        fps_range = f"{bucket:3d}-{bucket+4:3d} FPS"
                        print(f"  {fps_range:15s} {count:5d} frames ({percentage:5.1f}%) {bar}")
        
        print("="*80)


# Global instance for easy access
performance_manager = AdaptiveClamping()
