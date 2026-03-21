"""Test suite for Scrollbar interaction coverage.

This module tests the Scrollbar class including mouse down handling on
thumb and track, mouse up clearing drag state, mouse motion with drag
and hover, and scroll position calculations.
"""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.ui import Scrollbar
from tests.mocks.test_mock_factory import MockFactory

# Test constants
SCROLLBAR_X = 290
SCROLLBAR_Y = 2
SCROLLBAR_WIDTH = 8
SCROLLBAR_HEIGHT = 196
TOTAL_ITEMS = 50
VISIBLE_ITEMS = 10


def _create_scrollbar(total_items=TOTAL_ITEMS, visible_items=VISIBLE_ITEMS, scroll_offset=0):
    """Create a Scrollbar with standard test configuration.

    Returns:
        A Scrollbar instance configured for testing.
    """
    return Scrollbar(
        x=SCROLLBAR_X,
        y=SCROLLBAR_Y,
        width=SCROLLBAR_WIDTH,
        height=SCROLLBAR_HEIGHT,
        total_items=total_items,
        visible_items=visible_items,
        scroll_offset=scroll_offset,
    )


class TestScrollbarProperties:
    """Test Scrollbar computed properties."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_max_scroll_calculation(self):
        """Test max_scroll is total_items minus visible_items."""
        scrollbar = _create_scrollbar(total_items=50, visible_items=10)
        assert scrollbar.max_scroll == 40

    def test_max_scroll_when_fewer_items_than_visible(self):
        """Test max_scroll is 0 when total items <= visible items."""
        scrollbar = _create_scrollbar(total_items=5, visible_items=10)
        assert scrollbar.max_scroll == 0

    def test_is_visible_when_scrollable(self):
        """Test is_visible is True when total items > visible items."""
        scrollbar = _create_scrollbar(total_items=50, visible_items=10)
        assert scrollbar.is_visible is True

    def test_is_visible_when_not_scrollable(self):
        """Test is_visible is False when total items <= visible items."""
        scrollbar = _create_scrollbar(total_items=5, visible_items=10)
        assert scrollbar.is_visible is False

    def test_thumb_height_proportional_to_content(self):
        """Test thumb height is proportional to visible/total ratio."""
        scrollbar = _create_scrollbar(total_items=50, visible_items=10)
        expected_ratio = 10 / 50
        expected_height = max(20, int(expected_ratio * SCROLLBAR_HEIGHT))
        assert scrollbar.thumb_height == expected_height

    def test_thumb_height_minimum_size(self):
        """Test thumb height never goes below 20 pixels."""
        scrollbar = _create_scrollbar(total_items=1000, visible_items=1)
        assert scrollbar.thumb_height >= 20

    def test_thumb_height_when_no_items(self):
        """Test thumb height equals scrollbar height when no items."""
        scrollbar = _create_scrollbar(total_items=0, visible_items=10)
        assert scrollbar.thumb_height == SCROLLBAR_HEIGHT

    def test_thumb_y_at_top(self):
        """Test thumb Y position at scroll offset 0 is at the top."""
        scrollbar = _create_scrollbar(scroll_offset=0)
        assert scrollbar.thumb_y == SCROLLBAR_Y

    def test_thumb_y_at_bottom(self):
        """Test thumb Y position at max scroll is at the bottom."""
        scrollbar = _create_scrollbar(total_items=50, visible_items=10, scroll_offset=40)
        available_space = SCROLLBAR_HEIGHT - scrollbar.thumb_height
        expected_y = SCROLLBAR_Y + available_space
        assert scrollbar.thumb_y == expected_y

    def test_thumb_y_when_not_scrollable(self):
        """Test thumb Y returns scrollbar Y when max_scroll is 0."""
        scrollbar = _create_scrollbar(total_items=5, visible_items=10)
        assert scrollbar.thumb_y == SCROLLBAR_Y

    def test_get_thumb_rect(self):
        """Test get_thumb_rect returns correct Rect."""
        scrollbar = _create_scrollbar()
        thumb_rect = scrollbar.get_thumb_rect()
        assert isinstance(thumb_rect, pygame.Rect)
        assert thumb_rect.x == SCROLLBAR_X
        assert thumb_rect.y == scrollbar.thumb_y
        assert thumb_rect.width == SCROLLBAR_WIDTH
        assert thumb_rect.height == scrollbar.thumb_height


class TestScrollbarHandleMouseDown:
    """Test Scrollbar.handle_mouse_down()."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_mouse_down_on_thumb_starts_drag(self):
        """Test clicking on thumb starts drag mode."""
        scrollbar = _create_scrollbar()
        thumb_rect = scrollbar.get_thumb_rect()
        click_pos = (thumb_rect.centerx, thumb_rect.centery)

        result = scrollbar.handle_mouse_down(click_pos)

        assert result is True
        assert scrollbar.is_dragging is True
        assert scrollbar.drag_start_y == click_pos[1]
        assert scrollbar.drag_start_offset == 0

    def test_mouse_down_on_track_jumps_to_position(self):
        """Test clicking on track (not thumb) jumps scroll position."""
        scrollbar = _create_scrollbar()

        # Click near the bottom of the track (below the thumb)
        click_pos = (SCROLLBAR_X + 4, SCROLLBAR_Y + SCROLLBAR_HEIGHT - 10)

        result = scrollbar.handle_mouse_down(click_pos)

        assert result is True
        assert scrollbar.scroll_offset > 0
        assert scrollbar.is_dragging is False

    def test_mouse_down_outside_scrollbar_returns_false(self):
        """Test clicking outside scrollbar returns False."""
        scrollbar = _create_scrollbar()
        click_pos = (0, 0)

        result = scrollbar.handle_mouse_down(click_pos)

        assert result is False

    def test_mouse_down_when_not_visible_returns_false(self):
        """Test clicking when scrollbar is not visible returns False."""
        scrollbar = _create_scrollbar(total_items=5, visible_items=10)

        click_pos = (SCROLLBAR_X + 4, SCROLLBAR_Y + 50)

        result = scrollbar.handle_mouse_down(click_pos)

        assert result is False

    def test_mouse_down_on_track_top(self):
        """Test clicking at the top of the track sets offset near 0."""
        scrollbar = _create_scrollbar(scroll_offset=20)

        click_pos = (SCROLLBAR_X + 4, SCROLLBAR_Y + 1)

        result = scrollbar.handle_mouse_down(click_pos)

        assert result is True
        # Click near top should set scroll_offset close to 0
        assert scrollbar.scroll_offset < 5


