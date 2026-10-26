"""Drawing Fire moved out of glitchygames/examples: its logical names, history and sprite stayed."""

from __future__ import annotations

import importlib.util
import os
import shutil
import zipfile
from pathlib import Path

from drawing_fire.game import DrawingFireScene
from glitchygames.logical_names import logical_name
from glitchygames.process import run_command
from glitchygames.recording_metrics import RECORDING_PATH_RENAMES

# src/games/drawing-fire/tests/ -> the repository root, where `uv build --package` runs
PROJECT_ROOT = Path(__file__).resolve().parents[4]
GOLDEN_REPOSITORY_PATH = 'src/games/drawing-fire/tests/fixtures/replays/golden.jsonl.gz'
GOLDEN_FORMER_PATH = 'tests/fixtures/replays/drawing-fire/golden.jsonl.gz'
# The soldier sprite, package data: the game reads it through drawing_fire's own path
SOLDIER_SPRITE_WHEEL_PATH = 'drawing_fire/sprites/soldier.toml'
# Building the member's wheel resolves its build backend: allow for a cold uv cache
WHEEL_BUILD_TIMEOUT_SECONDS = 300.0


def test_drawing_fire_keeps_its_logical_names():
    """Its scene keeps the logical name its recordings hold, from its new package."""
    assert logical_name(scene_class=DrawingFireScene) == 'games.drawing_fire.game:DrawingFireScene'
    assert DrawingFireScene.__module__ == 'drawing_fire.game'


def test_the_old_example_package_is_gone():
    """Nothing is left in glitchygames/examples to import (a stale __pycache__ would be)."""
    assert importlib.util.find_spec('glitchygames.examples') is None


def test_drawing_fires_golden_keeps_its_history():
    """Drawing Fire's golden moved into its member: its rows from before the move follow."""
    assert RECORDING_PATH_RENAMES[GOLDEN_FORMER_PATH] == GOLDEN_REPOSITORY_PATH


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


def test_drawing_fire_is_imported_from_its_src_directory():
    """Drawing Fire's package is under its member's src/ (or site-packages in a wheel install)."""
    import drawing_fire

    member_source_directory = Path(__file__).resolve().parents[1] / 'src'
    package_directory = Path(drawing_fire.__file__).resolve().parent

    assert (
        package_directory.parent == member_source_directory
        or 'site-packages' in package_directory.parts
    ), f'{package_directory} is not under {member_source_directory} or site-packages'
