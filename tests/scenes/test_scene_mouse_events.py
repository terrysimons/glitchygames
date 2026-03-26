"""Tests for Scene mouse event handler behaviors.

Focuses on verifying that mouse event handlers properly delegate to sprites
via collision detection and sprites_at_position calls.
"""

from glitchygames.scenes import Scene


class TestOnMouseDragEvent:
    """Test Scene.on_mouse_drag_event() behavior."""

    def test_calls_sprites_at_position(self, mock_pygame_patches, mocker):
        """Test that on_mouse_drag_event calls sprites_at_position."""
        scene = Scene()
        mocker.patch.object(scene, 'sprites_at_position', return_value=[])

        event = mocker.Mock()
        event.pos = (50, 50)
        trigger = mocker.Mock()

        scene.on_mouse_drag_event(event, trigger)

        scene.sprites_at_position.assert_called_once_with(pos=(50, 50))  # type: ignore[unresolved-attribute]

    def test_delegates_to_collided_sprites(self, mock_pygame_patches, mocker):
        """Test that collided sprites receive drag events."""
        scene = Scene()

        mock_sprite = mocker.Mock()
        mock_sprite.on_mouse_drag_event = mocker.Mock()
        mocker.patch.object(scene, 'sprites_at_position', return_value=[mock_sprite])

        event = mocker.Mock()
        event.pos = (50, 50)
        trigger = mocker.Mock()

        scene.on_mouse_drag_event(event, trigger)

        mock_sprite.on_mouse_drag_event.assert_called_once_with(event, trigger)

    def test_delegates_to_multiple_collided_sprites(self, mock_pygame_patches, mocker):
        """Test that all collided sprites receive drag events."""
        scene = Scene()

        first_sprite = mocker.Mock()
        second_sprite = mocker.Mock()
        mocker.patch.object(
            scene, 'sprites_at_position', return_value=[first_sprite, second_sprite],
        )

        event = mocker.Mock()
        event.pos = (50, 50)
        trigger = mocker.Mock()

        scene.on_mouse_drag_event(event, trigger)

        first_sprite.on_mouse_drag_event.assert_called_once_with(event, trigger)
        second_sprite.on_mouse_drag_event.assert_called_once_with(event, trigger)

    def test_no_error_with_no_collided_sprites(self, mock_pygame_patches, mocker):
        """Test no error when no sprites are at the drag position."""
        scene = Scene()
        mocker.patch.object(scene, 'sprites_at_position', return_value=[])

        event = mocker.Mock()
        event.pos = (999, 999)
        trigger = mocker.Mock()

        scene.on_mouse_drag_event(event, trigger)


class TestOnMouseDropEvent:
    """Test Scene.on_mouse_drop_event() behavior."""

    def test_calls_sprites_at_position(self, mock_pygame_patches, mocker):
        """Test that on_mouse_drop_event calls sprites_at_position."""
        scene = Scene()
        mocker.patch.object(scene, 'sprites_at_position', return_value=[])

        event = mocker.Mock()
        event.pos = (100, 200)
        trigger = mocker.Mock()

        scene.on_mouse_drop_event(event, trigger)

        scene.sprites_at_position.assert_called_once_with(pos=(100, 200))  # type: ignore[unresolved-attribute]

    def test_delegates_to_collided_sprites(self, mock_pygame_patches, mocker):
        """Test that collided sprites receive drop events."""
        scene = Scene()

        mock_sprite = mocker.Mock()
        mocker.patch.object(scene, 'sprites_at_position', return_value=[mock_sprite])

        event = mocker.Mock()
        event.pos = (100, 200)
        trigger = mocker.Mock()

        scene.on_mouse_drop_event(event, trigger)

        mock_sprite.on_mouse_drop_event.assert_called_once_with(event, trigger)

    def test_delegates_to_multiple_collided_sprites(self, mock_pygame_patches, mocker):
        """Test that all collided sprites receive drop events."""
        scene = Scene()

        first_sprite = mocker.Mock()
        second_sprite = mocker.Mock()
        mocker.patch.object(
            scene, 'sprites_at_position', return_value=[first_sprite, second_sprite],
        )

        event = mocker.Mock()
        event.pos = (100, 200)
        trigger = mocker.Mock()

        scene.on_mouse_drop_event(event, trigger)

        first_sprite.on_mouse_drop_event.assert_called_once_with(event, trigger)
        second_sprite.on_mouse_drop_event.assert_called_once_with(event, trigger)


