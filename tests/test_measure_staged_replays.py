"""scripts/measure_staged_replays.py: the pre-commit hook that measures what a commit changes."""

from __future__ import annotations

import pytest
from scripts import measure_staged_replays
from scripts.code_tree import LEDGER_DIRECTORY
from scripts.measure_staged_replays import main, touches_replays

from glitchygames.exit_codes import ExitCode

TREE = '0123456789abcdef0123456789abcdef01234567'


@pytest.mark.parametrize(
    ('staged_paths', 'touches'),
    [
        # Code, a game, a recording or the locked dependencies: the replays may change
        (['glitchygames/engine/game_engine.py'], True),
        (['games/mr-muncher/mr_muncher/game.py'], True),
        (['demos/joystick-demo/joystick_demo/demo.py'], True),
        (['apps/bitmappy/bitmappy/editor.py'], True),
        (['tests/fixtures/replays/paddleslap/golden.jsonl.gz'], True),
        (['uv.lock'], True),
        (['pyproject.toml'], True),
        (['README.md', 'glitchygames/scenes/scene.py'], True),
        # Docs, plans, bug notes, tests and tooling only: nothing to measure
        (['README.md', 'BUGS.md', 'plans/future-features.md', 'docs/index.md'], False),
        (['tests/test_code_tree.py', 'scripts/code_tree.py'], False),
        # The hook's own rows never trigger it
        ([f'{LEDGER_DIRECTORY}/abc-machine-1-golden.json'], False),
        ([], False),
    ],
)
def test_what_can_change_the_replays(staged_paths, touches):
    """Code, games, recordings and dependencies may; docs, tests and tooling cannot."""
    assert touches_replays(staged_paths=staged_paths) is touches


def test_a_commit_that_cannot_change_the_replays_measures_nothing(mocker, capsys):
    """A docs commit is instant: no measuring."""
    mocker.patch.object(measure_staged_replays, 'staged_paths', return_value=['README.md'])
    measure = mocker.patch.object(measure_staged_replays.replay_metrics, 'run')

    assert main() == ExitCode.SUCCESS

    measure.assert_not_called()
    assert 'nothing staged can change the replays' in capsys.readouterr().out


def test_a_code_commit_is_measured_and_its_rows_staged(mocker, tmp_path):
    """The staged code tree is measured into the ledger and the new row files are staged."""
    rows_directory = tmp_path / 'replay-ledger'
    rows_directory.mkdir()
    (rows_directory / 'older.json').write_text('{}\n', encoding='utf-8')
    mocker.patch.object(measure_staged_replays, 'ROWS_DIRECTORY', rows_directory)
    mocker.patch.object(
        measure_staged_replays, 'staged_paths', return_value=['glitchygames/world.py']
    )
    mocker.patch.object(measure_staged_replays, 'staged_code_tree', return_value=TREE)
    staged: list[list[str]] = []
    mocker.patch.object(
        measure_staged_replays,
        'run_git',
        side_effect=lambda *, repository, arguments: staged.append(arguments) or '',
    )

    def measured(*, arguments):
        (rows_directory / 'new.json').write_text('{}\n', encoding='utf-8')
        return ExitCode.SUCCESS

    measure = mocker.patch.object(
        measure_staged_replays.replay_metrics, 'run', side_effect=measured
    )

    assert main() == ExitCode.SUCCESS

    (call,) = measure.call_args_list
    arguments = call.kwargs['arguments']
    assert arguments[0] == 'measure'
    assert '--allow-dirty' in arguments
    assert arguments[arguments.index('--code-tree') + 1] == TREE
    assert arguments[arguments.index('--rows-directory') + 1] == str(rows_directory)
    # Only the new row is staged, not the ones already there
    assert staged == [['add', '--', str(rows_directory / 'new.json')]]


def test_a_failed_measurement_fails_the_commit(mocker, tmp_path, capsys):
    """The commit is refused (a non-zero exit) and nothing is staged."""
    mocker.patch.object(measure_staged_replays, 'ROWS_DIRECTORY', tmp_path / 'replay-ledger')
    mocker.patch.object(
        measure_staged_replays, 'staged_paths', return_value=['glitchygames/world.py']
    )
    mocker.patch.object(measure_staged_replays, 'staged_code_tree', return_value=TREE)
    staging = mocker.patch.object(measure_staged_replays, 'run_git')
    mocker.patch.object(
        measure_staged_replays.replay_metrics, 'run', return_value=ExitCode.INTERNAL_ERROR
    )

    assert main() == ExitCode.INTERNAL_ERROR

    staging.assert_not_called()
    assert 'SKIP=replay-metrics' in capsys.readouterr().err


def test_the_hook_is_configured_to_run_before_each_commit():
    """.pre-commit-config.yaml runs it at the pre-commit stage, once per commit."""
    configuration = (measure_staged_replays.PROJECT_ROOT / '.pre-commit-config.yaml').read_text(
        encoding='utf-8'
    )

    assert 'id: replay-metrics' in configuration
    assert 'scripts/measure_staged_replays.py' in configuration
    assert 'stages: [pre-commit]' in configuration
