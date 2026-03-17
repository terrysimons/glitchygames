"""Tests for glitchygames.events.mouse module - MouseEventManager and MousePointer."""

import pygame
import pytest

from glitchygames.events.mouse import (
    MOUSE_BUTTON_LEFT,
    MOUSE_BUTTON_RIGHT,
    MOUSE_BUTTON_WHEEL,
    MOUSE_WHEEL_SCROLL_DOWN,
    MOUSE_WHEEL_SCROLL_UP,
    MouseEventManager,
    MousePointer,
    collided_sprites,
)


@pytest.fixture
def mock_game(mocker):
    """Create a mock game object with all required event handlers."""
    game = mocker.Mock()
    game.all_sprites = pygame.sprite.Group()
    return game


class TestMousePointer:
    """Test MousePointer class."""

    def test_init(self):
        pointer = MousePointer(pos=(100, 200))
        assert pointer.x == 100
        assert pointer.y == 200

    def test_init_with_size(self):
        pointer = MousePointer(pos=(50, 75), size=(2, 2))
        assert pointer.size == (2, 2)

    def test_x_property(self):
        pointer = MousePointer(pos=(100, 200))
        assert pointer.x == 100

    def test_x_setter(self):
        pointer = MousePointer(pos=(100, 200))
        pointer.x = 300
        assert pointer.x == 300
        assert pointer.pos[0] == 300

    def test_y_property(self):
        pointer = MousePointer(pos=(100, 200))
        assert pointer.y == 200

    def test_y_setter(self):
        pointer = MousePointer(pos=(100, 200))
        pointer.y = 400
        assert pointer.y == 400
        assert pointer.pos[1] == 400

    def test_rect_created(self):
        pointer = MousePointer(pos=(10, 20))
        assert isinstance(pointer.rect, pygame.Rect)
        assert pointer.rect.x == 10
        assert pointer.rect.y == 20


