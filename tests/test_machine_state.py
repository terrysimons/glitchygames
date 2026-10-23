"""Tests for the machine's state as a run starts (glitchygames/machine_state.py).

The real machine is read for real; Linux readings come from stand-in ``/proc`` and ``/sys``
trees built in ``tmp_path`` (real files), and macOS's tools' reports are parsed from their
real formats, so every platform's code runs on any machine (CI is Linux, local runs macOS).
"""

from __future__ import annotations

import os
import platform
from typing import TYPE_CHECKING

import pytest

from glitchygames import machine_state as machine_state_module
from glitchygames.machine_state import (
    MachineState,
    PowerSource,
    cpu_model_from_cpuinfo,
    current_machine_state,
    in_continuous_integration,
    machine_state,
    memory_bytes_from_meminfo,
    power_source_from_pmset,
    power_source_from_power_supplies,
    thermal_report_from_pmset,
)
from glitchygames.process import TimeoutExpired
from glitchygames.recording_history import MeasurementRun, latest_measurement_run

if TYPE_CHECKING:
    from pathlib import Path

PMSET_BATTERY_ON_MAINS = (
    "Now drawing from 'AC Power'\n"
    ' -InternalBattery-0 (id=23265379)\t100%; charged; 0:00 remaining present: true\n'
)
PMSET_BATTERY_ON_BATTERY = (
    "Now drawing from 'Battery Power'\n"
    ' -InternalBattery-0 (id=23265379)\t87%; discharging; 6:12 remaining present: true\n'
)
PMSET_THERMAL_APPLE_SILICON = (
    'Note: No thermal warning level has been recorded\n'
    'Note: No performance warning level has been recorded\n'
    'Note: No CPU power status has been recorded\n'
)
PMSET_THERMAL_INTEL = (
    'CPU_Scheduler_Limit \t= 100\nCPU_Available_CPUs \t= 8\nCPU_Speed_Limit \t= 63\n'
)
CPUINFO_X86 = (
    'processor\t: 0\nvendor_id\t: GenuineIntel\nmodel name\t: Intel(R) Core(TM) i7-8700\n\n'
    'processor\t: 1\nmodel name\t: Intel(R) Core(TM) i7-8700\n'
)
CPUINFO_RASPBERRY_PI = 'processor\t: 0\nBogoMIPS\t: 108.00\n\nModel\t\t: Raspberry Pi 4 Model B\n'
MEMINFO = 'MemTotal:       16316412 kB\nMemFree:         1234567 kB\n'
NOT_IN_CI: dict[str, str] = {}


def _power_supply(root: Path, *, name: str, supply_type: str, online: str | None = None) -> None:
    supply = root / 'sys' / 'class' / 'power_supply' / name
    supply.mkdir(parents=True)
    (supply / 'type').write_text(f'{supply_type}\n', encoding='utf-8')
    if online is not None:
        (supply / 'online').write_text(f'{online}\n', encoding='utf-8')


def _linux_tree(root: Path, *, cpuinfo: str = CPUINFO_X86, meminfo: str = MEMINFO) -> Path:
    (root / 'proc').mkdir(parents=True)
    (root / 'proc' / 'cpuinfo').write_text(cpuinfo, encoding='utf-8')
    (root / 'proc' / 'meminfo').write_text(meminfo, encoding='utf-8')
    return root


