"""Helpers for the voice table's tests: baked sounds, a reserved mixer, a table, channel spies."""

import itertools
from typing import ClassVar

import numpy as np
import pygame

from glitchygames.audio.buses import BusTree
from glitchygames.audio.library import Sound
from glitchygames.audio.spec import PlaybackDefaults
from glitchygames.audio.voices import ChannelPartition, VoiceTable, reserve_channels
from tests.audio.library_support import start_mixer

SAMPLE_RATE = 44100
FRAME_SECONDS = 1 / 60
# The spec's defaults (global constraints): live pool 4, library 32, legacy 8
LIVE_POOL = 4
LIBRARY_CHANNELS = 32
LEGACY_CHANNELS = 8
GAME_SCENE = 'game scene'
OTHER_SCENE = 'other scene'
PLAY_DEFAULTS = {
    'volume': 1.0,
    'pan': 0.0,
    'bus': 'effects',
    'priority': 50,
    'loop': False,
    'persist': False,
}

_identity_numbers = itertools.count()


def baked_sound(*, seconds: float, name: str = 'tone') -> Sound:
    """Make a compiled sound of exactly ``seconds`` (a quiet 440 Hz sine) at the test rate.

    Returns:
        The sound.
    """
    frame_count = round(seconds * SAMPLE_RATE)
    time_points = np.arange(frame_count) / SAMPLE_RATE
    samples_float = 0.25 * np.sin(2 * np.pi * 440.0 * time_points)
    samples_int16 = (samples_float * 32767).astype(np.int16)
    sound = Sound(
        name=name,
        identity_key=f'{name}-{next(_identity_numbers)}',
        sample_rate=SAMPLE_RATE,
        playback_defaults=PlaybackDefaults(),
    )
    sound.install(
        samples_float=samples_float, samples_int16=samples_int16, peak=0.25, sample_rate=SAMPLE_RATE
    )
    return sound


def start_reserved_mixer(
    *,
    live_pool: int = LIVE_POOL,
    library_channels: int = LIBRARY_CHANNELS,
    legacy_channels: int = LEGACY_CHANNELS,
) -> ChannelPartition:
    """Start a stereo mixer on the dummy driver and partition its channels.

    Returns:
        The partition.
    """
    start_mixer(channels=2)
    return reserve_channels(
        live_pool=live_pool, library_channels=library_channels, legacy_channels=legacy_channels
    )


def unreserved_buses() -> BusTree:
    """The default buses without the ui and music reservations, for tables of a few channels.

    Returns:
        The buses.
    """
    buses = BusTree()
    buses['ui'].reserved_channels = 0
    buses['music'].reserved_channels = 0
    return buses


def make_table(
    partition: ChannelPartition, *, buses: BusTree | None = None, compile_for_play=None
) -> VoiceTable:
    """Build a voice table whose compile step returns the sound itself unless one is given.

    Returns:
        The table.
    """
    return VoiceTable(
        partition=partition,
        buses=buses if buses is not None else BusTree(),
        compile_for_play=compile_for_play
        if compile_for_play is not None
        else (lambda sound: sound),
    )


def advance_frames(table: VoiceTable, *, count: int, paused_owners=frozenset()) -> None:
    """Advance the table ``count`` frames of 1/60 s."""
    for _ in range(count):
        table.advance(dt=FRAME_SECONDS, paused_owners=paused_owners)


class RecordingChannel(pygame.mixer.Channel):
    """A real mixer channel that also records what the voice table asks of it."""

    calls: ClassVar[list[tuple[int, str, tuple[object, ...]]]] = []

    def play(self, *args, **kwargs):
        """Record, then play."""
        RecordingChannel.calls.append((self.id, 'play', (*args, *kwargs.values())))
        return super().play(*args, **kwargs)

    def set_volume(self, *args):
        """Record, then set the volume."""
        RecordingChannel.calls.append((self.id, 'set_volume', args))
        return super().set_volume(*args)

    def fadeout(self, *args):
        """Record, then fade out."""
        RecordingChannel.calls.append((self.id, 'fadeout', args))
        return super().fadeout(*args)

    def stop(self):
        """Record, then stop."""
        RecordingChannel.calls.append((self.id, 'stop', ()))
        return super().stop()

    def pause(self):
        """Record, then pause."""
        RecordingChannel.calls.append((self.id, 'pause', ()))
        return super().pause()

    def unpause(self):
        """Record, then unpause."""
        RecordingChannel.calls.append((self.id, 'unpause', ()))
        return super().unpause()


def calls_named(calls, name: str) -> list[tuple[int, tuple[object, ...]]]:
    """The recorded calls of one kind, as (channel index, arguments).

    Returns:
        The calls.
    """
    return [(index, arguments) for index, kind, arguments in calls if kind == name]
