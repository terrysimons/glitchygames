"""The machine's state while a run measures: what makes its numbers comparable, or not.

A recording names it in every run (``MeasurementRun.machine_state``,
glitchygames/recording_history.py) beside the platform string (``machine``): the CPU, its
logical CPU count and memory, whether the machine ran on mains power or battery, what the
operating system reported about thermal throttling, and whether the run was in continuous
integration. "Slower" is often a laptop on battery or a hot one, so these travel with the times.

Read once per process, as its first run starts (``current_machine_state``: a game process makes
one run; reading on every run cost the test suite, which starts thousands, about 30 seconds),
with the standard library and the operating system's own tools:

- **macOS:** ``sysctl`` (``machdep.cpu.brand_string``, ``hw.memsize``), ``pmset -g batt`` (the
  power source line) and ``pmset -g therm`` (its lines, kept as reported: Apple silicon reports
  only notes such as "No thermal warning level has been recorded", Intel adds the CPU speed
  limit).
- **Linux:** ``/proc/cpuinfo`` (``model name``, or ``Model``/``Hardware`` on ARM),
  ``/proc/meminfo`` (``MemTotal``) and ``/sys/class/power_supply`` (a ``Mains`` supply online:
  mains; otherwise a ``Battery``: battery; no supplies: unknown). No thermal report.
- **Anything else** (Windows): ``platform.processor()`` for the CPU; the rest unknown.

Any reading that fails is None (unknown), never a guess and never an error. Tools run through
``glitchygames.process.run_command`` (the one launcher) with a short timeout.
"""

from __future__ import annotations

import functools
import os
import platform
import shutil
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from glitchygames.process import TimeoutExpired, run_command

TOOL_TIMEOUT_SECONDS = 5.0
MACOS_SYSTEM = 'Darwin'
LINUX_SYSTEM = 'Linux'
# What pmset -g batt says the machine draws from
PMSET_POWER_SOURCE_PREFIX = 'Now drawing from'
PMSET_MAINS_SOURCE = "'AC Power'"
PMSET_BATTERY_SOURCE = "'Battery Power'"
# /proc/cpuinfo's CPU name, x86 first, then what ARM boards report
LINUX_CPU_NAME_KEYS = ('model name', 'Model', 'Hardware')
LINUX_POWER_SUPPLY_DIRECTORY = Path('sys/class/power_supply')
BYTES_PER_KIBIBYTE = 1024
# Environment variables that say the run is in continuous integration
CONTINUOUS_INTEGRATION_VARIABLES = ('CI', 'CIRCLECI', 'GITHUB_ACTIONS')
FALSE_VALUES = frozenset({'', '0', 'false', 'no'})


class PowerSource(StrEnum):
    """What the machine ran on."""

    MAINS = 'mains'
    BATTERY = 'battery'


