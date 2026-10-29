"""CircleCI's pinned tool versions match the ones uv.lock pins, so CI runs what a local run does."""

from __future__ import annotations

import itertools
import json
import re
import shlex
import tomllib
from pathlib import Path
from types import SimpleNamespace

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
        # CI installs nox as a uv tool, outside the project's environment
        ('NOX_VERSION', 'nox'),
        # CI installs uv itself before anything reads uv.lock (GHSA-hq85-5cpj-mr62: < 0.13.4)
        ('UV_VERSION', 'uv'),
    ],
)
def test_circleci_pins_the_locked_version(parameter, package):
    """Each tool CI installs itself is the version uv.lock pins."""
    assert pipeline_parameter_default(name=parameter) == locked_version(package=package)


def test_circleci_runs_an_installed_nox_never_through_uvx():
    """Each job installs nox once, as a uv tool, and runs it directly: no uvx parent waits on it.

    Under ``uvx`` the uvx process stayed alive as nox's parent, about 47 MiB the Linux job's
    memory guard counted (plans/future-work.md, 2026-10-28). Each installation (the POSIX jobs'
    install-deps-posix, the Windows job's own step) pins NOX_VERSION and comes before the job's
    first nox session.
    """
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    install = 'uv tool install "nox[uv]==<< pipeline.parameters.NOX_VERSION >>"'
    jobs = configuration[configuration.index('\njobs:\n') : configuration.index('\nworkflows:\n')]
    windows_job = jobs[
        jobs.index('\n  build-and-test-windows:\n') : jobs.index('\n  deploy-docs:\n')
    ]
    install_deps_posix = configuration[
        configuration.index('\n  install-deps-posix:\n') : configuration.index('\n  nox-format:\n')
    ]

    assert re.search(r'^\s+uvx ', configuration, flags=re.MULTILINE) is None
    assert configuration.count(install) == 2
    assert install in install_deps_posix
    assert windows_job.index(install) < windows_job.index('nox -s ')
    job_starts = [match.start() for match in re.finditer(r'^  [a-z-]+:$', jobs, re.MULTILINE)]
    for start, end in itertools.pairwise([*job_starts, len(jobs)]):
        job = jobs[start:end]
        first_nox = re.search(r'^\s+(- nox-|nox -s )', job, flags=re.MULTILINE)
        if first_nox is not None and not job.startswith('  build-and-test-windows:'):
            assert '      - install-deps-posix\n' in job[: first_nox.start()], job.split(':')[0]
    # The tool is never restored from a cache: the uv caches name uv's Python, not all its data
    assert '- ~/.local/share/uv\n' not in configuration


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


def test_the_docs_deploy_publishes_mains_latest_commit_once():
    """The deploy moves to main's tip first, and stops when gh-pages already holds it.

    The owner (2026-10-29): pull the latest main right before publishing, so a merge that
    landed meanwhile gets its docs. The move comes before the submodule checkout, so the
    pygame-ce submodule is main's too.
    """
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    job = configuration[configuration.index('\n  deploy-docs:\n') :]
    job = job[: job.index('\nworkflows:\n')]

    move = job.index('git checkout --quiet --detach origin/main')
    assert 'git fetch --quiet origin main gh-pages' in job[:move]
    assert move < job.index('git submodule update --init third_party/pygame-ce')
    assert move < job.index('nox -s docs-deploy')
    assert 'circleci-agent step halt' in job[move : job.index('git submodule update')]


