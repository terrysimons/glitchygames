"""Test suite for text sprite cursor functionality.

This module tests TextSprite cursor blinking, input handling, and visual updates, drawn with
the real font on real surfaces.
"""

import numpy as np
import pygame
import pytest

from glitchygames.color import WHITE
from glitchygames.fonts import FontManager
from glitchygames.ui import TextSprite

# Test constants to avoid magic values
TEST_CURSOR_BLINK_RATE = 2
EDITING_BACKGROUND_COLOR = (50, 50, 50)
CURSOR_WIDTH = 2


def _make_text_sprite(text='Test', **keyword_arguments):
    """Create a 100x30 TextSprite at (10, 20).

    Returns:
        TextSprite: The sprite.
    """
    return TextSprite(
        x=10, y=20, width=100, height=30, text=text, name='TestText', **keyword_arguments
    )


def _rgb_pixels(surface):
    """Copy a surface's RGB pixels (the alpha is not the point here).

    Returns:
        numpy.ndarray: A (width, height, 3) array.
    """
    return pygame.surfarray.array3d(surface)


def _columns_drawn_in(rgb_pixels, color):
    """List the x columns holding at least one pixel of a colour.

    Returns:
        list[int]: The column indexes, ascending.
    """
    return np.flatnonzero((rgb_pixels == color[:3]).all(axis=2).any(axis=1)).tolist()


def _draw_active(text_sprite, *, cursor_visible):
    """Redraw an active text sprite with the cursor shown or hidden.

    Returns:
        numpy.ndarray: The redrawn image's RGB pixels.
    """
    text_sprite.is_active = True
    text_sprite._cursor_visible = cursor_visible
    text_sprite.update_text(text_sprite.text)
    return _rgb_pixels(text_sprite.image)


