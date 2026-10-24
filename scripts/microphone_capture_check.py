"""Check the microphone: capture a few seconds from it with miniaudio and report what arrived.

It lists the capture devices miniaudio finds, opens one (the system default, or the first whose
name contains ``--device``), captures ``--duration`` seconds of signed 16-bit audio at
``--sample-rate`` in ``--channels`` channels, and reports how much audio arrived (bytes, frames
and the share of the frames expected: a little over 100% is normal, as the device delivers
whole buffers) and how loud it was (peak and RMS level in dBFS, where 0 is full scale). Audio
that arrives but is all zeros is silent; on macOS that usually means the terminal has no
microphone permission (System Settings > Privacy & Security > Microphone).
Bitmappy's voice commands (``glitchygames/events/voice_miniaudio.py``) capture the same way.

Exit codes (``glitchygames.exit_codes.ExitCode``):
    SUCCESS (0)                audio arrived and was not all zeros
    ARGUMENT_PARSER_ERROR (2)  a usage error (argparse)
    UNUSABLE_INPUT (65)        no audio arrived, or every sample was zero
    MISSING_INPUT (66)         no capture device, or none whose name contains ``--device``
    SERVICE_UNAVAILABLE (69)   the capture device could not be opened or started

Usage:
    uv run python scripts/microphone_capture_check.py
    uv run python scripts/microphone_capture_check.py --list-devices
    uv run python scripts/microphone_capture_check.py --device "MacBook Pro" --duration 5
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from typing import TYPE_CHECKING, Any

import miniaudio
import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from glitchygames.exit_codes import ExitCode

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glitchygames.audio.controller_audio import CaptureCallbackGenerator, MiniaudioDeviceId

DEFAULT_DURATION_SECONDS = 3.0
DEFAULT_SAMPLE_RATE = 48000
DEFAULT_CHANNELS = 1
# Signed 16-bit samples: two bytes each, full scale 32768
SAMPLE_FORMAT = miniaudio.SampleFormat.SIGNED16
BYTES_PER_SAMPLE = 2
FULL_SCALE = 32768.0
# The name the operating system shows for the capturing application
APPLICATION_NAME = 'glitchygames microphone check'
# What the report calls the device when none is named
DEFAULT_DEVICE_DESCRIPTION = 'the default capture device'


class CaptureSettings(BaseModel):
    """What to capture.

    Attributes:
        duration_seconds: How long to capture.
        sample_rate: Frames per second.
        channels: Channels per frame.
        device_name: Capture from the first device whose name contains this, or from the
            default capture device when None.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    duration_seconds: float = Field(gt=0.0)
    sample_rate: int = Field(gt=0)
    channels: int = Field(gt=0)
    device_name: str | None = None


