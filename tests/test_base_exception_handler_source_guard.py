"""No source catches BaseException (or a bare ``except:``) without raising it again.

A test callback that runs inside a game's run fails the test through ``pytest.fail``
(tests/replay/replay_helpers.py ``failing_the_test``), whose exception is a ``BaseException``:
the engine's crash boundary catches ``Exception``, so it passes through, and the test fails with
the callback's own message instead of the engine's ``INTERNAL_ERROR``
(bugs/2026-11-20-compare-trace-step-back-exited-internal-error-under-load.md). A handler that
catches ``BaseException`` and does not raise it again would swallow or convert it (and Ctrl-C and
a signal's ``SystemExit`` with it). Handlers that clean up and then raise again are fine: the
engine, the scene's playback scope, the trace reader, ``run_command`` and the compare child each
have one.

So this scans the engine's and every member's source (tests/workspace_sources.py): every
``except BaseException`` (alone or in a tuple), bare ``except:`` and
``contextlib.suppress(BaseException)`` must end its handler with a bare ``raise``. What an AST scan
cannot see: a handler that raises again only on some paths, a ``BaseException`` caught under
another name, and ``suppress`` called through another name.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from tests.ast_scanning import PROJECT_ROOT
from tests.workspace_sources import scanned_source_files

if TYPE_CHECKING:
    from pathlib import Path


def catches_everything(handler: ast.ExceptHandler) -> bool:
    """Tell whether a handler catches BaseException: bare, by name, or in a tuple.

    Returns:
        True when it does.

    """
    if handler.type is None:
        return True
    names = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return any(ast.unparse(name) in {'BaseException', 'builtins.BaseException'} for name in names)


def ends_by_raising_again(handler: ast.ExceptHandler) -> bool:
    """Tell whether a handler's last statement is a bare ``raise`` (or raises the caught name).

    Returns:
        True when it does.

    """
    last = handler.body[-1]
    if not isinstance(last, ast.Raise):
        return False
    return last.exc is None or (
        handler.name is not None
        and isinstance(last.exc, ast.Name)
        and last.exc.id == handler.name
        and last.cause is None
    )


def swallowing_handlers(*, source: str) -> list[int]:
    """Return the lines of handlers and suppressions that can swallow a BaseException.

    Returns:
        Each offending ``except`` or ``suppress`` line, in order.

    """
    lines = []
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.ExceptHandler)
            and catches_everything(node)
            and not ends_by_raising_again(node)
        ):
            lines.append(node.lineno)
        if (
            isinstance(node, ast.Call)
            and ast.unparse(node.func) in {'contextlib.suppress', 'suppress'}
            and any(ast.unparse(argument) == 'BaseException' for argument in node.args)
        ):
            lines.append(node.lineno)
    return sorted(lines)


def swallowing_handlers_in(*, project_root: Path) -> list[str]:
    """Return ``<file>:<line>`` for each handler in the scanned source that can swallow one.

    Returns:
        The findings, in scan order.

    """
    return [
        f'{key}:{line}'
        for key, path in scanned_source_files(project_root=project_root)
        for line in swallowing_handlers(source=path.read_text(encoding='utf-8'))
    ]


def test_no_source_swallows_a_base_exception():
    """The engine and every member raise again whatever BaseException they catch."""
    assert swallowing_handlers_in(project_root=PROJECT_ROOT) == []


def test_the_scan_reads_the_engine_and_the_members():
    """Not a vacuous pass: the scan covers the engine's handlers that do catch BaseException."""
    keys = {key for key, _ in scanned_source_files(project_root=PROJECT_ROOT)}

    assert {'engine/game_engine.py', 'replay/tools/compare.py', 'process.py'} <= keys
    assert any(key.startswith('src/apps/bitmappy/') for key in keys)


def test_cleanup_then_raise_again_is_allowed():
    """``except BaseException:`` that cleans up and raises (or raises the caught name) passes."""
    source = (
        'try:\n    work()\nexcept BaseException:\n    clean()\n    raise\n'
        'try:\n    work()\nexcept (OSError, BaseException) as error:\n    raise error\n'
    )

    assert swallowing_handlers(source=source) == []


def test_every_way_of_swallowing_is_found():
    """A bare except, BaseException alone or in a tuple, raising something else, and suppress."""
    source = (
        'try:\n    work()\nexcept:\n    pass\n'  # line 3
        'try:\n    work()\nexcept BaseException:\n    log()\n'  # line 7
        'try:\n    work()\nexcept (ValueError, BaseException) as error:\n'  # line 11
        '    raise RuntimeError() from error\n'
        'with contextlib.suppress(BaseException):\n    work()\n'  # line 13
        'try:\n    work()\nexcept Exception:\n    pass\n'  # Exception: not reported
    )

    assert swallowing_handlers(source=source) == [3, 7, 11, 13]
