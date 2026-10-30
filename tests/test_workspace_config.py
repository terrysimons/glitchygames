"""Every tool covers every workspace member: no new game slips out of lint, types or coverage."""

from __future__ import annotations

import ast
import configparser
import importlib.metadata
import json
import re
import sys
import tomllib
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

import noxfile
import pytest
import yaml
from scripts.gen_ref_pages import reference_page_path
from scripts.workspace_packages import (
    ENGINE_PACKAGE,
    WorkspaceMember,
    canonical_distribution_name,
    workspace_members,
)

from glitchygames import logical_names
from tests.ast_scanning import (
    import_bindings,
    imported_module_names,
    member_imports,
    module_name_of,
    path_to_package,
)
from tests.engine_source import ENGINE_DIRECTORY
from tests.workspace_sources import member_import_packages, scanned_source_files

if TYPE_CHECKING:
    from collections.abc import Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Bitmappy's package when it was in the engine (it is the member src/apps/bitmappy now)
BITMAPPY_PACKAGE = 'glitchygames.bitmappy'
# The sprite library's path when it was in the engine, which Bitmappy owns
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

    # deptry ties the root's imports of a member (scripts/ imports the games) to the member's
    # distribution, which the root's extras declare: a member package taken as first party is
    # never checked against them (a game missing from its extra goes unreported), and in the
    # editable dev venv, which records no member's packages, the map is what ties them
    assert not set(member.import_packages) & set(deptry['known_first_party'])
    assert deptry['package_module_name_map'][member.distribution] == list(member.import_packages)
    # Members are projects of their own: the root's dependency check leaves their layer out
    assert repository_path(member.directory.parent) in deptry['extend_exclude']
    for package_directory in member.package_directories:
        assert repository_path(package_directory) in noxfile._SOURCE_PACKAGE_DIRS
    assert repository_path(member.directory) in wily['wily']['path'].split(',')


def test_the_deptry_map_names_the_members_and_pygame_alone():
    """No key is left for a removed member: the map is pygame-ce's and each member's."""
    package_module_name_map = root_pyproject()['tool']['deptry']['package_module_name_map']

    assert sorted(package_module_name_map) == sorted([
        'pygame-ce',
        *(member.distribution for member in MEMBERS),
    ])


