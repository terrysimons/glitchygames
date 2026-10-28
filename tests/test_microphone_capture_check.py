"""Tests for scripts/microphone_capture_check.py: capture from the microphone and report.

The microphone is hardware, so miniaudio's ``Devices`` and ``CaptureDevice`` are replaced with
stand-ins (pytest-mock) that list made-up devices and send prepared chunks into the capture
generator exactly as miniaudio's capture thread does; everything else runs for real.
"""

from __future__ import annotations

import math
import os
import struct
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Self

import miniaudio
import pytest
from pydantic import ValidationError
from scripts.microphone_capture_check import (
    APPLICATION_NAME,
    DEFAULT_CHANNELS,
    DEFAULT_DEVICE_DESCRIPTION,
    DEFAULT_DURATION_SECONDS,
    DEFAULT_SAMPLE_RATE,
    CaptureLevels,
    CaptureReport,
    CaptureSettings,
    capture_audio,
    find_capture_device,
    main,
    measure_levels,
    parse_arguments,
)

from glitchygames.exit_codes import ExitCode
from glitchygames.process import OutputCapture, run_command

if TYPE_CHECKING:
    from collections.abc import Generator

    from pytest_mock import MockerFixture

SCRIPT_PATH = Path(__file__).parent.parent / 'scripts' / 'microphone_capture_check.py'
# A generous limit for a child process that only parses its arguments
SCRIPT_TIMEOUT_SECONDS = 60.0
# A capture short enough for a test
TEST_DURATION_SECONDS = 0.001
DEVICES = [
    {'name': 'Built-in Microphone', 'id': 'built-in id'},
    {'name': 'USB Headset Microphone', 'id': 'headset id'},
]


def _samples(*values: int) -> bytes:
    """Return signed 16-bit little-endian samples."""
    return struct.pack(f'<{len(values)}h', *values)


class StandInDevices:
    """Stands in for miniaudio.Devices: lists DEVICES (or raises)."""

    devices: ClassVar[list[dict[str, Any]]] = DEVICES
    error: ClassVar[miniaudio.MiniaudioError | None] = None

    def get_captures(self: Self) -> list[dict[str, Any]]:
        """Return the stand-in capture devices, or raise ``error`` when it is set."""
        if self.error is not None:
            raise self.error
        return self.devices


class StandInCaptureDevice:
    """Stands in for miniaudio.CaptureDevice: sends ``chunks`` into the generator on start."""

    chunks: ClassVar[list[bytes]] = []
    init_error: ClassVar[miniaudio.MiniaudioError | None] = None
    start_error: ClassVar[miniaudio.MiniaudioError | None] = None
    instances: ClassVar[list[StandInCaptureDevice]] = []

    def __init__(self: Self, **keywords: Any) -> None:
        """Record the keywords the device was opened with, or raise ``init_error`` if set."""
        if self.init_error is not None:
            raise self.init_error
        self.keywords = keywords
        self.is_closed = False
        self.instances.append(self)

    def start(self: Self, receiver: Generator[None, bytes]) -> None:
        """Send each chunk in, as miniaudio's capture thread does (or raise ``start_error``)."""
        if self.start_error is not None:
            raise self.start_error
        for chunk in self.chunks:
            receiver.send(bytearray(chunk))

    def close(self: Self) -> None:
        """Mark the device closed."""
        self.is_closed = True


@pytest.fixture
def microphone(mocker: MockerFixture) -> type[StandInCaptureDevice]:
    """Replace miniaudio's devices with the stand-ins, reset for each test.

    Returns:
        The capture device stand-in class (set its ``chunks`` and errors).

    """
    mocker.patch.object(StandInDevices, 'devices', DEVICES)
    mocker.patch.object(StandInDevices, 'error', None)
    mocker.patch.object(StandInCaptureDevice, 'chunks', [])
    mocker.patch.object(StandInCaptureDevice, 'init_error', None)
    mocker.patch.object(StandInCaptureDevice, 'start_error', None)
    mocker.patch.object(StandInCaptureDevice, 'instances', [])
    mocker.patch.object(miniaudio, 'Devices', StandInDevices)
    mocker.patch.object(miniaudio, 'CaptureDevice', StandInCaptureDevice)
    return StandInCaptureDevice


def _settings(**changes: Any) -> CaptureSettings:
    values: dict[str, Any] = {
        'duration_seconds': TEST_DURATION_SECONDS,
        'sample_rate': DEFAULT_SAMPLE_RATE,
        'channels': DEFAULT_CHANNELS,
        **changes,
    }
    return CaptureSettings(**values)


