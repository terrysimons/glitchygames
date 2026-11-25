"""The recording side of tests/audio/test_live.py's heard pans: live sounds on SDL's disk driver.

Run as ``python -m tests.audio.live_pan_probe CASE`` from the repository root, with
``SDL_AUDIODRIVER=disk`` and ``SDL_DISKAUDIOFILE`` naming the recording (as
tests/audio/channel_fade_probe.py). Only the mixer's output shows what a channel does to a chunk:
SDL_mixer drops a channel's pan when a queued chunk starts, and no call reads a pan back.

Every live sound here is a constant, so its level is its gain and a chunk cut short is no step.
Nothing the test asserts depends on when the mixer thread runs.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import numpy as np
import pygame

from glitchygames import clock
from glitchygames.audio.diagnostics import DEFAULT_BUFFER_SAMPLES, DEFAULT_SAMPLE_RATE
from glitchygames.audio.live import LiveStream, LiveVoiceOptions

if TYPE_CHECKING:
    from glitchygames.audio.synth import FloatArray

LEFT = 'left'
CENTRE_ON_A_PANNED_CHANNEL = 'centre-on-a-panned-channel'
RESTARTED = 'restarted'
PAUSED = 'paused'
STOLEN = 'stolen'
RELEASED = 'released'
MOVED = 'moved'
NEXT_USER = 'next-user'
CASES = (
    LEFT,
    CENTRE_ON_A_PANNED_CHANNEL,
    RESTARTED,
    PAUSED,
    STOLEN,
    RELEASED,
    MOVED,
    NEXT_USER,
)
LEVEL = 0.5
# The plain sound that plays on the channel after a live one (NEXT_USER): another level
NEXT_USER_LEVEL = 0.25
CHUNK_SECONDS = 0.1
FRAME_SECONDS = 1.0 / 60.0
# Long enough for several chunks to play out
PLAY_SECONDS = 0.45
# Longer than a playing and a queued chunk: the channel drains
STALL_SECONDS = 0.4
INT16_FULL_SCALE = 32767


def _constant(count: int) -> FloatArray:
    return np.full(count, LEVEL)


def _started(channel: pygame.mixer.Channel, *, pan: float) -> LiveStream:
    """Start a constant live sound on a channel.

    Returns:
        Its stream.
    """
    stream = LiveStream(
        channel=channel,
        owner='probe',
        render=_constant,
        sample_rate=DEFAULT_SAMPLE_RATE,
        options=LiveVoiceOptions(pan=pan, chunk_seconds=CHUNK_SECONDS),
    )
    stream.start()
    return stream


def _play_on(stream: LiveStream) -> None:
    """Update a stream each frame, as ``LiveAudio.update`` does."""
    for _ in range(round(PLAY_SECONDS / FRAME_SECONDS)):
        clock.raw_sleep(FRAME_SECONDS)
        stream.update()


def play(case: str) -> None:
    """Play the case's live sounds on channel 0."""
    channel = pygame.mixer.Channel(0)
    if case == CENTRE_ON_A_PANNED_CHANNEL:
        channel.set_volume(0.0, 1.0)
    stream = _started(channel, pan=0.0 if case in {CENTRE_ON_A_PANNED_CHANNEL, MOVED} else -1.0)
    _play_on(stream)
    if case == RESTARTED:
        clock.raw_sleep(STALL_SECONDS)
        _play_on(stream)
    elif case == PAUSED:
        stream.pause()
        clock.raw_sleep(STALL_SECONDS)
        stream.resume()
        _play_on(stream)
    elif case == STOLEN:
        stream.stop_now()
        stream = _started(channel, pan=1.0)
        _play_on(stream)
    elif case == RELEASED:
        stream.stop(fade_out=CHUNK_SECONDS)
        _play_on(stream)
    elif case == MOVED:
        stream.set_pan(1.0)
        _play_on(stream)
    stream.stop_now()
    if case == NEXT_USER:
        frames = np.full((DEFAULT_SAMPLE_RATE // 4, 2), NEXT_USER_LEVEL * INT16_FULL_SCALE)
        channel.play(pygame.sndarray.make_sound(frames.astype(np.int16)))
        clock.raw_sleep(STALL_SECONDS)


def main(argv: list[str]) -> int:
    """Record one case (the disk driver's file is named by ``SDL_DISKAUDIOFILE``).

    Returns:
        0, or 2 for an unknown case.
    """
    if len(argv) != 1 or argv[0] not in CASES:
        sys.stderr.write(f'usage: python -m tests.audio.live_pan_probe {"|".join(CASES)}\n')
        return 2
    pygame.mixer.init(
        frequency=DEFAULT_SAMPLE_RATE, size=-16, channels=2, buffer=DEFAULT_BUFFER_SAMPLES
    )
    play(argv[0])
    pygame.mixer.quit()  # Flushes the recording
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
