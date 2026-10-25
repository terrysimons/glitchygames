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

from glitchygames.code_tree import LEDGER_DIRECTORY, staged_code_tree
from glitchygames.exit_codes import ExitCode
from glitchygames.recording_metrics import read_row_files, write_row_files
from tests.test_code_tree import git, write
from tests.test_recording_metrics import ledger_row

if TYPE_CHECKING:
    from pathlib import Path

# The machine the stand-in rows were measured on (ledger_row's)
MACHINE = ledger_row().machine


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """Return a repository with one commit of engine code.

    Returns:
        Its directory.

    """
    git(repository=tmp_path, arguments=['init', '--quiet'])
    write(repository=tmp_path, relative_path='src/glitchygames/game.py', text='speed = 1\n')
    git(repository=tmp_path, arguments=['commit', '--quiet', '-m', 'First'])
    return tmp_path


def stand_in_measurement(
    mocker,
    *,
    repository: Path,
    outcome: ExitCode = ExitCode.SUCCESS,
    history_recording: str | None = None,
):
    """Replace the replay measurement by one writing a row for the code tree it is given.

    ``history_recording`` also writes a history row (a run the recording held, no code tree).

    Returns:
        The mock (its calls are the measurements).

    """

    def measure(*, arguments: list[str]) -> ExitCode:
        tree = arguments[arguments.index('--code-tree') + 1]
        row = ledger_row(measured_at='2026-10-25T12:00:00+00:00').model_copy(
            update={'code_tree': tree}
        )
        write_row_files(rows=[row], directory=repository / LEDGER_DIRECTORY)
        if history_recording is not None:
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
    assert len(staged_rows(repository=repository)) == 1
    assert read_row_files(directory=repository / LEDGER_DIRECTORY)[0].code_tree == tree


def test_history_rows_the_measurement_wrote_are_staged_with_the_commit(mocker, repository):
    """A run a recording held, written as a history row file, joins the commit too."""
    stand_in_measurement(mocker, repository=repository, history_recording='older/run.jsonl.gz')
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 6\n')

    assert run_hook(repository=repository) == ExitCode.SUCCESS

    names = [path.rsplit('/', maxsplit=1)[-1] for path in staged_rows(repository=repository)]
    assert len(names) == 2
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
    assert len(staged_rows(repository=repository)) == 1


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


def test_rows_written_before_a_failure_are_staged_on_the_retry(mocker, repository):
    """A refused commit leaves its rows on disk; the retry stages them though nothing is new."""
    stand_in_measurement(mocker, repository=repository, outcome=ExitCode.INTERNAL_ERROR)
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 3\n')
    assert run_hook(repository=repository) == ExitCode.INTERNAL_ERROR
    assert staged_rows(repository=repository) == []

    measure = stand_in_measurement(mocker, repository=repository)
    assert run_hook(repository=repository) == ExitCode.SUCCESS

    measure.assert_not_called()
    assert len(staged_rows(repository=repository)) == 1


def test_untracked_files_under_the_measured_paths_refuse_the_commit(mocker, repository, capsys):
    """The framework stashes only tracked changes: an untracked module would be measured."""
    measure = stand_in_measurement(mocker, repository=repository)
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 4\n')
    (repository / 'src' / 'glitchygames' / 'new_module.py').write_text('x = 1\n', encoding='utf-8')

    assert run_hook(repository=repository) == ExitCode.OPTIONS_REFUSED

    measure.assert_not_called()
    assert 'src/glitchygames/new_module.py' in capsys.readouterr().err


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
