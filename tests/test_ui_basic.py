"""Basic test coverage for UI module - focusing on non-pygame dependent functionality."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.ui import MenuBar


class TestUIBasicCoverage(unittest.TestCase):
    """Test coverage for UI basic functionality."""

    def test_menubar_initialization(self):
        """Test MenuBar initialization."""
        with patch('pygame.sprite.LayeredDirty') as mock_layered_dirty:
            with patch('glitchygames.ui.FocusableSingletonBitmappySprite.__init__') as mock_super_init:
                with patch('pygame.Surface') as mock_surface:
                    with patch('pygame.draw.rect') as mock_draw_rect:
                        mock_super_init.return_value = None
                        
                        # Create a mock rect
                        mock_rect = Mock()
                        mock_rect.x = 0
                        mock_rect.y = 0
                        mock_rect.width = 800
                        mock_rect.height = 50
                        
                        groups = Mock()
                        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
                        
                        # Manually set the rect attribute that would come from parent class
                        menubar.rect = mock_rect
                        
                        # Verify super().__init__ was called with correct parameters
                        mock_super_init.assert_called_once_with(
                            x=0, y=0, width=800, height=50, name="test_menubar", groups=groups
                        )
                        
                        # Verify MenuBar-specific attributes
                        self.assertEqual(menubar.all_sprites, groups)
                        self.assertEqual(menubar.background_color, (0, 255, 0))
                        self.assertEqual(menubar.border_width, 2)
                        self.assertEqual(menubar.menu_items, {})
                        self.assertEqual(menubar.menu_offset_x, 2)
                        self.assertEqual(menubar.menu_offset_y, 2)
                        self.assertEqual(menubar.width, 800)
                        self.assertEqual(menubar.height, 50)
                        self.assertFalse(menubar.has_focus)

    def test_menubar_add_menu_item(self):
        """Test adding menu items to MenuBar."""
        with patch('pygame.sprite.LayeredDirty') as mock_layered_dirty:
            with patch('glitchygames.ui.FocusableSingletonBitmappySprite.__init__') as mock_super_init:
                mock_super_init.return_value = None
                
                groups = Mock()
                menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
                
                # Test adding a menu item
                menubar.add_menu_item("File", "file_menu")
                self.assertIn("File", menubar.menu_items)
                self.assertEqual(menubar.menu_items["File"], "file_menu")

    def test_menubar_remove_menu_item(self):
        """Test removing menu items from MenuBar."""
        with patch('pygame.sprite.LayeredDirty') as mock_layered_dirty:
            with patch('glitchygames.ui.FocusableSingletonBitmappySprite.__init__') as mock_super_init:
                mock_super_init.return_value = None
                
                groups = Mock()
                menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
                
                # Add and then remove a menu item
                menubar.add_menu_item("File", "file_menu")
                self.assertIn("File", menubar.menu_items)
                
                menubar.remove_menu_item("File")
                self.assertNotIn("File", menubar.menu_items)

    def test_menubar_clear_menu_items(self):
        """Test clearing all menu items from MenuBar."""
        with patch('pygame.sprite.LayeredDirty') as mock_layered_dirty:
            with patch('glitchygames.ui.FocusableSingletonBitmappySprite.__init__') as mock_super_init:
                mock_super_init.return_value = None
                
                groups = Mock()
                menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
                
                # Add multiple menu items
                menubar.add_menu_item("File", "file_menu")
                menubar.add_menu_item("Edit", "edit_menu")
                self.assertEqual(len(menubar.menu_items), 2)
                
                # Clear all menu items
                menubar.clear_menu_items()
                self.assertEqual(len(menubar.menu_items), 0)

    def test_menubar_get_menu_item(self):
        """Test getting menu items from MenuBar."""
        with patch('pygame.sprite.LayeredDirty') as mock_layered_dirty:
            with patch('glitchygames.ui.FocusableSingletonBitmappySprite.__init__') as mock_super_init:
                mock_super_init.return_value = None
                
                groups = Mock()
                menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
                
                # Add a menu item
                menubar.add_menu_item("File", "file_menu")
                
                # Get the menu item
                item = menubar.get_menu_item("File")
                self.assertEqual(item, "file_menu")
                
                # Test getting non-existent item
                item = menubar.get_menu_item("NonExistent")
                self.assertIsNone(item)

    def test_menubar_has_menu_item(self):
        """Test checking if MenuBar has a menu item."""
        with patch('pygame.sprite.LayeredDirty') as mock_layered_dirty:
            with patch('glitchygames.ui.FocusableSingletonBitmappySprite.__init__') as mock_super_init:
                mock_super_init.return_value = None
                
                groups = Mock()
                menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
                
                # Add a menu item
                menubar.add_menu_item("File", "file_menu")
                
                # Check if menu item exists
                self.assertTrue(menubar.has_menu_item("File"))
                self.assertFalse(menubar.has_menu_item("NonExistent"))

    def test_menubar_get_menu_item_count(self):
        """Test getting menu item count from MenuBar."""
        with patch('pygame.sprite.LayeredDirty') as mock_layered_dirty:
            with patch('glitchygames.ui.FocusableSingletonBitmappySprite.__init__') as mock_super_init:
                mock_super_init.return_value = None
                
                groups = Mock()
                menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
                
                # Initially no menu items
                self.assertEqual(menubar.get_menu_item_count(), 0)
                
                # Add menu items
                menubar.add_menu_item("File", "file_menu")
                menubar.add_menu_item("Edit", "edit_menu")
                self.assertEqual(menubar.get_menu_item_count(), 2)

    def test_menubar_get_menu_item_names(self):
        """Test getting menu item names from MenuBar."""
        with patch('pygame.sprite.LayeredDirty') as mock_layered_dirty:
            with patch('glitchygames.ui.FocusableSingletonBitmappySprite.__init__') as mock_super_init:
                mock_super_init.return_value = None
                
                groups = Mock()
                menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
                
                # Add menu items
                menubar.add_menu_item("File", "file_menu")
                menubar.add_menu_item("Edit", "edit_menu")
                
                # Get menu item names
                names = menubar.get_menu_item_names()
                self.assertIn("File", names)
                self.assertIn("Edit", names)
                self.assertEqual(len(names), 2)

    def test_menubar_get_menu_item_values(self):
        """Test getting menu item values from MenuBar."""
        with patch('pygame.sprite.LayeredDirty') as mock_layered_dirty:
            with patch('glitchygames.ui.FocusableSingletonBitmappySprite.__init__') as mock_super_init:
                mock_super_init.return_value = None
                
                groups = Mock()
                menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
                
                # Add menu items
                menubar.add_menu_item("File", "file_menu")
                menubar.add_menu_item("Edit", "edit_menu")
                
                # Get menu item values
                values = menubar.get_menu_item_values()
                self.assertIn("file_menu", values)
                self.assertIn("edit_menu", values)
                self.assertEqual(len(values), 2)

    def test_menubar_get_menu_item_items(self):
        """Test getting menu item items from MenuBar."""
        with patch('pygame.sprite.LayeredDirty') as mock_layered_dirty:
            with patch('glitchygames.ui.FocusableSingletonBitmappySprite.__init__') as mock_super_init:
                mock_super_init.return_value = None
                
                groups = Mock()
                menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
                
                # Add menu items
                menubar.add_menu_item("File", "file_menu")
                menubar.add_menu_item("Edit", "edit_menu")
                
                # Get menu item items
                items = menubar.get_menu_item_items()
                self.assertEqual(len(items), 2)
                self.assertIn(("File", "file_menu"), items)
                self.assertIn(("Edit", "edit_menu"), items)

    def test_menubar_update_menu_item(self):
        """Test updating menu items in MenuBar."""
        with patch('pygame.sprite.LayeredDirty') as mock_layered_dirty:
            with patch('glitchygames.ui.FocusableSingletonBitmappySprite.__init__') as mock_super_init:
                mock_super_init.return_value = None
                
                groups = Mock()
                menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
                
                # Add a menu item
                menubar.add_menu_item("File", "file_menu")
                self.assertEqual(menubar.menu_items["File"], "file_menu")
                
                # Update the menu item
                menubar.update_menu_item("File", "updated_file_menu")
                self.assertEqual(menubar.menu_items["File"], "updated_file_menu")

    def test_menubar_set_menu_item(self):
        """Test setting menu items in MenuBar."""
        with patch('pygame.sprite.LayeredDirty') as mock_layered_dirty:
            with patch('glitchygames.ui.FocusableSingletonBitmappySprite.__init__') as mock_super_init:
                mock_super_init.return_value = None
                
                groups = Mock()
                menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
                
                # Set a menu item
                menubar.set_menu_item("File", "file_menu")
                self.assertEqual(menubar.menu_items["File"], "file_menu")
                
                # Set another menu item
                menubar.set_menu_item("Edit", "edit_menu")
                self.assertEqual(menubar.menu_items["Edit"], "edit_menu")

    def test_menubar_pop_menu_item(self):
        """Test popping menu items from MenuBar."""
        with patch('pygame.sprite.LayeredDirty') as mock_layered_dirty:
            with patch('glitchygames.ui.FocusableSingletonBitmappySprite.__init__') as mock_super_init:
                mock_super_init.return_value = None
                
                groups = Mock()
                menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
                
                # Add a menu item
                menubar.add_menu_item("File", "file_menu")
                self.assertEqual(len(menubar.menu_items), 1)
                
                # Pop the menu item
                item = menubar.pop_menu_item("File")
                self.assertEqual(item, "file_menu")
                self.assertEqual(len(menubar.menu_items), 0)
                
                # Test popping non-existent item
                item = menubar.pop_menu_item("NonExistent")
                self.assertIsNone(item)

    def test_menubar_copy_menu_items(self):
        """Test copying menu items from MenuBar."""
        with patch('pygame.sprite.LayeredDirty') as mock_layered_dirty:
            with patch('glitchygames.ui.FocusableSingletonBitmappySprite.__init__') as mock_super_init:
                mock_super_init.return_value = None
                
                groups = Mock()
                menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
                
                # Add menu items
                menubar.add_menu_item("File", "file_menu")
                menubar.add_menu_item("Edit", "edit_menu")
                
                # Copy menu items
                copied_items = menubar.copy_menu_items()
                self.assertEqual(copied_items, menubar.menu_items)
                self.assertIsNot(copied_items, menubar.menu_items)  # Should be a copy, not the same object

    def test_menubar_menu_items_property(self):
        """Test MenuBar menu_items property."""
        with patch('pygame.sprite.LayeredDirty') as mock_layered_dirty:
            with patch('glitchygames.ui.FocusableSingletonBitmappySprite.__init__') as mock_super_init:
                mock_super_init.return_value = None
                
                groups = Mock()
                menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
                
                # Test getting menu_items property
                self.assertEqual(menubar.menu_items, {})
                
                # Test setting menu_items property
                menubar.menu_items = {"File": "file_menu", "Edit": "edit_menu"}
                self.assertEqual(menubar.menu_items["File"], "file_menu")
                self.assertEqual(menubar.menu_items["Edit"], "edit_menu")

    def test_menubar_menu_offset_properties(self):
        """Test MenuBar menu offset properties."""
        with patch('pygame.sprite.LayeredDirty') as mock_layered_dirty:
            with patch('glitchygames.ui.FocusableSingletonBitmappySprite.__init__') as mock_super_init:
                mock_super_init.return_value = None
                
                groups = Mock()
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
        with patch('pygame.sprite.LayeredDirty') as mock_layered_dirty:
            with patch('glitchygames.ui.FocusableSingletonBitmappySprite.__init__') as mock_super_init:
                mock_super_init.return_value = None
                
                groups = Mock()
                menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
                
                # Test default background color
                self.assertEqual(menubar.background_color, (0, 255, 0))
                
                # Test setting background color
                menubar.background_color = (255, 0, 0)
                self.assertEqual(menubar.background_color, (255, 0, 0))

    def test_menubar_border_width_property(self):
        """Test MenuBar border_width property."""
        with patch('pygame.sprite.LayeredDirty') as mock_layered_dirty:
            with patch('glitchygames.ui.FocusableSingletonBitmappySprite.__init__') as mock_super_init:
                mock_super_init.return_value = None
                
                groups = Mock()
                menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
                
                # Test default border width
                self.assertEqual(menubar.border_width, 2)
                
                # Test setting border width
                menubar.border_width = 5
                self.assertEqual(menubar.border_width, 5)

    def test_menubar_has_focus_property(self):
        """Test MenuBar has_focus property."""
        with patch('pygame.sprite.LayeredDirty') as mock_layered_dirty:
            with patch('glitchygames.ui.FocusableSingletonBitmappySprite.__init__') as mock_super_init:
                mock_super_init.return_value = None
                
                groups = Mock()
                menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
                
                # Test default focus state
                self.assertFalse(menubar.has_focus)
                
                # Test setting focus state
                menubar.has_focus = True
                self.assertTrue(menubar.has_focus)

    def test_menubar_all_sprites_property(self):
        """Test MenuBar all_sprites property."""
        with patch('pygame.sprite.LayeredDirty') as mock_layered_dirty:
            with patch('glitchygames.ui.FocusableSingletonBitmappySprite.__init__') as mock_super_init:
                mock_super_init.return_value = None
                
                groups = Mock()
                menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
                
                # Test all_sprites property
                self.assertEqual(menubar.all_sprites, groups)

    def test_menubar_width_height_properties(self):
        """Test MenuBar width and height properties."""
        with patch('pygame.sprite.LayeredDirty') as mock_layered_dirty:
            with patch('glitchygames.ui.FocusableSingletonBitmappySprite.__init__') as mock_super_init:
                mock_super_init.return_value = None
                
                groups = Mock()
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
