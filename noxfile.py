"""Nox session definitions for linting, testing, security scanning, and benchmarks."""

import contextlib
import json
import os
import shutil
import socket
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import nox

if TYPE_CHECKING:
    from collections.abc import Generator

# Use uv as the venv backend so nox sessions get their own isolated venvs
# managed by uv, without touching the project's .venv.
nox.options.default_venv_backend = 'uv'

_CODE_DIRS = ['noxfile.py', 'glitchygames', 'scripts', 'tests']


# ---------------------------------------------------------------------------
# Helper functions (reusable logic, not sessions themselves)
# ---------------------------------------------------------------------------


def _install_from_lockfile(session: nox.Session, *, all_extras: bool = True) -> None:
    """Install the project into the session's venv exactly as uv.lock pins it.

    ``uv sync --frozen`` never re-resolves, so every session, local or CI, on every OS, runs
    the locked versions (installing ``.[api,dev,docs]`` with pip-style resolution picked the
    newest matching versions, so a new release of any dependency could change what CI tested
    without the lockfile changing). ``--no-editable`` installs the built package, as before,
    not the source tree.

    Args:
        session: The nox session whose venv to fill.
        all_extras: Every extra (dev, docs, api) when True; the runtime dependencies only
            when False.

    """
    session.run_install(
        'uv',
        'sync',
        '--frozen',
        '--no-editable',
        *(['--all-extras'] if all_extras else []),
        env={'UV_PROJECT_ENVIRONMENT': session.virtualenv.location},
    )


def _format_code(session: nox.Session) -> None:
    """Format Python code with ruff (import sorting + black-style formatting)."""
    for target in _CODE_DIRS:
        session.run('ruff', 'check', '--select', 'I', '--fix', target)
    for target in _CODE_DIRS:
        session.run('ruff', 'format', target)


def _format_toml(session: nox.Session) -> None:
    """Format TOML files with taplo."""
    session.run('taplo', 'format', external=True)


def _lint_code(session: nox.Session) -> None:
    """Lint Python code with ruff."""
    session.run('ruff', 'check', *_CODE_DIRS)


def _lint_docs(session: nox.Session) -> None:
    """Lint documentation with mkdocs strict build."""
    session.run('mkdocs', 'build', '--strict')


def _lint_yaml(session: nox.Session) -> None:
    """Lint YAML files with yamllint."""
    session.run('yamllint', '--strict', '.', external=True)


def _lint_circleci(session: nox.Session) -> None:
    """Validate CircleCI configuration."""
    if os.environ.get('CIRCLECI') == 'true':
        session.log(
            'Running inside CircleCI; skipping config validation'
            ' (agent binary does not support it).'
        )
        return
    if not shutil.which('circleci'):
        session.log('circleci CLI not found on PATH; skipping config validation.')
        return
    session.run('circleci', 'config', 'validate', external=True)


def _lint_github_actions(session: nox.Session) -> None:
    """Lint GitHub Actions workflows with actionlint."""
    if not Path('.github/workflows').is_dir():
        session.log('No .github/workflows/ directory found; skipping actionlint.')
        return
    if not shutil.which('actionlint'):
        session.log('actionlint not found on PATH; skipping.')
        return
    session.run('actionlint', external=True)


def _lint_toml(session: nox.Session) -> None:
    """Lint TOML files with taplo."""
    session.run('taplo', 'lint', external=True)


def _lint_dependencies(session: nox.Session) -> None:
    """Check for dependency issues with deptry."""
    session.run('deptry', '.')


def _lint_dead_code(session: nox.Session) -> None:
    """Detect dead code with vulture."""
    session.run('vulture', 'glitchygames', 'vulture_whitelist.py', '--min-confidence=80')


# Known vulnerabilities pip-audit ignores: only ones with no fix we can take yet, each with why.
# Re-check every entry when dependencies are upgraded and remove it once upstream allows the fix
# (pip-audit says nothing about an ignore that no longer matches). Checked 2026-10-23.
_IGNORED_VULNERABILITIES: dict[str, str] = {
    # google-cloud-aiplatform 1.71.1 (also PYSEC-2026-2500, GHSA-wh2j-26j7-9728): predictable
    # bucket names in Vertex AI Experiments, fixed in 1.133.0. vertexai 1.71.1, the newest, pins
    # google-cloud-aiplatform==1.71.1, and aisuite 0.2.0, the newest, needs vertexai (its Google
    # backend). The engine never uses Vertex AI Experiments
    'CVE-2026-2473': 'google-cloud-aiplatform 1.71.1, pinned by vertexai (aisuite)',
    # filelock 3.32.7, fixed in 4.2.1: the SQLite-backed ReadWriteLock/AsyncReadWriteLock (all
    # platforms) and, on Windows, the soft locks and the read-write lock's database path. safety
    # 3.8.1, the newest (nox -s safety-scan), requires filelock<4.0; forcing filelock 4 moves the
    # lock back to safety 3.2.3. Only tools use filelock (safety, virtualenv, huggingface-hub);
    # the engine never imports it
    'CVE-2026-112907': 'filelock 3.32.7, capped below 4 by safety 3.8.1',
    'CVE-2026-112913': 'filelock 3.32.7, capped below 4 by safety 3.8.1',
    'CVE-2026-112940': 'filelock 3.32.7, capped below 4 by safety 3.8.1',
}


