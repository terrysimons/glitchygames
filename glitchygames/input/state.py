"""Polled input as one immutable snapshot per frame: the polled-input door.

Once per frame, right after the frame's pump (``GameEngine.process_events``), the engine asks
the active sources (glitchygames/sources.py) for an ``InputSnapshot`` and makes it
``current_input()`` until the next frame's pump. Live sources read pygame
(``capture_live_snapshot``); a replay hands back the recorded snapshot. Code reads held keys,
modifiers, the mouse and device positions from the snapshot, never from pygame; a guard test
(added later in Part 1 of the gameplay replay plan) rejects direct polling.

Timing: a frame runs ``dt_tick`` before it processes events, so logic in ``dt_tick`` reads the
snapshot captured at the previous frame's pump. That is the same state
``pygame.key.get_pressed()`` returned there before snapshots existed: SDL updates its polled
state when the event queue is pumped, and the previous frame's pump was the last one. Event
handlers and everything after the pump read the snapshot captured this frame.

Recordings store only what changed from the previous frame (``snapshot_changes``), so idle
frames add nothing; ``apply_snapshot_changes`` rebuilds the snapshot.
"""

from __future__ import annotations

import dataclasses
import functools
from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast, override

import pygame
from pygame.key import ScancodeWrapper

if TYPE_CHECKING:
    from collections.abc import Sequence

# Length of pygame.key.get_pressed(): one entry per SDL scancode
SCANCODE_COUNT = 512
MOUSE_BUTTON_COUNT = 3

# Device instance id -> positions. Mapping is a real import (not TYPE_CHECKING only), so
# typing.get_type_hints(InputSnapshot) resolves every field
type DeviceAxes = Mapping[int, tuple[float, ...]]
type DeviceButtons = Mapping[int, tuple[bool, ...]]
type DeviceHats = Mapping[int, tuple[tuple[int, int], ...]]
# Game controller layer: instance id -> values indexed by pygame.CONTROLLER_AXIS_* /
# CONTROLLER_BUTTON_* ids, axes on pygame's int scale (-32768..32767)
type ControllerAxes = Mapping[int, tuple[int, ...]]
type ControllerButtons = Mapping[int, tuple[bool, ...]]

_EMPTY: Mapping[int, Any] = MappingProxyType({})


