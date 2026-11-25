#!/usr/bin/env python3
"""Midi Event Manager.

MIDI starts only when a port is named (``--midi-input NAME``, ``--midi-output NAME``, each
repeatable): the manager opens each named port through the devices door
(``glitchygames/input/devices.py``) and holds one proxy per opened port, as the joystick manager
does (``ports``). With no port named the manager asks the door nothing about MIDI, PortMidi is
never initialized and a recording holds no MIDI answers.

A named port that is not present, or that fails to open, is logged once (naming it) and skipped:
the run goes on without it. The answers are the door's, so they are recorded and a replay gives
them again: a replay takes the recorded options, so it opens the ports the recording named
whatever ports its own command line names (``--midi-input`` is not a ``REPLAY_LOCAL_OPTIONS``
member).

``pygame.midi`` is optional: pygame's WebAssembly builds (Pyodide, pygbag) have no PortMidi, and
there the door answers "no ports", so a named port is simply absent.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

import pygame

from glitchygames.checks import required
from glitchygames.events import (
    MIDI_EVENTS,
    MidiEvent,
    MidiEvents,
    ResourceManager,
    set_event_types_allowed,
)
from glitchygames.input.devices import (
    MIDI_INPUT_KIND,
    MIDI_OUTPUT_KIND,
    MidiPortDescriptor,
    find_midi_port,
)
from glitchygames.sources import active_sources

if TYPE_CHECKING:
    import argparse
    from collections.abc import Sequence

    from glitchygames.events import HashableEvent
    from glitchygames.input.devices import OpenedMidiInput, OpenedMidiOutput

log = logging.getLogger('game.midi')
log.addHandler(logging.NullHandler())


class MidiEventManager(ResourceManager):
    """Manage midi events."""

    class MidiEventProxy(MidiEvents, ResourceManager):
        """Proxy for one opened MIDI port: forwards its events to the game, exposes the port.

        ``proxies`` lists the game and then the port, so a game calls the port's own methods
        (``poll``, ``read``, ``write_short``, ``note_on``, ...) through the proxy. The raw
        ``pygame.midi`` module is not among them: a port is opened through the devices door only.
        """

        # A proxy belongs to its manager: each construction is a new one (ResourceManager)
        SHARES_INSTANCE: ClassVar[bool] = False

        def __init__(
            self: Self,
            *,
            game: object,
            port: OpenedMidiInput | OpenedMidiOutput,
            descriptor: MidiPortDescriptor,
        ) -> None:
            """Initialize the proxy for an opened port.

            Args:
                game: The game object.
                port: The opened port (pygame's, or a replay's stand-in).
                descriptor: What the port is (kind, id, name, interface).

            """
            super().__init__(game)
            self.game: Any = game
            self.port = port
            self.descriptor = descriptor
            self.proxies = [self.game, self.port]

        def get_device_info(self: Self) -> tuple[bytes, bytes, int, int, int]:
            """Describe the port as ``pygame.midi.get_device_info`` does.

            A port object has no such method of its own (pygame's is a module function), so the
            proxy answers from the descriptor it was opened with, without asking PortMidi.

            Returns:
                ``(interface, name, is_input, is_output, opened)``; ``opened`` is 1.

            """
            is_input = self.descriptor.kind == MIDI_INPUT_KIND
            return (
                self.descriptor.interface.encode(),
                self.descriptor.name.encode(),
                int(is_input),
                int(not is_input),
                1,
            )

        @override
        def on_midi_in_event(self: Self, event: MidiEvent) -> None:
            """Forward MIDI input events to the game object."""
            if hasattr(self.game, 'on_midi_in_event'):
                self.game.on_midi_in_event(event)

        @override
        def on_midi_out_event(self: Self, event: MidiEvent) -> None:
            """Forward MIDI output events to the game object."""
            if hasattr(self.game, 'on_midi_out_event'):
                self.game.on_midi_out_event(event)

    def __init__(
        self: Self,
        game: object = None,
        *,
        input_names: Sequence[str] = (),
        output_names: Sequence[str] = (),
    ) -> None:
        """Initialize the midi event manager and open the named ports.

        Args:
            game (object): The game object.
            input_names: Names of the MIDI input ports to open (``--midi-input``).
            output_names: Names of the MIDI output ports to open (``--midi-output``).

        """
        super().__init__(game=game)
        try:
            set_event_types_allowed(event_types=MIDI_EVENTS, allowed=True)
        except pygame.error:
            log.debug('Failed to set allowed MIDI events: pygame not fully initialized')
        self.game: Any = game
        self.proxies = [game]
        self.ports: dict[tuple[str, int], MidiEventManager.MidiEventProxy] = (
            self.open_connected_midi_ports(input_names=input_names, output_names=output_names)
        )

    def open_connected_midi_ports(
        self: Self, *, input_names: Sequence[str], output_names: Sequence[str]
    ) -> dict[tuple[str, int], MidiEventManager.MidiEventProxy]:
        """Open the named ports through the devices door, as new proxies.

        With no name the door is asked nothing. A name that matches no port of its kind, or whose
        port fails to open, is logged (naming it) and skipped. A port named twice is opened once.

        Args:
            input_names: Names of the MIDI input ports to open.
            output_names: Names of the MIDI output ports to open.

        Returns:
            The proxies, by ``(kind, port id)`` (``MIDI_INPUT_KIND`` or ``MIDI_OUTPUT_KIND``).

        """
        proxies: dict[tuple[str, int], MidiEventManager.MidiEventProxy] = {}
        for kind, names in ((MIDI_INPUT_KIND, input_names), (MIDI_OUTPUT_KIND, output_names)):
            for name in names:
                self._open_named_port(kind=kind, name=name, proxies=proxies)
        return proxies

    def _open_named_port(
        self: Self,
        *,
        kind: str,
        name: str,
        proxies: dict[tuple[str, int], MidiEventManager.MidiEventProxy],
    ) -> None:
        """Open the port ``name`` of ``kind`` into ``proxies``, or log why it is skipped."""
        devices = active_sources().devices()
        port_id = find_midi_port(devices=devices, name=name, kind=kind)
        if port_id is None:
            log.warning('MIDI %s port %r is not present: skipped', kind, name)
            return
        if (kind, port_id) in proxies:
            return
        try:
            port = (
                devices.open_midi_input(port_id=port_id)
                if kind == MIDI_INPUT_KIND
                else devices.open_midi_output(port_id=port_id)
            )
        except pygame.error as error:
            log.warning('MIDI %s port %r could not be opened: %s', kind, name, error)
            return
        info = required(devices.midi_port_info(port_id=port_id), what=f'MIDI port {port_id}')
        descriptor = MidiPortDescriptor(
            kind=kind, port_id=port_id, name=info.name, interface=info.interface
        )
        proxies[kind, port_id] = MidiEventManager.MidiEventProxy(
            game=self.game, port=port, descriptor=descriptor
        )
        log.info('Opened MIDI %s port %d (%s)', kind, port_id, info.name)

    def on_midi_in_event(self: Self, event: HashableEvent) -> None:
        """Forward MIDI input events to the game object."""
        if hasattr(self.game, 'on_midi_in_event'):
            self.game.on_midi_in_event(event)

    def on_midi_out_event(self: Self, event: HashableEvent) -> None:
        """Forward MIDI output events to the game object."""
        if hasattr(self.game, 'on_midi_out_event'):
            self.game.on_midi_out_event(event)

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add midi-specific arguments to the global parser.

        This class method will get called automatically by the GameEngine class.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            argparse.ArgumentParser

        """
        group = parser.add_argument_group('Midi Options')
        group.add_argument(
            '--midi-input',
            action='append',
            default=[],
            metavar='NAME',
            help=(
                'Open the MIDI input port with this name (repeatable). With no port named, '
                'MIDI is never started. A port that is not present is logged and skipped. A '
                'replay opens the ports its recording named, whatever is given here'
            ),
        )
        group.add_argument(
            '--midi-output',
            action='append',
            default=[],
            metavar='NAME',
            help=(
                'Open the MIDI output port with this name (repeatable). With no port named, '
                'MIDI is never started. A port that is not present is logged and skipped. A '
                'replay opens the ports its recording named, whatever is given here'
            ),
        )

        return parser
