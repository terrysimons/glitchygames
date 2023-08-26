#!/usr/bin/env python3
import logging

from glitchygames.events import ResourceManager

log = logging.getLogger('game.midi')
log.addHandler(logging.NullHandler())


class MidiManager(ResourceManager):
    def __init__(self, game=None):  # noqa: W0235
        """
        Manage music.

        MusicManager manages music.

        Args:
        ----
        game -

        """
        super().__init__(game=game)

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Midi Options')  # noqa: W0612, F841

        return parser
