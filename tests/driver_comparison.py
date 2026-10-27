"""Every local test run draws on two SDL video drivers and fails on a frame they disagree on.

The dummy driver and the platform's native one (macOS cocoa, Windows windows, Linux wayland or
x11) draw in software through the same code and the engine presents opaque frames
(glitchygames/opacity.py), so a test should present the same pixels on both; a difference is a
driver dependence (BUGS.md #142, #189). Outside CI, a pytest run therefore:

1. runs the suite on the dummy driver in this process (and its xdist workers), as always,
   recording every presented frame (glitchygames/testing/frame_fingerprints.py, asked through
   its environment variables), and coverage is measured here alone, so the 99% gate is the
   dummy run's, as before;
2. runs the same command on the native driver in a child pytest started at the session's start
   (``NATIVE_WORKER_SHARE`` of the usual workers go to it, the rest stay here: the native run is
   slower per test, and the two together never use more workers than one run would), with its
   output in ``test-results/driver-comparison/pytest/native/pytest.log``;
3. at the session's end compares the two runs' frames (glitchygames/testing/frame_comparison.py),
   re-runs any differing tests on both drivers saving PNG files of the differing frames and a
   difference image, and reports them in the terminal summary. A driver difference, or a failure
   in the native run, fails this run.

Tests marked ``@pytest.mark.frames_vary(reason=...)`` are listed, not compared: their frames are
not expected to match between runs or drivers (they hold measured frame times, or the live
window's mouse focus, which the dummy driver always reports). A marker keeps the reason next to
the test, where a review sees it, and moves with the test; a list kept apart would go stale.

The comparison is off (the run is dummy only, as before, and the summary says why) in CI (the
``CI`` variable is ``true``, as CircleCI and GitHub Actions set it), with ``--dummy-only`` (fast
iteration), when the invoker set SDL_VIDEODRIVER or SDL_AUDIODRIVER (that driver alone runs:
tests/sdl_defaults.py), on Linux without WAYLAND_DISPLAY or DISPLAY (no native display), for
``--collect-only``, and in any pytest started inside a comparison (its native run, an xdist
worker, a pytest a test starts). GLITCHYGAMES_COMPARE_WITH_DRIVER names another driver to compare
with (``dummy`` checks the comparison itself).
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from typing import TYPE_CHECKING, TextIO

import pytest
from pydantic import BaseModel, ConfigDict

from glitchygames.process import (
    RunningProcess,
    TimeoutExpired,
    start_command,
    stop_command,
    with_options_appended,
)
from glitchygames.testing.frame_comparison import (
    LabelledRun,
    compare_labelled_runs,
    comparison_report,
    image_request_for,
    images_report,
)
from glitchygames.testing.frame_fingerprints import (
    FINGERPRINTS_OPTION,
    FINGERPRINTS_VARIABLE,
    IMAGES_REQUEST_OPTION,
    OWNER_VARIABLE,
    SEED_OPTION,
    SEED_VARIABLE,
    FrameImageRequest,
)
from tests.sdl_defaults import SDL_DRIVER_VARIABLES, SDL_VARIABLES_DEFAULTED_AT_STARTUP

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

DUMMY_ONLY_OPTION = '--dummy-only'
# Names the video driver to compare with instead of the native one (dummy checks the comparison
# itself: tests/test_driver_comparison.py); its audio driver is the native one's for a native
# video driver, else dummy
COMPARE_WITH_VARIABLE = 'GLITCHYGAMES_COMPARE_WITH_DRIVER'
# Set in this process's environment while a comparison runs: every pytest started from here on
# (the native run, xdist workers, a pytest a test starts) runs its own driver only
COMPARISON_ACTIVE_VARIABLE = 'GLITCHYGAMES_DRIVER_COMPARISON_ACTIVE'
CI_VARIABLE = 'CI'
DUMMY_DRIVER = 'dummy'
# Where the runs' frames, logs and difference images go (test-results/ is git-ignored)
OUTPUT_PARTS = ('test-results', 'driver-comparison', 'pytest')
# Each test's unseeded engine master seeds come from this and its node id in both runs, so a
# test that draws random pictures draws the same ones on both drivers
COMPARISON_SEED = 20261023
# The native run's share of the usual xdist workers: cocoa ran the suite about three times
# slower per test than dummy, so it gets two thirds and both runs end at about the same time
NATIVE_WORKER_SHARE = 2 / 3
# The most workers a re-run of the differing tests uses (it saves images of a few tests)
IMAGE_RUN_MAXIMUM_WORKERS = 4
# How long the native run and the image re-runs may take before they are stopped
NATIVE_RUN_TIMEOUT_SECONDS = 3600.0
IMAGE_RUN_TIMEOUT_SECONDS = 900.0
# macOS: a window of the native run must not activate its app (take keyboard focus from the
# person typing while the tests run)
MAC_BACKGROUND_APP_VARIABLE = 'SDL_MAC_BACKGROUND_APP'
# The pytest exit codes of a native run with nothing wrong: all passed, or no tests collected
NATIVE_RUN_SUCCESS_CODES = frozenset({pytest.ExitCode.OK, pytest.ExitCode.NO_TESTS_COLLECTED})
# The audio driver that goes with each native video driver
NATIVE_AUDIO_DRIVERS = {'cocoa': 'coreaudio', 'windows': 'wasapi'}
# pytest-cov's plugin name (its --no-cov exists only while it is loaded)
COVERAGE_PLUGIN_NAME = '_cov'
SUMMARY_TITLE = 'driver comparison'
# The second (native) run's directory under the comparison's
NATIVE_DIRECTORY_NAME = 'native'
# The short test summary lines of a failed native run, as its log holds them
FAILURE_SUMMARY_PREFIXES = ('FAILED ', 'ERROR ')

_SKIP_REASON_KEY = pytest.StashKey[str | None]()


class NativeDrivers(BaseModel):
    """The SDL video and audio drivers of the platform's own display and sound."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    video: str
    audio: str


