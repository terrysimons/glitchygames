"""Coverage tests for glitchygames/ui/widgets.py.

This module targets uncovered areas of the widgets module including:
- MenuBar event handlers (drag, drop, wheel, motion)
- MenuItem initialization, add, update, event handlers
- TextSprite property accessors and cursor blinking
- ButtonSprite nested sprite updates and position setters
- CheckboxSprite toggling and rendering
- InputBox activation/deactivation and key handling
- TextBoxSprite update and nested sprites
- ColorWellSprite hex_color property and RGBA handling
- InputDialog initialization and nested components
- MultiLineTextBox scroll handling
"""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.ui import (
    ButtonSprite,
    CheckboxSprite,
    ColorWellSprite,
    InputDialog,
    MenuBar,
    MenuItem,
    SliderSprite,
    TextBoxSprite,
    TextSprite,
)
from glitchygames.ui.widgets import InputBox
from tests.mocks import MockFactory

# Test constants
TEST_X = 10
TEST_Y = 20
TEST_WIDTH = 200
TEST_HEIGHT = 30
TEST_MENUBAR_WIDTH = 800
TEST_MENUBAR_HEIGHT = 50


class TestMenuBarEventHandlers:
    """Test MenuBar event handlers that are not covered."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_menubar_left_mouse_drag_event(self, mocker):
        """Test MenuBar on_left_mouse_drag_event handler."""
        groups = mocker.Mock()
        menubar = MenuBar(
            x=0,
            y=0,
            width=TEST_MENUBAR_WIDTH,
            height=TEST_MENUBAR_HEIGHT,
            name='test_menubar',
            groups=groups,
        )
        event = mocker.Mock()
        trigger = mocker.Mock()
        # Should not raise - just logs
        menubar.on_left_mouse_drag_event(event, trigger)

    def test_menubar_left_mouse_drop_event(self, mocker):
        """Test MenuBar on_left_mouse_drop_event handler."""
        groups = mocker.Mock()
        menubar = MenuBar(
            x=0,
            y=0,
            width=TEST_MENUBAR_WIDTH,
            height=TEST_MENUBAR_HEIGHT,
            name='test_menubar',
            groups=groups,
        )
        event = mocker.Mock()
        menubar.on_left_mouse_drop_event(event)

    def test_menubar_middle_mouse_drag_event(self, mocker):
        """Test MenuBar on_middle_mouse_drag_event handler."""
        groups = mocker.Mock()
        menubar = MenuBar(
            x=0,
            y=0,
            width=TEST_MENUBAR_WIDTH,
            height=TEST_MENUBAR_HEIGHT,
            name='test_menubar',
            groups=groups,
        )
        event = mocker.Mock()
        menubar.on_middle_mouse_drag_event(event)

    def test_menubar_middle_mouse_drop_event(self, mocker):
        """Test MenuBar on_middle_mouse_drop_event handler."""
        groups = mocker.Mock()
        menubar = MenuBar(
            x=0,
            y=0,
            width=TEST_MENUBAR_WIDTH,
            height=TEST_MENUBAR_HEIGHT,
            name='test_menubar',
            groups=groups,
        )
        event = mocker.Mock()
        menubar.on_middle_mouse_drop_event(event)

    def test_menubar_mouse_drag_event(self, mocker):
        """Test MenuBar on_mouse_drag_event handler."""
        groups = mocker.Mock()
        menubar = MenuBar(
            x=0,
            y=0,
            width=TEST_MENUBAR_WIDTH,
            height=TEST_MENUBAR_HEIGHT,
            name='test_menubar',
            groups=groups,
        )
        event = mocker.Mock()
        trigger = mocker.Mock()
        menubar.on_mouse_drag_event(event, trigger)

    def test_menubar_mouse_drop_event(self, mocker):
        """Test MenuBar on_mouse_drop_event handler."""
        groups = mocker.Mock()
        menubar = MenuBar(
            x=0,
            y=0,
            width=TEST_MENUBAR_WIDTH,
            height=TEST_MENUBAR_HEIGHT,
            name='test_menubar',
            groups=groups,
        )
        event = mocker.Mock()
        trigger = mocker.Mock()
        menubar.on_mouse_drop_event(event, trigger)

    def test_menubar_mouse_motion_event(self, mocker):
        """Test MenuBar on_mouse_motion_event handler."""
        groups = mocker.Mock()
        menubar = MenuBar(
            x=0,
            y=0,
            width=TEST_MENUBAR_WIDTH,
            height=TEST_MENUBAR_HEIGHT,
            name='test_menubar',
            groups=groups,
        )
        event = mocker.Mock()
        menubar.on_mouse_motion_event(event)

    def test_menubar_right_mouse_drag_event(self, mocker):
        """Test MenuBar on_right_mouse_drag_event handler."""
        groups = mocker.Mock()
        menubar = MenuBar(
            x=0,
            y=0,
            width=TEST_MENUBAR_WIDTH,
            height=TEST_MENUBAR_HEIGHT,
            name='test_menubar',
            groups=groups,
        )
        event = mocker.Mock()
        menubar.on_right_mouse_drag_event(event)

    def test_menubar_right_mouse_drop_event(self, mocker):
        """Test MenuBar on_right_mouse_drop_event handler."""
        groups = mocker.Mock()
        menubar = MenuBar(
            x=0,
            y=0,
            width=TEST_MENUBAR_WIDTH,
            height=TEST_MENUBAR_HEIGHT,
            name='test_menubar',
            groups=groups,
        )
        event = mocker.Mock()
        menubar.on_right_mouse_drop_event(event)

    def test_menubar_mouse_wheel_event(self, mocker):
        """Test MenuBar on_mouse_wheel_event handler."""
        groups = mocker.Mock()
        menubar = MenuBar(
            x=0,
            y=0,
            width=TEST_MENUBAR_WIDTH,
            height=TEST_MENUBAR_HEIGHT,
            name='test_menubar',
            groups=groups,
        )
        event = mocker.Mock()
        menubar.on_mouse_wheel_event(event)

    def test_menubar_update_with_menu_items(self, mocker):
        """Test MenuBar update with menu items blits them."""
        groups = mocker.Mock()
        menubar = MenuBar(
            x=0,
            y=0,
            width=TEST_MENUBAR_WIDTH,
            height=TEST_MENUBAR_HEIGHT,
            name='test_menubar',
            groups=groups,
        )
        # Add a mock menu item
        mock_item = mocker.Mock(spec=MenuItem)
        mock_item.name = 'File'
        mock_item.rect = mocker.Mock()
        mock_item.rect.x = 0
        mock_item.rect.y = 0
        mock_item.image = mocker.Mock()
        menubar.menu_items['File'] = mock_item

        # Update should blit menu items
        menubar.update()

    def test_menubar_update_with_focus(self, mocker):
        """Test MenuBar update draws focus border when focused."""
        groups = mocker.Mock()
        menubar = MenuBar(
            x=0,
            y=0,
            width=TEST_MENUBAR_WIDTH,
            height=TEST_MENUBAR_HEIGHT,
            name='test_menubar',
            groups=groups,
        )
        menubar.has_focus = True
        menubar.update()

    def test_menubar_add_menu_item_with_menu(self, mocker):
        """Test MenuBar add_menu_item with explicit menu parameter."""
        groups = mocker.Mock()
        menubar = MenuBar(
            x=0,
            y=0,
            width=TEST_MENUBAR_WIDTH,
            height=TEST_MENUBAR_HEIGHT,
            name='test_menubar',
            groups=groups,
        )
        mock_menu_item = mocker.Mock(spec=MenuItem)
        mock_menu_item.name = 'Item'
        mock_menu = mocker.Mock()
        # Call with menu parameter (takes the else branch)
        menubar.add_menu_item(mock_menu_item, menu=mock_menu)


class TestMenuItemEventHandlers:
    """Test MenuItem event handlers for coverage."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_menuitem_drag_events(self, mocker):
        """Test MenuItem drag/drop event handlers."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        item = MenuItem(x=0, y=0, width=100, height=20, name='TestItem')
        event = mocker.Mock()
        trigger = mocker.Mock()

        item.on_left_mouse_drag_event(event, trigger)
        item.on_left_mouse_drop_event(event, trigger)
        item.on_middle_mouse_drag_event(event, trigger)
        item.on_middle_mouse_drop_event(event, trigger)
        item.on_mouse_drag_event(event, trigger)
        item.on_mouse_drop_event(event, trigger)
        item.on_right_mouse_drag_event(event)
        item.on_right_mouse_drop_event(event)
        item.on_mouse_wheel_event(event)

    def test_menuitem_without_name(self, mocker):
        """Test MenuItem without a name does not create text sprite."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        item = MenuItem(x=0, y=0, width=100, height=20, name=None)
        assert item.name is None

    def test_menuitem_update_active(self, mocker):
        """Test MenuItem update when active with menu_image."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        item = MenuItem(x=0, y=0, width=100, height=20, name='TestItem')
        item.active = True
        item.menu_image = pygame.Surface((100, 100))
        item.menu_rect = item.menu_image.get_rect()
        item.update()

    def test_menuitem_update_inactive(self, mocker):
        """Test MenuItem update when not active."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        item = MenuItem(x=0, y=0, width=100, height=20, name='TestItem')
        item.active = False
        item.update()

    def test_menuitem_add_method(self, mocker):
        """Test MenuItem add method with text attribute."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        item = MenuItem(x=0, y=0, width=100, height=20, name='TestItem')
        mock_group = mocker.Mock()
        # Should call text.add if text exists
        item.add(mock_group)

    def test_menuitem_add_method_without_text(self, mocker):
        """Test MenuItem add method without text attribute."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        item = MenuItem(x=0, y=0, width=100, height=20, name=None)
        mock_group = mocker.Mock()
        # Should handle missing text attribute gracefully
        item.add(mock_group)

    def test_menuitem_add_menu_item_method_with_menu(self, mocker):
        """Test MenuItem add_menu_item with explicit menu parameter takes else branch."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        item = MenuItem(x=0, y=0, width=100, height=20, name='TestItem')
        sub_item = mocker.Mock(spec=MenuItem)
        sub_item.name = 'SubItem'
        mock_menu = mocker.Mock()

        # Call with menu parameter to take the else branch (just logs)
        item.add_menu_item(sub_item, menu=mock_menu)

    def test_menuitem_mouse_exit_sets_dirty(self, mocker):
        """Test MenuItem on_mouse_exit_event sets dirty flag."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        item = MenuItem(x=0, y=0, width=100, height=20, name='TestItem')
        event = mocker.Mock()
        event.pos = (50, 10)
        item.on_mouse_exit_event(event)
        assert item.has_focus is False
        assert item.dirty == 1

    def test_menuitem_left_button_up_resets_state(self, mocker):
        """Test MenuItem on_left_mouse_button_up_event resets active state."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        item = MenuItem(x=0, y=0, width=100, height=20, name='TestItem')
        event = mocker.Mock()
        event.pos = (50, 10)
        item.on_left_mouse_button_up_event(event)
        assert item.active == 0
        assert item.dirty == 2

    def test_menuitem_left_button_down_activates(self, mocker):
        """Test MenuItem on_left_mouse_button_down_event activates menu."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        item = MenuItem(x=0, y=0, width=100, height=20, name='TestItem')
        event = mocker.Mock()
        event.pos = (50, 10)
        item.on_left_mouse_button_down_event(event)
        assert item.active == 1
        assert item.dirty == 2


