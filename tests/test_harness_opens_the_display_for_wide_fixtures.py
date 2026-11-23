"""The test harness starts pygame's display before a fixture wider than one test is made.

A module-, class-, package- or session-scoped fixture is set up before the function-scoped
fixtures of the first test that asks for it, so it saw whatever the worker's previous test left:
after a test that quit pygame, no display at all (tests/harness.py ``pytest_fixture_setup``;
bugs/2026-11-22-a-module-fixture-ran-before-the-test-display.md).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUBPROCESS_TIMEOUT_SECONDS = 120.0

# A test that stops pygame (as tests/test_logging.py does) or only its display, then a test whose
# wide fixture reads the display, as Zombies' module-scoped demo_plan does when it builds its
# scene
QUIT_THEN_WIDE_FIXTURE_TESTS = """
import pygame
import pytest

from tests.display_canvas import canvas_color_at


def test_a_test_that_stops_the_display():
    {stop}


@pytest.fixture(scope='{scope}')
def display_size_when_made():
    surface = pygame.display.get_surface() if pygame.get_init() else None
    assert surface is not None, 'no display when the {scope}-scoped fixture was made'
    # Drawn on, not black: only the test's own setup, not the harness's black-frame backstop,
    # can put the canvas back over it
    surface.fill((10, 200, 30))
    return surface.get_size()


def test_then_a_wide_fixture_reads_the_display(display_size_when_made):
    assert display_size_when_made == (800, 600)
    # The display opened early is still reset to the canvas every test starts on
    surface = pygame.display.get_surface()
    for x, y in ((0, 0), (400, 300), (799, 599)):
        assert surface.get_at((x, y)) == canvas_color_at(x=x, y=y), (x, y)
"""


def _run_inner_tests(*, pytester: pytest.Pytester, arguments: Sequence[str]) -> pytest.RunResult:
    """Run the inner tests in a fresh interpreter under the harness, in their written order.

    The flags are tests/world/test_mock_isolation.py's (the rootdir and confcutdir are the
    test's own directory: BUGS.md #259).

    Returns:
        The inner run's result.

    """
    return pytester.runpytest_subprocess(
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
        *arguments,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )


@pytest.mark.parametrize('stop', ['pygame.quit()', 'pygame.display.quit()'])
@pytest.mark.parametrize('scope', ['module', 'session'])
def test_a_wide_fixture_after_a_test_that_stopped_the_display_has_the_test_display(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch, scope: str, stop: str
) -> None:
    """The fixture is made after the stopping test's teardown, and finds the 800x600 display.

    Stopping pygame and stopping only its display (pygame still running) both leave no display.
    """
    monkeypatch.setenv('PYTHONPATH', str(PROJECT_ROOT))
    monkeypatch.setenv('SDL_VIDEODRIVER', 'dummy')
    monkeypatch.setenv('SDL_AUDIODRIVER', 'dummy')
    path = pytester.makepyfile(
        test_inner=QUIT_THEN_WIDE_FIXTURE_TESTS.format(scope=scope, stop=stop)
    )

    result = _run_inner_tests(pytester=pytester, arguments=[str(path)])

    result.assert_outcomes(passed=2)
