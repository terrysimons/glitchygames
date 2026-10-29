"""Test suite for MultiLineTextBox cursor behavior with text wrapping.

This module tests cursor positioning and behavior when long lines are automatically
wrapped to multiple lines, which is a common issue in text editors. The text box draws
with the real default font (FontManager) on real surfaces; expected positions are derived
from the wrapped text, so they follow the font's metrics.
"""

import numpy as np
import pygame
import pytest

from glitchygames.fonts import FontManager
from glitchygames.ui import MultiLineTextBox

# Test constants to avoid magic values
TEST_CURSOR_POSITION_20 = 20
TEXT_PADDING = 5
CURSOR_HEIGHT = 20

LONG_TEXT = (
    'This is a very long line that will definitely be wrapped to '
    'multiple lines because it is much longer than the text box width'
)


def _make_textbox(*, width=150, height=120):
    """Create a MultiLineTextBox at (10, 10).

    Returns:
        MultiLineTextBox: The text box.
    """
    return MultiLineTextBox(x=10, y=10, width=width, height=height, name='TestTextBox')


def _expected_line_and_column(textbox, position):
    """Find a position's wrapped line and column from the wrapped text.

    Wrapping only turns spaces into newlines, so a position in the original text is the same
    position in the wrapped text.

    Returns:
        tuple[int, int]: The wrapped line and column.
    """
    text_before = textbox.text[:position]
    line = text_before.count('\n')
    column = position - (text_before.rfind('\n') + 1)
    return line, column


def _line_start(textbox, line):
    """Return the original-text position where a wrapped line starts.

    Returns:
        int: The position.
    """
    return sum(len(wrapped_line) + 1 for wrapped_line in textbox.text.split('\n')[:line])


def _cursor_pixels(textbox):
    """Find where the cursor is drawn: the pixels a visible cursor changes.

    Returns:
        numpy.ndarray: A (width, height) boolean array of the pixels the cursor drew.
    """
    textbox.cursor_visible = False
    textbox.update()
    without_cursor = pygame.surfarray.array3d(textbox.image)
    textbox.cursor_visible = True
    textbox.update()
    with_cursor = pygame.surfarray.array3d(textbox.image)
    return (with_cursor != without_cursor).any(axis=2)


def _assert_cursor_drawn_at(textbox, line, column):
    """Assert the cursor bar is drawn after `column` characters of wrapped line `line`."""
    line_text = textbox.text.split('\n')[line]
    expected_x = TEXT_PADDING + FontManager.get_font().get_rect(line_text[:column]).width
    expected_top = TEXT_PADDING + (line - textbox.scroll_offset) * textbox._get_line_height()

    changed = _cursor_pixels(textbox)
    changed_columns = np.flatnonzero(changed.any(axis=1))
    changed_rows = np.flatnonzero(changed.any(axis=0))
    assert changed_columns.size, 'the cursor drew nothing'
    assert changed_columns.min() >= expected_x - 1
    assert changed_columns.max() <= expected_x + 1
    assert changed_rows.min() >= expected_top
    assert changed_rows.max() <= expected_top + CURSOR_HEIGHT


def _key_down(key):
    """Build a real key down event without text.

    Returns:
        pygame.event.Event: The event.
    """
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=pygame.KMOD_NONE, unicode='', scancode=0)


def _mouse_down(position):
    """Build a real left mouse button down event.

    Returns:
        pygame.event.Event: The event.
    """
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=position, button=1)


