"""Tests for Bitmappy's PyInstaller packaging: the frozen entry point and bitmappy.spec."""

import ast
import importlib.util
import runpy
from pathlib import Path, PurePosixPath

import pytest

import bitmappy
from bitmappy import SPRITE_CONFIG_DIR

# src/apps/bitmappy/tests/ -> the repository root, which holds bitmappy.spec and the paths it names
PROJECT_ROOT = Path(__file__).resolve().parents[4]
SPEC_PATH = PROJECT_ROOT / 'bitmappy.spec'
ENTRY_POINT_PATH = PROJECT_ROOT / 'scripts' / 'bitmappy_entry.py'


def _spec_analysis_call() -> ast.Call:
    """Return bitmappy.spec's Analysis(...) call, parsed (PyInstaller defines Analysis).

    Returns:
        ast.Call: The call.

    """
    spec_tree = ast.parse(SPEC_PATH.read_text(encoding='utf-8'))
    return next(
        node
        for node in ast.walk(spec_tree)
        if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'Analysis'
    )


def _spec_datas() -> list[tuple[str, str]]:
    """Return bitmappy.spec's Analysis(datas=[...]): (source, destination in the bundle) pairs.

    Returns:
        list[tuple[str, str]]: The pairs, in spec order; sources relative to the repository root.

    """
    return next(
        ast.literal_eval(keyword.value)
        for keyword in _spec_analysis_call().keywords
        if keyword.arg == 'datas'
    )


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
    mocker.patch('bitmappy.main', call_order.main)

    runpy.run_path(str(ENTRY_POINT_PATH), run_name='__main__')

    assert [call[0] for call in call_order.mock_calls] == ['freeze_support', 'main']


@pytest.mark.parametrize('module_name', _spec_hidden_imports())
def test_every_spec_hidden_import_exists(module_name):
    """Each hidden import names a module that exists, so PyInstaller can collect it."""
    assert importlib.util.find_spec(module_name) is not None, module_name


def test_spec_script_and_data_sources_exist():
    """The Analysis script and every datas source directory exist."""
    scripts = ast.literal_eval(_spec_analysis_call().args[0])
    data_sources = [source for source, _destination in _spec_datas()]

    assert all((PROJECT_ROOT / script).is_file() for script in scripts), scripts
    assert data_sources
    assert all((PROJECT_ROOT / source).is_dir() for source in data_sources), data_sources


def test_the_spec_bundles_the_resources_where_bitmappy_reads_them():
    """The frozen app finds the sprite library where SPRITE_CONFIG_DIR looks for it.

    PyInstaller sets a bundled module's __file__ under sys._MEIPASS, so the frozen Bitmappy
    reads <_MEIPASS>/bitmappy/resources/sprites: a datas destination must cover that path, and
    its source must hold the sprite library there.
    """
    package_parent = Path(bitmappy.__file__).resolve().parent.parent
    sprite_library_in_bundle = PurePosixPath(
        SPRITE_CONFIG_DIR.resolve().relative_to(package_parent).as_posix()
    )
    covering_datas = [
        (source, PurePosixPath(destination))
        for source, destination in _spec_datas()
        if sprite_library_in_bundle.is_relative_to(destination)
    ]

    assert sprite_library_in_bundle == PurePosixPath('bitmappy/resources/sprites')
    assert covering_datas
    for source, destination in covering_datas:
        bundled_sprite_library = (
            PROJECT_ROOT / source / sprite_library_in_bundle.relative_to(destination)
        )
        assert sorted(path.name for path in bundled_sprite_library.glob('*.toml')) == sorted(
            path.name for path in SPRITE_CONFIG_DIR.glob('*.toml')
        )


def test_spec_lists_the_audio_module_pygame_sdl2_imports():
    """pygame._sdl2 imports pygame._sdl2.audio when the package is imported; list it explicitly."""
    assert 'pygame._sdl2.audio' in _spec_hidden_imports()


AISUITE_HOOK_PATH = PROJECT_ROOT / 'packaging' / 'pyinstaller_hooks' / 'hook-aisuite.py'


def _hook_supported_providers() -> list[str]:
    """Return SUPPORTED_AI_PROVIDERS from the aisuite PyInstaller hook (parsed, not executed).

    Returns:
        list[str]: The aisuite provider keys the binary bundles.

    """
    hook_tree = ast.parse(AISUITE_HOOK_PATH.read_text(encoding='utf-8'))
    for node in hook_tree.body:
        if isinstance(node, ast.Assign) and any(
            getattr(target, 'id', None) == 'SUPPORTED_AI_PROVIDERS' for target in node.targets
        ):
            return list(ast.literal_eval(node.value))
    pytest.fail('hook-aisuite.py defines no SUPPORTED_AI_PROVIDERS')
    return []


def test_spec_uses_the_project_pyinstaller_hooks():
    """The aisuite hook is used: aisuite finds providers by globbing *_provider.py files.

    PyInstaller stores modules compiled inside its archive, so without the hook the glob
    finds nothing and every AI request fails with "Supported providers: set()".
    """
    hook_paths = next(
        ast.literal_eval(keyword.value)
        for keyword in _spec_analysis_call().keywords
        if keyword.arg == 'hookspath'
    )
    # Compared as paths: the spec writes / separators, which Windows paths print as \\
    assert AISUITE_HOOK_PATH.parent in [PROJECT_ROOT / hook_path for hook_path in hook_paths]
    assert AISUITE_HOOK_PATH.is_file()


def test_aisuite_hook_bundles_the_default_provider_and_real_modules():
    """The hook bundles the default model's provider, and every listed provider exists."""
    from bitmappy.ai_worker import AI_MODEL

    supported_providers = _hook_supported_providers()
    assert AI_MODEL.split(':', maxsplit=1)[0] in supported_providers
    for provider_key in supported_providers:
        module_name = f'aisuite.providers.{provider_key}_provider'
        assert importlib.util.find_spec(module_name) is not None, module_name
