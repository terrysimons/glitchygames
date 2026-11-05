"""scripts/measure_on_raspberry_pi.py: the pre-push hook that also measures on the Raspberry Pi.

Driven against real git repositories in tmp_path (a real push, real staging, a real tar); only ssh
is replaced, by bash running the same scripts here, and the measurement, by a stand-in that stages
a row file the way ``scripts/measure_staged_replays.py`` does.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from scripts import measure_on_raspberry_pi
from scripts.measure_on_raspberry_pi import RaspberryPi

from glitchygames.exit_codes import ExitCode
from tests.test_code_tree import git, write

if TYPE_CHECKING:
    from pathlib import Path

LEDGER = 'quality/replay-ledger'
ROW = f'{LEDGER}/tree-raspberry-pi-row.json'
OTHER_ROW = f'{LEDGER}/tree-other-machine-row.json'
FAILED_MEASUREMENT_STATUS = 70
# Stages the row unless the commit holds it, as the commit hook does for an unmeasured tree
MEASURE = (
    f'mkdir -p {LEDGER} && if ! git cat-file -e HEAD:{ROW} 2>/dev/null; then '
    f"echo '{{}}' > {ROW} && git add {ROW}; fi"
)


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


@pytest.fixture
def raspberry_pi(repository: Path, tmp_path: Path) -> RaspberryPi:
    """Return a Pi whose clone is local, its origin holding main, measuring with the stand-in.

    Returns:
        The Pi.

    """
    origin = tmp_path / 'origin.git'
    clone = tmp_path / 'clone'
    git(repository=tmp_path, arguments=['clone', '--quiet', '--bare', str(repository), str(origin)])
    git(repository=tmp_path, arguments=['clone', '--quiet', str(origin), str(clone)])
    return RaspberryPi(
        script_runner=('bash', '-s'),
        clone_url=str(clone),
        clone_directory=str(clone),
        measure_command=MEASURE,
    )


def measure(*, repository: Path, raspberry_pi: RaspberryPi) -> int:
    """Run the hook on HEAD.

    Returns:
        Its exit code.

    """
    return measure_on_raspberry_pi.measure_on_raspberry_pi(
        repository=repository,
        raspberry_pi=raspberry_pi,
        ledger_directory=LEDGER,
        commit_name='HEAD',
    )


def staged(*, repository: Path) -> list[str]:
    """Return the staged files.

    Returns:
        Their paths.

    """
    return git(repository=repository, arguments=['diff', '--cached', '--name-only']).splitlines()


def test_rows_from_the_pi_land_in_the_ledger_staged_and_stop_the_push(
    repository, raspberry_pi, capsys
):
    """The row files reach this repository's ledger directory, and the push waits for a commit."""
    exit_code = measure(repository=repository, raspberry_pi=raspberry_pi)

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert (repository / ROW).is_file()
    assert staged(repository=repository) == [ROW]
    assert 'commit them and push again' in capsys.readouterr().err


def test_the_next_push_passes_once_the_rows_are_committed(repository, raspberry_pi, capsys):
    """A commit of the rows brings no new rows from the Pi, so the push goes on."""
    measure(repository=repository, raspberry_pi=raspberry_pi)
    git(repository=repository, arguments=['commit', '--quiet', '--message', 'rows'])

    exit_code = measure(repository=repository, raspberry_pi=raspberry_pi)

    assert exit_code == ExitCode.SUCCESS
    assert staged(repository=repository) == []
    assert 'needs no new rows' in capsys.readouterr().out


def test_pushing_again_without_the_commit_stops_again_with_the_rows_still_staged(
    repository, raspberry_pi
):
    """Rows nobody committed yet are not lost, and the push is stopped until they are."""
    measure(repository=repository, raspberry_pi=raspberry_pi)

    exit_code = measure(repository=repository, raspberry_pi=raspberry_pi)

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert staged(repository=repository) == [ROW]


def test_rows_left_in_the_clone_survive_the_checkout_of_another_commit(repository, raspberry_pi):
    """A later run does not delete rows staged by an earlier one: they stay, and are not lost."""
    measure(repository=repository, raspberry_pi=raspberry_pi)
    git(repository=repository, arguments=['reset', '--quiet'])
    write(repository=repository, relative_path='README', text='docs\n')
    git(repository=repository, arguments=['commit', '--quiet', '--message', 'docs'])
    keep_measured = RaspberryPi(
        script_runner=raspberry_pi.script_runner,
        clone_url=raspberry_pi.clone_url,
        clone_directory=raspberry_pi.clone_directory,
        measure_command=f'git add {ROW}',
    )

    exit_code = measure(repository=repository, raspberry_pi=keep_measured)

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert (repository / ROW).is_file()
    assert staged(repository=repository) == [ROW]


