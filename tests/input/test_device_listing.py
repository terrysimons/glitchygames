"""--list-input-devices (glitchygames/input/device_listing.py): every device, through the door."""

from __future__ import annotations

import itertools

import pygame
import pytest

from glitchygames.input import device_listing
from glitchygames.input.device_listing import (
    NO_DEVICES_PROMPT,
    DeviceEvent,
    list_input_devices,
    listen,
    listening_lines,
)
from glitchygames.sources import active_sources
from tests.input.stand_in_devices import STAND_IN_PAD, STAND_IN_STICK, install_stand_in_devices

SDL_VERSION = '.'.join(str(part) for part in pygame.get_sdl_version())
HEADER = f'Input devices (SDL {SDL_VERSION}, pygame-ce {pygame.version.ver}; input mode auto):'


def never_wait(_seconds: float) -> None:
    """Stand in for time.sleep: the listening pumps run back to back."""


def listing(*, input_mode: str = 'auto') -> list[str]:
    """Return the listing of the installed doors' devices, listening for no time, no prompt.

    Returns:
        The listing's lines.

    """
    return list_input_devices(
        sources=active_sources(), input_mode=input_mode, listen_seconds=0.0, sleep=never_wait
    )


def measured_clock(mocker, *, step: float, start: float = 0.0) -> None:
    """Make the measured clock read ``start``, then ``step`` more at each later reading."""
    mocker.patch(
        'glitchygames.clock.measured_seconds', side_effect=itertools.count(start=start, step=step)
    )


def test_every_device_is_listed_by_index_with_what_it_is():
    """A mapped pad is listed as a game controller, an unmapped stick as a joystick only."""
    install_stand_in_devices(descriptors=[STAND_IN_STICK, STAND_IN_PAD])

    assert listing() == [
        HEADER,
        "  before pumping SDL's queue: 2 devices counted",
        '  while listening (0.0 s): no device added or removed',
        '  index 0  instance 5  Stand-in Flight Stick',
        (
            '           joystick only (no game controller mapping), '
            'guid 03000000aaaa0000bbbb000000000000'
        ),
        '           3 axes, 4 buttons, 1 hat, 1 ball',
        '  index 1  instance 9  Stand-in Game Pad',
        '           game controller (SDL maps it), guid 03000000cccc0000dddd000000000000',
        '           6 axes, 15 buttons, 1 hat, 0 balls',
        '2 devices (1 game controller, 1 joystick only)',
    ]


def test_no_devices_and_no_prompt_says_so():
    """Without a prompt (not at a terminal), finding nothing is listed at once."""
    install_stand_in_devices(descriptors=[])

    assert listing(input_mode='controller') == [
        HEADER.replace('input mode auto', 'input mode controller'),
        "  before pumping SDL's queue: 0 devices counted",
        '  while listening (0.0 s): no device added or removed',
        '  none: SDL reports no joysticks or game controllers',
        '0 devices (0 game controllers, 0 joystick only)',
    ]


def test_devices_seen_are_listed_without_a_prompt():
    """When something is seen, the listing never prompts."""
    install_stand_in_devices(descriptors=[STAND_IN_STICK])
    prompts: list[str] = []

    lines = list_input_devices(
        sources=active_sources(),
        input_mode='auto',
        listen_seconds=0.0,
        prompt=prompts.append,
        sleep=never_wait,
    )

    assert prompts == []
    assert '  index 0  instance 5  Stand-in Flight Stick' in lines


def test_seeing_nothing_prompts_then_lists_the_device_plugged_in(mocker):
    """No device: prompt, wait for the first device added, then list what arrived."""
    registry = install_stand_in_devices(descriptors=[STAND_IN_STICK], plugged_in_at_start=False)
    # Counted before pumping, after listening, and after the device was added
    mocker.patch.object(registry, 'joystick_count', side_effect=[0, 0, 1])
    sources = active_sources()
    mocker.patch.object(
        sources,
        'pump_events',
        side_effect=[
            [],  # the usual listening
            [],  # waiting...
            [pygame.event.Event(pygame.JOYDEVICEADDED, device_index=0)],
        ],
    )
    measured_clock(mocker, step=1.0)
    prompts: list[str] = []

    lines = list_input_devices(
        sources=sources,
        input_mode='auto',
        listen_seconds=1.0,
        prompt=prompts.append,
        sleep=never_wait,
    )

    assert prompts == [NO_DEVICES_PROMPT]
    assert lines[1:3] == [
        "  before pumping SDL's queue: 0 devices counted",
        '  while listening (3.0 s): joystick added (index 0) at 3.00 s',
    ]
    assert '  index 0  instance 5  Stand-in Flight Stick' in lines
    assert lines[-1] == '1 device (0 game controllers, 1 joystick only)'


