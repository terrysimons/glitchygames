"""Focused tests for glitchygames.ui quick coverage wins.

These tests avoid full pygame initialization by mocking surfaces, fonts,
groups, and draw calls. They validate core behaviors of TextSprite and
ButtonSprite that are independent of display setup.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.sprites import Sprite
from glitchygames.ui import (
    ButtonSprite,
    CheckboxSprite,
    InputBox,
    MenuBar,
    MenuItem,
    SliderSprite,
    TextBoxSprite,
    TextSprite,
)

from test_mock_factory import MockFactory


class TestTextSpriteRendering(unittest.TestCase):
    """Exercise TextSprite update_text paths and property behaviors."""

    # Constants for test values
    TEST_X_POSITION = 11
    TEST_Y_POSITION = 22
    TEST_DIRTY_FLAG = 2

    @staticmethod
    def _mock_surface_class():
        """Create a mock surface class for testing."""
        surf = MockFactory.create_pygame_surface_mock()
        # Ensure convert_alpha exists and returns self for UI code paths
        surf.convert_alpha.return_value = surf
        # Ensure rect has center attributes used during text centering
        rect = surf.get_rect.return_value
        if not hasattr(rect, "centerx"):
            rect.centerx = 0
        if not hasattr(rect, "centery"):
            rect.centery = 0
        return surf

    @staticmethod
    def _mock_font_with_render_to():
        """Create a mock freetype-like font supporting render_to and render."""
        font = Mock()
        font.render_to = Mock(return_value=Mock())
        # Also provide render to cover solid background path
        font.render = Mock(return_value=(Mock(), Mock()))
        return font

    @staticmethod
    def _mock_font_with_render_only():
        """Create a mock pygame.font-like font (no render_to)."""
        # Use spec to ensure hasattr(font, 'render_to') is False
        font = Mock(spec=["render"])
        font.render = Mock(return_value=Mock())
        return font

    @staticmethod
    def _mock_display_surface():
        """Create a mock display surface for testing."""
        return MockFactory.create_display_mock(width=800, height=600)

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_transparent_background_uses_render_to(
        self, mock_get_font, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test that transparent background uses render_to method."""
        # Arrange
        mock_surface_cls.return_value = self._mock_surface_class()
        mock_get_font.return_value = self._mock_font_with_render_to()
        mock_get_display.return_value = self._mock_display_surface()

        # Act: background with alpha=0 triggers transparent path
        ts = TextSprite(
            x=10,
            y=20,
            width=100,
            height=40,
            name="label",
            background_color=(0, 0, 0, 0),
            text_color=(255, 255, 255),
            text="Hello",
        )

        # Assert
        assert ts.text == "Hello"
        mock_get_font.return_value.render_to.assert_called()

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_render_to_fallbacks_to_render_on_type_error(
        self, mock_get_font, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test that render_to fallbacks to render on TypeError."""
        # Arrange
        mock_surface_cls.return_value = self._mock_surface_class()
        font = self._mock_font_with_render_to()
        font.render_to.side_effect = TypeError("bad args")
        mock_get_font.return_value = font
        mock_get_display.return_value = self._mock_display_surface()

        # Act
        ts = TextSprite(
            x=0,
            y=0,
            width=50,
            height=20,
            name="label",
            background_color=(10, 10, 10, 255),
            text_color=(255, 255, 0),
            text="X",
        )

        # Assert: fell back to font.render
        font.render.assert_called()
        assert ts.text == "X"

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_no_render_to_transparent_font_render(
        self, mock_get_font, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test transparent font rendering without render_to."""
        mock_surface_cls.return_value = self._mock_surface_class()
        # Provide a render() that returns a surface with get_rect
        font = self._mock_font_with_render_only()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render.return_value = rendered_surface
        mock_get_font.return_value = font
        mock_get_display.return_value = self._mock_display_surface()

        ts = TextSprite(
            x=5,
            y=6,
            width=30,
            height=12,
            name="t",
            background_color=(0, 0, 0, 0),
            text_color=(1, 2, 3),
            text="A",
        )

        mock_get_font.return_value.render.assert_called()
        assert ts.text == "A"

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_property_setters_update_rect_and_dirty(
        self, mock_get_font, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test that property setters update rect and dirty flag."""
        mock_surface_cls.return_value = self._mock_surface_class()
        mock_get_font.return_value = self._mock_font_with_render_only()
        mock_get_display.return_value = self._mock_display_surface()

        ts = TextSprite(x=1, y=2, width=10, height=10, name="p", background_color=(0, 0, 0, 0))

        # x setter
        ts.x = self.TEST_X_POSITION
        assert ts.x == self.TEST_X_POSITION
        assert ts.rect.x == self.TEST_X_POSITION
        assert ts.dirty == self.TEST_DIRTY_FLAG

        # y setter
        ts.y = self.TEST_Y_POSITION
        assert ts.y == self.TEST_Y_POSITION
        assert ts.rect.y == self.TEST_Y_POSITION
        assert ts.dirty == self.TEST_DIRTY_FLAG

        # text setter triggers update
        ts.text = "B"
        assert ts.text == "B"
        assert ts.dirty == self.TEST_DIRTY_FLAG


class TestButtonSpriteBasic(unittest.TestCase):
    """Exercise ButtonSprite minimal initialization path."""

    @patch("pygame.draw.rect")
    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_button_initialization_creates_text_and_border(  # noqa: PLR6301
        self, mock_get_font, mock_group, mock_surface_cls, mock_get_display, mock_draw_rect
    ):
        """Test that button initialization creates text and border."""
        # Arrange: font with .render (solid background path)
        font = Mock()
        # TextSprite will use font.render (no render_to). Return a surface mock with get_rect
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        # Surface instance with rect
        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        # Act
        btn = ButtonSprite(x=0, y=0, width=120, height=40, name="ClickMe")

        # Assert text child exists and is centered
        assert btn.text is not None
        font.render.assert_called()
        mock_draw_rect.assert_called()  # border drawn


class TestCheckboxSpriteBasic(unittest.TestCase):
    """Test basic CheckboxSprite functionality."""

    # Constants for test values
    CHECKBOX_SIZE = 30

    @staticmethod
    def setUp():
        """Set up test environment."""
        # Ensure Sprite breakpoints are disabled for clean tests
        Sprite.SPRITE_BREAKPOINTS = None

    @patch("pygame.draw.rect")
    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_checkbox_initialization_and_toggle(
        self, mock_get_font, mock_group, mock_surface_cls, mock_get_display, mock_draw_rect
    ):
        """Test checkbox initialization and toggle functionality."""
        # Arrange: font with .render (solid background path)
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        # Surface instance with rect
        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        # Act
        checkbox = CheckboxSprite(
            x=10, y=20, width=self.CHECKBOX_SIZE, height=self.CHECKBOX_SIZE, name="TestCheckbox"
        )

        # Assert initial state
        assert checkbox.name == "TestCheckbox"
        assert checkbox.width == self.CHECKBOX_SIZE
        assert checkbox.height == self.CHECKBOX_SIZE
        assert not checkbox.checked
        assert checkbox.color == (128, 128, 128)

        # Test toggle functionality
        checkbox.checked = True
        assert checkbox.checked

    @patch("pygame.draw.rect")
    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_checkbox_update_method(  # noqa: PLR6301
        self, mock_get_font, mock_group, mock_surface_cls, mock_get_display, mock_draw_rect
    ):
        """Test checkbox update method."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        checkbox = CheckboxSprite(x=10, y=20, width=30, height=30, name="TestCheckbox")

        # Test update method (should not raise exception)
        checkbox.update()


class TestTextBoxSpriteBasic(unittest.TestCase):
    """Test basic TextBoxSprite functionality."""

    # Constants for test values
    TEXTBOX_WIDTH = 199
    TEXTBOX_HEIGHT = 39

    @staticmethod
    def setUp():
        """Set up test environment."""
        # Ensure Sprite breakpoints are disabled for clean tests
        Sprite.SPRITE_BREAKPOINTS = None

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_textbox_initialization(
        self, mock_get_font, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test textbox initialization."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        # Act
        textbox = TextBoxSprite(x=10, y=20, width=200, height=40, name="TestTextBox")

        # Assert
        assert textbox.name == "TestTextBox"
        # TextBoxSprite adjusts dimensions for border, so expect width-1 and height-1
        assert textbox.width == self.TEXTBOX_WIDTH
        assert textbox.height == self.TEXTBOX_HEIGHT
        assert textbox.background_color == (0, 0, 0)
        assert textbox.border_width == 1
        assert textbox.value is None

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_textbox_value_property(  # noqa: PLR6301
        self, mock_get_font, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test textbox value property functionality."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        textbox = TextBoxSprite(x=10, y=20, width=200, height=40, name="TestTextBox")

        # Test value setter/getter
        textbox.value = "Test Input"
        assert textbox.value == "Test Input"


class TestMenuBarBasic(unittest.TestCase):
    """Test basic MenuBar functionality."""

    @staticmethod
    def setUp():
        """Set up test environment."""
        Sprite.SPRITE_BREAKPOINTS = None

    @patch("pygame.draw.rect")
    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_menubar_initialization(  # noqa: PLR6301
        self, mock_get_font, mock_group, mock_surface_cls, mock_get_display, mock_draw_rect
    ):
        """Test menubar initialization."""
        # Arrange
        # Create a simple font mock
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font
        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        # Act
        menubar = MenuBar(x=0, y=0, width=800, height=30, name="TestMenuBar")

        # Assert
        assert menubar.name == "TestMenuBar"
        expected_width = 800
        expected_height = 30
        assert menubar.width == expected_width
        assert menubar.height == expected_height

    @patch("pygame.draw.rect")
    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_menubar_add_menu_item(  # noqa: PLR6301
        self, mock_get_font, mock_group, mock_surface_cls, mock_get_display, mock_draw_rect
    ):
        """Test adding menu items to menubar."""
        # Arrange
        # Create a simple font mock
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font
        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        menubar = MenuBar(x=0, y=0, width=800, height=30, name="TestMenuBar")

        # Act - create actual MenuItem objects
        file_menu = MenuItem(x=0, y=0, width=50, height=30, name="File")
        edit_menu = MenuItem(x=0, y=0, width=50, height=30, name="Edit")
        menubar.add_menu_item(file_menu)
        menubar.add_menu_item(edit_menu)

        # Assert
        expected_menu_items = 2
        assert len(menubar.menu_items) == expected_menu_items
        assert "File" in menubar.menu_items
        assert "Edit" in menubar.menu_items


class TestMenuItemBasic(unittest.TestCase):
    """Test basic MenuItem functionality."""

    @staticmethod
    def setUp():
        """Set up test environment."""
        Sprite.SPRITE_BREAKPOINTS = None

    @patch("pygame.draw.rect")
    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_menuitem_initialization(  # noqa: PLR6301
        self, mock_get_font, mock_group, mock_surface_cls, mock_get_display, mock_draw_rect
    ):
        """Test menuitem initialization."""
        # Arrange
        # Create a simple font mock
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font
        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        # Act
        menuitem = MenuItem(x=10, y=10, width=100, height=30, name="TestMenuItem")

        # Assert
        assert menuitem.name == "TestMenuItem"
        expected_width = 100
        expected_height = 30
        assert menuitem.width == expected_width
        assert menuitem.height == expected_height

    @patch("pygame.draw.rect")
    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_menuitem_mouse_events(  # noqa: PLR6301
        self, mock_get_font, mock_group, mock_surface_cls, mock_get_display, mock_draw_rect
    ):
        """Test menuitem mouse event handling."""
        # Arrange
        # Create a simple font mock
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font
        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        menuitem = MenuItem(x=10, y=10, width=100, height=30, name="TestMenuItem")

        # Create mock event
        mock_event = Mock()
        mock_event.type = 1025  # MOUSEBUTTONDOWN
        mock_event.button = 1
        mock_event.pos = (50, 20)  # Within the menuitem bounds

        # Act & Assert - should not raise exception
        menuitem.on_left_mouse_button_down_event(mock_event)
        menuitem.on_left_mouse_button_up_event(mock_event)


class TestSliderSpriteBasic(unittest.TestCase):
    """Test basic SliderSprite functionality."""

    @staticmethod
    def setUp():
        """Set up test environment."""
        Sprite.SPRITE_BREAKPOINTS = None

    @patch("pygame.draw.line")
    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_slider_initialization(  # noqa: PLR6301
        self, mock_get_font, mock_group, mock_surface_cls, mock_get_display, mock_draw_line
    ):
        """Test slider initialization."""
        # Arrange
        # Create a simple font mock
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font
        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        # Act
        slider = SliderSprite(x=10, y=10, width=200, height=20, name="TestSlider")

        # Assert
        assert slider.name == "TestSlider"
        # SliderSprite width gets modified by update_slider_appearance, so just check it exists
        assert slider.width > 0
        expected_height = 20
        assert slider.height == expected_height

    @patch("pygame.draw.line")
    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_slider_update_method(  # noqa: PLR6301
        self, mock_get_font, mock_group, mock_surface_cls, mock_get_display, mock_draw_line
    ):
        """Test slider update method."""
        # Arrange
        # Create a simple font mock
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font
        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        slider = SliderSprite(x=10, y=10, width=200, height=20, name="TestSlider")

        # Act & Assert - should not raise exception
        slider.update()


class TestInputBoxBasic(unittest.TestCase):
    """Test basic InputBox functionality."""

    @staticmethod
    def setUp():
        """Set up test environment."""
        Sprite.SPRITE_BREAKPOINTS = None

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_inputbox_initialization(  # noqa: PLR6301
        self, mock_get_font, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test inputbox initialization."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        # Act
        inputbox = InputBox(x=10, y=10, width=200, height=30, name="TestInputBox")

        # Assert
        assert inputbox.name == "TestInputBox"
        expected_width = 200
        expected_height = 30
        assert inputbox.width == expected_width
        assert inputbox.height == expected_height

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_inputbox_key_events(  # noqa: PLR6301
        self, mock_get_font, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test inputbox key event handling."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        inputbox = InputBox(x=10, y=10, width=200, height=30, name="TestInputBox")

        # Create mock key event
        mock_event = Mock()
        mock_event.type = 768  # KEYDOWN
        mock_event.key = 97  # 'a' key
        mock_event.unicode = "a"

        # Act & Assert - should not raise exception
        inputbox.on_key_down_event(mock_event)

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_inputbox_mouse_events(  # noqa: PLR6301
        self, mock_get_font, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test inputbox mouse event handling."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        inputbox = InputBox(x=10, y=10, width=200, height=30, name="TestInputBox")

        # Create mock mouse event
        mock_event = Mock()
        mock_event.type = 1025  # MOUSEBUTTONDOWN
        mock_event.button = 1
        mock_event.pos = (50, 20)  # Within the inputbox bounds

        # Act & Assert - should not raise exception
        inputbox.on_left_mouse_button_down_event(mock_event)


class TestUIEventHandlers(unittest.TestCase):
    """Test UI event handler methods."""

    @staticmethod
    def setUp():
        """Set up test environment."""
        Sprite.SPRITE_BREAKPOINTS = None

    @patch("pygame.draw.rect")
    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_button_mouse_events(  # noqa: PLR6301
        self, mock_get_font, mock_group, mock_surface_cls, mock_get_display, mock_draw_rect
    ):
        """Test button mouse event handling."""
        # Arrange
        # Create a simple font mock
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font
        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        button = ButtonSprite(x=10, y=10, width=100, height=30, name="TestButton")

        # Create mock events
        mouse_down_event = Mock()
        mouse_down_event.type = 1025  # MOUSEBUTTONDOWN
        mouse_down_event.button = 1
        mouse_down_event.pos = (50, 20)

        mouse_up_event = Mock()
        mouse_up_event.type = 1026  # MOUSEBUTTONUP
        mouse_up_event.button = 1
        mouse_up_event.pos = (50, 20)

        # Act & Assert - should not raise exception
        button.on_left_mouse_button_down_event(mouse_down_event)
        button.on_left_mouse_button_up_event(mouse_up_event)

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_textbox_mouse_events(  # noqa: PLR6301
        self, mock_get_font, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test textbox mouse event handling."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        textbox = TextBoxSprite(x=10, y=10, width=200, height=30, name="TestTextBox")

        # Create mock events
        mouse_down_event = Mock()
        mouse_down_event.type = 1025  # MOUSEBUTTONDOWN
        mouse_down_event.button = 1
        mouse_down_event.pos = (50, 20)

        mouse_up_event = Mock()
        mouse_up_event.type = 1026  # MOUSEBUTTONUP
        mouse_up_event.button = 1
        mouse_up_event.pos = (50, 20)

        # Act & Assert - should not raise exception
        textbox.on_left_mouse_button_down_event(mouse_down_event)
        textbox.on_left_mouse_button_up_event(mouse_up_event)

    @patch("pygame.draw.rect")
    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_checkbox_mouse_events(  # noqa: PLR6301
        self, mock_get_font, mock_group, mock_surface_cls, mock_get_display, mock_draw_rect
    ):
        """Test checkbox mouse event handling."""
        # Arrange
        # Create a simple font mock
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font
        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        checkbox = CheckboxSprite(x=10, y=10, width=30, height=30, name="TestCheckbox")

        # Create mock events
        mouse_down_event = Mock()
        mouse_down_event.type = 1025  # MOUSEBUTTONDOWN
        mouse_down_event.button = 1
        mouse_down_event.pos = (25, 25)

        mouse_up_event = Mock()
        mouse_up_event.type = 1026  # MOUSEBUTTONUP
        mouse_up_event.button = 1
        mouse_up_event.pos = (25, 25)

        # Act & Assert - should not raise exception
        checkbox.on_left_mouse_button_down_event(mouse_down_event)
        checkbox.on_left_mouse_button_up_event(mouse_up_event)

        # Verify checkbox state changed
        assert checkbox.checked


if __name__ == "__main__":
    unittest.main()
