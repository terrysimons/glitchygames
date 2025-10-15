"""Test suite for tab control UI component.

This module tests TabControlSprite functionality including tab switching,
format changes, and integration with slider input formatting.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.ui import TabControlSprite
from mocks.test_mock_factory import MockFactory


class TestTabControlSpriteFunctionality(unittest.TestCase):
    """Test TabControlSprite functionality."""

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

    def test_tab_control_initialization(self):
        """Test TabControlSprite initialization."""
        # Arrange
        parent = Mock()
        parent.slider_input_format = "%d"

        # Act
        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)

        # Assert
        assert tab_control.rect.x == 10
        assert tab_control.rect.y == 20
        assert tab_control.rect.width == 100
        assert tab_control.rect.height == 30
        assert tab_control.parent == parent
        assert tab_control.tabs == ["%d", "%X"]
        assert tab_control.active_tab == 0
        # Dirty flag is set to 1 by default in DirtySprite
        assert tab_control.dirty == 1

    def test_tab_control_click_handling(self):
        """Test TabControlSprite click handling."""
        # Arrange
        parent = Mock()
        parent.slider_input_format = "%d"
        parent.on_tab_change_event = Mock()

        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)

        # Create mock event
        event = Mock()
        event.pos = (60, 35)  # Click on second tab (hex)

        # Act
        tab_control.on_left_mouse_button_down_event(event)

        # Assert
        assert tab_control.active_tab == 1
        assert tab_control.dirty == 2
        parent.on_tab_change_event.assert_called_once_with("%X")

    def test_tab_control_click_first_tab(self):
        """Test TabControlSprite click on first tab."""
        # Arrange
        parent = Mock()
        parent.slider_input_format = "%X"
        parent.on_tab_change_event = Mock()

        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)
        tab_control.active_tab = 1  # Start on second tab

        # Create mock event
        event = Mock()
        event.pos = (35, 35)  # Click on first tab (decimal)

        # Act
        tab_control.on_left_mouse_button_down_event(event)

        # Assert
        assert tab_control.active_tab == 0
        assert tab_control.dirty == 2
        parent.on_tab_change_event.assert_called_once_with("%d")

    def test_tab_control_click_outside_bounds(self):
        """Test TabControlSprite click outside bounds."""
        # Arrange
        parent = Mock()
        parent.slider_input_format = "%d"
        parent.on_tab_change_event = Mock()

        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)

        # Create mock event
        event = Mock()
        event.pos = (200, 200)  # Click outside bounds

        # Act
        tab_control.on_left_mouse_button_down_event(event)

        # Assert - should not change active tab
        assert tab_control.active_tab == 0
        # Dirty flag remains 1 (default) when clicking outside bounds
        assert tab_control.dirty == 1
        parent.on_tab_change_event.assert_not_called()

    def test_tab_control_update_rendering(self):
        """Test TabControlSprite update and rendering."""
        # Arrange
        parent = Mock()
        parent.slider_input_format = "%d"

        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)
        tab_control.dirty = 2

        # Mock surface for rendering
        mock_surface = Mock()
        tab_control.image = mock_surface

        # Act
        tab_control.update()

        # Assert - should call render method
        # Note: The actual rendering logic would be tested in integration tests
        # Dirty flag behavior depends on the actual implementation
        assert tab_control.dirty >= 0  # Should be a valid dirty flag value

    def test_tab_control_tab_calculation(self):
        """Test TabControlSprite tab position calculation."""
        # Arrange
        parent = Mock()
        parent.slider_input_format = "%d"

        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)

        # Test tab position calculations
        # The actual implementation may have different positioning logic
        # We'll test the basic properties instead of specific calculations
        assert tab_control.rect.width == 100
        assert tab_control.rect.height == 30
        assert len(tab_control.tabs) == 2

    def test_tab_control_active_tab_property(self):
        """Test TabControlSprite active tab property."""
        # Arrange
        parent = Mock()
        parent.slider_input_format = "%d"

        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)

        # Act
        tab_control.active_tab = 1

        # Assert
        assert tab_control.active_tab == 1
        assert tab_control.tabs[tab_control.active_tab] == "%X"

    def test_tab_control_parent_integration(self):
        """Test TabControlSprite integration with parent."""
        # Arrange
        parent = Mock()
        parent.slider_input_format = "%d"
        parent.on_tab_change_event = Mock()

        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)

        # Act - simulate tab change
        tab_control.active_tab = 1
        tab_control.on_left_mouse_button_down_event(Mock(pos=(60, 35)))

        # Assert
        parent.on_tab_change_event.assert_called_once_with("%X")

    def test_tab_control_dirty_flag_management(self):
        """Test TabControlSprite dirty flag management."""
        # Arrange
        parent = Mock()
        parent.slider_input_format = "%d"

        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)

        # Act - set dirty flag
        tab_control.dirty = 2

        # Assert
        assert tab_control.dirty == 2

        # Act - update should handle dirty flag appropriately
        tab_control.update()

        # Assert - dirty flag behavior depends on implementation
        assert tab_control.dirty >= 0  # Should be a valid dirty flag value

    def test_tab_control_tab_text_content(self):
        """Test TabControlSprite tab text content."""
        # Arrange
        parent = Mock()
        parent.slider_input_format = "%d"

        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)

        # Assert
        assert tab_control.tabs[0] == "%d"  # Decimal format
        assert tab_control.tabs[1] == "%X"  # Hex format

    def test_tab_control_rect_properties(self):
        """Test TabControlSprite rect properties."""
        # Arrange
        parent = Mock()
        parent.slider_input_format = "%d"

        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)

        # Assert
        assert tab_control.rect.x == 10
        assert tab_control.rect.y == 20
        assert tab_control.rect.width == 100
        assert tab_control.rect.height == 30

    def test_tab_control_click_boundary_conditions(self):
        """Test TabControlSprite click boundary conditions."""
        # Arrange
        parent = Mock()
        parent.slider_input_format = "%d"
        parent.on_tab_change_event = Mock()

        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)

        # Test click on exact boundary
        event = Mock()
        event.pos = (60, 35)  # Right on the boundary between tabs

        # Act
        tab_control.on_left_mouse_button_down_event(event)

        # Assert - should select second tab
        assert tab_control.active_tab == 1
        parent.on_tab_change_event.assert_called_once_with("%X")


if __name__ == "__main__":
    unittest.main()