def test_a_device_that_cannot_be_opened_is_listed_with_its_error(mocker):
    """A device unplugged between counting and opening is listed with SDL's error."""
    registry = install_stand_in_devices(descriptors=[STAND_IN_STICK, STAND_IN_PAD])
    mocker.patch.object(registry, 'open_joystick', side_effect=pygame.error('Joystick gone'))

    lines = listing()

    assert '  index 0  could not be opened: Joystick gone' in lines
    assert '  index 1  instance 9  Stand-in Game Pad' in lines
    assert lines[-1] == '2 devices (1 game controller, 0 joystick only, 1 could not be opened)'


def test_a_device_the_door_cannot_describe_is_listed_as_a_failure(mocker):
    """An opened device without a descriptor is reported, never left out."""
    registry = install_stand_in_devices(descriptors=[STAND_IN_STICK])
    mocker.patch.object(registry, 'descriptor_for_instance', return_value=None)

    assert '  index 0  could not be opened: opened, but the door has no descriptor for it' in (
        listing()
    )


@pytest.mark.parametrize(
    ('count', 'noun', 'expected'), [(1, 'axis', '1 axis'), (2, 'axis', '2 axes')]
)
def test_axis_counts_read_as_english(count, noun, expected):
    """One axis, two axes."""
    assert device_listing._plural(count=count, noun=noun) == expected


def test_listening_pumps_until_the_time_is_up(mocker):
    """SDL's queue is pumped, pausing between pumps, until the listening time has passed."""
    install_stand_in_devices(descriptors=[])
    sources = active_sources()
    pumps = mocker.spy(sources, 'pump_events')
    # Read after each pump: 0.4, 0.8, 1.2 seconds since listening started at 0.0
    measured_clock(mocker, step=0.4, start=0.4)
    pauses: list[float] = []

    listening = listen(sources=sources, started_at=0.0, listen_seconds=1.0, sleep=pauses.append)

    assert listening.events == ()
    assert listening.seconds == pytest.approx(1.2)
    assert pumps.call_count == 3
    assert pauses == [device_listing.PUMP_INTERVAL_SECONDS] * 2


def test_device_events_are_kept_with_when_they_arrived(mocker):
    """Added and removed events on both layers are kept; every other event is dropped."""
    install_stand_in_devices(descriptors=[])
    sources = active_sources()
    mocker.patch.object(
        sources,
        'pump_events',
        side_effect=[
            [
                pygame.event.Event(pygame.JOYDEVICEADDED, device_index=0),
                pygame.event.Event(pygame.CONTROLLERDEVICEADDED, device_index=0),
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a),
            ],
            [
                pygame.event.Event(pygame.JOYDEVICEREMOVED, instance_id=3),
                pygame.event.Event(pygame.CONTROLLERDEVICEREMOVED, instance_id=3),
            ],
        ],
    )
    measured_clock(mocker, step=0.25, start=0.25)

    listening = listen(sources=sources, started_at=0.0, listen_seconds=0.5, sleep=never_wait)

    assert list(listening.events) == [
        DeviceEvent(seconds=0.25, change='added', layer='joystick', device_number=0),
        DeviceEvent(seconds=0.25, change='added', layer='controller', device_number=0),
        DeviceEvent(seconds=0.5, change='removed', layer='joystick', device_number=3),
        DeviceEvent(seconds=0.5, change='removed', layer='controller', device_number=3),
    ]


def test_waiting_listens_until_the_first_device_added(mocker):
    """Listening without a time limit stops at the first device added (a removal does not)."""
    install_stand_in_devices(descriptors=[])
    sources = active_sources()
    pumps = mocker.patch.object(
        sources,
        'pump_events',
        side_effect=[
            [],
            [pygame.event.Event(pygame.JOYDEVICEREMOVED, instance_id=2)],
            [pygame.event.Event(pygame.CONTROLLERDEVICEADDED, device_index=1)],
        ],
    )
    measured_clock(mocker, step=10.0)

    listening = listen(sources=sources, started_at=0.0, listen_seconds=None, sleep=never_wait)

    assert pumps.call_count == 3
    assert [event.change for event in listening.events] == ['removed', 'added']


def test_the_listening_lines_name_each_device_event():
    """Each event's layer, change, device and time are named."""
    lines = listening_lines(
        count_before_pumping=1,
        device_events=[
            DeviceEvent(seconds=0.02, change='added', layer='joystick', device_number=0),
            DeviceEvent(seconds=2.5, change='removed', layer='controller', device_number=7),
        ],
        listened_seconds=3.0,
    )

    assert lines == [
        "  before pumping SDL's queue: 1 device counted",
        (
            '  while listening (3.0 s): joystick added (index 0) at 0.02 s, '
            'controller removed (instance 7) at 2.50 s'
        ),
    ]
