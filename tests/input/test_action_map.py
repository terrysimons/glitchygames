"""Tests for ActionMap input action mapping."""

from __future__ import annotations

import pygame

from glitchygames.events.base import HashableEvent
from glitchygames.input.action_map import ActionMap


def _key_down(key: int) -> HashableEvent:
    """Create a KEYDOWN HashableEvent."""
    return HashableEvent(type=pygame.KEYDOWN, key=key, mod=0, unicode='')


def _key_up(key: int) -> HashableEvent:
    """Create a KEYUP HashableEvent."""
    return HashableEvent(type=pygame.KEYUP, key=key, mod=0)


def _button_down(button: int, instance_id: int = 0) -> HashableEvent:
    """Create a CONTROLLERBUTTONDOWN HashableEvent."""
    return HashableEvent(
        type=pygame.CONTROLLERBUTTONDOWN,
        button=button,
        instance_id=instance_id,
    )


def _button_up(button: int, instance_id: int = 0) -> HashableEvent:
    """Create a CONTROLLERBUTTONUP HashableEvent."""
    return HashableEvent(
        type=pygame.CONTROLLERBUTTONUP,
        button=button,
        instance_id=instance_id,
    )


def _axis_motion(axis: int, value: int, instance_id: int = 0) -> HashableEvent:
    """Create a CONTROLLERAXISMOTION HashableEvent.

    Args:
        axis: The axis constant.
        value: Raw SDL value (-32767 to 32767).
        instance_id: Controller instance.

    """
    return HashableEvent(
        type=pygame.CONTROLLERAXISMOTION,
        axis=axis,
        value=value,
        instance_id=instance_id,
    )


class TestBasicLookup:
    """Tests for stateless event-to-action lookup."""

    def test_keyboard_binding_returns_action(self) -> None:
        """Bound keyboard key returns the action name."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE)
        assert actions.get_action(_key_down(pygame.K_SPACE)) == 'jump'

    def test_controller_button_returns_action(self) -> None:
        """Bound controller button returns the action name."""
        actions = ActionMap()
        actions.bind('jump', controller_button=pygame.CONTROLLER_BUTTON_A)
        assert actions.get_action(_button_down(pygame.CONTROLLER_BUTTON_A)) == 'jump'

    def test_unbound_event_returns_none(self) -> None:
        """Unbound event returns None."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE)
        assert actions.get_action(_key_down(pygame.K_RETURN)) is None

    def test_multiple_bindings_same_action(self) -> None:
        """Multiple keys can map to the same action."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE)
        actions.bind('jump', keyboard=pygame.K_UP)
        assert actions.get_action(_key_down(pygame.K_SPACE)) == 'jump'
        assert actions.get_action(_key_down(pygame.K_UP)) == 'jump'

    def test_keyboard_and_controller_same_action(self) -> None:
        """Keyboard and controller can both map to the same action."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE, controller_button=pygame.CONTROLLER_BUTTON_A)
        assert actions.get_action(_key_down(pygame.K_SPACE)) == 'jump'
        assert actions.get_action(_button_down(pygame.CONTROLLER_BUTTON_A)) == 'jump'

    def test_get_actions_returns_all(self) -> None:
        """get_actions returns all matching action names."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE)
        actions.bind('confirm', keyboard=pygame.K_SPACE)
        result = actions.get_actions(_key_down(pygame.K_SPACE))
        assert 'jump' in result
        assert 'confirm' in result

    def test_mouse_event_ignored(self) -> None:
        """Non-input events return None without error."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE)
        mouse_event = HashableEvent(type=pygame.MOUSEMOTION, pos=(100, 200), rel=(1, 0))
        assert actions.get_action(mouse_event) is None


