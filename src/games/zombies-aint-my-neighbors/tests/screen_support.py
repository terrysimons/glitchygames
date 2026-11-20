"""Helpers the game's screen tests share: stepping frames, pixels, presses and stand-in pads.

The member directory's name holds dashes, so tests load this module by its path from the
repository root (docs/architecture/game_packages.md, "Create the member"):
``importlib.import_module('src.games.zombies-aint-my-neighbors.tests.screen_support')``.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Protocol

import pygame

from glitchygames.events.base import HashableEvent
from glitchygames.replay.tools.golden_traces import (
    GoldenTraceEngine,
    GoldenTraceSceneManager,
    command_line,
)
from glitchygames.testing.keys import qwerty_scancode
from tests.input.stand_in_devices import STAND_IN_PAD, install_stand_in_devices
from zombies_aint_my_neighbors.roster import DeviceIdentity, DeviceKind

if TYPE_CHECKING:
    from collections.abc import Generator

    from glitchygames.scenes import Scene
    from zombies_aint_my_neighbors.roster import JoinRoster

SCREEN_SIZE = (800, 480)
FRAME_SECONDS = 1.0 / 60.0
KEYBOARD = DeviceIdentity(kind=DeviceKind.KEYBOARD, instance_id=None)


class HasRoster(Protocol):
    """A screen that keeps the join roster."""

    roster: JoinRoster


def gamepad(instance_id: int) -> DeviceIdentity:
    """Return a pad's identity.

    Returns:
        The identity.

    """
    return DeviceIdentity(kind=DeviceKind.GAMEPAD, instance_id=instance_id)


def tick_to(scene: Scene, *, seconds: float) -> None:
    """Run a scene's logic frame by frame, as the scene manager does, until ``seconds``."""
    while scene.game_time + FRAME_SECONDS / 2 < seconds:
        scene.advance_game_time(seconds=FRAME_SECONDS)
        scene.dt_tick(FRAME_SECONDS)


def rendered(scene: Scene) -> pygame.Surface:
    """Draw a scene and return the screen.

    Returns:
        The screen surface.

    """
    assert scene.screen is not None
    scene.render(scene.screen)
    return scene.screen


def exact_colour_count(
    surface: pygame.Surface, area: pygame.Rect, colour: tuple[int, int, int]
) -> int:
    """Count the pixels in an area that are exactly a colour (antialiased edges are not).

    Returns:
        The count.

    """
    area = area.clip(surface.get_rect())
    return sum(
        1
        for x in range(area.left, area.right)
        for y in range(area.top, area.bottom)
        if tuple(surface.get_at((x, y)))[:3] == colour
    )


def joined_devices(scene: HasRoster) -> list[DeviceIdentity | None]:
    """Return the device in each slot (None: free).

    Returns:
        One entry per slot.

    """
    return [None if player is None else player.device for player in scene.roster.slots]


def key_event(event_type: int, key: int) -> HashableEvent:
    """Return a key event as the engine delivers it (QWERTY scancode).

    Returns:
        The event.

    """
    return HashableEvent(event_type, key=key, mod=0, unicode='', scancode=qwerty_scancode(key=key))


def press_key(scene: Scene, key: int) -> None:
    """Press a key on a screen."""
    scene.on_key_down_event(key_event(pygame.KEYDOWN, key))


def controller_start(scene: Scene, *, instance_id: int) -> None:
    """Press START on a mapped pad (the controller layer)."""
    scene.on_controller_button_down_event(
        HashableEvent(
            pygame.CONTROLLERBUTTONDOWN,
            instance_id=instance_id,
            button=pygame.CONTROLLER_BUTTON_START,
        )
    )


def joystick_start(scene: Scene, *, instance_id: int) -> None:
    """Press START on an unmapped pad, or any pad in joystick mode (the joystick layer)."""
    scene.on_joy_button_down_event(
        HashableEvent(
            pygame.JOYBUTTONDOWN,
            instance_id=instance_id,
            joy=instance_id,
            button=pygame.CONTROLLER_BUTTON_START,
        )
    )


@contextlib.contextmanager
def running_game(
    *,
    scene_class: type[Scene],
    input_mode: str = 'auto',
    plugged_in_at_start: bool = True,
    unhandled_events_raise: bool = True,
) -> Generator[tuple[GoldenTraceEngine, Scene]]:
    """Start a screen on the real engine (without its frame loop) with a stand-in pad.

    Modelled on the joystick demo's ``running_demo``
    (src/demos/joystick-demo/tests/test_joystick_demo.py). Unhandled events raise unless a
    test passes ``unhandled_events_raise=False``: only for a path through the engine's own
    PauseScene, which leaves raw device events unhandled (master plan, Engine wishlist #10).

    Yields:
        The engine and the running scene.

    """
    blocked_before = [
        pygame.event.get_blocked(event_type) for event_type in range(pygame.NUMEVENTS)
    ]
    manager = GoldenTraceSceneManager.install()
    try:
        with command_line([
            '--windowed',
            '--resolution',
            f'{SCREEN_SIZE[0]}x{SCREEN_SIZE[1]}',
            '--log-level',
            'warning',
            '--input-mode',
            input_mode,
            # Unhandled events raise (events/base.py unhandled_event), as every test should
            *(['--no-unhandled-events'] if unhandled_events_raise else []),
        ]):
            engine = GoldenTraceEngine(game=scene_class)
        install_stand_in_devices(
            descriptors=(STAND_IN_PAD,), plugged_in_at_start=plugged_in_at_start
        )
        engine.install_game(scene_class=scene_class)
        scene = manager.active_scene
        assert isinstance(scene, scene_class)
        # The first frame, as the engine's frame loop would draw it
        rendered(scene)
        yield engine, scene
    finally:
        pygame.event.clear()
        GoldenTraceSceneManager.uninstall()
        for event_type, was_blocked in enumerate(blocked_before):
            if was_blocked:
                pygame.event.set_blocked(event_type)
            else:
                pygame.event.set_allowed(event_type)


def plug_in_the_pad(engine: GoldenTraceEngine) -> None:
    """Plug the stand-in pad in, on both layers, as SDL announces a mapped pad."""
    device_index = STAND_IN_PAD.device_index
    engine.process_joystick_event(
        HashableEvent(pygame.JOYDEVICEADDED, device_index=device_index, guid='g')
    )
    engine.process_controller_event(
        HashableEvent(pygame.CONTROLLERDEVICEADDED, device_index=device_index, guid='g')
    )
    assert engine.input_devices.get(instance_id=STAND_IN_PAD.instance_id) is not None


def unplug_the_pad(engine: GoldenTraceEngine) -> None:
    """Unplug the stand-in pad, on both layers, as SDL announces a mapped pad leaving."""
    instance_id = STAND_IN_PAD.instance_id
    engine.process_joystick_event(HashableEvent(pygame.JOYDEVICEREMOVED, instance_id=instance_id))
    engine.process_controller_event(
        HashableEvent(pygame.CONTROLLERDEVICEREMOVED, instance_id=instance_id)
    )
    assert engine.input_devices.get(instance_id=instance_id) is None
