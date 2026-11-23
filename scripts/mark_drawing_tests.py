"""Add the draws_frames marker to the tests a draws_frames report lists as drawing without it.

The frame fingerprints plugin's draws_frames check (glitchygames/testing/frame_fingerprints.py)
writes every test whose marker disagrees with what it did to ``test-results/frame-markers.txt``,
one ``<node id><TAB><reason>`` line each. Run the suite with ``--frame-markers-report-only`` to
list them without failing, then this script places the marker on each test listed as drawing
without it ("draws without the draws_frames marker ..."):

- a function all of whose collected cases are listed gets ``@pytest.mark.draws_frames`` above its
  decorators;
- a parametrized function only some of whose cases are listed gets the mark on each listed case
  instead: its value in the function's ``@pytest.mark.parametrize`` list becomes
  ``pytest.param(value, marks=pytest.mark.draws_frames)`` (or an existing ``pytest.param`` gains
  ``marks=``).

It collects the listed files with pytest (in process, ``--collect-only``) to learn each case's
function and parametrize index, so it places marks by what pytest collected, never by parsing
node ids. A file that needs it gains ``import pytest``. Run ``ruff format`` and ``ruff check
--select I --fix`` on the changed files afterwards.

A listed test that carries the marker already (the report is older than the code) is left
alone. Tests listed as marked but drawing nothing are printed, to remove by hand. The script
refuses, changing nothing, when a listed test cannot be placed: a node id pytest does not
collect, a case of a function whose parametrization is not one ``@pytest.mark.parametrize`` on
the function with a literal list, or a ``pytest.param`` that already has ``marks=``.

Exit codes: ``ExitCode.SUCCESS``; ``MISSING_INPUT`` when the report does not exist;
``UNUSABLE_INPUT`` when a test cannot be placed (each is printed).

Usage:
    uv run python -m scripts.mark_drawing_tests [REPORT]
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel, ConfigDict

from glitchygames.exit_codes import ExitCode
from glitchygames.testing.frame_fingerprints import DRAWS_FRAMES_MARKER, MARKERS_REPORT_PATH

if TYPE_CHECKING:
    from collections.abc import Sequence

# The report's reasons begin with these (DrawsFramesCheck.disagreement)
DRAWS_WITHOUT_THE_MARKER = f'draws without the {DRAWS_FRAMES_MARKER} marker'
MARKED_BUT_DRAWS_NOTHING = f'is marked {DRAWS_FRAMES_MARKER} but draws nothing'
MARK_EXPRESSION = f'pytest.mark.{DRAWS_FRAMES_MARKER}'
PARAMETRIZE_MARKER = 'parametrize'
# parametrize(argnames, argvalues, ...): the values are its second argument
ARGVALUES_POSITION = 1
ARGVALUES_KEYWORD = 'argvalues'
# parametrize's first argument names the arguments: a comma-separated string, or a list
ARGNAMES_POSITION = 0
ARGNAMES_KEYWORD = 'argnames'


class CollectedCase(BaseModel):
    """What pytest collected for one test case: where its function is and which case it is."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    nodeid: str
    path: Path
    # The function's qualified name in its module (a method: Class.method)
    qualname: str
    # The case's index in each parametrize decorator, by argument names; empty when not
    # parametrized
    indices: tuple[int, ...]
    # How many parametrize marks the case has, and whether every one is on the function itself
    parametrize_count: int
    parametrized_on_the_function: bool
    # Whether it carries the draws_frames marker already (a report older than the code)
    already_marked: bool


class CaseCollector:
    """A pytest plugin that records every collected case (``pytest_collection_modifyitems``)."""

    def __init__(self) -> None:
        """Start with no cases."""
        self.cases: dict[str, CollectedCase] = {}

    def pytest_collection_modifyitems(self, items: list[pytest.Item]) -> None:
        """Record each collected function's case.

        Args:
            items: The collected tests.

        """
        for item in items:
            if not isinstance(item, pytest.Function):
                continue
            self.cases[item.nodeid] = collected_case(item=item)


