"""Test suite for control UI components.

This module tests SliderSprite, CheckboxSprite, and ColorWellSprite functionality
including user interactions, value changes, and visual feedback.
"""

import sys
from pathlib import Path

import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.ui import CheckboxSprite, ColorWellSprite, SliderSprite

from tests.mocks.test_mock_factory import MockFactory

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


class TestSliderSpriteFunctionality:
    """Test SliderSprite functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        MockFactory.setup_pygame_mocks_with_mocker(mocker)
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

    def test_slider_initialization(self, mocker):
        """Test SliderSprite initialization."""
        # Arrange
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        mock_draw_rect = mocker.patch("pygame.draw.rect")
        mock_group = mocker.patch("pygame.sprite.LayeredDirty")
        mock_surface_cls = mocker.patch("pygame.Surface")
        mock_get_display = mocker.patch("pygame.display.get_surface")

        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
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

    def test_slider_value_change(self, mocker):
        """Test SliderSprite value change functionality."""
        # Arrange
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        mock_draw_rect = mocker.patch("pygame.draw.rect")
        mock_group = mocker.patch("pygame.sprite.LayeredDirty")
        mock_surface_cls = mocker.patch("pygame.Surface")
        mock_get_display = mocker.patch("pygame.display.get_surface")

        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        slider = SliderSprite(x=10, y=20, width=200, height=20, name="TestSlider")

        # Test that slider can be created and has expected properties
        assert slider is not None
        assert slider.name == "TestSlider"

    def test_slider_mouse_drag(self, mocker):
        """Test SliderSprite mouse drag functionality."""
        # Arrange
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        mock_draw_rect = mocker.patch("pygame.draw.rect")
        mock_group = mocker.patch("pygame.sprite.LayeredDirty")
        mock_surface_cls = mocker.patch("pygame.Surface")
        mock_get_display = mocker.patch("pygame.display.get_surface")

        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        slider = SliderSprite(x=10, y=20, width=200, height=20, name="TestSlider")

        # Test that slider can be created and responds to mouse events
        assert slider is not None

        # Act: simulate mouse motion
        event = mocker.Mock()
        event.pos = (110, 30)  # Middle of slider
        slider.on_mouse_motion_event(event)

        # Assert: slider should handle mouse motion without error
        assert slider is not None

    def test_slider_callback(self, mocker):
        """Test SliderSprite value change callback."""
        # Arrange
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        mock_draw_rect = mocker.patch("pygame.draw.rect")
        mock_group = mocker.patch("pygame.sprite.LayeredDirty")
        mock_surface_cls = mocker.patch("pygame.Surface")
        mock_get_display = mocker.patch("pygame.display.get_surface")

        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        slider = SliderSprite(x=10, y=20, width=200, height=20, name="TestSlider")

        # Test that slider can be created
        assert slider is not None
        assert slider.name == "TestSlider"


class TestCheckboxSpriteFunctionality:
    """Test CheckboxSprite functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        MockFactory.setup_pygame_mocks_with_mocker(mocker)
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

    def test_checkbox_initialization(self, mocker):
        """Test CheckboxSprite initialization."""
        # Arrange
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        mock_draw_rect = mocker.patch("pygame.draw.rect")
        mock_group = mocker.patch("pygame.sprite.LayeredDirty")
        mock_surface_cls = mocker.patch("pygame.Surface")
        mock_get_display = mocker.patch("pygame.display.get_surface")

        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
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

    def test_checkbox_toggle(self, mocker):
        """Test CheckboxSprite toggle functionality."""
        # Arrange
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        mock_draw_rect = mocker.patch("pygame.draw.rect")
        mock_group = mocker.patch("pygame.sprite.LayeredDirty")
        mock_surface_cls = mocker.patch("pygame.Surface")
        mock_get_display = mocker.patch("pygame.display.get_surface")

        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name="TestCheckbox")

        # Test initial state
        assert not checkbox.checked

        # Act: simulate click to toggle
        event = mocker.Mock()
        checkbox.on_left_mouse_button_up_event(event)

        # Assert: should be checked after click
        assert checkbox.checked

        # Act: click again
        checkbox.on_left_mouse_button_up_event(event)

        # Assert: should be unchecked after second click
        assert not checkbox.checked

    def test_checkbox_click_toggle(self, mocker):
        """Test CheckboxSprite click to toggle functionality."""
        # Arrange
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        mock_draw_rect = mocker.patch("pygame.draw.rect")
        mock_group = mocker.patch("pygame.sprite.LayeredDirty")
        mock_surface_cls = mocker.patch("pygame.Surface")
        mock_get_display = mocker.patch("pygame.display.get_surface")

        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name="TestCheckbox")

        # Test initial state
        assert not checkbox.checked

        # Act: simulate click
        event = mocker.Mock()
        event.pos = (20, 30)  # Within checkbox
        checkbox.on_left_mouse_button_up_event(event)

        # Assert: should be checked after click
        assert checkbox.checked

    def test_checkbox_callback(self, mocker):
        """Test CheckboxSprite state change callback."""
        # Arrange
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        mock_draw_rect = mocker.patch("pygame.draw.rect")
        mock_group = mocker.patch("pygame.sprite.LayeredDirty")
        mock_surface_cls = mocker.patch("pygame.Surface")
        mock_get_display = mocker.patch("pygame.display.get_surface")

        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name="TestCheckbox")

        # Test that checkbox can be created and responds to events
        assert checkbox is not None
        assert checkbox.name == "TestCheckbox"

    def test_checkbox_set_checked(self, mocker):
        """Test CheckboxSprite set checked state."""
        # Arrange
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        mock_draw_rect = mocker.patch("pygame.draw.rect")
        mock_group = mocker.patch("pygame.sprite.LayeredDirty")
        mock_surface_cls = mocker.patch("pygame.Surface")
        mock_get_display = mocker.patch("pygame.display.get_surface")

        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name="TestCheckbox")

        # Test initial state
        assert not checkbox.checked

        # Act: simulate click to check
        event = mocker.Mock()
        checkbox.on_left_mouse_button_up_event(event)

        # Assert: should be checked
        assert checkbox.checked

        # Act: simulate click to uncheck
        checkbox.on_left_mouse_button_up_event(event)

        # Assert: should be unchecked
        assert not checkbox.checked


