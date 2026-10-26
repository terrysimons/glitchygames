"""scripts/workspace_packages.py reads the uv workspace: the one list of member packages."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.git_checkout import run_git as scripts_run_git
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
members = ["src/games/space-game"]
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
    """Write a root project with one member, src/games/space-game."""
    (root / 'pyproject.toml').write_text(ROOT_PYPROJECT, encoding='utf-8')
    member = root / 'src' / 'games' / 'space-game'
    (member / 'space_game').mkdir(parents=True)
    (member / 'pyproject.toml').write_text(MEMBER_PYPROJECT, encoding='utf-8')


def test_a_member_is_read_from_its_own_pyproject(tmp_path):
    """A member is described by its own pyproject.toml."""
    write_workspace(tmp_path)

    (member,) = workspace_members(project_root=tmp_path)

    assert member == WorkspaceMember(
        directory=tmp_path / 'src' / 'games' / 'space-game',
        distribution='space-game',
        import_packages=('space_game',),
        console_scripts=('space-game',),
    )
    assert member.package_directories == (tmp_path / 'src' / 'games' / 'space-game' / 'space_game',)
    assert member.tests_directory == tmp_path / 'src' / 'games' / 'space-game' / 'tests'
    assert member.replay_fixtures_directory == (
        tmp_path / 'src' / 'games' / 'space-game' / 'tests' / 'fixtures' / 'replays'
    )


def test_source_packages_are_the_engine_then_every_member(tmp_path):
    """The guards scan the engine, then each member."""
    write_workspace(tmp_path)

    assert source_package_directories(project_root=tmp_path) == [
        tmp_path / 'src' / 'glitchygames',
        tmp_path / 'src' / 'games' / 'space-game' / 'space_game',
    ]


def test_a_member_without_its_pyproject_is_refused(tmp_path):
    """A listed member with no pyproject.toml is an error naming it."""
    write_workspace(tmp_path)
    (tmp_path / 'src' / 'games' / 'space-game' / 'pyproject.toml').unlink()

    with pytest.raises(FileNotFoundError, match='space-game'):
        workspace_members(project_root=tmp_path)


def test_a_project_without_a_workspace_has_no_members(tmp_path):
    """Before any workspace is declared there are no members."""
    (tmp_path / 'pyproject.toml').write_text('[project]\nname = "glitchygames"\n', encoding='utf-8')

    assert workspace_members(project_root=tmp_path) == []
    assert source_package_directories(project_root=tmp_path) == [tmp_path / 'src' / 'glitchygames']


def test_the_real_repository_is_readable():
    """The repository itself reads, engine first."""
    assert source_package_directories(project_root=PROJECT_ROOT)[0] == (
        PROJECT_ROOT / 'src' / 'glitchygames'
    )


def test_a_member_declaring_no_wheel_packages_is_refused(tmp_path):
    """A member whose wheel packages are missing would be scanned as nothing: refuse it."""
    write_workspace(tmp_path)
    member_pyproject = tmp_path / 'src' / 'games' / 'space-game' / 'pyproject.toml'
    member_pyproject.write_text('[project]\nname = "space-game"\n', encoding='utf-8')

    with pytest.raises(ValueError, match=r'space-game.*no .*packages'):
        workspace_members(project_root=tmp_path)


def test_a_declared_package_that_is_not_a_directory_is_refused(tmp_path):
    """A typo in the wheel packages names the member and the missing directory."""
    write_workspace(tmp_path)
    member_pyproject = tmp_path / 'src' / 'games' / 'space-game' / 'pyproject.toml'
    member_pyproject.write_text(
        MEMBER_PYPROJECT.replace('["space_game"]', '["space_gamme"]'), encoding='utf-8'
    )

    with pytest.raises(FileNotFoundError, match=r'space-game.*space_gamme'):
        workspace_members(project_root=tmp_path)


def test_a_src_layout_package_keeps_its_declared_path(tmp_path):
    """Packages = ["src/space_game"] imports as space_game but lives under src/."""
    write_workspace(tmp_path)
    member_directory = tmp_path / 'src' / 'games' / 'space-game'
    (member_directory / 'space_game').rmdir()
    (member_directory / 'src' / 'space_game').mkdir(parents=True)
    (member_directory / 'pyproject.toml').write_text(
        MEMBER_PYPROJECT.replace('["space_game"]', '["src/space_game"]'), encoding='utf-8'
    )

    (member,) = workspace_members(project_root=tmp_path)

    assert member.import_packages == ('space_game',)
    assert member.package_directories == (member_directory / 'src' / 'space_game',)
    assert member.import_roots == (member_directory / 'src',)


def test_a_flat_members_import_root_is_its_directory(tmp_path):
    """Packages = ["space_game"] at the member's root: imports resolve from the member itself."""
    write_workspace(tmp_path)

    (member,) = workspace_members(project_root=tmp_path)

    assert member.import_roots == (tmp_path / 'src' / 'games' / 'space-game',)


