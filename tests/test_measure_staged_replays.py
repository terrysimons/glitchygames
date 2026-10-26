"""scripts/measure_staged_replays.py: the pre-commit hook that measures what a commit holds.

Driven against a real git repository in tmp_path (real staging, real code trees); only the
replay measurement itself is replaced (``replay_metrics.run``), by one that writes the row files
a real measurement would. The pre-commit framework's own part (stashing unstaged changes, then
restoring them; a file the hook stages joining the commit) was proven in a throwaway repository
before the hook was written (plans/2026-10-25-measured-rows-in-the-repository.md).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from scripts import measure_staged_replays
from scripts.measure_staged_replays import measure_staged
from scripts.replay_metrics import metric_recordings, recording_ledger_name

from glitchygames.bundled_demos import bundled_demos
from glitchygames.code_tree import LEDGER_DIRECTORY, staged_code_tree
from glitchygames.exit_codes import ExitCode
from glitchygames.recording_metrics import read_row_files, write_row_files
from tests.test_code_tree import git, write
from tests.test_recording_metrics import ledger_row

if TYPE_CHECKING:
    from pathlib import Path

# The machine the stand-in rows were measured on (ledger_row's)
MACHINE = ledger_row().machine
# The recordings the stand-in measurement measures (the repository holds a file for each): their
# folders are installed games' console scripts, as replay_metrics.metric_recordings requires
RECORDING_NAMES = ('paddleslap', 'clockwork-keep')
# What the hook measures: those, and every installed package's bundled demo
# (glitchygames.bundled_demos finds them where the packages are installed, not in this
# stand-in repository)
MEASURED_RECORDING_COUNT = len(RECORDING_NAMES) + len(bundled_demos())
# The repository's root project: a workspace without members (metric_recordings reads it)
ROOT_PYPROJECT = '[project]\nname = "stand-in"\n'


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """Return a repository with one commit of engine code.

    Returns:
        Its directory.

    """
    git(repository=tmp_path, arguments=['init', '--quiet'])
    write(repository=tmp_path, relative_path='pyproject.toml', text=ROOT_PYPROJECT)
    write(repository=tmp_path, relative_path='src/glitchygames/game.py', text='speed = 1\n')
    for name in RECORDING_NAMES:
        write(
            repository=tmp_path,
            relative_path=f'tests/fixtures/replays/{name}/golden.jsonl.gz',
            text='recording\n',
        )
    git(repository=tmp_path, arguments=['commit', '--quiet', '-m', 'First'])
    return tmp_path


def stand_in_measurement(
    mocker,
    *,
    repository: Path,
    outcome: ExitCode = ExitCode.SUCCESS,
    history_recording: str | None = None,
    fail_after: int | None = None,
):
    """Replace the replay measurement by one writing a row for the code tree it is given.

    ``history_recording`` also writes a history row (a run the recording held, no code tree).
    The measurement skips a recording already measured for the tree, as the real one does, and
    fails (``outcome``) after writing ``fail_after`` recordings when that is given.

    Returns:
        The mock (its calls are the measurements).

    """

    def measure(*, arguments: list[str]) -> ExitCode:
        tree = arguments[arguments.index('--code-tree') + 1]
        held = {
            row.recording
            for row in read_row_files(directory=repository / LEDGER_DIRECTORY)
            if row.code_tree == tree
        }
        written = 0
        for _, path in metric_recordings(project_root=repository).replayable:
            recording = recording_ledger_name(path=path, project_root=repository)
            if recording in held:
                continue
            if fail_after is not None and written == fail_after:
                return outcome
            row = ledger_row(
                recording=recording, measured_at=f'2026-10-25T12:00:0{written}+00:00'
            ).model_copy(update={'code_tree': tree})
            write_row_files(rows=[row], directory=repository / LEDGER_DIRECTORY)
            written += 1
            if history_recording is not None and written == 1:
                history = ledger_row(
                    recording=history_recording, measured_at='2026-10-20T09:00:00+00:00'
                )
                write_row_files(rows=[history], directory=repository / LEDGER_DIRECTORY)
        return outcome

    return mocker.patch.object(measure_staged_replays.replay_metrics, 'run', side_effect=measure)


def staged_rows(*, repository: Path) -> list[str]:
    """Return the staged row files.

    Returns:
        Their paths.

    """
    staged = git(repository=repository, arguments=['diff', '--cached', '--name-only'])
    return [path for path in staged.splitlines() if path.startswith(LEDGER_DIRECTORY)]


def run_hook(*, repository: Path) -> int:
    """Run the hook's measuring step on the repository.

    Returns:
        Its exit code.

    """
    return measure_staged(
        repository=repository, rows_directory=repository / LEDGER_DIRECTORY, machine=MACHINE
    )


def test_a_code_commit_is_measured_and_its_rows_staged_with_it(mocker, repository):
    """The staged code tree is measured; its row file joins the commit."""
    measure = stand_in_measurement(mocker, repository=repository)
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 2\n')
    tree = staged_code_tree(repository=repository)

    assert run_hook(repository=repository) == ExitCode.SUCCESS

    measure.assert_called_once()
    assert len(staged_rows(repository=repository)) == MEASURED_RECORDING_COUNT
    assert {row.code_tree for row in read_row_files(directory=repository / LEDGER_DIRECTORY)} == {
        tree
    }


def test_history_rows_the_measurement_wrote_are_staged_with_the_commit(mocker, repository):
    """A run a recording held, written as a history row file, joins the commit too."""
    stand_in_measurement(mocker, repository=repository, history_recording='older/run.jsonl.gz')
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 6\n')

    assert run_hook(repository=repository) == ExitCode.SUCCESS

    names = [path.rsplit('/', maxsplit=1)[-1] for path in staged_rows(repository=repository)]
    assert len(names) == MEASURED_RECORDING_COUNT + 1
    assert sum(name.startswith('history-') for name in names) == 1


def test_an_unrelated_untracked_file_in_the_rows_directory_is_not_staged(mocker, repository):
    """Only the files the measurement wrote (and the tree's own) are staged."""
    stand_in_measurement(mocker, repository=repository)
    stray = repository / LEDGER_DIRECTORY / 'history-stray-from-another-branch.json'
    stray.parent.mkdir(parents=True, exist_ok=True)
    stray.write_text('{}\n', encoding='utf-8')
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 7\n')

    assert run_hook(repository=repository) == ExitCode.SUCCESS

    assert not any('stray' in path for path in staged_rows(repository=repository))
    assert len(staged_rows(repository=repository)) == MEASURED_RECORDING_COUNT


def test_code_that_arrived_without_the_hook_is_measured_by_the_next_commit(mocker, repository):
    """After updating a branch from main (no pre-commit stage runs), a docs commit measures.

    The staged code tree is HEAD's, but nothing measured it on this machine.
    """
    measure = stand_in_measurement(mocker, repository=repository)
    write(repository=repository, relative_path='README.md', text='# notes\n')

    assert run_hook(repository=repository) == ExitCode.SUCCESS

    measure.assert_called_once()


def test_a_measured_code_tree_is_not_measured_again(mocker, repository):
    """A docs commit after a measured one: instant."""
    measure = stand_in_measurement(mocker, repository=repository)
    run_hook(repository=repository)
    git(repository=repository, arguments=['commit', '--quiet', '-m', 'Measured'])
    write(repository=repository, relative_path='README.md', text='# notes\n')

    assert run_hook(repository=repository) == ExitCode.SUCCESS

    measure.assert_called_once()


def test_a_retry_measures_the_recordings_a_failed_attempt_left_and_stages_everything(
    mocker, repository
):
    """The first attempt writes one recording's row (and a history row) then fails.

    Those files are valid measurements: staged at once. The retry measures only the recording
    that failed, and the commit holds both rows and the history row.
    """
    stand_in_measurement(
        mocker,
        repository=repository,
        outcome=ExitCode.INTERNAL_ERROR,
        history_recording='older/run.jsonl.gz',
        fail_after=1,
    )
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 3\n')
    assert run_hook(repository=repository) == ExitCode.INTERNAL_ERROR
    assert len(staged_rows(repository=repository)) == 2

    measure = stand_in_measurement(mocker, repository=repository)
    assert run_hook(repository=repository) == ExitCode.SUCCESS

    measure.assert_called_once()
    names = [path.rsplit('/', maxsplit=1)[-1] for path in staged_rows(repository=repository)]
    assert len(names) == MEASURED_RECORDING_COUNT + 1
    assert sum(name.startswith('history-') for name in names) == 1


def test_a_retry_where_every_recording_is_measured_does_not_measure_again(mocker, repository):
    """Every recording has its row for the tree: the retry only stages them."""
    stand_in_measurement(mocker, repository=repository)
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 8\n')
    run_hook(repository=repository)
    git(repository=repository, arguments=['reset', '--quiet', '--', LEDGER_DIRECTORY])
    assert staged_rows(repository=repository) == []

    measure = stand_in_measurement(mocker, repository=repository)
    assert run_hook(repository=repository) == ExitCode.SUCCESS

    measure.assert_not_called()
    assert len(staged_rows(repository=repository)) == MEASURED_RECORDING_COUNT


def test_untracked_files_under_the_measured_paths_refuse_the_commit(mocker, repository, capsys):
    """The framework stashes only tracked changes: an untracked module would be measured."""
    measure = stand_in_measurement(mocker, repository=repository)
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 4\n')
    (repository / 'src' / 'glitchygames' / 'new_module.py').write_text('x = 1\n', encoding='utf-8')

    assert run_hook(repository=repository) == ExitCode.OPTIONS_REFUSED

    measure.assert_not_called()
    assert 'src/glitchygames/new_module.py' in capsys.readouterr().err


def test_an_untracked_member_test_does_not_refuse_the_commit(mocker, repository):
    """A member's tests are not measured, so an untracked one is not under the measured paths."""
    stand_in_measurement(mocker, repository=repository)
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 8\n')
    member_test = repository / 'src' / 'games' / 'a-game' / 'tests' / 'test_new.py'
    member_test.parent.mkdir(parents=True)
    member_test.write_text('def test_new():\n    pass\n', encoding='utf-8')

    assert run_hook(repository=repository) == ExitCode.SUCCESS


def test_an_untracked_member_recording_refuses_the_commit(mocker, repository, capsys):
    """A member's recordings are measured: an untracked one would be measured unstaged."""
    measure = stand_in_measurement(mocker, repository=repository)
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 9\n')
    recording = repository / 'src/games/a-game/tests/fixtures/replays/golden.jsonl.gz'
    recording.parent.mkdir(parents=True)
    recording.write_text('recording\n', encoding='utf-8')

    assert run_hook(repository=repository) == ExitCode.OPTIONS_REFUSED

    measure.assert_not_called()
    assert 'src/games/a-game/tests/fixtures/replays/golden.jsonl.gz' in capsys.readouterr().err


def test_a_partial_commit_that_needs_measuring_is_refused(mocker, repository, capsys):
    """Git commit <path>: rows staged into its temporary index never reach the real one."""
    measure = stand_in_measurement(mocker, repository=repository)
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 5\n')
    mocker.patch.dict(os.environ, {'GIT_INDEX_FILE': '.git/next-index-12345.lock'})

    assert run_hook(repository=repository) == ExitCode.OPTIONS_REFUSED

    measure.assert_not_called()
    assert 'git commit <path>' in capsys.readouterr().err


def test_the_hook_is_configured_to_run_before_each_commit():
    """.pre-commit-config.yaml runs it at the pre-commit stage, once per commit."""
    configuration = (measure_staged_replays.PROJECT_ROOT / '.pre-commit-config.yaml').read_text(
        encoding='utf-8'
    )

    assert 'id: replay-metrics' in configuration
    assert 'python -m scripts.measure_staged_replays' in configuration
    assert 'stages: [pre-commit]' in configuration


def test_main_measures_this_repository_on_this_machine(mocker):
    """main() runs the measuring step here, labelled with this machine."""
    core = mocker.patch.object(measure_staged_replays, 'measure_staged', return_value=0)
    mocker.patch.object(
        measure_staged_replays.replay_metrics, 'this_machine', return_value='This Machine'
    )

    assert measure_staged_replays.main() == 0

    core.assert_called_once_with(
        repository=measure_staged_replays.PROJECT_ROOT,
        rows_directory=measure_staged_replays.ROWS_DIRECTORY,
        machine='This Machine',
    )


def test_installing_the_hooks_installs_the_measuring_one_too():
    """pre-commit install sets up both stages; direnv runs it, so a fresh clone measures."""
    root = measure_staged_replays.PROJECT_ROOT
    configuration = (root / '.pre-commit-config.yaml').read_text(encoding='utf-8')
    environment = (root / '.envrc').read_text(encoding='utf-8')

    assert 'default_install_hook_types: [pre-commit, pre-push]' in configuration
    assert 'pre-commit install' in environment
