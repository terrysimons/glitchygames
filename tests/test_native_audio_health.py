"""scripts/native_audio_health.py: the native audio probe and the audio-failure labelling.

The probe's children are real processes: a real pygame mixer on the dummy audio driver (success)
and on an SDL audio driver that does not exist (pygame's own ``pygame.error``), and a child that
sleeps past the time limit (a hung mixer start). The junit reports follow pytest's xunit
format: a failure's text is its ``message`` attribute and its body.
"""

from __future__ import annotations

import io
import json
import os
import sys
from typing import TYPE_CHECKING, Any

import pygame
import pytest
from scripts import native_audio_health
from scripts.driver_configurations import DriverPlan, PlannedConfiguration
from scripts.native_audio_health import (
    AUDIO_UNAVAILABLE_MARKERS,
    classify_differing_tests,
    junit_key,
    native_audio_configurations,
    probe_native_audio,
    run,
    run_probe,
)

from glitchygames.exit_codes import ExitCode

if TYPE_CHECKING:
    from pathlib import Path

COREAUDIO_FAILURE = 'pygame.error: CoreAudio error (AudioQueueStart): -66681'


def write_junit(*, path: Path, cases: list[tuple[str, str, str | None]]) -> Path:
    """Write a pytest-style junit report: (classname, name, failure text or None) per test.

    Returns:
        The path.

    """
    body = []
    for classname, name, failure in cases:
        inner = (
            ''
            if failure is None
            else f'<failure message="{failure}">Traceback\n{failure}</failure>'
        )
        body.append(f'<testcase classname="{classname}" name="{name}">{inner}</testcase>')
    path.write_text(
        f'<?xml version="1.0"?><testsuites><testsuite>{"".join(body)}</testsuite></testsuites>',
        encoding='utf-8',
    )
    return path


def plan_with(*configurations: tuple[str, dict[str, str], bool]) -> DriverPlan:
    """Return a plan: (name, environment, runs_in_linux_container) each."""
    return DriverPlan(
        configurations=tuple(
            PlannedConfiguration(
                name=name, environment=environment, runs_in_linux_container=container
            )
            for name, environment, container in configurations
        ),
        unavailable=(),
        needs_xquartz=False,
    )


class TestWhichConfigurationsNeedTheProbe:
    """Only a configuration whose audio driver is the machine's own is probed."""

    def test_native_audio_is_probed_and_dummy_audio_and_the_container_are_not(self) -> None:
        plan = plan_with(
            ('dummy', {'SDL_AUDIODRIVER': 'dummy'}, False),
            ('cocoa', {'SDL_AUDIODRIVER': 'coreaudio'}, False),
            ('x11', {'SDL_AUDIODRIVER': 'dummy'}, False),
            ('x11-linux', {'SDL_AUDIODRIVER': 'alsa'}, True),
        )

        assert [name for name, _ in native_audio_configurations(plan=plan)] == ['cocoa']

    def test_a_configuration_without_an_audio_driver_variable_is_not_probed(self) -> None:
        assert native_audio_configurations(plan=plan_with(('odd', {}, False))) == []


class TestProbe:
    """The probe's three outcomes: opens, errors, hangs."""

    def test_a_mixer_that_opens_and_closes_is_working(self) -> None:
        result = probe_native_audio(configuration='cocoa', environment={'SDL_AUDIODRIVER': 'dummy'})

        assert result.working
        assert not result.detail

    def test_a_mixer_pygame_cannot_open_is_named_with_pygames_error(self) -> None:
        result = probe_native_audio(
            configuration='cocoa', environment={'SDL_AUDIODRIVER': 'no-such-audio-driver'}
        )

        assert not result.working
        assert 'pygame.error' in result.detail

    def test_a_child_that_never_returns_is_a_hang(self) -> None:
        result = probe_native_audio(
            configuration='cocoa',
            environment={},
            timeout_seconds=1.0,
            command=[sys.executable, '-c', 'import time; time.sleep(60)'],
        )

        assert not result.working
        assert 'hung' in result.detail

    def test_a_child_that_fails_without_a_message_reports_its_exit_code(self) -> None:
        result = probe_native_audio(
            configuration='cocoa',
            environment={},
            command=[sys.executable, '-c', 'raise SystemExit(7)'],
        )

        assert not result.working
        assert result.detail == 'the probe exited 7'


