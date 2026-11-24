"""Run a whole-source scan in a child process, so the memory it takes goes when the child ends.

A guard that parses every module of the workspace (an AST each, or every line of every tracked
file) builds hundreds of thousands of small objects at once. Freed, they still pin the
interpreter's small-object arenas: a few survivors per arena (interned names, cached values) keep
the arena allocated, so the test process's resident floor stays raised for the rest of the run
(tests/test_engine_context_source_guards.py alone: 50 arenas at the start, 164 at its peak, 142
still allocated after a collection, with about 5 MiB of live objects; measured in CircleCI's Linux
container on 2026-11-23, it raised the floor by 74 MiB). A child's arenas go back to the system
when it exits.

``scan_in_child(scan=..., arguments=...)`` runs ``scan(**arguments)`` in a fresh interpreter and
returns what it returned. The scan must be a module-level function of a module under the
repository (a test module, or a helper of one), and its arguments and result must be JSON: plain
lists, dictionaries, strings, numbers, booleans and None (a set or a path is converted by the
caller, and a tuple comes back as a list). The child is started through
``glitchygames.process.run_command``, which holds it until it is reaped, from the repository's
root, so it imports the same ``tests`` package; its standard output carries only the JSON result
(anything the scan or an import prints goes to its standard error).
"""

from __future__ import annotations

import importlib
import inspect
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from glitchygames.process import OutputCapture, run_command
from tests.ast_scanning import PROJECT_ROOT, module_name_of

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

# The JSON values a scan takes and returns
type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None

# The slowest scan (every tracked file's lines) takes a few seconds; far past it, a child that
# hangs is killed and the test fails
SCAN_TIMEOUT_SECONDS = 300.0
# pygame prints its banner as it is imported: hidden, so the child's output is its result alone
HIDE_PYGAME_BANNER = {'PYGAME_HIDE_SUPPORT_PROMPT': '1'}


class ChildScanError(RuntimeError):
    """A scan's child process failed: its exit status and standard error say why."""


def scan_module_name(*, scan: Callable[..., object]) -> str:
    """Return the module a scan is imported from in the child, from the file that defines it.

    The file decides, not ``scan.__module__``: pytest imports a test file under a name of its own
    choosing (``--import-mode=importlib``).

    Args:
        scan: A module-level function of a Python file under the repository.

    Returns:
        Its module's dotted name (``tests.test_read_only_views``).

    Raises:
        ChildScanError: The function is not module-level, or its file is outside the repository.

    """
    if '.' in scan.__qualname__:
        message = f'{scan.__qualname__} is not a module-level function: a child cannot import it'
        raise ChildScanError(message)
    source_file = Path(inspect.getfile(scan)).resolve()
    if not source_file.is_relative_to(PROJECT_ROOT):
        message = (
            f'{source_file} is outside the repository ({PROJECT_ROOT}): a child cannot import it'
        )
        raise ChildScanError(message)
    return module_name_of(relative=source_file.relative_to(PROJECT_ROOT))


def scan_in_child[ResultT](
    *, scan: Callable[..., ResultT], arguments: Mapping[str, JsonValue] | None = None
) -> ResultT:
    """Run ``scan(**arguments)`` in a child process and return its result.

    Args:
        scan: A module-level function returning JSON (``scan_module_name``), so what comes back
            is what it returned, of the type it declares.
        arguments: Its keyword arguments, each a JSON value; None passes none.

    Returns:
        What the scan returned, decoded from JSON.

    Raises:
        ChildScanError: The child failed (an exception in the scan, an import error, a result
            that JSON does not carry unchanged): the message holds its exit status and standard
            error.

    """
    module_name = scan_module_name(scan=scan)
    finished = run_command(
        command=[sys.executable, '-m', 'tests.child_scans', module_name, scan.__name__],
        environment={**os.environ, **HIDE_PYGAME_BANNER},
        timeout_seconds=SCAN_TIMEOUT_SECONDS,
        capture_output=OutputCapture.APART,
        working_directory=PROJECT_ROOT,
        input_text=json.dumps(dict(arguments or {})),
    )
    if finished.returncode != 0:
        message = (
            f'the scan {module_name}.{scan.__name__} failed in its child process '
            f'(exit status {finished.returncode}):\n{finished.stderr}'
        )
        raise ChildScanError(message)
    return json.loads(finished.stdout)


def main(arguments: Sequence[str]) -> int:
    """Run one scan: its module and function from ``arguments``, its keyword arguments on stdin.

    Writes the scan's result as JSON to standard output; whatever else is printed goes to
    standard error.

    Args:
        arguments: The scan's module and function name.

    Returns:
        The exit status (0; an exception in the scan ends the child with Python's own status).

    Raises:
        TypeError: The result is not JSON that decodes to itself (a tuple would come back as a
            list, a set not at all): the caller would compare something other than the scan's
            findings.

    """
    module_name, function_name = arguments
    result_stream = sys.stdout
    sys.stdout = sys.stderr
    keyword_arguments = json.loads(sys.stdin.read())
    scan = getattr(importlib.import_module(module_name), function_name)
    result = scan(**keyword_arguments)
    encoded = json.dumps(result)
    # A tuple decodes to a list and a non-string key to a string, neither equal to what it was
    if json.loads(encoded) != result:
        message = f'{module_name}.{function_name} returned {type(result).__name__}, not plain JSON'
        raise TypeError(message)
    result_stream.write(encoded)
    result_stream.flush()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
