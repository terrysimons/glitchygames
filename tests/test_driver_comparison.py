"""tests/driver_comparison.py: a local run compares the dummy driver's frames with the native's.

The decisions (which drivers, whether to compare, how the workers are split, the child's command
and environment) are tested directly. The whole comparison runs end to end in a pytest
subprocess (pytester) comparing dummy with dummy (GLITCHYGAMES_COMPARE_WITH_DRIVER), so it runs
on every machine; an inner test that draws differently in the comparison's second run stands in
for a driver difference.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

from glitchygames.testing.frame_fingerprints import (
    FINGERPRINTS_OPTION,
    FINGERPRINTS_VARIABLE,
    OWNER_VARIABLE,
    SEED_VARIABLE,
)
from tests.driver_comparison import (
    CI_VARIABLE,
    COMPARE_WITH_VARIABLE,
    COMPARISON_ACTIVE_VARIABLE,
    DUMMY_ONLY_OPTION,
    MAC_BACKGROUND_APP_VARIABLE,
    OUTPUT_PARTS,
    NativeDrivers,
    child_pytest_command,
    comparison_skip_reason,
    driver_environment,
    failure_summary_lines,
    native_drivers,
    split_workers,
)
from tests.sdl_defaults import SDL_DRIVER_VARIABLES

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# A pytest run of the inner project (two runs, and two image re-runs) takes a few seconds
SUBPROCESS_TIMEOUT_SECONDS = 300
# The inner project loads the comparison and the recorder as this project's root conftest does
INNER_CONFTEST = textwrap.dedent(
    """
    pytest_plugins = ['tests.driver_comparison', 'glitchygames.testing.frame_fingerprints']
    """
)
# The inner tests' window: at least 72 wide, which every window manager (XQuartz's) allows
INNER_WINDOW_SIZE = (96, 64)
INNER_WINDOW_PIXELS = INNER_WINDOW_SIZE[0] * INNER_WINDOW_SIZE[1]
# Inner tests: one draws the same in both runs; one draws red in the first run and its re-run
# (recording into dummy/ and dummy-images/) and green in the second run and its re-run
INNER_TESTS = textwrap.dedent(
    f"""
    import os
    from pathlib import Path

    import pygame


    def present(color):
        pygame.init()
        display = pygame.display.set_mode({INNER_WINDOW_SIZE})
        display.fill(color)
        pygame.display.flip()


    def test_same_everywhere():
        present((10, 20, 30))


    def test_differs_in_the_second_run(request):
        # Not recording at all (--dummy-only): a first run
        directory = request.config.getoption({FINGERPRINTS_OPTION!r}) or os.environ.get(
            {FINGERPRINTS_VARIABLE!r}, 'dummy'
        )
        first_run = Path(directory).name in {{'dummy', 'dummy-images'}}
        present((200, 0, 0) if first_run else (0, 200, 0))
    """
)
DIFFERING_TEST = 'test_inner.py::test_differs_in_the_second_run'


def no_comparison_environment(**overrides: str) -> dict[str, str]:
    """Return an environment in which nothing stops a comparison, with overrides.

    Returns:
        No comparison, CI or SDL driver variables; the overrides added.

    """
    return {'HOME': '/home/tester', **overrides}


class TestNativeDrivers:
    """native_drivers picks the platform's own display and sound drivers."""

    @pytest.mark.parametrize(
        ('platform', 'environment', 'expected'),
        [
            ('darwin', {}, NativeDrivers(video='cocoa', audio='coreaudio')),
            ('win32', {}, NativeDrivers(video='windows', audio='wasapi')),
            (
                'linux',
                {'WAYLAND_DISPLAY': 'wayland-0', 'DISPLAY': ':0'},
                NativeDrivers(video='wayland', audio='dummy'),
            ),
            ('linux', {'DISPLAY': ':0'}, NativeDrivers(video='x11', audio='dummy')),
            ('linux', {}, None),
            ('freebsd14', {'DISPLAY': ':0'}, None),
            (
                'linux',
                {COMPARE_WITH_VARIABLE: 'dummy'},
                NativeDrivers(video='dummy', audio='dummy'),
            ),
            (
                'linux',
                {COMPARE_WITH_VARIABLE: 'cocoa'},
                NativeDrivers(video='cocoa', audio='coreaudio'),
            ),
        ],
        ids=[
            'macOS',
            'Windows',
            'Linux Wayland first',
            'Linux X11',
            'Linux without a display',
            'another platform',
            'named driver',
            'named native driver keeps its audio',
        ],
    )
    def test_the_platforms_drivers(self, platform, environment, expected):
        """By platform, and on Linux by the display variables; a named driver wins."""
        assert native_drivers(platform=platform, environment=environment) == expected


