"""Tests for film strip selection behavior.

This module tests the film strip selection system to ensure that:
1. Animation preview clicks preserve the selected frame
2. Frame insertion works correctly
3. Strip switching preserves individual strip selections

Every test runs a real Bitmappy editor on the real display, with a sprite of two
four-frame animations ('walk' and 'run'), each shown in its own film strip.
"""

import pygame
import pytest
from src.apps.bitmappy.tests.film_strip_support import (
    PIXEL_SIZE,
    PIXELS_ACROSS,
    PIXELS_TALL,
    make_real_animated_sprite,
)

from bitmappy.editor import BitmapEditorScene
from bitmappy.film_strip import FilmTabWidget
from glitchygames import events

# Test constants to avoid magic values
TEST_FRAME_COUNT_2 = 2


def find_empty_strip_position(film_strip):
    """Find a strip-local position inside the strip that is on no frame, label, tab or button.

    Returns:
        tuple[int, int]: The strip-local position.

    Raises:
        AssertionError: If the strip has no empty area.

    """
    occupied_rects = [
        *film_strip.frame_layouts.values(),
        *film_strip.preview_rects.values(),
        *film_strip.animation_layouts.values(),
        *film_strip.removal_button_layouts.values(),
        *(tab.rect for tab in film_strip.film_tabs),
    ]
    for local_y in range(0, film_strip.rect.height, 4):
        for local_x in range(0, film_strip.rect.width, 4):
            if not any(rect.collidepoint(local_x, local_y) for rect in occupied_rects):
                return (local_x, local_y)
    message = 'The film strip has no empty area'
    raise AssertionError(message)


def click_frame(editor, *, animation_name, frame_index):
    """Left-click a frame's thumbnail in its film strip with a real mouse event."""
    film_strip_sprite = editor.film_strip_sprites[animation_name]
    frame_rect = film_strip_sprite.film_strip_widget.frame_layouts[animation_name, frame_index]
    film_strip_sprite.on_left_mouse_button_down_event(
        events.HashableEvent(
            pygame.MOUSEBUTTONDOWN,
            pos=(
                film_strip_sprite.rect.x + frame_rect.centerx,
                film_strip_sprite.rect.y + frame_rect.centery,
            ),
            button=1,
        ),
    )


