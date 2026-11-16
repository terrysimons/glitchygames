"""The ``disk_sound_cache`` fixture: turn the sound cache's disk layer on, and prove it was used.

The test harness sets ``GLITCHYGAMES_SOUND_CACHE_ROOT`` empty (tests/harness.py), so cache
``disk`` runs as ``ram`` and no test writes to a user's cache folder. A test of the disk layer
asks for this fixture instead: it points the root at a fresh folder of the test's own (child
processes, such as golden replays, inherit it) and fails the test at teardown when no file was
written or read there. The folder starts empty, so a read needs a write in the same test first:
"no file in the folder" is exactly "the disk layer was never used". A test that ran on the memory
cache by mistake fails instead of passing without testing the disk
(plans/2026-11-14-sound-cache-on-first-use.md, decision 7; checked by
tests/test_disk_sound_cache_fixture.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from glitchygames.audio.disk_cache import SOUND_CACHE_ROOT_VARIABLE

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture
def disk_sound_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point the sound cache's root at a fresh folder; fail the test if nothing used it.

    Yields:
        The cache root (sounds go under ``<root>/<game>/sounds/<render_version>/``).
    """
    root = tmp_path / 'sound-cache'
    root.mkdir()
    monkeypatch.setenv(SOUND_CACHE_ROOT_VARIABLE, str(root))
    yield root
    if not any(path.is_file() for path in root.rglob('*')):
        pytest.fail(
            f'disk_sound_cache: no file was written or read under {root}: the test asked for '
            'the disk layer but never used it (did cache disk run as ram?)'
        )