class TestStateTracking:
    """Tests for frame-based held/pressed/released state."""

    def test_just_pressed_on_key_down(self) -> None:
        """just_pressed is True after handling a key down event."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE)
        actions.handle_event(_key_down(pygame.K_SPACE))
        assert actions.just_pressed('jump') is True

    def test_just_pressed_clears_after_begin_frame(self) -> None:
        """just_pressed is False after begin_frame."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE)
        actions.handle_event(_key_down(pygame.K_SPACE))
        actions.begin_frame()
        assert actions.just_pressed('jump') is False

    def test_is_held_while_down(self) -> None:
        """is_held is True while the key is held down."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE)
        actions.handle_event(_key_down(pygame.K_SPACE))
        assert actions.is_held('jump') is True

    def test_is_held_false_after_release(self) -> None:
        """is_held is False after key release."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE)
        actions.handle_event(_key_down(pygame.K_SPACE))
        actions.handle_event(_key_up(pygame.K_SPACE))
        assert actions.is_held('jump') is False

    def test_just_released_on_key_up(self) -> None:
        """just_released is True after releasing a held key."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE)
        actions.handle_event(_key_down(pygame.K_SPACE))
        actions.begin_frame()
        actions.handle_event(_key_up(pygame.K_SPACE))
        assert actions.just_released('jump') is True

    def test_controller_state_tracking(self) -> None:
        """State tracking works for controller buttons too."""
        actions = ActionMap()
        actions.bind('jump', controller_button=pygame.CONTROLLER_BUTTON_A)
        actions.handle_event(_button_down(pygame.CONTROLLER_BUTTON_A))
        assert actions.is_held('jump') is True
        assert actions.just_pressed('jump') is True
        actions.begin_frame()
        actions.handle_event(_button_up(pygame.CONTROLLER_BUTTON_A))
        assert actions.is_held('jump') is False
        assert actions.just_released('jump') is True

    def test_repeated_keydown_no_double_press(self) -> None:
        """OS key repeat does not re-trigger just_pressed."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE)
        actions.handle_event(_key_down(pygame.K_SPACE))
        actions.begin_frame()
        # OS sends another KEYDOWN while held
        actions.handle_event(_key_down(pygame.K_SPACE))
        assert actions.just_pressed('jump') is False
        assert actions.is_held('jump') is True

    def test_is_held_persists_across_frames(self) -> None:
        """is_held stays True across multiple frames without release."""
        actions = ActionMap()
        actions.bind('run', keyboard=pygame.K_RIGHT)
        actions.handle_event(_key_down(pygame.K_RIGHT))
        actions.begin_frame()
        assert actions.is_held('run') is True
        actions.begin_frame()
        assert actions.is_held('run') is True


class TestAxisHandling:
    """Tests for analog axis to digital action conversion."""

    def test_axis_above_positive_threshold(self) -> None:
        """Axis value above positive threshold activates the action."""
        actions = ActionMap()
        actions.bind('move_right', controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, 0.3))
        # Value 20000/32767 ≈ 0.61, above threshold
        actions.handle_event(_axis_motion(pygame.CONTROLLER_AXIS_LEFTX, 20000))
        assert actions.is_held('move_right') is True

    def test_axis_below_positive_threshold(self) -> None:
        """Axis value below positive threshold does not activate."""
        actions = ActionMap()
        actions.bind('move_right', controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, 0.3))
        # Value 5000/32767 ≈ 0.15, below threshold
        actions.handle_event(_axis_motion(pygame.CONTROLLER_AXIS_LEFTX, 5000))
        assert actions.is_held('move_right') is False

    def test_negative_threshold(self) -> None:
        """Negative threshold detects negative axis direction."""
        actions = ActionMap()
        actions.bind('move_left', controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, -0.3))
        actions.handle_event(_axis_motion(pygame.CONTROLLER_AXIS_LEFTX, -20000))
        assert actions.is_held('move_left') is True

    def test_deadzone_filters_small_values(self) -> None:
        """Values below deadzone are treated as zero."""
        actions = ActionMap(deadzone=0.15)
        actions.bind('move_right', controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, 0.3))
        # Value 3000/32767 ≈ 0.09, below deadzone
        actions.handle_event(_axis_motion(pygame.CONTROLLER_AXIS_LEFTX, 3000))
        assert actions.axis_value('move_right') == 0.0

    def test_axis_value_returns_normalized(self) -> None:
        """axis_value returns the deadzone-filtered normalized float."""
        actions = ActionMap()
        actions.bind('move_right', controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, 0.3))
        actions.handle_event(_axis_motion(pygame.CONTROLLER_AXIS_LEFTX, 20000))
        value = actions.axis_value('move_right')
        assert 0.5 < value < 0.7  # 20000/32767 ≈ 0.61

    def test_axis_release_on_return_to_center(self) -> None:
        """Action deactivates when axis returns below threshold."""
        actions = ActionMap()
        actions.bind('move_right', controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, 0.3))
        actions.handle_event(_axis_motion(pygame.CONTROLLER_AXIS_LEFTX, 20000))
        assert actions.is_held('move_right') is True
        actions.begin_frame()
        actions.handle_event(_axis_motion(pygame.CONTROLLER_AXIS_LEFTX, 0))
        assert actions.is_held('move_right') is False
        assert actions.just_released('move_right') is True


