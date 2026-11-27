"""A run whose project modules are loaded twice stops at its start (tests/module_copies_guard.py).

2026-11-27: ``--cov=glitchygames.sprites.hud_label`` (a dotted coverage source) failed 8 Brave
Adventurer tests in a fixed order and none without it: coverage imported the engine to find the
module, then took those modules out of ``sys.modules``, so the harness's ``pixel_snap`` and the
game's were two modules with two snap modes, and the harness's reset missed the game's
(bugs/2026-11-27-a-dotted-coverage-source-loaded-the-engine-twice.md).
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from tests.module_copies_guard import modules_loaded_twice

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUBPROCESS_TIMEOUT_SECONDS = 120.0


def module(*, name: str, file: Path) -> types.ModuleType:
    """Build a module object as an import would, with its file."""
    built = types.ModuleType(name)
    built.__file__ = str(file)
    return built


def test_a_package_holding_another_copy_of_its_submodule_is_reported(tmp_path, monkeypatch):
    """The package's attribute and sys.modules' entry are two modules of the same file."""
    package = module(name='twice_package', file=tmp_path / 'twice_package' / '__init__.py')
    loaded = module(name='twice_package.state', file=tmp_path / 'twice_package' / 'state.py')
    vars(package)['state'] = module(
        name='twice_package.state', file=tmp_path / 'twice_package' / 'state.py'
    )
    monkeypatch.setitem(sys.modules, 'twice_package', package)
    monkeypatch.setitem(sys.modules, 'twice_package.state', loaded)

    assert modules_loaded_twice(roots=(tmp_path,)) == ['twice_package.state']


def test_one_copy_and_modules_elsewhere_are_not_reported(tmp_path, monkeypatch):
    """The same object both ways is one module; a stale copy outside the roots is not ours."""
    package = module(name='once_package', file=tmp_path / 'once_package' / '__init__.py')
    vars(package)['state'] = module(
        name='once_package.state', file=tmp_path / 'once_package' / 'state.py'
    )
    monkeypatch.setitem(sys.modules, 'once_package', package)
    monkeypatch.setitem(sys.modules, 'once_package.state', vars(package)['state'])
    elsewhere = tmp_path.parent / f'{tmp_path.name}-elsewhere'
    other = module(name='other_package', file=elsewhere / 'other_package' / '__init__.py')
    vars(other)['state'] = module(
        name='other_package.state', file=elsewhere / 'other_package' / 'state.py'
    )
    monkeypatch.setitem(sys.modules, 'other_package', other)
    monkeypatch.setitem(
        sys.modules,
        'other_package.state',
        module(name='other_package.state', file=elsewhere / 'other_package' / 'state.py'),
    )

    assert modules_loaded_twice(roots=(tmp_path,)) == []


def test_this_run_loads_each_project_module_once():
    """The run these tests are in passed the check at its start, and nothing split since."""
    assert modules_loaded_twice(roots=(PROJECT_ROOT / 'src', PROJECT_ROOT / 'tests')) == []


ONE_TEST = """
def test_nothing():
    pass
"""


def test_a_dotted_coverage_source_stops_the_run_with_the_cause(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The harness's session start names the split modules, the cause and what to run instead."""
    monkeypatch.setenv('PYTHONPATH', str(PROJECT_ROOT))
    monkeypatch.setenv('SDL_VIDEODRIVER', 'dummy')
    monkeypatch.setenv('SDL_AUDIODRIVER', 'dummy')
    # Loaded as the repository loads it, from a conftest, so after coverage has started: a
    # plugin given with -p loads first, the engine with it, and coverage then removes nothing
    pytester.makeconftest("pytest_plugins = ['tests.harness']")
    tests = pytester.makepyfile(test_one=ONE_TEST)

    result = pytester.runpytest_subprocess(
        '-c',
        str(PROJECT_ROOT / 'pyproject.toml'),
        '--rootdir',
        str(pytester.path),
        '--confcutdir',
        str(pytester.path),
        '-p',
        'no:cacheprovider',
        '-p',
        'no:xdist',
        '-p',
        'no:randomly',
        '-o',
        'addopts=',
        '--cov=glitchygames.sprites.hud_label',
        '--cov-report=',
        '--cov-fail-under=0',
        str(tests),
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )

    # Stopped at the session's start: no test ran, so there is no summary line to count
    assert result.ret == pytest.ExitCode.USAGE_ERROR
    # One line, in this order: the modules, the cause, what to run instead
    expected = (
        '*glitchygames.pixel_snap*loaded twice*dotted --cov*'
        '--cov=glitchygames*coverage report --include*'
    )
    result.stdout.fnmatch_lines([expected])
