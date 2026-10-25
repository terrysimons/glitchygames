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

from tests.harness import CHECKOUT_ENGINE_DIRECTORY, imported_engine_directory

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


def collected_test_roots(*, project_root: Path = PROJECT_ROOT) -> list[Path]:
    """Return every directory of tests pytest collects: tests/, then each workspace member's.

    Args:
        project_root: The repository (its pyproject.toml names the members).

    Returns:
        The test roots.

    """
    from scripts.workspace_packages import workspace_members

    return [
        project_root / 'tests',
        *(member.tests_directory for member in workspace_members(project_root=project_root)),
    ]


def _python_files(*, roots: list[Path]) -> list[tuple[Path, Path]]:
    """Return every Python file below the roots (no __pycache__), each with its root, sorted."""
    return sorted(
        (root, python_file)
        for root in roots
        for python_file in root.rglob('*.py')
        if '__pycache__' not in python_file.parts
    )


def _test_defining_files(*, roots: list[Path]) -> list[tuple[Path, Path]]:
    """Return every Python file below the roots that defines tests, each with its root."""
    return [
        (root, python_file)
        for root, python_file in _python_files(roots=roots)
        if python_file.name not in NON_TEST_MODULE_NAMES and _defines_tests(python_file)
    ]


def norecursedirs_exclusions(
    *, project_root: Path, roots: list[Path], patterns: list[str]
) -> list[str]:
    """Return each test file below the roots in a directory a norecursedirs pattern matches.

    Args:
        project_root: What the reported paths are relative to.
        roots: The test roots.
        patterns: pytest's norecursedirs (matched against directory names at any depth).

    Returns:
        ``<file> (directory '<name>' matches [<patterns>])`` for each excluded file.

    """
    excluded_test_files = []
    for root, test_file in _test_defining_files(roots=roots):
        for directory_name in test_file.relative_to(root).parent.parts:
            matching_patterns = [
                pattern for pattern in patterns if fnmatch.fnmatch(directory_name, pattern)
            ]
            if matching_patterns:
                excluded_test_files.append(
                    f'{test_file.relative_to(project_root)} '
                    f'(directory {directory_name!r} matches {matching_patterns})',
                )
    return excluded_test_files


def misnamed_test_files(*, project_root: Path, roots: list[Path], patterns: list[str]) -> list[str]:
    """Return each file below the roots that defines tests but matches no python_files pattern.

    Args:
        project_root: What the reported paths are relative to.
        roots: The test roots.
        patterns: pytest's python_files.

    Returns:
        The misnamed files.

    """
    return [
        str(test_file.relative_to(project_root))
        for _root, test_file in _test_defining_files(roots=roots)
        if not any(fnmatch.fnmatch(test_file.name, pattern) for pattern in patterns)
    ]


def test_no_test_directory_matches_norecursedirs():
    """Every directory holding tests (tests/ and every member's) is one pytest recurses into."""
    excluded_test_files = norecursedirs_exclusions(
        project_root=PROJECT_ROOT,
        roots=collected_test_roots(),
        patterns=PYTEST_SETTINGS.get('norecursedirs', []),
    )
    assert not excluded_test_files, (
        'Tests excluded by norecursedirs (patterns match directory names at any depth): '
        f'{excluded_test_files}'
    )


def _python_files_patterns() -> list[str]:
    """Return pytest's python_files setting as a list."""
    python_files_patterns = PYTEST_SETTINGS.get('python_files', ['test_*.py', '*_test.py'])
    if isinstance(python_files_patterns, str):
        python_files_patterns = python_files_patterns.split()
    return python_files_patterns


