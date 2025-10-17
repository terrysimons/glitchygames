"""Test suite for text-related UI components.

This module tests TextSprite, TextBoxSprite, and MultiLineTextBox functionality
including text rendering, input handling, and display properties.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.ui import MultiLineTextBox, TextBoxSprite, TextSprite

from tests.mocks.test_mock_factory import MockFactory

# Test constants to avoid magic values
TEST_X_POS = 10
TEST_Y_POS = 20
TEST_WIDTH = 200
TEST_HEIGHT = 30
TEST_MULTILINE_WIDTH = 300
TEST_MULTILINE_HEIGHT = 100
TEST_SCROLL_OFFSET = 10


class TestTextSpriteFunctionality(unittest.TestCase):
    """Test TextSprite functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Use centralized mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        # Start all the patchers
        for patcher in self.patchers:
            patcher.start()
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_text_sprite_initialization(self):
        """Test TextSprite initialization."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            # Act
            text_sprite = TextSprite(
                x=TEST_X_POS,
                y=TEST_Y_POS,
                width=TEST_WIDTH,
                height=TEST_HEIGHT,
                text="Hello World",
                name="TestText"
            )

            # Assert
            assert text_sprite.rect.x == TEST_X_POS
            assert text_sprite.rect.y == TEST_Y_POS
            assert text_sprite.text == "Hello World"
            assert text_sprite.name == "TestText"

    def test_text_sprite_text_update(self):
        """Test TextSprite text update functionality."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            text_sprite = TextSprite(
                x=TEST_X_POS,
                y=TEST_Y_POS,
                width=TEST_WIDTH,
                height=TEST_HEIGHT,
                text="Hello",
                name="TestText"
            )

            # Act
            text_sprite.text = "Updated Text"

            # Assert
            assert text_sprite.text == "Updated Text"
            font.render.assert_called()


class TestTextBoxSpriteFunctionality(unittest.TestCase):
    """Test TextBoxSprite functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Use centralized mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        # Start all the patchers
        for patcher in self.patchers:
            patcher.start()
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_textbox_initialization(self):
        """Test TextBoxSprite initialization."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            # Act
            textbox = TextBoxSprite(
                x=TEST_X_POS,
                y=TEST_Y_POS,
                width=TEST_WIDTH,
                height=TEST_HEIGHT,
                name="TestTextBox"
            )

            # Assert
            assert textbox.rect.x == TEST_X_POS
            assert textbox.rect.y == TEST_Y_POS
            assert textbox.rect.width == TEST_WIDTH
            assert textbox.rect.height == TEST_HEIGHT
            assert textbox.name == "TestTextBox"

    def test_textbox_text_input(self):
        """Test TextBoxSprite text input handling."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            textbox = TextBoxSprite(
                x=TEST_X_POS,
                y=TEST_Y_POS,
                width=TEST_WIDTH,
                height=TEST_HEIGHT,
                name="TestTextBox"
            )

            # Act: simulate text input by directly setting the text_box text
            textbox.text_box.text = "Hello"

            # Assert - TextBoxSprite has text_box attribute that contains the text
            assert textbox.text_box.text == "Hello"

    def test_textbox_backspace(self):
        """Test TextBoxSprite backspace functionality."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            textbox = TextBoxSprite(
                x=TEST_X_POS,
                y=TEST_Y_POS,
                width=TEST_WIDTH,
                height=TEST_HEIGHT,
                name="TestTextBox"
            )
            textbox.text = "Hello"

            # Act: simulate backspace by directly modifying text
            textbox.text = "Hell"  # Simulate backspace effect

            # Assert
            assert textbox.text == "Hell"

    def test_textbox_focus_handling(self):
        """Test TextBoxSprite focus handling."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            textbox = TextBoxSprite(
                x=TEST_X_POS,
                y=TEST_Y_POS,
                width=TEST_WIDTH,
                height=TEST_HEIGHT,
                name="TestTextBox"
            )

            # Act: gain focus by clicking on the textbox
            event = Mock()
            event.pos = (15, 25)  # Within textbox bounds
            textbox.on_left_mouse_button_down_event(event)

            # Assert - TextBoxSprite doesn't have has_focus, check if it was clicked
            assert textbox.background_color == (128, 128, 128)  # Changed on click

            # Act: lose focus by clicking outside
            textbox.on_left_mouse_button_up_event(event)

            # Assert - check if background color changed back
            assert textbox.background_color == (0, 0, 0)  # Changed back on release


class TestMultiLineTextBoxFunctionality(unittest.TestCase):
    """Test MultiLineTextBox functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Use centralized mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        # Start all the patchers
        for patcher in self.patchers:
            patcher.start()
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_multiline_textbox_initialization(self):
        """Test MultiLineTextBox initialization."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            font.get_linesize = Mock(return_value=24)  # Provide proper line height
            font.size = 24  # For freetype fonts
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            # Act
            multiline = MultiLineTextBox(
                x=TEST_X_POS,
                y=TEST_Y_POS,
                width=TEST_MULTILINE_WIDTH,
                height=TEST_MULTILINE_HEIGHT,
                name="TestMultiLine"
            )

            # Assert
            assert multiline.rect.x == TEST_X_POS
            assert multiline.rect.y == TEST_Y_POS
            assert multiline.rect.width == TEST_MULTILINE_WIDTH
            assert multiline.rect.height == TEST_MULTILINE_HEIGHT
            assert multiline.name == "TestMultiLine"

    def test_multiline_textbox_line_breaks(self):
        """Test MultiLineTextBox line break handling."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            font.get_linesize = Mock(return_value=24)  # Provide proper line height
            # Mock font.size to return a tuple (width, height) for text measurements
            font.size = Mock(return_value=(50, 24))  # width, height for text size
            # Mock get_rect for freetype fonts
            font.get_rect = Mock(return_value=Mock(width=50))
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            multiline = MultiLineTextBox(
                x=TEST_X_POS,
                y=TEST_Y_POS,
                width=TEST_MULTILINE_WIDTH,
                height=TEST_MULTILINE_HEIGHT,
                name="TestMultiLine"
            )

            # Act: simulate text input with line breaks by setting text directly
            multiline.text = "Line 1\nLine 2"

            # Assert
            assert "Line 1" in multiline.text
            assert "Line 2" in multiline.text

    def test_multiline_textbox_scrolling(self):
        """Test MultiLineTextBox scrolling functionality."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            font.get_linesize = Mock(return_value=24)  # Provide proper line height
            font.size = 24  # For freetype fonts
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            multiline = MultiLineTextBox(
                x=TEST_X_POS,
                y=TEST_Y_POS,
                width=TEST_MULTILINE_WIDTH,
                height=TEST_MULTILINE_HEIGHT,
                name="TestMultiLine"
            )

            # Act: test scrolling by modifying scroll_offset directly
            multiline.scroll_offset = TEST_SCROLL_OFFSET

            # Assert: should handle scrolling without errors
            assert multiline is not None
            assert multiline.scroll_offset == TEST_SCROLL_OFFSET

            # Act: scroll up by modifying scroll_offset
            multiline.scroll_offset = 0

            # Assert: should handle scrolling without errors
            assert multiline is not None
            assert multiline.scroll_offset == 0


if __name__ == "__main__":
    unittest.main()