class TestTextSpritePropertyAccessors:
    """Test TextSprite property accessors and cursor blinking."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_text_sprite_x_setter(self, mocker):
        """Test TextSprite x property setter updates rect and dirty flag."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        text_sprite = TextSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='Hello',
        )
        text_sprite.x = 50
        assert text_sprite.x == 50
        assert text_sprite.rect.x == 50
        assert text_sprite.dirty == 2

    def test_text_sprite_y_setter(self, mocker):
        """Test TextSprite y property setter updates rect and dirty flag."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        text_sprite = TextSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='Hello',
        )
        text_sprite.y = 100
        assert text_sprite.y == 100
        assert text_sprite.rect.y == 100
        assert text_sprite.dirty == 2

    def test_text_sprite_text_setter_same_value_no_update(self, mocker):
        """Test TextSprite text setter does not update when value is the same."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        text_sprite = TextSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='Hello',
        )
        # Reset call count after initialization
        initial_call_count = font.render.call_count
        text_sprite.text = 'Hello'  # Same value
        # Should not call render again since text hasn't changed
        assert font.render.call_count == initial_call_count

    def test_text_sprite_update_active_cursor_blink(self, mocker):
        """Test TextSprite update with active state toggles cursor."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        text_sprite = TextSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='Hello',
        )
        text_sprite.active = True
        text_sprite._cursor_timer = 29  # Just before blink threshold

        text_sprite.update()
        # After update, timer should have rolled over and cursor toggled
        assert text_sprite._cursor_timer == 0
        assert text_sprite._cursor_visible is False

    def test_text_sprite_update_inactive(self, mocker):
        """Test TextSprite update when not active sets dirty to 1."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        text_sprite = TextSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='Hello',
        )
        text_sprite.active = False
        text_sprite.update()
        assert text_sprite.dirty == 1

    def test_text_sprite_transparent_background(self, mocker):
        """Test TextSprite with transparent background (alpha=0)."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        text_sprite = TextSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='Hello',
            background_color=(0, 0, 0, 0),
        )
        assert text_sprite is not None

    def test_text_sprite_on_mouse_motion_event(self, mocker):
        """Test TextSprite on_mouse_motion_event does nothing (hover disabled)."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        text_sprite = TextSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='Hello',
        )
        event = mocker.Mock()
        # Should not raise
        text_sprite.on_mouse_motion_event(event)

    def test_text_sprite_text_box_self_reference(self, mocker):
        """Test TextSprite text_box is self-referential for compatibility."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        text_sprite = TextSprite(
            x=TEST_X,
            y=TEST_Y,
            width=TEST_WIDTH,
            height=TEST_HEIGHT,
            text='Hello',
        )
        assert text_sprite.text_box is text_sprite


class TestButtonSpriteExtended:
    """Extended coverage tests for ButtonSprite."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_button_x_property_setter(self, mocker):
        """Test ButtonSprite x property setter."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = MockFactory.create_pygame_font_mock()
        mock_get_font.return_value = font

        button = ButtonSprite(x=10, y=20, width=100, height=40, name='TestBtn')
        button.x = 50
        assert button.x == 50
        assert button.rect.x == 50
        assert button.dirty == 1

    def test_button_y_property_setter(self, mocker):
        """Test ButtonSprite y property setter."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = MockFactory.create_pygame_font_mock()
        mock_get_font.return_value = font

        button = ButtonSprite(x=10, y=20, width=100, height=40, name='TestBtn')
        button.y = 80
        assert button.y == 80
        assert button.rect.y == 80
        assert button.dirty == 1

    def test_button_update_nested_sprites(self, mocker):
        """Test ButtonSprite update_nested_sprites propagates dirty flag."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = MockFactory.create_pygame_font_mock()
        mock_get_font.return_value = font

        button = ButtonSprite(x=10, y=20, width=100, height=40, name='TestBtn')
        button.dirty = 2
        button.update_nested_sprites()
        assert button.text.dirty == 2

    def test_button_callbacks_initialized_to_none(self, mocker):
        """Test ButtonSprite callbacks attribute is initialized to None."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = MockFactory.create_pygame_font_mock()
        mock_get_font.return_value = font

        button = ButtonSprite(x=10, y=20, width=100, height=40, name='TestBtn')
        assert button.callbacks is None


