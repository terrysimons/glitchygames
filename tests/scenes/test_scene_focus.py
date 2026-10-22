"""Tests for Scene focus management and key handling behaviors.

Focuses on verifying _handle_focus_management, _handle_quit_key_press,
on_key_down_event, _handle_focused_sprite_events, and _handle_scene_key_events.
"""

import pygame

from glitchygames import events
from glitchygames.scenes import Scene
from glitchygames.testing.keys import qwerty_scancode


class FocusSprite(pygame.sprite.DirtySprite):
    """A real sprite that can hold focus and records the key-downs and focus losses it gets."""

    def __init__(self, *, is_active: bool = False, focusable: bool = True):
        """Make an 8x8 sprite, focused or not."""
        super().__init__()
        self.image = pygame.Surface((8, 8))
        self.rect = self.image.get_rect()
        self.is_active = is_active
        self.focusable = focusable
        self.key_down_events: list[events.HashableEvent] = []
        self.focus_lost_count = 0

    def on_key_down_event(self, event):
        """Record the key-down."""
        self.key_down_events.append(event)

    def on_focus_lost(self):
        """Count the focus loss."""
        self.focus_lost_count += 1


class ActiveSpriteWithoutKeyHandler(pygame.sprite.DirtySprite):
    """A real, active sprite with no on_key_down_event and nothing focusable."""

    def __init__(self):
        """Make an active 8x8 sprite."""
        super().__init__()
        self.image = pygame.Surface((8, 8))
        self.rect = self.image.get_rect()
        self.is_active = True


def _key_down(key: int) -> events.HashableEvent:
    """Return a real KEYDOWN event for the key, with its US QWERTY scancode.

    Returns:
        events.HashableEvent: The event.

    """
    return events.HashableEvent(
        pygame.KEYDOWN, key=key, scancode=qwerty_scancode(key=key), mod=pygame.KMOD_NONE
    )


class TestHandleFocusManagement:
    """Test Scene._handle_focus_management() behavior."""

    def test_unfocuses_sprites_when_no_focusable_sprites_clicked(self):
        """Test that focused sprites are unfocused when clicking on non-focusable area."""
        scene = Scene()

        focused_sprite = FocusSprite(is_active=True)
        scene.all_sprites.add(focused_sprite)

        # Click on no focusable sprites (empty list)
        scene._handle_focus_management([])

        assert focused_sprite.is_active is False
        assert focused_sprite.focus_lost_count == 1

    def test_does_not_unfocus_when_focusable_sprite_clicked(self):
        """Test that focused sprites remain focused when clicking on focusable sprite."""
        scene = Scene()

        focused_sprite = FocusSprite(is_active=True)
        scene.all_sprites.add(focused_sprite)

        focusable_sprite = FocusSprite()

        # Click on a focusable sprite
        scene._handle_focus_management([focusable_sprite])

        assert focused_sprite.is_active is True
        assert focused_sprite.focus_lost_count == 0

    def test_handles_no_focused_sprites_gracefully(self):
        """Test that focus management works when no sprites are currently focused."""
        scene = Scene()

        # No focused sprites, clicking on nothing
        scene._handle_focus_management([])

    def test_unfocuses_multiple_focused_sprites(self):
        """Test that multiple focused sprites are all unfocused."""
        scene = Scene()

        first_focused = FocusSprite(is_active=True)

        second_focused = FocusSprite(is_active=True)

        scene.all_sprites.add(first_focused)
        scene.all_sprites.add(second_focused)

        scene._handle_focus_management([])

        assert first_focused.is_active is False
        assert second_focused.is_active is False
        assert first_focused.focus_lost_count == 1
        assert second_focused.focus_lost_count == 1

    def test_non_focusable_collided_sprites_still_unfocus(self):
        """Test that clicking non-focusable sprites still causes unfocus."""
        scene = Scene()

        focused_sprite = FocusSprite(is_active=True)
        scene.all_sprites.add(focused_sprite)

        # A sprite that is not focusable (no focusable attribute)
        non_focusable_sprite = ActiveSpriteWithoutKeyHandler()

        scene._handle_focus_management([non_focusable_sprite])

        assert focused_sprite.is_active is False


class TestHandleQuitKeyPress:
    """Test Scene._handle_quit_key_press() behavior."""

    def test_posts_pygame_quit_event(self):
        """Test that _handle_quit_key_press posts a pygame.QUIT event."""
        scene = Scene()

        pygame.event.clear(eventtype=pygame.QUIT)

        scene._handle_quit_key_press()

        # The QUIT event is in pygame's real event queue (taken out, so no later test sees it)
        quit_events = pygame.event.get(eventtype=pygame.QUIT)
        assert len(quit_events) == 1
        assert quit_events[0].type == pygame.QUIT