class TestArguments:
    """The command line: duration, device, sample rate, channels, list only."""

    def test_the_defaults_capture_three_seconds_from_the_default_device(self):
        arguments = parse_arguments([])

        assert arguments.duration == DEFAULT_DURATION_SECONDS == 3.0
        assert arguments.device is None
        assert arguments.sample_rate == DEFAULT_SAMPLE_RATE
        assert arguments.channels == DEFAULT_CHANNELS
        assert not arguments.list_devices

    def test_every_option_is_read(self):
        arguments = parse_arguments([
            '--duration',
            '5',
            '--device',
            'USB',
            '--sample-rate',
            '16000',
            '--channels',
            '2',
            '--list-devices',
        ])

        assert (
            arguments.duration,
            arguments.device,
            arguments.sample_rate,
            arguments.channels,
            arguments.list_devices,
        ) == (5.0, 'USB', 16000, 2, True)

    @pytest.mark.parametrize(
        'option', [['--duration', '0'], ['--sample-rate', '-1'], ['--channels', '0']]
    )
    def test_a_value_that_is_not_positive_is_a_usage_error(self, option, capsys):
        with pytest.raises(SystemExit) as exit_info:
            parse_arguments(option)

        assert exit_info.value.code == ExitCode.ARGUMENT_PARSER_ERROR
        assert f'{option[0]} must be greater than 0' in capsys.readouterr().err


class TestLevels:
    """Peak and RMS levels of signed 16-bit samples, as fractions of full scale."""

    def test_peak_and_root_mean_square(self):
        levels = measure_levels(audio=_samples(16384, -16384, 16384, -16384))

        assert levels == CaptureLevels(peak=0.5, root_mean_square=0.5)

    def test_the_most_negative_sample_is_full_scale(self):
        levels = measure_levels(audio=_samples(-32768, 0))

        assert levels is not None
        assert levels.peak == 1.0
        assert levels.root_mean_square == pytest.approx(math.sqrt(0.5))

    def test_a_trailing_odd_byte_is_ignored(self):
        levels = measure_levels(audio=_samples(100) + b'\x7f')

        assert levels == CaptureLevels(peak=100 / 32768, root_mean_square=100 / 32768)

    @pytest.mark.parametrize('audio', [b'', b'\x01'])
    def test_no_whole_sample_has_no_levels(self, audio):
        assert measure_levels(audio=audio) is None

    def test_all_zero_samples_are_silent(self):
        levels = measure_levels(audio=_samples(0, 0, 0))

        assert levels is not None
        assert levels.is_silent
        assert not CaptureLevels(peak=1 / 32768, root_mean_square=0.0).is_silent


class TestReport:
    """The report: what arrived, how loud, and the exit code."""

    def test_audio_that_arrived_is_reported_with_its_levels(self):
        report = CaptureReport(
            device_description="'USB Headset Microphone'",
            settings=_settings(duration_seconds=0.5, sample_rate=1000, channels=2),
            captured_bytes=2000,
            levels=CaptureLevels(peak=0.5, root_mean_square=0.1),
        )

        assert report.captured_frames == 500
        assert report.expected_frames == 500
        assert report.lines() == [
            "Captured 0.5 s from 'USB Headset Microphone' (1000 Hz, 2 channel(s), signed 16-bit)",
            'Received 2000 bytes: 500 of 500 expected frames (100.0%)',
            'Level: peak -6.0 dBFS, RMS -20.0 dBFS',
        ]
        assert report.exit_code() == ExitCode.SUCCESS

    def test_nothing_arriving_is_unusable_input(self):
        report = CaptureReport(
            device_description=DEFAULT_DEVICE_DESCRIPTION,
            settings=_settings(duration_seconds=1.0, sample_rate=100),
            captured_bytes=0,
            levels=None,
        )

        assert report.lines()[1:] == [
            'Received 0 bytes: 0 of 100 expected frames (0.0%)',
            'No audio arrived: the device delivered nothing',
        ]
        assert report.exit_code() == ExitCode.UNUSABLE_INPUT

    def test_silence_is_unusable_input_and_names_the_macos_permission(self):
        report = CaptureReport(
            device_description=DEFAULT_DEVICE_DESCRIPTION,
            settings=_settings(duration_seconds=1.0, sample_rate=100),
            captured_bytes=200,
            levels=CaptureLevels(peak=0.0, root_mean_square=0.0),
        )

        assert 'Privacy & Security > Microphone' in report.lines()[-1]
        assert report.exit_code() == ExitCode.UNUSABLE_INPUT

    def test_a_capture_too_short_for_one_frame_has_no_percentage(self):
        report = CaptureReport(
            device_description=DEFAULT_DEVICE_DESCRIPTION,
            settings=_settings(duration_seconds=0.001, sample_rate=100),
            captured_bytes=0,
            levels=None,
        )

        assert report.expected_frames == 0
        assert report.lines()[1] == 'Received 0 bytes: 0 of 0 expected frames (n/a)'

    def test_settings_refuse_a_duration_that_is_not_positive(self):
        with pytest.raises(ValidationError):
            _settings(duration_seconds=0.0)


