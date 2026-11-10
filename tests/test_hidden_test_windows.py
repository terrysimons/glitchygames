"""Test windows on a real video driver are hidden (tests/hidden_test_windows.py, BUGS.md #225)."""

from __future__ import annotations

import os

import pygame
import pytest

from tests.harness import TEST_WINDOWS_HIDDEN
from tests.hidden_test_windows import (
    SHOW_TEST_WINDOWS_VARIABLE,
    hidden_set_mode,
    hides_test_windows,
)


@pytest.mark.parametrize(
    ('environment', 'hidden'),
    [
        ({'SDL_VIDEODRIVER': 'cocoa'}, True),
        ({'SDL_VIDEODRIVER': 'x11'}, True),
        ({'SDL_VIDEODRIVER': 'dummy'}, False),
        ({'SDL_VIDEODRIVER': 'cocoa', SHOW_TEST_WINDOWS_VARIABLE: '1'}, False),
    ],
    ids=['cocoa', 'x11', 'dummy', 'shown-on-request'],
)
def test_a_real_drivers_windows_are_hidden_unless_asked(environment, hidden):
    """The dummy driver has no host input; a real one's windows hide unless asked to show."""
    assert hides_test_windows(environment=environment) is hidden


def test_hidden_set_mode_adds_the_hidden_flag_and_keeps_the_rest():
    """Every argument reaches pygame, with HIDDEN added to the flags it was given."""
    calls = []

    def recording_set_mode(*args, **kwargs):
        calls.append((args, kwargs))
        return pygame.Surface((1, 1))

    set_mode = hidden_set_mode(recording_set_mode)
    set_mode((320, 240), pygame.RESIZABLE, 32, vsync=0)
    set_mode((64, 48))

    assert calls == [
        (((320, 240), pygame.RESIZABLE | pygame.HIDDEN, 32), {'vsync': 0}),
        (((64, 48), pygame.HIDDEN), {}),
    ]


def test_this_run_hides_its_windows_as_its_driver_asks():
    """The harness installed the wrapper exactly when this run's environment hides windows."""
    assert TEST_WINDOWS_HIDDEN is hides_test_windows(environment=os.environ)
    assert hasattr(pygame.display.set_mode, '__wrapped__') is TEST_WINDOWS_HIDDEN
