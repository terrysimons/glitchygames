"""Tests for tests/memory_by_file.py: what each test file keeps in the test process."""

from __future__ import annotations

import json
import sys

import pytest

from tests import memory_by_file


class ScriptedResident:
    """Resident-memory readings served in order, as the recorder reads them."""

    def __init__(self, *readings: float) -> None:
        """Serve ``readings``, one per call."""
        self.readings = list(readings)

    def __call__(self) -> float:
        return self.readings.pop(0)


def test_a_file_s_row_is_what_it_kept_and_the_most_it_rose(tmp_path):
    """Kept is start to end; peak rise is the highest reading after a test, from the start."""
    output = tmp_path / 'rows.json'
    # start, after test 1, after test 2, at the file's end
    recorder = memory_by_file.FileMemoryRecorder(
        output=output, read_resident=ScriptedResident(100.0, 180.0, 150.0, 130.0)
    )

    recorder.pytest_runtest_logstart(nodeid='tests/test_a.py::test_one')
    recorder.pytest_runtest_logfinish()
    recorder.pytest_runtest_logstart(nodeid='tests/test_a.py::test_two')
    recorder.pytest_runtest_logfinish()
    recorder.pytest_sessionfinish()

    assert json.loads(output.read_text(encoding='utf-8')) == [
        {'file': 'tests/test_a.py', 'kept': 30.0, 'peak_rise': 80.0, 'after': 130.0}
    ]


def test_the_rows_are_written_as_each_file_ends_so_a_stopped_run_keeps_them(tmp_path):
    """The memory guard stops a run with os._exit: the files finished before it are on disk."""
    output = tmp_path / 'rows.json'
    recorder = memory_by_file.FileMemoryRecorder(
        output=output, read_resident=ScriptedResident(100.0, 110.0, 120.0, 120.0)
    )

    recorder.pytest_runtest_logstart(nodeid='tests/test_a.py::test_one')
    recorder.pytest_runtest_logfinish()
    recorder.pytest_runtest_logstart(nodeid='tests/test_b.py::test_one')

    rows = json.loads(output.read_text(encoding='utf-8'))
    assert [row['file'] for row in rows] == ['tests/test_a.py']


def test_a_parametrized_test_s_cases_count_as_one_file(tmp_path):
    """Node ids differ only after the file's path: one row."""
    output = tmp_path / 'rows.json'
    recorder = memory_by_file.FileMemoryRecorder(
        output=output, read_resident=ScriptedResident(100.0, 101.0, 102.0, 103.0)
    )

    for case in ('a', 'b'):
        recorder.pytest_runtest_logstart(nodeid=f'tests/test_a.py::test_one[{case}]')
        recorder.pytest_runtest_logfinish()
    recorder.pytest_sessionfinish()

    assert len(json.loads(output.read_text(encoding='utf-8'))) == 1


def test_the_plugin_is_off_unless_its_variable_names_an_output(mocker, monkeypatch):
    """No variable, or an empty one: nothing is registered."""
    config = mocker.Mock()
    monkeypatch.delenv(memory_by_file.OUTPUT_VARIABLE, raising=False)
    memory_by_file.pytest_configure(config)
    monkeypatch.setenv(memory_by_file.OUTPUT_VARIABLE, '  ')
    memory_by_file.pytest_configure(config)

    config.pluginmanager.register.assert_not_called()


def test_with_its_variable_set_a_recorder_is_registered(mocker, monkeypatch, tmp_path):
    """The recorder writes to the file the variable names."""
    config = mocker.Mock()
    monkeypatch.setenv(memory_by_file.OUTPUT_VARIABLE, str(tmp_path / 'rows.json'))

    memory_by_file.pytest_configure(config)

    recorder = config.pluginmanager.register.call_args.args[0]
    assert isinstance(recorder, memory_by_file.FileMemoryRecorder)
    assert recorder.output == tmp_path / 'rows.json'


def test_where_memory_cannot_be_read_the_plugin_says_so_and_stays_off(
    mocker, monkeypatch, tmp_path, capsys
):
    """A platform with no reader (Windows) gets one line on standard error, not a failed run."""
    config = mocker.Mock()
    monkeypatch.setenv(memory_by_file.OUTPUT_VARIABLE, str(tmp_path / 'rows.json'))
    mocker.patch.object(sys, 'platform', 'win32')

    memory_by_file.pytest_configure(config)

    config.pluginmanager.register.assert_not_called()
    assert 'no resident-memory reader on win32' in capsys.readouterr().err


@pytest.mark.parametrize(
    ('platform', 'expected'),
    [
        ('darwin', '_macos_resident_mebibytes'),
        ('win32', None),
    ],
)
def test_each_platform_gets_its_reader(mocker, platform, expected):
    """On macOS the reader is task_info's; a platform with no reader gets None."""
    mocker.patch.object(sys, 'platform', platform)

    reader = memory_by_file.resident_reader()

    assert (reader.__name__ if reader is not None else None) == expected


def test_linux_reads_proc_self_statm(mocker, tmp_path):
    """The resident set is statm's second field, in pages."""
    statm = tmp_path / 'statm'
    statm.write_text('1000 256 10 1 0 100 0\n', encoding='ascii')
    mocker.patch.object(sys, 'platform', 'linux')
    mocker.patch.object(memory_by_file, 'PROC_STATM', statm)
    mocker.patch.object(memory_by_file.os, 'sysconf', return_value=4096)

    reader = memory_by_file.resident_reader()

    assert reader is not None
    assert reader() == 1.0  # 256 pages of 4 KiB


@pytest.mark.skipif(sys.platform not in {'darwin', 'linux'}, reason='no reader on this platform')
def test_this_platform_s_reader_reads_this_process():
    """A real reading: more than nothing, less than a terabyte."""
    reader = memory_by_file.resident_reader()

    assert reader is not None
    assert 1.0 < reader() < 1024 * 1024
