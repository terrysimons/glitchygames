"""Tests for bitmappy.film_strip_animation: preview timing and frame images."""

import logging
from types import SimpleNamespace

import pygame
import pytest

from bitmappy.film_strip import FilmStripWidget
from bitmappy.film_strip_animation import FilmStripAnimation
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame

FRAME_SIZE = 2


def make_film_strip() -> FilmStripWidget:
    """Build a film strip showing a two-frame 'idle' animation.

    Returns:
        The film strip widget.

    """
    animated_sprite = AnimatedSprite()
    frames = [
        SpriteFrame(pygame.Surface((FRAME_SIZE, FRAME_SIZE), pygame.SRCALPHA), duration=0.5)
        for _ in range(2)
    ]
    animated_sprite.add_animation('idle', frames)
    film_strip = FilmStripWidget(x=0, y=0, width=400, height=120)
    film_strip.set_animated_sprite(animated_sprite)
    film_strip.current_animation = 'idle'
    return film_strip


class TestUpdateAnimations:
    """Test FilmStripAnimation.update_animations preview timing."""

    def test_zero_length_animation_time_is_not_wrapped(self):
        """With a total duration of zero, the preview time keeps growing instead of looping."""
        film_strip = make_film_strip()
        film_strip.preview_frame_durations['idle'] = [0.0, 0.0]
        film_strip.preview_animation_speeds['idle'] = 1.0
        film_strip.preview_animation_times['idle'] = 3.0

        film_strip.animation.update_animations(0.25)

        assert film_strip.preview_animation_times['idle'] == pytest.approx(3.25)


class TestGetStaleFrameSurface:
    """Test FilmStripAnimation.get_stale_frame_surface."""

    def test_pixels_beyond_the_image_size_are_ignored(self):
        """Pixel data longer than width x height draws only the pixels that fit."""
        frame = SpriteFrame(pygame.Surface((FRAME_SIZE, FRAME_SIZE), pygame.SRCALPHA))
        frame.pixels = [(255, 0, 0, 255)] * (FRAME_SIZE * FRAME_SIZE) + [(0, 255, 0, 255)] * 3
        frame._image_stale = True  # pyright: ignore[reportPrivateUsage]

        stale_surface = FilmStripAnimation.get_stale_frame_surface(frame)

        assert stale_surface is not None
        assert stale_surface.get_size() == (FRAME_SIZE, FRAME_SIZE)
        for pixel_y in range(FRAME_SIZE):
            for pixel_x in range(FRAME_SIZE):
                assert tuple(stale_surface.get_at((pixel_x, pixel_y))) == (255, 0, 0, 255)


class TestGetFrameImage:
    """Test FilmStripAnimation.get_frame_image."""

    def test_frame_without_image_or_pixel_data_has_no_image(self):
        """A frame with no image whose pixel data is empty yields None."""
        frame = SimpleNamespace(image=None, get_pixel_data=list)

        assert FilmStripAnimation.get_frame_image(frame) is None  # type: ignore[arg-type]


class TestDumpAnimatedSpriteDebug:
    """Test FilmStripAnimation.dump_animated_sprite_debug."""

    def test_sprite_without_animations_dumps_only_the_frame_manager(self, caplog):
        """A sprite with no animations logs no per-animation lines but still its FrameManager."""
        film_strip = FilmStripWidget(x=0, y=0, width=400, height=120)
        film_strip.animated_sprite = AnimatedSprite()

        with caplog.at_level(logging.DEBUG, logger='game.tools.film_strip'):
            film_strip.animation.dump_animated_sprite_debug()

        messages = [record.getMessage() for record in caplog.records]
        assert not any(message.startswith("  Animation '") for message in messages)
        assert '  FrameManager debug info:' in messages