class TestCheckboxSpriteCoverage:
    """Coverage tests for CheckboxSprite."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_checkbox_initialization(self, mocker):
        """Test CheckboxSprite initialization."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = MockFactory.create_pygame_font_mock()
        mock_get_font.return_value = font

        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name='TestCheck')
        assert checkbox.checked is False
        assert checkbox.color == (128, 128, 128)

    def test_checkbox_toggle_on_click(self, mocker):
        """Test CheckboxSprite toggles checked state on left mouse button up."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = MockFactory.create_pygame_font_mock()
        mock_get_font.return_value = font

        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name='TestCheck')
        event = mocker.Mock()

        assert checkbox.checked is False
        checkbox.on_left_mouse_button_up_event(event)
        assert checkbox.checked is True
        assert checkbox.dirty == 1

        checkbox.on_left_mouse_button_up_event(event)
        assert checkbox.checked is False

    def test_checkbox_update_unchecked(self, mocker):
        """Test CheckboxSprite update when unchecked clears and draws border."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = MockFactory.create_pygame_font_mock()
        mock_get_font.return_value = font

        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name='TestCheck')
        checkbox.checked = False
        checkbox.update()

    def test_checkbox_update_checked(self, mocker):
        """Test CheckboxSprite update when checked draws X lines."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = MockFactory.create_pygame_font_mock()
        mock_get_font.return_value = font

        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name='TestCheck')
        checkbox.checked = True
        checkbox.update()

    def test_checkbox_left_mouse_down_does_nothing(self, mocker):
        """Test CheckboxSprite on_left_mouse_button_down_event is a no-op."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = MockFactory.create_pygame_font_mock()
        mock_get_font.return_value = font

        checkbox = CheckboxSprite(x=10, y=20, width=20, height=20, name='TestCheck')
        event = mocker.Mock()
        initial_checked = checkbox.checked
        checkbox.on_left_mouse_button_down_event(event)
        assert checkbox.checked == initial_checked


