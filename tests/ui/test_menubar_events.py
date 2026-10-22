"""Test suite for MenuBar and MenuItem event handling coverage.

This module tests event handlers on MenuBar and MenuItem, including mouse enter/exit,
button up/down, and motion events with collided sprites. Every widget is real and lives in a
real sprite group, so the collisions are pygame's own: a menu item "collides" because the
event's position is inside its rect.
"""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames import events
from glitchygames.ui import MenuBar, MenuItem

# Test constants
TEST_MENUBAR_WIDTH = 800
TEST_MENUBAR_HEIGHT = 50
TEST_MENU_ITEM_WIDTH = 100
TEST_MENU_ITEM_HEIGHT = 30

# A position inside the File menu (the first menu, at the bar's top-left)
FILE_MENU_POSITION = (50, 15)
# A position no menu or sub-menu of these tests covers
EMPTY_POSITION = (700, 500)


@pytest.fixture(autouse=True)
def drain_menu_events():
    """Keep MENUEVENTs a test posts to the real event queue out of other tests.

    Yields:
        None
    """
    pygame.event.clear(eventtype=events.MENUEVENT)
    yield
    pygame.event.clear(eventtype=events.MENUEVENT)


def _mouse_event(position, event_type=pygame.MOUSEMOTION):
    """Build a real mouse event at a position.

    Returns:
        pygame.event.Event: The event.
    """
    if event_type == pygame.MOUSEMOTION:
        return pygame.event.Event(event_type, pos=position, rel=(0, 0), buttons=(0, 0, 0))
    return pygame.event.Event(event_type, pos=position, button=1)


def _create_menubar():
    """Create a MenuBar with standard test configuration in a real sprite group.

    Returns:
        A MenuBar instance configured for testing.
    """
    return MenuBar(
        x=0,
        y=0,
        width=TEST_MENUBAR_WIDTH,
        height=TEST_MENUBAR_HEIGHT,
        name='test_menubar',
        groups=pygame.sprite.LayeredDirty(),
    )


def _create_menu_item(
    groups,
    *,
    name='FileMenu',
    position=(0, 0),
    width=TEST_MENU_ITEM_WIDTH,
    height=TEST_MENU_ITEM_HEIGHT,
):
    """Create a real MenuItem in the given sprite group.

    Returns:
        MenuItem: The menu item.
    """
    x, y = position
    return MenuItem(x=x, y=y, width=width, height=height, name=name, groups=groups)


def _menu_events_posted():
    """Take the MENUEVENTs posted to the real event queue.

    Returns:
        list: The posted MENUEVENTs, oldest first.
    """
    return pygame.event.get(eventtype=events.MENUEVENT)


class _StrangerSprite(pygame.sprite.DirtySprite):
    """A collidable sprite that is neither a MenuItem nor registered with a menu.

    It records every handler called on it, so a test can show no menu sent it an event.
    """

    def __init__(self, groups, rect):
        super().__init__(groups)
        self.name = 'Stranger'
        self.rect = pygame.Rect(rect)
        self.image = pygame.Surface(self.rect.size)
        self.menu_items = {}
        self.handlers_called = []

    def __getattr__(self, attribute_name):
        if attribute_name.startswith('on_'):
            return lambda *_args, **_kwargs: self.handlers_called.append(attribute_name)
        raise AttributeError(attribute_name)


