"""Drawing Fire's wheel holds its soldier sprite, so an installed game can read it."""

from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path

from glitchygames.process import run_command

# src/games/drawing-fire/tests/ -> the repository root, where `uv build --package` runs
PROJECT_ROOT = Path(__file__).resolve().parents[4]
# The soldier sprite, package data: the game reads it through drawing_fire's own path
SOLDIER_SPRITE_WHEEL_PATH = 'drawing_fire/sprites/soldier.toml'
# Building the member's wheel resolves its build backend: allow for a cold uv cache
WHEEL_BUILD_TIMEOUT_SECONDS = 300.0


def test_the_soldier_sprite_ships_in_its_wheel(tmp_path):
    """The member's wheel holds the soldier sprite, so an installed game can read it."""
    uv = shutil.which('uv')
    assert uv is not None, 'uv is not on PATH: it builds the member wheel'

    completed = run_command(
        command=[uv, 'build', '--package', 'drawing-fire', '--wheel', '--out-dir', str(tmp_path)],
        environment=os.environ,
        timeout_seconds=WHEEL_BUILD_TIMEOUT_SECONDS,
        capture_output=True,
        working_directory=PROJECT_ROOT,
    )

    assert completed.returncode == 0, completed.stdout
    (wheel,) = tmp_path.glob('drawing_fire-*.whl')
    with zipfile.ZipFile(wheel) as archive:
        assert SOLDIER_SPRITE_WHEEL_PATH in archive.namelist()