def test_the_docs_deploy_job_publishes_without_measuring():
    """The CI deploy measures nothing (its machines vary); people's deploys still do."""
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')

    deploys = re.findall(
        r'^\s+nox -s docs-deploy(?P<arguments>.*)$', configuration, flags=re.MULTILINE
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


def test_only_the_linux_job_sets_the_memory_limit():
    """The Linux job (2 GB, serial) stops a run past 1600 MiB, naming the test (memory_guard.py).

    Only there: the macOS and Windows jobs have the memory, and the plugin needs Linux's
    ``/proc/self/statm`` anyway. The resource class and the worker count stay as they were.
    """
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    linux_job = configuration[
        configuration.index('\n  build-and-test-linux:\n') : configuration.index(
            '\n  build-and-test-macos:\n'
        )
    ]

    assert configuration.count('GLITCHYGAMES_TEST_RSS_LIMIT_MB') == 1
    assert '      GLITCHYGAMES_TEST_RSS_LIMIT_MB: "1600"\n' in linux_job
    assert '    resource_class: small\n' in linux_job
    assert '      PYTEST_WORKERS: "0"\n' in linux_job


class LoggingRecordingSession(RecordingSession):
    """A recording session that also takes the session's log lines and refusals."""

    def log(self, message: str) -> None:
        """Ignore a log line."""

    def error(self, message: str) -> None:
        """Fail as nox would.

        Raises:
            AssertionError: Always, with the message.

        """
        raise AssertionError(message)


class LinuxCiSession(LoggingRecordingSession):
    """A recording session whose git commands answer as a worktree on branch feature/x would."""

    def __init__(self, *, tmp_path: Path) -> None:
        """Answer from ``tmp_path``: its temporary directory, and the repository's git directory."""
        super().__init__(posargs=[])
        self.tmp_path = tmp_path
        self.answers = {
            ('rev-parse', '--git-common-dir'): f'{tmp_path / "repository.git"}\n',
            ('symbolic-ref', '--quiet', '--short', 'HEAD'): 'feature/x\n',
            ('remote', 'get-url', 'origin'): 'https://example.com/glitchygames.git\n',
            ('ls-files', '--stage'): (
                '100644 1111 0\tREADME.md\n160000 2222 0\tthird_party/pygame-ce\n'
            ),
            ('ls-files', '-z', '--cached', '--others', '--exclude-standard'): (
                'README.md\0third_party/pygame-ce\0deleted.py\0README.md\0'
            ),
            ('rev-parse', 'HEAD'): 'abc123\n',
        }

    def run(self, *command: str, **options: object) -> str | None:  # type: ignore[override]
        """Record the command; answer a git command as the worktree would.

        Returns:
            The git command's output, else None.

        """
        super().run(*command, **options)
        if command[0] == 'git':
            return self.answers[command[1:]]
        return None

    def create_tmp(self) -> str:
        """Return the session's temporary directory.

        Returns:
            Its path.

        """
        return str(self.tmp_path)


def test_the_linux_ci_session_runs_the_linux_job_with_its_memory(tmp_path, monkeypatch):
    """``nox -s test-linux-ci``: the job's amd64 image, 2 GB without swap, 1 CPU, its environment.

    Read from .circleci/config.yml, so a change to the job changes the session too.
    """
    import noxfile

    monkeypatch.setattr(noxfile, '_LINUX_CI_RESULTS', tmp_path / 'linux-ci')
    session = LinuxCiSession(tmp_path=tmp_path)

    noxfile.test_linux_ci(session)

    docker_run = next(command for command in session.commands if command[:2] == ('docker', 'run'))
    python_version = pipeline_parameter_default(name='PYTHON_LATEST_VERSION')
    assert f'cimg/python:{python_version}' in docker_run
    assert {'--memory=2g', '--memory-swap=2g', '--cpus=1', '--platform=linux/amd64'} <= set(
        docker_run
    )
    environment = {
        docker_run[index + 1] for index, argument in enumerate(docker_run) if argument == '--env'
    }
    assert {
        'PYTEST_WORKERS=0',
        'GLITCHYGAMES_TEST_RSS_LIMIT_MB=1600',
        'CI=true',
        'CIRCLECI=true',
    } <= environment
    script = docker_run[-1]
    uv_version = pipeline_parameter_default(name='UV_VERSION')
    nox_version = pipeline_parameter_default(name='NOX_VERSION')
    assert f'https://astral.sh/uv/{uv_version}/install.sh' in script
    assert f'uv python install "{python_version}"' in script
    assert script.index(f'uv tool install "nox[uv]=={nox_version}"') < script.index(
        'nox -s test || status=$?'
    )
    assert 'uvx' not in script
    assert (tmp_path / 'linux-ci').is_dir()


def test_the_linux_ci_session_copies_what_git_would_commit_from_a_worktree(tmp_path, monkeypatch):
    """Tracked and untracked-not-ignored files only, no submodule; .git from the git directory.

    A worktree's .git names the repository's git directory on this machine, so that directory is
    mounted at its own path and the clone is made from it; HEAD is the worktree's, on its branch.
    """
    import noxfile

    monkeypatch.setattr(noxfile, '_LINUX_CI_RESULTS', tmp_path / 'linux-ci')
    session = LinuxCiSession(tmp_path=tmp_path)

    noxfile.test_linux_ci(session)

    docker_run = next(command for command in session.commands if command[:2] == ('docker', 'run'))
    repository = tmp_path / 'repository.git'
    assert f'{repository}:{repository}:ro' in docker_run
    assert (tmp_path / 'files').read_bytes() == b'README.md\0'
    script = docker_run[-1]
    # Quoted as the noxfile quotes it (a Windows path's backslashes need quotes)
    assert f'git clone --quiet --no-checkout {shlex.quote(str(repository))} ' in script
    assert 'git update-ref refs/heads/feature/x abc123' in script
    assert 'git symbolic-ref HEAD refs/heads/feature/x' in script
    assert 'git remote set-url origin https://example.com/glitchygames.git' in script
    assert '--exclude' not in script


def test_an_environment_line_the_session_cannot_read_is_refused():
    """An unquoted value would be left out of the container without a word: refused instead."""
    import noxfile

    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8').replace(
        '      PYTEST_WORKERS: "0"\n', '      PYTEST_WORKERS: 0\n'
    )

    with pytest.raises(ValueError, match=r"cannot read .*'PYTEST_WORKERS: 0'"):
        noxfile._linux_ci_job_settings(configuration=configuration)