class TestThisMachine:
    """The machine running the tests, read for real."""

    def test_it_reads_this_machine(self):
        state = machine_state(environment=NOT_IN_CI)

        assert state.logical_cpu_count == os.cpu_count()
        assert state.continuous_integration is False
        if platform.system() == 'Darwin':
            assert state.cpu_model
            assert state.memory_bytes is not None
            assert state.memory_bytes > 0
            assert state.power_source in {PowerSource.MAINS, PowerSource.BATTERY}
            assert state.thermal_report

    def test_macos_tools_missing_leave_everything_unknown(self, mocker):
        """What a Linux machine reads if asked as macOS: no sysctl, no pmset."""
        mocker.patch.object(machine_state_module.shutil, 'which', return_value=None)

        state = machine_state(system='Darwin', environment=NOT_IN_CI)

        assert (state.cpu_model, state.memory_bytes, state.power_source) == (None, None, None)
        assert state.thermal_report is None

    @pytest.mark.parametrize(
        'failure', [TimeoutExpired(cmd='pmset', timeout=5.0), OSError('cannot start')]
    )
    def test_a_tool_that_hangs_or_cannot_start_is_unknown(self, mocker, failure):
        mocker.patch.object(machine_state_module.shutil, 'which', return_value='/usr/bin/tool')
        mocker.patch.object(machine_state_module, 'run_command', side_effect=failure)

        state = machine_state(system='Darwin', environment=NOT_IN_CI)

        assert state.cpu_model is None
        assert state.power_source is None

    def test_a_tool_that_fails_is_unknown(self, mocker):
        mocker.patch.object(machine_state_module.shutil, 'which', return_value='/usr/bin/false')
        failed = mocker.Mock(returncode=1, stdout='')
        mocker.patch.object(machine_state_module, 'run_command', return_value=failed)

        state = machine_state(system='Darwin', environment=NOT_IN_CI)

        assert state.memory_bytes is None
        assert state.thermal_report is None

    def test_other_systems_name_only_the_processor(self, mocker):
        mocker.patch.object(machine_state_module.platform, 'processor', return_value='Intel64')

        state = machine_state(system='Windows', environment=NOT_IN_CI)

        assert state == MachineState(
            cpu_model='Intel64',
            logical_cpu_count=os.cpu_count(),
            memory_bytes=None,
            power_source=None,
            thermal_report=None,
            continuous_integration=False,
        )


class TestMacosReports:
    """pmset's reports, as macOS prints them."""

    @pytest.mark.parametrize(
        ('report', 'expected'),
        [
            (PMSET_BATTERY_ON_MAINS, PowerSource.MAINS),
            (PMSET_BATTERY_ON_BATTERY, PowerSource.BATTERY),
            ("Now drawing from 'UPS Power'\n", None),
            ("Battery status\nNow drawing from 'Battery Power'\n", PowerSource.BATTERY),
            ('', None),
        ],
    )
    def test_the_power_source(self, report, expected):
        assert power_source_from_pmset(report=report) == expected

    def test_apple_silicon_thermal_notes_are_kept_as_reported(self):
        assert thermal_report_from_pmset(report=PMSET_THERMAL_APPLE_SILICON) == (
            'Note: No thermal warning level has been recorded; '
            'Note: No performance warning level has been recorded; '
            'Note: No CPU power status has been recorded'
        )

    def test_an_intel_speed_limit_is_kept(self):
        report = thermal_report_from_pmset(report=PMSET_THERMAL_INTEL)

        assert report is not None
        assert 'CPU_Speed_Limit \t= 63' in report

    def test_an_empty_thermal_report_is_none(self):
        assert thermal_report_from_pmset(report='\n  \n') is None


