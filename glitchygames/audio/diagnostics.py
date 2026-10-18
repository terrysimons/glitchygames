"""Audio glitch diagnostics: analyze rendered samples and measure GIL contention.

Two kinds of glitch are covered:

- DSP glitches live in the samples themselves (gaps, steps, abrupt edges); the pure functions
  here find them in a recording, and need only numpy.
- Handover glitches come from the mixer thread waiting for Python's GIL while the main thread is
  busy (pygame's channel-finished callback takes the GIL to start the next live-voice chunk). A
  disk-driver recording cannot show these, because that driver is not real-time: a late callback
  just writes later. ``measure_lock_wait`` measures the wait directly instead.

See BUGS.md #27 and scripts/audio_glitch_probe.py.
"""

from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from glitchygames.timing import FastTimer

FloatArray = npt.NDArray[np.float64]

DEFAULT_MINIMUM_GAP_SAMPLES = 32
DEFAULT_DISCONTINUITY_SENSITIVITY = 8.0
DEFAULT_BUFFER_SAMPLES = 512
DEFAULT_SAMPLE_RATE = 44100
DEFAULT_RISK_FRACTION = 0.5
ONSET_SAMPLE_COUNT = 8
SECONDS_TO_MILLISECONDS = 1000.0
NANOSECONDS_TO_MILLISECONDS = 1e-6
SLEEP_MARGIN_SECONDS = 0.001  # FastTimer sleeps until this long before the deadline, then spins


def find_silent_gaps(
    samples: FloatArray, *, minimum_samples: int = DEFAULT_MINIMUM_GAP_SAMPLES
) -> list[tuple[int, int]]:
    """Find runs of exact zeros strictly inside the sound.

    Leading and trailing silence (before the first and after the last non-zero sample) is not a
    gap. A real gap means the mixer ran dry between two chunks.

    Returns:
        (start index, length) of each run of at least minimum_samples zeros.

    """
    non_zero_indices = np.flatnonzero(samples)
    if non_zero_indices.size == 0:
        return []
    # Zero runs strictly inside the sound are exactly the spaces between consecutive non-zero
    # samples: a space of (next - previous - 1) zeros starting at previous + 1.
    run_lengths = np.diff(non_zero_indices) - 1
    run_starts = non_zero_indices[:-1] + 1
    long_enough = run_lengths >= minimum_samples
    return [
        (int(start), int(length))
        for start, length in zip(run_starts[long_enough], run_lengths[long_enough], strict=True)
    ]


def find_discontinuities(
    samples: FloatArray, *, sensitivity: float = DEFAULT_DISCONTINUITY_SENSITIVITY
) -> list[int]:
    """Find indices where the absolute second difference exceeds sensitivity x its 99th percentile.

    A smooth waveform has a small, steady second difference; a click or step makes a spike.

    Returns:
        Sample indices of the spikes (empty when the signal is too short or perfectly smooth).

    """
    if samples.size < 3:  # ruff: ignore[magic-value-comparison]
        return []
    second_difference = np.abs(np.diff(samples, n=2))
    threshold = sensitivity * float(np.percentile(second_difference, 99))
    if threshold <= 0.0:
        return []
    # diff(n=2)[i] is centered on sample i + 1
    return [int(index) + 1 for index in np.flatnonzero(second_difference > threshold)]


@dataclass(frozen=True)
class EdgeReport:
    """How a sound starts and ends.

    Attributes:
        onset_samples: The first few non-zero samples (a smooth onset ramps up from zero).
        final_sample: The last non-zero sample before the trailing silence.
        typical_step: Median absolute sample-to-sample change.
        cut_ratio: final_sample / typical_step; near or below 1 is a fade, large is a hard cut.

    """

    onset_samples: tuple[float, ...]
    final_sample: float
    typical_step: float
    cut_ratio: float


def describe_edges(samples: FloatArray) -> EdgeReport:
    """Describe the onset and the final cut of a sound.

    Returns:
        The edge report (all zeros for pure silence).

    """
    non_zero_indices = np.flatnonzero(samples)
    if non_zero_indices.size == 0:
        return EdgeReport(onset_samples=(), final_sample=0.0, typical_step=0.0, cut_ratio=0.0)
    first_index = int(non_zero_indices[0])
    last_index = int(non_zero_indices[-1])
    sound = samples[first_index : last_index + 1]
    typical_step = float(np.median(np.abs(np.diff(sound)))) if sound.size > 1 else 0.0
    final_sample = float(samples[last_index])
    cut_ratio = final_sample / typical_step if typical_step > 0.0 else 0.0
    onset = tuple(float(value) for value in sound[:ONSET_SAMPLE_COUNT])
    return EdgeReport(
        onset_samples=onset,
        final_sample=final_sample,
        typical_step=typical_step,
        cut_ratio=cut_ratio,
    )


