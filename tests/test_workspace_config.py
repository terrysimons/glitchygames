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
from scripts.workspace_packages import WorkspaceMember, workspace_members

from glitchygames import logical_names

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MEMBERS = workspace_members(project_root=PROJECT_ROOT)
JSONC_NOISE = re.compile(r'(?P<string>"(?:\\.|[^"\\])*")|//[^\n]*|,(?=\s*[}\]])')


def root_pyproject() -> dict[str, Any]:
    """The root pyproject.toml."""
    with (PROJECT_ROOT / 'pyproject.toml').open('rb') as pyproject_file:
        return tomllib.load(pyproject_file)


def pyright_configuration() -> dict[str, Any]:
    """pyrightconfig.json, which is JSON with comments and trailing commas (JSONC)."""
    text = (PROJECT_ROOT / 'pyrightconfig.json').read_text(encoding='utf-8')
    # Keep string literals whole; drop // comments and commas before a closing bracket
    plain_json = JSONC_NOISE.sub(lambda match: match.group('string') or '', text)
    return json.loads(plain_json)


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
    """ruff, ty, pyright and the nox targets include every member."""
    pyproject = root_pyproject()
    member_path = repository_path(member.directory)
    pyright = pyright_configuration()

    assert member_path in pyproject['tool']['ruff']['src']
    assert f'{member_path}/**/*.py' in pyproject['tool']['ruff']['include']
    assert set(member.import_packages) <= set(
        pyproject['tool']['ruff']['lint']['isort']['known-first-party']
    )
    assert member_path in pyproject['tool']['ty']['src']['include']
    assert member_path in pyproject['tool']['ty']['environment']['root']
    assert member_path in pyright['include']
    assert member_path in noxfile._CODE_DIRS


@pytest.mark.parametrize('member', MEMBERS, ids=member_name)
def test_member_tests_get_the_tests_relaxations(member):
    """A member's tests lint and type-check like tests/ (pre-flight C9, C10)."""
    per_file_ignores = root_pyproject()['tool']['ruff']['lint']['per-file-ignores']
    # src/games/*/tests/**/*.py: one glob per layer (games, demos, apps)
    layer = repository_path(member.directory.parent)
    assert per_file_ignores[f'{layer}/*/tests/**/*.py'] == per_file_ignores['tests/**/*.py']

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
    assert member_path in engine_tests['extraPaths']
    assert 'src' in environments[roots.index(member_path)]['extraPaths']


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
