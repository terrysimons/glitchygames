"""Tests for the sound cache's inventory and clearing (audio/cache_inventory.py).

plans/2026-11-14-sound-cache-on-first-use.md, decision 8: the cache's operations are an engine
API that GG Sound Studio's panel, the commands and the tests share.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest

from glitchygames.audio import cache_inventory, engine
from glitchygames.audio.cache_inventory import clear, inventory
from glitchygames.audio.disk_cache import DiskSoundCache, sounds_directory

if TYPE_CHECKING:
    from pathlib import Path

RATE = 44100
# The render version these tests take as current, whatever the real one is, so two older ones
# exist (the real one is 1)
CURRENT = 5


@pytest.fixture(autouse=True)
def current_render_version(monkeypatch):
    """Make CURRENT the render version the inventory and a game's start take as current."""
    monkeypatch.setattr(cache_inventory, 'AUDIO_RENDER_VERSION', CURRENT)
    monkeypatch.setattr(engine, 'AUDIO_RENDER_VERSION', CURRENT)


def _write_sounds(root: Path, *, game: str, version: int, count: int, frames: int = 100) -> None:
    """Write ``count`` sounds into a game's folder for a render version, as a game would."""
    cache = DiskSoundCache(
        directory=sounds_directory(root=root, game=game, render_version=version),
        limit_bytes=64 * 1024 * 1024,
    )
    for index in range(count):
        cache.write(
            identity_key=f'{index:02x}' + 'a' * 30,
            samples_int16=np.zeros(frames, dtype=np.int16),
            peak=0.5,
            sample_rate=RATE,
        )


def test_an_empty_or_missing_root_holds_nothing(tmp_path):
    """No root, or an empty one: no folders, no bytes; the root may be given as text."""
    assert inventory(root=str(tmp_path / 'nowhere')).folders == ()
    assert inventory(root=tmp_path).total_bytes == 0


def test_every_games_folders_are_listed_with_their_sounds_and_bytes(tmp_path):
    """A folder per game and render version; sizes are the sound files' own."""
    _write_sounds(tmp_path, game='clockwork_keep', version=CURRENT, count=3)
    _write_sounds(tmp_path, game='mr_muncher', version=CURRENT, count=2, frames=1000)

    found = inventory(root=tmp_path)

    assert [(folder.game, folder.sound_count) for folder in found.folders] == [
        ('clockwork_keep', 3),
        ('mr_muncher', 2),
    ]
    sizes = {
        folder.game: sum(path.stat().st_size for path in folder.path.rglob('*.wav'))
        for folder in found.folders
    }
    assert {folder.game: folder.size_bytes for folder in found.folders} == sizes
    assert found.total_bytes == sum(sizes.values())


def test_an_older_render_version_is_stale_and_a_newer_one_is_not(tmp_path):
    """Older folders can only be an older engine's; a newer one may be another engine's."""
    for version in (CURRENT - 1, CURRENT, CURRENT + 1):
        _write_sounds(tmp_path, game='clockwork_keep', version=version, count=1)

    found = inventory(root=tmp_path)

    assert [(folder.render_version, folder.stale) for folder in found.folders] == [
        (CURRENT - 1, True),
        (CURRENT, False),
        (CURRENT + 1, False),
    ]
    assert found.stale_bytes == found.folders[0].size_bytes


def test_what_is_not_a_cache_folder_is_left_out(tmp_path):
    """Only <root>/<game>/sounds/<render version>/ counts: stray files and folders do not."""
    _write_sounds(tmp_path, game='clockwork_keep', version=CURRENT, count=1)
    (tmp_path / 'notes.txt').write_text('mine')
    (tmp_path / 'clockwork_keep' / 'sounds' / 'drafts').mkdir()
    (tmp_path / 'other' / 'things').mkdir(parents=True)

    assert [folder.game for folder in inventory(root=tmp_path).folders] == ['clockwork_keep']


def test_clearing_the_stale_versions_removes_only_older_folders_and_says_what_it_freed(tmp_path):
    """Every game's older versions go; the current and newer stay; the report adds up."""
    for version in (CURRENT - 2, CURRENT - 1, CURRENT, CURRENT + 1):
        _write_sounds(tmp_path, game='clockwork_keep', version=version, count=2)
    _write_sounds(tmp_path, game='mr_muncher', version=CURRENT - 1, count=1)
    stale_bytes = inventory(root=tmp_path).stale_bytes

    cleared = clear(root=tmp_path, stale_only=True)

    assert (cleared.removed_sounds, cleared.freed_bytes) == (5, stale_bytes)
    remaining = [
        (folder.game, folder.render_version) for folder in inventory(root=tmp_path).folders
    ]
    assert remaining == [('clockwork_keep', CURRENT), ('clockwork_keep', CURRENT + 1)]


def test_clearing_one_game_leaves_the_others(tmp_path):
    """One game's folder goes, all its versions; the other games' stay."""
    _write_sounds(tmp_path, game='clockwork_keep', version=CURRENT, count=2)
    _write_sounds(tmp_path, game='mr_muncher', version=CURRENT, count=1)

    cleared = clear(root=tmp_path, game='clockwork_keep')

    assert cleared.removed_sounds == 2
    assert [folder.game for folder in inventory(root=tmp_path).folders] == ['mr_muncher']
    assert not (tmp_path / 'clockwork_keep').exists()


def test_clearing_everything_leaves_the_root_and_nothing_of_the_cache(tmp_path):
    """The root may be a folder of the player's: only cache folders go, never stray files."""
    _write_sounds(tmp_path, game='clockwork_keep', version=CURRENT, count=2)
    _write_sounds(tmp_path, game='mr_muncher', version=CURRENT - 1, count=1)
    (tmp_path / 'notes.txt').write_text('mine')

    cleared = clear(root=tmp_path)

    assert cleared.removed_sounds == 3
    assert inventory(root=tmp_path).folders == ()
    assert (tmp_path / 'notes.txt').read_text() == 'mine'


def test_clearing_a_missing_root_removes_nothing(tmp_path):
    """Nothing there, nothing removed, no error."""
    assert clear(root=tmp_path / 'nowhere').removed_sounds == 0


def test_a_games_start_removes_its_older_render_versions(tmp_path, monkeypatch):
    """Pruning looks only at the current version's folder; a start sweeps the older ones."""
    from glitchygames.audio.disk_cache import SOUND_CACHE_ROOT_VARIABLE
    from glitchygames.audio.engine import AudioEngine
    from glitchygames.audio.library import CacheMode
    from glitchygames.audio.voices import ChannelPartition

    monkeypatch.setenv(SOUND_CACHE_ROOT_VARIABLE, str(tmp_path))
    for version in (CURRENT - 1, CURRENT, CURRENT + 1):
        _write_sounds(tmp_path, game='clockwork_keep', version=version, count=1)
    _write_sounds(tmp_path, game='mr_muncher', version=CURRENT - 1, count=1)

    AudioEngine(
        partition=ChannelPartition(live=(), library=(), legacy_count=0),
        cache=CacheMode.DISK,
        game_name='clockwork_keep',
    )

    left = [(folder.game, folder.render_version) for folder in inventory(root=tmp_path).folders]
    assert left == [
        ('clockwork_keep', CURRENT),
        ('clockwork_keep', CURRENT + 1),
        ('mr_muncher', CURRENT - 1),  # another game's: its own start sweeps it
    ]
