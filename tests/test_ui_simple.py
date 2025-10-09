"""Simple test coverage for UI module - testing pure Python functionality."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestUISimpleCoverage(unittest.TestCase):
    """Test coverage for UI simple functionality."""

    def test_menubar_menu_item_methods(self):
        """Test MenuBar menu item management methods."""
        # Create a mock MenuBar instance without pygame dependencies
        with patch('glitchygames.ui.FocusableSingletonBitmappySprite.__init__'):
            with patch('pygame.sprite.LayeredDirty'):
                with patch('pygame.Surface'):
                    with patch('pygame.draw.rect'):
                        from glitchygames.ui import MenuBar
                        
                        # Create a mock rect
                        mock_rect = Mock()
                        mock_rect.x = 0
                        mock_rect.y = 0
                        mock_rect.width = 800
                        mock_rect.height = 50
                        
                        groups = Mock()
                        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
                        menubar.rect = mock_rect
                        
                        # Test adding menu items
                        menubar.add_menu_item("File", "file_menu")
                        self.assertIn("File", menubar.menu_items)
                        self.assertEqual(menubar.menu_items["File"], "file_menu")
                        
                        # Test getting menu items
                        item = menubar.get_menu_item("File")
                        self.assertEqual(item, "file_menu")
                        
                        # Test checking if menu item exists
                        self.assertTrue(menubar.has_menu_item("File"))
                        self.assertFalse(menubar.has_menu_item("NonExistent"))
                        
                        # Test getting menu item count
                        self.assertEqual(menubar.get_menu_item_count(), 1)
                        
                        # Test getting menu item names
                        names = menubar.get_menu_item_names()
                        self.assertIn("File", names)
                        self.assertEqual(len(names), 1)
                        
                        # Test getting menu item values
                        values = menubar.get_menu_item_values()
                        self.assertIn("file_menu", values)
                        self.assertEqual(len(values), 1)
                        
                        # Test getting menu item items
                        items = menubar.get_menu_item_items()
                        self.assertEqual(len(items), 1)
                        self.assertIn(("File", "file_menu"), items)
                        
                        # Test updating menu items
                        menubar.update_menu_item("File", "updated_file_menu")
                        self.assertEqual(menubar.menu_items["File"], "updated_file_menu")
                        
                        # Test setting menu items
                        menubar.set_menu_item("Edit", "edit_menu")
                        self.assertEqual(menubar.menu_items["Edit"], "edit_menu")
                        self.assertEqual(menubar.get_menu_item_count(), 2)
                        
                        # Test popping menu items
                        item = menubar.pop_menu_item("File")
                        self.assertEqual(item, "updated_file_menu")
                        self.assertEqual(menubar.get_menu_item_count(), 1)
                        
                        # Test removing menu items
                        menubar.remove_menu_item("Edit")
                        self.assertEqual(menubar.get_menu_item_count(), 0)
                        
                        # Test clearing menu items
                        menubar.add_menu_item("File", "file_menu")
                        menubar.add_menu_item("Edit", "edit_menu")
                        self.assertEqual(menubar.get_menu_item_count(), 2)
                        menubar.clear_menu_items()
                        self.assertEqual(menubar.get_menu_item_count(), 0)
                        
                        # Test copying menu items
                        menubar.add_menu_item("File", "file_menu")
                        menubar.add_menu_item("Edit", "edit_menu")
                        copied_items = menubar.copy_menu_items()
                        self.assertEqual(copied_items, menubar.menu_items)
                        self.assertIsNot(copied_items, menubar.menu_items)  # Should be a copy

    def test_menubar_properties(self):
        """Test MenuBar properties."""
        with patch('glitchygames.ui.FocusableSingletonBitmappySprite.__init__'):
            with patch('pygame.sprite.LayeredDirty'):
                with patch('pygame.Surface'):
                    with patch('pygame.draw.rect'):
                        from glitchygames.ui import MenuBar
                        
                        # Create a mock rect
                        mock_rect = Mock()
                        mock_rect.x = 0
                        mock_rect.y = 0
                        mock_rect.width = 800
                        mock_rect.height = 50
                        
                        groups = Mock()
                        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
                        menubar.rect = mock_rect
                        
                        # Test default properties
                        self.assertEqual(menubar.background_color, (0, 255, 0))
                        self.assertEqual(menubar.border_width, 2)
                        self.assertEqual(menubar.menu_offset_x, 2)
                        self.assertEqual(menubar.menu_offset_y, 2)
                        self.assertEqual(menubar.width, 800)
                        self.assertEqual(menubar.height, 50)
                        self.assertFalse(menubar.has_focus)
                        self.assertEqual(menubar.all_sprites, groups)
                        self.assertEqual(menubar.menu_items, {})
                        
                        # Test setting properties
                        menubar.background_color = (255, 0, 0)
                        self.assertEqual(menubar.background_color, (255, 0, 0))
                        
                        menubar.border_width = 5
                        self.assertEqual(menubar.border_width, 5)
                        
                        menubar.menu_offset_x = 10
                        menubar.menu_offset_y = 15
                        self.assertEqual(menubar.menu_offset_x, 10)
                        self.assertEqual(menubar.menu_offset_y, 15)
                        
                        menubar.width = 1000
                        menubar.height = 100
                        self.assertEqual(menubar.width, 1000)
                        self.assertEqual(menubar.height, 100)
                        
                        menubar.has_focus = True
                        self.assertTrue(menubar.has_focus)
                        
                        # Test setting menu_items property
                        menubar.menu_items = {"Test": "test_value"}
                        self.assertEqual(menubar.menu_items["Test"], "test_value")

    def test_menubar_edge_cases(self):
        """Test MenuBar edge cases."""
        with patch('glitchygames.ui.FocusableSingletonBitmappySprite.__init__'):
            with patch('pygame.sprite.LayeredDirty'):
                with patch('pygame.Surface'):
                    with patch('pygame.draw.rect'):
                        from glitchygames.ui import MenuBar
                        
                        # Create a mock rect
                        mock_rect = Mock()
                        mock_rect.x = 0
                        mock_rect.y = 0
                        mock_rect.width = 800
                        mock_rect.height = 50
                        
                        groups = Mock()
                        menubar = MenuBar(x=0, y=0, width=800, height=50, name="test_menubar", groups=groups)
                        menubar.rect = mock_rect
                        
                        # Test getting non-existent menu item
                        item = menubar.get_menu_item("NonExistent")
                        self.assertIsNone(item)
                        
                        # Test popping non-existent menu item
                        item = menubar.pop_menu_item("NonExistent")
                        self.assertIsNone(item)
                        
                        # Test removing non-existent menu item
                        menubar.remove_menu_item("NonExistent")  # Should not raise error
                        
                        # Test updating non-existent menu item
                        menubar.update_menu_item("NonExistent", "value")  # Should not raise error
                        
                        # Test with empty menu items
                        self.assertEqual(menubar.get_menu_item_count(), 0)
                        self.assertEqual(menubar.get_menu_item_names(), [])
                        self.assertEqual(menubar.get_menu_item_values(), [])
                        self.assertEqual(menubar.get_menu_item_items(), [])


if __name__ == '__main__':
    unittest.main()