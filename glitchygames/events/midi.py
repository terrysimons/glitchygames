#!/usr/bin/env python3
"""Midi Event Manager.

``pygame.midi`` is optional: pygame's WebAssembly builds (Pyodide, pygbag) have no PortMidi, so
there the manager forwards MIDI events to the game but has no subsystem to proxy to.
"""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING, Any, Self, override

import pygame

from glitchygames.events import MIDI_EVENTS

if TYPE_CHECKING:
    import argparse
    from types import ModuleType

from glitchygames.events import MidiEvent, MidiEvents, ResourceManager

log = logging.getLogger('game.midi')
log.addHandler(logging.NullHandler())


def import_midi_module() -> ModuleType | None:
    """Import pygame.midi, or return None where this pygame build has no PortMidi.

    Returns:
        The module, or None.

    """
    try:
        return importlib.import_module('pygame.midi')
    except ImportError:
        log.info('pygame.midi is unavailable in this pygame build: no MIDI devices')
        return None


MIDI_MODULE = import_midi_module()


class MidiEventManager(ResourceManager):
    """Manage midi events."""

    class MidiEventProxy(MidiEvents, ResourceManager):
        """Proxy for MIDI events."""

        def __init__(self: Self, game: object) -> None:
            """Initialize the MIDI event proxy with a game object."""
            super().__init__(game)
            self.game: Any = game
            # Proxy to game first, then pygame.midi for subsystem queries
            # (get_count, get_device_info, get_default_input_id, etc.), where this pygame
            # build has it (MIDI_MODULE is None without PortMidi)
            self.proxies = [self.game] if MIDI_MODULE is None else [self.game, MIDI_MODULE]

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

    def __init__(self: Self, game: object = None) -> None:
        """Initialize the midi event manager.

        Args:
            game (object): The game object.

        """
        super().__init__(game=game)
        try:
            pygame.event.set_allowed(MIDI_EVENTS)
        except pygame.error:
            log.debug('Failed to set allowed MIDI events: pygame not fully initialized')
        self.game = game
        self.proxies = [MidiEventManager.MidiEventProxy(game=game)]

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add midi-specific arguments to the global parser.

        This class method will get called automatically by the GameEngine class.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            argparse.ArgumentParser

        """
        _group = parser.add_argument_group('Midi Options')

        return parser