def test_every_test_file_matches_python_files():
    """Every file that defines tests (tests/ and every member's) has a name pytest collects."""
    python_files_patterns = _python_files_patterns()
    misnamed = misnamed_test_files(
        project_root=PROJECT_ROOT, roots=collected_test_roots(), patterns=python_files_patterns
    )
    assert not misnamed, (
        f'Files define tests but are not collected (python_files={python_files_patterns}): '
        f'{misnamed}'
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


def pygame_constant_reassignments(*, project_root: Path, roots: list[Path]) -> list[str]:
    """Return ``<file>:<line>: <target>`` for each pygame constant assigned below the roots.

    Args:
        project_root: What the reported paths are relative to.
        roots: The test roots.

    Returns:
        The assignments.

    """
    return [
        f'{python_file.relative_to(project_root)}:{assignment}'
        for _root, python_file in _python_files(roots=roots)
        for assignment in _assigned_pygame_constants(python_file)
    ]


def test_no_test_reassigns_pygame_constants():
    """Tests (tests/ and every member's) must not overwrite pygame's module-level constants.

    An assignment like `pygame.K_SPACE = 32` outlives the test and changes the constant for
    every later test in the same process. Use the real constant, or `mocker.patch` it so the
    original is restored.
    """
    offending_assignments = pygame_constant_reassignments(
        project_root=PROJECT_ROOT, roots=collected_test_roots()
    )
    assert not offending_assignments, (
        f'Tests reassign pygame constants (use mocker.patch): {offending_assignments}'
    )


def test_the_test_roots_are_the_engines_and_every_members():
    """The guards above scan the member's tests too (src/games/mr-muncher/tests)."""
    roots = [root.relative_to(PROJECT_ROOT).as_posix() for root in collected_test_roots()]

    assert roots[0] == 'tests'
    assert 'src/games/mr-muncher/tests' in roots


MEMBER_TESTS = Path('src') / 'games' / 'space-game' / 'tests'


def write_member_test_root(*, project_root: Path) -> list[Path]:
    """Write a repository whose one member, src/games/space-game, holds a good test file.

    Returns:
        Its test roots (from the workspace, as the guards read them).

    """
    (project_root / 'pyproject.toml').write_text(
        '[tool.uv.workspace]\nmembers = ["src/games/space-game"]\n', encoding='utf-8'
    )
    member = project_root / 'src' / 'games' / 'space-game'
    (member / 'space_game').mkdir(parents=True)
    (member / 'pyproject.toml').write_text(
        '[project]\nname = "space-game"\n\n'
        '[tool.hatch.build.targets.wheel]\npackages = ["space_game"]\n',
        encoding='utf-8',
    )
    (project_root / 'tests').mkdir()
    (member / 'tests').mkdir()
    (member / 'tests' / 'test_space_game.py').write_text(
        'def test_flies():\n    assert True\n', encoding='utf-8'
    )
    return collected_test_roots(project_root=project_root)


def test_a_misnamed_member_test_file_is_found(tmp_path):
    """A member's test file pytest would never collect is reported."""
    roots = write_member_test_root(project_root=tmp_path)
    misnamed = tmp_path / MEMBER_TESTS / 'space_game_helpers_test_cases.py'
    misnamed.write_text('def test_lands():\n    assert True\n', encoding='utf-8')

    assert misnamed_test_files(
        project_root=tmp_path, roots=roots, patterns=_python_files_patterns()
    ) == [(MEMBER_TESTS / misnamed.name).as_posix()]


def test_a_member_test_in_a_norecursedirs_directory_is_found(tmp_path):
    """A member's test file in a directory norecursedirs matches is reported."""
    roots = write_member_test_root(project_root=tmp_path)
    (tmp_path / MEMBER_TESTS / 'build').mkdir()
    (tmp_path / MEMBER_TESTS / 'build' / 'test_built.py').write_text(
        'def test_built():\n    assert True\n', encoding='utf-8'
    )

    excluded = norecursedirs_exclusions(
        project_root=tmp_path, roots=roots, patterns=PYTEST_SETTINGS['norecursedirs']
    )

    expected = (
        f'{(MEMBER_TESTS / "build" / "test_built.py").as_posix()} '
        "(directory 'build' matches ['build'])"
    )
    assert excluded == [expected]


def test_a_member_test_reassigning_a_pygame_constant_is_found(tmp_path):
    """A member's test that overwrites pygame.K_SPACE is reported."""
    roots = write_member_test_root(project_root=tmp_path)
    (tmp_path / MEMBER_TESTS / 'test_space_game.py').write_text(
        'import pygame\n\n\ndef test_flies():\n    pygame.K_SPACE = 32\n', encoding='utf-8'
    )

    assert pygame_constant_reassignments(project_root=tmp_path, roots=roots) == [
        f'{(MEMBER_TESTS / "test_space_game.py").as_posix()}:5: pygame.K_SPACE'
    ]


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
    project_root = PROJECT_ROOT.resolve()
    assert not (project_root / 'glitchygames').exists(), 'the engine lives in src/glitchygames'
    imported_from = imported_engine_directory()
    distribution = importlib.metadata.distribution('glitchygames')
    direct_url = json.loads(distribution.read_text('direct_url.json') or '{}')
    if direct_url.get('dir_info', {}).get('editable', False):
        assert imported_from == CHECKOUT_ENGINE_DIRECTORY
    else:
        assert imported_from == Path(str(distribution.locate_file('glitchygames'))).resolve()


def test_every_member_packages_tests_are_collected(pytestconfig):
    """A member's tests directory is in testpaths and its test files are importable by name."""
    from scripts.workspace_packages import workspace_members

    testpaths = pytestconfig.getini('testpaths')
    for member in workspace_members(project_root=PROJECT_ROOT):
        relative = member.tests_directory.relative_to(PROJECT_ROOT).as_posix()
        assert relative in testpaths, f'{relative} is not collected'
        assert not (member.tests_directory / '__init__.py').exists(), (
            f'{relative} must not be a package named "tests" (it would shadow tests/)'
        )


def test_test_file_names_are_unique_across_packages():
    """Member tests are not packages, so pytest imports them by file name: names must differ."""
    names = [path.name for root in collected_test_roots() for path in root.rglob('test_*.py')]

    assert len(names) == len(set(names))