def test_a_src_layout_with_several_packages_has_one_import_root(tmp_path):
    """Two packages under one src/ share their import root, listed once."""
    write_workspace(tmp_path)
    member_directory = tmp_path / 'src' / 'games' / 'space-game'
    (member_directory / 'space_game').rmdir()
    for package in ('space_core', 'space_game'):
        (member_directory / 'src' / package).mkdir(parents=True)
    (member_directory / 'pyproject.toml').write_text(
        MEMBER_PYPROJECT.replace('["space_game"]', '["src/space_core", "src/space_game"]'),
        encoding='utf-8',
    )

    (member,) = workspace_members(project_root=tmp_path)

    assert member.import_packages == ('space_core', 'space_game')
    assert member.import_roots == (member_directory / 'src',)


@pytest.mark.parametrize('members', ['"src/games/space-game"', '[1]'])
def test_workspace_members_that_are_not_a_list_of_strings_are_refused(tmp_path, members):
    """A string must not be iterated character by character."""
    (tmp_path / 'pyproject.toml').write_text(
        f'[project]\nname = "glitchygames"\n\n[tool.uv.workspace]\nmembers = {members}\n',
        encoding='utf-8',
    )

    with pytest.raises(ValueError, match='list of strings'):
        workspace_members(project_root=tmp_path)


def test_a_member_knows_its_layer(tmp_path):
    """A member's layer is its directory's parent under src/."""
    write_workspace(tmp_path)

    (member,) = workspace_members(project_root=tmp_path)

    assert member.layer == 'games'


def test_a_member_outside_a_layer_is_refused(tmp_path):
    """A member must live in src/<layer>/, or the engine cannot name its classes."""
    (tmp_path / 'pyproject.toml').write_text(
        '[tool.uv.workspace]\nmembers = ["space-game"]\n', encoding='utf-8'
    )
    (tmp_path / 'space-game' / 'space_game').mkdir(parents=True)
    (tmp_path / 'space-game' / 'pyproject.toml').write_text(MEMBER_PYPROJECT, encoding='utf-8')

    with pytest.raises(ValueError, match='src/<layer>/'):
        workspace_members(project_root=tmp_path)


def test_this_repositorys_members_are_read():
    """The real workspace (members grow part by part)."""
    distributions = [member.distribution for member in workspace_members(project_root=PROJECT_ROOT)]

    assert 'mr-muncher' in distributions


# Part 2's and Part 4's end state (plans/2026-10-24-workspace-packages.md): every game and
# Bitmappy are members, so the engine's examples hold only the demos Part 3 has not moved yet (the
# dt demo is a member of the demos layer) and resources/ (which still holds snd/), beside
# foo2.toml (Part 3 moves it to the one test that reads it)
ENGINE_EXAMPLES_DIRECTORY = PROJECT_ROOT / 'src' / 'glitchygames' / 'examples'
ENGINE_EXAMPLES_NOT_CHECKED = frozenset({'__init__.py', '__pycache__', 'foo2.toml'})
ENGINE_EXAMPLES_AFTER_PART_2 = frozenset({
    'joystick_demo.py',
    'text_input_demo.py',
    'resources',
})
# A console script a game had before Part 2 and no longer has (Brave Adventurer's launcher
# replaced it): its old root golden directory is checked too
FORMER_GAME_CONSOLE_SCRIPTS = ('brave-adventurer-papyrus',)
ROOT_REPLAY_FIXTURES_DIRECTORY = PROJECT_ROOT / 'tests' / 'fixtures' / 'replays'


