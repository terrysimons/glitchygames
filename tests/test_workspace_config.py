"""Every tool covers every workspace member: no new game slips out of lint, types or coverage."""

from __future__ import annotations

import configparser
import json
import re
import tomllib
from pathlib import Path
from typing import Any

import noxfile
import pytest
import yaml
from scripts.gen_ref_pages import reference_page_path
from scripts.workspace_packages import WorkspaceMember, workspace_members

from glitchygames import logical_names

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEMBERS = workspace_members(project_root=PROJECT_ROOT)
# Each pattern matches a whole string literal first, so a // or ,] inside a string is data
JSONC_COMMENTS = re.compile(r'(?P<string>"(?:\\.|[^"\\])*")|//[^\n]*|/\*.*?\*/', re.DOTALL)
JSONC_TRAILING_COMMAS = re.compile(r'(?P<string>"(?:\\.|[^"\\])*")|,(?=\s*[}\]])')


def root_pyproject() -> dict[str, Any]:
    """The root pyproject.toml."""
    with (PROJECT_ROOT / 'pyproject.toml').open('rb') as pyproject_file:
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


def pyright_configuration() -> dict[str, Any]:
    """pyrightconfig.json, which is JSON with comments and trailing commas (JSONC)."""
    return parse_jsonc(text=(PROJECT_ROOT / 'pyrightconfig.json').read_text(encoding='utf-8'))


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


def mkdocs_configuration() -> dict[str, Any]:
    """mkdocs.yml."""
    loader = MkdocsConfigurationLoader((PROJECT_ROOT / 'mkdocs.yml').read_text(encoding='utf-8'))
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
