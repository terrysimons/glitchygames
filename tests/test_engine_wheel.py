"""The engine's wheel holds the engine alone: its package, its resources, nothing of a member."""

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


def test_the_engine_wheel_holds_the_engine_alone(tmp_path):
    """The engine wheel ships the engine, its four sounds and its two sprites, and no member."""
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