def collected_case(*, item: pytest.Function) -> CollectedCase:
    """Describe one collected test case.

    Args:
        item: The case.

    Returns:
        Its function's place and its parametrize indices.

    """
    function: object = item.obj
    callspec = getattr(item, 'callspec', None)
    indices = () if callspec is None else tuple(sorted(set(callspec.indices.values())))
    parametrize_marks = list(item.iter_markers(name=PARAMETRIZE_MARKER))
    own_marks: list[pytest.Mark] = list(getattr(function, 'pytestmark', []))
    own_parametrize_count = sum(1 for mark in own_marks if mark.name == PARAMETRIZE_MARKER)
    return CollectedCase(
        nodeid=item.nodeid,
        path=item.path,
        qualname=str(getattr(function, '__qualname__', item.name)),
        indices=indices,
        parametrize_count=len(parametrize_marks),
        parametrized_on_the_function=own_parametrize_count == len(parametrize_marks),
        already_marked=item.get_closest_marker(DRAWS_FRAMES_MARKER) is not None,
    )


class Edit(BaseModel):
    """One change to a file's bytes: replace a span (start == end inserts).

    Offsets are in bytes: the syntax tree's columns count UTF-8 bytes, and working on bytes
    keeps the file's own line endings.
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    start: int
    end: int
    text: bytes


def read_report(*, path: Path) -> tuple[list[str], list[str]]:
    """Read a draws_frames report.

    Args:
        path: The report.

    Returns:
        The node ids drawing without the marker, and those marked but drawing nothing.

    """
    drawing: list[str] = []
    idle: list[str] = []
    for line in path.read_text(encoding='utf-8').splitlines():
        nodeid, _, reason = line.partition('\t')
        if reason.startswith(DRAWS_WITHOUT_THE_MARKER):
            drawing.append(nodeid)
        elif reason.startswith(MARKED_BUT_DRAWS_NOTHING):
            idle.append(nodeid)
    return drawing, idle


def collect_cases(*, files: Sequence[str]) -> dict[str, CollectedCase]:
    """Collect files with pytest, in process, and return every case it found.

    Args:
        files: The test files.

    Returns:
        The cases by node id.

    """
    collector = CaseCollector()
    # The collected test modules are forgotten afterwards, so a later import (another
    # collection in this process) reads the files as they are then, not as they were
    modules_before = set(sys.modules)
    try:
        pytest.main(
            ['--collect-only', '-q', '-n', '0', '-p', 'no:cacheprovider', *files],
            plugins=[collector],
        )
    finally:
        for name in set(sys.modules) - modules_before:
            del sys.modules[name]
    return collector.cases


def find_function(*, module: ast.Module, qualname: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    """Find a function in a module's syntax tree by its qualified name.

    Args:
        module: The parsed module.
        qualname: ``function`` or ``Class.method`` (nested classes too).

    Returns:
        The function's definition.

    Raises:
        LookupError: If the module defines no such function.

    """
    body: list[ast.stmt] = module.body
    *class_names, function_name = qualname.split('.')
    for class_name in class_names:
        found_class = next(
            (node for node in body if isinstance(node, ast.ClassDef) and node.name == class_name),
            None,
        )
        if found_class is None:
            message = f'no class {class_name}'
            raise LookupError(message)
        body = found_class.body
    for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return node
    message = f'no function {qualname}'
    raise LookupError(message)


def argument_name_count(*, decorator: ast.Call) -> int:
    """Return how many arguments a ``@pytest.mark.parametrize`` names.

    Args:
        decorator: The decorator's call.

    Returns:
        The count: ``'a, b'`` and ``('a', 'b')`` both name two.

    Raises:
        LookupError: If the names are neither a literal string nor a literal list or tuple.

    """
    names: ast.expr | None = None
    if len(decorator.args) > ARGNAMES_POSITION:
        names = decorator.args[ARGNAMES_POSITION]
    for keyword in decorator.keywords:
        if keyword.arg == ARGNAMES_KEYWORD:
            names = keyword.value
    if isinstance(names, ast.Constant) and isinstance(names.value, str):
        return len([name for name in names.value.split(',') if name.strip()])
    if isinstance(names, (ast.List, ast.Tuple)):
        return len(names.elts)
    message = 'its parametrize argument names are not a literal'
    raise LookupError(message)


def parametrize_values(
    *, function: ast.FunctionDef | ast.AsyncFunctionDef
) -> tuple[list[ast.expr], int]:
    """Return the values listed in a function's one ``@pytest.mark.parametrize``.

    Args:
        function: The function's definition.

    Returns:
        The list's elements, in order, and how many arguments each value gives.

    Raises:
        LookupError: If the function has no such decorator, or its values are not a literal list
            or tuple.

    """
    for decorator in function.decorator_list:
        if not (
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == PARAMETRIZE_MARKER
        ):
            continue
        values: ast.expr | None = None
        if len(decorator.args) > ARGVALUES_POSITION:
            values = decorator.args[ARGVALUES_POSITION]
        for keyword in decorator.keywords:
            if keyword.arg == ARGVALUES_KEYWORD:
                values = keyword.value
        if isinstance(values, (ast.List, ast.Tuple)):
            return list(values.elts), argument_name_count(decorator=decorator)
        message = 'its parametrize values are not a literal list'
        raise LookupError(message)
    message = 'no @pytest.mark.parametrize on the function'
    raise LookupError(message)


def is_pytest_param(node: ast.expr) -> bool:
    """Tell whether an expression is a ``pytest.param(...)`` call.

    Args:
        node: The expression.

    Returns:
        True for ``pytest.param(...)``.

    """
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == 'param'
    )


def node_text(*, source: bytes, offsets: list[int], node: ast.expr) -> tuple[int, int, str]:
    """Return a node's span in a file's bytes and its source text.

    Args:
        source: The file's bytes.
        offsets: Each line's start offset in the bytes.
        node: The expression.

    Returns:
        Its start and end offsets, and its text.

    """
    start = offsets[node.lineno - 1] + node.col_offset
    end = offsets[require_int(node.end_lineno) - 1] + require_int(node.end_col_offset)
    return start, end, source[start:end].decode('utf-8')


def case_mark_edit(*, source: bytes, offsets: list[int], value: ast.expr, name_count: int) -> Edit:
    """Return the edit that marks one parametrize value.

    Args:
        source: The file's bytes.
        offsets: Each line's start offset in the bytes.
        value: The value's expression.
        name_count: How many arguments the value gives: a value for several is a tuple, whose
            items ``pytest.param`` takes one by one.

    Returns:
        The edit: the value wrapped in ``pytest.param`` (a tuple's items unpacked), or ``marks=``
        added to one.

    Raises:
        LookupError: If the value is a ``pytest.param`` that already has ``marks=``.

    """
    start, end, segment = node_text(source=source, offsets=offsets, node=value)
    if is_pytest_param(value):
        if isinstance(value, ast.Call) and any(
            keyword.arg == 'marks' for keyword in value.keywords
        ):
            message = 'its pytest.param already has marks='
            raise LookupError(message)
        inside = segment[:-1].rstrip()
        separator = ' ' if inside.endswith(('(', ',')) else ', '
        marked = f'{inside}{separator}marks={MARK_EXPRESSION})'
    elif name_count > 1 and isinstance(value, ast.Tuple):
        items = ', '.join(
            node_text(source=source, offsets=offsets, node=item)[2] for item in value.elts
        )
        marked = f'pytest.param({items}, marks={MARK_EXPRESSION})'
    elif name_count > 1:
        marked = f'pytest.param(*{segment}, marks={MARK_EXPRESSION})'
    else:
        marked = f'pytest.param({segment}, marks={MARK_EXPRESSION})'
    return Edit(start=start, end=end, text=marked.encode('utf-8'))


def require_int(value: int | None) -> int:
    """Return a syntax node's end position (always set on parsed source).

    Args:
        value: The position.

    Returns:
        The position.

    Raises:
        ValueError: If it is missing.

    """
    if value is None:
        message = 'a parsed node has no end position'
        raise ValueError(message)
    return value


def line_ending(*, source: bytes, offsets: list[int], line: int) -> bytes:
    """Return the line ending a line of the file uses (CRLF or LF).

    Args:
        source: The file's bytes.
        offsets: Each line's start offset in the bytes.
        line: The line number (1 for the first).

    Returns:
        CRLF or LF, as bytes.

    """
    text = source[offsets[line - 1] : offsets[line]]
    return b'\r\n' if text.endswith(b'\r\n') else b'\n'


def function_mark_edit(
    *, source: bytes, offsets: list[int], function: ast.FunctionDef | ast.AsyncFunctionDef
) -> Edit:
    """Return the edit that puts the marker above a function's decorators.

    Args:
        source: The file's bytes.
        offsets: Each line's start offset in the bytes.
        function: The function's definition.

    Returns:
        The insertion, indented as the function.

    """
    first_line = min([
        function.lineno,
        *(decorator.lineno for decorator in function.decorator_list),
    ])
    start = offsets[first_line - 1]
    newline = line_ending(source=source, offsets=offsets, line=first_line)
    decorator = f'{" " * function.col_offset}@{MARK_EXPRESSION}'.encode() + newline
    return Edit(start=start, end=start, text=decorator)


def import_pytest_edit(*, source: bytes, module: ast.Module, offsets: list[int]) -> Edit | None:
    """Return the edit that adds ``import pytest``, or None when the module has it.

    Args:
        source: The file's bytes.
        module: The parsed module.
        offsets: Each line's start offset in the bytes.

    Returns:
        An insertion before the first import after any ``from __future__``, or None.

    """
    for node in module.body:
        if isinstance(node, ast.Import) and any(alias.name == 'pytest' for alias in node.names):
            return None
    for node in module.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)) and not (
            isinstance(node, ast.ImportFrom) and node.module == '__future__'
        ):
            start = offsets[node.lineno - 1]
            newline = line_ending(source=source, offsets=offsets, line=node.lineno)
            return Edit(start=start, end=start, text=b'import pytest' + newline)
    start = offsets[module.body[0].lineno - 1] if module.body else 0
    return Edit(start=start, end=start, text=b'import pytest\n')


def line_offsets(source: bytes) -> list[int]:
    """Return each line's start offset in a file's bytes (and the end, after the last line).

    Args:
        source: The bytes.

    Returns:
        The offsets, line 1 first.

    """
    offsets = [0]
    for line in source.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    return offsets


def function_edits(
    *,
    source: bytes,
    module: ast.Module,
    qualname: str,
    listed: Sequence[CollectedCase],
    whole_function: bool,
) -> list[Edit]:
    """Plan the edits that mark one function's listed cases.

    Args:
        source: The file's bytes.
        module: The parsed file.
        qualname: The function's qualified name.
        listed: Its cases listed as drawing without the marker.
        whole_function: Whether every collected case of the function is listed.

    Returns:
        The marker above the function, or one mark per listed parametrize value.

    Raises:
        LookupError: If the function, or a listed case's value, cannot be found or marked.

    """
    offsets = line_offsets(source)
    function = find_function(module=module, qualname=qualname)
    if whole_function:
        return [function_mark_edit(source=source, offsets=offsets, function=function)]
    if any(
        case.parametrize_count != 1
        or not case.parametrized_on_the_function
        or len(case.indices) != 1
        for case in listed
    ):
        message = 'its cases are not one @pytest.mark.parametrize on the function'
        raise LookupError(message)
    values, name_count = parametrize_values(function=function)
    indices = sorted({case.indices[0] for case in listed})
    return [
        case_mark_edit(source=source, offsets=offsets, value=values[index], name_count=name_count)
        for index in indices
    ]


def plan_file_edits(
    *, path: Path, listed: Sequence[CollectedCase], cases: dict[str, CollectedCase]
) -> tuple[list[Edit], list[str]]:
    """Plan one file's edits for its listed cases.

    Args:
        path: The file.
        listed: The file's cases listed as drawing without the marker.
        cases: Every collected case (to tell whether all of a function's cases are listed).

    Returns:
        The edits, and the refusals (a line each).

    """
    source = path.read_bytes()
    module = ast.parse(source)
    offsets = line_offsets(source)
    edits: list[Edit] = []
    refusals: list[str] = []
    listed_ids = {case.nodeid for case in listed}
    by_function: dict[str, list[CollectedCase]] = {}
    for case in listed:
        by_function.setdefault(case.qualname, []).append(case)
    for qualname, function_cases in by_function.items():
        every_case = [
            case for case in cases.values() if case.path == path and case.qualname == qualname
        ]
        whole_function = all(case.nodeid in listed_ids for case in every_case)
        try:
            edits.extend(
                function_edits(
                    source=source,
                    module=module,
                    qualname=qualname,
                    listed=function_cases,
                    whole_function=whole_function,
                )
            )
        except LookupError as error:
            refusals.extend(f'{case.nodeid}: {error}' for case in function_cases)
    if edits:
        import_edit = import_pytest_edit(source=source, module=module, offsets=offsets)
        if import_edit is not None:
            edits.append(import_edit)
    return edits, refusals


def apply_edits(*, source: bytes, edits: Sequence[Edit]) -> bytes:
    """Apply edits to a file's bytes, last first, so earlier offsets stay right.

    Args:
        source: The bytes.
        edits: Non-overlapping edits.

    Returns:
        The edited bytes.

    """
    for edit in sorted(edits, key=lambda edit: (edit.start, edit.end), reverse=True):
        source = source[: edit.start] + edit.text + source[edit.end :]
    return source


def argument_parser() -> argparse.ArgumentParser:
    """Build the command line.

    Returns:
        The parser.

    """
    parser = argparse.ArgumentParser(
        description='Add the draws_frames marker to the tests a draws_frames report lists.'
    )
    parser.add_argument(
        'report',
        nargs='?',
        type=Path,
        default=MARKERS_REPORT_PATH,
        help=f'the report (default: {MARKERS_REPORT_PATH})',
    )
    return parser


def run(*, arguments: Sequence[str]) -> ExitCode:
    """Mark the report's drawing tests.

    Args:
        arguments: The command line, without the program name.

    Returns:
        The exit code.

    """
    report_path: Path = argument_parser().parse_args(arguments).report
    if not report_path.is_file():
        sys.stderr.write(f'{report_path}: no such report\n')
        return ExitCode.MISSING_INPUT
    drawing, idle = read_report(path=report_path)
    for nodeid in idle:
        sys.stdout.write(f'remove the marker by hand: {nodeid}\n')
    if not drawing:
        return ExitCode.SUCCESS
    files = sorted({nodeid.split('::', 1)[0] for nodeid in drawing})
    cases = collect_cases(files=files)
    refusals = [
        f'{nodeid}: pytest does not collect it' for nodeid in drawing if nodeid not in cases
    ]
    edits_by_path: dict[Path, list[Edit]] = {}
    listed_by_path: dict[Path, list[CollectedCase]] = {}
    for nodeid in drawing:
        if nodeid in cases and not cases[nodeid].already_marked:
            listed_by_path.setdefault(cases[nodeid].path, []).append(cases[nodeid])
    for path, listed in listed_by_path.items():
        edits, file_refusals = plan_file_edits(path=path, listed=listed, cases=cases)
        refusals.extend(file_refusals)
        edits_by_path[path] = edits
    if refusals:
        for refusal in refusals:
            sys.stderr.write(f'cannot place: {refusal}\n')
        return ExitCode.UNUSABLE_INPUT
    for path, edits in edits_by_path.items():
        path.write_bytes(apply_edits(source=path.read_bytes(), edits=edits))
        sys.stdout.write(f'edited {path} ({len(edits)} edit(s))\n')
    return ExitCode.SUCCESS


if __name__ == '__main__':
    sys.exit(run(arguments=sys.argv[1:]))
