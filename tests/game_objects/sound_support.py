"""A real sound for the game objects' tests: what a game hands a ball or paddle to play.

The ball and paddle take a ``Sound`` from the game's audio engine (plans/2026-11-14-sound-
migration.md); this one comes from an audio engine with no channels, so it needs no mixer and a
play is a silent no-op.
"""

from typing import TYPE_CHECKING

from glitchygames.audio.engine import AudioEngine
from glitchygames.audio.instrument import Instrument
from glitchygames.audio.voices import ChannelPartition

if TYPE_CHECKING:
    from glitchygames.audio.library import Sound


def a_sound() -> Sound:
    """Return a short square-wave sound from an audio engine with no channels.

    Returns:
        The sound.
    """
    audio = AudioEngine(partition=ChannelPartition(live=(), library=(), legacy_count=0))
    return audio.sound(Instrument(wave='square'), pitch='C5', length=0.05)
