"""Probe for audio glitches: clicks in the samples, and GIL starvation of the mixer thread.

Two independent checks, because they find different problems:

  dsp       Plays a live voice configured like the Clockwork Keep elevator motor through SDL's
            disk audio driver, then analyzes the raw recording for silent gaps, discontinuities
            and edge cuts. While playing, the main loop does game-like work (busy Python code
            plus FastTimer pacing), not plain sleeps, so the recording is made under realistic
            contention. The disk driver is not real-time, so a late mixer callback only writes
            later; it cannot show handover delays. That is what the next mode is for.

  realtime  Measures how late a background thread gets the GIL while the main thread runs a
            game-like frame loop. pygame's channel-finished callback needs the GIL to queue the
            next live-voice chunk, so a wait approaching the mixer buffer (512 samples at
            44100 Hz = 11.6 ms) is an audible click. Exits with ``ExitCode.AUDIO_DROPOUT_RISK``
            (6) when the p99 wait reaches half the buffer (the max is shown but includes OS
            scheduling noise).

Note: the 5 ms comparison is indicative; on a quiet machine the old setting can land just
under the 5.8 ms threshold.

Usage:
    uv run python scripts/audio_glitch_probe.py
    uv run python scripts/audio_glitch_probe.py --mode realtime --switch-interval-ms 5
"""

from __future__ import annotations

import argparse
import math
import os
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from glitchygames.audio.diagnostics import (
    DEFAULT_BUFFER_SAMPLES,
    DEFAULT_SAMPLE_RATE,
    FloatArray,
    LockWaitReport,
    busy_python_work,
    describe_edges,
    dropout_risk,
    find_discontinuities,
    find_silent_gaps,
    measure_lock_wait,
)
from glitchygames.exit_codes import ExitCode
from glitchygames.timing import DEFAULT_TARGET_FPS, GIL_SWITCH_INTERVAL_SECONDS, FastTimer

DSP_WORKER_FLAG = '--dsp-worker'
DEFAULT_GAME_LOGIC_MILLISECONDS = 6.0
DEFAULT_FRAMES = 240
DEFAULT_SECONDS = 4.0
MAXIMUM_REPORTED_ITEMS = 10


