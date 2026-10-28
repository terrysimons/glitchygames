"""Test film strip event handling with return value pattern."""

import pygame
import pytest
from src.apps.bitmappy.tests.film_strip_support import (
    FRAME_INDEX_2,
    PIXEL_SIZE,
    PIXELS_ACROSS,
    PIXELS_TALL,
    frame_color_for_index,
    make_real_animated_sprite,
)

from bitmappy import editor as bitmappy
from bitmappy.onion_skinning import get_onion_skinning_manager
from glitchygames import events

# Frame colours far from magenta, so no frame is drawn or sampled as transparent
BASE_FRAME_COLOR = (200, 40, 10)
OPAQUE_ALPHA = 255


def right_click_event(*, position: tuple[int, int]) -> events.HashableEvent:
    """Build a real right MOUSEBUTTONUP event.

    Returns:
        The event.

    """
    return events.HashableEvent(pygame.MOUSEBUTTONUP, pos=position, button=3)


class TestFilmStripEventHandling:
    """Test film strip event handling with return value pattern."""

    @pytest.fixture(autouse=True)
    def setup_real_editor(self):
        """Load a five-frame 'idle' animation into a real editor scene."""
        self.scene = bitmappy.BitmapEditorScene(
            options={
                'pixels_across': PIXELS_ACROSS,
                'pixels_tall': PIXELS_TALL,
                'pixel_size': PIXEL_SIZE,
            },
        )
        self.scene.film_strip_coordinator.on_sprite_loaded(
            make_real_animated_sprite(base_color=BASE_FRAME_COLOR),
        )
        self.film_strip_sprite = self.scene.film_strip_sprites['idle']
        self.film_strip_widget = self.film_strip_sprite.film_strip_widget

    def screen_position_of_frame(self, frame_index: int) -> tuple[int, int]:
        """Return the screen position of the centre of a frame's thumbnail.

        Returns:
            The screen position.

        """
        frame_rect = self.film_strip_widget.frame_layouts['idle', frame_index]
        return (
            self.film_strip_sprite.rect.x + frame_rect.centerx,
            self.film_strip_sprite.rect.y + frame_rect.centery,
        )

    def screen_position_off_the_frames(self) -> tuple[int, int]:
        """Return a screen position inside the film strip that is on no frame.

        Returns:
            The screen position (the centre of the animation label).

        """
        label_rect = self.film_strip_widget.animation_layouts['idle']
        film_position = label_rect.center
        assert self.film_strip_widget.get_frame_at_position(film_position) is None
        return (
            self.film_strip_sprite.rect.x + film_position[0],
            self.film_strip_sprite.rect.y + film_position[1],
        )

    def test_right_click_inside_bounds_returns_true(self):
        """Test that right-click inside film strip bounds returns True."""
        result = self.film_strip_sprite.on_right_mouse_button_up_event(
            right_click_event(position=self.screen_position_of_frame(0)),
        )

        assert result, 'Film strip should return True when handling event inside bounds'

    def test_right_click_outside_bounds_returns_false(self):
        """Test that right-click outside film strip bounds returns False."""
        outside_position = (self.film_strip_sprite.rect.x - 1, self.film_strip_sprite.rect.y - 1)

        result = self.film_strip_sprite.on_right_mouse_button_up_event(
            right_click_event(position=outside_position),
        )

        assert not result, 'Film strip should return False when not handling event outside bounds'

    def test_right_click_with_frame_selection_returns_true(self):
        """Test that right-click on a frame samples its colour into the editor and returns True."""
        result = self.film_strip_sprite.on_right_mouse_button_up_event(
            right_click_event(position=self.screen_position_of_frame(1)),
        )

        assert result, 'Film strip should return True when handling frame selection event'
        expected_color = frame_color_for_index(base_color=BASE_FRAME_COLOR, frame_index=1)
        assert tuple(self.scene.color_well.active_color) == (*expected_color, OPAQUE_ALPHA)

    def test_right_click_off_the_frames_returns_true(self):
        """Test that a right-click inside the strip but on no frame is still handled.

        It goes to the widget's handle_click (the onion-skinning path), which does nothing
        off the frames, and the sprite still reports the click as handled.
        """
        result = self.film_strip_sprite.on_right_mouse_button_up_event(
            right_click_event(position=self.screen_position_off_the_frames()),
        )

        assert result, 'Film strip should return True for a right-click inside its bounds'

    def test_right_click_when_invisible_returns_false(self):
        """Test that right-click when sprite is invisible returns False."""
        self.film_strip_sprite.visible = False

        result = self.film_strip_sprite.on_right_mouse_button_up_event(
            right_click_event(position=self.screen_position_of_frame(0)),
        )

        assert not result, 'Film strip should return False when sprite is invisible'

    def test_right_click_without_widget_returns_false(self):
        """Test that right-click without widget returns False."""
        position = self.screen_position_of_frame(0)
        self.film_strip_sprite.film_strip_widget = None

        result = self.film_strip_sprite.on_right_mouse_button_up_event(
            right_click_event(position=position),
        )

        assert not result, 'Film strip should return False when no widget'

    def test_event_coordinate_conversion(self):
        """Test that screen coordinates are converted to film strip coordinates.

        The strip sits away from the screen origin, so only a converted position lands on
        frame 2 and samples frame 2's colour.
        """
        assert self.film_strip_sprite.rect.topleft != (0, 0)

        self.film_strip_sprite.on_right_mouse_button_up_event(
            right_click_event(position=self.screen_position_of_frame(FRAME_INDEX_2)),
        )

        expected_color = frame_color_for_index(
            base_color=BASE_FRAME_COLOR,
            frame_index=FRAME_INDEX_2,
        )
        assert tuple(self.scene.color_well.active_color) == (*expected_color, OPAQUE_ALPHA)

    def test_frame_selection_takes_priority_over_onion_skinning(self):
        """Test that a right-click on a frame samples its colour and leaves onion skinning."""
        onion_manager = get_onion_skinning_manager()
        onion_state_before = onion_manager.is_frame_onion_skinned('idle', 1)

        result = self.film_strip_sprite.on_right_mouse_button_up_event(
            right_click_event(position=self.screen_position_of_frame(1)),
        )

        assert result
        expected_color = frame_color_for_index(base_color=BASE_FRAME_COLOR, frame_index=1)
        assert tuple(self.scene.color_well.active_color) == (*expected_color, OPAQUE_ALPHA)
        assert onion_manager.is_frame_onion_skinned('idle', 1) == onion_state_before
