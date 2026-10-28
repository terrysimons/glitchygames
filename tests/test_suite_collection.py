"""Guard against test files that pytest silently never collects.

pytest skips tests without any warning when a directory matches a norecursedirs pattern
(matched against directory *names* at any depth, not paths) or when a file's name does
not match python_files. Both have happened: norecursedirs = ["examples"] once excluded
the engine's examples tests (tests/examples/, deleted since) for months.
"""

import ast
import fnmatch
import importlib.metadata
import importlib.util
import json
import re
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

from scripts.git_checkout import run_git
from scripts.workspace_packages import WorkspaceMember, workspace_members

from tests.ast_scanning import (
    import_bindings,
    imported_module_names,
    member_imports,
    module_name_of,
    path_to_package,
    pytest_plugin_names,
    qualified_name,
)
from tests.harness import CHECKOUT_ENGINE_DIRECTORY, imported_engine_directory
from tests.workspace_sources import member_import_packages

if TYPE_CHECKING:
    from collections.abc import Sequence

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
                    f'{test_file.relative_to(project_root).as_posix()} '
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
        test_file.relative_to(project_root).as_posix()
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
        f'{python_file.relative_to(project_root).as_posix()}:{assignment}'
        for _root, python_file in _python_files(roots=roots)
        for assignment in _assigned_pygame_constants(python_file)
    ]


# pytest fixtures that warn under junit_family 'xunit2' (the JUnit reports pyproject.toml and nox
# write): the suite turns warnings into errors, but only when the warning is raised, which with
# xdist workers it is not, so a local `-n auto` run passes and CI's `-n 0` run errors
JUNIT_XUNIT2_INCOMPATIBLE_FIXTURES = frozenset({'record_property', 'record_xml_attribute'})


def junit_incompatible_fixture_uses(*, project_root: Path, roots: list[Path]) -> list[str]:
    """Return ``<file>:<line>: <name>`` for each function taking an xunit2-incompatible fixture.

    Args:
        project_root: What the reported paths are relative to.
        roots: The test roots.

    Returns:
        The uses.

    """
    uses = []
    for _root, python_file in _python_files(roots=roots):
        tree = ast.parse(python_file.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
            uses.extend(
                f'{python_file.relative_to(project_root).as_posix()}:{node.lineno}: {argument.arg}'
                for argument in arguments
                if argument.arg in JUNIT_XUNIT2_INCOMPATIBLE_FIXTURES
            )
    return uses


def test_no_test_uses_a_fixture_the_junit_report_rejects():
    """Tests (tests/ and every member's) must not take record_property or record_xml_attribute.

    Both warn under the xunit2 JUnit report, which becomes an error in CI's serial run only.
    Put what a failure needs into the assertion's message instead.
    """
    uses = junit_incompatible_fixture_uses(project_root=PROJECT_ROOT, roots=collected_test_roots())
    assert not uses, f'Tests take fixtures the xunit2 JUnit report rejects: {uses}'


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


def test_the_shared_harness_is_a_plugin_loaded_before_any_other(pytestconfig):
    """Every package's tests get the harness: SDL defaults set before anything imports pygame.

    The root conftest is looked up as pytest registered it, by its path: ``import conftest``
    finds whichever conftest pytest imported last under that bare name, and a member's
    tests/conftest.py (not in a package: Drawing Fire's) is one.
    """
    # pytest registers a conftest under its path built from the rootdir (not resolved: through
    # a symlinked checkout the two differ)
    root_conftest = pytestconfig.pluginmanager.get_plugin(
        str(pytestconfig.rootpath / 'conftest.py')
    )

    assert root_conftest is not None, 'the root conftest.py is not a registered plugin'
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


def test_tests_are_imported_by_their_paths(pytestconfig):
    """No test module is imported under its bare file name, so no two can collide (D15 item 5).

    pytest's importlib import mode names each test module (and conftest.py) after its path
    from the repository root, in every environment: namespace packages are not considered, as
    with them the name would follow sys.path, which an editable install changes. The root is on
    the path, so a member's helper is imported by the same path
    (``src.apps.bitmappy.tests.film_strip_support``). Two members may then hold test files or
    helpers of the same name (BUGS.md #224 item 31: the user, 2026-10-27, "we can't really
    control what a game calls its files"). This module's own name is pinned here; a member's
    is pinned by Bitmappy's ``test_bitmappy_test_module_names.py``.
    """
    assert pytestconfig.option.importmode == 'importlib'
    assert pytestconfig.getini('consider_namespace_packages') is False
    assert [Path(path) for path in pytestconfig.getini('pythonpath')] == [PROJECT_ROOT]
    assert __name__ == 'tests.test_suite_collection'


def bare_name_imports(*, members: Sequence[WorkspaceMember]) -> list[str]:
    """Return each import in a member's tests of one of its test modules by a bare name.

    Nothing puts a test directory on the path (importlib mode), so ``import film_support``
    from a member's tests finds no module of its own, or, worse, an installed one of that name:
    the one thing the import mode cannot make work. A test imports a helper by its qualified
    path from the repository root instead. Test-data directories (``fixtures``) are not scanned.

    Args:
        members: The workspace's members.

    Returns:
        ``<distribution>: tests/<file>:<line> imports <name>`` for each, in the members' order.

    """
    found: list[str] = []
    for member in members:
        python_files = sorted(
            python_file
            for python_file in member.tests_directory.rglob('*.py')
            if not TEST_DATA_DIRECTORY_NAMES
            & set(python_file.relative_to(member.tests_directory).parts)
        )
        # A test subdirectory counts only when it holds modules and its name is no module an
        # import finds (a tests/pygame/ never makes `import pygame` a bare-name import)
        local_names = {python_file.stem for python_file in python_files} | {
            python_file.parent.name
            for python_file in python_files
            if python_file.parent != member.tests_directory
            # A name that is no identifier (v1.2) is never imported by a bare name, and
            # find_spec would try its dotted parent
            and python_file.parent.name.isidentifier()
            and importlib.util.find_spec(python_file.parent.name) is None
        }
        for python_file in python_files:
            tree = ast.parse(python_file.read_text(encoding='utf-8'), filename=str(python_file))
            relative = python_file.relative_to(member.tests_directory).as_posix()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module]
                else:
                    continue
                found.extend(
                    f'{member.distribution}: tests/{relative}:{node.lineno} imports {name}'
                    for name in names
                    if name.partition('.')[0] in local_names
                )
    return found


def test_no_member_test_imports_a_module_by_a_bare_name():
    """A member's helpers are imported by their qualified paths (src.<layer>.<member>.tests)."""
    assert bare_name_imports(members=MEMBERS) == []


def test_a_bare_name_import_of_a_members_test_module_is_found(tmp_path):
    """Imports of a sibling module or package by bare name are found; qualified ones are not."""
    roots = write_member_test_root(project_root=tmp_path)
    assert roots
    tests_directory = tmp_path / MEMBER_TESTS
    (tests_directory / 'ship_support.py').write_text('SPEED = 3\n', encoding='utf-8')
    (tests_directory / 'fleet').mkdir()
    (tests_directory / 'fleet' / 'test_space_game_fleet.py').write_text(
        'import os\n'
        'import ship_support\n'
        'from fleet import formations\n'
        'from src.games.space_game.tests.ship_support import SPEED\n'
        'from . import ship_support as relative_support\n',
        encoding='utf-8',
    )
    (tests_directory / 'fixtures').mkdir()
    (tests_directory / 'fixtures' / 'data.py').write_text('import ship_support\n', encoding='utf-8')
    # A test directory named like an installed package does not make its imports bare-name ones
    (tests_directory / 'pygame').mkdir()
    (tests_directory / 'pygame' / 'test_space_game_pygame.py').write_text(
        'import pygame\n', encoding='utf-8'
    )
    # Nor does one whose name is no identifier (find_spec would import its dotted parent)
    (tests_directory / 'v1.2').mkdir()
    (tests_directory / 'v1.2' / 'test_space_game_versions.py').write_text('', encoding='utf-8')
    # Nor does a directory holding no module
    (tests_directory / 'art').mkdir()
    (tests_directory / 'fleet' / 'test_space_game_art.py').write_text(
        'import art\n', encoding='utf-8'
    )
    member = WorkspaceMember(
        directory=tmp_path / 'src' / 'games' / 'space-game',
        distribution='space-game',
        import_packages=('space_game',),
        console_scripts=(),
    )

    assert bare_name_imports(members=[member]) == [
        'space-game: tests/fleet/test_space_game_fleet.py:2 imports ship_support',
        'space-game: tests/fleet/test_space_game_fleet.py:3 imports fleet',
    ]


