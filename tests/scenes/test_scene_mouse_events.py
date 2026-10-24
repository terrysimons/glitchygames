"""Tests for Scene mouse event handler behaviors.

Focuses on verifying that mouse event handlers deliver each event to the sprites under the
pointer: real sprites in the scene's real sprite group, found by the scene's real collision
check (sprites_at_position), receiving real mouse events.
"""

import pygame

from glitchygames import events
from glitchygames.scenes import Scene

# Every scene mouse handler that hands the event on to sprites
SPRITE_MOUSE_HANDLERS = (
    'on_mouse_drag_event',
    'on_mouse_drop_event',
    'on_left_mouse_drag_event',
    'on_left_mouse_drop_event',
    'on_middle_mouse_drag_event',
    'on_middle_mouse_drop_event',
    'on_right_mouse_drag_event',
    'on_right_mouse_drop_event',
    'on_left_mouse_button_up_event',
    'on_middle_mouse_button_up_event',
    'on_right_mouse_button_up_event',
    'on_middle_mouse_button_down_event',
    'on_right_mouse_button_down_event',
    'on_left_mouse_button_down_event',
    'on_mouse_button_down_event',
)


class MouseSprite(pygame.sprite.DirtySprite):
    """A real sprite that records every mouse handler call it receives, in order."""

    def __init__(self, *, rect: tuple[int, int, int, int], layer: int = 0):
        """Make a sprite covering rect on the given layer."""
        super().__init__()
        self.image = pygame.Surface(rect[2:])
        self.rect = pygame.Rect(rect)
        self._layer = layer
        self.received: list[tuple[str, tuple[object, ...]]] = []


def _make_recorder(handler_name: str):
    """Return a MouseSprite method that records calls to handler_name.

    Returns:
        Callable: The method.

    """

    def record(self, *arguments):
        self.received.append((handler_name, arguments))

    record.__name__ = handler_name
    record.__doc__ = f'Record the {handler_name} call.'
    return record


for _handler_name in SPRITE_MOUSE_HANDLERS:
    setattr(MouseSprite, _handler_name, _make_recorder(_handler_name))


class FocusedSprite(pygame.sprite.DirtySprite):
    """A real sprite holding focus, far from every click in these tests."""

    def __init__(self):
        """Make a focused 4x4 sprite in the bottom-right corner."""
        super().__init__()
        self.image = pygame.Surface((4, 4))
        self.rect = pygame.Rect(790, 590, 4, 4)
        self.is_active = True
        self.focus_lost_count = 0

    def on_focus_lost(self):
        """Count the focus loss."""
        self.focus_lost_count += 1


class SpriteWithoutHandlers(pygame.sprite.DirtySprite):
    """A real sprite with no mouse handlers at all."""

    def __init__(self, *, rect: tuple[int, int, int, int]):
        """Make a sprite covering rect."""
        super().__init__()
        self.image = pygame.Surface(rect[2:])
        self.rect = pygame.Rect(rect)


def _mouse_event(pos: tuple[int, int], *, button: int = 1) -> events.HashableEvent:
    """Return a real mouse-button event at pos.

    Returns:
        events.HashableEvent: The event.

    """
    return events.HashableEvent(pygame.MOUSEBUTTONDOWN, pos=pos, button=button)


def _sprite_around(pos: tuple[int, int], *, layer: int = 0) -> MouseSprite:
    """Return a 20x20 MouseSprite centred on pos.

    Returns:
        MouseSprite: The sprite.

    """
    return MouseSprite(rect=(pos[0] - 10, pos[1] - 10, 20, 20), layer=layer)


def _sprite_elsewhere() -> MouseSprite:
    """Return a MouseSprite in the top-left corner, away from every test position.

    Returns:
        MouseSprite: The sprite.

    """
    return MouseSprite(rect=(0, 0, 10, 10))