class TestDevices:
    """Choosing a capture device by part of its name."""

    def test_the_first_device_whose_name_contains_the_text_is_chosen(self):
        assert find_capture_device(devices=DEVICES, name='Microphone') is DEVICES[0]
        assert find_capture_device(devices=DEVICES, name='USB') is DEVICES[1]

    def test_no_match_is_none(self):
        assert find_capture_device(devices=DEVICES, name='usb') is None


class TestCapture:
    """Capturing collects every chunk the device sends, then closes the device."""

    def test_every_chunk_is_kept_in_order(self, microphone):
        microphone.chunks = [_samples(1, 2), _samples(3)]

        audio = capture_audio(settings=_settings(sample_rate=16000, channels=2), device_id='an id')

        assert audio == _samples(1, 2, 3)
        (device,) = microphone.instances
        assert device.keywords == {
            'input_format': miniaudio.SampleFormat.SIGNED16,
            'nchannels': 2,
            'sample_rate': 16000,
            'device_id': 'an id',
            'app_name': APPLICATION_NAME,
        }
        assert device.is_closed

    def test_the_device_is_closed_when_it_cannot_start(self, microphone):
        microphone.start_error = miniaudio.MiniaudioError('failed to start audio device')

        with pytest.raises(miniaudio.MiniaudioError):
            capture_audio(settings=_settings(), device_id=None)

        (device,) = microphone.instances
        assert device.is_closed


class TestMain:
    """The whole check: list, choose, capture, report, exit code."""

    def test_a_capture_with_sound_succeeds(self, microphone, capsys):
        microphone.chunks = [_samples(16384, -16384)]

        exit_code = main(['--duration', str(TEST_DURATION_SECONDS)])

        output = capsys.readouterr().out.splitlines()
        assert exit_code == ExitCode.SUCCESS
        assert output[0] == 'Capture devices: Built-in Microphone, USB Headset Microphone'
        assert output[1].startswith(f'Captured 0.001 s from {DEFAULT_DEVICE_DESCRIPTION} ')
        assert output[3] == 'Level: peak -6.0 dBFS, RMS -6.0 dBFS'
        assert microphone.instances[0].keywords['device_id'] is None

    def test_a_named_device_is_captured_from(self, microphone, capsys):
        microphone.chunks = [_samples(1)]

        exit_code = main(['--duration', str(TEST_DURATION_SECONDS), '--device', 'USB'])

        assert exit_code == ExitCode.SUCCESS
        assert microphone.instances[0].keywords['device_id'] == 'headset id'
        assert "from 'USB Headset Microphone'" in capsys.readouterr().out

    def test_a_silent_capture_is_unusable_input(self, microphone):
        microphone.chunks = [_samples(0, 0)]

        assert main(['--duration', str(TEST_DURATION_SECONDS)]) == ExitCode.UNUSABLE_INPUT

    def test_list_devices_only_lists(self, microphone, capsys):
        assert main(['--list-devices']) == ExitCode.SUCCESS
        assert microphone.instances == []
        assert capsys.readouterr().out == (
            'Capture devices: Built-in Microphone, USB Headset Microphone\n'
        )

    def test_no_capture_device_is_missing_input(self, microphone, mocker, capsys):
        mocker.patch.object(StandInDevices, 'devices', [])

        assert main([]) == ExitCode.MISSING_INPUT
        assert capsys.readouterr().out == 'Capture devices: none\n'

    def test_an_unknown_device_name_is_missing_input(self, microphone, capsys):
        assert main(['--device', 'Theremin']) == ExitCode.MISSING_INPUT
        assert "No capture device name contains 'Theremin'" in capsys.readouterr().out
        assert microphone.instances == []

    def test_devices_that_cannot_be_listed_are_unavailable(self, microphone, mocker, capsys):
        mocker.patch.object(
            StandInDevices, 'error', miniaudio.MiniaudioError('cannot get device infos')
        )

        assert main([]) == ExitCode.SERVICE_UNAVAILABLE
        assert 'Cannot list the capture devices: ' in capsys.readouterr().out

    def test_a_device_that_cannot_open_is_unavailable(self, microphone, capsys):
        microphone.init_error = miniaudio.MiniaudioError('failed to init device')

        assert main(['--duration', str(TEST_DURATION_SECONDS)]) == ExitCode.SERVICE_UNAVAILABLE
        assert f'Cannot capture from {DEFAULT_DEVICE_DESCRIPTION}: ' in capsys.readouterr().out


def test_the_script_exits_with_its_exit_code():
    """Run as a script, it exits with main()'s code (a usage error here: no device is opened)."""
    completed = run_command(
        command=[sys.executable, str(SCRIPT_PATH), '--duration', '0'],
        environment=os.environ,
        timeout_seconds=SCRIPT_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
    )

    assert completed.returncode == ExitCode.ARGUMENT_PARSER_ERROR
    assert '--duration must be greater than 0' in completed.stdout
