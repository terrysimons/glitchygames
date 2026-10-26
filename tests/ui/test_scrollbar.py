"""Test suite for Scrollbar interaction coverage.

This module tests the Scrollbar class including mouse down handling on
thumb and track, mouse up clearing drag state, mouse motion with drag
and hover, and scroll position calculations.
"""

import pygame

from glitchygames.ui import Scrollbar

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

    def test_drag_on_a_track_no_taller_than_its_thumb_does_not_scroll(self):
        """A track shorter than the minimum thumb (20 px) has no room to drag in."""
        scrollbar = Scrollbar(
            x=SCROLLBAR_X,
            y=SCROLLBAR_Y,
            width=SCROLLBAR_WIDTH,
            height=15,
            total_items=TOTAL_ITEMS,
            visible_items=VISIBLE_ITEMS,
            scroll_offset=5,
        )
        scrollbar.is_dragging = True
        scrollbar.drag_start_y = SCROLLBAR_Y
        scrollbar.drag_start_offset = 5

        result = scrollbar.handle_mouse_motion((SCROLLBAR_X + 4, SCROLLBAR_Y + 40))

        assert result is True
        assert scrollbar.scroll_offset == 5

    def test_motion_when_not_visible_returns_false(self):
        """Test motion when scrollbar is not visible clears hover and returns False."""
        scrollbar = _create_scrollbar(total_items=5, visible_items=10)
        scrollbar.is_hovering = True

        result = scrollbar.handle_mouse_motion((SCROLLBAR_X + 4, SCROLLBAR_Y + 50))

        assert result is False
        assert scrollbar.is_hovering is False


class TestScrollbarUpdate:
    """Test Scrollbar.update() method."""

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


BACKGROUND_COLOR = (255, 0, 255)


def _draw_scrollbar(scrollbar):
    """Draw a scrollbar onto a real surface filled with a background colour.

    Returns:
        The surface drawn on.
    """
    surface = pygame.Surface((
        SCROLLBAR_X + SCROLLBAR_WIDTH + 2,
        SCROLLBAR_Y + SCROLLBAR_HEIGHT + 2,
    ))
    surface.fill(BACKGROUND_COLOR)
    scrollbar.draw(surface)
    return surface


def _rgb_at(surface, position):
    """Return the RGB colour of one pixel (the alpha is not the point here).

    Returns:
        The (red, green, blue) tuple at the position.
    """
    return tuple(surface.get_at(position))[:3]


class TestScrollbarDraw:
    """Test Scrollbar.draw() method on a real surface."""

    def test_draw_when_visible(self):
        """Test draw paints the track and the thumb when visible."""
        scrollbar = _create_scrollbar()

        surface = _draw_scrollbar(scrollbar)

        thumb_rect = scrollbar.get_thumb_rect()
        track_position = (SCROLLBAR_X + 1, SCROLLBAR_Y + SCROLLBAR_HEIGHT - 1)
        assert not thumb_rect.collidepoint(track_position)
        assert _rgb_at(surface, track_position) == scrollbar.track_color
        assert _rgb_at(surface, thumb_rect.center) == scrollbar.thumb_color
        # Nothing is drawn outside the scrollbar's rect
        assert _rgb_at(surface, (SCROLLBAR_X - 1, SCROLLBAR_Y)) == BACKGROUND_COLOR
        assert _rgb_at(surface, (SCROLLBAR_X + SCROLLBAR_WIDTH, SCROLLBAR_Y)) == BACKGROUND_COLOR
        assert _rgb_at(surface, (SCROLLBAR_X, SCROLLBAR_Y + SCROLLBAR_HEIGHT)) == BACKGROUND_COLOR

    def test_draw_when_not_visible(self):
        """Test draw leaves the surface untouched when not visible."""
        scrollbar = _create_scrollbar(total_items=5, visible_items=10)

        surface = _draw_scrollbar(scrollbar)

        rgb_pixels = pygame.surfarray.pixels3d(surface)
        assert (rgb_pixels == BACKGROUND_COLOR).all()
        del rgb_pixels

    def test_draw_uses_drag_color_when_dragging(self):
        """Test draw uses thumb_drag_color when is_dragging."""
        scrollbar = _create_scrollbar()
        scrollbar.is_dragging = True

        surface = _draw_scrollbar(scrollbar)

        assert _rgb_at(surface, scrollbar.get_thumb_rect().center) == scrollbar.thumb_drag_color

    def test_draw_uses_hover_color_when_hovering(self):
        """Test draw uses thumb_hover_color when is_hovering."""
        scrollbar = _create_scrollbar()
        scrollbar.is_hovering = True

        surface = _draw_scrollbar(scrollbar)

        assert _rgb_at(surface, scrollbar.get_thumb_rect().center) == scrollbar.thumb_hover_color

    def test_draw_uses_default_color_normally(self):
        """Test draw uses default thumb_color when not dragging or hovering."""
        scrollbar = _create_scrollbar()

        surface = _draw_scrollbar(scrollbar)

        assert _rgb_at(surface, scrollbar.get_thumb_rect().center) == scrollbar.thumb_color
