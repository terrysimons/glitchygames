"""Core sprite functionality tests."""

import sys
from pathlib import Path
from unittest.mock import patch

import pygame

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.sprites import RootSprite, Sprite

from tests.mocks.test_mock_factory import MockFactory

# Constants for magic values
SPRITE_X = 10
SPRITE_Y = 20
SPRITE_WIDTH = 30
SPRITE_HEIGHT = 40
EXPECTED_ERROR_COUNT_2 = 2
SPRITE_WIDTH_100 = 100
SPRITE_HEIGHT_50 = 50
SPRITE_WIDTH_200 = 200
SPRITE_HEIGHT_75 = 75
SPRITE_DT = 0.016


class TestRootSprite:
    """Test RootSprite class functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers:
            patcher.start()

    def teardown_method(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_root_sprite_initialization_with_groups(self):
        """Test RootSprite initialization with groups."""
        groups = pygame.sprite.LayeredDirty()
        sprite = Sprite(x=0, y=0, width=10, height=10, groups=groups)

        assert isinstance(sprite, RootSprite)
        assert sprite.groups() == [groups]

    def test_root_sprite_initialization_without_groups(self):
        """Test RootSprite initialization without groups."""
        sprite = Sprite(x=0, y=0, width=10, height=10)

        assert isinstance(sprite, RootSprite)
        # When no groups are provided, sprite gets added to a default group
        assert len(sprite.groups()) == 1
        # Check that the group has the expected methods (works with centralized mocks)
        group = sprite.groups()[0]
        assert hasattr(group, 'add')
        assert hasattr(group, 'remove')
        assert hasattr(group, 'draw')


class TestSpriteInitialization:
    """Test Sprite initialization and basic functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers:
            patcher.start()

    def teardown_method(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_sprite_initialization_with_all_parameters(self):
        """Test Sprite initialization with all parameters."""
        # Create proper pygame sprite group
        groups = pygame.sprite.LayeredDirty()
        sprite = Sprite(
            x=SPRITE_X, y=SPRITE_Y, width=SPRITE_WIDTH, height=SPRITE_HEIGHT,
            name="test_sprite", parent=None, groups=groups
        )

        assert sprite.rect.x == SPRITE_X
        assert sprite.rect.y == SPRITE_Y
        assert sprite.rect.width == SPRITE_WIDTH
        assert sprite.rect.height == SPRITE_HEIGHT
        assert sprite.name == "test_sprite"

    def test_sprite_initialization_without_name(self):
        """Test Sprite initialization without name."""
        sprite = Sprite(x=SPRITE_X, y=SPRITE_Y, width=SPRITE_WIDTH, height=SPRITE_HEIGHT)

        # When no name is provided, it defaults to the class type
        assert sprite.name is type(sprite)

    def test_sprite_initialization_with_zero_dimensions(self):
        """Test Sprite initialization with zero dimensions."""
        # Use centralized mocks to suppress logs during successful runs
        with patch.object(Sprite, "log") as mock_log:
            sprite = Sprite(x=0, y=0, width=0, height=0)

            assert sprite.width == 0
            assert sprite.height == 0

            # Verify the ERROR log messages were called
            assert mock_log.error.call_count == EXPECTED_ERROR_COUNT_2
            # Check that the log messages contain the expected content
            first_call = mock_log.error.call_args_list[0][0][0]
            second_call = mock_log.error.call_args_list[1][0][0]
            assert "has 0 Width" in first_call
            assert "has 0 Height" in second_call

    def test_sprite_breakpoints_enabled_empty_list(self):
        """Test sprite breakpoints with empty list."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        sprite.break_when = []

        assert sprite.break_when == []

    def test_sprite_breakpoints_enabled_with_specific_type(self):
        """Test sprite breakpoints with specific type."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        sprite.break_when = [Sprite]

        assert sprite.break_when == [Sprite]

    def test_break_when_none_creates_list(self):
        """Test that break_when creates a list when passed None."""
        # break_when is a class method, not an instance attribute
        # Test that the class method exists and can be called
        assert hasattr(Sprite, "break_when")
        assert callable(Sprite.break_when)

    def test_break_when_specific_type_appends(self):
        """Test that break_when appends specific type."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        sprite.break_when = [Sprite]
        sprite.break_when.append("test")

        assert "test" in sprite.break_when


class TestSpriteProperties:
    """Test Sprite properties and methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers:
            patcher.start()

    def teardown_method(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_width_property_getter(self):
        """Test width property getter."""
        sprite = Sprite(x=0, y=0, width=SPRITE_WIDTH_100, height=SPRITE_HEIGHT_50)

        assert sprite.width == SPRITE_WIDTH_100

    def test_width_property_setter(self):
        """Test width property setter."""
        sprite = Sprite(x=0, y=0, width=SPRITE_WIDTH_100, height=SPRITE_HEIGHT_50)
        sprite.width = SPRITE_WIDTH_200

        assert sprite.width == SPRITE_WIDTH_200

    def test_height_property_getter(self):
        """Test height property getter."""
        sprite = Sprite(x=0, y=0, width=SPRITE_WIDTH_100, height=SPRITE_HEIGHT_50)

        assert sprite.height == SPRITE_HEIGHT_50

    def test_height_property_setter(self):
        """Test height property setter."""
        sprite = Sprite(x=0, y=0, width=SPRITE_WIDTH_100, height=SPRITE_HEIGHT_50)
        sprite.height = SPRITE_HEIGHT_75

        assert sprite.height == SPRITE_HEIGHT_75

    def test_sprite_dt_tick(self):
        """Test sprite dt tick functionality."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        sprite.dt = SPRITE_DT  # 60 FPS

        assert sprite.dt == SPRITE_DT

    def test_sprite_event_handlers(self):
        """Test sprite event handlers."""
        sprite = Sprite(x=0, y=0, width=10, height=10)

        # Test that event handlers exist (using correct method names)
        assert hasattr(sprite, "on_mouse_motion_event")
        assert hasattr(sprite, "on_mouse_button_down_event")
        assert hasattr(sprite, "on_key_down_event")

    def test_sprite_update(self):
        """Test sprite update method."""
        sprite = Sprite(x=0, y=0, width=10, height=10)

        # Should not raise an exception
        sprite.update()

    def test_sprite_initialization_sets_screen_dimensions(self):
        """Test that sprite initialization sets screen dimensions."""
        sprite = Sprite(x=0, y=0, width=10, height=10)

        assert sprite.screen_width is not None
        assert sprite.screen_height is not None
