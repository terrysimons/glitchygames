"""Every tool covers every workspace member: no new game slips out of lint, types or coverage."""

from __future__ import annotations

import ast
import configparser
import json
import re
import tomllib
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

import noxfile
import pytest
import yaml
from scripts.gen_ref_pages import reference_page_path
from scripts.workspace_packages import WorkspaceMember, workspace_members

from glitchygames import logical_names
from tests.ast_scanning import import_bindings, scanned_source_files

if TYPE_CHECKING:
    from collections.abc import Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BITMAPPY_PACKAGE = 'glitchygames.bitmappy'
# Bitmappy's package since it became a workspace member (src/apps/bitmappy)
BITMAPPY_MEMBER_PACKAGE = 'bitmappy'
# The sprite library's path inside the engine, which Bitmappy owns
BITMAPPY_SPRITE_PATH_SEGMENTS = "'examples', 'resources', 'sprites'"
MEMBERS = workspace_members(project_root=PROJECT_ROOT)
# Each pattern matches a whole string literal first, so a // or ,] inside a string is data
JSONC_COMMENTS = re.compile(r'(?P<string>"(?:\\.|[^"\\])*")|//[^\n]*|/\*.*?\*/', re.DOTALL)
JSONC_TRAILING_COMMAS = re.compile(r'(?P<string>"(?:\\.|[^"\\])*")|,(?=\s*[}\]])')


