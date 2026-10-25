"""Guard against test files that pytest silently never collects.

pytest skips tests without any warning when a directory matches a norecursedirs pattern
(matched against directory *names* at any depth, not paths) or when a file's name does
not match python_files. Both have happened: norecursedirs = ["examples"] once excluded
tests/examples/ for months.
"""

import ast
import fnmatch
import importlib.metadata
import json
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


def _assigned_pygame_constants(python_file: Path) -> list[str]:
    """Return 'line: target' for every assignment to an upper-case pygame attribute.

    Matches `pygame.K_SPACE = ...` and `pygame.locals.K_ESCAPE = ...` (any dotted path under
    `pygame` ending in a constant-style name), including augmented and annotated assignments.
    """
    module = ast.parse(python_file.read_text(encoding='utf-8'), filename=str(python_file))
    assigned_constants = []
    for node in ast.walk(module):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            targets = [node.target]
        else:
            continue
        for target in targets:
            if not isinstance(target, ast.Attribute) or not target.attr.isupper():
                continue
            root = target.value
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id == 'pygame':
                assigned_constants.append(f'{node.lineno}: {ast.unparse(target)}')
    return assigned_constants


def test_no_test_reassigns_pygame_constants():
    """Tests must not overwrite pygame's module-level constants.

    An assignment like `pygame.K_SPACE = 32` outlives the test and changes the constant for
    every later test in the same process. Use the real constant, or `mocker.patch` it so the
    original is restored.
    """
    offending_assignments = [
        f'{python_file.relative_to(PROJECT_ROOT)}:{assignment}'
        for python_file in sorted(TESTS_ROOT.rglob('*.py'))
        if '__pycache__' not in python_file.parts
        for assignment in _assigned_pygame_constants(python_file)
    ]
    assert not offending_assignments, (
        f'Tests reassign pygame constants (use mocker.patch): {offending_assignments}'
    )


def test_the_shared_harness_is_a_plugin_loaded_before_any_other():
    """Every package's tests get the harness: SDL defaults set before anything imports pygame."""
    import conftest as root_conftest

    assert root_conftest.pytest_plugins[0] == 'tests.harness'
    assert not (TESTS_ROOT / 'conftest.py').exists(), 'the harness lives in tests/harness.py'


def test_the_engine_is_imported_from_its_installed_package_never_the_source_tree():
    """The repository root holds no glitchygames/ (src layout, the user's decision 7, 2026-10-25).

    The root conftest.py puts the root on sys.path, so a glitchygames/ there would be imported
    instead of the installed package. nox installs the engine non-editable (site-packages);
    uv sync installs it editable, through a .pth naming src/. Either way the engine imported is
    the one the distribution installed.
    """
    import glitchygames

    project_root = PROJECT_ROOT.resolve()
    assert not (project_root / 'glitchygames').exists(), 'the engine lives in src/glitchygames'
    # The engine is a namespace package (no __init__.py, so no __file__): it is imported from its
    # __path__, where any other glitchygames/ on sys.path would be merged in beside it
    imported_directories = [Path(entry).resolve() for entry in glitchygames.__path__]
    assert len(imported_directories) == 1, imported_directories
    imported_from = imported_directories[0]
    distribution = importlib.metadata.distribution('glitchygames')
    direct_url = json.loads(distribution.read_text('direct_url.json') or '{}')
    if direct_url.get('dir_info', {}).get('editable', False):
        assert imported_from == project_root / 'src' / 'glitchygames'
    else:
        assert imported_from == Path(str(distribution.locate_file('glitchygames'))).resolve()