# Living documentation writes repository paths from the repository root (the engine at
# src/glitchygames/, the workspace layers at src/games/, src/demos/ and src/apps/). Finished
# plans (plans/*.md except the ones below) and resolved BUGS.md entries are history: they name
# the locations as they were when written, so they are not scanned (TEST_UPDATE_PLAN.md says
# "complete (historical)" and is among them).
LIVING_PLAN_FILES = (
    'plans/future-features.md',
    'plans/future-work.md',
    'plans/2026-10-23-arcade-showcase.md',
    'plans/2026-10-24-workspace-packages.md',
    'plans/2026-10-25-engine-context.md',
)
# An engine path not written from the repository root: `glitchygames/<something>` right after
# something that makes it part of a longer path or name (a word, '.', '/', '-', '~') is not one,
# which leaves out `src/glitchygames/`, `site-packages/glitchygames/`, URLs, `dev.glitchygames/`
# and the dotted module name `glitchygames.engine`. A bare `glitchygames/` names the package
# directory (a wheel's top level, an archive listing), not a path from the root, so it needs a
# name after the slash. There is no check that the file exists: a planned engine file is under
# src/ too, and a deleted file's stale reference must not go quiet.
ENGINE_PATH_WITHOUT_ROOT = re.compile(r'(?<![\w./~-])glitchygames/(?P<rest>[\w<][\w./<>-]*)')
# `src/examples` (there is no examples layer), and, in backticks, a layer directory written from
# the root without `src/` (`games/<game>/tests`; `examples/...` too: the examples are games and
# demos). Relative links (`games/paddleslap.md`, a docs page), `tests/examples/` and
# `src/glitchygames/examples/` (their slash follows another name) and prose such as "games/demos"
# (no backtick) are not claims about the root.
STALE_LAYER_PATH = re.compile(
    r'src/examples\b|(?<=`)(?:games|demos|apps|examples)/(?![\w./<>-]*\.md\b)(?=[\w<])'
)
# A fence opens with three or more backticks or tildes and closes with the same marker
FENCE_LINE = re.compile(r'^\s*(?P<marker>`{3,}|~{3,})')


def _is_generated_api_stub(*, text: str) -> bool:
    """Return True for a mkdocstrings stub: only `::: module` directives and their options."""
    lines = [line for line in text.splitlines() if line.strip()]
    return all(line.startswith((':::', ' ')) for line in lines)


def _active_bug_lines(*, text: str) -> list[tuple[int, str]]:
    """Return the (line number, line) pairs of every BUGS.md entry whose Status is not resolved."""
    entries: list[list[tuple[int, str]]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.startswith(('## ', '### ')):
            entries.append([])
        if entries:
            entries[-1].append((line_number, line))
    active: list[tuple[int, str]] = []
    for entry in entries:
        statuses = [line for _, line in entry if line.startswith('- **Status**:')]
        if statuses and not statuses[0].removeprefix('- **Status**:').strip().startswith((
            'Resolved',
            'Fixed',
            'Closed',
        )):
            active.extend(entry)
    return active


def living_documentation_lines(*, project_root: Path = PROJECT_ROOT) -> list[tuple[str, int, str]]:
    """Return (file, line number, line) for every line of the living documentation.

    Args:
        project_root: The repository.

    Returns:
        The lines of CLAUDE.md, README.md, the root README and architecture files, docs/ (but
        not generated API stubs or the generated docs/quality/graphs and docs/quality/metrics,
        which are gitignored), the living plans and BUGS.md's active entries.

    """
    paths = [
        *(project_root / name for name in ('CLAUDE.md', 'README.md', 'BITMAPPY_ARCHITECTURE.md')),
        *sorted(project_root.glob('*_README.md')),
        *(project_root / name for name in LIVING_PLAN_FILES),
        *(
            path
            for path in sorted((project_root / 'docs').rglob('*.md'))
            if not path.is_relative_to(project_root / 'docs' / 'quality' / 'graphs')
            and not path.is_relative_to(project_root / 'docs' / 'quality' / 'metrics')
        ),
    ]
    lines: list[tuple[str, int, str]] = []
    for path in paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding='utf-8')
        if _is_generated_api_stub(text=text):
            continue
        relative = path.relative_to(project_root).as_posix()
        lines.extend(
            (relative, line_number, line)
            for line_number, line in enumerate(text.splitlines(), start=1)
        )
    bugs = project_root / 'BUGS.md'
    if bugs.is_file():
        lines.extend(
            ('BUGS.md', line_number, line)
            for line_number, line in _active_bug_lines(text=bugs.read_text(encoding='utf-8'))
        )
    return lines


def _scan_units(*, project_root: Path) -> list[tuple[str, list[tuple[int, str]]]]:
    """Return (file, lines) units whose fenced-code state is independent of each other.

    A file is one unit; each active BUGS.md entry is its own unit, because only those entries'
    lines are scanned and an unclosed fence in one must not carry into the next.
    """
    units: dict[tuple[str, int], list[tuple[int, str]]] = {}
    previous_line_number = 0
    unit_number = 0
    for relative, line_number, line in living_documentation_lines(project_root=project_root):
        if relative == 'BUGS.md' and (
            line.startswith(('## ', '### ')) or line_number != previous_line_number + 1
        ):
            unit_number += 1
        previous_line_number = line_number if relative == 'BUGS.md' else 0
        units.setdefault((relative, unit_number if relative == 'BUGS.md' else 0), []).append((
            line_number,
            line,
        ))
    return [(relative, lines) for (relative, _), lines in units.items()]


def paths_without_the_source_root(*, project_root: Path = PROJECT_ROOT) -> list[str]:
    """Return 'file:line: text' for each living-documentation path that predates src/."""
    problems: list[str] = []
    for relative, lines in _scan_units(project_root=project_root):
        fence_marker: str | None = None
        previous_is_tree = False
        for line_number, line in lines:
            fence = FENCE_LINE.match(line)
            if fence is not None:
                marker = fence.group('marker')
                if fence_marker is None:
                    fence_marker = marker
                elif marker[0] == fence_marker[0] and len(marker) >= len(fence_marker):
                    fence_marker = None
                previous_is_tree = False
                continue
            if not line.strip():
                continue
            # In a fenced layout tree an indented entry is a child of the tree line above it
            # (`  glitchygames/` under `src/`), not a path from the repository root. A tree line
            # starts with a name ending in a slash; an entry follows a tree line or an entry. A
            # command's continuation (`uv run pytest \\` then an indented path) follows neither.
            indentation = len(line) - len(line.lstrip())
            is_tree_entry = (
                fence_marker is not None
                and indentation > 0
                and previous_is_tree
                and ENGINE_PATH_WITHOUT_ROOT.match(line.lstrip(), 0) is not None
            )
            if fence_marker is not None:
                previous_is_tree = line.split()[0].endswith('/') or (
                    indentation > 0 and previous_is_tree
                )
            stale = [
                match.group(0)
                for match in ENGINE_PATH_WITHOUT_ROOT.finditer(line)
                if not (is_tree_entry and match.start() == indentation)
            ]
            stale.extend(match.group(0) for match in STALE_LAYER_PATH.finditer(line))
            problems.extend(f'{relative}:{line_number}: {text}' for text in stale)
    return problems


def test_living_documentation_writes_repository_paths_from_the_repository_root():
    """No living document names the engine as glitchygames/..., or a layer that does not exist.

    The engine is src/glitchygames/ (#105); games, demos and apps are src/games/, src/demos/ and
    src/apps/ (no examples layer, nothing at the root). History (finished plans, resolved bugs)
    keeps the paths it was written with.
    """
    assert paths_without_the_source_root() == []


def _guard_findings(*, tmp_path: Path, claude_text: str, bugs_text: str = '') -> list[str]:
    """Return the guard's findings for a repository whose CLAUDE.md and BUGS.md have this text."""
    engine = tmp_path / 'src' / 'glitchygames'
    engine.mkdir(parents=True, exist_ok=True)
    (tmp_path / 'CLAUDE.md').write_text(claude_text, encoding='utf-8')
    if bugs_text:
        (tmp_path / 'BUGS.md').write_text(bugs_text, encoding='utf-8')
    return paths_without_the_source_root(project_root=tmp_path)


