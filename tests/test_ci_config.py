"""CircleCI's pinned tool versions match the ones uv.lock pins, so CI runs what a local run does."""

from __future__ import annotations

import json
import re
import shlex
import shutil
import socket
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace
from typing import Any, NoReturn

import pytest
import yaml
from scripts.workspace_packages import workspace_members

from glitchygames.process import OutputCapture, run_command
from tests.ansible_inventory import raspberry_pi_hosts
from tests.ledger_repositories import environment_without_git_variables, git

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CIRCLECI_CONFIG_PATH = PROJECT_ROOT / '.circleci' / 'config.yml'
# How a job's text names its platform: the Linux image, the Windows executor
LINUX_IMAGE_MARKER = '      - image: cimg/python:'
WINDOWS_EXECUTOR_MARKER = 'name: win/default'
# A job that runs a test session runs one of these commands
TEST_SESSION_COMMANDS = ('      - nox-test:\n', '      - nox-test-windows:\n')
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
def test_docs_serve_refuses_a_taken_address_before_building(listing, command):
    """A taken address stops the session at once, naming who holds it and a free one.

    mkdocs binds its address only after the whole build (about five minutes), so it failed late
    (2026-11-13: ports 8000-8002 all held by Python servers). ``lsof`` finds the listener and
    ``ps`` its command line (``lsof``'s short name was ``python3.14`` for all three); without
    ``lsof``, or when it finds none, the message names only the address.
    """
    import noxfile

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
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
    assert re.search(r'nox -s docs-serve -- --dev-addr 127\.0\.0\.1:\d+$', message)
    assert not any('mkdocs' in command for command in session.commands)


def test_docs_serve_suggests_an_address_that_is_free():
    """The suggested port is one nothing listens on, after the taken one."""
    import noxfile

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        port = listener.getsockname()[1]

        suggested = noxfile._free_port_after(host='127.0.0.1', port=port)

        assert suggested > port
        assert not noxfile._address_in_use(host='127.0.0.1', port=suggested)
        assert noxfile._address_in_use(host='127.0.0.1', port=port)


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

    assert 'requires:\n            - test-python-3-15-macos\n' in entry
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
APT_CACHE_KEY_PREFIX = 'apt-v1-'
# The file a step writes this ISO week to, whose checksum ends the apt cache's key (git-ignored)
APT_CACHE_WEEK_FILE = 'test-results/apt-cache-week'


def linux_job_steps() -> list[Any]:
    """Return the Linux test job's steps, parsed.

    Returns:
        The steps, in order.

    """
    steps = circleci_jobs()['test-python-3-15-linux']['steps']
    assert isinstance(steps, list)
    return steps


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


def run_apt_install_script(
    *, tmp_path: Path, cache_hit: bool, mirror_up: bool
) -> tuple[int, list[str]]:
    """Run the step's script with stand-ins for sudo and apt-get; return its status and apt's calls.

    The stand-in apt-get installs when the cache was restored (cache_hit) or after an update
    that reached the mirror (mirror_up); an install with neither fails, as apt-get does with no
    lists ("Unable to locate package", exit 100). sudo runs its command as this user, except that
    ``tee`` writes into tmp_path instead of /etc.

    Returns:
        The script's exit status and each apt-get call's arguments, in order.

    """
    stand_ins = tmp_path / 'bin'
    stand_ins.mkdir()
    calls = tmp_path / 'apt-calls.txt'
    (stand_ins / 'sudo').write_text(
        '#!/bin/bash\n'
        'if [ "$1" = tee ]; then shift; cat > "$STAND_IN_ROOT/$(basename "$1")"; exit; fi\n'
        'exec "$@"\n',
        encoding='utf-8',
    )
    (stand_ins / 'apt-get').write_text(
        '#!/bin/bash\n'
        'echo "$*" >> "$APT_CALLS"\n'
        'if [ "$1" = autoclean ]; then exit 0; fi\n'
        'if [ "$1" = update ]; then\n'
        '  [ "$MIRROR_UP" = 1 ] && touch "$STAND_IN_ROOT/updated"\n'
        '  exit 0\n'
        'fi\n'
        '[ "$CACHE_HIT" = 1 ] || [ -e "$STAND_IN_ROOT/updated" ] || exit 100\n',
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
            'CACHE_HIT': '1' if cache_hit else '0',
            'MIRROR_UP': '1' if mirror_up else '0',
        },
        timeout_seconds=60,
        capture_output=OutputCapture.TOGETHER,
    )
    called = calls.read_text(encoding='utf-8').splitlines() if calls.exists() else []
    return result.returncode, [call.split()[0] for call in called]


apt_script_needs_bash = pytest.mark.skipif(
    sys.platform == 'win32' or shutil.which('bash') is None,
    reason="the Linux job's script is bash; its stand-ins are bash scripts",
)


@apt_script_needs_bash
def test_a_restored_apt_cache_installs_without_updating(tmp_path):
    """A cache hit installs from the cached lists and packages: no mirror is asked."""
    status, calls = run_apt_install_script(tmp_path=tmp_path, cache_hit=True, mirror_up=False)

    assert (status, calls) == (0, ['install'])


