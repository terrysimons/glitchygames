"""Every benchmark lives where ``nox -s performance-test`` looks for benchmarks.

The session collects only ``_BENCHMARK_PATHS`` (noxfile.py), so a test that takes pytest-benchmark's
``benchmark`` fixture anywhere else would silently stop being measured.
"""

from __future__ import annotations

import ast
import functools
import tomllib
from pathlib import Path

from tests.child_scans import scan_in_child

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOXFILE_PATH = PROJECT_ROOT / 'noxfile.py'


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


def benchmark_test_file_names(*, project_root: str) -> list[str]:
    """Return every test module, under pytest's testpaths, with a test taking ``benchmark``.

    It parses every test module: run it in a child process (tests/child_scans.py), so the syntax
    trees never pin this process's memory. It takes and returns JSON.

    Args:
        project_root: The repository, whose pyproject.toml names pytest's testpaths.

    Returns:
        The modules' paths, relative to the repository root (POSIX spelling), sorted.

    """
    root = Path(project_root)
    testpaths = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))['tool'][
        'pytest'
    ]['ini_options']['testpaths']
    files: set[str] = set()
    for testpath in testpaths:
        for path in (root / testpath).rglob('test_*.py'):
            module = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(module):
                if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    continue
                arguments = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
                if node.name.startswith('test_') and any(
                    argument.arg == 'benchmark' for argument in arguments
                ):
                    files.add(path.relative_to(root).as_posix())
    return sorted(files)


@functools.cache
def benchmark_test_files() -> set[Path]:
    """Return the repository's test modules with a benchmark, scanned once in a child process.

    Returns:
        The modules' paths, relative to the repository root.

    """
    names = scan_in_child(
        scan=benchmark_test_file_names, arguments={'project_root': str(PROJECT_ROOT)}
    )
    return {Path(name) for name in names}


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


def test_the_benchmark_scan_finds_the_same_files_in_a_child_process(tmp_path) -> None:
    """No finding is lost in the child: the scan answers there what it answers here."""
    (tmp_path / 'pyproject.toml').write_text(
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n', encoding='utf-8'
    )
    (tmp_path / 'tests' / 'speed').mkdir(parents=True)
    (tmp_path / 'tests' / 'speed' / 'test_fast.py').write_text(
        'def test_fast(benchmark):\n    benchmark(int)\n', encoding='utf-8'
    )
    (tmp_path / 'tests' / 'test_plain.py').write_text(
        'def test_plain():\n    pass\n\ndef helper(benchmark):\n    pass\n', encoding='utf-8'
    )
    arguments = {'project_root': str(tmp_path)}

    in_this_process = benchmark_test_file_names(**arguments)

    assert scan_in_child(scan=benchmark_test_file_names, arguments=arguments) == in_this_process
    assert in_this_process == ['tests/speed/test_fast.py']