class TestMenuBarMouseEnterEvent:
    """Test MenuBar.on_mouse_enter_event() with collided sprites."""

    def test_mouse_enter_sets_focus(self):
        """Test that on_mouse_enter_event sets has_focus to True."""
        menubar = _create_menubar()

        menubar.on_mouse_enter_event(_mouse_event((50, 25)))

        assert menubar.has_focus is True

    def test_mouse_enter_with_collided_menu_item(self):
        """Test mouse enter gives the registered menu item under the mouse focus."""
        menubar = _create_menubar()
        file_menu = _create_menu_item(menubar.all_sprites)
        menubar.add_menu(file_menu)
        assert getattr(file_menu, 'has_focus', False) is False

        menubar.on_mouse_enter_event(_mouse_event(FILE_MENU_POSITION))

        assert file_menu.has_focus is True
        assert menubar.has_focus is True

    def test_mouse_enter_propagates_to_sub_menu_items(self):
        """Test mouse enter reaches the sub menu items of the collided menu item."""
        menubar = _create_menubar()
        file_menu = _create_menu_item(menubar.all_sprites)
        menubar.add_menu(file_menu)
        new_file = _create_menu_item(menubar.all_sprites, name='NewFile', height=20)
        file_menu.add_menu(new_file)
        # The sub-item is not under the mouse: only the propagation can reach it
        assert not new_file.rect.collidepoint(FILE_MENU_POSITION)

        menubar.on_mouse_enter_event(_mouse_event(FILE_MENU_POSITION))

        assert new_file.has_focus is True

    def test_mouse_enter_ignores_non_registered_sprites(self):
        """Test mouse enter ignores menu items not in the bar's menu_items dict."""
        menubar = _create_menubar()
        unregistered_item = _create_menu_item(menubar.all_sprites, name='UnknownSprite')

        menubar.on_mouse_enter_event(_mouse_event(FILE_MENU_POSITION))

        # The unregistered item should not have its event called
        assert getattr(unregistered_item, 'has_focus', False) is False
        assert menubar.has_focus is True


class TestMenuBarMouseExitEvent:
    """Test MenuBar.on_mouse_exit_event()."""

    def test_mouse_exit_clears_focus(self):
        """Test that on_mouse_exit_event clears has_focus."""
        menubar = _create_menubar()
        menubar.has_focus = True

        menubar.on_mouse_exit_event(_mouse_event((50, 25)))

        assert menubar.has_focus is False

    def test_mouse_exit_with_collided_menu_item(self):
        """Test mouse exit takes the focus from the collided menu item."""
        menubar = _create_menubar()
        file_menu = _create_menu_item(menubar.all_sprites)
        menubar.add_menu(file_menu)
        file_menu.has_focus = True
        file_menu.dirty = 0

        menubar.on_mouse_exit_event(_mouse_event(FILE_MENU_POSITION))

        assert getattr(file_menu, 'has_focus', False) is False
        assert file_menu.dirty == 1
        assert menubar.has_focus is False

    def test_mouse_exit_propagates_to_sub_menu_items(self):
        """Test mouse exit reaches the sub menu items of the collided menu item."""
        menubar = _create_menubar()
        file_menu = _create_menu_item(menubar.all_sprites)
        menubar.add_menu(file_menu)
        new_file = _create_menu_item(menubar.all_sprites, name='NewFile', height=20)
        file_menu.add_menu(new_file)
        assert not new_file.rect.collidepoint(FILE_MENU_POSITION)
        new_file.has_focus = True

        menubar.on_mouse_exit_event(_mouse_event(FILE_MENU_POSITION))

        assert new_file.has_focus is False


class TestMenuBarLeftMouseButtonDownEvent:
    """Test MenuBar.on_left_mouse_button_down_event()."""

    def test_button_down_with_menu_item_collision(self):
        """Test left mouse button down presses the MenuItem under the mouse."""
        menubar = _create_menubar()
        file_menu = _create_menu_item(menubar.all_sprites)

        menubar.on_left_mouse_button_down_event(
            _mouse_event(FILE_MENU_POSITION, pygame.MOUSEBUTTONDOWN)
        )

        assert file_menu.is_active is True
        assert file_menu.image is file_menu.menu_down_image

    def test_button_down_propagates_to_sub_items(self):
        """Test button down reaches the sub menu items of the pressed menu item."""
        menubar = _create_menubar()
        file_menu = _create_menu_item(menubar.all_sprites)
        menubar.add_menu(file_menu)
        new_file = _create_menu_item(menubar.all_sprites, name='NewFile', height=20)
        file_menu.add_menu(new_file)
        assert not new_file.rect.collidepoint(FILE_MENU_POSITION)

        menubar.on_left_mouse_button_down_event(
            _mouse_event(FILE_MENU_POSITION, pygame.MOUSEBUTTONDOWN)
        )

        assert file_menu.is_active is True
        assert new_file.is_active is True

    def test_button_down_no_collisions(self):
        """Test left mouse button down away from every menu item presses nothing."""
        menubar = _create_menubar()
        file_menu = _create_menu_item(menubar.all_sprites)

        menubar.on_left_mouse_button_down_event(
            _mouse_event(EMPTY_POSITION, pygame.MOUSEBUTTONDOWN)
        )

        assert file_menu.is_active is False


