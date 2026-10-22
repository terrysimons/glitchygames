"""Test suite for visual animation rendering and pixel verification.

This module tests that animated sprites properly render to screen surfaces,
transition between frames correctly, and maintain pixel integrity during
the complete animation pipeline.

Like test_animation_hardware.py (whose scene and helpers it shares), it renders to a real
pygame display surface (headless under the dummy video driver ``tests/conftest.py`` sets)
and reads its pixels in bulk: the shared pygame mocks it used to run on drew nothing.
"""

import os
import time

import numpy as np
import pygame
import pytest

from tests.animation.test_animation_hardware import (
    BACKGROUND_COLOR,
    COLORS_FILE,
    FRAME_COLORS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    HardwareAnimationTestScene,
    region_colors,
)

IS_CI = os.environ.get('CI') == 'true'
CI_TIME_MULTIPLIER = 50.0 if IS_CI else 1.0

# Animation rendering performance limit (seconds)
RENDERING_PERF_LIMIT = 6.0 * CI_TIME_MULTIPLIER

# Constants for test thresholds
MAX_FRAME_DURATION = 10
PERF_TEST_CAPTURE_COUNT = 10


class AnimationTestScene(HardwareAnimationTestScene):
    """Test scene for animation visual testing."""

    NAME = 'Animation Visual Test Scene'

    def capture_frame_pixels(self) -> np.ndarray:
        """Render the scene to the screen and capture the screen's pixels in one bulk read.

        Returns:
            np.ndarray: The RGB pixels, indexed [x, y, channel].

        """
        self.force_display_update()
        return self.capture_hardware_display_buffer()

    def sprite_image_colors(self) -> set[tuple[int, int, int]]:
        """Read the colours of the animated sprite's current image.

        Returns:
            set[tuple[int, int, int]]: The RGB colours in the image.

        """
        assert self.animated_sprite is not None
        assert self.animated_sprite.image is not None
        return region_colors(self.animated_sprite.image, self.animated_sprite.image.get_rect())


