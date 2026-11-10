"""The engine's wheel holds the engine alone: its package, its resources, nothing of a member.

It also carries the golden-replay pytest plugin's ``pytest11`` entry point, so any project with
the wheel installed gets its recordings collected (glitchygames/testing/replays.py). The build of
every workspace package (``nox -s build-wheel``: ``uv build --all-packages``) gives each member a
wheel of its own packages, their data files included, and the engine's still holds no member.
"""

import os
import shutil
import zipfile
from pathlib import Path

from scripts.git_checkout import files_not_ignored
from scripts.workspace_packages import ENGINE_PACKAGE, workspace_members

from glitchygames.process import OutputCapture, run_command

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENGINE_SOUND_WHEEL_PATHS = (
    'glitchygames/resources/sounds/sfx_menu_move1.wav',
    'glitchygames/resources/sounds/sfx_sounds_impact5.wav',
    'glitchygames/resources/sounds/sfx_sounds_impact8.wav',
    'glitchygames/resources/sounds/slap8.wav',
)
# Building the wheel resolves its build backend: allow for a cold uv cache
WHEEL_BUILD_TIMEOUT_SECONDS = 300.0
# The wheel's entry points (the packaging spec's dist-info file) and pytest's plugin group
ENTRY_POINTS_FILE_NAME = 'entry_points.txt'
PYTEST_PLUGIN_GROUP = 'pytest11'
# The golden-replay plugin, registered under its module's name (pyproject.toml says why)
REPLAY_PLUGIN_MODULE = 'glitchygames.testing.replays'
# A wheel's metadata directory ends with this; everything else in it is a package's files
DIST_INFO_SUFFIX = '.dist-info'
# Data files members ship that their games read at run time, by distribution: the checks below
# would pass on a wheel missing them only if the source tree lost them too
MEMBER_DATA_WHEEL_PATHS = {
    'brave-adventurer': 'brave_adventurer_papyrus/sprites/cobra.toml',
    'paddleslap': 'paddleslap/demos/rally.jsonl.gz',
    'drawing-fire': 'drawing_fire/sprites/soldier.toml',
}


def entry_points_in_group(*, text: str, group: str) -> dict[str, str]:
    """Read one group of a dist-info ``entry_points.txt``: ``[group]`` then ``name = value`` lines.

    Args:
        text: The file's text.
        group: The group (section) to read.

    Returns:
        The group's entry points, name to value (empty if the group is not there).

    """
    entries: dict[str, str] = {}
    in_group = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('['):
            in_group = stripped == f'[{group}]'
        elif in_group and stripped:
            name, value = stripped.split('=', maxsplit=1)
            entries[name.strip()] = value.strip()
    return entries


def test_the_engine_wheel_holds_the_engine_alone(tmp_path):
    """The engine wheel ships the engine, its four sounds and its two sprites, and no member.

    Its metadata registers the replay pytest plugin, and only it, as a pytest11 entry point.
    """
    uv = shutil.which('uv')
    assert uv is not None, 'uv is not on PATH: it builds the engine wheel'

    # Without --all-packages uv builds only the root project, the engine
    completed = run_command(
        command=[uv, 'build', '--wheel', '--out-dir', str(tmp_path)],
        environment=os.environ,
        timeout_seconds=WHEEL_BUILD_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
        working_directory=PROJECT_ROOT,
    )

    assert completed.returncode == 0, completed.stdout
    (wheel,) = tmp_path.glob('glitchygames-*.whl')
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        (entry_points_name,) = [
            name
            for name in names
            if name.endswith(f'.dist-info/{ENTRY_POINTS_FILE_NAME}') and name.count('/') == 1
        ]
        entry_points_text = archive.read(entry_points_name).decode('utf-8')
    top_level_names = {name.split('/', maxsplit=1)[0] for name in names}
    assert {name for name in top_level_names if not name.endswith('.dist-info')} == {ENGINE_PACKAGE}

    assert not [name for name in names if name.startswith(f'{ENGINE_PACKAGE}/examples/')]

    member_packages = {
        package
        for member in workspace_members(project_root=PROJECT_ROOT)
        for package in member.import_packages
    }
    assert member_packages, 'the workspace has no member packages: this check would pass on zero'
    assert not [
        name for name in names if name.split('/')[1:2] and name.split('/')[1] in member_packages
    ]

    # The engine's only TOML sprites are in assets/; a sprite library elsewhere is a member's
    stray_sprite_files = [
        name
        for name in names
        if name.endswith('.toml') and not name.startswith(f'{ENGINE_PACKAGE}/assets/')
    ]
    assert not stray_sprite_files
    sprites = sorted(
        name
        for name in names
        if name.startswith(f'{ENGINE_PACKAGE}/assets/') and name.endswith('.toml')
    )
    assert sprites == [
        f'{ENGINE_PACKAGE}/assets/eraser.toml',
        f'{ENGINE_PACKAGE}/assets/raspberry.toml',
    ]
    sounds = sorted(name for name in names if name.startswith('glitchygames/resources/sounds/'))
    assert sounds == sorted(ENGINE_SOUND_WHEEL_PATHS)

    assert entry_points_in_group(text=entry_points_text, group=PYTEST_PLUGIN_GROUP) == {
        REPLAY_PLUGIN_MODULE: REPLAY_PLUGIN_MODULE
    }


