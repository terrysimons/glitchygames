"""Polled input as one immutable snapshot per frame (glitchygames/input/state.py)."""

from __future__ import annotations

import json
import typing
from typing import TYPE_CHECKING, Any

import pygame
import pytest

from glitchygames.input.state import (
    IDLE_INPUT,
    SCANCODE_COUNT,
    InputSnapshot,
    apply_snapshot_changes,
    capture_live_snapshot,
    current_input,
    set_current_input,
    snapshot_changes,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

LEFT_ARROW_SCANCODE = 80  # SDL_SCANCODE_LEFT; pygame.K_LEFT maps to it


@pytest.fixture(autouse=True)
def initialized_pygame():
    """Make sure SDL is initialized, so these tests do not depend on test order.

    Key-code lookups (ScancodeWrapper[K_LEFT]) need SDL initialized: before pygame.init()
    every lookup is False. A running engine always has it; these unit tests make sure.
    """
    if not pygame.get_init():
        pygame.init()


def snapshot_with(**fields: Any) -> InputSnapshot:
    """Return a snapshot with every field at rest except ``fields``.

    Returns:
        The snapshot.

    """
    values: dict[str, Any] = {
        'pressed_scancodes': frozenset(),
        'modifiers': 0,
        'mouse_position': (0, 0),
        'mouse_buttons': (False, False, False),
        'mouse_focused': True,
        'device_axes': {},
        'device_buttons': {},
        'device_hats': {},
    }
    values.update(fields)
    return InputSnapshot(**values)


class TestQueries:
    """Held keys and device positions are read from the snapshot."""

    def test_key_pressed_maps_key_codes_to_scancodes(self):
        """key_pressed takes a pygame.K_* code, as get_pressed()[key] does."""
        snapshot = snapshot_with(pressed_scancodes=frozenset({LEFT_ARROW_SCANCODE}))
        assert snapshot.key_pressed(pygame.K_LEFT)
        assert not snapshot.key_pressed(pygame.K_RIGHT)

    def test_pressed_keys_is_a_drop_in_for_get_pressed(self):
        """pressed_keys is a ScancodeWrapper of the same length as get_pressed()."""
        snapshot = snapshot_with(pressed_scancodes=frozenset({LEFT_ARROW_SCANCODE}))
        pressed = snapshot.pressed_keys
        assert isinstance(pressed, pygame.key.ScancodeWrapper)
        assert len(pressed) == SCANCODE_COUNT
        assert pressed[pygame.K_LEFT]

    def test_device_queries_default_to_rest(self):
        """Unknown devices, axes, buttons and hats read as at rest."""
        snapshot = snapshot_with(
            device_axes={7: (0.5, -1.0)},
            device_hats={7: ((1, 0),)},
            device_buttons={7: (True,)},
        )
        assert snapshot.axis(device_id=7, axis=1) == -1.0
        assert snapshot.hat(device_id=7, hat=0) == (1, 0)
        assert snapshot.button(device_id=7, button=0)
        assert snapshot.axis(device_id=9, axis=0) == 0.0
        assert snapshot.button(device_id=7, button=5) is False
        assert snapshot.hat(device_id=7, hat=3) == (0, 0)


class TestLiveCapture:
    """capture_live_snapshot reads pygame's polled state."""

    def test_held_scancodes_come_from_a_real_scancode_wrapper(self, mocker: MockerFixture):
        """pygame-ce's ScancodeWrapper refuses iteration; the held scancodes are still found."""
        held = {4, LEFT_ARROW_SCANCODE, SCANCODE_COUNT - 1}
        mocker.patch.object(
            pygame.key,
            'get_pressed',
            return_value=pygame.key.ScancodeWrapper(
                tuple(scancode in held for scancode in range(SCANCODE_COUNT))
            ),
        )
        snapshot = capture_live_snapshot()
        assert snapshot.pressed_scancodes == frozenset(held)
        assert snapshot.key_pressed(pygame.K_LEFT)

    def test_nothing_held_is_an_empty_set(self, mocker: MockerFixture):
        """With no key held the snapshot holds no scancodes."""
        mocker.patch.object(
            pygame.key,
            'get_pressed',
            return_value=pygame.key.ScancodeWrapper((False,) * SCANCODE_COUNT),
        )
        assert capture_live_snapshot().pressed_scancodes == frozenset()

    @pytest.mark.usefixtures('mock_pygame_patches')
    def test_the_centralized_get_pressed_mock_refuses_iteration_like_pygame_ce(self):
        """The shared mock behaves like ScancodeWrapper, so iterating code fails under it too."""
        pressed = pygame.key.get_pressed()
        assert isinstance(pressed, tuple)
        assert len(pressed) == SCANCODE_COUNT
        with pytest.raises(TypeError, match='Iterating over key states is not supported'):
            iter(pressed)
        assert pressed.count(True) == 0


class TestFreezing:
    """A snapshot never changes, whatever it was built from."""

    def test_list_device_values_become_tuples(self):
        """Lists (as JSON hands them back) are stored as tuples; hats as tuples of 2-tuples."""
        from_lists = snapshot_with(
            device_axes={3: [0.25, -0.5]},
            device_buttons={3: [False, True]},
            device_hats={3: [[0, -1], [1, 1]]},
        )
        assert from_lists.device_axes[3] == (0.25, -0.5)
        assert from_lists.device_buttons[3] == (False, True)
        assert from_lists.device_hats[3] == ((0, -1), (1, 1))
        assert all(isinstance(hat, tuple) for hat in from_lists.device_hats[3])
        assert from_lists == snapshot_with(
            device_axes={3: (0.25, -0.5)},
            device_buttons={3: (False, True)},
            device_hats={3: ((0, -1), (1, 1))},
        )

    def test_changing_the_source_mapping_does_not_change_the_snapshot(self):
        """The snapshot keeps its own copy of the device mappings and values."""
        axes = [0.25]
        source = {3: axes}
        snapshot = snapshot_with(device_axes=source)
        axes.append(1.0)
        source[4] = [0.5]
        assert dict(snapshot.device_axes) == {3: (0.25,)}

    def test_type_hints_resolve(self):
        """Every annotation names a real module-level type (get_type_hints evaluates them)."""
        hints = typing.get_type_hints(InputSnapshot)
        assert set(hints) == {
            'pressed_scancodes',
            'modifiers',
            'mouse_position',
            'mouse_buttons',
            'mouse_focused',
            'device_axes',
            'device_buttons',
            'device_hats',
        }


class TestCurrentInput:
    """current_input() is the frame's snapshot."""

    def test_idle_until_set(self):
        """Before any frame (and after the conftest reset) the input is idle."""
        assert current_input() == IDLE_INPUT

    def test_set_current_input(self):
        """set_current_input makes the snapshot the frame's input."""
        snapshot = snapshot_with(modifiers=pygame.KMOD_LSHIFT)
        set_current_input(snapshot=snapshot)
        assert current_input() is snapshot


class TestChanges:
    """Recordings store only what changed; the changes rebuild the snapshot."""

    def test_no_changes_is_an_empty_dict(self):
        """An unchanged frame records nothing."""
        assert snapshot_changes(previous=IDLE_INPUT, current=IDLE_INPUT) == {}

    @pytest.mark.parametrize(
        'current',
        [
            snapshot_with(pressed_scancodes=frozenset({LEFT_ARROW_SCANCODE, 4})),
            snapshot_with(modifiers=pygame.KMOD_CTRL, mouse_position=(10, 20)),
            snapshot_with(mouse_buttons=(True, False, True), mouse_focused=False),
            snapshot_with(
                device_axes={3: (0.25,)},
                device_buttons={3: (False, True)},
                device_hats={3: ((0, -1),)},
            ),
        ],
    )
    def test_changes_round_trip_through_json(self, current: InputSnapshot):
        """The changes survive JSON and rebuild exactly the snapshot they came from."""
        changes = json.loads(json.dumps(snapshot_changes(previous=IDLE_INPUT, current=current)))
        assert apply_snapshot_changes(previous=IDLE_INPUT, changes=changes) == current

    def test_a_removed_device_is_recorded_and_removed(self):
        """A device that disappears is recorded as None and removed on rebuild."""
        previous = snapshot_with(device_axes={3: (0.25,)})
        changes = snapshot_changes(previous=previous, current=IDLE_INPUT)
        assert apply_snapshot_changes(previous=previous, changes=changes) == IDLE_INPUT
