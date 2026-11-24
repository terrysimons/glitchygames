"""Tests for tests/import_failure_threads.py: import-machinery failures report the live threads."""

from __future__ import annotations

import importlib
import sys
import threading
from pathlib import Path

import pytest

from tests.import_failure_threads import (
    OUTSIDE_ANY_TEST,
    SECTION_TITLE,
    live_thread_report,
    raised_by_import_machinery,
    started_during,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# A module that removes its own sys.modules entry while it runs: importlib then fails exactly as
# CircleCI's Windows job did (KeyError from _load_unlocked's sys.modules.pop)
SELF_REMOVING_MODULE = 'import sys\ndel sys.modules[__name__]\n'


def test_a_module_leaving_sys_modules_mid_import_is_an_import_machinery_failure(
    tmp_path, monkeypatch
):
    """The planted failure: KeyError naming the module, raised from importlib._bootstrap."""
    (tmp_path / 'leaves_mid_import.py').write_text(SELF_REMOVING_MODULE)
    monkeypatch.syspath_prepend(tmp_path)

    with pytest.raises(KeyError, match='leaves_mid_import') as excinfo:
        importlib.import_module('leaves_mid_import')

    assert raised_by_import_machinery(excinfo.tb)


def test_an_ordinary_failure_is_not_the_import_machinerys():
    """A KeyError raised by the test's own code passes through no importlib frame."""
    with pytest.raises(KeyError) as excinfo:
        {}['missing']

    assert not raised_by_import_machinery(excinfo.tb)


def test_a_thread_started_during_a_test_is_marked_with_that_test(request):
    """This test's own thread carries this test's node id."""
    release = threading.Event()
    thread = threading.Thread(target=release.wait, name='marked-probe')
    thread.start()
    try:
        assert started_during(thread) == request.node.nodeid
    finally:
        release.set()
        thread.join()


def test_a_thread_never_started_is_outside_any_test():
    """A thread object nobody started (so never marked) reads as started outside any test."""
    assert started_during(threading.Thread(target=lambda: None)) == OUTSIDE_ANY_TEST


def test_the_report_names_each_thread_its_test_and_its_stack(request):
    """Name, daemon or not, the starting test, and the stack down to the waiting call."""
    release = threading.Event()

    def wait_for_release() -> None:
        release.wait()

    thread = threading.Thread(target=wait_for_release, name='report-probe', daemon=True)
    thread.start()
    try:
        report = live_thread_report(threads=[thread], frames=sys._current_frames())  # type: ignore[reportPrivateUsage]
    finally:
        release.set()
        thread.join()

    assert report.startswith(f'report-probe (daemon), started during: {request.node.nodeid}\n')
    assert 'wait_for_release' in report


def test_a_thread_without_a_frame_reports_no_stack():
    """A thread that is not running (no current frame) is still named, with no stack."""
    report = live_thread_report(threads=[threading.Thread(name='idle-probe')], frames={})

    assert (
        report == f'idle-probe (not a daemon), started during: {OUTSIDE_ANY_TEST}\n  (no stack)\n'
    )


def run_child_pytest(pytester, monkeypatch, test_source: str) -> pytest.RunResult:
    """Run one test module in a child pytest with only this plugin loaded.

    Returns:
        The child run's result.

    """
    monkeypatch.setenv('PYTHONPATH', str(PROJECT_ROOT))
    pytester.makepyfile(test_probe=test_source)
    return pytester.runpytest_subprocess(
        '-p',
        'tests.import_failure_threads',
        '-p',
        'no:cacheprovider',
        '-n',
        '0',
        '--no-cov',
        '-o',
        'addopts=',
    )


def test_an_import_failure_reports_a_thread_an_earlier_test_left_running(pytester, monkeypatch):
    """Through pytest: the earlier test's leftover thread is named with that earlier test.

    A later test releases the thread, so it is still alive when the failing test's report is made.
    """
    result = run_child_pytest(
        pytester,
        monkeypatch,
        'import importlib, sys, threading\n'
        'RELEASE = threading.Event()\n'
        'def test_leaves_a_thread():\n'
        "    threading.Thread(target=RELEASE.wait, name='leftover', daemon=True).start()\n"
        'def test_import_fails(tmp_path, monkeypatch):\n'
        f"    (tmp_path / 'leaves_mid_import.py').write_text({SELF_REMOVING_MODULE!r})\n"
        '    monkeypatch.syspath_prepend(tmp_path)\n'
        "    importlib.import_module('leaves_mid_import')\n"
        'def test_releases_the_thread():\n'
        '    RELEASE.set()\n',
    )

    result.assert_outcomes(passed=2, failed=1)
    result.stdout.fnmatch_lines([
        f'*{SECTION_TITLE}*',
        'leftover (daemon), started during: test_probe.py::test_leaves_a_thread',
    ])


def test_an_ordinary_failure_and_a_pass_report_no_threads(pytester, monkeypatch):
    """Through pytest: neither a pass nor a failure outside importlib adds the section."""
    result = run_child_pytest(
        pytester,
        monkeypatch,
        'def test_passes():\n    pass\ndef test_fails():\n    assert {}.get("x") == 1\n',
    )

    result.assert_outcomes(passed=1, failed=1)
    assert SECTION_TITLE not in result.stdout.str()
