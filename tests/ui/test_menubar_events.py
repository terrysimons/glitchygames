"""Test suite for MenuBar and MenuItem event handling coverage.

This module tests event handlers on MenuBar and MenuItem that are not
covered by existing tests, including mouse enter/exit, button up/down,
and motion events with collided sprites.
"""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Save REAL LayeredDirty before mock_pygame_patches replaces it with a Mock.
# Tests that create real MenuItem/MenuBar widgets need actual sprite groups
# because pygame.sprite.Sprite.add_internal() requires a real group, not a Mock.
_RealLayeredDirty = pygame.sprite.LayeredDirty

from glitchygames.ui import MenuBar, MenuItem  # noqa: E402
from tests.mocks.test_mock_factory import MockFactory  # noqa: E402

# Test constants
TEST_MENUBAR_WIDTH = 800
TEST_MENUBAR_HEIGHT = 50
TEST_MENU_ITEM_WIDTH = 100
TEST_MENU_ITEM_HEIGHT = 30


def _create_menubar(mocker):
    """Create a MenuBar with standard test configuration.

    Returns:
        A MenuBar instance configured for testing.
    """
    groups = _RealLayeredDirty()
    return MenuBar(
        x=0,
        y=0,
        width=TEST_MENUBAR_WIDTH,
        height=TEST_MENUBAR_HEIGHT,
        name='test_menubar',
        groups=groups,
    )


def _create_mock_menu_item_sprite(mocker, name='FileMenu', *, has_menu_items=True):
    """Create a mock sprite that looks like a MenuItem for collision results.

    Returns:
        A mock sprite configured to look like a MenuItem.
    """
    mock_sprite = mocker.Mock(spec=MenuItem)
    mock_sprite.name = name
    mock_sprite.rect = mocker.Mock()
    mock_sprite.rect.x = 0
    mock_sprite.rect.y = 0
    mock_sprite.rect.width = TEST_MENU_ITEM_WIDTH
    mock_sprite.rect.height = TEST_MENU_ITEM_HEIGHT
    mock_sprite.image = mocker.Mock()
    mock_sprite.add = mocker.Mock()
    mock_sprite.callbacks = {}
    mock_sprite.active = False

    if has_menu_items:
        sub_item = mocker.Mock()
        sub_item.name = 'SubItem'
        mock_sprite.menu_items = {sub_item.name: sub_item}
    else:
        mock_sprite.menu_items = {}

    return mock_sprite


