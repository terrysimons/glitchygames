#!/usr/bin/env python3
"""OS-level accuracy tests for the FastTimer backend."""

import sys
import time
from math import comb

import pytest

from glitchygames.timing import FastTimer, create_timer

# The accuracy tests compare the engine's timer with the OS's own sleep, in pairs: each pair is
# one timer sleep and one plain time.sleep of the same length, taken back to back (alternating
# which goes first). They claim, with 99.999% confidence, that the median of
# (timer overshoot - OS sleep overshoot) is under PAIRED_TOLERANCE_NS: the timer wakes no later
# than the OS's sleep would.
#
# The sleeping test uses the engine's default, --timer-backend auto (calibrated to the machine's
# sleep delay, so it spins wherever sleeping would wake late). Plain fast is not tested this way:
# it assumes a sleep wakes on time, and on CircleCI's macOS VM (2026-10-21; sleeps of 1 ms woke
# 11 ms late, 8 ms 66 ms late) its 3 ms deadlines were met 15 ms late, which the pairs could not
# tell apart from the OS sleep's own lateness (the VM wakes in coarse steps, so each sleep's
# delay depends on when it began). auto met the same deadlines 0.00 ms late (median; max
# 0.26 ms) on that VM.
#
# Why paired, not an absolute bound: the machine decides how late any sleep wakes. On macOS with
# every core busy, about 3% of 3 ms sleeps overshot 5 ms; a CircleCI macOS job (2026-10-21)
# woke at least 29 of 100 spaced sleeps 15 ms or more late while spin-only sleeps in the same
# job stayed accurate (a sleep-specific delay: timer coalescing or the VM's timer, or heavy time
# sharing); at background priority (taskpolicy -b) macOS wakes every sleep 55-65 ms late. No
# timer can wake before the OS lets it, so an absolute bound tests the machine. A pair shares the
# machine's state (load clusters over tens of milliseconds; a coarse OS timer delays both), so
# the difference tests the timer: it fails when FastTimer is the slower of the two.
#
# The claim is distribution-free: sorted, the MEDIAN_UPPER_BOUND_RANK-th smallest of
# INDEPENDENT_SAMPLES independent differences is at or above the true median with probability at
# least CONFIDENCE (the binomial sign test), so asserting it is under the tolerance is wrong at
# most 1 time in 100,000. Independence: on macOS with every core busy, a late 3 ms sleep made
# the next few late 45-64% of the time (16% otherwise), back to the baseline after about 60 ms
# (the longest late run was 15 sleeps, about 45 ms), so the pairs are SAMPLE_SPACING_SECONDS
# apart. A good timer fails only if 29 or more of the 100 pairs are over the tolerance: with 10%
# of pairs over it that is about 1e-7. The tail is not tested (the OS's rescheduling time); the
# engine reports it with --log-timer-jitter. Each test takes about 8 s, nearly all of it waiting.
CONFIDENCE = 0.99999
INDEPENDENT_SAMPLES = 100
SAMPLE_SPACING_SECONDS = 0.075
# Scheduling jitter allowed between the two sleeps of a pair
PAIRED_TOLERANCE_NS = 1_000_000


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


def _timer_overshoot_ns(*, timer: FastTimer, sleep_ns: int) -> int:
    """Sleep once with the timer.

    Returns:
        How far past its deadline the timer woke, in nanoseconds.

    """
    deadline = timer.ns_now() + sleep_ns
    woke = timer.sleep_until_next(deadline)
    assert woke >= deadline
    return woke - deadline


def _os_sleep_overshoot_ns(*, timer: FastTimer, sleep_ns: int) -> int:
    """Sleep once with the OS's plain time.sleep, timed on the timer's clock.

    Returns:
        How far past the requested length the sleep lasted, in nanoseconds.

    """
    started = timer.ns_now()
    time.sleep(sleep_ns / 1e9)
    return timer.ns_now() - started - sleep_ns