def build_every_workspace_wheel(*, directory: Path) -> dict[str, list[str]]:
    """Build every workspace package's wheel as ``nox -s build-wheel`` does, and read them.

    Args:
        directory: Where the wheels are written.

    Returns:
        Each wheel's distribution name (the file name's first part, ``drawing_fire``) -> the
        paths it holds outside its metadata directory.

    """
    uv = shutil.which('uv')
    assert uv is not None, 'uv is not on PATH: it builds the wheels'
    completed = run_command(
        command=[uv, 'build', '--all-packages', '--wheel', '--out-dir', str(directory)],
        environment=os.environ,
        timeout_seconds=WHEEL_BUILD_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
        working_directory=PROJECT_ROOT,
    )
    assert completed.returncode == 0, completed.stdout
    contents: dict[str, list[str]] = {}
    for wheel in sorted(directory.glob('*.whl')):
        with zipfile.ZipFile(wheel) as archive:
            contents[wheel.name.split('-', maxsplit=1)[0]] = sorted(
                name
                for name in archive.namelist()
                if not name.split('/', maxsplit=1)[0].endswith(DIST_INFO_SUFFIX)
            )
    return contents


def wheel_mismatch(*, distribution: str, wheel_files: list[str], expected_files: list[str]) -> str:
    """Describe how a member's wheel differs from its packages' files, and what to do.

    Args:
        distribution: The member's distribution name.
        wheel_files: The files its wheel holds, outside its metadata directory.
        expected_files: The files git does not ignore in its packages.

    Returns:
        The failure message.

    """
    only_in_wheel = sorted(set(wheel_files) - set(expected_files))
    only_in_packages = sorted(set(expected_files) - set(wheel_files))
    return (
        f'The {distribution} wheel differs from its packages. In the wheel only: '
        f'{only_in_wheel or "none"}; in the packages only: {only_in_packages or "none"}. A file '
        'in the wheel only is ignored by .git/info/exclude or your global git excludes but not '
        'by a .gitignore, which is all hatch reads: delete it, or ignore it in .gitignore. A file '
        "in the packages only is one the member's [tool.hatch.build] settings leave out: ship "
        "it, or ignore it in .gitignore if it is not the package's"
    )


def test_a_wheel_mismatch_names_each_differing_file_and_what_to_do():
    """The failure names the files on each side and the fixes."""
    message = wheel_mismatch(
        distribution='space-game',
        wheel_files=['space_game/.game.py.swp', 'space_game/game.py'],
        expected_files=['space_game/game.py', 'space_game/sprites/ship.toml'],
    )

    assert "In the wheel only: ['space_game/.game.py.swp']" in message
    assert "in the packages only: ['space_game/sprites/ship.toml']" in message
    assert '.git/info/exclude' in message
    assert 'ignore it in .gitignore' in message


def test_every_member_wheel_holds_exactly_its_own_packages(tmp_path):
    """Each member's wheel holds its packages' files, data files included, and nothing else.

    A package's files are what git does not ignore in its directory, tracked or not, so a
    sprite, sound or demo a game reads at run time ships with it. hatch ships the same files,
    an untracked one included (a stray editor swap file ships too, and passes here). They differ
    only for a file ignored by .git/info/exclude or the user's global excludes alone: git leaves
    it out, hatch, which reads only the nearest .gitignore, ships it, and this fails naming it.
    The engine's wheel from the same build holds the engine alone.
    """
    members = workspace_members(project_root=PROJECT_ROOT)
    contents = build_every_workspace_wheel(directory=tmp_path)

    assert sorted(contents) == sorted([
        ENGINE_PACKAGE,
        *(member.distribution.replace('-', '_') for member in members),
    ])
    assert {name.split('/', maxsplit=1)[0] for name in contents[ENGINE_PACKAGE]} == {ENGINE_PACKAGE}
    for member in members:
        expected = sorted(
            f'{package}/{relative_path.as_posix()}'
            for package, package_directory in zip(
                member.import_packages, member.package_directories, strict=True
            )
            for relative_path in files_not_ignored(directory=package_directory)
        )
        wheel_files = contents[member.distribution.replace('-', '_')]
        assert wheel_files == expected, wheel_mismatch(
            distribution=member.distribution, wheel_files=wheel_files, expected_files=expected
        )
    for distribution, data_path in MEMBER_DATA_WHEEL_PATHS.items():
        assert data_path in contents[distribution.replace('-', '_')]