class TestMouseEventProxy:
    """Test MouseEventProxy event delegation."""

    def test_proxy_init(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        assert proxy.game is mock_game
        assert proxy.mouse_dragging is False
        assert proxy.mouse_dropping is False
        assert proxy.current_focus is None
        assert proxy.previous_focus is None

    def test_on_mouse_button_down_left(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=MOUSE_BUTTON_LEFT,
            pos=(100, 200),
        )
        proxy.on_mouse_button_down_event(event)
        mock_game.on_mouse_button_down_event.assert_called_once()
        mock_game.on_left_mouse_button_down_event.assert_called_once()

    def test_on_mouse_button_down_right(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=MOUSE_BUTTON_RIGHT,
            pos=(100, 200),
        )
        proxy.on_mouse_button_down_event(event)
        mock_game.on_right_mouse_button_down_event.assert_called_once()

    def test_on_mouse_button_down_middle(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=MOUSE_BUTTON_WHEEL,
            pos=(100, 200),
        )
        proxy.on_mouse_button_down_event(event)
        mock_game.on_middle_mouse_button_down_event.assert_called_once()

    def test_on_mouse_button_down_scroll_up(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=MOUSE_WHEEL_SCROLL_UP,
            pos=(100, 200),
        )
        proxy.on_mouse_button_down_event(event)
        mock_game.on_mouse_scroll_down_event.assert_called_once()

    def test_on_mouse_button_down_scroll_down(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            button=MOUSE_WHEEL_SCROLL_DOWN,
            pos=(100, 200),
        )
        proxy.on_mouse_button_down_event(event)
        mock_game.on_mouse_scroll_up_event.assert_called_once()

    def test_on_mouse_button_up_left(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = pygame.event.Event(
            pygame.MOUSEBUTTONUP,
            button=MOUSE_BUTTON_LEFT,
            pos=(100, 200),
        )
        proxy.on_mouse_button_up_event(event)
        mock_game.on_left_mouse_button_up_event.assert_called_once()
        mock_game.on_mouse_button_up_event.assert_called_once()

    def test_on_mouse_button_up_right(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = pygame.event.Event(
            pygame.MOUSEBUTTONUP,
            button=MOUSE_BUTTON_RIGHT,
            pos=(100, 200),
        )
        proxy.on_mouse_button_up_event(event)
        mock_game.on_right_mouse_button_up_event.assert_called_once()

    def test_on_mouse_button_up_middle(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = pygame.event.Event(
            pygame.MOUSEBUTTONUP,
            button=MOUSE_BUTTON_WHEEL,
            pos=(100, 200),
        )
        proxy.on_mouse_button_up_event(event)
        mock_game.on_middle_mouse_button_up_event.assert_called_once()

    def test_on_mouse_button_up_triggers_drop_if_dragging(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        proxy.mouse_dragging = True
        event = pygame.event.Event(
            pygame.MOUSEBUTTONUP,
            button=MOUSE_BUTTON_LEFT,
            pos=(100, 200),
        )
        proxy.on_mouse_button_up_event(event)
        mock_game.on_mouse_drop_event.assert_called_once()
        assert proxy.mouse_dragging is False

    def test_on_mouse_wheel_event(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=1)
        proxy.on_mouse_wheel_event(event)
        mock_game.on_mouse_wheel_event.assert_called_once()

    def test_on_mouse_drag_event_left(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        motion_event = pygame.event.Event(
            pygame.MOUSEMOTION, pos=(150, 250), rel=(5, 5), buttons=(1, 0, 0)
        )
        trigger = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=MOUSE_BUTTON_LEFT, pos=(100, 200)
        )
        proxy.on_mouse_drag_event(motion_event, trigger)
        mock_game.on_mouse_drag_event.assert_called_once()
        mock_game.on_left_mouse_drag_event.assert_called_once()

    def test_on_mouse_drag_event_right(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        motion_event = pygame.event.Event(
            pygame.MOUSEMOTION, pos=(150, 250), rel=(5, 5), buttons=(0, 0, 1)
        )
        trigger = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=MOUSE_BUTTON_RIGHT, pos=(100, 200)
        )
        proxy.on_mouse_drag_event(motion_event, trigger)
        mock_game.on_right_mouse_drag_down_event.assert_called_once()

    def test_on_mouse_drag_event_middle(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        motion_event = pygame.event.Event(
            pygame.MOUSEMOTION, pos=(150, 250), rel=(5, 5), buttons=(0, 1, 0)
        )
        trigger = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=MOUSE_BUTTON_WHEEL, pos=(100, 200)
        )
        proxy.on_mouse_drag_event(motion_event, trigger)
        mock_game.on_middle_mouse_drag_down_event.assert_called_once()

    def test_on_mouse_drop_event_left(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = pygame.event.Event(pygame.MOUSEBUTTONUP, button=MOUSE_BUTTON_LEFT, pos=(100, 200))
        trigger = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=MOUSE_BUTTON_LEFT, pos=(90, 190)
        )
        proxy.on_mouse_drop_event(event, trigger)
        mock_game.on_mouse_drop_event.assert_called_once()
        mock_game.on_left_mouse_drag_up_event.assert_called_once()
        assert proxy.mouse_dropping is False

    def test_on_mouse_drop_event_right(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = pygame.event.Event(pygame.MOUSEBUTTONUP, button=MOUSE_BUTTON_RIGHT, pos=(100, 200))
        trigger = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=MOUSE_BUTTON_RIGHT, pos=(90, 190)
        )
        proxy.on_mouse_drop_event(event, trigger)
        mock_game.on_right_mouse_drag_up_event.assert_called_once()

    def test_on_mouse_drop_event_middle(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = pygame.event.Event(pygame.MOUSEBUTTONUP, button=MOUSE_BUTTON_WHEEL, pos=(100, 200))
        trigger = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=MOUSE_BUTTON_WHEEL, pos=(90, 190)
        )
        proxy.on_mouse_drop_event(event, trigger)
        mock_game.on_middle_mouse_drag_up_event.assert_called_once()

    def test_on_mouse_focus_event(self, mock_game, mocker):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = pygame.event.Event(
            pygame.MOUSEMOTION, pos=(100, 200), rel=(1, 1), buttons=(0, 0, 0)
        )
        mock_sprite = mocker.Mock()
        proxy.on_mouse_focus_event(event, mock_sprite)
        assert proxy.current_focus is mock_sprite

    def test_on_mouse_unfocus_event(self, mock_game, mocker):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = pygame.event.Event(
            pygame.MOUSEMOTION, pos=(100, 200), rel=(1, 1), buttons=(0, 0, 0)
        )
        mock_sprite = mocker.Mock()
        proxy.current_focus = mock_sprite
        proxy.on_mouse_unfocus_event(event, mock_sprite)
        assert proxy.current_focus is None
        assert proxy.previous_focus is mock_sprite

    def test_on_mouse_unfocus_event_none(self, mock_game):
        proxy = MouseEventManager.MouseEventProxy(game=mock_game)
        event = pygame.event.Event(
            pygame.MOUSEMOTION, pos=(100, 200), rel=(1, 1), buttons=(0, 0, 0)
        )
        proxy.on_mouse_unfocus_event(event, None)
        assert proxy.previous_focus is None


class TestMouseEventManager:
    """Test MouseEventManager initialization."""

    def test_init(self, mock_game):
        manager = MouseEventManager(game=mock_game)
        assert len(manager.proxies) == 1

    def test_args(self):
        import argparse

        parser = argparse.ArgumentParser()
        result = MouseEventManager.args(parser)
        assert result is parser


class TestCollidedSprites:
    """Test collided_sprites function."""

    def test_no_collision(self, mock_game):
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 200))
        result = collided_sprites(mock_game, event)
        assert result == []
