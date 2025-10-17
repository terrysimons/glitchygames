"""Test suite for bitmappy film strip functionality.

This module tests the film strip add/delete functionality, scroll behavior,
and integration with the bitmap editor scene.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.tools.bitmappy import BitmapEditorScene
from glitchygames.tools.film_strip import FilmStripDeleteTab, FilmStripTab, FilmStripWidget

from tests.mocks import MockFactory

# Test constants to avoid magic values
TEST_SIZE_10 = 10
TEST_SIZE_20 = 20
TEST_SIZE_40 = 40
TEST_SIZE_2 = 2
TEST_SIZE_3 = 3


class TestFilmStripAddDeleteFunctionality(unittest.TestCase):
    """Test film strip add/delete functionality."""

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

    def test_film_strip_tab_initialization(self):
        """Test FilmStripTab initialization."""
        # Act
        tab = FilmStripTab(x=10, y=20, width=40, height=10)

        # Assert
        assert tab.rect.x == TEST_SIZE_10
        assert tab.rect.y == TEST_SIZE_20
        assert tab.rect.width == TEST_SIZE_40
        assert tab.rect.height == TEST_SIZE_10
        assert tab.insertion_type == "after"
        assert tab.target_frame_index == 0
        assert not tab.is_clicked
        assert not tab.is_hovered

    def test_film_strip_delete_tab_initialization(self):
        """Test FilmStripDeleteTab initialization."""
        # Act
        delete_tab = FilmStripDeleteTab(x=10, y=20, width=40, height=10)

        # Assert
        assert delete_tab.rect.x == TEST_SIZE_10
        assert delete_tab.rect.y == TEST_SIZE_20
        assert delete_tab.rect.width == TEST_SIZE_40
        assert delete_tab.rect.height == TEST_SIZE_10
        assert delete_tab.insertion_type == "delete"
        assert delete_tab.target_frame_index == 0
        assert not delete_tab.is_clicked
        assert not delete_tab.is_hovered

    def test_film_strip_tab_click_handling(self):
        """Test FilmStripTab click handling."""
        # Arrange
        tab = FilmStripTab(x=10, y=20, width=40, height=10)
        click_pos = (30, 25)  # Inside the tab

        # Act
        result = tab.handle_click(click_pos)

        # Assert
        assert result is True
        assert tab.is_clicked is True

    def test_film_strip_delete_tab_click_handling(self):
        """Test FilmStripDeleteTab click handling."""
        # Arrange
        delete_tab = FilmStripDeleteTab(x=10, y=20, width=40, height=10)
        click_pos = (30, 25)  # Inside the tab

        # Act
        result = delete_tab.handle_click(click_pos)

        # Assert
        assert result is True
        assert delete_tab.is_clicked is True

    def test_film_strip_tab_hover_handling(self):
        """Test FilmStripTab hover handling."""
        # Arrange
        tab = FilmStripTab(x=10, y=20, width=40, height=10)
        hover_pos = (30, 25)  # Inside the tab

        # Act
        tab.handle_hover(hover_pos)

        # Assert
        assert tab.is_hovered is True

    def test_film_strip_tab_reset_click_state(self):
        """Test FilmStripTab click state reset."""
        # Arrange
        tab = FilmStripTab(x=10, y=20, width=40, height=10)
        tab.is_clicked = True

        # Act
        tab.reset_click_state()

        # Assert
        assert tab.is_clicked is False

    def test_film_strip_tab_set_insertion_type(self):
        """Test FilmStripTab insertion type setting."""
        # Arrange
        tab = FilmStripTab(x=10, y=20, width=40, height=10)

        # Act
        tab.set_insertion_type("after", 2)

        # Assert
        assert tab.insertion_type == "after"
        assert tab.target_frame_index == TEST_SIZE_2

    def test_film_strip_delete_tab_set_insertion_type(self):
        """Test FilmStripDeleteTab insertion type setting."""
        # Arrange
        delete_tab = FilmStripDeleteTab(x=10, y=20, width=40, height=10)

        # Act
        delete_tab.set_insertion_type("delete", 0)

        # Assert
        assert delete_tab.insertion_type == "delete"
        assert delete_tab.target_frame_index == 0


class TestBitmapEditorFilmStripIntegration(unittest.TestCase):
    """Test bitmap editor film strip integration."""

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

    def test_add_new_animation_creates_strip(self):
        """Test that adding new animation creates a new film strip."""
        with patch("glitchygames.tools.bitmappy.BitmapEditorScene._setup_canvas") as _:
            # Arrange
            options = {}
            scene = BitmapEditorScene(options)

            # Use centralized mocks
            scene.canvas = MockFactory().create_canvas_mock()
            scene.canvas.animated_sprite = Mock()
            scene.canvas.animated_sprite._animations = {"strip_1": []}
            scene._on_sprite_loaded = Mock()
            scene._update_film_strip_visibility = Mock()
            scene._update_scroll_arrows = Mock()
            scene.max_visible_strips = 2

            # Act
            scene._add_new_animation()

            # Assert
            assert len(scene.canvas.animated_sprite._animations) == TEST_SIZE_2
            assert "strip_2" in scene.canvas.animated_sprite._animations
            scene._on_sprite_loaded.assert_called_once()

    def test_add_new_animation_with_insert_after_index(self):
        """Test adding new animation at specific index."""
        with patch("glitchygames.tools.bitmappy.BitmapEditorScene._setup_canvas") as _:
            # Arrange
            options = {}
            scene = BitmapEditorScene(options)
            # Use centralized mocks
            scene.canvas = MockFactory().create_canvas_mock()
            scene.canvas.animated_sprite = Mock()
            scene.canvas.animated_sprite._animations = {"strip_1": [], "strip_2": []}
            scene._on_sprite_loaded = Mock()
            scene._update_film_strip_visibility = Mock()
            scene._update_scroll_arrows = Mock()
            scene.max_visible_strips = 2

            # Act - insert after index 0 (between strip_1 and strip_2)
            scene._add_new_animation(insert_after_index=0)

            # Assert
            animations = list(scene.canvas.animated_sprite._animations.keys())
            assert len(animations) == TEST_SIZE_3
            assert animations[0] == "strip_1"
            assert animations[1] == "strip_3"  # New strip inserted
            assert animations[2] == "strip_2"

    def test_delete_animation_removes_strip(self):
        """Test that deleting animation removes the film strip."""
        with patch("glitchygames.tools.bitmappy.BitmapEditorScene._setup_canvas") as _:
            # Arrange
            options = {}
            scene = BitmapEditorScene(options)
            scene.canvas = Mock()
            scene.canvas.animated_sprite = Mock()
            scene.canvas.animated_sprite._animations = {"strip_1": [], "strip_2": []}
            scene._on_sprite_loaded = Mock()
            scene._update_film_strip_visibility = Mock()
            scene._update_scroll_arrows = Mock()
            scene.canvas.show_frame = Mock()

            # Act
            scene._delete_animation("strip_1")

            # Assert
            assert "strip_1" not in scene.canvas.animated_sprite._animations
            assert len(scene.canvas.animated_sprite._animations) == 1
            scene._on_sprite_loaded.assert_called_once()

    def test_delete_animation_prevents_last_strip_deletion(self):
        """Test that deleting the last remaining strip is prevented."""
        with patch("glitchygames.tools.bitmappy.BitmapEditorScene._setup_canvas") as _:
            # Arrange
            options = {}
            scene = BitmapEditorScene(options)
            # Use centralized mocks
            scene.canvas = MockFactory().create_canvas_mock()
            scene.canvas.animated_sprite = Mock()
            scene.canvas.animated_sprite._animations = {"strip_1": []}
            scene._on_sprite_loaded = Mock()

            # Act
            scene._delete_animation("strip_1")

            # Assert - should not delete the last strip
            assert "strip_1" in scene.canvas.animated_sprite._animations
            assert len(scene.canvas.animated_sprite._animations) == 1
            scene._on_sprite_loaded.assert_not_called()

    def test_delete_animation_scroll_offset_calculation(self):
        """Test that deleting animation sets correct scroll offset."""
        with patch("glitchygames.tools.bitmappy.BitmapEditorScene._setup_canvas") as _:
            # Arrange
            options = {}
            scene = BitmapEditorScene(options)
            scene.canvas = Mock()
            scene.canvas.animated_sprite = Mock()
            scene.canvas.animated_sprite._animations = {"strip_1": [], "strip_2": [], "strip_3": []}
            scene._on_sprite_loaded = Mock()
            scene._update_film_strip_visibility = Mock()
            scene._update_scroll_arrows = Mock()
            scene.canvas.show_frame = Mock()

            # Act - delete middle strip (index 1)
            scene._delete_animation("strip_2")

            # Assert - should show previous 2 strips
            assert scene.film_strip_scroll_offset == 0  # max(0, 1-1) = 0

    def test_delete_animation_scroll_offset_last_strip(self):
        """Test that deleting last strip shows previous 2 strips."""
        with patch("glitchygames.tools.bitmappy.BitmapEditorScene._setup_canvas") as _:
            # Arrange
            options = {}
            scene = BitmapEditorScene(options)
            scene.canvas = Mock()
            scene.canvas.animated_sprite = Mock()
            scene.canvas.animated_sprite._animations = {"strip_1": [], "strip_2": [], "strip_3": []}
            scene._on_sprite_loaded = Mock()
            scene._update_film_strip_visibility = Mock()
            scene._update_scroll_arrows = Mock()
            scene.canvas.show_frame = Mock()

            # Act - delete last strip (index 2)
            scene._delete_animation("strip_3")

            # Assert - should show previous 2 strips
            assert scene.film_strip_scroll_offset == 0  # max(0, 2-2) = 0

    def test_delete_animation_scroll_offset_many_strips(self):
        """Test that deleting strip with many strips shows appropriate offset."""
        with patch("glitchygames.tools.bitmappy.BitmapEditorScene._setup_canvas") as _:
            # Arrange
            options = {}
            scene = BitmapEditorScene(options)
            scene.canvas = Mock()
            scene.canvas.animated_sprite = Mock()
            scene.canvas.animated_sprite._animations = {
                "strip_1": [], "strip_2": [], "strip_3": [], "strip_4": [], "strip_5": []
            }
            scene._on_sprite_loaded = Mock()
            scene._update_film_strip_visibility = Mock()
            scene._update_scroll_arrows = Mock()
            scene.canvas.show_frame = Mock()

            # Act - delete strip at index 2
            scene._delete_animation("strip_3")

            # Assert - should show current and one more
            assert scene.film_strip_scroll_offset == 1  # max(0, 2-1) = 1

    def test_delete_animation_switches_to_first_remaining(self):
        """Test that deleting animation switches to first remaining animation."""
        with patch("glitchygames.tools.bitmappy.BitmapEditorScene._setup_canvas") as _:
            # Arrange
            options = {}
            scene = BitmapEditorScene(options)
            scene.canvas = Mock()
            scene.canvas.animated_sprite = Mock()
            scene.canvas.animated_sprite._animations = {"strip_1": [], "strip_2": [], "strip_3": []}
            scene._on_sprite_loaded = Mock()
            scene._update_film_strip_visibility = Mock()
            scene._update_scroll_arrows = Mock()
            scene.canvas.show_frame = Mock()

            # Act
            scene._delete_animation("strip_2")

            # Assert - should switch to first remaining animation
            scene.canvas.show_frame.assert_called_once_with("strip_1", 0)
            assert scene.selected_animation == "strip_1"
            assert scene.selected_frame == 0


class TestFilmStripWidgetIntegration(unittest.TestCase):
    """Test film strip widget integration with tabs."""

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

    def test_film_strip_widget_creates_tabs(self):
        """Test that film strip widget creates appropriate tabs."""
        # Arrange
        widget = FilmStripWidget(x=0, y=0, width=100, height=50)
        widget.current_animation = "test_animation"
        widget.parent_scene = Mock()
        widget.parent_scene._add_new_animation = Mock()
        widget.parent_scene._delete_animation = Mock()
        # Set up canvas for parent_scene
        widget.parent_scene.canvas = Mock()
        widget.parent_scene.canvas.animated_sprite = Mock()
        widget.parent_scene.canvas.animated_sprite._animations = {"test_animation": []}

        # Create mock animated sprite with frames
        animated_sprite = Mock()
        animated_sprite._animations = {"test_animation": [Mock(), Mock()]}
        animated_sprite._animation_order = ["test_animation"]  # Add missing attribute
        widget.set_animated_sprite(animated_sprite)

        # Act
        widget._create_film_tabs()

        # Assert - should create add, delete, and frame tabs
        # Should have: 1 delete tab + 1 add tab + 2 frame tabs = 4 tabs
        assert len(widget.film_tabs) >= TEST_SIZE_2  # At least add and delete tabs
        assert any(isinstance(tab, FilmStripTab) for tab in widget.film_tabs)
        assert any(isinstance(tab, FilmStripDeleteTab) for tab in widget.film_tabs)

    def test_film_strip_widget_handles_tab_clicks(self):
        """Test that film strip widget handles tab clicks correctly."""
        # Arrange
        widget = FilmStripWidget(x=0, y=0, width=100, height=50)
        widget.current_animation = "test_animation"
        widget.parent_scene = Mock()
        widget.parent_scene._add_new_animation = Mock()
        widget.parent_scene._delete_animation = Mock()
        # Set up canvas for parent_scene
        widget.parent_scene.canvas = Mock()
        widget.parent_scene.canvas.animated_sprite = Mock()
        widget.parent_scene.canvas.animated_sprite._animations = {"test_animation": []}

        # Create mock animated sprite with frames
        animated_sprite = Mock()
        animated_sprite._animations = {"test_animation": [Mock(), Mock()]}
        animated_sprite._animation_order = ["test_animation"]  # Add missing attribute
        widget.set_animated_sprite(animated_sprite)

        # Create tabs
        widget._create_film_tabs()

        # Find the add tab (FilmStripTab)
        add_tab = next(tab for tab in widget.film_tabs if isinstance(tab, FilmStripTab))
        add_tab.rect = Mock()
        add_tab.rect.collidepoint.return_value = True

        # Act - click on add tab
        result = widget._handle_tab_click((50, 25))

        # Assert
        assert result is True
        widget.parent_scene._add_new_animation.assert_called_once()

    def test_film_strip_widget_handles_delete_tab_clicks(self):
        """Test that film strip widget handles delete tab clicks correctly."""
        # Arrange
        widget = FilmStripWidget(x=0, y=0, width=100, height=50)
        widget.current_animation = "test_animation"
        widget.parent_scene = Mock()
        widget.parent_scene._add_new_animation = Mock()
        widget.parent_scene._delete_animation = Mock()
        # Set up canvas for parent_scene
        widget.parent_scene.canvas = Mock()
        widget.parent_scene.canvas.animated_sprite = Mock()
        widget.parent_scene.canvas.animated_sprite._animations = {
            "test_animation": [],
            "other_animation": []
        }

        # Create mock animated sprite with frames
        animated_sprite = Mock()
        animated_sprite._animations = {"test_animation": [Mock(), Mock()]}
        animated_sprite._animation_order = ["test_animation"]  # Add missing attribute
        widget.set_animated_sprite(animated_sprite)

        # Create tabs
        widget._create_film_tabs()

        # Find the delete tab (FilmStripDeleteTab)
        delete_tab = next(tab for tab in widget.film_tabs if isinstance(tab, FilmStripDeleteTab))
        delete_tab.rect = Mock()
        delete_tab.rect.collidepoint.return_value = True

        # Act - click on delete tab
        result = widget._handle_tab_click((50, 5))

        # Assert
        assert result is True
        widget.parent_scene._delete_animation.assert_called_once_with("test_animation")

    def test_film_strip_widget_no_tabs_without_frames(self):
        """Test that film strip widget doesn't create tabs without frames."""
        # Arrange
        widget = FilmStripWidget(x=0, y=0, width=100, height=50)
        widget.current_animation = "test_animation"
        widget.parent_scene = Mock()

        # Create mock animated sprite without frames
        animated_sprite = Mock()
        animated_sprite._animations = {"test_animation": []}
        animated_sprite._animation_order = ["test_animation"]  # Add missing attribute
        widget.set_animated_sprite(animated_sprite)

        # Act
        widget._create_film_tabs()

        # Assert - should not create tabs without frames
        assert len(widget.film_tabs) == 0


if __name__ == "__main__":
    unittest.main()
