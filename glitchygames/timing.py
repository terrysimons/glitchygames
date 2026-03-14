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

LOG = logging.getLogger(__name__)


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

    def start_frame(self, target_fps: int) -> int:
        """Return the frame period in nanoseconds for the given target FPS.

        Returns:
            int: The frame period in nanoseconds.

        """
        if target_fps and target_fps > 0:
            return 1_000_000_000 // target_fps
        return 0

    def compute_deadline(self, prev_deadline_ns: int | None, period_ns: int) -> int:
        """Compute the next frame deadline in nanoseconds.

        Returns:
            int: The deadline in nanoseconds.

        """
        if prev_deadline_ns is None:
            return self.ns_now() + period_ns
        return prev_deadline_ns + period_ns

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
        self, sleep_granularity_ns: int = 1_000_000, windows_timer_1ms: bool = False
    ) -> None:
        """Initialize the FastTimer with sleep granularity and Windows timer options."""
        self.sleep_granularity_ns = max(0, int(sleep_granularity_ns))
        self._win_period_on = False
        if windows_timer_1ms and sys.platform.startswith("win"):
            try:
                import ctypes

                ctypes.windll.winmm.timeBeginPeriod(1)
                self._win_period_on = True
            except (OSError, AttributeError) as timer_error:
                LOG.debug("Windows timer resolution setup failed: %s", timer_error)
                self._win_period_on = False

    def __del__(self) -> None:
        """Clean up Windows timer resolution if it was changed."""
        if self._win_period_on and sys.platform.startswith("win"):
            try:
                import ctypes

                ctypes.windll.winmm.timeEndPeriod(1)
            except (OSError, AttributeError) as timer_error:
                LOG.debug("Windows timer resolution cleanup failed: %s", timer_error)

    def ns_now(self) -> int:
        """Return the current time in nanoseconds using perf_counter_ns.

        Returns:
            int: The current time in nanoseconds.

        """
        return time.perf_counter_ns()

    def start_frame(self, target_fps: int) -> int:
        """Return the frame period in nanoseconds for the given target FPS.

        Returns:
            int: The frame period in nanoseconds.

        """
        if target_fps and target_fps > 0:
            return 1_000_000_000 // target_fps
        return 0

    def compute_deadline(self, prev_deadline_ns: int | None, period_ns: int) -> int:
        """Compute the next frame deadline in nanoseconds.

        Returns:
            int: The deadline in nanoseconds.

        """
        if prev_deadline_ns is None:
            return self.ns_now() + period_ns
        return prev_deadline_ns + period_ns

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


def create_timer(timer_type: str | None, options: dict | None = None) -> PygameTimer | FastTimer:
    """Create a timer backend instance based on the given type string.

    Returns:
        PygameTimer | FastTimer: The created timer backend.

    """
    tt = (timer_type or (options or {}).get("timer_backend") or "pygame").lower()
    if tt == "fast":
        sleep_gran_ns = (options or {}).get("sleep_granularity_ns", 1_000_000)
        windows_1ms = bool((options or {}).get("windows_timer_1ms", False))
        return FastTimer(sleep_granularity_ns=sleep_gran_ns, windows_timer_1ms=windows_1ms)
    return PygameTimer()