def emit(message: str) -> None:
    """Write a line of the probe's report to stdout."""
    sys.stdout.write(message + '\n')


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line.

    Returns:
        The parsed arguments.

    """
    parser = argparse.ArgumentParser(
        description='Probe for audio glitches in samples and GIL starvation of the mixer.'
    )
    parser.add_argument('--mode', choices=('dsp', 'realtime', 'both'), default='both')
    parser.add_argument('--seconds', type=float, default=DEFAULT_SECONDS, help='dsp: playback time')
    parser.add_argument('--game-logic-ms', type=float, default=DEFAULT_GAME_LOGIC_MILLISECONDS)
    parser.add_argument('--target-fps', type=float, default=DEFAULT_TARGET_FPS)
    parser.add_argument('--frames', type=int, default=DEFAULT_FRAMES, help='realtime: frame count')
    parser.add_argument(
        '--switch-interval-ms',
        type=float,
        default=GIL_SWITCH_INTERVAL_SECONDS * 1000.0,
        help=(
            'GIL switch interval; 5 shows the old Python default (indicative only: on a quiet '
            'machine the old setting can land just under the 5.8 ms risk threshold)'
        ),
    )
    parser.add_argument(DSP_WORKER_FLAG, help=argparse.SUPPRESS)  # Internal: recording subprocess
    return parser.parse_args(argv)


def run_dsp_worker(arguments: argparse.Namespace) -> None:
    """Play the elevator motor through the disk driver (runs inside the subprocess)."""
    # Imports are deferred: SDL_AUDIODRIVER must be set (by the parent) before pygame loads
    import pygame

    from glitchygames.audio.live import LiveAudio, reserve_live_voice_pool
    from glitchygames.audio.recipes import Tremolo
    from glitchygames.audio.synth import Waveform
    from glitchygames.examples.clockwork_keep.constants import (
        ELEVATOR_MOTOR_IDLE_FREQUENCY,
        ELEVATOR_MOTOR_LOW_PASS_CUTOFF,
        ELEVATOR_MOTOR_MAXIMUM_VOLUME,
        ELEVATOR_MOTOR_MINIMUM_VOLUME,
        ELEVATOR_MOTOR_PEAK_FREQUENCY,
        ELEVATOR_MOTOR_TREMOLO_DEPTH,
        ELEVATOR_MOTOR_TREMOLO_RATE,
    )

    sys.setswitchinterval(arguments.switch_interval_ms / 1000.0)
    pygame.mixer.init()
    live_audio = LiveAudio(channel_indices=reserve_live_voice_pool(1))
    motor = live_audio.create_voice(
        owner=object(),
        waveform=Waveform.SAWTOOTH,
        frequency=ELEVATOR_MOTOR_IDLE_FREQUENCY,
        volume=ELEVATOR_MOTOR_MINIMUM_VOLUME,
        low_pass_cutoff=ELEVATOR_MOTOR_LOW_PASS_CUTOFF,
        tremolo=Tremolo(rate_hz=ELEVATOR_MOTOR_TREMOLO_RATE, depth=ELEVATOR_MOTOR_TREMOLO_DEPTH),
    )
    motor.start()

    timer = FastTimer()
    period_ns = timer.start_frame(arguments.target_fps)
    start_ns = time.perf_counter_ns()
    deadline_ns = start_ns + period_ns
    while (time.perf_counter_ns() - start_ns) / 1e9 < arguments.seconds:
        busy_python_work(seconds=arguments.game_logic_ms / 1000.0)
        # The ride uses ease_in_sine, whose normalized slope is sin(pi * progress / 2)
        progress = min(1.0, (time.perf_counter_ns() - start_ns) / 1e9 / arguments.seconds)
        speed_fraction = math.sin(math.pi * progress / 2.0)
        motor.frequency = ELEVATOR_MOTOR_IDLE_FREQUENCY + (
            (ELEVATOR_MOTOR_PEAK_FREQUENCY - ELEVATOR_MOTOR_IDLE_FREQUENCY) * speed_fraction
        )
        motor.volume = ELEVATOR_MOTOR_MINIMUM_VOLUME + (
            (ELEVATOR_MOTOR_MAXIMUM_VOLUME - ELEVATOR_MOTOR_MINIMUM_VOLUME) * speed_fraction
        )
        motor.update()
        timer.sleep_until_next(deadline_ns)
        deadline_ns = timer.compute_deadline(deadline_ns, period_ns)
    live_audio.release_voice(motor)
    pygame.mixer.quit()  # Flushes the recording


def load_recording(path: Path) -> FloatArray:
    """Read the disk driver's raw signed 16-bit stereo file as the left channel in -1..1.

    Returns:
        The left channel samples.

    """
    raw = np.fromfile(path, dtype='<i2')
    return raw[: raw.size - raw.size % 2].reshape(-1, 2)[:, 0].astype(np.float64) / 32768.0


def run_dsp_mode() -> None:
    """Record the motor in a subprocess and analyze the recording."""
    emit('== dsp: recorded elevator motor, analyzed for glitches ==')
    with tempfile.TemporaryDirectory() as directory:
        recording_path = Path(directory) / 'motor.raw'
        environment = {
            **os.environ,
            'SDL_AUDIODRIVER': 'disk',
            'SDL_DISKAUDIOFILE': str(recording_path),
            'SDL_VIDEODRIVER': 'dummy',
        }
        subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
            [
                sys.executable,
                str(Path(__file__).resolve()),
                *sys.argv[1:],
                DSP_WORKER_FLAG,
                str(recording_path),
            ],
            env=environment,
            check=True,
        )
        samples = load_recording(recording_path)

    gaps = find_silent_gaps(samples)
    discontinuities = find_discontinuities(samples)
    edges = describe_edges(samples)
    emit(f'samples analyzed: {samples.size} ({samples.size / DEFAULT_SAMPLE_RATE:.2f} s)')
    emit(f'silent gaps inside the sound (>= 32 zeros): {len(gaps)}')
    for start, length in gaps[:MAXIMUM_REPORTED_ITEMS]:
        emit(f'  gap at sample {start}, {length} samples')
    emit(f'discontinuities (2nd difference spikes): {len(discontinuities)}')
    emit(f'  first indices: {discontinuities[:MAXIMUM_REPORTED_ITEMS]}')
    emit(f'onset first samples: {[round(value, 5) for value in edges.onset_samples]}')
    emit(
        f'final sample {edges.final_sample:.5f}, typical step {edges.typical_step:.5f}, '
        f"cut ratio {edges.cut_ratio:.1f} (large = hard cut; expected at the ride's arrival)"
    )
    emit('meaning: gaps are mixer dropouts; discontinuities are steps/clicks in the waveform;')
    emit('         a smooth onset ramps up from ~0. The disk driver cannot show GIL delays.')


def run_realtime_mode(arguments: argparse.Namespace) -> bool:
    """Measure GIL wait for a background thread under game-like load.

    Returns:
        True when the p99 wait puts the mixer buffer at risk.

    """
    emit('== realtime: GIL wait of a 2 ms-period background thread under game load ==')
    report: LockWaitReport = measure_lock_wait(
        frames=arguments.frames,
        target_fps=arguments.target_fps,
        game_logic_seconds=arguments.game_logic_ms / 1000.0,
        switch_interval_seconds=arguments.switch_interval_ms / 1000.0,
    )
    buffer_milliseconds = DEFAULT_BUFFER_SAMPLES / DEFAULT_SAMPLE_RATE * 1000.0
    emit(
        f'switch interval {arguments.switch_interval_ms} ms, game logic '
        f'{arguments.game_logic_ms} ms/frame at {arguments.target_fps} FPS, '
        f'{arguments.frames} frames'
    )
    emit(
        f'wait for the GIL: median {report.median_milliseconds:.2f} ms, '
        f'p99 {report.p99_milliseconds:.2f} ms (decides the result), '
        f'max {report.maximum_milliseconds:.2f} ms (includes OS scheduling noise) '
        f'({report.sample_count} samples)'
    )
    emit(
        f'budget: mixer buffer {DEFAULT_BUFFER_SAMPLES} samples = {buffer_milliseconds:.1f} ms; '
        f'risk threshold for p99 (half) {buffer_milliseconds / 2:.1f} ms'
    )
    at_risk = dropout_risk(report)
    emit('RESULT: ' + ('DROPOUT RISK (clicks likely)' if at_risk else 'ok (within budget)'))
    emit('meaning: the mixer callback waits like this thread does; p99 waits near the buffer')
    emit('         length leave a silent gap, heard as a click at each chunk boundary.')
    return at_risk


def main() -> int:
    """Run the requested modes.

    Returns:
        ``ExitCode.AUDIO_DROPOUT_RISK`` when the realtime check finds dropout risk, otherwise
        ``ExitCode.SUCCESS``.

    """
    arguments = parse_arguments()
    if arguments.dsp_worker is not None:
        run_dsp_worker(arguments)
        return ExitCode.SUCCESS
    at_risk = False
    if arguments.mode in {'dsp', 'both'}:
        run_dsp_mode()
    if arguments.mode in {'realtime', 'both'}:
        at_risk = run_realtime_mode(arguments)
    return ExitCode.AUDIO_DROPOUT_RISK if at_risk else ExitCode.SUCCESS


if __name__ == '__main__':
    sys.exit(main())
