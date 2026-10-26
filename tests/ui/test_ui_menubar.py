"""Test suite for MenuBar UI component.

This module tests the MenuBar class functionality including initialization,
menu item management, event handling and drawing, on real surfaces and sprite groups.
"""

import pygame
import pytest

from glitchygames.ui import MenuBar, MenuItem

# Test constants to avoid magic values
TEST_BORDER_WIDTH = 2
TEST_MENU_OFFSET_X = 2
TEST_MENU_OFFSET_Y = 2
TEST_MENUBAR_WIDTH = 800
TEST_MENUBAR_HEIGHT = 50
TEST_MENU_ITEM_WIDTH = 100
TEST_MENU_ITEM_HEIGHT = 30
TEST_EXPECTED_MENU_COUNT = 2

# The bar's semi-transparent white background (WHITE at alpha 128)
MENUBAR_BACKGROUND = (255, 255, 255, 128)


def _create_menubar(*, x=0, y=0):
    """Create a MenuBar in a real sprite group.

    Returns:
        MenuBar: The menu bar.
    """
    return MenuBar(
        x=x,
        y=y,
        width=TEST_MENUBAR_WIDTH,
        height=TEST_MENUBAR_HEIGHT,
        name='test_menubar',
        groups=pygame.sprite.LayeredDirty(),
    )


def _create_menu_item(groups, name):
    """Create a real MenuItem in a sprite group.

    Returns:
        MenuItem: The menu item.
    """
    return MenuItem(
        x=0,
        y=0,
        width=TEST_MENU_ITEM_WIDTH,
        height=TEST_MENU_ITEM_HEIGHT,
        name=name,
        groups=groups,
    )


