"""Guard against test files that pytest silently never collects.

pytest skips tests without any warning when a directory matches a norecursedirs pattern
(matched against directory *names* at any depth, not paths) or when a file's name does
not match python_files. Both have happened: norecursedirs = ["examples"] once excluded
the engine's examples tests (tests/examples/, deleted since) for months.
"""

import ast
import fnmatch
import importlib.metadata
import json
import re
import tomllib
from pathlib import Path

from scripts.git_checkout import run_git

from tests.ast_scanning import import_bindings, qualified_name
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


def duplicate_test_file_names(*, project_root: Path, roots: list[Path]) -> list[str]:
    """Return every test file name used more than once below the roots, with each file using it.

    A member's tests directory is not a package (rootless), so pytest imports each of its test
    files under its bare file name: a second ``test_game.py`` anywhere, in another member or in
    the root's tests/, would collide with it (BUGS.md #31). A member names its test files after
    its package (``test_<package>_<area>.py``).

    Args:
        project_root: The repository (the files are named relative to it).
        roots: The test roots (``collected_test_roots``).

    Returns:
        ``<name>: <file>, <file>[, ...]`` for each name used more than once, sorted.

    """
    files_by_name: dict[str, list[str]] = {}
    for root, test_file in _python_files(roots=roots):
        if fnmatch.fnmatch(test_file.name, 'test_*.py'):
            files_by_name.setdefault(test_file.name, []).append(
                test_file.relative_to(project_root).as_posix()
            )
    return [
        f'{name}: {", ".join(files)}'
        for name, files in sorted(files_by_name.items())
        if len(files) > 1
    ]


def test_test_file_names_are_unique_across_packages():
    """Member tests are not packages, so pytest imports them by file name: names must differ."""
    assert not duplicate_test_file_names(project_root=PROJECT_ROOT, roots=collected_test_roots())


