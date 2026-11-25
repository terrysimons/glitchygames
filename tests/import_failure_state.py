"""What ``sys.modules`` and the garbage collector looked like when a test's import failed.

Triage tool for bugs/2026-11-20-httpcore2-import-keyerror-on-windows.md, reported by
tests/import_failure_threads.py. Read when the report is made, after the exception has unwound: by
then importlib has deleted the entry of each module whose own code was running, so those being
absent is expected (the section names them). What separates the hypotheses is which other names
under the failed module's top-level package are there (``HOW_TO_READ``); a name that is gone is
found through its package's attribute, read from ``sys.modules`` or, when the package is gone too,
from the traceback's frames. Children of a finished subpackage that has itself left ``sys.modules``
are not listed: nothing here holds it.
Tests: tests/test_import_failure_state.py.
"""

from __future__ import annotations

import gc
import sys
import traceback
import types
from typing import TYPE_CHECKING, Any

from tests.module_removals import LOAD_FILENAME, LOAD_FUNCTION

if TYPE_CHECKING:
    from collections.abc import Mapping
    from types import TracebackType

# How to read the state: hints, each with the other explanation it leaves open
HOW_TO_READ = (
    'How to read this (hints, not proof):',
    '- absent, with its own code in the traceback: nothing (importlib deletes it, unwinding)',
    '- only the failed name absent: perhaps a targeted delete, or a second load failing',
    '- siblings loaded earlier absent too: perhaps a whole-dictionary restore',
    '- but a `with patch.dict(sys.modules)` in the failing test restores as the exception unwinds,',
    '  after the failure, and looks the same',
    '- the failed name present: perhaps it was put back since, or the pop missed it',
    '- found by iteration but not by hash, or the other way: perhaps a fault in the dictionary',
)


def failed_module(error: BaseException) -> str | None:
    """Return the module an import failure names.

    Returns:
        A ``KeyError``'s key, an ``ImportError``'s module, or None when there is neither.

    """
    match error:
        case KeyError(args=(str() as name,)):
            return name
        case ImportError(name=name):
            return name
        case _:
            return None


def loads_report(*, name: str, traceback_object: TracebackType | None) -> str:
    """Describe the loads of a module a traceback passes through.

    CPython strips importlib's frames around a module's code from a traceback, so a load inside
    another of the same module shows as that module's own code, not as a second load frame.

    Returns:
        How many frames load that module, and how many run its code.

    """
    loading = running = 0
    for frame, _ in traceback.walk_tb(traceback_object):
        code = frame.f_code
        if code.co_name == LOAD_FUNCTION and code.co_filename == LOAD_FILENAME:
            loading += frame.f_locals['spec'].name == name
        elif code.co_name == '<module>':
            running += frame.f_globals.get('__name__') == name
    return (
        f'in the traceback, {name} is being loaded by {loading} frames and its own code is run by '
        f'{running} (a load with its code above it: one load inside another; a load that had '
        'ended does not show)'
    )


def running_modules(traceback_object: TracebackType | None) -> list[str]:
    """Name the modules whose own code a traceback passes through.

    Returns:
        Their names, outermost first.

    """
    return [
        str(frame.f_globals.get('__name__'))
        for frame, _ in traceback.walk_tb(traceback_object)
        if frame.f_code.co_name == '<module>'
    ]


def namespace_of(module: object) -> Mapping[str, Any]:
    """Read a module's attributes without its own ``__getattribute__`` (a lazy module would load).

    Returns:
        Its ``__dict__``, or nothing for an object without one (``sys.modules`` may hold None).

    """
    try:
        return object.__getattribute__(module, '__dict__')
    except AttributeError:
        return {}


def package_namespaces(
    *, modules: Mapping[str, object], traceback_object: TracebackType | None
) -> dict[str, Mapping[str, Any]]:
    """Find each module's attributes, those of a module already gone from the traceback's frames.

    Returns:
        The attributes by module name; ``sys.modules``'s module wins over a frame's.

    """
    namespaces: dict[str, Mapping[str, Any]] = {}
    for frame, _ in traceback.walk_tb(traceback_object):
        name = frame.f_globals.get('__name__')
        if isinstance(name, str):
            namespaces[name] = frame.f_globals
    namespaces.update((name, namespace_of(module)) for name, module in modules.items())
    return namespaces