def native_drivers(*, platform: str, environment: Mapping[str, str]) -> NativeDrivers | None:
    """Return the platform's native SDL drivers, if it has a display to draw on.

    Linux's sound servers vary (and containers have none), so its native run keeps the dummy
    audio driver, as ``nox -s test-linux-x11`` does.

    Args:
        platform: ``sys.platform``.
        environment: The process environment (WAYLAND_DISPLAY, DISPLAY).

    Returns:
        The driver GLITCHYGAMES_COMPARE_WITH_DRIVER names, when set; else cocoa and coreaudio on
        macOS, windows and wasapi on Windows, wayland (when WAYLAND_DISPLAY is set) or x11 (when
        DISPLAY is) with dummy audio on Linux; None for a Linux without a display, or another
        platform.

    """
    named = environment.get(COMPARE_WITH_VARIABLE)
    if named:
        return NativeDrivers(video=named, audio=NATIVE_AUDIO_DRIVERS.get(named, DUMMY_DRIVER))
    if platform == 'darwin':
        return NativeDrivers(video='cocoa', audio='coreaudio')
    if platform == 'win32':
        return NativeDrivers(video='windows', audio='wasapi')
    if platform.startswith('linux'):
        if environment.get('WAYLAND_DISPLAY'):
            return NativeDrivers(video='wayland', audio=DUMMY_DRIVER)
        if environment.get('DISPLAY'):
            return NativeDrivers(video='x11', audio=DUMMY_DRIVER)
    return None


def comparison_skip_reason(
    *,
    environment: Mapping[str, str],
    platform: str,
    variables_defaulted: Sequence[str],
    dummy_only: bool,
    collect_only: bool,
) -> str | None:
    """Tell why this run does not compare drivers, or None when it does.

    Args:
        environment: The process environment.
        platform: ``sys.platform``.
        variables_defaulted: The SDL driver variables tests/sdl_defaults.py defaulted (the
            invoker set the others).
        dummy_only: ``--dummy-only`` was given.
        collect_only: The run only collects.

    Returns:
        The reason, for the terminal summary, or None to compare.

    """
    set_by_invoker = [name for name in SDL_DRIVER_VARIABLES if name not in variables_defaulted]
    # In order: the first that holds is the reason
    reasons = (
        (
            bool(environment.get(COMPARISON_ACTIVE_VARIABLE)),
            'a pytest run inside a driver comparison',
        ),
        (environment.get(CI_VARIABLE) == 'true', 'CI runs the dummy driver only'),
        (dummy_only, f'{DUMMY_ONLY_OPTION} given'),
        (
            bool(set_by_invoker),
            f'{" and ".join(set_by_invoker)} set by the invoker: that driver only',
        ),
        (collect_only, 'collection only'),
        (
            native_drivers(platform=platform, environment=environment) is None,
            f'no native display on {platform} (no WAYLAND_DISPLAY or DISPLAY)',
        ),
    )
    return next((reason for holds, reason in reasons if holds), None)