class TestOnMouseDragEvent:
    """Test Scene.on_mouse_drag_event() behavior."""

    def test_only_sprites_under_the_pointer_receive_it(self):
        """A sprite under the pointer receives the event and its trigger; one elsewhere not."""
        scene = Scene()
        under_sprite = _sprite_around((50, 50))
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(under_sprite, elsewhere_sprite)
        event = _mouse_event((50, 50))
        trigger = _mouse_event((50, 50))

        scene.on_mouse_drag_event(event, trigger)

        assert under_sprite.received == [('on_mouse_drag_event', (event, trigger))]
        assert elsewhere_sprite.received == []

    def test_delegates_to_multiple_collided_sprites(self):
        """Every sprite under the pointer receives the event."""
        scene = Scene()
        first_sprite = _sprite_around((50, 50))
        second_sprite = _sprite_around((50, 50), layer=1)
        scene.all_sprites.add(first_sprite, second_sprite)
        event = _mouse_event((50, 50))
        trigger = _mouse_event((50, 50))

        scene.on_mouse_drag_event(event, trigger)

        assert first_sprite.received == [('on_mouse_drag_event', (event, trigger))]
        assert second_sprite.received == [('on_mouse_drag_event', (event, trigger))]

    def test_no_error_with_no_collided_sprites(self):
        """Nothing under the pointer: nobody receives the event, and nothing raises."""
        scene = Scene()
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(elsewhere_sprite)

        scene.on_mouse_drag_event(_mouse_event((50, 50)), _mouse_event((50, 50)))

        assert elsewhere_sprite.received == []


class TestOnMouseDropEvent:
    """Test Scene.on_mouse_drop_event() behavior."""

    def test_only_sprites_under_the_pointer_receive_it(self):
        """A sprite under the pointer receives the event and its trigger; one elsewhere not."""
        scene = Scene()
        under_sprite = _sprite_around((100, 200))
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(under_sprite, elsewhere_sprite)
        event = _mouse_event((100, 200))
        trigger = _mouse_event((100, 200))

        scene.on_mouse_drop_event(event, trigger)

        assert under_sprite.received == [('on_mouse_drop_event', (event, trigger))]
        assert elsewhere_sprite.received == []

    def test_delegates_to_multiple_collided_sprites(self):
        """Every sprite under the pointer receives the event."""
        scene = Scene()
        first_sprite = _sprite_around((100, 200))
        second_sprite = _sprite_around((100, 200), layer=1)
        scene.all_sprites.add(first_sprite, second_sprite)
        event = _mouse_event((100, 200))
        trigger = _mouse_event((100, 200))

        scene.on_mouse_drop_event(event, trigger)

        assert first_sprite.received == [('on_mouse_drop_event', (event, trigger))]
        assert second_sprite.received == [('on_mouse_drop_event', (event, trigger))]

    def test_no_error_with_no_collided_sprites(self):
        """Nothing under the pointer: nobody receives the event, and nothing raises."""
        scene = Scene()
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(elsewhere_sprite)

        scene.on_mouse_drop_event(_mouse_event((100, 200)), _mouse_event((100, 200)))

        assert elsewhere_sprite.received == []


class TestOnLeftMouseDragEvent:
    """Test Scene.on_left_mouse_drag_event() behavior."""

    def test_only_sprites_under_the_pointer_receive_it(self):
        """A sprite under the pointer receives the event and its trigger; one elsewhere not."""
        scene = Scene()
        under_sprite = _sprite_around((50, 50))
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(under_sprite, elsewhere_sprite)
        event = _mouse_event((50, 50))
        trigger = _mouse_event((50, 50))

        scene.on_left_mouse_drag_event(event, trigger)

        assert under_sprite.received == [('on_left_mouse_drag_event', (event, trigger))]
        assert elsewhere_sprite.received == []

    def test_delegates_to_top_sprite_only(self):
        """Only the top sprite under the pointer (highest layer) receives it."""
        scene = Scene()
        top_sprite = _sprite_around((50, 50), layer=2)
        bottom_sprite = _sprite_around((50, 50), layer=1)
        scene.all_sprites.add(top_sprite, bottom_sprite)
        event = _mouse_event((50, 50))
        trigger = _mouse_event((50, 50))

        scene.on_left_mouse_drag_event(event, trigger)

        assert top_sprite.received == [('on_left_mouse_drag_event', (event, trigger))]
        assert bottom_sprite.received == []

    def test_no_error_with_no_collided_sprites(self):
        """Nothing under the pointer: nobody receives the event, and nothing raises."""
        scene = Scene()
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(elsewhere_sprite)

        scene.on_left_mouse_drag_event(_mouse_event((50, 50)), _mouse_event((50, 50)))

        assert elsewhere_sprite.received == []


