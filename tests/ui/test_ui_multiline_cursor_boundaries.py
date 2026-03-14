"""Test suite for MultiLineTextBox cursor boundary conditions.

This module comprehensively tests cursor positioning, especially at line
boundaries and end-of-line positions where off-by-one errors commonly occur.

The tests focus on the cursor positioning bug where the cursor cannot reach
the very last character of a line - it's always 1 character short.
"""

import pygame
import pytest
from glitchygames.ui import MultiLineTextBox

from tests.mocks import MockFactory


# Test constants to avoid magic values
TEST_TEXTBOX_X = 10
TEST_TEXTBOX_Y = 10
TEST_TEXTBOX_WIDTH_NARROW = 150
TEST_TEXTBOX_WIDTH_MEDIUM = 200
TEST_TEXTBOX_WIDTH_WIDE = 400
TEST_TEXTBOX_HEIGHT = 120
TEST_PADDING = 5
TEST_LINE_HEIGHT = 24

# Sample text constants
TEST_SHORT_TEXT = "Hello"
TEST_REPEATED_CHARS = "aaaaaaaaaa"
TEST_LONG_TEXT = "This is a very long line of text that will definitely wrap to multiple lines"
TEST_MULTILINE_TEXT = "Line 1\nLine 2\nLine 3"
TEST_EMPTY_LINES_TEXT = "Line 1\n\n\nLine 4"