class TestSkipReason:
    """comparison_skip_reason: why a run stays on one driver (None: it compares)."""

    def test_a_plain_local_run_compares(self):
        """No reason on macOS with both SDL variables defaulted."""
        assert (
            comparison_skip_reason(
                environment=no_comparison_environment(),
                platform='darwin',
                variables_defaulted=SDL_DRIVER_VARIABLES,
                dummy_only=False,
                collect_only=False,
            )
            is None
        )

    @pytest.mark.parametrize(
        ('case', 'reason'),
        [
            ({'environment': {COMPARISON_ACTIVE_VARIABLE: '1'}}, 'inside a driver comparison'),
            ({'environment': {CI_VARIABLE: 'true'}}, 'CI runs'),
            ({'dummy_only': True}, '--dummy-only given'),
            ({'variables_defaulted': ('SDL_AUDIODRIVER',)}, 'SDL_VIDEODRIVER set by the invoker'),
            ({'variables_defaulted': ()}, 'SDL_VIDEODRIVER and SDL_AUDIODRIVER set'),
            ({'collect_only': True}, 'collection only'),
            ({'platform': 'linux'}, 'no native display on linux'),
        ],
        ids=[
            'inside a comparison',
            'CI',
            'dummy only',
            'video driver set',
            'both drivers set',
            'collect only',
            'no display',
        ],
    )
    def test_reasons_to_stay_on_one_driver(self, case, reason):
        """Each reason, the rest of the run as a plain local macOS run."""
        found = comparison_skip_reason(
            environment=no_comparison_environment(**case.get('environment', {})),
            platform=case.get('platform', 'darwin'),
            variables_defaulted=case.get('variables_defaulted', SDL_DRIVER_VARIABLES),
            dummy_only=case.get('dummy_only', False),
            collect_only=case.get('collect_only', False),
        )

        assert found is not None
        assert reason in found

    def test_a_ci_value_other_than_true_is_not_ci(self):
        """The CI variable counts as CI only when it is 'true' (as noxfile.py reads it)."""
        assert (
            comparison_skip_reason(
                environment=no_comparison_environment(**{CI_VARIABLE: 'false'}),
                platform='darwin',
                variables_defaulted=SDL_DRIVER_VARIABLES,
                dummy_only=False,
                collect_only=False,
            )
            is None
        )


class TestWorkersAndCommands:
    """The worker split, the child's command and its environment."""

    @pytest.mark.parametrize(
        ('workers', 'expected'),
        [(0, (0, 0)), (1, (1, 1)), (2, (1, 1)), (3, (1, 2)), (16, (5, 11))],
    )
    def test_the_native_run_takes_two_thirds_of_the_workers(self, workers, expected):
        """Together the usual count; each run at least one worker."""
        assert split_workers(workers=workers) == expected

    def test_the_child_command_appends_its_options(self, tmp_path):
        """This interpreter's pytest, the arguments, then workers, no coverage, its outputs."""
        command = child_pytest_command(
            arguments=['tests/a.py', '-k', 'name'],
            workers=4,
            coverage_loaded=True,
            directory=tmp_path,
        )

        assert command == [
            sys.executable,
            '-m',
            'pytest',
            'tests/a.py',
            '-k',
            'name',
            '-n',
            '4',
            '--no-cov',
            f'--junitxml={tmp_path / "junit.xml"}',
            '-o',
            f'cache_dir={tmp_path / "cache"}',
        ]

    def test_without_xdist_or_coverage_their_options_are_left_out(self, tmp_path):
        """No -n without xdist; no --no-cov without pytest-cov."""
        command = child_pytest_command(
            arguments=[], workers=None, coverage_loaded=False, directory=tmp_path
        )

        assert '-n' not in command
        assert '--no-cov' not in command

    def test_the_child_environment_names_its_drivers(self):
        """Its drivers, inside-a-comparison, background app; this run's recording dropped."""
        environment = driver_environment(
            environment={
                'HOME': '/home/tester',
                FINGERPRINTS_VARIABLE: '/runs/dummy',
                SEED_VARIABLE: '1',
                OWNER_VARIABLE: '123',
            },
            drivers=NativeDrivers(video='cocoa', audio='coreaudio'),
        )

        assert environment == {
            'HOME': '/home/tester',
            'SDL_VIDEODRIVER': 'cocoa',
            'SDL_AUDIODRIVER': 'coreaudio',
            COMPARISON_ACTIVE_VARIABLE: '1',
            MAC_BACKGROUND_APP_VARIABLE: '1',
        }

    def test_failure_lines_come_from_the_short_summary(self):
        """FAILED and ERROR lines, in order."""
        log_text = 'tests/a.py::t PASSED\nFAILED tests/a.py::t - x\nnoise\nERROR tests/b.py::u\n'

        assert failure_summary_lines(log_text=log_text) == [
            'FAILED tests/a.py::t - x',
            'ERROR tests/b.py::u',
        ]


