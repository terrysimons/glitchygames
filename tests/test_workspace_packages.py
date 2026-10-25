"""scripts/workspace_packages.py reads the uv workspace: the one list of member packages."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.workspace_packages import (
    WorkspaceMember,
    source_package_directories,
    workspace_members,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

ROOT_PYPROJECT = """
[project]
name = "glitchygames"

[tool.uv.workspace]
members = ["games/space-game"]
"""
MEMBER_PYPROJECT = """
[project]
name = "space-game"

[project.scripts]
space-game = "space_game:main"

[tool.hatch.build.targets.wheel]
packages = ["space_game"]
"""


def write_workspace(root: Path) -> None:
    """Write a root project with one member, games/space-game."""
    (root / 'pyproject.toml').write_text(ROOT_PYPROJECT, encoding='utf-8')
    member = root / 'games' / 'space-game'
    (member / 'space_game').mkdir(parents=True)
    (member / 'pyproject.toml').write_text(MEMBER_PYPROJECT, encoding='utf-8')


def test_a_member_is_read_from_its_own_pyproject(tmp_path):
    """A member is described by its own pyproject.toml."""
    write_workspace(tmp_path)

    (member,) = workspace_members(project_root=tmp_path)

    assert member == WorkspaceMember(
        directory=tmp_path / 'games' / 'space-game',
        distribution='space-game',
        import_packages=('space_game',),
        console_scripts=('space-game',),
    )
    assert member.package_directories == (tmp_path / 'games' / 'space-game' / 'space_game',)
    assert member.tests_directory == tmp_path / 'games' / 'space-game' / 'tests'
    assert member.replay_fixtures_directory == (
        tmp_path / 'games' / 'space-game' / 'tests' / 'fixtures' / 'replays'
    )


def test_source_packages_are_the_engine_then_every_member(tmp_path):
    """The guards scan the engine, then each member."""
    write_workspace(tmp_path)

    assert source_package_directories(project_root=tmp_path) == [
        tmp_path / 'glitchygames',
        tmp_path / 'games' / 'space-game' / 'space_game',
    ]


def test_a_member_without_its_pyproject_is_refused(tmp_path):
    """A listed member with no pyproject.toml is an error naming it."""
    write_workspace(tmp_path)
    (tmp_path / 'games' / 'space-game' / 'pyproject.toml').unlink()

    with pytest.raises(FileNotFoundError, match='space-game'):
        workspace_members(project_root=tmp_path)


def test_a_project_without_a_workspace_has_no_members(tmp_path):
    """Before any workspace is declared there are no members."""
    (tmp_path / 'pyproject.toml').write_text('[project]\nname = "glitchygames"\n', encoding='utf-8')

    assert workspace_members(project_root=tmp_path) == []
    assert source_package_directories(project_root=tmp_path) == [tmp_path / 'glitchygames']


def test_the_real_repository_is_readable():
    """The repository itself reads, engine first."""
    assert source_package_directories(project_root=PROJECT_ROOT)[0] == (
        PROJECT_ROOT / 'glitchygames'
    )


def test_a_member_declaring_no_wheel_packages_is_refused(tmp_path):
    """A member whose wheel packages are missing would be scanned as nothing: refuse it."""
    write_workspace(tmp_path)
    member_pyproject = tmp_path / 'games' / 'space-game' / 'pyproject.toml'
    member_pyproject.write_text('[project]\nname = "space-game"\n', encoding='utf-8')

    with pytest.raises(ValueError, match=r'space-game.*no .*packages'):
        workspace_members(project_root=tmp_path)


def test_a_declared_package_that_is_not_a_directory_is_refused(tmp_path):
    """A typo in the wheel packages names the member and the missing directory."""
    write_workspace(tmp_path)
    member_pyproject = tmp_path / 'games' / 'space-game' / 'pyproject.toml'
    member_pyproject.write_text(
        MEMBER_PYPROJECT.replace('["space_game"]', '["space_gamme"]'), encoding='utf-8'
    )

    with pytest.raises(FileNotFoundError, match=r'space-game.*space_gamme'):
        workspace_members(project_root=tmp_path)


def test_a_src_layout_package_keeps_its_declared_path(tmp_path):
    """Packages = ["src/space_game"] imports as space_game but lives under src/."""
    write_workspace(tmp_path)
    member_directory = tmp_path / 'games' / 'space-game'
    (member_directory / 'space_game').rmdir()
    (member_directory / 'src' / 'space_game').mkdir(parents=True)
    (member_directory / 'pyproject.toml').write_text(
        MEMBER_PYPROJECT.replace('["space_game"]', '["src/space_game"]'), encoding='utf-8'
    )

    (member,) = workspace_members(project_root=tmp_path)

    assert member.import_packages == ('space_game',)
    assert member.package_directories == (member_directory / 'src' / 'space_game',)


@pytest.mark.parametrize('members', ['"games/space-game"', '[1]'])
def test_workspace_members_that_are_not_a_list_of_strings_are_refused(tmp_path, members):
    """A string must not be iterated character by character."""
    (tmp_path / 'pyproject.toml').write_text(
        f'[project]\nname = "glitchygames"\n\n[tool.uv.workspace]\nmembers = {members}\n',
        encoding='utf-8',
    )

    with pytest.raises(ValueError, match='list of strings'):
        workspace_members(project_root=tmp_path)
