"""scripts/measure_staged_replays.py: the pre-commit hook that measures what a commit holds.

Driven against a real git repository in tmp_path (real staging, real code trees, the engine's
real ``glitchygames unmeasured``); only the replay measurement itself is replaced
(``glitchygames measure``, through the hook's ``glitchygames``), by one that writes the row files
a real measurement would. The pre-commit framework's own part (stashing unstaged changes, then
restoring them; a file the hook stages joining the commit) was proven in a throwaway repository
before the hook was written (plans/2026-10-25-measured-rows-in-the-repository.md).
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

import pytest
from scripts import measure_staged_replays
from scripts.measure_staged_replays import measure_staged

from glitchygames.code_tree import staged_code_tree
from glitchygames.exit_codes import ExitCode
from glitchygames.recording_metrics import read_row_files, write_row_files
from glitchygames.replay.tools import command
from glitchygames.replay.tools.identity import console_script_identity
from glitchygames.replay.tools.measure import ledger_names
from glitchygames.replay.tools.registry import build_command_parser
from glitchygames.replay.tools.settings import load_project_settings
from tests.stand_in_games import write_stand_in_distribution, write_stand_in_package
from tests.test_code_tree import LEDGER_DIRECTORY, PATHS, git, write
from tests.test_recording_metrics import ledger_row

if TYPE_CHECKING:
    from pathlib import Path

# The machine the stand-in rows were measured on (ledger_row's)
MACHINE = ledger_row().machine
# The goldens the stand-in measurement measures (the repository holds a file for each): their
# folders are stand-in console scripts, installed so the engine can tell whose they are, and the
# repository's games
RECORDING_NAMES = ('stand-in-rally', 'stand-in-tower')
# The bundled demos it measures: one stand-in package's, whose entry point is stand-in-rally's
STAND_IN_DEMO_PACKAGES = ('stand_in_rally',)
STAND_IN_DEMO_NAMES = ('rally.jsonl.gz',)
# What the hook measures: those goldens and the stand-in's bundled demo, never an installed
# member's (the repository's [tool.glitchygames] games are the stand-ins alone)
MEASURED_RECORDING_COUNT = len(RECORDING_NAMES) + len(STAND_IN_DEMO_NAMES)
# The repository's root project: its games, and what a code tree holds and where the rows are
# (this repository's, as the hook reads them from the repository it is given)
ROOT_PYPROJECT = (
    '[project]\nname = "stand-in"\n\n[tool.glitchygames]\n'
    f'games = {json.dumps(list(RECORDING_NAMES))}\n'
    f'ledger-directory = {json.dumps(LEDGER_DIRECTORY)}\n'
    f'measured-paths = {json.dumps(list(PATHS.measured))}\n'
    f'unmeasured-paths = {json.dumps(list(PATHS.unmeasured))}\n'
)


@pytest.fixture
def stand_in_games(tmp_path_factory, monkeypatch, mocker) -> None:
    """Install the stand-in console scripts and demo package, on a machine labelled MACHINE.

    One stand-in distribution holds a console script per golden folder (RECORDING_NAMES); the
    stand-in package ``stand_in_rally`` bundles a demo and holds stand-in-rally's entry point.
    The demo lies outside the repository, so it is named by its install name, as a built
    install's is. The engine labels this machine as the stand-in rows do (``ledger_row``'s).
    """
    installed = tmp_path_factory.mktemp('site-packages')
    write_stand_in_distribution(
        directory=installed,
        distribution='stand-in-games',
        console_scripts={
            'stand-in-rally': 'stand_in_rally:main',
            'stand-in-tower': 'stand_in_tower:main',
        },
    )
    write_stand_in_package(
        directory=installed, package='stand_in_rally', demo_names=STAND_IN_DEMO_NAMES
    )
    monkeypatch.syspath_prepend(installed)
    mocker.patch('glitchygames.replay.tools.measure.this_machine', return_value=MACHINE)


@pytest.fixture
def repository(tmp_path: Path, stand_in_games) -> Path:
    """Return a repository with one commit of engine code, its goldens' games installed.

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
    fails (``outcome``) after writing ``fail_after`` recordings when that is given. Every other
    ``glitchygames`` subcommand (``unmeasured``) is the engine's own.

    Returns:
        A mock whose calls are the measurements.

    """
    measurements = mocker.MagicMock()

    def glitchygames(*, arguments: list[str]) -> int:
        if arguments[0] != 'measure':
            return command.main(arguments)
        measurements(arguments=arguments)
        return stand_in_measure(arguments=arguments)

    def stand_in_measure(*, arguments: list[str]) -> ExitCode:
        tree = arguments[arguments.index('--code-tree') + 1]
        held = {
            row.recording
            for row in read_row_files(directory=repository / LEDGER_DIRECTORY)
            if row.code_tree == tree
        }
        written = 0
        settings = load_project_settings(project_root=repository)
        recordings = [
            recording
            for console_script in RECORDING_NAMES
            for recording in ledger_names(
                identity=console_script_identity(console_script=console_script),
                settings=settings,
                project_root=repository,
            )
        ]
        for recording in recordings:
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

    mocker.patch.object(measure_staged_replays, 'glitchygames', side_effect=glitchygames)
    return measurements


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
    return measure_staged(repository=repository, rows_directory=repository / LEDGER_DIRECTORY)


def test_a_code_commit_is_measured_and_its_rows_staged_with_it(mocker, repository):
    """The staged code tree is measured; its row file joins the commit."""
    measure = stand_in_measurement(mocker, repository=repository)
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 2\n')
    tree = staged_code_tree(repository=repository, paths=PATHS)

    assert run_hook(repository=repository) == ExitCode.SUCCESS

    measure.assert_called_once()
    assert len(staged_rows(repository=repository)) == MEASURED_RECORDING_COUNT
    assert {row.code_tree for row in read_row_files(directory=repository / LEDGER_DIRECTORY)} == {
        tree
    }


def test_a_row_file_written_now_is_staged_once(mocker, repository):
    """A file just written is also one of the tree's row files: git add is given it once."""
    stand_in_measurement(mocker, repository=repository)
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 4\n')
    stage = mocker.spy(measure_staged_replays, '_stage')

    assert run_hook(repository=repository) == ExitCode.SUCCESS

    staged_paths = stage.call_args.kwargs['paths']
    assert len(staged_paths) == MEASURED_RECORDING_COUNT
    assert len(set(staged_paths)) == len(staged_paths)


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
    assert 'entry: uv run --locked python -m scripts.measure_staged_replays' in configuration
    assert 'stages: [pre-commit]' in configuration