@pytest.fixture
def inner_project(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> pytest.Pytester:
    """A project of two inner tests, run where a comparison would start (dummy vs dummy).

    The variables this run itself may carry (a comparison in progress, CI, chosen drivers,
    recording) are removed, so the inner run decides for itself.

    Returns:
        The pytester.

    """
    for name in (
        COMPARISON_ACTIVE_VARIABLE,
        CI_VARIABLE,
        FINGERPRINTS_VARIABLE,
        SEED_VARIABLE,
        OWNER_VARIABLE,
        *SDL_DRIVER_VARIABLES,
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(COMPARE_WITH_VARIABLE, 'dummy')
    monkeypatch.setenv('PYTHONPATH', str(PROJECT_ROOT))
    pytester.makeconftest(INNER_CONFTEST)
    pytester.makepyfile(test_inner=INNER_TESTS)
    return pytester


class TestEndToEnd:
    """The whole comparison in a pytest subprocess."""

    def test_a_frame_difference_fails_the_run_with_images(self, inner_project):
        """The differing test is reported with its images; the run fails though tests pass."""
        result = inner_project.runpytest_subprocess(timeout=SUBPROCESS_TIMEOUT_SECONDS)

        assert result.ret == pytest.ExitCode.TESTS_FAILED
        result.assert_outcomes(passed=2)
        result.stdout.fnmatch_lines([
            '*driver comparison: dummy vs dummy-2*',
            '*Driver differences: 1*',
            f'*{DIFFERING_TEST}: present 0 differs (pixels)*',
            '*Re-run of 1 tests*',
            f'*present 0: {INNER_WINDOW_PIXELS} of {INNER_WINDOW_PIXELS} pixels*difference-frame*',
        ])
        differences = inner_project.path.joinpath(*OUTPUT_PARTS, 'differences')
        assert len(list(differences.glob('*/difference-frame-0.png'))) == 1

    def test_dummy_only_runs_one_driver(self, inner_project):
        """--dummy-only: no comparison, said in the summary; the tests pass."""
        result = inner_project.runpytest_subprocess(
            DUMMY_ONLY_OPTION, timeout=SUBPROCESS_TIMEOUT_SECONDS
        )

        assert result.ret == pytest.ExitCode.OK
        result.stdout.fnmatch_lines(['*driver comparison: off (--dummy-only given)*'])

    def test_a_failure_in_the_second_run_fails_this_run(self, inner_project):
        """A test failing only in the comparison's second run is listed, and fails the run."""
        inner_project.makepyfile(
            test_fails_second=textwrap.dedent(
                f"""
                import os


                def test_fails_in_the_second_run():
                    assert {FINGERPRINTS_VARIABLE!r} in os.environ
                """
            )
        )

        result = inner_project.runpytest_subprocess(
            'test_fails_second.py', timeout=SUBPROCESS_TIMEOUT_SECONDS
        )

        assert result.ret == pytest.ExitCode.TESTS_FAILED
        result.assert_outcomes(passed=1)
        result.stdout.fnmatch_lines([
            '*The dummy-2 run failed (1 listed):*',
            '*FAILED test_fails_second.py::test_fails_in_the_second_run*',
        ])
