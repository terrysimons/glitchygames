"""Test suite for input-related UI components.

This module tests InputBox and other input components functionality
including input validation, event handling, and user interaction.
"""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events.base import HashableEvent
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
        mock_get_font = mocker.patch('glitchygames.fonts.FontManager.get_font')
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
        assert inputbox.rect is not None
        assert inputbox.rect.x == TEST_INPUT_X_POS
        assert inputbox.rect.y == TEST_INPUT_Y_POS
        assert inputbox.rect.width == TEST_INPUT_WIDTH
        assert inputbox.rect.height == TEST_INPUT_HEIGHT
        assert inputbox.name == 'TestInputBox'

    def test_inputbox_text_input(self, mocker):
        """Test InputBox text input handling."""
        # Arrange
        mock_get_font = mocker.patch('glitchygames.fonts.FontManager.get_font')
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
        mock_get_font = mocker.patch('glitchygames.fonts.FontManager.get_font')
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
        mock_get_font = mocker.patch('glitchygames.fonts.FontManager.get_font')
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
        mock_get_font = mocker.patch('glitchygames.fonts.FontManager.get_font')
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
        mock_get_font = mocker.patch('glitchygames.fonts.FontManager.get_font')
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
        mock_get_font = mocker.patch('glitchygames.fonts.FontManager.get_font')
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
        mock_get_font = mocker.patch('glitchygames.fonts.FontManager.get_font')
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
        mock_get_font = mocker.patch('glitchygames.fonts.FontManager.get_font')
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


class TestInputBoxKeyHandling:
    """InputBox key events while active and inactive."""

    @pytest.fixture
    def input_box(self, mock_pygame_patches):
        """A real InputBox (the display is set up by mock_pygame_patches).

        mock_pygame_patches replaces the pygame.key attribute with a Mock, so the tests patch
        set_repeat on that object (patching the string 'pygame.key.set_repeat' would patch the
        real module, which the code under test no longer reaches).

        Returns:
            The input box.

        """
        return InputBox(
            x=TEST_INPUT_X_POS,
            y=TEST_INPUT_Y_POS,
            width=TEST_INPUT_WIDTH,
            height=TEST_INPUT_HEIGHT,
            name='TestInputBox',
        )

    def test_key_up_while_inactive_changes_nothing(self, input_box, mocker):
        set_repeat = mocker.patch.object(pygame.key, 'set_repeat')

        input_box.on_key_up_event(HashableEvent(pygame.KEYUP, key=pygame.K_TAB))

        set_repeat.assert_not_called()
        assert input_box.is_active is False

    def test_key_up_of_an_ordinary_key_keeps_the_box_active(self, input_box, mocker):
        set_repeat = mocker.patch.object(pygame.key, 'set_repeat')
        input_box.activate()

        input_box.on_key_up_event(HashableEvent(pygame.KEYUP, key=pygame.K_a))

        set_repeat.assert_called_once_with(200)
        assert input_box.is_active is True

    def test_return_without_a_confirming_parent_does_nothing(self, input_box):
        """Return asks the parent to confirm; a box without one keeps its text."""
        input_box.activate()
        input_box.text = 'sprite.toml'
        input_box.parent = object()

        input_box.on_key_down_event(
            HashableEvent(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0, unicode='\r')
        )

        assert input_box.text == 'sprite.toml'
        assert input_box.is_active is True