class TestOnLeftMouseDropEvent:
    """Test Scene.on_left_mouse_drop_event() behavior."""

    def test_only_sprites_under_the_pointer_receive_it(self):
        """A sprite under the pointer receives the event and its trigger; one elsewhere not."""
        scene = Scene()
        under_sprite = _sprite_around((150, 250))
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(under_sprite, elsewhere_sprite)
        event = _mouse_event((150, 250))
        trigger = _mouse_event((150, 250))

        scene.on_left_mouse_drop_event(event, trigger)

        assert under_sprite.received == [('on_left_mouse_drop_event', (event, trigger))]
        assert elsewhere_sprite.received == []

    def test_delegates_to_multiple_collided_sprites(self):
        """Every sprite under the pointer receives the event."""
        scene = Scene()
        first_sprite = _sprite_around((150, 250))
        second_sprite = _sprite_around((150, 250), layer=1)
        scene.all_sprites.add(first_sprite, second_sprite)
        event = _mouse_event((150, 250))
        trigger = _mouse_event((150, 250))

        scene.on_left_mouse_drop_event(event, trigger)

        assert first_sprite.received == [('on_left_mouse_drop_event', (event, trigger))]
        assert second_sprite.received == [('on_left_mouse_drop_event', (event, trigger))]

    def test_no_error_with_no_collided_sprites(self):
        """Nothing under the pointer: nobody receives the event, and nothing raises."""
        scene = Scene()
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(elsewhere_sprite)

        scene.on_left_mouse_drop_event(_mouse_event((150, 250)), _mouse_event((150, 250)))

        assert elsewhere_sprite.received == []


class TestOnMiddleMouseDragEvent:
    """Test Scene.on_middle_mouse_drag_event() behavior."""

    def test_only_sprites_under_the_pointer_receive_it(self):
        """A sprite under the pointer receives the event and its trigger; one elsewhere not."""
        scene = Scene()
        under_sprite = _sprite_around((200, 300))
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(under_sprite, elsewhere_sprite)
        event = _mouse_event((200, 300))
        trigger = _mouse_event((200, 300))

        scene.on_middle_mouse_drag_event(event, trigger)

        assert under_sprite.received == [('on_middle_mouse_drag_event', (event, trigger))]
        assert elsewhere_sprite.received == []

    def test_delegates_to_multiple_collided_sprites(self):
        """Every sprite under the pointer receives the event."""
        scene = Scene()
        first_sprite = _sprite_around((200, 300))
        second_sprite = _sprite_around((200, 300), layer=1)
        scene.all_sprites.add(first_sprite, second_sprite)
        event = _mouse_event((200, 300))
        trigger = _mouse_event((200, 300))

        scene.on_middle_mouse_drag_event(event, trigger)

        assert first_sprite.received == [('on_middle_mouse_drag_event', (event, trigger))]
        assert second_sprite.received == [('on_middle_mouse_drag_event', (event, trigger))]

    def test_no_error_with_no_collided_sprites(self):
        """Nothing under the pointer: nobody receives the event, and nothing raises."""
        scene = Scene()
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(elsewhere_sprite)

        scene.on_middle_mouse_drag_event(_mouse_event((200, 300)), _mouse_event((200, 300)))

        assert elsewhere_sprite.received == []


class TestOnMiddleMouseDropEvent:
    """Test Scene.on_middle_mouse_drop_event() behavior."""

    def test_only_sprites_under_the_pointer_receive_it(self):
        """A sprite under the pointer receives the event and its trigger; one elsewhere not."""
        scene = Scene()
        under_sprite = _sprite_around((200, 300))
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(under_sprite, elsewhere_sprite)
        event = _mouse_event((200, 300))
        trigger = _mouse_event((200, 300))

        scene.on_middle_mouse_drop_event(event, trigger)

        assert under_sprite.received == [('on_middle_mouse_drop_event', (event, trigger))]
        assert elsewhere_sprite.received == []

    def test_delegates_to_multiple_collided_sprites(self):
        """Every sprite under the pointer receives the event."""
        scene = Scene()
        first_sprite = _sprite_around((200, 300))
        second_sprite = _sprite_around((200, 300), layer=1)
        scene.all_sprites.add(first_sprite, second_sprite)
        event = _mouse_event((200, 300))
        trigger = _mouse_event((200, 300))

        scene.on_middle_mouse_drop_event(event, trigger)

        assert first_sprite.received == [('on_middle_mouse_drop_event', (event, trigger))]
        assert second_sprite.received == [('on_middle_mouse_drop_event', (event, trigger))]

    def test_no_error_with_no_collided_sprites(self):
        """Nothing under the pointer: nobody receives the event, and nothing raises."""
        scene = Scene()
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(elsewhere_sprite)

        scene.on_middle_mouse_drop_event(_mouse_event((200, 300)), _mouse_event((200, 300)))

        assert elsewhere_sprite.received == []


