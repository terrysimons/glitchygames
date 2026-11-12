"""scripts/measure_on_raspberry_pi.py: the pre-push hook that also measures on the Raspberry Pis.

Driven against real git repositories in tmp_path (a real push, real staging, a real tar); only ssh
is replaced, by bash running the same scripts here, the measurement, by a stand-in that stages
a row file the way ``scripts/measure_staged_replays.py`` does (named for the checkout's code tree
and holding it), and util-linux's ``flock``, which macOS lacks, by a stand-in locking the same
inherited descriptor with the same system call. Two stand-in Pis are two clones, each staging a
row file named for itself, as each machine's rows are.

Local only (the owner, 2026-11-09): the hook runs only on the owner's machine, at ``git push``, so
its tests run there (``uv run pytest``, the push hooks' shuffled suite) and never in CI, on any
platform.
"""

from __future__ import annotations

import dataclasses
import fcntl
import io
import json
import os
import re
import shlex
import sys
import tarfile
import threading
from pathlib import Path

import pytest
import yaml
from scripts import measure_on_raspberry_pi
from scripts.measure_on_raspberry_pi import RaspberryPi

from glitchygames.code_tree import CodeTreePaths, commit_code_tree
from glitchygames.exit_codes import ExitCode
from glitchygames.replay.tools.settings import load_project_settings
from tests.test_code_tree import git, write

pytestmark = pytest.mark.skipif(
    os.environ.get('CI') == 'true',
    reason=(
        "The Raspberry Pi pre-push hook runs only on the owner's machine; "
        'its tests run there, not in CI'
    ),
)

LEDGER = 'quality/replay-ledger'
OTHER_ROW = f'{LEDGER}/tree-other-machine-row.json'
# The stand-in repositories' code tree holds src/ only
CODE_TREE_PATHS = CodeTreePaths(measured=('src',))
# The same code tree, computed by the stand-in measurement on the Pi from its checkout: a tree
# holding only src/, as git write-tree makes of an index holding only src/'s files
SHELL_CODE_TREE = 'printf \'040000 tree %s\\tsrc\\n\' "$(git rev-parse HEAD:src)" | git mktree'
# A code tree no stand-in repository has
FOREIGN_TREE = 'a' * 40
FAILED_MEASUREMENT_STATUS = 70
# How long a stand-in waits for the other Pi (or run) to reach the same point
BOTH_AT_ONCE_SECONDS = 20
# More than a pipe's buffer holds (64 KiB on macOS and Linux), so writing it to a runner that
# never reads always fails on the closed pipe
LARGER_THAN_A_PIPE_BYTES = 1024 * 1024
# How long a stand-in Pi waits for its lock (long enough for a whole stand-in run)
STAND_IN_LOCK_TIMEOUT_SECONDS = 60
# The variable naming the file the stand-in flock touches when it finds the lock taken
WAITING_MARKER_VARIABLE = 'STAND_IN_FLOCK_WAITING_MARKER'
# util-linux's flock(1), as the measuring script uses it: ``--nonblock FD`` and ``--wait
# SECONDS FD`` on a descriptor the script opened. The lock belongs to the open file, so it outlives
# this process, held until the script closes the file (when it exits), as flock(1)'s is
STAND_IN_FLOCK = """
import fcntl
import os
import pathlib
import sys
import time

if sys.argv[1] == '--nonblock':
    deadline = None
    descriptor = int(sys.argv[2])
else:
    deadline = time.monotonic() + float(sys.argv[2])
    descriptor = int(sys.argv[3])
while True:
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        if deadline is None:
            marker = os.environ.get('STAND_IN_FLOCK_WAITING_MARKER')
            if marker:
                pathlib.Path(marker).touch()
            sys.exit(1)
        if time.monotonic() >= deadline:
            sys.exit(1)
        time.sleep(0.05)
    else:
        sys.exit(0)
"""


def code_tree_of(*, repository: Path, commit: str = 'HEAD') -> str:
    """Return a stand-in repository's code tree for a commit.

    Returns:
        The tree hash.

    """
    return commit_code_tree(repository=repository, commit=commit, paths=CODE_TREE_PATHS)


def row_of(*, code_tree: str, machine: str) -> str:
    """Return the row file a stand-in measurement of a code tree on a machine stages.

    Returns:
        Its path, relative to the repository.

    """
    return f'{LEDGER}/{code_tree[:12]}-{machine}-row.json'


def measure_command(*, machine: str) -> str:
    """Return a stand-in measurement: stage the checkout's row unless the commit holds it.

    As the commit hook does for an unmeasured tree: the row is named for the code tree of what is
    checked out, and holds it.

    Returns:
        The shell command.

    """
    return (
        f'tree=$({SHELL_CODE_TREE}); row={LEDGER}/${{tree:0:12}}-{machine}-row.json; '
        f'mkdir -p {LEDGER} && if ! git cat-file -e "HEAD:$row" 2>/dev/null; then '
        'printf \'{"code_tree": "%s"}\\n\' "$tree" > "$row" && git add "$row"; fi'
    )


def stage_row_command(*, path: str, code_tree: str | None) -> str:
    """Return a command the stand-in Pi runs to stage a row file holding a code tree.

    Returns:
        The shell command.

    """
    contents = shlex.quote(json.dumps({'code_tree': code_tree}))
    return f'mkdir -p {LEDGER} && printf %s {contents} > {path} && git add {path}'


