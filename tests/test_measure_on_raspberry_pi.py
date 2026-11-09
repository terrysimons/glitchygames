"""scripts/measure_on_raspberry_pi.py: the pre-push hook that also measures on the Raspberry Pis.

Driven against real git repositories in tmp_path (a real push, real staging, a real tar); only ssh
is replaced, by bash running the same scripts here, and the measurement, by a stand-in that stages
a row file the way ``scripts/measure_staged_replays.py`` does. Two stand-in Pis are two clones,
each staging a row file named for itself, as each machine's rows are.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import pytest
import yaml
from scripts import measure_on_raspberry_pi
from scripts.measure_on_raspberry_pi import RaspberryPi

from glitchygames.exit_codes import ExitCode
from tests.test_code_tree import git, write

if TYPE_CHECKING:
    from pathlib import Path

LEDGER = 'quality/replay-ledger'
ROW = f'{LEDGER}/tree-raspberry-pi-4-row.json'
OTHER_PI_ROW = f'{LEDGER}/tree-raspberry-pi-5-row.json'
OTHER_ROW = f'{LEDGER}/tree-other-machine-row.json'
FAILED_MEASUREMENT_STATUS = 70
# How long a stand-in waits for the other Pi to reach the same point, proving the two run at once
BOTH_AT_ONCE_SECONDS = 20
# More than a pipe's buffer holds (64 KiB on macOS and Linux), so writing it to a runner that
# never reads always fails on the closed pipe
LARGER_THAN_A_PIPE_BYTES = 1024 * 1024


def measure_command(*, row: str) -> str:
    """Return a stand-in measurement: stage the row unless the commit holds it.

    As the commit hook does for an unmeasured tree.

    Returns:
        The shell command.

    """
    return (
        f'mkdir -p {LEDGER} && if ! git cat-file -e HEAD:{row} 2>/dev/null; then '
        f"echo '{{}}' > {row} && git add {row}; fi"
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


def stand_in_pi(*, repository: Path, tmp_path: Path, name: str, row: str) -> RaspberryPi:
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
        script_runner=('bash', '-s'),
        clone_url=str(clone),
        clone_directory=str(clone),
        measure_command=measure_command(row=row),
    )


@pytest.fixture
def raspberry_pi(repository: Path, tmp_path: Path) -> RaspberryPi:
    """Return one stand-in Pi.

    Returns:
        The Pi.

    """
    return stand_in_pi(repository=repository, tmp_path=tmp_path, name='raspberry-pi-4', row=ROW)


@pytest.fixture
def other_raspberry_pi(repository: Path, tmp_path: Path) -> RaspberryPi:
    """Return a second stand-in Pi, staging its own row.

    Returns:
        The Pi.

    """
    return stand_in_pi(
        repository=repository, tmp_path=tmp_path, name='raspberry-pi-5', row=OTHER_PI_ROW
    )


def with_measurement(*, raspberry_pi: RaspberryPi, command: str) -> RaspberryPi:
    """Return the Pi measuring with another command.

    Returns:
        The Pi.

    """
    return RaspberryPi(
        name=raspberry_pi.name,
        script_runner=raspberry_pi.script_runner,
        clone_url=raspberry_pi.clone_url,
        clone_directory=raspberry_pi.clone_directory,
        measure_command=command,
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


def test_rows_from_the_pi_land_in_the_ledger_staged_and_stop_the_push(
    repository, raspberry_pi, capsys
):
    """The row files reach this repository's ledger directory, and the push waits for a commit."""
    exit_code = measure(repository=repository, raspberry_pis=(raspberry_pi,))

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert (repository / ROW).is_file()
    assert staged(repository=repository) == [ROW]
    assert 'commit them and push again' in capsys.readouterr().err


def test_every_pis_rows_land_staged_in_one_push(repository, raspberry_pi, other_raspberry_pi):
    """Each Pi measures and its own rows come back; both are staged together."""
    exit_code = measure(repository=repository, raspberry_pis=(raspberry_pi, other_raspberry_pi))

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert staged(repository=repository) == sorted([ROW, OTHER_PI_ROW])


