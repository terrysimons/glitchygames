"""CircleCI's pinned tool versions match the ones uv.lock pins, so CI runs what a local run does."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

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
        self.virtualenv = type('Virtualenv', (), {'location': '.nox/docs-deploy'})()

    def run(self, *command: str, **_options: object) -> None:
        """Record a command the session runs."""
        self.commands.append(command)

    def run_install(self, *command: str, **_options: object) -> None:
        """Record an install command the session runs."""
        self.commands.append(command)


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
    """A deploy from a person's machine measures this commit's replays first."""
    commands = docs_deploy_commands(posargs=[])

    assert any('measure' in command for command in commands)
    assert ('mkdocs', 'gh-deploy', '--strict') in commands


def test_docs_deploy_with_no_measure_measures_nothing():
    """CI deploys with --no-measure: its machines vary, so their timings would be noise."""
    commands = docs_deploy_commands(posargs=['--no-measure'])

    assert not any('measure' in command for command in commands)
    assert ('python', 'scripts/build_browser_bundle.py', 'all') in commands
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