@pytest.fixture
def stand_in_bin(tmp_path: Path) -> Path:
    """Return a directory holding the stand-in flock.

    Returns:
        The directory.

    """
    directory = tmp_path / 'bin'
    directory.mkdir()
    flock = directory / 'flock'
    flock.write_text(f'#!{sys.executable} -I\n{STAND_IN_FLOCK}', encoding='utf-8')
    flock.chmod(0o755)
    return directory


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """Return this machine's repository, with a commit.

    Returns:
        Its path.

    """
    path = tmp_path / 'here'
    path.mkdir()
    git(repository=path, arguments=['init', '--quiet', '--initial-branch=main'])
    write(repository=path, relative_path='src/code.py', text='code\n')
    git(repository=path, arguments=['commit', '--quiet', '--message', 'code'])
    return path


def waiting_marker(*, tmp_path: Path, name: str) -> Path:
    """Return the file a stand-in Pi's flock touches when a run finds the lock taken.

    Returns:
        Its path.

    """
    return tmp_path / f'{name}-waiting'


def stand_in_pi(
    *, repository: Path, tmp_path: Path, stand_in_bin: Path, name: str, lock_timeout_seconds: int
) -> RaspberryPi:
    """Return a Pi whose clone is local, its origin holding main, measuring with the stand-in.

    Returns:
        The Pi.

    """
    origin = tmp_path / f'{name}-origin.git'
    clone = tmp_path / f'{name}-clone'
    git(repository=tmp_path, arguments=['clone', '--quiet', '--bare', str(repository), str(origin)])
    git(repository=tmp_path, arguments=['clone', '--quiet', str(origin), str(clone)])
    return RaspberryPi(
        name=name,
        script_runner=(
            'env',
            f'PATH={stand_in_bin}{os.pathsep}{os.environ["PATH"]}',
            f'{WAITING_MARKER_VARIABLE}={waiting_marker(tmp_path=tmp_path, name=name)}',
            'bash',
            '-s',
        ),
        clone_url=str(clone),
        clone_directory=str(clone),
        measure_command=measure_command(machine=name),
        lock_file=f'{clone}.lock',
        lock_timeout_seconds=lock_timeout_seconds,
    )


@pytest.fixture
def raspberry_pi(repository: Path, tmp_path: Path, stand_in_bin: Path) -> RaspberryPi:
    """Return one stand-in Pi.

    Returns:
        The Pi.

    """
    return stand_in_pi(
        repository=repository,
        tmp_path=tmp_path,
        stand_in_bin=stand_in_bin,
        name='raspberry-pi-4',
        lock_timeout_seconds=STAND_IN_LOCK_TIMEOUT_SECONDS,
    )


@pytest.fixture
def other_raspberry_pi(repository: Path, tmp_path: Path, stand_in_bin: Path) -> RaspberryPi:
    """Return a second stand-in Pi, staging its own row.

    Returns:
        The Pi.

    """
    return stand_in_pi(
        repository=repository,
        tmp_path=tmp_path,
        stand_in_bin=stand_in_bin,
        name='raspberry-pi-5',
        lock_timeout_seconds=STAND_IN_LOCK_TIMEOUT_SECONDS,
    )


@pytest.fixture
def row(repository: Path) -> str:
    """Return the row the first stand-in Pi stages for HEAD.

    Returns:
        Its path, relative to the repository.

    """
    return row_of(code_tree=code_tree_of(repository=repository), machine='raspberry-pi-4')


@pytest.fixture
def other_pi_row(repository: Path) -> str:
    """Return the row the second stand-in Pi stages for HEAD.

    Returns:
        Its path, relative to the repository.

    """
    return row_of(code_tree=code_tree_of(repository=repository), machine='raspberry-pi-5')


@pytest.fixture
def both_rows(row: str, other_pi_row: str) -> list[str]:
    """Return the rows both stand-in Pis stage for HEAD.

    Returns:
        Their paths, relative to the repository, sorted.

    """
    return sorted([row, other_pi_row])


def with_measurement(*, raspberry_pi: RaspberryPi, command: str) -> RaspberryPi:
    """Return the Pi measuring with another command.

    Returns:
        The Pi.

    """
    return dataclasses.replace(raspberry_pi, measure_command=command)


def unreachable_pi(*, script_runner: tuple[str, ...]) -> RaspberryPi:
    """Return a Pi that runs nothing it is given.

    Returns:
        The Pi.

    """
    return RaspberryPi(
        name='raspberry-pi-4',
        script_runner=script_runner,
        clone_url='nowhere',
        clone_directory='nowhere',
        measure_command='true',
        lock_file='nowhere.lock',
        lock_timeout_seconds=STAND_IN_LOCK_TIMEOUT_SECONDS,
    )


def measure(*, repository: Path, raspberry_pis: tuple[RaspberryPi, ...]) -> int:
    """Run the hook on HEAD.

    Returns:
        Its exit code.

    """
    return measure_on_raspberry_pi.measure_on_raspberry_pis(
        repository=repository,
        raspberry_pis=raspberry_pis,
        ledger_directory=LEDGER,
        code_tree_paths=CODE_TREE_PATHS,
        commit_name='HEAD',
    )


