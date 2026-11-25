#!/usr/bin/env python3
"""Bring a PipeWire session's HDMI outputs to a volume, unmuted, with an HDMI default.

Run as the session's user, with its XDG_RUNTIME_DIR (ansible/roles/raspberry_pi_audio, the Ubuntu
Raspberry Pi 5s). It is the owner's HDMI audio procedure (plans/2026-11-04-raspberry-pi-ci-
runner.md, "HDMI audio on the Ubuntu Pi 5s"), steps 4 to 6, done by a script:

- Each HDMI port is an ALSA card named ``vc4hdmi<N>`` (``aplay -l``), seen in ``pw-dump`` as an
  Audio/Device whose ``alsa.id`` is that name, and its output as an Audio/Sink carrying the same
  ``alsa.id`` (WirePlumber copies the card's ``alsa.*`` properties onto each node it makes:
  /usr/share/wireplumber/scripts/monitors/alsa.lua, 0.5.13, "for rule matching purposes").
- A port with no sink whose stereo HDMI profile is available but inactive gets that profile
  (``wpctl set-profile``), and its sink is waited for.
- Each sink not at the volume, or muted, is unmuted and set to it (``wpctl set-mute``,
  ``wpctl set-volume``), then read back. Volumes are wpctl's: on WirePlumber's cubic scale (wpctl
  sets its mixer's scale to cubic: src/tools/wpctl.c, 0.5.13,
  https://gitlab.freedesktop.org/pipewire/wireplumber/-/blob/0.5.13/src/tools/wpctl.c), so 75%
  reads back as ``Volume: 0.75`` and is stored as 0.75 ** 3 = 0.421875 on the channels.
- The default sink is kept when it is one of the HDMI sinks; otherwise HDMI0's sink, or the
  lowest-numbered port's, becomes the default (``wpctl set-default``).

WirePlumber remembers what wpctl sets (its ``device.restore-routes`` and
``node.restore-default-targets`` settings, both on by default), so the result survives a login
or a reboot. Object ids are local to the running session, so each run reads them afresh.

It prints one JSON object: ``changed``; ``actions`` (each wpctl command it ran, or with
``--dry-run`` would run); ``ports`` (per port: its sink's name, volume and mute before and after,
or why it is pending); ``default`` (the default sink before and after); ``pending`` and
``problems`` (lists of sentences). It exits 1 when there are problems: a sink that did not take
the volume, or PipeWire that could not be read. A port with no display, or a session with no
HDMI device at all (another user holds the seat), is pending, not a problem.
Tests: tests/test_ansible_raspberry_pis.py (on the Pis' own pw-dump, 2026-11-20).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections.abc import Callable
from typing import Any, NamedTuple

# The Pi 5's HDMI cards (aplay -l: vc4hdmi0, vc4hdmi1); the number is the port's
HDMI_CARD = re.compile(r'^vc4hdmi(\d+)$')
STEREO_PROFILE = 'output:hdmi-stereo'
# wpctl get-volume's line: "Volume: %.2f" and " [MUTED]" (src/tools/wpctl.c, 0.5.13)
VOLUME_LINE = re.compile(r'^Volume: (\d+(?:\.\d+)?)( \[MUTED\])?\s*$')
# How long a profile change may take to bring its sink, in polls of this many seconds
SINK_WAIT_ATTEMPTS = 20
SINK_WAIT_SECONDS = 0.25

type PipeWireObject = dict[str, Any]
type Runner = Callable[[list[str]], str]


class Volume(NamedTuple):
    """A sink's volume as wpctl reports it (the cubic scale) and whether it is muted.

    A NamedTuple, not a pydantic model: this runs on the Pi's system Python, which has no pydantic.
    """

    level: float
    muted: bool


def properties(item: PipeWireObject) -> dict[str, Any]:
    """Return an object's properties: a node's or device's are in ``info``, metadata's at the top.

    Returns:
        The properties (empty when it has none).

    """
    return (item.get('info') or {}).get('props') or item.get('props') or {}


def port_number(item: PipeWireObject) -> int | None:
    """Return the HDMI port an object belongs to, from its ``alsa.id``.

    Returns:
        The port number, or None for an object of no HDMI card.

    """
    match = HDMI_CARD.match(str(properties(item).get('alsa.id', '')))
    return int(match.group(1)) if match else None


def hdmi_devices(objects: list[PipeWireObject]) -> dict[int, PipeWireObject]:
    """Return the HDMI cards, by port.

    Returns:
        Each port's Audio/Device.

    """
    return {
        number: item
        for item in objects
        if item.get('type') == 'PipeWire:Interface:Device'
        and properties(item).get('media.class') == 'Audio/Device'
        and (number := port_number(item)) is not None
    }


def hdmi_sinks(objects: list[PipeWireObject]) -> dict[int, PipeWireObject]:
    """Return the HDMI outputs, by port.

    Returns:
        Each port's Audio/Sink.

    """
    return {
        number: item
        for item in objects
        if item.get('type') == 'PipeWire:Interface:Node'
        and properties(item).get('media.class') == 'Audio/Sink'
        and (number := port_number(item)) is not None
    }


def default_sink_name(objects: list[PipeWireObject]) -> str | None:
    """Return the session's default sink, from the ``default`` metadata's ``default.audio.sink``.

    Returns:
        Its node name, or None when the session names none.

    """
    for item in objects:
        if item.get('type') != 'PipeWire:Interface:Metadata':
            continue
        if properties(item).get('metadata.name') != 'default':
            continue
        for entry in item.get('metadata') or []:
            if entry.get('key') != 'default.audio.sink':
                continue
            value = entry.get('value')
            # pw-dump gives Spa:String:JSON values parsed; a plain string is JSON text
            if isinstance(value, str):
                value = json.loads(value)
            if isinstance(value, dict) and value.get('name'):
                return str(value['name'])
    return None


def inactive_stereo_profile(device: PipeWireObject) -> int | None:
    """Return the index of a card's stereo HDMI profile when it is available but not active.

    pactl list cards in the procedure; here the card's EnumProfile and Profile params.

    Returns:
        The profile's index, or None when it is active, unavailable (no display) or absent.

    """
    parameters = (device.get('info') or {}).get('params') or {}
    active = {profile.get('name') for profile in parameters.get('Profile') or []}
    if STEREO_PROFILE in active:
        return None
    for profile in parameters.get('EnumProfile') or []:
        if profile.get('name') == STEREO_PROFILE and profile.get('available') != 'no':
            return int(profile['index'])
    return None


def parse_volume(text: str) -> Volume:
    """Read wpctl get-volume's output.

    Returns:
        The volume.

    Raises:
        ValueError: When the output is not wpctl's volume line.

    """
    match = VOLUME_LINE.match(text.strip())
    if match is None:
        message = f'not a wpctl volume line: {text!r}'
        raise ValueError(message)
    return Volume(level=float(match.group(1)), muted=match.group(2) is not None)


def at_target(volume: Volume, *, volume_percent: int) -> bool:
    """Return whether a volume is the deployment's: unmuted, at the percentage to wpctl's 2 places.

    Returns:
        Whether nothing needs changing.

    """
    return not volume.muted and round(volume.level, 2) == round(volume_percent / 100, 2)


def run_command(argv: list[str]) -> str:
    """Run a PipeWire tool and return its output.

    Returns:
        What it printed.

    """
    return subprocess.run(argv, check=True, capture_output=True, text=True, timeout=30).stdout


def read_objects(run: Runner) -> list[PipeWireObject]:
    """Return the session's objects, as pw-dump prints them.

    Returns:
        The objects.

    """
    return json.loads(run(['pw-dump']))


class Session:
    """One session's run: what it changes (or with a dry run would), and what it reports."""

    def __init__(
        self, *, volume_percent: int, dry_run: bool, run: Runner, sleep: Callable[[float], None]
    ) -> None:
        """Hold how to reach the session and start an empty report."""
        self.volume_percent = volume_percent
        self.dry_run = dry_run
        self.run = run
        self.sleep = sleep
        self.actions: list[list[str]] = []
        self.pending: list[str] = []
        self.problems: list[str] = []

    def change(self, argv: list[str]) -> None:
        """Record a command that changes the session, and run it unless this is a dry run."""
        self.actions.append(argv)
        if not self.dry_run:
            self.run(argv)

    def read_volume(self, sink_id: str) -> Volume:
        """Return a sink's volume, as wpctl reads it.

        Returns:
            The volume.

        """
        return parse_volume(self.run(['wpctl', 'get-volume', sink_id]))

    def turn_on_stereo_profiles(
        self, *, devices: dict[int, PipeWireObject], sinks: dict[int, PipeWireObject]
    ) -> list[int]:
        """Step 4: give each port with no sink its stereo profile, when it is available.

        Returns:
            The ports whose profile was set (or with a dry run would be).

        """
        switched = []
        for number, device in sorted(devices.items()):
            if number in sinks:
                continue
            index = inactive_stereo_profile(device)
            if index is not None:
                self.change(['wpctl', 'set-profile', str(device['id']), str(index)])
                switched.append(number)
        return switched

    def wait_for_sinks(self, ports: list[int]) -> list[PipeWireObject]:
        """Wait until WirePlumber has made a sink for each port whose profile was set.

        Returns:
            The session's objects as last read.

        """
        objects = read_objects(self.run)
        for _ in range(SINK_WAIT_ATTEMPTS):
            if all(number in hdmi_sinks(objects) for number in ports):
                break
            self.sleep(SINK_WAIT_SECONDS)
            objects = read_objects(self.run)
        return objects

    def set_port(
        self, *, number: int, sink: PipeWireObject | None, switched: bool
    ) -> dict[str, Any]:
        """Step 5: unmute a port's sink at the volume, and read it back.

        Returns:
            The port's part of the report.

        """
        port: dict[str, Any] = {'port': f'HDMI{number}'}
        if sink is None:
            reason = (
                'its stereo profile was set but no sink appeared'
                if switched and not self.dry_run
                else 'no sink: no audio-capable display is connected to it, or its card offers no '
                'stereo HDMI profile'
            )
            port['pending'] = reason
            self.pending.append(f'HDMI{number}: {reason}')
            return port
        sink_id = str(sink['id'])
        port['sink'] = properties(sink).get('node.name')
        before = self.read_volume(sink_id)
        port['before'] = before._asdict()
        if not at_target(before, volume_percent=self.volume_percent):
            self.change(['wpctl', 'set-mute', sink_id, '0'])
            self.change(['wpctl', 'set-volume', sink_id, f'{self.volume_percent}%'])
        if self.dry_run:
            return port
        # WirePlumber applies a volume through the card's route, so the node may report the
        # old one for a moment: read until it holds, or the wait runs out
        after = self.read_volume(sink_id)
        for _ in range(SINK_WAIT_ATTEMPTS):
            if at_target(after, volume_percent=self.volume_percent):
                break
            self.sleep(SINK_WAIT_SECONDS)
            after = self.read_volume(sink_id)
        port['after'] = after._asdict()
        if not at_target(after, volume_percent=self.volume_percent):
            self.problems.append(
                f'HDMI{number} ({port["sink"]}) reads {after.level:.2f}'
                f'{" muted" if after.muted else ""}, not {self.volume_percent / 100:.2f} unmuted'
            )
        return port

    def choose_default(
        self, *, current: str | None, sinks: dict[int, PipeWireObject]
    ) -> str | None:
        """Step 6: keep an HDMI default; else make HDMI0's sink, or the lowest port's, the default.

        Returns:
            The default sink's name afterwards.

        """
        names = {properties(sink).get('node.name') for sink in sinks.values()}
        if not sinks or current in names:
            return current
        preferred = sinks[min(sinks)]
        self.change(['wpctl', 'set-default', str(preferred['id'])])
        return properties(preferred).get('node.name')


