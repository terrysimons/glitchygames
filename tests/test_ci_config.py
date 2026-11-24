"""CircleCI's pinned tool versions match the ones uv.lock pins, so CI runs what a local run does."""

from __future__ import annotations

import ast
import inspect
import json
import re
import shlex
import shutil
import socket
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, NoReturn

import pytest
import yaml
from pydantic import BaseModel, ConfigDict
from scripts.workspace_packages import workspace_members

from glitchygames.process import OutputCapture, run_command
from tests.ansible_inventory import raspberry_pi_hosts
from tests.ledger_repositories import environment_without_git_variables, git

if TYPE_CHECKING:
    from collections.abc import Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# The pipeline's configuration: the workflows, continued from the setup configuration, which only
# chooses what runs (tests/test_ci_change_scope.py; docs-only changes skip the test jobs)
CIRCLECI_CONFIG_PATH = PROJECT_ROOT / '.circleci' / 'continue_config.yml'
CIRCLECI_SETUP_PATH = PROJECT_ROOT / '.circleci' / 'config.yml'
# How a job's text names its platform: the Linux image, the Windows executor
LINUX_IMAGE_MARKER = '      - image: cimg/python:'
WINDOWS_EXECUTOR_MARKER = 'name: win/default'
# A job that runs a test session runs one of these commands
TEST_SESSION_COMMANDS = ('      - nox-test:\n', '      - nox-test-windows:\n')
LOCK_PATH = PROJECT_ROOT / 'uv.lock'
# The highest TCP port; bind() refuses anything above it
HIGHEST_PORT = 65535


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


def test_every_pipeline_parameter_the_config_uses_is_declared():
    """Each ``<< pipeline.parameters.NAME >>`` names a declared pipeline parameter.

    CircleCI refuses the whole pipeline over one unknown name ("Unknown variable(s)"), and a
    branch merged after a rename keeps the old one: the website's jobs still named
    ``PYTHON_LATEST_VERSION`` after main renamed it ``PYTHON_VERSION``, and no job ran.
    """
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    declared = set(yaml.safe_load(configuration)['parameters'])
    used = set(re.findall(r'<<\s*pipeline\.parameters\.(\w+)\s*>>', configuration))

    assert used, f'{CIRCLECI_CONFIG_PATH} uses no pipeline parameters: the pattern is stale'
    assert used - declared == set()


def test_the_raspberry_pi_playbook_pins_circlecis_uv():
    """The uv the owner measures with on the Pi is the one its CI job installs."""
    playbook = (PROJECT_ROOT / 'ansible' / 'raspberry_pi_runner.yml').read_text(encoding='utf-8')

    uv_version = pipeline_parameter_default(name='UV_VERSION')

    assert f'    raspberry_pi_uv_version: "{uv_version}"\n' in playbook


RASPBERRY_PI_PLAYBOOK_PATH = PROJECT_ROOT / 'ansible' / 'raspberry_pi_runner.yml'
CI_USER = '{{ ci_user }}'


def raspberry_pi_play() -> dict:
    """Return the Raspberry Pi playbook's one play.

    Returns:
        The play, parsed.

    """
    return yaml.safe_load(RASPBERRY_PI_PLAYBOOK_PATH.read_text(encoding='utf-8'))[0]


def raspberry_pi_role_files() -> list[Path]:
    """Return the Pi roles' task and handler files (ansible/roles/raspberry_pi_*).

    Returns:
        The files, sorted.

    """
    roles = PROJECT_ROOT / 'ansible' / 'roles'
    return sorted(
        path
        for path in roles.glob('raspberry_pi_*/*/*.yml')
        if path.parent.name in {'tasks', 'handlers'}
    )


def raspberry_pi_tasks() -> list[dict]:
    """Return every Pi task and handler: each play's, then each Pi role's, blocks flattened.

    Returns:
        The tasks, in order.

    """
    plays = yaml.safe_load(RASPBERRY_PI_PLAYBOOK_PATH.read_text(encoding='utf-8'))
    pending = [task for play in plays for task in [*play['tasks'], *play.get('handlers', [])]]
    for path in raspberry_pi_role_files():
        pending += yaml.safe_load(path.read_text(encoding='utf-8'))
    flattened: list[dict] = []
    while pending:
        task = pending.pop(0)
        if 'block' in task:
            pending[:0] = task['block']
        else:
            flattened.append(task)
    return flattened


def test_the_raspberry_pi_playbook_names_its_deploy_and_ci_users():
    """Two users, each named once: the one Ansible logs in as, and the runner's."""
    variables = raspberry_pi_play()['vars']

    assert variables['deploy_user'] == '{{ ansible_user }}'
    assert variables['ci_user'] == 'circleci'
    assert 'raspberry_pi_video_users' not in variables


def test_the_raspberry_pi_playbook_names_its_users_only_through_their_variables():
    """No task spells out ansible_user or the circleci account: only the two variables do."""
    playbook = RASPBERRY_PI_PLAYBOOK_PATH.read_text(encoding='utf-8')
    roles_text = ''.join(path.read_text(encoding='utf-8') for path in raspberry_pi_role_files())
    tasks_text = playbook[playbook.index('\n  pre_tasks:') :] + roles_text

    assert raspberry_pi_role_files()
    assert 'ansible_user' not in tasks_text
    assert not re.search(r'(name|owner|group|become_user): circleci\s*$', tasks_text, re.MULTILINE)
    assert 'AutomaticLogin=circleci' not in tasks_text
    assert 'autologin-user=circleci' not in tasks_text


def test_raspberry_pi_tasks_never_become_the_deploy_user():
    """Only the CI user is reached through sudo; deploy-user tasks say become: false.

    Ansible skips sudo when the become user is the login user (BECOME_ALLOW_SAME_USER), so
    become_user naming the deploy user would only look like a switch.
    """
    tasks = raspberry_pi_tasks()
    switching = [task for task in tasks if 'become_user' in task]

    assert switching
    assert all(task['become_user'] == CI_USER for task in switching)
    assert all(task.get('become', True) is not False for task in switching)


def test_every_raspberry_pi_task_has_a_name():
    """Each task is named, so a run's output says what each step was."""
    assert all(task.get('name') for task in raspberry_pi_tasks())


def test_deploy_user_tasks_run_as_the_login_user():
    """The tasks working in the deploy user's home run with become: false."""
    tasks = raspberry_pi_tasks()
    names = {task['name']: task for task in tasks}

    for name in (
        'Read the installed uv version',
        'Install uv at its pinned version',
        'Set the git identity of commits made here',
        'Clone the repository the pre-push hook measures in',
    ):
        assert names[name].get('become') is False, name


def test_the_deploy_users_throttling_check_runs_on_a_fresh_connection():
    """The play reconnects between adding the deploy user to video and checking it.

    Its open ssh connection keeps the groups it logged in with (a fresh Pi's first run failed
    here, 2026-11-14). The CI user is checked through sudo, which reads its groups afresh.
    """
    tasks = raspberry_pi_tasks()
    position = {task['name']: index for index, task in enumerate(tasks)}
    reconnect = tasks[position["Reconnect, so the deploy user's session has its new group"]]
    deploy_check = tasks[position['Check the deploy user can read the throttling state']]
    ci_check = tasks[position['Check the CI user can read the throttling state']]

    assert (
        position['Add the users who read the throttling state to the video group']
        < position["Reconnect, so the deploy user's session has its new group"]
        < position['Check the deploy user can read the throttling state']
    )
    assert reconnect['ansible.builtin.meta'] == 'reset_connection'
    assert deploy_check['become'] is False
    assert ci_check['become_user'] == CI_USER
    assert 'loop' not in deploy_check
    assert 'loop' not in ci_check