class TestMenuBarLeftMouseButtonUpEvent:
    """Test MenuBar.on_left_mouse_button_up_event()."""

    def test_button_up_with_menu_item_collision(self):
        """Test left mouse button up routes to the collided MenuItem."""
        menubar = _create_menubar()
        file_menu = _create_menu_item(menubar.all_sprites)

        menubar.on_left_mouse_button_up_event(
            _mouse_event(FILE_MENU_POSITION, pygame.MOUSEBUTTONUP)
        )

        # MenuBar calls on_left_mouse_button_down_event on the sprite (yes, down on up), so
        # releasing the button over a menu leaves it pressed (open)
        assert file_menu.is_active is True
        assert file_menu.image is file_menu.menu_down_image

    def test_button_up_releases_the_sub_items(self):
        """Test left mouse button up sends the button up to the menu's sub items."""
        menubar = _create_menubar()
        file_menu = _create_menu_item(menubar.all_sprites)
        menubar.add_menu(file_menu)
        new_file = _create_menu_item(menubar.all_sprites, name='NewFile', height=20)
        file_menu.add_menu(new_file)
        new_file.is_active = True

        menubar.on_left_mouse_button_up_event(
            _mouse_event(FILE_MENU_POSITION, pygame.MOUSEBUTTONUP)
        )

        assert new_file.is_active is False

    def test_button_up_no_collisions(self):
        """Test left mouse button up away from every menu item changes nothing."""
        menubar = _create_menubar()
        file_menu = _create_menu_item(menubar.all_sprites)

        menubar.on_left_mouse_button_up_event(_mouse_event(EMPTY_POSITION, pygame.MOUSEBUTTONUP))

        assert file_menu.is_active is False
        assert _menu_events_posted() == []


class TestMenuItemMouseMotionEvent:
    """Test MenuItem.on_mouse_motion_event()."""

    def test_motion_event_with_no_collisions(self):
        """Test mouse motion event with no collisions clears focus."""
        menu_item = _create_menu_item(pygame.sprite.LayeredDirty())
        menu_item.has_focus = True

        menu_item.on_mouse_motion_event(_mouse_event(EMPTY_POSITION))

        assert menu_item.has_focus is False

    def test_motion_event_with_collided_sub_item(self):
        """Test mouse motion reaches the registered sub item under the mouse."""
        groups = pygame.sprite.LayeredDirty()
        menu_item = _create_menu_item(groups)
        new_file = _create_menu_item(groups, name='NewFile', position=(0, 200), height=20)
        menu_item.menu_items['NewFile'] = new_file
        new_file.has_focus = True

        menu_item.on_mouse_motion_event(_mouse_event(new_file.rect.center))

        assert new_file.has_focus is False


class TestMenuItemMouseEnterEvent:
    """Test MenuItem.on_mouse_enter_event()."""

    def test_enter_sets_focus(self):
        """Test mouse enter sets has_focus on MenuItem."""
        menu_item = _create_menu_item(pygame.sprite.LayeredDirty())

        menu_item.on_mouse_enter_event(_mouse_event(FILE_MENU_POSITION))

        assert menu_item.has_focus is True

    def test_enter_calls_enter_on_collided_sub_item(self):
        """Test mouse enter gives the registered sub item under the mouse focus."""
        groups = pygame.sprite.LayeredDirty()
        menu_item = _create_menu_item(groups)
        new_file = _create_menu_item(groups, name='NewFile', position=(0, 200), height=20)
        menu_item.menu_items['NewFile'] = new_file

        menu_item.on_mouse_enter_event(_mouse_event(new_file.rect.center))

        assert new_file.has_focus is True