def _lint_cves(session: nox.Session) -> None:
    """Audit every locked dependency (all extras) for known CVEs with pip-audit.

    Ignores only ``_IGNORED_VULNERABILITIES``, each documented with why it cannot be fixed yet.
    """
    import tempfile

    # Export requirements to a temp file (cross-platform; /dev/stdin doesn't exist on Windows)
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.txt',
        delete=False,
        encoding='utf-8',
    ) as tmp:
        tmp_path = tmp.name
    try:
        session.run(
            'uv',
            'export',
            '--quiet',
            '--no-emit-project',
            # The extras too (dev tools, aisuite and its SDKs): what `uv sync --all-extras` installs
            '--all-extras',
            '--output-file',
            tmp_path,
            external=True,
        )
        ignore_arguments = [
            argument
            for vulnerability in _IGNORED_VULNERABILITIES
            for argument in ('--ignore-vuln', vulnerability)
        ]
        session.run(
            'pip-audit',
            '--requirement',
            tmp_path,
            '--require-hashes',
            '--disable-pip',
            *ignore_arguments,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Aggregate sessions
# ---------------------------------------------------------------------------


@nox.session(python=['3.14'], reuse_venv=False, name='format')
def format_all(session: nox.Session) -> None:
    """Run all formatters (code + TOML)."""
    _install_from_lockfile(session)
    _format_code(session)
    _format_toml(session)


@nox.session(python=['3.14'], reuse_venv=False, name='lint')
def lint_all(session: nox.Session) -> None:
    """Run all linters (code, docs, YAML, TOML, deps, dead code, CVEs)."""
    _install_from_lockfile(session)
    _lint_code(session)
    _lint_docs(session)
    _lint_yaml(session)
    _lint_circleci(session)
    _lint_github_actions(session)
    _lint_toml(session)
    _lint_dependencies(session)
    _lint_dead_code(session)
    _lint_cves(session)


# ---------------------------------------------------------------------------
# Individual format sessions
# ---------------------------------------------------------------------------


@nox.session(python=['3.14'], reuse_venv=False, name='format-code', default=False)
def format_code(session: nox.Session) -> None:
    """Format Python code with ruff (import sorting + black-style formatting)."""
    _install_from_lockfile(session)
    _format_code(session)


@nox.session(venv_backend='none', name='format-toml', default=False)
def format_toml(session: nox.Session) -> None:
    """Format TOML files with taplo."""
    _format_toml(session)


# ---------------------------------------------------------------------------
# Individual lint sessions
# ---------------------------------------------------------------------------


@nox.session(python=['3.14'], reuse_venv=False, name='lint-code', default=False)
def lint_code(session: nox.Session) -> None:
    """Lint Python code with ruff."""
    _install_from_lockfile(session)
    _lint_code(session)


@nox.session(python=['3.14'], reuse_venv=False, name='lint-docs', default=False)
def lint_docs(session: nox.Session) -> None:
    """Lint documentation with mkdocs strict build."""
    _install_from_lockfile(session)
    _lint_docs(session)


# git fetch's exit statuses a docs build accepts: fetched, or failed (offline, no remote, no
# gh-pages branch yet)
_GIT_FETCH_STATUSES = [0, 1, 128]


def _replay_metrics(session: nox.Session, *arguments: str) -> None:
    """Run scripts/replay_metrics.py in the project's environment (``uv run``).

    The rebaselines it starts must run this checkout's package (the project's editable install)
    to know their commit: a nox venv's built copy of the package cannot name it.
    """
    session.run(
        'uv',
        'run',
        '--frozen',
        'python',
        'scripts/replay_metrics.py',
        *arguments,
        external=True,
        # Unset (nox drops None): a session's own venv is not the project's, and uv would warn
        env={'VIRTUAL_ENV': None},
    )


@nox.session(venv_backend='none', name='replay-metrics', default=False)
def replay_metrics(session: nox.Session) -> None:
    """Measure every golden replay and bundled demo on this machine into the run ledger.

    scripts/replay_metrics.py rebaselines each recording headless (a few seconds each), which
    measures every frame's processing time, and appends one row per recording to
    test-results/replay-metrics/pending.jsonl; ``nox -s docs-deploy`` publishes the rows with the
    docs site (gh-pages), whose Performance page graphs them. A recording already measured for
    this commit on this machine is skipped. A checkout with uncommitted changes is refused.

    Usage:
        nox -s replay-metrics                    # Measure what this commit has not measured
        nox -s replay-metrics -- --force         # Measure everything again
        nox -s replay-metrics -- --allow-dirty   # A trial on uncommitted changes (rows say so)
        nox -s replay-metrics -- --only muncher  # Only recordings whose path contains "muncher"
    """
    _replay_metrics(session, 'measure', *session.posargs)


@nox.session(python=['3.14'], reuse_venv=False, name='docs-deploy', default=False)
def docs_deploy(session: nox.Session) -> None:
    """Measure the replays, build the docs strictly and publish them to GitHub Pages.

    https://terrysimons.github.io/glitchygames/ serves the gh-pages branch. First ``git fetch
    origin gh-pages`` (the deploy republishes the run ledger merged with what gh-pages holds, so
    a failed fetch stops it; ``--build-only`` goes on offline with what the last fetch saw) and
    ``nox -s replay-metrics``'s measurement (``--skip-dirty``: nothing is measured on a checkout
    with uncommitted changes). ``mkdocs gh-deploy`` then builds the site (its hook,
    scripts/mkdocs_hooks.py, first generates the complexity graphs from HEAD's whole git history
    when they were made from another commit: about a minute, and the performance graphs from the
    published run ledger plus the pending rows, which it publishes with the site), commits it to
    gh-pages and pushes it. Only after that succeeded are the now-published pending rows
    removed. Before the docs, every game's browser build (``scripts/build_browser_bundle.py
    all``: the pygame-ce wheel is built first when the submodule changed) goes into the site as
    play/. Run it from what should be published (usually main after a merge); a warning stops
    it before anything is pushed.

    Usage:
        nox -s docs-deploy                  # Measure, build (graphs included) and push gh-pages
        nox -s docs-deploy -- --build-only  # Measure and build into site/; no push
    """
    _install_from_lockfile(session)
    build_only = '--build-only' in session.posargs
    # A deploy publishes the merged ledger in place of the published one, so it must start from
    # what gh-pages holds now: only a build tolerates a failed fetch
    session.run(
        'git',
        'fetch',
        'origin',
        'gh-pages',
        external=True,
        success_codes=_GIT_FETCH_STATUSES if build_only else [0],
    )
    _replay_metrics(session, 'measure', '--skip-dirty')
    # The browser games, published with the docs as play/ (scripts/mkdocs_hooks.py)
    session.run('python', 'scripts/build_browser_bundle.py', 'all')
    if build_only:
        session.run('mkdocs', 'build', '--strict')
        return
    session.run('mkdocs', 'gh-deploy', '--strict')
    _replay_metrics(session, 'clear-published')


@nox.session(python=['3.14'], reuse_venv=False, name='docs-serve', default=False)
def docs_serve(session: nox.Session) -> None:
    """Serve the docs locally, built as docs-deploy builds them (graphs included, strict).

    ``mkdocs serve --strict`` builds the site (its hook generates the complexity graphs when they
    were made from another commit; each reload with the same HEAD skips that) and serves it at
    http://127.0.0.1:8000/glitchygames/, rebuilding as files change, until Ctrl-C. Nothing is
    pushed. Arguments after ``--`` go to ``mkdocs serve``.

    Usage:
        nox -s docs-serve                               # Serve at http://127.0.0.1:8000/
        nox -s docs-serve -- --dev-addr 127.0.0.1:8001  # Another address
    """
    _install_from_lockfile(session)
    session.run('mkdocs', 'serve', '--strict', *session.posargs)


@nox.session(venv_backend='none', name='lint-yaml', default=False)
def lint_yaml(session: nox.Session) -> None:
    """Lint YAML files with yamllint."""
    _lint_yaml(session)


@nox.session(venv_backend='none', name='lint-circleci', default=False)
def lint_circleci(session: nox.Session) -> None:
    """Validate CircleCI configuration."""
    _lint_circleci(session)


@nox.session(venv_backend='none', name='lint-github-actions', default=False)
def lint_github_actions(session: nox.Session) -> None:
    """Lint GitHub Actions workflows with actionlint."""
    _lint_github_actions(session)


@nox.session(venv_backend='none', name='lint-ci-config', default=False)
def lint_ci_config(session: nox.Session) -> None:
    """Validate all CI configurations (CircleCI + GitHub Actions)."""
    _lint_circleci(session)
    _lint_github_actions(session)


@nox.session(venv_backend='none', name='lint-toml', default=False)
def lint_toml(session: nox.Session) -> None:
    """Lint TOML files with taplo."""
    _lint_toml(session)


@nox.session(python=['3.14'], reuse_venv=False, name='lint-dependencies', default=False)
def lint_dependencies(session: nox.Session) -> None:
    """Check for dependency issues with deptry."""
    _install_from_lockfile(session)
    _lint_dependencies(session)


@nox.session(python=['3.14'], reuse_venv=False, name='lint-dead-code', default=False)
def lint_dead_code(session: nox.Session) -> None:
    """Detect dead code with vulture."""
    _install_from_lockfile(session)
    _lint_dead_code(session)


@nox.session(python=['3.14'], reuse_venv=False, name='lint-cves', default=False)
def lint_cves(session: nox.Session) -> None:
    """Audit dependencies for known CVEs with pip-audit."""
    _install_from_lockfile(session)
    _lint_cves(session)


# ---------------------------------------------------------------------------
# Static type analysis
# ---------------------------------------------------------------------------


def _static_analysis_basedpyright(session: nox.Session) -> None:
    """Run static type analysis with basedpyright."""
    session.run('basedpyright')


def _static_analysis_ty(session: nox.Session) -> None:
    """Run static type analysis with ty (Astral's type checker)."""
    session.run('ty', 'check')


@nox.session(python=['3.14'], reuse_venv=False, name='static-analysis-basedpyright', default=False)
def static_analysis_basedpyright(session: nox.Session) -> None:
    """Run static type analysis with basedpyright."""
    _install_from_lockfile(session)
    _static_analysis_basedpyright(session)


@nox.session(python=['3.14'], reuse_venv=False, name='static-analysis-ty', default=False)
def static_analysis_ty(session: nox.Session) -> None:
    """Run static type analysis with ty (Astral's type checker)."""
    _install_from_lockfile(session)
    _static_analysis_ty(session)


@nox.session(python=['3.14'], reuse_venv=False, name='static-analysis')
def static_analysis(session: nox.Session) -> None:
    """Run all static type analysis (basedpyright + ty)."""
    _install_from_lockfile(session)
    _static_analysis_basedpyright(session)
    _static_analysis_ty(session)


# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------


# cgroup v2's CPU limit: "<quota> <period>" in microseconds, or "max <period>" for no limit
_CGROUP_CPU_MAX = Path('/sys/fs/cgroup/cpu.max')


def _usable_cpu_count() -> int:
    """Count the CPUs this process may use: its CPU set, capped by a container's CPU quota.

    A container sees the host's CPUs (CircleCI's small Linux executor has 1 vCPU on a host
    with dozens), so the count alone would start dozens of test workers in its 2 GB.

    Returns:
        The usable CPU count, at least 1.

    """
    cpus = os.process_cpu_count() or 1
    try:
        quota, period = _CGROUP_CPU_MAX.read_text(encoding='utf-8').split()
    except OSError, ValueError:
        return cpus
    if quota == 'max':
        return cpus
    return max(1, min(cpus, int(quota) // int(period)))


@nox.session(python=['3.14'], reuse_venv=False)
def test(session: nox.Session) -> None:
    """Run tests."""
    _install_from_lockfile(session)

    # The SDL drivers are left to the suite (tests/sdl_defaults.py defaults both to dummy, and
    # outside CI tests/driver_comparison.py also runs the native driver and compares the
    # frames); a driver the caller set is passed on and runs alone.

    # PYTEST_WORKERS, when set, is the xdist worker count as given (0: run serially in this
    # process, no worker; CircleCI's Linux job sets it). Otherwise, in CI, use half the CPUs the
    # job may use, to avoid resource exhaustion, or run serially with too few for two workers.
    # Locally, -n auto (from pyproject.toml addopts) uses all cores.
    args: list[str] = []
    requested_workers = os.environ.get('PYTEST_WORKERS')
    if requested_workers is not None:
        args.extend(['-n', str(int(requested_workers))])
    elif os.environ.get('CI') == 'true':
        half_cpus = _usable_cpu_count() // 2
        args.extend(['-n', str(half_cpus if half_cpus > 1 else 0)])

    # Live log output: pyproject.toml's addopts stream every DEBUG record as tests run. In CI
    # that is only WARNING and above (a serial run printed every debug line into the job log);
    # PYTEST_LOG_CLI_LEVEL overrides it (e.g. DEBUG, to re-run a failing job with full logs).
    # A test's captured logs are still reported when it fails.
    log_cli_level = os.environ.get('PYTEST_LOG_CLI_LEVEL')
    if log_cli_level is None and os.environ.get('CI') == 'true':
        log_cli_level = 'WARNING'
    if log_cli_level is not None:
        args.append(f'--log-cli-level={log_cli_level}')

    # Run tests with coverage: pytest-cov (pyproject.toml addopts) prints the terminal report
    # and writes htmlcov/. JUnit XML output is stored for CI test result ingestion.
    session.run('pytest', *args)


# The Linux X11 test image and the X server it draws on (XQuartz's display :0, over TCP)
_LINUX_X11_IMAGE = 'glitchygames-linux-x11'
_LINUX_X11_VENV_VOLUME = 'glitchygames-linux-venv'
_XQUARTZ_PORT = 6000
_XQUARTZ_START_SECONDS = 30
# `xauth nlist` writes each record as hex fields: family, then length-prefixed address, display
# number, auth name and cookie. Family 0000 is a TCP address; display number "0" is 30 in hex
_XAUTH_TCP_FAMILY = '0000'
_XAUTH_WILDCARD_FAMILY = 'ffff'
_XAUTH_DISPLAY_ZERO = ('0001', '30')


def _wait_for_xquartz(session: nox.Session) -> None:
    """Start XQuartz (a no-op when it runs) and wait until it accepts TCP connections.

    Args:
        session: The nox session (for errors).

    """
    session.run('open', '-a', 'XQuartz', external=True)
    deadline = time.monotonic() + _XQUARTZ_START_SECONDS
    while time.monotonic() < deadline:
        with contextlib.suppress(OSError), socket.create_connection(('localhost', _XQUARTZ_PORT)):
            return
        time.sleep(0.5)
    session.error(
        f'XQuartz is not listening on port {_XQUARTZ_PORT}: enable TCP connections with '
        '`defaults write org.xquartz.X11 nolisten_tcp -bool false` and restart XQuartz'
    )


def _write_wildcard_xauthority(session: nox.Session, *, path: Path) -> None:
    """Copy XQuartz's TCP cookie for display :0 to ``path`` with a wildcard address.

    A container's connection does not arrive as this host's name, so a cookie for the host's
    address would not match; the wildcard family matches any address and still needs the
    secret (XQuartz makes a new one at each launch, so this runs every session).

    Args:
        session: The nox session (runs xauth).
        path: The Xauthority file to write.

    """
    records = session.run(
        '/opt/X11/bin/xauth', 'nlist', silent=True, external=True, env={'DISPLAY': ':0'}
    )
    for record in str(records).splitlines():
        family, *fields = record.split()
        if family == _XAUTH_TCP_FAMILY and tuple(fields[2:4]) == _XAUTH_DISPLAY_ZERO:
            path.write_bytes(bytes.fromhex(_XAUTH_WILDCARD_FAMILY + ''.join(fields)))
            path.chmod(0o644)
            return
    session.error('XQuartz has no TCP cookie for display :0 (is XQuartz running?)')


# The Mac's PulseAudio server, which the Linux container plays its sound through: its TCP port,
# the addresses that may connect without a cookie (loopback and Docker's private ranges; the
# container's connections arrive from Docker Desktop's network), and how long it may take to
# start listening
_PULSEAUDIO_PORT = 4713
_PULSEAUDIO_ALLOWED_ADDRESSES = '127.0.0.1;192.168.0.0/16;172.16.0.0/12'
_PULSEAUDIO_TCP_MODULE = (
    'module-native-protocol-tcp',
    f'auth-ip-acl={_PULSEAUDIO_ALLOWED_ADDRESSES}',
    'auth-anonymous=1',
)
_PULSEAUDIO_START_SECONDS = 15


def _pulseaudio_listening() -> bool:
    """Tell whether something accepts connections on PulseAudio's TCP port here.

    Returns:
        True when a connection to localhost's port 4713 succeeds.

    """
    with contextlib.suppress(OSError), socket.create_connection(('localhost', _PULSEAUDIO_PORT)):
        return True
    return False


def _start_pulseaudio(session: nox.Session) -> bool:
    """Start the Mac's PulseAudio server with TCP for the container, unless it runs already.

    The server is left running afterwards, as XQuartz is (`pulseaudio --kill` stops it). A
    server already running without TCP gets the TCP module loaded (`pactl load-module`).

    Args:
        session: The nox session.

    Returns:
        True when the server accepts TCP connections; False (logged in one line: the container
        then uses the dummy audio driver) when PulseAudio is not installed or will not start.

    """
    if shutil.which('pulseaudio') is None:
        session.warn('PulseAudio is not installed (brew install pulseaudio): dummy audio instead')
        return False
    if not _pulseaudio_listening():
        # A server already running gets the TCP module (pactl fails, harmlessly, without one);
        # then one is started if still nothing listens (it fails, harmlessly, if one runs)
        session.run(
            'pactl', 'load-module', *_PULSEAUDIO_TCP_MODULE, external=True, success_codes=[0, 1]
        )
    if not _pulseaudio_listening():
        session.run(
            'pulseaudio',
            '--daemonize=yes',
            '--exit-idle-time=-1',
            f'--load={" ".join(_PULSEAUDIO_TCP_MODULE)}',
            external=True,
            success_codes=[0, 1],
        )
    deadline = time.monotonic() + _PULSEAUDIO_START_SECONDS
    while time.monotonic() < deadline:
        if _pulseaudio_listening():
            return True
        time.sleep(0.5)
    session.warn(
        f'PulseAudio is not listening on port {_PULSEAUDIO_PORT} (see `pulseaudio --check -v`): '
        'dummy audio instead'
    )
    return False


# The container's setup before its command: the locked dev dependencies into the venv volume
_LINUX_X11_SYNC = 'uv sync --frozen --extra dev --no-install-package taplo --quiet'


def _run_in_linux_x11_container(
    session: nox.Session,
    *,
    command: list[str],
    video_driver: str = 'x11',
    audio_driver: str = 'dummy',
    success_codes: list[int] | None = None,
) -> None:
    """Run a command in the Linux test container, its windows on this Mac's XQuartz.

    Starts XQuartz, copies its cookie and builds the image (each a no-op when already done),
    then runs the command in /work (this checkout, mounted) with the venv kept in a Docker
    volume between runs. The container is named after this process and removed afterwards,
    even when the session is interrupted.

    Args:
        session: The nox session.
        command: The command, as an argument list.
        video_driver: SDL's video driver in the container (``x11``, or ``dummy``).
        audio_driver: SDL's audio driver in the container: ``dummy``, or ``pulseaudio`` (the
            Mac's PulseAudio server over TCP: start it first with ``_start_pulseaudio``).
        success_codes: The exit codes that count as success (default: 0 only).

    """
    if sys.platform != 'darwin':
        session.error(
            'the Linux X11 container forwards windows to XQuartz, so it runs on macOS only'
        )
    _wait_for_xquartz(session)
    xauthority = Path(session.create_tmp()).resolve() / 'xauthority'
    _write_wildcard_xauthority(session, path=xauthority)
    session.run(
        'docker', 'build', '--quiet', '--tag', _LINUX_X11_IMAGE, 'scripts/linux_x11', external=True
    )
    audio_environment = (
        ['--env', f'PULSE_SERVER=tcp:host.docker.internal:{_PULSEAUDIO_PORT}']
        if audio_driver == 'pulseaudio'
        else []
    )
    container_name = f'{_LINUX_X11_IMAGE}-{os.getpid()}'
    try:
        session.run(
            'docker',
            'run',
            '--rm',
            # An init process as PID 1 reaps orphaned processes, as on any real system: without
            # it a grandchild a test stops stays a zombie (tests/test_process.py)
            '--init',
            '--name',
            container_name,
            '--env',
            'DISPLAY=host.docker.internal:0',
            '--env',
            'XAUTHORITY=/x11/xauthority',
            '--env',
            f'SDL_VIDEODRIVER={video_driver}',
            '--env',
            f'SDL_AUDIODRIVER={audio_driver}',
            *audio_environment,
            '--env',
            'UV_PROJECT_ENVIRONMENT=/venv',
            '--env',
            'UV_LINK_MODE=copy',
            # Coverage data stays in the container, apart from the host's own runs
            '--env',
            'COVERAGE_FILE=/venv/.coverage',
            '--volume',
            f'{xauthority}:/x11/xauthority:ro',
            '--volume',
            f'{Path.cwd()}:/work',
            '--volume',
            f'{_LINUX_X11_VENV_VOLUME}:/venv',
            _LINUX_X11_IMAGE,
            *command,
            external=True,
            success_codes=success_codes,
        )
    finally:
        # Gone already after a normal end (--rm): "No such container" (exit 1) is expected
        session.run(
            'docker',
            'rm',
            '--force',
            container_name,
            external=True,
            silent=True,
            success_codes=[0, 1],
        )


@nox.session(venv_backend='none', name='test-linux-x11', default=False)
def test_linux_x11(session: nox.Session) -> None:
    """Run the tests on Linux in Docker, windows on this Mac's XQuartz, sound on its PulseAudio.

    The suite runs with SDL's x11 video driver (a real framebuffer: real pixel formats and
    window behaviour, unlike the dummy driver) and the pulseaudio audio driver, playing through
    the Mac's PulseAudio server over TCP (`brew install pulseaudio`; the session starts it when
    it is not running, accepting connections from loopback and Docker's private ranges, and
    leaves it running, as XQuartz: `pulseaudio --kill` stops it). Without PulseAudio, or when
    it will not start, the container uses the dummy audio driver (one line says so). Needs
    Docker and XQuartz with TCP connections enabled (`defaults write org.xquartz.X11
    nolisten_tcp -bool false`, then restart XQuartz). The container's venv is kept in a Docker
    volume between runs. Arguments after `--` replace the command, e.g. `nox -s test-linux-x11
    -- uv run pytest tests/animation`. `nox -s compare-drivers -- --drivers dummy,x11-linux`
    compares its frames with the dummy driver's.
    """
    command = session.posargs or [
        'sh',
        '-c',
        f'{_LINUX_X11_SYNC} && uv run pytest -p no:randomly -p no:cacheprovider',
    ]
    audio_driver = 'pulseaudio' if _start_pulseaudio(session) else 'dummy'
    _run_in_linux_x11_container(session, command=command, audio_driver=audio_driver)


@nox.session(venv_backend='none', name='build-sdl-x11', default=False)
def build_sdl_x11(session: nox.Session) -> None:
    """Build SDL with x11 for macOS, so pygame-ce draws on XQuartz (compare-drivers' x11-macos).

    pygame-ce's macOS SDL has no x11. scripts/build_sdl_x11.py builds the SDL version the wheel
    reports, from its GitHub release tarball (SHA-256 pinned per version), with x11 enabled
    against XQuartz (/opt/X11), into ~/Library/Caches/glitchygames/sdl-x11/<version>/ (reused
    when present), then checks that pygame opens and fills a window on XQuartz with
    SDL_DYNAMIC_API naming the library (SDL's dynamic API then runs it in place of the wheel's
    SDL). `nox -s compare-drivers` builds it when needed; this session builds and checks it
    alone. Arguments after `--` go to the script's build command (e.g. `--cache-root DIR`).
    """
    if sys.platform != 'darwin':
        session.error('SDL with x11 is built for macOS only (Linux has x11 in its own SDL)')
    _wait_for_xquartz(session)
    session.run(
        'uv',
        'run',
        'python',
        'scripts/build_sdl_x11.py',
        'build',
        '--check',
        *session.posargs,
        external=True,
    )


# compare-drivers: its output folder (test-results/ is git-ignored), its xdist workers per run
# (a modest count keeps the machine usable: the runs go one after another, and the container's
# run counts too; all cores starved other work), and the master seed each test's unseeded
# engines draw from (with its node id)
_COMPARE_DRIVERS_OUTPUT = Path('test-results/driver-comparison/nox')
# While a comparison runs, the last complete one waits here, and goes back to the output folder
# if this one fails (a run that recorded no test, a pytest that could not run, Ctrl-C); the
# failed comparison's runs are then kept in the failed folder for a look (BUGS.md #192)
_COMPARE_DRIVERS_PREVIOUS = Path('test-results/driver-comparison/nox-previous')
_COMPARE_DRIVERS_FAILED = Path('test-results/driver-comparison/nox-failed')
_COMPARE_DRIVERS_WORKERS = 4
_COMPARE_DRIVERS_SEED = 20261023
_FRAME_FINGERPRINTS_PLUGIN = 'glitchygames.testing.frame_fingerprints'
# pytest's exit codes the comparison continues after: all passed, or some tests failed (a
# failure on one configuration is a finding, reported with the frames)
_PYTEST_FINISHED_CODES = [0, 1]
_DRIVERS_OPTION = '--drivers'
_SOUND_OPTION = '--sound'


def _compare_drivers_arguments(session: nox.Session) -> tuple[str | None, bool, list[str]]:
    """Read compare-drivers' arguments: ``--drivers A,B``, ``--sound`` and the test selection.

    Args:
        session: The nox session (its posargs).

    Returns:
        The configurations asked for (None: every available one), whether the container plays
        sound through PulseAudio, and the remaining arguments (test paths; none: the suite).

    """
    arguments = list(session.posargs)
    drivers = None
    for index, argument in enumerate(arguments):
        if argument.startswith(f'{_DRIVERS_OPTION}='):
            drivers = argument.partition('=')[2]
            del arguments[index]
            break
        if argument == _DRIVERS_OPTION:
            if index + 1 >= len(arguments):
                session.error(f'{_DRIVERS_OPTION} takes a comma-separated list')
            drivers = arguments[index + 1]
            del arguments[index : index + 2]
            break
    sound = _SOUND_OPTION in arguments
    if sound:
        arguments.remove(_SOUND_OPTION)
    return drivers, sound, arguments


def _run_fingerprinted_tests(
    session: nox.Session,
    *,
    configuration: dict[str, Any],
    directory: Path,
    arguments: list[str],
    container_audio_driver: str = 'dummy',
) -> None:
    """Run tests on one driver configuration with the frame fingerprints plugin.

    Coverage is off (it would only slow the runs); the live log shows warnings only.

    Args:
        session: The nox session.
        configuration: A planned configuration (scripts/driver_configurations.py's
            ``PlannedConfiguration`` as JSON): its name, environment and where it runs.
        directory: The run's fingerprints directory (relative to the checkout).
        arguments: More pytest arguments (the test selection, the image request).
        container_audio_driver: The container's audio driver (``dummy`` or ``pulseaudio``).

    """
    environment: dict[str, str] = configuration['environment']
    pytest_arguments = [
        '-n',
        str(_COMPARE_DRIVERS_WORKERS),
        '--no-cov',
        '--log-cli-level=WARNING',
        f'--junitxml={directory}/junit.xml',
        '--hypothesis-seed=0',
        '-p',
        _FRAME_FINGERPRINTS_PLUGIN,
        f'--frame-fingerprints={directory}',
        f'--frame-fingerprints-seed={_COMPARE_DRIVERS_SEED}',
        *arguments,
    ]
    if configuration['runs_in_linux_container']:
        _run_in_linux_x11_container(
            session,
            command=[
                'sh',
                '-c',
                f'{_LINUX_X11_SYNC} && exec uv run pytest -p no:cacheprovider "$@"',
                'pytest',
                *pytest_arguments,
            ],
            video_driver=environment['SDL_VIDEODRIVER'],
            audio_driver=container_audio_driver,
            success_codes=_PYTEST_FINISHED_CODES,
        )
        return
    session.run(
        'uv',
        'run',
        'pytest',
        *pytest_arguments,
        env=environment,
        success_codes=_PYTEST_FINISHED_CODES,
        external=True,
    )


def _plan_driver_configurations(
    session: nox.Session, *, drivers: str | None, output: Path
) -> list[dict[str, Any]]:
    """Choose compare-drivers' configurations (scripts/driver_configurations.py), dummy first.

    Builds SDL with x11 when x11-macos is chosen.

    Args:
        session: The nox session.
        drivers: The configurations asked for (None: every available one).
        output: The comparison's folder (the plan goes in it).

    Returns:
        The planned configurations (``PlannedConfiguration`` as JSON).

    """
    plan_path = output / 'plan.json'
    session.run(
        'uv',
        'run',
        'python',
        '-m',
        'scripts.driver_configurations',
        'plan',
        f'--output={plan_path}',
        *([] if drivers is None else [f'{_DRIVERS_OPTION}={drivers}']),
        external=True,
    )
    return json.loads(plan_path.read_text(encoding='utf-8'))['configurations']


def _prepare_driver_configurations(
    session: nox.Session, *, configurations: list[dict[str, Any]], sound: bool
) -> str:
    """Start what the configurations need: XQuartz, PulseAudio (``--sound``); check x11-macos.

    Args:
        session: The nox session.
        configurations: The planned configurations.
        sound: The container plays its sound through the Mac's PulseAudio.

    Returns:
        The container's audio driver: ``pulseaudio``, or ``dummy``.

    """
    in_container = any(configuration['runs_in_linux_container'] for configuration in configurations)
    libraries = [
        configuration['environment']['SDL_DYNAMIC_API']
        for configuration in configurations
        if 'SDL_DYNAMIC_API' in configuration['environment']
    ]
    if in_container or libraries:
        _wait_for_xquartz(session)
    for library in libraries:
        session.run(
            'uv',
            'run',
            'python',
            'scripts/build_sdl_x11.py',
            'check',
            f'--library={library}',
            external=True,
        )
    if sound and in_container and _start_pulseaudio(session):
        return 'pulseaudio'
    return 'dummy'


def _run_timed_configurations(
    session: nox.Session,
    *,
    runs: list[tuple[dict[str, Any], str]],
    output: Path,
    arguments: list[str],
    container_audio_driver: str,
) -> Path:
    """Run the suite on each configuration, one after another, timing each run.

    Args:
        session: The nox session.
        runs: Each run's configuration and directory name.
        output: The comparison's folder.
        arguments: More pytest arguments (the test selection).
        container_audio_driver: The container's audio driver.

    Returns:
        The file of each run's seconds by its directory name (JSON).

    """
    run_seconds: dict[str, float] = {}
    for configuration, directory_name in runs:
        started = time.monotonic()
        _run_fingerprinted_tests(
            session,
            configuration=configuration,
            directory=output / directory_name,
            arguments=arguments,
            container_audio_driver=container_audio_driver,
        )
        run_seconds[directory_name] = time.monotonic() - started
        session.log(f'{directory_name}: {run_seconds[directory_name]:.0f} s')
    run_seconds_path = output / 'run-seconds.json'
    run_seconds_path.write_text(json.dumps(run_seconds, indent=2), encoding='utf-8')
    return run_seconds_path


def _set_aside_previous_comparison(*, output: Path, previous: Path) -> None:
    """Move the last complete comparison aside, and make the output folder empty for this one.

    A previous folder already there was left by a session that ended before it could put it
    back (killed): it is still the last complete comparison, so it stays, and the output folder
    (that session's unfinished runs) is removed.

    Args:
        output: The comparison's folder.
        previous: Where the last complete comparison waits.

    """
    if previous.exists():
        shutil.rmtree(output, ignore_errors=True)
    elif output.exists():
        output.rename(previous)
    output.mkdir(parents=True)


def _restore_previous_comparison(
    session: nox.Session, *, output: Path, previous: Path, failed: Path
) -> None:
    """Keep a failed comparison's runs in the failed folder; put the last complete one back.

    Args:
        session: The nox session (for its log).
        output: The comparison's folder, holding the failed comparison's runs.
        previous: Where the last complete comparison waits (absent: there was none).
        failed: Where the failed comparison's runs are kept (replacing an earlier failure's).

    """
    shutil.rmtree(failed, ignore_errors=True)
    if output.exists():
        output.rename(failed)
    if previous.exists():
        previous.rename(output)
        kept = f'the last complete comparison is still in {output}'
    else:
        kept = 'there is no earlier complete comparison'
    session.log(f'The comparison did not finish: its runs are in {failed}; {kept}')


@nox.session(venv_backend='none', name='compare-drivers', default=False)
def compare_drivers(session: nox.Session) -> None:
    """Compare the frames tests present on every SDL driver configuration available here.

    Every local `pytest` run compares the dummy driver with the native one already
    (tests/driver_comparison.py); this session is the on-demand, deeper check, an N-way matrix.
    The configurations (scripts/driver_configurations.py): `dummy` (the baseline), the native
    driver (`cocoa`, `windows`, `wayland` or `x11`), and on macOS `x11-macos` (x11 drawing on
    XQuartz through an SDL built with x11, `nox -s build-sdl-x11`, built here when needed) and
    `x11-linux` (the Linux container of `test-linux-x11`, forwarding to XQuartz: needs Docker).
    By default every configuration available here runs; `-- --drivers dummy,cocoa,x11-macos`
    chooses (dummy is always the baseline). Every configuration draws in software through the
    same code and the engine presents opaque frames, so a test should present the same pixels
    on each; a difference is a driver dependence (BUGS.md #142, #189).

    The frame fingerprints plugin (glitchygames/testing/frame_fingerprints.py) records every
    frame each test presents. The suite runs twice on dummy (tests whose frames differ between
    those runs are nondeterministic: listed apart, never counted as driver differences; mark
    them `@pytest.mark.frames_vary(reason=...)`) and once on each other configuration, one run
    after another with 4 workers each; scripts/driver_frame_matrix.py compares every pair. The
    differing tests are re-run on every configuration saving PNGs of their differing frames,
    and each differing pair gets a difference image (differing pixels magenta) under
    test-results/driver-comparison/nox/differences/<first>-vs-<second>/. The report,
    test-results/driver-comparison/nox/matrix.md, has each run's time, a summary per pair, the
    patterns of agreement and a table per test (first differing frame, differing pixels,
    linked images); the summary is printed at the end. It reports; it does not fail on a
    difference.

    It fails when a run recorded no test (pytest ran none: `-- --help` or `--collect-only`
    reach every run and exit 0), naming the run, rather than report that every configuration
    agrees (BUGS.md #192), and when a pytest run cannot run at all. A comparison that fails (or
    is interrupted) never replaces the last complete one: that one waits in
    test-results/driver-comparison/nox-previous/ while the comparison runs and goes back to
    nox/ when it fails, and the failed comparison's runs are kept in
    test-results/driver-comparison/nox-failed/.

    The container uses dummy audio; `--sound` plays its sound through the Mac's PulseAudio, as
    `test-linux-x11` does. Other arguments after `--` select tests, e.g. `nox -s
    compare-drivers -- tests/scenes`. The host runs use the project's own environment (`uv
    run`), as a developer's `uv run pytest` does; each names its driver, so none starts a
    comparison of its own.
    """
    drivers, sound, selection = _compare_drivers_arguments(session)
    output = _COMPARE_DRIVERS_OUTPUT
    _set_aside_previous_comparison(output=output, previous=_COMPARE_DRIVERS_PREVIOUS)
    try:
        _compare_driver_configurations(
            session, output=output, drivers=drivers, sound=sound, selection=selection
        )
    except BaseException:
        # Whatever ended it (a failed command, a refusal, Ctrl-C), the last complete comparison
        # stays the report
        _restore_previous_comparison(
            session,
            output=output,
            previous=_COMPARE_DRIVERS_PREVIOUS,
            failed=_COMPARE_DRIVERS_FAILED,
        )
        raise
    shutil.rmtree(_COMPARE_DRIVERS_PREVIOUS, ignore_errors=True)


def _compare_driver_configurations(
    session: nox.Session, *, output: Path, drivers: str | None, sound: bool, selection: list[str]
) -> None:
    """Run compare-drivers' comparison into its (empty) folder: see ``compare_drivers``.

    Args:
        session: The nox session.
        output: The comparison's folder.
        drivers: The configurations asked for (None: every available one).
        sound: The container plays its sound through the Mac's PulseAudio.
        selection: More pytest arguments (the test selection).

    """
    configurations = _plan_driver_configurations(session, drivers=drivers, output=output)
    container_audio_driver = _prepare_driver_configurations(
        session, configurations=configurations, sound=sound
    )
    runs = [
        (configuration, configuration['name'])
        for configuration in configurations
        if configuration['name'] != 'dummy'
    ]
    runs[:0] = [(configurations[0], 'dummy-1'), (configurations[0], 'dummy-2')]
    run_seconds_path = _run_timed_configurations(
        session,
        runs=runs,
        output=output,
        arguments=selection,
        container_audio_driver=container_audio_driver,
    )
    matrix_command = [
        'uv',
        'run',
        'python',
        '-m',
        'scripts.driver_frame_matrix',
        *(
            f'{configuration["name"]}={output / directory_name}'
            for configuration, directory_name in runs
        ),
        f'--output={output}',
        f'--run-seconds={run_seconds_path}',
    ]
    request = output / 'image-request.json'
    summary = session.run(*matrix_command, f'--image-request={request}', external=True, silent=True)
    differing_tests = list(json.loads(request.read_text(encoding='utf-8'))['positions_by_test'])
    if not differing_tests:
        session.log(f'No driver differences: nothing to re-run\n{summary}')
        return
    # One node id per line, passed as @FILE: node ids may hold spaces
    tests_file = output / 'differing-tests.txt'
    tests_file.write_text('\n'.join(differing_tests) + '\n', encoding='utf-8')
    reruns = [
        (configuration, f'{configuration["name"]}-images') for configuration in configurations
    ]
    for configuration, directory_name in reruns:
        _run_fingerprinted_tests(
            session,
            configuration=configuration,
            directory=output / directory_name,
            arguments=[f'--frame-images-request={request}', f'@{tests_file}'],
            container_audio_driver=container_audio_driver,
        )
    session.run(
        *matrix_command,
        *(
            f'--rerun={configuration["name"]}={output / directory_name}'
            for configuration, directory_name in reruns
        ),
        external=True,
    )


@nox.session(venv_backend='none', name='browser', default=False)
def browser(session: nox.Session) -> None:
    """Build a game for the browser (PyScript, Pyodide 314) and serve it on localhost.

    scripts/build_browser_bundle.py writes build/browser/<game>: the page, the engine and our
    pygame-ce wheel. The wheel is built from the third_party/pygame-ce submodule the first time
    (several minutes; run ``git submodule update --init`` first) and reused while the submodule
    stays at the same commit. The page opens in the default browser; click it to play. Design:
    plans/2026-10-23-game-host-and-browser-runner.md.

    Usage:
        nox -s browser                                   # PaddleSlap
        nox -s browser -- mr-muncher                     # Another game
        nox -s browser -- clockwork-keep --port 9000     # Builder options after the game
        nox -s browser -- paddleslap -- --target-fps 30  # The game's own options after a --
    """
    arguments = session.posargs or ['paddleslap']
    session.run(
        'uv',
        'run',
        '--frozen',
        'python',
        'scripts/build_browser_bundle.py',
        # Before the game's own arguments, which may follow a -- that ends the builder's options
        '--serve',
        *arguments,
        external=True,
        # Unset (nox drops None): a session's own venv is not the project's, and uv would warn
        env={'VIRTUAL_ENV': None},
    )


@nox.session(python=['3.14'], reuse_venv=False, name='timer-report', default=False)
def timer_report(session: nox.Session) -> None:
    """Report this machine's timer accuracy (diagnostic; always succeeds).

    The same command on every OS: scripts/timer_report.py detects the OS itself (macOS's
    kern.hv_vmm_present, Linux's hypervisor CPU flag) for whether it runs in a VM, then measures
    the CPU share and how late FastTimer, time.sleep and spin-only sleeps wake.
    """
    _install_from_lockfile(session, all_extras=False)
    session.run('python', 'scripts/timer_report.py')


@nox.session(python=['3.14'], reuse_venv=False, name='performance-test', default=False)
def performance_test(session: nox.Session) -> None:
    """Run performance benchmarks."""
    _install_from_lockfile(session)

    # Run performance tests with pytest-benchmark
    # Override addopts to avoid conflict with --cov flags from pyproject.toml
    session.run(
        'pytest',
        '-o',
        'addopts=',
        '-p',
        'no:xdist',
        '--benchmark-only',
        '--benchmark-save=baseline',
        'tests/',
    )


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------


def _bandit_scan(session: nox.Session) -> None:
    """Run bandit security scan (exclude_dirs configured in pyproject.toml)."""
    session.run(
        'bandit',
        '-c',
        'pyproject.toml',
        '-ll',  # Medium+ severity
        '-ii',  # Medium+ confidence
        '-r',
        'glitchygames',
        '-f',
        'json',
        '-o',
        'bandit-report.json',
    )


def _safety_scan(session: nox.Session) -> None:
    """Run safety check for known vulnerabilities."""
    if not os.getenv('SAFETY_API_KEY'):
        session.log('SAFETY_API_KEY not set; skipping Safety scan.')
        return

    session.run(
        'safety',
        'scan',
        '--exclude',
        '.venv',
        '--exclude',
        '.nox',
        '--output',
        'screen',
        '--save-as',
        'json',
        'safety-report.json',
    )


@nox.session(python=['3.14'], reuse_venv=False, name='bandit-scan', default=False)
def bandit_scan(session: nox.Session) -> None:
    """Run bandit security scan."""
    _install_from_lockfile(session)
    _bandit_scan(session)


@nox.session(python=['3.14'], reuse_venv=False, name='safety-scan', default=False)
def safety_scan(session: nox.Session) -> None:
    """Run safety vulnerability scan."""
    _install_from_lockfile(session)
    _safety_scan(session)


@nox.session(python=['3.14'], reuse_venv=False, name='security-scan', default=False)
def security_scan(session: nox.Session) -> None:
    """Run all security scanning tools (bandit + safety)."""
    _install_from_lockfile(session)
    _bandit_scan(session)
    _safety_scan(session)


# ---------------------------------------------------------------------------
# Build / Package
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _build_stamp(session: nox.Session) -> Generator[None]:
    """Write the engine's build stamp for the builds inside, and remove it after.

    A packaged engine has no git checkout, so the stamp (glitchygames/_build_info.json, gitignored,
    packaged through hatch's ``artifacts``) carries the commit it was built from and whether the
    checkout had uncommitted changes (glitchygames/build_info.py). It is removed afterwards so no
    stale stamp reaches a later build. Written before the session installs the package
    (``--no-editable`` builds it), so the installed copy PyInstaller collects has it too.

    Args:
        session: The nox session building.

    Yields:
        Nothing; the builds run inside.

    """
    session.run('uv', 'run', '--frozen', 'python', 'scripts/write_build_stamp.py', external=True)
    try:
        yield
    finally:
        session.run(
            'uv',
            'run',
            '--frozen',
            'python',
            'scripts/write_build_stamp.py',
            '--remove',
            external=True,
        )


def _build_binary(session: nox.Session) -> None:
    """Build a standalone Bitmappy binary with PyInstaller."""
    session.run(
        'pyinstaller',
        'bitmappy.spec',
        '--distpath',
        'dist',
        '--workpath',
        'build/pyinstaller',
        '--noconfirm',
    )


def _build_wheel(session: nox.Session) -> None:
    """Build a wheel package with uv build."""
    session.run('uv', 'build', '--wheel', '--out-dir', 'dist', external=True)


@nox.session(python=['3.14'], reuse_venv=False, name='build-binary', default=False)
def build_binary(session: nox.Session) -> None:
    """Build a standalone Bitmappy binary with PyInstaller.

    Outputs a single-file executable to dist/:
      - Linux:   dist/bitmappy
      - macOS:   dist/bitmappy
      - Windows: dist/bitmappy.exe

    Usage:
        nox -s build-binary
    """
    with _build_stamp(session):
        _install_from_lockfile(session)
        _build_binary(session)


@nox.session(venv_backend='none', name='build-wheel', default=False)
def build_wheel(session: nox.Session) -> None:
    """Build a wheel package (.whl) for distribution.

    Usage:
        nox -s build-wheel
    """
    with _build_stamp(session):
        _build_wheel(session)


@nox.session(python=['3.14'], reuse_venv=False, name='build', default=False)
def build_all(session: nox.Session) -> None:
    """Build Bitmappy binary and wheel package.

    Usage:
        nox -s build
    """
    with _build_stamp(session):
        _install_from_lockfile(session)
        _build_binary(session)
        _build_wheel(session)


# ---------------------------------------------------------------------------
# Code Complexity
# ---------------------------------------------------------------------------


@nox.session(python=['3.14'], reuse_venv=False, name='code-complexity', default=False)
def code_complexity(session: nox.Session) -> None:
    """Analyze code complexity with wily and generate optional HTML graphs.

    Tools: complexity_report.py (wily: the working tree's changes against HEAD, the history measured
    in a temporary worktree so the working tree is never checked out over), and
    generate_complexity_graphs.py (the docs' graphs, generated in a temporary worktree from the
    whole history into docs/quality/graphs/, which git ignores; every mkdocs build does too)

    Usage:
        nox -s code-complexity              # The working tree's changes against HEAD
        nox -s code-complexity -- --graphs  # Also generate the docs' complexity graphs
        nox -s code-complexity -- --rank    # Show files ranked by complexity
    """
    _install_from_lockfile(session)

    # The working tree against HEAD, its history measured in a temporary worktree: wily build
    # checks each revision out where it runs, which in the working tree would rewrite the files
    # being worked on (scripts/complexity_report.py)
    rank_arguments = ['--rank'] if '--rank' in session.posargs else []
    # As a module from the project root: the session installs the package (not editable), so the
    # script's own `from scripts...` import needs the root on sys.path, which -m gives it
    session.run('python', '-m', 'scripts.complexity_report', *rank_arguments)

    # Optional: generate graphs for documentation
    if '--graphs' in session.posargs:
        session.run('python', 'scripts/generate_complexity_graphs.py')
