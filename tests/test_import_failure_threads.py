"""Tests for tests/import_failure_threads.py: what a failure in the import machinery reports."""

from __future__ import annotations

import importlib
import sys
import threading
from pathlib import Path

import pytest

from tests.import_failure_threads import (
    OUTSIDE_ANY_TEST,
    REMOVALS_SECTION_TITLE,
    SECTION_TITLE,
    STATE_SECTION_TITLE,
    live_thread_report,
    raised_by_import_machinery,
    section_text,
    started_during,
)
from tests.module_removals import NOT_RECORDED

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


def run_child_pytest(
    pytester, monkeypatch, test_source: str, *, conftest_source: str = ''
) -> pytest.RunResult:
    """Run one test module in a child pytest with only this plugin loaded.

    Returns:
        The child run's result.

    """
    monkeypatch.setenv('PYTHONPATH', str(PROJECT_ROOT))
    pytester.makepyfile(test_probe=test_source)
    pytester.makeconftest(conftest_source)
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
    for title in (SECTION_TITLE, REMOVALS_SECTION_TITLE, STATE_SECTION_TITLE):
        assert title not in result.stdout.str()


# A module that stops while it executes until told to go on
PAUSING_MODULE = (
    'import test_probe\ntest_probe.ENTERED.set()\n'
    'if not test_probe.GO_ON.wait(timeout=30):\n'
    "    raise RuntimeError('never told to go on')\n"
)

# A child test: a thread is executing the pausing module while the main thread runs REMOVE; the
# thread's failure (importlib's KeyError) is then the test's. Its module is named test_probe, so
# the pausing module shares its events through sys.modules (put there before the removal begins).
PAUSED_IMPORT_TEST = """
import contextlib, importlib, sys, threading
import pytest
from _pytest.pytester import SysModulesSnapshot
ENTERED, GO_ON = threading.Event(), threading.Event()

def test_import_meets_a_removal(tmp_path, monkeypatch, mocker):
    monkeypatch.setitem(sys.modules, 'test_probe', sys.modules[__name__])
    (tmp_path / 'pauses_mid_import.py').write_text({source!r})
    monkeypatch.syspath_prepend(tmp_path)
    errors = []

    def import_it():
        try:
            importlib.import_module('pauses_mid_import')
        except KeyError as error:
            errors.append(error)

    thread = threading.Thread(target=import_it, name='importer')
    {prepare}
    thread.start()
    if not ENTERED.wait(timeout=30):
        pytest.fail('the import never began')
    try:
        {remove}
    finally:
        GO_ON.set()
        thread.join()
    raise errors[0]
"""


def section(output: str, title: str) -> str:
    """Return one report section's text (pytest heads each with a dashed line)."""
    assert output.count(f' {title} ') == 1
    return output.partition(f' {title} ')[2].partition('\n---')[0]


@pytest.mark.parametrize(
    ('prepare', 'remove', 'made_by'),
    [
        pytest.param(
            'mocker.patch.dict(sys.modules)',
            'mocker.stopall()',
            'patch.dict(sys.modules) ending',
            id='patch-dict',
        ),
        pytest.param(
            "mocker.patch.dict('sys.modules')",
            'mocker.stopall()',
            'patch.dict(sys.modules) ending',
            id='patch-dict-by-name',
        ),
        pytest.param(
            'snapshot = SysModulesSnapshot()',
            'snapshot.restore()',
            'pytester SysModulesSnapshot.restore',
            id='pytester-snapshot',
        ),
        pytest.param(
            'pass',
            "monkeypatch.delitem(sys.modules, 'pauses_mid_import')",
            'monkeypatch.delitem(sys.modules, ...)',
            id='monkeypatch-delitem',
        ),
    ],
)
def test_a_removal_during_another_threads_import_is_named_and_marked(
    pytester, monkeypatch, prepare, remove, made_by
):
    """The reproductions: the report names the call that removed the module, and the overlap."""
    result = run_child_pytest(
        pytester,
        monkeypatch,
        PAUSED_IMPORT_TEST.format(source=PAUSING_MODULE, prepare=prepare, remove=remove),
    )

    result.assert_outcomes(failed=1)
    output = result.stdout.str()
    assert "KeyError: 'pauses_mid_import'" in output
    removals = section(output, REMOVALS_SECTION_TITLE)
    newest = removals[removals.index('#') :]
    assert newest.split('\n')[0].partition(' ')[2].startswith(made_by)
    assert newest.split('\n')[0].endswith('*** MAY OVERLAP AN IMPORT ***')
    assert 'pauses_mid_import' in newest.split('\n')[1]
    assert (
        'thread: MainThread (the main thread), '
        'during: test_probe.py::test_import_meets_a_removal' in newest
    )
    assert 'may overlap: pauses_mid_import (another thread)' in newest
    assert 'test_probe.py:' in newest
    assert 'pauses_mid_import in sys.modules: NOT found by hash, NOT found by iteration' in section(
        output, STATE_SECTION_TITLE
    )


