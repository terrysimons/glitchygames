"""Bitmappy's wheel holds only its package, its resources and its whole sprite library."""

from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path

import bitmappy
from bitmappy import SPRITE_CONFIG_DIR, utils
from glitchygames.process import run_command

# src/apps/bitmappy/tests/ -> the repository root, where `uv build --package` runs
PROJECT_ROOT = Path(__file__).resolve().parents[4]
# The sprite library's size when it moved with Bitmappy (2026-10-26)
SPRITE_LIBRARY_FILE_COUNT = 71
SPRITE_LIBRARY_WHEEL_DIRECTORY = 'bitmappy/resources/sprites/'
RESOURCE_WHEEL_PATHS = ('bitmappy/resources/bitmappy.cfg', 'bitmappy/resources/bitmappy.png')
# Building the member's wheel resolves its build backend: allow for a cold uv cache
WHEEL_BUILD_TIMEOUT_SECONDS = 300.0


def test_the_sprite_library_is_package_data():
    """The sprite library is inside the package, read through the package's own path."""
    package_directory = Path(bitmappy.__file__).resolve().parent

    assert SPRITE_CONFIG_DIR.resolve().is_relative_to(package_directory)
    assert Path(utils.__file__).parent / 'resources' / 'sprites' == SPRITE_CONFIG_DIR
    assert len(list(SPRITE_CONFIG_DIR.glob('*.toml'))) == SPRITE_LIBRARY_FILE_COUNT


def test_the_sprite_library_ships_in_its_wheel(tmp_path):
    """The member's wheel holds only bitmappy, its resources and its whole sprite library."""
    uv = shutil.which('uv')
    assert uv is not None, 'uv is not on PATH: it builds the member wheel'

    completed = run_command(
        command=[uv, 'build', '--package', 'bitmappy', '--wheel', '--out-dir', str(tmp_path)],
        environment=os.environ,
        timeout_seconds=WHEEL_BUILD_TIMEOUT_SECONDS,
        capture_output=True,
        working_directory=PROJECT_ROOT,
    )

    assert completed.returncode == 0, completed.stdout
    (wheel,) = tmp_path.glob('bitmappy-*.whl')
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
    sprite_library_names = [
        name for name in names if name.startswith(SPRITE_LIBRARY_WHEEL_DIRECTORY)
    ]
    assert len(sprite_library_names) == SPRITE_LIBRARY_FILE_COUNT
    assert all(name.endswith('.toml') for name in sprite_library_names)
    assert set(RESOURCE_WHEEL_PATHS) <= set(names)
    top_level_names = {name.split('/', maxsplit=1)[0] for name in names}
    assert {name for name in top_level_names if not name.endswith('.dist-info')} == {'bitmappy'}