def test_the_path_guard_finds_stale_paths_and_leaves_names_and_urls_alone(tmp_path):
    """The guard names stale paths, and leaves dotted names, URLs, cache names and history alone."""
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'docs' / 'stub.md').write_text(
        '::: glitchygames.ui\n    options:\n', encoding='utf-8'
    )

    assert _guard_findings(
        tmp_path=tmp_path,
        claude_text=(
            'See `glitchygames/ui/` and glitchygames/ui/x.py.\n'
            'See `src/glitchygames/ui/`, glitchygames.ui, site-packages/glitchygames/ui.\n'
            'https://github.com/terrysimons/glitchygames/ui and `glitchygames/arcade/` planned.\n'
            'The ~/.glitchygames/cache, glitchygames-wasm and src/examples/x, `apps/y`.\n'
            'Plain games/ prose, src/games/muncher and docs/games/x.md are fine.'
        ),
        bugs_text=(
            '## Active Bugs\n### 1. A\n- **Status**: Active\nglitchygames/ui/y.py\n'
            '## Resolved Bugs\n### 2. B\n- **Status**: Resolved\nglitchygames/ui/z.py\n'
        ),
    ) == [
        'CLAUDE.md:1: glitchygames/ui/',
        'CLAUDE.md:1: glitchygames/ui/x.py.',
        'CLAUDE.md:3: glitchygames/arcade/',
        'CLAUDE.md:4: src/examples',
        'CLAUDE.md:4: apps/',
        'BUGS.md:4: glitchygames/ui/y.py',
    ]


def test_the_path_guard_leaves_a_bare_package_directory_name_alone(tmp_path):
    """`glitchygames/` with nothing after it names the package (a wheel, a listing), not a path."""
    assert (
        _guard_findings(
            tmp_path=tmp_path,
            claude_text=(
                'The wheel holds glitchygames/ at the top, `glitchygames/`, glitchygames/*.py.'
            ),
        )
        == []
    )


def test_the_path_guard_flags_only_a_root_level_layer_path_claim(tmp_path):
    """Relative links, prose pairs and docs-relative paths are not claims about the root."""
    assert _guard_findings(
        tmp_path=tmp_path,
        claude_text=(
            'See [a](games/paddleslap.md) and [b](demos/x.md), games/demos, games/<game>/tests.\n'
            '`games/paddleslap.md`, src/games/x, tests/examples/x.py,'
            ' `src/glitchygames/examples/`.\n'
            'Stale: `examples/resources/x.toml`, `demos/dt/`, `games/<game>/tests`.'
        ),
    ) == [
        'CLAUDE.md:3: examples/',
        'CLAUDE.md:3: demos/',
        'CLAUDE.md:3: games/',
    ]


def test_the_path_guard_exempts_only_fenced_tree_entries(tmp_path):
    """A tree's indented entry sits under its parent; a command's continuation does not."""
    fence = '```'
    tree_text = [
        fence,
        'src/',
        '  glitchygames/    the engine',
        '    ui/',
        '  games/',
        fence,
        '~~~~',
        'uv run pytest \\',
        '    glitchygames/ui/x.py',
        fence,
        'inside a four-marker fence',
        fence,
        '    glitchygames/ui/y.py',
        '~~~~',
        'glitchygames/ui/after.py',
    ]
    assert _guard_findings(
        tmp_path=tmp_path,
        claude_text='\n'.join(tree_text),
    ) == [
        'CLAUDE.md:9: glitchygames/ui/x.py',
        'CLAUDE.md:13: glitchygames/ui/y.py',
        'CLAUDE.md:15: glitchygames/ui/after.py',
    ]


def test_an_unclosed_fence_in_one_bug_entry_does_not_hide_the_next(tmp_path):
    """BUGS.md scans only active entries, so fence state starts afresh in each of them."""
    assert _guard_findings(
        tmp_path=tmp_path,
        claude_text='',
        bugs_text=(
            '### 1. A\n- **Status**: Active\n```\nsrc/\n'
            '### 2. Resolved\n- **Status**: Resolved\n```\n'
            '### 3. B\n- **Status**: Active\n  glitchygames/ui/y.py\n'
        ),
    ) == ['BUGS.md:10: glitchygames/ui/y.py']


MEMBERS = workspace_members(project_root=PROJECT_ROOT)
# Why the per-game world rules of tests/world/test_golden_traces.py may import these internals
GOLDEN_TRACE_WORLD_RULES_REASON = (
    'the per-game world rules (TestWorldRules, the EXPECTED_DIFFERENCES rule helpers and the '
    "*_OLD_FALL_POSES constants) measure the games' own drawings and players (the user, "
    '2026-10-26, narrowed by the controller to these names)'
)
# The root test modules that may import any member, each with its reason and decision date
MEMBER_IMPORT_EXEMPT_MODULES: dict[str, str] = {
    'tests/replay/golden_replay_controls.py': (
        "the golden replays' per-game control tables, cross-member infrastructure moved here "
        'unchanged from tests/replay/test_golden_replays.py, which stays guarded (the '
        'controller, 2026-10-26)'
    ),
}
# The only named imports of a member a root test module may make: (module, imported name) ->
# reason. Matched by module and name, so an alias (`Player as AdventurerPlayer`) changes nothing.
MEMBER_IMPORT_EXEMPT_NAMES: dict[str, dict[tuple[str, str], str]] = {
    'tests/world/test_golden_traces.py': {
        ('brave_adventurer', 'constants'): GOLDEN_TRACE_WORLD_RULES_REASON,
        ('brave_adventurer.drawing', 'draw_player'): GOLDEN_TRACE_WORLD_RULES_REASON,
        ('brave_adventurer.drawing', 'draw_scarab'): GOLDEN_TRACE_WORLD_RULES_REASON,
        ('brave_adventurer.player', 'Player'): GOLDEN_TRACE_WORLD_RULES_REASON,
        ('brave_adventurer_core', 'constants'): GOLDEN_TRACE_WORLD_RULES_REASON,
        ('brave_adventurer_papyrus.player', 'PapyrusPlayer'): GOLDEN_TRACE_WORLD_RULES_REASON,
        (
            'brave_adventurer_papyrus.sprite_utils',
            'apply_transparency_and_scale',
        ): GOLDEN_TRACE_WORLD_RULES_REASON,
        ('clockwork_keep.constants', 'PLAYER_HEIGHT'): GOLDEN_TRACE_WORLD_RULES_REASON,
        ('clockwork_keep.constants', 'PLAYER_WIDTH'): GOLDEN_TRACE_WORLD_RULES_REASON,
        ('clockwork_keep.drawing', 'draw_tinker'): GOLDEN_TRACE_WORLD_RULES_REASON,
        ('clockwork_keep.player', 'Tinker'): GOLDEN_TRACE_WORLD_RULES_REASON,
    },
}


def _root_test_modules(*, project_root: Path) -> list[tuple[str, ast.Module]]:
    """Return each Python file under the root tests/ (no __pycache__), keyed by its path, parsed."""
    return [
        (
            python_file.relative_to(project_root).as_posix(),
            ast.parse(python_file.read_text(encoding='utf-8'), filename=str(python_file)),
        )
        for python_file in sorted((project_root / 'tests').rglob('*.py'))
        if '__pycache__' not in python_file.parts
    ]


def engine_test_imports_of_members(
    *, project_root: Path, members: Sequence[WorkspaceMember]
) -> list[str]:
    """Return every import of a member package by a file under the root tests/.

    The engine's tests test the engine: a game, demo or app is tested in its member, and an
    engine test that needs a game writes a stand-in (decision 7, the user, 2026-10-26). Every
    file under tests/ is scanned, helpers too, and every import in it, at any level. Only
    ``MEMBER_IMPORT_EXEMPT_MODULES`` and ``MEMBER_IMPORT_EXEMPT_NAMES`` are exempt.

    The tools in scripts/ are out of scope: they are not tests. ``scripts/record_golden_traces.py``
    and ``scripts/golden_inputs.py`` are what root tests import of our games' scripts, and they
    load no game when imported (only when a game runs).

    Args:
        project_root: The repository (its tests/ directory is scanned).
        members: The workspace's members.

    Returns:
        ``<file>:<line>: <import>`` for each import that is not exempt, sorted by file and line.

    """
    member_packages = member_import_packages(members=members)
    findings: list[str] = []
    for relative, tree in _root_test_modules(project_root=project_root):
        if relative in MEMBER_IMPORT_EXEMPT_MODULES:
            continue
        exempt_names = MEMBER_IMPORT_EXEMPT_NAMES.get(relative, {})
        findings.extend(
            f'{relative}:{found.line}: {found.describe()}'
            for found in member_imports(tree=tree, member_packages=member_packages)
            if found.name is None or (found.module, found.name) not in exempt_names
        )
    return findings