class TestAnimationVisual:
    """Test visual animation rendering and pixel verification."""

    @pytest.fixture(autouse=True)
    def real_display(self):
        """Open a real (headless under the dummy video driver) display for each test.

        Yields:
            pygame.Surface: The display surface.

        """
        pygame.init()
        yield pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.quit()

    def test_animation_scene_setup(self):
        """Test that the animation test scene loads, plays and centres its sprite."""
        scene = AnimationTestScene(COLORS_FILE)

        assert scene.animated_sprite is not None, 'Animated sprite should be loaded'
        assert scene.animated_sprite.is_playing
        assert scene.animated_sprite.image is not None
        assert scene.animated_sprite.rect is not None
        assert scene.animated_sprite.rect.size == scene.animated_sprite.image.get_size()
        assert scene.animated_sprite.rect.center == (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)

    def test_animation_frame_rendering(self):
        """Test that the first frame renders in the sprite's rect and nowhere else."""
        scene = AnimationTestScene(COLORS_FILE)

        screen_pixels = scene.capture_frame_pixels()

        assert scene.animated_sprite is not None
        assert scene.animated_sprite.rect is not None
        sprite_rect = scene.animated_sprite.rect
        sprite_area_pixels = screen_pixels[
            sprite_rect.left : sprite_rect.right, sprite_rect.top : sprite_rect.bottom
        ]
        assert np.all(sprite_area_pixels == FRAME_COLORS[0])
        background_pixel_count = int(np.all(screen_pixels == BACKGROUND_COLOR, axis=2).sum())
        assert background_pixel_count == SCREEN_WIDTH * SCREEN_HEIGHT - sprite_rect.width * (
            sprite_rect.height
        )

    def test_animation_frame_transitions(self):
        """Test that setting each frame gives the sprite that frame's colour."""
        scene = AnimationTestScene(COLORS_FILE)
        assert scene.animated_sprite is not None

        sprite_colors = []
        for frame_index in range(len(FRAME_COLORS)):
            scene.animated_sprite.set_frame(frame_index)
            sprite_colors.append(scene.sprite_image_colors())

        assert sprite_colors == [{color} for color in FRAME_COLORS]

    def test_animation_timing_visual_verification(self):
        """Test that each frame shows for its own duration, then the animation loops."""
        scene = AnimationTestScene(COLORS_FILE)
        assert scene.animated_sprite is not None
        animation_name = next(iter(scene.animated_sprite.animations))
        frames = scene.animated_sprite.animations[animation_name]

        shown_colors = []
        for frame in frames:
            shown_colors.append(scene.sprite_image_colors())
            # Just short of the frame's duration the frame is still shown
            scene.dt_tick(frame.duration / 2)
            assert scene.sprite_image_colors() == shown_colors[-1]
            scene.dt_tick(frame.duration / 2)

        assert shown_colors == [{color} for color in FRAME_COLORS]
        # After the last frame's duration the looping animation is back on frame 0
        assert scene.sprite_image_colors() == {FRAME_COLORS[0]}

    def test_animation_surface_properties(self):
        """Test that every frame has a same-sized image of its own colour."""
        scene = AnimationTestScene(COLORS_FILE)
        assert scene.animated_sprite is not None
        animation_name = next(iter(scene.animated_sprite.animations))
        frames = scene.animated_sprite.animations[animation_name]

        assert len(frames) == len(FRAME_COLORS)
        first_frame_size = frames[0].image.get_size()
        for frame, frame_color in zip(frames, FRAME_COLORS, strict=True):
            assert frame.image.get_size() == first_frame_size
            assert region_colors(frame.image, frame.image.get_rect()) == {frame_color}

    def test_animation_pixel_integrity(self):
        """Test that the sprite shows each frame's pixels unchanged."""
        scene = AnimationTestScene(COLORS_FILE)
        assert scene.animated_sprite is not None
        animation_name = next(iter(scene.animated_sprite.animations))
        frames = scene.animated_sprite.animations[animation_name]

        for frame_index, frame in enumerate(frames):
            scene.animated_sprite.set_frame(frame_index)

            assert scene.animated_sprite.image is not None
            assert np.array_equal(
                pygame.surfarray.array3d(scene.animated_sprite.image),
                pygame.surfarray.array3d(frame.image),
            ), f'Frame {frame_index} should be shown unchanged'

    def test_animation_rendering_performance(self):
        """Test that animation rendering performs within acceptable limits."""
        scene = AnimationTestScene(COLORS_FILE)
        assert scene.animated_sprite is not None

        start_time = time.perf_counter()
        for capture_index in range(PERF_TEST_CAPTURE_COUNT):
            scene.animated_sprite.set_frame(capture_index % len(FRAME_COLORS))
            scene.capture_frame_pixels()
        total_time = time.perf_counter() - start_time

        # Adjust performance threshold for headless environments
        # In CI/headless environments, rendering is much slower due to software rendering
        assert total_time < RENDERING_PERF_LIMIT, (
            f'Frame capture should be fast: {total_time:.3f}s (max: {RENDERING_PERF_LIMIT}s)'
        )

    def test_animation_screen_integration(self):
        """Test that the sprite appears on the scene's screen, inside its bounds."""
        scene = AnimationTestScene(COLORS_FILE)

        scene.capture_frame_pixels()

        assert scene.animated_sprite is not None
        assert scene.animated_sprite.rect is not None
        sprite_rect = scene.animated_sprite.rect
        assert scene.screen is not None
        assert scene.screen.get_rect().contains(sprite_rect), 'Sprite should fit on screen'
        assert tuple(scene.screen.get_at(sprite_rect.topleft))[:3] == FRAME_COLORS[0]

    def test_animation_frame_consistency(self):
        """Test that animation frames maintain consistent properties."""
        scene = AnimationTestScene(COLORS_FILE)
        assert scene.animated_sprite is not None
        animation_name = next(iter(scene.animated_sprite.animations))
        frames = scene.animated_sprite.animations[animation_name]

        # Test frame consistency
        frame_sizes = []
        frame_durations = []

        for frame in frames:
            assert frame.image is not None
            surface = frame.image
            frame_sizes.append(surface.get_size())
            frame_durations.append(frame.duration)

        # Verify all frames have the same size
        unique_sizes = set(frame_sizes)
        assert len(unique_sizes) == 1, 'All frames should have the same size'

        # Verify durations are reasonable
        for duration in frame_durations:
            assert duration > 0, 'Frame duration should be positive'
            assert duration < MAX_FRAME_DURATION, 'Frame duration should be reasonable'
