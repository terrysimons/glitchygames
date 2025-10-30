#!/usr/bin/env python3
import time

import pytest

from glitchygames.timing import FastTimer, PygameTimer


def test_fast_timer_compute_deadline_monotonic():
    t = FastTimer(sleep_granularity_ns=0)
    period = 1_000_000  # 1ms
    d0 = t.compute_deadline(None, period)
    d1 = t.compute_deadline(d0, period)
    d2 = t.compute_deadline(d1, period)
    assert d0 < d1 < d2


@pytest.mark.skip(reason="Pygame may not be initialized in CI; ns_now() still callable if available")
def test_pygame_timer_ns_now_monotonic():
    p = PygameTimer()
    a = p.ns_now()
    time.sleep(0.001)
    b = p.ns_now()
    assert b >= a


