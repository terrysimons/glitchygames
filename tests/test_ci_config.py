"""CircleCI's pinned tool versions match the ones uv.lock pins, so CI runs what a local run does."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
from scripts.workspace_packages import workspace_members

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CIRCLECI_CONFIG_PATH = PROJECT_ROOT / '.circleci' / 'config.yml'
LOCK_PATH = PROJECT_ROOT / 'uv.lock'


def pipeline_parameter_default(*, name: str) -> str:
    """Return a CircleCI pipeline parameter's default.

    Args:
        name: The parameter, e.g. ``NOX_VERSION``.

    Returns:
        Its ``default``, without quotes.

    """
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    match = re.search(
        rf'^  {name}:\n    type: string\n    default: "(?P<default>[^"]+)"$',
        configuration,
        flags=re.MULTILINE,
    )
    assert match is not None, f'{CIRCLECI_CONFIG_PATH} has no string parameter {name}'
    return match['default']


def locked_version(*, package: str) -> str:
    """Return the version uv.lock pins for a package.

    Args:
        package: The package's name.

    Returns:
        The locked version.

    """
    with LOCK_PATH.open('rb') as lock_file:
        lock = tomllib.load(lock_file)
    versions = [entry['version'] for entry in lock['package'] if entry['name'] == package]
    assert len(versions) == 1, f'uv.lock pins {package} {len(versions)} times: {versions}'
    return versions[0]


@pytest.mark.parametrize(
    ('parameter', 'package'),
    [
        # CI runs nox through uvx, outside the project's environment
        ('NOX_VERSION', 'nox'),
        # CI installs uv itself before anything reads uv.lock (GHSA-hq85-5cpj-mr62: < 0.13.4)
        ('UV_VERSION', 'uv'),
    ],
)
def test_circleci_pins_the_locked_version(parameter, package):
    """Each tool CI installs itself is the version uv.lock pins."""
    assert pipeline_parameter_default(name=parameter) == locked_version(package=package)


def test_circleci_installs_uv_at_its_pinned_version():
    """Every uv installer CI runs is the one for UV_VERSION, never the newest release."""
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    installer_urls = re.findall(r'https://astral\.sh/uv/[^\n|]*?install\.(?:sh|ps1)', configuration)

    assert installer_urls, 'CircleCI installs uv with no astral.sh installer'
    assert set(installer_urls) == {
        'https://astral.sh/uv/<< pipeline.parameters.UV_VERSION >>/install.sh',
        'https://astral.sh/uv/<< pipeline.parameters.UV_VERSION >>/install.ps1',
    }


class RecordingSession:
    """Stands in for a nox session: records every command, runs nothing."""

    def __init__(self, *, posargs: list[str]) -> None:
        """Start with the session's arguments and no commands."""
        self.posargs = posargs
        self.commands: list[tuple[str, ...]] = []
        # Each command's environment overrides (``env=``), by command
        self.environments: dict[tuple[str, ...], object] = {}
        self.virtualenv = type('Virtualenv', (), {'location': '.nox/docs-deploy'})()

    def run(self, *command: str, **options: object) -> None:
        """Record a command the session runs, and its environment overrides."""
        self.commands.append(command)
        self.environments[command] = options.get('env')

    def run_install(self, *command: str, **options: object) -> None:
        """Record an install command the session runs, and its environment overrides."""
        self.commands.append(command)
        self.environments[command] = options.get('env')


# How the measurement sessions run the engine's ``glitchygames`` command: in the project's
# environment, every member installed editable (noxfile._glitchygames)
GLITCHYGAMES_IN_THE_PROJECT = ('uv', 'run', '--frozen', '--all-packages', 'glitchygames')


def docs_deploy_commands(*, posargs: list[str]) -> list[tuple[str, ...]]:
    """Return the commands ``nox -s docs-deploy`` runs with these arguments.

    Returns:
        The commands, in order.

    """
    import noxfile

    session = RecordingSession(posargs=posargs)
    noxfile.docs_deploy(session)
    return session.commands


def test_docs_deploy_measures_the_replays_by_default():
    """A deploy from a person's machine measures this commit's replays first, then clears.

    Both through the engine's command: ``glitchygames measure --skip-dirty`` before the build,
    ``glitchygames clear-published`` after the push.
    """
    commands = docs_deploy_commands(posargs=[])

    measuring = commands.index((*GLITCHYGAMES_IN_THE_PROJECT, 'measure', '--skip-dirty'))
    deploying = commands.index(('mkdocs', 'gh-deploy', '--strict'))
    clearing = commands.index((*GLITCHYGAMES_IN_THE_PROJECT, 'clear-published'))
    assert measuring < deploying < clearing


def test_replay_metrics_runs_on_the_editable_install_of_every_package():
    """Bundled demos are found where installed: editable, so in the repository, by its paths."""
    import noxfile

    session = RecordingSession(posargs=['--only', 'rally'])
    noxfile.replay_metrics(session)

    (command,) = session.commands
    # The engine's command (glitchygames/replay/tools/measure.py), not the deleted script
    assert command == (*GLITCHYGAMES_IN_THE_PROJECT, 'measure', '--only', 'rally')
    assert '--no-editable' not in command
    assert session.environments[command] == {'VIRTUAL_ENV': None, 'UV_NO_EDITABLE': None}


def test_the_test_sessions_install_stays_built():
    """The test sessions install the built packages on purpose (what a user installs)."""
    import noxfile

    session = RecordingSession(posargs=[])
    noxfile._install_from_lockfile(session)

    (command,) = session.commands
    assert '--no-editable' in command
    assert '--all-packages' in command