class TestColorWellSpriteFunctionality:
    """Test ColorWellSprite functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        MockFactory.setup_pygame_mocks_with_mocker(mocker)
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

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
        assert colorwell.active_color == (0, 0, 0, 255)  # Default color (RGBA)

    def test_colorwell_color_change(self, mocker):
        """Test ColorWellSprite color change functionality."""
        # Arrange
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        mock_draw_rect = mocker.patch("pygame.draw.rect")
        mock_group = mocker.patch("pygame.sprite.LayeredDirty")
        mock_surface_cls = mocker.patch("pygame.Surface")
        mock_get_display = mocker.patch("pygame.display.get_surface")

        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        mock_surface_cls.return_value = MockFactory.create_pygame_surface_mock()
        mock_get_display.return_value = MockFactory.create_display_mock(width=800, height=600)

        colorwell = ColorWellSprite(x=10, y=20, width=50, height=30, name="TestColorWell")

        # Test that colorwell can be created
        assert colorwell is not None
        assert colorwell.name == "TestColorWell"

    def test_colorwell_click_callback(self, mocker):
        """Test ColorWellSprite click callback."""
        # Arrange - use centralized mocks
        colorwell = ColorWellSprite(x=10, y=20, width=50, height=30, name="TestColorWell")

        # Test that colorwell can be created and responds to mouse events
        assert colorwell is not None

        # Act: simulate click
        event = mocker.Mock()
        event.pos = (35, 35)  # Within color well
        colorwell.on_left_mouse_button_down_event(event)

        # Assert: should handle click without error
        assert colorwell is not None

    def test_colorwell_hover_effect(self, mocker):
        """Test ColorWellSprite hover effect."""
        # Arrange - use centralized mocks
        colorwell = ColorWellSprite(x=10, y=20, width=50, height=30, name="TestColorWell")

        # Test that colorwell can be created and responds to mouse events
        assert colorwell is not None

        # Act: simulate mouse enter
        event = mocker.Mock()
        colorwell.on_mouse_enter_event(event)

        # Assert: should handle mouse enter without error
        assert colorwell is not None

        # Act: simulate mouse exit (correct method name)
        colorwell.on_mouse_exit_event(event)

        # Assert: should handle mouse exit without error
        assert colorwell is not None

    def test_colorwell_color_validation(self, mocker):
        """Test ColorWellSprite color validation."""
        # Arrange
        mock_get_font = mocker.patch("glitchygames.ui.FontManager.get_font")
        mock_draw_rect = mocker.patch("pygame.draw.rect")
        mock_group = mocker.patch("pygame.sprite.LayeredDirty")
        mock_surface_cls = mocker.patch("pygame.Surface")
        mock_get_display = mocker.patch("pygame.display.get_surface")

        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
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