def stale_member_import_exemptions(
    *, project_root: Path, members: Sequence[WorkspaceMember]
) -> list[str]:
    """Return each member-import exemption that no longer applies, so the lists can't rot.

    Args:
        project_root: The repository.
        members: The workspace's members.

    Returns:
        ``<file>: <why the exemption is stale>`` for each, in the lists' order.

    """
    member_packages = member_import_packages(members=members)
    stale: list[str] = []
    for relative in MEMBER_IMPORT_EXEMPT_MODULES:
        path = project_root / relative
        if not path.is_file():
            stale.append(f'{relative}: no such file')
        elif not member_imports(
            tree=ast.parse(path.read_text(encoding='utf-8')), member_packages=member_packages
        ):
            stale.append(f'{relative}: imports no member')
    for relative, exempt_names in MEMBER_IMPORT_EXEMPT_NAMES.items():
        path = project_root / relative
        if not path.is_file():
            stale.append(f'{relative}: no such file')
            continue
        imported = {
            (found.module, found.name)
            for found in member_imports(
                tree=ast.parse(path.read_text(encoding='utf-8')), member_packages=member_packages
            )
        }
        stale.extend(
            f'{relative}: no longer imports {name} from {module}'
            for module, name in exempt_names
            if (module, name) not in imported
        )
    return stale


def test_no_engine_test_imports_a_member():
    """No file under the root tests/ imports a game, demo or app, apart from the exemptions."""
    assert engine_test_imports_of_members(project_root=PROJECT_ROOT, members=MEMBERS) == []


def test_every_member_import_exemption_still_applies():
    """Each exempt module still imports a member, and each exempt name is still imported."""
    assert stale_member_import_exemptions(project_root=PROJECT_ROOT, members=MEMBERS) == []


def stand_in_member(*, project_root: Path) -> WorkspaceMember:
    """A second, synthetic member, src/games/space-game with its package space_game.

    Args:
        project_root: The repository it is in (its directory is not written).

    Returns:
        The member.

    """
    return WorkspaceMember(
        directory=project_root / 'src' / 'games' / 'space-game',
        distribution='space-game',
        import_packages=('space_game',),
        console_scripts=(),
    )


def write_root_test(*, project_root: Path, relative: str, source: str) -> None:
    """Write a file under a repository's root tests/ (its directories too)."""
    path = project_root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding='utf-8')


GOLDEN_TRACES_TEST = 'tests/world/test_golden_traces.py'
GOLDEN_REPLAY_CONTROLS = 'tests/replay/golden_replay_controls.py'


def copy_golden_traces_test(*, project_root: Path, appended: str = '') -> None:
    """Copy the real tests/world/test_golden_traces.py into a repository, with source appended."""
    source = (PROJECT_ROOT / GOLDEN_TRACES_TEST).read_text(encoding='utf-8')
    write_root_test(
        project_root=project_root, relative=GOLDEN_TRACES_TEST, source=source + appended
    )


def test_a_non_exempt_member_import_in_the_golden_traces_test_is_found(tmp_path):
    """Only the named imports are exempt in that file: another name from the same module is not."""
    copy_golden_traces_test(
        project_root=tmp_path,
        appended='\nfrom clockwork_keep.player import TinkerController\nimport space_game\n',
    )
    line_count = len((tmp_path / GOLDEN_TRACES_TEST).read_text(encoding='utf-8').splitlines())
    members = [*MEMBERS, stand_in_member(project_root=tmp_path)]

    assert engine_test_imports_of_members(project_root=tmp_path, members=members) == [
        (
            f'{GOLDEN_TRACES_TEST}:{line_count - 1}: '
            'from clockwork_keep.player import TinkerController'
        ),
        f'{GOLDEN_TRACES_TEST}:{line_count}: import space_game',
    ]


def test_an_exempt_name_imported_under_an_alias_is_not_found(tmp_path):
    """An exempt name stays exempt under any alias (``Tinker as KeepTinker``)."""
    copy_golden_traces_test(
        project_root=tmp_path,
        appended=(
            '\n\ndef rules():\n'
            '    from clockwork_keep.player import Tinker as KeepTinker\n'
            '    from brave_adventurer import constants as adventurer_constants\n'
            '    return KeepTinker, adventurer_constants\n'
        ),
    )

    assert engine_test_imports_of_members(project_root=tmp_path, members=MEMBERS) == []


def test_a_function_level_member_import_is_found(tmp_path):
    """An import inside a function counts, and so does an import of the synthetic member."""
    write_root_test(
        project_root=tmp_path,
        relative='tests/test_paddles.py',
        source=(
            'def test_paddles():\n'
            '    from paddleslap import Game\n'
            '    import space_game.ships\n'
            '    from . import paddleslap\n'
            '    return Game, space_game, paddleslap\n'
        ),
    )
    members = [*MEMBERS, stand_in_member(project_root=tmp_path)]

    assert engine_test_imports_of_members(project_root=tmp_path, members=members) == [
        'tests/test_paddles.py:2: from paddleslap import Game',
        'tests/test_paddles.py:3: import space_game.ships',
    ]


def test_a_member_loaded_by_its_name_as_a_string_is_found(tmp_path):
    """``importlib.import_module`` and ``__import__`` of a literal member name count."""
    write_root_test(
        project_root=tmp_path,
        relative='tests/helpers/loading.py',
        source=(
            'import importlib\n'
            'from importlib import import_module as load\n\n'
            "GAME = importlib.import_module('paddleslap')\n"
            "SHIPS = load('space_game.ships')\n"
            "DEMO = __import__('dt_demo')\n"
            "ENGINE = importlib.import_module('glitchygames')\n"
            'NAMED = importlib.import_module(GAME.__name__)\n'
        ),
    )
    members = [*MEMBERS, stand_in_member(project_root=tmp_path)]

    assert engine_test_imports_of_members(project_root=tmp_path, members=members) == [
        'tests/helpers/loading.py:4: import paddleslap',
        'tests/helpers/loading.py:5: import space_game.ships',
        'tests/helpers/loading.py:6: import dt_demo',
    ]


def test_a_member_import_in_the_exempt_module_is_not_found(tmp_path):
    """The golden-replay control tables' module may import any member, at any level."""
    write_root_test(
        project_root=tmp_path,
        relative=GOLDEN_REPLAY_CONTROLS,
        source='import paddleslap\n\n\ndef tables():\n    import space_game\n',
    )
    members = [*MEMBERS, stand_in_member(project_root=tmp_path)]

    assert engine_test_imports_of_members(project_root=tmp_path, members=members) == []


def test_a_stale_member_import_exemption_is_found(tmp_path):
    """A missing exempt module, and an exempt name the file stopped importing, are reported."""
    write_root_test(
        project_root=tmp_path,
        relative=GOLDEN_TRACES_TEST,
        source=(
            (PROJECT_ROOT / GOLDEN_TRACES_TEST)
            .read_text(encoding='utf-8')
            .replace('from clockwork_keep.drawing import draw_tinker\n', '')
        ),
    )

    assert stale_member_import_exemptions(project_root=tmp_path, members=MEMBERS) == [
        f'{GOLDEN_REPLAY_CONTROLS}: no such file',
        f'{GOLDEN_TRACES_TEST}: no longer imports draw_tinker from clockwork_keep.drawing',
    ]


def test_an_exempt_module_importing_no_member_is_stale(tmp_path):
    """The exempt module importing no member, and a missing exempt-names file, are reported."""
    write_root_test(
        project_root=tmp_path, relative=GOLDEN_REPLAY_CONTROLS, source='import pygame\n'
    )

    assert stale_member_import_exemptions(project_root=tmp_path, members=MEMBERS) == [
        f'{GOLDEN_REPLAY_CONTROLS}: imports no member',
        f'{GOLDEN_TRACES_TEST}: no such file',
    ]