class TestMenuBarMouseEnterEvent:
    """Test MenuBar.on_mouse_enter_event() with collided sprites."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_mouse_enter_sets_focus(self, mocker):
        """Test that on_mouse_enter_event sets has_focus to True."""
        menubar = _create_menubar(mocker)
        event = mocker.Mock()
        event.pos = (50, 25)

        mocker.patch('pygame.sprite.spritecollide', return_value=[])

        menubar.on_mouse_enter_event(event)
        assert menubar.has_focus is True

    def test_mouse_enter_with_collided_menu_item(self, mocker):
        """Test mouse enter triggers on_mouse_enter_event on collided menu items."""
        menubar = _create_menubar(mocker)
        mock_menu_item = _create_mock_menu_item_sprite(mocker, name='FileMenu')

        # Register the item in menubar's menu_items so the name check passes
        menubar.menu_items['FileMenu'] = mock_menu_item

        event = mocker.Mock()
        event.pos = (50, 25)

        mocker.patch('pygame.sprite.spritecollide', return_value=[mock_menu_item])

        menubar.on_mouse_enter_event(event)

        mock_menu_item.on_mouse_enter_event.assert_called_once_with(event)
        assert menubar.has_focus is True

    def test_mouse_enter_propagates_to_sub_menu_items(self, mocker):
        """Test mouse enter propagates to sub menu items of collided sprite."""
        menubar = _create_menubar(mocker)
        sub_item = mocker.Mock()
        sub_item.name = 'NewFile'
        mock_menu_item = _create_mock_menu_item_sprite(mocker, name='FileMenu')
        mock_menu_item.menu_items = {'NewFile': sub_item}

        menubar.menu_items['FileMenu'] = mock_menu_item

        event = mocker.Mock()
        event.pos = (50, 25)

        mocker.patch('pygame.sprite.spritecollide', return_value=[mock_menu_item])

        menubar.on_mouse_enter_event(event)

        sub_item.on_mouse_enter_event.assert_called_once_with(event)

    def test_mouse_enter_ignores_non_registered_sprites(self, mocker):
        """Test mouse enter ignores sprites not in menu_items dict."""
        menubar = _create_menubar(mocker)
        unregistered_sprite = mocker.Mock()
        unregistered_sprite.name = 'UnknownSprite'

        event = mocker.Mock()
        event.pos = (50, 25)

        mocker.patch('pygame.sprite.spritecollide', return_value=[unregistered_sprite])

        menubar.on_mouse_enter_event(event)

        # The unregistered sprite should not have its event called
        unregistered_sprite.on_mouse_enter_event.assert_not_called()
        assert menubar.has_focus is True


class TestMenuBarMouseExitEvent:
    """Test MenuBar.on_mouse_exit_event()."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_mouse_exit_clears_focus(self, mocker):
        """Test that on_mouse_exit_event clears has_focus."""
        menubar = _create_menubar(mocker)
        menubar.has_focus = True

        event = mocker.Mock()
        event.pos = (50, 25)

        mocker.patch('pygame.sprite.spritecollide', return_value=[])

        menubar.on_mouse_exit_event(event)
        assert menubar.has_focus is False

    def test_mouse_exit_with_collided_menu_item(self, mocker):
        """Test mouse exit triggers on_mouse_exit_event on collided menu items."""
        menubar = _create_menubar(mocker)
        mock_menu_item = _create_mock_menu_item_sprite(mocker, name='FileMenu')
        menubar.menu_items['FileMenu'] = mock_menu_item

        event = mocker.Mock()
        event.pos = (50, 25)

        mocker.patch('pygame.sprite.spritecollide', return_value=[mock_menu_item])

        menubar.on_mouse_exit_event(event)

        mock_menu_item.on_mouse_exit_event.assert_called_once_with(event)
        assert menubar.has_focus is False

    def test_mouse_exit_propagates_to_sub_menu_items(self, mocker):
        """Test mouse exit propagates to sub menu items."""
        menubar = _create_menubar(mocker)
        sub_item = mocker.Mock()
        sub_item.name = 'NewFile'
        mock_menu_item = _create_mock_menu_item_sprite(mocker, name='FileMenu')
        mock_menu_item.menu_items = {'NewFile': sub_item}
        menubar.menu_items['FileMenu'] = mock_menu_item

        event = mocker.Mock()
        event.pos = (50, 25)

        mocker.patch('pygame.sprite.spritecollide', return_value=[mock_menu_item])

        menubar.on_mouse_exit_event(event)

        sub_item.on_mouse_exit_event.assert_called_once_with(event)


class TestMenuBarLeftMouseButtonDownEvent:
    """Test MenuBar.on_left_mouse_button_down_event()."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_button_down_with_menu_item_collision(self, mocker):
        """Test left mouse button down routes to MenuItem collisions."""
        menubar = _create_menubar(mocker)

        # Create a real MenuItem so isinstance() check passes
        groups = _RealLayeredDirty()
        real_menu_item = MenuItem(x=0, y=0, width=100, height=30, name='FileMenu', groups=groups)
        # Spy on the method to verify it was called
        mock_button_down = mocker.patch.object(real_menu_item, 'on_left_mouse_button_down_event')
        real_menu_item.menu_items = {}

        event = mocker.Mock()
        event.pos = (50, 25)

        mocker.patch('pygame.sprite.spritecollide', return_value=[real_menu_item])

        menubar.on_left_mouse_button_down_event(event)

        mock_button_down.assert_called_once_with(event)

    def test_button_down_propagates_to_sub_items(self, mocker):
        """Test button down propagates to sub menu items."""
        menubar = _create_menubar(mocker)

        sub_item = mocker.Mock()
        sub_item.name = 'NewFile'

        groups = _RealLayeredDirty()
        real_menu_item = MenuItem(x=0, y=0, width=100, height=30, name='FileMenu', groups=groups)
        real_menu_item.menu_items = {'NewFile': sub_item}

        event = mocker.Mock()
        event.pos = (50, 25)

        mocker.patch('pygame.sprite.spritecollide', return_value=[real_menu_item])

        menubar.on_left_mouse_button_down_event(event)

        # Sub items only get called if collided_sprite.name is in self.menu_items
        # (which uses MenuItem's own menu_items dict, not menubar's)
        # The source checks collided_sprite.name in self.menu_items on the sub-loop

    def test_button_down_no_collisions(self, mocker):
        """Test left mouse button down with no collisions does nothing."""
        menubar = _create_menubar(mocker)

        event = mocker.Mock()
        event.pos = (50, 25)

        mocker.patch('pygame.sprite.spritecollide', return_value=[])

        # Should not raise
        menubar.on_left_mouse_button_down_event(event)


class TestMenuBarLeftMouseButtonUpEvent:
    """Test MenuBar.on_left_mouse_button_up_event()."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_button_up_with_menu_item_collision(self, mocker):
        """Test left mouse button up routes to collided MenuItem."""
        menubar = _create_menubar(mocker)

        groups = _RealLayeredDirty()
        real_menu_item = MenuItem(x=0, y=0, width=100, height=30, name='FileMenu', groups=groups)
        real_menu_item.menu_items = {}
        mock_button_down = mocker.patch.object(real_menu_item, 'on_left_mouse_button_down_event')

        event = mocker.Mock()
        event.pos = (50, 25)

        mocker.patch('pygame.sprite.spritecollide', return_value=[real_menu_item])

        menubar.on_left_mouse_button_up_event(event)

        # MenuBar calls on_left_mouse_button_down_event on the sprite (yes, down on up)
        mock_button_down.assert_called_once_with(event)

    def test_button_up_no_collisions(self, mocker):
        """Test left mouse button up with no collisions does nothing."""
        menubar = _create_menubar(mocker)

        event = mocker.Mock()
        event.pos = (50, 25)

        mocker.patch('pygame.sprite.spritecollide', return_value=[])

        # Should not raise
        menubar.on_left_mouse_button_up_event(event)


