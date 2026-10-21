"""Pygame mocking must never outlive the test that applied it.

A test that runs under ``mock_pygame_patches`` and then a test that needs real pygame objects
must work in either order on the same worker. These checks run the sequence in a fresh
interpreter, because the leaks they guard against depend on what the process has already
done: pygame imports ``sndarray`` lazily, on first attribute access, and that import binds
whatever ``pygame.mixer`` is at that moment; ``GameEngine.initialize_icon`` writes a class
attribute that outlives the engine.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SUBPROCESS_TIMEOUT_SECONDS = 120

# Runs in file order: the mocked test first, then the tests that need real pygame objects
MOCKED_THEN_REAL_TESTS = '''\
from pathlib import Path

import numpy as np
import pygame

from glitchygames.audio.synth import to_sound
from glitchygames.engine import GameEngine


def test_first_runs_under_the_pygame_mocks(mock_pygame_patches, mocker):
    """Touch pygame's lazily imported modules and set the engine icon while mocked."""
    assert pygame.sndarray.make_sound is not None
    assert pygame.surfarray.pixels3d is not None
    mocker.patch('pygame.image.load', return_value=mocker.Mock())
    GameEngine.initialize_icon(icon=Path('icon.png'))


def test_then_to_sound_makes_a_real_sound():
    """sndarray must have bound the real pygame.mixer, not the mock."""
    sound = to_sound(np.zeros(64), volume=0.5)
    assert isinstance(sound, pygame.mixer.Sound)


def test_then_the_engine_icon_is_a_real_surface():
    """The icon the mocked test set must not outlive it."""
    assert isinstance(GameEngine.icon, pygame.Surface)
'''


def test_a_mocked_test_does_not_leak_into_a_later_real_test(pytester, monkeypatch):
    """Real pygame objects come back after a test that ran under the pygame mocks."""
    pytester.makepyfile(test_mocked_then_real=MOCKED_THEN_REAL_TESTS)
    monkeypatch.setenv('PYTHONPATH', str(PROJECT_ROOT))
    monkeypatch.setenv('SDL_VIDEODRIVER', 'dummy')
    monkeypatch.setenv('SDL_AUDIODRIVER', 'dummy')

    # A fresh interpreter, so nothing earlier on this worker has already loaded the lazy modules.
    # The project's pytest settings apply (warnings are errors) without its addopts (xdist,
    # coverage, junit); the project conftest is loaded as a plugin so its fixtures and resets apply
    result = pytester.runpytest_subprocess(
        '-c',
        str(PROJECT_ROOT / 'pyproject.toml'),
        '-p',
        'tests.conftest',
        '-p',
        'no:cacheprovider',
        '-p',
        'no:xdist',
        '-o',
        'addopts=',
        str(pytester.path / 'test_mocked_then_real.py'),
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )

    result.assert_outcomes(passed=3)