# The scripts/ package: this repository's tools and policy, which the engine's tests never import
# (Part 3, Stage D's constraints: the engine's tools moved into glitchygames.replay.tools)
SCRIPTS_PACKAGE = 'scripts'
# The root tests' own package: its helper modules are followed, so a test that reaches scripts/
# through a helper is found too (Task D9: tests/workspace_expectations.py once took
# tests/replay/test_replay_plugin.py there)
ROOT_TESTS_PACKAGE = 'tests'
# pytest loads every one above a test, and the plugins its pytest_plugins names
CONFTEST_FILE_NAME = 'conftest.py'
# The root test files that test a script, each with the scripts it tests: they may import them
# (the controller's pre-flight ruling for Stage D, 2026-10-26: "exempting each remaining
# script's own test file by name"). A test of the engine that uses a script's code as its test
# data is listed only while it does (the sprite tests: the legacy loader and the stack prototype)
SCRIPT_TEST_FILES: dict[str, tuple[str, ...]] = {
    'tests/replay/test_record_scripted_session.py': ('scripts/record_scripted_session.py',),
    'tests/sprites/test_animated_sprite.py': ('scripts/sprite_stack.py',),
    'tests/sprites/test_legacy_sprite_glyphs.py': ('scripts/raw_sprite_loader.py',),
    'tests/sprites/test_sprite_color_map_limits.py': ('scripts/raw_sprite_loader.py',),
    'tests/test_browser_touch_controls.py': ('scripts/build_browser_bundle.py',),
    'tests/test_build_browser_bundle.py': ('scripts/build_browser_bundle.py',),
    'tests/test_build_info.py': ('scripts/write_build_stamp.py',),
    'tests/test_build_sdl_x11.py': ('scripts/build_sdl_x11.py',),
    'tests/test_compare_driver_frames.py': ('scripts/compare_driver_frames.py',),
    'tests/test_complexity_report.py': ('scripts/complexity_report.py',),
    'tests/test_driver_configurations.py': ('scripts/driver_configurations.py',),
    'tests/test_driver_frame_matrix.py': ('scripts/driver_frame_matrix.py',),
    'tests/test_gen_ref_pages.py': ('scripts/gen_ref_pages.py',),
    'tests/test_generate_complexity_graphs.py': (
        'scripts/generate_complexity_graphs.py',
        'scripts/mkdocs_hooks.py',
    ),
    'tests/test_generate_performance_graphs.py': (
        'scripts/generate_performance_graphs.py',
        'scripts/mkdocs_hooks.py',
    ),
    'tests/test_import_published_ledger.py': ('scripts/import_published_ledger.py',),
    'tests/test_measure_staged_replays.py': ('scripts/measure_staged_replays.py',),
    'tests/test_microphone_capture_check.py': ('scripts/microphone_capture_check.py',),
    'tests/test_mkdocs_hooks_browser_games.py': ('scripts/mkdocs_hooks.py',),
    'tests/test_record_golden_traces.py': (
        'scripts/record_golden_traces.py',
        'scripts/golden_inputs.py',
        'scripts/record_scripted_session.py',
    ),
    'tests/test_workspace_packages.py': (
        'scripts/workspace_packages.py',
        'scripts/git_checkout.py',
    ),
}
# Why a source guard may reach scripts/: tests/workspace_sources.py's scanned_source_files lists
# the members' packages with scripts/workspace_packages.py, so the guard reads every member's
# source
SOURCE_GUARD_REASON = (
    "a guard over the engine's and every member's source (tests/workspace_sources.py "
    'scanned_source_files lists the members with scripts/workspace_packages.py)'
)
# The root test files that check this repository itself (its workspace, its members' goldens,
# demos and console scripts, its CI and its suite), not the engine, each with its reason (Task
# D9's decision, kept by the controller in its review: these test no script but read the
# workspace through one, which an engine test never needs). Each holds only such tests: an
# engine file that held one or two (the source guards, the power-on test, our goldens' checks)
# had them moved out to a file named for what it checks (Task D9 fix round 1), so no engine test
# shares an exemption. They may reach scripts/ too
REPOSITORY_TEST_FILES: dict[str, str] = {
    'tests/engine/test_every_game_powers_on.py': (
        "powers on every member's console script through its own main(), listed from the workspace"
    ),
    'tests/replay/test_bundled_demos.py': "replays our members' bundled demos",
    'tests/replay/test_golden_replays.py': "checks our members' goldens with our games' tables",
    'tests/replay/test_replays_log_quietly.py': (
        "replays our members' goldens and bundled demos at the tools' log level"
    ),
    'tests/replay/test_recording_logical_names.py': (
        'checks the logical names of every committed recording of our members'
    ),
    'tests/test_ci_config.py': "checks the CI configuration against the workspace's members",
    'tests/test_engine_context_source_guards.py': SOURCE_GUARD_REASON,
    'tests/test_engine_doors.py': SOURCE_GUARD_REASON,
    'tests/test_engine_wheel.py': (
        'checks the engine wheel holds no member (read from the workspace)'
    ),
    'tests/test_our_measured_recordings.py': "checks our games' recordings are all measured",
    'tests/test_pump_seam_guard.py': SOURCE_GUARD_REASON,
    'tests/test_suite_collection.py': (
        "the suite's own collection and import guards, over every test root"
    ),
    'tests/test_unseeded_randomness_guard.py': SOURCE_GUARD_REASON,
    'tests/test_workspace_config.py': (
        "checks the workspace's configuration (members, extras, docs)"
    ),
    'tests/test_workspace_sprite_files.py': (
        "checks every member's sprite files, found from the workspace"
    ),
    'tests/test_workspace_expectations.py': (
        'checks the hand-written expected sets against a workspace (tests/workspace_goldens.py)'
    ),
    'tests/world/test_golden_traces.py': (
        "replays our games' golden traces with scripts/record_golden_traces.py's games and scripts"
    ),
}


def root_test_module_name(*, relative: str) -> str:
    """Return the module a file under the repository is imported as (the root is on sys.path).

    Args:
        relative: Its path from the repository (``tests/replay/helpers.py``, ``conftest.py``).

    Returns:
        Its module (``tests.replay.helpers``, ``conftest``).

    """
    return module_name_of(relative=Path(relative))


def conftest_modules_above(*, project_root: Path, relative: str) -> list[str]:
    """Return the conftest modules pytest loads for a test file: one per directory above it.

    Args:
        project_root: The repository (the root conftest's directory).
        relative: The test file's path from the repository.

    Returns:
        Their module names, the root's first.

    """
    directories = [*reversed(Path(relative).parents)]
    return [
        root_test_module_name(relative=(directory / CONFTEST_FILE_NAME).as_posix())
        for directory in directories
        if (project_root / directory / CONFTEST_FILE_NAME).is_file()
    ]


def root_test_import_graph(*, project_root: Path) -> dict[str, frozenset[str]]:
    """Return what each module under the root tests/, and the root conftest, brings in.

    A module's imports of ``tests`` and ``scripts`` (``ast_scanning.imported_module_names``);
    a conftest's ``pytest_plugins`` too, and a test module's conftests (every ``conftest.py``
    above it): pytest loads both before the test runs, so a fixture or plugin reaches a test by
    name, never by an import (the review of Task D9).

    Args:
        project_root: The repository.

    Returns:
        Module name -> the module names it brings in.

    """
    files = [(relative, tree) for relative, tree in _root_test_modules(project_root=project_root)]
    root_conftest = project_root / CONFTEST_FILE_NAME
    if root_conftest.is_file():
        files.append((
            CONFTEST_FILE_NAME,
            ast.parse(root_conftest.read_text(encoding='utf-8'), filename=str(root_conftest)),
        ))
    graph: dict[str, frozenset[str]] = {}
    for relative, tree in files:
        module = root_test_module_name(relative=relative)
        brought_in = imported_module_names(
            tree=tree,
            module=module,
            is_package=relative.endswith('__init__.py'),
            followed=ROOT_TESTS_PACKAGE,
            target=SCRIPTS_PACKAGE,
        )
        if Path(relative).name == CONFTEST_FILE_NAME:
            brought_in |= set(pytest_plugin_names(tree=tree))
        if Path(relative).name.startswith('test_'):
            brought_in |= set(conftest_modules_above(project_root=project_root, relative=relative))
        graph[module] = frozenset(brought_in)
    return graph


