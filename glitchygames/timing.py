#!/usr/bin/env python3
"""High-resolution timer backends and factory for draw-loop pacing.

Backends:
- PygameTimer: uses pygame.time.delay/get_ticks
- FastTimer: uses time.perf_counter_ns() with sleep+spin
"""

from __future__ import annotations

import sys
import time
from typing import Optional


def ms_to_ns(ms: float) -> int:
    return int(ms * 1_000_000)


def s_to_ns(s: float) -> int:
    return int(s * 1_000_000_000)


class PygameTimer:
    """Legacy pygame-based timer backend."""

    def __init__(self) -> None:
        import pygame  # local import to avoid hard dependency at import-time

        self._pg = pygame

    def ns_now(self) -> int:
        return self._pg.time.get_ticks() * 1_000_000

    def start_frame(self, target_fps: int) -> int:
        if target_fps and target_fps > 0:
            return 1_000_000_000 // target_fps
        return 0

    def compute_deadline(self, prev_deadline_ns: Optional[int], period_ns: int) -> int:
        if prev_deadline_ns is None:
            return self.ns_now() + period_ns
        return prev_deadline_ns + period_ns

    def sleep_until_next(self, deadline_ns: int) -> int:
        remaining_ns = deadline_ns - self.ns_now()
        if remaining_ns > 0:
            self._pg.time.delay(remaining_ns // 1_000_000)
        return self.ns_now()


class FastTimer:
    """perf_counter_ns-based timer with sleep+spin pacing."""

    def __init__(self, sleep_granularity_ns: int = 1_000_000, windows_timer_1ms: bool = False) -> None:
        self.sleep_granularity_ns = max(0, int(sleep_granularity_ns))
        self._win_period_on = False
        if windows_timer_1ms and sys.platform.startswith("win"):
            try:
                import ctypes

                ctypes.windll.winmm.timeBeginPeriod(1)
                self._win_period_on = True
            except Exception:
                self._win_period_on = False

    def __del__(self) -> None:
        if self._win_period_on and sys.platform.startswith("win"):
            try:
                import ctypes

                ctypes.windll.winmm.timeEndPeriod(1)
            except Exception:
                pass

    def ns_now(self) -> int:
        return time.perf_counter_ns()

    def start_frame(self, target_fps: int) -> int:
        if target_fps and target_fps > 0:
            return 1_000_000_000 // target_fps
        return 0

    def compute_deadline(self, prev_deadline_ns: Optional[int], period_ns: int) -> int:
        if prev_deadline_ns is None:
            return self.ns_now() + period_ns
        return prev_deadline_ns + period_ns

    def sleep_until_next(self, deadline_ns: int) -> int:
        # Coarse sleep first
        while True:
            now = self.ns_now()
            remaining = deadline_ns - now
            if remaining <= 0:
                return now
            # If we have time above the granularity plus a small spin window, sleep
            if self.sleep_granularity_ns > 0 and remaining > (self.sleep_granularity_ns + 1_000_000):
                time.sleep((remaining - 1_000_000) / 1e9)
            else:
                break
        # Final spin to tighten
        while True:
            now = self.ns_now()
            if now >= deadline_ns:
                return now


def create_timer(timer_type: Optional[str], options: Optional[dict] = None):
    tt = (timer_type or (options or {}).get("timer_backend") or "pygame").lower()
    if tt == "fast":
        sleep_gran_ns = (options or {}).get("sleep_granularity_ns", 1_000_000)
        windows_1ms = bool((options or {}).get("windows_timer_1ms", False))
        return FastTimer(sleep_granularity_ns=sleep_gran_ns, windows_timer_1ms=windows_1ms)
    return PygameTimer()