def split_workers(*, workers: int) -> tuple[int, int]:
    """Split the usual xdist worker count between the dummy and the native run.

    Args:
        workers: The worker count this run would use alone (0: no workers, run in process).

    Returns:
        The dummy run's and the native run's workers: together the usual count, the native run
        taking NATIVE_WORKER_SHARE, each at least one; with fewer than two workers both runs
        get the usual count.

    """
    if workers < 2:
        return workers, workers
    native = min(workers - 1, max(1, round(workers * NATIVE_WORKER_SHARE)))
    return workers - native, native


def child_pytest_command(
    *, arguments: Sequence[str], workers: int | None, coverage_loaded: bool, directory: Path
) -> list[str]:
    """Build a child pytest command that writes its results to a directory.

    Args:
        arguments: pytest's own arguments (this run's, for the native run).
        workers: Its xdist worker count, or None when xdist is not loaded.
        coverage_loaded: pytest-cov is loaded (the child measures no coverage: ``--no-cov``).
        directory: The child's directory (JUnit XML, cache).

    Returns:
        The command: this interpreter running pytest with the arguments, then the child's
        options (later options win).

    """
    appended = [
        *([] if workers is None else ['-n', str(workers)]),
        *(['--no-cov'] if coverage_loaded else []),
        f'--junitxml={directory / "junit.xml"}',
        '-o',
        f'cache_dir={directory / "cache"}',
    ]
    return [
        sys.executable,
        '-m',
        'pytest',
        *with_options_appended(arguments=arguments, appended=appended),
    ]


def driver_environment(*, environment: Mapping[str, str], drivers: NativeDrivers) -> dict[str, str]:
    """Return a child run's environment: this one on the given drivers, recording by option.

    The recording variables (this run's) are dropped: a child records only by the options its
    command gives it.

    Args:
        environment: This process's environment.
        drivers: The child's SDL video and audio drivers.

    Returns:
        The child's whole environment.

    """
    child_environment = {
        name: value
        for name, value in environment.items()
        if name not in {FINGERPRINTS_VARIABLE, SEED_VARIABLE, OWNER_VARIABLE}
    }
    child_environment.update({
        'SDL_VIDEODRIVER': drivers.video,
        'SDL_AUDIODRIVER': drivers.audio,
        COMPARISON_ACTIVE_VARIABLE: '1',
        MAC_BACKGROUND_APP_VARIABLE: '1',
    })
    return child_environment


def failure_summary_lines(*, log_text: str) -> list[str]:
    """Return a pytest log's short test summary lines of failures and errors.

    Args:
        log_text: The log.

    Returns:
        The ``FAILED ...`` and ``ERROR ...`` lines, in order.

    """
    return [line for line in log_text.splitlines() if line.startswith(FAILURE_SUMMARY_PREFIXES)]


