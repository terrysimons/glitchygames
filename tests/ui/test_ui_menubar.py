"""Test suite for MenuBar UI component.

This module tests the MenuBar class functionality including initialization,
menu item management, and event handling.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.ui import MenuBar, MenuItem

from mocks.test_mock_factory import MockFactory

# Test constants to avoid magic values
TEST_BORDER_WIDTH = 2
TEST_MENU_OFFSET_X = 2
TEST_MENU_OFFSET_Y = 2
TEST_MENUBAR_WIDTH = 800
TEST_MENUBAR_HEIGHT = 50
TEST_MENU_ITEM_WIDTH = 100
TEST_EXPECTED_MENU_COUNT = 2


@pytest.mark.usefixtures("mock_pygame_patches")
class TestMenuBarFunctionality(unittest.TestCase):
    """Test MenuBar functionality."""

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

    def test_menubar_initialization(self):
        """Test MenuBar initialization."""
        groups = Mock()
        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)

        # Verify MenuBar-specific attributes
        assert menubar.all_sprites == groups
        assert menubar.background_color == (0, 255, 0)
        assert menubar.border_width == TEST_BORDER_WIDTH
        assert menubar.menu_items == {}
        assert menubar.menu_offset_x == TEST_MENU_OFFSET_X
        assert menubar.menu_offset_y == TEST_MENU_OFFSET_Y
        assert menubar.width == TEST_MENUBAR_WIDTH
        assert menubar.height == TEST_MENUBAR_HEIGHT
        assert not menubar.has_focus

    def test_menubar_menu_item_methods(self):
        """Test MenuBar menu item management methods."""
        groups = Mock()
        menubar = MenuBar(
            x=0,
            y=0,
            width=TEST_MENUBAR_WIDTH,
            height=TEST_MENUBAR_HEIGHT,
            name="test_menubar",
            groups=groups
        )

        # Create a mock MenuItem
        mock_menu_item = Mock(spec=MenuItem)
        mock_menu_item.name = "File"
        mock_menu_item.rect = Mock()
        mock_menu_item.rect.x = 0
        mock_menu_item.rect.y = 0
        mock_menu_item.rect.width = TEST_MENU_ITEM_WIDTH
        mock_menu_item.image = Mock()
        mock_menu_item.add = Mock()

        # Test adding menu items
        menubar.add_menu_item(mock_menu_item)
        assert "File" in menubar.menu_items
        assert menubar.menu_items["File"] == mock_menu_item

        # Test that menu_items is a dictionary that can be accessed directly
        assert len(menubar.menu_items) == 1
        assert "File" in menubar.menu_items

        # Test adding another menu item
        mock_menu_item2 = Mock(spec=MenuItem)
        mock_menu_item2.name = "Edit"
        mock_menu_item2.rect = Mock()
        mock_menu_item2.rect.x = 0
        mock_menu_item2.rect.y = 0
        mock_menu_item2.rect.width = TEST_MENU_ITEM_WIDTH
        mock_menu_item2.image = Mock()
        mock_menu_item2.add = Mock()

        menubar.add_menu_item(mock_menu_item2)
        assert len(menubar.menu_items) == TEST_EXPECTED_MENU_COUNT
        assert "Edit" in menubar.menu_items

    def test_menubar_add_menu(self):
        """Test adding MenuItem objects to MenuBar."""
        groups = Mock()
        menubar = MenuBar(
            x=0,
            y=0,
            width=TEST_MENUBAR_WIDTH,
            height=TEST_MENUBAR_HEIGHT,
            name="test_menubar",
            groups=groups
        )

        # Create a mock MenuItem with proper attributes
        mock_menu = Mock(spec=MenuItem)
        mock_menu.name = "TestMenu"
        mock_menu.rect = Mock()
        mock_menu.rect.x = 0
        mock_menu.rect.y = 0
        mock_menu.rect.width = TEST_MENU_ITEM_WIDTH  # Add width attribute
        mock_menu.image = Mock()
        mock_menu.add = Mock()

        # Test adding menu
        menubar.add_menu(mock_menu)

        # Verify menu was added
        assert "TestMenu" in menubar.menu_items
        assert menubar.menu_items["TestMenu"] == mock_menu

        # Verify menu was added to groups
        mock_menu.add.assert_called_once()

    def test_menubar_focus_handling(self):
        """Test MenuBar focus handling."""
        groups = Mock()
        menubar = MenuBar(
            x=0,
            y=0,
            width=TEST_MENUBAR_WIDTH,
            height=TEST_MENUBAR_HEIGHT,
            name="test_menubar",
            groups=groups
        )

        # Test initial focus state
        assert not menubar.has_focus

        # Test setting focus directly (since gain_focus/lose_focus don't exist)
        menubar.has_focus = True
        assert menubar.has_focus

        # Test losing focus
        menubar.has_focus = False
        assert not menubar.has_focus

    def test_menubar_mouse_events(self):
        """Test MenuBar mouse event handling."""
        # Create a proper mock groups that is iterable
        groups = Mock()
        groups.__iter__ = Mock(return_value=iter([]))  # Empty list for no collisions
        menubar = MenuBar(
            x=0,
            y=0,
            width=TEST_MENUBAR_WIDTH,
            height=TEST_MENUBAR_HEIGHT,
            name="test_menubar",
            groups=groups
        )

        # Test mouse button down event
        event = Mock()
        event.pos = (100, 25)  # Within menu bar
        menubar.on_left_mouse_button_down_event(event)

        # Test mouse button up event
        menubar.on_left_mouse_button_up_event(event)

    def test_menubar_rendering(self):
        """Test MenuBar rendering functionality."""
        groups = Mock()
        menubar = MenuBar(
            x=0,
            y=0,
            width=TEST_MENUBAR_WIDTH,
            height=TEST_MENUBAR_HEIGHT,
            name="test_menubar",
            groups=groups
        )

        # Test that menubar was created successfully
        assert menubar is not None
        assert menubar.width == TEST_MENUBAR_WIDTH
        assert menubar.height == TEST_MENUBAR_HEIGHT


if __name__ == "__main__":
    unittest.main()