class TestMenuItemMouseExitEvent:
    """Test MenuItem.on_mouse_exit_event()."""

    def test_exit_clears_focus(self):
        """Test mouse exit clears has_focus and sets dirty."""
        menu_item = _create_menu_item(pygame.sprite.LayeredDirty())
        menu_item.has_focus = True

        menu_item.on_mouse_exit_event(_mouse_event(EMPTY_POSITION))

        assert menu_item.has_focus is False
        assert menu_item.dirty == 1

    def test_exit_calls_exit_on_collided_sub_item(self):
        """Test mouse exit takes the focus from the registered sub item under the mouse."""
        groups = pygame.sprite.LayeredDirty()
        menu_item = _create_menu_item(groups)
        new_file = _create_menu_item(groups, name='NewFile', position=(0, 200), height=20)
        menu_item.menu_items['NewFile'] = new_file
        new_file.has_focus = True
        new_file.dirty = 0

        menu_item.on_mouse_exit_event(_mouse_event(new_file.rect.center))

        assert new_file.has_focus is False
        assert new_file.dirty == 1


class TestMenuItemLeftMouseButtonUpEvent:
    """Test MenuItem.on_left_mouse_button_up_event()."""

    def test_button_up_restores_up_image(self):
        """Test button up restores menu_up_image and deactivates."""
        menu_item = _create_menu_item(pygame.sprite.LayeredDirty())
        original_up_image = menu_item.menu_up_image
        menu_item.on_left_mouse_button_down_event(
            _mouse_event(EMPTY_POSITION, pygame.MOUSEBUTTONDOWN)
        )
        assert menu_item.is_active is True

        menu_item.on_left_mouse_button_up_event(_mouse_event(EMPTY_POSITION, pygame.MOUSEBUTTONUP))

        assert menu_item.image is original_up_image
        assert menu_item.rect is menu_item.menu_up_rect
        assert menu_item.is_active is False
        assert menu_item.dirty == 2

    def test_button_up_invokes_callback(self, mocker):
        """Test button up invokes the collided item's on_menu_item_event callback."""
        groups = pygame.sprite.LayeredDirty()
        menu_item = _create_menu_item(groups)
        collided_item = _create_menu_item(groups, name='NewFile', position=(0, 200))
        callback = mocker.Mock()
        collided_item.callbacks = {'on_menu_item_event': callback}
        event = _mouse_event(collided_item.rect.center, pygame.MOUSEBUTTONUP)

        menu_item.on_left_mouse_button_up_event(event)

        callback.assert_called_once_with(menu_item, event)

    def test_button_up_posts_menu_event(self):
        """Test button up posts a MENUEVENT naming the clicked item to the event queue."""
        groups = pygame.sprite.LayeredDirty()
        menu_item = _create_menu_item(groups)
        collided_item = _create_menu_item(groups, name='NewFile', position=(0, 200))

        menu_item.on_left_mouse_button_up_event(
            _mouse_event(collided_item.rect.center, pygame.MOUSEBUTTONUP)
        )

        posted_events = _menu_events_posted()
        assert len(posted_events) == 1
        assert posted_events[0].menu is menu_item
        assert posted_events[0].menu_item is collided_item


class TestMenuItemLeftMouseButtonDownEvent:
    """Test MenuItem.on_left_mouse_button_down_event()."""

    def test_button_down_sets_down_image_and_activates(self):
        """Test button down switches to menu_down_image and activates."""
        menu_item = _create_menu_item(pygame.sprite.LayeredDirty())

        menu_item.on_left_mouse_button_down_event(
            _mouse_event(EMPTY_POSITION, pygame.MOUSEBUTTONDOWN)
        )

        assert menu_item.image is menu_item.menu_down_image
        assert menu_item.rect is menu_item.menu_down_rect
        assert menu_item.is_active is True
        assert menu_item.dirty == 2

    def test_button_down_propagates_to_collided_sub_items(self):
        """Test button down presses the registered sub item under the mouse."""
        groups = pygame.sprite.LayeredDirty()
        menu_item = _create_menu_item(groups)
        new_file = _create_menu_item(groups, name='NewFile', position=(0, 200), height=20)
        menu_item.menu_items['NewFile'] = new_file

        menu_item.on_left_mouse_button_down_event(
            _mouse_event(new_file.rect.center, pygame.MOUSEBUTTONDOWN)
        )

        assert new_file.is_active is True


