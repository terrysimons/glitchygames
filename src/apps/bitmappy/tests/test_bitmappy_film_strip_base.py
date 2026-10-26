"""Base test class and real-object builders for film strip tests.

Every test runs on the real pygame display that tests/harness.py
(``ensure_pygame_graceful_quit``) opens, so these helpers build real sprites, frames and
editor scenes: a film strip draws into real surfaces and a rendering bug fails the test.
"""

import pygame
import pytest

from bitmappy import editor as bitmappy
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame

# Test constants to avoid magic values
MIN_FILM_STRIP_WIDTH = 300
FRAME_INDEX_2 = 2
FRAME_SIZE = 32
MAGENTA_PIXELS = (255, 0, 255)
FRAME_DURATION = 0.5
UPDATE_ITERATIONS = 10
CLICK_OFFSET = 50
PIXEL_SIZE = 16
PIXELS_ACROSS = 32
PIXELS_TALL = 32
DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 600
CANVAS_OFFSET = 20
MIN_HEIGHT_OFFSET = 20
# The frame count of the default test animation
DEFAULT_FRAME_COUNT = 5


def make_real_frame(
    *,
    size: tuple[int, int] = (FRAME_SIZE, FRAME_SIZE),
    color: tuple[int, ...] = MAGENTA_PIXELS,
    duration: float = FRAME_DURATION,
) -> SpriteFrame:
    """Build a real single-colour sprite frame.

    Args:
        size: The frame's (width, height).
        color: The colour of every pixel (RGB or RGBA).
        duration: How long the frame shows, in seconds.

    Returns:
        The frame, with ``pixels`` set to match its image.

    """
    surface = pygame.Surface(size, pygame.SRCALPHA)
    surface.fill(color)
    frame = SpriteFrame(surface, duration=duration)
    frame.pixels = [tuple(color)] * (size[0] * size[1])
    return frame


def frame_color_for_index(
    *,
    base_color: tuple[int, int, int],
    frame_index: int,
) -> tuple[int, int, int]:
    """Return a colour that differs from frame to frame, so frames can be told apart.

    Returns:
        The frame's RGB colour.

    """
    return (
        (base_color[0] + frame_index * 20) % 256,
        (base_color[1] + frame_index * 30) % 256,
        (base_color[2] + frame_index * 40) % 256,
    )


def make_real_animated_sprite(
    *,
    frame_counts: dict[str, int] | None = None,
    frame_size: tuple[int, int] = (FRAME_SIZE, FRAME_SIZE),
    base_color: tuple[int, int, int] = MAGENTA_PIXELS,
) -> AnimatedSprite:
    """Build a real animated sprite with distinctly coloured frames.

    Frame ``i`` of every animation has the colour ``frame_color_for_index(i)`` and lasts
    ``0.3 + 0.2 * i`` seconds, so tests can tell frames apart by colour and duration.

    Args:
        frame_counts: Animation name to frame count (default: 'idle' with five frames).
        frame_size: Each frame's (width, height).
        base_color: The colour of frame 0.

    Returns:
        The animated sprite.

    """
    if frame_counts is None:
        frame_counts = {'idle': DEFAULT_FRAME_COUNT}
    animated_sprite = AnimatedSprite()
    for animation_name, frame_count in frame_counts.items():
        frames = [
            make_real_frame(
                size=frame_size,
                color=frame_color_for_index(base_color=base_color, frame_index=frame_index),
                duration=0.3 + frame_index * 0.2,
            )
            for frame_index in range(frame_count)
        ]
        animated_sprite.add_animation(animation_name, frames)
    return animated_sprite


class FilmStripTestBase:
    """Base class for film strip tests: real sprites and real editor scenes."""

    @pytest.fixture(autouse=True)
    def setup_real_objects(self, mocker):
        """Build the shared real sprite and keep ``mocker`` for targeted mocks."""
        self.cached_sprite = make_real_animated_sprite()
        self._mocker = mocker

    def create_optimized_scene(self, options=None, mocker=None):
        """Create a real Bitmappy editor scene on the real display.

        Returns:
            BitmapEditorScene: The new scene.

        """
        if options is None:
            options = {
                'pixels_across': PIXELS_ACROSS,
                'pixels_tall': PIXELS_TALL,
                'pixel_size': PIXEL_SIZE,
            }

        return bitmappy.BitmapEditorScene(options=options)

    def create_optimized_sprite(self, animation_name='idle'):
        """Create a real animated sprite with one five-frame animation.

        Returns:
            AnimatedSprite: The new sprite.

        """
        return make_real_animated_sprite(frame_counts={animation_name: DEFAULT_FRAME_COUNT})

    def setup_scene_with_sprite(self, sprite=None, options=None):
        """Set up a real editor scene with a sprite loaded.

        Returns:
            tuple: The scene and the loaded sprite.

        """
        if sprite is None:
            sprite = self.cached_sprite

        scene = self.create_optimized_scene(options)
        scene.film_strip_coordinator.on_sprite_loaded(sprite)
        return scene, sprite