class TestMenuBarFunctionality:
    """Test MenuBar functionality."""

    def test_menubar_initialization(self):
        """Test MenuBar initialization."""
        groups = pygame.sprite.LayeredDirty()
        menubar = MenuBar(x=0, y=0, width=800, height=50, name='test_menubar', groups=groups)

        # Verify MenuBar-specific attributes
        assert menubar.all_sprites is groups
        assert menubar in groups
        assert menubar.background_color == (0, 255, 0)
        assert menubar.border_width == TEST_BORDER_WIDTH
        assert menubar.menu_items == {}
        assert menubar.menu_offset_x == TEST_MENU_OFFSET_X
        assert menubar.menu_offset_y == TEST_MENU_OFFSET_Y
        assert menubar.width == TEST_MENUBAR_WIDTH
        assert menubar.height == TEST_MENUBAR_HEIGHT
        assert menubar.dirty == 2  # The bar is always refreshed
        assert not menubar.has_focus

    def test_menubar_menu_item_methods(self):
        """Test MenuBar menu item management methods."""
        menubar = _create_menubar()
        file_menu = _create_menu_item(menubar.all_sprites, 'File')

        # Test adding menu items
        menubar.add_menu_item(file_menu)
        assert 'File' in menubar.menu_items
        assert menubar.menu_items['File'] is file_menu

        # Test that menu_items is a dictionary that can be accessed directly
        assert len(menubar.menu_items) == 1

        # Test adding another menu item
        edit_menu = _create_menu_item(menubar.all_sprites, 'Edit')

        menubar.add_menu_item(edit_menu)
        assert len(menubar.menu_items) == TEST_EXPECTED_MENU_COUNT
        assert 'Edit' in menubar.menu_items
        # The second menu is laid out to the right of the first, a border apart
        assert edit_menu.rect.x == file_menu.rect.right + TEST_BORDER_WIDTH

    def test_menubar_add_menu_item_to_a_menu_adds_no_menu(self):
        """Test add_menu_item with a menu given leaves the bar's own menus alone."""
        menubar = _create_menubar()
        file_menu = _create_menu_item(menubar.all_sprites, 'File')

        menubar.add_menu_item(file_menu, menu=menubar)

        assert menubar.menu_items == {}

    def test_menubar_add_menu(self):
        """Test adding MenuItem objects to MenuBar."""
        menubar = _create_menubar()
        menu = _create_menu_item(pygame.sprite.LayeredDirty(), 'TestMenu')

        # Test adding menu
        menubar.add_menu(menu)

        # Verify menu was added
        assert 'TestMenu' in menubar.menu_items
        assert menubar.menu_items['TestMenu'] is menu

        # Verify the menu's label was added to the bar's groups
        assert menu.text in menubar.all_sprites
        # Inset by the border, and magenta is its transparent colour
        assert menu.rect.y == TEST_MENU_OFFSET_Y
        assert menu.text.rect.y == TEST_MENU_OFFSET_Y
        colorkey = menu.image.get_colorkey()
        assert colorkey is not None
        assert colorkey[:3] == (255, 0, 255)
        assert menubar.menu_offset_x == menu.rect.right + TEST_BORDER_WIDTH

    def test_menubar_add_menu_places_icon_menus_side_by_side(self):
        """Menus without a name (icons) have no label; each one after the first follows the last."""
        menubar = _create_menubar()
        first_icon = _create_menu_item(menubar.all_sprites, None)
        second_icon = _create_menu_item(menubar.all_sprites, None)
        assert not hasattr(second_icon, 'text')

        menubar.add_menu(first_icon)
        offset_after_first = menubar.menu_offset_x
        menubar.add_menu(second_icon)

        assert second_icon.rect.x == offset_after_first
        assert second_icon.rect.y == TEST_MENU_OFFSET_Y
        assert menubar.menu_offset_x == second_icon.rect.right + TEST_BORDER_WIDTH

    def test_menubar_focus_handling(self):
        """Test MenuBar focus handling."""
        menubar = _create_menubar()

        # Test initial focus state
        assert not menubar.has_focus

        # Test setting focus directly (since gain_focus/lose_focus don't exist)
        menubar.has_focus = True
        assert menubar.has_focus

        # Test losing focus
        menubar.has_focus = False
        assert not menubar.has_focus

    def test_menubar_mouse_events(self):
        """Test MenuBar mouse button events press the menu under the mouse."""
        menubar = _create_menubar()
        file_menu = _create_menu_item(menubar.all_sprites, 'File')
        menubar.add_menu(file_menu)
        position = file_menu.rect.center

        # Test mouse button down event
        menubar.on_left_mouse_button_down_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=position, button=1)
        )
        assert file_menu.is_active is True

        # Test mouse button up event (the bar presses the menu again: it stays open)
        menubar.on_left_mouse_button_up_event(
            pygame.event.Event(pygame.MOUSEBUTTONUP, pos=position, button=1)
        )
        assert file_menu.is_active is True

    def test_menubar_rendering(self):
        """Test MenuBar draws its background and blits its menus in update()."""
        menubar = _create_menubar()

        assert menubar.width == TEST_MENUBAR_WIDTH
        assert menubar.height == TEST_MENUBAR_HEIGHT
        assert menubar.image.get_size() == (TEST_MENUBAR_WIDTH, TEST_MENUBAR_HEIGHT)
        # The whole bar is drawn semi-transparent white (it is its own SRCALPHA surface)
        alpha_values = pygame.surfarray.pixels_alpha(menubar.image)
        assert (alpha_values == MENUBAR_BACKGROUND[3]).all()
        del alpha_values
        rgb_pixels = pygame.surfarray.pixels3d(menubar.image)
        assert (rgb_pixels == MENUBAR_BACKGROUND[:3]).all()
        del rgb_pixels

        # update() blits each menu's image at the menu's position
        file_menu = _create_menu_item(menubar.all_sprites, 'File')
        menubar.add_menu(file_menu)
        file_menu.image.fill((255, 0, 0))
        menubar.update()

        menu_rect = file_menu.rect
        assert tuple(menubar.image.get_at(menu_rect.center))[:3] == (255, 0, 0)
        assert tuple(menubar.image.get_at((menu_rect.right + 5, menu_rect.centery))) == (
            MENUBAR_BACKGROUND
        )

    def test_menubar_rendering_with_focus_keeps_the_bar_drawn(self):
        """Test update() with focus draws the focus outline over the bar without erasing it."""
        menubar = _create_menubar()
        menubar.has_focus = True

        menubar.update()

        assert tuple(menubar.image.get_at((0, 0))) == MENUBAR_BACKGROUND
        assert tuple(menubar.image.get_at((5, 5))) == MENUBAR_BACKGROUND

    @pytest.mark.xfail(
        strict=True,
        reason=(
            'MenuBar.__init__ draws its background and border with self.rect (screen '
            'coordinates) onto its own image, so a bar not at (0, 0) leaves its top-left '
            'strip undrawn (transparent) and its border off the image'
        ),
    )
    def test_menubar_not_at_the_origin_draws_its_whole_background(self):
        """A bar placed away from (0, 0) is drawn over its whole image, like one at (0, 0)."""
        menubar = _create_menubar(x=20, y=20)

        rgb_pixels = pygame.surfarray.pixels3d(menubar.image)
        assert (rgb_pixels == MENUBAR_BACKGROUND[:3]).all()
        del rgb_pixels