class TestOnKeyDownEvent:
    """Test Scene.on_key_down_event() behavior."""

    def test_focused_sprite_handles_event_first(self):
        """Test that focused sprites handle key events before scene-level handling."""
        scene = Scene()

        focused_sprite = FocusSprite(is_active=True)
        scene.all_sprites.add(focused_sprite)

        event = _key_down(pygame.K_q)

        scene.on_key_down_event(event)

        # The focused sprite should handle it
        assert focused_sprite.key_down_events == [event]
        # Scene-level handling (quit_requested) should NOT happen
        assert not getattr(scene, 'quit_requested', False)

    def test_scene_handles_q_key_when_no_focused_sprites(self):
        """Test that Q key sets quit_requested when no sprites are focused."""
        scene = Scene()

        event = _key_down(pygame.K_q)

        scene.on_key_down_event(event)

        assert scene.quit_requested is True

    def test_non_q_key_does_not_set_quit(self):
        """Test that non-Q keys do not set quit_requested."""
        scene = Scene()

        event = _key_down(pygame.K_a)

        scene.on_key_down_event(event)

        assert not getattr(scene, 'quit_requested', False)

    def test_focused_sprite_stops_event_propagation(self):
        """Test that focused sprite handling stops further key event propagation."""
        scene = Scene()

        focused_sprite = FocusSprite(is_active=True)
        scene.all_sprites.add(focused_sprite)

        # Q would set quit_requested at scene level; the focused sprite takes it instead
        event = _key_down(pygame.K_q)

        scene.on_key_down_event(event)

        # Scene-level key events never ran
        assert scene.quit_requested is False
        assert focused_sprite.key_down_events == [event]


class TestHandleFocusedSpriteEvents:
    """Test Scene._handle_focused_sprite_events() behavior."""

    def test_returns_true_when_focused_sprite_handles_event(self):
        """Test returns True when a focused sprite handles the event."""
        scene = Scene()

        focused_sprite = FocusSprite(is_active=True)
        scene.all_sprites.add(focused_sprite)

        event = _key_down(pygame.K_a)

        result = scene._handle_focused_sprite_events(event)

        assert result is True
        assert focused_sprite.key_down_events == [event]

    def test_returns_false_when_no_focused_sprites(self):
        """Test returns False when no sprites are focused."""
        scene = Scene()

        event = _key_down(pygame.K_a)

        result = scene._handle_focused_sprite_events(event)

        assert result is False

    def test_returns_false_when_sprites_not_active(self):
        """Test returns False when sprites exist but none are active."""
        scene = Scene()

        inactive_sprite = FocusSprite(is_active=False)
        scene.all_sprites.add(inactive_sprite)

        event = _key_down(pygame.K_a)

        result = scene._handle_focused_sprite_events(event)

        assert result is False

    def test_only_first_focused_sprite_handles_event(self):
        """Test that event propagation stops after first focused sprite handles it."""
        scene = Scene()

        first_focused = FocusSprite(is_active=True)

        second_focused = FocusSprite(is_active=True)

        scene.all_sprites.add(first_focused)
        scene.all_sprites.add(second_focused)

        event = _key_down(pygame.K_a)

        result = scene._handle_focused_sprite_events(event)

        assert result is True
        # Only the first focused sprite should have been called
        assert first_focused.key_down_events == [event]
        assert second_focused.key_down_events == []

    def test_skips_sprites_without_on_key_down_event(self):
        """Test that sprites without on_key_down_event are skipped."""
        scene = Scene()

        sprite_without_handler = ActiveSpriteWithoutKeyHandler()
        scene.all_sprites.add(sprite_without_handler)

        event = _key_down(pygame.K_a)

        result = scene._handle_focused_sprite_events(event)

        # The sprite is active but has no on_key_down_event, so it is not handled
        assert result is False


class TestHandleSceneKeyEvents:
    """Test Scene._handle_scene_key_events() behavior."""

    def test_q_key_sets_quit_requested(self):
        """Test that Q key sets quit_requested to True."""
        scene = Scene()

        event = _key_down(pygame.K_q)

        scene._handle_scene_key_events(event)

        assert scene.quit_requested is True

    def test_non_q_key_does_not_set_quit_requested(self):
        """Test that non-Q keys do not set quit_requested."""
        scene = Scene()

        event = _key_down(pygame.K_a)

        scene._handle_scene_key_events(event)

        assert not getattr(scene, 'quit_requested', False)

    def test_escape_key_does_not_set_quit_requested(self):
        """Test that escape key does not set quit_requested via _handle_scene_key_events."""
        scene = Scene()

        event = _key_down(pygame.K_ESCAPE)

        scene._handle_scene_key_events(event)

        # Only Q key triggers quit in _handle_scene_key_events
        assert not getattr(scene, 'quit_requested', False)