class TestRunProbe:
    """The probe command: stops at the first failing configuration, with advice."""

    def write_plan(self, *, tmp_path: Path, audio_driver: str) -> Path:
        plan_path = tmp_path / 'plan.json'
        plan_path.write_text(
            plan_with(('cocoa', {'SDL_AUDIODRIVER': audio_driver}, False)).model_dump_json(),
            encoding='utf-8',
        )
        return plan_path

    def test_working_audio_succeeds(self, tmp_path: Path, mocker: Any) -> None:
        # A native driver cannot be opened portably here (SDL's disk driver writes a file), so
        # the probe's outcome is given; TestProbe runs the real child
        mocker.patch.object(
            native_audio_health,
            'probe_native_audio',
            return_value=native_audio_health.AudioProbeResult(configuration='cocoa', working=True),
        )
        log = io.StringIO()

        code = run_probe(
            plan_path=self.write_plan(tmp_path=tmp_path, audio_driver='coreaudio'), log=log
        )

        assert code == ExitCode.SUCCESS, log.getvalue()
        assert 'native audio opens and closes' in log.getvalue()

    def test_failing_audio_stops_with_the_error_and_the_advice(self, tmp_path: Path) -> None:
        log = io.StringIO()

        code = run_probe(
            plan_path=self.write_plan(tmp_path=tmp_path, audio_driver='no-such-audio-driver'),
            log=log,
        )

        assert code == ExitCode.SERVICE_UNAVAILABLE
        assert "this machine's audio, not the change" in log.getvalue()
        assert 'killall coreaudiod' in log.getvalue()
        assert 'pygame.error' in log.getvalue()

    def test_a_plan_with_no_native_audio_needs_no_probe(self, tmp_path: Path) -> None:
        log = io.StringIO()

        code = run_probe(
            plan_path=self.write_plan(tmp_path=tmp_path, audio_driver='dummy'), log=log
        )

        assert code == ExitCode.SUCCESS
        assert not log.getvalue()


class TestJunitKey:
    """A node id maps to junit's classname.name."""

    @pytest.mark.parametrize(
        ('nodeid', 'key'),
        [
            ('tests/test_a.py', 'tests.test_a'),
            ('tests/test_a.py::test_b', 'tests.test_a.test_b'),
            ('tests/test_a.py::TestB::test_c', 'tests.test_a.TestB.test_c'),
            ('src/x/tests/test_a.py::test_b[a/b::c-1]', 'src.x.tests.test_a.test_b[a/b::c-1]'),
        ],
    )
    def test_key(self, nodeid: str, key: str) -> None:
        assert junit_key(nodeid=nodeid) == key


