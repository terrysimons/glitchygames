"""Tests for Bitmappy's PyInstaller packaging: the frozen entry point and bitmappy.spec."""

import ast
import importlib.util
import runpy
from pathlib import Path

import pytest

SPEC_PATH = Path('bitmappy.spec')
ENTRY_POINT_PATH = Path('scripts/bitmappy_entry.py')


def _spec_hidden_imports() -> list[str]:
    """Return the module names in bitmappy.spec's Analysis(hiddenimports=[...]).

    The spec is Python, so it is parsed rather than executed (PyInstaller defines Analysis).

    Returns:
        list[str]: The hidden import names, in spec order.

    """
    spec_tree = ast.parse(SPEC_PATH.read_text(encoding='utf-8'))
    for node in ast.walk(spec_tree):
        if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'Analysis':
            for keyword in node.keywords:
                if keyword.arg == 'hiddenimports':
                    return [ast.literal_eval(element) for element in keyword.value.elts]
    pytest.fail('bitmappy.spec has no Analysis(hiddenimports=[...])')
    return []


def test_entry_point_calls_freeze_support_before_starting_bitmappy(mocker):
    """freeze_support() runs before Bitmappy starts (and parses its arguments).

    In the frozen app, multiprocessing starts child processes (the AI worker, the resource
    tracker) by re-running this executable with its own arguments; freeze_support() must
    run them and exit before Bitmappy's argument parser sees those arguments.
    """
    call_order = mocker.Mock()
    mocker.patch('multiprocessing.freeze_support', call_order.freeze_support)
    mocker.patch('glitchygames.bitmappy.main', call_order.main)

    runpy.run_path(str(ENTRY_POINT_PATH), run_name='__main__')

    assert [call[0] for call in call_order.mock_calls] == ['freeze_support', 'main']


@pytest.mark.parametrize('module_name', _spec_hidden_imports())
def test_every_spec_hidden_import_exists(module_name):
    """Each hidden import names a module that exists, so PyInstaller can collect it."""
    assert importlib.util.find_spec(module_name) is not None, module_name


def test_spec_script_and_data_sources_exist():
    """The Analysis script and every datas source directory exist."""
    spec_tree = ast.parse(SPEC_PATH.read_text(encoding='utf-8'))
    analysis_call = next(
        node
        for node in ast.walk(spec_tree)
        if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'Analysis'
    )
    scripts = ast.literal_eval(analysis_call.args[0])
    data_sources = [
        source
        for keyword in analysis_call.keywords
        if keyword.arg == 'datas'
        for source, _destination in ast.literal_eval(keyword.value)
    ]

    assert all(Path(script).is_file() for script in scripts), scripts
    assert data_sources
    assert all(Path(source).is_dir() for source in data_sources), data_sources
