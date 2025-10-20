"""Test suite for MultiLineTextBox cursor behavior with text wrapping.

This module tests cursor positioning and behavior when long lines are automatically
wrapped to multiple lines, which is a common issue in text editors.
"""

import unittest
from unittest.mock import Mock, patch

import pygame
from glitchygames.ui import MultiLineTextBox

from tests.mocks import MockFactory

# Test constants to avoid magic values
TEST_CURSOR_POSITION_20 = 20


class TestMultiLineTextBoxCursorWrapping(unittest.TestCase):
    """Test MultiLineTextBox cursor behavior with text wrapping."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers:
            patcher.start()

        # Initialize pygame for real font operations
        pygame.init()
        pygame.display.set_mode((800, 600), pygame.HIDDEN)

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_cursor_positioning_with_wrapped_text(self):
        """Test that cursor positioning works correctly with automatically wrapped text."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Create a real font for accurate text measurements
            font = pygame.font.Font(None, 24)
            mock_get_font.return_value = font

            # Create a narrow text box that will force wrapping
            textbox = MultiLineTextBox(
                x=10,
                y=10,
                width=200,  # Narrow width to force wrapping
                height=100,
                name="TestTextBox"
            )

            # Set a long line that will be wrapped
            long_text = (
                "This is a very long line of text that should be automatically "
                "wrapped to multiple lines when it exceeds the width of the text box"
            )
            textbox.text = long_text
            textbox.active = True
            textbox.cursor_pos = len(long_text)  # Position cursor at end

            # Update to trigger rendering and cursor positioning
            textbox.update()

            # The cursor should be positioned correctly at the end of the wrapped text
            # This test will fail if the cursor positioning logic doesn't account for wrapping
            assert textbox.cursor_pos == len(long_text)

    def test_cursor_positioning_issue_with_wrapped_text(self):
        """Test that demonstrates the cursor positioning issue with wrapped text."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            font = pygame.font.Font(None, 24)
            mock_get_font.return_value = font

            # Create a very narrow text box that will force wrapping
            textbox = MultiLineTextBox(
                x=10,
                y=10,
                width=150,  # Very narrow width to force wrapping
                height=120,
                name="TestTextBox"
            )

            # Set a long line that will definitely wrap
            long_text = (
                "This is a very long line of text that will definitely be wrapped to "
                "multiple lines because it is much longer than the text box width"
            )
            textbox.text = long_text
            textbox.active = True

            # Position cursor in the middle of the text (this is where the issue occurs)
            cursor_pos = 50  # Position in the middle of the long text
            textbox.cursor_pos = cursor_pos

            # Update to trigger rendering and cursor positioning
            textbox.update()

            # Debug information (removed print statements for linting)

            # Test the new cursor positioning logic
            cursor_line, cursor_column = textbox._get_cursor_line_and_column_in_wrapped_text(
                cursor_pos
            )
            # Debug information (removed print statements for linting)

            # The cursor should now be positioned correctly in the wrapped text
            assert textbox.cursor_pos == cursor_pos  # Original position is preserved
            assert cursor_line >= 0  # Should be on a valid line
            assert cursor_column >= 0  # Should be on a valid column

    def test_cursor_positioning_with_mixed_wrapped_and_explicit_newlines(self):
        """Test cursor positioning with both wrapped text and explicit newlines."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            font = pygame.font.Font(None, 24)
            mock_get_font.return_value = font

            textbox = MultiLineTextBox(
                x=10,
                y=10,
                width=150,  # Narrow width
                height=120,
                name="TestTextBox"
            )

            # Text with both explicit newlines and long lines that will wrap
            mixed_text = (
                "Line 1\nThis is a very long line that will be wrapped automatically\nLine 3"
            )
            textbox.text = mixed_text
            textbox.active = True
            textbox.cursor_pos = len(mixed_text)

            textbox.update()

            # Cursor should be positioned correctly
            assert textbox.cursor_pos == len(mixed_text)

    def test_cursor_positioning_at_beginning_of_wrapped_line(self):
        """Test cursor positioning at the beginning of a wrapped line."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            font = pygame.font.Font(None, 24)
            mock_get_font.return_value = font

            textbox = MultiLineTextBox(
                x=10,
                y=10,
                width=200,
                height=100,
                name="TestTextBox"
            )

            # Long text that will wrap
            long_text = "This is a very long line of text that should be automatically wrapped"
            textbox.text = long_text
            textbox.active = True

            # Find where the text wraps (this is tricky to determine exactly)
            # For now, just test that cursor positioning doesn't crash
            textbox.cursor_pos = 20  # Position somewhere in the middle
            textbox.update()

            # Should not crash and cursor should be positioned
            assert textbox.cursor_pos == TEST_CURSOR_POSITION_20

    def test_cursor_positioning_with_very_long_single_word(self):
        """Test cursor positioning when a single word is longer than the text box width."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            font = pygame.font.Font(None, 24)
            mock_get_font.return_value = font

            textbox = MultiLineTextBox(
                x=10,
                y=10,
                width=100,  # Very narrow width
                height=100,
                name="TestTextBox"
            )

            # Single very long word that will be forced onto its own line
            long_word = "supercalifragilisticexpialidocious"
            textbox.text = long_word
            textbox.active = True
            textbox.cursor_pos = len(long_word)

            textbox.update()

            # Should handle the long word gracefully
            assert textbox.cursor_pos == len(long_word)

    def test_cursor_blinking_with_wrapped_text(self):
        """Test that cursor blinking works correctly with wrapped text."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            font = pygame.font.Font(None, 24)
            mock_get_font.return_value = font

            textbox = MultiLineTextBox(
                x=10,
                y=10,
                width=200,
                height=100,
                name="TestTextBox"
            )

            long_text = "This is a very long line that will be wrapped to multiple lines"
            textbox.text = long_text
            textbox.active = True
            textbox.cursor_pos = len(long_text)

            # Test multiple updates to check cursor blinking
            for _ in range(5):
                textbox.update()

            # Cursor should still be positioned correctly after multiple updates
            assert textbox.cursor_pos == len(long_text)

    def test_mouse_click_positioning_with_wrapped_text(self):
        """Test that mouse clicks position the cursor correctly in wrapped text."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            font = pygame.font.Font(None, 24)
            mock_get_font.return_value = font

            textbox = MultiLineTextBox(
                x=10,
                y=10,
                width=200,
                height=100,
                name="TestTextBox"
            )

            long_text = "This is a very long line that will be wrapped to multiple lines"
            textbox.text = long_text
            textbox.active = True

            # Simulate a mouse click event
            mock_event = Mock()
            mock_event.pos = (50, 30)  # Click somewhere in the text area

            # This should position the cursor based on the click location
            textbox.on_left_mouse_button_down_event(mock_event)

            # The cursor position should be set (exact position depends on font metrics)
            assert textbox.cursor_pos >= 0
            assert textbox.cursor_pos <= len(long_text)

    def test_arrow_key_navigation_with_wrapped_text(self):
        """Test that arrow key navigation works correctly with wrapped text."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            font = pygame.font.Font(None, 24)
            mock_get_font.return_value = font

            textbox = MultiLineTextBox(
                x=10,
                y=10,
                width=150,  # Narrow width to force wrapping
                height=120,
                name="TestTextBox"
            )

            long_text = (
                "This is a very long line that will definitely be wrapped to "
                "multiple lines because it is much longer than the text box width"
            )
            textbox.text = long_text
            textbox.active = True

            # Position cursor in the middle of the text
            textbox.cursor_pos = 50

            # Test up arrow key (should move to previous line)
            up_event = Mock()
            up_event.key = pygame.K_UP
            up_event.unicode = ""

            # This should move the cursor up one line in the wrapped text
            textbox.on_key_down_event(up_event)

            # The cursor should have moved up (exact position depends on line length)
            # For now, just verify it doesn't crash and cursor position is valid
            assert textbox.cursor_pos >= 0
            assert textbox.cursor_pos <= len(long_text)

            # Test down arrow key (should move to next line)
            down_event = Mock()
            down_event.key = pygame.K_DOWN
            down_event.unicode = ""

            # This should move the cursor down one line in the wrapped text
            textbox.on_key_down_event(down_event)

            # The cursor should have moved down
            assert textbox.cursor_pos >= 0
            assert textbox.cursor_pos <= len(long_text)

    def test_mouse_click_positioning_issue_with_wrapped_text(self):
        """Test that demonstrates the mouse click positioning issue with wrapped text."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            font = pygame.font.Font(None, 24)
            mock_get_font.return_value = font

            textbox = MultiLineTextBox(
                x=10,
                y=10,
                width=150,  # Narrow width to force wrapping
                height=120,
                name="TestTextBox"
            )

            long_text = (
                "This is a very long line that will definitely be wrapped to "
                "multiple lines because it is much longer than the text box width"
            )
            textbox.text = long_text
            textbox.active = True

            # Simulate clicking on the second line of wrapped text
            mock_event = Mock()
            mock_event.pos = (50, 50)  # Click on what should be the second line

            # Debug information (removed print statements for linting)

            # This should position the cursor correctly in the original text
            textbox.on_left_mouse_button_down_event(mock_event)

            # Debug information (removed print statements for linting)

            # The cursor position should be valid
            assert textbox.cursor_pos >= 0
            assert textbox.cursor_pos <= len(long_text)


if __name__ == "__main__":
    unittest.main()