@dataclasses.dataclass(frozen=True)
class InputSnapshot:
    """The polled input of one frame.

    Attributes:
        pressed_scancodes: SDL scancodes held this frame.
        modifiers: pygame KMOD bits.
        mouse_position: The mouse position in window pixels.
        mouse_buttons: (left, middle, right) held.
        mouse_focused: Whether the window has mouse focus.
        device_axes: Joystick/controller instance id -> axis positions (-1.0..1.0).
        device_buttons: Instance id -> buttons held.
        device_hats: Instance id -> hat positions.
        controller_axes: Game controller instance id -> axis values by CONTROLLER_AXIS_* id
            (pygame's Controller.get_axis scale, -32768..32767).
        controller_buttons: Game controller instance id -> buttons held by CONTROLLER_BUTTON_*
            id.

    """

    pressed_scancodes: frozenset[int]
    modifiers: int
    mouse_position: tuple[int, int]
    mouse_buttons: tuple[bool, bool, bool]
    mouse_focused: bool
    device_axes: DeviceAxes = _EMPTY
    device_buttons: DeviceButtons = _EMPTY
    device_hats: DeviceHats = _EMPTY
    controller_axes: ControllerAxes = _EMPTY
    controller_buttons: ControllerButtons = _EMPTY

    def __post_init__(self) -> None:
        """Freeze the device mappings and their values (a snapshot never changes).

        Each device's values become a tuple, and each hat position a 2-tuple, so a snapshot
        built from lists (JSON hands lists back) equals one built from tuples.
        """
        object.__setattr__(
            self,
            'device_axes',
            MappingProxyType({
                device_id: tuple(axes) for device_id, axes in self.device_axes.items()
            }),
        )
        object.__setattr__(
            self,
            'device_buttons',
            MappingProxyType({
                device_id: tuple(buttons) for device_id, buttons in self.device_buttons.items()
            }),
        )
        object.__setattr__(
            self,
            'device_hats',
            MappingProxyType({
                device_id: tuple((hat_x, hat_y) for hat_x, hat_y in hats)
                for device_id, hats in self.device_hats.items()
            }),
        )
        object.__setattr__(
            self,
            'controller_axes',
            MappingProxyType({
                device_id: tuple(axes) for device_id, axes in self.controller_axes.items()
            }),
        )
        object.__setattr__(
            self,
            'controller_buttons',
            MappingProxyType({
                device_id: tuple(buttons) for device_id, buttons in self.controller_buttons.items()
            }),
        )

    @override
    def __eq__(self, other: object) -> bool:
        """Compare field by field (the mapping proxies compare by content).

        Returns:
            True when every field is equal; NotImplemented for a non-snapshot.

        """
        if not isinstance(other, InputSnapshot):
            return NotImplemented
        return (
            self.pressed_scancodes == other.pressed_scancodes
            and self.modifiers == other.modifiers
            and self.mouse_position == other.mouse_position
            and self.mouse_buttons == other.mouse_buttons
            and self.mouse_focused == other.mouse_focused
            and dict(self.device_axes) == dict(other.device_axes)
            and dict(self.device_buttons) == dict(other.device_buttons)
            and dict(self.device_hats) == dict(other.device_hats)
            and dict(self.controller_axes) == dict(other.controller_axes)
            and dict(self.controller_buttons) == dict(other.controller_buttons)
        )

    @override
    def __hash__(self) -> int:
        """Hash every field.

        The device mappings are hashed through frozensets of their items (their values are
        tuples), so equal snapshots hash equal whatever order the devices were added in.

        Returns:
            The hash.

        """
        return hash((
            self.pressed_scancodes,
            self.modifiers,
            self.mouse_position,
            self.mouse_buttons,
            self.mouse_focused,
            frozenset(self.device_axes.items()),
            frozenset(self.device_buttons.items()),
            frozenset(self.device_hats.items()),
            frozenset(self.controller_axes.items()),
            frozenset(self.controller_buttons.items()),
        ))

    @functools.cached_property
    def pressed_keys(self) -> ScancodeWrapper:
        """The held keys indexable by key code, exactly like ``pygame.key.get_pressed()``.

        Indexing it by a pygame.K_* code needs SDL initialized (pygame.init()), which a running
        engine always has; before it, every lookup is False. Built once per snapshot on first
        use (about 10 microseconds; it is immutable, so every caller shares it). The class is
        bound at import (``from pygame.key import ScancodeWrapper``), so code that later replaces
        the ``pygame.key`` module attribute (test mocks) cannot change what this returns.
        """
        return ScancodeWrapper(
            tuple(scancode in self.pressed_scancodes for scancode in range(SCANCODE_COUNT))
        )

    def key_pressed(self, key: int) -> bool:
        """Return whether ``key`` (a pygame.K_* code) is held this frame.

        The key-code-to-scancode lookup needs SDL initialized (pygame.init()), which a running
        engine always has; before it, every lookup is False. ``key`` stays positional: this is a
        drop-in for ``pygame.key.get_pressed()[key]``.

        Returns:
            True when the key is held.

        """
        return bool(self.pressed_keys[key])

    def axis(self, *, device_id: int, axis: int) -> float:
        """Return an axis position; 0.0 for an unknown device or axis.

        Returns:
            The axis position.

        """
        axes = self.device_axes.get(device_id, ())
        return axes[axis] if 0 <= axis < len(axes) else 0.0

    def button(self, *, device_id: int, button: int) -> bool:
        """Return whether a device button is held; False when unknown.

        Returns:
            True when the button is held.

        """
        buttons = self.device_buttons.get(device_id, ())
        return buttons[button] if 0 <= button < len(buttons) else False

    def hat(self, *, device_id: int, hat: int) -> tuple[int, int]:
        """Return a hat position; (0, 0) when unknown.

        Returns:
            The hat position.

        """
        hats = self.device_hats.get(device_id, ())
        return hats[hat] if 0 <= hat < len(hats) else (0, 0)

    def controller_axis(self, *, device_id: int, axis: int) -> int:
        """Return a game controller axis value by CONTROLLER_AXIS_* id; 0 when unknown.

        Args:
            device_id: The controller's instance id.
            axis: A pygame.CONTROLLER_AXIS_* id.

        Returns:
            The value on pygame's Controller.get_axis scale.

        """
        axes = self.controller_axes.get(device_id, ())
        return axes[axis] if 0 <= axis < len(axes) else 0

    def controller_button(self, *, device_id: int, button: int) -> bool:
        """Return whether a game controller button is held by CONTROLLER_BUTTON_* id.

        Args:
            device_id: The controller's instance id.
            button: A pygame.CONTROLLER_BUTTON_* id.

        Returns:
            True when held; False when unknown.

        """
        buttons = self.controller_buttons.get(device_id, ())
        return buttons[button] if 0 <= button < len(buttons) else False