class TestLabelling:
    """Differing tests whose failure says audio was unavailable are audio failures."""

    def test_the_coreaudio_failures_are_audio_and_the_rest_are_frames(self, tmp_path: Path) -> None:
        junit = write_junit(
            path=tmp_path / 'junit.xml',
            cases=[
                ('tests.test_a', 'test_bounce', COREAUDIO_FAILURE),
                ('tests.test_a.TestB', 'test_channels', 'pygame.error: mixer not initialized'),
                ('tests.test_a', 'test_pixels', 'AssertionError: frames differ'),
                ('tests.test_a', 'test_passing', None),
            ],
        )

        classification = classify_differing_tests(
            nodeids=[
                'tests/test_a.py::test_bounce',
                'tests/test_a.py::TestB::test_channels',
                'tests/test_a.py::test_pixels',
                'tests/test_a.py::test_passing',
            ],
            junit_paths=[junit],
        )

        assert classification.audio == (
            'tests/test_a.py::test_bounce',
            'tests/test_a.py::TestB::test_channels',
        )
        assert classification.frames == (
            'tests/test_a.py::test_pixels',
            'tests/test_a.py::test_passing',
        )

    def test_every_differing_test_is_in_exactly_one_group(self, tmp_path: Path) -> None:
        junit = write_junit(
            path=tmp_path / 'junit.xml',
            cases=[
                (f'tests.t{index}', 'test', COREAUDIO_FAILURE if index % 2 else None)
                for index in range(9)
            ],
        )
        nodeids = [f'tests/t{index}.py::test' for index in range(9)] + ['tests/absent.py::test']

        classification = classify_differing_tests(nodeids=nodeids, junit_paths=[junit])

        assert sorted(classification.audio + classification.frames) == sorted(nodeids)
        assert set(classification.audio).isdisjoint(classification.frames)

    def test_an_error_element_counts_as_a_failure(self, tmp_path: Path) -> None:
        path = tmp_path / 'junit.xml'
        path.write_text(
            '<testsuites><testsuite><testcase classname="tests.t" name="test">'
            f'<error message="{COREAUDIO_FAILURE}">setup</error>'
            '</testcase></testsuite></testsuites>',
            encoding='utf-8',
        )

        classification = classify_differing_tests(nodeids=['tests/t.py::test'], junit_paths=[path])

        assert classification.audio == ('tests/t.py::test',)

    def test_a_failure_on_any_native_run_counts(self, tmp_path: Path) -> None:
        clean = write_junit(path=tmp_path / 'one.xml', cases=[('tests.t', 'test', None)])
        broken = write_junit(
            path=tmp_path / 'two.xml', cases=[('tests.t', 'test', COREAUDIO_FAILURE)]
        )

        classification = classify_differing_tests(
            nodeids=['tests/t.py::test'], junit_paths=[clean, broken]
        )

        assert classification.audio == ('tests/t.py::test',)

    def test_the_markers_are_the_messages_pygame_gives(self) -> None:
        assert AUDIO_UNAVAILABLE_MARKERS == ('CoreAudio error', 'mixer not initialized')


