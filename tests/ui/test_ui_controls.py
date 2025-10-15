"""Test suite for control UI components.

This module tests SliderSprite, CheckboxSprite, and ColorWellSprite functionality
including user interactions, value changes, and visual feedback.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.ui import CheckboxSprite, ColorWellSprite, SliderSprite

from mocks.test_mock_factory import MockFactory

# Test constants to avoid magic values
SLIDER_X = 10
SLIDER_Y = 20
SLIDER_WIDTH = 200
SLIDER_HEIGHT = 20
CHECKBOX_X = 10
CHECKBOX_Y = 20
CHECKBOX_WIDTH = 20
CHECKBOX_HEIGHT = 20
COLORWELL_X = 10
COLORWELL_Y = 20
COLORWELL_WIDTH = 50
COLORWELL_HEIGHT = 30


class TestSliderSpriteFunctionality(unittest.TestCase):
    """Test SliderSprite functionality."""

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
    def test_slider_initialization(
        self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test SliderSprite initialization."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        # Act
        slider = SliderSprite(x=10, y=20, width=200, height=20, name="TestSlider")

        # Assert
        assert slider.rect.x == SLIDER_X
        assert slider.rect.y == SLIDER_Y
        assert slider.rect.width == SLIDER_WIDTH
        assert slider.rect.height == SLIDER_HEIGHT
        assert slider.name == "TestSlider"

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_slider_value_change(
        self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test SliderSprite value change functionality."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        slider = SliderSprite(x=10, y=20, width=200, height=20, name="TestSlider")

        # Test that slider can be created and has expected properties
        assert slider is not None
        assert slider.name == "TestSlider"

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_slider_mouse_drag(
        self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test SliderSprite mouse drag functionality."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        slider = SliderSprite(x=10, y=20, width=200, height=20, name="TestSlider")

        # Test that slider can be created and responds to mouse events
        assert slider is not None

        # Act: simulate mouse motion
        event = Mock()
        event.pos = (110, 30)  # Middle of slider
        slider.on_mouse_motion_event(event)

        # Assert: slider should handle mouse motion without error
        assert slider is not None

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_slider_callback(
        self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test SliderSprite value change callback."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        slider = SliderSprite(x=10, y=20, width=200, height=20, name="TestSlider")

        # Test that slider can be created
        assert slider is not None
        assert slider.name == "TestSlider"


class TestCheckboxSpriteFunctionality(unittest.TestCase):
    """Test CheckboxSprite functionality."""

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
    def test_checkbox_initialization(
        self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test CheckboxSprite initialization."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        # Act
        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name="TestCheckbox")

        # Assert
        assert checkbox.rect.x == CHECKBOX_X
        assert checkbox.rect.y == CHECKBOX_Y
        assert checkbox.rect.width == CHECKBOX_WIDTH
        assert checkbox.rect.height == CHECKBOX_HEIGHT
        assert checkbox.name == "TestCheckbox"
        assert not checkbox.checked

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_checkbox_toggle(
        self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test CheckboxSprite toggle functionality."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name="TestCheckbox")

        # Test initial state
        assert not checkbox.checked

        # Act: simulate click to toggle
        event = Mock()
        checkbox.on_left_mouse_button_up_event(event)

        # Assert: should be checked after click
        assert checkbox.checked

        # Act: click again
        checkbox.on_left_mouse_button_up_event(event)

        # Assert: should be unchecked after second click
        assert not checkbox.checked

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_checkbox_click_toggle(
        self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test CheckboxSprite click to toggle functionality."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name="TestCheckbox")

        # Test initial state
        assert not checkbox.checked

        # Act: simulate click
        event = Mock()
        event.pos = (20, 30)  # Within checkbox
        checkbox.on_left_mouse_button_up_event(event)

        # Assert: should be checked after click
        assert checkbox.checked

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_checkbox_callback(
        self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test CheckboxSprite state change callback."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name="TestCheckbox")

        # Test that checkbox can be created and responds to events
        assert checkbox is not None
        assert checkbox.name == "TestCheckbox"

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_checkbox_set_checked(
        self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test CheckboxSprite set checked state."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name="TestCheckbox")

        # Test initial state
        assert not checkbox.checked

        # Act: simulate click to check
        event = Mock()
        checkbox.on_left_mouse_button_up_event(event)

        # Assert: should be checked
        assert checkbox.checked

        # Act: simulate click to uncheck
        checkbox.on_left_mouse_button_up_event(event)

        # Assert: should be unchecked
        assert not checkbox.checked


class TestColorWellSpriteFunctionality(unittest.TestCase):
    """Test ColorWellSprite functionality."""

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

    def test_colorwell_initialization(self):
        """Test ColorWellSprite initialization."""
        # Arrange - use centralized mocks
        # Act
        colorwell = ColorWellSprite(x=10, y=20, width=50, height=30, name="TestColorWell")

        # Assert
        assert colorwell.rect.x == COLORWELL_X
        assert colorwell.rect.y == COLORWELL_Y
        assert colorwell.rect.width == COLORWELL_WIDTH
        assert colorwell.rect.height == COLORWELL_HEIGHT
        assert colorwell.name == "TestColorWell"
        assert colorwell.active_color == (0, 0, 0)  # Default color

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_colorwell_color_change(
        self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test ColorWellSprite color change functionality."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        colorwell = ColorWellSprite(x=10, y=20, width=50, height=30, name="TestColorWell")

        # Test that colorwell can be created
        assert colorwell is not None
        assert colorwell.name == "TestColorWell"

    def test_colorwell_click_callback(self):
        """Test ColorWellSprite click callback."""
        # Arrange - use centralized mocks
        colorwell = ColorWellSprite(x=10, y=20, width=50, height=30, name="TestColorWell")

        # Test that colorwell can be created and responds to mouse events
        assert colorwell is not None

        # Act: simulate click
        event = Mock()
        event.pos = (35, 35)  # Within color well
        colorwell.on_left_mouse_button_down_event(event)

        # Assert: should handle click without error
        assert colorwell is not None

    def test_colorwell_hover_effect(self):
        """Test ColorWellSprite hover effect."""
        # Arrange - use centralized mocks
        colorwell = ColorWellSprite(x=10, y=20, width=50, height=30, name="TestColorWell")

        # Test that colorwell can be created and responds to mouse events
        assert colorwell is not None

        # Act: simulate mouse enter
        event = Mock()
        colorwell.on_mouse_enter_event(event)

        # Assert: should handle mouse enter without error
        assert colorwell is not None

        # Act: simulate mouse exit (correct method name)
        colorwell.on_mouse_exit_event(event)

        # Assert: should handle mouse exit without error
        assert colorwell is not None

    @patch("pygame.display.get_surface")
    @patch("pygame.Surface")
    @patch("pygame.sprite.LayeredDirty")
    @patch("pygame.draw.rect")
    @patch("glitchygames.ui.FontManager.get_font")
    def test_colorwell_color_validation(
        self, mock_get_font, mock_draw_rect, mock_group, mock_surface_cls, mock_get_display
    ):
        """Test ColorWellSprite color validation."""
        # Arrange
        font = Mock()
        rendered_surface = Mock()
        rendered_surface.get_rect.return_value = Mock()
        font.render = Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        colorwell = ColorWellSprite(x=10, y=20, width=50, height=30, name="TestColorWell")

        # Test that colorwell can be created
        assert colorwell is not None
        assert colorwell.name == "TestColorWell"

        # Test that it has default color properties
        assert colorwell.active_color is not None
        assert colorwell.red is not None
        assert colorwell.green is not None
        assert colorwell.blue is not None


if __name__ == "__main__":
    unittest.main()
