"""The recording side of tests/audio/test_live.py's chunks heard whole, on SDL's disk driver.

Run as ``python -m tests.audio.live_restart_probe`` with ``SDL_AUDIODRIVER=disk`` and
``SDL_DISKAUDIOFILE`` naming the recording. Each chunk is a constant at a level of its own, so the
recording says how much of it was heard. Every update is made with pygame's end callback pending
(tests/audio/pending_callback.py): the moment at which a restart used to cut the queued chunk.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import numpy as np
import pygame

from glitchygames.audio.diagnostics import DEFAULT_BUFFER_SAMPLES, DEFAULT_SAMPLE_RATE
from glitchygames.audio.live import LiveStream, LiveVoiceOptions
from tests.audio.pending_callback import gil_held, until_idle_with_a_chunk_queued

if TYPE_CHECKING:
    from glitchygames.audio.synth import FloatArray

CHUNK_SECONDS = 0.1
CHUNK_SAMPLES = int(CHUNK_SECONDS * DEFAULT_SAMPLE_RATE)
UPDATE_COUNT = 8
LEVEL_STEP = 1.0 / 64.0


def chunk_level(number: int) -> float:
    """The level of chunk ``number`` (1 is the first), before the centre gain.

    Returns:
        The level.
    """
    return number * LEVEL_STEP


def main() -> int:
    """Record the chunks.

    Returns:
        0.
    """
    pygame.mixer.init(
        frequency=DEFAULT_SAMPLE_RATE, size=-16, channels=2, buffer=DEFAULT_BUFFER_SAMPLES
    )
    channel = pygame.mixer.Channel(0)
    rendered: list[int] = []

    def _numbered(count: int) -> FloatArray:
        rendered.append(count)
        return np.full(count, chunk_level(len(rendered)))

    stream = LiveStream(
        channel=channel,
        owner='probe',
        render=_numbered,
        sample_rate=DEFAULT_SAMPLE_RATE,
        options=LiveVoiceOptions(chunk_seconds=CHUNK_SECONDS),
    )
    stream.start()
    for _ in range(UPDATE_COUNT):
        with gil_held():
            until_idle_with_a_chunk_queued(channel, keep_queued=stream.update)
            stream.update()
    stream.stop_now()
    pygame.mixer.quit()  # Flushes the recording
    return 0


if __name__ == '__main__':
    sys.exit(main())
