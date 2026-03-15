#!/usr/bin/env python3
"""Midi Event Manager."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Self

import pygame
from glitchygames.events import MIDI_EVENTS

if TYPE_CHECKING:
    import argparse

from glitchygames.events import MidiEvents, ResourceManager

log = logging.getLogger("game.midi")
log.addHandler(logging.NullHandler())


class MidiEventManager(ResourceManager):
    """Manage midi events."""

    class MidiEventProxy(MidiEvents, ResourceManager):
        """Proxy for MIDI events."""

        def __init__(self: Self, game: object) -> None:
            """Initialize the MIDI event proxy with a game object."""
            super().__init__(game)
            self.game = game
            self.proxies = [self.game]

        def on_midi_in_event(self: Self, event: pygame.event.Event) -> None:
            """Forward MIDI input events to the game object."""
            if hasattr(self.game, "on_midi_in_event"):
                self.game.on_midi_in_event(event)

        def on_midi_out_event(self: Self, event: pygame.event.Event) -> None:
            """Forward MIDI output events to the game object."""
            if hasattr(self.game, "on_midi_out_event"):
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
            log.debug("Failed to set allowed MIDI events: pygame not fully initialized")
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
        _group = parser.add_argument_group("Midi Options")

        return parser
