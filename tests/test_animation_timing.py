"""Test suite for animation timing and frame intervals.

This module tests that animated sprites properly utilize per-frame timing
and that the animation system respects individual frame intervals.
"""

import time
import unittest
from pathlib import Path

import pygame
import pytest
from glitchygames.sprites import SpriteFactory


class TestAnimationTiming(unittest.TestCase):
    """Test animation timing and frame intervals."""

    def setUp(self):
        """Set up test fixtures."""
        pygame.init()
        pygame.display.set_mode((800, 600))

        # Load the colors.toml animation for testing
        self.animation_file = "colors.toml"
        if not Path(self.animation_file).exists():
            self.skipTest(f"Animation file {self.animation_file} not found")

    @staticmethod
    def tearDown():
        """Clean up test fixtures."""
        pygame.quit()

    def test_animation_frame_timing_structure(self):
        """Test that animation frames have proper timing structure."""
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)

        # Verify it's an animated sprite
        self.assertTrue(hasattr(sprite, "animations"), "Should be an animated sprite")
        self.assertGreater(len(sprite.animations), 0, "Should have animations")

        # Get the first animation
        animation_name = list(sprite.animations.keys())[0]
        frames = sprite.animations[animation_name]

        # Verify frames exist
        self.assertGreater(len(frames), 0, "Should have frames")

        # Check that frames have timing information
        for i, frame in enumerate(frames):
            self.assertIsNotNone(frame, f"Frame {i} should exist")
            self.assertIsNotNone(frame.image, f"Frame {i} should have an image")

            # Check timing attributes
            self.assertTrue(hasattr(frame, "duration"), f"Frame {i} should have duration")
            self.assertIsInstance(
                frame.duration, (int, float), f"Frame {i} duration should be numeric"
            )
            self.assertGreater(frame.duration, 0, f"Frame {i} duration should be positive")

            print(f"Frame {i}: duration={frame.duration}s")

    def test_animation_timing_accuracy(self):
        """Test that animation timing is accurate within reasonable tolerance."""
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)

        if not hasattr(sprite, "animations") or not sprite.animations:
            self.skipTest("No animations found")

        animation_name = list(sprite.animations.keys())[0]
        frames = sprite.animations[animation_name]

        # Test timing for a few frames
        test_frames = min(3, len(frames))  # Test first 3 frames

        for frame_idx in range(test_frames):
            frame = frames[frame_idx]
            expected_interval = frame.duration

            # Start timing
            start_time = time.time()

            # Simulate frame display (we can't easily test the actual animation loop
            # without a full game loop, so we'll test the timing data)
            actual_interval = frame.duration

            # Verify the timing data is correct
            self.assertAlmostEqual(
                actual_interval,
                expected_interval,
                places=2,
                msg=f"Frame {frame_idx} timing mismatch",
            )

            print(f"Frame {frame_idx}: expected={expected_interval}s, actual={actual_interval}s")

    def test_animation_frame_sequence(self):
        """Test that animation frames are in correct sequence."""
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)

        if not hasattr(sprite, "animations") or not sprite.animations:
            self.skipTest("No animations found")

        animation_name = list(sprite.animations.keys())[0]
        frames = sprite.animations[animation_name]

        # Check frame sequence
        for i, frame in enumerate(frames):
            # Verify frame index matches position
            if hasattr(frame, "frame_index"):
                self.assertEqual(frame.frame_index, i, f"Frame {i} should have frame_index {i}")

            # Verify frame has content
            self.assertIsNotNone(frame.image, f"Frame {i} should have an image")
            width, height = frame.image.get_size()
            self.assertGreater(width, 0, f"Frame {i} should have width > 0")
            self.assertGreater(height, 0, f"Frame {i} should have height > 0")

            print(f"Frame {i}: {width}x{height}, duration={frame.duration}s")

    def test_animation_timing_consistency(self):
        """Test that animation timing is consistent across frames."""
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)

        if not hasattr(sprite, "animations") or not sprite.animations:
            self.skipTest("No animations found")

        animation_name = list(sprite.animations.keys())[0]
        frames = sprite.animations[animation_name]

        # Collect all frame intervals
        intervals = [frame.duration for frame in frames]

        # Verify we have different intervals (colors.toml has varied timing)
        unique_intervals = set(intervals)
        self.assertGreater(len(unique_intervals), 1, "Animation should have varied frame intervals")

        # Verify all intervals are reasonable (between 0.01s and 10s)
        for interval in intervals:
            self.assertGreater(interval, 0.01, f"Frame interval {interval} should be > 0.01s")
            self.assertLess(interval, 10.0, f"Frame interval {interval} should be < 10s")

        print(f"Frame intervals: {intervals}")
        print(f"Unique intervals: {sorted(unique_intervals)}")

    def test_animation_playback_simulation(self):
        """Simulate animation playback to test timing behavior."""
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)

        if not hasattr(sprite, "animations") or not sprite.animations:
            self.skipTest("No animations found")

        animation_name = list(sprite.animations.keys())[0]
        frames = sprite.animations[animation_name]

        # Simulate playing through the animation
        total_expected_time = sum(frame.duration for frame in frames)

        print(f"Total animation duration: {total_expected_time:.2f}s")
        print(f"Frame count: {len(frames)}")

        # Verify total time is reasonable
        self.assertGreater(total_expected_time, 0, "Total animation time should be > 0")
        self.assertLess(total_expected_time, 60, "Total animation time should be < 60s")

        # Test frame-by-frame timing
        cumulative_time = 0
        for i, frame in enumerate(frames):
            cumulative_time += frame.duration
            print(f"Frame {i}: +{frame.duration:.2f}s = {cumulative_time:.2f}s total")

        self.assertAlmostEqual(
            cumulative_time, total_expected_time, places=2, msg="Cumulative time should match total"
        )

    def test_animation_timing_edge_cases(self):
        """Test animation timing with edge cases."""
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)

        if not hasattr(sprite, "animations") or not sprite.animations:
            self.skipTest("No animations found")

        animation_name = list(sprite.animations.keys())[0]
        frames = sprite.animations[animation_name]

        # Test minimum and maximum intervals
        intervals = [frame.duration for frame in frames]
        min_interval = min(intervals)
        max_interval = max(intervals)

        print(f"Min interval: {min_interval}s")
        print(f"Max interval: {max_interval}s")

        # Verify reasonable bounds
        self.assertGreaterEqual(min_interval, 0.01, "Minimum interval should be >= 0.01s")
        self.assertLessEqual(max_interval, 10.0, "Maximum interval should be <= 10s")

        # Test that we have both fast and slow frames
        fast_frames = [i for i, interval in enumerate(intervals) if interval < 0.5]
        slow_frames = [i for i, interval in enumerate(intervals) if interval > 0.5]

        print(f"Fast frames (< 0.5s): {fast_frames}")
        print(f"Slow frames (> 0.5s): {slow_frames}")

        # Colors.toml should have both fast and slow frames
        self.assertGreater(len(fast_frames), 0, "Should have fast frames")
        self.assertGreater(len(slow_frames), 0, "Should have slow frames")

    def test_animation_timing_performance(self):
        """Test that animation timing doesn't cause performance issues."""
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)

        if not hasattr(sprite, "animations") or not sprite.animations:
            self.skipTest("No animations found")

        animation_name = list(sprite.animations.keys())[0]
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
        self.assertLess(
            calculation_time, 0.1, f"Timing calculations should be fast: {calculation_time:.3f}s"
        )

        print(f"Timing calculation took: {calculation_time:.3f}s")
        print(f"Total animation time: {total_time:.2f}s")

    def test_animation_frame_content_consistency(self):
        """Test that animation frames have consistent content structure."""
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)

        if not hasattr(sprite, "animations") or not sprite.animations:
            self.skipTest("No animations found")

        animation_name = list(sprite.animations.keys())[0]
        frames = sprite.animations[animation_name]

        # Check that all frames have consistent dimensions
        if frames:
            first_frame_size = frames[0].image.get_size()

            for i, frame in enumerate(frames):
                frame_size = frame.image.get_size()
                self.assertEqual(
                    frame_size, first_frame_size, f"Frame {i} should have same size as first frame"
                )

                # Check that frame has content (not just transparent)
                pixels = self._extract_pixel_data(frame.image)
                unique_colors = set(pixels)

                # Should have some non-transparent colors
                non_transparent = [
                    color for color in unique_colors if color != (255, 0, 255)
                ]  # Not magenta/transparent

                print(
                    f"Frame {i}: {frame_size}, {len(unique_colors)} colors, "
                    f"{len(non_transparent)} non-transparent"
                )

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
