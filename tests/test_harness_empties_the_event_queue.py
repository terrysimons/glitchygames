"""The test harness empties SDL's event queue after every test (end_of_test_event_queue_problems).

SDL's queue is process-wide: an event a test posts and never takes is still queued when the
worker's next test runs. 2026-11-26: the AI console's spawn event, left by
tests/test_ai_console.py::test_a_sprite_named_like_a_path_is_saved_in_the_sprites_folder, was
merged into the next test's replay batch as the game's own post, and that test failed on an
event with no ``sprite`` (CircleCI job 6258, seed 1289560758;
bugs/2026-11-26-a-test-left-its-event-for-the-next-one.md).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pygame

from glitchygames.events.sprite_spawn import SPRITE_SPAWN_EVENT
from tests.harness import end_of_test_event_queue_problems

if TYPE_CHECKING:
    import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUBPROCESS_TIMEOUT_SECONDS = 120.0


def test_a_game_event_left_queued_is_named_and_taken():
    """The registered name and the fields say which post was never taken; nothing stays queued."""
    pygame.event.post(pygame.event.Event(SPRITE_SPAWN_EVENT, {'sprite_name': 'heart'}))

    problems = end_of_test_event_queue_problems()

    assert len(problems) == 1
    assert 'left glitchygames.sprite_spawn' in problems[0]
    assert "fields ['sprite_name']" in problems[0]
    assert pygame.event.get() == []


def test_an_unnamed_custom_event_left_queued_is_named_as_pygame_names_it():
    """A type allocated straight from pygame has no registered name: pygame's is used."""
    pygame.event.post(pygame.event.Event(pygame.USEREVENT))

    problems = end_of_test_event_queue_problems()

    assert len(problems) == 1
    assert f'left UserEvent (type {pygame.USEREVENT}, fields [])' in problems[0]


def test_a_quit_left_queued_is_reported():
    """A replay takes a queued QUIT for the window's close, and a live engine quits on it."""
    pygame.event.post(pygame.event.Event(pygame.QUIT))

    problems = end_of_test_event_queue_problems()

    assert len(problems) == 1
    assert 'left Quit' in problems[0]


def test_sdls_own_notifications_and_input_are_taken_without_a_report():
    """SDL queues window events whenever a display starts; input can come from the machine."""
    pygame.event.post(pygame.event.Event(pygame.WINDOWSHOWN))
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {'key': pygame.K_a}))

    problems = end_of_test_event_queue_problems()

    assert problems == []
    assert pygame.event.get() == []


def test_without_a_display_there_is_no_queue_to_read(mocker):
    """SDL's queue runs with the video subsystem: with it stopped, nothing is read."""
    pygame.event.post(pygame.event.Event(pygame.USEREVENT))
    mocker.patch.object(pygame.display, 'get_init', return_value=False)

    problems = end_of_test_event_queue_problems()

    assert problems == []
    # Still queued: the check did not read it. Taken here, so this test leaves nothing behind
    assert [event.type for event in pygame.event.get()] == [pygame.USEREVENT]


LEAVES_THEN_CLEAN = """
import pygame

from glitchygames.events.base import named_custom_event_type

LEFTOVER = named_custom_event_type('harness_test.leftover')


def test_a_leaves_an_event():
    pygame.event.post(pygame.event.Event(LEFTOVER, {'count': 1}))


def test_b_finds_the_queue_empty():
    assert pygame.event.get(LEFTOVER) == []
"""


def test_an_event_left_queued_fails_only_the_test_that_left_it(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The harness's teardown wiring: the leftover errors its own test; the next one is clean."""
    monkeypatch.setenv('PYTHONPATH', str(PROJECT_ROOT))
    monkeypatch.setenv('SDL_VIDEODRIVER', 'dummy')
    monkeypatch.setenv('SDL_AUDIODRIVER', 'dummy')
    tests = pytester.makepyfile(test_leaves=LEAVES_THEN_CLEAN)

    # As tests/test_harness_silences_the_mixer.py runs the harness
    result = pytester.runpytest_subprocess(
        '-c',
        str(PROJECT_ROOT / 'pyproject.toml'),
        '--rootdir',
        str(pytester.path),
        '--confcutdir',
        str(pytester.path),
        '-p',
        'tests.harness',
        '-p',
        'no:cacheprovider',
        '-p',
        'no:xdist',
        '-p',
        'no:randomly',
        '-o',
        'addopts=',
        '-rE',
        str(tests),
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )

    result.assert_outcomes(passed=2, errors=1)
    result.stdout.fnmatch_lines([
        # fnmatch reads [...] as a character class, so the fields are matched loosely
        "*Failed: left harness_test.leftover (type *, fields *'count'*) in pygame's event queue*",
        '*ERROR test_leaves.py::test_a_leaves_an_event*',
    ])
    result.stdout.no_fnmatch_line('*ERROR*test_b_finds_the_queue_empty*')


STARTS_EMPTY_FIRST_AND_AFTER_A_RESIZE = """
import pygame


def queued_event_names():
    return [pygame.event.event_name(event.type) for event in pygame.event.get()]


def test_a_first_on_its_worker_starts_with_an_empty_queue():
    assert queued_event_names() == []


def test_b_resizes_the_display():
    pygame.display.set_mode((320, 240)).fill((40, 80, 120))
    pygame.display.flip()
    # Its own window events are taken, so the end-of-test check has nothing to report
    pygame.event.get()


def test_c_after_a_resize_starts_with_an_empty_queue():
    assert queued_event_names() == []
"""


def test_every_test_starts_with_an_empty_queue(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Neither SDL's start-up notifications nor the harness's display restore reach a test.

    The first test on a worker would otherwise find SDL's start-up events (audio device added,
    window shown, focus), and a test after one that resized the display would find the window
    events the harness's restore queued after its end-of-test check (2026-11-27: on main
    7991846cc, test_without_a_display_there_is_no_queue_to_read failed when run alone).
    """
    monkeypatch.setenv('PYTHONPATH', str(PROJECT_ROOT))
    monkeypatch.setenv('SDL_VIDEODRIVER', 'dummy')
    monkeypatch.setenv('SDL_AUDIODRIVER', 'dummy')
    tests = pytester.makepyfile(test_starts_empty=STARTS_EMPTY_FIRST_AND_AFTER_A_RESIZE)

    result = pytester.runpytest_subprocess(
        '-c',
        str(PROJECT_ROOT / 'pyproject.toml'),
        '--rootdir',
        str(pytester.path),
        '--confcutdir',
        str(pytester.path),
        '-p',
        'tests.harness',
        '-p',
        'no:cacheprovider',
        '-p',
        'no:xdist',
        '-p',
        'no:randomly',
        '-o',
        'addopts=',
        '-rf',
        str(tests),
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )

    result.assert_outcomes(passed=3)
