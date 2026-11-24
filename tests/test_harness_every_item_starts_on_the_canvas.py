"""The test harness starts every test item on the canvas, not only test functions.

The harness's autouse ``ensure_pygame_graceful_quit`` shows the canvas before each test, but
autouse fixtures reach only test functions: an item a collector makes (the golden replays'
``ReplayItem``, glitchygames/testing/replays.py) started on whatever the previous test left. A
golden replay draws nothing on the display, so on a shuffled Windows CI worker (#283, job 5039)
it ended on the previous test's picture, and the draws_frames check failed it as drawing
unmarked. ``pytest_runtest_setup`` in tests/harness.py shows the canvas for every other item.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUBPROCESS_TIMEOUT_SECONDS = 120.0

# A test that leaves a red picture, then an item a collector makes (as replays.py's are) that
# checks the display shows the canvas when it starts
LEAVES_A_PICTURE = """
import pygame


def test_leaves_a_red_picture():
    pygame.display.get_surface().fill((200, 0, 0))
"""
COLLECTOR_CONFTEST = """
import pygame
import pytest

from tests.display_canvas import canvas_color_at


class StartsOnTheCanvas(pytest.Item):
    def runtest(self):
        shown = pygame.display.get_surface().get_at((0, 0))
        assert shown == canvas_color_at(x=0, y=0), f'started on {shown}'


class ItemFile(pytest.File):
    def collect(self):
        yield StartsOnTheCanvas.from_parent(self, name='starts_on_the_canvas')


def pytest_collect_file(file_path, parent):
    if file_path.suffix == '.item':
        return ItemFile.from_parent(parent, path=file_path)
    return None
"""


def test_an_item_a_collector_makes_starts_on_the_canvas(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After a test that left a picture, a custom item still starts on the canvas."""
    monkeypatch.setenv('PYTHONPATH', str(PROJECT_ROOT))
    monkeypatch.setenv('SDL_VIDEODRIVER', 'dummy')
    monkeypatch.setenv('SDL_AUDIODRIVER', 'dummy')
    pytester.makeconftest(COLLECTOR_CONFTEST)
    first = pytester.makepyfile(test_a_leaves=LEAVES_A_PICTURE)
    second = pytester.path / 'b_custom.item'
    second.write_text('', encoding='utf-8')

    # As tests/world/test_mock_isolation.py runs its sequence: the project's settings without its
    # addopts, the harness as a plugin, the rootdir and confcutdir the test's own
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
        str(first),
        str(second),
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )

    result.assert_outcomes(passed=2)