def path_to_scripts(*, graph: dict[str, frozenset[str]], module: str) -> list[str] | None:
    """Return the shortest chain from a root test module to a ``scripts`` module, if any.

    Args:
        graph: ``root_test_import_graph``'s.
        module: The test module.

    Returns:
        ``[module, helper, ..., 'scripts[.<name>]']``, or None when it reaches none.

    """
    return path_to_package(graph=graph, module=module, target=SCRIPTS_PACKAGE)


def root_test_files(*, project_root: Path) -> list[str]:
    """Return every test module under the root tests/ (``test_*.py``), relative, sorted.

    Returns:
        Their paths from the repository.

    """
    return sorted(
        path.relative_to(project_root).as_posix()
        for path in (project_root / ROOT_TESTS_PACKAGE).rglob('test_*.py')
        if '__pycache__' not in path.parts
    )


def engine_tests_reaching_scripts(*, project_root: Path, exempt: frozenset[str]) -> list[str]:
    """Return each root test module that imports ``scripts``, directly or through a helper.

    The engine's tests test the engine as a game sees it: installed, with no scripts/ (Stage D:
    "No engine module imports ``scripts.*``, and no engine test does"). Every import counts, at
    any level, through any chain of the root tests' own modules (the controller's note to Task
    D9: a direct-import check missed tests/replay/test_replay_plugin.py, which reached
    ``scripts.workspace_packages`` through tests/workspace_expectations.py).

    Args:
        project_root: The repository.
        exempt: The test files that may (``SCRIPT_TEST_FILES``, ``REPOSITORY_TEST_FILES``).

    Returns:
        ``<file>: <module> -> <helper> -> ... -> scripts.<name>`` for each, sorted by file.

    """
    graph = root_test_import_graph(project_root=project_root)
    findings: list[str] = []
    for relative in root_test_files(project_root=project_root):
        if relative in exempt:
            continue
        chain = path_to_scripts(graph=graph, module=root_test_module_name(relative=relative))
        if chain is not None:
            findings.append(f'{relative}: {" -> ".join(chain)}')
    return findings


def stale_scripts_import_exemptions(
    *,
    project_root: Path,
    script_tests: dict[str, tuple[str, ...]],
    repository_tests: dict[str, str],
) -> list[str]:
    """Return each exemption from ``engine_tests_reaching_scripts`` that no longer applies.

    Args:
        project_root: The repository.
        script_tests: ``SCRIPT_TEST_FILES``'s shape.
        repository_tests: ``REPOSITORY_TEST_FILES``'s shape.

    Returns:
        ``<file>: <why it is stale>`` for each, the script tests first, each list in its order.

    """
    graph = root_test_import_graph(project_root=project_root)
    stale: list[str] = []
    for relative in [*script_tests, *repository_tests]:
        if not (project_root / relative).is_file():
            stale.append(f'{relative}: no such file')
        elif path_to_scripts(graph=graph, module=root_test_module_name(relative=relative)) is None:
            stale.append(f'{relative}: reaches no scripts.* any more')
        stale.extend(
            f'{relative}: tests {script}, which is gone'
            for script in script_tests.get(relative, ())
            if not (project_root / script).is_file()
        )
    return stale


def test_no_engine_test_reaches_scripts():
    """No root test imports scripts/, directly or through a helper, apart from the exemptions."""
    exempt = frozenset(SCRIPT_TEST_FILES) | frozenset(REPOSITORY_TEST_FILES)

    assert engine_tests_reaching_scripts(project_root=PROJECT_ROOT, exempt=exempt) == []


def test_every_scripts_import_exemption_still_applies():
    """Each exempt file exists and still reaches scripts/, and each script it tests exists."""
    assert (
        stale_scripts_import_exemptions(
            project_root=PROJECT_ROOT,
            script_tests=SCRIPT_TEST_FILES,
            repository_tests=REPOSITORY_TEST_FILES,
        )
        == []
    )


def test_the_two_exemption_lists_do_not_overlap():
    """A file is exempt for one reason: it tests a script, or it checks this repository."""
    assert not set(SCRIPT_TEST_FILES) & set(REPOSITORY_TEST_FILES)


def write_planted_tests(*, project_root: Path) -> None:
    """Plant root tests reaching scripts/ in each way, and one that does not, in a repository.

    - ``test_engine_thing.py``: two helpers deep (``expected`` -> ``workspace`` -> scripts)
    - ``test_by_relative.py``: through a helper that imports its sibling relatively
    - ``test_function_level.py``: an import inside a test function
    - ``test_string_load.py``: ``importlib.import_module('scripts.tool')``
    - ``test_by_package.py``: through a helpers package whose ``__init__`` imports scripts
    - ``test_bare.py``: a bare ``import scripts`` (it runs ``scripts/__init__.py``)
    - ``inside/test_in_package.py``: through its own package's ``__init__``, which imports scripts
    - ``test_clean.py``: a helper that imports only pygame
    - ``test_tool.py``: a script's own test (exempt in the test)
    """
    for relative, source in {
        'scripts/tool.py': 'THING = 1\n',
        'tests/__init__.py': '',
        'tests/helpers/__init__.py': '',
        'tests/helpers/workspace.py': 'from scripts.tool import THING\n',
        'tests/helpers/expected.py': 'from tests.helpers.workspace import THING\n',
        'tests/helpers/relative.py': 'from .workspace import THING\n',
        'tests/helpers/clean.py': 'import pygame\n',
        'tests/loaded/__init__.py': 'import scripts.tool\n',
        'tests/loaded/inner.py': 'VALUE = 2\n',
        'tests/test_engine_thing.py': 'from tests.helpers.expected import THING\n',
        'tests/test_by_relative.py': 'from tests.helpers import relative\n',
        'tests/test_function_level.py': 'def test_tool():\n    import scripts.tool\n',
        'tests/test_string_load.py': (
            "import importlib\n\nTOOL = importlib.import_module('scripts.tool')\n"
        ),
        'tests/test_by_package.py': 'from tests.loaded.inner import VALUE\n',
        'tests/test_clean.py': 'from tests.helpers import clean\n',
        'tests/test_tool.py': 'from scripts import tool\n',
        'tests/test_bare.py': 'import scripts\n',
        'tests/inside/__init__.py': 'import scripts.tool\n',
        'tests/inside/test_in_package.py': 'VALUE = 3\n',
    }.items():
        write_root_test(project_root=project_root, relative=relative, source=source)


def test_a_root_test_reaching_scripts_in_any_way_is_found_with_its_chain(tmp_path):
    """Every way a root test reaches scripts/ is found, with the chain of imports that does.

    Directly, by a bare ``import scripts``, at function level, by a string load, or through
    helpers, relative imports, a package's ``__init__`` and the test's own package.
    """
    write_planted_tests(project_root=tmp_path)

    assert engine_tests_reaching_scripts(
        project_root=tmp_path, exempt=frozenset({'tests/test_tool.py'})
    ) == [
        (
            'tests/inside/test_in_package.py: tests.inside.test_in_package -> tests.inside -> '
            'scripts.tool'
        ),
        'tests/test_bare.py: tests.test_bare -> scripts',
        ('tests/test_by_package.py: tests.test_by_package -> tests.loaded -> scripts.tool'),
        (
            'tests/test_by_relative.py: tests.test_by_relative -> tests.helpers.relative -> '
            'tests.helpers.workspace -> scripts.tool'
        ),
        (
            'tests/test_engine_thing.py: tests.test_engine_thing -> tests.helpers.expected -> '
            'tests.helpers.workspace -> scripts.tool'
        ),
        'tests/test_function_level.py: tests.test_function_level -> scripts.tool',
        'tests/test_string_load.py: tests.test_string_load -> scripts.tool',
    ]


