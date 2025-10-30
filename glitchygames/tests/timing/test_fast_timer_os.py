#!/usr/bin/env python3
import sys

import pytest

from glitchygames.timing import FastTimer, create_timer


def _os_overshoot_ns_default() -> int:
    if sys.platform.startswith("win"):
        # Without timeBeginPeriod, Windows can overshoot ~15ms; be generous
        return 20_000_000
    # macOS/Linux typically within a few ms
    return 5_000_000


def test_factory_fast_backend_instantiates():
    t = create_timer("fast", {"sleep_granularity_ns": 1_000_000, "windows_timer_1ms": False})
    assert isinstance(t, FastTimer)


def test_fast_timer_basic_sleep_accuracy():
    t = FastTimer(sleep_granularity_ns=1_000_000, windows_timer_1ms=False)
    start = t.ns_now()
    deadline = start + 3_000_000  # 3ms
    woke = t.sleep_until_next(deadline)
    assert woke >= deadline
    overshoot = woke - deadline
    assert overshoot < _os_overshoot_ns_default()


def test_fast_timer_spin_tighten_accuracy():
    # No sleep floor: rely on final spin to tighten
    t = FastTimer(sleep_granularity_ns=0, windows_timer_1ms=False)
    start = t.ns_now()
    deadline = start + 1_000_000  # 1ms
    woke = t.sleep_until_next(deadline)
    assert woke >= deadline
    overshoot = woke - deadline
    # With spin, we still allow a few ms overshoot; set OS-specific bound
    assert overshoot < _os_overshoot_ns_default()


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="Windows-only timing resolution test")
def test_fast_timer_windows_1ms_option_tighter():
    # With timeBeginPeriod(1), expect tighter overshoot than default Windows
    t = FastTimer(sleep_granularity_ns=1_000_000, windows_timer_1ms=True)
    start = t.ns_now()
    deadline = start + 3_000_000  # 3ms
    woke = t.sleep_until_next(deadline)
    assert woke >= deadline
    overshoot = woke - deadline
    # Expect notably tighter than default 20ms bound; assert < 5ms
    assert overshoot < 5_000_000