def staged(*, repository: Path) -> list[str]:
    """Return the staged files.

    Returns:
        Their paths, sorted.

    """
    return sorted(
        git(repository=repository, arguments=['diff', '--cached', '--name-only']).splitlines()
    )


def archive_of(files: dict[str, bytes]) -> bytes:
    """Return a tar holding files, as a Pi sends its rows.

    Returns:
        The archive.

    """
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w') as archive:
        for name, contents in files.items():
            member = tarfile.TarInfo(name=name)
            member.size = len(contents)
            archive.addfile(member, io.BytesIO(contents))
    return buffer.getvalue()


def test_rows_from_the_pi_land_in_the_ledger_staged_and_stop_the_push(
    repository, raspberry_pi, row, capsys
):
    """The row files reach this repository's ledger directory, and the push waits for a commit."""
    exit_code = measure(repository=repository, raspberry_pis=(raspberry_pi,))

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert (repository / row).is_file()
    assert staged(repository=repository) == [row]
    assert 'commit them and push again' in capsys.readouterr().err


def test_every_pis_rows_land_staged_in_one_push(
    repository, raspberry_pi, other_raspberry_pi, both_rows
):
    """Each Pi measures and its own rows come back; both are staged together."""
    exit_code = measure(repository=repository, raspberry_pis=(raspberry_pi, other_raspberry_pi))

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert staged(repository=repository) == both_rows


def test_the_pis_measure_at_the_same_time(
    repository, raspberry_pi, other_raspberry_pi, both_rows, tmp_path
):
    """Each stand-in waits for the other to start: one after the other, the first would give up.

    Each Pi has its own lock: the lock keeps pushes apart on one Pi, never the Pis apart.
    """
    started_directory = tmp_path / 'started'
    started_directory.mkdir()
    # Forward slashes and quoted: bash on Windows reads backslashes as escapes
    started = shlex.quote(started_directory.as_posix())

    def waiting_for_the_other(*, raspberry_pi: RaspberryPi, other: str) -> RaspberryPi:
        mine = f'{started}/{raspberry_pi.name}'
        theirs = f'{started}/{other}'
        return with_measurement(
            raspberry_pi=raspberry_pi,
            command=(
                f'touch {mine}; '
                f'for _ in $(seq {BOTH_AT_ONCE_SECONDS * 10}); do '
                f'[ -e {theirs} ] && break; sleep 0.1; done; '
                f'[ -e {theirs} ] || exit {FAILED_MEASUREMENT_STATUS}; '
                f'{raspberry_pi.measure_command}'
            ),
        )

    exit_code = measure(
        repository=repository,
        raspberry_pis=(
            waiting_for_the_other(raspberry_pi=raspberry_pi, other=other_raspberry_pi.name),
            waiting_for_the_other(raspberry_pi=other_raspberry_pi, other=raspberry_pi.name),
        ),
    )

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert staged(repository=repository) == both_rows


def test_the_pis_rows_are_fetched_at_the_same_time_and_staged_once(
    repository, raspberry_pi, other_raspberry_pi, both_rows, mocker
):
    """Both fetches are under way together; staging, git's index, happens once for both."""
    both_fetching = threading.Barrier(parties=2, timeout=BOTH_AT_ONCE_SECONDS)
    real_fetch = measure_on_raspberry_pi._fetch_rows

    def fetch_once_both_are_fetching(**arguments):
        both_fetching.wait()
        return real_fetch(**arguments)

    mocker.patch.object(measure_on_raspberry_pi, '_fetch_rows', fetch_once_both_are_fetching)
    stage = mocker.spy(measure_on_raspberry_pi, '_stage_rows')

    exit_code = measure(repository=repository, raspberry_pis=(raspberry_pi, other_raspberry_pi))

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert stage.call_count == 1
    assert sorted(stage.call_args.kwargs['names']) == both_rows
    assert staged(repository=repository) == both_rows


def test_each_line_a_pi_prints_names_the_pi(repository, raspberry_pi, other_raspberry_pi, capsys):
    """Two Pis printing at once stay readable: every line says which Pi it came from."""
    exit_code = measure(
        repository=repository,
        raspberry_pis=tuple(
            with_measurement(
                raspberry_pi=each, command=f'echo measuring here; {each.measure_command}'
            )
            for each in (raspberry_pi, other_raspberry_pi)
        ),
    )

    output = capsys.readouterr().out

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert 'raspberry-pi-4: measuring here\n' in output
    assert 'raspberry-pi-5: measuring here\n' in output


def test_the_next_push_passes_once_the_rows_are_committed(repository, raspberry_pi, capsys):
    """A commit of the rows brings no new rows from the Pi, so the push goes on."""
    measure(repository=repository, raspberry_pis=(raspberry_pi,))
    git(repository=repository, arguments=['commit', '--quiet', '--message', 'rows'])

    exit_code = measure(repository=repository, raspberry_pis=(raspberry_pi,))

    assert exit_code == ExitCode.SUCCESS
    assert staged(repository=repository) == []
    assert 'needs no new rows' in capsys.readouterr().out


def test_pushing_again_without_the_commit_stops_again_with_the_rows_still_staged(
    repository, raspberry_pi, row
):
    """Rows nobody committed yet are not lost, and the push is stopped until they are."""
    measure(repository=repository, raspberry_pis=(raspberry_pi,))

    exit_code = measure(repository=repository, raspberry_pis=(raspberry_pi,))

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert staged(repository=repository) == [row]