class TestOnRightMouseDragEvent:
    """Test Scene.on_right_mouse_drag_event() behavior."""

    def test_only_sprites_under_the_pointer_receive_it(self):
        """A sprite under the pointer receives the event and its trigger; one elsewhere not."""
        scene = Scene()
        under_sprite = _sprite_around((300, 400))
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(under_sprite, elsewhere_sprite)
        event = _mouse_event((300, 400))
        trigger = _mouse_event((300, 400))

        scene.on_right_mouse_drag_event(event, trigger)

        assert under_sprite.received == [('on_right_mouse_drag_event', (event, trigger))]
        assert elsewhere_sprite.received == []

    def test_delegates_to_multiple_collided_sprites(self):
        """Every sprite under the pointer receives the event."""
        scene = Scene()
        first_sprite = _sprite_around((300, 400))
        second_sprite = _sprite_around((300, 400), layer=1)
        scene.all_sprites.add(first_sprite, second_sprite)
        event = _mouse_event((300, 400))
        trigger = _mouse_event((300, 400))

        scene.on_right_mouse_drag_event(event, trigger)

        assert first_sprite.received == [('on_right_mouse_drag_event', (event, trigger))]
        assert second_sprite.received == [('on_right_mouse_drag_event', (event, trigger))]

    def test_no_error_with_no_collided_sprites(self):
        """Nothing under the pointer: nobody receives the event, and nothing raises."""
        scene = Scene()
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(elsewhere_sprite)

        scene.on_right_mouse_drag_event(_mouse_event((300, 400)), _mouse_event((300, 400)))

        assert elsewhere_sprite.received == []


class TestOnRightMouseDropEvent:
    """Test Scene.on_right_mouse_drop_event() behavior."""

    def test_only_sprites_under_the_pointer_receive_it(self):
        """A sprite under the pointer receives the event and its trigger; one elsewhere not."""
        scene = Scene()
        under_sprite = _sprite_around((300, 400))
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(under_sprite, elsewhere_sprite)
        event = _mouse_event((300, 400))
        trigger = _mouse_event((300, 400))

        scene.on_right_mouse_drop_event(event, trigger)

        assert under_sprite.received == [('on_right_mouse_drop_event', (event, trigger))]
        assert elsewhere_sprite.received == []

    def test_delegates_to_multiple_collided_sprites(self):
        """Every sprite under the pointer receives the event."""
        scene = Scene()
        first_sprite = _sprite_around((300, 400))
        second_sprite = _sprite_around((300, 400), layer=1)
        scene.all_sprites.add(first_sprite, second_sprite)
        event = _mouse_event((300, 400))
        trigger = _mouse_event((300, 400))

        scene.on_right_mouse_drop_event(event, trigger)

        assert first_sprite.received == [('on_right_mouse_drop_event', (event, trigger))]
        assert second_sprite.received == [('on_right_mouse_drop_event', (event, trigger))]

    def test_no_error_with_no_collided_sprites(self):
        """Nothing under the pointer: nobody receives the event, and nothing raises."""
        scene = Scene()
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(elsewhere_sprite)

        scene.on_right_mouse_drop_event(_mouse_event((300, 400)), _mouse_event((300, 400)))

        assert elsewhere_sprite.received == []


class TestOnLeftMouseButtonUpEvent:
    """Test Scene.on_left_mouse_button_up_event() behavior."""

    def test_delegates_to_collided_sprites(self):
        """Every sprite under the pointer receives the event; one elsewhere does not."""
        scene = Scene()
        first_sprite = _sprite_around((100, 100))
        second_sprite = _sprite_around((100, 100), layer=1)
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(first_sprite, second_sprite, elsewhere_sprite)
        event = _mouse_event((100, 100))

        scene.on_left_mouse_button_up_event(event)

        assert first_sprite.received == [('on_left_mouse_button_up_event', (event,))]
        assert second_sprite.received == [('on_left_mouse_button_up_event', (event,))]
        assert elsewhere_sprite.received == []

    def test_no_error_with_no_collided_sprites(self):
        """Nothing under the pointer: nobody receives the event, and nothing raises."""
        scene = Scene()
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(elsewhere_sprite)

        scene.on_left_mouse_button_up_event(_mouse_event((100, 100)))

        assert elsewhere_sprite.received == []


