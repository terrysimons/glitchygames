"""Golden replays still match under each sound cache mode, and cache disk reads its files back.

A repository test (tests/test_suite_collection.py ``REPOSITORY_TEST_FILES``): it replays our
member's golden, found through the workspace (tests/workspace_goldens.py), headless in a child
(``replay_recording_headless``). ``--sound-cache`` is replay-local, so the recording replays under
whichever mode is given.
"""

import os
from pathlib import Path

import pytest
from filelock import FileLock

from glitchygames.audio.disk_cache import SOUND_CACHE_ROOT_VARIABLE
from glitchygames.exit_codes import ExitCode
from glitchygames.replay.tools.children import recording_console_script, replay_recording_headless
from tests.workspace_goldens import every_games_golden, every_golden_and_bundled_demo

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


LONG_AGO = 1_000_000.0
RECORDINGS = every_golden_and_bundled_demo(project_root=PROJECT_ROOT)
# Where each recording's replay keeps its compiled sounds under cache disk: its game's folder
# (the game scene's package: Brave Adventurer's two games keep one each), or None when it caches
# none (PaddleSlap's sounds are recorded files, never cached; the others play no library sound).
# Written out by hand, so a recording that stops writing, or starts, fails (migration step 8)
SOUND_FOLDERS = {
    ('brave-adventurer', 'golden-classic.jsonl.gz'): 'brave_adventurer',
    ('brave-adventurer', 'golden-papyrus.jsonl.gz'): 'brave_adventurer_papyrus',
    ('brave-adventurer', 'classic.jsonl.gz'): 'brave_adventurer',
    ('brave-adventurer', 'papyrus.jsonl.gz'): 'brave_adventurer_papyrus',
    ('clockwork-keep', 'golden.jsonl.gz'): 'clockwork_keep',
    ('clockwork-keep', 'climb.jsonl.gz'): 'clockwork_keep',
    ('mr-muncher', 'golden.jsonl.gz'): 'mr_muncher',
    ('mr-muncher', 'chase.jsonl.gz'): 'mr_muncher',
    ('drawing-fire', 'golden.jsonl.gz'): None,
    ('drawing-fire', 'battle.jsonl.gz'): None,
    ('paddleslap', 'golden.jsonl.gz'): None,
    ('paddleslap', 'rally.jsonl.gz'): None,
    ('bitmappy', 'drawing.jsonl.gz'): None,
    ('dt-demo', 'timing.jsonl.gz'): None,
    ('joystick-demo', 'pad.jsonl.gz'): None,
    ('text-input-demo', 'typing.jsonl.gz'): None,
    ('zombies-aint-my-neighbors', 'golden.jsonl.gz'): 'zombies_aint_my_neighbors',
    ('zombies-aint-my-neighbors', 'golden-neighborhood.jsonl.gz'): 'zombies_aint_my_neighbors',
}


def lock_files_outlive_their_lock(folder: Path) -> bool:
    """Whether a released ``filelock`` lock leaves its file behind here.

    It does on macOS and Linux; on Windows ``filelock`` deletes the file on release (CircleCI's
    Windows job, PR #213). Asked of the library itself, never inferred from the platform's
    name, so a release that changes it is noticed.

    Returns:
        True when the lock file remains after release.
    """
    probe = folder / 'probe.lock'
    lock = FileLock(probe)
    lock.acquire()
    lock.release()
    return probe.exists()


def test_every_golden_and_bundled_demo_has_its_sound_folder_written_down():
    """A new recording must say where its sounds go (or that it caches none)."""
    assert {(console_script, path.name) for console_script, path in RECORDINGS} == set(
        SOUND_FOLDERS
    )


@pytest.mark.parametrize(
    ('console_script', 'recording'),
    RECORDINGS,
    ids=[f'{console_script}-{path.name}' for console_script, path in RECORDINGS],
)
def test_every_recording_writes_its_sounds_cold_and_reads_every_one_back_warm(
    console_script, recording, request, tmp_path, monkeypatch
):
    """The disk proof (migration step 8): cold writes, warm reads, nothing compiled twice.

    Run in children, so the option and the cache root (inherited from the environment) both
    reach the replayed game. A miss on the warm run compiles and writes its sound again, which
    replaces the file (a new inode) and gives it a new time; a hit writes nothing. So every file
    keeping the time set before the warm run and its inode, and none added, means every sound
    was read back and none compiled again, on every platform. Where lock files outlive their
    lock (``lock_files_outlive_their_lock``: macOS and Linux, not Windows), a second witness:
    every miss takes its sound's write lock, which leaves ``<key>.wav.lock`` behind, so with the
    cold run's removed, none afterwards means no sound missed (and a miss that could not write,
    its lock held elsewhere, is caught too). Both runs match the recording, frame for frame,
    with equal digests. A recording that caches nothing writes nothing, and still matches.
    """
    folder = SOUND_FOLDERS[console_script, recording.name]
    locks_witness = lock_files_outlive_their_lock(tmp_path)
    if folder is None:
        root = tmp_path / 'sound-cache'
        root.mkdir()
        monkeypatch.setenv(SOUND_CACHE_ROOT_VARIABLE, str(root))
    else:
        # The fixture fails the test if the replay never used the disk layer
        root = request.getfixturevalue('disk_sound_cache')
    digests = {run: tmp_path / f'{run}.digest' for run in ('cold', 'warm')}

    def replay(run):
        arguments = ('--sound-cache', 'disk', '--replay-digest', str(digests[run]))
        return replay_recording_headless(
            console_script=console_script, path=recording, game_arguments=arguments
        )

    cold = replay('cold')
    written = sorted(root.rglob('*.wav'))
    inodes = {path: path.stat().st_ino for path in written}
    for path in written:
        os.utime(path, (LONG_AGO, LONG_AGO))
    cold_locks = sorted(root.rglob('*.wav.lock'))
    for lock in cold_locks:
        lock.unlink()
    warm = replay('warm')

    assert cold.returncode == ExitCode.SUCCESS, cold.stdout
    assert warm.returncode == ExitCode.SUCCESS, warm.stdout
    assert digests['cold'].read_bytes()
    assert digests['warm'].read_bytes() == digests['cold'].read_bytes()
    if folder is None:
        assert not list(root.rglob('*')), 'a recording that caches nothing wrote something'
        return
    assert written
    assert all(path.is_relative_to(root / folder) for path in written)
    if locks_witness:
        assert len(cold_locks) == len(written)
        assert not list(root.rglob('*.wav.lock')), 'a sound missed and was compiled'
    assert sorted(root.rglob('*.wav')) == written
    assert all(path.stat().st_mtime == LONG_AGO for path in written)
    assert {path: path.stat().st_ino for path in written} == inodes
