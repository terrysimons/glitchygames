#!/usr/bin/env python3
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import argparse

from glitchygames.events import ResourceManager

log = logging.getLogger('game.midi')
log.addHandler(logging.NullHandler())


class MidiManager(ResourceManager):
    def __init__(self: Self, game: object = None) -> None:
        """
        Manage music.

        MusicManager manages music.

        Args:
        ----
        game -

        """
        super().__init__(game=game)

    @classmethod
    def args(cls: Self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        group = parser.add_argument_group('Midi Options')  # noqa: F841

        return parser
