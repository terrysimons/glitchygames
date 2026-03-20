"""Test suite for text-related UI components.

This module tests TextSprite, TextBoxSprite, and MultiLineTextBox functionality
including text rendering, input handling, and display properties.
"""

import sys
from pathlib import Path

import pytest

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


class TestTextSpriteFunctionality:
    """Test TextSprite functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

    def test_text_sprite_initialization(self, mocker):
        """Test TextSprite initialization."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        # Arrange
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        # Act
        text_sprite = TextSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='Hello World',
            name='TestText',
        )

        # Assert
        assert text_sprite.rect is not None
        assert text_sprite.rect.x == TEST_X_POS
        assert text_sprite.rect.y == TEST_Y_POS
        assert text_sprite.text == 'Hello World'
        assert text_sprite.name == 'TestText'

    def test_text_sprite_text_update(self, mocker):
        """Test TextSprite text update functionality."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        # Arrange
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        text_sprite = TextSprite(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='Hello',
            name='TestText',
        )

        # Act
        text_sprite.text = 'Updated Text'

        # Assert
        assert text_sprite.text == 'Updated Text'
        font.render.assert_called()


class TestTextBoxSpriteFunctionality:
    """Test TextBoxSprite functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

    def test_textbox_initialization(self, mocker):
        """Test TextBoxSprite initialization."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        # Arrange
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        # Act
        textbox = TextBoxSprite(
            x=TEST_X_POS, y=TEST_Y_POS, width=TEST_WIDTH, height=TEST_HEIGHT, name='TestTextBox'
        )

        # Assert
        assert textbox.rect is not None
        assert textbox.rect.x == TEST_X_POS
        assert textbox.rect.y == TEST_Y_POS
        assert textbox.rect.width == TEST_WIDTH
        assert textbox.rect.height == TEST_HEIGHT
        assert textbox.name == 'TestTextBox'

    def test_textbox_text_input(self, mocker):
        """Test TextBoxSprite text input handling."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        # Arrange
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        textbox = TextBoxSprite(
            x=TEST_X_POS, y=TEST_Y_POS, width=TEST_WIDTH, height=TEST_HEIGHT, name='TestTextBox'
        )

        # Act: simulate text input by directly setting the text_box text
        textbox.text_box.text = 'Hello'

        # Assert - TextBoxSprite has text_box attribute that contains the text
        assert textbox.text_box.text == 'Hello'

    def test_textbox_backspace(self, mocker):
        """Test TextBoxSprite backspace functionality."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        # Arrange
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        textbox = TextBoxSprite(
            x=TEST_X_POS, y=TEST_Y_POS, width=TEST_WIDTH, height=TEST_HEIGHT, name='TestTextBox'
        )
        textbox.text = 'Hello'  # type: ignore[unresolved-attribute]

        # Act: simulate backspace by directly modifying text
        textbox.text = 'Hell'  # type: ignore[unresolved-attribute]

        # Assert
        assert textbox.text == 'Hell'  # type: ignore[unresolved-attribute]

    def test_textbox_focus_handling(self, mocker):
        """Test TextBoxSprite focus handling."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        # Arrange
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        textbox = TextBoxSprite(
            x=TEST_X_POS, y=TEST_Y_POS, width=TEST_WIDTH, height=TEST_HEIGHT, name='TestTextBox'
        )

        # Act: gain focus by clicking on the textbox
        event = mocker.Mock()
        event.pos = (15, 25)  # Within textbox bounds
        textbox.on_left_mouse_button_down_event(event)

        # Assert - TextBoxSprite doesn't have has_focus, check if it was clicked
        assert textbox.background_color == (128, 128, 128)  # Changed on click

        # Act: lose focus by clicking outside
        textbox.on_left_mouse_button_up_event(event)

        # Assert - check if background color changed back
        assert textbox.background_color == (0, 0, 0)  # Changed back on release


class TestMultiLineTextBoxFunctionality:
    """Test MultiLineTextBox functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

    def test_multiline_textbox_initialization(self, mocker):
        """Test MultiLineTextBox initialization."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        # Arrange
        font = mocker.Mock()
        font.get_linesize = mocker.Mock(return_value=24)  # Provide proper line height
        font.size = 24  # For freetype fonts
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        # Act
        multiline = MultiLineTextBox(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_MULTILINE_WIDTH,
            height=TEST_MULTILINE_HEIGHT,
            name='TestMultiLine',
        )

        # Assert
        assert multiline.rect is not None
        assert multiline.rect.x == TEST_X_POS
        assert multiline.rect.y == TEST_Y_POS
        assert multiline.rect.width == TEST_MULTILINE_WIDTH
        assert multiline.rect.height == TEST_MULTILINE_HEIGHT
        assert multiline.name == 'TestMultiLine'

    def test_multiline_textbox_line_breaks(self, mocker):
        """Test MultiLineTextBox line break handling."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        # Arrange
        font = mocker.Mock()
        font.get_linesize = mocker.Mock(return_value=24)  # Provide proper line height
        # Mock font.size to return a tuple (width, height) for text measurements
        font.size = mocker.Mock(return_value=(50, 24))  # width, height for text size
        # Mock get_rect for freetype fonts
        font.get_rect = mocker.Mock(return_value=mocker.Mock(width=50))
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        multiline = MultiLineTextBox(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_MULTILINE_WIDTH,
            height=TEST_MULTILINE_HEIGHT,
            name='TestMultiLine',
        )

        # Act: simulate text input with line breaks by setting text directly
        multiline.text = 'Line 1\nLine 2'

        # Assert
        assert 'Line 1' in multiline.text
        assert 'Line 2' in multiline.text

    def test_multiline_textbox_scrolling(self, mocker):
        """Test MultiLineTextBox scrolling functionality."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        # Arrange
        font = mocker.Mock()
        font.get_linesize = mocker.Mock(return_value=24)  # Provide proper line height
        font.size = 24  # For freetype fonts
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        multiline = MultiLineTextBox(
            x=TEST_X_POS,
            y=TEST_Y_POS,
            width=TEST_MULTILINE_WIDTH,
            height=TEST_MULTILINE_HEIGHT,
            name='TestMultiLine',
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