def test_rows_left_in_the_clone_survive_the_checkout_of_another_commit(
    repository, raspberry_pi, row
):
    """A later run does not delete rows staged by an earlier one: they stay, and are not lost."""
    measure(repository=repository, raspberry_pis=(raspberry_pi,))
    git(repository=repository, arguments=['reset', '--quiet'])
    write(repository=repository, relative_path='README', text='docs\n')
    git(repository=repository, arguments=['commit', '--quiet', '--message', 'docs'])
    keep_measured = with_measurement(raspberry_pi=raspberry_pi, command=f'git add {row}')

    exit_code = measure(repository=repository, raspberry_pis=(keep_measured,))

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert (repository / row).is_file()
    assert staged(repository=repository) == [row]


def test_a_failed_measurement_keeps_its_rows_and_fails_with_its_status(
    repository, raspberry_pi, row, capsys
):
    """The rows written before the failure are valid; the push stops with the failure's status."""
    failing = with_measurement(
        raspberry_pi=raspberry_pi,
        command=f'{raspberry_pi.measure_command}; exit {FAILED_MEASUREMENT_STATUS}',
    )

    exit_code = measure(repository=repository, raspberry_pis=(failing,))

    assert exit_code == FAILED_MEASUREMENT_STATUS
    assert staged(repository=repository) == [row]
    assert 'measuring on raspberry-pi-4 failed (1 rows copied' in capsys.readouterr().err


def test_one_pis_failed_measurement_keeps_the_other_pis_rows(
    repository, raspberry_pi, other_raspberry_pi, other_pi_row, capsys
):
    """The Pi that measured still brings its rows; the push stops with the failure's status."""
    failing = with_measurement(
        raspberry_pi=raspberry_pi, command=f'exit {FAILED_MEASUREMENT_STATUS}'
    )

    exit_code = measure(repository=repository, raspberry_pis=(failing, other_raspberry_pi))

    errors = capsys.readouterr().err
    assert exit_code == FAILED_MEASUREMENT_STATUS
    assert staged(repository=repository) == [other_pi_row]
    assert 'measuring on raspberry-pi-4 failed (0 rows copied' in errors
    assert 'raspberry-pi-5 failed' not in errors


def test_a_pi_that_cannot_be_reached_stops_the_push_and_says_how_to_skip(repository, capsys):
    """Nothing is sent, and the message names the way past."""
    exit_code = measure(
        repository=repository, raspberry_pis=(unreachable_pi(script_runner=('false',)),)
    )

    errors = capsys.readouterr().err
    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert 'could not reach raspberry-pi-4' in errors
    assert 'SKIP=raspberry-pi-replay-metrics' in errors


def test_one_unreachable_pi_stops_the_push_before_any_pi_measures(
    repository, other_raspberry_pi, capsys
):
    """The reachable Pi is sent nothing either, so no push is left half measured."""
    unreachable = unreachable_pi(script_runner=('false',))

    exit_code = measure(repository=repository, raspberry_pis=(unreachable, other_raspberry_pi))

    errors = capsys.readouterr().err
    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert 'could not reach raspberry-pi-4;' in errors
    assert staged(repository=repository) == []
    # Nothing was pushed to the reachable Pi's clone
    branches = git(repository=other_raspberry_pi.clone_directory, arguments=['branch', '--all'])
    assert 'to-measure' not in branches


def test_a_runner_that_exits_without_reading_the_script_reports_its_status():
    """An ssh that could not connect closes the pipe: its status says so, nothing raises.

    The script is larger than a pipe's buffer, so the write always meets the closed pipe.
    """
    exits_at_once = unreachable_pi(script_runner=('sh', '-c', f'exit {FAILED_MEASUREMENT_STATUS}'))

    completed = measure_on_raspberry_pi._run_on_raspberry_pi(
        raspberry_pi=exits_at_once, script='#' * LARGER_THAN_A_PIPE_BYTES
    )

    assert completed.returncode == FAILED_MEASUREMENT_STATUS


def test_a_failed_copy_is_reported_not_taken_for_no_rows(repository, raspberry_pi):
    """The Pi failing to send the rows raises, so the push cannot go on without them.

    The stand-in stages its row and deletes the file, so the archive's tar fails.
    """
    loses_its_row = with_measurement(
        raspberry_pi=raspberry_pi,
        command=f'{raspberry_pi.measure_command}; rm -f {LEDGER}/*-row.json',
    )

    with pytest.raises(RuntimeError, match='copying the rows from raspberry-pi-4 failed'):
        measure(repository=repository, raspberry_pis=(loses_its_row,))
    assert staged(repository=repository) == []


def test_one_pis_failed_copy_still_stages_the_other_pis_rows(
    repository, raspberry_pi, other_raspberry_pi, other_pi_row
):
    """The other Pi's rows are staged before the failure is raised, so they are not lost."""
    loses_its_row = with_measurement(
        raspberry_pi=raspberry_pi,
        command=f'{raspberry_pi.measure_command}; rm -f {LEDGER}/*-row.json',
    )

    with pytest.raises(RuntimeError, match='copying the rows from raspberry-pi-4 failed'):
        measure(repository=repository, raspberry_pis=(loses_its_row, other_raspberry_pi))
    assert staged(repository=repository) == [other_pi_row]