class TestScrollbarHandleMouseUp:
    """Test Scrollbar.handle_mouse_up()."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_mouse_up_clears_drag_state(self):
        """Test mouse up clears is_dragging when dragging."""
        scrollbar = _create_scrollbar()
        scrollbar.is_dragging = True

        result = scrollbar.handle_mouse_up((SCROLLBAR_X + 4, SCROLLBAR_Y + 50))

        assert result is True
        assert scrollbar.is_dragging is False

    def test_mouse_up_when_not_dragging_returns_false(self):
        """Test mouse up returns False when not dragging."""
        scrollbar = _create_scrollbar()

        result = scrollbar.handle_mouse_up((SCROLLBAR_X + 4, SCROLLBAR_Y + 50))

        assert result is False


class TestScrollbarHandleMouseMotion:
    """Test Scrollbar.handle_mouse_motion()."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_motion_updates_hover_on_thumb(self):
        """Test motion over thumb sets is_hovering."""
        scrollbar = _create_scrollbar()
        thumb_rect = scrollbar.get_thumb_rect()
        hover_pos = (thumb_rect.centerx, thumb_rect.centery)

        result = scrollbar.handle_mouse_motion(hover_pos)

        # Not dragging, so returns False
        assert result is False
        assert scrollbar.is_hovering is True

    def test_motion_clears_hover_off_thumb(self):
        """Test motion off thumb clears is_hovering."""
        scrollbar = _create_scrollbar()
        scrollbar.is_hovering = True

        # Position far from the thumb
        hover_pos = (0, 0)

        scrollbar.handle_mouse_motion(hover_pos)

        assert scrollbar.is_hovering is False

    def test_motion_during_drag_updates_scroll_offset(self):
        """Test dragging updates scroll offset based on pixel delta."""
        scrollbar = _create_scrollbar()
        thumb_rect = scrollbar.get_thumb_rect()

        # Start drag
        scrollbar.handle_mouse_down((thumb_rect.centerx, thumb_rect.centery))
        assert scrollbar.is_dragging is True

        # Move down by 50 pixels
        drag_pos = (thumb_rect.centerx, thumb_rect.centery + 50)
        result = scrollbar.handle_mouse_motion(drag_pos)

        assert result is True
        assert scrollbar.scroll_offset > 0

    def test_motion_during_drag_clamps_to_max(self):
        """Test dragging does not exceed max_scroll."""
        scrollbar = _create_scrollbar()
        thumb_rect = scrollbar.get_thumb_rect()

        scrollbar.handle_mouse_down((thumb_rect.centerx, thumb_rect.centery))

        # Move down by a huge amount
        drag_pos = (thumb_rect.centerx, thumb_rect.centery + 5000)
        scrollbar.handle_mouse_motion(drag_pos)

        assert scrollbar.scroll_offset <= scrollbar.max_scroll

    def test_motion_during_drag_clamps_to_zero(self):
        """Test dragging up does not go below 0."""
        scrollbar = _create_scrollbar(scroll_offset=20)
        thumb_rect = scrollbar.get_thumb_rect()

        scrollbar.handle_mouse_down((thumb_rect.centerx, thumb_rect.centery))

        # Move up by a huge amount
        drag_pos = (thumb_rect.centerx, thumb_rect.centery - 5000)
        scrollbar.handle_mouse_motion(drag_pos)

        assert scrollbar.scroll_offset >= 0

    def test_motion_when_not_visible_returns_false(self):
        """Test motion when scrollbar is not visible clears hover and returns False."""
        scrollbar = _create_scrollbar(total_items=5, visible_items=10)
        scrollbar.is_hovering = True

        result = scrollbar.handle_mouse_motion((SCROLLBAR_X + 4, SCROLLBAR_Y + 50))

        assert result is False
        assert scrollbar.is_hovering is False


