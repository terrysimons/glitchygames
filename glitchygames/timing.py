#!/usr/bin/env python3
"""High-resolution timer backends and factory for draw-loop pacing.

Backends:
- PygameTimer: uses pygame.time.delay/get_ticks
- FastTimer: uses time.perf_counter_ns() with sleep+spin: it sleeps so that it wakes
  ``sleep_granularity_ns`` before the deadline, then spins the rest

A sleep's delay past its length is modelled as a constant plus a fraction of the length
(``SleepModel``): macOS lets a normal-priority sleep run late by a quarter of its length (4 ms
wakes 1.01 ms late, 16 ms 4.01 ms; measured 2026-10-21), so a fixed spin left most frames 1-2 ms
late; at background priority the delay is a flat 85-100 ms, and a CircleCI macOS job woke 2 ms
sleeps 15 ms late. Without a model (``--timer-backend fast``) FastTimer assumes a sleep wakes on
time. ``--timer-backend auto`` (the engine's default) measures the model
(``measure_sleep_model``: short and long probe sleeps) when the engine starts a paced game, or
at the first paced frame (a run that never paces never measures), and sizes each sleep so its
predicted wake lands ``sleep_granularity_ns`` before the deadline; where even no sleep could
(a delay longer than the wait), it spins the whole wait. The cost is CPU spent spinning, only
where the OS delays sleeps.
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict

LOG = logging.getLogger(__name__)

# 60.01 rather than 60 so the average frame lands just above 60 FPS (16.664 ms vs the
# 16.667 ms limit). The 2.8 us margin is smaller than timer wake-up jitter, so individual
# frames fall either side of 60; a higher target such as 60.5 keeps nearly every frame
# above it (BUGS.md #26: 99.2% of frames reached the target at 60.5).
DEFAULT_TARGET_FPS = 60.01

# pygame's mixer callback takes the GIL to start the next live-voice chunk. With Python's
# default 5 ms switch interval a busy main thread delayed it up to ~6.8 ms, an audible click
# at every chunk boundary; 0.5 ms measured p99 1.16 ms against an 11.6 ms mixer buffer
# (BUGS.md #27; scripts/audio_glitch_probe.py reproduces the measurement).
GIL_SWITCH_INTERVAL_SECONDS = 0.0005

# FastTimer's final spin: how long before each deadline its sleep is to wake
DEFAULT_SLEEP_GRANULARITY_NS = 1_000_000
# Calibration probes: this many sleeps of each length (about 0.1 s at startup on a good machine)
SLEEP_CALIBRATION_SAMPLES = 10
SHORT_SLEEP_PROBE_NS = 1_000_000
LONG_SLEEP_PROBE_NS = 8_000_000
# The fraction of probe sleeps the model covers: one very late wake does not make every frame
# spin for it
SLEEP_CALIBRATION_PERCENTILE = 0.9
# The --timer-backend choices
TIMER_BACKEND_AUTO = 'auto'
TIMER_BACKEND_FAST = 'fast'
TIMER_BACKEND_PYGAME = 'pygame'


class SleepModel(BaseModel):
    """How late this machine's OS wakes a sleep: ``constant_ns + fraction * length``.

    Attributes:
        constant_ns: The delay every sleep has, whatever its length.
        fraction: The delay per nanosecond slept (macOS normal priority: 0.25).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    constant_ns: int
    fraction: float

    def sleep_ns_to_wake_by(self: Self, *, wake_in_ns: int) -> int:
        """Return how long to sleep to wake (as predicted) ``wake_in_ns`` from now.

        Returns:
            The sleep length; 0 or less when even no sleep would wake in time (spin instead).

        """
        return int((wake_in_ns - self.constant_ns) / (1.0 + self.fraction))


# What FastTimer assumes without a model (--timer-backend fast): a sleep wakes on time
SLEEP_WAKES_ON_TIME = SleepModel(constant_ns=0, fraction=0.0)