def test_a_failed_measurement_keeps_its_rows_and_fails_with_its_status(
    repository, raspberry_pi, capsys
):
    """The rows written before the failure are valid; the push stops with the failure's status."""
    failing = RaspberryPi(
        script_runner=raspberry_pi.script_runner,
        clone_url=raspberry_pi.clone_url,
        clone_directory=raspberry_pi.clone_directory,
        measure_command=f'{MEASURE}; exit {FAILED_MEASUREMENT_STATUS}',
    )

    exit_code = measure(repository=repository, raspberry_pi=failing)

    assert exit_code == FAILED_MEASUREMENT_STATUS
    assert staged(repository=repository) == [ROW]
    assert 'measuring on the Pi failed (1 rows copied' in capsys.readouterr().err


def test_a_pi_that_cannot_be_reached_stops_the_push_and_says_how_to_skip(repository, capsys):
    """Nothing is sent, and the message names the way past."""
    unreachable = RaspberryPi(
        script_runner=('false',),
        clone_url='nowhere',
        clone_directory='nowhere',
        measure_command='true',
    )

    exit_code = measure(repository=repository, raspberry_pi=unreachable)

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert 'SKIP=raspberry-pi-replay-metrics' in capsys.readouterr().err


def test_a_failed_copy_is_reported_not_taken_for_no_rows(repository, raspberry_pi, mocker):
    """The Pi failing to send the rows raises, so the push cannot go on without them."""
    real_run = measure_on_raspberry_pi._run_on_raspberry_pi

    def fail_the_archive(*, raspberry_pi, script, capture):
        if capture:
            return real_run(raspberry_pi=raspberry_pi, script='exit 3\n', capture=capture)
        return real_run(raspberry_pi=raspberry_pi, script=script, capture=capture)

    mocker.patch.object(measure_on_raspberry_pi, '_run_on_raspberry_pi', fail_the_archive)

    with pytest.raises(RuntimeError, match='status 3'):
        measure(repository=repository, raspberry_pi=raspberry_pi)


def test_an_empty_answer_from_the_pi_is_no_rows(repository, raspberry_pi, mocker):
    """Some tar writes nothing at all for no files, which is not an archive to open."""
    real_run = measure_on_raspberry_pi._run_on_raspberry_pi

    def empty_archive(*, raspberry_pi, script, capture):
        return real_run(
            raspberry_pi=raspberry_pi, script='true\n' if capture else script, capture=capture
        )

    mocker.patch.object(measure_on_raspberry_pi, '_run_on_raspberry_pi', empty_archive)

    assert measure(repository=repository, raspberry_pi=raspberry_pi) == ExitCode.SUCCESS
    assert staged(repository=repository) == []


def test_only_the_pis_rows_are_copied_not_what_is_staged_here(repository, raspberry_pi):
    """Other staged work here stays as it was, and only the Pi's rows stop the push."""
    write(repository=repository, relative_path=OTHER_ROW, text='{}\n')

    exit_code = measure(repository=repository, raspberry_pi=raspberry_pi)

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert sorted(staged(repository=repository)) == sorted([ROW, OTHER_ROW])


def test_the_pis_clone_is_the_one_ansible_makes():
    """The script's clone and host are the playbook's and the inventory's."""
    ansible = measure_on_raspberry_pi.PROJECT_ROOT / 'ansible'
    playbook = (ansible / 'raspberry_pi_runner.yml').read_text(encoding='utf-8')
    inventory = (ansible / 'inventory.yml').read_text(encoding='utf-8')
    user, host = measure_on_raspberry_pi.RASPBERRY_PI_HOST.split('@')

    assert f'/{measure_on_raspberry_pi.RASPBERRY_PI_CLONE}"\n' in playbook
    assert f'ansible_host: {host}\n' in inventory
    assert f'ansible_user: {user}\n' in inventory


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
    """The framework names the pushed commit; by hand, it is HEAD."""
    monkeypatch.delenv('PRE_COMMIT_TO_REF', raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    core = mocker.patch.object(measure_on_raspberry_pi, 'measure_on_raspberry_pi', return_value=0)

    assert measure_on_raspberry_pi.main() == 0

    assert core.call_args.kwargs['commit_name'] == expected
    assert core.call_args.kwargs['raspberry_pi'] is measure_on_raspberry_pi.THE_RASPBERRY_PI
    assert core.call_args.kwargs['ledger_directory'] == LEDGER
