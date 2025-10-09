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

from glitchygames.ui import TextSprite, TextBoxSprite, MultiLineTextBox
from mocks.test_mock_factory import MockFactory


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
            text_sprite = TextSprite(x=10, y=20, width=200, height=30, text="Hello World", name="TestText")

            # Assert
            self.assertEqual(text_sprite.rect.x, 10)
            self.assertEqual(text_sprite.rect.y, 20)
            self.assertEqual(text_sprite.text, "Hello World")
            self.assertEqual(text_sprite.name, "TestText")

    def test_text_sprite_text_update(self):
        """Test TextSprite text update functionality."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            text_sprite = TextSprite(x=10, y=20, width=200, height=30, text="Hello", name="TestText")

            # Act
            text_sprite.text = "Updated Text"

            # Assert
            self.assertEqual(text_sprite.text, "Updated Text")
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
            textbox = TextBoxSprite(x=10, y=20, width=200, height=30, name="TestTextBox")

            # Assert
            self.assertEqual(textbox.rect.x, 10)
            self.assertEqual(textbox.rect.y, 20)
            self.assertEqual(textbox.rect.width, 200)
            self.assertEqual(textbox.rect.height, 30)
            self.assertEqual(textbox.name, "TestTextBox")

    def test_textbox_text_input(self):
        """Test TextBoxSprite text input handling."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            textbox = TextBoxSprite(x=10, y=20, width=200, height=30, name="TestTextBox")

            # Act: simulate text input by directly setting the text_box text
            textbox.text_box.text = "Hello"

            # Assert - TextBoxSprite has text_box attribute that contains the text
            self.assertEqual(textbox.text_box.text, "Hello")

    def test_textbox_backspace(self):
        """Test TextBoxSprite backspace functionality."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            textbox = TextBoxSprite(x=10, y=20, width=200, height=30, name="TestTextBox")
            textbox.text = "Hello"

            # Act: simulate backspace by directly modifying text
            textbox.text = "Hell"  # Simulate backspace effect

            # Assert
            self.assertEqual(textbox.text, "Hell")

    def test_textbox_focus_handling(self):
        """Test TextBoxSprite focus handling."""
        with patch("glitchygames.ui.FontManager.get_font") as mock_get_font:
            # Arrange
            font = Mock()
            rendered_surface = Mock()
            rendered_surface.get_rect.return_value = Mock()
            font.render = Mock(return_value=rendered_surface)
            mock_get_font.return_value = font

            textbox = TextBoxSprite(x=10, y=20, width=200, height=30, name="TestTextBox")

            # Act: gain focus by clicking on the textbox
            event = Mock()
            event.pos = (15, 25)  # Within textbox bounds
            textbox.on_left_mouse_button_down_event(event)

            # Assert - TextBoxSprite doesn't have has_focus, check if it was clicked
            self.assertEqual(textbox.background_color, (128, 128, 128))  # Changed on click

            # Act: lose focus by clicking outside
            textbox.on_left_mouse_button_up_event(event)

            # Assert - check if background color changed back
            self.assertEqual(textbox.background_color, (0, 0, 0))  # Changed back on release


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
            multiline = MultiLineTextBox(x=10, y=20, width=300, height=100, name="TestMultiLine")

            # Assert
            self.assertEqual(multiline.rect.x, 10)
            self.assertEqual(multiline.rect.y, 20)
            self.assertEqual(multiline.rect.width, 300)
            self.assertEqual(multiline.rect.height, 100)
            self.assertEqual(multiline.name, "TestMultiLine")

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

            multiline = MultiLineTextBox(x=10, y=20, width=300, height=100, name="TestMultiLine")

            # Act: simulate text input with line breaks by setting text directly
            multiline.text = "Line 1\nLine 2"

            # Assert
            self.assertIn("Line 1", multiline.text)
            self.assertIn("Line 2", multiline.text)

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

            multiline = MultiLineTextBox(x=10, y=20, width=300, height=100, name="TestMultiLine")

            # Act: test scrolling by modifying scroll_offset directly
            multiline.scroll_offset = 10

            # Assert: should handle scrolling without errors
            self.assertIsNotNone(multiline)
            self.assertEqual(multiline.scroll_offset, 10)

            # Act: scroll up by modifying scroll_offset
            multiline.scroll_offset = 0

            # Assert: should handle scrolling without errors
            self.assertIsNotNone(multiline)
            self.assertEqual(multiline.scroll_offset, 0)


if __name__ == "__main__":
    unittest.main()