IDLE_INPUT = InputSnapshot(
    pressed_scancodes=frozenset(),
    modifiers=0,
    mouse_position=(0, 0),
    mouse_buttons=(False, False, False),
    mouse_focused=False,
)

_CURRENT: list[InputSnapshot] = [IDLE_INPUT]


def _held_scancodes(*, pressed: Sequence[bool]) -> frozenset[int]:
    """Return the scancodes held in a ``pygame.key.get_pressed()`` result.

    pygame-ce's ScancodeWrapper refuses iteration, and its subscript takes key codes, not
    scancodes. Its tuple ``count`` and ``index`` are not overridden and see the flags in
    scancode order, so they find the held scancodes (usually none) without iterating.

    Returns:
        The held scancodes.

    """
    held_scancodes: list[int] = []
    held_count = pressed.count(True)
    search_start = 0
    while len(held_scancodes) < held_count:
        scancode = pressed.index(True, search_start)
        held_scancodes.append(scancode)
        search_start = scancode + 1
    return frozenset(held_scancodes)


def capture_live_snapshot(
    *,
    device_axes: DeviceAxes = _EMPTY,
    device_buttons: DeviceButtons = _EMPTY,
    device_hats: DeviceHats = _EMPTY,
    controller_axes: ControllerAxes = _EMPTY,
    controller_buttons: ControllerButtons = _EMPTY,
) -> InputSnapshot:
    """Read pygame's polled state now (the live door; the only polling in the package).

    Args:
        device_axes: Device positions read by the live device registry (Task 5).
        device_buttons: Device buttons read by the live device registry.
        device_hats: Device hats read by the live device registry.
        controller_axes: Game controller axes read by the live device registry.
        controller_buttons: Game controller buttons read by the live device registry.

    Returns:
        The snapshot.

    """
    mouse_x, mouse_y = pygame.mouse.get_pos()
    left, middle, right = pygame.mouse.get_pressed(num_buttons=MOUSE_BUTTON_COUNT)
    return InputSnapshot(
        pressed_scancodes=_held_scancodes(pressed=pygame.key.get_pressed()),
        modifiers=int(pygame.key.get_mods()),
        mouse_position=(int(mouse_x), int(mouse_y)),
        mouse_buttons=(bool(left), bool(middle), bool(right)),
        mouse_focused=bool(pygame.mouse.get_focused()),
        device_axes=device_axes,
        device_buttons=device_buttons,
        device_hats=device_hats,
        controller_axes=controller_axes,
        controller_buttons=controller_buttons,
    )


def current_input() -> InputSnapshot:
    """Return the snapshot captured at the latest pump (IDLE_INPUT before the first pump).

    In ``dt_tick``, which runs before the frame's pump, that is the previous frame's snapshot.

    Returns:
        The snapshot.

    """
    return _CURRENT[0]


def set_current_input(*, snapshot: InputSnapshot) -> None:
    """Make ``snapshot`` this frame's input (GameEngine.process_events, once per frame)."""
    _CURRENT[0] = snapshot


