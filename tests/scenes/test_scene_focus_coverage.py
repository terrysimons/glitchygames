"""Tests for Scene focus management and key handling behaviors.

Focuses on verifying _handle_focus_management, _handle_quit_key_press,
on_key_down_event, _handle_focused_sprite_events, and _handle_scene_key_events.
"""

import pygame

from glitchygames.scenes import Scene


class TestHandleFocusManagement:
    """Test Scene._handle_focus_management() behavior."""

    def test_unfocuses_sprites_when_no_focusable_sprites_clicked(self, mock_pygame_patches, mocker):
        """Test that focused sprites are unfocused when clicking on non-focusable area."""
        scene = Scene()

        focused_sprite = mocker.Mock()
        focused_sprite.active = True
        focused_sprite.on_focus_lost = mocker.Mock()
        scene.all_sprites.add(focused_sprite)

        # Click on no focusable sprites (empty list)
        scene._handle_focus_management([])

        assert focused_sprite.active is False
        focused_sprite.on_focus_lost.assert_called_once()

    def test_does_not_unfocus_when_focusable_sprite_clicked(self, mock_pygame_patches, mocker):
        """Test that focused sprites remain focused when clicking on focusable sprite."""
        scene = Scene()

        focused_sprite = mocker.Mock()
        focused_sprite.active = True
        focused_sprite.on_focus_lost = mocker.Mock()
        scene.all_sprites.add(focused_sprite)

        focusable_sprite = mocker.Mock()
        focusable_sprite.focusable = True

        # Click on a focusable sprite
        scene._handle_focus_management([focusable_sprite])

        assert focused_sprite.active is True
        focused_sprite.on_focus_lost.assert_not_called()

    def test_handles_no_focused_sprites_gracefully(self, mock_pygame_patches, mocker):
        """Test that focus management works when no sprites are currently focused."""
        scene = Scene()

        # No focused sprites, clicking on nothing
        scene._handle_focus_management([])

    def test_unfocuses_multiple_focused_sprites(self, mock_pygame_patches, mocker):
        """Test that multiple focused sprites are all unfocused."""
        scene = Scene()

        first_focused = mocker.Mock()
        first_focused.active = True
        first_focused.on_focus_lost = mocker.Mock()

        second_focused = mocker.Mock()
        second_focused.active = True
        second_focused.on_focus_lost = mocker.Mock()

        scene.all_sprites.add(first_focused)
        scene.all_sprites.add(second_focused)

        scene._handle_focus_management([])

        assert first_focused.active is False
        assert second_focused.active is False
        first_focused.on_focus_lost.assert_called_once()
        second_focused.on_focus_lost.assert_called_once()

    def test_non_focusable_collided_sprites_still_unfocus(self, mock_pygame_patches, mocker):
        """Test that clicking non-focusable sprites still causes unfocus."""
        scene = Scene()

        focused_sprite = mocker.Mock()
        focused_sprite.active = True
        focused_sprite.on_focus_lost = mocker.Mock()
        scene.all_sprites.add(focused_sprite)

        # A sprite that is not focusable (no focusable attribute)
        non_focusable_sprite = mocker.Mock(spec=['some_method'])

        scene._handle_focus_management([non_focusable_sprite])

        assert focused_sprite.active is False


class TestHandleQuitKeyPress:
    """Test Scene._handle_quit_key_press() behavior."""

    def test_posts_pygame_quit_event(self, mock_pygame_patches, mocker):
        """Test that _handle_quit_key_press posts a pygame.QUIT event."""
        scene = Scene()

        mock_event_post = mocker.patch('pygame.event.post')
        mock_event_cls = mocker.patch('pygame.event.Event')

        scene._handle_quit_key_press()

        mock_event_cls.assert_called_once_with(pygame.QUIT)
        mock_event_post.assert_called_once_with(mock_event_cls.return_value)