class CaptureLevels(BaseModel):
    """How loud a capture was.

    Attributes:
        peak: The largest absolute sample, as a fraction of full scale (0.0 to 1.0).
        root_mean_square: The root mean square of the samples, as a fraction of full scale.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    peak: float
    root_mean_square: float

    @property
    def is_silent(self) -> bool:
        """Whether every sample was zero."""
        # The peak is never negative: no level above 0 is silence
        return self.peak <= 0.0


class CaptureReport(BaseModel):
    """What one capture brought in.

    Attributes:
        device_description: The device captured from.
        settings: What was asked for.
        captured_bytes: How many bytes arrived.
        levels: How loud they were (None when nothing arrived).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    device_description: str
    settings: CaptureSettings
    captured_bytes: int
    levels: CaptureLevels | None

    @property
    def captured_frames(self) -> int:
        """How many whole frames arrived."""
        return self.captured_bytes // (BYTES_PER_SAMPLE * self.settings.channels)

    @property
    def expected_frames(self) -> int:
        """How many frames the duration holds at the sample rate."""
        return round(self.settings.duration_seconds * self.settings.sample_rate)

    def exit_code(self) -> ExitCode:
        """Return how the check ends.

        Returns:
            SUCCESS when audio arrived and was not all zeros, else UNUSABLE_INPUT.

        """
        if self.levels is None or self.levels.is_silent:
            return ExitCode.UNUSABLE_INPUT
        return ExitCode.SUCCESS

    def lines(self) -> list[str]:
        """Describe the capture, one line each.

        Returns:
            The report's lines.

        """
        settings = self.settings
        lines = [
            (
                f'Captured {settings.duration_seconds:g} s from {self.device_description} '
                f'({settings.sample_rate} Hz, {settings.channels} channel(s), signed 16-bit)'
            ),
            (
                f'Received {self.captured_bytes} bytes: {self.captured_frames} of '
                f'{self.expected_frames} expected frames '
                f'({_percentage(part=self.captured_frames, whole=self.expected_frames)})'
            ),
        ]
        if self.levels is None:
            lines.append('No audio arrived: the device delivered nothing')
        elif self.levels.is_silent:
            lines.append(
                'Every sample is zero (silence): on macOS, check that the terminal may use the '
                'microphone (System Settings > Privacy & Security > Microphone)'
            )
        else:
            lines.append(
                f'Level: peak {_decibels_full_scale(fraction=self.levels.peak)}, '
                f'RMS {_decibels_full_scale(fraction=self.levels.root_mean_square)}'
            )
        return lines


def _percentage(*, part: int, whole: int) -> str:
    """Format a share as a percentage.

    Args:
        part: The share.
        whole: The whole (0 gives 'n/a').

    Returns:
        The percentage, to one decimal place.

    """
    if whole == 0:
        return 'n/a'
    return f'{100.0 * part / whole:.1f}%'


def _decibels_full_scale(*, fraction: float) -> str:
    """Format a level given as a fraction of full scale in dBFS.

    Args:
        fraction: The level (greater than 0.0; 1.0 is full scale).

    Returns:
        The level in dBFS, to one decimal place.

    """
    return f'{20.0 * math.log10(fraction):.1f} dBFS'


def measure_levels(*, audio: bytes) -> CaptureLevels | None:
    """Measure the peak and RMS level of signed 16-bit little-endian samples.

    Args:
        audio: The samples (a trailing odd byte is ignored).

    Returns:
        The levels, or None when the audio holds no whole sample.

    """
    sample_count = len(audio) // BYTES_PER_SAMPLE
    if sample_count == 0:
        return None
    samples = np.frombuffer(audio, dtype='<i2', count=sample_count).astype(np.float64)
    return CaptureLevels(
        peak=float(np.max(np.abs(samples))) / FULL_SCALE,
        root_mean_square=float(np.sqrt(np.mean(np.square(samples)))) / FULL_SCALE,
    )


def capture_devices() -> list[dict[str, Any]]:
    """Return the capture devices miniaudio finds.

    Returns:
        miniaudio's description of each device (its ``name`` and ``id`` among them).

    """
    return miniaudio.Devices().get_captures()


def find_capture_device(*, devices: Sequence[dict[str, Any]], name: str) -> dict[str, Any] | None:
    """Return the first device whose name contains ``name``.

    Args:
        devices: The capture devices (``capture_devices``).
        name: Part of the device's name (case-sensitive).

    Returns:
        The device, or None if no name contains ``name``.

    """
    return next((device for device in devices if name in str(device.get('name', ''))), None)