class TestOnLeftMouseDragEvent:
    """Test Scene.on_left_mouse_drag_event() behavior."""

    def test_delegates_to_top_sprite_only(self, mock_pygame_patches, mocker):
        """Test that only the top (last) sprite receives left drag event."""
        scene = Scene()

        bottom_sprite = mocker.Mock()
        top_sprite = mocker.Mock()
        mocker.patch.object(scene, 'sprites_at_position', return_value=[bottom_sprite, top_sprite])

        event = mocker.Mock()
        event.pos = (50, 50)
        trigger = mocker.Mock()

        scene.on_left_mouse_drag_event(event, trigger)

        top_sprite.on_left_mouse_drag_event.assert_called_once_with(event, trigger)
        bottom_sprite.on_left_mouse_drag_event.assert_not_called()

    def test_no_error_with_no_collided_sprites(self, mock_pygame_patches, mocker):
        """Test no error when no sprites are at the drag position."""
        scene = Scene()
        mocker.patch.object(scene, 'sprites_at_position', return_value=[])

        event = mocker.Mock()
        event.pos = (50, 50)
        trigger = mocker.Mock()

        scene.on_left_mouse_drag_event(event, trigger)

    def test_single_sprite_receives_event(self, mock_pygame_patches, mocker):
        """Test that a single collided sprite receives the drag event."""
        scene = Scene()

        single_sprite = mocker.Mock()
        mocker.patch.object(scene, 'sprites_at_position', return_value=[single_sprite])

        event = mocker.Mock()
        event.pos = (50, 50)
        trigger = mocker.Mock()

        scene.on_left_mouse_drag_event(event, trigger)

        single_sprite.on_left_mouse_drag_event.assert_called_once_with(event, trigger)


class TestOnLeftMouseDropEvent:
    """Test Scene.on_left_mouse_drop_event() behavior."""

    def test_delegates_to_all_collided_sprites(self, mock_pygame_patches, mocker):
        """Test that all collided sprites receive left drop event."""
        scene = Scene()

        first_sprite = mocker.Mock()
        second_sprite = mocker.Mock()
        mocker.patch.object(
            scene, 'sprites_at_position', return_value=[first_sprite, second_sprite],
        )

        event = mocker.Mock()
        event.pos = (150, 250)
        trigger = mocker.Mock()

        scene.on_left_mouse_drop_event(event, trigger)

        first_sprite.on_left_mouse_drop_event.assert_called_once_with(event, trigger)
        second_sprite.on_left_mouse_drop_event.assert_called_once_with(event, trigger)

    def test_calls_sprites_at_position(self, mock_pygame_patches, mocker):
        """Test that collision detection is performed."""
        scene = Scene()
        mocker.patch.object(scene, 'sprites_at_position', return_value=[])

        event = mocker.Mock()
        event.pos = (150, 250)
        trigger = mocker.Mock()

        scene.on_left_mouse_drop_event(event, trigger)

        scene.sprites_at_position.assert_called_once_with(pos=(150, 250))  # type: ignore[unresolved-attribute]


class TestOnMiddleMouseDragEvent:
    """Test Scene.on_middle_mouse_drag_event() behavior."""

    def test_delegates_to_all_collided_sprites(self, mock_pygame_patches, mocker):
        """Test that all collided sprites receive middle drag event."""
        scene = Scene()

        mock_sprite = mocker.Mock()
        mocker.patch.object(scene, 'sprites_at_position', return_value=[mock_sprite])

        event = mocker.Mock()
        event.pos = (200, 300)
        trigger = mocker.Mock()

        scene.on_middle_mouse_drag_event(event, trigger)

        mock_sprite.on_middle_mouse_drag_event.assert_called_once_with(event, trigger)

    def test_no_error_with_no_collided_sprites(self, mock_pygame_patches, mocker):
        """Test no error when no sprites are at the position."""
        scene = Scene()
        mocker.patch.object(scene, 'sprites_at_position', return_value=[])

        event = mocker.Mock()
        event.pos = (200, 300)
        trigger = mocker.Mock()

        scene.on_middle_mouse_drag_event(event, trigger)