def _paired_difference_upper_bound_ns(*, timer: FastTimer, sleep_ns: int) -> int:
    """Measure INDEPENDENT_SAMPLES spaced pairs; return a CONFIDENCE upper bound on the median.

    Each pair's difference is the timer's overshoot minus the OS sleep's; the two sleeps
    alternate which goes first, so neither always wakes into the other's aftermath.

    Returns:
        The MEDIAN_UPPER_BOUND_RANK-th smallest difference, in nanoseconds.

    """
    differences = []
    for pair_index in range(INDEPENDENT_SAMPLES):
        # Unmeasured gap: a burst of load that delayed the last pair is over by now
        time.sleep(SAMPLE_SPACING_SECONDS)
        if pair_index % 2 == 0:
            timer_overshoot = _timer_overshoot_ns(timer=timer, sleep_ns=sleep_ns)
            os_overshoot = _os_sleep_overshoot_ns(timer=timer, sleep_ns=sleep_ns)
        else:
            os_overshoot = _os_sleep_overshoot_ns(timer=timer, sleep_ns=sleep_ns)
            timer_overshoot = _timer_overshoot_ns(timer=timer, sleep_ns=sleep_ns)
        differences.append(timer_overshoot - os_overshoot)
    return sorted(differences)[MEDIAN_UPPER_BOUND_RANK - 1]


def test_median_upper_bound_rank_is_the_sign_test_rank():
    """100 samples at 99.999%: the 72nd smallest (P(Binomial(100, 1/2) >= 72) is about 6.3e-6)."""
    assert MEDIAN_UPPER_BOUND_RANK == 72
    tail_at_rank = sum(comb(100, count) for count in range(72, 101)) / 2**100
    tail_one_lower = sum(comb(100, count) for count in range(71, 101)) / 2**100
    assert tail_at_rank <= 1 - CONFIDENCE < tail_one_lower


def test_factory_fast_backend_instantiates():
    """Test that create_timer with 'fast' returns a FastTimer instance."""
    t = create_timer('fast', {'sleep_granularity_ns': 1_000_000, 'windows_timer_1ms': False})
    assert isinstance(t, FastTimer)


def _calibrated_auto_timer(*, windows_timer_1ms: bool) -> FastTimer:
    """Return the timer the engine paces with by default: auto, calibrated to this machine.

    Returns:
        The calibrated FastTimer.

    """
    timer = create_timer(
        'auto', {'sleep_granularity_ns': None, 'windows_timer_1ms': windows_timer_1ms}
    )
    assert isinstance(timer, FastTimer)
    timer.calibrate()
    return timer


def test_fast_timer_basic_sleep_accuracy():
    """The engine's default timer (auto) wakes no later than the OS's own sleep (3 ms)."""
    t = _calibrated_auto_timer(windows_timer_1ms=False)
    difference = _paired_difference_upper_bound_ns(timer=t, sleep_ns=3_000_000)
    assert difference < PAIRED_TOLERANCE_NS


def test_fast_timer_spin_tighten_accuracy():
    """Spin-only mode wakes no later than the OS's own sleep of the same length (1 ms)."""
    t = FastTimer(sleep_granularity_ns=0, windows_timer_1ms=False)
    difference = _paired_difference_upper_bound_ns(timer=t, sleep_ns=1_000_000)
    assert difference < PAIRED_TOLERANCE_NS


@pytest.mark.skipif(
    not sys.platform.startswith('win'),
    reason='Windows-only timing resolution test',
)
def test_fast_timer_windows_1ms_option_tighter():
    """With the Windows 1 ms timer resolution, auto wakes no later than the OS sleep (3 ms)."""
    t = _calibrated_auto_timer(windows_timer_1ms=True)
    difference = _paired_difference_upper_bound_ns(timer=t, sleep_ns=3_000_000)
    assert difference < PAIRED_TOLERANCE_NS