def test_docs_deploy_with_no_measure_measures_nothing():
    """CI deploys with --no-measure: its machines vary, so their timings would be noise."""
    commands = docs_deploy_commands(posargs=['--no-measure'])

    assert not any('measure' in command for command in commands)
    assert ('python', '-m', 'scripts.build_browser_bundle', 'all') in commands
    assert ('mkdocs', 'gh-deploy', '--strict') in commands


def circleci_workflow_job(*, name: str) -> str:
    """Return a job's entry in the build-and-test workflow (its lines, as text).

    Returns:
        The entry, from its ``- name:`` line to the next job's.

    """
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    workflow = configuration[configuration.index('\nworkflows:') :]
    match = re.search(
        rf'^      - {name}:\n(?P<body>(?:        .*\n)+)', workflow, flags=re.MULTILINE
    )
    assert match is not None, f'the workflow has no job {name}'
    return match['body']


def test_the_docs_deploy_after_main_passes_on_macos():
    """Docs deploy from main only, as soon as the macOS job passes, one deploy at a time.

    macOS is the fastest job, so the deploy overlaps the Linux and Windows jobs instead of
    adding its time after them; the same tree passed all three in its pull request.
    """
    entry = circleci_workflow_job(name='deploy-docs')

    assert 'requires:\n            - build-and-test-macos\n' in entry
    assert 'branches:\n              only: main\n' in entry
    assert 'serial-group:' in entry


def test_the_docs_deploy_job_publishes_without_measuring():
    """The CI deploy measures nothing (its machines vary); people's deploys still do."""
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')

    deploys = re.findall(
        r'^\s+uvx .* nox -s docs-deploy(?P<arguments>.*)$', configuration, flags=re.MULTILINE
    )

    assert deploys == [' -- --no-measure']


def test_nox_sessions_always_reinstall_the_project():
    """A reused nox venv gets this checkout's package, not an older build of the same version.

    uv sync --no-editable keeps an installed project whose version is unchanged, so a module
    added since (glitchygames/code_tree.py) was missing from the docs build.
    """
    install = docs_deploy_commands(posargs=['--no-measure'])[0]
    reinstalled = {
        install[index + 1]
        for index, argument in enumerate(install)
        if argument == '--reinstall-package'
    }

    assert install[:2] == ('uv', 'sync')
    assert '--all-packages' in install
    # The engine and every workspace member (src/games/mr-muncher), kept the same way
    assert reinstalled == {
        'glitchygames',
        *(member.distribution for member in workspace_members(project_root=PROJECT_ROOT)),
    }


def test_every_other_sync_installs_the_workspace_members():
    """The Linux test container's sync and direnv's (.envrc) install the members (C4, C5).

    Without --all-packages an exact uv sync uninstalls them: the member's tests, its golden
    replay and the replay-metrics hook would then find no mr-muncher.
    """
    import noxfile

    envrc_syncs = [
        line.split()
        for line in (PROJECT_ROOT / '.envrc').read_text(encoding='utf-8').splitlines()
        if line.strip().startswith('uv sync')
    ]

    assert '--all-packages' in noxfile._LINUX_X11_SYNC.split()
    assert envrc_syncs
    assert all('--all-packages' in sync for sync in envrc_syncs)


def test_the_test_session_installs_a_stamped_engine():
    """The nox test session builds its engine with the build stamp: the installed copy names HEAD.

    The installed copy is not editable and has no git checkout; without the stamp it records an
    unknown commit, which measuring refuses (glitchygames/replay/tools/measure.py,
    tests/replay/tools/test_measure.py).
    """
    import noxfile

    session = RecordingSession(posargs=[])
    noxfile.test(session)
    commands = session.commands
    write_stamp = ('uv', 'run', '--frozen', 'python', 'scripts/write_build_stamp.py')
    remove_stamp = (*write_stamp, '--remove')
    install = next(index for index, command in enumerate(commands) if command[:2] == ('uv', 'sync'))
    pytest_run = next(index for index, command in enumerate(commands) if command[0] == 'pytest')

    assert commands.index(write_stamp) < install < commands.index(remove_stamp) < pytest_run


def test_docs_deploy_publishes_only_from_main():
    """A deploy from a branch would publish its unlanded rows: refused before anything is pushed.

    The check (HEAD is on origin/main) runs before the build; a build only (--build-only) is
    not checked.
    """
    commands = docs_deploy_commands(posargs=['--no-measure'])
    on_main = ('git', 'merge-base', '--is-ancestor', 'HEAD', 'origin/main')

    assert on_main in commands
    assert commands.index(on_main) < commands.index(('mkdocs', 'gh-deploy', '--strict'))
    assert on_main not in docs_deploy_commands(posargs=['--build-only'])


def test_the_performance_session_benchmarks_every_testpath():
    """Benchmarks live in several packages' tests: pytest is given no directory to narrow it."""
    import noxfile

    session = RecordingSession(posargs=[])
    noxfile.performance_test(session)

    pytest_command = next(command for command in session.commands if command[0] == 'pytest')
    assert '--benchmark-only' in pytest_command
    assert not [argument for argument in pytest_command if argument.startswith('tests')]


def test_the_wheel_build_builds_every_workspace_package(mocker):
    """The wheel build covers the engine and every workspace member, not the root project alone."""
    import noxfile

    session = mocker.Mock()
    noxfile._build_wheel(session)

    session.run.assert_called_once_with(
        'uv', 'build', '--all-packages', '--wheel', '--out-dir', 'dist', external=True
    )
