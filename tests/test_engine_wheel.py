"""The engine's wheel holds the engine alone: its package, its resources, nothing of a member.

It also carries the golden-replay pytest plugin's ``pytest11`` entry point, so any project with
the wheel installed gets its recordings collected (glitchygames/testing/replays.py).
"""

import os
import shutil
import zipfile
from pathlib import Path

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