class TestMenuItemNestedSubMenus:
    """A collided sub-item's own sub-items get the event too (they are the dict's values)."""

    @staticmethod
    def _menu_with_nested_item():
        """A real MenuItem whose collided sub-item has a sub-item of its own.

        The nested item is away from the mouse, so only the propagation reaches it.

        Returns:
            The menu item, the collided sub-item, its own sub-item and the event position.

        """
        groups = pygame.sprite.LayeredDirty()
        menu_item = _create_menu_item(groups)
        sub_item = _create_menu_item(groups, name='OpenRecent', position=(0, 200), height=20)
        nested_item = _create_menu_item(groups, name='RecentFile', position=(400, 400), height=20)
        menu_item.menu_items['OpenRecent'] = sub_item
        sub_item.menu_items['RecentFile'] = nested_item
        return menu_item, sub_item, nested_item, sub_item.rect.center

    def test_motion_reaches_nested_sub_items(self):
        """It iterated the dict's keys (names) and called the handler on a string."""
        menu_item, sub_item, nested_item, position = self._menu_with_nested_item()
        sub_item.has_focus = True
        nested_item.has_focus = True

        menu_item.on_mouse_motion_event(_mouse_event(position))

        assert sub_item.has_focus is False
        assert nested_item.has_focus is False

    def test_enter_reaches_nested_sub_items(self):
        menu_item, sub_item, nested_item, position = self._menu_with_nested_item()

        menu_item.on_mouse_enter_event(_mouse_event(position))

        assert sub_item.has_focus is True
        assert nested_item.has_focus is True

    def test_exit_sends_exit_to_nested_sub_items(self):
        """Leaving the menu leaves its nested items too (it sent them an enter event)."""
        menu_item, sub_item, nested_item, position = self._menu_with_nested_item()
        sub_item.has_focus = True
        nested_item.has_focus = True
        nested_item.dirty = 0

        menu_item.on_mouse_exit_event(_mouse_event(position))

        assert sub_item.has_focus is False
        # An exit (not an enter) reached the nested item: focus cleared, marked dirty
        assert nested_item.has_focus is False
        assert nested_item.dirty == 1


class TestMenuHandlersIgnoreOtherSprites:
    """Collided sprites that are not this menu's items (or not MenuItems) get no event."""

    STRANGER_RECT = (600, 400, 20, 20)
    STRANGER_POSITION = (610, 410)

    @pytest.mark.parametrize(
        'handler_name',
        [
            'on_mouse_exit_event',
            'on_left_mouse_button_down_event',
            'on_left_mouse_button_up_event',
        ],
    )
    def test_menubar_ignores_a_stranger(self, handler_name):
        menubar = _create_menubar()
        stranger = _StrangerSprite(menubar.all_sprites, self.STRANGER_RECT)

        getattr(menubar, handler_name)(_mouse_event(self.STRANGER_POSITION, pygame.MOUSEBUTTONUP))

        assert stranger.handlers_called == []

    @pytest.mark.parametrize(
        'handler_name',
        [
            'on_mouse_motion_event',
            'on_mouse_enter_event',
            'on_mouse_exit_event',
            'on_left_mouse_button_up_event',
        ],
    )
    def test_menu_item_ignores_a_stranger(self, handler_name):
        groups = pygame.sprite.LayeredDirty()
        menu_item = _create_menu_item(groups)
        stranger = _StrangerSprite(groups, self.STRANGER_RECT)

        getattr(menu_item, handler_name)(_mouse_event(self.STRANGER_POSITION, pygame.MOUSEBUTTONUP))

        assert stranger.handlers_called == []
        assert _menu_events_posted() == []


class TestMenuItemWithoutGroups:
    """A MenuItem made without groups gets a group of its own."""

    def test_menu_item_without_groups_keeps_its_sprites_in_a_new_group(self):
        first_item = MenuItem(x=0, y=0, width=100, height=30, name='FileMenu', groups=None)
        second_item = MenuItem(x=0, y=0, width=100, height=30, name='EditMenu', groups=None)

        assert isinstance(first_item.all_sprites, pygame.sprite.LayeredDirty)
        assert first_item.all_sprites is not second_item.all_sprites
        assert first_item.text in first_item.all_sprites
