"""Adaptive delta time clamping based on performance."""

from typing import Self


class AdaptiveClamping:
    """Singleton class for performance-based adaptive delta time clamping."""
    
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
            self._initialized = True
    
    def get_adaptive_dt(self: Self, dt: float) -> float:
        """Get adaptively clamped delta time based on performance.
        
        Args:
            dt (float): The raw delta time.
            
        Returns:
            float: The clamped delta time.
        """
        # Track recent delta times
        self._dt_history.append(dt)
        if len(self._dt_history) > 60:  # Keep last 60 frames
            self._dt_history.pop(0)
        
        # Calculate average performance
        if len(self._dt_history) >= 10:
            avg_dt = sum(self._dt_history) / len(self._dt_history)
            avg_fps = 1.0 / avg_dt if avg_dt > 0 else 60
            
            # Adaptive clamping based on performance - 1 FPS increments from 120 to 20
            # Clamp to the nearest FPS tier (round down to ensure we don't exceed performance)
            target_fps = min(120, max(20, int(avg_fps)))
            max_dt = 1.0 / target_fps
            
            # Apply clamping with gradual adjustment to reduce jarring movement
            if dt > max_dt:
                # Use a more gradual clamping to reduce jarring paddle movement
                clamped_dt = min(dt, max_dt * 1.5)  # Allow up to 50% more than max_dt
                print(f"PERFORMANCE: Adaptive clamping dt from {dt:.6f} to {clamped_dt:.6f} (avg_fps={avg_fps:.1f})")
                return clamped_dt
        
        return dt
    
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
        print("PERFORMANCE: Reset performance tracking")


# Global instance for easy access
performance_manager = AdaptiveClamping()
