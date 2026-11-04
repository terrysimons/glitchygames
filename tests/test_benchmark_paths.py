"""Every benchmark lives where ``nox -s performance-test`` looks for benchmarks.

The session collects only ``_BENCHMARK_PATHS`` (noxfile.py), so a test that takes pytest-benchmark's
``benchmark`` fixture anywhere else would silently stop being measured.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOXFILE_PATH = PROJECT_ROOT / 'noxfile.py'
PYPROJECT_PATH = PROJECT_ROOT / 'pyproject.toml'


def noxfile_benchmark_paths() -> list[str]:
    """Return ``_BENCHMARK_PATHS`` as noxfile.py defines it.

    Returns:
        The paths, relative to the repository root.

    """
    module = ast.parse(NOXFILE_PATH.read_text(encoding='utf-8'))
    values = [
        node.value
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == '_BENCHMARK_PATHS'
            for target in node.targets
        )
    ]
    assert len(values) == 1, f'{NOXFILE_PATH} must define _BENCHMARK_PATHS exactly once'
    return list(ast.literal_eval(values[0]))


def benchmark_test_files() -> set[Path]:
    """Return every test module, under pytest's testpaths, with a test taking ``benchmark``.

    Returns:
        The modules' paths, relative to the repository root.

    """
    testpaths = tomllib.loads(PYPROJECT_PATH.read_text(encoding='utf-8'))['tool']['pytest'][
        'ini_options'
    ]['testpaths']
    files: set[Path] = set()
    for testpath in testpaths:
        for path in (PROJECT_ROOT / testpath).rglob('test_*.py'):
            module = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(module):
                if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    continue
                arguments = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
                if node.name.startswith('test_') and any(
                    argument.arg == 'benchmark' for argument in arguments
                ):
                    files.add(path.relative_to(PROJECT_ROOT))
    return files


def test_every_benchmark_is_under_the_performance_test_paths() -> None:
    """A test using the benchmark fixture outside _BENCHMARK_PATHS would never be measured."""
    roots = [PROJECT_ROOT / path for path in noxfile_benchmark_paths()]
    outside = sorted(
        str(path)
        for path in benchmark_test_files()
        if not any((PROJECT_ROOT / path).is_relative_to(root) for root in roots)
    )
    assert not outside, f'benchmarks outside noxfile.py _BENCHMARK_PATHS: {outside}'


def test_every_benchmark_path_exists_and_holds_benchmarks() -> None:
    """A stale path would make the session collect nothing there without failing."""
    files = benchmark_test_files()
    for path in noxfile_benchmark_paths():
        root = PROJECT_ROOT / path
        assert root.exists(), f'noxfile.py _BENCHMARK_PATHS names a missing path: {path}'
        assert any((PROJECT_ROOT / file).is_relative_to(root) for file in files), (
            f'noxfile.py _BENCHMARK_PATHS names a path with no benchmarks: {path}'
        )


def test_performance_test_session_runs_only_the_benchmark_paths() -> None:
    """The performance-test session passes _BENCHMARK_PATHS to pytest."""
    module = ast.parse(NOXFILE_PATH.read_text(encoding='utf-8'))
    session = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == 'performance_test'
    )
    starred_names = {
        node.value.id
        for node in ast.walk(session)
        if isinstance(node, ast.Starred) and isinstance(node.value, ast.Name)
    }
    assert '_BENCHMARK_PATHS' in starred_names, (
        'performance_test must pass *_BENCHMARK_PATHS to pytest'
    )
