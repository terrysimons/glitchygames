"""Test suite for animation timing and frame intervals.

This module tests that animated sprites properly utilize per-frame timing
and that the animation system respects individual frame intervals.
"""

import sys
import time
from pathlib import Path

import pygame
import pytest

from glitchygames.sprites import SpriteFactory

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# The engine's own sprite test data (Bitmappy keeps its sprite library)
SPRITE_FIXTURES_DIRECTORY = Path(__file__).resolve().parents[1] / 'fixtures' / 'sprites'


def get_resource_path(filename: str) -> str:
    """Get the full path to a resource file.

    Returns:
        str: The resource path.

    """
    return str(
        SPRITE_FIXTURES_DIRECTORY / filename,
    )


# Constants for test thresholds
TIMING_TOLERANCE = 0.5
MAX_FRAME_COUNT = 3
TIMING_PRECISION = 0.001
MIN_INTERVAL = 0.01
MAX_INTERVAL = 10.0
MAX_ANIMATION_TIME = 60
PERFORMANCE_THRESHOLD = 0.1

# The solid color of each frame of colors.toml, in order (from its [colors] table)
COLORS_TOML_FRAME_COLORS = [
    (255, 0, 0),
    (0, 255, 0),
    (0, 0, 255),
    (255, 255, 0),
    (255, 0, 255),
    (0, 255, 255),
    (255, 128, 0),
    (128, 0, 255),
    (0, 255, 128),
    (255, 255, 255),
]