def test_a_root_test_reaching_scripts_through_a_conftest_or_its_plugins_is_found(tmp_path):
    """A conftest above a test, and a plugin a conftest loads, are followed as imports are.

    pytest loads every ``conftest.py`` above a test, and the plugins its ``pytest_plugins``
    names, before the test runs, so a fixture or plugin that imports scripts/ reaches the test
    by name, never by an import. The shortest chain is named.
    """
    for relative, source in {
        'scripts/tool.py': 'THING = 1\n',
        'conftest.py': "pytest_plugins = ['pytester', 'tests.shared_plugin']\n",
        'tests/__init__.py': '',
        'tests/shared_plugin.py': 'from scripts.tool import THING\n',
        'tests/test_plain.py': 'VALUE = 1\n',
        'tests/nested/__init__.py': '',
        'tests/nested/conftest.py': (
            'import pytest\n\n\n@pytest.fixture\ndef tool():\n'
            '    from scripts import tool\n    return tool\n'
        ),
        'tests/nested/test_deep.py': 'def test_deep(tool):\n    assert tool\n',
    }.items():
        write_root_test(project_root=tmp_path, relative=relative, source=source)

    assert engine_tests_reaching_scripts(project_root=tmp_path, exempt=frozenset()) == [
        (
            'tests/nested/test_deep.py: tests.nested.test_deep -> tests.nested.conftest -> '
            'scripts.tool'
        ),
        'tests/test_plain.py: tests.test_plain -> conftest -> tests.shared_plugin -> scripts.tool',
    ]


def test_a_stale_scripts_import_exemption_is_found(tmp_path):
    """A missing file, a file that reaches no script, and a script that is gone are reported."""
    write_planted_tests(project_root=tmp_path)

    assert stale_scripts_import_exemptions(
        project_root=tmp_path,
        script_tests={
            'tests/test_tool.py': ('scripts/tool.py', 'scripts/deleted_tool.py'),
            'tests/test_no_such_file.py': ('scripts/tool.py',),
        },
        repository_tests={
            'tests/test_clean.py': 'reads the workspace',
            'tests/test_engine_thing.py': 'reads the workspace',
        },
    ) == [
        'tests/test_tool.py: tests scripts/deleted_tool.py, which is gone',
        'tests/test_no_such_file.py: no such file',
        'tests/test_clean.py: reaches no scripts.* any more',
    ]


# Directories of test data, not test modules (a member's golden replays live in fixtures/)
TEST_DATA_DIRECTORY_NAMES = frozenset({'fixtures', '__pycache__'})


def misnamed_member_test_modules(*, members: Sequence[WorkspaceMember]) -> list[str]:
    """Return each test file in a member's tests, at any depth, not named for its distribution.

    A convention, not a collision guard (each test module is imported by its path:
    ``test_tests_are_imported_by_their_paths``): every test file (``test_*.py``) is named
    ``test_<distribution with - as _>.py`` or ``test_<distribution with - as _>_*.py``
    (``test_mr_muncher_*.py``; Brave Adventurer's four packages share
    ``test_brave_adventurer_*.py``), so ``test_bitmappyx.py`` is misnamed. Helper modules
    (``film_strip_support.py``) and ``conftest.py`` are named freely; test-data directories
    (``fixtures``) are not scanned.

    Args:
        members: The workspace's members.

    Returns:
        ``<distribution>: tests/<module>`` for each misnamed module, sorted within each member,
        in the members' order.

    """
    misnamed: list[str] = []
    for member in members:
        prefix = f'test_{member.distribution.replace("-", "_")}'
        misnamed.extend(
            f'{member.distribution}: tests/{relative}'
            for relative in sorted(
                python_file.relative_to(member.tests_directory).as_posix()
                for python_file in member.tests_directory.rglob('*.py')
                if not TEST_DATA_DIRECTORY_NAMES
                & set(python_file.relative_to(member.tests_directory).parts)
                and fnmatch.fnmatch(python_file.name, 'test_*.py')
                and python_file.name != f'{prefix}.py'
                and not fnmatch.fnmatch(python_file.name, f'{prefix}_*.py')
            )
        )
    return misnamed


def test_every_members_test_modules_are_named_for_it():
    """Every test file in every member's tests, subdirectories included, is named for it."""
    assert misnamed_member_test_modules(members=MEMBERS) == []
    # Each member's move tests are split by subject, and every member has the logical-names one
    for member in MEMBERS:
        logical_names = f'test_{member.distribution.replace("-", "_")}_logical_names.py'
        assert (member.tests_directory / logical_names).is_file(), member.distribution


def test_a_misnamed_member_test_module_in_a_subdirectory_is_found(tmp_path):
    """Each member's misnamed modules are reported; conftest.py and fixtures/ are not."""
    bitmappy = WorkspaceMember(
        directory=tmp_path / 'src' / 'apps' / 'bitmappy',
        distribution='bitmappy',
        import_packages=('bitmappy',),
        console_scripts=(),
    )
    space_game = stand_in_member(project_root=tmp_path)
    for member, relatives in (
        (
            bitmappy,
            (
                'conftest.py',
                'test_bitmappy_tools.py',
                'test_bitmappyx.py',
                'canvas/conftest.py',
                'canvas/test_bitmappy_canvas.py',
                'canvas/test_canvas.py',
                'canvas/fixtures/sprite_data.py',
                'canvas/canvas_support.py',
            ),
        ),
        (
            space_game,
            (
                'test_space_game.py',
                'test_space_game_ships.py',
                'test_spacegame_orbits.py',
                'fleet/test_bitmappy_fleet.py',
                'fixtures/replays/ships.py',
            ),
        ),
    ):
        for relative in relatives:
            path = member.tests_directory / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('', encoding='utf-8')

    assert misnamed_member_test_modules(members=[bitmappy, space_game]) == [
        'bitmappy: tests/canvas/test_canvas.py',
        'bitmappy: tests/test_bitmappyx.py',
        'space-game: tests/fleet/test_bitmappy_fleet.py',
        'space-game: tests/test_spacegame_orbits.py',
    ]


SYS_PATH_EDITS = frozenset({'sys.path.insert', 'sys.path.append'})


def sys_path_edits(*, project_root: Path, roots: list[Path]) -> list[str]:
    """Return every call of ``sys.path.insert`` or ``sys.path.append`` below the test roots.

    Tests import the installed packages; a path edit can put the repository (or ``src/``) ahead
    of the installed copy, so a non-editable run would test the source tree. ``from sys import
    path`` and ``import sys as s`` spellings are followed.

    Args:
        project_root: The repository.
        roots: The test roots to scan.

    Returns:
        ``<file>:<line>`` for each call, sorted.

    """
    findings: list[str] = []
    for _root, python_file in _python_files(roots=roots):
        module = ast.parse(python_file.read_text(encoding='utf-8'), filename=str(python_file))
        bindings = import_bindings(tree=module, watched_modules=frozenset({'sys'}))
        findings.extend(
            f'{python_file.relative_to(project_root).as_posix()}:{node.lineno}'
            for node in ast.walk(module)
            if isinstance(node, ast.Call)
            and qualified_name(
                node=node.func, bindings=bindings, watched_modules=frozenset({'sys'})
            )
            in SYS_PATH_EDITS
        )
    return sorted(findings)


def test_no_test_edits_sys_path():
    """No test file, in the engine's tests or any member's, edits ``sys.path``."""
    assert sys_path_edits(project_root=PROJECT_ROOT, roots=collected_test_roots()) == []


def test_a_test_editing_sys_path_is_found(tmp_path):
    """Every spelling of a path edit is reported; reading ``sys.path`` and list inserts are not."""
    roots = write_member_test_root(project_root=tmp_path)
    (tmp_path / 'tests' / 'test_root_edit.py').write_text(
        'import sys\nsys.path.insert(0, "x")\n', encoding='utf-8'
    )
    (tmp_path / MEMBER_TESTS / 'test_member_edit.py').write_text(
        'import sys as system\nfrom sys import path\n'
        'system.path.append("y")\npath.insert(0, "z")\n',
        encoding='utf-8',
    )
    (tmp_path / MEMBER_TESTS / 'test_innocent.py').write_text(
        'import sys\nitems = []\nitems.insert(0, 1)\nprint(sys.path[0])\n', encoding='utf-8'
    )

    assert sys_path_edits(project_root=tmp_path, roots=roots) == [
        'src/games/space-game/tests/test_member_edit.py:3',
        'src/games/space-game/tests/test_member_edit.py:4',
        'tests/test_root_edit.py:2',
    ]


