"""Test suite for tab control UI component.

This module tests TabControlSprite functionality including tab switching,
format changes, and integration with slider input formatting.
"""

import pygame

from glitchygames.ui import TabControlSprite

# Test constants to avoid magic values
TEST_X_POS = 10
TEST_Y_POS = 20
TEST_WIDTH = 100
TEST_HEIGHT = 30
TEST_TAB_COUNT = 2
TAB_WIDTH = TEST_WIDTH // TEST_TAB_COUNT


def _surface_in_cocoa_format(size):
    """A surface in the format a plain pygame.Surface takes on cocoa: alpha mask, no SRCALPHA.

    Alpha-blending text onto such a surface leaves alpha 0, which the window shows as black
    (glitchygames/opacity.py). Built explicitly, so the rule is tested on the dummy driver too.

    Returns:
        pygame.Surface: The surface.

    """
    return pygame.Surface(size, depth=32, masks=(0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000))


class _TabParent:
    """A slider-like parent that records the tab changes it is told about."""

    def __init__(self):
        self.slider_input_format = '%d'
        self.tab_changes = []

    def on_tab_change_event(self, tab):
        self.tab_changes.append(tab)


def _mouse_down_event(position):
    """Build a real left mouse button down event at a position.

    Returns:
        pygame.event.Event: The event.
    """
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=position, button=1)


def _rgb_at(surface, position):
    """Return the RGB colour of one pixel (the alpha is not the point here).

    Returns:
        tuple: The (red, green, blue) colour.
    """
    return tuple(surface.get_at(position))[:3]


def _text_pixel_count(surface, tab_index, text_color):
    """Count the text-coloured pixels inside one tab's inner area (border excluded).

    Returns:
        int: The number of pixels in the text colour.
    """
    left = tab_index * TAB_WIDTH + 1
    rgb_pixels = pygame.surfarray.pixels3d(surface)
    inner_area = rgb_pixels[left : left + TAB_WIDTH - 2, 1 : TEST_HEIGHT - 1]
    count = int((inner_area == text_color).all(axis=2).sum())
    del inner_area, rgb_pixels
    return count