def apply(
    *,
    volume_percent: int,
    dry_run: bool,
    run: Runner,
    sleep: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """Bring the session's HDMI outputs to the volume, unmuted, with an HDMI default.

    Returns:
        The report (see the module docstring).

    """
    session = Session(
        volume_percent=volume_percent,
        dry_run=dry_run,
        run=run,
        sleep=time.sleep if sleep is None else sleep,
    )
    objects = read_objects(run)
    devices = hdmi_devices(objects)
    if not devices and not hdmi_sinks(objects):
        session.pending.append(
            'no HDMI card in this session: its user does not hold the seat, so it has no access '
            'to the sound devices (logind gives them to the active session only)'
        )
    switched = session.turn_on_stereo_profiles(devices=devices, sinks=hdmi_sinks(objects))
    if switched and not dry_run:
        objects = session.wait_for_sinks(switched)
    sinks = hdmi_sinks(objects)
    ports = [
        session.set_port(number=number, sink=sinks.get(number), switched=number in switched)
        for number in sorted(set(devices) | set(sinks))
    ]
    current = default_sink_name(objects)
    chosen = session.choose_default(current=current, sinks=sinks)
    return {
        'changed': bool(session.actions) and not dry_run,
        'actions': [' '.join(argv) for argv in session.actions],
        'ports': ports,
        'default': {'before': current, 'after': chosen},
        'pending': session.pending,
        'problems': session.problems,
    }


def main(argv: list[str] | None = None) -> int:
    """Apply the volume and print the report.

    Returns:
        The exit status: 1 when there are problems, else 0.

    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--volume-percent', type=int, required=True)
    parser.add_argument(
        '--dry-run', action='store_true', help='report what would change, changing nothing'
    )
    arguments = parser.parse_args(argv)
    try:
        report = apply(
            volume_percent=arguments.volume_percent, dry_run=arguments.dry_run, run=run_command
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError) as error:
        report = {
            'changed': False,
            'actions': [],
            'ports': [],
            'default': {'before': None, 'after': None},
            'pending': [],
            'problems': [f'PipeWire could not be read or set: {error}'],
        }
    json.dump(report, sys.stdout)
    sys.stdout.write('\n')
    return 1 if report['problems'] else 0


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