class TestFilmStripSelection:
    """Test film strip selection behavior."""

    @pytest.fixture
    def editor(self):
        """Build a real editor scene showing 'walk' and 'run', four frames each.

        Returns:
            BitmapEditorScene: The editor.

        """
        scene = BitmapEditorScene(
            options={
                'pixels_across': PIXELS_ACROSS,
                'pixels_tall': PIXELS_TALL,
                'pixel_size': PIXEL_SIZE,
            },
        )
        scene.film_strip_coordinator.on_sprite_loaded(
            make_real_animated_sprite(frame_counts={'walk': 4, 'run': 4}),
        )
        return scene

    @pytest.fixture
    def film_strip_widget(self, editor):
        """The editor's 'walk' film strip, with frame 2 selected by a click on it.

        Returns:
            FilmStripWidget: The 'walk' film strip.

        """
        click_frame(editor, animation_name='walk', frame_index=TEST_FRAME_COUNT_2)
        assert editor.selected_animation == 'walk'
        assert editor.selected_frame == TEST_FRAME_COUNT_2
        return editor.film_strips['walk']

    def test_animation_preview_click_preserves_selected_frame(self, film_strip_widget):
        """Test that clicking on animation preview preserves the selected frame."""
        preview_pos = film_strip_widget.preview_rects['walk'].center

        result = film_strip_widget.handle_click(preview_pos)

        # Should return the selected frame (2), not reset to 0
        assert result is not None
        animation, frame_idx = result
        assert animation == 'walk'
        assert frame_idx == TEST_FRAME_COUNT_2, (
            f'Expected frame {TEST_FRAME_COUNT_2}, got {frame_idx}'
        )
        assert film_strip_widget.selected_frame == TEST_FRAME_COUNT_2

    def test_frame_insertion_initializes_selection_correctly(self, editor, film_strip_widget):
        """Test that inserting a frame before frame 0 selects the new frame 0."""
        before_first_tab = next(
            tab
            for tab in film_strip_widget.film_tabs
            if type(tab) is FilmTabWidget
            and tab.insertion_type == 'before'
            and tab.target_frame_index == 0
        )

        film_strip_widget._insert_frame_at_tab(before_first_tab)

        # The scene selects the new frame
        assert editor.selected_animation == 'walk'
        assert editor.selected_frame == 0
        # The film strip shows the same selection
        assert film_strip_widget.selected_frame == 0
        assert len(film_strip_widget.animated_sprite.animations['walk']) == 5

    def test_strip_switching_preserves_individual_selections(self, editor, film_strip_widget):
        """Test that switching strips preserves individual strip selections."""
        second_strip = editor.film_strips['run']

        # Switch to the second strip by clicking its frame 1
        click_frame(editor, animation_name='run', frame_index=1)

        # First strip is deselected but keeps its selected frame
        assert not film_strip_widget.is_selected
        assert film_strip_widget.selected_frame == TEST_FRAME_COUNT_2
        # Second strip is selected at frame 1
        assert second_strip.is_selected
        assert second_strip.selected_frame == 1

        # Switch back to the first strip at its preserved selection
        click_frame(editor, animation_name='walk', frame_index=TEST_FRAME_COUNT_2)

        assert film_strip_widget.is_selected
        assert film_strip_widget.selected_frame == TEST_FRAME_COUNT_2
        assert not second_strip.is_selected
        assert second_strip.selected_frame == 1

    def test_animation_label_click_enters_edit_mode(self, film_strip_widget):
        """Test that clicking on animation label enters rename edit mode."""
        label_pos = film_strip_widget.animation_layouts['walk'].center
        assert film_strip_widget.get_frame_at_position(label_pos) is None

        result = film_strip_widget.handle_click(label_pos)

        # Animation label clicks enter edit mode for renaming, returning None
        assert result is None
        assert film_strip_widget.editing_animation == 'walk'
        assert film_strip_widget.original_animation_name == 'walk'
        # Entering edit mode does not change the selected frame
        assert film_strip_widget.selected_frame == TEST_FRAME_COUNT_2

    def test_frame_click_updates_selection(self, editor):
        """Test that clicking on a specific frame updates the selection."""
        film_strip_widget = editor.film_strips['walk']
        frame_pos = film_strip_widget.frame_layouts['walk', TEST_FRAME_COUNT_2].center

        result = film_strip_widget.handle_click(frame_pos)

        assert result == ('walk', TEST_FRAME_COUNT_2)
        assert film_strip_widget.selected_frame == TEST_FRAME_COUNT_2

    def test_multiple_strips_independent_selections(self, editor):
        """Test that multiple strips maintain independent selections."""
        strip1 = editor.film_strips['walk']
        strip2 = editor.film_strips['run']
        strip2.selected_frame = 1

        editor.selected_animation = 'walk'
        editor.selected_frame = 2
        editor.update_film_strip_selection_state()

        # Strip 1 is selected with frame 2; strip 2 keeps its own selection
        assert strip1.is_selected
        assert strip1.selected_frame == TEST_FRAME_COUNT_2
        assert not strip2.is_selected
        assert strip2.selected_frame == 1

        editor.selected_animation = 'run'
        editor.selected_frame = 1
        editor.update_film_strip_selection_state()

        # Strip 2 is selected with frame 1; strip 1 keeps its own selection
        assert strip2.is_selected
        assert strip2.selected_frame == 1
        assert not strip1.is_selected
        assert strip1.selected_frame == TEST_FRAME_COUNT_2

    def test_click_handlers_use_global_selection(self, editor, film_strip_widget):
        """Test that a preview click uses the scene's global selection, not the strip's own."""
        # Mismatch: the strip thinks frame 0 is selected, the scene thinks frame 2 is
        film_strip_widget.selected_frame = 0
        assert editor.selected_frame == TEST_FRAME_COUNT_2

        result = film_strip_widget.handle_click(film_strip_widget.preview_rects['walk'].center)

        assert result is not None
        _, frame_idx = result
        assert frame_idx == TEST_FRAME_COUNT_2, (
            f'Expected frame {TEST_FRAME_COUNT_2} (global), got {frame_idx}'
        )

    @pytest.mark.xfail(
        strict=True,
        reason=(
            'Production bug: FilmStripEventHandler.handle_click tests the strip-local click '
            "position against the widget's screen rect (film_strip_events.py, parent strip "
            'path), so in the editor, where strips sit right of the canvas, a click on a '
            "strip's empty area selects nothing"
        ),
    )
    def test_parent_strip_click_selects_itself(self, editor, film_strip_widget):
        """Test that clicking on the strip's empty area selects the strip at the global frame."""
        film_strip_widget.selected_frame = 0
        editor.film_strip_coordinator.switch_to_film_strip('run', TEST_FRAME_COUNT_2)
        empty_position = find_empty_strip_position(film_strip_widget)

        result = film_strip_widget.handle_click(empty_position)

        assert result == ('walk', TEST_FRAME_COUNT_2)
        assert film_strip_widget.selected_frame == TEST_FRAME_COUNT_2

    @pytest.mark.xfail(
        strict=True,
        reason=(
            'Production bug: a click on the empty area of a film strip in the editor does '
            'not select that strip (handle_click compares the strip-local position with the '
            "widget's screen rect)"
        ),
    )
    def test_clicking_a_strips_empty_area_on_screen_selects_that_strip(
        self,
        editor,
        film_strip_widget,
    ):
        """Test that a real mouse click on the empty area of the 'walk' strip selects 'walk'."""
        editor.film_strip_coordinator.switch_to_film_strip('run', 1)
        film_strip_sprite = editor.film_strip_sprites['walk']
        local_x, local_y = find_empty_strip_position(film_strip_widget)

        film_strip_sprite.on_left_mouse_button_down_event(
            events.HashableEvent(
                pygame.MOUSEBUTTONDOWN,
                pos=(film_strip_sprite.rect.x + local_x, film_strip_sprite.rect.y + local_y),
                button=1,
            ),
        )

        assert editor.selected_animation == 'walk'

    def test_parent_strip_click_at_the_origin_selects_the_strip(self, editor, film_strip_widget):
        """Test the parent strip path where it works: a strip whose screen rect is at (0, 0).

        Strip-local and screen positions then coincide, so the click reaches the path that
        selects the strip at the scene's global frame.
        """
        film_strip_widget.rect.topleft = (0, 0)
        film_strip_widget.selected_frame = 0
        assert editor.selected_frame == TEST_FRAME_COUNT_2
        empty_position = find_empty_strip_position(film_strip_widget)

        result = film_strip_widget.handle_click(empty_position)

        assert result == ('walk', TEST_FRAME_COUNT_2)
        assert film_strip_widget.selected_frame == TEST_FRAME_COUNT_2