class TestMultiLineTextBoxCursorBoundaries:
    """Test MultiLineTextBox cursor behavior at boundaries."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        MockFactory.setup_pygame_mocks_with_mocker(mocker)
        pygame.init()
        pygame.display.set_mode((800, 600), pygame.HIDDEN)

    def _create_textbox(self, mocker, width=TEST_TEXTBOX_WIDTH_MEDIUM, text=""):
        """Create a test textbox with proper font mocking.

        Args:
            mocker: pytest-mock mocker fixture
            width: Width of the textbox (affects wrapping)
            text: Initial text content

        Returns:
            Configured MultiLineTextBox instance
        """
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font
        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=width,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        if text:
            textbox.text = text
        textbox.active = True
        return textbox

    def _simulate_key_press(self, mocker, textbox, key, unicode_char=""):
        """Simulate a key press event.

        Args:
            mocker: pytest-mock mocker fixture
            textbox: The textbox to send the event to
            key: pygame key constant (e.g., pygame.K_RIGHT)
            unicode_char: Unicode character for text input events
        """
        mock_event = mocker.Mock()
        mock_event.key = key
        mock_event.unicode = unicode_char
        textbox.on_key_down_event(mock_event)

    def _simulate_mouse_click(self, mocker, textbox, x_offset, y_offset):
        """Simulate mouse click at offset from textbox origin.

        Args:
            mocker: pytest-mock mocker fixture
            textbox: The textbox to click on
            x_offset: X offset from textbox left edge
            y_offset: Y offset from textbox top edge
        """
        mock_event = mocker.Mock()
        mock_event.pos = (textbox.rect.x + x_offset, textbox.rect.y + y_offset)
        textbox.on_left_mouse_button_down_event(mock_event)

    # =========================================================================
    # Section 1: End-of-Line Cursor Positioning Tests
    # =========================================================================

    def test_cursor_reaches_last_character_single_line(self, mocker):
        """Test cursor can reach the very last character of a single line.

        This is the core bug test: cursor should be able to reach position
        len(text), not len(text) - 1.
        """
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,  # Wide enough to avoid wrapping
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = TEST_SHORT_TEXT  # "Hello" - 5 characters
        textbox.active = True

        # Set cursor to the end (position 5, after the 'o')
        textbox.cursor_pos = len(TEST_SHORT_TEXT)

        # Verify cursor position is exactly at end
        assert textbox.cursor_pos == 5, (
            f"Cursor should reach position 5 (end of 'Hello'), got {textbox.cursor_pos}"
        )

        # Verify the cursor position maps correctly
        line, column = textbox._get_cursor_line_and_column_in_wrapped_text(textbox.cursor_pos)
        assert line == 0, f"Cursor should be on line 0, got {line}"
        assert column == 5, f"Cursor column should be 5, got {column}"

    def test_cursor_reaches_last_character_multi_line(self, mocker):
        """Test cursor can reach last character on each line of multi-line text."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = TEST_MULTILINE_TEXT  # "Line 1\nLine 2\nLine 3"
        textbox.active = True

        # Test cursor at end of each line
        # Line 1 ends at position 6 (just before \n)
        textbox.cursor_pos = 6
        line, column = textbox._get_cursor_line_and_column_in_wrapped_text(textbox.cursor_pos)
        assert line == 0, f"Position 6 should be on line 0, got {line}"
        assert column == 6, f"Position 6 should have column 6, got {column}"

        # Line 2 starts at position 7, ends at position 13
        textbox.cursor_pos = 13
        line, column = textbox._get_cursor_line_and_column_in_wrapped_text(textbox.cursor_pos)
        assert line == 1, f"Position 13 should be on line 1, got {line}"
        assert column == 6, f"Position 13 should have column 6, got {column}"

        # End of text (position 20)
        textbox.cursor_pos = len(TEST_MULTILINE_TEXT)
        assert textbox.cursor_pos == 20, f"End position should be 20, got {textbox.cursor_pos}"

    def test_cursor_at_end_after_explicit_newline(self, mocker):
        """Test cursor position immediately after an explicit newline character."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = "Line 1\nLine 2"
        textbox.active = True

        # Position cursor right after the newline (start of Line 2)
        textbox.cursor_pos = 7  # Position after "Line 1\n"
        line, column = textbox._get_cursor_line_and_column_in_wrapped_text(textbox.cursor_pos)
        assert line == 1, f"Position 7 should be on line 1, got {line}"
        assert column == 0, f"Position 7 should have column 0, got {column}"

    def test_cursor_at_end_of_wrapped_line(self, mocker):
        """Test cursor can reach end of automatically wrapped line."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_NARROW,  # Narrow to force wrapping
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = TEST_LONG_TEXT
        textbox.active = True

        # Set cursor to absolute end
        textbox.cursor_pos = len(TEST_LONG_TEXT)
        assert textbox.cursor_pos == len(TEST_LONG_TEXT), (
            f"Cursor should reach end position {len(TEST_LONG_TEXT)}, "
            f"got {textbox.cursor_pos}"
        )

    # =========================================================================
    # Section 2: Keyboard Navigation Boundary Tests
    # =========================================================================

    def test_right_arrow_at_end_of_line_moves_to_next_line(self, mocker):
        """Test right arrow at end of line moves cursor to start of next line."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = "AB\nCD"
        textbox.active = True

        # Position at end of line 1 (position 2, before newline)
        textbox.cursor_pos = 2
        self._simulate_key_press(mocker, textbox, pygame.K_RIGHT)

        # Should now be at position 3 (the newline character position)
        assert textbox.cursor_pos == 3, (
            f"Right arrow should move to position 3, got {textbox.cursor_pos}"
        )

    def test_left_arrow_at_start_of_line_moves_to_prev_line_end(self, mocker):
        """Test left arrow at position 0 of line moves to end of previous line."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = "AB\nCD"
        textbox.active = True

        # Position at start of line 2 (position 3, right after newline)
        textbox.cursor_pos = 3
        self._simulate_key_press(mocker, textbox, pygame.K_LEFT)

        # Should now be at position 2 (end of "AB")
        assert textbox.cursor_pos == 2, (
            f"Left arrow should move to position 2, got {textbox.cursor_pos}"
        )

    def test_right_arrow_at_absolute_end(self, mocker):
        """Test right arrow at very end of text does not crash or move past end."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = TEST_SHORT_TEXT
        textbox.active = True

        # Position at absolute end
        textbox.cursor_pos = len(TEST_SHORT_TEXT)
        self._simulate_key_press(mocker, textbox, pygame.K_RIGHT)

        # Should still be at end, not beyond
        assert textbox.cursor_pos == len(TEST_SHORT_TEXT), (
            f"Cursor should stay at end, got {textbox.cursor_pos}"
        )

    def test_left_arrow_at_absolute_start(self, mocker):
        """Test left arrow at position 0 does not crash or go negative."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = TEST_SHORT_TEXT
        textbox.active = True

        # Position at start
        textbox.cursor_pos = 0
        self._simulate_key_press(mocker, textbox, pygame.K_LEFT)

        # Should still be at 0, not negative
        assert textbox.cursor_pos == 0, (
            f"Cursor should stay at 0, got {textbox.cursor_pos}"
        )

    def test_down_arrow_preserves_column_when_possible(self, mocker):
        """Test down arrow maintains column position when next line is long enough."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = "ABCDEF\nGHIJKL"
        textbox.active = True

        # Position at column 3 on line 1
        textbox.cursor_pos = 3
        self._simulate_key_press(mocker, textbox, pygame.K_DOWN)

        # Should be at column 3 on line 2 (position 10: 7 for line1+newline + 3)
        # "ABCDEF\n" = 7 chars, position 10 = 'J'
        assert textbox.cursor_pos == 10, (
            f"Down arrow should move to position 10, got {textbox.cursor_pos}"
        )

    def test_up_arrow_preserves_column_when_possible(self, mocker):
        """Test up arrow maintains column position when previous line is long enough."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = "ABCDEF\nGHIJKL"
        textbox.active = True

        # Position at column 3 on line 2 (position 10)
        textbox.cursor_pos = 10
        self._simulate_key_press(mocker, textbox, pygame.K_UP)

        # Should be at column 3 on line 1 (position 3)
        assert textbox.cursor_pos == 3, (
            f"Up arrow should move to position 3, got {textbox.cursor_pos}"
        )

    # =========================================================================
    # Section 3: Mouse Click Positioning Tests
    # =========================================================================

    def test_mouse_click_at_exact_character_boundary(self, mocker):
        """Test mouse click exactly at character boundary positions cursor correctly."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = "ABCD"
        textbox.active = True

        # Click at position (5 + padding, 5 + padding) - should be near start
        self._simulate_mouse_click(mocker, textbox, TEST_PADDING, TEST_PADDING)

        # Cursor should be at or near position 0
        assert textbox.cursor_pos >= 0, "Cursor position should be non-negative"
        assert textbox.cursor_pos <= len("ABCD"), "Cursor should not exceed text length"

    def test_mouse_click_past_end_of_line(self, mocker):
        """Test clicking past the last character positions cursor at end of line."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = "Short"
        textbox.active = True

        # Click far to the right of the text (past all characters)
        self._simulate_mouse_click(mocker, textbox, TEST_TEXTBOX_WIDTH_WIDE - 20, TEST_PADDING + 5)

        # Cursor should be at position 5 (end of "Short")
        assert textbox.cursor_pos == 5, (
            f"Click past end should position cursor at 5, got {textbox.cursor_pos}"
        )

    def test_mouse_click_on_wrapped_second_line(self, mocker):
        """Test mouse click on automatically wrapped line maps to correct position."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_NARROW,  # Force wrapping
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = TEST_LONG_TEXT
        textbox.active = True

        # Get line height for clicking on second line
        line_height = font.get_linesize()

        # Click on the second line (y = padding + line_height + some offset)
        self._simulate_mouse_click(mocker, textbox, 50, TEST_PADDING + line_height + 5)

        # Cursor should be somewhere in the text, not at 0
        assert textbox.cursor_pos >= 0, "Cursor should be non-negative"
        assert textbox.cursor_pos <= len(TEST_LONG_TEXT), "Cursor should not exceed text"

    def test_mouse_click_on_empty_line(self, mocker):
        """Test mouse click on empty line (just newline) positions cursor correctly."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = "Line 1\n\nLine 3"  # Empty line in middle
        textbox.active = True

        # Get line height for clicking on second line (the empty one)
        line_height = font.get_linesize()

        # Click on the empty second line
        self._simulate_mouse_click(mocker, textbox, 50, TEST_PADDING + line_height + 5)

        # Cursor should be at position 7 (right after first newline)
        assert textbox.cursor_pos == 7, (
            f"Click on empty line should position cursor at 7, got {textbox.cursor_pos}"
        )

    # =========================================================================
    # Section 4: Repeated Character Stress Tests
    # =========================================================================

    def test_cursor_with_all_same_characters(self, mocker):
        """Test cursor positioning in text with all identical characters.

        This stress tests the character-matching algorithm which counts
        character occurrences. With 'aaaa', positions 0-4 should all work.
        """
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = TEST_REPEATED_CHARS  # "aaaaaaaaaa" (10 chars)
        textbox.active = True

        # Test that all positions 0-10 work correctly
        for position in range(len(TEST_REPEATED_CHARS) + 1):
            textbox.cursor_pos = position
            line, column = textbox._get_cursor_line_and_column_in_wrapped_text(position)
            assert line == 0, f"Position {position} should be on line 0"
            assert column == position, (
                f"Position {position} should have column {position}, got {column}"
            )

    def test_cursor_with_repeated_patterns(self, mocker):
        """Test cursor in text with repeating patterns like 'abcabc'."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = "abcabc"  # Repeating pattern
        textbox.active = True

        # Test positions that would confuse character-matching algorithm
        # Position 0 is first 'a', position 3 is second 'a'
        for position in range(7):  # 0-6 inclusive
            textbox.cursor_pos = position
            line, column = textbox._get_cursor_line_and_column_in_wrapped_text(position)
            assert column == position, (
                f"Position {position} should have column {position}, got {column}"
            )

    def test_cursor_with_spaces_only(self, mocker):
        """Test cursor positioning in text that is only spaces."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = "     "  # 5 spaces
        textbox.active = True

        # Test all positions work
        for position in range(6):  # 0-5 inclusive
            textbox.cursor_pos = position
            line, column = textbox._get_cursor_line_and_column_in_wrapped_text(position)
            assert column == position, (
                f"Position {position} should have column {position}, got {column}"
            )

    # =========================================================================
    # Section 5: Mixed Newlines and Wrapping Tests
    # =========================================================================

    def test_explicit_newline_followed_by_long_line(self, mocker):
        """Test cursor when explicit newline is followed by auto-wrapped line."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_NARROW,  # Force wrapping
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = "A\n" + TEST_LONG_TEXT
        textbox.active = True

        # Cursor at start of long text (position 2)
        textbox.cursor_pos = 2
        line, column = textbox._get_cursor_line_and_column_in_wrapped_text(2)
        assert line >= 1, f"Position 2 should be on line >= 1, got {line}"

    def test_multiple_explicit_newlines_in_sequence(self, mocker):
        """Test cursor positioning with consecutive newlines (empty lines)."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = TEST_EMPTY_LINES_TEXT  # "Line 1\n\n\nLine 4"
        textbox.active = True

        # Position at each newline and verify correct line
        # Line 1 ends at position 6, first \n is at 6
        textbox.cursor_pos = 7  # After first newline (empty line 2)
        line, column = textbox._get_cursor_line_and_column_in_wrapped_text(7)
        assert line == 1, f"Position 7 should be on line 1, got {line}"
        assert column == 0, f"Position 7 should have column 0, got {column}"

        textbox.cursor_pos = 8  # After second newline (empty line 3)
        line, column = textbox._get_cursor_line_and_column_in_wrapped_text(8)
        assert line == 2, f"Position 8 should be on line 2, got {line}"
        assert column == 0, f"Position 8 should have column 0, got {column}"

    def test_wrapped_line_ending_with_explicit_newline(self, mocker):
        """Test auto-wrapped line that also ends with explicit newline."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_NARROW,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = TEST_LONG_TEXT + "\nShort"
        textbox.active = True

        # Position at end of text
        end_pos = len(TEST_LONG_TEXT + "\nShort")
        textbox.cursor_pos = end_pos
        assert textbox.cursor_pos == end_pos, (
            f"Cursor should be at {end_pos}, got {textbox.cursor_pos}"
        )

    # =========================================================================
    # Section 6: Backspace/Delete at Boundaries Tests
    # =========================================================================

    def test_backspace_at_end_of_line(self, mocker):
        """Test backspace at end of line deletes correct character."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = "Hello"
        textbox.active = True

        # Position cursor at end
        textbox.cursor_pos = 5
        self._simulate_key_press(mocker, textbox, pygame.K_BACKSPACE)

        # Should delete 'o', leaving "Hell"
        assert textbox._original_text == "Hell", (
            f"Text should be 'Hell', got '{textbox._original_text}'"
        )
        assert textbox.cursor_pos == 4, (
            f"Cursor should be at 4, got {textbox.cursor_pos}"
        )

    def test_backspace_at_start_of_line_joins_lines(self, mocker):
        """Test backspace at start of line joins with previous line."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = "AB\nCD"
        textbox.active = True

        # Position cursor at start of line 2 (position 3)
        textbox.cursor_pos = 3
        self._simulate_key_press(mocker, textbox, pygame.K_BACKSPACE)

        # Should delete newline, resulting in "ABCD"
        assert textbox._original_text == "ABCD", (
            f"Text should be 'ABCD', got '{textbox._original_text}'"
        )
        assert textbox.cursor_pos == 2, (
            f"Cursor should be at 2, got {textbox.cursor_pos}"
        )

    def test_delete_at_end_of_line_joins_lines(self, mocker):
        """Test delete at end of line joins with next line."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = "AB\nCD"
        textbox.active = True

        # Position cursor at end of line 1 (position 2, before newline)
        textbox.cursor_pos = 2
        self._simulate_key_press(mocker, textbox, pygame.K_DELETE)

        # Should delete newline, resulting in "ABCD"
        assert textbox._original_text == "ABCD", (
            f"Text should be 'ABCD', got '{textbox._original_text}'"
        )
        assert textbox.cursor_pos == 2, (
            f"Cursor should remain at 2, got {textbox.cursor_pos}"
        )

    def test_delete_at_very_end_of_text(self, mocker):
        """Test delete at absolute end does nothing and doesn't crash."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = "Test"
        textbox.active = True

        # Position cursor at very end
        textbox.cursor_pos = 4
        self._simulate_key_press(mocker, textbox, pygame.K_DELETE)

        # Text should be unchanged
        assert textbox._original_text == "Test", (
            f"Text should be 'Test', got '{textbox._original_text}'"
        )
        assert textbox.cursor_pos == 4, (
            f"Cursor should remain at 4, got {textbox.cursor_pos}"
        )

    # =========================================================================
    # Section 7: Text Insertion at Boundaries Tests
    # =========================================================================

    def test_insert_at_end_of_line(self, mocker):
        """Test inserting character at end of line works correctly."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = "AB\nCD"
        textbox.active = True

        # Position cursor at end of line 1 (position 2)
        textbox.cursor_pos = 2

        # Simulate text input via key event with unicode
        self._simulate_key_press(mocker, textbox, 0, "X")

        # Should result in "ABX\nCD"
        assert textbox._original_text == "ABX\nCD", (
            f"Text should be 'ABX\\nCD', got '{textbox._original_text}'"
        )
        assert textbox.cursor_pos == 3, (
            f"Cursor should be at 3, got {textbox.cursor_pos}"
        )

    def test_insert_at_very_end_of_text(self, mocker):
        """Test inserting at absolute end of text appends correctly."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = "Test"
        textbox.active = True

        # Position cursor at end
        textbox.cursor_pos = 4

        # Simulate text input via key event with unicode
        self._simulate_key_press(mocker, textbox, 0, "!")

        # Should result in "Test!"
        assert textbox._original_text == "Test!", (
            f"Text should be 'Test!', got '{textbox._original_text}'"
        )
        assert textbox.cursor_pos == 5, (
            f"Cursor should be at 5, got {textbox.cursor_pos}"
        )

    def test_insert_newline_in_middle_of_line(self, mocker):
        """Test inserting newline splits line correctly."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = "ABCD"
        textbox.active = True

        # Position cursor in middle
        textbox.cursor_pos = 2
        self._simulate_key_press(mocker, textbox, pygame.K_RETURN)

        # Should result in "AB\nCD"
        assert textbox._original_text == "AB\nCD", (
            f"Text should be 'AB\\nCD', got '{textbox._original_text}'"
        )
        assert textbox.cursor_pos == 3, (
            f"Cursor should be at 3, got {textbox.cursor_pos}"
        )

    # =========================================================================
    # Section 8: Selection at Boundaries Tests
    # =========================================================================

    def test_selection_to_end_of_line(self, mocker):
        """Test shift+right selects to end of line correctly."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = "Hello"
        textbox.active = True

        # Start selection at position 2
        textbox.cursor_pos = 2
        textbox.selection_start = None
        textbox.selection_end = None

        # Simulate Shift+Right to select "llo"
        # Patch where pygame is used, not where it's defined
        mocker.patch("glitchygames.ui.pygame.key.get_mods", return_value=pygame.KMOD_SHIFT)
        for _ in range(3):
            mock_event = mocker.Mock()
            mock_event.key = pygame.K_RIGHT
            mock_event.unicode = ""
            textbox.on_key_down_event(mock_event)

        # Selection should be from 2 to 5
        assert textbox.selection_start == 2, (
            f"Selection start should be 2, got {textbox.selection_start}"
        )
        assert textbox.selection_end == 5, (
            f"Selection end should be 5, got {textbox.selection_end}"
        )
        assert textbox.cursor_pos == 5, (
            f"Cursor should be at 5, got {textbox.cursor_pos}"
        )

    def test_selection_from_end_of_line_backwards(self, mocker):
        """Test selection starting at end going backwards."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_WIDE,
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = "Hello"
        textbox.active = True

        # Start at end
        textbox.cursor_pos = 5
        textbox.selection_start = None
        textbox.selection_end = None

        # Simulate Shift+Left to select backwards
        # Patch where pygame is used, not where it's defined
        mocker.patch("glitchygames.ui.pygame.key.get_mods", return_value=pygame.KMOD_SHIFT)
        for _ in range(3):
            mock_event = mocker.Mock()
            mock_event.key = pygame.K_LEFT
            mock_event.unicode = ""
            textbox.on_key_down_event(mock_event)

        # Selection should span from 5 to 2
        assert textbox.selection_start == 5, (
            f"Selection start should be 5, got {textbox.selection_start}"
        )
        assert textbox.selection_end == 2, (
            f"Selection end should be 2, got {textbox.selection_end}"
        )
        assert textbox.cursor_pos == 2, (
            f"Cursor should be at 2, got {textbox.cursor_pos}"
        )

    def test_selection_across_wrapped_line_boundary(self, mocker):
        """Test selection spanning auto-wrapped line boundary."""
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        font = pygame.font.Font(None, TEST_LINE_HEIGHT)
        mock_get_font.return_value = font

        textbox = MultiLineTextBox(
            x=TEST_TEXTBOX_X,
            y=TEST_TEXTBOX_Y,
            width=TEST_TEXTBOX_WIDTH_NARROW,  # Force wrapping
            height=TEST_TEXTBOX_HEIGHT,
            name="TestTextBox"
        )
        textbox.text = TEST_LONG_TEXT
        textbox.active = True

        # Start selection at position 10
        textbox.cursor_pos = 10
        textbox.selection_start = None
        textbox.selection_end = None

        # Simulate Shift+Right to select across potential wrap boundary
        # Patch where pygame is used, not where it's defined
        mocker.patch("glitchygames.ui.pygame.key.get_mods", return_value=pygame.KMOD_SHIFT)
        for _ in range(20):  # Select 20 characters
            mock_event = mocker.Mock()
            mock_event.key = pygame.K_RIGHT
            mock_event.unicode = ""
            textbox.on_key_down_event(mock_event)

        # Selection should span from 10 to 30
        assert textbox.selection_start == 10, (
            f"Selection start should be 10, got {textbox.selection_start}"
        )
        assert textbox.selection_end == 30, (
            f"Selection end should be 30, got {textbox.selection_end}"
        )