class TestOnKeyDownEvent:
    """Test Scene.on_key_down_event() behavior."""

    def test_focused_sprite_handles_event_first(self, mock_pygame_patches, mocker):
        """Test that focused sprites handle key events before scene-level handling."""
        scene = Scene()

        focused_sprite = mocker.Mock()
        focused_sprite.active = True
        focused_sprite.on_key_down_event = mocker.Mock()
        scene.all_sprites.add(focused_sprite)

        event = mocker.Mock()
        event.key = pygame.K_q

        scene.on_key_down_event(event)

        # The focused sprite should handle it
        focused_sprite.on_key_down_event.assert_called_once_with(event)
        # Scene-level handling (quit_requested) should NOT happen
        assert not getattr(scene, 'quit_requested', False)

    def test_scene_handles_q_key_when_no_focused_sprites(self, mock_pygame_patches, mocker):
        """Test that Q key sets quit_requested when no sprites are focused."""
        scene = Scene()

        event = mocker.Mock()
        event.key = pygame.K_q

        scene.on_key_down_event(event)

        assert scene.quit_requested is True

    def test_non_q_key_does_not_set_quit(self, mock_pygame_patches, mocker):
        """Test that non-Q keys do not set quit_requested."""
        scene = Scene()

        event = mocker.Mock()
        event.key = pygame.K_a

        scene.on_key_down_event(event)

        assert not getattr(scene, 'quit_requested', False)

    def test_focused_sprite_stops_event_propagation(self, mock_pygame_patches, mocker):
        """Test that focused sprite handling stops further key event propagation."""
        scene = Scene()
        mocker.patch.object(scene, '_handle_scene_key_events')

        focused_sprite = mocker.Mock()
        focused_sprite.active = True
        focused_sprite.on_key_down_event = mocker.Mock()
        scene.all_sprites.add(focused_sprite)

        event = mocker.Mock()
        event.key = pygame.K_a

        scene.on_key_down_event(event)

        # Scene-level key events should not be called
        scene._handle_scene_key_events.assert_not_called()


class TestHandleFocusedSpriteEvents:
    """Test Scene._handle_focused_sprite_events() behavior."""

    def test_returns_true_when_focused_sprite_handles_event(self, mock_pygame_patches, mocker):
        """Test returns True when a focused sprite handles the event."""
        scene = Scene()

        focused_sprite = mocker.Mock()
        focused_sprite.active = True
        focused_sprite.on_key_down_event = mocker.Mock()
        scene.all_sprites.add(focused_sprite)

        event = mocker.Mock()

        result = scene._handle_focused_sprite_events(event)

        assert result is True
        focused_sprite.on_key_down_event.assert_called_once_with(event)

    def test_returns_false_when_no_focused_sprites(self, mock_pygame_patches, mocker):
        """Test returns False when no sprites are focused."""
        scene = Scene()

        event = mocker.Mock()

        result = scene._handle_focused_sprite_events(event)

        assert result is False

    def test_returns_false_when_sprites_not_active(self, mock_pygame_patches, mocker):
        """Test returns False when sprites exist but none are active."""
        scene = Scene()

        inactive_sprite = mocker.Mock()
        inactive_sprite.active = False
        scene.all_sprites.add(inactive_sprite)

        event = mocker.Mock()

        result = scene._handle_focused_sprite_events(event)

        assert result is False

    def test_only_first_focused_sprite_handles_event(self, mock_pygame_patches, mocker):
        """Test that event propagation stops after first focused sprite handles it."""
        scene = Scene()

        first_focused = mocker.Mock()
        first_focused.active = True
        first_focused.on_key_down_event = mocker.Mock()

        second_focused = mocker.Mock()
        second_focused.active = True
        second_focused.on_key_down_event = mocker.Mock()

        scene.all_sprites.add(first_focused)
        scene.all_sprites.add(second_focused)

        event = mocker.Mock()

        result = scene._handle_focused_sprite_events(event)

        assert result is True
        # Only the first focused sprite should have been called
        first_focused.on_key_down_event.assert_called_once_with(event)
        second_focused.on_key_down_event.assert_not_called()

    def test_skips_sprites_without_on_key_down_event(self, mock_pygame_patches, mocker):
        """Test that sprites without on_key_down_event are skipped."""
        scene = Scene()

        sprite_without_handler = mocker.Mock(spec=['active'])
        sprite_without_handler.active = True
        scene.all_sprites.add(sprite_without_handler)

        event = mocker.Mock()

        result = scene._handle_focused_sprite_events(event)

        # The sprite is active but has no on_key_down_event, so it is not handled
        assert result is False


class TestHandleSceneKeyEvents:
    """Test Scene._handle_scene_key_events() behavior."""

    def test_q_key_sets_quit_requested(self, mock_pygame_patches, mocker):
        """Test that Q key sets quit_requested to True."""
        scene = Scene()

        event = mocker.Mock()
        event.key = pygame.K_q

        scene._handle_scene_key_events(event)

        assert scene.quit_requested is True

    def test_non_q_key_does_not_set_quit_requested(self, mock_pygame_patches, mocker):
        """Test that non-Q keys do not set quit_requested."""
        scene = Scene()

        event = mocker.Mock()
        event.key = pygame.K_a

        scene._handle_scene_key_events(event)

        assert not getattr(scene, 'quit_requested', False)

    def test_escape_key_does_not_set_quit_requested(self, mock_pygame_patches, mocker):
        """Test that escape key does not set quit_requested via _handle_scene_key_events."""
        scene = Scene()

        event = mocker.Mock()
        event.key = pygame.K_ESCAPE

        scene._handle_scene_key_events(event)

        # Only Q key triggers quit in _handle_scene_key_events
        assert not getattr(scene, 'quit_requested', False)