class DriverComparison:
    """The plugin object of one comparing run: starts the native run, compares, reports."""

    def __init__(
        self,
        *,
        config: pytest.Config,
        native: NativeDrivers,
        native_workers: int | None,
        output: Path,
    ) -> None:
        """Prepare a comparison (its directories are made when the session starts).

        Args:
            config: pytest's configuration.
            native: The native drivers.
            native_workers: The native run's xdist workers (None without xdist).
            output: The comparison's directory.

        """
        self.config = config
        self.native = native
        self.native_workers = native_workers
        self.output = output
        # The second run's label: its driver, told apart from the first when that is dummy too
        self.native_label = native.video if native.video != DUMMY_DRIVER else f'{DUMMY_DRIVER}-2'
        self.dummy_directory = output / DUMMY_DRIVER
        self.native_directory = output / NATIVE_DIRECTORY_NAME
        self.native_process: RunningProcess[str] | None = None
        self.native_log: TextIO | None = None
        self.native_started = 0.0
        self.summary_lines: list[str] = []
        # A driver difference or a failed native run: this run fails
        self.failed = False

    @property
    def coverage_loaded(self) -> bool:
        """Whether pytest-cov is loaded (so a child can be given ``--no-cov``)."""
        return self.config.pluginmanager.has_plugin(COVERAGE_PLUGIN_NAME)

    def pytest_sessionstart(self) -> None:
        """Start the native run alongside this one."""
        shutil.rmtree(self.output, ignore_errors=True)
        self.native_directory.mkdir(parents=True)
        self.dummy_directory.mkdir(parents=True)
        command = with_options_appended(
            arguments=child_pytest_command(
                arguments=self.config.invocation_params.args,
                workers=self.native_workers,
                coverage_loaded=self.coverage_loaded,
                directory=self.native_directory,
            ),
            appended=[
                f'{FINGERPRINTS_OPTION}={self.native_directory}',
                f'{SEED_OPTION}={COMPARISON_SEED}',
            ],
        )
        self.native_log = (self.native_directory / 'pytest.log').open('w', encoding='utf-8')
        self.native_started = time.monotonic()
        self.native_process = start_command(
            command=command,
            environment=driver_environment(environment=os.environ, drivers=self.native),
            output=self.native_log,
        )

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        """Wait for the native run, compare the frames, and fail this run on a difference.

        Args:
            session: The session.
            exitstatus: This run's exit status so far.

        """
        process = self.native_process
        if process is None:
            return
        if exitstatus == pytest.ExitCode.INTERRUPTED:
            self.stop_native_run()
            self.summary_lines = [f'stopped: the run was interrupted ({self.native_label} run too)']
            return
        try:
            returncode = process.wait(timeout=NATIVE_RUN_TIMEOUT_SECONDS)
        except TimeoutExpired:
            self.stop_native_run()
            returncode = None
        native_seconds = time.monotonic() - self.native_started
        self.close_native_log()
        self.summary_lines = self.compare(returncode=returncode, native_seconds=native_seconds)
        if self.failed and session.exitstatus == pytest.ExitCode.OK:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED

    def compare(self, *, returncode: int | None, native_seconds: float) -> list[str]:
        """Compare the runs' frames and make the summary; images for any difference.

        Args:
            returncode: The native run's exit code (None: stopped after its timeout).
            native_seconds: How long the native run took.

        Returns:
            The summary lines.

        """
        log_path = self.native_directory / 'pytest.log'
        lines = [
            (
                f'{self.native_label} run: exit {returncode} after {native_seconds:.1f} s '
                f'({self.native_workers} workers); its output: {log_path}'
            )
        ]
        if returncode not in NATIVE_RUN_SUCCESS_CODES:
            self.failed = True
            failures = failure_summary_lines(log_text=log_path.read_text(encoding='utf-8'))
            lines.append(f'The {self.native_label} run failed ({len(failures)} listed):')
            lines.extend(f'  {line}' for line in failures)
        runs = [
            LabelledRun(label=DUMMY_DRIVER, directory=self.dummy_directory),
            LabelledRun(label=self.native_label, directory=self.native_directory),
        ]
        repeats, drivers = compare_labelled_runs(runs=runs)
        lines.extend(comparison_report(repeats=repeats, drivers=drivers).splitlines())
        request = image_request_for(drivers=drivers)
        if request.positions_by_test:
            self.failed = True
            lines.extend(self.save_difference_images(request=request))
        return lines

    def save_difference_images(self, *, request: FrameImageRequest) -> list[str]:
        """Re-run the differing tests on both drivers saving their differing frames; compare.

        Args:
            request: The frames to save (positions by node id).

        Returns:
            The images report's lines.

        """
        request_path = self.output / 'image-request.json'
        request_path.write_text(request.model_dump_json(indent=2), encoding='utf-8')
        tests_path = self.output / 'differing-tests.txt'
        # One node id per line, passed as @FILE: node ids may hold spaces
        tests_path.write_text('\n'.join(request.positions_by_test) + '\n', encoding='utf-8')
        workers = (
            None
            if self.native_workers is None
            else min(IMAGE_RUN_MAXIMUM_WORKERS, len(request.positions_by_test))
        )
        reruns = [
            (DUMMY_DRIVER, NativeDrivers(video=DUMMY_DRIVER, audio=DUMMY_DRIVER)),
            (self.native_label, self.native),
        ]
        processes: list[tuple[RunningProcess[str], TextIO]] = []
        for label, drivers in reruns:
            directory = self.output / f'{label}-images'
            directory.mkdir(parents=True)
            command = child_pytest_command(
                arguments=[
                    f'{IMAGES_REQUEST_OPTION}={request_path}',
                    f'{FINGERPRINTS_OPTION}={directory}',
                    f'{SEED_OPTION}={COMPARISON_SEED}',
                    f'@{tests_path}',
                ],
                workers=workers,
                coverage_loaded=self.coverage_loaded,
                directory=directory,
            )
            log = (directory / 'pytest.log').open('w', encoding='utf-8')
            processes.append((
                start_command(
                    command=command,
                    environment=driver_environment(environment=os.environ, drivers=drivers),
                    output=log,
                ),
                log,
            ))
        for process, log in processes:
            try:
                process.wait(timeout=IMAGE_RUN_TIMEOUT_SECONDS)
            except TimeoutExpired:
                stop_command(process=process)
            log.close()
        return images_report(
            request=request,
            baseline=LabelledRun(label=DUMMY_DRIVER, directory=self.output / 'dummy-images'),
            candidate=LabelledRun(
                label=self.native_label, directory=self.output / f'{self.native_label}-images'
            ),
            output=self.output / 'differences',
        ).splitlines()

    def stop_native_run(self) -> None:
        """Stop the native run (with its workers) if it is still running."""
        if self.native_process is not None:
            stop_command(process=self.native_process)
        self.close_native_log()

    def close_native_log(self) -> None:
        """Close the native run's log file, if open."""
        if self.native_log is not None:
            self.native_log.close()
            self.native_log = None

    def pytest_unconfigure(self) -> None:
        """Never leave the native run behind (an error or Ctrl-C ended this run early)."""
        self.stop_native_run()


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add ``--dummy-only``.

    Args:
        parser: pytest's option parser.

    """
    parser.addoption(
        DUMMY_ONLY_OPTION,
        action='store_true',
        default=False,
        help='run on the dummy SDL driver only: no comparison with the native driver (fast)',
    )


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    """Decide whether this run compares drivers; if so, set it up before the others configure.

    First (tryfirst): the frame fingerprints plugin reads its variables, and xdist its worker
    count, after this.

    Args:
        config: pytest's configuration.

    """
    is_worker = hasattr(config, 'workerinput')
    skip_reason = (
        'an xdist worker'
        if is_worker
        else comparison_skip_reason(
            environment=os.environ,
            platform=sys.platform,
            variables_defaulted=SDL_VARIABLES_DEFAULTED_AT_STARTUP,
            dummy_only=config.getoption(DUMMY_ONLY_OPTION),
            collect_only=config.getoption('collectonly'),
        )
    )
    config.stash[_SKIP_REASON_KEY] = skip_reason
    native = native_drivers(platform=sys.platform, environment=os.environ)
    if skip_reason is not None or native is None:
        return
    # xdist turned its worker count into one 'popen' gateway each (config.option.tx) when the
    # command line was read; no gateways (or no xdist): this run runs its tests itself
    gateways: list[str] | None = getattr(config.option, 'tx', None)
    native_workers: int | None = None
    if gateways is not None:
        dummy_workers, native_workers = split_workers(workers=len(gateways))
        config.option.tx = gateways[:dummy_workers]
        config.option.numprocesses = dummy_workers
    output = config.rootpath.joinpath(*OUTPUT_PARTS)
    comparison = DriverComparison(
        config=config, native=native, native_workers=native_workers, output=output
    )
    # This run (and its workers) record the dummy frames; everything started from here on
    # runs its own driver only
    os.environ[FINGERPRINTS_VARIABLE] = str(comparison.dummy_directory)
    os.environ[SEED_VARIABLE] = str(COMPARISON_SEED)
    os.environ[OWNER_VARIABLE] = str(os.getpid())
    os.environ[COMPARISON_ACTIVE_VARIABLE] = '1'
    config.pluginmanager.register(comparison, name=SUMMARY_TITLE)


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter, config: pytest.Config
) -> None:
    """Report the comparison, or why this run is on one driver only.

    Args:
        terminalreporter: The terminal reporter.
        config: pytest's configuration.

    """
    comparison = config.pluginmanager.get_plugin(SUMMARY_TITLE)
    if isinstance(comparison, DriverComparison):
        terminalreporter.write_sep(
            '=', f'{SUMMARY_TITLE}: {DUMMY_DRIVER} vs {comparison.native_label}'
        )
        for line in comparison.summary_lines:
            terminalreporter.write_line(line)
        return
    skip_reason = config.stash.get(_SKIP_REASON_KEY, None)
    if skip_reason is not None:
        terminalreporter.write_line(
            f'{SUMMARY_TITLE}: off ({skip_reason}); this run used one driver'
        )
