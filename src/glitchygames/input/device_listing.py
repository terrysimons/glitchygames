"""``--list-input-devices``: print every joystick and game controller the game would see, then exit.

``GameEngine`` runs ``list_input_devices`` in place of the game when the option is given (the
game's scene is never built, nothing is recorded):

1. start pygame's joystick and game controller subsystems, as the event managers do, and count
   the devices before SDL's queue is ever pumped (what the managers' startup count sees);
2. listen: pump SDL's queue through the doors for ``LISTEN_SECONDS``, keeping each device added
   or removed event (both layers) with when it arrived. macOS reports a pad that is already
   connected as a device-added event once SDL pumps, so the count before pumping can miss it;
3. open every device through the devices door (``active_sources().devices()``), as a game
   controller when SDL maps it and as a joystick otherwise, and describe it with the door's
   descriptor, the one a recording would hold; a device that cannot be opened (unplugged since
   it was counted) is listed with the error;
4. when nothing was found and the run can prompt (the engine passes ``prompt`` only when stdin
   and stdout are a terminal), write ``NO_DEVICES_PROMPT``, listen until the first device is
   added (Ctrl-C ends the run, exit ``INTERRUPTED``) and open again;
5. write the listing to stdout: the count before pumping, the device events and when they
   came (which tell a pad SDL knew at startup from one it reported only later), then each
   device. The run then ends normally (exit ``SUCCESS``).

Everything goes through the doors, so the doors guard (tests/test_engine_doors.py) holds and the
tests list stand-in devices (tests/input/stand_in_devices.py).
"""

from __future__ import annotations

import operator
from typing import TYPE_CHECKING, Literal

import pygame
import pygame._sdl2.controller
from pydantic import BaseModel, ConfigDict

from glitchygames import clock
from glitchygames.input.devices import CONTROLLER_KIND

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from glitchygames.input.devices import DeviceDescriptor, DeviceRegistry
    from glitchygames.sources import EngineSources

# How long SDL's queue is pumped before opening, so devices macOS reports as added are counted
LISTEN_SECONDS = 1.0
# The pause between pumps while listening
PUMP_INTERVAL_SECONDS = 0.05
# Written when nothing was found and the run can prompt; the listing then waits for a device
NO_DEVICES_PROMPT = (
    'No input devices found: plug one in or turn one on now (Ctrl-C to stop waiting)...'
)
# The device events kept while listening: (change, layer, the field naming the device)
DEVICE_EVENT_TYPES: dict[
    int, tuple[Literal['added', 'removed'], Literal['joystick', 'controller'], str]
] = {
    pygame.JOYDEVICEADDED: ('added', 'joystick', 'device_index'),
    pygame.JOYDEVICEREMOVED: ('removed', 'joystick', 'instance_id'),
    pygame.CONTROLLERDEVICEADDED: ('added', 'controller', 'device_index'),
    pygame.CONTROLLERDEVICEREMOVED: ('removed', 'controller', 'instance_id'),
}


class DeviceEvent(BaseModel):
    """One device added or removed while listening.

    Attributes:
        seconds: When it arrived, in seconds since the listing started.
        change: ``added`` or ``removed``.
        layer: ``joystick`` or ``controller`` (SDL sends both for a mapped pad).
        device_number: The device index (added) or instance id (removed), as SDL names it.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    seconds: float
    change: Literal['added', 'removed']
    layer: Literal['joystick', 'controller']
    device_number: int


class Listening(BaseModel):
    """What one listen heard.

    Attributes:
        events: The device events, in arrival order.
        seconds: When it stopped, in seconds since the listing started.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    events: tuple[DeviceEvent, ...]
    seconds: float


# The listing's indent for a device's detail lines (under its name)
DETAIL_INDENT = ' ' * 11


def _plural(*, count: int, noun: str) -> str:
    """Return ``count`` with ``noun``, plural unless the count is one.

    Returns:
        E.g. ``'1 axis'``, ``'6 axes'``, ``'2 buttons'``.

    """
    if count == 1:
        return f'{count} {noun}'
    plural = 'axes' if noun == 'axis' else f'{noun}s'
    return f'{count} {plural}'


