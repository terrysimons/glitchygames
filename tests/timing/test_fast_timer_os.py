#!/usr/bin/env python3
"""OS-level accuracy tests for the FastTimer backend."""

import sys
import time
from math import comb

import pytest

from glitchygames.timing import FastTimer, create_timer

# The accuracy tests claim, with 99.999% confidence, that the timer's median overshoot (how late
# it usually wakes, which is what the timer controls) is under the bound. The tail is not
# tested: it is how long the OS takes to reschedule a busy process (p99 7 ms, max 9 ms on macOS
# with every core busy), so it measures the machine; the engine reports it with
# --log-timer-jitter instead.
#
# The claim is distribution-free: sorted, the MEDIAN_UPPER_BOUND_RANK-th smallest of
# INDEPENDENT_SAMPLES independent overshoots is at or above the true median with probability at
# least CONFIDENCE (the binomial sign test), so asserting it is under the bound is wrong at most
# 1 time in 100,000. Independence: on macOS with every core busy, a late 3 ms sleep made the next
# few late 45-64% of the time (16% otherwise), back to the baseline after about 60 ms (the
# longest late run was 15 sleeps, about 45 ms), so the samples are SAMPLE_SPACING_SECONDS apart.
# A good timer fails only if 29 or more of the 100 samples are over the bound: with 3% of sleeps
# over 5 ms (measured, every core busy) that is about 1e-20, with 10% about 1e-7, with 20% about
# 2e-2 (then 150 samples would be needed). Each test takes about 7.5 s, nearly all of it waiting.
CONFIDENCE = 0.99999
INDEPENDENT_SAMPLES = 100
SAMPLE_SPACING_SECONDS = 0.075


def _median_upper_bound_rank(*, samples: int, confidence: float) -> int:
    """The 1-based rank whose sorted sample bounds the true median from above with confidence.

    The k-th smallest of n independent samples is below the true median only if k or more of
    them are, which has probability P(Binomial(n, 1/2) >= k) whatever the distribution.

    Returns:
        The smallest rank k with P(Binomial(samples, 1/2) >= k) <= 1 - confidence.

    """
    allowed = (1 - confidence) * 2**samples
    tail = 0
    for rank in range(samples, 0, -1):
        tail += comb(samples, rank)
        if tail > allowed:
            return rank + 1
    return 1


MEDIAN_UPPER_BOUND_RANK = _median_upper_bound_rank(
    samples=INDEPENDENT_SAMPLES, confidence=CONFIDENCE
)


def _median_overshoot_upper_bound_ns(*, timer: FastTimer, sleep_ns: int) -> int:
    """Measure INDEPENDENT_SAMPLES spaced sleeps; return a CONFIDENCE upper bound on the median.

    Returns:
        The MEDIAN_UPPER_BOUND_RANK-th smallest overshoot past each deadline, in nanoseconds.

    """
    overshoots = []
    for _ in range(INDEPENDENT_SAMPLES):
        # Unmeasured gap: a burst of load that made the last sleep late is over by now
        time.sleep(SAMPLE_SPACING_SECONDS)
        deadline = timer.ns_now() + sleep_ns
        woke = timer.sleep_until_next(deadline)
        assert woke >= deadline
        overshoots.append(woke - deadline)
    return sorted(overshoots)[MEDIAN_UPPER_BOUND_RANK - 1]


def test_median_upper_bound_rank_is_the_sign_test_rank():
    """100 samples at 99.999%: the 72nd smallest (P(Binomial(100, 1/2) >= 72) is about 6.3e-6)."""
    assert MEDIAN_UPPER_BOUND_RANK == 72
    tail_at_rank = sum(comb(100, count) for count in range(72, 101)) / 2**100
    tail_one_lower = sum(comb(100, count) for count in range(71, 101)) / 2**100
    assert tail_at_rank <= 1 - CONFIDENCE < tail_one_lower


def _os_overshoot_ns_default() -> int:
    if sys.platform.startswith('win'):
        return 20_000_000
    return 5_000_000


def test_factory_fast_backend_instantiates():
    """Test that create_timer with 'fast' returns a FastTimer instance."""
    t = create_timer('fast', {'sleep_granularity_ns': 1_000_000, 'windows_timer_1ms': False})
    assert isinstance(t, FastTimer)


def test_fast_timer_basic_sleep_accuracy():
    """Test that FastTimer sleep accuracy is within OS-specific bounds."""
    t = FastTimer(sleep_granularity_ns=1_000_000, windows_timer_1ms=False)
    overshoot = _median_overshoot_upper_bound_ns(timer=t, sleep_ns=3_000_000)  # 3ms
    assert overshoot < _os_overshoot_ns_default()


def test_fast_timer_spin_tighten_accuracy():
    """Test that spin-only mode achieves tight sleep accuracy."""
    t = FastTimer(sleep_granularity_ns=0, windows_timer_1ms=False)
    overshoot = _median_overshoot_upper_bound_ns(timer=t, sleep_ns=1_000_000)  # 1ms
    assert overshoot < _os_overshoot_ns_default()


@pytest.mark.skipif(
    not sys.platform.startswith('win'),
    reason='Windows-only timing resolution test',
)
def test_fast_timer_windows_1ms_option_tighter():
    """Test that Windows 1ms timer resolution yields tighter sleep accuracy."""
    t = FastTimer(sleep_granularity_ns=1_000_000, windows_timer_1ms=True)
    overshoot = _median_overshoot_upper_bound_ns(timer=t, sleep_ns=3_000_000)  # 3ms
    assert overshoot < 5_000_000