class TestLinuxReadings:
    """/proc and /sys, from stand-in trees."""

    def test_a_laptop_on_mains(self, tmp_path):
        root = _linux_tree(tmp_path)
        _power_supply(root, name='AC', supply_type='Mains', online='1')
        _power_supply(root, name='BAT0', supply_type='Battery')

        state = machine_state(system='Linux', root=root, environment=NOT_IN_CI)

        assert state.cpu_model == 'Intel(R) Core(TM) i7-8700'
        assert state.memory_bytes == 16316412 * 1024
        assert state.power_source is PowerSource.MAINS
        assert state.thermal_report is None

    def test_a_laptop_on_battery(self, tmp_path):
        root = _linux_tree(tmp_path)
        _power_supply(root, name='AC', supply_type='Mains', online='0')
        _power_supply(root, name='BAT0', supply_type='Battery')

        assert (
            power_source_from_power_supplies(directory=root / 'sys' / 'class' / 'power_supply')
            is PowerSource.BATTERY
        )

    def test_supplies_that_are_neither_say_nothing(self, tmp_path):
        _power_supply(tmp_path, name='hidpp_battery_0', supply_type='USB')

        assert (
            power_source_from_power_supplies(directory=tmp_path / 'sys' / 'class' / 'power_supply')
            is None
        )

    def test_a_machine_without_proc_or_sys_is_unknown(self, tmp_path):
        state = machine_state(system='Linux', root=tmp_path, environment=NOT_IN_CI)

        assert (state.cpu_model, state.memory_bytes, state.power_source) == (None, None, None)

    def test_an_arm_board_names_its_model(self):
        assert cpu_model_from_cpuinfo(cpuinfo=CPUINFO_RASPBERRY_PI) == 'Raspberry Pi 4 Model B'

    def test_cpuinfo_without_a_name_is_none(self):
        assert cpu_model_from_cpuinfo(cpuinfo='processor\t: 0\nflags\t\t:\n') is None

    @pytest.mark.parametrize('meminfo', ['MemFree: 5 kB\n', 'MemTotal: lots\n', 'MemTotal:\n'])
    def test_meminfo_without_a_readable_total_is_none(self, meminfo):
        assert memory_bytes_from_meminfo(meminfo=meminfo) is None

    def test_an_unreadable_cpuinfo_is_none(self, tmp_path):
        root = _linux_tree(tmp_path)
        (root / 'proc' / 'cpuinfo').write_bytes(b'\xff\xfe')

        assert machine_state(system='Linux', root=root, environment=NOT_IN_CI).cpu_model is None


class TestContinuousIntegration:
    """CI, CIRCLECI or GITHUB_ACTIONS set to anything not false."""

    @pytest.mark.parametrize(
        ('environment', 'expected'),
        [
            ({}, False),
            ({'CI': 'true'}, True),
            ({'CI': 'false'}, False),
            ({'CI': '0'}, False),
            ({'CIRCLECI': 'true'}, True),
            ({'GITHUB_ACTIONS': 'true'}, True),
            ({'CI': ''}, False),
        ],
    )
    def test_the_environment_decides(self, environment, expected):
        assert in_continuous_integration(environment=environment) is expected

    def test_the_process_environment_is_read_by_default(self, mocker):
        mocker.patch.dict(os.environ, {'CI': 'true'})

        assert machine_state(system='Windows').continuous_integration is True


class TestRecordedRuns:
    """Every run records the machine's state; older runs read without it."""

    def test_it_is_read_once_per_process(self, mocker):
        current_machine_state.cache_clear()
        state = machine_state(system='Windows', environment=NOT_IN_CI)
        read = mocker.patch.object(machine_state_module, 'machine_state', return_value=state)
        try:
            assert current_machine_state() is state
            assert current_machine_state() is state
            assert read.call_count == 1
        finally:
            current_machine_state.cache_clear()

    def test_a_run_from_before_the_field_reads_as_none_and_a_new_run_round_trips(self):
        old_run = {
            'machine': 'macOS',
            'processing_paced': False,
            'engine_version': None,
            'pygame_version': '2.5.8',
            'python_version': '3.14.0',
            'measured_at': '2026-10-23T12:00:00+00:00',
            'rebaselined_from': None,
            'hash_scheme': 1,
        }
        old = latest_measurement_run(header={'measurement_runs': [old_run]})
        assert old is not None
        assert old.machine_state is None

        state = machine_state(system='Windows', environment=NOT_IN_CI)
        new_run = MeasurementRun.model_validate({**old_run, 'machine_state': state})
        assert latest_measurement_run(header={'measurement_runs': [new_run.to_json()]}) == new_run