def reset_current_input() -> None:
    """Back to IDLE_INPUT (a new run, or a test)."""
    _CURRENT[0] = IDLE_INPUT


def _device_mapping_changes(
    *, previous: Mapping[int, tuple[Any, ...]], current: Mapping[int, tuple[Any, ...]]
) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    for device_id in sorted(set(previous) | set(current)):
        if device_id not in current:
            changes[str(device_id)] = None
        elif previous.get(device_id) != current[device_id]:
            # Hat positions are (x, y) tuples; JSON stores them as lists
            changes[str(device_id)] = [
                list(cast('tuple[Any, ...]', value)) if isinstance(value, tuple) else value
                for value in current[device_id]
            ]
    return changes


def snapshot_changes(*, previous: InputSnapshot, current: InputSnapshot) -> dict[str, Any]:
    """Return the JSON-safe fields of ``current`` that differ from ``previous``.

    Returns:
        A dict of changed fields; device fields hold only changed devices (None = removed).

    """
    changes: dict[str, Any] = {}
    if current.pressed_scancodes != previous.pressed_scancodes:
        changes['pressed_scancodes'] = sorted(current.pressed_scancodes)
    if current.modifiers != previous.modifiers:
        changes['modifiers'] = current.modifiers
    if current.mouse_position != previous.mouse_position:
        changes['mouse_position'] = list(current.mouse_position)
    if current.mouse_buttons != previous.mouse_buttons:
        changes['mouse_buttons'] = list(current.mouse_buttons)
    if current.mouse_focused != previous.mouse_focused:
        changes['mouse_focused'] = current.mouse_focused
    for field_name in (
        'device_axes',
        'device_buttons',
        'device_hats',
        'controller_axes',
        'controller_buttons',
    ):
        device_changes = _device_mapping_changes(
            previous=getattr(previous, field_name), current=getattr(current, field_name)
        )
        if device_changes:
            changes[field_name] = device_changes
    return changes


def _apply_device_changes(
    *, previous: Mapping[int, tuple[Any, ...]], changes: dict[str, Any], is_hat: bool
) -> dict[int, tuple[Any, ...]]:
    devices = dict(previous)
    for device_text, values in changes.items():
        device_id = int(device_text)
        if values is None:
            devices.pop(device_id, None)
        elif is_hat:
            devices[device_id] = tuple((int(value[0]), int(value[1])) for value in values)
        else:
            devices[device_id] = tuple(values)
    return devices


def apply_snapshot_changes(*, previous: InputSnapshot, changes: dict[str, Any]) -> InputSnapshot:
    """Rebuild a snapshot from the previous one and recorded changes.

    Returns:
        The new snapshot.

    """
    mouse_buttons = changes.get('mouse_buttons', previous.mouse_buttons)
    mouse_position = changes.get('mouse_position', previous.mouse_position)
    return InputSnapshot(
        pressed_scancodes=frozenset(changes.get('pressed_scancodes', previous.pressed_scancodes)),
        modifiers=int(changes.get('modifiers', previous.modifiers)),
        mouse_position=(int(mouse_position[0]), int(mouse_position[1])),
        mouse_buttons=(bool(mouse_buttons[0]), bool(mouse_buttons[1]), bool(mouse_buttons[2])),
        mouse_focused=bool(changes.get('mouse_focused', previous.mouse_focused)),
        device_axes=_apply_device_changes(
            previous=previous.device_axes, changes=changes.get('device_axes', {}), is_hat=False
        ),
        device_buttons=_apply_device_changes(
            previous=previous.device_buttons,
            changes=changes.get('device_buttons', {}),
            is_hat=False,
        ),
        device_hats=_apply_device_changes(
            previous=previous.device_hats, changes=changes.get('device_hats', {}), is_hat=True
        ),
        controller_axes=_apply_device_changes(
            previous=previous.controller_axes,
            changes=changes.get('controller_axes', {}),
            is_hat=False,
        ),
        controller_buttons=_apply_device_changes(
            previous=previous.controller_buttons,
            changes=changes.get('controller_buttons', {}),
            is_hat=False,
        ),
    )
