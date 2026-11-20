"""Tests for the disk_sound_cache fixture (tests/disk_sound_cache.py): it cannot be fooled.

The test harness turns the sound cache's disk layer off (GLITCHYGAMES_SOUND_CACHE_ROOT empty), so
a test of the disk layer must turn it on, and must prove it touched it: a test that asked for
the disk but ran on the memory cache would otherwise pass without testing the disk at all
(plans/2026-11-14-sound-cache-on-first-use.md, decision 7).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUBPROCESS_TIMEOUT_SECONDS = 120.0

INNER_TESTS = """
import os

from glitchygames.audio.disk_cache import SOUND_CACHE_ROOT_VARIABLE


def test_writes_a_file(disk_sound_cache):
    (disk_sound_cache / 'sounds').mkdir(parents=True)
    (disk_sound_cache / 'sounds' / 'a.wav').write_bytes(b'RIFF')


def test_touches_nothing(disk_sound_cache):
    pass


def test_the_root_is_the_fixtures_folder(disk_sound_cache):
    assert os.environ[SOUND_CACHE_ROOT_VARIABLE] == str(disk_sound_cache)
    (disk_sound_cache / 'b.wav').write_bytes(b'RIFF')
"""


def _run_inner_tests(pytester: pytest.Pytester) -> pytest.RunResult:
    """Run INNER_TESTS in a fresh interpreter with only the fixture's plugin.

    The flags are tests/world/test_mock_isolation.py's (the rootdir and confcutdir are the
    test's own directory: BUGS.md #259), with tests.disk_sound_cache in place of the harness.

    Returns:
        The inner run's result.
    """
    pytester.makepyfile(test_inner=INNER_TESTS)
    return pytester.runpytest_subprocess(
        '-c',
        str(PROJECT_ROOT / 'pyproject.toml'),
        '--rootdir',
        str(pytester.path),
        '--confcutdir',
        str(pytester.path),
        '-p',
        'tests.disk_sound_cache',
        '-p',
        'no:cacheprovider',
        '-p',
        'no:xdist',
        '-p',
        'no:randomly',
        '-o',
        'addopts=',
        str(pytester.path / 'test_inner.py'),
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )


def test_a_test_that_touched_no_cache_file_fails_and_one_that_did_passes(
    pytester: pytest.Pytester,
) -> None:
    """Two tests that wrote a file pass; the one that touched nothing errors at teardown."""
    result = _run_inner_tests(pytester)

    result.assert_outcomes(passed=3, errors=1)
    result.stdout.fnmatch_lines(['*test_touches_nothing*', '*no file was written or read*'])