def test_main_measures_this_repository_into_its_ledger_directory(mocker):
    """main() runs the measuring step here, its rows in this repository's ledger directory."""
    core = mocker.patch.object(measure_staged_replays, 'measure_staged', return_value=0)
    root = measure_staged_replays.PROJECT_ROOT

    assert measure_staged_replays.main() == 0

    core.assert_called_once_with(
        repository=root,
        rows_directory=root / load_project_settings(project_root=root).ledger_directory,
    )


def test_installing_the_hooks_installs_the_measuring_one_too():
    """pre-commit install sets up both stages; direnv runs it, so a fresh clone measures."""
    root = measure_staged_replays.PROJECT_ROOT
    configuration = (root / '.pre-commit-config.yaml').read_text(encoding='utf-8')
    environment = (root / '.envrc').read_text(encoding='utf-8')

    assert 'default_install_hook_types: [pre-commit, pre-push]' in configuration
    assert 'pre-commit install' in environment


def test_an_unmeasured_listing_that_fails_measures_so_the_failure_is_said(
    mocker, repository, capsys
):
    """``glitchygames unmeasured`` refusing (a game not installed): measuring runs, and says."""
    measure = stand_in_measurement(mocker, repository=repository)
    pyproject = repository / 'pyproject.toml'
    pyproject.write_text(
        pyproject.read_text(encoding='utf-8').replace(
            'games = [', 'games = ["glitchygames-no-such-game", '
        ),
        encoding='utf-8',
    )
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 10\n')

    assert run_hook(repository=repository) == ExitCode.SUCCESS

    measure.assert_called_once()
    assert 'glitchygames-no-such-game' in capsys.readouterr().err


def test_the_hooks_command_lines_are_the_engines_own(tmp_path):
    """The hook's two command lines, from its builders, read as meant by the real parser."""
    parser = build_command_parser()
    rows_directory = tmp_path / LEDGER_DIRECTORY
    tree = '0123456789abcdef0123456789abcdef01234567'

    listing = parser.parse_args(
        measure_staged_replays.unmeasured_arguments(
            repository=tmp_path, rows_directory=rows_directory, code_tree=tree
        )
    )
    measuring = parser.parse_args(
        measure_staged_replays.measure_arguments(
            repository=tmp_path, rows_directory=rows_directory, code_tree=tree
        )
    )

    assert (listing.tool, listing.code_tree, listing.rows_directory) == (
        'unmeasured',
        tree,
        str(rows_directory),
    )
    assert listing.project_root == tmp_path
    assert (measuring.tool, measuring.measure, measuring.code_tree) == ('measure', [], tree)
    assert measuring.allow_dirty
    assert not measuring.skip_dirty
    assert not measuring.force
    assert measuring.rows_directory == str(rows_directory)
    assert measuring.project_root == tmp_path
    assert measuring.game is None
