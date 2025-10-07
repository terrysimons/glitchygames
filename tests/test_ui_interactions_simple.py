"""Focused UI interaction tests for quick coverage wins."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.ui import ButtonSprite, CheckboxSprite, MultiLineTextBox, TextBoxSprite

from test_mock_factory import MockFactory

# Constants for test values
NEW_X_POSITION = 50
NEW_Y_POSITION = 60


class TestButtonSpriteInteractions(unittest.TestCase):
    """Test ButtonSprite mouse interactions."""

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_button_mouse_down_up_changes_background(  # noqa: PLR6301
        self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test that button background changes on mouse down/up events."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        # Font may be freetype (render_to) or font (render)
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        btn = ButtonSprite(x=10, y=20, width=100, height=40, name="ClickMe")
        assert btn.background_color == btn.inactive_color

        # Act: simulate mouse down
        event = Mock()
        btn.on_left_mouse_button_down_event(event)

        # Assert
        assert btn.background_color == btn.active_color
        assert btn.dirty == 1

        # Act: simulate mouse up
        btn.dirty = 0
        btn.on_left_mouse_button_up_event(event)

        # Assert inactive restored and dirty set
        assert btn.background_color == btn.inactive_color
        assert btn.dirty == 1


class TestCheckboxSpriteInteractions(unittest.TestCase):
    """Test CheckboxSprite mouse toggle behavior."""

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("pygame.draw.line")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_checkbox_toggle_on_mouse_up(  # noqa: PLR6301
        self,
        mock_get_font,
        mock_draw_line,
        mock_draw_rect,
        mock_group,
        mock_surface_cls,
        mock_get_display,
    ):
        """Test that checkbox toggles state on mouse up events."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        cb = CheckboxSprite(x=5, y=6, width=20, height=20, name="CB")
        assert not cb.checked

        # Act: mouse up toggles
        event = Mock()
        cb.on_left_mouse_button_up_event(event)
        assert cb.checked

        cb.on_left_mouse_button_up_event(event)
        assert not cb.checked

        # Update should draw border and optionally check mark
        cb.checked = True
        cb.update()
        assert mock_draw_rect.called
        assert mock_draw_line.called


class TestTextBoxSpriteInteractions(unittest.TestCase):
    """Test TextBoxSprite focus and mouse interactions."""

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_textbox_mouse_down_up_changes_background(  # noqa: PLR6301
        self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test that textbox background changes on mouse down/up events."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        tb = TextBoxSprite(x=10, y=10, width=200, height=40, name="TB")
        assert tb.background_color == (0, 0, 0)

        event = Mock()
        tb.on_left_mouse_button_down_event(event)
        assert tb.background_color == (128, 128, 128)
        assert tb.dirty == 1

        tb.dirty = 0
        tb.on_left_mouse_button_up_event(event)
        assert tb.background_color == (0, 0, 0)
        assert tb.dirty == 1


class TestButtonSpriteSettersAndNested(unittest.TestCase):
    """Test ButtonSprite property setters and nested sprite updates."""

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_button_setters_and_update_nested(  # noqa: PLR6301
        self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test button property setters and nested sprite updates."""
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        btn = ButtonSprite(x=10, y=20, width=100, height=40, name="Btn")

        # Change position via setters
        btn.dirty = 0
        btn.x = NEW_X_POSITION
        btn.y = NEW_Y_POSITION
        assert btn.rect.x == NEW_X_POSITION
        assert btn.rect.y == NEW_Y_POSITION
        # Nested text should follow
        assert btn.text.x == NEW_X_POSITION
        assert btn.text.y == NEW_Y_POSITION
        assert btn.dirty == 1

        # Propagate dirty to nested
        btn.dirty = 1
        btn.text.dirty = 0
        btn.update_nested_sprites()
        assert btn.text.dirty == 1


class TestTextBoxSpriteUpdateNestedAndBorder(unittest.TestCase):
    """Test TextBoxSprite nested updates and border rendering."""

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_textbox_update_nested_and_border(  # noqa: PLR6301
        self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test textbox nested updates and border rendering."""
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        tb = TextBoxSprite(x=10, y=10, width=200, height=40, name="TB")

        # Propagate dirty to nested text_box
        tb.dirty = 1
        tb.text_box.dirty = 0
        tb.update_nested_sprites()
        assert tb.text_box.dirty == 1

        # Update should draw border
        tb.update()
        assert mock_draw_rect.called


class TestTextBoxSpriteKeyboardInput(unittest.TestCase):
    """Test TextBoxSprite keyboard input handling."""

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_textbox_activation_and_basic_properties(  # noqa: PLR6301
        self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test textbox activation and basic properties."""
        font = Mock()
        font.get_linesize.return_value = 20  # Mock line height
        font.size = 20  # For freetype fallback
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        tb = MultiLineTextBox(x=10, y=10, width=200, height=40, name="TB")

        # Test initial state
        assert not tb._text
        assert not tb.active
        assert tb.cursor_pos == 0

        # Test activation
        tb.active = True
        assert tb.active

        # Test text property
        tb._text = "test"
        assert tb._text == "test"


if __name__ == "__main__":
    unittest.main()