def circleci_jobs() -> dict[str, dict[str, object]]:
    """Return the CircleCI configuration's jobs, with YAML merge keys resolved.

    Returns:
        Each job's settings, by name.

    """
    return yaml.safe_load(CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8'))['jobs']


def test_each_raspberry_pis_job_uses_the_resource_class_ansible_registers():
    """Each Pi's job (build-and-test-<host>) runs on the resource class its runner registers."""
    jobs = circleci_jobs()
    hosts = raspberry_pi_hosts()

    assert list(hosts) == [
        'raspberry-pi-4-4gb-ubuntu',
        'raspberry-pi-5-8gb-ubuntu',
        'raspberry-pi-5-16gb-ubuntu',
        'raspberry-pi-5-16gb-raspberry-pi-os',
    ]
    for host, variables in hosts.items():
        assert (
            jobs[f'build-and-test-{host}']['resource_class']
            == (variables['raspberry_pi_resource_class'])
        )


@pytest.mark.parametrize(
    'host',
    [
        'raspberry-pi-5-8gb-ubuntu',
        'raspberry-pi-5-16gb-ubuntu',
        'raspberry-pi-5-16gb-raspberry-pi-os',
    ],
)
def test_each_raspberry_pi_5_job_is_the_raspberry_pi_4_job_on_its_own_runner(host):
    """Only the runner differs, so the Pis' results compare the hardware, not the settings."""
    jobs = circleci_jobs()

    assert jobs[f'build-and-test-{host}'] == {
        **jobs['build-and-test-raspberry-pi-4-4gb-ubuntu'],
        'resource_class': f'terrysimons/{host}',
    }


def test_the_8_gb_raspberry_pi_5_is_in_the_inventory():
    """The owner's third Pi (2026-11-14): a Pi 5 with 8 GB at 172.23.23.140, on Ubuntu 26.10."""
    host = raspberry_pi_hosts()['raspberry-pi-5-8gb-ubuntu']

    assert host['ansible_host'] == '172.23.23.140'
    assert host['raspberry_pi_hostname'] == 'rpi5-8gb-ubuntu-2610'
    assert host['raspberry_pi_resource_class'] == 'terrysimons/raspberry-pi-5-8gb-ubuntu'
    assert '8 GB' in host['raspberry_pi_description']


def test_circleci_runs_an_installed_nox_never_through_uvx():
    """Each job installs nox once, as a uv tool, and runs it directly: no uvx parent waits on it.

    Under ``uvx`` the uvx process stayed alive as nox's parent, about 47 MiB the Linux job's
    memory guard counted (plans/future-work.md, 2026-10-28). Each installation (the POSIX jobs'
    install-deps-posix, the Windows job's own step) pins NOX_VERSION and comes before the job's
    first nox session.
    """
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    install = 'uv tool install "nox[uv]==<< pipeline.parameters.NOX_VERSION >>"'
    install_deps_posix = configuration[
        configuration.index('\n  install-deps-posix:\n') : configuration.index('\n  nox-format:\n')
    ]
    install_deps_windows = configuration[
        configuration.index('\n  install-deps-windows:\n') : configuration.index(
            '\n  nox-test-windows:\n'
        )
    ]

    assert re.search(r'^\s+uvx ', configuration, flags=re.MULTILINE) is None
    assert configuration.count(install) == 2
    assert install in install_deps_posix
    assert install in install_deps_windows
    for name, job in circleci_job_texts().items():
        first_nox = re.search(r'^\s+(- nox-|nox -s )', job, flags=re.MULTILINE)
        if first_nox is not None:
            before = job[: first_nox.start()]
            installs = ('      - install-deps-posix', '      - install-deps-windows')
            assert any(install_step in before for install_step in installs), name
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


def test_the_linux_ci_session_installs_what_the_linux_job_installs():
    """The Linux job installs the port tools, and test-linux-ci does the same; neither ansible-core.

    The apt packages test-linux-ci reads from the job (``_linux_ci_job_packages``). iproute2 (ss)
    and lsof: without the platform's port tool the real-socket port test in
    tests/test_ansible_ai_service.py skips. ansible-core comes from uv.lock's dev extra (main's
    #215), which the syntax checks there run first; a separate ``uv tool install`` was a second
    copy nothing ran, removed (the owner, 2026-11-19; plans/lucid-circuit-linux.md, 12).
    """
    import noxfile

    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    noxfile_source = (PROJECT_ROOT / 'noxfile.py').read_text(encoding='utf-8')

    assert {'iproute2', 'lsof'} <= set(noxfile._linux_ci_job_packages(configuration=configuration))
    assert re.findall(r'uv tool install "?ansible', configuration) == []
    assert re.findall(r'uv tool install "?ansible', noxfile_source) == []


def test_the_linux_ci_checkout_copies_with_cp_not_tar():
    """The container's checkout copy uses cp: GNU tar cannot stat the mount under amd64 emulation.

    Docker Desktop's amd64 emulation on Apple silicon refused tar's stat of every file in a
    subdirectory of the mounted checkout ("Function not implemented"), so the session copied 28
    of 9,793 files and stopped (2026-11-23); cp copies them all.
    """
    import noxfile

    script = noxfile._linux_ci_script(
        python_versions=['3.15.2'],
        uv_version='0.13.9',
        nox_version='2026.7.11',
        apt_packages=['fontconfig'],
        checkout=noxfile._HostCheckout(
            common_directory=Path('/repository/.git'),
            head='0' * 40,
            branch='main',
            origin_url=None,
            files=b'README.md\x00src/glitchygames/world.py\x00',
        ),
    )

    assert 'cp --parents --no-dereference' in script
    assert 'tar -C /source' not in script


class RecordingSession:
    """Stands in for a nox session: records every command, runs nothing."""

    def __init__(self, *, posargs: list[str], outputs: dict[str, str] | None = None) -> None:
        """Start with the session's arguments and no commands.

        Args:
            posargs: The session's arguments.
            outputs: What a silent command prints, by its program (``python``): ``run`` returns
                it, as nox does for ``silent=True``.

        """
        self.posargs = posargs
        self.outputs = {} if outputs is None else outputs
        self.commands: list[tuple[str, ...]] = []
        # Each command's environment overrides (``env=``), by command
        self.environments: dict[tuple[str, ...], object] = {}
        # Each command's options (``success_codes=``, ``silent=``, ...), by command
        self.options: dict[tuple[str, ...], dict[str, object]] = {}
        # What the session logged (``session.log``), in order
        self.logs: list[str] = []
        self.virtualenv = type('Virtualenv', (), {'location': '.nox/docs-deploy'})()

    def log(self, message: str) -> None:
        """Record a message the session logs."""
        self.logs.append(message)

    def run(self, *command: str, **options: object) -> str | None:
        """Record a command the session runs, and its environment overrides.

        Returns:
            A silent command's canned output (``outputs``), else None.

        """
        self.commands.append(command)
        self.environments[command] = options.get('env')
        self.options[command] = options
        return self.outputs.get(command[0]) if options.get('silent') else None

    def error(self, message: str) -> NoReturn:
        """Fail the session, as nox's ``session.error`` does.

        Raises:
            RuntimeError: Always, with the message.

        """
        raise RuntimeError(message)

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


def pending_ledger(*, mocker, tmp_path: Path, text: str | None) -> Path:
    """Point the docs deploy at a pending ledger in tmp_path holding ``text`` (None: no file).

    Returns:
        The pending ledger's path.

    """
    import noxfile

    path = tmp_path / 'pending.jsonl'
    if text is not None:
        path.write_text(text, encoding='utf-8')
    mocker.patch.object(noxfile, '_pending_ledger_path', return_value=path)
    return path


def test_docs_deploy_measures_the_replays_by_default(mocker, tmp_path):
    """A deploy from a person's machine measures this commit's replays first, then clears.

    Both through the engine's command: ``glitchygames measure --skip-dirty`` before the build,
    ``glitchygames clear-published`` after the push (the measured rows wait in the pending
    ledger).
    """
    pending_ledger(mocker=mocker, tmp_path=tmp_path, text='{"recording": "a row"}\n')

    commands = docs_deploy_commands(posargs=[])

    measuring = commands.index((*GLITCHYGAMES_IN_THE_PROJECT, 'measure', '--skip-dirty'))
    deploying = commands.index(('mkdocs', 'gh-deploy', '--strict', '--config-file', 'zensical.yml'))
    clearing = commands.index((*GLITCHYGAMES_IN_THE_PROJECT, 'clear-published'))
    assert measuring < deploying < clearing


BUILD_THE_BROWSER_GAMES = ('python', '-m', 'scripts.build_browser_bundle', 'all')


def test_docs_deploy_leaves_the_browser_games_to_gh_deploy(mocker, tmp_path):
    """gh-deploy builds the games afresh itself (scripts/mkdocs_hooks.py): not twice."""
    pending_ledger(mocker=mocker, tmp_path=tmp_path, text=None)

    commands = docs_deploy_commands(posargs=['--no-measure'])

    assert BUILD_THE_BROWSER_GAMES not in commands
    assert ('mkdocs', 'gh-deploy', '--strict', '--config-file', 'zensical.yml') in commands


def test_docs_deploy_build_only_builds_the_browser_games_before_the_docs():
    """A local build builds no games itself, so --build-only builds them first, as a deploy does."""
    commands = docs_deploy_commands(posargs=['--build-only', '--no-measure'])

    building_games = commands.index(BUILD_THE_BROWSER_GAMES)
    building_docs = commands.index(('mkdocs', 'build', '--strict', '--config-file', 'zensical.yml'))
    assert building_games < building_docs


@pytest.mark.parametrize('text', [None, '', '\n  \n'])
def test_docs_deploy_without_pending_rows_clears_nothing(mocker, tmp_path, text):
    """No pending rows (CircleCI's fresh checkout): no ``clear-published``, so no member builds.

    ``uv run --all-packages`` there first built every member from PyPI, and a network blink
    failed a deploy that had already published (CircleCI build 3138).
    """
    import noxfile

    path = pending_ledger(mocker=mocker, tmp_path=tmp_path, text=text)
    session = RecordingSession(posargs=['--no-measure'])

    noxfile.docs_deploy(session)

    assert ('mkdocs', 'gh-deploy', '--strict', '--config-file', 'zensical.yml') in session.commands
    assert not any('clear-published' in command for command in session.commands)
    assert session.logs == [f'No pending rows in {path}: nothing published to clear.']


def test_docs_deploy_with_no_measure_still_clears_rows_measured_before(mocker, tmp_path):
    """Rows measured earlier (``nox -s replay-metrics``) are published, so they are cleared."""
    pending_ledger(mocker=mocker, tmp_path=tmp_path, text='{"recording": "a row"}\n')

    commands = docs_deploy_commands(posargs=['--no-measure'])

    assert commands[-1] == (*GLITCHYGAMES_IN_THE_PROJECT, 'clear-published')


def test_the_pending_ledger_is_the_projects_setting_or_the_engines_default(tmp_path, monkeypatch):
    """Read from pyproject.toml; a project without the key gets the engine's own default."""
    import noxfile

    from glitchygames.replay.tools.settings import ProjectSettings

    monkeypatch.chdir(tmp_path)
    (tmp_path / 'pyproject.toml').write_text('[project]\nname = "a-game"\n', encoding='utf-8')
    default = noxfile._pending_ledger_path()
    (tmp_path / 'pyproject.toml').write_text(
        '[tool.glitchygames]\npending-ledger = "measured/pending.jsonl"\n', encoding='utf-8'
    )

    assert default == Path(ProjectSettings().pending_ledger)
    assert noxfile._pending_ledger_path() == Path('measured/pending.jsonl')


def test_this_repositorys_pending_ledger_is_its_setting():
    """Ours is the [tool.glitchygames] pending-ledger in the root pyproject.toml."""
    import noxfile

    settings = tomllib.loads((PROJECT_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))

    assert noxfile._pending_ledger_path() == Path(
        settings['tool']['glitchygames']['pending-ledger']
    )


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


@pytest.mark.parametrize('configuration_name', ['dummy', 'cocoa'])
def test_every_compare_drivers_run_runs_only_the_drawing_tests(configuration_name, tmp_path):
    """Each run (a baseline, a native one, the images re-run) passes --draws-frames-only."""
    import noxfile

    session = RecordingSession(posargs=[])
    noxfile._run_fingerprinted_tests(
        session,
        configuration={
            'name': configuration_name,
            'environment': {'SDL_VIDEODRIVER': configuration_name},
            'runs_in_linux_container': False,
        },
        directory=tmp_path / 'run',
        arguments=['tests/scenes', '-m', 'slow'],
        settings=noxfile._RunSettings(workers='4'),
    )

    (command,) = session.commands
    assert '--draws-frames-only' in command
    # The caller's selection stays: the plugin deselects after any -m
    assert command[-3:] == ('tests/scenes', '-m', 'slow')


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
    assert ('mkdocs', 'gh-deploy', '--strict', '--config-file', 'zensical.yml') in commands


# How ``nox -s docs-serve`` runs mkdocs: in a fresh environment of its own from uv.lock, removed
# when it ends (noxfile.docs_serve), on 3.15 as every session but the tests (the owner, 2026-11-18:
# "Migrate docs-serve to 3.15")
DOCS_SERVE_IN_A_FRESH_ENVIRONMENT = (
    'uv',
    'run',
    '--isolated',
    '--frozen',
    '--no-editable',
    '--all-packages',
    '--all-extras',
    '--python',
    '3.15',
)


def free_local_port() -> int:
    """Return a port nothing listens on at 127.0.0.1 (the system's pick, released at once).

    Returns:
        The port.

    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


@pytest.mark.parametrize(
    ('arguments', 'address'),
    [
        ([], ('127.0.0.1', 8000)),
        (['--dev-addr', '127.0.0.1:8001'], ('127.0.0.1', 8001)),
        (['-a', 'localhost:8002'], ('localhost', 8002)),
        (['--dev-addr=192.0.2.1:8003'], ('192.0.2.1', 8003)),
        (['--dirty', '-a', '127.0.0.1:8004', '--dev-addr', '127.0.0.1:8005'], ('127.0.0.1', 8005)),
    ],
)
def test_docs_serve_reads_its_address_as_mkdocs_serve_does(arguments, address):
    """``--dev-addr`` or ``-a``, joined by ``=`` or not, the last one given; else 127.0.0.1:8000."""
    import noxfile

    assert noxfile._docs_serve_address(arguments=arguments) == address


def test_docs_serve_runs_mkdocs_in_a_fresh_environment_of_its_own():
    """Each run has its own environment, so a second run never deletes the first's.

    The session's own venv (``reuse_venv=False``) was recreated by every run, before the
    session's code ran: a second ``docs-serve`` deleted the first's packages in the middle of
    its build (2026-11-13: Material's ``favicon.png`` vanished mid-copy).
    """
    import noxfile

    address = f'127.0.0.1:{free_local_port()}'
    session = RecordingSession(posargs=['--dev-addr', address])

    noxfile.docs_serve(session)

    serve = (*DOCS_SERVE_IN_A_FRESH_ENVIRONMENT, 'mkdocs', 'serve', '--strict')
    assert session.commands == [(*serve, '--config-file', 'zensical.yml', '--dev-addr', address)]
    assert session.environments[session.commands[0]] == {'VIRTUAL_ENV': None}


LISTENER_COMMAND = '/home/someone/.venv/bin/python /home/someone/.venv/bin/server --port 8000'


def expected_holder(*, listing: str, command: str) -> str:
    """Return how the refusal names the listener, on this machine.

    Returns:
        `` (by pid N: COMMAND)`` (``ps``'s command line, else ``lsof``'s short name), or ``''``
        without ``lsof`` or a listener it found.

    """
    if shutil.which('lsof') is None or not listing:
        return ''
    if shutil.which('ps') is not None and command:
        return f' (by pid 71400: {command})'
    return ' (by pid 71400: python3.14)'


@pytest.mark.parametrize(
    ('listing', 'command'),
    [
        ('p71400\ncpython3.14\n', LISTENER_COMMAND),
        ('p71400\ncpython3.14\n', ''),
        ('', ''),
    ],
    ids=['named-by-its-command-line', 'named-by-lsof', 'unnamed'],
)
@pytest.mark.parametrize('held', ['port-the-os-hands-out', 'highest-port'])
def test_docs_serve_refuses_a_taken_address_before_building(listing, command, held, mocker):
    """A taken address stops the session at once, naming who holds it and a free one.

    mkdocs binds its address only after the whole build (about five minutes), so it failed late
    (2026-11-13: ports 8000-8002 all held by Python servers). ``lsof`` finds the listener and
    ``ps`` its command line (``lsof``'s short name was ``python3.14`` for all three); without
    ``lsof``, or when it finds none, the message names only the address.

    The highest port, 65535, is pinned rather than left to the OS, which hands it out about once
    in 16,000 binds: the suggestion search probed 65536 and crashed (2026-11-22, seed 872572785;
    bugs/2026-11-22-free-port-search-leaves-the-port-range.md).
    """
    import noxfile

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        if held == 'highest-port':
            port = HIGHEST_PORT
            really_in_use = noxfile._address_in_use
            mocker.patch.object(
                noxfile,
                '_address_in_use',
                side_effect=lambda *, host, port: (
                    port == HIGHEST_PORT or really_in_use(host=host, port=port)
                ),
            )
        else:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            port = listener.getsockname()[1]
        session = RecordingSession(
            posargs=['--dev-addr', f'127.0.0.1:{port}'],
            outputs={'lsof': listing, 'ps': f'{command}\n'},
        )

        with pytest.raises(RuntimeError) as refusal:
            noxfile.docs_serve(session)

    message = str(refusal.value)
    holder = expected_holder(listing=listing, command=command)
    assert message.startswith(f'127.0.0.1:{port} is in use{holder}: ')
    suggestion = re.search(r'nox -s docs-serve -- --dev-addr 127\.0\.0\.1:(\d+)$', message)
    assert suggestion is not None
    assert 1 <= int(suggestion.group(1)) <= HIGHEST_PORT
    assert not any('mkdocs' in command for command in session.commands)


def test_docs_serve_suggests_an_address_that_is_free():
    """The suggested port is one nothing listens on, after the taken one."""
    import noxfile

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        port = listener.getsockname()[1]

        suggested = noxfile._free_port_near(host='127.0.0.1', port=port)

        assert suggested is not None
        assert suggested > port
        assert not noxfile._address_in_use(host='127.0.0.1', port=suggested)
        assert noxfile._address_in_use(host='127.0.0.1', port=port)


def test_docs_serve_suggests_a_port_below_the_highest_when_it_is_taken():
    """With 65535 held, the suggestion is a free port below it, not 65536 (which crashed).

    No listener is needed on 65535: the search starts past it, and probing 65536 raised
    ``OverflowError`` before any bind.
    """
    import noxfile

    suggested = noxfile._free_port_near(host='127.0.0.1', port=HIGHEST_PORT)

    assert suggested is not None
    assert 1 <= suggested < HIGHEST_PORT
    assert not noxfile._address_in_use(host='127.0.0.1', port=suggested)


@pytest.mark.parametrize('port', [1, 1024, 65515, HIGHEST_PORT])
@pytest.mark.parametrize('others_taken', [False, True], ids=['others-free', 'all-taken'])
def test_docs_serve_searches_only_ports_from_1_to_65535(port, others_taken, mocker):
    """Every port probed, and every port suggested, is 1-65535; none free suggests none.

    The invariant for the whole search, at the ports where it meets either end of the range
    (65515 is the last one whose 20 ports above it all exist). ``bind()`` refuses a port outside
    0-65535 with ``OverflowError``, and port 0 means "any port", so neither may be probed.
    """
    import noxfile

    probed: list[int] = []
    held_port = port

    def address_in_use(*, host: str, port: int) -> bool:
        del host
        probed.append(port)
        return others_taken or port == held_port

    mocker.patch.object(noxfile, '_address_in_use', side_effect=address_in_use)

    suggested = noxfile._free_port_near(host='127.0.0.1', port=port)

    assert probed
    assert all(1 <= probe <= HIGHEST_PORT for probe in probed)
    assert port not in probed
    if others_taken:
        assert suggested is None
    else:
        assert suggested is not None
        assert 1 <= suggested <= HIGHEST_PORT
        assert suggested != port


def test_docs_serve_names_no_port_when_none_nearby_is_free(mocker):
    """With every nearby port taken, the refusal says so and names no address to use.

    The old fallback named the port 21 past the taken one, unchecked, which past 65514 is not a
    port at all.
    """
    import noxfile

    mocker.patch.object(noxfile, '_address_in_use', return_value=True)
    mocker.patch.object(noxfile, '_listening_process', return_value=None)
    session = RecordingSession(posargs=['--dev-addr', f'127.0.0.1:{HIGHEST_PORT}'])

    with pytest.raises(RuntimeError) as refusal:
        noxfile.docs_serve(session)

    message = str(refusal.value)
    assert message.startswith(f'127.0.0.1:{HIGHEST_PORT} is in use: ')
    assert '--dev-addr' not in message
    assert 'no free port within 20 of 65535' in message
    assert not any('mkdocs' in command for command in session.commands)


@pytest.mark.parametrize('port_text', ['0', '65536', '70000', 'http'])
def test_docs_serve_refuses_an_address_whose_port_is_not_1_to_65535(port_text):
    """A ``--dev-addr`` port outside 1-65535 is refused by name, before any probe or build.

    Probing 65536 or more raised ``OverflowError``; 0 probed "any port", found it free, and went
    on to the five-minute build.
    """
    import noxfile

    session = RecordingSession(posargs=['--dev-addr', f'127.0.0.1:{port_text}'])

    with pytest.raises(RuntimeError) as refusal:
        noxfile.docs_serve(session)

    assert str(refusal.value) == (
        f'--dev-addr 127.0.0.1:{port_text}: the port must be a number from 1 to 65535'
    )
    assert session.commands == []


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


DOCS_DEPLOY_LOCK = 'serial-group: << pipeline.project.slug >>/deploy-docs'
SITE_DEPLOY_LOCK = 'serial-group: << pipeline.project.slug >>/deploy-site'


def test_the_docs_deploy_starts_as_soon_as_main_changes_under_its_own_lock():
    """Docs deploy from main only, at once, waiting for no job, one docs deploy at a time.

    The owner, 2026-11-20: "Docs only run after merging to main, so let's actually run it in
    parallel to the other jobs". Weighed against a merge that turns main red publishing a broken
    browser game (as #227's did to the tests): "For now I want faster". Its lock is its own, so
    two quick merges cannot race gh-pages, and a deploy that waited its turn finds main's docs
    already published and stops.
    """
    entry = circleci_workflow_job(name='deploy-docs')

    assert 'requires:' not in entry
    assert 'branches:\n              only: main\n' in entry
    assert DOCS_DEPLOY_LOCK in entry


def test_the_docs_deploy_runs_on_linux_and_leaves_the_macs_to_the_tests():
    """deploy-docs runs in deploy-site's Linux image, never on a Mac.

    The owner, 2026-11-20: the deploy took a Mac that pull requests' macOS jobs waited for
    ("cross-job contention for the mac"). It only builds the docs and the browser games, which
    need no Mac.
    """
    linux_image = (
        '    docker:\n      - image: cimg/python:<< pipeline.parameters.PYTHON_VERSION >>\n'
    )
    job = circleci_job_definition(name='deploy-docs')

    assert 'macos:' not in job
    assert job.startswith(linux_image)
    assert circleci_job_definition(name='deploy-site').startswith(linux_image)


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


# The uv commands that sync a nox session's environment (inside a session uv targets it)
UV_SYNCS = frozenset({('uv', 'run'), ('uv', 'sync')})


def test_the_test_session_installs_a_stamped_engine():
    """The nox test session builds its engine with the build stamp: the installed copy names HEAD.

    The installed copy is not editable and has no git checkout; without the stamp it records an
    unknown commit, which measuring refuses (glitchygames/replay/tools/measure.py,
    tests/replay/tools/test_measure.py).
    """
    import noxfile

    installed = '.nox/test-3-15/lib/python3.15/site-packages/glitchygames'
    session = RecordingSession(posargs=[], outputs={'python': f'{installed}\n'})
    noxfile.test(session)
    commands = session.commands
    # The session's python: a `uv run` after the install would sync the session's environment
    # again (editable), replacing the installed copy it stamps
    stamp_installed_copy = ('python', 'scripts/write_build_stamp.py', '--into', installed)
    install = next(index for index, command in enumerate(commands) if command[:2] == ('uv', 'sync'))
    pytest_run = next(index for index, command in enumerate(commands) if command[0] == 'pytest')

    assert install < commands.index(stamp_installed_copy) < pytest_run
    # Nothing syncs the session's environment again after the install: the suite tests the
    # installed (built) engine, not an editable one
    assert not [
        command for command in commands[install + 1 : pytest_run] if command[:2] in UV_SYNCS
    ]
    # Never the checkout's stamp: a build running alongside keeps its own (BUGS.md #224.47)
    assert not [
        command
        for command in commands
        if 'scripts/write_build_stamp.py' in command and '--into' not in command
    ]


def test_the_test_session_installs_the_dev_extra_that_holds_ansible_core():
    """Every test session gets ansible-playbook from uv.lock's dev extra, CI's only copy.

    Since the separate ``uv tool install`` step went (the owner, 2026-11-19), the Ansible syntax
    checks in tests/test_ansible_ai_service.py run the ansible-playbook beside the session's
    Python, which only the dev extra installs: the session syncs with every extra, and the dev
    extra, as written and as locked, names ansible-core. (Those checks also fail in CI when no
    ansible-playbook is found.)
    """
    import noxfile

    installed = '.nox/test-3-15/lib/python3.15/site-packages/glitchygames'
    session = RecordingSession(posargs=[], outputs={'python': f'{installed}\n'})
    noxfile.test(session)
    (sync,) = [command for command in session.commands if command[:2] == ('uv', 'sync')]
    project = tomllib.loads((PROJECT_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    written = project['project']['optional-dependencies']['dev']
    lock = tomllib.loads((PROJECT_ROOT / 'uv.lock').read_text(encoding='utf-8'))
    (engine,) = [package for package in lock['package'] if package['name'] == 'glitchygames']
    locked = engine['optional-dependencies']['dev']

    assert '--all-extras' in sync
    assert [requirement for requirement in written if requirement.startswith('ansible-core')]
    assert 'ansible-core' in {dependency['name'] for dependency in locked}


def test_the_test_session_fails_when_it_cannot_find_its_installed_engine():
    """No package path printed: the session stops rather than run unstamped."""
    import noxfile

    session = RecordingSession(posargs=[])

    with pytest.raises(RuntimeError, match='installed glitchygames'):
        noxfile.test(session)


def test_circleci_runs_3_15_on_every_os():
    """CircleCI's one Python is noxfile.TEST_PYTHONS' one, and every OS runs test-3.15 only.

    Every test step names its session, never a default (the owner: "Be explicit about the 3.14
    testing, too"). Python 3.14 is gone from the tests and CI (the owner, 2026-11-19: "let's get
    rid of Python 3.14 altogether"): no job, parameter or session names it.
    """
    import noxfile

    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    installed = pipeline_parameter_default(name='PYTHON_VERSION').rsplit('.', 1)[0]
    assert (installed,) == noxfile.TEST_PYTHONS
    assert 'default: "3.14' not in configuration
    assert 'test-3.14' not in configuration
    assert noxfile.test.python == list(noxfile.TEST_PYTHONS)
    assert re.search(r'^\s+- nox-test(-windows)?$', configuration, flags=re.MULTILINE) is None
    assert 'default: test-3' not in configuration

    jobs = circleci_job_texts()
    operating_systems = {
        'linux': '      - image: cimg/python:',
        'macos': '    macos:\n',
        'windows': '      name: win/default\n',
    }
    for operating_system, marker in operating_systems.items():
        sessions = {
            session
            for name in workflow_jobs()
            if marker in jobs[name]
            for session in re.findall(
                r'^      - nox-test(?:-windows)?:\n          session: (\S+)$',
                jobs[name],
                flags=re.MULTILINE,
            )
        }
        assert sessions == {f'test-{noxfile.TEST_PYTHONS[-1]}'}, operating_system


# Windows' path limit: 260 characters with the terminating null, so 259 usable (MAX_PATH)
WINDOWS_MAX_PATH = 259
# The longest path a source build met under uv's default cache (CircleCI job 3628, 2026-11-17):
# hidapi 0.15.0 built for Python 3.15, which has no Windows wheel for it, failed with LNK1104 on
# build/temp.win-amd64-cpython-315/Release/<the cache's own path>/hid.cp315-win_amd64.exp, 260
# characters. setuptools repeats the absolute source path inside its build folder, so the cache's
# path counts twice
UV_DEFAULT_WINDOWS_CACHE = r'C:\Users\circleci\AppData\Local\uv\cache'
WINDOWS_SHORT_UV_CACHE = r'C:\uv-cache'


def test_no_parameter_reference_is_escaped():
    r"""Every ``<< ... >>`` is substituted: none follows a backslash, CircleCI's escape for ``<<``.

    A Windows path written ``coverage-data\<< parameters.share >>`` reached PowerShell unreplaced,
    and New-Item refused the path (job 3768, 2026-11-18). A path uses ``/``, which PowerShell takes.
    """
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    escaped = [
        f'{number}: {line.strip()}'
        for number, line in enumerate(configuration.splitlines(), start=1)
        if '\\<<' in line
    ]

    assert escaped == []


def test_every_running_job_that_restores_the_uv_cache_saves_it_last():
    """A job that restores the uv cache saves it as its last step, so each OS's cache is kept.

    Only the 3.14 jobs saved it, so with them off (the owner, 2026-11-18) Linux and Windows saved
    none: the 3.15 jobs save it now (the owner: "Yes, let's move the uv cache").
    """
    jobs = circleci_job_texts()
    restoring = [name for name in workflow_jobs() if '- restore-uv-cache-' in jobs[name]]

    assert set(restoring) >= {
        'test-python-3-15-macos',
        'test-python-3-15-linux',
        'test-python-3-15-windows',
    }
    for name in restoring:
        steps = re.findall(r'^      - ([a-z0-9-]+):?$', jobs[name], flags=re.MULTILINE)
        assert steps[-1].startswith('save-uv-cache-'), (name, steps[-1])


def test_windows_builds_from_source_within_the_path_limit():
    """The Windows job's uv cache is short, cached under that path, and long paths are on.

    The owner chose both (2026-11-17): the short cache brings the build's paths under the limit,
    and long paths are belt and braces (MSVC's linker may not honour them).
    """
    jobs = circleci_job_texts()
    windows_job = jobs['test-python-3-15-windows']
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    save_windows = configuration[
        configuration.index('\n  save-uv-cache-windows:\n') : configuration.index(
            '\n  install-deps-windows:\n'
        )
    ]
    install_windows = configuration[
        configuration.index('\n  install-deps-windows:\n') : configuration.index(
            '\n  nox-test-windows:\n'
        )
    ]

    assert f"      UV_CACHE_DIR: '{WINDOWS_SHORT_UV_CACHE}'\n" in windows_job
    # Every Windows test job builds from source on 3.15 or might, so each has the short cache
    windows_jobs = jobs_that_run_tests(platform_marker=WINDOWS_EXECUTOR_MARKER)
    assert set(windows_jobs) == {'test-python-3-15-windows'}
    for name, job in windows_jobs.items():
        assert f"      UV_CACHE_DIR: '{WINDOWS_SHORT_UV_CACHE}'\n" in job, name
    assert f'            - {WINDOWS_SHORT_UV_CACHE}\n' in save_windows
    assert UV_DEFAULT_WINDOWS_CACHE not in configuration
    assert install_windows.index('LongPathsEnabled') < install_windows.index('uv python install')
    # The failing path, with the short cache in place of the default one, fits
    failing_path_under_short_cache = 260 - 2 * (
        len(UV_DEFAULT_WINDOWS_CACHE) - len(WINDOWS_SHORT_UV_CACHE)
    )
    assert failing_path_under_short_cache <= WINDOWS_MAX_PATH


# What hidapi's source build needs on Linux: Python 3.15 has no manylinux wheel for hidapi 0.15,
# so uv compiles it, its hid extension finding libusb through pkg-config and its hidraw extension
# including libudev.h (CircleCI job 3629: "pkg-config package 'libusb-1.0 >= 1.0.9' not found";
# the Raspberry Pis' playbook installs the same, 2026-11-16 and 2026-11-17)
HIDAPI_SOURCE_BUILD_PACKAGES = frozenset({'pkg-config', 'libusb-1.0-0-dev', 'libudev-dev'})


def test_the_linux_job_installs_what_hidapis_source_build_needs():
    """Its apt step installs pkg-config and libusb's and libudev's headers, beside fontconfig."""
    import noxfile

    packages = noxfile._linux_ci_job_packages(
        configuration=CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    )

    assert HIDAPI_SOURCE_BUILD_PACKAGES | {'fontconfig'} <= set(packages)
    assert 'libusb-dev' not in packages


APT_INSTALL_STEP_NAME = 'Install Linux system dependencies'
APT_CACHE_KEY_PREFIX = 'apt-v2-'
# The file a step writes this ISO week to, whose checksum ends the apt cache's key (git-ignored)
APT_CACHE_WEEK_FILE = 'test-results/apt-cache-week'
# How many times the fallback runs apt-get update before the step fails, and CircleCI's
# no-output limit for a step that sets none: the waits between attempts stay under it
APT_UPDATE_ATTEMPTS = 5
CIRCLECI_DEFAULT_NO_OUTPUT_SECONDS = 600
# The Ubuntu sources file of CircleCI's image (cimg/python:3.15.2, amd64): the step derives
# the main-only sources apt reads from it
UBUNTU_SOURCES = (
    'Types: deb\n'
    'URIs: http://archive.ubuntu.com/ubuntu/\n'
    'Suites: resolute resolute-updates resolute-backports\n'
    'Components: main universe restricted multiverse\n'
    'Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n'
    '\n'
    'Types: deb\n'
    'URIs: http://security.ubuntu.com/ubuntu/\n'
    'Suites: resolute-security\n'
    'Components: main universe restricted multiverse\n'
    'Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n'
)
# The apt settings file the step writes, and the sources file it points apt at
APT_SETTINGS_PATH = Path('etc/apt/apt.conf.d/80glitchygames-apt-cache')
APT_MAIN_SOURCES_PATH = Path('etc/apt/glitchygames-ubuntu-main.sources')


LINUX_SYSTEM_DEPENDENCIES_COMMAND = 'install-linux-system-dependencies'


def linux_job_steps() -> list[Any]:
    """Return the steps that install the Linux jobs' system packages, parsed.

    They are the reusable command both Linux jobs run (test-python-3-15-linux and deploy-docs:
    ``test_both_linux_jobs_install_their_system_packages_through_one_command``).

    Returns:
        The steps, in order.

    """
    commands = yaml.safe_load(CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8'))['commands']
    steps = commands[LINUX_SYSTEM_DEPENDENCIES_COMMAND]['steps']
    assert isinstance(steps, list)
    return steps


def test_both_linux_jobs_install_their_system_packages_through_one_command():
    """The test job and the docs deploy run one install, so one list, cache and fallback.

    The owner, 2026-11-20, moved deploy-docs to Linux. It needs hidapi's source-build packages
    and rsync (the pygame-ce browser wheel's build script); a second copy of the install step
    would drift from the first (as a second package list once did: CircleCI job 3629).
    """
    import noxfile

    jobs = circleci_jobs()

    for name in ('test-python-3-15-linux', 'deploy-docs', CHECKS_JOB):
        steps = jobs[name]['steps']
        assert isinstance(steps, list)
        assert steps.count(LINUX_SYSTEM_DEPENDENCIES_COMMAND) == 1, name
        # Before uv and Python: hidapi builds from source while the project installs
        python_installed = next(
            index
            for index, step in enumerate(steps)
            if isinstance(step, dict) and 'install-deps-posix' in step
        )
        assert steps.index(LINUX_SYSTEM_DEPENDENCIES_COMMAND) < python_installed, name
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    assert len(re.findall(r'sudo apt-get install -y \S', configuration)) == 1
    assert {'rsync', 'libusb-1.0-0-dev', 'libudev-dev', 'pkg-config'} <= set(
        noxfile._linux_ci_job_packages(configuration=configuration)
    )


def test_the_linux_package_reader_refuses_a_job_that_skips_the_install_command():
    """test-linux-ci would otherwise install packages the job itself never installs."""
    import noxfile

    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    skipped = configuration.replace(f'      - {LINUX_SYSTEM_DEPENDENCIES_COMMAND}\n', '', 1)

    with pytest.raises(ValueError, match=f'does not run {LINUX_SYSTEM_DEPENDENCIES_COMMAND}'):
        noxfile._linux_ci_job_packages(configuration=skipped)


def test_the_linux_package_reader_refuses_a_command_without_an_install_line():
    """An install command with no apt line names nothing to install: refused, not empty."""
    import noxfile

    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    no_line = configuration.replace('sudo apt-get install -y ', 'sudo apt-get install ', 1)

    with pytest.raises(ValueError, match='has no "sudo apt-get install -y" line'):
        noxfile._linux_ci_job_packages(configuration=no_line)


def apt_install_step_index(*, steps: list[Any]) -> int:
    """Return the index of the Linux job's system-package step.

    Returns:
        The index.

    """
    for index, step in enumerate(steps):
        if isinstance(step, dict) and step.get('run', {}).get('name') == APT_INSTALL_STEP_NAME:
            return index
    pytest.fail(f'test-python-3-15-linux has no "{APT_INSTALL_STEP_NAME}" step')


def apt_install_script() -> str:
    """Return the Linux job's system-package step's shell script.

    Returns:
        The script.

    """
    steps = linux_job_steps()
    script = steps[apt_install_step_index(steps=steps)]['run']['command']
    assert isinstance(script, str)
    return script


def apt_cache_steps(*, steps: list[Any], kind: str) -> list[tuple[int, dict]]:
    """Return the Linux job's restore_cache or save_cache steps for the apt cache.

    Returns:
        (index, the step's settings) for each one whose key starts with the apt prefix.

    """
    found = []
    for index, step in enumerate(steps):
        if not isinstance(step, dict) or kind not in step:
            continue
        settings = step[kind]
        keys = settings.get('keys', [settings.get('key')])
        if any(str(key).startswith(APT_CACHE_KEY_PREFIX) for key in keys):
            found.append((index, settings))
    return found


def test_the_linux_job_restores_its_apt_cache_before_installing_and_saves_it_after():
    """An Ubuntu mirror outage (jobs 3822, 3827) cannot stop a job whose packages are cached.

    The owner, 2026-11-19 ("Yeah, 226"): cache apt's lists and the downloaded packages. One
    restore before the install and one save after it, under the same key.
    """
    steps = linux_job_steps()
    install = apt_install_step_index(steps=steps)
    restores = apt_cache_steps(steps=steps, kind='restore_cache')
    saves = apt_cache_steps(steps=steps, kind='save_cache')

    assert len(restores) == 1
    assert len(saves) == 1
    (restore_index, restore), (save_index, save) = restores[0], saves[0]
    assert restore_index < install < save_index
    assert restore['keys'][0] == save['key']


def test_the_apt_cache_key_turns_over_weekly_and_falls_back_to_the_last_one():
    """CircleCI never overwrites a key: a key that never changed would freeze the first lists.

    Once the mirror dropped a version those lists name, every run would install from the mirror
    and none could save fresher lists (glitchygames-43's review, 2026-11-19). The key ends with
    this ISO week's checksum, written by a step before the restore; the restore falls back to
    the key without it, so a new week starts from last week's cache, and its run saves anew.
    """
    steps = linux_job_steps()
    ((restore_index, restore),) = apt_cache_steps(steps=steps, kind='restore_cache')
    ((_, save),) = apt_cache_steps(steps=steps, kind='save_cache')
    week_file = APT_CACHE_WEEK_FILE
    week_steps = [
        index
        for index, step in enumerate(steps)
        if isinstance(step, dict)
        and f'date +%G-%V > {week_file}' in str(step.get('run', {}).get('command', ''))
    ]

    assert len(week_steps) == 1
    assert week_steps[0] < restore_index
    assert save['key'].endswith(f'-{{{{ checksum "{week_file}" }}}}')
    (current, fallback) = restore['keys']
    assert current == save['key']
    assert fallback != current
    assert current.startswith(fallback)
    assert fallback.endswith('-')


def test_the_apt_cache_key_holds_the_image_the_arch_and_every_installed_package():
    """Changing the packages, the image or the machine's architecture makes a new cache."""
    import noxfile

    steps = linux_job_steps()
    ((_, save),) = apt_cache_steps(steps=steps, kind='save_cache')
    key = save['key']
    packages = noxfile._linux_ci_job_packages(
        configuration=CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    )

    assert '<< pipeline.parameters.PYTHON_VERSION >>' in key
    assert '{{ arch }}' in key
    assert [package for package in packages if package not in key] == []


def test_apt_retries_and_keeps_its_lists_and_packages_in_the_cached_directory():
    """Apt retries a flaky mirror and keeps what the cache saves where the cache saves it."""
    steps = linux_job_steps()
    ((_, save),) = apt_cache_steps(steps=steps, kind='save_cache')
    (cached_directory,) = save['paths']
    script = apt_install_script()
    home_directory = cached_directory.replace('~', '$HOME', 1)

    assert re.search(r'Acquire::Retries \\?"[1-9]\d*\\?"', script)
    assert f'Dir::State::Lists \\"{home_directory}/lists\\"' in script
    assert f'Dir::Cache::Archives \\"{home_directory}/archives\\"' in script
    assert 'Keep-Downloaded-Packages \\"true\\"' in script


def test_the_linux_job_has_exactly_one_install_line():
    """Noxfile's test-linux-ci and these tests read the packages from that one line."""
    script = apt_install_script()

    assert len(re.findall(r'^\s*sudo apt-get install -y \S', script, flags=re.MULTILINE)) == 1


class AptScriptRun(BaseModel):
    """One run of the Linux job's system-package step with stand-ins (run_apt_install_script)."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    status: int
    # Each apt-get call's arguments, in order
    calls: tuple[str, ...]
    # Each wait the script slept, in seconds, in order
    sleeps: tuple[float, ...]
    # Each time limit a command ran under (timeout's seconds), in order
    timeouts: tuple[float, ...]
    output: str

    @property
    def commands(self) -> list[str]:
        """Each apt-get call's command (install, update, autoclean), in order."""
        return [call.split()[0] for call in self.calls]


def run_apt_install_script(
    *,
    tmp_path: Path,
    cache_hit: bool,
    mirror_up: bool,
    failed_updates: int = 0,
) -> AptScriptRun:
    """Run the step's script with stand-ins for sudo, apt-get and sleep.

    The stand-in apt-get installs when the cache was restored (cache_hit) or after an update
    that reached the mirror; an install with neither fails, as apt-get does with no lists
    ("Unable to locate package", exit 100). Its update reaches the mirror when mirror_up, after
    the first failed_updates attempts fail. A failed update exits 100 only when given
    ``APT::Update::Error-Mode=any``, as apt 3.2 on the job's image does; without it apt exits 0
    after a failed fetch. sudo runs its command as this user, except that ``tee`` writes into
    tmp_path instead of /etc: every argument under /etc/ is taken under tmp_path, where the
    image's Ubuntu sources file (UBUNTU_SOURCES, amd64's, as CircleCI's machines are) is
    written first. sleep records its seconds and returns at once; timeout records its seconds
    and runs its command.

    Returns:
        AptScriptRun: The script's status, apt's calls, the waits and the output.

    """
    stand_ins = tmp_path / 'bin'
    stand_ins.mkdir()
    calls = tmp_path / 'apt-calls.txt'
    sleeps = tmp_path / 'sleeps.txt'
    timeouts = tmp_path / 'timeouts.txt'
    image_sources = tmp_path / 'etc' / 'apt' / 'sources.list.d' / 'ubuntu.sources'
    image_sources.parent.mkdir(parents=True)
    image_sources.write_text(UBUNTU_SOURCES, encoding='utf-8')
    (stand_ins / 'sudo').write_text(
        '#!/bin/bash\n'
        'arguments=()\n'
        'for argument in "$@"; do\n'
        '  case "$argument" in\n'
        '    /etc/*) argument="$STAND_IN_ROOT$argument"; mkdir -p "$(dirname "$argument")" ;;\n'
        '  esac\n'
        '  arguments+=("$argument")\n'
        'done\n'
        'exec "${arguments[@]}"\n',
        encoding='utf-8',
    )
    (stand_ins / 'timeout').write_text(
        '#!/bin/bash\necho "$1" >> "$TIMEOUTS"\nshift\nexec "$@"\n',
        encoding='utf-8',
    )
    (stand_ins / 'apt-get').write_text(
        '#!/bin/bash\n'
        'echo "$*" >> "$APT_CALLS"\n'
        'if [ "$1" = autoclean ]; then exit 0; fi\n'
        'if [ "$1" = update ]; then\n'
        '  attempts_file="$STAND_IN_ROOT/update-attempts"\n'
        '  attempt=$(( $(cat "$attempts_file" 2>/dev/null || echo 0) + 1 ))\n'
        '  echo "$attempt" > "$attempts_file"\n'
        '  if [ "$MIRROR_UP" = 1 ] && [ "$attempt" -gt "$FAILED_UPDATES" ]; then\n'
        '    touch "$STAND_IN_ROOT/updated"; exit 0\n'
        '  fi\n'
        '  echo "E: Failed to fetch http://archive.ubuntu.com/ubuntu/dists/resolute/InRelease"'
        ' >&2\n'
        '  case "$*" in *APT::Update::Error-Mode=any*) exit 100 ;; esac\n'
        '  exit 0\n'
        'fi\n'
        '[ "$CACHE_HIT" = 1 ] || [ -e "$STAND_IN_ROOT/updated" ] || exit 100\n',
        encoding='utf-8',
    )
    (stand_ins / 'sleep').write_text(
        '#!/bin/bash\necho "$1" >> "$SLEEPS"\n',
        encoding='utf-8',
    )
    for stand_in in stand_ins.iterdir():
        stand_in.chmod(0o755)
    home = tmp_path / 'home'
    home.mkdir()
    result = run_command(
        command=['bash', '-c', apt_install_script()],
        environment={
            # /usr/sbin and /sbin: chown is there on macOS
            'PATH': f'{stand_ins}:/usr/bin:/bin:/usr/sbin:/sbin',
            'HOME': str(home),
            'STAND_IN_ROOT': str(tmp_path),
            'APT_CALLS': str(calls),
            'SLEEPS': str(sleeps),
            'TIMEOUTS': str(timeouts),
            'CACHE_HIT': '1' if cache_hit else '0',
            'MIRROR_UP': '1' if mirror_up else '0',
            'FAILED_UPDATES': str(failed_updates),
        },
        timeout_seconds=60,
        capture_output=OutputCapture.TOGETHER,
    )
    return AptScriptRun(
        status=result.returncode,
        calls=tuple(calls.read_text(encoding='utf-8').splitlines()) if calls.exists() else (),
        sleeps=tuple(float(line) for line in sleeps.read_text(encoding='utf-8').split())
        if sleeps.exists()
        else (),
        timeouts=tuple(float(line) for line in timeouts.read_text(encoding='utf-8').split())
        if timeouts.exists()
        else (),
        output=result.stdout or '',
    )


apt_script_needs_bash = pytest.mark.skipif(
    sys.platform == 'win32' or shutil.which('bash') is None,
    reason="the Linux job's script is bash; its stand-ins are bash scripts",
)


@apt_script_needs_bash
def test_every_run_first_refreshes_from_the_mirror_and_prunes_before_the_save(tmp_path):
    """Each run updates first, so its install takes our packages' newest versions, then prunes.

    The owner, 2026-11-19: "Make the update/upgrade non-fatal if it fails", "But attempt it
    every run", "just do it with the packages we care about": the install line upgrades an
    installed package to the fresh lists' version, so no apt-get upgrade touches the image's
    others. autoclean drops the packages the fresh lists no longer name, before the save.
    """
    run = run_apt_install_script(tmp_path=tmp_path, cache_hit=True, mirror_up=True)

    assert (run.status, run.commands) == (0, ['update', 'install', 'autoclean'])


@apt_script_needs_bash
def test_a_failed_refresh_installs_from_the_cache(tmp_path):
    """The mirror down: the first update fails, is reported, and the cache installs anyway."""
    run = run_apt_install_script(tmp_path=tmp_path, cache_hit=True, mirror_up=False)

    assert (run.status, run.commands) == (0, ['update', 'install'])
    assert 'Refreshing from the mirror failed' in run.output


@apt_script_needs_bash
def test_the_first_refresh_gives_up_within_a_minute_and_never_retries(tmp_path):
    """An outage costs a job at most a minute before the cache installs (the owner, 2026-11-19).

    The first update runs under a time limit with apt's retries off: in the outage of
    2026-11-19 one update kept trying for 7+ minutes.
    """
    run = run_apt_install_script(tmp_path=tmp_path, cache_hit=True, mirror_up=False)

    first_update = next(call for call in run.calls if call.startswith('update'))
    assert 'Acquire::Retries=0' in first_update
    assert len(run.timeouts) == 1
    assert run.timeouts[0] <= 60


@apt_script_needs_bash
def test_apt_reads_only_the_main_component_of_ubuntus_own_sources(tmp_path):
    """Our packages are all in Ubuntu's main: apt fetches nothing else (about 4 MB, not 27).

    The image's Docker, git PPA and git-lfs sources and Ubuntu's other components are left
    out, so neither their outages nor their size reach the step. The main-only file keeps
    each source's URIs, suites and key, so amd64's and arm64's mirrors both work.
    """
    run = run_apt_install_script(tmp_path=tmp_path, cache_hit=True, mirror_up=True)
    settings = (tmp_path / APT_SETTINGS_PATH).read_text(encoding='utf-8')
    main_sources = (tmp_path / APT_MAIN_SOURCES_PATH).read_text(encoding='utf-8')

    assert run.status == 0
    assert f'Dir::Etc::SourceList "/{APT_MAIN_SOURCES_PATH}";' in settings
    assert re.search(r'Dir::Etc::SourceParts "/nonexistent[^"]*";', settings)
    assert main_sources == UBUNTU_SOURCES.replace(
        'Components: main universe restricted multiverse', 'Components: main'
    )


@apt_script_needs_bash
def test_a_failed_cached_install_updates_from_the_mirror_and_installs_again(tmp_path):
    """No cache (a new key) and the mirror up: the first refresh fetches the lists to install."""
    run = run_apt_install_script(tmp_path=tmp_path, cache_hit=False, mirror_up=True)

    assert (run.status, run.commands) == (0, ['update', 'install', 'autoclean'])


@apt_script_needs_bash
def test_no_cache_and_no_mirror_fails_the_step_after_its_last_update(tmp_path):
    """With nothing cached and the mirror down, every update fails, then the step does.

    It never installs from lists it could not fetch, and it says it gave up.
    """
    run = run_apt_install_script(tmp_path=tmp_path, cache_hit=False, mirror_up=False)

    assert run.status != 0
    assert run.commands == ['update', 'install'] + ['update'] * APT_UPDATE_ATTEMPTS
    assert 'giving up' in run.output


@apt_script_needs_bash
def test_the_fallback_outlasts_a_few_failed_updates(tmp_path):
    """The fallback's mirror answering on its third try: the job goes on.

    Job 3840 died on one HTTP 520. The run's first refresh failed too, so its cache could not
    install.
    """
    run = run_apt_install_script(
        tmp_path=tmp_path, cache_hit=False, mirror_up=True, failed_updates=3
    )

    assert run.status == 0
    assert run.commands == [
        'update',
        'install',
        'update',
        'update',
        'update',
        'install',
        'autoclean',
    ]
    assert len(run.sleeps) == 2
    assert run.output.count('apt-get update failed') == 2


@apt_script_needs_bash
def test_every_update_fails_on_a_failed_fetch(tmp_path):
    """apt-get update exits 0 after a failed fetch unless told otherwise: each update says so."""
    run = run_apt_install_script(tmp_path=tmp_path, cache_hit=False, mirror_up=False)

    updates = [call for call in run.calls if call.startswith('update')]
    assert updates
    assert all('APT::Update::Error-Mode=any' in update for update in updates)


@apt_script_needs_bash
def test_the_update_waits_grow_and_stay_under_the_no_output_limit(tmp_path):
    """The waits outlast a 7-minute outage (2026-11-19) yet stay under the step's limit."""
    steps = linux_job_steps()
    install_step = steps[apt_install_step_index(steps=steps)]['run']
    limit_seconds = CIRCLECI_DEFAULT_NO_OUTPUT_SECONDS
    assert 'no_output_timeout' not in install_step

    run = run_apt_install_script(tmp_path=tmp_path, cache_hit=False, mirror_up=False)

    assert len(run.sleeps) == APT_UPDATE_ATTEMPTS - 1
    assert list(run.sleeps) == sorted(run.sleeps)
    assert sum(run.sleeps) > 7 * 60
    assert sum(run.sleeps) < limit_seconds


def test_the_install_line_is_the_one_noxfile_reads():
    """The retry leaves the install line as noxfile's test-linux-ci and these tests read it."""
    import noxfile

    assert noxfile._linux_ci_job_packages(
        configuration=CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    ) == [
        'fontconfig',
        'libudev-dev',
        'libusb-1.0-0-dev',
        'pkg-config',
        'iproute2',
        'lsof',
        'rsync',
    ]


def test_every_linux_job_installs_the_linux_jobs_system_packages():
    """Every Linux test job installs through the one shared command, so a new one can't drift.

    Since CI runs 3.15 only (2026-11-19) the Linux job is the only Linux test job: the test
    guards a second Linux test job added later (another Python, another image). The Linux job
    must be one of the test jobs it finds, so it never passes on an empty list.
    """
    import noxfile

    linux_jobs = jobs_that_run_tests(platform_marker=LINUX_IMAGE_MARKER)

    assert noxfile._CIRCLECI_LINUX_JOB in linux_jobs
    for name, job in linux_jobs.items():
        assert f'      - {LINUX_SYSTEM_DEPENDENCIES_COMMAND}\n' in job, name
        assert 'apt-get install' not in job, name


def test_the_windows_job_runs_a_test_worker_on_every_cpu():
    """Windows medium (4 CPUs, 16 GB) runs 4 xdist workers, not CI's half-the-CPUs default.

    The owner, 2026-11-23: noxfile.py's half-CPU rule in CI (#71, "to avoid resource
    exhaustion", from when the count was the host's CPUs) gave each Windows machine 2 workers.
    The job asks for 4 itself, leaving the rule as it is for every other job; a commit of its
    own, so it can be dropped alone if 4 workers prove flaky.
    """
    job = circleci_job_definition(name='test-python-3-15-windows')

    assert '      name: win/default\n      size: medium\n' in job
    assert '      PYTEST_WORKERS: "4"\n' in job


# Each split test job's machines (parallelism): Linux 6 (the owner, 2026-11-23), Windows 3
MACHINES_PER_TEST_JOB = {'linux': 6, 'windows': 3}


@pytest.mark.parametrize(
    ('platform_marker', 'platform', 'save_command', 'combine_job'),
    [
        (LINUX_IMAGE_MARKER, 'linux', 'save-coverage-share-posix', 'coverage-combine-linux'),
        (
            WINDOWS_EXECUTOR_MARKER,
            'windows',
            'save-coverage-share-windows',
            'coverage-combine-windows',
        ),
    ],
    ids=['linux', 'windows'],
)
def test_every_linux_and_windows_test_job_is_split_and_its_coverage_combined(
    platform_marker, platform, save_command, combine_job
):
    """Each runs on its machines, saves each's coverage, and one combine job applies the rule.

    The owner, 2026-11-18 (one Python ran past the one-hour limit on Linux, jobs 3705, 3707):
    "yes" to two machines a job, and "Do it for windows too"; 2026-11-20: "split Linux, Windows
    by 3 instead of 2"; 2026-11-23: Linux on 6 (Docker costs the same per CPU, so about the same
    credits). tests/circleci_test_split.py picks each machine's share; the combine job holds the
    shares together to 100%.
    """
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    workflow = configuration[configuration.index('\nworkflows:\n') :]
    jobs = jobs_that_run_tests(platform_marker=platform_marker)

    assert set(jobs) == {f'test-python-3-15-{platform}'}
    assert set(jobs) <= set(workflow_jobs())
    for name, job in jobs.items():
        session = re.search(r'session: (?P<session>test-[0-9.]+)\n', job)
        assert session is not None, name
        share = f'{platform}-{session["session"]}'
        assert f'    parallelism: {MACHINES_PER_TEST_JOB[platform]}\n' in job, name
        assert '      GLITCHYGAMES_TEST_SPLIT: "circleci"\n' in job, name
        assert f'      - {save_command}:\n          share: {share}\n' in job, name
        # Saved after the tests ran, so the data is the run's
        assert job.index(f'      - {save_command}:') > job.index('session: test-'), name
        # One combine job for the share, after this job
        python = session['session'].removeprefix('test-')
        combine = (
            f'      - {combine_job}:\n'
            f'          name: {combine_job}-{session["session"].replace(".", "-")}\n'
            f'          share: {share}\n'
            f'          pythons: {PYTHON_PARAMETERS[python]}\n'
            f'          session: coverage-combine-{python}\n'
            f'          requires:\n'
            f'            - {name}\n'
        )
        assert workflow.count(combine) == 1, name
        assert workflow.count(f'          share: {share}\n') == 1, name


# Each Python's pipeline parameter, as a job's install step names it
PYTHON_PARAMETERS = {
    '3.15': '<< pipeline.parameters.PYTHON_VERSION >>',
}
# The Linux and Windows test jobs, each one Python's
ONE_PYTHON_JOBS = {
    'test-python-3-15-linux': '3.15',
    'test-python-3-15-windows': '3.15',
}


def nox_sessions_of(job: str) -> set[str]:
    """Return the nox sessions a job's steps run: its test sessions, timer report and builds.

    Returns:
        The sessions' names.

    """
    sessions = set(re.findall(r'session: (test-[0-9.]+)\n', job))
    if '- nox-timer-report' in job or 'nox -s timer-report' in job:
        sessions.add('timer-report')
    if re.search(r'^      - nox-build(-windows)?$', job, flags=re.MULTILINE):
        sessions.add('build')
    return sessions


@pytest.mark.parametrize(('name', 'python'), ONE_PYTHON_JOBS.items(), ids=list(ONE_PYTHON_JOBS))
def test_a_one_python_job_installs_and_runs_only_its_python(name, python):
    """A 3.15 job's nox runs only 3.15, and a 3.14 job's only 3.14, as each installs only it.

    The owner, 2026-11-18: "Make sure we're only targeting 3.15 with nox in the 3.15 jobs", "Same
    with the commented out 3.14 blocks". The build is 3.15's, so it is in the 3.15 jobs.
    """
    import noxfile

    job = circleci_job_texts()[name]
    pythons_of_session = {
        'timer-report': noxfile.timer_report.python,
        'build': noxfile.build_all.python,
        **{f'test-{version}': [version] for version in PYTHON_PARAMETERS},
    }

    assert re.findall(r'          pythons: (.+)\n', job) == [PYTHON_PARAMETERS[python]]
    sessions = nox_sessions_of(job)
    assert f'test-{python}' in sessions
    assert ('build' in sessions) == (python == '3.15'), name
    for session in sessions:
        assert pythons_of_session[session] == [python], (name, session)


def build_step_command(*, command_name: str) -> str:
    """Return the script of a CircleCI build command's build step.

    Returns:
        The step's ``command`` text.
    """
    configuration = yaml.safe_load(CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8'))
    steps = configuration['commands'][command_name]['steps']
    return next(step['run']['command'] for step in steps if 'run' in step)


# (CIRCLE_NODE_INDEX, CIRCLE_NODE_TOTAL) and whether that machine builds: an unsplit job (the
# macOS job) on its only machine, a split job (Linux, Windows) on its last, never twice
BUILD_MACHINE_LAYOUTS = [
    pytest.param(None, None, True, id='no-split-variables'),
    pytest.param('0', '1', True, id='unsplit'),
    pytest.param('0', '2', False, id='split-first-machine'),
    pytest.param('1', '2', True, id='split-last-machine'),
]


def run_build_step(
    *,
    interpreter: list[str],
    script: str,
    node_index: str | None,
    node_total: str | None,
    home: Path,
) -> str:
    """Run a build step's script with ``nox -s build`` replaced by a marker, as one machine.

    Returns:
        What it printed.
    """
    environment = {'PATH': '/usr/bin:/bin', 'HOME': str(home), 'USERPROFILE': str(home)}
    if node_index is not None and node_total is not None:
        environment |= {'CIRCLE_NODE_INDEX': node_index, 'CIRCLE_NODE_TOTAL': node_total}
    completed = run_command(
        command=[*interpreter, script.replace('nox -s build', 'echo BUILDING')],
        environment=environment,
        timeout_seconds=60,
        capture_output=OutputCapture.TOGETHER,
    )
    assert completed.returncode == 0, completed.stdout
    return completed.stdout


@pytest.mark.parametrize(('node_index', 'node_total', 'builds'), BUILD_MACHINE_LAYOUTS)
def test_a_job_builds_on_its_last_machine_only(tmp_path, node_index, node_total, builds):
    """The Linux and macOS build step: machine 1 of a split job, the only machine of the rest.

    The owner, 2026-11-19: "move building the binary and wheel over to machine 1 for windows and
    linux to help balance the build time out" (machine 0 also ran the build after its share of
    the tests: 53 of the Linux job's 60 minutes on 66df986e). The last machine, not machine 1:
    the macOS job is not split, and "machine 1" would never build there.
    """
    printed = run_build_step(
        interpreter=['bash', '-c'],
        script=build_step_command(command_name='nox-build'),
        node_index=node_index,
        node_total=node_total,
        home=tmp_path,
    )

    assert ('BUILDING' in printed) is builds


@pytest.mark.skipif(
    shutil.which('pwsh') is None and shutil.which('powershell') is None,
    reason='PowerShell is not installed here (the Windows job and macOS with pwsh run it)',
)
@pytest.mark.parametrize(('node_index', 'node_total', 'builds'), BUILD_MACHINE_LAYOUTS)
def test_a_windows_job_builds_on_its_last_machine_only(tmp_path, node_index, node_total, builds):
    """The Windows build step, run by PowerShell: as the Linux one (machine 1 of a split job)."""
    powershell = shutil.which('pwsh') or shutil.which('powershell')
    assert powershell is not None
    printed = run_build_step(
        interpreter=[powershell, '-NoProfile', '-NonInteractive', '-Command'],
        script=build_step_command(command_name='nox-build-windows'),
        node_index=node_index,
        node_total=node_total,
        home=tmp_path,
    )

    assert ('BUILDING' in printed) is builds


def test_the_builds_are_on_3_15_once_an_os():
    """Build and build-binary run on 3.15; each OS builds in one running job, on one machine.

    The owner, 2026-11-18: "Switch the builds over to 3.15". A split job runs every step on each
    machine, so its build runs on one machine only (its last:
    ``test_a_job_builds_on_its_last_machine_only``).
    """
    import noxfile

    assert noxfile.PINNED_PYTHONS == ['3.15']
    assert noxfile.build_all.python == noxfile.build_binary.python == ['3.15']
    jobs = circleci_job_texts()
    building = {
        name
        for name in workflow_jobs()
        if re.search(r'^      - nox-build(-windows)?$', jobs[name], flags=re.MULTILINE)
    }
    assert building == {
        'test-python-3-15-macos',
        'test-python-3-15-linux',
        'test-python-3-15-windows',
    }
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    for command in ('nox-build', 'nox-build-windows'):
        steps = configuration.split(f'\n  {command}:\n', 1)[1].split('\n\n', 1)[0]
        assert 'CIRCLE_NODE_INDEX' in steps, command
        assert steps.index('CIRCLE_NODE_INDEX') < steps.index('nox -s build'), command


def test_a_coverage_combine_session_runs_on_each_test_python():
    """coverage-combine-3.14 and -3.15: a split job's data is combined on its own Python."""
    import noxfile

    assert noxfile.coverage_combine.python == list(noxfile.TEST_PYTHONS)


def test_every_session_but_the_tests_is_pinned_to_3_15():
    """Only the test and coverage-combine sessions are one a Python; every other is 3.15's.

    The owner, 2026-11-18: "pin 3.15", "Also upgrade deploy-docs to 3.15". The macOS job and
    deploy-docs, which run those sessions, install 3.15 alone.
    """
    import noxfile

    pinned = {
        name: session.python
        for name, session in vars(noxfile).items()
        if callable(session) and isinstance(getattr(session, 'python', None), list)
    }
    assert pinned, 'no nox session found'
    for name, python in pinned.items():
        expected = (
            list(noxfile.TEST_PYTHONS)
            if getattr(noxfile, name).__name__ in {'test', 'coverage_combine'}
            else noxfile.PINNED_PYTHONS
        )
        assert python == expected, name
    jobs = circleci_job_texts()
    for job in ('test-python-3-15-macos', 'deploy-docs', CHECKS_JOB):
        assert re.findall(r'          pythons: (.+)\n', jobs[job]) == [PYTHON_PARAMETERS['3.15']], (
            job
        )


def test_a_split_share_turns_off_the_coverage_rule_and_names_test_files():
    """Set: its 100% rule off (applied combined) and file names in JUnit (CircleCI's timings)."""
    import noxfile

    arguments = noxfile.split_share_pytest_arguments(
        environment={'GLITCHYGAMES_TEST_SPLIT': 'circleci'}
    )

    assert arguments == ['--cov-fail-under=0', '-o', 'junit_family=xunit1']


def test_an_unsplit_run_adds_no_arguments():
    """Unset (macOS, a local run): pytest's own 100% rule and report stand."""
    import noxfile

    assert noxfile.split_share_pytest_arguments(environment={}) == []


# The test session's order switch, which CircleCI's test jobs set to "roll"
SUITE_ORDER_VARIABLE = 'GLITCHYGAMES_TEST_ORDER'


@pytest.fixture(autouse=True)
def suite_order_record_in_tmp_path(tmp_path, monkeypatch):
    """A test session run here writes its order record under tmp_path, not test-results/."""
    import noxfile

    record = tmp_path / 'test-results' / 'test-order.txt'
    monkeypatch.setattr(noxfile, 'SUITE_ORDER_RECORD', record)
    return record


def test_the_suite_order_is_fixed_unless_a_run_asks_for_another():
    """Unset or ``fixed``: the files' own order, nothing rolled, pytest-randomly left blocked."""
    import noxfile

    for environment in ({}, {SUITE_ORDER_VARIABLE: 'fixed'}):
        order = noxfile.choose_suite_order(environment=environment)

        assert order == noxfile.SuiteOrder(seed=None, rolled=False), environment
        assert noxfile.suite_order_pytest_arguments(order=order) == []


def test_a_rolled_order_flips_a_coin_then_draws_a_seed():
    """``roll``: a draw of two picks fixed (0) or shuffled (1); shuffled then draws its seed.

    The owner, 2026-11-20: "roll to decide if we're randomizing or not, and then also roll the
    seed if we are randomizing".
    """
    import noxfile

    for coin, expected_draws, expected in (
        ([0], [2], noxfile.SuiteOrder(seed=None, rolled=True)),
        (
            [1, 4242],
            [2, noxfile.RANDOM_ORDER_SEED_LIMIT],
            noxfile.SuiteOrder(seed=4242, rolled=True),
        ),
    ):
        results = iter(coin)
        draws: list[int] = []

        def draw(limit: int, results=results, draws=draws) -> int:
            draws.append(limit)
            return next(results)

        order = noxfile.choose_suite_order(environment={SUITE_ORDER_VARIABLE: 'roll'}, draw=draw)

        assert order == expected
        assert draws == expected_draws

    shuffled = noxfile.SuiteOrder(seed=4242, rolled=True)
    assert noxfile.suite_order_pytest_arguments(order=shuffled) == [
        '-p',
        'randomly',
        '--randomly-dont-reset-seed',
        '--randomly-seed=4242',
    ]


# A CircleCI machine's identity: its workflow's workspace (kept by a rerun from failed, which
# gets a new workflow ID), its job and its machine index
CIRCLECI_MACHINE = {
    SUITE_ORDER_VARIABLE: 'roll',
    'CIRCLE_WORKFLOW_WORKSPACE_ID': 'workspace-7f3a',
    'CIRCLE_WORKFLOW_ID': 'workspace-7f3a',
    'CIRCLE_JOB': 'test-python-3-15-linux',
    'CIRCLE_NODE_INDEX': '1',
}


def _refuse_to_draw(limit: int) -> int:
    message = f'drew below {limit}: a CircleCI roll comes from the workflow, not a draw'
    raise AssertionError(message)


def test_a_rerun_of_a_circleci_machine_rolls_what_its_first_run_rolled():
    """The roll is a function of the workspace, job and machine: a rerun gets the same order.

    The owner, 2026-11-20 ("Yes"): a rerun from failed keeps CIRCLE_WORKFLOW_WORKSPACE_ID (a
    community report, unverified until a real rerun shows it), so a shuffle-only failure comes
    back on rerun instead of vanishing.
    """
    import noxfile

    first_run = noxfile.choose_suite_order(environment=CIRCLECI_MACHINE, draw=_refuse_to_draw)
    rerun = noxfile.choose_suite_order(
        environment=CIRCLECI_MACHINE | {'CIRCLE_WORKFLOW_ID': 'rerun-90c1'},
        draw=_refuse_to_draw,
    )

    assert (first_run.seed, first_run.rolled) == (rerun.seed, rerun.rolled)
    assert first_run.rolled
    assert first_run.workspace == rerun.workspace == 'workspace-7f3a'
    assert not first_run.rerun
    assert rerun.rerun


def test_each_workflow_and_machine_rolls_its_own_order():
    """New workspaces (new pushes) come up both ways, seeds in range; machines roll apart."""
    import noxfile

    orders = [
        noxfile.choose_suite_order(
            environment=CIRCLECI_MACHINE
            | {'CIRCLE_WORKFLOW_WORKSPACE_ID': f'w{index}', 'CIRCLE_WORKFLOW_ID': f'w{index}'},
            draw=_refuse_to_draw,
        )
        for index in range(200)
    ]
    seeds = [order.seed for order in orders if order.seed is not None]
    machines = {
        noxfile.choose_suite_order(
            environment=CIRCLECI_MACHINE | {'CIRCLE_NODE_INDEX': str(index)},
            draw=_refuse_to_draw,
        )
        for index in range(20)
    } | {
        noxfile.choose_suite_order(
            environment=CIRCLECI_MACHINE | {'CIRCLE_JOB': f'job-{index}'},
            draw=_refuse_to_draw,
        )
        for index in range(20)
    }

    assert 0 < len(seeds) < len(orders)
    assert len(set(seeds)) == len(seeds)
    assert all(0 <= seed < noxfile.RANDOM_ORDER_SEED_LIMIT for seed in seeds)
    assert len(machines) > 2


def test_without_a_circleci_workspace_a_roll_draws_at_random():
    """Unset or empty (a local run): the draw decides, and the order says so."""
    import noxfile

    for workspace in ({}, {'CIRCLE_WORKFLOW_WORKSPACE_ID': ''}):
        environment = {SUITE_ORDER_VARIABLE: 'roll', **workspace}
        order = noxfile.choose_suite_order(environment=environment, draw=lambda limit: 0)

        assert order == noxfile.SuiteOrder(seed=None, rolled=True, workspace=None, rerun=False)
        assert 'at random' in noxfile.describe_suite_order(order=order)


def test_the_order_says_whether_it_is_a_first_run_or_a_rerun():
    """The log line names the workspace and the kind of run, so a rerun's order can be trusted."""
    import noxfile

    first_run = noxfile.choose_suite_order(environment=CIRCLECI_MACHINE)
    rerun = noxfile.choose_suite_order(
        environment=CIRCLECI_MACHINE | {'CIRCLE_WORKFLOW_ID': 'rerun-90c1'}
    )

    assert 'workspace-7f3a' in noxfile.describe_suite_order(order=first_run)
    assert 'first run' in noxfile.describe_suite_order(order=first_run)
    assert 'rerun' in noxfile.describe_suite_order(order=rerun)
    assert 'same roll as its first run' in noxfile.describe_suite_order(order=rerun)


def test_rolling_comes_up_both_ways_with_seeds_in_range():
    """The real draw: over 200 rolls both outcomes appear (a miss is 2**-199), seeds in range."""
    import noxfile

    orders = [
        noxfile.choose_suite_order(environment={SUITE_ORDER_VARIABLE: 'roll'}) for _ in range(200)
    ]
    seeds = [order.seed for order in orders if order.seed is not None]

    assert all(order.rolled for order in orders)
    assert 0 < len(seeds) < len(orders)
    assert all(0 <= seed < noxfile.RANDOM_ORDER_SEED_LIMIT for seed in seeds)


def test_a_seed_replays_that_shuffled_order():
    """A number: that seed, nothing rolled (how a rolled CI run's order is replayed)."""
    import noxfile

    order = noxfile.choose_suite_order(environment={SUITE_ORDER_VARIABLE: '4242'})

    assert order == noxfile.SuiteOrder(seed=4242, rolled=False)


def test_an_unknown_suite_order_stops_the_run():
    """Anything else, or a seed outside pytest-randomly's range, stops rather than guess."""
    import noxfile

    for value in ('shuffle', 'Roll', '-1', str(noxfile.RANDOM_ORDER_SEED_LIMIT), ''):
        with pytest.raises(ValueError, match=SUITE_ORDER_VARIABLE):
            noxfile.choose_suite_order(environment={SUITE_ORDER_VARIABLE: value})


# The marker of a test that times real work against a tolerance (tests/harness.py registers it)
WALL_CLOCK_MARKER = 'wall_clock'


def option_value(command: Sequence[str], option: str) -> str:
    """Return the value after the last ``option`` in a command (pytest's last one wins).

    Returns:
        The value.

    """
    index = len(command) - 1 - list(reversed(command)).index(option)
    return command[index + 1]


@pytest.mark.parametrize('split', [False, True], ids=['one machine', 'a split machine'])
def test_the_test_session_runs_the_wall_clock_tests_alone_after_the_rest(monkeypatch, split):
    """Two pytest runs: every other test in parallel, then the wall_clock tests serially.

    #287's Windows job (5141) ran 4 workers on 4 CPUs, and a timer accuracy test lost its
    deadline to the other workers (19 ms against a 3 ms bound). The owner, 2026-11-23: keep the
    workers, and time real work alone. The second run appends to the first's coverage, so the
    100% rule (off on a split machine) is applied to both; it writes its own JUnit report, and a
    machine whose share holds no wall_clock test (pytest's exit 5) passes.
    """
    import noxfile

    installed = '.nox/test-3-15/lib/python3.15/site-packages/glitchygames'
    monkeypatch.setenv('PYTEST_WORKERS', '4')
    if split:
        monkeypatch.setenv('GLITCHYGAMES_TEST_SPLIT', 'circleci')
    else:
        monkeypatch.delenv('GLITCHYGAMES_TEST_SPLIT', raising=False)
    session = RecordingSession(posargs=[], outputs={'python': f'{installed}\n'})
    noxfile.test(session)
    parallel, serial = [command for command in session.commands if command[0] == 'pytest']

    assert option_value(parallel, '-m') == f'not {WALL_CLOCK_MARKER}'
    assert option_value(parallel, '-n') == '4'
    assert '--cov-fail-under=0' in parallel
    assert option_value(serial, '-m') == WALL_CLOCK_MARKER
    assert option_value(serial, '-n') == '0'
    assert '--cov-append' in serial
    assert '--junitxml=test-results/junit-wall-clock.xml' in serial
    assert ('--cov-fail-under=0' in serial) == split
    assert session.options[serial]['success_codes'] == [0, 5]
    # Only the files that hold wall_clock tests are collected by the serial run, none by the other
    assert serial[-len(noxfile.WALL_CLOCK_TEST_FILES) :] == noxfile.WALL_CLOCK_TEST_FILES
    assert not [argument for argument in parallel if argument.endswith('.py')]
    # Both runs take the same order and log level
    for argument in ('--log-cli-level=WARNING',):
        assert (argument in parallel) == (argument in serial)


def test_the_shuffled_pre_push_run_times_the_wall_clock_tests_alone_too():
    """test-random (the pre-push hook) splits the same way: every core, then one process."""
    import noxfile

    session = RecordingSession(posargs=['12345'])
    noxfile.test_random(session)
    parallel, serial = session.commands

    assert option_value(parallel, '-m') == f'not {WALL_CLOCK_MARKER}'
    assert option_value(parallel, '-n') == 'auto'
    assert option_value(serial, '-m') == WALL_CLOCK_MARKER
    assert option_value(serial, '-n') == '0'
    assert '--randomly-seed=12345' in serial
    assert serial[-len(noxfile.WALL_CLOCK_TEST_FILES) :] == noxfile.WALL_CLOCK_TEST_FILES
    assert not [argument for argument in parallel if argument.endswith('.py')]
    assert session.options[serial]['success_codes'] == [0, 5]


def test_the_wall_clock_file_list_is_every_test_file_that_uses_the_marker():
    """noxfile.WALL_CLOCK_TEST_FILES is exactly the test files that use the wall_clock marker.

    The serial run collects only these files, so a test marked in a file missing from the list
    would silently never run, in either run. A marker applied some way the text does not show
    (a conftest adding it to items) is not detected: name it here by hand if one appears.
    """
    import noxfile

    marker_use = re.compile(rf'pytest\.mark\.{WALL_CLOCK_MARKER}\b')
    test_files = sorted(
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in [
            *(PROJECT_ROOT / 'tests').rglob('test_*.py'),
            *(PROJECT_ROOT / 'src').glob('*/*/tests/**/test_*.py'),
        ]
    )
    users = [
        path
        for path in test_files
        if marker_use.search((PROJECT_ROOT / path).read_text(encoding='utf-8'))
    ]

    assert users, 'no test file uses the wall_clock marker: the detection is stale'
    assert list(noxfile.WALL_CLOCK_TEST_FILES) == users


def test_the_test_session_prints_its_order_and_passes_it_to_pytest(monkeypatch):
    """The order is logged before pytest runs, shuffled or fixed, and a shuffle reaches pytest."""
    import noxfile

    installed = '.nox/test-3-15/lib/python3.15/site-packages/glitchygames'
    monkeypatch.setenv(SUITE_ORDER_VARIABLE, '4242')
    session = RecordingSession(posargs=[], outputs={'python': f'{installed}\n'})
    noxfile.test(session)
    # Both runs (the parallel one and the wall_clock tests' serial one) take the order
    pytest_runs = [command for command in session.commands if command[0] == 'pytest']

    assert len(pytest_runs) == 2
    for pytest_run in pytest_runs:
        assert '--randomly-seed=4242' in pytest_run
        assert pytest_run[pytest_run.index('randomly') - 1] == '-p'
    assert [log for log in session.logs if 'Test order: shuffled, seed 4242' in log]

    monkeypatch.delenv(SUITE_ORDER_VARIABLE)
    session = RecordingSession(posargs=[], outputs={'python': f'{installed}\n'})
    noxfile.test(session)
    pytest_runs = [command for command in session.commands if command[0] == 'pytest']

    assert len(pytest_runs) == 2
    for pytest_run in pytest_runs:
        assert not [argument for argument in pytest_run if 'randomly' in argument]
    assert [log for log in session.logs if log.startswith('Test order: fixed')]


def test_the_test_session_writes_its_order_for_the_jobs_artifacts(
    monkeypatch, suite_order_record_in_tmp_path
):
    """test-results/test-order.txt holds the order, seed, workspace and kind of run, before pytest.

    CircleCI uploads test-results/ with ``when: always``, so a failed job's roll is a file beside
    its test-split-junit.txt.
    """
    import noxfile

    installed = '.nox/test-3-15/lib/python3.15/site-packages/glitchygames'
    for name, value in (CIRCLECI_MACHINE | {'CIRCLE_WORKFLOW_ID': 'rerun-90c1'}).items():
        monkeypatch.setenv(name, value)
    session = RecordingSession(posargs=[], outputs={'python': f'{installed}\n'})
    noxfile.test(session)
    order = noxfile.choose_suite_order(environment=CIRCLECI_MACHINE)
    record = suite_order_record_in_tmp_path.read_text(encoding='utf-8').splitlines()

    assert record[0] == noxfile.describe_suite_order(
        order=noxfile.choose_suite_order(
            environment=CIRCLECI_MACHINE | {'CIRCLE_WORKFLOW_ID': 'rerun-90c1'}
        )
    )
    assert f'order={"fixed" if order.seed is None else "shuffled"}' in record
    assert f'seed={"" if order.seed is None else order.seed}' in record
    assert 'workspace=workspace-7f3a' in record
    assert 'rerun=yes' in record


def test_a_failed_test_session_restates_its_order_and_how_to_replay_it(monkeypatch):
    """After a failure (the log's start is 26,000 tests back) the order and replay come again."""
    import noxfile
    from nox.command import CommandFailed

    installed = '.nox/test-3-15/lib/python3.15/site-packages/glitchygames'
    monkeypatch.setenv(SUITE_ORDER_VARIABLE, '4242')
    session = RecordingSession(posargs=[], outputs={'python': f'{installed}\n'})
    record = session.run

    def run(*command: str, **options: object) -> str | None:
        if command[0] == 'pytest':
            reason = 'pytest failed'
            raise CommandFailed(reason)
        return record(*command, **options)

    monkeypatch.setattr(session, 'run', run)

    with pytest.raises(RuntimeError) as failure:
        noxfile.test(session)

    message = str(failure.value)
    assert 'Test order: shuffled, seed 4242' in message
    assert f'{SUITE_ORDER_VARIABLE}=4242' in message


def test_every_ci_test_job_rolls_its_suite_order():
    """Each job that runs the suite sets ``roll``, so each machine flips its own coin."""
    jobs = {name: job for name, job in circleci_job_texts().items() if 'session: test-3.15' in job}

    assert set(jobs) == {
        'test-python-3-15-macos',
        'test-python-3-15-linux',
        'test-python-3-15-windows',
        'build-and-test-raspberry-pi-4-4gb-ubuntu',
    }
    for name, job in jobs.items():
        assert f'      {SUITE_ORDER_VARIABLE}: "roll"\n' in job, name


def test_the_combine_session_installs_the_locked_coverage():
    """coverage-combine installs coverage at uv.lock's version, which the lock does pin."""
    import noxfile

    lock = (PROJECT_ROOT / 'uv.lock').read_text(encoding='utf-8')

    version = noxfile.locked_version(package='coverage', lock=lock)

    assert re.fullmatch(r'\d+\.\d+(\.\d+)?', version)


def test_a_package_the_lock_does_not_pin_is_refused():
    """A misspelled name is an error, never an unpinned install."""
    import noxfile

    with pytest.raises(ValueError, match="no package named 'coverge'"):
        noxfile.locked_version(
            package='coverge', lock='[[package]]\nname = "coverage"\nversion = "7.0"\n'
        )


def test_the_macos_job_is_not_split_and_holds_its_own_coverage():
    """The macOS job runs 3.15's suite whole, under the hour, with pytest's own 100% rule."""
    job = circleci_job_texts()['test-python-3-15-macos']

    assert 'parallelism:' not in job
    assert 'GLITCHYGAMES_TEST_SPLIT' not in job
    assert 'save-coverage-share' not in job


def test_random_order_is_off_unless_asked_for():
    """pytest-randomly is blocked in addopts: every ordinary run keeps the files' order.

    Only nox -s test-random and the test session's GLITCHYGAMES_TEST_ORDER (CircleCI's test
    jobs roll it) turn it back on.
    """
    pyproject = tomllib.loads((PROJECT_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    addopts = shlex.split(pyproject['tool']['pytest']['ini_options']['addopts'])

    assert '-p' in addopts
    assert addopts[addopts.index('-p') + 1] == 'no:randomly'


def test_every_run_with_workers_balances_them_by_work_stealing():
    """The addopts give xdist --dist worksteal, read by every run, and nothing chooses another.

    One definition: every pytest in the checkout reads addopts (nox's test and test-random
    sessions, compare-drivers, CircleCI's jobs through PYTEST_WORKERS, the native driver's child
    run), so a worker that runs out of tests takes queued ones from a busy worker. Under the
    default (--dist load) #287's Windows job (5210) left one worker 525 s of work at the end
    and another 7 s.
    """
    pyproject = tomllib.loads((PROJECT_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    addopts = shlex.split(pyproject['tool']['pytest']['ini_options']['addopts'])

    assert addopts[addopts.index('--dist') + 1] == 'worksteal'
    assert addopts.count('--dist') == 1
    for path in (PROJECT_ROOT / 'noxfile.py', CIRCLECI_CONFIG_PATH):
        text = path.read_text(encoding='utf-8')
        assert not re.search(r"--dist\b(?!path)|'--dist'|\bloadfile\b|\bloadscope\b", text), path


def test_work_stealing_is_accepted_by_a_run_without_workers(pytester):
    """-n 0 (CircleCI's Linux jobs, every wall_clock run) with addopts' --dist runs in process."""
    pytester.makepyfile(test_two='def test_one():\n    pass\n\ndef test_two():\n    pass\n')

    result = pytester.runpytest_inprocess('-p', 'no:randomly', '-n', '0', '--dist', 'worksteal')

    result.assert_outcomes(passed=2)


# How each shuffled run gets its Python: a throwaway environment from uv.lock, never the
# project's .venv, so the push tests every Python whichever one the .venv was synced on
SHUFFLED_RUN_ENVIRONMENT = (
    'uv',
    'run',
    '--isolated',
    '--frozen',
    '--all-extras',
    '--all-groups',
    '--all-packages',
    '--python',
)


def test_the_shuffled_run_reorders_only_on_the_dummy_drivers():
    """Nox -s test-random -- SEED: pytest-randomly back on, that seed, no reseeding, no coverage."""
    import noxfile

    session = RecordingSession(posargs=['12345'])
    noxfile.test_random(session)

    for command in session.commands:
        python_at = len(SHUFFLED_RUN_ENVIRONMENT)
        assert command[:python_at] == SHUFFLED_RUN_ENVIRONMENT
        assert command[python_at + 1 : python_at + 5] == (
            'pytest',
            '-p',
            'randomly',
            '--randomly-dont-reset-seed',
        )
        assert '--randomly-seed=12345' in command
        assert '--no-cov' in command
        assert session.environments[command] == {
            'SDL_VIDEODRIVER': 'dummy',
            'SDL_AUDIODRIVER': 'dummy',
        }


def test_the_shuffled_run_tests_only_the_development_python():
    """One run, on 3.15, the development version: the newest of the Pythons the suite supports.

    The owner, 2026-11-18: "For the pre-commit checks only run python 3.15", "so that we can push
    more quickly. The pipeline can catch 3.14 breakage" (nox -s test and CircleCI still run both).
    """
    import noxfile

    session = RecordingSession(posargs=['12345'])
    noxfile.test_random(session)

    python_at = len(SHUFFLED_RUN_ENVIRONMENT)
    pythons = [command[python_at] for command in session.commands]
    # The parallel run and the wall_clock tests' serial run, both on 3.15
    assert pythons == ['3.15', '3.15']
    assert noxfile.TEST_PYTHONS[-1] == noxfile.SHUFFLED_RUN_PYTHON
    assert '--randomly-seed=12345' in session.commands[0]


def test_a_shuffled_run_picks_a_new_seed_each_time():
    """Without a seed given, each run draws one, in pytest-randomly's range."""
    import noxfile

    seeds = set()
    for _ in range(3):
        session = RecordingSession(posargs=[])
        noxfile.test_random(session)
        run_seeds = {
            argument.removeprefix('--randomly-seed=')
            for command in session.commands
            for argument in command
            if argument.startswith('--randomly-seed=')
        }
        (seed,) = run_seeds
        seeds.add(int(seed))

    assert all(0 <= seed < noxfile.RANDOM_ORDER_SEED_LIMIT for seed in seeds)
    assert len(seeds) > 1


def test_a_failed_shuffled_run_names_its_seed_and_how_to_replay_it(mocker):
    """The failure says which order failed and gives the one-process command that replays it."""
    import noxfile
    from nox.command import CommandFailed

    session = RecordingSession(posargs=['777'])
    mocker.patch.object(session, 'run', side_effect=CommandFailed('pytest failed'))

    with pytest.raises(RuntimeError) as failure:
        noxfile.test_random(session)

    message = str(failure.value)
    assert 'seed 777' in message
    assert 'Python 3.15' in message
    assert '--python 3.15 pytest' in message
    assert '--randomly-seed=777 -n 0' in message
    assert 'nox -s test-random -- 777' in message


# pre-commit's own run of a hook set in a throwaway repository: a minute is far more than it needs
PRE_COMMIT_TIMEOUT_SECONDS = 60.0
# The hook stages .pre-commit-config.yaml installs (default_install_hook_types): pre-push alone
# since the owner stopped committing replay-ledger rows (2026-11-22), which was the commit stage
HOOK_STAGES = ('pre-push',)


def run_project_hooks_on(*, tmp_path: Path, changed_paths: list[str], stage: str) -> dict[str, str]:
    """Run this project's hooks, as pre-commit decides, on a change to ``changed_paths``.

    The configuration is the project's own with each hook's command swapped for one that does
    nothing (a pygrep that never matches, which pre-commit runs in its own interpreter on every
    platform), so what is checked is pre-commit's choice of which hooks run.

    Returns:
        Each hook's name with pre-commit's verdict for it ("Passed": it ran; "Skipped").

    """
    configuration = yaml.safe_load(
        (PROJECT_ROOT / '.pre-commit-config.yaml').read_text(encoding='utf-8')
    )
    for repository_entry in configuration['repos']:
        for hook in repository_entry['hooks']:
            hook['language'] = 'pygrep'
            hook['entry'] = 'a^'
    repository = tmp_path / 'repository'
    repository.mkdir()
    (repository / '.pre-commit-config.yaml').write_text(yaml.safe_dump(configuration))
    for changed_path in changed_paths:
        (repository / changed_path).parent.mkdir(parents=True, exist_ok=True)
        (repository / changed_path).write_text('changed\n', encoding='utf-8')
    git(repository=repository, arguments=['init', '--quiet'])
    git(repository=repository, arguments=['add', '.'])
    # Without the outer hook run's own controls: the suite runs inside the pre-push hook, and a
    # push's SKIP (or another PRE_COMMIT_ variable) would steer this pre-commit run too
    environment = {
        name: value
        for name, value in environment_without_git_variables().items()
        if name != 'SKIP' and not name.startswith('PRE_COMMIT_')
    } | {'PRE_COMMIT_HOME': str(tmp_path / 'pre-commit-home')}

    completed = run_command(
        command=[
            sys.executable,
            '-m',
            'pre_commit',
            'run',
            '--color',
            'never',
            '--hook-stage',
            stage,
            '--files',
            *changed_paths,
        ],
        environment=environment,
        timeout_seconds=PRE_COMMIT_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
        working_directory=repository,
    )

    assert completed.returncode == 0, completed.stdout
    hook_names = [
        hook.get('name', hook['id'])
        for repository_entry in configuration['repos']
        for hook in repository_entry['hooks']
        if stage in hook.get('stages', HOOK_STAGES)
    ]
    verdicts = {}
    for line in (completed.stdout or '').splitlines():
        for name in hook_names:
            if line.startswith(name):
                verdicts[name] = re.findall(r'(Passed|Skipped|Failed)$', line.rstrip())[0]
    assert sorted(verdicts) == sorted(hook_names), completed.stdout
    return verdicts


@pytest.mark.parametrize('stage', HOOK_STAGES)
def test_a_markdown_only_change_runs_no_hook(tmp_path, stage):
    """A commit or push that changes only Markdown files skips every check and measurement.

    The owner (2026-11-14): skip running checks if only markdown files change; "since we only
    have a markdown change, we don't need to run any code measurements or checks". Markdown
    anywhere: the root's (BUGS.md), the docs' and the plans'. CI still lints the docs and runs
    the suite on every pull request.
    """
    verdicts = run_project_hooks_on(
        tmp_path=tmp_path,
        changed_paths=['BUGS.md', 'docs/architecture/sound.md', 'plans/a-plan.md'],
        stage=stage,
    )

    assert set(verdicts.values()) == {'Skipped'}, verdicts


@pytest.mark.parametrize('stage', HOOK_STAGES)
def test_any_other_change_runs_every_hook(tmp_path, stage):
    """One file that is not Markdown, beside Markdown, and every hook of the stage runs."""
    verdicts = run_project_hooks_on(
        tmp_path=tmp_path, changed_paths=['BUGS.md', 'src/module.py'], stage=stage
    )

    assert set(verdicts.values()) == {'Passed'}, verdicts


def test_the_outer_runs_skip_list_never_reaches_the_hooks_under_test(tmp_path, monkeypatch):
    """A push's own SKIP (SKIP=raspberry-pi-replay-metrics git push) leaves these tests' run alone.

    The suite runs inside the pre-push hook, so this process has the push's environment: once,
    the inner pre-commit took its SKIP and skipped the Pi hook, failing the test above in the
    gate only (2026-11-14). Here every hook's id is in SKIP, and every hook still runs.
    """
    configuration = yaml.safe_load(
        (PROJECT_ROOT / '.pre-commit-config.yaml').read_text(encoding='utf-8')
    )
    hook_ids = [
        hook['id']
        for repository_entry in configuration['repos']
        for hook in repository_entry['hooks']
    ]
    monkeypatch.setenv('SKIP', ','.join(hook_ids))

    verdicts = run_project_hooks_on(
        tmp_path=tmp_path, changed_paths=['src/module.py'], stage='pre-push'
    )

    assert set(verdicts.values()) == {'Passed'}, verdicts


def test_the_pre_push_hooks_run_the_shuffled_suite():
    """Every push shuffles the suite once (the hook, not CI: CI keeps the files' order)."""
    hooks = (PROJECT_ROOT / '.pre-commit-config.yaml').read_text(encoding='utf-8')

    assert 'entry: uv run --all-extras --all-groups --all-packages nox -s test-random' in hooks


def test_every_hook_installs_every_extra_group_and_package():
    """Whichever hook runs first in a new worktree fills its .venv with all uv.lock pins.

    basedpyright reads the repository's .venv whatever environment nox gives it, so a .venv
    with only the dev extra failed static-analysis on mkdocs and cookiecutter imports
    (bugs/2026-11-14-pre-push-fails-in-worktree-synced-with-dev-extra-only.md).
    """
    configuration = yaml.safe_load(
        (PROJECT_ROOT / '.pre-commit-config.yaml').read_text(encoding='utf-8')
    )
    entries = {
        hook['id']: shlex.split(hook['entry'])
        for repository in configuration['repos']
        for hook in repository['hooks']
    }
    uv_runs = {name: words for name, words in entries.items() if words[:2] == ['uv', 'run']}
    every = {'--all-extras', '--all-groups', '--all-packages'}

    assert uv_runs
    missing = {name: every - set(words) for name, words in uv_runs.items()}
    assert {name: flags for name, flags in missing.items() if flags} == {}
    assert [name for name, words in uv_runs.items() if '--extra' in words] == []


@pytest.mark.parametrize(
    ('posargs', 'expected'),
    [
        ([], {}),
        (
            [
                '--drivers',
                'native',
                '--fail-on-difference',
                '--workers',
                'auto',
                '--skip-when-frames-cannot-change',
            ],
            {
                'drivers': 'native',
                'fail_on_difference': True,
                'workers': 'auto',
                'skip_when_frames_cannot_change': True,
            },
        ),
        (
            ['--drivers=dummy,cocoa', '--sound', '--workers=8', 'tests/scenes'],
            {
                'drivers': 'dummy,cocoa',
                'sound': True,
                'workers': '8',
                'selection': ('tests/scenes',),
            },
        ),
    ],
    ids=['nothing', 'the-pre-push-hooks', 'by-hand'],
)
def test_compare_drivers_reads_its_options(posargs, expected):
    """--drivers, --sound, --fail-on-difference and --workers are taken out; the rest selects.

    Without --workers each run has four (the by-hand matrix keeps the machine usable).
    """
    import noxfile

    defaults = {
        'drivers': None,
        'sound': False,
        'fail_on_difference': False,
        'workers': '4',
        'skip_when_frames_cannot_change': False,
        'selection': (),
    }

    options = noxfile._compare_drivers_arguments(RecordingSession(posargs=posargs))

    assert options == noxfile._CompareDriversOptions(**{**defaults, **expected})


@pytest.mark.parametrize('posargs', [['--workers', 'zero'], ['--workers=0'], ['--workers']])
def test_compare_drivers_refuses_a_worker_count_that_is_not_one(posargs):
    """--workers takes a whole number of at least 1, or auto (every core, as xdist counts)."""
    import noxfile

    with pytest.raises(RuntimeError, match='--workers'):
        noxfile._compare_drivers_arguments(RecordingSession(posargs=posargs))


@pytest.mark.parametrize('workers', ['4', 'auto'])
def test_each_comparison_run_has_the_workers_asked_for(workers):
    """The worker count reaches each run's pytest as ``-n``."""
    import noxfile

    session = RecordingSession(posargs=[])

    noxfile._run_fingerprinted_tests(
        session,
        configuration={'name': 'dummy', 'environment': {}, 'runs_in_linux_container': False},
        directory=Path('runs/dummy-1'),
        arguments=[],
        settings=noxfile._RunSettings(workers=workers),
    )

    (command,) = session.commands
    assert command[command.index('-n') + 1] == workers


def test_the_pre_push_comparison_runs_on_every_core():
    """The hook's runs use every core (2026-11-13: 10 minutes instead of 19 at four workers).

    A push is waited for; the by-hand matrix keeps four workers so the machine stays usable.
    """
    hooks = (PROJECT_ROOT / '.pre-commit-config.yaml').read_text(encoding='utf-8')

    assert (
        'entry: uv run --all-extras --all-groups --all-packages nox -s compare-drivers -- '
        '--drivers native '
        '--fail-on-difference --workers auto --skip-when-frames-cannot-change'
    ) in hooks


@pytest.mark.parametrize(
    ('path', 'cannot_change_frames'),
    [
        ('plans/2026-11-13-zensical-migration.md', True),
        ('docs/quality/driver_comparison.md', True),
        ('quality/replay-ledger/abc-row.json', True),
        ('.circleci/config.yml', True),
        ('.circleci/continue_config.yml', True),
        ('.github/workflows/lint.yml', True),
        ('BUGS.md', True),
        ('bugs/2026-11-14-type-gate-never-reads-the-tests.md', True),
        ('CLAUDE.md', True),
        ('src/glitchygames/scenes/__init__.py', False),
        ('tests/test_process.py', False),
        ('scripts/golden_inputs.py', False),
        ('src/games/paddleslap/README.md', False),
        ('uv.lock', False),
        ('pyproject.toml', False),
        ('noxfile.py', False),
        ('conftest.py', False),
    ],
)
def test_only_plans_docs_ledger_rows_ci_bug_files_and_root_markdown_cannot_change_a_frame(
    path, cannot_change_frames
):
    """An allowlist: a path not on it (a new directory included) is compared.

    A frame is what a test presents: the engine, games, apps, demos, tests, the scripts tests
    import, the dependencies and the suite's configuration can change one. Docs a test checks
    (zensical.yml's nav) can fail a test, which test-random catches; never a frame.
    """
    import noxfile

    assert noxfile._path_cannot_change_frames(path=path) is cannot_change_frames


@pytest.mark.parametrize(
    ('from_reference', 'expected_base'),
    [('a' * 40, 'a' * 40), ('0' * 40, 'merge-base-commit')],
    ids=['an-updated-branch', 'a-new-branch'],
)
def test_a_push_names_the_paths_it_changes(mocker, monkeypatch, from_reference, expected_base):
    """The range pre-commit gives a pre-push hook; a new branch's starts where it left main."""
    import noxfile

    monkeypatch.setenv('PRE_COMMIT_FROM_REF', from_reference)
    monkeypatch.setenv('PRE_COMMIT_TO_REF', 'b' * 40)
    host_git = mocker.patch.object(
        noxfile,
        '_host_git',
        side_effect=lambda session, *arguments, **options: (
            'merge-base-commit\n' if arguments[0] == 'merge-base' else 'docs/a.md\nplans/b.md\n'
        ),
    )

    paths = noxfile._pushed_paths(RecordingSession(posargs=[]))

    assert paths == ['docs/a.md', 'plans/b.md']
    assert host_git.call_args_list[-1].args[1:] == ('diff', '--name-only', expected_base, 'b' * 40)


def test_outside_a_push_no_paths_are_known(monkeypatch):
    """By hand (no pre-commit range) the comparison always runs."""
    import noxfile

    monkeypatch.delenv('PRE_COMMIT_FROM_REF', raising=False)
    monkeypatch.delenv('PRE_COMMIT_TO_REF', raising=False)

    assert noxfile._pushed_paths(RecordingSession(posargs=[])) is None


def test_git_failing_to_name_the_paths_means_the_comparison_runs(mocker, monkeypatch):
    """A push whose range git cannot read (no origin/main here) is compared, never skipped."""
    import noxfile
    from nox.command import CommandFailed

    monkeypatch.setenv('PRE_COMMIT_FROM_REF', '0' * 40)
    monkeypatch.setenv('PRE_COMMIT_TO_REF', 'b' * 40)
    mocker.patch.object(noxfile, '_host_git', side_effect=CommandFailed('no origin/main'))

    assert noxfile._pushed_paths(RecordingSession(posargs=[])) is None


@pytest.mark.parametrize(
    ('paths', 'skipped'),
    [
        (['docs/a.md', 'BUGS.md'], True),
        (['docs/a.md', 'src/glitchygames/process.py'], False),
        ([], True),
        (None, False),
    ],
    ids=['docs-only', 'code-too', 'nothing-changed', 'range-unknown'],
)
def test_the_comparison_is_skipped_only_when_no_pushed_path_can_change_a_frame(
    mocker, paths, skipped
):
    """Skipped for a push of plans or docs alone (#187 ran 19 minutes for none); never unknown."""
    import noxfile

    mocker.patch.object(noxfile, '_pushed_paths', return_value=paths)

    reason = noxfile._why_no_frame_can_change(RecordingSession(posargs=[]))

    assert (reason is not None) is skipped


@pytest.mark.parametrize(
    ('posargs', 'differing', 'fails'),
    [
        (['--fail-on-difference'], ['tests/a.py::test_one'], True),
        (['--fail-on-difference'], [], False),
        ([], ['tests/a.py::test_one'], False),
    ],
    ids=['a-difference-fails', 'agreement-passes', 'by-hand-only-reports'],
)
def test_compare_drivers_fails_on_a_difference_only_when_asked(
    mocker, tmp_path, posargs, differing, fails
):
    """The failure comes after the comparison completed: its report is kept, not set aside."""
    import noxfile

    # Every folder and the lock under tmp_path: never the real test-results
    for name in ('_COMPARE_DRIVERS_OUTPUT', '_COMPARE_DRIVERS_PREVIOUS', '_COMPARE_DRIVERS_FAILED'):
        mocker.patch.object(noxfile, name, tmp_path / name.lower())
    mocker.patch.object(noxfile, '_COMPARE_DRIVERS_LOCK', tmp_path / 'compare-drivers.lock')
    mocker.patch.object(noxfile, '_set_aside_previous_comparison')
    restore = mocker.patch.object(noxfile, '_restore_previous_comparison')
    mocker.patch.object(
        noxfile,
        '_compare_driver_configurations',
        return_value=noxfile._DifferingTests(frames=differing, audio=[]),
    )
    session = RecordingSession(posargs=posargs)

    if fails:
        with pytest.raises(
            RuntimeError, match=r'1 test\(s\) presented different frames'
        ) as failure:
            noxfile.compare_drivers(session)
        assert 'tests/a.py::test_one' in str(failure.value)
        assert 'matrix.md' in str(failure.value)
    else:
        noxfile.compare_drivers(session)
    restore.assert_not_called()


def test_a_second_compare_drivers_is_refused_while_one_runs(mocker, tmp_path):
    """Two at once deleted each other's runs: the second refuses, the first goes on."""
    import noxfile
    from filelock import FileLock

    lock_path = tmp_path / 'compare-drivers.lock'
    compare = mocker.patch.object(
        noxfile,
        '_compare_driver_configurations',
        return_value=noxfile._DifferingTests(frames=[], audio=[]),
    )
    mocker.patch.object(noxfile, '_set_aside_previous_comparison')
    mocker.patch.object(noxfile, '_COMPARE_DRIVERS_LOCK', lock_path)
    mocker.patch.object(noxfile, '_COMPARE_DRIVERS_PREVIOUS', tmp_path / 'previous')

    with FileLock(lock_path), pytest.raises(RuntimeError, match='Another compare-drivers'):
        noxfile.compare_drivers(RecordingSession(posargs=[]))
    compare.assert_not_called()

    # Released by the one that held it: the next comparison runs
    noxfile.compare_drivers(RecordingSession(posargs=[]))
    compare.assert_called_once()


def test_the_pre_push_hooks_compare_the_native_driver_with_dummy():
    """Every push compares the drivers here, and a difference stops it."""
    hooks = (PROJECT_ROOT / '.pre-commit-config.yaml').read_text(encoding='utf-8')

    assert (
        'entry: uv run --all-extras --all-groups --all-packages nox -s compare-drivers -- '
        '--drivers native --fail-on-difference' in hooks
    )


def test_no_type_checking_environment_turns_off_call_checks():
    """Wrong arguments in a test's call into game code are type errors (BUGS.md #250).

    The test environments had reportCallIssue off, so a call with a keyword the function had
    lost (input_mode=, after --axis-deadzone) passed basedpyright and reached CI as a collection
    error. A deliberate wrong call takes a narrow ``# pyright: ignore[reportCallIssue]``.
    """
    config = (PROJECT_ROOT / 'pyrightconfig.json').read_text(encoding='utf-8')

    assert '"reportCallIssue": true' in config
    assert '"reportCallIssue": false' not in config


def test_docs_deploy_publishes_only_from_main():
    """A deploy from a branch would publish its unlanded rows: refused before anything is pushed.

    The check (HEAD is on origin/main) runs before the build; a build only (--build-only) is
    not checked.
    """
    commands = docs_deploy_commands(posargs=['--no-measure'])
    on_main = ('git', 'merge-base', '--is-ancestor', 'HEAD', 'origin/main')

    assert on_main in commands
    assert commands.index(on_main) < commands.index((
        'mkdocs',
        'gh-deploy',
        '--strict',
        '--config-file',
        'zensical.yml',
    ))
    assert on_main not in docs_deploy_commands(posargs=['--build-only'])


def test_the_performance_session_collects_only_the_benchmark_paths():
    """The session gives pytest exactly ``_BENCHMARK_PATHS``, so it collects only benchmarks.

    Benchmarks live in several packages' tests; tests/test_benchmark_paths.py fails if one is
    added outside these paths.
    """
    import noxfile

    session = RecordingSession(posargs=[])
    noxfile.performance_test(session)

    pytest_command = next(command for command in session.commands if command[0] == 'pytest')
    assert '--benchmark-only' in pytest_command
    assert pytest_command[-len(noxfile._BENCHMARK_PATHS) :] == tuple(noxfile._BENCHMARK_PATHS)


def test_the_wheel_build_builds_every_workspace_package(mocker):
    """The wheel build covers the engine and every workspace member, not the root project alone."""
    import noxfile

    session = mocker.Mock()
    noxfile._build_wheel(session)

    session.run.assert_called_once_with(
        'uv', 'build', '--all-packages', '--wheel', '--out-dir', 'dist', external=True
    )


def jobs_that_run_tests(*, platform_marker: str) -> dict[str, str]:
    """Return the jobs on one platform that run a test session, each's text by its name.

    A job on the same image that runs no tests (coverage-combine-linux, -windows) is left out:
    the test jobs' rules (memory limit, system packages, the short uv cache) are about the suite.

    Returns:
        The jobs' texts by name.

    """
    return {
        name: job
        for name, job in circleci_job_texts().items()
        if platform_marker in job and any(command in job for command in TEST_SESSION_COMMANDS)
    }


def circleci_job_texts() -> dict[str, str]:
    """Return each CircleCI job's text by its name, from its name line to the next job's.

    Returns:
        The jobs, in the file's order.

    """
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    jobs = configuration[configuration.index('\njobs:\n') : configuration.index('\nworkflows:\n')]
    starts = list(re.finditer(r'^  (?P<name>[a-z0-9-]+):(?: &\S+)?$', jobs, flags=re.MULTILINE))
    return {
        start['name']: jobs[start.start() : end]
        for start, end in zip(
            starts, [*(match.start() for match in starts[1:]), len(jobs)], strict=True
        )
    }


def workflow_jobs() -> list[str]:
    """Return the jobs the build-and-test workflow runs (commented-out ones left out).

    Returns:
        Their names, in order.

    """
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    workflow = configuration[configuration.index('\n  build-and-test:\n    jobs:\n') :]
    return re.findall(r'^      - (?P<name>[a-z0-9-]+):?$', workflow, flags=re.MULTILINE)


def raspberry_pi_job() -> str:
    """Return the Raspberry Pi 4 job's text in the CircleCI configuration.

    The Pi 5's job is this one merged with its own resource class
    (``test_the_raspberry_pi_5_job_is_the_raspberry_pi_4_job_on_its_own_runner``).

    Returns:
        From its name to the Pi 5 job's comment.

    """
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    job = configuration[configuration.index('\n  build-and-test-raspberry-pi-4-4gb-ubuntu:') :]
    return job[: job.index('\n  # The same job on a Raspberry Pi 5')]


@pytest.mark.parametrize(
    'host',
    [
        'raspberry-pi-4-4gb-ubuntu',
        'raspberry-pi-5-8gb-ubuntu',
        'raspberry-pi-5-16gb-ubuntu',
        'raspberry-pi-5-16gb-raspberry-pi-os',
    ],
)
def test_no_workflow_runs_a_raspberry_pis_job(host):
    """The Pis measure replays when the owner pushes, and take no CI jobs."""
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    workflow = configuration[configuration.index('\nworkflows:\n') :]

    assert f'\n      # - build-and-test-{host}\n' in workflow
    assert f'\n      - build-and-test-{host}\n' not in workflow
    assert f'            - build-and-test-{host}\n' not in workflow


def test_the_raspberry_pi_job_runs_the_tests_serially_on_its_runner():
    """The job runs on the self-hosted machine runner, with no xdist workers to reach its swap."""
    job = raspberry_pi_job()

    assert '    machine: true\n    resource_class: terrysimons/raspberry-pi-4-4gb-ubuntu\n' in job
    assert '      PYTEST_WORKERS: "0"\n' in job
    assert job.index('      - install-deps-posix') < job.index('      - nox-test:\n')


def test_the_raspberry_pi_job_allows_30_minutes_of_silence_per_step():
    """A cold install compiles without printing, past CircleCI's default 10 minutes."""
    job = raspberry_pi_job()

    assert re.search(
        r'- install-deps-posix:\n          pythons: .+\n          no_output_timeout: 30m\n', job
    )
    assert '- nox-timer-report:\n          no_output_timeout: 30m\n' in job
    assert job.count('          no_output_timeout: 30m\n') == 4


def test_the_raspberry_pi_job_never_runs_the_benchmarks():
    """performance-test runs test_logging_cost.py, whose heavy logs wear the Pi's SD card."""
    steps = raspberry_pi_job().split('    steps:\n')[1]

    assert 'performance' not in steps
    assert 'benchmark' not in steps


def test_the_raspberry_pi_job_needs_no_sudo_and_no_circleci_cache():
    """The runner's user has no sudo, and the uv cache stays on the host, pruned every run."""
    job = raspberry_pi_job()

    assert 'sudo apt-get' not in job
    assert '_cache' not in job
    assert 'uv-cache' not in job
    prune = job[job.index('name: "Prune the uv cache"') :]
    assert 'when: always\n' in prune
    assert 'uv cache prune\n' in prune
    assert '--ci' not in prune


def test_the_raspberry_pi_job_reports_throttling_even_when_the_tests_fail():
    """A failed or slow run on a Pi with no added cooling says whether heat was the reason."""
    job = raspberry_pi_job()
    throttling = job[job.index('name: "Throttling and temperature') :]

    # After the last Python's run, so heat from either run is reported
    assert job.rindex('      - nox-test:\n') < job.index('name: "Throttling and temperature')
    assert 'when: always\n' in throttling
    assert 'vcgencmd get_throttled\n' in throttling


@pytest.mark.parametrize(
    ('system', 'machine', 'has_no_wheel'),
    [
        ('linux', 'aarch64', True),
        ('linux', 'x86_64', False),
        ('darwin', 'arm64', False),
        ('win32', 'AMD64', False),
    ],
)
def test_the_taplo_sessions_skip_only_linux_arm(mocker, system, machine, has_no_wheel):
    """pyproject.toml's marker leaves taplo out on Linux ARM alone, so only there do they skip."""
    import noxfile

    mocker.patch.object(noxfile.sys, 'platform', system)
    mocker.patch.object(noxfile.platform, 'machine', return_value=machine)
    session = mocker.Mock()

    noxfile._format_toml(session)
    noxfile._lint_toml(session)

    assert session.run.call_count == (0 if has_no_wheel else 2)
    assert session.log.call_count == (2 if has_no_wheel else 0)


def test_taplo_leaves_the_worktrees_nested_in_this_checkout_alone():
    """Claude Code's worktrees (.claude/worktrees/<name>/) are other checkouts inside this one.

    Formatted from here, their TOML files were rewritten mid-task: their CRLF sprite fixtures
    lost their line endings, which the fixture exclusions (this checkout's paths) don't cover
    (BUGS.md #271).
    """
    configuration = tomllib.loads((PROJECT_ROOT / '.taplo.toml').read_text(encoding='utf-8'))

    assert '.claude/**' in configuration['exclude']


# Every Linux job's memory guard limit, in MiB (tests/memory_guard.py; the owner, 2026-11-23)
LINUX_MEMORY_LIMIT_MB = 1500


def test_the_linux_and_raspberry_pi_jobs_set_the_memory_limit():
    """The Linux job (2 GB, serial) stops a run past 1500 MiB, naming the test (memory_guard.py).

    So does the Raspberry Pi's (real hardware, 3.7 GB with its desktop): one limit for every
    Linux job (the owner, 2026-11-19). 1500 from 2026-11-23 (the owner): with every machine
    collecting the whole suite (#286), the Linux machines peaked at 1335, 1226 and 1240 MiB
    (job 5115), too near 1400 for a slab that swings about 120 MiB a run. The macOS and Windows
    jobs have the memory, and the plugin needs Linux's ``/proc/self/statm`` anyway. The Linux
    job's resource class and worker count stay as they were.
    """
    linux_jobs = jobs_that_run_tests(platform_marker=LINUX_IMAGE_MARKER)

    # Every test job on the Linux image, so a new one can't miss them
    assert set(linux_jobs) == {'test-python-3-15-linux'}
    limit = f'      GLITCHYGAMES_TEST_RSS_LIMIT_MB: "{LINUX_MEMORY_LIMIT_MB}"\n'
    assert limit in raspberry_pi_job()
    for name, job in linux_jobs.items():
        assert limit in job, name
        assert '    resource_class: small\n' in job, name
        assert '      PYTEST_WORKERS: "0"\n' in job, name


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

    Read from .circleci/continue_config.yml, so a change to the job changes the session too.
    """
    import noxfile

    monkeypatch.setattr(noxfile, '_LINUX_CI_RESULTS', tmp_path / 'linux-ci')
    session = LinuxCiSession(tmp_path=tmp_path)

    noxfile.test_linux_ci(session)

    docker_run = next(command for command in session.commands if command[:2] == ('docker', 'run'))
    python_version = pipeline_parameter_default(name='PYTHON_VERSION')
    assert f'cimg/python:{python_version}' in docker_run
    assert {'--memory=2g', '--memory-swap=2g', '--cpus=1', '--platform=linux/amd64'} <= set(
        docker_run
    )
    environment = {
        docker_run[index + 1] for index, argument in enumerate(docker_run) if argument == '--env'
    }
    assert {
        'PYTEST_WORKERS=0',
        f'GLITCHYGAMES_TEST_RSS_LIMIT_MB={LINUX_MEMORY_LIMIT_MB}',
        'CI=true',
        'CIRCLECI=true',
    } <= environment
    # The job is split across CircleCI's machines; a local run is one machine, the whole suite
    assert not any(variable.startswith('GLITCHYGAMES_TEST_SPLIT=') for variable in environment)
    script = docker_run[-1]
    uv_version = pipeline_parameter_default(name='UV_VERSION')
    nox_version = pipeline_parameter_default(name='NOX_VERSION')
    assert f'https://astral.sh/uv/{uv_version}/install.sh' in script
    assert f'\nuv python install "{python_version}"\n' in script
    # The job's own apt packages, read from it, so the two can't drift
    job_packages = noxfile._linux_ci_job_packages(
        configuration=CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    )
    assert f'sudo apt-get install -y -qq {shlex.join(job_packages)} > /dev/null' in script
    nox_installed = script.index(f'uv tool install "nox[uv]=={nox_version}"')
    runs = [script.index(f'nox -s test-{python} || status=1') for python in noxfile.TEST_PYTHONS]
    assert nox_installed < runs[0]
    assert runs == sorted(runs)
    for python in noxfile.TEST_PYTHONS:
        assert f'cp -r test-results/. /results/test-{python}/' in script
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
        From its name to the next job's (the Linux one).

    """
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    return configuration[
        configuration.index('\n  test-python-3-15-macos:\n') : configuration.index(
            '\n  test-python-3-15-linux:\n'
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


# The Linux job that runs every check whose answer is the same on every OS (format, lint with
# the docs build, the type checkers, the security scan), beside the test jobs
CHECKS_JOB = 'checks-linux'
LINUX_IMAGE = '    docker:\n      - image: cimg/python:<< pipeline.parameters.PYTHON_VERSION >>\n'
# The release architectures the Linux job's syft and grype are pinned for: CircleCI's Docker
# executors (x86_64) and Linux on ARM
SUPPLY_CHAIN_ARCHITECTURES = ('AMD64', 'ARM64')


def nox_steps_of(job: str) -> list[str]:
    """Return a job's nox steps (the commands named ``nox-...``), in order.

    Returns:
        The steps' command names.

    """
    return re.findall(r'^      - (nox-[a-z-]+):?$', job, flags=re.MULTILINE)


def test_the_macos_job_runs_only_what_is_there_for_a_mac():
    """The macOS job keeps the tests, the timer report and the build alone.

    The owner, 2026-11-22 (through the coordinator): every non-test check ran on the one macOS
    machine, at 200 credits a minute, one macOS job at a time (job 5021: 1,601 s, 558 of them
    lint). The timer report explains the macOS tests' timings and the build is the macOS
    binary. The benchmarks left CI (the owner, 2026-11-23: "Don't run the macOS benchmarks"):
    ``nox -s performance-test`` runs by hand.
    """
    job = macos_job()

    assert nox_steps_of(job) == [
        'nox-timer-report',
        'nox-test',
        'nox-build',
    ]
    assert 'install-supply-chain-tools' not in job


def test_no_ci_job_runs_the_benchmarks():
    """The benchmarks run by hand only (the owner, 2026-11-23: "Don't run the macOS benchmarks")."""
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')

    assert not re.search(r'^\s+nox -s performance-test\b', configuration, flags=re.MULTILINE)


def test_the_checks_run_on_a_large_linux_container_beside_the_tests():
    """Format, lint (the docs build with it), the type checkers and the security scan: Linux.

    large (4 CPUs, 8 GB): the strict docs build was killed for memory at 4 GB (deploy-docs).
    Beside the tests: it waits for no job, and runs only where the tests do (test-scope all).
    """
    job = circleci_job_definition(name=CHECKS_JOB)

    assert job.startswith(LINUX_IMAGE)
    assert '    resource_class: large\n' in job
    assert nox_steps_of(job) == [
        'nox-format',
        'nox-lint',
        'nox-static-analysis',
        'nox-security-scan',
    ]
    assert job.index('      - install-supply-chain-tools-linux\n') < job.index(
        '      - nox-security-scan\n'
    )
    assert workflow_entries()[CHECKS_JOB] == {
        'job': CHECKS_JOB,
        'filters': TEST_SCOPE_FILTER.format(scope='all'),
    }


def test_the_lint_step_allows_30_minutes_of_silence():
    """The strict docs build inside nox -s lint can go quiet for minutes while graphs generate.

    checks-linux (#285 moved the docs build there) was killed on #261's job 5089: "Too long with
    no output (exceeded 10m0s)" during mkdocs build --strict.
    """
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    step = configuration.split('\n  nox-lint:\n', 1)[1].split('\n\n', 1)[0]

    assert '          no_output_timeout: 30m\n' in step
    assert step.index('no_output_timeout') < step.index('nox -s lint')


def test_ci_builds_the_docs_once_outside_their_deploy():
    """One strict docs build per pipeline: lint's (job 5021 built them twice, 553 s and 124 s).

    nox -s lint builds the docs (the local pre-push lint hook keeps them), so no job runs
    lint-docs beside it.
    """
    import noxfile

    jobs = circleci_job_texts()
    docs_builds = [
        name
        for name in workflow_jobs()
        if name != 'deploy-docs'
        for step in nox_steps_of(jobs[name])
        if step in {'nox-lint', 'nox-lint-docs'}
    ]

    assert docs_builds == [CHECKS_JOB]
    assert '_lint_docs(session)' in inspect.getsource(noxfile.lint_all)
    assert 'nox-lint-docs' not in CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')


@pytest.mark.parametrize('tool', ['SYFT', 'GRYPE'])
def test_circleci_pins_syft_and_grype_with_checksums(tool):
    """Each is pinned to an exact version and the SHA-256 of each Linux release tarball."""
    assert re.fullmatch(r'\d+\.\d+\.\d+', pipeline_parameter_default(name=f'{tool}_VERSION'))
    for architecture in SUPPLY_CHAIN_ARCHITECTURES:
        assert re.fullmatch(
            r'[0-9a-f]{64}',
            pipeline_parameter_default(name=f'{tool}_LINUX_{architecture}_SHA256'),
        )


def test_circleci_installs_syft_and_grype_checked_before_the_security_scan():
    """The pinned releases are checksummed before extraction, and installed before the scan."""
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')

    assert 'https://github.com/anchore/${tool}/releases/download/v${version}/${archive}' in (
        configuration
    )
    assert configuration.index('sha256sum -c -') < configuration.index('tar -xzf')
    for tool in ('SYFT', 'GRYPE'):
        for architecture in SUPPLY_CHAIN_ARCHITECTURES:
            assert f'<< pipeline.parameters.{tool}_LINUX_{architecture}_SHA256 >>' in (
                configuration
            )
    assert 'DARWIN_ARM64' not in configuration
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
            'Virtualenv', (), {'location': '/checkout/.nox/security-scan-3-15'}
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


def circleci_job_definition(*, name: str) -> str:
    """Return a job's definition under ``jobs:`` (its lines, as text).

    Returns:
        The definition, from its ``name:`` line to the next job's (or the workflows).

    """
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    jobs = configuration[configuration.index('\njobs:\n') : configuration.index('\nworkflows:')]
    # The body ends at the next line indented less than a job's contents: the next job, or a
    # comment or key at the top level
    match = re.search(
        rf'^  {name}:\n(?P<body>(?:(?:    .*)?\n)+?)(?=^ {{0,2}}\S|\Z)', jobs + '\n', re.MULTILINE
    )
    assert match is not None, f'the configuration has no job {name}'
    return match['body']


# The website's AWS infrastructure tests' job (nox -s infra-test: the CDK stacks, the publisher,
# the deploy settings and the CloudFront redirect function, none reaching AWS). Was test-infra,
# which read as the project's test infrastructure (the owner, 2026-11-23)
WEBSITE_INFRASTRUCTURE_JOB = 'test-website-aws-infrastructure'


def test_no_ci_file_names_the_job_by_its_old_name():
    """The rename is whole: a requires or workflow entry left on test-infra would never run."""
    leftovers = [
        f'{path.relative_to(PROJECT_ROOT)}:{number}'
        for path in sorted((PROJECT_ROOT / '.circleci').rglob('*'))
        if path.is_file()
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1)
        if re.search(r'(?<![\w-])test-infra(?![\w-])', line)
    ]

    assert leftovers == []
    assert WEBSITE_INFRASTRUCTURE_JOB in circleci_job_texts()


def test_the_infra_tests_run_on_every_branch():
    """The website's CDK app and publisher are tested on every branch, like the engine.

    The workflow lists the job bare (``- test-website-aws-infrastructure``, no requires or filters).
    """
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    workflow = configuration[configuration.index('\nworkflows:') :]

    assert re.search(rf'^      - {WEBSITE_INFRASTRUCTURE_JOB}\n', workflow, flags=re.MULTILINE)
    assert 'nox -s infra-test' in circleci_job_definition(name=WEBSITE_INFRASTRUCTURE_JOB)


def test_the_infra_sessions_node_tests_name_their_files_never_a_folder():
    """``nox -s infra-test`` hands ``node --test`` files or globs that match every test file.

    Node 26 searches a folder named after ``--test``, but Node 24 (CircleCI's ``-node`` image)
    loads it as one module and fails with "Cannot find module" (every
    ``test-website-aws-infrastructure`` run from
    2026-10-28 to 2026-11-20 failed so, while local runs on Node 26 passed). A glob works on
    Node 22, 24 and 26.
    """
    import noxfile

    session = RecordingSession(posargs=[])
    noxfile.infra_test(session)
    node_commands = [command for command in session.commands if command[0] == 'node']
    assert len(node_commands) == 1, session.commands
    node_command = node_commands[0]
    assert node_command[1] == '--test'
    patterns = node_command[2:]

    named: set[Path] = set()
    for pattern in patterns:
        assert not (PROJECT_ROOT / pattern).is_dir(), f'{pattern} is a folder'
        matches = {path for path in PROJECT_ROOT.glob(pattern) if path.is_file()}
        assert matches, f'{pattern} matches no file'
        named |= matches

    test_files = set((PROJECT_ROOT / 'infra' / 'tests' / 'functions').rglob('*.test.mjs'))
    assert test_files, 'infra/tests/functions holds no *.test.mjs: the check is stale'
    assert named == test_files


def test_the_site_deploys_from_main_once_the_infra_tests_pass():
    """play.glitchy.games publishes from main alone, once its infrastructure tests pass.

    It publishes beside the docs, not after them.

    The owner, 2026-11-20: "essentially would like docs and site publish to happen in parallel"
    (it was "after docs publish", 2026-10-28). The site publishes ``src/website``, not the docs'
    output, so it needs nothing from deploy-docs; test-website-aws-infrastructure still tests the
    code that publishes.
    """
    entry = circleci_workflow_job(name='deploy-site')

    assert f'requires:\n            - {WEBSITE_INFRASTRUCTURE_JOB}\n          filters:' in entry
    assert 'branches:\n              only: main\n' in entry
    assert SITE_DEPLOY_LOCK in entry
    assert 'nox -s site-publish' in circleci_job_definition(name='deploy-site')


def test_the_docs_and_site_deploys_run_side_by_side():
    """Neither deploy waits for the other: different locks, and neither requires the other."""
    docs_entry = circleci_workflow_job(name='deploy-docs')
    site_entry = circleci_workflow_job(name='deploy-site')

    assert SITE_DEPLOY_LOCK not in docs_entry
    assert DOCS_DEPLOY_LOCK not in site_entry
    assert '- deploy-docs\n' not in site_entry
    assert '- deploy-site\n' not in docs_entry


def test_the_site_deploy_uses_oidc_not_stored_keys():
    """The deploy assumes its role with CircleCI's OIDC token: no AWS keys anywhere in CI."""
    definition = circleci_job_definition(name='deploy-site')
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')

    assert 'CIRCLE_OIDC_TOKEN_V2' in definition
    assert 'AWS_WEB_IDENTITY_TOKEN_FILE' in definition
    assert 'AWS_ROLE_ARN' in definition
    assert 'AWS_ACCESS_KEY_ID' not in configuration
    assert 'AWS_SECRET_ACCESS_KEY' not in configuration


def test_the_site_deploy_role_arn_stays_out_of_the_repository():
    """The role's ARN names the AWS account, so it lives in CircleCI's project settings.

    The owner (2026-10-28): "Make SITE_DEPLOY_ROLE_ARN private." The job reads the project
    environment variable and refuses to run without it; the public configuration holds neither
    a pipeline parameter for it nor any ARN.
    """
    definition = circleci_job_definition(name='deploy-site')
    configuration = CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')

    assert 'pipeline.parameters.SITE_DEPLOY_ROLE_ARN' not in configuration
    assert not re.search(r'^  SITE_DEPLOY_ROLE_ARN:', configuration, flags=re.MULTILINE)
    assert 'arn:aws:' not in configuration
    assert '"${SITE_DEPLOY_ROLE_ARN:-}"' in definition
    assert 'Project Settings > Environment Variables' in definition


# The jobs a docs-only change leaves out: every job that runs the suite, and the jobs combining
# their coverage (the owner, 2026-11-20, via the coordinator)
TEST_SCOPE_ALL_JOBS = {
    'test-python-3-15-macos',
    'test-python-3-15-linux',
    'test-python-3-15-windows',
    'coverage-combine-linux-test-3-15',
    'coverage-combine-windows-test-3-15',
    # Of its checks only the strict docs build reads Markdown, and markdown-checks runs that build
    CHECKS_JOB,
}
TEST_SCOPE_FILTER = 'pipeline.parameters.test-scope == "{scope}"'


def workflow_entries() -> dict[str, dict[str, Any]]:
    """Return the build-and-test workflow's jobs by their names, each with its settings.

    Returns:
        Each entry's settings (empty for a bare job name), by the name it runs under.

    """
    configuration = yaml.safe_load(CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8'))
    entries: dict[str, dict[str, Any]] = {}
    for entry in configuration['workflows']['build-and-test']['jobs']:
        if isinstance(entry, str):
            entries[entry] = {}
            continue
        ((job, settings),) = entry.items()
        entries[settings.get('name', job)] = {'job': job, **settings}
    return entries


def test_the_setup_configuration_only_chooses_what_runs():
    """config.yml is a setup configuration: one small job reads the change and continues.

    It checks out, fetches main, runs scripts/ci_change_scope.py (Python's standard library only,
    so nothing is installed) and continues with continue_config.yml and the parameters it wrote.
    Its image is the pipeline's Python's, cimg/python carrying the curl and jq the continuation
    needs.
    """
    from scripts import ci_change_scope

    setup = yaml.safe_load(CIRCLECI_SETUP_PATH.read_text(encoding='utf-8'))
    text = CIRCLECI_SETUP_PATH.read_text(encoding='utf-8')

    assert setup['setup'] is True
    assert setup['orbs'] == {'continuation': 'circleci/continuation@2.0.1'}
    assert list(setup['workflows']) == ['choose-what-runs']
    assert setup['workflows']['choose-what-runs']['jobs'] == ['choose-what-runs']
    (job,) = setup['jobs'].values()
    image = f'cimg/python:{pipeline_parameter_default(name="PYTHON_VERSION")}'
    assert job['docker'] == [{'image': image}]
    assert job['resource_class'] == 'small'
    steps = job['steps']
    assert steps[0] == 'checkout'
    choose = steps[1]['run']['command']
    assert 'git fetch --quiet origin main' in choose
    # git writes the change where the script reads it, and the script writes the parameters
    # where the continuation reads them
    listed = re.search(r'git diff --name-only --no-renames "\$base" HEAD > (?P<file>\S+)', choose)
    run = re.search(
        r'python3 scripts/ci_change_scope\.py --paths (?P<paths>\S+) \\\n'
        r'\s+--output (?P<output>\S+)',
        choose,
    )
    assert listed is not None
    assert run is not None
    assert run['paths'] == listed['file']
    parameters_file = run['output']
    assert steps[2] == {
        'continuation/continue': {
            'configuration_path': '.circleci/continue_config.yml',
            'parameters': parameters_file,
        }
    }
    assert len(steps) == 3
    # Nothing installed before the choice: no uv, no nox, no pip
    assert not re.findall(r'\b(uv|nox|pip)\b', text.split('jobs:', 1)[1])
    assert ci_change_scope.TEST_SCOPES == ('all', 'markdown')


def test_the_test_scope_parameter_defaults_to_running_everything():
    """continue_config.yml's test-scope: the script's two scopes, ``all`` unless it says else."""
    from scripts import ci_change_scope

    configuration = yaml.safe_load(CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8'))

    assert configuration['parameters']['test-scope'] == {
        'type': 'enum',
        'enum': list(ci_change_scope.TEST_SCOPES),
        'default': 'all',
    }


def test_a_docs_only_pipeline_leaves_out_the_test_jobs_and_checks_and_nothing_else():
    """The test, coverage and checks jobs run on ``all`` only, the Markdown checks on ``markdown``.

    Every other job (the infrastructure tests, the deploys on main) has no test-scope filter, and
    every job that runs a test session is among those left out, so a test job added later can't
    run on a docs-only change unseen. The workflow keeps its name: build-and-test is the check
    main's ruleset requires, so a docs-only pull request can still merge.
    """
    entries = workflow_entries()
    jobs = circleci_job_texts()
    scoped = {
        name: settings['filters']
        for name, settings in entries.items()
        if 'test-scope' in str(settings.get('filters', ''))
    }

    assert scoped == {
        **dict.fromkeys(TEST_SCOPE_ALL_JOBS, TEST_SCOPE_FILTER.format(scope='all')),
        'markdown-checks': TEST_SCOPE_FILTER.format(scope='markdown'),
    }
    for name, settings in entries.items():
        job = jobs[settings.get('job', name)]
        if any(command in job for command in TEST_SESSION_COMMANDS):
            assert name in TEST_SCOPE_ALL_JOBS, name


def test_the_markdown_checks_build_the_docs_and_run_the_tests_that_read_markdown():
    """One Linux machine: the strict docs build and the Markdown-reading tests (test-markdown)."""
    job = circleci_job_texts()['markdown-checks']

    assert LINUX_IMAGE_MARKER in job
    assert 'nox -s lint-docs' in job
    assert 'nox -s test-markdown' in job
    assert 'parallelism' not in job


def _reads_markdown(*, path: Path) -> bool:
    """Tell whether a test file names a Markdown file in its code (not its docstrings).

    A string in the code ending ``.md``, or a ``*.md`` pattern: how a test reads a Markdown file
    or a folder of them. Comments and docstrings don't count.

    Returns:
        True if the file names one.

    """
    tree = ast.parse(path.read_text(encoding='utf-8'))
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    return any(
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
        and re.search(r'(\.md$|\*\.md)', node.value) is not None
        for node in ast.walk(tree)
    )


def test_the_markdown_test_list_is_every_test_file_that_reads_markdown():
    """noxfile.MARKDOWN_TEST_FILES is exactly the test files that name a Markdown file.

    The owner, 2026-11-20: docs-only pull requests still run the tests that read Markdown, from
    an explicit list kept honest. A test reading Markdown some other way (a folder listed with
    no ``.md`` in its code) is not detected: name it here by hand if one appears.
    """
    import noxfile

    test_files = sorted(
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in [
            *(PROJECT_ROOT / 'tests').rglob('test_*.py'),
            *(PROJECT_ROOT / 'src').glob('*/*/tests/**/test_*.py'),
        ]
    )
    readers = [path for path in test_files if _reads_markdown(path=PROJECT_ROOT / path)]

    assert readers, 'no test file names a Markdown file: the detection is stale'
    assert list(noxfile.MARKDOWN_TEST_FILES) == readers


def test_the_markdown_test_session_runs_the_list_without_the_coverage_rule():
    """Nox -s test-markdown: the listed files only, in their order, on the dummy drivers.

    A part of the suite can't reach the 100% coverage rule, so coverage is off; the order stays
    the files' own (no rolled order: the change touched no code).
    """
    import noxfile

    installed = '.nox/test-markdown/lib/python3.15/site-packages/glitchygames'
    session = RecordingSession(posargs=[], outputs={'python': f'{installed}\n'})
    noxfile.test_markdown(session)
    (pytest_run,) = [command for command in session.commands if command[0] == 'pytest']

    assert pytest_run[1 : 1 + len(noxfile.MARKDOWN_TEST_FILES)] == noxfile.MARKDOWN_TEST_FILES
    assert '--no-cov' in pytest_run
    assert '--dummy-only' in pytest_run
    assert not [argument for argument in pytest_run if 'randomly' in argument]


def test_every_step_that_builds_the_browser_wheel_lets_uv_replace_a_stale_venv():
    """Each step running nox -s docs-deploy sets UV_VENV_CLEAR=1 (the browser wheel's build).

    The build (third_party/pygame-ce/buildconfig/glitchygames/build_pyodide_wheel.sh) runs
    ``uv venv`` on its cached toolchain folder when the cached venv's python doesn't run, and uv
    0.13.9 then asks "A virtual environment already exists ... replace it? [y/n]" on the step's
    terminal, which no one answers: deploy-docs hung until the step's 60-minute no-output limit
    (jobs 4431, 4443). Closing stdin doesn't stop it (uv reads the answer from the terminal;
    tried 2026-11-21); UV_VENV_CLEAR=1 replaces the venv without asking. The script's own fix
    (``uv venv --clear``) is a submodule change, recorded in plans/future-work.md.
    """
    configuration = yaml.safe_load(CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8'))
    builds = [
        (name, step['run'])
        for name, job in configuration['jobs'].items()
        for step in job.get('steps', [])
        if isinstance(step, dict)
        and isinstance(step.get('run'), dict)
        and 'nox -s docs-deploy' in step['run'].get('command', '')
    ]

    assert [name for name, _ in builds] == ['deploy-docs']
    for name, run in builds:
        assert run.get('environment', {}).get('UV_VENV_CLEAR') == '1', name


# The command that refuses a checkout not on main (docs-deploy and site-publish share it)
ON_MAIN_CHECK = ('git', 'merge-base', '--is-ancestor', 'HEAD', 'origin/main')


def site_publish_session(*, posargs: list[str], git_status: str = '') -> RecordingSession:
    """Run ``nox -s site-publish`` with these arguments against a recording session.

    Args:
        posargs: The session's arguments.
        git_status: What ``git status --porcelain`` prints for the source (empty: clean).

    Returns:
        The session, holding the commands it ran.

    """
    import noxfile

    session = RecordingSession(posargs=posargs, outputs={'git': git_status})
    noxfile.site_publish(session)
    return session


def publish_command(session: RecordingSession) -> tuple[str, ...]:
    """Return the session's ``glitchy_site.publish`` command.

    Returns:
        The command.

    """
    (command,) = [command for command in session.commands if 'glitchy_site.publish' in command]
    return command


def test_the_site_publishes_only_a_clean_checkout_on_main():
    """A publish checks HEAD is on origin/main and the source is committed, before uploading.

    The site's deploy has its own lock now, beside the docs' (the owner, 2026-11-20), so a
    branch or an edited checkout must not reach play.glitchy.games, as docs-deploy refuses one.
    """
    session = site_publish_session(posargs=[])

    publish_at = session.commands.index(publish_command(session))
    assert ON_MAIN_CHECK in session.commands[:publish_at]
    assert ('git', 'status', '--porcelain', '--', 'src/website') in session.commands[:publish_at]


def test_the_site_refuses_to_publish_uncommitted_changes():
    """An edited file in the source stops the publish before anything is uploaded."""
    import noxfile

    session = RecordingSession(posargs=[], outputs={'git': ' M src/website/index.html\n'})

    with pytest.raises(RuntimeError, match='uncommitted'):
        noxfile.site_publish(session)

    assert not [command for command in session.commands if 'glitchy_site.publish' in command]


@pytest.mark.parametrize('flag', ['--dry-run', '--allow-unmerged'])
def test_a_dry_run_or_a_preview_publishes_without_the_main_check(flag):
    """--dry-run changes nothing, and --allow-unmerged is the deliberate local preview."""
    session = site_publish_session(posargs=[flag], git_status=' M src/website/index.html\n')

    assert ON_MAIN_CHECK not in session.commands
    assert '--allow-unmerged' not in publish_command(session)
    assert ('--dry-run' in publish_command(session)) is (flag == '--dry-run')


def test_the_docs_deploy_shares_the_on_main_check():
    """docs-deploy refuses a checkout off main with the same command as site-publish."""
    assert ON_MAIN_CHECK in docs_deploy_commands(posargs=['--no-measure'])
    assert ON_MAIN_CHECK not in docs_deploy_commands(posargs=['--build-only', '--no-measure'])


def test_the_site_deploy_publishes_mains_latest_commit():
    """The deploy moves to main's tip before publishing, so an older pipeline cannot win.

    With its own lock and only test-website-aws-infrastructure to wait for (the owner,
    2026-11-20), a site deploy
    from an older pipeline could otherwise finish after a newer one and put the older site back.
    """
    definition = circleci_job_definition(name='deploy-site')

    move = definition.index('git checkout --quiet --detach origin/main')
    assert 'git fetch --quiet origin main' in definition[:move]
    publish = definition.index('            nox -s site-publish\n')
    assert definition.index('- checkout') < move < publish