def device_lines(*, descriptor: DeviceDescriptor) -> list[str]:
    """Return one device's lines: index, instance and name, then its mapping and its controls.

    Args:
        descriptor: The device, as the door described it when it was opened.

    Returns:
        The lines.

    """
    if descriptor.kind == CONTROLLER_KIND:
        mapping = 'game controller (SDL maps it)'
    else:
        mapping = 'joystick only (no game controller mapping)'
    guid = 'unknown' if descriptor.guid is None else descriptor.guid
    controls = ', '.join([
        _plural(count=descriptor.axis_count, noun='axis'),
        _plural(count=descriptor.button_count, noun='button'),
        _plural(count=descriptor.hat_count, noun='hat'),
        _plural(count=descriptor.ball_count, noun='ball'),
    ])
    return [
        f'  index {descriptor.device_index}  instance {descriptor.instance_id}  {descriptor.name}',
        f'{DETAIL_INDENT}{mapping}, guid {guid}',
        f'{DETAIL_INDENT}{controls}',
    ]


def _describe_event(*, event: DeviceEvent) -> str:
    """Return e.g. ``joystick added (index 0) at 0.02 s``.

    Returns:
        The description.

    """
    naming = 'index' if event.change == 'added' else 'instance'
    return f'{event.layer} {event.change} ({naming} {event.device_number}) at {event.seconds:.2f} s'


def listening_lines(
    *, count_before_pumping: int, device_events: Sequence[DeviceEvent], listened_seconds: float
) -> list[str]:
    """Return the count before pumping and the device events heard, with when they came.

    Args:
        count_before_pumping: The joystick count before SDL's queue was pumped.
        device_events: The device events, in arrival order.
        listened_seconds: How long the listing listened, in all.

    Returns:
        The two lines.

    """
    heard = (
        ', '.join(_describe_event(event=event) for event in device_events)
        if device_events
        else 'no device added or removed'
    )
    counted = _plural(count=count_before_pumping, noun='device')
    return [
        f"  before pumping SDL's queue: {counted} counted",
        f'  while listening ({listened_seconds:.1f} s): {heard}',
    ]


def header_line(*, input_mode: str) -> str:
    """Return the listing's first line: SDL's and pygame's versions and the input mode.

    Args:
        input_mode: The run's ``--input-mode``.

    Returns:
        The line.

    """
    sdl_version = '.'.join(str(part) for part in pygame.get_sdl_version())
    versions = f'SDL {sdl_version}, pygame-ce {pygame.version.ver}'
    return f'Input devices ({versions}; input mode {input_mode}):'


def listing_lines(
    *,
    descriptors: list[DeviceDescriptor],
    failures: dict[int, str],
    header: str,
    listening: list[str],
) -> list[str]:
    """Return the whole listing: a header, the listening, each device (or failure), a summary.

    Args:
        descriptors: The devices opened, by device index.
        failures: The error for each device index that could not be opened.
        header: ``header_line``'s line.
        listening: ``listening_lines``'s lines.

    Returns:
        The lines.

    """
    lines = [header, *listening]
    entries: list[tuple[int, list[str]]] = [
        (descriptor.device_index, device_lines(descriptor=descriptor)) for descriptor in descriptors
    ]
    entries.extend(
        (device_index, [f'  index {device_index}  could not be opened: {error}'])
        for device_index, error in failures.items()
    )
    for _device_index, entry_lines in sorted(entries, key=operator.itemgetter(0)):
        lines.extend(entry_lines)
    if not entries:
        lines.append('  none: SDL reports no joysticks or game controllers')
    controllers = sum(1 for descriptor in descriptors if descriptor.kind == CONTROLLER_KIND)
    summary = [
        _plural(count=controllers, noun='game controller'),
        f'{len(descriptors) - controllers} joystick only',
    ]
    if failures:
        summary.append(f'{len(failures)} could not be opened')
    device_count = len(descriptors) + len(failures)
    lines.append(f'{_plural(count=device_count, noun="device")} ({", ".join(summary)})')
    return lines


