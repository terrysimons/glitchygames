"""Golden replays still match under each sound cache mode, and cache disk reads its files back.

A repository test (tests/test_suite_collection.py ``REPOSITORY_TEST_FILES``): it replays our
member's golden, found through the workspace (tests/workspace_goldens.py), headless in a child
(``replay_recording_headless``). ``--sound-cache`` is replay-local, so the recording replays under
whichever mode is given.
"""

import os
from pathlib import Path

import pytest

from glitchygames.exit_codes import ExitCode
from glitchygames.replay.tools.children import recording_console_script, replay_recording_headless
from tests.workspace_goldens import every_games_golden

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN_GAME = 'paddleslap'


def paddleslap_golden() -> Path:
    """PaddleSlap's golden replay, from the workspace.

    Returns:
        Its path.
    """
    (golden,) = [
        path
        for path in every_games_golden(project_root=PROJECT_ROOT)
        if recording_console_script(path=path) == GOLDEN_GAME
    ]
    return golden


@pytest.mark.parametrize('cache_mode', ['none', 'ram'])
def test_golden_replay_still_matches_under_each_cache_mode(cache_mode):
    """Both M1 cache modes replay the golden exactly."""
    replayed = replay_recording_headless(
        console_script=GOLDEN_GAME,
        path=paddleslap_golden(),
        game_arguments=('--sound-cache', cache_mode),
    )

    assert replayed.returncode == ExitCode.SUCCESS, replayed.stdout


def golden_of(console_script: str) -> Path:
    """A game's golden replay, from the workspace (its first, by path).

    Returns:
        Its path.
    """
    return min(
        path
        for path in every_games_golden(project_root=PROJECT_ROOT)
        if recording_console_script(path=path) == console_script
    )


# A game whose sounds come from the sound library (plans/2026-11-14-sound-migration.md)
DISK_GOLDEN_GAME = 'clockwork-keep'
DISK_GOLDEN_PACKAGE = 'clockwork_keep'
LONG_AGO = 1_000_000.0


def test_a_golden_under_cache_disk_writes_its_sounds_then_reads_them_back(disk_sound_cache):
    """Cold, the replay matches and writes its sounds; warm, it matches and reads every one back.

    Run in children, so the option and the cache root (inherited from the environment) both
    reach the replayed game. Every miss takes its sound's write lock, which leaves
    ``<key>.wav.lock`` behind (filelock keeps the file on macOS and Linux; on Windows it deletes
    it on release, so there this proof would pass vacuously). So with the cold run's lock files
    removed, no lock file afterwards means no sound missed. A hit writes nothing: every file
    keeps the time set before the warm run, and stays the same file (its inode), and none is
    added. The files are in the game's own folder (its package, clockwork_keep).
    """
    golden = golden_of(DISK_GOLDEN_GAME)
    arguments = ('--sound-cache', 'disk')
    game_folder = disk_sound_cache / DISK_GOLDEN_PACKAGE

    cold = replay_recording_headless(
        console_script=DISK_GOLDEN_GAME, path=golden, game_arguments=arguments
    )
    written = sorted(disk_sound_cache.rglob('*.wav'))
    inodes = {path: path.stat().st_ino for path in written}
    for path in written:
        os.utime(path, (LONG_AGO, LONG_AGO))
    cold_locks = sorted(disk_sound_cache.rglob('*.wav.lock'))
    for lock in cold_locks:
        lock.unlink()
    warm = replay_recording_headless(
        console_script=DISK_GOLDEN_GAME, path=golden, game_arguments=arguments
    )

    assert cold.returncode == ExitCode.SUCCESS, cold.stdout
    assert warm.returncode == ExitCode.SUCCESS, warm.stdout
    assert written
    assert all(path.is_relative_to(game_folder) for path in written)
    assert len(cold_locks) == len(written)
    assert not list(disk_sound_cache.rglob('*.wav.lock')), 'a sound missed and was compiled'
    assert sorted(disk_sound_cache.rglob('*.wav')) == written
    assert all(path.stat().st_mtime == LONG_AGO for path in written)
    assert {path: path.stat().st_ino for path in written} == inodes