class MachineState(BaseModel):
    """The machine's state as a run started.

    Attributes:
        cpu_model: The CPU's name (``Apple M4 Max``), or None when unknown.
        logical_cpu_count: How many logical CPUs the operating system reports, or None.
        memory_bytes: Physical memory, or None when unknown.
        power_source: Mains or battery, or None when unknown (a desktop without a power
            supply report, Windows).
        thermal_report: What the operating system reported about thermal throttling (macOS
            ``pmset -g therm``, its lines joined with ``; ``), or None when there is no report.
        continuous_integration: Whether the run was in continuous integration (``CI``,
            ``CIRCLECI`` or ``GITHUB_ACTIONS`` set to something other than false).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    cpu_model: str | None
    logical_cpu_count: int | None
    memory_bytes: int | None
    power_source: PowerSource | None
    thermal_report: str | None
    continuous_integration: bool


def _tool_output(*, command: list[str]) -> str | None:
    """Run an operating system tool and return its standard output, stripped.

    Args:
        command: The tool and its arguments (the tool looked up on PATH).

    Returns:
        The output, or None when the tool is missing, fails or times out.

    """
    program = shutil.which(command[0])
    if program is None:
        return None
    try:
        completed = run_command(
            command=[program, *command[1:]],
            environment=os.environ,
            timeout_seconds=TOOL_TIMEOUT_SECONDS,
            capture_output=True,
        )
    except OSError, TimeoutExpired:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _read_text(path: Path) -> str | None:
    """Return a file's text, or None when it cannot be read.

    Returns:
        The text, or None.

    """
    try:
        return path.read_text(encoding='utf-8')
    except OSError, UnicodeDecodeError:
        return None


def power_source_from_pmset(*, report: str) -> PowerSource | None:
    """Read the power source from ``pmset -g batt``.

    Args:
        report: Its output.

    Returns:
        Mains or battery, or None when the report names neither.

    """
    for line in report.splitlines():
        if line.startswith(PMSET_POWER_SOURCE_PREFIX):
            if PMSET_MAINS_SOURCE in line:
                return PowerSource.MAINS
            if PMSET_BATTERY_SOURCE in line:
                return PowerSource.BATTERY
    return None


def thermal_report_from_pmset(*, report: str) -> str | None:
    """Keep ``pmset -g therm``'s lines as reported, joined with ``; ``.

    Args:
        report: Its output.

    Returns:
        The lines, or None when there are none.

    """
    lines = [line.strip() for line in report.splitlines() if line.strip()]
    return '; '.join(lines) or None


def cpu_model_from_cpuinfo(*, cpuinfo: str) -> str | None:
    """Read the CPU's name from ``/proc/cpuinfo``.

    Args:
        cpuinfo: Its text.

    Returns:
        The first ``model name`` (else ``Model``, else ``Hardware``), or None.

    """
    values: dict[str, str] = {}
    for line in cpuinfo.splitlines():
        key, separator, value = line.partition(':')
        if separator and value.strip():
            values.setdefault(key.strip(), value.strip())
    for key in LINUX_CPU_NAME_KEYS:
        if key in values:
            return values[key]
    return None


def memory_bytes_from_meminfo(*, meminfo: str) -> int | None:
    """Read physical memory from ``/proc/meminfo`` (``MemTotal: 16316412 kB``).

    Args:
        meminfo: Its text.

    Returns:
        The bytes, or None when the line is missing or malformed.

    """
    for line in meminfo.splitlines():
        key, _, value = line.partition(':')
        if key.strip() == 'MemTotal':
            amount = value.split()
            if amount and amount[0].isdigit():
                return int(amount[0]) * BYTES_PER_KIBIBYTE
    return None


def power_source_from_power_supplies(*, directory: Path) -> PowerSource | None:
    """Read the power source from Linux's power supply directory.

    Args:
        directory: ``/sys/class/power_supply`` (or a stand-in tree).

    Returns:
        Mains when a ``Mains`` supply is online, battery when there is a ``Battery`` and no
        mains is online, else None.

    """
    try:
        supplies = sorted(directory.iterdir())
    except OSError:
        return None
    has_battery = False
    for supply in supplies:
        supply_type = (_read_text(supply / 'type') or '').strip()
        if supply_type == 'Mains' and (_read_text(supply / 'online') or '').strip() == '1':
            return PowerSource.MAINS
        has_battery = has_battery or supply_type == 'Battery'
    return PowerSource.BATTERY if has_battery else None


def in_continuous_integration(*, environment: dict[str, str]) -> bool:
    """Return whether the environment says the run is in continuous integration.

    Args:
        environment: The environment variables.

    Returns:
        True when any of ``CONTINUOUS_INTEGRATION_VARIABLES`` is set to something not false.

    """
    return any(
        environment.get(name, '').strip().lower() not in FALSE_VALUES
        for name in CONTINUOUS_INTEGRATION_VARIABLES
    )


def _macos_state() -> tuple[str | None, int | None, PowerSource | None, str | None]:
    """Read the CPU, memory, power source and thermal report on macOS.

    Returns:
        The four readings (each None when unknown).

    """
    cpu_model = _tool_output(command=['sysctl', '-n', 'machdep.cpu.brand_string']) or None
    memory = _tool_output(command=['sysctl', '-n', 'hw.memsize'])
    battery_report = _tool_output(command=['pmset', '-g', 'batt'])
    thermal = _tool_output(command=['pmset', '-g', 'therm'])
    return (
        cpu_model,
        int(memory) if memory is not None and memory.isdigit() else None,
        None if battery_report is None else power_source_from_pmset(report=battery_report),
        None if thermal is None else thermal_report_from_pmset(report=thermal),
    )


def _linux_state(*, root: Path) -> tuple[str | None, int | None, PowerSource | None]:
    """Read the CPU, memory and power source on Linux.

    Args:
        root: The filesystem root (``/``, or a stand-in tree).

    Returns:
        The three readings (each None when unknown).

    """
    cpuinfo = _read_text(root / 'proc' / 'cpuinfo')
    meminfo = _read_text(root / 'proc' / 'meminfo')
    return (
        None if cpuinfo is None else cpu_model_from_cpuinfo(cpuinfo=cpuinfo),
        None if meminfo is None else memory_bytes_from_meminfo(meminfo=meminfo),
        power_source_from_power_supplies(directory=root / LINUX_POWER_SUPPLY_DIRECTORY),
    )


def machine_state(
    *,
    system: str | None = None,
    root: Path = Path('/'),
    environment: dict[str, str] | None = None,
) -> MachineState:
    """Read the machine's state now.

    Args:
        system: The operating system (``platform.system()`` when None).
        root: The filesystem root Linux readings come from (``/``; tests pass a stand-in tree).
        environment: The environment variables (``os.environ`` when None).

    Returns:
        The state.

    """
    system = platform.system() if system is None else system
    environment = dict(os.environ) if environment is None else environment
    thermal_report: str | None = None
    if system == MACOS_SYSTEM:
        cpu_model, memory_bytes, power_source, thermal_report = _macos_state()
    elif system == LINUX_SYSTEM:
        cpu_model, memory_bytes, power_source = _linux_state(root=root)
    else:
        cpu_model, memory_bytes, power_source = platform.processor() or None, None, None
    return MachineState(
        cpu_model=cpu_model,
        logical_cpu_count=os.cpu_count(),
        memory_bytes=memory_bytes,
        power_source=power_source,
        thermal_report=thermal_report,
        continuous_integration=in_continuous_integration(environment=environment),
    )


@functools.cache
def current_machine_state() -> MachineState:
    """Return this machine's state, read once per process (what recorded runs hold).

    Returns:
        The state.

    """
    return machine_state()