class TestInputBoxCoverage:
    """Coverage tests for InputBox."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_inputbox_initialization(self, mocker):
        """Test InputBox initialization."""
        inputbox = InputBox(x=10, y=20, width=200, height=30, text='initial')
        assert inputbox.text == 'initial'
        assert inputbox.active is False

    def test_inputbox_activate_deactivate(self, mocker):
        """Test InputBox activate and deactivate methods."""
        inputbox = InputBox(x=10, y=20, width=200, height=30)
        inputbox.activate()
        assert inputbox.active is True
        assert inputbox.dirty == 2

        inputbox.deactivate()
        assert inputbox.active is False
        assert inputbox.dirty == 0

    def test_inputbox_render(self, mocker):
        """Test InputBox render method updates text image."""
        inputbox = InputBox(x=10, y=20, width=200, height=30, text='hello')
        inputbox.render()
        # Should not raise

    def test_inputbox_on_mouse_up_activates(self, mocker):
        """Test InputBox on_mouse_up_event activates the input box."""
        inputbox = InputBox(x=10, y=20, width=200, height=30)
        event = mocker.Mock()
        inputbox.on_mouse_up_event(event)
        assert inputbox.active is True

    def test_inputbox_key_up_tab_deactivates(self, mocker):
        """Test InputBox on_key_up_event with Tab key deactivates."""
        inputbox = InputBox(x=10, y=20, width=200, height=30)
        inputbox.activate()
        event = mocker.Mock()
        event.key = pygame.K_TAB
        inputbox.on_key_up_event(event)
        assert inputbox.active is False

    def test_inputbox_key_up_escape_deactivates(self, mocker):
        """Test InputBox on_key_up_event with Escape key deactivates."""
        inputbox = InputBox(x=10, y=20, width=200, height=30)
        inputbox.activate()
        event = mocker.Mock()
        event.key = pygame.K_ESCAPE
        inputbox.on_key_up_event(event)
        assert inputbox.active is False

    def test_inputbox_key_down_backspace(self, mocker):
        """Test InputBox on_key_down_event with backspace removes character."""
        inputbox = InputBox(x=10, y=20, width=200, height=30, text='hello')
        inputbox.activate()
        event = mocker.Mock()
        event.key = pygame.K_BACKSPACE
        event.unicode = ''
        event.mod = 0
        inputbox.on_key_down_event(event)
        assert inputbox.text == 'hell'

    def test_inputbox_key_down_unicode_input(self, mocker):
        """Test InputBox on_key_down_event with unicode character input."""
        inputbox = InputBox(x=10, y=20, width=200, height=30, text='')
        inputbox.activate()
        event = mocker.Mock()
        event.key = pygame.K_a
        event.unicode = 'a'
        event.mod = 0
        inputbox.on_key_down_event(event)
        assert inputbox.text == 'a'

    def test_inputbox_key_down_return_triggers_confirm(self, mocker):
        """Test InputBox on_key_down_event with Return triggers parent confirm."""
        parent = mocker.Mock()
        parent.x = 0
        parent.y = 0
        parent.on_confirm_event = mocker.Mock()
        inputbox = InputBox(x=10, y=20, width=200, height=30, text='test', parent=parent)
        inputbox.activate()
        event = mocker.Mock()
        event.key = pygame.K_RETURN
        event.unicode = ''
        event.mod = 0
        inputbox.on_key_down_event(event)
        parent.on_confirm_event.assert_called_once()

    def test_inputbox_key_down_colon_via_shift_semicolon(self, mocker):
        """Test InputBox on_key_down_event with Shift+semicolon produces colon."""
        inputbox = InputBox(x=10, y=20, width=200, height=30, text='')
        inputbox.activate()
        event = mocker.Mock()
        event.key = pygame.K_SEMICOLON
        event.unicode = ':'
        event.mod = pygame.KMOD_SHIFT
        inputbox.on_key_down_event(event)
        assert inputbox.text == ':'

    def test_inputbox_on_input_box_submit_no_parent(self, mocker):
        """Test InputBox submit event with no parent."""
        inputbox = InputBox(x=10, y=20, width=200, height=30, text='test')
        inputbox.parent = None
        event = mocker.Mock()
        # Should not raise
        inputbox.on_input_box_submit_event(event)

    def test_inputbox_on_input_box_submit_with_parent(self, mocker):
        """Test InputBox submit event with parent."""
        parent = mocker.Mock()
        parent.x = 0
        parent.y = 0
        parent.on_input_box_submit_event = mocker.Mock()
        inputbox = InputBox(x=10, y=20, width=200, height=30, text='test', parent=parent)
        event = mocker.Mock()
        inputbox.on_input_box_submit_event(event)
        parent.on_input_box_submit_event.assert_called_once()

    def test_inputbox_update(self, mocker):
        """Test InputBox update method renders cursor when active."""
        inputbox = InputBox(x=10, y=20, width=200, height=30, text='hello')
        inputbox.update()


class TestTextBoxSpriteCoverage:
    """Coverage tests for TextBoxSprite."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_textbox_update_nested_sprites(self, mocker):
        """Test TextBoxSprite update_nested_sprites propagates dirty flag."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        textbox = TextBoxSprite(x=10, y=20, width=200, height=30, name='TestTB')
        textbox.dirty = 2
        textbox.update_nested_sprites()
        assert textbox.text_box.dirty == 2

    def test_textbox_update_with_border(self, mocker):
        """Test TextBoxSprite update draws border when border_width > 0."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        textbox = TextBoxSprite(x=10, y=20, width=200, height=30, name='TestTB')
        textbox.border_width = 2
        textbox.update()


