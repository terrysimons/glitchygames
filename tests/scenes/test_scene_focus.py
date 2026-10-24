"""Tests for Scene focus management and key handling behaviors.

Focuses on verifying _handle_focus_management, _handle_quit_key_press,
on_key_down_event, _handle_focused_sprite_events, and _handle_scene_key_events.
"""

import pygame
import pytest

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


def _key_up(key: int) -> events.HashableEvent:
    """Return a real KEYUP event for the key, with its US QWERTY scancode.

    Returns:
        events.HashableEvent: The event.

    """
    return events.HashableEvent(
        pygame.KEYUP, key=key, scancode=qwerty_scancode(key=key), mod=pygame.KMOD_NONE
    )


def _take_quit_events() -> list[pygame.event.Event]:
    """Remove and return the QUIT events waiting in pygame's real event queue.

    Returns:
        list[pygame.event.Event]: The QUIT events.

    """
    return pygame.event.get(eventtype=pygame.QUIT)


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

    def test_q_quits_once_on_its_release_and_its_press_claims_nothing(self, caplog):
        """Q's press neither quits nor says it does; its release posts one QUIT (BUGS.md #203).

        The press used to log "Quit requested" and set the scene's quit_requested, which
        nothing read: the quit comes from the release (Scene.on_key_up_event).
        """
        scene = Scene()
        _take_quit_events()
        caplog.set_level('INFO')

        # As SceneManager routes a key-down: the press is recorded, then handled
        scene.record_key_press(key=pygame.K_q)
        scene.on_key_down_event(_key_down(pygame.K_q))

        assert _take_quit_events() == []
        assert 'Quit requested' not in caplog.text
        assert not hasattr(scene, 'quit_requested')

        scene.on_key_up_event(_key_up(pygame.K_q))

        assert len(_take_quit_events()) == 1
        assert 'Quit requested' in caplog.text

    def test_non_q_key_does_not_quit(self):
        """A key other than Q or ESC neither quits on its press nor on its release."""
        scene = Scene()
        _take_quit_events()

        scene.record_key_press(key=pygame.K_a)
        scene.on_key_down_event(_key_down(pygame.K_a))
        scene.on_key_up_event(_key_up(pygame.K_a))

        assert _take_quit_events() == []

    def test_focused_sprite_stops_event_propagation(self):
        """Test that focused sprite handling stops further key event propagation."""
        scene = Scene()

        focused_sprite = FocusSprite(is_active=True)
        scene.all_sprites.add(focused_sprite)

        # The focused sprite takes Q instead of the scene
        event = _key_down(pygame.K_q)

        scene.on_key_down_event(event)

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

    @pytest.mark.parametrize('key', [pygame.K_q, pygame.K_ESCAPE, pygame.K_a])
    def test_a_press_does_nothing_at_scene_level(self, key):
        """The base scene acts on no key press (Q and ESC quit on release): a hook for scenes."""
        scene = Scene()
        _take_quit_events()

        scene._handle_scene_key_events(_key_down(key))

        assert _take_quit_events() == []
