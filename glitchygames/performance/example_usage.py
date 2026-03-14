"""Example usage of the centralized performance manager."""

import logging

from glitchygames.performance import performance_manager

LOG = logging.getLogger(__name__)


class ExampleGameObject:
    """Example game object showing how to use the performance manager."""

    def __init__(self):
        """Initialize the example game object with position and speed."""
        self.x = 0
        self.y = 0
        self.speed = 100  # pixels per second

    def dt_tick(self, dt: float) -> None:
        """Update with adaptive delta time adjustment."""
        # Get adaptively adjusted delta time for consistent speed
        dt = performance_manager.get_adaptive_dt(dt)

        # Use the adjusted dt for movement
        self.x += self.speed * dt
        self.y += self.speed * dt

    def get_performance_info(self) -> str:
        """Get current performance statistics.

        Returns:
            str: The performance info.

        """
        stats = performance_manager.get_performance_stats()
        return f"Avg FPS: {stats['avg_fps']:.1f}, History: {stats['history_length']} frames"


# Example usage in a game loop
def example_game_loop():
    """Demonstrate how to use the performance manager in a game loop."""
    obj = ExampleGameObject()

    # Simulate some delta times
    test_dts = [0.016, 0.033, 0.008, 0.025, 0.050]  # Various frame times

    for dt in test_dts:
        LOG.info(f"Raw dt: {dt:.3f}")
        obj.dt_tick(dt)
        LOG.info(f"Performance: {obj.get_performance_info()}")
        LOG.info("")


if __name__ == "__main__":
    example_game_loop()