def capture_audio(
    *,
    settings: CaptureSettings,
    device_id: MiniaudioDeviceId | None,
) -> bytes:
    """Capture audio from a device for the settings' duration.

    Args:
        settings: What to capture.
        device_id: The device's miniaudio id, or None for the default capture device.

    Returns:
        The captured samples, as they arrived.

    """
    chunks: list[bytes] = []

    def receive_chunks() -> CaptureCallbackGenerator:
        """Keep each chunk the device sends (on miniaudio's capture thread).

        Yields:
            Nothing: the device sends each chunk in.

        """
        while True:
            chunk = yield
            chunks.append(bytes(chunk))

    receiver = receive_chunks()
    next(receiver)  # Run to the first yield, so the device can send into it
    # Any: miniaudio types start()'s frames as a bare array.array (an unknown item type)
    device: Any = miniaudio.CaptureDevice(
        input_format=SAMPLE_FORMAT,
        nchannels=settings.channels,
        sample_rate=settings.sample_rate,
        device_id=device_id,
        app_name=APPLICATION_NAME,
    )
    try:
        device.start(receiver)
        time.sleep(settings.duration_seconds)
    finally:
        device.close()
    return b''.join(chunks)


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the command line.

    Args:
        argv: The arguments (default: the process's).

    Returns:
        The parsed arguments.

    """
    parser = argparse.ArgumentParser(
        description='Capture a few seconds from the microphone and report what arrived.'
    )
    parser.add_argument(
        '--duration',
        type=float,
        default=DEFAULT_DURATION_SECONDS,
        help='seconds to capture (default: %(default)s)',
    )
    parser.add_argument(
        '--device',
        default=None,
        help='capture from the first device whose name contains this (default: the system '
        'default capture device)',
    )
    parser.add_argument(
        '--sample-rate',
        type=int,
        default=DEFAULT_SAMPLE_RATE,
        help='frames per second (default: %(default)s)',
    )
    parser.add_argument(
        '--channels',
        type=int,
        default=DEFAULT_CHANNELS,
        help='channels to capture (default: %(default)s)',
    )
    parser.add_argument(
        '--list-devices',
        action='store_true',
        help='only list the capture devices',
    )
    arguments = parser.parse_args(argv)
    for option, value in (
        ('--duration', arguments.duration),
        ('--sample-rate', arguments.sample_rate),
        ('--channels', arguments.channels),
    ):
        if value <= 0:
            parser.error(f'{option} must be greater than 0, not {value}')
    return arguments


def emit(message: str) -> None:
    """Write a line of the report to stdout.

    Args:
        message: The line.

    """
    sys.stdout.write(message + '\n')


def main(argv: Sequence[str] | None = None) -> ExitCode:
    """List the capture devices, capture from one, and report.

    Args:
        argv: The arguments (default: the process's).

    Returns:
        How the check ended (see the module docstring).

    """
    arguments = parse_arguments(argv)
    settings = CaptureSettings(
        duration_seconds=arguments.duration,
        sample_rate=arguments.sample_rate,
        channels=arguments.channels,
        device_name=arguments.device,
    )
    try:
        devices = capture_devices()
    except miniaudio.MiniaudioError as error:
        emit(f'Cannot list the capture devices: {error}')
        return ExitCode.SERVICE_UNAVAILABLE
    emit(f'Capture devices: {", ".join(str(device["name"]) for device in devices) or "none"}')
    if not devices:
        return ExitCode.MISSING_INPUT
    if arguments.list_devices:
        return ExitCode.SUCCESS

    device_id: MiniaudioDeviceId | None = None
    device_description = DEFAULT_DEVICE_DESCRIPTION
    if settings.device_name is not None:
        device = find_capture_device(devices=devices, name=settings.device_name)
        if device is None:
            emit(f'No capture device name contains {settings.device_name!r}')
            return ExitCode.MISSING_INPUT
        device_id = device['id']
        device_description = repr(device['name'])

    try:
        audio = capture_audio(settings=settings, device_id=device_id)
    except miniaudio.MiniaudioError as error:
        emit(f'Cannot capture from {device_description}: {error}')
        return ExitCode.SERVICE_UNAVAILABLE

    report = CaptureReport(
        device_description=device_description,
        settings=settings,
        captured_bytes=len(audio),
        levels=measure_levels(audio=audio),
    )
    for line in report.lines():
        emit(line)
    return report.exit_code()


if __name__ == '__main__':
    sys.exit(main())