def test_a_test_file_name_used_twice_is_found_naming_both_files(tmp_path):
    """A member's test file and the root's of the same name: both are reported."""
    roots = write_member_test_root(project_root=tmp_path)
    (tmp_path / 'tests' / 'test_space_game.py').write_text(
        'def test_orbits():\n    assert True\n', encoding='utf-8'
    )

    member_file = (MEMBER_TESTS / 'test_space_game.py').as_posix()

    assert duplicate_test_file_names(project_root=tmp_path, roots=roots) == [
        f'test_space_game.py: {member_file}, tests/test_space_game.py'
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


def engine_test_imports_of_bitmappy(*, project_root: Path) -> list[str]:
    """Return every file under the root tests/ that imports Bitmappy, as ``<file>:<line>``.

    Bitmappy is a workspace member (src/apps/bitmappy); its tests live there, so the engine's
    tests never need it.

    Args:
        project_root: The repository (its tests/ directory is scanned).

    Returns:
        ``<file>:<line>`` for each import of a module whose top level is ``bitmappy``, sorted.

    """
    tests_directory = project_root / 'tests'
    findings: list[str] = []
    for python_file in sorted(tests_directory.rglob('*.py')):
        if '__pycache__' in python_file.parts:
            continue
        relative = python_file.relative_to(project_root)
        module = ast.parse(python_file.read_text(encoding='utf-8'), filename=str(python_file))
        for node in ast.walk(module):
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                imported_names = [node.module or '']
            elif isinstance(node, ast.Import):
                imported_names = [alias.name for alias in node.names]
            else:
                continue
            if any(name.split('.')[0] == 'bitmappy' for name in imported_names):
                findings.append(f'{relative.as_posix()}:{node.lineno}')
    return findings


def test_no_engine_test_imports_bitmappy():
    """The engine's tests import no Bitmappy module: Bitmappy's tests are in its member."""
    assert engine_test_imports_of_bitmappy(project_root=PROJECT_ROOT) == []


def test_an_engine_test_importing_bitmappy_is_found(tmp_path):
    """Both spellings of an import of Bitmappy are reported, a relative import is not."""
    (tmp_path / 'tests' / 'tools').mkdir(parents=True)
    (tmp_path / 'tests' / 'tools' / 'test_editor.py').write_text(
        'import bitmappy.editor\nfrom bitmappy import main\nfrom . import bitmappy\n',
        encoding='utf-8',
    )

    assert engine_test_imports_of_bitmappy(project_root=tmp_path) == [
        'tests/tools/test_editor.py:1',
        'tests/tools/test_editor.py:2',
    ]


BITMAPPY_TESTS_DIRECTORY = PROJECT_ROOT / 'src' / 'apps' / 'bitmappy' / 'tests'
# Directories of test data, not test modules (a member's golden replays live in fixtures/)
TEST_DATA_DIRECTORY_NAMES = frozenset({'fixtures', '__pycache__'})


def misnamed_bitmappy_test_modules(*, tests_directory: Path) -> list[str]:
    """Return each module in Bitmappy's tests, at any depth, not named ``test_bitmappy*.py``.

    Rootless tests are imported by their bare file names, so every module is named for Bitmappy.
    ``conftest.py`` is the one exception; test-data directories (``fixtures``) are not scanned.

    Args:
        tests_directory: Bitmappy's tests directory (src/apps/bitmappy/tests).

    Returns:
        The misnamed modules, relative to the tests directory, sorted.

    """
    return sorted(
        python_file.relative_to(tests_directory).as_posix()
        for python_file in tests_directory.rglob('*.py')
        if not TEST_DATA_DIRECTORY_NAMES & set(python_file.relative_to(tests_directory).parts)
        and python_file.name != 'conftest.py'
        and not fnmatch.fnmatch(python_file.name, 'test_bitmappy*.py')
    )


def test_bitmappys_test_modules_are_named_for_it():
    """Every module in Bitmappy's tests, subdirectories included, is named test_bitmappy*.py."""
    assert misnamed_bitmappy_test_modules(tests_directory=BITMAPPY_TESTS_DIRECTORY) == []
    assert (BITMAPPY_TESTS_DIRECTORY / 'test_bitmappy_after_the_move.py').is_file()


def test_a_misnamed_bitmappy_test_module_in_a_subdirectory_is_found(tmp_path):
    """A subdirectory's misnamed module is reported; conftest.py and fixtures/ are not."""
    (tmp_path / 'canvas' / 'fixtures').mkdir(parents=True)
    for relative in (
        'conftest.py',
        'test_bitmappy_tools.py',
        'canvas/conftest.py',
        'canvas/test_bitmappy_canvas.py',
        'canvas/test_canvas.py',
        'canvas/fixtures/sprite_data.py',
    ):
        (tmp_path / relative).write_text('', encoding='utf-8')

    assert misnamed_bitmappy_test_modules(tests_directory=tmp_path) == ['canvas/test_canvas.py']


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
    'src/glitchygames/recording_metrics.py': (
        'RECORDING_PATH_RENAMES keys: the old paths of the recordings that moved'
    ),
    'src/demos/dt-demo/tests/test_dt_demo_after_the_move.py': 'the move out of the engine',
    'src/demos/joystick-demo/tests/test_joystick_demo_after_the_move.py': (
        'the move out of the engine'
    ),
    'src/demos/text-input-demo/tests/test_text_input_demo_after_the_move.py': (
        'the move out of the engine'
    ),
    'src/games/brave-adventurer/tests/test_brave_adventurer_after_the_move.py': (
        'the move out of the engine'
    ),
    'src/games/clockwork-keep/tests/test_clockwork_keep_after_the_move.py': (
        'the move out of the engine'
    ),
    'src/games/drawing-fire/tests/test_drawing_fire_after_the_move.py': (
        'the move out of the engine'
    ),
    'src/games/mr-muncher/tests/test_logical_names_after_the_move.py': (
        'the move out of the engine'
    ),
    'src/games/paddleslap/tests/test_paddleslap_after_the_move.py': 'the move out of the engine',
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
    'tests/replay/test_replay_plugin.py': (
        'old-format stand-in: a recording whose header names the module as it was'
    ),
    'tests/test_recording_report.py': (
        'the golden replay is old-format: its scene start names the module as it was'
    ),
    'tests/test_replay_metrics.py': (
        'old-format recordings and the ledger rows keyed by their old paths'
    ),
    'docs/architecture/game_packages.md': (
        'the recipe for moving a game out of the engine: its history lines name where games were'
    ),
    'docs/games/clockwork_keep.md': (
        'describes test_clockwork_keep_after_the_move.py, which asserts the old package is gone'
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
        'pyproject.toml': 'path = "src/glitchygames/examples"\n',
        'docs/guide.md': 'fine\nsee glitchygames/examples/x\n',
        'plans/old.md': 'glitchygames.examples\n',
        'BUGS.md': (
            '## 1. A\n- **Status**: Active\nglitchygames.examples\n'
            '## 2. B\n- **Status**: Resolved\nglitchygames.examples\n'
        ),
        'src/glitchygames/recording_metrics.py': 'glitchygames/examples/x\n',
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
        'pyproject.toml:1: path = "src/glitchygames/examples"',
        'src/engine.py:1: import glitchygames.examples',
    ]
