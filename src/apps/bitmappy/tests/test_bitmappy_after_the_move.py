"""Bitmappy moved out of the engine into src/apps/bitmappy: the first member of the apps layer."""

from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import json
import os
import shutil
import zipfile
from pathlib import Path

import bitmappy
from bitmappy import SPRITE_CONFIG_DIR, utils
from bitmappy.ai_worker import run_ai_worker_process
from bitmappy.editor import BitmapEditorScene
from glitchygames.logical_names import logical_name
from glitchygames.process import run_command

# src/apps/bitmappy/tests/ -> the repository root, where `uv build --package` runs
PROJECT_ROOT = Path(__file__).resolve().parents[4]
MEMBER_PACKAGE_DIRECTORY = PROJECT_ROOT / 'src' / 'apps' / 'bitmappy' / 'bitmappy'
# The sprite library's size when it moved with Bitmappy (2026-10-26)
SPRITE_LIBRARY_FILE_COUNT = 71
SPRITE_LIBRARY_WHEEL_DIRECTORY = 'bitmappy/resources/sprites/'
RESOURCE_WHEEL_PATHS = ('bitmappy/resources/bitmappy.cfg', 'bitmappy/resources/bitmappy.png')
# Building the member's wheel resolves its build backend: allow for a cold uv cache
WHEEL_BUILD_TIMEOUT_SECONDS = 300.0


def test_the_editor_is_named_in_the_apps_layer():
    """The editor's scene is named by the apps layer, from its own package."""
    assert logical_name(scene_class=BitmapEditorScene) == 'apps.bitmappy.editor:BitmapEditorScene'
    assert BitmapEditorScene.__module__ == 'bitmappy.editor'


def test_the_old_engine_package_is_gone():
    """Nothing is left in the engine to import (a stale __pycache__ would be)."""
    spec = importlib.util.find_spec('glitchygames.bitmappy')
    leftover_locations = [] if spec is None else list(spec.submodule_search_locations or [])

    assert spec is None, (
        f'glitchygames.bitmappy still resolves, at {leftover_locations}: a leftover of the move '
        '(ignored __pycache__); rm -rf src/glitchygames/bitmappy'
    )


def test_bitmappy_is_imported_from_its_member():
    """The bitmappy imported is the one its distribution installed, never another copy.

    uv sync installs the member editable (the package imported is its source under src/apps/);
    nox installs it non-editable (site-packages).
    """
    imported_from = Path(bitmappy.__file__).resolve().parent
    distribution = importlib.metadata.distribution('bitmappy')
    direct_url = json.loads(distribution.read_text('direct_url.json') or '{}')

    if direct_url.get('dir_info', {}).get('editable', False):
        assert imported_from == MEMBER_PACKAGE_DIRECTORY.resolve()
    else:
        assert imported_from == Path(str(distribution.locate_file('bitmappy'))).resolve()


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


def test_the_ai_worker_target_is_importable_by_name():
    """The AI worker process's target is found again by its module and name.

    The spawn start method (macOS, Windows) pickles the target by reference, and the child
    imports it by those two names, so they must name an importable function.
    """
    assert run_ai_worker_process.__module__ == 'bitmappy.ai_worker'
    module = importlib.import_module(run_ai_worker_process.__module__)

    assert getattr(module, run_ai_worker_process.__qualname__) is run_ai_worker_process
