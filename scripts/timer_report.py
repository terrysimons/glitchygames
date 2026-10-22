"""Report how accurately this machine wakes sleeping code, for diagnosing timing tests in CI.

Prints three things, to tell apart why sleeps wake late:

  machine       Whether the OS runs under a hypervisor (macOS ``kern.hv_vmm_present``; Linux's
                ``hypervisor`` CPU flag) and the CPUs it offers.
  cpu share     The share of one CPU a busy loop gets over a second (process time / wall time).
                Well under 1.0 means the process is time-shared away (heavy contention).
  wakes         Overshoot distributions for spaced sleeps: FastTimer (sleep+spin), the OS's plain
                time.sleep, and spin-only. A delay that hits sleeps but not spin-only is the OS or
                VM waking sleepers late (coarse timers, coalescing); one that hits spin-only too
                is contention.

Always exits ``ExitCode.SUCCESS``: it reports, it does not judge (the timing tests judge).

Usage:
    uv run python scripts/timer_report.py
"""

from __future__ import annotations

import os
import platform
import subprocess  # ruff: ignore[suspicious-subprocess-import] — SubprocessError, from run_command
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from glitchygames.exit_codes import ExitCode
from glitchygames.process import run_command
from glitchygames.timing import FastTimer

if TYPE_CHECKING:
    from collections.abc import Callable

SAMPLES = 60
# Spacing between samples, past the ~60 ms over which load makes consecutive sleeps late together
SAMPLE_SPACING_SECONDS = 0.075
SLEEP_NS = 3_000_000
SPIN_SLEEP_NS = 1_000_000
CPU_SHARE_SECONDS = 1.0
NANOSECONDS_PER_MILLISECOND = 1_000_000
# macOS's sysctl, by absolute path (no PATH lookup)
SYSCTL_PATH = '/usr/sbin/sysctl'


def emit(message: str) -> None:
    """Write a line of the report to stdout."""
    sys.stdout.write(message + '\n')


def hypervisor_description() -> str:
    """Say whether the OS reports running under a hypervisor.

    Returns:
        'yes', 'no' or 'unknown', with where the answer came from.

    """
    if sys.platform == 'darwin':
        try:
            finished = run_command(
                command=[SYSCTL_PATH, '-n', 'kern.hv_vmm_present'],
                environment=os.environ,
                timeout_seconds=10,
                capture_output=True,
            )
        except (OSError, subprocess.SubprocessError) as error:
            return f'unknown (sysctl kern.hv_vmm_present: {error})'
        answer = (finished.stdout or '').strip()
        if finished.returncode != 0:
            return f'unknown (sysctl kern.hv_vmm_present exited {finished.returncode})'
        return f'{"yes" if answer == "1" else "no"} (sysctl kern.hv_vmm_present = {answer})'
    if sys.platform.startswith('linux'):
        try:
            flags = Path('/proc/cpuinfo').read_text(encoding='utf-8')
        except OSError as error:
            return f'unknown (/proc/cpuinfo: {error})'
        return f'{"yes" if " hypervisor" in flags else "no"} (/proc/cpuinfo hypervisor flag)'
    return 'unknown (no check on this OS)'


def cpu_share() -> float:
    """Measure the share of one CPU a busy loop gets.

    Returns:
        Process time over wall time for CPU_SHARE_SECONDS of spinning (1.0 = a whole CPU).

    """
    wall_started = time.perf_counter()
    cpu_started = time.process_time()
    while time.perf_counter() - wall_started < CPU_SHARE_SECONDS:
        pass
    return (time.process_time() - cpu_started) / (time.perf_counter() - wall_started)


def describe(*, label: str, overshoots_ns: list[int]) -> str:
    """Summarize overshoots as median, p90 and max in milliseconds.

    Returns:
        One report line.

    """
    ordered = sorted(overshoots_ns)

    def at(fraction: float) -> float:
        return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))] / (
            NANOSECONDS_PER_MILLISECOND
        )

    return (
        f'{label:34} median {at(0.5):6.2f}  p90 {at(0.9):6.2f}  '
        f'max {ordered[-1] / NANOSECONDS_PER_MILLISECOND:6.2f} ms ({len(ordered)} sleeps)'
    )


def spaced_overshoots(*, sleep_once: Callable[[], int]) -> list[int]:
    """Take SAMPLES spaced measurements.

    Args:
        sleep_once: Sleeps once and returns its overshoot in nanoseconds.

    Returns:
        The overshoots.

    """
    overshoots: list[int] = []
    for _ in range(SAMPLES):
        time.sleep(SAMPLE_SPACING_SECONDS)
        overshoots.append(sleep_once())
    return overshoots


def main() -> int:
    """Print the report.

    Returns:
        ``ExitCode.SUCCESS``.

    """
    fast_timer = FastTimer(sleep_granularity_ns=1_000_000, windows_timer_1ms=False)
    spin_timer = FastTimer(sleep_granularity_ns=0, windows_timer_1ms=False)

    def timer_overshoot(timer: FastTimer, sleep_ns: int) -> int:
        deadline = timer.ns_now() + sleep_ns
        return timer.sleep_until_next(deadline) - deadline

    def os_sleep_overshoot() -> int:
        started = time.perf_counter_ns()
        time.sleep(SLEEP_NS / 1e9)
        return time.perf_counter_ns() - started - SLEEP_NS

    emit('== timer report ==')
    emit(
        f'machine: {platform.platform()}, {platform.machine()}, Python {platform.python_version()}'
    )
    emit(f'hypervisor: {hypervisor_description()}')
    emit(f'CPUs: {os.cpu_count()} reported, {os.process_cpu_count()} usable by this process')
    emit(f'cpu share of a busy loop: {cpu_share():.2f} (1.00 = a whole CPU; low = time-shared)')
    emit(
        describe(
            label='FastTimer 3 ms (sleep+spin)',
            overshoots_ns=spaced_overshoots(
                sleep_once=lambda: timer_overshoot(fast_timer, SLEEP_NS)
            ),
        )
    )
    emit(
        describe(
            label='time.sleep 3 ms (OS)',
            overshoots_ns=spaced_overshoots(sleep_once=os_sleep_overshoot),
        )
    )
    emit(
        describe(
            label='FastTimer 1 ms (spin only)',
            overshoots_ns=spaced_overshoots(
                sleep_once=lambda: timer_overshoot(spin_timer, SPIN_SLEEP_NS)
            ),
        )
    )
    emit('meaning: sleeps late but spin-only accurate = the OS/VM wakes sleepers late;')
    emit('         spin-only late too (and a low cpu share) = contention for the CPU.')
    return ExitCode.SUCCESS


if __name__ == '__main__':
    sys.exit(main())