class TestColorWellSpriteCoverage:
    """Coverage tests for ColorWellSprite."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_color_well_hex_color_property(self):
        """Test ColorWellSprite hex_color property returns correct format."""
        color_well = ColorWellSprite(x=10, y=20, width=100, height=60, name='TestCW')
        color_well.active_color = (255, 128, 0)
        hex_color = color_well.hex_color
        assert hex_color == '#FF8000FF'

    def test_color_well_hex_color_with_alpha(self):
        """Test ColorWellSprite hex_color with explicit alpha."""
        color_well = ColorWellSprite(x=10, y=20, width=100, height=60, name='TestCW')
        color_well.active_color = (0, 0, 0, 128)
        hex_color = color_well.hex_color
        assert hex_color == '#00000080'

    def test_color_well_rgba_setter(self):
        """Test ColorWellSprite active_color setter with 4-tuple RGBA."""
        color_well = ColorWellSprite(x=10, y=20, width=100, height=60, name='TestCW')
        color_well.active_color = (10, 20, 30, 40)
        assert color_well.red == 10
        assert color_well.green == 20
        assert color_well.blue == 30
        assert color_well.alpha == 40

    def test_color_well_rgb_setter_defaults_alpha(self):
        """Test ColorWellSprite active_color setter with 3-tuple defaults alpha to 255."""
        color_well = ColorWellSprite(x=10, y=20, width=100, height=60, name='TestCW')
        color_well.active_color = (10, 20, 30)
        assert color_well.alpha == 255

    def test_color_well_update(self):
        """Test ColorWellSprite update draws border and fills color."""
        color_well = ColorWellSprite(x=10, y=20, width=100, height=60, name='TestCW')
        color_well.active_color = (255, 0, 0, 255)
        color_well.update()

    def test_color_well_update_nested_sprites(self):
        """Test ColorWellSprite update_nested_sprites is a no-op."""
        color_well = ColorWellSprite(x=10, y=20, width=100, height=60, name='TestCW')
        color_well.update_nested_sprites()


class TestInputDialogCoverage:
    """Coverage tests for InputDialog widget."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_input_dialog_initialization(self, mocker):
        """Test InputDialog creates all expected child components."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = MockFactory.create_pygame_font_mock()
        mock_get_font.return_value = font

        dialog = InputDialog(
            x=100,
            y=100,
            width=400,
            height=200,
            name='TestDialog',
            dialog_text='Enter value:',
            confirm_text='OK',
            cancel_text='Cancel',
        )
        assert dialog.dialog_text_sprite is not None
        assert dialog.input_box is not None
        assert dialog.confirm_button is not None
        assert dialog.cancel_button is not None
        assert dialog.input_box.active is True

    def test_input_dialog_custom_text(self, mocker):
        """Test InputDialog with custom dialog text."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = MockFactory.create_pygame_font_mock()
        mock_get_font.return_value = font

        dialog = InputDialog(
            x=100,
            y=100,
            width=400,
            height=200,
            name='TestDialog',
            dialog_text='Custom prompt',
            confirm_text='Save',
            cancel_text='Abort',
        )
        assert dialog.dialog_text_sprite.text_box.text == 'Custom prompt'
        assert dialog.confirm_button.name == 'Save'
        assert dialog.cancel_button.name == 'Abort'