def test_a_measurement_that_stages_nothing_brings_no_rows(repository, raspberry_pi, capsys):
    """An archive of no files is no rows: the push goes on."""
    measures_nothing = with_measurement(raspberry_pi=raspberry_pi, command='true')

    assert measure(repository=repository, raspberry_pis=(measures_nothing,)) == ExitCode.SUCCESS
    assert staged(repository=repository) == []
    assert 'needs no new rows' in capsys.readouterr().out


def test_an_empty_answer_from_the_pi_is_no_rows(repository, raspberry_pi):
    """Some tar writes nothing at all for no files, which is not an archive to open."""
    fetched = measure_on_raspberry_pi._fetch_rows(
        repository=repository,
        raspberry_pi=raspberry_pi,
        archive=b'',
        ledger_directory=LEDGER,
        code_tree=code_tree_of(repository=repository),
    )

    assert fetched == []


def test_only_the_pis_rows_are_copied_not_what_is_staged_here(repository, raspberry_pi, row):
    """Other staged work here stays as it was, and only the Pi's rows stop the push."""
    write(repository=repository, relative_path=OTHER_ROW, text='{}\n')

    exit_code = measure(repository=repository, raspberry_pis=(raspberry_pi,))

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert staged(repository=repository) == sorted([row, OTHER_ROW])


def test_only_the_pushed_trees_rows_and_history_rows_leave_the_pi(repository, raspberry_pi, row):
    """Rows of another code tree staged in the clone stay there (BUGS.md #273).

    History rows (``history-...``, a recording's earlier runs that landed) name no code tree, and
    the measurement of this tree wrote them: they come back.
    """
    foreign_row = row_of(code_tree=FOREIGN_TREE, machine='raspberry-pi-4')
    history_row = f'{LEDGER}/history-raspberry-pi-4-row.json'
    stages_others_too = with_measurement(
        raspberry_pi=raspberry_pi,
        command=(
            f'{raspberry_pi.measure_command}; '
            f'{stage_row_command(path=foreign_row, code_tree=FOREIGN_TREE)}; '
            f'{stage_row_command(path=history_row, code_tree=None)}'
        ),
    )

    exit_code = measure(repository=repository, raspberry_pis=(stages_others_too,))

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert staged(repository=repository) == sorted([row, history_row])
    assert not (repository / foreign_row).exists()


def test_a_row_named_for_the_pushed_tree_but_measuring_another_is_refused(
    repository, raspberry_pi, row
):
    """A row whose ``code_tree`` is not the pushed tree's is never staged: the hook fails.

    As in BUGS.md #273, where a measurement of the other push's checkout carried this push's name.
    """
    mislabelled = with_measurement(
        raspberry_pi=raspberry_pi, command=stage_row_command(path=row, code_tree=FOREIGN_TREE)
    )

    with pytest.raises(RuntimeError, match=f'not of the pushed code tree.*{row}'):
        measure(repository=repository, raspberry_pis=(mislabelled,))
    assert staged(repository=repository) == []
    assert not (repository / row).exists()


@pytest.mark.parametrize(
    ('name', 'contents'),
    [
        ('{tree}-raspberry-pi-4-row.json', json.dumps({'code_tree': FOREIGN_TREE})),
        (f'{FOREIGN_TREE[:12]}-raspberry-pi-4-row.json', json.dumps({'code_tree': FOREIGN_TREE})),
        ('history-raspberry-pi-4-row.json', json.dumps({'code_tree': FOREIGN_TREE})),
        ('{tree}-raspberry-pi-4-row.json', 'not json'),
        ('{tree}-raspberry-pi-4-row.json', json.dumps(['a', 'list'])),
        ('{tree}-raspberry-pi-4-row.txt', json.dumps({'code_tree': '{full_tree}'})),
    ],
    ids=[
        'named-for-the-tree-holding-another',
        'named-for-another-tree',
        'history-holding-a-tree',
        'not-json',
        'not-a-row',
        'not-a-row-file',
    ],
)
def test_fetching_refuses_any_file_that_is_not_a_row_of_the_pushed_tree(
    repository, raspberry_pi, name, contents
):
    """A Pi sending one file that is not this push's row has none of its rows copied."""
    code_tree = code_tree_of(repository=repository)
    good_row = row_of(code_tree=code_tree, machine='raspberry-pi-4')
    bad_file = f'{LEDGER}/{name.format(tree=code_tree[:12])}'
    archive = archive_of({
        good_row: json.dumps({'code_tree': code_tree}).encode(),
        bad_file: contents.replace('{full_tree}', code_tree).encode(),
    })

    with pytest.raises(RuntimeError, match=f'raspberry-pi-4 sent rows that are not .*{bad_file}'):
        measure_on_raspberry_pi._fetch_rows(
            repository=repository,
            raspberry_pi=raspberry_pi,
            archive=archive,
            ledger_directory=LEDGER,
            code_tree=code_tree,
        )
    assert not (repository / good_row).exists()
    assert not (repository / bad_file).exists()