# `glitchygames.examples` (a module path) or `glitchygames/examples` (a directory path): the
# engine's examples package, deleted when the last demo became a workspace member (Part 3 of
# plans/2026-10-24-workspace-packages.md)
FORMER_EXAMPLES_REFERENCE = re.compile(r'glitchygames[./]examples\b')
# File types the guard reads: code, configuration and documentation
FORMER_EXAMPLES_SCANNED_SUFFIXES = frozenset({
    '.py',
    '.mjs',
    '.toml',
    '.yml',
    '.yaml',
    '.cfg',
    '.md',
    '.html',
})
# Tracked directories that are history, not code, configuration or living documentation: finished
# plans (the living ones are scanned below through living_documentation_lines) and the replay
# ledger's rows, which record the recordings' paths as they were measured
FORMER_EXAMPLES_HISTORY_DIRECTORIES = ('plans', 'quality', '.superpowers')
# The only files that may still name the deleted package, each for a reason that is history on
# purpose. A path is listed (never a pattern), so a new reference anywhere else is found.
FORMER_EXAMPLES_EXEMPT_PATHS: dict[str, str] = {
    'pyproject.toml': (
        '[tool.glitchygames] recording-renames keys: the old paths of the recordings that moved'
    ),
    'tests/replay/tools/test_settings.py': (
        'the recording-renames our settings must give, copied from the constant they replaced'
    ),
    'src/demos/dt-demo/tests/test_dt_demo_install_location.py': (
        'the move out of the engine: nothing is left of the old package'
    ),
    'src/demos/dt-demo/tests/test_dt_demo_entry_points.py': (
        'the move out of the engine: the old python -m command it replaces'
    ),
    'src/demos/joystick-demo/tests/test_joystick_demo_install_location.py': (
        'the move out of the engine: nothing is left of the old package'
    ),
    'src/demos/joystick-demo/tests/test_joystick_demo_entry_points.py': (
        'the move out of the engine: the old python -m command it replaces'
    ),
    'src/demos/text-input-demo/tests/test_text_input_demo_install_location.py': (
        'the move out of the engine: nothing is left of the old package'
    ),
    'src/demos/text-input-demo/tests/test_text_input_demo_entry_points.py': (
        'the move out of the engine: the old python -m command it replaces'
    ),
    'src/games/brave-adventurer/tests/test_brave_adventurer_install_location.py': (
        'the move out of the engine: nothing is left of the old package'
    ),
    'src/games/clockwork-keep/tests/test_clockwork_keep_install_location.py': (
        'the move out of the engine: nothing is left of the old package'
    ),
    'src/games/drawing-fire/tests/test_drawing_fire_install_location.py': (
        'the move out of the engine: nothing is left of the old package'
    ),
    'src/games/mr-muncher/tests/test_mr_muncher_logical_names.py': (
        'the move out of the engine: an old-format recording names the old module'
    ),
    'src/games/paddleslap/tests/test_paddleslap_install_location.py': (
        'the move out of the engine: nothing is left of the old package'
    ),
    'src/games/paddleslap/tests/test_paddleslap_entry_points.py': (
        'the move out of the engine: the old python -m command it replaces'
    ),
    'src/demos/dt-demo/src/dt_demo/__main__.py': (
        'docstring: the old python -m command, kept as history'
    ),
    'src/demos/joystick-demo/src/joystick_demo/__main__.py': (
        'docstring: the old python -m command, kept as history'
    ),
    'src/demos/text-input-demo/src/text_input_demo/__main__.py': (
        'docstring: the old python -m command, kept as history'
    ),
    'src/games/paddleslap/src/paddleslap/__main__.py': (
        'docstring: the old python -m command, kept as history'
    ),
    'tests/world/test_gameplay_replay.py': (
        'old-format stand-ins: recordings whose header names the module as it was'
    ),
    'tests/replay/tools/test_children.py': (
        'old-format stand-in: a recording whose header names the module as it was'
    ),
    'src/games/paddleslap/tests/test_paddleslap_recording_history.py': (
        'the golden replay is old-format: its scene start names the module as it was'
    ),
    'tests/replay/tools/test_measure.py': (
        "a ledger row keyed by a moved recording's old path (recording-renames)"
    ),
    'docs/architecture/game_packages.md': (
        'the recipe for moving a game out of the engine: its history lines name where games were'
    ),
    'docs/games/clockwork_keep.md': (
        'describes test_clockwork_keep_install_location.py, which asserts the old package is gone'
    ),
    'plans/2026-10-24-workspace-packages.md': 'the master plan: the decisions and the history',
    'tests/test_workspace_packages.py': (
        'test_the_engines_examples_directory_is_gone: names the deleted directory to check it'
    ),
    'tests/test_suite_collection.py': 'this guard: its regex, exemptions and examples',
}


def _tracked_paths(*, project_root: Path) -> list[str]:
    """Return the paths git tracks in ``project_root`` (ignored and untracked files are not)."""
    returncode, listing = run_git(arguments=['ls-files', '-z'], directory=project_root)
    assert returncode == 0, listing
    return [tracked_path for tracked_path in listing.split('\0') if tracked_path]


def former_examples_references(*, project_root: Path) -> list[str]:
    """Return ``<file>:<line>: <text>`` for each reference to the deleted examples package.

    Args:
        project_root: The repository (a git work tree).

    Returns:
        The references in tracked code, configuration and documentation, and in the living plans
        and BUGS.md's active entries, other than those in the exempt paths; sorted.

    """
    lines: list[tuple[str, int, str]] = []
    for relative in _tracked_paths(project_root=project_root):
        path = project_root / relative
        if (
            Path(relative).suffix not in FORMER_EXAMPLES_SCANNED_SUFFIXES
            or relative.split('/', maxsplit=1)[0] in FORMER_EXAMPLES_HISTORY_DIRECTORIES
            or relative == 'BUGS.md'
            or not path.is_file()
        ):
            continue
        lines.extend(
            (relative, line_number, line)
            for line_number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1)
        )
    # Finished plans and resolved bugs are history; the living plans and open bugs are not
    lines.extend(
        entry
        for entry in living_documentation_lines(project_root=project_root)
        if entry[0] == 'BUGS.md' or entry[0] in LIVING_PLAN_FILES
    )
    return sorted(
        f'{relative}:{line_number}: {line.strip()}'
        for relative, line_number, line in lines
        if relative not in FORMER_EXAMPLES_EXEMPT_PATHS
        and FORMER_EXAMPLES_REFERENCE.search(line) is not None
    )


def test_nothing_names_the_deleted_examples_package():
    """No code, configuration or living document names glitchygames.examples any more."""
    assert former_examples_references(project_root=PROJECT_ROOT) == []


def test_the_exempt_paths_all_exist_and_still_name_the_deleted_package():
    """An exemption that no longer applies is removed, so the list never hides a new reference."""
    stale = [
        relative
        for relative in FORMER_EXAMPLES_EXEMPT_PATHS
        if relative != 'tests/test_suite_collection.py'
        and FORMER_EXAMPLES_REFERENCE.search((PROJECT_ROOT / relative).read_text(encoding='utf-8'))
        is None
    ]

    assert stale == []


def test_a_reference_outside_the_exempt_paths_is_found(tmp_path):
    """Code, config and a living doc are found; history, exempt paths and other types are not."""
    files = {
        'src/engine.py': 'import glitchygames.examples\n',
        'mkdocs.yml': 'path: src/glitchygames/examples\n',
        'docs/guide.md': 'fine\nsee glitchygames/examples/x\n',
        'plans/old.md': 'glitchygames.examples\n',
        'BUGS.md': (
            '## 1. A\n- **Status**: Active\nglitchygames.examples\n'
            '## 2. B\n- **Status**: Resolved\nglitchygames.examples\n'
        ),
        'pyproject.toml': '"glitchygames/examples/x" = "src/games/x"\n',
        'notes.txt': 'glitchygames.examples\n',
        'src/glitchygames/examples_utils.py': 'glitchygames.examples_utils\n',
    }
    for relative, text in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    run_git(arguments=['init', '--quiet'], directory=tmp_path)
    run_git(arguments=['add', '.'], directory=tmp_path)

    assert former_examples_references(project_root=tmp_path) == [
        'BUGS.md:3: glitchygames.examples',
        'docs/guide.md:2: see glitchygames/examples/x',
        'mkdocs.yml:1: path: src/glitchygames/examples',
        'src/engine.py:1: import glitchygames.examples',
    ]