class TestCommandLine:
    """The commands and the child."""

    def test_classify_prints_json(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        junit = write_junit(
            path=tmp_path / 'junit.xml', cases=[('tests.t', 'test', COREAUDIO_FAILURE)]
        )
        tests_file = tmp_path / 'tests.txt'
        tests_file.write_text('tests/t.py::test\ntests/u.py::other\n', encoding='utf-8')

        code = run(arguments=['classify', f'--tests-file={tests_file}', f'--junit={junit}'])

        assert code == ExitCode.SUCCESS
        assert json.loads(capsys.readouterr().out) == {
            'audio': ['tests/t.py::test'],
            'frames': ['tests/u.py::other'],
        }

    def test_probe_command_reads_the_plan(self, tmp_path: Path) -> None:
        plan_path = tmp_path / 'plan.json'
        plan_path.write_text(
            plan_with(('dummy', {'SDL_AUDIODRIVER': 'dummy'}, False)).model_dump_json()
        )

        assert run(arguments=['probe', f'--plan={plan_path}']) == ExitCode.SUCCESS

    def test_child_opens_the_mixer_at_the_engines_settings(
        self, mocker: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv('SDL_AUDIODRIVER', 'dummy')
        spy = mocker.spy(pygame.mixer, 'init')

        assert run(arguments=['child']) == ExitCode.SUCCESS
        spy.assert_called_once_with(frequency=44100, size=-16, channels=2, buffer=512)

    def test_child_reports_pygames_error(self, mocker: Any) -> None:
        # The harness's mixer is already open in this process, so init would be a no-op: give
        # it pygame's own failure (the real one is TestProbe's child)
        mocker.patch.object(
            pygame.mixer,
            'init',
            side_effect=pygame.error('CoreAudio error (AudioQueueStart): -66681'),
        )
        error_output = io.StringIO()

        code = native_audio_health.open_and_close_mixer(error_output=error_output)

        assert code == ExitCode.SERVICE_UNAVAILABLE
        assert error_output.getvalue().startswith('pygame.error: ')

    def test_main_exits_with_the_command_code(self, mocker: Any, tmp_path: Path) -> None:
        mocker.patch.dict(os.environ)  # main() sets PYGAME_HIDE_SUPPORT_PROMPT
        plan_path = tmp_path / 'plan.json'
        plan_path.write_text(plan_with().model_dump_json())
        mocker.patch.object(sys, 'argv', ['native_audio_health', 'probe', f'--plan={plan_path}'])

        with pytest.raises(SystemExit) as exit_info:
            native_audio_health.main()

        assert exit_info.value.code == ExitCode.SUCCESS


class TestCompareDriversSession:
    """nox -s compare-drivers: probes before the runs and labels audio failures."""

    def fake_session(self, mocker: Any) -> Any:
        session = mocker.Mock()
        session.error.side_effect = SystemExit
        return session

    def test_the_probe_runs_before_any_test_run(self, mocker: Any, tmp_path: Path) -> None:
        import noxfile

        session = self.fake_session(mocker)
        calls: list[str] = []
        session.run.side_effect = lambda *arguments, **_: (
            calls.append(' '.join(arguments))
            or ((tmp_path / 'image-request.json').write_text('{"positions_by_test": {}}') and '')
        )
        mocker.patch.object(
            noxfile,
            '_plan_driver_configurations',
            side_effect=lambda *_, **__: (
                calls.append('plan')
                or [{'name': 'dummy', 'runs_in_linux_container': False, 'environment': {}}]
            ),
        )
        mocker.patch.object(noxfile, '_prepare_driver_configurations', return_value='dummy')
        mocker.patch.object(
            noxfile,
            '_run_timed_configurations',
            side_effect=lambda *_, **__: calls.append('runs') or tmp_path / 'run-seconds.json',
        )
        options = noxfile._CompareDriversOptions(
            drivers=None,
            sound=False,
            fail_on_difference=False,
            workers='1',
            skip_when_frames_cannot_change=False,
            selection=(),
        )

        result = noxfile._compare_driver_configurations(session, output=tmp_path, options=options)

        assert result == noxfile._DifferingTests(frames=[], audio=[])
        assert calls[0] == 'plan'
        assert 'scripts.native_audio_health probe' in calls[1]
        assert calls[2] == 'runs'

    def test_the_session_splits_the_classifiers_answer(self, mocker: Any, tmp_path: Path) -> None:
        import noxfile

        session = self.fake_session(mocker)
        session.run.return_value = '{"audio":["a.py::x"],"frames":["b.py::y"]}\n'

        result = noxfile._split_audio_failures(
            session,
            differing_tests=['a.py::x', 'b.py::y'],
            tests_file=tmp_path / 'tests.txt',
            junit_paths=[tmp_path / 'one' / 'junit.xml'],
        )

        assert result == noxfile._DifferingTests(frames=['b.py::y'], audio=['a.py::x'])
        arguments = session.run.call_args.args
        assert f'--junit={tmp_path / "one" / "junit.xml"}' in arguments

    def test_a_classifier_that_loses_a_test_fails_the_session(
        self, mocker: Any, tmp_path: Path
    ) -> None:
        import noxfile

        session = self.fake_session(mocker)
        session.run.return_value = '{"audio":[],"frames":["b.py::y"]}'

        with pytest.raises(SystemExit):
            noxfile._split_audio_failures(
                session,
                differing_tests=['a.py::x', 'b.py::y'],
                tests_file=tmp_path / 'tests.txt',
                junit_paths=[],
            )

    @pytest.mark.parametrize('fail_on_difference', [True, False])
    def test_audio_failures_are_reported_as_audio_never_as_frame_differences(
        self, mocker: Any, *, fail_on_difference: bool
    ) -> None:
        import noxfile

        session = self.fake_session(mocker)
        mocker.patch.object(noxfile, '_only_comparison')
        mocker.patch.object(noxfile, '_set_aside_previous_comparison')
        mocker.patch.object(noxfile.shutil, 'rmtree')
        mocker.patch.object(
            noxfile,
            '_compare_driver_configurations',
            return_value=noxfile._DifferingTests(frames=[], audio=['t.py::bounce']),
        )
        mocker.patch.object(
            noxfile,
            '_compare_drivers_arguments',
            return_value=noxfile._CompareDriversOptions(
                drivers=None,
                sound=False,
                fail_on_difference=fail_on_difference,
                workers='1',
                skip_when_frames_cannot_change=False,
                selection=(),
            ),
        )

        with pytest.raises(SystemExit):
            noxfile.compare_drivers(session)

        message = session.error.call_args.args[0]
        assert message.startswith('audio failed in 1 test(s)')
        assert 't.py::bounce' in message
        assert 'presented different frames' not in message