class PacingTimer(BaseModel):
    """What paces a run's frames, as a recording's provenance names it.

    Attributes:
        backend: 'fast' (FastTimer) or 'pygame' (PygameTimer).
        sleep_granularity_ns: How long before each deadline FastTimer's sleep is to wake (its
            final spin); None for PygameTimer.
        sleep_model: The calibrated sleep delay (``measure_sleep_model``), or None when not
            calibrated (FastTimer then assumes sleeps wake on time).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    backend: Literal['fast', 'pygame']
    sleep_granularity_ns: int | None
    sleep_model: SleepModel | None


def describe_pacing_timer(*, pacing: PacingTimer) -> str:
    """Describe a pacing timer for the log.

    Returns:
        E.g. ``fast, final spin 1.0 ms (calibrated: sleeps wake 0.00 ms + 25% of their length
        late)``.

    """
    if pacing.sleep_granularity_ns is None:
        return pacing.backend
    description = f'{pacing.backend}, final spin {pacing.sleep_granularity_ns / 1e6:.1f} ms'
    if pacing.sleep_model is None:
        return description
    return (
        f'{description} (calibrated: sleeps wake {pacing.sleep_model.constant_ns / 1e6:.2f} ms '
        f'+ {pacing.sleep_model.fraction:.0%} of their length late)'
    )


def sleep_overshoot_ns(*, probe_ns: int, samples: int) -> int:
    """Measure how late this machine's OS wakes a sleep of one length.

    Args:
        probe_ns: Each sleep's length.
        samples: How many sleeps to take.

    Returns:
        The ``SLEEP_CALIBRATION_PERCENTILE`` overshoot past the requested length, in ns.

    """
    overshoots: list[int] = []
    for _ in range(samples):
        started = time.perf_counter_ns()
        time.sleep(probe_ns / 1e9)
        overshoots.append(max(0, time.perf_counter_ns() - started - probe_ns))
    overshoots.sort()
    return overshoots[int(SLEEP_CALIBRATION_PERCENTILE * (samples - 1))]


def measure_sleep_model() -> SleepModel:
    """Fit this machine's sleep delay from a short and a long probe.

    Returns:
        The model through both probes' delays (neither part negative).

    """
    short_ns = sleep_overshoot_ns(probe_ns=SHORT_SLEEP_PROBE_NS, samples=SLEEP_CALIBRATION_SAMPLES)
    long_ns = sleep_overshoot_ns(probe_ns=LONG_SLEEP_PROBE_NS, samples=SLEEP_CALIBRATION_SAMPLES)
    fraction = max(0.0, (long_ns - short_ns) / (LONG_SLEEP_PROBE_NS - SHORT_SLEEP_PROBE_NS))
    constant_ns = max(0, round(short_ns - fraction * SHORT_SLEEP_PROBE_NS))
    return SleepModel(constant_ns=constant_ns, fraction=fraction)


def ms_to_ns(ms: float) -> int:
    """Convert milliseconds to nanoseconds.

    Returns:
        int: The time in nanoseconds.

    """
    return int(ms * 1_000_000)


def s_to_ns(s: float) -> int:
    """Convert seconds to nanoseconds.

    Returns:
        int: The time in nanoseconds.

    """
    return int(s * 1_000_000_000)


def next_frame_deadline_ns(*, previous_deadline_ns: int | None, period_ns: int, now_ns: int) -> int:
    """Return the next frame deadline, shared by both timer backends.

    Normally the deadline is ``previous_deadline_ns + period_ns``, so a frame that wakes or
    finishes a little late is caught up by the next one and the long-run rate stays exactly at
    the target (60.01 FPS stays 60.01 FPS). After a hitch (a 2 s stall, a window drag) that
    deadline would be far in the past and the loop would run every missed frame back to back
    without sleeping (~120 frames for 2 s), so once the loop has fallen MORE than one full period
    behind (``now_ns - (previous_deadline_ns + period_ns) > period_ns``) the backlog is dropped
    and pacing re-anchors to ``now_ns + period_ns`` (BUGS.md #58).

    Boundary: exactly one period behind still catches up (strictly greater re-anchors). The
    PygameTimer clock is whole milliseconds, so its lateness is measured to within 1 ms.
    A non-positive period (uncapped) keeps the plain ``previous + period`` result.

    Args:
        previous_deadline_ns: The previous frame's deadline, or None for the first frame.
        period_ns: The frame period in nanoseconds.
        now_ns: The current time on the same clock as the deadlines.

    Returns:
        int: The next deadline in nanoseconds.

    """
    if previous_deadline_ns is None:
        return now_ns + period_ns
    scheduled_deadline_ns = previous_deadline_ns + period_ns
    if period_ns > 0 and now_ns - scheduled_deadline_ns > period_ns:
        return now_ns + period_ns
    return scheduled_deadline_ns


class PygameTimer:
    """Legacy pygame-based timer backend."""

    def __init__(self) -> None:
        """Initialize the PygameTimer by importing pygame."""
        import pygame  # local import to avoid hard dependency at import-time

        self._pg = pygame

    def pacing_timer(self: Self) -> PacingTimer:
        """Describe this timer for a recording's provenance.

        Returns:
            The pygame backend (whole-millisecond delays, no granularity).

        """
        return PacingTimer(
            backend=TIMER_BACKEND_PYGAME, sleep_granularity_ns=None, sleep_model=None
        )

    def calibrate(self: Self) -> None:
        """Do nothing: the legacy backend has nothing to calibrate."""

    def ns_now(self) -> int:
        """Return the current time in nanoseconds using pygame ticks.

        Returns:
            int: The current time in nanoseconds.

        """
        return self._pg.time.get_ticks() * 1_000_000

    def start_frame(self, target_fps: float) -> int:
        """Return the frame period in nanoseconds for the given target FPS.

        The target may be fractional (60.5 FPS); the period is rounded to the nearest
        nanosecond rather than floored, so 60 FPS is 16_666_667 ns.

        Returns:
            int: The frame period in nanoseconds (0 when the target is not positive).

        """
        if target_fps > 0:
            return round(1_000_000_000 / target_fps)
        return 0

    def compute_deadline(self, prev_deadline_ns: int | None, period_ns: int) -> int:
        """Compute the next frame deadline in nanoseconds (see next_frame_deadline_ns).

        Returns:
            int: The deadline in nanoseconds.

        """
        return next_frame_deadline_ns(
            previous_deadline_ns=prev_deadline_ns,
            period_ns=period_ns,
            now_ns=self.ns_now(),
        )

    def sleep_until_next(self, deadline_ns: int) -> int:
        """Sleep until the given deadline using pygame delay.

        Returns:
            int: The current time in nanoseconds after sleeping.

        """
        remaining_ns = deadline_ns - self.ns_now()
        if remaining_ns > 0:
            self._pg.time.delay(remaining_ns // 1_000_000)
        return self.ns_now()


class FastTimer:
    """perf_counter_ns-based timer with sleep+spin pacing."""

    def __init__(
        self,
        sleep_granularity_ns: int = DEFAULT_SLEEP_GRANULARITY_NS,
        *,
        windows_timer_1ms: bool = False,
        sleep_model: SleepModel | None = None,
        calibrate: bool = False,
    ) -> None:
        """Initialize the FastTimer with sleep granularity and Windows timer options.

        Args:
            sleep_granularity_ns: How long before each deadline the sleep is to wake, the final
                spin; 0 spins only.
            windows_timer_1ms: On Windows, request 1 ms system timer resolution.
            sleep_model: How late this machine's sleeps wake (``SleepModel``), or None to assume
                they wake on time.
            calibrate: Measure the sleep model (``measure_sleep_model``) when first needed:
                ``calibrate()`` or the first paced sleep. A run that never paces never measures.

        """
        self.sleep_granularity_ns = max(0, int(sleep_granularity_ns))
        self.sleep_model = sleep_model
        self._calibration_pending = calibrate
        self._win_period_on = False
        if windows_timer_1ms and sys.platform.startswith('win'):
            try:
                import ctypes

                ctypes.windll.winmm.timeBeginPeriod(1)
                self._win_period_on = True
            except (OSError, AttributeError) as timer_error:
                LOG.debug('Windows timer resolution setup failed: %s', timer_error)
                self._win_period_on = False

    def __del__(self) -> None:
        """Clean up Windows timer resolution if it was changed."""
        if self._win_period_on and sys.platform.startswith('win'):
            try:
                import ctypes

                ctypes.windll.winmm.timeEndPeriod(1)
            except (OSError, AttributeError) as timer_error:
                LOG.debug('Windows timer resolution cleanup failed: %s', timer_error)

    def calibrate(self: Self) -> None:
        """Measure this machine's sleep model, once, if this timer was made to calibrate."""
        if not self._calibration_pending:
            return
        self._calibration_pending = False
        self.sleep_model = measure_sleep_model()
        LOG.info('Timer calibrated: %s', describe_pacing_timer(pacing=self.pacing_timer()))

    def pacing_timer(self: Self) -> PacingTimer:
        """Describe this timer for a recording's provenance, as it is (never calibrating it).

        Returns:
            The fast backend, its final spin, and its sleep model (None if not calibrated).

        """
        return PacingTimer(
            backend=TIMER_BACKEND_FAST,
            sleep_granularity_ns=self.sleep_granularity_ns,
            sleep_model=self.sleep_model,
        )

    def ns_now(self) -> int:
        """Return the current time in nanoseconds using perf_counter_ns.

        Returns:
            int: The current time in nanoseconds.

        """
        return time.perf_counter_ns()

    def start_frame(self, target_fps: float) -> int:
        """Return the frame period in nanoseconds for the given target FPS.

        The target may be fractional (60.5 FPS); the period is rounded to the nearest
        nanosecond rather than floored, so 60 FPS is 16_666_667 ns.

        Returns:
            int: The frame period in nanoseconds (0 when the target is not positive).

        """
        if target_fps > 0:
            return round(1_000_000_000 / target_fps)
        return 0

    def compute_deadline(self, prev_deadline_ns: int | None, period_ns: int) -> int:
        """Compute the next frame deadline in nanoseconds (see next_frame_deadline_ns).

        Returns:
            int: The deadline in nanoseconds.

        """
        return next_frame_deadline_ns(
            previous_deadline_ns=prev_deadline_ns,
            period_ns=period_ns,
            now_ns=self.ns_now(),
        )

    def sleep_until_next(self, deadline_ns: int) -> int:
        """Sleep until the given deadline using a hybrid sleep+spin approach.

        Returns:
            int: The current time in nanoseconds after sleeping.

        """
        self.calibrate()
        model = self.sleep_model or SLEEP_WAKES_ON_TIME
        # Coarse sleep first, sized so its predicted wake is sleep_granularity_ns before the
        # deadline (a wake that came early sleeps again); a delay longer than the wait spins it
        while True:
            now = self.ns_now()
            remaining = deadline_ns - now
            if remaining <= 0:
                return now
            sleep_ns = (
                model.sleep_ns_to_wake_by(wake_in_ns=remaining - self.sleep_granularity_ns)
                if self.sleep_granularity_ns > 0
                else 0
            )
            if sleep_ns > 0:
                time.sleep(sleep_ns / 1e9)
            else:
                break
        # Final spin to tighten
        while True:
            now = self.ns_now()
            if now >= deadline_ns:
                return now
            # Yield the GIL so audio callbacks (live-voice chunk handovers) can run mid-spin
            time.sleep(0)


def pacing_timer_for_options(*, options: dict[str, Any]) -> PacingTimer:
    """Describe the timer ``create_timer`` would make from these options, uncalibrated.

    For a run's provenance before (or without) a timer: a rebaseline names its run while the
    engine starts, and a replay never calibrates.

    Args:
        options: The engine options (``timer_backend``, ``sleep_granularity_ns``).

    Returns:
        The backend, its final spin and no sleep model.

    """
    backend = str(options.get('timer_backend') or TIMER_BACKEND_FAST).lower()
    if backend not in {TIMER_BACKEND_AUTO, TIMER_BACKEND_FAST}:
        return PacingTimer(
            backend=TIMER_BACKEND_PYGAME, sleep_granularity_ns=None, sleep_model=None
        )
    given_granularity_ns = options.get('sleep_granularity_ns')
    return PacingTimer(
        backend=TIMER_BACKEND_FAST,
        sleep_granularity_ns=DEFAULT_SLEEP_GRANULARITY_NS
        if given_granularity_ns is None
        else max(0, int(given_granularity_ns)),
        sleep_model=None,
    )


def create_timer(
    timer_type: str | None,
    options: dict[str, Any] | None = None,
) -> PygameTimer | FastTimer:
    """Create a timer backend instance based on the given type string.

    'auto' is a FastTimer whose sleep model is measured (``measure_sleep_model``) when first
    needed (``calibrate()``, the first paced sleep); 'fast' assumes sleeps wake on time. Both use
    the options' ``sleep_granularity_ns`` as the final spin, or the 1 ms default; anything else
    is the legacy PygameTimer.

    Returns:
        PygameTimer | FastTimer: The created timer backend.

    """
    opts: dict[str, Any] = options or {}
    tt: str = (timer_type or opts.get('timer_backend', TIMER_BACKEND_FAST)).lower()
    if tt not in {TIMER_BACKEND_AUTO, TIMER_BACKEND_FAST}:
        return PygameTimer()
    given_granularity_ns = opts.get('sleep_granularity_ns')
    # auto's model is measured when first needed, with a Windows 1 ms timer resolution already
    # in force
    return FastTimer(
        sleep_granularity_ns=DEFAULT_SLEEP_GRANULARITY_NS
        if given_granularity_ns is None
        else int(given_granularity_ns),
        windows_timer_1ms=bool(opts.get('windows_timer_1ms')),
        calibrate=tt == TIMER_BACKEND_AUTO,
    )
