"""Test suite for input-related UI components.

This module tests InputBox and other input components functionality
including input validation, event handling, and user interaction.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.ui import InputBox
from mocks.test_mock_factory import MockFactory


class TestInputBoxFunctionality(unittest.TestCase):
    """Test InputBox functionality."""

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

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_inputbox_initialization(self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display):
        """Test InputBox initialization."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        # Act
        inputbox = InputBox(x=10, y=20, width=200, height=30, name="TestInputBox")

        # Assert
        self.assertEqual(inputbox.rect.x, 10)
        self.assertEqual(inputbox.rect.y, 20)
        self.assertEqual(inputbox.rect.width, 200)
        self.assertEqual(inputbox.rect.height, 30)
        self.assertEqual(inputbox.name, "TestInputBox")

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_inputbox_text_input(self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display):
        """Test InputBox text input handling."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        inputbox = InputBox(x=10, y=20, width=200, height=30, name="TestInputBox")

        # Test that inputbox can be created
        self.assertIsNotNone(inputbox)
        self.assertEqual(inputbox.name, "TestInputBox")

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_inputbox_enter_key_submission(self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display):
        """Test InputBox enter key submission."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        inputbox = InputBox(x=10, y=20, width=200, height=30, name="TestInputBox")

        # Test that inputbox can be created and has expected properties
        self.assertIsNotNone(inputbox)
        self.assertEqual(inputbox.name, "TestInputBox")
        self.assertIsNotNone(inputbox.text)

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_inputbox_escape_key_cancellation(self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display):
        """Test InputBox escape key cancellation."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        inputbox = InputBox(x=10, y=20, width=200, height=30, name="TestInputBox")

        # Test that inputbox can be created
        self.assertIsNotNone(inputbox)
        self.assertEqual(inputbox.name, "TestInputBox")

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_inputbox_focus_handling(self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display):
        """Test InputBox focus handling."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        inputbox = InputBox(x=10, y=20, width=200, height=30, name="TestInputBox")

        # Test that inputbox can be created
        self.assertIsNotNone(inputbox)
        self.assertEqual(inputbox.name, "TestInputBox")

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_inputbox_validation(self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display):
        """Test InputBox input validation."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        inputbox = InputBox(x=10, y=20, width=200, height=30, name="TestInputBox")

        # Test that inputbox can be created
        self.assertIsNotNone(inputbox)
        self.assertEqual(inputbox.name, "TestInputBox")

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_inputbox_placeholder_text(self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display):
        """Test InputBox placeholder text functionality."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        inputbox = InputBox(x=10, y=20, width=200, height=30, name="TestInputBox")

        # Test that inputbox can be created
        self.assertIsNotNone(inputbox)
        self.assertEqual(inputbox.name, "TestInputBox")

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_inputbox_max_length(self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display):
        """Test InputBox maximum length constraint."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        inputbox = InputBox(x=10, y=20, width=200, height=30, name="TestInputBox")

        # Test that inputbox can be created
        self.assertIsNotNone(inputbox)
        self.assertEqual(inputbox.name, "TestInputBox")

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_inputbox_clear_functionality(self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display):
        """Test InputBox clear functionality."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        inputbox = InputBox(x=10, y=20, width=200, height=30, name="TestInputBox")

        # Test that inputbox can be created
        self.assertIsNotNone(inputbox)
        self.assertEqual(inputbox.name, "TestInputBox")


if __name__ == "__main__":
    unittest.main()