class TestOnMiddleMouseDropEvent:
    """Test Scene.on_middle_mouse_drop_event() behavior."""

    def test_delegates_to_all_collided_sprites(self, mock_pygame_patches, mocker):
        """Test that all collided sprites receive middle drop event."""
        scene = Scene()

        mock_sprite = mocker.Mock()
        mocker.patch.object(scene, 'sprites_at_position', return_value=[mock_sprite])

        event = mocker.Mock()
        event.pos = (200, 300)
        trigger = mocker.Mock()

        scene.on_middle_mouse_drop_event(event, trigger)

        mock_sprite.on_middle_mouse_drop_event.assert_called_once_with(event, trigger)

    def test_no_error_with_no_collided_sprites(self, mock_pygame_patches, mocker):
        """Test no error when no sprites are at the position."""
        scene = Scene()
        mocker.patch.object(scene, 'sprites_at_position', return_value=[])

        event = mocker.Mock()
        event.pos = (200, 300)
        trigger = mocker.Mock()

        scene.on_middle_mouse_drop_event(event, trigger)


class TestOnRightMouseDragEvent:
    """Test Scene.on_right_mouse_drag_event() behavior."""

    def test_delegates_to_all_collided_sprites(self, mock_pygame_patches, mocker):
        """Test that all collided sprites receive right drag event."""
        scene = Scene()

        mock_sprite = mocker.Mock()
        mocker.patch.object(scene, 'sprites_at_position', return_value=[mock_sprite])

        event = mocker.Mock()
        event.pos = (300, 400)
        trigger = mocker.Mock()

        scene.on_right_mouse_drag_event(event, trigger)

        mock_sprite.on_right_mouse_drag_event.assert_called_once_with(event, trigger)

    def test_no_error_with_no_collided_sprites(self, mock_pygame_patches, mocker):
        """Test no error when no sprites are at the position."""
        scene = Scene()
        mocker.patch.object(scene, 'sprites_at_position', return_value=[])

        event = mocker.Mock()
        event.pos = (300, 400)
        trigger = mocker.Mock()

        scene.on_right_mouse_drag_event(event, trigger)


class TestOnRightMouseDropEvent:
    """Test Scene.on_right_mouse_drop_event() behavior."""

    def test_delegates_to_all_collided_sprites(self, mock_pygame_patches, mocker):
        """Test that all collided sprites receive right drop event."""
        scene = Scene()

        mock_sprite = mocker.Mock()
        mocker.patch.object(scene, 'sprites_at_position', return_value=[mock_sprite])

        event = mocker.Mock()
        event.pos = (300, 400)
        trigger = mocker.Mock()

        scene.on_right_mouse_drop_event(event, trigger)

        mock_sprite.on_right_mouse_drop_event.assert_called_once_with(event, trigger)

    def test_no_error_with_no_collided_sprites(self, mock_pygame_patches, mocker):
        """Test no error when no sprites are at the position."""
        scene = Scene()
        mocker.patch.object(scene, 'sprites_at_position', return_value=[])

        event = mocker.Mock()
        event.pos = (300, 400)
        trigger = mocker.Mock()

        scene.on_right_mouse_drop_event(event, trigger)


class TestOnLeftMouseButtonUpEvent:
    """Test Scene.on_left_mouse_button_up_event() behavior."""

    def test_delegates_to_collided_sprites(self, mock_pygame_patches, mocker):
        """Test that collided sprites receive left button up event."""
        scene = Scene()

        mock_sprite = mocker.Mock()
        mocker.patch.object(scene, 'sprites_at_position', return_value=[mock_sprite])

        event = mocker.Mock()
        event.pos = (100, 100)

        scene.on_left_mouse_button_up_event(event)

        mock_sprite.on_left_mouse_button_up_event.assert_called_once_with(event)

    def test_delegates_to_multiple_sprites(self, mock_pygame_patches, mocker):
        """Test that all collided sprites receive the event."""
        scene = Scene()

        first_sprite = mocker.Mock()
        second_sprite = mocker.Mock()
        mocker.patch.object(
            scene, 'sprites_at_position', return_value=[first_sprite, second_sprite],
        )

        event = mocker.Mock()
        event.pos = (100, 100)

        scene.on_left_mouse_button_up_event(event)

        first_sprite.on_left_mouse_button_up_event.assert_called_once_with(event)
        second_sprite.on_left_mouse_button_up_event.assert_called_once_with(event)