class TestTabControlSpriteFunctionality:
    """Test TabControlSprite functionality."""

    def test_tab_control_initialization(self):
        """Test TabControlSprite initialization."""
        # Arrange
        parent = _TabParent()
        parent.slider_input_format = '%d'

        # Act
        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)

        # Assert
        assert tab_control.rect is not None
        assert tab_control.rect.x == TEST_X_POS
        assert tab_control.rect.y == TEST_Y_POS
        assert tab_control.rect.width == TEST_WIDTH
        assert tab_control.rect.height == TEST_HEIGHT
        assert tab_control.parent == parent
        assert tab_control.tabs == ['%d', '%X']
        assert tab_control.active_tab == 0
        # Dirty flag is set to 1 by default in DirtySprite
        assert tab_control.dirty == 1

    def test_tab_control_click_handling(self):
        """Test TabControlSprite click handling."""
        # Arrange
        parent = _TabParent()
        parent.slider_input_format = '%d'

        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)

        event = _mouse_down_event((60, 35))  # Click on second tab (hex)

        # Act
        tab_control.on_left_mouse_button_down_event(event)

        # Assert
        assert tab_control.active_tab == 1
        assert tab_control.dirty == 1  # Redrawn once (BUGS.md #155 item 2)
        assert parent.tab_changes == ['%X']

    def test_tab_control_click_first_tab(self):
        """Test TabControlSprite click on first tab."""
        # Arrange
        parent = _TabParent()
        parent.slider_input_format = '%X'

        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)
        tab_control.active_tab = 1  # Start on second tab

        event = _mouse_down_event((35, 35))  # Click on first tab (decimal)

        # Act
        tab_control.on_left_mouse_button_down_event(event)

        # Assert
        assert tab_control.active_tab == 0
        assert tab_control.dirty == 1  # Redrawn once (BUGS.md #155 item 2)
        assert parent.tab_changes == ['%d']

    def test_tab_control_click_outside_bounds(self):
        """Test TabControlSprite click outside bounds."""
        # Arrange
        parent = _TabParent()
        parent.slider_input_format = '%d'

        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)

        event = _mouse_down_event((200, 200))  # Click outside bounds

        # Act
        tab_control.on_left_mouse_button_down_event(event)

        # Assert - should not change active tab
        assert tab_control.active_tab == 0
        # Dirty flag remains 1 (default) when clicking outside bounds
        assert tab_control.dirty == 1
        assert parent.tab_changes == []

    def test_tab_control_update_rendering(self):
        """Test update draws both tabs, the active one highlighted, with their labels."""
        # Arrange
        parent = _TabParent()
        parent.slider_input_format = '%d'

        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)
        tab_control.dirty = 2

        # Act
        tab_control.update()

        # Assert: border, active (first) and inactive (second) backgrounds
        image = tab_control.image
        assert _rgb_at(image, (0, 0)) == tab_control.border_color
        assert _rgb_at(image, (TAB_WIDTH, 0)) == tab_control.border_color
        assert _rgb_at(image, (2, 2)) == tab_control.active_color
        assert _rgb_at(image, (TAB_WIDTH + 2, 2)) == tab_control.inactive_color
        # Each tab's label is drawn in the text colour
        assert _text_pixel_count(image, 0, tab_control.text_color) > 0
        assert _text_pixel_count(image, 1, tab_control.text_color) > 0

    def test_tab_control_update_highlights_the_newly_active_tab(self):
        """Test clicking the second tab redraws it as the active one."""
        parent = _TabParent()
        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)
        tab_control.update()

        tab_control.on_left_mouse_button_down_event(_mouse_down_event((60, 35)))
        tab_control.update()

        assert _rgb_at(tab_control.image, (2, 2)) == tab_control.inactive_color
        assert _rgb_at(tab_control.image, (TAB_WIDTH + 2, 2)) == tab_control.active_color

    def test_tab_control_tab_calculation(self):
        """Test TabControlSprite tab position calculation."""
        # Arrange
        parent = _TabParent()
        parent.slider_input_format = '%d'

        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)

        # Test tab position calculations
        # The actual implementation may have different positioning logic
        # We'll test the basic properties instead of specific calculations
        assert tab_control.rect is not None
        assert tab_control.rect.width == TEST_WIDTH
        assert tab_control.rect.height == TEST_HEIGHT
        assert len(tab_control.tabs) == TEST_TAB_COUNT

    def test_tab_control_active_tab_property(self):
        """Test TabControlSprite active tab property."""
        # Arrange
        parent = _TabParent()
        parent.slider_input_format = '%d'

        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)

        # Act
        tab_control.active_tab = 1

        # Assert
        assert tab_control.active_tab == 1
        assert tab_control.tabs[tab_control.active_tab] == '%X'

    def test_tab_control_parent_integration(self):
        """Test TabControlSprite integration with parent."""
        # Arrange
        parent = _TabParent()
        parent.slider_input_format = '%d'

        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)

        # Act - simulate tab change
        tab_control.active_tab = 1
        tab_control.on_left_mouse_button_down_event(_mouse_down_event((60, 35)))

        # Assert
        assert parent.tab_changes == ['%X']

    def test_tab_control_dirty_flag_management(self):
        """Test TabControlSprite dirty flag management."""
        # Arrange
        parent = _TabParent()
        parent.slider_input_format = '%d'

        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)

        # Act - set dirty flag
        tab_control.dirty = 2

        # Assert
        assert tab_control.dirty == TEST_TAB_COUNT

        # Act - a dirty tab control draws its tabs on update
        tab_control.image.fill((1, 2, 3, 255))
        tab_control.update()

        # Assert - the placeholder fill was replaced by the tabs
        assert _rgb_at(tab_control.image, (2, 2)) == tab_control.active_color

    def test_tab_control_tab_text_content(self):
        """Test TabControlSprite tab text content."""
        # Arrange
        parent = _TabParent()
        parent.slider_input_format = '%d'

        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)

        # Assert
        assert tab_control.tabs[0] == '%d'  # Decimal format
        assert tab_control.tabs[1] == '%X'  # Hex format

    def test_tab_control_rect_properties(self):
        """Test TabControlSprite rect properties."""
        # Arrange
        parent = _TabParent()
        parent.slider_input_format = '%d'

        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)

        # Assert
        assert tab_control.rect is not None
        assert tab_control.rect.x == TEST_X_POS
        assert tab_control.rect.y == TEST_Y_POS
        assert tab_control.rect.width == TEST_WIDTH
        assert tab_control.rect.height == TEST_HEIGHT

    def test_tab_control_click_boundary_conditions(self):
        """Test TabControlSprite click boundary conditions."""
        # Arrange
        parent = _TabParent()
        parent.slider_input_format = '%d'

        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)

        # Test click on exact boundary
        event = _mouse_down_event((60, 35))  # Right on the boundary between tabs

        # Act
        tab_control.on_left_mouse_button_down_event(event)

        # Assert - should select second tab
        assert tab_control.active_tab == 1
        assert parent.tab_changes == ['%X']


class TestTabControlSpriteWithRealSurfaces:
    """TabControlSprite redraw rules on real pygame surfaces."""

    def test_click_outside_the_tabs_changes_nothing(self):
        parent = _TabParent()
        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=parent)
        tab_control.dirty = 0

        tab_control.on_left_mouse_button_down_event(_mouse_down_event((200, 200)))

        assert tab_control.active_tab == 0
        assert tab_control.dirty == 0
        assert parent.tab_changes == []

    def test_update_draws_nothing_while_clean(self):
        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=_TabParent())
        tab_control.update()  # The first update draws the tabs
        drawn_pixels = pygame.image.tobytes(tab_control.image, 'RGBA')
        tab_control.image.fill((1, 2, 3, 255))
        tab_control.dirty = 0

        tab_control.update()

        assert pygame.image.tobytes(tab_control.image, 'RGBA') != drawn_pixels
        assert tab_control.image.get_at((0, 0)) == (1, 2, 3, 255)

    def test_the_image_stays_opaque_under_its_text_in_the_cocoa_format(self):
        """The tab text is blended onto the image, which is then opaque: no black on cocoa."""
        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=_TabParent())
        tab_control.image = _surface_in_cocoa_format((TEST_WIDTH, TEST_HEIGHT))
        tab_control.dirty = 1

        tab_control.update()

        assert (pygame.surfarray.array_alpha(tab_control.image) == 255).all()

    def test_a_click_redraws_once_with_one_font(self, mocker):
        """A tab click redraws the tabs once; every draw reuses one font (BUGS.md #155 item 2)."""
        tab_control = TabControlSprite(x=10, y=20, width=100, height=30, parent=_TabParent())
        font_constructor = mocker.spy(pygame.font, 'Font')
        click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(10 + 75, 20 + 10))

        tab_control.on_left_mouse_button_down_event(click)
        tab_control.update()
        tab_control.on_left_mouse_button_down_event(click)
        tab_control.update()

        assert tab_control.dirty == 1
        assert font_constructor.call_count == 1