@apt_script_needs_bash
def test_a_failed_cached_install_updates_from_the_mirror_and_installs_again(tmp_path):
    """No cache (a new key) or a stale one: the fallback updates, installs, then autocleans.

    autoclean drops the packages the fresh lists no longer name, so the week's new cache holds
    no outdated ones.
    """
    status, calls = run_apt_install_script(tmp_path=tmp_path, cache_hit=False, mirror_up=True)

    assert (status, calls) == (0, ['install', 'update', 'install', 'autoclean'])


@apt_script_needs_bash
def test_no_cache_and_no_mirror_fails_the_step(tmp_path):
    """With nothing cached and the mirror down, the step fails rather than going on."""
    status, calls = run_apt_install_script(tmp_path=tmp_path, cache_hit=False, mirror_up=False)

    assert status != 0
    assert calls == ['install', 'update', 'install']


def test_every_linux_job_installs_the_linux_jobs_system_packages():
    """Every Linux test job installs exactly the Linux job's packages, so a new one can't drift."""
    import noxfile

    linux_jobs = jobs_that_run_tests(platform_marker=LINUX_IMAGE_MARKER)
    expected = noxfile._linux_ci_job_packages(
        configuration=CIRCLECI_CONFIG_PATH.read_text(encoding='utf-8')
    )
    for name, job in linux_jobs.items():
        install = re.search(
            r'^\s+sudo apt-get install -y (?P<packages>\S.*)$', job, flags=re.MULTILINE
        )
        assert install is not None, name
        assert install['packages'].split() == expected, name


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
    """Each runs on two machines, saves each's coverage, and one combine job applies the rule.

    The owner, 2026-11-18 (one Python ran past the one-hour limit on Linux, jobs 3705, 3707):
    "yes" to two machines a job, and "Do it for windows too". tests/circleci_test_split.py picks
    each machine's share; the combine job holds the shares together to 100%.
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
        assert '    parallelism: 2\n' in job, name
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


def test_the_builds_are_on_3_15_once_an_os():
    """Build and build-binary run on 3.15; each OS builds in one running job, on one machine.

    The owner, 2026-11-18: "Switch the builds over to 3.15". A split job runs every step on each
    machine, so its build runs on machine 0 only.
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
    for job in ('test-python-3-15-macos', 'deploy-docs'):
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
    """pytest-randomly is blocked in addopts: CI and every ordinary run keep the files' order."""
    pyproject = tomllib.loads((PROJECT_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    addopts = shlex.split(pyproject['tool']['pytest']['ini_options']['addopts'])

    assert '-p' in addopts
    assert addopts[addopts.index('-p') + 1] == 'no:randomly'


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
    assert pythons == ['3.15']
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
# The hook stages .pre-commit-config.yaml installs (default_install_hook_types)
HOOK_STAGES = ('pre-commit', 'pre-push')


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

    assert 'entry: uv run --extra dev nox -s test-random' in hooks


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
        configuration={'environment': {}, 'runs_in_linux_container': False},
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
        'entry: uv run --extra dev nox -s compare-drivers -- --drivers native '
        '--fail-on-difference --workers auto --skip-when-frames-cannot-change'
    ) in hooks


@pytest.mark.parametrize(
    ('path', 'cannot_change_frames'),
    [
        ('plans/2026-11-13-zensical-migration.md', True),
        ('docs/quality/driver_comparison.md', True),
        ('quality/replay-ledger/abc-row.json', True),
        ('.circleci/config.yml', True),
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
    mocker.patch.object(noxfile, '_compare_driver_configurations', return_value=differing)
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
    compare = mocker.patch.object(noxfile, '_compare_driver_configurations', return_value=[])
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
        'entry: uv run --extra dev nox -s compare-drivers -- --drivers native --fail-on-difference'
        in hooks
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
    configuration = (PROJECT_ROOT / '.circleci' / 'config.yml').read_text(encoding='utf-8')
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


def test_the_linux_and_raspberry_pi_jobs_set_the_memory_limit():
    """The Linux job (2 GB, serial) stops a run past 1750 MiB, naming the test (memory_guard.py).

    So does the Raspberry Pi's (real hardware, 3.7 GB with its desktop). The macOS and Windows
    jobs have the memory, and the plugin needs Linux's ``/proc/self/statm`` anyway. The Linux
    job's resource class and worker count stay as they were.
    """
    linux_jobs = jobs_that_run_tests(platform_marker=LINUX_IMAGE_MARKER)

    # Every test job on the Linux image, so a new one can't miss them
    assert set(linux_jobs) == {'test-python-3-15-linux'}
    assert '      GLITCHYGAMES_TEST_RSS_LIMIT_MB: "1750"\n' in raspberry_pi_job()
    for name, job in linux_jobs.items():
        assert '      GLITCHYGAMES_TEST_RSS_LIMIT_MB: "1750"\n' in job, name
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

    Read from .circleci/config.yml, so a change to the job changes the session too.
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
        'GLITCHYGAMES_TEST_RSS_LIMIT_MB=1750',
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