class TestOnMiddleMouseButtonUpEvent:
    """Test Scene.on_middle_mouse_button_up_event() behavior."""

    def test_delegates_to_collided_sprites(self, mock_pygame_patches, mocker):
        """Test that collided sprites receive middle button up event."""
        scene = Scene()

        mock_sprite = mocker.Mock()
        mocker.patch.object(scene, 'sprites_at_position', return_value=[mock_sprite])

        event = mocker.Mock()
        event.pos = (200, 200)

        scene.on_middle_mouse_button_up_event(event)

        mock_sprite.on_middle_mouse_button_up_event.assert_called_once_with(event)


class TestOnRightMouseButtonUpEvent:
    """Test Scene.on_right_mouse_button_up_event() behavior."""

    def test_delegates_to_collided_sprites(self, mock_pygame_patches, mocker):
        """Test that collided sprites receive right button up event."""
        scene = Scene()

        mock_sprite = mocker.Mock()
        mocker.patch.object(scene, 'sprites_at_position', return_value=[mock_sprite])

        event = mocker.Mock()
        event.pos = (300, 300)

        scene.on_right_mouse_button_up_event(event)

        mock_sprite.on_right_mouse_button_up_event.assert_called_once_with(event)


class TestOnLeftMouseButtonDownEvent:
    """Test Scene.on_left_mouse_button_down_event() with focus management."""

    def test_calls_handle_focus_management(self, mock_pygame_patches, mocker):
        """Test that focus management is invoked on left click."""
        scene = Scene()
        mocker.patch.object(scene, '_get_collided_sprites', return_value=[])
        mocker.patch.object(scene, '_get_focusable_sprites', return_value=[])
        mocker.patch.object(scene, '_get_focused_sprites', return_value=[])
        mocker.patch.object(scene, '_handle_focus_management')

        event = mocker.Mock()
        event.pos = (100, 100)

        scene.on_left_mouse_button_down_event(event)

        scene._handle_focus_management.assert_called_once_with([])  # type: ignore[unresolved-attribute]

    def test_delegates_to_sprites_with_handler(self, mock_pygame_patches, mocker):
        """Test that sprites with on_left_mouse_button_down_event receive it."""
        scene = Scene()

        mock_sprite = mocker.Mock()
        mock_sprite.on_left_mouse_button_down_event = mocker.Mock()
        mocker.patch.object(scene, '_get_collided_sprites', return_value=[mock_sprite])
        mocker.patch.object(scene, '_get_focusable_sprites', return_value=[])
        mocker.patch.object(scene, '_get_focused_sprites', return_value=[])
        mocker.patch.object(scene, '_handle_focus_management')

        event = mocker.Mock()
        event.pos = (100, 100)

        scene.on_left_mouse_button_down_event(event)

        mock_sprite.on_left_mouse_button_down_event.assert_called_once_with(event)

    def test_skips_sprites_without_handler(self, mock_pygame_patches, mocker):
        """Test that sprites without the handler method are skipped."""
        scene = Scene()

        # Create a sprite that has no on_left_mouse_button_down_event attribute
        mock_sprite = mocker.Mock(spec=['some_other_method'])
        mocker.patch.object(scene, '_get_collided_sprites', return_value=[mock_sprite])
        mocker.patch.object(scene, '_get_focusable_sprites', return_value=[])
        mocker.patch.object(scene, '_get_focused_sprites', return_value=[])
        mocker.patch.object(scene, '_handle_focus_management')

        event = mocker.Mock()
        event.pos = (100, 100)

        # Should not raise even though sprite lacks the handler
        scene.on_left_mouse_button_down_event(event)