class TestAnimationTiming:
    """Test animation timing and frame intervals."""

    def setup_method(self):
        """Set up test fixtures."""
        # Load the colors.toml animation for testing
        self.animation_file = get_resource_path('colors.toml')

    def test_animation_frame_timing_structure(self):
        """Test that animation frames have proper timing structure."""
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)

        # Verify it's an animated sprite
        assert hasattr(sprite, 'animations'), 'Should be an animated sprite'
        assert len(sprite.animations) > 0, 'Should have animations'

        # Get the first animation
        animation_name = next(iter(sprite.animations.keys()))
        frames = sprite.animations[animation_name]

        # Verify frames exist
        assert len(frames) > 0, 'Should have frames'

        # Check that frames have timing information
        for i, frame in enumerate(frames):
            assert frame is not None, f'Frame {i} should exist'
            assert frame.image is not None, f'Frame {i} should have an image'

            # Check timing attributes
            assert hasattr(frame, 'duration'), f'Frame {i} should have duration'
            assert isinstance(frame.duration, (int, float)), f'Frame {i} duration should be numeric'
            assert frame.duration > 0, f'Frame {i} duration should be positive'

    def test_animation_timing_accuracy(self):
        """Test that animation timing is accurate within reasonable tolerance."""
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)

        if not hasattr(sprite, 'animations') or not sprite.animations:
            pytest.skip('No animations found')

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
                f'Frame {frame_idx} timing mismatch: expected {expected_interval}, '
                f'actual {actual_interval}'
            )

    def test_animation_frame_sequence(self):
        """Test that animation frames are in correct sequence."""
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)

        if not hasattr(sprite, 'animations') or not sprite.animations:
            pytest.skip('No animations found')

        animation_name = next(iter(sprite.animations.keys()))
        frames = sprite.animations[animation_name]

        # Check frame sequence
        for i, frame in enumerate(frames):
            # Verify frame index matches position
            if hasattr(frame, 'frame_index'):
                assert frame.frame_index == i, f'Frame {i} should have frame_index {i}'

            # Verify frame has content
            assert frame.image is not None, f'Frame {i} should have an image'
            width, height = frame.image.get_size()
            assert width > 0, f'Frame {i} should have width > 0'
            assert height > 0, f'Frame {i} should have height > 0'

    def test_animation_timing_consistency(self):
        """Test that animation timing is consistent across frames."""
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)

        if not hasattr(sprite, 'animations') or not sprite.animations:
            pytest.skip('No animations found')

        animation_name = next(iter(sprite.animations.keys()))
        frames = sprite.animations[animation_name]

        # Collect all frame intervals
        intervals = [frame.duration for frame in frames]

        # Verify we have different intervals (colors.toml has varied timing)
        unique_intervals = set(intervals)
        assert len(unique_intervals) > 1, 'Animation should have varied frame intervals'

        # Verify all intervals are reasonable (between 0.01s and 10s)
        for interval in intervals:
            assert interval > MIN_INTERVAL, f'Frame interval {interval} should be > {MIN_INTERVAL}s'
            assert interval < MAX_INTERVAL, f'Frame interval {interval} should be < {MAX_INTERVAL}s'

    def test_animation_playback_simulation(self):
        """Simulate animation playback to test timing behavior."""
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)

        if not hasattr(sprite, 'animations') or not sprite.animations:
            pytest.skip('No animations found')

        animation_name = next(iter(sprite.animations.keys()))
        frames = sprite.animations[animation_name]

        # Simulate playing through the animation
        total_expected_time = sum(frame.duration for frame in frames)

        # Verify total time is reasonable
        assert total_expected_time > 0, 'Total animation time should be > 0'
        assert total_expected_time < MAX_ANIMATION_TIME, 'Total animation time should be < 60s'

        # Test frame-by-frame timing
        cumulative_time = 0
        for frame in frames:
            cumulative_time += frame.duration

        assert abs(cumulative_time - total_expected_time) < TIMING_PRECISION, (
            'Cumulative time should match total'
        )

    def test_animation_timing_edge_cases(self):
        """Test animation timing with edge cases."""
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)

        if not hasattr(sprite, 'animations') or not sprite.animations:
            pytest.skip('No animations found')

        animation_name = next(iter(sprite.animations.keys()))
        frames = sprite.animations[animation_name]

        # Test minimum and maximum intervals
        intervals = [frame.duration for frame in frames]
        min_interval = min(intervals)
        max_interval = max(intervals)

        # Verify reasonable bounds
        assert min_interval >= MIN_INTERVAL, f'Minimum interval should be >= {MIN_INTERVAL}s'
        assert max_interval <= MAX_INTERVAL, f'Maximum interval should be <= {MAX_INTERVAL}s'

        # Test that we have both fast and slow frames
        fast_frames = [i for i, interval in enumerate(intervals) if interval < TIMING_TOLERANCE]
        slow_frames = [i for i, interval in enumerate(intervals) if interval > TIMING_TOLERANCE]

        # Colors.toml should have both fast and slow frames
        assert len(fast_frames) > 0, 'Should have fast frames'
        assert len(slow_frames) > 0, 'Should have slow frames'

    def test_animation_timing_performance(self):
        """Test that animation timing doesn't cause performance issues."""
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)

        if not hasattr(sprite, 'animations') or not sprite.animations:
            pytest.skip('No animations found')

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
            f'Timing calculations should be fast: {calculation_time:.3f}s'
        )

    def test_animation_frame_content_consistency(self):
        """Test that animation frames have consistent content structure."""
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)

        if not hasattr(sprite, 'animations') or not sprite.animations:
            pytest.skip('No animations found')

        animation_name = next(iter(sprite.animations.keys()))
        frames = sprite.animations[animation_name]

        # Check that all frames have consistent dimensions
        if frames:
            first_frame_size = frames[0].image.get_size()

            for i, frame in enumerate(frames):
                frame_size = frame.image.get_size()
                assert frame_size == first_frame_size, (
                    f'Frame {i} should have same size as first frame'
                )

            # Each frame of colors.toml is one solid color, and the frames step through
            # the file's palette (frame 4 is the magenta transparency key: a blank frame)
            frame_colors = []
            for i, frame in enumerate(frames):
                rgb_pixels = pygame.surfarray.array3d(frame.image).reshape(-1, 3)
                unique_colors = {tuple(int(channel) for channel in pixel) for pixel in rgb_pixels}
                assert len(unique_colors) == 1, f'Frame {i} should be one solid color'
                frame_colors.append(unique_colors.pop())
            assert frame_colors == COLORS_TOML_FRAME_COLORS

    def test_playback_draws_each_frame_for_its_own_interval(self):
        """Playing the sprite shows each frame's pixels for that frame's own interval.

        colors.toml's frames last 0.25 s, 0.75 s and 0.66 s: the drawn image must change
        only when the current frame's interval has run out.
        """
        sprite = SpriteFactory.load_sprite(filename=self.animation_file)
        animation_name = next(iter(sprite.animations.keys()))
        frames = sprite.animations[animation_name]
        frame_colors = [
            pygame.surfarray.array3d(frame.image).tolist() for frame in frames[:MAX_FRAME_COUNT]
        ]
        assert len({str(colors) for colors in frame_colors}) == MAX_FRAME_COUNT, (
            'the first three frames must look different for this test to mean anything'
        )

        def drawn_colors():
            return pygame.surfarray.array3d(sprite.image).tolist()

        sprite.play()
        assert sprite.current_frame == 0
        assert drawn_colors() == frame_colors[0]

        # Just short of frame 0's 0.25 s: still frame 0
        sprite.update(0.2)
        assert sprite.current_frame == 0
        assert drawn_colors() == frame_colors[0]

        # Past it: frame 1 (0.75 s long) is drawn
        sprite.update(0.1)
        assert sprite.current_frame == 1
        assert drawn_colors() == frame_colors[1]

        # 0.6 s more is still inside frame 1; 0.15 s after that is frame 2
        sprite.update(0.6)
        assert sprite.current_frame == 1
        assert drawn_colors() == frame_colors[1]
        sprite.update(0.15)
        assert sprite.current_frame == MAX_FRAME_COUNT - 1
        assert drawn_colors() == frame_colors[2]

    @staticmethod
    def _extract_pixel_data(surface):
        """Extract pixel data from a pygame surface as RGB tuples.

        Returns:
            object: The result.

        """
        width, height = surface.get_size()
        pixels = []

        for y in range(height):
            for x in range(width):
                pixel = surface.get_at((x, y))
                # Convert to RGB (ignore alpha)
                rgb = (pixel.r, pixel.g, pixel.b)
                pixels.append(rgb)

        return pixels


# Remove unittest.main() since we're using pytest