class TestMenuItemMouseMotionEvent:
    """Test MenuItem.on_mouse_motion_event()."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_motion_event_with_no_collisions(self, mocker):
        """Test mouse motion event with no collisions clears focus."""
        groups = _RealLayeredDirty()
        menu_item = MenuItem(x=0, y=0, width=100, height=30, name='FileMenu', groups=groups)

        event = mocker.Mock()
        event.pos = (50, 15)

        mocker.patch('pygame.sprite.spritecollide', return_value=[])

        menu_item.on_mouse_motion_event(event)
        assert menu_item.has_focus is False

    def test_motion_event_with_collided_sub_item(self, mocker):
        """Test mouse motion triggers on_mouse_motion_event on collided sub items."""
        groups = _RealLayeredDirty()
        menu_item = MenuItem(x=0, y=0, width=100, height=30, name='FileMenu', groups=groups)

        collided_sprite = mocker.Mock()
        collided_sprite.name = 'NewFile'
        # Empty sub-menu so the inner loop (which iterates dict keys) is a no-op
        collided_sprite.menu_items = {}
        menu_item.menu_items['NewFile'] = collided_sprite

        event = mocker.Mock()
        event.pos = (50, 15)

        mocker.patch('pygame.sprite.spritecollide', return_value=[collided_sprite])

        menu_item.on_mouse_motion_event(event)

        collided_sprite.on_mouse_motion_event.assert_called_once_with(event)


class TestMenuItemMouseEnterEvent:
    """Test MenuItem.on_mouse_enter_event()."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_enter_sets_focus(self, mocker):
        """Test mouse enter sets has_focus on MenuItem."""
        groups = _RealLayeredDirty()
        menu_item = MenuItem(x=0, y=0, width=100, height=30, name='FileMenu', groups=groups)

        event = mocker.Mock()
        event.pos = (50, 15)

        mocker.patch('pygame.sprite.spritecollide', return_value=[])

        menu_item.on_mouse_enter_event(event)
        assert menu_item.has_focus is True

    def test_enter_calls_enter_on_collided_sub_item(self, mocker):
        """Test mouse enter calls on_mouse_enter_event on collided sub items."""
        groups = _RealLayeredDirty()
        menu_item = MenuItem(x=0, y=0, width=100, height=30, name='FileMenu', groups=groups)

        sub_item = mocker.Mock()
        sub_item.name = 'NewFile'
        # Empty sub-menu items so the inner loop is a no-op
        sub_item.menu_items = {}
        menu_item.menu_items['NewFile'] = sub_item

        event = mocker.Mock()
        event.pos = (50, 15)

        mocker.patch('pygame.sprite.spritecollide', return_value=[sub_item])

        menu_item.on_mouse_enter_event(event)

        sub_item.on_mouse_enter_event.assert_called_once_with(event)


