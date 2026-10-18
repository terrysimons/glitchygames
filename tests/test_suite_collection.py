"""Guard against test files that pytest silently never collects.

pytest skips tests without any warning when a directory matches a norecursedirs pattern
(matched against directory *names* at any depth, not paths) or when a file's name does
not match python_files. Both have happened: norecursedirs = ["examples"] once excluded
tests/examples/ for months.
"""

import ast
import fnmatch
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
TESTS_ROOT = PROJECT_ROOT / 'tests'
PYTEST_SETTINGS = tomllib.loads((PROJECT_ROOT / 'pyproject.toml').read_text(encoding='utf-8'))[
    'tool'
]['pytest']['ini_options']
# Files that legitimately hold no collectable tests even though they may define test-like names
NON_TEST_MODULE_NAMES = {'conftest.py', '__init__.py'}


def _defines_tests(python_file: Path) -> bool:
    """Return True if a module defines top-level test functions or Test* classes."""
    module = ast.parse(python_file.read_text(encoding='utf-8'), filename=str(python_file))
    return any(
        (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith('test_')
        )
        or (isinstance(node, ast.ClassDef) and node.name.startswith('Test'))
        for node in module.body
    )


def _test_defining_files() -> list[Path]:
    """Return every Python file under tests/ that defines tests."""
    return sorted(
        python_file
        for python_file in TESTS_ROOT.rglob('*.py')
        if '__pycache__' not in python_file.parts
        and python_file.name not in NON_TEST_MODULE_NAMES
        and _defines_tests(python_file)
    )


def test_no_test_directory_matches_norecursedirs():
    """Every directory holding tests must be one pytest will recurse into."""
    norecursedirs_patterns = PYTEST_SETTINGS.get('norecursedirs', [])
    excluded_test_files = []
    for test_file in _test_defining_files():
        for directory_name in test_file.relative_to(TESTS_ROOT).parent.parts:
            matching_patterns = [
                pattern
                for pattern in norecursedirs_patterns
                if fnmatch.fnmatch(directory_name, pattern)
            ]
            if matching_patterns:
                excluded_test_files.append(
                    f'{test_file.relative_to(PROJECT_ROOT)} '
                    f'(directory {directory_name!r} matches {matching_patterns})',
                )
    assert not excluded_test_files, (
        'Tests excluded by norecursedirs (patterns match directory names at any depth): '
        f'{excluded_test_files}'
    )


def test_every_test_file_matches_python_files():
    """Every file that defines tests must have a name pytest will collect."""
    python_files_patterns = PYTEST_SETTINGS.get('python_files', ['test_*.py', '*_test.py'])
    if isinstance(python_files_patterns, str):
        python_files_patterns = python_files_patterns.split()
    misnamed_test_files = [
        str(test_file.relative_to(PROJECT_ROOT))
        for test_file in _test_defining_files()
        if not any(fnmatch.fnmatch(test_file.name, pattern) for pattern in python_files_patterns)
    ]
    assert not misnamed_test_files, (
        f'Files define tests but are not collected (python_files={python_files_patterns}): '
        f'{misnamed_test_files}'
    )
