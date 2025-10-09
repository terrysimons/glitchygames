"""Comprehensive test coverage for UI module."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pygame

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))

from test_mock_factory import MockFactory
from glitchygames.ui import (
    MenuBar, MenuItem, TextSprite, ButtonSprite, CheckboxSprite,
    InputBox, TextBoxSprite, SliderSprite, ColorWellSprite,
    InputDialog, MultiLineTextBox
)

# Remove module-level setup to avoid conflicts with other UI test files


class TestMenuBarCoverage(unittest.TestCase):
    """Test coverage for MenuBar class."""

    def setUp(self):
        """Set up test fixtures."""
        # Use simple mocking instead of MockFactory to avoid conflicts
        self.display_patcher = patch('pygame.display')
        self.surface_patcher = patch('pygame.Surface')
        self.sprite_patcher = patch('pygame.sprite.LayeredDirty')
        self.draw_patcher = patch('pygame.draw.rect')
        
        self.mock_display = self.display_patcher.start()
        self.mock_surface = self.surface_patcher.start()
        self.mock_sprite = self.sprite_patcher.start()
        self.mock_draw = self.draw_patcher.start()
        
        # Set up mock display
        self.mock_display.get_surface.return_value = Mock()
        
        # Set up mock surface
        mock_surface_instance = Mock()
        mock_surface_instance.get_rect.return_value = Mock()
        self.mock_surface.return_value = mock_surface_instance
        
        # Mock pygame.freetype by adding it to pygame module
        pygame.freetype = Mock()
        pygame.freetype.Font.return_value = Mock()

    def tearDown(self):
        """Clean up test fixtures."""
        self.display_patcher.stop()
        self.surface_patcher.stop()
        self.sprite_patcher.stop()
        self.draw_patcher.stop()
        
        # Clean up pygame.freetype mock
        if hasattr(pygame, 'freetype'):
            delattr(pygame, 'freetype')

    def test_menubar_initialization(self):
        """Test MenuBar initialization."""
        groups = pygame.sprite.LayeredDirty()
        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
        
        self.assertEqual(menubar.name, "test_menubar")
        self.assertEqual(menubar.width, 800)
        self.assertEqual(menubar.height, 50)
        self.assertEqual(menubar.background_color, (0, 255, 0))
        self.assertEqual(menubar.border_width, 2)
        self.assertFalse(menubar.has_focus)

    def test_menubar_add_menu_item(self):
        """Test adding menu items to MenuBar."""
        groups = pygame.sprite.LayeredDirty()
        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
        
        # Create a MenuItem object
        menu_item = MenuItem(x=10, y=10, width=100, height=30, name="File", groups=groups)
        
        # Test adding a menu item
        menubar.add_menu_item(menu_item)
        self.assertIn("File", menubar.menu_items)
        self.assertEqual(menubar.menu_items["File"], menu_item)

    def test_menubar_remove_menu_item(self):
        """Test removing menu items from MenuBar."""
        groups = pygame.sprite.LayeredDirty()
        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
        
        # Add a menu item
        menu_item = MenuItem(x=10, y=10, width=100, height=30, name="File", groups=groups)
        menubar.add_menu_item(menu_item)
        self.assertIn("File", menubar.menu_items)
        
        # Remove menu item by deleting from dictionary (since there's no remove method)
        del menubar.menu_items["File"]
        self.assertNotIn("File", menubar.menu_items)

    def test_menubar_clear_menu_items(self):
        """Test clearing all menu items from MenuBar."""
        groups = pygame.sprite.LayeredDirty()
        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
        
        # Add multiple menu items
        menu_item1 = MenuItem(x=10, y=10, width=100, height=30, name="File", groups=groups)
        menu_item2 = MenuItem(x=120, y=10, width=100, height=30, name="Edit", groups=groups)
        menubar.add_menu_item(menu_item1)
        menubar.add_menu_item(menu_item2)
        self.assertEqual(len(menubar.menu_items), 2)
        
        # Clear all menu items by clearing the dictionary
        menubar.menu_items.clear()
        self.assertEqual(len(menubar.menu_items), 0)

    def test_menubar_get_menu_item(self):
        """Test getting menu items from MenuBar."""
        groups = pygame.sprite.LayeredDirty()
        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
        
        # Add a menu item
        menu_item = MenuItem(x=10, y=10, width=100, height=30, name="File", groups=groups)
        menubar.add_menu_item(menu_item)
        
        # Get the menu item from the dictionary
        item = menubar.menu_items.get("File")
        self.assertEqual(item, menu_item)
        
        # Test getting non-existent item
        item = menubar.menu_items.get("NonExistent")
        self.assertIsNone(item)

    def test_menubar_has_menu_item(self):
        """Test checking if MenuBar has a menu item."""
        groups = pygame.sprite.LayeredDirty()
        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
        
        # Add a menu item
        menu_item = MenuItem(x=10, y=10, width=100, height=30, name="File", groups=groups)
        menubar.add_menu_item(menu_item)
        
        # Check if menu item exists using dictionary lookup
        self.assertTrue("File" in menubar.menu_items)
        self.assertFalse("NonExistent" in menubar.menu_items)

    def test_menubar_get_menu_item_count(self):
        """Test getting menu item count from MenuBar."""
        groups = pygame.sprite.LayeredDirty()
        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
        
        # Initially no menu items
        self.assertEqual(len(menubar.menu_items), 0)
        
        # Add menu items
        menu_item1 = MenuItem(x=10, y=10, width=100, height=30, name="File", groups=groups)
        menu_item2 = MenuItem(x=120, y=10, width=100, height=30, name="Edit", groups=groups)
        menubar.add_menu_item(menu_item1)
        menubar.add_menu_item(menu_item2)
        self.assertEqual(len(menubar.menu_items), 2)

    def test_menubar_get_menu_item_names(self):
        """Test getting menu item names from MenuBar."""
        groups = pygame.sprite.LayeredDirty()
        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
        
        # Add menu items
        menu_item1 = MenuItem(x=10, y=10, width=100, height=30, name="File", groups=groups)
        menu_item2 = MenuItem(x=120, y=10, width=100, height=30, name="Edit", groups=groups)
        menubar.add_menu_item(menu_item1)
        menubar.add_menu_item(menu_item2)
        
        # Get menu item names from dictionary keys
        names = list(menubar.menu_items.keys())
        self.assertIn("File", names)
        self.assertIn("Edit", names)
        self.assertEqual(len(names), 2)

    def test_menubar_get_menu_item_values(self):
        """Test getting menu item values from MenuBar."""
        groups = pygame.sprite.LayeredDirty()
        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
        
        # Add menu items
        menu_item1 = MenuItem(x=10, y=10, width=100, height=30, name="File", groups=groups)
        menu_item2 = MenuItem(x=120, y=10, width=100, height=30, name="Edit", groups=groups)
        menubar.add_menu_item(menu_item1)
        menubar.add_menu_item(menu_item2)
        
        # Get menu item values from dictionary values
        values = list(menubar.menu_items.values())
        self.assertIn(menu_item1, values)
        self.assertIn(menu_item2, values)
        self.assertEqual(len(values), 2)

    def test_menubar_get_menu_item_items(self):
        """Test getting menu item items from MenuBar."""
        groups = pygame.sprite.LayeredDirty()
        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
        
        # Add menu items
        menu_item1 = MenuItem(x=10, y=10, width=100, height=30, name="File", groups=groups)
        menu_item2 = MenuItem(x=120, y=10, width=100, height=30, name="Edit", groups=groups)
        menubar.add_menu_item(menu_item1)
        menubar.add_menu_item(menu_item2)
        
        # Get menu item items from dictionary items
        items = list(menubar.menu_items.items())
        self.assertEqual(len(items), 2)
        self.assertIn(("File", menu_item1), items)
        self.assertIn(("Edit", menu_item2), items)

    def test_menubar_update_menu_item(self):
        """Test updating menu items in MenuBar."""
        groups = pygame.sprite.LayeredDirty()
        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
        
        # Add a menu item
        menu_item = MenuItem(x=10, y=10, width=100, height=30, name="File", groups=groups)
        menubar.add_menu_item(menu_item)
        self.assertEqual(menubar.menu_items["File"], menu_item)
        
        # Update the menu item by replacing it in the dictionary
        new_menu_item = MenuItem(x=10, y=10, width=100, height=30, name="File", groups=groups)
        menubar.menu_items["File"] = new_menu_item
        self.assertEqual(menubar.menu_items["File"], new_menu_item)

    def test_menubar_set_menu_item(self):
        """Test setting menu items in MenuBar."""
        groups = pygame.sprite.LayeredDirty()
        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
        
        # Set a menu item by adding it to the dictionary
        menu_item1 = MenuItem(x=10, y=10, width=100, height=30, name="File", groups=groups)
        menubar.menu_items["File"] = menu_item1
        self.assertEqual(menubar.menu_items["File"], menu_item1)
        
        # Set another menu item
        menu_item2 = MenuItem(x=120, y=10, width=100, height=30, name="Edit", groups=groups)
        menubar.menu_items["Edit"] = menu_item2
        self.assertEqual(menubar.menu_items["Edit"], menu_item2)

    def test_menubar_pop_menu_item(self):
        """Test popping menu items from MenuBar."""
        groups = pygame.sprite.LayeredDirty()
        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
        
        # Add a menu item
        menu_item = MenuItem(x=10, y=10, width=100, height=30, name="File", groups=groups)
        menubar.add_menu_item(menu_item)
        self.assertEqual(len(menubar.menu_items), 1)
        
        # Pop the menu item using dictionary pop
        item = menubar.menu_items.pop("File")
        self.assertEqual(item, menu_item)
        self.assertEqual(len(menubar.menu_items), 0)
        
        # Test popping non-existent item
        item = menubar.menu_items.pop("NonExistent", None)
        self.assertIsNone(item)

    def test_menubar_copy_menu_items(self):
        """Test copying menu items from MenuBar."""
        groups = pygame.sprite.LayeredDirty()
        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
        
        # Add menu items
        menu_item1 = MenuItem(x=10, y=10, width=100, height=30, name="File", groups=groups)
        menu_item2 = MenuItem(x=120, y=10, width=100, height=30, name="Edit", groups=groups)
        menubar.add_menu_item(menu_item1)
        menubar.add_menu_item(menu_item2)
        
        # Copy menu items using dictionary copy
        copied_items = menubar.menu_items.copy()
        self.assertEqual(copied_items, menubar.menu_items)
        self.assertIsNot(copied_items, menubar.menu_items)  # Should be a copy, not the same object

    def test_menubar_menu_items_property(self):
        """Test MenuBar menu_items property."""
        groups = pygame.sprite.LayeredDirty()
        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
        
        # Test getting menu_items property
        self.assertEqual(menubar.menu_items, {})
        
        # Test setting menu_items property
        menubar.menu_items = {"File": "file_menu", "Edit": "edit_menu"}
        self.assertEqual(menubar.menu_items["File"], "file_menu")
        self.assertEqual(menubar.menu_items["Edit"], "edit_menu")

    def test_menubar_menu_offset_properties(self):
        """Test MenuBar menu offset properties."""
        groups = pygame.sprite.LayeredDirty()
        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
        
        # Test default offset values
        self.assertEqual(menubar.menu_offset_x, 2)
        self.assertEqual(menubar.menu_offset_y, 2)
        
        # Test setting offset values
        menubar.menu_offset_x = 5
        menubar.menu_offset_y = 10
        self.assertEqual(menubar.menu_offset_x, 5)
        self.assertEqual(menubar.menu_offset_y, 10)

    def test_menubar_background_color_property(self):
        """Test MenuBar background_color property."""
        groups = pygame.sprite.LayeredDirty()
        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
        
        # Test default background color
        self.assertEqual(menubar.background_color, (0, 255, 0))
        
        # Test setting background color
        menubar.background_color = (255, 0, 0)
        self.assertEqual(menubar.background_color, (255, 0, 0))

    def test_menubar_border_width_property(self):
        """Test MenuBar border_width property."""
        groups = pygame.sprite.LayeredDirty()
        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
        
        # Test default border width
        self.assertEqual(menubar.border_width, 2)
        
        # Test setting border width
        menubar.border_width = 5
        self.assertEqual(menubar.border_width, 5)

    def test_menubar_has_focus_property(self):
        """Test MenuBar has_focus property."""
        groups = pygame.sprite.LayeredDirty()
        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
        
        # Test default focus state
        self.assertFalse(menubar.has_focus)
        
        # Test setting focus state
        menubar.has_focus = True
        self.assertTrue(menubar.has_focus)

    def test_menubar_all_sprites_property(self):
        """Test MenuBar all_sprites property."""
        groups = pygame.sprite.LayeredDirty()
        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
        
        # Test all_sprites property
        self.assertEqual(menubar.all_sprites, groups)

    def test_menubar_width_height_properties(self):
        """Test MenuBar width and height properties."""
        groups = pygame.sprite.LayeredDirty()
        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
        
        # Test width and height properties
        self.assertEqual(menubar.width, 800)
        self.assertEqual(menubar.height, 50)
        
        # Test setting width and height
        menubar.width = 1000
        menubar.height = 100
        self.assertEqual(menubar.width, 1000)
        self.assertEqual(menubar.height, 100)


if __name__ == '__main__':
    unittest.main()
