"""Put back the process state running an engine changes, after each test (used by tests/harness.py).

An engine run sets these for the whole process and leaves them set, as a game's process ends with
its game: SDL's blocked event types (the controller types in joystick input mode), the mixer's
channel count (the engine's partition only grows it), the window caption, and
``SDL_MOUSE_FOCUS_CLICKTHROUGH``. In the suite they would carry to every later test on the worker:
a posted controller event silently dropped, 44 mixer channels where a fresh process has 8. So they
are reset to what the run started with, for every item (autouse fixtures reach only test
functions: an item a collector makes could run an engine in this process and gets none; the golden
replays' items run theirs in a child process). Nothing fails: running an engine is the
tests' business. State a test must put back itself is tests/leaked_state_guard.py's.

What has stopped (pygame, its display or its mixer, quit by the test) is left alone: it starts
again as a fresh process's does.
"""

from __future__ import annotations

import functools
import os

import pygame
from pydantic import BaseModel, ConfigDict

# SDL reads it as a hint: a click that focuses the window is also a button press
CLICKTHROUGH_VARIABLE = 'SDL_MOUSE_FOCUS_CLICKTHROUGH'
CLICKTHROUGH_FOR_RUN = os.environ.get(CLICKTHROUGH_VARIABLE)
# pygame's custom event types (pygame.event.custom_type) are given out from USEREVENT up: more than
# this many are never made by one run
CUSTOM_EVENT_TYPE_COUNT = 64


def _event_types() -> tuple[int, ...]:
    """Return every event type pygame names, and its first custom ones.

    Returns:
        The types, lowest first.

    """
    named = {
        value
        for name, value in vars(pygame).items()
        if name.isupper()
        and isinstance(value, int)
        and pygame.NOEVENT < value < pygame.USEREVENT
        and pygame.event.event_name(value) not in {'Unknown', 'UserEvent'}
    }
    custom = range(pygame.USEREVENT, pygame.USEREVENT + CUSTOM_EVENT_TYPE_COUNT)
    return (*sorted(named), *custom)


EVENT_TYPES = _event_types()


class EngineWrittenState(BaseModel):
    """What the run started with.

    Attributes:
        blocked_types: The blocked event types (of ``EVENT_TYPES``).
        caption: The window's title and icon title; empty without a window.
        channel_count: The mixer's channels, or None when it could not start.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    blocked_types: frozenset[int]
    caption: tuple[str, ...]
    channel_count: int | None


def blocked_types() -> frozenset[int]:
    """Return the event types of ``EVENT_TYPES`` SDL is blocking (its display must be running).

    Returns:
        The types.

    """
    return frozenset(filter(pygame.event.get_blocked, EVENT_TYPES))


@functools.cache
def engine_written_state_for_run() -> EngineWrittenState:
    """Read the state, once for this process: the first call is before the first test's setup.

    Returns:
        The state the run started with.

    """
    # Blocked by the engine and by every test's setup (tests/harness.py
    # ensure_pygame_graceful_quit, which says why), so it is part of what a test starts with
    pygame.event.set_blocked(pygame.SYSWMEVENT)
    return EngineWrittenState(
        blocked_types=blocked_types(),
        caption=tuple(pygame.display.get_caption()),
        channel_count=(
            None if pygame.mixer.get_init() is None else pygame.mixer.get_num_channels()
        ),
    )


def reset_engine_written_state(*, run_state: EngineWrittenState) -> None:
    """Put back what differs from the run's start; a test that changed nothing costs the reads.

    Args:
        run_state: What the run started with.

    """
    if CLICKTHROUGH_FOR_RUN is None:
        os.environ.pop(CLICKTHROUGH_VARIABLE, None)
    elif os.environ.get(CLICKTHROUGH_VARIABLE) != CLICKTHROUGH_FOR_RUN:
        os.environ[CLICKTHROUGH_VARIABLE] = CLICKTHROUGH_FOR_RUN
    if pygame.display.get_init():
        blocked_now = blocked_types()
        if newly_blocked := blocked_now - run_state.blocked_types:
            pygame.event.set_allowed(list(newly_blocked))
        if newly_allowed := run_state.blocked_types - blocked_now:
            pygame.event.set_blocked(list(newly_allowed))
        if run_state.caption and tuple(pygame.display.get_caption()) != run_state.caption:
            pygame.display.set_caption(*run_state.caption)
    # A grown mixer's extra channels are silent (end_of_test_sound_problems) and reserved by
    # nothing (release_channels): both ran in the fixtures' teardown
    if (
        run_state.channel_count is not None
        and pygame.mixer.get_init() is not None
        and pygame.mixer.get_num_channels() != run_state.channel_count
    ):
        pygame.mixer.set_num_channels(run_state.channel_count)