SBOM_PATH = PROJECT_ROOT / 'docs' / 'sbom.cyclonedx.json'


def macos_job() -> str:
    """Return the macOS job's text in the CircleCI configuration.

    Returns:
        From its name to the Windows job's.

    """
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    return configuration[
        configuration.index('\n  build-and-test-macos:\n') : configuration.index(
            '\n  build-and-test-windows:\n'
        )
    ]


def test_circleci_pins_the_syft_that_wrote_the_committed_sbom():
    """CI's syft is the one named in docs/sbom.cyclonedx.json: another would write another SBOM."""
    sbom = json.loads(SBOM_PATH.read_text(encoding='utf-8'))
    syft_versions = [
        tool['version']
        for tool in sbom['metadata']['tools']['components']
        if tool['name'] == 'syft'
    ]

    assert syft_versions == [pipeline_parameter_default(name='SYFT_VERSION')]


@pytest.mark.parametrize('tool', ['SYFT', 'GRYPE'])
def test_circleci_pins_syft_and_grype_with_checksums(tool):
    """Each is pinned to an exact version and the SHA-256 of its release tarball."""
    assert re.fullmatch(r'\d+\.\d+\.\d+', pipeline_parameter_default(name=f'{tool}_VERSION'))
    assert re.fullmatch(
        r'[0-9a-f]{64}', pipeline_parameter_default(name=f'{tool}_DARWIN_ARM64_SHA256')
    )


def test_circleci_installs_syft_and_grype_checked_before_the_security_scan():
    """The pinned releases are checksummed before extraction, and installed before the scan."""
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    job = macos_job()

    assert 'https://github.com/anchore/${tool}/releases/download/v${version}/${archive}' in (
        configuration
    )
    assert configuration.index('shasum -a 256 -c -') < configuration.index('tar -xzf')
    for tool in ('SYFT', 'GRYPE'):
        assert (
            f'"<< pipeline.parameters.{tool}_VERSION >>" '
            f'"<< pipeline.parameters.{tool}_DARWIN_ARM64_SHA256 >>"'
        ) in configuration
    assert job.index('      - install-supply-chain-tools-macos\n') < job.index(
        '      - nox-security-scan\n'
    )
    # No other installer: never the newest release, never an unchecked script
    assert 'install.sh | sh -s' not in configuration
    assert 'raw.githubusercontent.com/anchore' not in configuration


def test_nothing_runs_safety_or_pip_audit():
    """The scanners syft and grype replaced (the owner, 2026-10-28) are run by nothing."""
    import noxfile

    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8').lower()
    hooks = (PROJECT_ROOT / '.pre-commit-config.yaml').read_text(encoding='utf-8').lower()
    sessions = Path(noxfile.__file__).read_text(encoding='utf-8')

    for text in (configuration, hooks):
        assert 'safety' not in text
        assert 'pip-audit' not in text
    # The nox sessions' commands: never either tool's executable
    assert "'safety'" not in sessions
    assert "'pip-audit'" not in sessions


