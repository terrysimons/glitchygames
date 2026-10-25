#!/usr/bin/env python3
"""Test film strip PNG drop functionality with real image files and a real film strip."""

import pygame
import pytest

from glitchygames import events
from glitchygames.bitmappy.film_strip import FilmStripWidget
from glitchygames.bitmappy.film_strip_sprite import FilmStripSprite
from glitchygames.input.state import InputSnapshot, set_current_input
from tests.tools.test_film_strip_base import FRAME_SIZE, make_real_animated_sprite

# The colour of the dropped image: far from magenta and from the strip's own frame colours
DROPPED_IMAGE_COLOR = (12, 200, 34)
OPAQUE_ALPHA = 255
# Where the film strip sprite sits on the screen
STRIP_X = 0
STRIP_Y = 0


def install_mouse_position(position: tuple[int, int]) -> None:
    """Make the frame's polled mouse position ``position`` (drop events carry none).

    The autouse ``reset_engine_sources`` fixture (tests/harness.py) resets it after the test.
    """
    set_current_input(
        snapshot=InputSnapshot(
            pressed_scancodes=frozenset(),
            modifiers=0,
            mouse_position=position,
            mouse_buttons=(False, False, False),
            mouse_focused=True,
        ),
    )


def drop_file_event(path) -> events.HashableEvent:
    """Build a real DROPFILE event for a file.

    Returns:
        The event.

    """
    return events.HashableEvent(pygame.DROPFILE, file=str(path))


def frame_rgba_pixels(frame) -> set[tuple[int, int, int, int]]:
    """Read every distinct RGBA colour of a frame's image, in bulk.

    Returns:
        The set of colours.

    """
    image = frame.image
    color_planes = pygame.surfarray.array3d(image).reshape(-1, 3)
    alpha_plane = pygame.surfarray.array_alpha(image).reshape(-1)
    return {
        (int(red), int(green), int(blue), int(alpha))
        for (red, green, blue), alpha in zip(color_planes, alpha_plane, strict=True)
    }


class TestFilmStripDropPNG:
    """Test film strip PNG drop functionality."""

    @pytest.fixture(autouse=True)
    def setup_film_strip(self, tmp_path):
        """Build a real film strip over a two-frame animation, and a real PNG to drop."""
        self.animated_sprite = make_real_animated_sprite(frame_counts={'test_animation': 2})
        self.film_strip_widget = FilmStripWidget(STRIP_X, STRIP_Y, 400, 100)
        self.film_strip_widget.set_animated_sprite(self.animated_sprite)
        self.film_strip_sprite = FilmStripSprite(
            self.film_strip_widget,
            x=STRIP_X,
            y=STRIP_Y,
            width=400,
            height=100,
        )

        # A smaller image than the canvas, so the drop also scales it to the canvas size
        dropped_image = pygame.Surface((FRAME_SIZE // 2, FRAME_SIZE // 2), flags=0, depth=32)
        dropped_image.fill(DROPPED_IMAGE_COLOR)
        self.png_path = tmp_path / 'dropped.png'
        pygame.image.save(dropped_image, str(self.png_path))

    def screen_position_of_frame(self, frame_index: int) -> tuple[int, int]:
        """Return the screen position of the centre of a frame's thumbnail.

        Returns:
            The screen position.

        """
        frame_rect = self.film_strip_widget.frame_layouts['test_animation', frame_index]
        return (STRIP_X + frame_rect.centerx, STRIP_Y + frame_rect.centery)

    def screen_position_off_the_frames(self) -> tuple[int, int]:
        """Return a screen position inside the film strip that is on no frame.

        Returns:
            The screen position (the centre of the animation label).

        """
        film_position = self.film_strip_widget.animation_layouts['test_animation'].center
        assert self.film_strip_widget.get_frame_at_position(film_position) is None
        return (STRIP_X + film_position[0], STRIP_Y + film_position[1])

    def test_drop_png_on_existing_frame(self):
        """Test dropping a PNG on an existing frame replaces its contents."""
        frames = self.animated_sprite.animations['test_animation']
        untouched_frame = frames[1]
        install_mouse_position(self.screen_position_of_frame(0))

        result = self.film_strip_sprite.on_drop_file_event(drop_file_event(self.png_path))

        assert result is True
        frames = self.animated_sprite.animations['test_animation']
        assert len(frames) == 2
        assert frames[0].get_size() == (FRAME_SIZE, FRAME_SIZE)
        assert frame_rgba_pixels(frames[0]) == {(*DROPPED_IMAGE_COLOR, OPAQUE_ALPHA)}
        assert frames[0].pixels == [(*DROPPED_IMAGE_COLOR, OPAQUE_ALPHA)] * FRAME_SIZE**2
        assert frames[1] is untouched_frame

    def test_drop_png_on_strip_area(self):
        """Test dropping a PNG on the film strip (not on a frame) appends and selects a frame."""
        install_mouse_position(self.screen_position_off_the_frames())

        result = self.film_strip_sprite.on_drop_file_event(drop_file_event(self.png_path))

        assert result is True
        frames = self.animated_sprite.animations['test_animation']
        assert len(frames) == 3
        assert frame_rgba_pixels(frames[-1]) == {(*DROPPED_IMAGE_COLOR, OPAQUE_ALPHA)}
        assert self.film_strip_widget.selected_frame == len(frames) - 1

    def test_drop_unsupported_file_type(self, tmp_path):
        """Test dropping an unsupported file type returns False and changes nothing."""
        text_path = tmp_path / 'notes.txt'
        text_path.write_text('not an image')
        install_mouse_position(self.screen_position_of_frame(0))

        result = self.film_strip_sprite.on_drop_file_event(drop_file_event(text_path))

        assert result is False
        assert len(self.animated_sprite.animations['test_animation']) == 2

    def test_drop_outside_film_strip_bounds(self):
        """Test dropping outside film strip bounds returns False and changes nothing."""
        install_mouse_position((
            self.film_strip_sprite.rect.right + 10,
            self.film_strip_sprite.rect.bottom + 10,
        ))

        result = self.film_strip_sprite.on_drop_file_event(drop_file_event(self.png_path))

        assert result is False
        assert len(self.animated_sprite.animations['test_animation']) == 2

    def test_image_conversion_to_sprite_frame(self):
        """Test that a dropped image becomes a canvas-sized RGBA SpriteFrame."""
        new_frame = self.film_strip_sprite._convert_image_to_sprite_frame(str(self.png_path))

        assert new_frame is not None
        assert new_frame.get_size() == (FRAME_SIZE, FRAME_SIZE)
        assert new_frame.image.get_flags() & pygame.SRCALPHA
        assert frame_rgba_pixels(new_frame) == {(*DROPPED_IMAGE_COLOR, OPAQUE_ALPHA)}
        assert new_frame.duration == pytest.approx(0.1)

    def test_unreadable_image_is_not_dropped(self, tmp_path):
        """Test that a file with an image name but no image in it is refused."""
        broken_path = tmp_path / 'broken.png'
        broken_path.write_bytes(b'not png data')
        install_mouse_position(self.screen_position_of_frame(0))

        result = self.film_strip_sprite.on_drop_file_event(drop_file_event(broken_path))

        assert result is False
        assert len(self.animated_sprite.animations['test_animation']) == 2