def parent_attribute_report(
    *, name: str, module: object, namespaces: Mapping[str, Mapping[str, Any]]
) -> str:
    """Compare a module with the attribute its package holds for it.

    Returns:
        Whether they are the same object, in words.

    """
    parent, _, child = name.rpartition('.')
    if not parent:
        return 'top level'
    if parent not in namespaces:
        return f'{parent} not found'
    if child not in namespaces[parent]:
        return f'{parent} has no attribute for it'
    same = namespaces[parent][child] is module
    return f"{'the same object as' if same else 'NOT the object'} {parent}'s attribute"


def modules_under_report(
    *,
    top: str,
    modules: Mapping[str, object],
    namespaces: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Describe every module under a top-level package, in ``sys.modules``'s order.

    Returns:
        One line for each entry, then one for each module only its package's attribute holds.

    """
    lines = [f'under {top}, of the {len(modules)} entries of sys.modules:']
    for position, (name, module) in enumerate(modules.items()):
        if not (name == top or name.startswith(f'{top}.')):
            continue
        initializing = getattr(namespace_of(module).get('__spec__'), '_initializing', 'unknown')
        attribute = parent_attribute_report(name=name, module=module, namespaces=namespaces)
        lines.append(
            f'  [{position}] {name}: id {id(module):#x}, _initializing {initializing}, {attribute}'
        )
    for package, namespace in namespaces.items():
        if not (package == top or package.startswith(f'{top}.')):
            continue
        for attribute, value in tuple(namespace.items()):
            name = f'{package}.{attribute}'
            if (
                # isinstance would run a lazy proxy's own __class__
                issubclass(type(value), types.ModuleType)
                and namespace_of(value).get('__name__') == name
                and name not in modules
            ):
                lines.append(
                    f"  {name}: NOT in sys.modules, held by {package}'s attribute, "
                    f'id {id(value):#x}'
                )
    return lines


def collections_report(before: list[dict[str, int]]) -> str:
    """Describe the process's garbage collection, now and since the test began.

    Args:
        before: ``gc.get_stats()`` when the test began.

    Returns:
        Whether it is on, its counts, and how many collections each generation has had since.

    """
    since = ', '.join(
        f'generation {generation}: {now["collections"] - then["collections"]} collections, '
        f'{now["collected"] - then["collected"]} objects'
        for generation, (then, now) in enumerate(zip(before, gc.get_stats(), strict=True))
    )
    return (
        f'garbage collection: {"enabled" if gc.isenabled() else "disabled"}, counts '
        f'{gc.get_count()}, thresholds {gc.get_threshold()}; since the test began: {since}'
    )


def modules_state_report(
    *,
    error: BaseException,
    traceback_object: TracebackType | None,
    startup_modules: Mapping[str, object],
    collections_before: list[dict[str, int]],
) -> str:
    """Describe ``sys.modules`` and garbage collection at the failure.

    Args:
        error: The exception the import failed with.
        traceback_object: Its traceback.
        startup_modules: The dictionary ``sys.modules`` was when the recording began.
        collections_before: ``gc.get_stats()`` when the test began.

    Returns:
        The section's text.

    """
    modules = sys.modules.copy()
    lines: list[str] = []
    name = failed_module(error)
    if name is None:
        lines.append('the failure names no module')
    else:
        by_hash = 'found' if name in sys.modules else 'NOT found'
        by_iteration = 'found' if any(key == name for key in tuple(sys.modules)) else 'NOT found'
        namespaces = package_namespaces(modules=modules, traceback_object=traceback_object)
        lines.extend((
            f'{name} in sys.modules: {by_hash} by hash, {by_iteration} by iteration',
            loads_report(name=name, traceback_object=traceback_object),
            f'own code in the traceback: {", ".join(running_modules(traceback_object)) or "none"}',
            *modules_under_report(
                top=name.partition('.')[0], modules=modules, namespaces=namespaces
            ),
            *HOW_TO_READ,
        ))
    same = sys.modules is startup_modules
    lines.extend((
        'sys.modules is the dictionary seen at startup'
        if same
        else 'sys.modules is NOT the dictionary seen at startup: it was rebound',
        collections_report(collections_before),
    ))
    return '\n'.join(lines)
