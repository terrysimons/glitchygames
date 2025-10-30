#!/usr/bin/env python3
"""Midi Event Manager."""

from __future__ import annotations

import logging
import pygame
from glitchygames.events import MIDI_EVENTS
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import argparse

from glitchygames.events import ResourceManager

log = logging.getLogger("game.midi")
log.addHandler(logging.NullHandler())


class MidiManager(ResourceManager):
    """Manage midi events."""

    def __init__(self: Self, game: object = None) -> None:
        """Initialize the midi event manager.

        Args:
            game (object): The game object.

        Returns:
            None

        """
        super().__init__(game=game)
        try:
            pygame.event.set_allowed(MIDI_EVENTS)
        except Exception:
            pass
        self.game = game
        self.proxies = []

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add midi-specific arguments to the global parser.

        This class method will get called automatically by the GameEngine class.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            argparse.ArgumentParser

        """
        group = parser.add_argument_group("Midi Options")  # noqa: F841

        return parser