class TestOnMiddleMouseButtonUpEvent:
    """Test Scene.on_middle_mouse_button_up_event() behavior."""

    def test_delegates_to_collided_sprites(self):
        """Every sprite under the pointer receives the event; one elsewhere does not."""
        scene = Scene()
        first_sprite = _sprite_around((200, 200))
        second_sprite = _sprite_around((200, 200), layer=1)
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(first_sprite, second_sprite, elsewhere_sprite)
        event = _mouse_event((200, 200))

        scene.on_middle_mouse_button_up_event(event)

        assert first_sprite.received == [('on_middle_mouse_button_up_event', (event,))]
        assert second_sprite.received == [('on_middle_mouse_button_up_event', (event,))]
        assert elsewhere_sprite.received == []

    def test_no_error_with_no_collided_sprites(self):
        """Nothing under the pointer: nobody receives the event, and nothing raises."""
        scene = Scene()
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(elsewhere_sprite)

        scene.on_middle_mouse_button_up_event(_mouse_event((200, 200)))

        assert elsewhere_sprite.received == []


class TestOnRightMouseButtonUpEvent:
    """Test Scene.on_right_mouse_button_up_event() behavior."""

    def test_delegates_to_collided_sprites(self):
        """Every sprite under the pointer receives the event; one elsewhere does not."""
        scene = Scene()
        first_sprite = _sprite_around((300, 300))
        second_sprite = _sprite_around((300, 300), layer=1)
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(first_sprite, second_sprite, elsewhere_sprite)
        event = _mouse_event((300, 300))

        scene.on_right_mouse_button_up_event(event)

        assert first_sprite.received == [('on_right_mouse_button_up_event', (event,))]
        assert second_sprite.received == [('on_right_mouse_button_up_event', (event,))]
        assert elsewhere_sprite.received == []

    def test_no_error_with_no_collided_sprites(self):
        """Nothing under the pointer: nobody receives the event, and nothing raises."""
        scene = Scene()
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(elsewhere_sprite)

        scene.on_right_mouse_button_up_event(_mouse_event((300, 300)))

        assert elsewhere_sprite.received == []


class TestOnMiddleMouseButtonDownEvent:
    """Test Scene.on_middle_mouse_button_down_event() behavior."""

    def test_delegates_to_collided_sprites(self):
        """Every sprite under the pointer receives the event; one elsewhere does not."""
        scene = Scene()
        first_sprite = _sprite_around((200, 200))
        second_sprite = _sprite_around((200, 200), layer=1)
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(first_sprite, second_sprite, elsewhere_sprite)
        event = _mouse_event((200, 200))

        scene.on_middle_mouse_button_down_event(event)

        assert first_sprite.received == [('on_middle_mouse_button_down_event', (event,))]
        assert second_sprite.received == [('on_middle_mouse_button_down_event', (event,))]
        assert elsewhere_sprite.received == []

    def test_no_error_with_no_collided_sprites(self):
        """Nothing under the pointer: nobody receives the event, and nothing raises."""
        scene = Scene()
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(elsewhere_sprite)

        scene.on_middle_mouse_button_down_event(_mouse_event((200, 200)))

        assert elsewhere_sprite.received == []


class TestOnRightMouseButtonDownEvent:
    """Test Scene.on_right_mouse_button_down_event() behavior."""

    def test_delegates_to_collided_sprites(self):
        """Every sprite under the pointer receives the event; one elsewhere does not."""
        scene = Scene()
        first_sprite = _sprite_around((300, 300))
        second_sprite = _sprite_around((300, 300), layer=1)
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(first_sprite, second_sprite, elsewhere_sprite)
        event = _mouse_event((300, 300))

        scene.on_right_mouse_button_down_event(event)

        assert first_sprite.received == [('on_right_mouse_button_down_event', (event,))]
        assert second_sprite.received == [('on_right_mouse_button_down_event', (event,))]
        assert elsewhere_sprite.received == []

    def test_no_error_with_no_collided_sprites(self):
        """Nothing under the pointer: nobody receives the event, and nothing raises."""
        scene = Scene()
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(elsewhere_sprite)

        scene.on_right_mouse_button_down_event(_mouse_event((300, 300)))

        assert elsewhere_sprite.received == []