def root_pyproject(*, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """The root pyproject.toml."""
    with (project_root / 'pyproject.toml').open('rb') as pyproject_file:
        return tomllib.load(pyproject_file)


def parse_jsonc(*, text: str) -> dict[str, Any]:
    """Parse JSON with comments and trailing commas (JSONC), as pyright reads its configuration.

    Args:
        text: The JSONC document.

    Returns:
        The parsed object.

    """
    # Comments first (a comma before a comment is trailing only once the comment is gone)
    without_comments = JSONC_COMMENTS.sub(lambda match: match.group('string') or ' ', text)
    plain_json = JSONC_TRAILING_COMMAS.sub(
        lambda match: match.group('string') or '', without_comments
    )
    return json.loads(plain_json)


def pyright_configuration(*, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """pyrightconfig.json, which is JSON with comments and trailing commas (JSONC)."""
    return parse_jsonc(text=(project_root / 'pyrightconfig.json').read_text(encoding='utf-8'))


def repository_path(path: Path) -> str:
    """A path as the configuration files spell it: relative, with forward slashes."""
    return path.relative_to(PROJECT_ROOT).as_posix()


def member_name(member: WorkspaceMember) -> str:
    """A member's test id."""
    return member.distribution


@pytest.mark.parametrize('member', MEMBERS, ids=member_name)
def test_coverage_measures_every_member_package(member):
    """Coverage sources, paths and pytest's --cov name every member package."""
    pyproject = root_pyproject()
    sources = pyproject['tool']['coverage']['run']['source']
    paths = pyproject['tool']['coverage']['paths']
    addopts = pyproject['tool']['pytest']['ini_options']['addopts'].split()

    for package, package_directory in zip(
        member.import_packages, member.package_directories, strict=True
    ):
        assert package in sources
        assert f'--cov={package}' in addopts
        # The installed copy is reported as the member's source under src/ (Task 7's mapping)
        assert paths[package] == [repository_path(package_directory), f'*/site-packages/{package}']


@pytest.mark.parametrize('member', MEMBERS, ids=member_name)
def test_pytest_collects_every_members_tests(member):
    """The testpaths of pytest include every member's tests."""
    testpaths = root_pyproject()['tool']['pytest']['ini_options']['testpaths']

    assert repository_path(member.tests_directory) in testpaths


@pytest.mark.parametrize('member', MEMBERS, ids=member_name)
def test_lint_and_type_checks_cover_every_member(member):
    """ruff, ty, pyright and the nox targets include every member.

    Imports resolve from the member's import roots: its own directory, or its src/ in a src
    layout (src/games/brave-adventurer/src); the files checked are the whole member's.
    """
    pyproject = root_pyproject()
    member_path = repository_path(member.directory)
    pyright = pyright_configuration()

    for import_root in member.import_roots:
        assert repository_path(import_root) in pyproject['tool']['ruff']['src']
        assert repository_path(import_root) in pyproject['tool']['ty']['environment']['root']
    assert f'{member_path}/**/*.py' in pyproject['tool']['ruff']['include']
    assert set(member.import_packages) <= set(
        pyproject['tool']['ruff']['lint']['isort']['known-first-party']
    )
    assert member_path in pyproject['tool']['ty']['src']['include']
    assert member_path in pyright['include']
    assert member_path in noxfile._CODE_DIRS


@pytest.mark.parametrize('member', MEMBERS, ids=member_name)
def test_member_tests_get_the_tests_relaxations(member):
    """A member's tests lint and type-check like tests/ (pre-flight C9, C10)."""
    per_file_ignores = root_pyproject()['tool']['ruff']['lint']['per-file-ignores']
    # src/games/*/tests/**/*.py: one glob per layer (games, demos, apps)
    layer = repository_path(member.directory.parent)
    assert per_file_ignores[f'{layer}/*/tests/**/*.py'] == per_file_ignores['tests/**/*.py']
    # ty leaves tests out (it misreads mocker.patch), a member's as tests/ (pre-flight C12)
    assert f'{layer}/*/tests' in root_pyproject()['tool']['ty']['src']['exclude']

    environments = pyright_configuration()['executionEnvironments']
    roots = [environment['root'] for environment in environments]
    tests_path = repository_path(member.tests_directory)
    member_path = repository_path(member.directory)
    # The member's tests environment comes before the member's own (pyright takes the first match)
    assert roots.index(tests_path) < roots.index(member_path)
    member_tests = {
        key: value for key, value in environments[roots.index(tests_path)].items() if key != 'root'
    }
    engine_tests = {
        key: value for key, value in environments[roots.index('tests')].items() if key != 'root'
    }
    assert member_tests == engine_tests
    # Not a package (it would shadow tests/), so ruff is told it is a namespace on purpose
    assert tests_path in root_pyproject()['tool']['ruff']['namespace-packages']
    member_extra_paths = environments[roots.index(member_path)]['extraPaths']
    assert 'src' in member_extra_paths
    for import_root in member.import_roots:
        assert repository_path(import_root) in engine_tests['extraPaths']
        # A src layout's packages are not at the member's root, where pyright looks first
        if import_root != member.directory:
            assert repository_path(import_root) in member_extra_paths


@pytest.mark.parametrize('member', MEMBERS, ids=member_name)
def test_dependency_dead_code_security_and_complexity_scans_cover_every_member(member):
    """deptry, vulture, bandit and wily (pre-flight A7, C11)."""
    pyproject = root_pyproject()
    deptry = pyproject['tool']['deptry']
    wily = configparser.ConfigParser()
    wily.read(PROJECT_ROOT / 'wily.cfg', encoding='utf-8')

    assert set(member.import_packages) <= set(deptry['known_first_party'])
    # Members are projects of their own: the root's dependency check leaves their layer out
    assert repository_path(member.directory.parent) in deptry['extend_exclude']
    for package_directory in member.package_directories:
        assert repository_path(package_directory) in noxfile._SOURCE_PACKAGE_DIRS
    assert repository_path(member.directory) in wily['wily']['path'].split(',')


def test_nox_installs_and_reinstalls_every_member():
    """noxfile._MEMBER_DISTRIBUTIONS is the workspace (pre-flight C3).

    nox reinstalls each listed member in a reused venv; CI runs nox through uvx, which cannot
    import scripts/workspace_packages.py, so the noxfile lists them and this keeps the list equal.
    """
    assert [member.distribution for member in MEMBERS] == noxfile._MEMBER_DISTRIBUTIONS


class MkdocsConfigurationLoader(yaml.SafeLoader):
    """Reads mkdocs.yml, its ``!!python/name:`` tags (pymdownx's fence formats) read as None."""


MkdocsConfigurationLoader.add_multi_constructor(
    'tag:yaml.org,2002:python/name:', lambda _loader, _suffix, _node: None
)


def mkdocs_configuration(*, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """mkdocs.yml."""
    loader = MkdocsConfigurationLoader((project_root / 'mkdocs.yml').read_text(encoding='utf-8'))
    try:
        return loader.get_single_data()
    finally:
        loader.dispose()


def navigation_pages(*, entries: list[Any]) -> set[str]:
    """Every page a mkdocs nav names, at any depth."""
    pages: set[str] = set()
    for entry in entries:
        values = entry.values() if isinstance(entry, dict) else [entry]
        for value in values:
            if isinstance(value, list):
                pages |= navigation_pages(entries=value)
            else:
                pages.add(value)
    return pages


@pytest.mark.parametrize('member', MEMBERS, ids=member_name)
def test_the_docs_render_and_list_every_members_api_reference(member):
    """gen-files runs scripts/gen_ref_pages.py, and the nav names each member package's page."""
    configuration = mkdocs_configuration()
    plugins = {
        name: options
        for plugin in configuration['plugins']
        for name, options in (plugin.items() if isinstance(plugin, dict) else [(plugin, {})])
    }
    pages = navigation_pages(entries=configuration['nav'])

    assert plugins['gen-files'] == {'scripts': ['scripts/gen_ref_pages.py']}
    for import_package in member.import_packages:
        assert reference_page_path(import_package=import_package) in pages


@pytest.mark.parametrize('member', MEMBERS, ids=member_name)
def test_a_plain_uv_sync_keeps_every_member_installed(member):
    """The root's dev group, which a plain `uv sync` installs, names every member (workspace).

    `uv sync` is exact: without this it uninstalls the members `--all-packages` installed, and
    their console scripts with them (uv's workspace docs: a member the root depends on through a
    `workspace = true` source is installed with the root).
    """
    pyproject = root_pyproject()

    assert member.distribution in pyproject['dependency-groups']['dev']
    assert pyproject['tool']['uv']['sources'][member.distribution] == {'workspace': True}


@pytest.mark.parametrize('member', MEMBERS, ids=member_name)
def test_a_members_console_scripts_are_its_own(member):
    """The root project no longer declares a script a member does (pre-flight A7)."""
    root_scripts = root_pyproject()['project']['scripts']

    assert not set(member.console_scripts) & set(root_scripts)


@pytest.mark.parametrize('member', MEMBERS, ids=member_name)
def test_the_engine_knows_every_members_layer(member):
    """Recordings name a member's classes by its layer (glitchygames/logical_names.py)."""
    for package in member.import_packages:
        assert logical_names.MEMBER_LAYERS[package] == member.layer


def test_the_engine_knows_no_layer_the_workspace_lacks():
    """Not parametrized: it holds with no members too ({} == {})."""
    workspace_packages = {package for member in MEMBERS for package in member.import_packages}

    assert set(logical_names.MEMBER_LAYERS) == workspace_packages


def test_each_layer_is_an_extra_naming_exactly_its_members():
    """`glitchygames[games]`, `[demos]` and `[apps]` install exactly that layer's members.

    Not parametrized: a layer with no member yet is an empty extra, so this holds before its
    first member moves too.
    """
    extras = root_pyproject()['project']['optional-dependencies']

    for layer in logical_names.LAYERS:
        members_in_layer = sorted(
            member.distribution for member in MEMBERS if member.layer == layer
        )
        assert sorted(extras[layer]) == members_in_layer, layer


def test_jsonc_trailing_comma_before_a_comment_is_dropped():
    """A comma, then a // comment, then the closing bracket: the comma is still trailing."""
    text = '{\n  "x": 1, // note\n  "y": [1, 2, // more\n  ],\n}'

    assert parse_jsonc(text=text) == {'x': 1, 'y': [1, 2]}


def test_jsonc_block_comments_are_dropped():
    """/* */ comments, on one line or several, are removed."""
    text = '{"x": 1, /* one */ "y": 2, /* two\n lines */ }'

    assert parse_jsonc(text=text) == {'x': 1, 'y': 2}


def test_jsonc_comment_markers_and_brackets_inside_strings_are_kept():
    """A URL's // and a string ending in ,] are data, not comments or trailing commas."""
    text = '{"url": "https://example.com/a", "tail": "a,]", "block": "/* kept */"}'

    assert parse_jsonc(text=text) == {
        'url': 'https://example.com/a',
        'tail': 'a,]',
        'block': '/* kept */',
    }


def test_jsonc_escaped_quotes_inside_strings_do_not_end_them():
    """A string holding an escaped quote and then // stays whole."""
    text = '{"quoted": "say \\"hi\\" // not a comment", "slash": "a\\\\"} // real comment'

    assert parse_jsonc(text=text) == {'quoted': 'say "hi" // not a comment', 'slash': 'a\\'}


def test_the_real_pyright_configuration_parses():
    """The repository's own pyrightconfig.json reads, with its known settings."""
    configuration = pyright_configuration()

    assert configuration['typeCheckingMode'] == 'strict'
    assert configuration['reportImplicitStringConcatenation'] is False
    assert 'src/glitchygames' in configuration['include']
    assert 'tests' in [
        environment['root'] for environment in configuration['executionEnvironments']
    ]


def absolute_imported_module_names(*, tree: ast.Module) -> list[str]:
    """List the modules a module imports absolutely, in walk order (relative imports left out).

    Args:
        tree: The parsed module.

    Returns:
        Each ``import`` alias's module and each absolute ``from ... import``'s module.

    """
    module_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            module_names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
            module_names.append(node.module)
    return module_names


def engine_files_pointing_into_bitmappy(*, project_root: Path) -> list[str]:
    """List the engine files (outside bitmappy/) that import Bitmappy or name its sprite path.

    Bitmappy is imported as ``glitchygames.bitmappy`` (where it was) or as the member's own
    top-level ``bitmappy`` (where it is): both are offences.

    Args:
        project_root: The repository.

    Returns:
        ``<file>: <what it points at>`` for each offence, in scan order.

    """
    watched_modules = frozenset({'glitchygames', BITMAPPY_PACKAGE})
    offences: list[str] = []
    for key, source_path in scanned_source_files(project_root=project_root):
        # Keys under src/ are workspace members; the engine's are relative to its package
        if key.startswith(('src/', 'bitmappy/')):
            continue
        source = source_path.read_text(encoding='utf-8')
        tree = ast.parse(source)
        bindings = import_bindings(tree=tree, watched_modules=watched_modules)
        offences.extend(
            f'{key}: imports {qualified}'
            for qualified in sorted(set(bindings.values()))
            if qualified.startswith(BITMAPPY_PACKAGE)
        )
        # `import glitchygames.bitmappy.utils` binds only `glitchygames`, so read those directly
        offences.extend(
            f'{key}: imports {alias.name}'
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
            if alias.name.startswith(BITMAPPY_PACKAGE)
        )
        # The member's package, in any spelling (`from bitmappy.editor import ...` too)
        offences.extend(
            f'{key}: imports {module_name}'
            for module_name in absolute_imported_module_names(tree=tree)
            if module_name.split('.')[0] == BITMAPPY_MEMBER_PACKAGE
        )
        if BITMAPPY_SPRITE_PATH_SEGMENTS in source:
            offences.append(f'{key}: names the sprite path {BITMAPPY_SPRITE_PATH_SEGMENTS}')
    return offences


def test_the_engine_outside_bitmappy_points_nowhere_into_it():
    """No engine file outside bitmappy/ imports Bitmappy or names its sprite library's path."""
    assert engine_files_pointing_into_bitmappy(project_root=PROJECT_ROOT) == []


@pytest.mark.parametrize(
    ('source', 'expected_offence'),
    [
        (
            'from glitchygames.bitmappy import detect_file_format\n',
            'imports glitchygames.bitmappy.',
        ),
        ('from glitchygames import bitmappy\n', 'imports glitchygames.bitmappy'),
        ('import glitchygames.bitmappy.utils\n', 'imports glitchygames.bitmappy.utils'),
        ('import bitmappy\n', 'imports bitmappy'),
        ('import bitmappy.utils\n', 'imports bitmappy.utils'),
        ('from bitmappy import main\n', 'imports bitmappy'),
        ('from bitmappy.editor import BitmapEditorScene\n', 'imports bitmappy.editor'),
        (
            "PATH = ('examples', 'resources', 'sprites')\n",
            "names the sprite path 'examples', 'resources', 'sprites'",
        ),
    ],
)
def test_the_guard_finds_each_way_to_point_into_bitmappy(tmp_path, source, expected_offence):
    """The guard reports an import (each spelling, either package) and the sprite path.

    It spares bitmappy/ (where the package was, inside the engine).
    """
    engine_directory = tmp_path / 'src' / 'glitchygames'
    (engine_directory / 'bitmappy').mkdir(parents=True)
    (engine_directory / 'bitmappy' / 'inside.py').write_text(source, encoding='utf-8')
    (engine_directory / 'outside.py').write_text(source, encoding='utf-8')
    (tmp_path / 'pyproject.toml').write_text(
        '[tool.uv.workspace]\nmembers = []\n', encoding='utf-8'
    )

    offences = engine_files_pointing_into_bitmappy(project_root=tmp_path)

    assert len(offences) == 1
    assert offences[0].startswith('outside.py: ')
    assert expected_offence in offences[0]


def test_every_member_keeps_its_packages_under_src():
    """Every member's import packages are under <member>/src/ (Brave Adventurer's precedent)."""
    assert members_with_packages_outside_src(members=MEMBERS) == []


def members_with_packages_outside_src(*, members: Sequence[WorkspaceMember]) -> list[str]:
    """List each member package directory that is not under its member's ``src/``.

    Args:
        members: The workspace's members.

    Returns:
        ``<distribution>: <package directory below the member>`` for each offence, in member order.

    """
    return [
        f'{member.distribution}: {package_directory.relative_to(member.directory).as_posix()}'
        for member in members
        for package_directory in member.package_directories
        if not package_directory.is_relative_to(member.directory / 'src')
    ]


def test_the_src_layout_guard_names_each_package_outside_src(tmp_path):
    """A flat package is reported with its distribution; src and mixed members are judged apart."""
    flat_member = WorkspaceMember(
        directory=tmp_path / 'src' / 'games' / 'flat-game',
        distribution='flat-game',
        import_packages=('flat_game',),
        console_scripts=(),
    )
    src_member = WorkspaceMember(
        directory=tmp_path / 'src' / 'games' / 'src-game',
        distribution='src-game',
        import_packages=('src_game',),
        package_relative_paths=(Path('src') / 'src_game',),
        console_scripts=(),
    )
    mixed_member = WorkspaceMember(
        directory=tmp_path / 'src' / 'games' / 'mixed-game',
        distribution='mixed-game',
        import_packages=('mixed_game', 'mixed_game_extra'),
        package_relative_paths=(Path('mixed_game'), Path('src') / 'mixed_game_extra'),
        console_scripts=(),
    )

    offences = members_with_packages_outside_src(members=[flat_member, src_member, mixed_member])

    assert offences == ['flat-game: flat_game', 'mixed-game: mixed_game']


def load_noxfile_source_package_directories(*, project_root: Path) -> list[str]:
    """Read ``_SOURCE_PACKAGE_DIRS`` from the project's noxfile.py without executing it.

    Importing a second copy of a noxfile registers its sessions again (a FutureWarning, an error
    here), and the synthetic project in a test has no importable noxfile, so the list literal is
    read from the syntax tree.

    Args:
        project_root: The repository.

    Returns:
        The noxfile's list.

    Raises:
        LookupError: If the noxfile assigns no ``_SOURCE_PACKAGE_DIRS``.

    """
    tree = ast.parse((project_root / 'noxfile.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == '_SOURCE_PACKAGE_DIRS'
        ):
            return list(ast.literal_eval(node.value))
    message = 'noxfile.py assigns no _SOURCE_PACKAGE_DIRS'
    raise LookupError(message)


def configuration_lists_naming_member_paths(
    *, project_root: Path
) -> list[tuple[str, bool, list[str]]]:
    """Read the root configuration lists that name member paths.

    Args:
        project_root: The repository.

    Returns:
        ``(where, takes_member_directory, entries)`` for each list: ``where`` names the file and
        key; ``takes_member_directory`` is whether the member directory itself is a valid entry.

    """
    pyproject = root_pyproject(project_root=project_root)
    coverage_paths: list[str] = [
        entry for entries in pyproject['tool']['coverage']['paths'].values() for entry in entries
    ]
    configuration_lists: list[tuple[str, bool, list[str]]] = [
        ('pyproject.toml [tool.ruff] src', False, pyproject['tool']['ruff']['src']),
        (
            'pyproject.toml [tool.ty.environment] root',
            False,
            pyproject['tool']['ty']['environment']['root'],
        ),
        ('pyproject.toml [tool.coverage.paths]', False, coverage_paths),
        (
            'noxfile.py _SOURCE_PACKAGE_DIRS',
            False,
            load_noxfile_source_package_directories(project_root=project_root),
        ),
    ]
    environments = pyright_configuration(project_root=project_root)['executionEnvironments']
    configuration_lists.append((
        'pyrightconfig.json executionEnvironments root',
        True,
        [environment['root'] for environment in environments],
    ))
    configuration_lists.extend(
        (
            f'pyrightconfig.json executionEnvironments[{environment["root"]}] extraPaths',
            False,
            environment.get('extraPaths', []),
        )
        for environment in environments
    )
    mkdocs = mkdocs_configuration(project_root=project_root)
    configuration_lists.extend(
        (
            'mkdocs.yml plugins mkdocstrings handlers python paths',
            False,
            plugin['mkdocstrings']['handlers']['python']['paths'],
        )
        for plugin in mkdocs['plugins']
        if isinstance(plugin, dict) and 'mkdocstrings' in plugin
    )
    return configuration_lists


def stale_member_paths_in_configuration(
    *, project_root: Path, members: Sequence[WorkspaceMember]
) -> list[str]:
    """List the configuration entries inside a member that the workspace does not derive.

    An entry inside a member's directory is derived when it is one of that member's import roots,
    package directories or tests directory, or (in a list that takes it) the member directory.

    Args:
        project_root: The repository, whose configuration files are read.
        members: The workspace's members, with directories under ``project_root``.

    Returns:
        ``<file and key>: <entry>`` for each stale entry, in list order.

    """
    stale_entries: list[str] = []
    for where, takes_member_directory, entries in configuration_lists_naming_member_paths(
        project_root=project_root
    ):
        for entry in entries:
            entry_path = PurePosixPath(entry)
            for member in members:
                member_path = PurePosixPath(member.directory.relative_to(project_root).as_posix())
                if entry_path != member_path and member_path not in entry_path.parents:
                    continue
                derived = {
                    *(
                        path.relative_to(project_root).as_posix()
                        for path in (
                            *member.import_roots,
                            *member.package_directories,
                            member.tests_directory,
                        )
                    ),
                    *([member_path.as_posix()] if takes_member_directory else []),
                }
                if entry not in derived:
                    stale_entries.append(f'{where}: {entry}')
    return stale_entries


def test_no_configuration_entry_names_a_member_path_the_workspace_does_not_derive():
    """Every ruff/ty/pyright/nox/mkdocs/coverage entry inside a member is one it derives.

    A flat path left beside the new src one (src/games/clockwork-keep next to
    src/games/clockwork-keep/src) would otherwise slip through every guard above, which only
    check that the right entries are present.
    """
    assert stale_member_paths_in_configuration(project_root=PROJECT_ROOT, members=MEMBERS) == []


def write_synthetic_workspace(*, project_root: Path, stale: bool) -> list[WorkspaceMember]:
    """Write a one-member src-layout project's configuration, optionally with stale entries.

    Args:
        project_root: Where to write it.
        stale: Whether to plant the old flat path (the member directory) in each list.

    Returns:
        The project's members.

    """
    member = WorkspaceMember(
        directory=project_root / 'src' / 'games' / 'fake-game',
        distribution='fake-game',
        import_packages=('fake_game',),
        package_relative_paths=(Path('src') / 'fake_game',),
        console_scripts=(),
    )
    member_path = 'src/games/fake-game'
    derived = f'{member_path}/src'
    old = member_path if stale else f'{member_path}/src'
    (project_root / 'pyproject.toml').write_text(
        '[tool.ruff]\n'
        f'src = ["src", "{derived}", "{old}"]\n'
        '[tool.ty.environment]\n'
        f'root = ["src", "{derived}", "{old}"]\n'
        '[tool.coverage.paths]\n'
        f'fake_game = ["{derived}/fake_game", "*/site-packages/fake_game", "{old}/fake_game"]\n',
        encoding='utf-8',
    )
    (project_root / 'pyrightconfig.json').write_text(
        json.dumps({
            'executionEnvironments': [
                {'root': f'{member_path}/tests', 'extraPaths': ['src', derived, old]},
                {'root': member_path, 'extraPaths': ['src', derived]},
            ]
        }),
        encoding='utf-8',
    )
    (project_root / 'noxfile.py').write_text(
        f'_SOURCE_PACKAGE_DIRS = ["src/glitchygames", "{derived}/fake_game", "{old}/fake_game"]\n',
        encoding='utf-8',
    )
    (project_root / 'mkdocs.yml').write_text(
        'plugins:\n'
        '  - search\n'
        '  - mkdocstrings:\n'
        '      handlers:\n'
        '        python:\n'
        f'          paths: [src, {derived}, {old}]\n',
        encoding='utf-8',
    )
    return [member]


def test_the_stale_path_guard_passes_a_configuration_that_names_only_derived_paths(tmp_path):
    """Import roots, package directories, the tests directory and the pyright member root pass."""
    members = write_synthetic_workspace(project_root=tmp_path, stale=False)

    assert stale_member_paths_in_configuration(project_root=tmp_path, members=members) == []


def test_the_stale_path_guard_names_the_file_and_key_of_each_planted_flat_path(tmp_path):
    """The old flat member directory (and a path under it) is reported in every list it is in."""
    members = write_synthetic_workspace(project_root=tmp_path, stale=True)

    stale_entries = stale_member_paths_in_configuration(project_root=tmp_path, members=members)

    tests_extra_paths = (
        'pyrightconfig.json executionEnvironments[src/games/fake-game/tests] extraPaths'
    )
    assert stale_entries == [
        'pyproject.toml [tool.ruff] src: src/games/fake-game',
        'pyproject.toml [tool.ty.environment] root: src/games/fake-game',
        'pyproject.toml [tool.coverage.paths]: src/games/fake-game/fake_game',
        'noxfile.py _SOURCE_PACKAGE_DIRS: src/games/fake-game/fake_game',
        f'{tests_extra_paths}: src/games/fake-game',
        'mkdocs.yml plugins mkdocstrings handlers python paths: src/games/fake-game',
    ]


def test_a_noxfile_without_the_source_package_list_is_an_error(tmp_path):
    """The guard refuses to pass on a list it cannot find."""
    (tmp_path / 'noxfile.py').write_text('_CODE_DIRS = []\n', encoding='utf-8')

    with pytest.raises(LookupError, match='_SOURCE_PACKAGE_DIRS'):
        load_noxfile_source_package_directories(project_root=tmp_path)