class TestScrollbarUpdate:
    """Test Scrollbar.update() method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_update_syncs_state(self):
        """Test update sets total_items, visible_items, and clamps scroll_offset."""
        scrollbar = _create_scrollbar()

        scrollbar.update(total_items=100, visible_items=20, scroll_offset=50)

        assert scrollbar.total_items == 100
        assert scrollbar.visible_items == 20
        assert scrollbar.scroll_offset == 50

    def test_update_clamps_scroll_offset_to_max(self):
        """Test update clamps scroll_offset to max_scroll."""
        scrollbar = _create_scrollbar()

        scrollbar.update(total_items=30, visible_items=20, scroll_offset=999)

        assert scrollbar.scroll_offset == scrollbar.max_scroll

    def test_update_clamps_scroll_offset_to_zero(self):
        """Test update clamps negative scroll_offset to 0."""
        scrollbar = _create_scrollbar()

        scrollbar.update(total_items=30, visible_items=20, scroll_offset=-10)

        assert scrollbar.scroll_offset == 0


class TestScrollbarDraw:
    """Test Scrollbar.draw() method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_draw_when_visible(self, mocker):
        """Test draw renders track and thumb when visible."""
        scrollbar = _create_scrollbar()
        surface = mocker.Mock()
        mock_draw_rect = mocker.patch('pygame.draw.rect')

        scrollbar.draw(surface)

        # Should draw track and thumb (2 calls)
        assert mock_draw_rect.call_count == 2

    def test_draw_when_not_visible(self, mocker):
        """Test draw does nothing when not visible."""
        scrollbar = _create_scrollbar(total_items=5, visible_items=10)
        surface = mocker.Mock()
        mock_draw_rect = mocker.patch('pygame.draw.rect')

        scrollbar.draw(surface)

        mock_draw_rect.assert_not_called()

    def test_draw_uses_drag_color_when_dragging(self, mocker):
        """Test draw uses thumb_drag_color when is_dragging."""
        scrollbar = _create_scrollbar()
        scrollbar.is_dragging = True
        surface = mocker.Mock()
        mock_draw_rect = mocker.patch('pygame.draw.rect')

        scrollbar.draw(surface)

        # The second call should use thumb_drag_color
        thumb_call = mock_draw_rect.call_args_list[1]
        assert thumb_call.args[1] == scrollbar.thumb_drag_color

    def test_draw_uses_hover_color_when_hovering(self, mocker):
        """Test draw uses thumb_hover_color when is_hovering."""
        scrollbar = _create_scrollbar()
        scrollbar.is_hovering = True
        surface = mocker.Mock()
        mock_draw_rect = mocker.patch('pygame.draw.rect')

        scrollbar.draw(surface)

        thumb_call = mock_draw_rect.call_args_list[1]
        assert thumb_call.args[1] == scrollbar.thumb_hover_color

    def test_draw_uses_default_color_normally(self, mocker):
        """Test draw uses default thumb_color when not dragging or hovering."""
        scrollbar = _create_scrollbar()
        surface = mocker.Mock()
        mock_draw_rect = mocker.patch('pygame.draw.rect')

        scrollbar.draw(surface)

        thumb_call = mock_draw_rect.call_args_list[1]
        assert thumb_call.args[1] == scrollbar.thumb_color