def test_the_pis_measure_at_the_same_time(repository, raspberry_pi, other_raspberry_pi, tmp_path):
    """Each stand-in waits for the other to start: one after the other, the first would give up."""
    started = tmp_path / 'started'
    started.mkdir()

    def waiting_for_the_other(*, raspberry_pi: RaspberryPi, other: str) -> RaspberryPi:
        return with_measurement(
            raspberry_pi=raspberry_pi,
            command=(
                f'touch {started}/{raspberry_pi.name}; '
                f'for _ in $(seq {BOTH_AT_ONCE_SECONDS * 10}); do '
                f'[ -e {started}/{other} ] && break; sleep 0.1; done; '
                f'[ -e {started}/{other} ] || exit {FAILED_MEASUREMENT_STATUS}; '
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
    assert staged(repository=repository) == sorted([ROW, OTHER_PI_ROW])


def test_the_pis_rows_are_fetched_at_the_same_time_and_staged_once(
    repository, raspberry_pi, other_raspberry_pi, mocker
):
    """Both fetches are under way together; staging, git's index, happens once for both."""
    both_fetching = threading.Barrier(parties=2, timeout=BOTH_AT_ONCE_SECONDS)
    real_fetch = measure_on_raspberry_pi._fetch_rows

    def fetch_once_both_are_fetching(*, repository, raspberry_pi, ledger_directory):
        both_fetching.wait()
        return real_fetch(
            repository=repository, raspberry_pi=raspberry_pi, ledger_directory=ledger_directory
        )

    mocker.patch.object(measure_on_raspberry_pi, '_fetch_rows', fetch_once_both_are_fetching)
    stage = mocker.spy(measure_on_raspberry_pi, '_stage_rows')

    exit_code = measure(repository=repository, raspberry_pis=(raspberry_pi, other_raspberry_pi))

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert stage.call_count == 1
    assert sorted(stage.call_args.kwargs['names']) == sorted([ROW, OTHER_PI_ROW])
    assert staged(repository=repository) == sorted([ROW, OTHER_PI_ROW])


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
    repository, raspberry_pi
):
    """Rows nobody committed yet are not lost, and the push is stopped until they are."""
    measure(repository=repository, raspberry_pis=(raspberry_pi,))

    exit_code = measure(repository=repository, raspberry_pis=(raspberry_pi,))

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert staged(repository=repository) == [ROW]


def test_rows_left_in_the_clone_survive_the_checkout_of_another_commit(repository, raspberry_pi):
    """A later run does not delete rows staged by an earlier one: they stay, and are not lost."""
    measure(repository=repository, raspberry_pis=(raspberry_pi,))
    git(repository=repository, arguments=['reset', '--quiet'])
    write(repository=repository, relative_path='README', text='docs\n')
    git(repository=repository, arguments=['commit', '--quiet', '--message', 'docs'])
    keep_measured = with_measurement(raspberry_pi=raspberry_pi, command=f'git add {ROW}')

    exit_code = measure(repository=repository, raspberry_pis=(keep_measured,))

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert (repository / ROW).is_file()
    assert staged(repository=repository) == [ROW]


def test_a_failed_measurement_keeps_its_rows_and_fails_with_its_status(
    repository, raspberry_pi, capsys
):
    """The rows written before the failure are valid; the push stops with the failure's status."""
    failing = with_measurement(
        raspberry_pi=raspberry_pi,
        command=f'{raspberry_pi.measure_command}; exit {FAILED_MEASUREMENT_STATUS}',
    )

    exit_code = measure(repository=repository, raspberry_pis=(failing,))

    assert exit_code == FAILED_MEASUREMENT_STATUS
    assert staged(repository=repository) == [ROW]
    assert 'measuring on raspberry-pi-4 failed (1 rows copied' in capsys.readouterr().err


def test_one_pis_failed_measurement_keeps_the_other_pis_rows(
    repository, raspberry_pi, other_raspberry_pi, capsys
):
    """The Pi that measured still brings its rows; the push stops with the failure's status."""
    failing = with_measurement(
        raspberry_pi=raspberry_pi, command=f'exit {FAILED_MEASUREMENT_STATUS}'
    )

    exit_code = measure(repository=repository, raspberry_pis=(failing, other_raspberry_pi))

    errors = capsys.readouterr().err
    assert exit_code == FAILED_MEASUREMENT_STATUS
    assert staged(repository=repository) == [OTHER_PI_ROW]
    assert 'measuring on raspberry-pi-4 failed (0 rows copied' in errors
    assert 'raspberry-pi-5 failed' not in errors


def test_a_pi_that_cannot_be_reached_stops_the_push_and_says_how_to_skip(repository, capsys):
    """Nothing is sent, and the message names the way past."""
    unreachable = RaspberryPi(
        name='raspberry-pi-4',
        script_runner=('false',),
        clone_url='nowhere',
        clone_directory='nowhere',
        measure_command='true',
    )

    exit_code = measure(repository=repository, raspberry_pis=(unreachable,))

    errors = capsys.readouterr().err
    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert 'could not reach raspberry-pi-4' in errors
    assert 'SKIP=raspberry-pi-replay-metrics' in errors


def test_one_unreachable_pi_stops_the_push_before_any_pi_measures(
    repository, other_raspberry_pi, capsys
):
    """The reachable Pi is sent nothing either, so no push is left half measured."""
    unreachable = RaspberryPi(
        name='raspberry-pi-4',
        script_runner=('false',),
        clone_url='nowhere',
        clone_directory='nowhere',
        measure_command='true',
    )

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
    exits_at_once = RaspberryPi(
        name='raspberry-pi-4',
        script_runner=('sh', '-c', f'exit {FAILED_MEASUREMENT_STATUS}'),
        clone_url='nowhere',
        clone_directory='nowhere',
        measure_command='true',
    )

    completed = measure_on_raspberry_pi._run_on_raspberry_pi(
        raspberry_pi=exits_at_once, script='#' * LARGER_THAN_A_PIPE_BYTES, capture=False
    )

    assert completed.returncode == FAILED_MEASUREMENT_STATUS


def test_a_failed_copy_is_reported_not_taken_for_no_rows(repository, raspberry_pi, mocker):
    """The Pi failing to send the rows raises, so the push cannot go on without them."""
    real_run = measure_on_raspberry_pi._run_on_raspberry_pi

    def fail_the_archive(*, raspberry_pi, script, capture):
        if capture:
            return real_run(raspberry_pi=raspberry_pi, script='exit 3\n', capture=capture)
        return real_run(raspberry_pi=raspberry_pi, script=script, capture=capture)

    mocker.patch.object(measure_on_raspberry_pi, '_run_on_raspberry_pi', fail_the_archive)

    with pytest.raises(RuntimeError, match='raspberry-pi-4 failed with status 3'):
        measure(repository=repository, raspberry_pis=(raspberry_pi,))


def test_one_pis_failed_copy_still_stages_the_other_pis_rows(
    repository, raspberry_pi, other_raspberry_pi, mocker
):
    """The other Pi's rows are staged before the failure is raised, so they are not lost."""
    real_run = measure_on_raspberry_pi._run_on_raspberry_pi

    def fail_one_archive(*, raspberry_pi, script, capture):
        if capture and raspberry_pi.name == 'raspberry-pi-4':
            return real_run(raspberry_pi=raspberry_pi, script='exit 3\n', capture=capture)
        return real_run(raspberry_pi=raspberry_pi, script=script, capture=capture)

    mocker.patch.object(measure_on_raspberry_pi, '_run_on_raspberry_pi', fail_one_archive)

    with pytest.raises(RuntimeError, match='raspberry-pi-4 failed with status 3'):
        measure(repository=repository, raspberry_pis=(raspberry_pi, other_raspberry_pi))
    assert staged(repository=repository) == [OTHER_PI_ROW]


def test_an_empty_answer_from_the_pi_is_no_rows(repository, raspberry_pi, mocker):
    """Some tar writes nothing at all for no files, which is not an archive to open."""
    real_run = measure_on_raspberry_pi._run_on_raspberry_pi

    def empty_archive(*, raspberry_pi, script, capture):
        return real_run(
            raspberry_pi=raspberry_pi, script='true\n' if capture else script, capture=capture
        )

    mocker.patch.object(measure_on_raspberry_pi, '_run_on_raspberry_pi', empty_archive)

    assert measure(repository=repository, raspberry_pis=(raspberry_pi,)) == ExitCode.SUCCESS
    assert staged(repository=repository) == []


def test_only_the_pis_rows_are_copied_not_what_is_staged_here(repository, raspberry_pi):
    """Other staged work here stays as it was, and only the Pi's rows stop the push."""
    write(repository=repository, relative_path=OTHER_ROW, text='{}\n')

    exit_code = measure(repository=repository, raspberry_pis=(raspberry_pi,))

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert staged(repository=repository) == sorted([ROW, OTHER_ROW])


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

    assert core.call_args.kwargs['commit_name'] == expected
    assert core.call_args.kwargs['raspberry_pis'] is measure_on_raspberry_pi.RASPBERRY_PIS
    assert core.call_args.kwargs['ledger_directory'] == LEDGER