class TestOnLeftMouseButtonDownEvent:
    """Test Scene.on_left_mouse_button_down_event() behavior."""

    def test_click_away_from_focusable_sprites_unfocuses(self):
        """A click on nothing focusable takes focus from the focused sprite."""
        scene = Scene()
        focused_sprite = FocusedSprite()
        scene.all_sprites.add(focused_sprite)

        scene.on_left_mouse_button_down_event(_mouse_event((100, 100)))

        assert focused_sprite.is_active is False
        assert focused_sprite.focus_lost_count == 1

    def test_click_on_a_focusable_sprite_keeps_focus(self):
        """A click on a focusable sprite leaves the focused sprite focused (it takes focus)."""
        scene = Scene()
        focused_sprite = FocusedSprite()
        focusable_sprite = _sprite_around((100, 100))
        focusable_sprite.focusable = True
        scene.all_sprites.add(focused_sprite, focusable_sprite)

        scene.on_left_mouse_button_down_event(_mouse_event((100, 100)))

        assert focused_sprite.is_active is True
        assert focused_sprite.focus_lost_count == 0

    def test_delegates_to_sprites_with_handler(self):
        """The sprite under the pointer receives the click."""
        scene = Scene()
        clicked_sprite = _sprite_around((100, 100))
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(clicked_sprite, elsewhere_sprite)
        event = _mouse_event((100, 100))

        scene.on_left_mouse_button_down_event(event)

        assert clicked_sprite.received == [('on_left_mouse_button_down_event', (event,))]
        assert elsewhere_sprite.received == []

    def test_skips_sprites_without_handler(self):
        """A sprite under the pointer without the handler is skipped; the others still get it."""
        scene = Scene()
        plain_sprite = SpriteWithoutHandlers(rect=(90, 90, 20, 20))
        clicked_sprite = _sprite_around((100, 100), layer=1)
        scene.all_sprites.add(plain_sprite, clicked_sprite)
        event = _mouse_event((100, 100))

        # Should not raise even though one sprite lacks the handler
        scene.on_left_mouse_button_down_event(event)

        assert clicked_sprite.received == [('on_left_mouse_button_down_event', (event,))]


class TestOnMouseButtonDownEvent:
    """Test Scene.on_mouse_button_down_event() behavior."""

    def test_click_away_from_focusable_sprites_unfocuses(self):
        """A click on nothing focusable takes focus from the focused sprite."""
        scene = Scene()
        focused_sprite = FocusedSprite()
        scene.all_sprites.add(focused_sprite)

        scene.on_mouse_button_down_event(_mouse_event((100, 100)))

        assert focused_sprite.is_active is False
        assert focused_sprite.focus_lost_count == 1

    def test_click_on_a_focusable_sprite_keeps_focus(self):
        """A click on a focusable sprite leaves the focused sprite focused (it takes focus)."""
        scene = Scene()
        focused_sprite = FocusedSprite()
        focusable_sprite = _sprite_around((100, 100))
        focusable_sprite.focusable = True
        scene.all_sprites.add(focused_sprite, focusable_sprite)

        scene.on_mouse_button_down_event(_mouse_event((100, 100)))

        assert focused_sprite.is_active is True
        assert focused_sprite.focus_lost_count == 0

    def test_delegates_to_sprites_with_handler(self):
        """The sprite under the pointer receives the click."""
        scene = Scene()
        clicked_sprite = _sprite_around((100, 100))
        elsewhere_sprite = _sprite_elsewhere()
        scene.all_sprites.add(clicked_sprite, elsewhere_sprite)
        event = _mouse_event((100, 100))

        scene.on_mouse_button_down_event(event)

        assert clicked_sprite.received == [('on_mouse_button_down_event', (event,))]
        assert elsewhere_sprite.received == []

    def test_skips_sprites_without_handler(self):
        """A sprite under the pointer without the handler is skipped; the others still get it."""
        scene = Scene()
        plain_sprite = SpriteWithoutHandlers(rect=(90, 90, 20, 20))
        clicked_sprite = _sprite_around((100, 100), layer=1)
        scene.all_sprites.add(plain_sprite, clicked_sprite)
        event = _mouse_event((100, 100))

        # Should not raise even though one sprite lacks the handler
        scene.on_mouse_button_down_event(event)

        assert clicked_sprite.received == [('on_mouse_button_down_event', (event,))]