def test_nox_installs_and_reinstalls_every_member():
    """noxfile._MEMBER_DISTRIBUTIONS is the workspace (pre-flight C3).

    nox reinstalls each listed member in a reused venv; CI runs nox as a uv tool, which cannot
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


def engine_files_importing_a_member(
    *, project_root: Path, members: Sequence[WorkspaceMember]
) -> list[str]:
    """List every import of a workspace member by the engine's source (decision 10).

    The engine is installed without its games, demos and apps, so it never imports one: a member
    depends on the engine, never the reverse. Every import counts, at any level, and so does a
    string load with a literal name (``importlib.import_module('paddleslap')``).

    Args:
        project_root: The repository.
        members: The workspace's members.

    Returns:
        ``<file>:<line>: <import>`` for each, in scan order (files relative to the engine).

    """
    member_packages = member_import_packages(members=members)
    offences: list[str] = []
    for key, source_path in scanned_source_files(project_root=project_root):
        # Keys under src/ are workspace members; the engine's are relative to its package
        if key.startswith('src/'):
            continue
        tree = ast.parse(source_path.read_text(encoding='utf-8'))
        offences.extend(
            f'{key}:{found.line}: {found.describe()}'
            for found in member_imports(tree=tree, member_packages=member_packages)
        )
    return offences


def test_the_engine_imports_no_member():
    """No engine file imports a game, demo or app."""
    assert engine_files_importing_a_member(project_root=PROJECT_ROOT, members=MEMBERS) == []


# The engine's import package (followed through its own modules) and the package it never reaches
ENGINE_IMPORT_PACKAGE = 'glitchygames'
SCRIPTS_PACKAGE = 'scripts'


def engine_modules_reaching_scripts(*, project_root: Path) -> list[str]:
    """Return each engine module that imports ``scripts.*``, directly or through engine modules.

    The engine is installed without this repository's scripts/ (Part 3, Stage D's constraint:
    "No engine module imports ``scripts.*``"), so none may. Every import counts, at any level,
    relative or by a literal string, and so does a package's ``__init__`` above a module.

    Args:
        project_root: The repository (its ``src/glitchygames/`` is scanned).

    Returns:
        ``<file>: <module> -> ... -> scripts.<name>`` for each, sorted by file.

    """
    source_root = project_root / ENGINE_DIRECTORY.parent
    modules: dict[str, Path] = {
        module_name_of(relative=path.relative_to(source_root)): path
        for path in sorted((project_root / ENGINE_DIRECTORY).rglob('*.py'))
        if '__pycache__' not in path.parts
    }
    graph = {
        module: frozenset(
            imported_module_names(
                tree=ast.parse(path.read_text(encoding='utf-8'), filename=str(path)),
                module=module,
                is_package=path.name == '__init__.py',
                followed=ENGINE_IMPORT_PACKAGE,
                target=SCRIPTS_PACKAGE,
            )
        )
        for module, path in modules.items()
    }
    findings: list[str] = []
    for path, module in sorted((path, module) for module, path in modules.items()):
        chain = path_to_package(graph=graph, module=module, target=SCRIPTS_PACKAGE)
        if chain is not None:
            findings.append(f'{path.relative_to(project_root).as_posix()}: {" -> ".join(chain)}')
    return findings


def test_no_engine_module_reaches_scripts():
    """No engine module imports scripts/, directly or through another engine module."""
    assert engine_modules_reaching_scripts(project_root=PROJECT_ROOT) == []


def test_an_engine_module_reaching_scripts_in_any_way_is_found_with_its_chain(tmp_path):
    """Directly, by a bare import, relatively, through another module or its own package."""
    for relative, source in {
        'scripts/tool.py': 'THING = 1\n',
        'src/glitchygames/__init__.py': '',
        'src/glitchygames/clean.py': 'import os\n',
        'src/glitchygames/helper.py': 'from scripts.tool import THING\n',
        'src/glitchygames/uses_helper.py': 'from glitchygames.helper import THING\n',
        'src/glitchygames/relative.py': 'from .helper import THING\n',
        'src/glitchygames/sub/__init__.py': 'import scripts\n',
        'src/glitchygames/sub/leaf.py': 'VALUE = 1\n',
    }.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding='utf-8')

    assert engine_modules_reaching_scripts(project_root=tmp_path) == [
        'src/glitchygames/helper.py: glitchygames.helper -> scripts.tool',
        (
            'src/glitchygames/relative.py: glitchygames.relative -> glitchygames.helper -> '
            'scripts.tool'
        ),
        'src/glitchygames/sub/__init__.py: glitchygames.sub -> scripts',
        'src/glitchygames/sub/leaf.py: glitchygames.sub.leaf -> glitchygames.sub -> scripts',
        (
            'src/glitchygames/uses_helper.py: glitchygames.uses_helper -> glitchygames.helper -> '
            'scripts.tool'
        ),
    ]


def write_engine_module(*, project_root: Path, source: str) -> list[WorkspaceMember]:
    """Write a repository whose engine holds one module and whose one member is space-game.

    Args:
        project_root: The repository.
        source: The engine module's source (``src/glitchygames/outside.py``).

    Returns:
        Bitmappy (as it is) and the synthetic second member, src/games/space-game.

    """
    engine_directory = project_root / 'src' / 'glitchygames'
    engine_directory.mkdir(parents=True)
    (engine_directory / 'outside.py').write_text(source, encoding='utf-8')
    member_directory = project_root / 'src' / 'games' / 'space-game'
    (member_directory / 'src' / 'space_game').mkdir(parents=True)
    (member_directory / 'src' / 'space_game' / 'ships.py').write_text(
        'import bitmappy\n', encoding='utf-8'
    )
    (member_directory / 'pyproject.toml').write_text(
        '[project]\nname = "space-game"\n\n'
        '[tool.hatch.build.targets.wheel]\npackages = ["src/space_game"]\n',
        encoding='utf-8',
    )
    (project_root / 'pyproject.toml').write_text(
        '[tool.uv.workspace]\nmembers = ["src/games/space-game"]\n', encoding='utf-8'
    )
    bitmappy = next(member for member in MEMBERS if member.distribution == 'bitmappy')
    return [bitmappy, *workspace_members(project_root=project_root)]


@pytest.mark.parametrize(
    ('source', 'expected_offences'),
    [
        ('import bitmappy\n', ['outside.py:1: import bitmappy']),
        ('import bitmappy.utils\n', ['outside.py:1: import bitmappy.utils']),
        ('from bitmappy import main\n', ['outside.py:1: from bitmappy import main']),
        (
            'from bitmappy.editor import BitmapEditorScene as Editor\n',
            ['outside.py:1: from bitmappy.editor import BitmapEditorScene'],
        ),
        ('import space_game\n', ['outside.py:1: import space_game']),
        (
            'def load():\n    from space_game.ships import Ship\n    return Ship\n',
            ['outside.py:2: from space_game.ships import Ship'],
        ),
        (
            "import importlib\n\nGAME = importlib.import_module('space_game.ships')\n",
            ['outside.py:3: import space_game.ships'],
        ),
        ("SHIPS = __import__('space_game')\n", ['outside.py:1: import space_game']),
        ('from . import space_game\nimport glitchygames.sprites\n', []),
    ],
)
def test_the_guard_finds_each_way_the_engine_imports_a_member(tmp_path, source, expected_offences):
    """Each spelling of an import of either member is reported; the members' own are not.

    The synthetic member's own module imports Bitmappy, which is the member's business.
    """
    members = write_engine_module(project_root=tmp_path, source=source)

    assert (
        engine_files_importing_a_member(project_root=tmp_path, members=members) == expected_offences
    )


def engine_files_pointing_at_bitmappys_old_places(*, project_root: Path) -> list[str]:
    """List the engine files that name where Bitmappy was in the engine.

    Bitmappy was the engine's ``glitchygames.bitmappy``, and its sprite library was the engine's
    ``examples/resources/sprites``. Both are its member's now (src/apps/bitmappy); importing the
    old package, or naming the old path, points the engine back into it.

    Args:
        project_root: The repository.

    Returns:
        ``<file>: <what it points at>`` for each offence, in scan order.

    """
    watched_modules = frozenset({'glitchygames', BITMAPPY_PACKAGE})
    offences: list[str] = []
    for key, source_path in scanned_source_files(project_root=project_root):
        # Keys under src/ are workspace members; the engine's are relative to its package
        if key.startswith('src/'):
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
        if BITMAPPY_SPRITE_PATH_SEGMENTS in source:
            offences.append(f'{key}: names the sprite path {BITMAPPY_SPRITE_PATH_SEGMENTS}')
    return offences


def test_the_engine_points_nowhere_bitmappy_was():
    """No engine file imports glitchygames.bitmappy or names Bitmappy's old sprite path."""
    assert engine_files_pointing_at_bitmappys_old_places(project_root=PROJECT_ROOT) == []