def test_a_direct_delete_during_an_import_is_said_not_to_be_recorded(pytester, monkeypatch):
    """A plain del removes the module unseen: nothing is marked, and the section says why."""
    result = run_child_pytest(
        pytester,
        monkeypatch,
        PAUSED_IMPORT_TEST.format(
            source=PAUSING_MODULE, prepare='pass', remove="del sys.modules['pauses_mid_import']"
        ),
    )

    result.assert_outcomes(failed=1)
    output = result.stdout.str()
    assert "KeyError: 'pauses_mid_import'" in output
    removals = section(output, REMOVALS_SECTION_TITLE)
    assert NOT_RECORDED in removals
    assert 'MAY OVERLAP' not in removals
    assert 'none recorded' in removals
    assert 'pauses_mid_import in sys.modules: NOT found by hash, NOT found by iteration' in section(
        output, STATE_SECTION_TITLE
    )


@pytest.mark.parametrize(
    ('fixture_body', 'outcome'),
    [
        pytest.param("    importlib.import_module('leaves_mid_import')\n    yield\n", 'setup'),
        pytest.param("    yield\n    importlib.import_module('leaves_mid_import')\n", 'teardown'),
    ],
)
def test_a_setup_or_teardown_failing_in_the_import_machinery_reports_too(
    pytester, monkeypatch, fixture_body, outcome
):
    """A fixture's import failing gives its own phase's report all three sections, once."""
    result = run_child_pytest(
        pytester,
        monkeypatch,
        'import importlib, pytest\n'
        '@pytest.fixture\n'
        'def importing(tmp_path, monkeypatch):\n'
        f"    (tmp_path / 'leaves_mid_import.py').write_text({SELF_REMOVING_MODULE!r})\n"
        '    monkeypatch.syspath_prepend(tmp_path)\n'
        f'{fixture_body}'
        'def test_uses_it(importing):\n'
        '    pass\n',
    )

    result.assert_outcomes(errors=1, passed=1 if outcome == 'teardown' else 0)
    result.stdout.fnmatch_lines([f'*ERROR at {outcome} of test_uses_it*'])
    for title in (SECTION_TITLE, REMOVALS_SECTION_TITLE, STATE_SECTION_TITLE):
        section(result.stdout.str(), title)


def test_a_skip_raised_while_importing_reports_nothing(pytester, monkeypatch):
    """A skip passes through importlib's frames, but nothing failed: no section is added."""
    result = run_child_pytest(
        pytester,
        monkeypatch,
        'import importlib\n'
        'def test_skips(tmp_path, monkeypatch):\n'
        "    (tmp_path / 'skips_mid_import.py').write_text("
        '"import pytest\\npytest.skip(\'mid-import\')\\n")\n'
        '    monkeypatch.syspath_prepend(tmp_path)\n'
        "    importlib.import_module('skips_mid_import')\n",
        conftest_source=(
            'def pytest_runtest_logreport(report):\n'
            "    print('SECTIONS', report.when, [title for title, _ in report.sections])\n"
        ),
    )

    result.assert_outcomes(skipped=1)
    result.stdout.fnmatch_lines(['*SECTIONS call []*'])


def test_a_fault_writing_a_section_becomes_its_text():
    """A report tool's own fault never becomes pytest's INTERNALERROR."""

    class UnprintableError(Exception):
        def __str__(self):
            raise self

    def fail():
        raise UnprintableError

    assert 'this section could not be written' in section_text(fail)
    assert 'UnprintableError' in section_text(fail)


def test_an_interrupt_writing_a_section_goes_on():
    """Ctrl-C still stops the run."""

    def interrupt():
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        section_text(interrupt)


def test_a_fault_in_each_section_leaves_the_tests_own_report(pytester, monkeypatch):
    """Through pytest: every writer broken, the failure is still reported, with three faults."""
    result = run_child_pytest(
        pytester,
        monkeypatch,
        'import importlib\n'
        'def test_import_fails(tmp_path, monkeypatch):\n'
        f"    (tmp_path / 'leaves_mid_import.py').write_text({SELF_REMOVING_MODULE!r})\n"
        '    monkeypatch.syspath_prepend(tmp_path)\n'
        "    importlib.import_module('leaves_mid_import')\n",
        conftest_source=(
            'from tests import import_failure_state, import_failure_threads, module_removals\n'
            'def fail(*args, **keywords):\n'
            "    raise ValueError('planted')\n"
            'import_failure_threads.live_thread_report = fail\n'
            'module_removals.removals_report = fail\n'
            'import_failure_state.modules_state_report = fail\n'
        ),
    )

    result.assert_outcomes(failed=1)
    output = result.stdout.str()
    assert 'INTERNALERROR' not in output
    assert "KeyError: 'leaves_mid_import'" in output
    for title in (SECTION_TITLE, REMOVALS_SECTION_TITLE, STATE_SECTION_TITLE):
        assert 'this section could not be written: ValueError: planted' in section(output, title)


def test_collections_are_counted_from_the_failing_tests_own_start(pytester, monkeypatch):
    """Through pytest: an earlier test's full collections are not this test's."""
    result = run_child_pytest(
        pytester,
        monkeypatch,
        'import gc, importlib\n'
        'def test_collects():\n'
        '    for _ in range(50):\n'
        '        gc.collect()\n'
        'def test_import_fails(tmp_path, monkeypatch):\n'
        '    gc.disable()\n'
        '    gc.collect()\n'
        f"    (tmp_path / 'leaves_mid_import.py').write_text({SELF_REMOVING_MODULE!r})\n"
        '    monkeypatch.syspath_prepend(tmp_path)\n'
        "    importlib.import_module('leaves_mid_import')\n",
    )

    result.assert_outcomes(passed=1, failed=1)
    assert 'generation 2: 1 collections' in section(result.stdout.str(), STATE_SECTION_TITLE)
