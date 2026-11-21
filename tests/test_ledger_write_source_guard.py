"""No in-place writer reaches a replay-ledger file: every ledger write is whole or nothing.

A ledger row file or the pending ledger written in place (``Path.write_text``, or ``open`` for
writing) and stopped part way leaves a truncated row: the Pi hook then refused every row of
that Pi, and an append after a cut line lost the next row
(bugs/2026-11-20-ledger-row-writes-are-not-atomic.md). So in the modules that write ledgers,
a file is opened for writing only in the functions of ALLOWED_WRITERS, each for the reason
given: ``recording_metrics.write_ledger_file`` (a partial copy that then replaces the file) and
``recording_metrics.append_ledger_rows`` (complete lines after its line-break guard). Every
other ledger write calls one of them. A legitimate one-off write in these modules (a report, a
temporary file) joins ALLOWED_WRITERS with its reason.

``scripts/measure_on_raspberry_pi.py`` writes no ledger itself (it copies the row files a Pi
sent), and engine tests never reach ``scripts/`` (``tests/test_suite_collection.py``), so it is
not scanned here.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from tests.ast_scanning import PROJECT_ROOT
from tests.engine_source import ENGINE_DIRECTORY

if TYPE_CHECKING:
    from pathlib import Path

PACKAGE = PROJECT_ROOT / ENGINE_DIRECTORY

# The modules that write replay-ledger files, relative to the package
LEDGER_WRITING_MODULES = ('recording_metrics.py', 'replay/tools/measure.py')

# (module, function) -> why it may open a file for writing
ALLOWED_WRITERS = {
    ('recording_metrics.py', 'write_ledger_file'): (
        'writes the partial copy, which then replaces the ledger file whole'
    ),
    ('recording_metrics.py', 'append_ledger_rows'): (
        'appends complete lines in one write, after ending a cut last line'
    ),
}

# Path methods that write a file in place
IN_PLACE_WRITE_METHODS = frozenset({'write_text', 'write_bytes'})
# Characters of an open mode that write
WRITING_MODE_CHARACTERS = frozenset('wax+')


def _opens_for_writing(call: ast.Call) -> bool:
    """Return whether a call writes a file: ``write_text``, ``write_bytes`` or a writing ``open``.

    An ``open`` whose mode is not a literal counts as writing: the scan can't tell.

    Returns:
        True for a writing call.

    """
    function = call.func
    name = function.attr if isinstance(function, ast.Attribute) else getattr(function, 'id', '')
    if name in IN_PLACE_WRITE_METHODS:
        return True
    if name != 'open':
        return False
    # Path.open(mode) takes the mode first; open(file, mode) second
    position = 0 if isinstance(function, ast.Attribute) else 1
    mode: ast.expr | None = call.args[position] if len(call.args) > position else None
    mode = next((keyword.value for keyword in call.keywords if keyword.arg == 'mode'), mode)
    if mode is None:
        return False
    if not (isinstance(mode, ast.Constant) and isinstance(mode.value, str)):
        return True
    return not WRITING_MODE_CHARACTERS.isdisjoint(mode.value)


def writing_calls(*, source: str) -> list[tuple[str, int]]:
    """Return each call that writes a file, with the top-level function or class it is in.

    Returns:
        (its function or class name, or ``<module>`` outside any, line) for each writing call.

    """
    found: list[tuple[str, int]] = []
    for node in ast.parse(source).body:
        is_named = isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        owner = node.name if is_named else None
        found.extend(
            (owner or '<module>', call.lineno)
            for call in ast.walk(node)
            if isinstance(call, ast.Call) and _opens_for_writing(call)
        )
    return found


def module_path(module: str) -> Path:
    """Return a ledger-writing module's file.

    Returns:
        Its path in the checkout.

    """
    return PACKAGE / module


@pytest.mark.parametrize('module', LEDGER_WRITING_MODULES)
def test_only_the_whole_or_nothing_writers_open_a_file_for_writing(module):
    """A ledger module writes a file only in the functions allowed to."""
    source = module_path(module).read_text(encoding='utf-8')

    unexpected = [
        f'{module}:{line} in {function}'
        for function, line in writing_calls(source=source)
        if (module, function) not in ALLOWED_WRITERS
    ]

    assert unexpected == [], (
        'Write ledger files through recording_metrics.write_ledger_file or append_ledger_rows '
        '(or list a one-off write in ALLOWED_WRITERS with its reason)'
    )


@pytest.mark.parametrize(('module', 'function'), sorted(ALLOWED_WRITERS))
def test_every_allowed_writer_still_writes(module, function):
    """A stale allowance would let a new writer of that name through unseen."""
    source = module_path(module).read_text(encoding='utf-8')

    assert function in {owner for owner, _line in writing_calls(source=source)}


@pytest.mark.parametrize(
    ('source', 'expected'),
    [
        ("def f(path):\n    path.write_text('x')\n", [('f', 2)]),
        ("def f(path):\n    path.write_bytes(b'x')\n", [('f', 2)]),
        ("def f(path):\n    path.open('a')\n", [('f', 2)]),
        ("def f(path):\n    path.open(mode='w', encoding='utf-8')\n", [('f', 2)]),
        ("def f(name):\n    open(name, 'r+')\n", [('f', 2)]),
        ('def f(path, mode):\n    path.open(mode)\n', [('f', 2)]),
        ("class Writer:\n    def f(self, path):\n        path.write_text('x')\n", [('Writer', 3)]),
        ("def f(path):\n    path.open('rb')\n", []),
        ('def f(path):\n    path.open()\n', []),
        ("def f(name):\n    open(name)\n    text.write('x')\n", []),
    ],
    ids=[
        'write-text',
        'write-bytes',
        'append',
        'mode-keyword',
        'builtin-open-update',
        'mode-not-a-literal',
        'in-a-class',
        'read-binary',
        'default-mode',
        'reads-and-stream-writes',
    ],
)
def test_the_scan_finds_every_kind_of_writing_call(source, expected):
    """The guard can fail: each way of writing a file in place is found, and reads are not."""
    assert writing_calls(source=source) == expected