class TestMultiLineTextBoxCursorWrapping:
    """Test MultiLineTextBox cursor behavior with text wrapping."""

    def test_cursor_positioning_with_wrapped_text(self):
        """The cursor at the end of wrapped text is drawn at the end of the last line."""
        textbox = _make_textbox(width=200, height=100)
        long_text = (
            'This is a very long line of text that should be automatically '
            'wrapped to multiple lines when it exceeds the width of the text box'
        )
        textbox.text = long_text
        textbox.is_active = True
        textbox.cursor_pos = len(long_text)

        textbox.update()

        wrapped_lines = textbox.text.split('\n')
        assert len(wrapped_lines) > 1
        assert textbox.text.replace('\n', ' ') == long_text
        assert textbox.cursor_pos == len(long_text)
        last_line = len(wrapped_lines) - 1
        assert textbox._get_cursor_line_and_column_in_wrapped_text(len(long_text)) == (
            last_line,
            len(wrapped_lines[-1]),
        )
        # The text box scrolled so the last line (and the cursor) is visible
        assert textbox.scroll_offset <= last_line < textbox.scroll_offset + textbox.visible_lines
        _assert_cursor_drawn_at(textbox, last_line, len(wrapped_lines[-1]))

    def test_every_wrapped_line_fits_the_text_box(self):
        """Every wrapped line made of several words fits inside the padding."""
        textbox = _make_textbox()
        textbox.text = LONG_TEXT

        font = FontManager.get_font()
        for wrapped_line in textbox.text.split('\n'):
            if ' ' in wrapped_line:
                assert font.get_rect(wrapped_line).width <= textbox.width - 2 * TEXT_PADDING

    def test_cursor_positioning_issue_with_wrapped_text(self):
        """A cursor in the middle of wrapped text is on its wrapped line and column."""
        textbox = _make_textbox()
        textbox.text = LONG_TEXT
        textbox.is_active = True
        cursor_pos = 50
        assert LONG_TEXT[cursor_pos] != ' '
        textbox.cursor_pos = cursor_pos

        textbox.update()

        cursor_line, cursor_column = textbox._get_cursor_line_and_column_in_wrapped_text(cursor_pos)
        assert textbox.cursor_pos == cursor_pos  # Original position is preserved
        assert (cursor_line, cursor_column) == _expected_line_and_column(textbox, cursor_pos)
        assert cursor_line > 0  # Position 50 is past the first wrap
        _assert_cursor_drawn_at(textbox, cursor_line, cursor_column)

    @pytest.mark.xfail(
        strict=True,
        reason=(
            '_map_cursor_pos_to_wrapped_text finds the Nth occurrence of the character under '
            'the cursor, but wrapping turned some spaces into newlines, so a cursor on a space '
            'after the first wrap maps to a later space or the end of the text'
        ),
    )
    def test_cursor_on_a_space_after_a_wrap_is_on_its_own_line_and_column(self):
        """Every cursor position maps to its own line and column in the wrapped text."""
        textbox = _make_textbox()
        textbox.text = LONG_TEXT

        wrong_positions = [
            position
            for position in range(len(LONG_TEXT) + 1)
            if textbox._get_cursor_line_and_column_in_wrapped_text(position)
            != _expected_line_and_column(textbox, position)
        ]

        assert wrong_positions == []

    def test_cursor_positioning_with_mixed_wrapped_and_explicit_newlines(self):
        """Test cursor positioning with both wrapped text and explicit newlines."""
        textbox = _make_textbox()
        mixed_text = 'Line 1\nThis is a very long line that will be wrapped automatically\nLine 3'
        textbox.text = mixed_text
        textbox.is_active = True
        textbox.cursor_pos = len(mixed_text)

        textbox.update()

        wrapped_lines = textbox.text.split('\n')
        # The explicit lines are kept and the long middle line is wrapped
        assert wrapped_lines[0] == 'Line 1'
        assert wrapped_lines[-1] == 'Line 3'
        assert len(wrapped_lines) > len(mixed_text.split('\n'))
        assert textbox.cursor_pos == len(mixed_text)
        assert textbox._get_cursor_line_and_column_in_wrapped_text(len(mixed_text)) == (
            len(wrapped_lines) - 1,
            len('Line 3'),
        )

    def test_cursor_positioning_at_beginning_of_wrapped_line(self):
        """A cursor at the start of a wrapped line is drawn at that line's left edge."""
        textbox = _make_textbox(width=200, height=100)
        long_text = 'This is a very long line of text that should be automatically wrapped'
        textbox.text = long_text
        textbox.is_active = True
        second_line_start = _line_start(textbox, 1)
        assert second_line_start < len(long_text)

        textbox.cursor_pos = second_line_start
        textbox.update()

        assert textbox._get_cursor_line_and_column_in_wrapped_text(second_line_start) == (1, 0)
        _assert_cursor_drawn_at(textbox, 1, 0)

        # Any cursor position keeps its place through an update
        textbox.cursor_pos = TEST_CURSOR_POSITION_20
        textbox.update()
        assert textbox.cursor_pos == TEST_CURSOR_POSITION_20

    def test_cursor_positioning_with_very_long_single_word(self):
        """Test cursor positioning when a single word is longer than the text box width."""
        textbox = _make_textbox(width=100, height=100)
        long_word = 'supercalifragilisticexpialidocious'
        textbox.text = long_word
        textbox.is_active = True
        textbox.cursor_pos = len(long_word)

        textbox.update()

        # A word cannot be split, so it stays on one line
        assert textbox.text == long_word
        assert textbox.cursor_pos == len(long_word)
        assert textbox._get_cursor_line_and_column_in_wrapped_text(len(long_word)) == (
            0,
            len(long_word),
        )

    def test_cursor_blinking_with_wrapped_text(self, mocker):
        """The cursor blinks every cursor_blink_rate milliseconds and keeps its position."""
        textbox = _make_textbox(width=200, height=100)
        long_text = 'This is a very long line that will be wrapped to multiple lines'
        textbox.text = long_text
        textbox.is_active = True
        textbox.cursor_pos = len(long_text)
        clock = mocker.patch(
            'glitchygames.clock.frame_clock_milliseconds',
            return_value=textbox.cursor_blink_time,
        )

        textbox.update()
        assert textbox.cursor_visible is True

        clock.return_value = textbox.cursor_blink_time + textbox.cursor_blink_rate
        textbox.update()
        assert textbox.cursor_visible is False

        clock.return_value = textbox.cursor_blink_time + textbox.cursor_blink_rate
        textbox.update()
        assert textbox.cursor_visible is True

        # Cursor should still be positioned correctly after multiple updates
        assert textbox.cursor_pos == len(long_text)

    def test_mouse_click_positioning_with_wrapped_text(self):
        """A click left of the first line's text puts the cursor at the start of the text."""
        textbox = _make_textbox(width=200, height=100)
        long_text = 'This is a very long line that will be wrapped to multiple lines'
        textbox.text = long_text
        textbox.cursor_pos = len(long_text)

        textbox.on_left_mouse_button_down_event(
            _mouse_down((textbox.rect.x + 1, textbox.rect.y + TEXT_PADDING + 1))
        )

        assert textbox.is_active is True
        assert textbox.cursor_pos == 0

    def test_arrow_key_navigation_with_wrapped_text(self):
        """Up and down move the cursor one wrapped line, keeping its column."""
        textbox = _make_textbox()
        textbox.text = LONG_TEXT
        textbox.is_active = True
        start_position = 50
        textbox.cursor_pos = start_position
        start_line, start_column = _expected_line_and_column(textbox, start_position)
        wrapped_lines = textbox.text.split('\n')

        textbox.on_key_down_event(_key_down(pygame.K_UP))

        up_column = min(start_column, len(wrapped_lines[start_line - 1]))
        assert textbox.cursor_pos == _line_start(textbox, start_line - 1) + up_column

        textbox.on_key_down_event(_key_down(pygame.K_DOWN))

        down_column = min(up_column, len(wrapped_lines[start_line]))
        assert textbox.cursor_pos == _line_start(textbox, start_line) + down_column

    def test_mouse_click_positioning_issue_with_wrapped_text(self):
        """A click at the left edge of the second line puts the cursor where it starts."""
        textbox = _make_textbox()
        textbox.text = LONG_TEXT
        line_height = textbox._get_line_height()

        textbox.on_left_mouse_button_down_event(
            _mouse_down((
                textbox.rect.x + 1,
                textbox.rect.y + TEXT_PADDING + line_height + line_height // 2,
            ))
        )

        assert textbox.is_active is True
        assert textbox.cursor_pos == _line_start(textbox, 1)