class TestMultiController:
    """Tests for multi-controller instance filtering."""

    def test_instance_id_accepts_matching(self) -> None:
        """Binding with instance_id accepts matching controller."""
        actions = ActionMap()
        actions.bind('jump', controller_button=pygame.CONTROLLER_BUTTON_A, instance_id=0)
        assert actions.get_action(_button_down(pygame.CONTROLLER_BUTTON_A, instance_id=0)) == 'jump'

    def test_instance_id_rejects_nonmatching(self) -> None:
        """Binding with instance_id rejects non-matching controller."""
        actions = ActionMap()
        actions.bind('jump', controller_button=pygame.CONTROLLER_BUTTON_A, instance_id=0)
        assert actions.get_action(_button_down(pygame.CONTROLLER_BUTTON_A, instance_id=1)) is None

    def test_none_instance_id_accepts_any(self) -> None:
        """Binding with no instance_id accepts any controller."""
        actions = ActionMap()
        actions.bind('jump', controller_button=pygame.CONTROLLER_BUTTON_A)
        assert actions.get_action(_button_down(pygame.CONTROLLER_BUTTON_A, instance_id=0)) == 'jump'
        assert actions.get_action(_button_down(pygame.CONTROLLER_BUTTON_A, instance_id=1)) == 'jump'

    def test_separate_maps_per_player(self) -> None:
        """Separate ActionMaps track state independently per player."""
        p1 = ActionMap()
        p1.bind('up', controller_button=pygame.CONTROLLER_BUTTON_DPAD_UP, instance_id=0)
        p2 = ActionMap()
        p2.bind('up', controller_button=pygame.CONTROLLER_BUTTON_DPAD_UP, instance_id=1)

        event_p1 = _button_down(pygame.CONTROLLER_BUTTON_DPAD_UP, instance_id=0)
        p1.handle_event(event_p1)
        p2.handle_event(event_p1)

        assert p1.is_held('up') is True
        assert p2.is_held('up') is False


class TestUnbindAndClear:
    """Tests for unbind and clear operations."""

    def test_unbind_removes_action(self) -> None:
        """Unbind removes all bindings for an action."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE, controller_button=pygame.CONTROLLER_BUTTON_A)
        actions.unbind('jump')
        assert actions.get_action(_key_down(pygame.K_SPACE)) is None
        assert actions.get_action(_button_down(pygame.CONTROLLER_BUTTON_A)) is None

    def test_clear_removes_everything(self) -> None:
        """Clear removes all bindings and state."""
        actions = ActionMap()
        actions.bind('jump', keyboard=pygame.K_SPACE)
        actions.bind('run', keyboard=pygame.K_RIGHT)
        actions.handle_event(_key_down(pygame.K_SPACE))
        actions.clear()
        assert actions.get_action(_key_down(pygame.K_SPACE)) is None
        assert actions.is_held('jump') is False


class TestPersistence:
    """Tests for serialization and deserialization."""

    def test_to_dict_round_trip(self) -> None:
        """Bindings survive a to_dict → from_dict round trip."""
        original = ActionMap()
        original.bind('jump', keyboard=pygame.K_SPACE)
        original.bind('jump', controller_button=pygame.CONTROLLER_BUTTON_A)

        data = original.to_dict()
        restored = ActionMap.from_dict(data)

        assert restored.get_action(_key_down(pygame.K_SPACE)) == 'jump'
        assert restored.get_action(_button_down(pygame.CONTROLLER_BUTTON_A)) == 'jump'

    def test_from_dict_with_defaults(self) -> None:
        """File data overrides defaults; missing actions use defaults."""
        defaults = ActionMap()
        defaults.bind('jump', keyboard=pygame.K_SPACE)
        defaults.bind('run', keyboard=pygame.K_RIGHT)

        # File only overrides 'jump' to K_RETURN
        file_data: dict[str, list[dict[str, object]]] = {
            'jump': [{'type': 'KeyDown', 'code': pygame.K_RETURN}],
        }
        restored = ActionMap.from_dict(file_data, defaults=defaults)

        # Jump is overridden
        assert restored.get_action(_key_down(pygame.K_RETURN)) == 'jump'
        assert restored.get_action(_key_down(pygame.K_SPACE)) is None
        # Run kept from defaults
        assert restored.get_action(_key_down(pygame.K_RIGHT)) == 'run'

    def test_axis_binding_round_trip(self) -> None:
        """Axis bindings survive serialization."""
        original = ActionMap()
        original.bind('move_right', controller_axis=(pygame.CONTROLLER_AXIS_LEFTX, 0.3))

        data = original.to_dict()
        restored = ActionMap.from_dict(data)

        # Feed an axis event and check it works
        restored.handle_event(_axis_motion(pygame.CONTROLLER_AXIS_LEFTX, 20000))
        assert restored.is_held('move_right') is True