def open_every_device(*, devices: DeviceRegistry) -> tuple[list[DeviceDescriptor], dict[int, str]]:
    """Open every device SDL counts through the door, as a game controller when it is mapped.

    Args:
        devices: The devices door.

    Returns:
        The descriptors of the devices opened, and the error for each index that failed.

    """
    descriptors: list[DeviceDescriptor] = []
    failures: dict[int, str] = {}
    for device_index in range(devices.joystick_count()):
        try:
            if devices.is_controller(device_index=device_index):
                joystick_view = devices.open_controller(device_index=device_index).as_joystick()
            else:
                joystick_view = devices.open_joystick(device_index=device_index)
        except pygame.error as error:
            failures[device_index] = str(error)
            continue
        descriptor = devices.descriptor_for_instance(instance_id=joystick_view.get_instance_id())
        if descriptor is None:
            failures[device_index] = 'opened, but the door has no descriptor for it'
            continue
        descriptors.append(descriptor)
    return descriptors, failures


def listen(
    *,
    sources: EngineSources,
    started_at: float,
    listen_seconds: float | None,
    sleep: Callable[[float], None] | None = None,
) -> Listening:
    """Pump SDL's queue, keeping its device events, for a time or until a device is added.

    Other events are dropped: no game is running to take them.

    Args:
        sources: The installed doors.
        started_at: When the listing started (``clock.measured_seconds``); times count from it.
        listen_seconds: How long to listen, from ``started_at``; None listens until a device is
            added (the prompt's wait, which only Ctrl-C ends otherwise).
        sleep: Pauses between pumps (tests pass one that does not wait); None is
            glitchygames/clock.py's raw sleep, looked up when called.

    Returns:
        The events heard and when listening stopped.

    """
    events: list[DeviceEvent] = []
    while True:
        batch = sources.pump_events()
        now = clock.measured_seconds() - started_at
        for event in batch:
            known = DEVICE_EVENT_TYPES.get(event.type)
            if known is None:
                continue
            change, layer, field = known
            events.append(
                DeviceEvent(
                    seconds=now,
                    change=change,
                    layer=layer,
                    device_number=int(getattr(event, field)),
                )
            )
        if listen_seconds is None:
            if any(event.change == 'added' for event in events):
                return Listening(events=tuple(events), seconds=now)
        elif now >= listen_seconds:
            return Listening(events=tuple(events), seconds=now)
        (clock.raw_sleep if sleep is None else sleep)(PUMP_INTERVAL_SECONDS)


def list_input_devices(
    *,
    sources: EngineSources,
    input_mode: str,
    listen_seconds: float = LISTEN_SECONDS,
    prompt: Callable[[str], None] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> list[str]:
    """Start the joystick subsystems, listen, open every device and list it (see the docstring).

    Args:
        sources: The installed doors.
        input_mode: The run's ``--input-mode``, named in the header.
        listen_seconds: How long to listen before opening.
        prompt: Writes ``NO_DEVICES_PROMPT`` when nothing was found, then the listing waits for
            a device; None never prompts or waits (not at a terminal).
        sleep: Pauses between pumps; None is glitchygames/clock.py's raw sleep (``listen``).

    Returns:
        The listing's lines.

    """
    pygame.joystick.init()
    pygame._sdl2.controller.init()
    devices = sources.devices()
    count_before_pumping = devices.joystick_count()
    started_at = clock.measured_seconds()
    listening = listen(
        sources=sources, started_at=started_at, listen_seconds=listen_seconds, sleep=sleep
    )
    events = list(listening.events)
    descriptors, failures = open_every_device(devices=devices)
    if not descriptors and not failures and prompt is not None:
        prompt(NO_DEVICES_PROMPT)
        listening = listen(sources=sources, started_at=started_at, listen_seconds=None, sleep=sleep)
        events.extend(listening.events)
        descriptors, failures = open_every_device(devices=devices)
    return listing_lines(
        descriptors=descriptors,
        failures=failures,
        listening=listening_lines(
            count_before_pumping=count_before_pumping,
            device_events=events,
            listened_seconds=listening.seconds,
        ),
        header=header_line(input_mode=input_mode),
    )