def test_fetching_refuses_a_file_outside_the_ledger(repository, raspberry_pi):
    """Only the ledger directory's rows: a file anywhere else is refused."""
    code_tree = code_tree_of(repository=repository)
    outside = f'src/{code_tree[:12]}-raspberry-pi-4-row.json'
    archive = archive_of({outside: json.dumps({'code_tree': code_tree}).encode()})

    with pytest.raises(RuntimeError, match=outside):
        measure_on_raspberry_pi._fetch_rows(
            repository=repository,
            raspberry_pi=raspberry_pi,
            archive=archive,
            ledger_directory=LEDGER,
            code_tree=code_tree,
        )
    assert not (repository / outside).exists()


def test_staging_refuses_a_row_of_another_tree(repository):
    """The last check before git's index: a row file named for another tree is not staged."""
    foreign_row = row_of(code_tree=FOREIGN_TREE, machine='raspberry-pi-4')
    write(repository=repository, relative_path=foreign_row, text='{}\n')
    git(repository=repository, arguments=['reset', '--quiet'])

    with pytest.raises(RuntimeError, match=f'refusing to stage .*{foreign_row}'):
        measure_on_raspberry_pi._stage_rows(
            repository=repository,
            names=[foreign_row],
            code_tree=code_tree_of(repository=repository),
        )
    assert staged(repository=repository) == []