class TestTextSpriteCursorFunctionality:
    """Test TextSprite cursor functionality."""

    def test_text_sprite_cursor_initialization(self):
        """Test TextSprite cursor initialization."""
        # Act
        text_sprite = _make_text_sprite()

        # Assert
        assert text_sprite._cursor_timer == 0
        assert text_sprite._cursor_visible is True
        # The text is drawn in its colour on the background colour
        rgb_pixels = _rgb_pixels(text_sprite.image)
        assert tuple(rgb_pixels[0, 0]) == text_sprite.background_color[:3]
        assert _columns_drawn_in(rgb_pixels, WHITE)

    def test_text_sprite_cursor_blinking_when_active(self):
        """Test TextSprite cursor blinking when active."""
        text_sprite = _make_text_sprite()
        text_sprite.is_active = True
        text_sprite._cursor_timer = 0
        text_sprite._cursor_visible = False

        # Act - simulate time passing
        text_sprite.update()

        # Assert - should set dirty flag for redraw
        assert text_sprite.dirty == TEST_CURSOR_BLINK_RATE

    def test_text_sprite_cursor_not_blinking_when_inactive(self):
        """Test TextSprite cursor not blinking when inactive."""
        text_sprite = _make_text_sprite()
        text_sprite.is_active = False

        # Act
        text_sprite.update()

        # Assert - should set dirty flag to 1 (not 2 for cursor)
        assert text_sprite.dirty == 1
        assert text_sprite._cursor_timer == 0

    def test_text_sprite_cursor_timer_increment(self):
        """Test TextSprite cursor timer increment."""
        text_sprite = _make_text_sprite()
        text_sprite.is_active = True
        text_sprite._cursor_timer = 0

        # Act
        text_sprite.update()

        # Assert - timer should increment by one frame
        assert text_sprite._cursor_timer == 1

    def test_text_sprite_cursor_visibility_toggle(self):
        """Test TextSprite cursor visibility toggle."""
        text_sprite = _make_text_sprite()
        text_sprite.is_active = True
        text_sprite._cursor_visible = False

        # Act - simulate enough time for cursor to toggle
        text_sprite._cursor_timer = 500
        text_sprite.update()

        # Assert - cursor visibility should toggle, and the cursor is now drawn
        assert text_sprite._cursor_visible is True
        drawn_by_update = _rgb_pixels(text_sprite.image)
        hidden_cursor_pixels = _draw_active(text_sprite, cursor_visible=False)
        assert not np.array_equal(drawn_by_update, hidden_cursor_pixels)

    def test_text_sprite_cursor_draw_when_visible(self):
        """A visible cursor is a 2 px text-coloured bar just right of the text."""
        text_sprite = _make_text_sprite()

        without_cursor = _draw_active(text_sprite, cursor_visible=False)
        with_cursor = _draw_active(text_sprite, cursor_visible=True)

        changed = (with_cursor != without_cursor).any(axis=2)
        changed_columns = np.flatnonzero(changed.any(axis=1)).tolist()
        assert changed_columns, 'the cursor drew nothing'
        assert len(changed_columns) <= CURSOR_WIDTH
        # Every pixel the cursor changed is in the text colour
        assert (with_cursor[changed] == text_sprite.text_color[:3]).all()
        # The cursor sits right of every text pixel (none of the text is in its columns)
        text_columns = _columns_drawn_in(without_cursor, text_sprite.text_color)
        assert min(changed_columns) > max(text_columns)
        # It is a vertical bar: taller than it is wide
        changed_rows = np.flatnonzero(changed.any(axis=0))
        assert len(changed_rows) > CURSOR_WIDTH

    def test_text_sprite_cursor_draw_when_invisible(self):
        """An invisible cursor draws nothing: only the text is on the editing background."""
        text_sprite = _make_text_sprite()

        without_cursor = _draw_active(text_sprite, cursor_visible=False)

        text_columns = _columns_drawn_in(without_cursor, text_sprite.text_color)
        # Nothing in the text colour right of the text (where the cursor would be)
        assert not (without_cursor[max(text_columns) + 1 :] == WHITE).all(axis=2).any()
        assert tuple(without_cursor[0, 0]) == EDITING_BACKGROUND_COLOR

    def test_text_sprite_cursor_skips_a_text_rect_it_cannot_read(self):
        """The cursor's guard for unreadable text rects skips drawing instead of raising.

        The guard (``except TypeError, AttributeError`` in ``_draw_cursor``) exists for mock
        objects in tests: a real ``update_text`` always passes a real Rect, so it is called
        directly here.
        """
        text_sprite = _make_text_sprite()
        text_sprite.is_active = True
        before = _rgb_pixels(text_sprite.image)

        text_sprite._draw_cursor(None, FontManager.get_font())  # ty: ignore[invalid-argument-type]

        assert np.array_equal(_rgb_pixels(text_sprite.image), before)

    def test_text_sprite_cursor_outside_the_sprite_is_not_drawn(self):
        """A cursor that would start past the sprite's right edge is not drawn."""
        text_sprite = _make_text_sprite()
        text_sprite.is_active = True
        text_sprite._cursor_visible = True
        before = _rgb_pixels(text_sprite.image)

        text_sprite._draw_cursor(pygame.Rect(90, 5, 10, 20), FontManager.get_font())

        assert np.array_equal(_rgb_pixels(text_sprite.image), before)

    def test_text_sprite_cursor_reset_on_deactivation(self):
        """Test TextSprite cursor resets on deactivation."""
        text_sprite = _make_text_sprite()
        text_sprite.is_active = True
        text_sprite._cursor_timer = 100
        text_sprite._cursor_visible = True

        # Act - deactivate
        text_sprite.is_active = False
        text_sprite.update()

        # Assert - should set dirty flag to 1 (not 2 for cursor), back on the normal background
        assert text_sprite.dirty == 1
        rgb_pixels = _rgb_pixels(text_sprite.image)
        assert tuple(rgb_pixels[0, 0]) == text_sprite.background_color[:3]

    def test_text_sprite_cursor_continuous_updates_when_active(self):
        """Test TextSprite cursor provides continuous updates when active."""
        text_sprite = _make_text_sprite()
        text_sprite.is_active = True

        # Act - multiple updates
        text_sprite.update()
        text_sprite.update()
        text_sprite.update()

        # Assert - should set dirty flag to 2 for cursor updates
        assert text_sprite.dirty == TEST_CURSOR_BLINK_RATE
        assert text_sprite._cursor_timer == 3

    def test_text_sprite_cursor_timer_wraparound(self):
        """Test TextSprite cursor timer wraparound behavior."""
        text_sprite = _make_text_sprite()
        text_sprite.is_active = True
        text_sprite._cursor_timer = 1000  # Max timer value

        # Act
        text_sprite.update()

        # Assert - timer should wrap around
        assert text_sprite._cursor_timer == 0

    @pytest.mark.xfail(
        strict=True,
        reason=(
            'An active TextSprite fills its image with the editing background (50, 50, 50) but '
            'renders its text with background_color as the text background, so a '
            'background_color box surrounds the text while editing (e.g. the black box of a '
            "slider's value field)"
        ),
    )
    def test_active_text_is_drawn_on_the_editing_background(self):
        """While editing, no pixel keeps the inactive background colour."""
        text_sprite = _make_text_sprite(background_color=(0, 0, 0))

        rgb_pixels = _draw_active(text_sprite, cursor_visible=False)

        assert not (rgb_pixels == (0, 0, 0)).all(axis=2).any()