@pytest.mark.parametrize(
    ('source', 'expected_offence'),
    [
        (
            'from glitchygames.bitmappy import detect_file_format\n',
            'imports glitchygames.bitmappy.',
        ),
        ('from glitchygames import bitmappy\n', 'imports glitchygames.bitmappy'),
        ('import glitchygames.bitmappy.utils\n', 'imports glitchygames.bitmappy.utils'),
        (
            "PATH = ('examples', 'resources', 'sprites')\n",
            "names the sprite path 'examples', 'resources', 'sprites'",
        ),
    ],
)
def test_the_guard_finds_each_way_to_point_where_bitmappy_was(tmp_path, source, expected_offence):
    """The guard reports an import of the old package (each spelling) and the old sprite path."""
    write_engine_module(project_root=tmp_path, source=source)

    offences = engine_files_pointing_at_bitmappys_old_places(project_root=tmp_path)

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


# A member declares what it imports (decision 10; Task D15 item 2). Adapted from the draft
# plans/2026-10-25-workspace-packages-2-games-demos-apps.md, Task 2 (its l.607-723), for the
# src/ layout


def imported_top_level_modules(*, package_directory: Path) -> set[str]:
    """Return every top-level module a package's files import (absolute imports, at any depth).

    Returns:
        The module names.

    """
    modules: set[str] = set()
    for path in package_directory.rglob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.partition('.')[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules.add(node.module.partition('.')[0])
    return modules


def distributions_by_module(*, members: Sequence[WorkspaceMember]) -> dict[str, set[str]]:
    """Return each importable top-level module's distributions, canonical names.

    The workspace's own packages are named from the workspace: their editable installs record a
    .pth file, not their packages, so importlib.metadata cannot map them.

    Returns:
        Module -> the distributions that install it.

    """
    owners = {
        module: {canonical_distribution_name(name=distribution) for distribution in distributions}
        for module, distributions in importlib.metadata.packages_distributions().items()
    }
    owners[ENGINE_PACKAGE] = {ENGINE_PACKAGE}
    for member in members:
        for package in member.import_packages:
            owners[package] = {member.distribution}
    return owners


def undeclared_imports(*, member: WorkspaceMember, owners: dict[str, set[str]]) -> list[str]:
    """Return what a member imports from a distribution its pyproject.toml does not declare.

    Every import counts: an optional one (in ``try``) or a type-only one (under
    ``if TYPE_CHECKING:``) too, since the member installed alone may still reach it (a type
    checker of the member, a feature turned on); declare it, or leave it out of the package.

    Returns:
        One line per undeclared module.

    """
    problems: list[str] = []
    for package_directory in member.package_directories:
        for module in sorted(imported_top_level_modules(package_directory=package_directory)):
            if module in sys.stdlib_module_names or module in member.import_packages:
                continue
            distributions = owners.get(module, set())
            if not distributions & set(member.dependencies):
                installed_by = ', '.join(sorted(distributions)) or 'no installed distribution'
                problems.append(
                    f'{member.distribution} imports {module} ({installed_by}) undeclared'
                )
    return problems


@pytest.mark.parametrize('member', MEMBERS, ids=member_name)
def test_every_member_declares_what_it_imports(member):
    """A member installed alone has every package it imports (the workspace hides a gap)."""
    assert undeclared_imports(member=member, owners=distributions_by_module(members=MEMBERS)) == []


@pytest.mark.parametrize('member', MEMBERS, ids=member_name)
def test_every_member_depends_on_the_engine_with_a_floor(member):
    """``glitchygames>=<the engine's version>``: no member resolves an older engine (#224 item 45).

    The floor is the engine's own version, read from the root pyproject.toml, so a version bump
    fails here until every member's floor follows it.
    """
    pyproject = tomllib.loads((member.directory / 'pyproject.toml').read_text(encoding='utf-8'))
    engine_version = root_pyproject()['project']['version']

    assert f'glitchygames>={engine_version}' in pyproject['project']['dependencies']


def test_an_undeclared_import_is_found(tmp_path):
    """A planted member importing pydantic while declaring only the engine and pygame is caught."""
    package_directory = tmp_path / 'space_game'
    (package_directory / 'levels').mkdir(parents=True)
    (package_directory / 'game.py').write_text(
        'import os\nimport pygame\nfrom space_game import levels\nfrom . import levels\n',
        encoding='utf-8',
    )
    (package_directory / 'levels' / 'first.py').write_text(
        'def load():\n    from pydantic import BaseModel\n    return BaseModel\n',
        encoding='utf-8',
    )
    member = WorkspaceMember(
        directory=tmp_path,
        distribution='space-game',
        import_packages=('space_game',),
        console_scripts=(),
        dependencies=('glitchygames', 'pygame-ce'),
    )

    problems = undeclared_imports(member=member, owners=distributions_by_module(members=MEMBERS))

    assert problems == ['space-game imports pydantic (pydantic) undeclared']


def test_an_import_no_distribution_installs_is_found(tmp_path):
    """A module nothing installed provides is named as such."""
    package_directory = tmp_path / 'space_game'
    package_directory.mkdir()
    (package_directory / 'game.py').write_text('import not_installed_anywhere\n', encoding='utf-8')
    member = WorkspaceMember(
        directory=tmp_path,
        distribution='space-game',
        import_packages=('space_game',),
        console_scripts=(),
        dependencies=('glitchygames',),
    )

    problems = undeclared_imports(member=member, owners=distributions_by_module(members=MEMBERS))

    assert problems == [
        'space-game imports not_installed_anywhere (no installed distribution) undeclared'
    ]


def test_an_optional_or_type_only_import_must_be_declared_too(tmp_path):
    """Every import counts, a guarded or a TYPE_CHECKING one too: installed alone, it may run."""
    package_directory = tmp_path / 'space_game'
    package_directory.mkdir()
    (package_directory / 'game.py').write_text(
        'from typing import TYPE_CHECKING\n'
        'if TYPE_CHECKING:\n'
        '    from pydantic import BaseModel\n'
        'try:\n'
        '    import numpy\n'
        'except ImportError:\n'
        '    numpy = None\n',
        encoding='utf-8',
    )
    member = WorkspaceMember(
        directory=tmp_path,
        distribution='space-game',
        import_packages=('space_game',),
        console_scripts=(),
        dependencies=('glitchygames',),
    )

    assert undeclared_imports(member=member, owners=distributions_by_module(members=MEMBERS)) == [
        'space-game imports numpy (numpy) undeclared',
        'space-game imports pydantic (pydantic) undeclared',
    ]