def test_a_pi_printing_before_the_script_fails_the_hook_rather_than_passing(
    repository, raspberry_pi
):
    """A line on standard output before the script's (a ~/.bashrc's) hides the header: fail.

    The script never exits 0 without its header, so its rows could not be read; passing would
    lose them silently.
    """
    chatty = dataclasses.replace(
        raspberry_pi,
        script_runner=(
            'sh',
            '-c',
            'echo "Welcome to the Pi"; exec "$@"',
            'sh',
            *raspberry_pi.script_runner,
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="raspberry-pi-4 exited 0 without sending its rows: its output began with 'Welcome",
    ):
        measure(repository=repository, raspberry_pis=(chatty,))
    assert staged(repository=repository) == []


@pytest.mark.parametrize(
    ('output', 'expected'),
    [
        (b'measured soon\n', "raspberry-pi-4 sent a malformed header: b'measured soon'"),
        (b'measured 0\nnot a tar archive', 'raspberry-pi-4 sent rows that are not a readable'),
    ],
    ids=['malformed-header', 'unreadable-archive'],
)
def test_an_unreadable_answer_from_the_pi_is_a_copy_failure(
    repository, raspberry_pi, mocker, output, expected
):
    """What the measuring script never sends: reported as the Pi's, never a traceback.

    The Pi runs a script printing that answer in place of the measuring script.
    """
    real_run = measure_on_raspberry_pi._run_on_raspberry_pi
    prints_the_answer = f'printf %s {shlex.quote(output.decode("ascii"))}\n'

    def answer(*, raspberry_pi, script):
        if script == 'true\n':
            return real_run(raspberry_pi=raspberry_pi, script=script)
        return real_run(raspberry_pi=raspberry_pi, script=prints_the_answer)

    mocker.patch.object(measure_on_raspberry_pi, '_run_on_raspberry_pi', answer)

    with pytest.raises(RuntimeError, match=re.escape(expected)):
        measure(repository=repository, raspberry_pis=(raspberry_pi,))
    assert staged(repository=repository) == []


def test_the_measurement_holds_neither_the_rows_channel_nor_the_lock(repository, raspberry_pi, row):
    """Only the script's own shell holds descriptors 3 and 9.

    A measurement child that outlived the script would otherwise keep the hook reading the rows
    channel and keep the lock held until it ended.
    """
    checks_its_descriptors = with_measurement(
        raspberry_pi=raspberry_pi,
        command=(
            'if [ -e /dev/fd/3 ] || [ -e /dev/fd/9 ]; then '
            f'echo "a descriptor leaked"; exit {FAILED_MEASUREMENT_STATUS}; fi; '
            f'{raspberry_pi.measure_command}'
        ),
    )

    exit_code = measure(repository=repository, raspberry_pis=(checks_its_descriptors,))

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert staged(repository=repository) == [row]


def test_a_checkout_moved_during_the_measurement_sends_no_rows(repository, raspberry_pi, capsys):
    """After measuring, the clone's HEAD must still be the pushed commit, or no rows come back."""
    write(repository=repository, relative_path='src/more.py', text='more\n')
    git(repository=repository, arguments=['commit', '--quiet', '--message', 'more'])
    moves_the_checkout = with_measurement(
        raspberry_pi=raspberry_pi,
        command=f'{raspberry_pi.measure_command}; git checkout --quiet --detach HEAD~1',
    )

    exit_code = measure(repository=repository, raspberry_pis=(moves_the_checkout,))

    captured = capsys.readouterr()
    pushed = git(repository=repository, arguments=['rev-parse', 'HEAD'])
    assert exit_code == measure_on_raspberry_pi.CHECKOUT_MOVED_STATUS
    assert staged(repository=repository) == []
    assert "raspberry-pi-4: the clone's HEAD is " in captured.out
    assert f'not the pushed {pushed}' in captured.out
    assert 'the checkout on raspberry-pi-4 moved away from the pushed commit' in captured.err


def test_a_run_gives_up_on_a_lock_held_too_long_and_measures_nothing(
    repository, raspberry_pi, tmp_path, capsys
):
    """Another push holding the Pi's lock throughout fails this push, naming the lock.

    It says once that it is waiting, and never measures without the lock.
    """
    measured = tmp_path / 'measured'
    impatient = dataclasses.replace(
        raspberry_pi,
        lock_timeout_seconds=1,
        measure_command=f'touch {shlex.quote(str(measured))}; {raspberry_pi.measure_command}',
    )

    with Path(impatient.lock_file).open('a', encoding='utf-8') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        exit_code = measure(repository=repository, raspberry_pis=(impatient,))

    captured = capsys.readouterr()
    assert exit_code == measure_on_raspberry_pi.LOCK_TIMED_OUT_STATUS
    assert not measured.exists()
    assert staged(repository=repository) == []
    assert captured.out.count('raspberry-pi-4: waiting for the lock') == 1
    assert f'raspberry-pi-4: gave up waiting for the lock {impatient.lock_file}' in captured.out
    assert (
        f'another push is measuring on raspberry-pi-4: gave up waiting for its lock '
        f'{impatient.lock_file} after 1 seconds, and measured nothing'
    ) in captured.err


def test_two_pushes_at_once_take_turns_on_a_pi_and_each_gets_only_its_own_rows(
    repository, raspberry_pi, tmp_path, capsys
):
    """BUGS.md #273: a second push's run waits for the first's whole run on the same Pi.

    Two repositories (two branches) push different code trees to one stand-in Pi. The first's
    measurement goes on only once the second's run has found the lock taken (the stand-in flock
    marks it), so without the lock the first would give up waiting; each measurement checks the
    clone's HEAD is unchanged across it. Each push gets its own tree's row and nothing else.
    """
    second_repository = tmp_path / 'there'
    git(
        repository=tmp_path, arguments=['clone', '--quiet', str(repository), str(second_repository)]
    )
    write(repository=second_repository, relative_path='src/more.py', text='more\n')
    git(repository=second_repository, arguments=['commit', '--quiet', '--message', 'more'])
    log = shlex.quote(str(tmp_path / 'measurements.log'))
    marker = shlex.quote(str(waiting_marker(tmp_path=tmp_path, name=raspberry_pi.name)))
    taking_turns = with_measurement(
        raspberry_pi=raspberry_pi,
        command=(
            f'head=$(git rev-parse HEAD); echo "begin $head" >> {log}; '
            f'for _ in $(seq {BOTH_AT_ONCE_SECONDS * 10}); do '
            f'[ -e {marker} ] && break; sleep 0.1; done; '
            f'[ -e {marker} ] || exit {FAILED_MEASUREMENT_STATUS}; '
            f'[ "$(git rev-parse HEAD)" = "$head" ] || exit {FAILED_MEASUREMENT_STATUS}; '
            f'{raspberry_pi.measure_command}; echo "end $head" >> {log}'
        ),
    )
    first_exit_codes: list[int] = []
    first = threading.Thread(
        target=lambda: first_exit_codes.append(
            measure(repository=repository, raspberry_pis=(taking_turns,))
        )
    )
    first.start()
    log_path = tmp_path / 'measurements.log'
    for _ in range(BOTH_AT_ONCE_SECONDS * 10):
        if log_path.exists() and log_path.read_text(encoding='utf-8'):
            break
        threading.Event().wait(0.1)

    second_exit_code = measure(repository=second_repository, raspberry_pis=(taking_turns,))
    first.join()

    first_commit = git(repository=repository, arguments=['rev-parse', 'HEAD'])
    second_commit = git(repository=second_repository, arguments=['rev-parse', 'HEAD'])
    assert log_path.read_text(encoding='utf-8').splitlines() == [
        f'begin {first_commit}',
        f'end {first_commit}',
        f'begin {second_commit}',
        f'end {second_commit}',
    ]
    assert first_exit_codes == [ExitCode.OPTIONS_REFUSED]
    assert second_exit_code == ExitCode.OPTIONS_REFUSED
    first_tree = code_tree_of(repository=repository)
    second_tree = code_tree_of(repository=second_repository)
    assert first_tree != second_tree
    assert staged(repository=repository) == [row_of(code_tree=first_tree, machine='raspberry-pi-4')]
    assert staged(repository=second_repository) == [
        row_of(code_tree=second_tree, machine='raspberry-pi-4')
    ]
    assert capsys.readouterr().out.count('raspberry-pi-4: waiting for the lock') == 1


def raspberry_pi_hosts() -> dict[str, dict[str, str]]:
    """Return ansible/inventory.yml's Raspberry Pis, with their group's variables.

    Returns:
        Each host's variables, by host name.

    """
    inventory_path = measure_on_raspberry_pi.PROJECT_ROOT / 'ansible' / 'inventory.yml'
    group = yaml.safe_load(inventory_path.read_text(encoding='utf-8'))['all']['children'][
        'raspberry_pis'
    ]
    return {name: {**group['vars'], **host} for name, host in group['hosts'].items()}


def test_the_hook_measures_on_every_pi_in_the_inventory():
    """The hook's Pis are the inventory's raspberry_pis, by name, address and login."""
    hosts = raspberry_pi_hosts()

    assert [each.name for each in measure_on_raspberry_pi.RASPBERRY_PIS] == sorted(hosts)
    for each in measure_on_raspberry_pi.RASPBERRY_PIS:
        variables = hosts[each.name]
        login = f'{variables["ansible_user"]}@{variables["ansible_host"]}'
        assert login in each.script_runner
        assert each.clone_url == f'{login}:{measure_on_raspberry_pi.RASPBERRY_PI_CLONE}'


def test_each_pis_clone_is_the_one_ansible_makes():
    """The script's clone is the playbook's, measured with the commit hook's own session."""
    playbook_path = measure_on_raspberry_pi.PROJECT_ROOT / 'ansible' / 'raspberry_pi_runner.yml'
    playbook = playbook_path.read_text(encoding='utf-8')

    assert f'/{measure_on_raspberry_pi.RASPBERRY_PI_CLONE}"\n' in playbook
    for each in measure_on_raspberry_pi.RASPBERRY_PIS:
        assert each.clone_directory == measure_on_raspberry_pi.RASPBERRY_PI_CLONE
        assert each.measure_command == 'uv run --locked --extra dev nox -s measure-staged'
        # An unreachable Pi fails at once, never waiting at a password prompt
        assert 'BatchMode=yes' in each.script_runner
        # A Pi that drops off mid-run fails the hook rather than hanging it
        assert 'ServerAliveInterval=30' in each.script_runner
        assert 'ServerAliveCountMax=4' in each.script_runner


def test_each_pis_runs_lock_a_file_beside_its_clone_with_flock():
    """One push at a time per Pi (BUGS.md #273), with util-linux's flock, named by the playbook."""
    playbook_path = measure_on_raspberry_pi.PROJECT_ROOT / 'ansible' / 'raspberry_pi_runner.yml'
    playbook = playbook_path.read_text(encoding='utf-8')

    assert '          - util-linux\n' in playbook
    for each in measure_on_raspberry_pi.RASPBERRY_PIS:
        assert each.lock_file == f'{measure_on_raspberry_pi.RASPBERRY_PI_CLONE}.lock'
        assert each.lock_timeout_seconds == measure_on_raspberry_pi.LOCK_TIMEOUT_SECONDS


def test_the_measuring_script_locks_before_the_checkout_and_archives_under_the_lock(
    raspberry_pi,
):
    """The lock is taken before anything touches the clone, and the rows leave in the same run."""
    script = measure_on_raspberry_pi.measure_script(
        raspberry_pi=raspberry_pi,
        commit='c' * 40,
        ledger_directory=LEDGER,
        code_tree='0123456789ab' + 'd' * 28,
    )

    lock_taken = script.index('flock --nonblock 9')
    assert lock_taken < script.index(f'cd {raspberry_pi.clone_directory}')
    assert script.index(f'cd {raspberry_pi.clone_directory}') < script.index('git checkout')
    assert script.index('git checkout') < script.index('measured_head=$(git rev-parse HEAD)')
    assert script.index('measured_head=') < script.index('tar -cf -')
    # Only the pushed tree's row files and history rows are listed for the archive
    assert f"'{LEDGER}/0123456789ab-*.json' '{LEDGER}/history-*.json'" in script
    # Nothing in the script lets go of the lock before it exits: the script's shell opens it once
    # and never closes it (only the measurement's subshell goes without it)
    assert script.count('exec 9>>') == 1
    assert 'exec 9>&-' not in script
    assert 'flock --unlock' not in script
    assert 'flock -u' not in script
    assert '\n) 3>&- 9>&-\n' in script


def test_the_hook_runs_first_at_push_and_stops_the_rest():
    """The later pre-push checks do not run for a push that is about to stop for its rows."""
    configuration = (measure_on_raspberry_pi.PROJECT_ROOT / '.pre-commit-config.yaml').read_text(
        encoding='utf-8'
    )
    hook = configuration[configuration.index('- id: raspberry-pi-replay-metrics') :]
    hook = hook[: hook.index('\n\n')]

    assert configuration.index('id: raspberry-pi-replay-metrics') < configuration.index(
        'id: format'
    )
    assert 'entry: uv run --locked --extra dev nox -s measure-on-raspberry-pi\n' in hook
    assert 'stages: [pre-push]' in hook
    assert 'fail_fast: true' in hook
    assert 'always_run: true' in hook


@pytest.mark.parametrize(
    ('environment', 'expected'),
    [({'PRE_COMMIT_TO_REF': 'abc123'}, 'abc123'), ({}, 'HEAD')],
    ids=['what-the-framework-names', 'by-hand'],
)
def test_main_measures_what_is_being_pushed(mocker, monkeypatch, environment, expected):
    """The framework names the pushed commit; by hand, it is HEAD; every Pi measures it."""
    monkeypatch.delenv('PRE_COMMIT_TO_REF', raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    core = mocker.patch.object(measure_on_raspberry_pi, 'measure_on_raspberry_pis', return_value=0)

    assert measure_on_raspberry_pi.main() == 0

    settings = load_project_settings(project_root=measure_on_raspberry_pi.PROJECT_ROOT)
    assert core.call_args.kwargs['commit_name'] == expected
    assert core.call_args.kwargs['raspberry_pis'] is measure_on_raspberry_pi.RASPBERRY_PIS
    assert core.call_args.kwargs['ledger_directory'] == LEDGER
    assert core.call_args.kwargs['code_tree_paths'] == settings.code_tree_paths