class SecurityScanSession(LoggingRecordingSession):
    """A recording session for ``nox -s security-scan``: warnings kept, git status answered."""

    def __init__(self, *, git_status: str) -> None:
        """Answer ``git status --porcelain`` with ``git_status``."""
        super().__init__(posargs=[])
        self.git_status = git_status
        self.warnings: list[str] = []
        self.virtualenv = type(
            'Virtualenv', (), {'location': '/checkout/.nox/security-scan-3-14'}
        )()

    def warn(self, message: str) -> None:
        """Keep a warning."""
        self.warnings.append(message)

    def run(self, *command: str, **options: object) -> str | None:  # type: ignore[override]
        """Record the command; answer git status.

        Returns:
            The git status output for a git command, else None.

        """
        super().run(*command, **options)
        return self.git_status if command[0] == 'git' else None


def tools_on_path(*, mocker, present: set[str]) -> None:
    """Replace noxfile's own ``shutil`` so only ``present`` tools are found on PATH."""
    import noxfile

    mocker.patch.object(
        noxfile,
        'shutil',
        SimpleNamespace(which=lambda name: f'/usr/local/bin/{name}' if name in present else None),
    )


SECURITY_SCAN_COMMANDS = [
    (
        'python',
        '-m',
        'scripts.generate_sbom',
        '--lock',
        'uv.lock',
        '--output',
        'docs/sbom.cyclonedx.json',
    ),
    ('git', 'status', '--porcelain', '--', 'docs/sbom.cyclonedx.json'),
    (
        'grype',
        'sbom:docs/sbom.cyclonedx.json',
        '--fail-on',
        'high',
        '--config',
        '.grype.yaml',
    ),
    ('python', '-m', 'scripts.check_licenses', '--sbom', 'docs/sbom.cyclonedx.json'),
]


def test_the_security_scan_runs_bandit_then_the_sbom_grype_and_licenses(mocker, monkeypatch):
    """bandit, then the SBOM from uv.lock, grype on it, its license check."""
    import noxfile

    tools_on_path(mocker=mocker, present={'syft', 'grype'})
    monkeypatch.delenv('CI', raising=False)
    monkeypatch.delenv('CIRCLECI', raising=False)
    session = SecurityScanSession(git_status='')

    noxfile.security_scan(session)

    commands = [command for command in session.commands if command[0] != 'uv']
    assert commands[0][0] == 'bandit'
    assert commands[1:] == SECURITY_SCAN_COMMANDS
    assert session.warnings == []


def test_sbom_drift_fails_the_scan_after_grype_and_the_license_check(mocker, monkeypatch):
    """A regenerated SBOM that differs from the committed one fails, once both scans have run."""
    import noxfile

    tools_on_path(mocker=mocker, present={'syft', 'grype'})
    monkeypatch.delenv('CI', raising=False)
    monkeypatch.delenv('CIRCLECI', raising=False)
    session = SecurityScanSession(git_status=' M docs/sbom.cyclonedx.json\n')

    with pytest.raises(AssertionError, match='differs from the committed one'):
        noxfile.security_scan(session)

    assert [command for command in session.commands if command[0] != 'uv'][1:] == (
        SECURITY_SCAN_COMMANDS
    )
    assert session.warnings == ['SBOM drift: M docs/sbom.cyclonedx.json']


def test_missing_syft_or_grype_is_skipped_locally(mocker, monkeypatch):
    """Locally, bandit still runs and the supply-chain scan is skipped with a warning."""
    import noxfile

    tools_on_path(mocker=mocker, present={'syft'})
    monkeypatch.delenv('CI', raising=False)
    monkeypatch.delenv('CIRCLECI', raising=False)
    session = SecurityScanSession(git_status='')

    noxfile.security_scan(session)

    assert [command[0] for command in session.commands if command[0] != 'uv'] == ['bandit']
    assert len(session.warnings) == 1
    assert session.warnings[0].startswith('grype not found on PATH')


@pytest.mark.parametrize('variable', ['CI', 'CIRCLECI'])
def test_missing_syft_or_grype_fails_in_ci(mocker, monkeypatch, variable):
    """In CI a scan that cannot run is a failure, never a silent pass."""
    import noxfile

    tools_on_path(mocker=mocker, present=set())
    monkeypatch.delenv('CI', raising=False)
    monkeypatch.delenv('CIRCLECI', raising=False)
    monkeypatch.setenv(variable, 'true')
    session = SecurityScanSession(git_status='')

    with pytest.raises(AssertionError, match='syft and grype not found on PATH'):
        noxfile.security_scan(session)