class TestOnMiddleMouseButtonDownEvent:
    """Test Scene.on_middle_mouse_button_down_event() behavior."""

    def test_delegates_to_collided_sprites(self, mock_pygame_patches, mocker):
        """Test that collided sprites receive middle button down event."""
        scene = Scene()

        mock_sprite = mocker.Mock()
        mocker.patch.object(scene, 'sprites_at_position', return_value=[mock_sprite])

        event = mocker.Mock()
        event.pos = (200, 200)

        scene.on_middle_mouse_button_down_event(event)

        mock_sprite.on_middle_mouse_button_down_event.assert_called_once_with(event)

    def test_no_error_with_no_collided_sprites(self, mock_pygame_patches, mocker):
        """Test no error when no sprites are at the position."""
        scene = Scene()
        mocker.patch.object(scene, 'sprites_at_position', return_value=[])

        event = mocker.Mock()
        event.pos = (200, 200)

        scene.on_middle_mouse_button_down_event(event)


class TestOnRightMouseButtonDownEvent:
    """Test Scene.on_right_mouse_button_down_event() behavior."""

    def test_delegates_to_collided_sprites(self, mock_pygame_patches, mocker):
        """Test that collided sprites receive right button down event."""
        scene = Scene()

        mock_sprite = mocker.Mock()
        mocker.patch.object(scene, '_get_collided_sprites', return_value=[mock_sprite])

        event = mocker.Mock()
        event.pos = (300, 300)

        scene.on_right_mouse_button_down_event(event)

        mock_sprite.on_right_mouse_button_down_event.assert_called_once_with(event)

    def test_no_error_with_no_collided_sprites(self, mock_pygame_patches, mocker):
        """Test no error when no sprites are at the position."""
        scene = Scene()
        mocker.patch.object(scene, '_get_collided_sprites', return_value=[])

        event = mocker.Mock()
        event.pos = (300, 300)

        scene.on_right_mouse_button_down_event(event)


class TestOnMouseButtonDownEvent:
    """Test Scene.on_mouse_button_down_event() behavior."""

    def test_calls_handle_focus_management(self, mock_pygame_patches, mocker):
        """Test that focus management is invoked on generic mouse button down."""
        scene = Scene()
        mocker.patch.object(scene, '_get_collided_sprites', return_value=[])
        mocker.patch.object(scene, '_get_focusable_sprites', return_value=[])
        mocker.patch.object(scene, '_get_focused_sprites', return_value=[])
        mocker.patch.object(scene, '_handle_focus_management')

        event = mocker.Mock()
        event.pos = (100, 100)

        scene.on_mouse_button_down_event(event)

        scene._handle_focus_management.assert_called_once_with([])  # type: ignore[unresolved-attribute]

    def test_delegates_to_sprites_with_handler(self, mock_pygame_patches, mocker):
        """Test that sprites with on_mouse_button_down_event receive it."""
        scene = Scene()

        mock_sprite = mocker.Mock()
        mock_sprite.on_mouse_button_down_event = mocker.Mock()
        mocker.patch.object(scene, '_get_collided_sprites', return_value=[mock_sprite])
        mocker.patch.object(scene, '_get_focusable_sprites', return_value=[])
        mocker.patch.object(scene, '_get_focused_sprites', return_value=[])
        mocker.patch.object(scene, '_handle_focus_management')

        event = mocker.Mock()
        event.pos = (100, 100)

        scene.on_mouse_button_down_event(event)

        mock_sprite.on_mouse_button_down_event.assert_called_once_with(event)

    def test_skips_sprites_without_handler(self, mock_pygame_patches, mocker):
        """Test that sprites without on_mouse_button_down_event are skipped."""
        scene = Scene()

        mock_sprite = mocker.Mock(spec=['some_other_method'])
        mocker.patch.object(scene, '_get_collided_sprites', return_value=[mock_sprite])
        mocker.patch.object(scene, '_get_focusable_sprites', return_value=[])
        mocker.patch.object(scene, '_get_focused_sprites', return_value=[])
        mocker.patch.object(scene, '_handle_focus_management')

        event = mocker.Mock()
        event.pos = (100, 100)

        # Should not raise even though sprite lacks the handler
        scene.on_mouse_button_down_event(event)