class TestSliderSpriteCoverage:
    """Additional coverage tests for SliderSprite."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_slider_update_color_well_red(self, mocker):
        """Test SliderSprite update_color_well for red slider."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        parent = mocker.Mock()
        parent.color_well = mocker.Mock()
        parent.red_slider = mocker.Mock()
        parent.red_slider.value = 100
        parent.green_slider = mocker.Mock()
        parent.green_slider.value = 50
        parent.blue_slider = mocker.Mock()
        parent.blue_slider.value = 25
        parent.alpha_slider = mocker.Mock()
        parent.alpha_slider.value = 255
        # Prevent _draw_slider_visual_indicators from accessing visual_collision_manager
        del parent.visual_collision_manager

        slider = SliderSprite(x=10, y=20, width=200, height=10, name='R', parent=parent)
        slider._value = 100
        slider.update_color_well()

    def test_slider_update_method(self, mocker):
        """Test SliderSprite update calls update_slider_appearance when dirty."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        slider = SliderSprite(x=10, y=20, width=200, height=10, name='TestSlider')
        slider.dirty = 2
        slider.update()

    def test_slider_color_based_on_name(self, mocker):
        """Test SliderSprite assigns color based on name."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        red_slider = SliderSprite(x=10, y=20, width=200, height=10, name='R')
        assert red_slider.color == (255, 0, 0)

        green_slider = SliderSprite(x=10, y=20, width=200, height=10, name='G')
        assert green_slider.color == (0, 255, 0)

        blue_slider = SliderSprite(x=10, y=20, width=200, height=10, name='B')
        assert blue_slider.color == (0, 0, 255)

        other_slider = SliderSprite(x=10, y=20, width=200, height=10, name='Other')
        assert other_slider.color == (128, 128, 128)

    def test_slider_restore_original_value(self, mocker):
        """Test SliderSprite _restore_original_value restores text."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        slider = SliderSprite(x=10, y=20, width=200, height=10, name='TestSlider')
        slider.value = 100
        slider.original_value = 100
        slider.text_sprite.active = True
        slider.text_sprite.text = '200'
        slider._restore_original_value()
        assert slider.text_sprite.text == '100'
        assert slider.text_sprite.active is False

    def test_slider_handle_text_enter_empty(self, mocker):
        """Test SliderSprite _handle_text_enter with empty text restores."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        slider = SliderSprite(x=10, y=20, width=200, height=10, name='TestSlider')
        slider.value = 50
        slider.original_value = 50
        slider.text_sprite.text = '  '
        slider.text_sprite.active = True
        event = mocker.Mock()
        slider._handle_text_enter(event)
        assert slider.text_sprite.text == '50'

    def test_slider_handle_text_enter_hex_value(self, mocker):
        """Test SliderSprite _handle_text_enter with hex input."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        slider = SliderSprite(x=10, y=20, width=200, height=10, name='TestSlider')
        slider.text_sprite.text = 'ff'
        slider.text_sprite.active = True
        event = mocker.Mock()
        slider._handle_text_enter(event)
        assert slider.value == 255

    def test_slider_handle_text_character_max_length(self, mocker):
        """Test SliderSprite _handle_text_character_input respects max length."""
        mock_get_font = mocker.patch('glitchygames.ui.widgets.FontManager.get_font')
        font = mocker.Mock()
        rendered_surface = mocker.Mock()
        rendered_surface.get_rect.return_value = mocker.Mock()
        font.render = mocker.Mock(return_value=rendered_surface)
        mock_get_font.return_value = font

        slider = SliderSprite(x=10, y=20, width=200, height=10, name='TestSlider')
        slider.text_sprite.text = '12'
        slider.text_sprite.active = True
        event = mocker.Mock()
        event.key = pygame.K_3
        event.unicode = '3'
        slider._handle_text_character_input(event)
        assert slider.text_sprite.text == '123'

        # Try adding a 4th character - should be truncated to 3
        event.key = pygame.K_4
        event.unicode = '4'
        slider._handle_text_character_input(event)
        assert len(slider.text_sprite.text) == 3
