"""A mixer channel caught with pygame's end callback pending, on the real mixer.

pygame's callback waits for the GIL (bugs/2026-11-25-live-sounds-restart-mid-chunk.md), so holding
the GIL until the channel reads idle keeps the callback from running, however fast or slow the
mixer or the machine is. Nothing here asks for a chunk to end at a time: the wait is on the channel,
bounded by ``WAIT_LIMIT_SECONDS`` only so that a broken mixer fails instead of hanging.
"""

from __future__ import annotations

import contextlib
import sys
from typing import TYPE_CHECKING

from glitchygames import clock

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    import pygame

# Never asked for the GIL within a test
HELD_SWITCH_INTERVAL_SECONDS = 100.0
# Longer than a thread already waiting for the GIL at the old interval (5 ms) waits to ask for it
OLD_REQUEST_SECONDS = 0.02
WAIT_LIMIT_SECONDS = 20.0


@contextlib.contextmanager
def gil_held() -> Generator[None]:
    """Give the GIL up only where a call does (``Channel.unpause``, ``stop``, ``play``)."""
    previous_interval = sys.getswitchinterval()
    sys.setswitchinterval(HELD_SWITCH_INTERVAL_SECONDS)
    try:
        started = clock.raw_counter_seconds()
        while clock.raw_counter_seconds() - started < OLD_REQUEST_SECONDS:
            pass
        yield
    finally:
        sys.setswitchinterval(previous_interval)


def spin_until(condition: Callable[[], bool]) -> None:
    """Wait for a condition without giving up the GIL.

    Raises:
        TimeoutError: After ``WAIT_LIMIT_SECONDS``.
    """
    started = clock.raw_counter_seconds()
    while not condition():
        if clock.raw_counter_seconds() - started > WAIT_LIMIT_SECONDS:
            message = 'the mixer never got there'
            raise TimeoutError(message)


def until_idle_with_a_chunk_queued(
    channel: pygame.mixer.Channel, *, keep_queued: Callable[[], object]
) -> None:
    """Under ``gil_held``: wait until the channel reads idle with a queued chunk about to start.

    A machine that stalled before the GIL was held may have played the queue out: ``keep_queued``
    (the stream's ``update``) is then called until the channel is playing with a chunk queued.
    """

    def _is_pending() -> bool:
        if channel.get_queue() is None or channel.get_sound() is None:
            keep_queued()
        return not channel.get_busy() and None not in {channel.get_sound(), channel.get_queue()}

    spin_until(_is_pending)
