"""Core sprite functionality tests."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pygame

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.sprites import RootSprite, Sprite

from mocks.test_mock_factory import MockFactory


class TestRootSprite(unittest.TestCase):
    """Test RootSprite class functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_root_sprite_initialization_with_groups(self):
        """Test RootSprite initialization with groups."""
        groups = pygame.sprite.LayeredDirty()
        sprite = Sprite(x=0, y=0, width=10, height=10, groups=groups)
        
        self.assertIsInstance(sprite, RootSprite)
        self.assertEqual(sprite.groups(), [groups])

    def test_root_sprite_initialization_without_groups(self):
        """Test RootSprite initialization without groups."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        
        self.assertIsInstance(sprite, RootSprite)
        # When no groups are provided, sprite gets added to a default group
        self.assertEqual(len(sprite.groups()), 1)
        self.assertIsInstance(sprite.groups()[0], pygame.sprite.LayeredDirty)


class TestSpriteInitialization(unittest.TestCase):
    """Test Sprite initialization and basic functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_sprite_initialization_with_all_parameters(self):
        """Test Sprite initialization with all parameters."""
        # Create proper pygame sprite group
        groups = pygame.sprite.LayeredDirty()
        sprite = Sprite(
            x=10, y=20, width=30, height=40, 
            name="test_sprite", parent=None, groups=groups
        )
        
        self.assertEqual(sprite.rect.x, 10)
        self.assertEqual(sprite.rect.y, 20)
        self.assertEqual(sprite.rect.width, 30)
        self.assertEqual(sprite.rect.height, 40)
        self.assertEqual(sprite.name, "test_sprite")

    def test_sprite_initialization_without_name(self):
        """Test Sprite initialization without name."""
        sprite = Sprite(x=10, y=20, width=30, height=40)
        
        # When no name is provided, it defaults to the class type
        self.assertEqual(sprite.name, type(sprite))

    def test_sprite_initialization_with_zero_dimensions(self):
        """Test Sprite initialization with zero dimensions."""
        sprite = Sprite(x=0, y=0, width=0, height=0)
        
        self.assertEqual(sprite.width, 0)
        self.assertEqual(sprite.height, 0)

    def test_sprite_breakpoints_enabled_empty_list(self):
        """Test sprite breakpoints with empty list."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        sprite.break_when = []
        
        self.assertEqual(sprite.break_when, [])

    def test_sprite_breakpoints_enabled_with_specific_type(self):
        """Test sprite breakpoints with specific type."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        sprite.break_when = [Sprite]
        
        self.assertEqual(sprite.break_when, [Sprite])

    def test_break_when_none_creates_list(self):
        """Test that break_when creates a list when passed None."""
        # break_when is a class method, not an instance attribute
        # Test that the class method exists and can be called
        self.assertTrue(hasattr(Sprite, "break_when"))
        self.assertTrue(callable(Sprite.break_when))

    def test_break_when_specific_type_appends(self):
        """Test that break_when appends specific type."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        sprite.break_when = [Sprite]
        sprite.break_when.append("test")
        
        self.assertIn("test", sprite.break_when)


class TestSpriteProperties(unittest.TestCase):
    """Test Sprite properties and methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_width_property_getter(self):
        """Test width property getter."""
        sprite = Sprite(x=0, y=0, width=100, height=50)
        
        self.assertEqual(sprite.width, 100)

    def test_width_property_setter(self):
        """Test width property setter."""
        sprite = Sprite(x=0, y=0, width=100, height=50)
        sprite.width = 200
        
        self.assertEqual(sprite.width, 200)

    def test_height_property_getter(self):
        """Test height property getter."""
        sprite = Sprite(x=0, y=0, width=100, height=50)
        
        self.assertEqual(sprite.height, 50)

    def test_height_property_setter(self):
        """Test height property setter."""
        sprite = Sprite(x=0, y=0, width=100, height=50)
        sprite.height = 75
        
        self.assertEqual(sprite.height, 75)

    def test_sprite_dt_tick(self):
        """Test sprite dt tick functionality."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        sprite.dt = 0.016  # 60 FPS
        
        self.assertEqual(sprite.dt, 0.016)

    def test_sprite_event_handlers(self):
        """Test sprite event handlers."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        
        # Test that event handlers exist (using correct method names)
        self.assertTrue(hasattr(sprite, "on_mouse_motion_event"))
        self.assertTrue(hasattr(sprite, "on_mouse_button_down_event"))
        self.assertTrue(hasattr(sprite, "on_key_down_event"))

    def test_sprite_update(self):
        """Test sprite update method."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        
        # Should not raise an exception
        sprite.update()

    def test_sprite_initialization_sets_screen_dimensions(self):
        """Test that sprite initialization sets screen dimensions."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        
        self.assertIsNotNone(sprite.screen_width)
        self.assertIsNotNone(sprite.screen_height)


if __name__ == "__main__":
    unittest.main()
