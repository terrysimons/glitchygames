#!/usr/bin/env python3
"""High-resolution timer backends and factory for draw-loop pacing.

Backends:
- PygameTimer: uses pygame.time.delay/get_ticks
- FastTimer: uses time.perf_counter_ns() with sleep+spin
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Any

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
        sleep_granularity_ns: int = 1_000_000,
        *,
        windows_timer_1ms: bool = False,
    ) -> None:
        """Initialize the FastTimer with sleep granularity and Windows timer options."""
        self.sleep_granularity_ns = max(0, int(sleep_granularity_ns))
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
        # Coarse sleep first
        while True:
            now = self.ns_now()
            remaining = deadline_ns - now
            if remaining <= 0:
                return now
            # If we have time above the granularity plus a small spin window, sleep
            if self.sleep_granularity_ns > 0 and remaining > (
                self.sleep_granularity_ns + 1_000_000
            ):
                time.sleep((remaining - 1_000_000) / 1e9)
            else:
                break
        # Final spin to tighten
        while True:
            now = self.ns_now()
            if now >= deadline_ns:
                return now
            # Yield the GIL so audio callbacks (live-voice chunk handovers) can run mid-spin
            time.sleep(0)


def create_timer(
    timer_type: str | None,
    options: dict[str, Any] | None = None,
) -> PygameTimer | FastTimer:
    """Create a timer backend instance based on the given type string.

    Returns:
        PygameTimer | FastTimer: The created timer backend.

    """
    opts: dict[str, Any] = options or {}
    tt: str = (timer_type or opts.get('timer_backend', 'fast')).lower()
    if tt == 'fast':
        sleep_gran_ns: int = int(opts.get('sleep_granularity_ns', 1_000_000))
        windows_1ms: bool = bool(opts.get('windows_timer_1ms'))
        return FastTimer(sleep_granularity_ns=sleep_gran_ns, windows_timer_1ms=windows_1ms)
    return PygameTimer()