def run_git(*, arguments: list[str], directory: Path) -> str:
    """Run git in ``directory`` without the ambient ``GIT_*`` variables.

    Args:
        arguments: The git arguments, after the program.
        directory: The working directory.

    Returns:
        git's standard output.

    """
    returncode, output = scripts_run_git(arguments=arguments, directory=directory)
    assert returncode == 0, output
    return output


def tracked_entry_names(*, directory: Path) -> set[str]:
    """Return the names directly in a directory that git tracks, ignored and untracked files out.

    A directory counts when git tracks any file below it. A file git ignores (macOS Finder's
    ``.DS_Store``) or has not been told about is not part of the repository, so it is not here.

    Args:
        directory: A directory inside a git work tree.

    Returns:
        The tracked files' and directories' names directly in ``directory``.

    """
    listing = run_git(arguments=['ls-files', '-z', '--', '.'], directory=directory)
    return {
        tracked_path.split('/', maxsplit=1)[0]
        for tracked_path in listing.split('\0')
        if tracked_path
    }


def test_the_engines_examples_hold_only_the_demos_and_their_resources():
    """The engine's examples are its unmoved demos and resources/: each game moved to its member."""
    entries = tracked_entry_names(directory=ENGINE_EXAMPLES_DIRECTORY)

    assert entries - ENGINE_EXAMPLES_NOT_CHECKED == ENGINE_EXAMPLES_AFTER_PART_2


def test_tracked_entry_names_leaves_out_ignored_and_untracked_files(tmp_path):
    """An ignored .DS_Store and an untracked file are not entries; a tracked directory is one."""
    run_git(arguments=['init', '--quiet'], directory=tmp_path)
    (tmp_path / '.gitignore').write_text('.DS_Store\n', encoding='utf-8')
    (tmp_path / 'demo.py').write_text('', encoding='utf-8')
    (tmp_path / 'resources').mkdir()
    (tmp_path / 'resources' / 'tone.wav').write_text('', encoding='utf-8')
    (tmp_path / '.DS_Store').write_text('', encoding='utf-8')
    (tmp_path / 'untracked.py').write_text('', encoding='utf-8')
    run_git(arguments=['add', '.gitignore', 'demo.py', 'resources'], directory=tmp_path)

    assert tracked_entry_names(directory=tmp_path) == {'.gitignore', 'demo.py', 'resources'}


def test_tracked_entry_names_ignores_a_git_dir_from_the_environment(tmp_path, monkeypatch):
    """A GIT_DIR set by a git hook does not send the helper to another repository."""
    other_repository = tmp_path / 'other'
    other_repository.mkdir()
    run_git(arguments=['init', '--quiet'], directory=other_repository)
    (other_repository / 'other.py').write_text('', encoding='utf-8')
    run_git(arguments=['add', 'other.py'], directory=other_repository)
    repository = tmp_path / 'repository'
    repository.mkdir()
    run_git(arguments=['init', '--quiet'], directory=repository)
    (repository / 'demo.py').write_text('', encoding='utf-8')
    run_git(arguments=['add', 'demo.py'], directory=repository)
    monkeypatch.setenv('GIT_DIR', str(other_repository / '.git'))
    monkeypatch.setenv('GIT_INDEX_FILE', str(other_repository / '.git' / 'index'))

    assert tracked_entry_names(directory=repository) == {'demo.py'}


def test_the_root_goldens_are_the_engines_own():
    """No game's recording lives under the root tests/: each game's are in its member."""
    game_members = [
        member for member in workspace_members(project_root=PROJECT_ROOT) if member.layer == 'games'
    ]
    game_names = {
        name
        for member in game_members
        for name in (member.distribution, *member.console_scripts, *member.import_packages)
    } | set(FORMER_GAME_CONSOLE_SCRIPTS)

    assert {member.distribution for member in game_members} == {
        'mr-muncher',
        'clockwork-keep',
        'brave-adventurer',
        'paddleslap',
        'drawing-fire',
    }
    assert [
        name for name in sorted(game_names) if (ROOT_REPLAY_FIXTURES_DIRECTORY / name).exists()
    ] == []
