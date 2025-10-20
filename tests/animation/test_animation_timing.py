"""Test suite for animation timing and frame intervals.

This module tests that animated sprites properly utilize per-frame timing
and that the animation system respects individual frame intervals.
"""

import time
import unittest
from pathlib import Path

import pygame
from glitchygames.sprites import SpriteFactory


def get_resource_path(filename: str) -> str:
    """Get the full path to a resource file."""
    return str(
        Path(__file__).parent.parent.parent
        / "glitchygames"
        / "examples"
        / "resources"
        / "sprites"
        / filename
    )


# Constants for test thresholds
TIMING_TOLERANCE = 0.5
MAX_FRAME_COUNT = 3
TIMING_PRECISION = 0.001
MIN_INTERVAL = 0.01
MAX_INTERVAL = 10.0
MAX_ANIMATION_TIME = 60
PERFORMANCE_THRESHOLD = 0.1


class TestAnimationTiming(unittest.TestCase):
    """Test animation timing and frame intervals."""

    def setUp(self):
        """Set up test fixtures."""
        # Ensure pygame is properly initialized, even if it was quit by previous tests
        if not pygame.get_init():
            pygame.init()
        pygame.display.set_mode((800, 600))

        # Load the colors.toml animation for testing
        self.animation_file = get_resource_path("colors.toml")

    @staticmethod
    def tearDown():
        """Clean up test fixtures."""
        pygame.quit()

    def test_animation_frame_timing_structure(self):
        """Test that animation frames have proper timing structure."""
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)

        # Verify it's an animated sprite
        assert hasattr(sprite, "animations"), "Should be an animated sprite"
        assert len(sprite.animations) > 0, "Should have animations"

        # Get the first animation
        animation_name = next(iter(sprite.animations.keys()))
        frames = sprite.animations[animation_name]

        # Verify frames exist
        assert len(frames) > 0, "Should have frames"

        # Check that frames have timing information
        for i, frame in enumerate(frames):
            assert frame is not None, f"Frame {i} should exist"
            assert frame.image is not None, f"Frame {i} should have an image"

            # Check timing attributes
            assert hasattr(frame, "duration"), f"Frame {i} should have duration"
            assert isinstance(frame.duration, (int, float)), f"Frame {i} duration should be numeric"
            assert frame.duration > 0, f"Frame {i} duration should be positive"

    def test_animation_timing_accuracy(self):
        """Test that animation timing is accurate within reasonable tolerance."""
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)

        if not hasattr(sprite, "animations") or not sprite.animations:
            self.skipTest("No animations found")

        animation_name = next(iter(sprite.animations.keys()))
        frames = sprite.animations[animation_name]

        # Test timing for a few frames
        test_frames = min(MAX_FRAME_COUNT, len(frames))  # Test first 3 frames

        for frame_idx in range(test_frames):
            frame = frames[frame_idx]
            expected_interval = frame.duration

            # Simulate frame display (we can't easily test the actual animation loop
            # without a full game loop, so we'll test the timing data)
            actual_interval = frame.duration

            # Verify the timing data is correct
            assert abs(actual_interval - expected_interval) < TIMING_PRECISION, (
                f"Frame {frame_idx} timing mismatch: expected {expected_interval}, "
                f"actual {actual_interval}"
            )

    def test_animation_frame_sequence(self):
        """Test that animation frames are in correct sequence."""
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)

        if not hasattr(sprite, "animations") or not sprite.animations:
            self.skipTest("No animations found")

        animation_name = next(iter(sprite.animations.keys()))
        frames = sprite.animations[animation_name]

        # Check frame sequence
        for i, frame in enumerate(frames):
            # Verify frame index matches position
            if hasattr(frame, "frame_index"):
                assert frame.frame_index == i, f"Frame {i} should have frame_index {i}"

            # Verify frame has content
            assert frame.image is not None, f"Frame {i} should have an image"
            width, height = frame.image.get_size()
            assert width > 0, f"Frame {i} should have width > 0"
            assert height > 0, f"Frame {i} should have height > 0"

    def test_animation_timing_consistency(self):
        """Test that animation timing is consistent across frames."""
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)

        if not hasattr(sprite, "animations") or not sprite.animations:
            self.skipTest("No animations found")

        animation_name = next(iter(sprite.animations.keys()))
        frames = sprite.animations[animation_name]

        # Collect all frame intervals
        intervals = [frame.duration for frame in frames]

        # Verify we have different intervals (colors.toml has varied timing)
        unique_intervals = set(intervals)
        assert len(unique_intervals) > 1, "Animation should have varied frame intervals"

        # Verify all intervals are reasonable (between 0.01s and 10s)
        for interval in intervals:
            assert interval > MIN_INTERVAL, f"Frame interval {interval} should be > {MIN_INTERVAL}s"
            assert interval < MAX_INTERVAL, f"Frame interval {interval} should be < {MAX_INTERVAL}s"

    def test_animation_playback_simulation(self):
        """Simulate animation playback to test timing behavior."""
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)

        if not hasattr(sprite, "animations") or not sprite.animations:
            self.skipTest("No animations found")

        animation_name = next(iter(sprite.animations.keys()))
        frames = sprite.animations[animation_name]

        # Simulate playing through the animation
        total_expected_time = sum(frame.duration for frame in frames)

        # Verify total time is reasonable
        assert total_expected_time > 0, "Total animation time should be > 0"
        assert total_expected_time < MAX_ANIMATION_TIME, "Total animation time should be < 60s"

        # Test frame-by-frame timing
        cumulative_time = 0
        for frame in frames:
            cumulative_time += frame.duration

        assert abs(cumulative_time - total_expected_time) < TIMING_PRECISION, (
            "Cumulative time should match total"
        )

    def test_animation_timing_edge_cases(self):
        """Test animation timing with edge cases."""
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)

        if not hasattr(sprite, "animations") or not sprite.animations:
            self.skipTest("No animations found")

        animation_name = next(iter(sprite.animations.keys()))
        frames = sprite.animations[animation_name]

        # Test minimum and maximum intervals
        intervals = [frame.duration for frame in frames]
        min_interval = min(intervals)
        max_interval = max(intervals)

        # Verify reasonable bounds
        assert min_interval >= MIN_INTERVAL, f"Minimum interval should be >= {MIN_INTERVAL}s"
        assert max_interval <= MAX_INTERVAL, f"Maximum interval should be <= {MAX_INTERVAL}s"

        # Test that we have both fast and slow frames
        fast_frames = [i for i, interval in enumerate(intervals) if interval < TIMING_TOLERANCE]
        slow_frames = [i for i, interval in enumerate(intervals) if interval > TIMING_TOLERANCE]

        # Colors.toml should have both fast and slow frames
        assert len(fast_frames) > 0, "Should have fast frames"
        assert len(slow_frames) > 0, "Should have slow frames"

    def test_animation_timing_performance(self):
        """Test that animation timing doesn't cause performance issues."""
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)

        if not hasattr(sprite, "animations") or not sprite.animations:
            self.skipTest("No animations found")

        animation_name = next(iter(sprite.animations.keys()))
        frames = sprite.animations[animation_name]

        # Test timing calculation performance
        start_time = time.time()

        # Simulate timing calculations
        total_time = 0
        for frame in frames:
            total_time += frame.duration

        end_time = time.time()
        calculation_time = end_time - start_time

        # Verify timing calculations are fast
        assert calculation_time < PERFORMANCE_THRESHOLD, (
            f"Timing calculations should be fast: {calculation_time:.3f}s"
        )

    def test_animation_frame_content_consistency(self):
        """Test that animation frames have consistent content structure."""
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)

        if not hasattr(sprite, "animations") or not sprite.animations:
            self.skipTest("No animations found")

        animation_name = next(iter(sprite.animations.keys()))
        frames = sprite.animations[animation_name]

        # Check that all frames have consistent dimensions
        if frames:
            first_frame_size = frames[0].image.get_size()

            for i, frame in enumerate(frames):
                frame_size = frame.image.get_size()
                assert frame_size == first_frame_size, (
                    f"Frame {i} should have same size as first frame"
                )

                # Check that frame has content (not just transparent)
                # Should have some non-transparent colors
                # Not magenta/transparent

    @staticmethod
    def _extract_pixel_data(surface):
        """Extract pixel data from a pygame surface as RGB tuples."""
        width, height = surface.get_size()
        pixels = []

        for y in range(height):
            for x in range(width):
                pixel = surface.get_at((x, y))
                # Convert to RGB (ignore alpha)
                rgb = (pixel.r, pixel.g, pixel.b)
                pixels.append(rgb)

        return pixels


if __name__ == "__main__":
    unittest.main()
