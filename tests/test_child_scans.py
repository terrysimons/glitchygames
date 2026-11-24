"""tests/child_scans.py: a scan run in a child process answers exactly what it returned there."""

from __future__ import annotations

import os
import sys

import pytest

from tests.child_scans import ChildScanError, scan_in_child

FAILURE_MESSAGE = 'the planted scan failed'


def findings_of_every_json_kind(*, prefix: str) -> dict[str, list[object]]:
    """A scan returning every JSON kind, printing on the way (it must not reach the result).

    Returns:
        Nested lists and dictionaries of strings, numbers, booleans and None.

    """
    sys.stdout.write(f'{prefix}: printed by the scan\n')
    return {f'{prefix}.found': ['a', 1, 2.5, True, None, {'nested': []}], 'empty': []}


def failing_scan() -> list[str]:
    """A scan that raises.

    Raises:
        ValueError: Always.

    """
    raise ValueError(FAILURE_MESSAGE)


def tuple_returning_scan() -> tuple[str, ...]:
    """A scan returning a tuple, which JSON would bring back as a list.

    Returns:
        A tuple.

    """
    return ('found',)


def process_id_scan() -> int:
    """A scan answering the process it ran in.

    Returns:
        Its process id.

    """
    return os.getpid()


def test_a_scan_answers_what_it_returned_in_its_child():
    """Every JSON kind comes back unchanged; what the scan prints does not."""
    arguments = {'prefix': 'planted'}

    assert scan_in_child(
        scan=findings_of_every_json_kind, arguments=arguments
    ) == findings_of_every_json_kind(**arguments)


def test_the_scan_runs_in_another_process():
    """The scan's memory is a child's: it runs outside this process."""
    assert scan_in_child(scan=process_id_scan) != os.getpid()


def test_a_scan_that_raises_fails_with_the_childs_error():
    """The child's traceback is in the error, so a guard's own failure message is not lost."""
    with pytest.raises(ChildScanError, match=FAILURE_MESSAGE):
        scan_in_child(scan=failing_scan)


def test_a_result_json_would_change_is_refused():
    """A tuple would come back as a list: refused, never compared as something else."""
    with pytest.raises(ChildScanError, match='not plain JSON'):
        scan_in_child(scan=tuple_returning_scan)


def test_a_function_a_child_cannot_import_is_refused_before_any_child_starts(mocker):
    """A nested function has no module-level name to import."""
    run_command = mocker.patch('tests.child_scans.run_command')

    def nested_scan() -> list[str]:
        return []

    with pytest.raises(ChildScanError, match='not a module-level function'):
        scan_in_child(scan=nested_scan)
    run_command.assert_not_called()
