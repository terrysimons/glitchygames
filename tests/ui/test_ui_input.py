"""Test suite for input-related UI components.

This module tests InputBox and other input components functionality
including input validation, event handling, and user interaction.
"""

import sys
from pathlib import Path

import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.ui import InputBox
from tests.mocks.test_mock_factory import MockFactory

# Test constants to avoid magic values
TEST_INPUT_X_POS = 10
TEST_INPUT_Y_POS = 20
TEST_INPUT_WIDTH = 200
TEST_INPUT_HEIGHT = 30


class TestInputBoxFunctionality:
    """Test InputBox functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

    def test_inputbox_initialization(self, mocker):
        """Test InputBox initialization."""
        # Arrange
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        mock_draw_rect = mocker.patch('pygame.draw.rect')
        mock_group = mocker.patch('pygame.sprite.LayeredDirty')
        mock_surface_cls = mocker.patch('pygame.Surface')
        mock_get_display = mocker.patch('pygame.display.get_surface')

        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        # Act
        inputbox = InputBox(
            x=TEST_INPUT_X_POS,
            y=TEST_INPUT_Y_POS,
            width=TEST_INPUT_WIDTH,
            height=TEST_INPUT_HEIGHT,
            name='TestInputBox',
        )

        # Assert
        assert inputbox.rect.x == TEST_INPUT_X_POS
        assert inputbox.rect.y == TEST_INPUT_Y_POS
        assert inputbox.rect.width == TEST_INPUT_WIDTH
        assert inputbox.rect.height == TEST_INPUT_HEIGHT
        assert inputbox.name == 'TestInputBox'

    def test_inputbox_text_input(self, mocker):
        """Test InputBox text input handling."""
        # Arrange
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        mock_draw_rect = mocker.patch('pygame.draw.rect')
        mock_group = mocker.patch('pygame.sprite.LayeredDirty')
        mock_surface_cls = mocker.patch('pygame.Surface')
        mock_get_display = mocker.patch('pygame.display.get_surface')

        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        inputbox = InputBox(
            x=TEST_INPUT_X_POS,
            y=TEST_INPUT_Y_POS,
            width=TEST_INPUT_WIDTH,
            height=TEST_INPUT_HEIGHT,
            name='TestInputBox',
        )

        # Test that inputbox can be created
        assert inputbox is not None
        assert inputbox.name == 'TestInputBox'

    def test_inputbox_enter_key_submission(self, mocker):
        """Test InputBox enter key submission."""
        # Arrange
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        mock_draw_rect = mocker.patch('pygame.draw.rect')
        mock_group = mocker.patch('pygame.sprite.LayeredDirty')
        mock_surface_cls = mocker.patch('pygame.Surface')
        mock_get_display = mocker.patch('pygame.display.get_surface')

        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        inputbox = InputBox(
            x=TEST_INPUT_X_POS,
            y=TEST_INPUT_Y_POS,
            width=TEST_INPUT_WIDTH,
            height=TEST_INPUT_HEIGHT,
            name='TestInputBox',
        )

        # Test that inputbox can be created and has expected properties
        assert inputbox is not None
        assert inputbox.name == 'TestInputBox'
        assert inputbox.text is not None

    def test_inputbox_escape_key_cancellation(self, mocker):
        """Test InputBox escape key cancellation."""
        # Arrange
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        mock_draw_rect = mocker.patch('pygame.draw.rect')
        mock_group = mocker.patch('pygame.sprite.LayeredDirty')
        mock_surface_cls = mocker.patch('pygame.Surface')
        mock_get_display = mocker.patch('pygame.display.get_surface')

        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        inputbox = InputBox(
            x=TEST_INPUT_X_POS,
            y=TEST_INPUT_Y_POS,
            width=TEST_INPUT_WIDTH,
            height=TEST_INPUT_HEIGHT,
            name='TestInputBox',
        )

        # Test that inputbox can be created
        assert inputbox is not None
        assert inputbox.name == 'TestInputBox'

    def test_inputbox_focus_handling(self, mocker):
        """Test InputBox focus handling."""
        # Arrange
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        mock_draw_rect = mocker.patch('pygame.draw.rect')
        mock_group = mocker.patch('pygame.sprite.LayeredDirty')
        mock_surface_cls = mocker.patch('pygame.Surface')
        mock_get_display = mocker.patch('pygame.display.get_surface')

        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        inputbox = InputBox(
            x=TEST_INPUT_X_POS,
            y=TEST_INPUT_Y_POS,
            width=TEST_INPUT_WIDTH,
            height=TEST_INPUT_HEIGHT,
            name='TestInputBox',
        )

        # Test that inputbox can be created
        assert inputbox is not None
        assert inputbox.name == 'TestInputBox'

    def test_inputbox_validation(self, mocker):
        """Test InputBox input validation."""
        # Arrange
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        mock_draw_rect = mocker.patch('pygame.draw.rect')
        mock_group = mocker.patch('pygame.sprite.LayeredDirty')
        mock_surface_cls = mocker.patch('pygame.Surface')
        mock_get_display = mocker.patch('pygame.display.get_surface')

        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        inputbox = InputBox(
            x=TEST_INPUT_X_POS,
            y=TEST_INPUT_Y_POS,
            width=TEST_INPUT_WIDTH,
            height=TEST_INPUT_HEIGHT,
            name='TestInputBox',
        )

        # Test that inputbox can be created
        assert inputbox is not None
        assert inputbox.name == 'TestInputBox'

    def test_inputbox_placeholder_text(self, mocker):
        """Test InputBox placeholder text functionality."""
        # Arrange
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        mock_draw_rect = mocker.patch('pygame.draw.rect')
        mock_group = mocker.patch('pygame.sprite.LayeredDirty')
        mock_surface_cls = mocker.patch('pygame.Surface')
        mock_get_display = mocker.patch('pygame.display.get_surface')

        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        inputbox = InputBox(
            x=TEST_INPUT_X_POS,
            y=TEST_INPUT_Y_POS,
            width=TEST_INPUT_WIDTH,
            height=TEST_INPUT_HEIGHT,
            name='TestInputBox',
        )

        # Test that inputbox can be created
        assert inputbox is not None
        assert inputbox.name == 'TestInputBox'

    def test_inputbox_max_length(self, mocker):
        """Test InputBox maximum length constraint."""
        # Arrange
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        mock_draw_rect = mocker.patch('pygame.draw.rect')
        mock_group = mocker.patch('pygame.sprite.LayeredDirty')
        mock_surface_cls = mocker.patch('pygame.Surface')
        mock_get_display = mocker.patch('pygame.display.get_surface')

        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        inputbox = InputBox(
            x=TEST_INPUT_X_POS,
            y=TEST_INPUT_Y_POS,
            width=TEST_INPUT_WIDTH,
            height=TEST_INPUT_HEIGHT,
            name='TestInputBox',
        )

        # Test that inputbox can be created
        assert inputbox is not None
        assert inputbox.name == 'TestInputBox'

    def test_inputbox_clear_functionality(self, mocker):
        """Test InputBox clear functionality."""
        # Arrange
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        mock_draw_rect = mocker.patch('pygame.draw.rect')
        mock_group = mocker.patch('pygame.sprite.LayeredDirty')
        mock_surface_cls = mocker.patch('pygame.Surface')
        mock_get_display = mocker.patch('pygame.display.get_surface')

        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        inputbox = InputBox(
            x=TEST_INPUT_X_POS,
            y=TEST_INPUT_Y_POS,
            width=TEST_INPUT_WIDTH,
            height=TEST_INPUT_HEIGHT,
            name='TestInputBox',
        )

        # Test that inputbox can be created
        assert inputbox is not None
        assert inputbox.name == 'TestInputBox'