class TestMenuItemMouseExitEvent:
    """Test MenuItem.on_mouse_exit_event()."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_exit_clears_focus(self, mocker):
        """Test mouse exit clears has_focus and sets dirty."""
        groups = _RealLayeredDirty()
        menu_item = MenuItem(x=0, y=0, width=100, height=30, name='FileMenu', groups=groups)
        menu_item.has_focus = True

        event = mocker.Mock()
        event.pos = (50, 15)

        mocker.patch('pygame.sprite.spritecollide', return_value=[])

        menu_item.on_mouse_exit_event(event)
        assert menu_item.has_focus is False
        assert menu_item.dirty == 1

    def test_exit_calls_exit_on_collided_sub_item(self, mocker):
        """Test mouse exit calls on_mouse_exit_event on collided sub items."""
        groups = _RealLayeredDirty()
        menu_item = MenuItem(x=0, y=0, width=100, height=30, name='FileMenu', groups=groups)

        sub_item = mocker.Mock()
        sub_item.name = 'NewFile'
        # Empty sub-menu items so the inner loop is a no-op
        sub_item.menu_items = {}
        menu_item.menu_items['NewFile'] = sub_item

        event = mocker.Mock()
        event.pos = (50, 15)

        mocker.patch('pygame.sprite.spritecollide', return_value=[sub_item])

        menu_item.on_mouse_exit_event(event)

        sub_item.on_mouse_exit_event.assert_called_once_with(event)


class TestMenuItemLeftMouseButtonUpEvent:
    """Test MenuItem.on_left_mouse_button_up_event()."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_button_up_restores_up_image(self, mocker):
        """Test button up restores menu_up_image and deactivates."""
        groups = _RealLayeredDirty()
        menu_item = MenuItem(x=0, y=0, width=100, height=30, name='FileMenu', groups=groups)
        original_up_image = menu_item.menu_up_image

        event = mocker.Mock()
        event.pos = (50, 15)

        mocker.patch('pygame.sprite.spritecollide', return_value=[])
        mocker.patch('pygame.event.post')

        menu_item.on_left_mouse_button_up_event(event)

        assert menu_item.image == original_up_image
        assert menu_item.active == 0
        assert menu_item.dirty == 2

    def test_button_up_invokes_callback(self, mocker):
        """Test button up invokes on_menu_item_event callback when present."""
        groups = _RealLayeredDirty()
        menu_item = MenuItem(x=0, y=0, width=100, height=30, name='FileMenu', groups=groups)

        callback = mocker.Mock()

        # Use a real MenuItem so isinstance() check passes
        collided_groups = _RealLayeredDirty()
        collided_item = MenuItem(
            x=0,
            y=0,
            width=100,
            height=30,
            name='NewFile',
            groups=collided_groups,
        )
        collided_item.callbacks = {'on_menu_item_event': callback}
        collided_item.menu_items = {}

        event = mocker.Mock()
        event.pos = (50, 15)

        mocker.patch('pygame.sprite.spritecollide', return_value=[collided_item])
        mocker.patch('pygame.event.post')

        menu_item.on_left_mouse_button_up_event(event)

        callback.assert_called_once_with(menu_item, event)

    def test_button_up_posts_menu_event(self, mocker):
        """Test button up posts a MENUEVENT to pygame event system."""
        groups = _RealLayeredDirty()
        menu_item = MenuItem(x=0, y=0, width=100, height=30, name='FileMenu', groups=groups)

        # Use a real MenuItem so isinstance() check passes
        collided_groups = _RealLayeredDirty()
        collided_item = MenuItem(
            x=0,
            y=0,
            width=100,
            height=30,
            name='NewFile',
            groups=collided_groups,
        )
        collided_item.callbacks = {}
        collided_item.menu_items = {}

        event = mocker.Mock()
        event.pos = (50, 15)

        mocker.patch('pygame.sprite.spritecollide', return_value=[collided_item])
        mock_post = mocker.patch('pygame.event.post')

        menu_item.on_left_mouse_button_up_event(event)

        mock_post.assert_called_once()


class TestMenuItemLeftMouseButtonDownEvent:
    """Test MenuItem.on_left_mouse_button_down_event()."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker, mock_pygame_patches):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_button_down_sets_down_image_and_activates(self, mocker):
        """Test button down switches to menu_down_image and activates."""
        groups = _RealLayeredDirty()
        menu_item = MenuItem(x=0, y=0, width=100, height=30, name='FileMenu', groups=groups)

        event = mocker.Mock()
        event.pos = (50, 15)

        mocker.patch('pygame.sprite.spritecollide', return_value=[])

        menu_item.on_left_mouse_button_down_event(event)

        assert menu_item.active == 1
        assert menu_item.dirty == 2

    def test_button_down_propagates_to_collided_sub_items(self, mocker):
        """Test button down propagates to collided sub menu items."""
        groups = _RealLayeredDirty()
        menu_item = MenuItem(x=0, y=0, width=100, height=30, name='FileMenu', groups=groups)

        sub_item = mocker.Mock()
        sub_item.name = 'NewFile'
        menu_item.menu_items['NewFile'] = sub_item

        event = mocker.Mock()
        event.pos = (50, 15)

        mocker.patch('pygame.sprite.spritecollide', return_value=[sub_item])

        menu_item.on_left_mouse_button_down_event(event)

        sub_item.on_left_mouse_button_down_event.assert_called_once_with(event)