@dataclass(frozen=True)
class LockWaitReport:
    """How late a background thread acquired the GIL, in milliseconds."""

    median_milliseconds: float
    p99_milliseconds: float
    maximum_milliseconds: float
    sample_count: int


def busy_python_work(*, seconds: float) -> None:
    """Hold the GIL with pure Python work (what a game's update/draw does) for a duration."""
    end_time = time.perf_counter() + seconds
    counter = 0
    while time.perf_counter() < end_time:
        counter += 1


def _pace_until(*, deadline_ns: int, timer: FastTimer, yield_in_spin: bool) -> None:
    """Coarse sleep, then spin until the deadline (FastTimer-style), optionally without yielding."""
    if yield_in_spin:
        timer.sleep_until_next(deadline_ns)
        return
    remaining_seconds = (deadline_ns - time.perf_counter_ns()) / 1e9
    if remaining_seconds > SLEEP_MARGIN_SECONDS:
        time.sleep(remaining_seconds - SLEEP_MARGIN_SECONDS)
    while time.perf_counter_ns() < deadline_ns:
        pass


def measure_lock_wait(  # ruff: ignore[too-many-arguments]
    *,
    frames: int,
    target_fps: float,
    game_logic_seconds: float,
    period_seconds: float = 0.002,
    switch_interval_seconds: float | None = None,
    yield_in_spin: bool = True,
) -> LockWaitReport:
    """Measure how late a background thread gets the GIL while the main thread plays a game.

    A background thread wakes every period_seconds and records how much later than requested it
    resumed (it needs the GIL to resume, exactly like the mixer's channel-finished callback). The
    calling thread simulates frames: busy Python work for game_logic_seconds, then a FastTimer-style
    coarse sleep plus final spin up to the frame deadline. The previous switch interval is restored.

    Returns:
        Median, 99th percentile and maximum extra wake-up delay in milliseconds.

    """
    previous_switch_interval = sys.getswitchinterval()
    if switch_interval_seconds is not None:
        sys.setswitchinterval(switch_interval_seconds)
    waits_milliseconds: list[float] = []
    stop_event = threading.Event()

    def background_listener() -> None:
        while not stop_event.is_set():
            before_ns = time.perf_counter_ns()
            time.sleep(period_seconds)
            elapsed_ns = time.perf_counter_ns() - before_ns
            late_ns = elapsed_ns - int(period_seconds * 1e9)
            waits_milliseconds.append(max(0.0, late_ns * NANOSECONDS_TO_MILLISECONDS))

    listener = threading.Thread(target=background_listener, name='lock-wait-listener', daemon=True)
    timer = FastTimer()
    period_ns = timer.start_frame(target_fps)
    try:
        listener.start()
        deadline_ns = time.perf_counter_ns() + period_ns
        for _ in range(frames):
            busy_python_work(seconds=game_logic_seconds)
            _pace_until(deadline_ns=deadline_ns, timer=timer, yield_in_spin=yield_in_spin)
            deadline_ns = timer.compute_deadline(deadline_ns, period_ns)
    finally:
        stop_event.set()
        listener.join()
        sys.setswitchinterval(previous_switch_interval)

    if not waits_milliseconds:
        return LockWaitReport(
            median_milliseconds=0.0,
            p99_milliseconds=0.0,
            maximum_milliseconds=0.0,
            sample_count=0,
        )
    waits = np.array(waits_milliseconds)
    return LockWaitReport(
        median_milliseconds=float(np.median(waits)),
        p99_milliseconds=float(np.percentile(waits, 99)),
        maximum_milliseconds=float(waits.max()),
        sample_count=int(waits.size),
    )


def dropout_risk(
    report: LockWaitReport,
    *,
    buffer_samples: int = DEFAULT_BUFFER_SAMPLES,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    risk_fraction: float = DEFAULT_RISK_FRACTION,
) -> bool:
    """Say whether the p99 GIL wait reaches risk_fraction of the mixer buffer's duration.

    The p99 is used rather than the maximum: on a busy machine the maximum is dominated by OS
    scheduling noise that no GIL setting can remove, while the p99 separates a fixed switch
    interval (about 2 ms) from the 5 ms default (about 6.4 ms).

    Returns:
        True when p99 wait >= risk_fraction x buffer duration (512 samples at 44100 Hz is
        11.6 ms, so 5.8 ms by default).

    """
    buffer_milliseconds = buffer_samples / sample_rate * SECONDS_TO_MILLISECONDS
    return report.p99_milliseconds >= risk_fraction * buffer_milliseconds
