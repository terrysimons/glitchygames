"""Tests for glitchygames.bitmappy.film_strip_rendering: the animation preview panel."""

import pygame
import pytest

from glitchygames.bitmappy.film_strip import FilmStripWidget
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame

FRAME_SIZE = 8


def make_frame(*, color: tuple[int, int, int]) -> SpriteFrame:
    """Build an opaque single-colour frame.

    Args:
        color: The frame's colour.

    Returns:
        The frame.

    """
    surface = pygame.Surface((FRAME_SIZE, FRAME_SIZE), pygame.SRCALPHA)
    surface.fill((*color, 255))
    return SpriteFrame(surface, duration=0.5)


@pytest.fixture
def film_strip_with_two_frames() -> FilmStripWidget:
    """Build a film strip showing a red-then-green 'idle' animation.

    Returns:
        The film strip widget.

    """
    animated_sprite = AnimatedSprite()
    animated_sprite._animations = {  # pyright: ignore[reportPrivateUsage]
        'idle': [make_frame(color=(255, 0, 0)), make_frame(color=(0, 255, 0))],
    }
    animated_sprite.frame_manager.current_animation = 'idle'
    film_strip = FilmStripWidget(x=0, y=0, width=400, height=120)
    film_strip.set_animated_sprite(animated_sprite)
    film_strip.current_animation = 'idle'
    return film_strip


class TestRenderPreview:
    """Test FilmStripRendering.render_preview."""

    def test_out_of_range_preview_frame_falls_back_to_the_first_frame(
        self,
        film_strip_with_two_frames,
        mocker,
    ):
        """An out-of-range preview index shows frame 0 and restarts the preview clock."""
        film_strip = film_strip_with_two_frames
        film_strip.preview_animation_times['idle'] = 0.75
        mocker.patch.object(film_strip.animation, 'get_current_preview_frame', return_value=7)
        surface = pygame.Surface(film_strip.rect.size, pygame.SRCALPHA)

        film_strip.renderer.render_preview(surface)

        assert film_strip.preview_animation_times['idle'] == pytest.approx(0.0)
        preview_rect = film_strip.preview_rects['idle']
        center_color = tuple(surface.get_at(preview_rect.center))
        assert center_color[:3] == (255, 0, 0)

    def test_negative_preview_frame_falls_back_to_the_first_frame(
        self,
        film_strip_with_two_frames,
        mocker,
    ):
        """A negative preview index is also replaced by frame 0."""
        film_strip = film_strip_with_two_frames
        mocker.patch.object(film_strip.animation, 'get_current_preview_frame', return_value=-1)
        surface = pygame.Surface(film_strip.rect.size, pygame.SRCALPHA)

        film_strip.renderer.render_preview(surface)

        preview_rect = film_strip.preview_rects['idle']
        assert tuple(surface.get_at(preview_rect.center))[:3] == (255, 0, 0)

    def test_valid_preview_frame_is_shown(self, film_strip_with_two_frames, mocker):
        """A valid preview index shows that frame and keeps the preview clock."""
        film_strip = film_strip_with_two_frames
        film_strip.preview_animation_times['idle'] = 0.75
        mocker.patch.object(film_strip.animation, 'get_current_preview_frame', return_value=1)
        surface = pygame.Surface(film_strip.rect.size, pygame.SRCALPHA)

        film_strip.renderer.render_preview(surface)

        assert film_strip.preview_animation_times['idle'] == pytest.approx(0.75)
        preview_rect = film_strip.preview_rects['idle']
        assert tuple(surface.get_at(preview_rect.center))[:3] == (0, 255, 0)
