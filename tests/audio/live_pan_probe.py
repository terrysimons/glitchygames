"""The recording side of tests/audio/test_live.py's heard pans: live sounds on SDL's disk driver.

Run as ``python -m tests.audio.live_pan_probe CASE`` from the repository root, with
``SDL_AUDIODRIVER=disk`` and ``SDL_DISKAUDIOFILE`` naming the recording (as
tests/audio/channel_fade_probe.py). Only the mixer's output shows what a channel does to a chunk:
SDL_mixer drops a channel's pan when a queued chunk starts, and no call reads a pan back.

Every live sound here is a constant, so its level is its gain and a chunk cut short is no step.
Each case goes on until enough chunks have been rendered, which a slow device only makes longer
(``WAIT_LIMIT_SECONDS`` bounds it, and passing it fails the probe); the restart waits until the
channel has drained. No level the test asserts depends on how fast the mixer thread runs.
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
    from collections.abc import Callable

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
# Chunks rendered per stretch: all but the last two have played (a chunk cut short by a restart
# over a queued one, the bug record's open sibling, leaves plenty)
CHUNKS_PER_STRETCH = 8
# No stretch takes this long, however slow the device
WAIT_LIMIT_SECONDS = 50.0
PAUSE_SECONDS = 0.1
INT16_FULL_SCALE = 32767


_rendered_chunk_counts: list[int] = []


def _constant(count: int) -> FloatArray:
    _rendered_chunk_counts.append(count)
    return np.full(count, LEVEL)


def _wait_until(condition: Callable[[], bool], *, stream: LiveStream | None = None) -> None:
    """Wait for a condition, updating a stream each frame as ``LiveAudio.update`` does.

    Raises:
        TimeoutError: After ``WAIT_LIMIT_SECONDS``.
    """
    waited = 0.0
    while not condition():
        if waited > WAIT_LIMIT_SECONDS:
            message = 'the mixer played too slowly: the recording would prove nothing'
            raise TimeoutError(message)
        clock.raw_sleep(FRAME_SECONDS)
        waited += FRAME_SECONDS
        if stream is not None:
            stream.update()


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
    """Play a stretch of chunks."""
    target = len(_rendered_chunk_counts) + CHUNKS_PER_STRETCH
    _wait_until(lambda: len(_rendered_chunk_counts) >= target, stream=stream)


def play(case: str) -> None:
    """Play the case's live sounds on channel 0."""
    channel = pygame.mixer.Channel(0)
    if case == CENTRE_ON_A_PANNED_CHANNEL:
        channel.set_volume(0.0, 1.0)
    stream = _started(channel, pan=0.0 if case in {CENTRE_ON_A_PANNED_CHANNEL, MOVED} else -1.0)
    _play_on(stream)
    if case == RESTARTED:
        _wait_until(lambda: not channel.get_busy() and channel.get_sound() is None)
        _play_on(stream)
    elif case == PAUSED:
        stream.pause()
        clock.raw_sleep(PAUSE_SECONDS)
        stream.resume()
        _play_on(stream)
    elif case == STOLEN:
        stream.stop_now()
        stream = _started(channel, pan=1.0)
        _play_on(stream)
    elif case == RELEASED:
        stream.stop(fade_out=CHUNK_SECONDS)
        _wait_until(lambda: stream.is_finished, stream=stream)
    elif case == MOVED:
        stream.set_pan(1.0)
        _play_on(stream)
    stream.stop_now()
    if case == NEXT_USER:
        frames = np.full((DEFAULT_SAMPLE_RATE // 4, 2), NEXT_USER_LEVEL * INT16_FULL_SCALE)
        channel.play(pygame.sndarray.make_sound(frames.astype(np.int16)))
        _wait_until(lambda: not channel.get_busy())


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
