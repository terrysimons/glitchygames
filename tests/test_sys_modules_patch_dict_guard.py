"""No test file uses patch.dict(sys.modules, ...) — it clears the whole dict on teardown.

``patch.dict(sys.modules)`` takes a full snapshot at setup and calls ``sys.modules.clear()``
at teardown before restoring the snapshot. That ``clear()`` races with any thread currently
importing a module for the first time, causing a ``KeyError`` inside importlib's
``_load_unlocked`` (bugs/2026-11-20-httpcore2-import-keyerror-on-windows.md).

The safe replacements:

- **Pattern A** (whole-dict snapshot, to clean up newly imported modules): request the
  ``clean_modules_on_teardown`` fixture (tests/harness.py) instead.
- **Pattern B** (specific entries): use ``monkeypatch.setitem(sys.modules, name, value)``
  or ``monkeypatch.delitem(sys.modules, name)`` instead.
"""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def _is_patch_dict_sys_modules(node: ast.Call) -> bool:
    """Return True when the call patches sys.modules via patch.dict.

    Matches both ``*.patch.dict(sys.modules, ...)`` and ``*.patch.dict('sys.modules', ...)``.
    """
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr != 'dict':
        return False
    if not isinstance(func.value, ast.Attribute) or func.value.attr != 'patch':
        return False
    if not node.args:
        return False
    first = node.args[0]
    if isinstance(first, ast.Attribute) and first.attr == 'modules':
        return isinstance(first.value, ast.Name) and first.value.id == 'sys'
    return isinstance(first, ast.Constant) and first.value == 'sys.modules'


def patch_dict_sys_modules_calls(source_path: Path) -> list[str]:
    """Return ``<path>:<line>`` for every ``patch.dict(sys.modules, ...)`` call in a file.

    Args:
        source_path: The Python file to scan.

    Returns:
        Location strings for each offending call, in source order.

    """
    try:
        tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
    except SyntaxError:
        return []
    return [
        f'{source_path}:{node.lineno}'
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _is_patch_dict_sys_modules(node)
    ]


def _test_files(project_root: Path):
    """Yield every test Python file under the repository's test directories.

    Yields:
        Path to each ``test_*.py`` file found.

    """
    for directory in [project_root / 'tests', *sorted((project_root / 'src').rglob('tests'))]:
        if directory.is_dir():
            yield from sorted(directory.rglob('test_*.py'))


def test_no_test_uses_patch_dict_sys_modules():
    """No test file calls patch.dict(sys.modules): it clears the whole dict on teardown.

    Use ``clean_modules_on_teardown`` (Pattern A) or ``monkeypatch.setitem``/
    ``monkeypatch.delitem`` (Pattern B) instead.
    """
    offenders = [
        location
        for source_path in _test_files(PROJECT_ROOT)
        for location in patch_dict_sys_modules_calls(source_path)
    ]

    assert offenders == [], (
        'These test locations call patch.dict(sys.modules, ...), which runs '
        'sys.modules.clear() on teardown and races with concurrent imports:\n'
        + '\n'.join(f'  {o}' for o in offenders)
        + '\nUse clean_modules_on_teardown (Pattern A) or monkeypatch.setitem/'
        'monkeypatch.delitem (Pattern B) instead.'
    )


def test_the_guard_detects_the_attribute_form(tmp_path):
    """patch.dict(sys.modules) is detected when sys.modules is an attribute reference."""
    source = tmp_path / 'test_example.py'
    source.write_text(
        'import sys\ndef test_x(mocker):\n    mocker.patch.dict(sys.modules)\n',
        encoding='utf-8',
    )

    assert patch_dict_sys_modules_calls(source) == [f'{source}:3']


def test_the_guard_detects_the_string_form(tmp_path):
    """patch.dict('sys.modules', {...}) is detected when the first argument is a string."""
    source = tmp_path / 'test_example.py'
    source.write_text(
        "import sys\ndef test_x(mocker):\n    mocker.patch.dict('sys.modules', {'x': None})\n",
        encoding='utf-8',
    )

    assert patch_dict_sys_modules_calls(source) == [f'{source}:3']


def test_the_guard_ignores_patch_dict_on_other_dicts(tmp_path):
    """patch.dict(os.environ, ...) is not an offender."""
    source = tmp_path / 'test_example.py'
    source.write_text(
        'import os\ndef test_x(mocker):\n    mocker.patch.dict(os.environ, {"X": "1"})\n',
        encoding='utf-8',
    )

    assert patch_dict_sys_modules_calls(source) == []


def test_the_guard_ignores_monkeypatch_setitem(tmp_path):
    """monkeypatch.setitem(sys.modules, ...) is not an offender."""
    source = tmp_path / 'test_example.py'
    source.write_text(
        'import sys\ndef test_x(monkeypatch):\n    monkeypatch.setitem(sys.modules, "x", None)\n',
        encoding='utf-8',
    )

    assert patch_dict_sys_modules_calls(source) == []
