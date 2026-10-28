"""Bitmappy moved out of the engine into src/apps/bitmappy: it is imported from its member alone."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
from pathlib import Path

import bitmappy

# src/apps/bitmappy/tests/ -> the repository root
PROJECT_ROOT = Path(__file__).resolve().parents[4]
MEMBER_PACKAGE_DIRECTORY = PROJECT_ROOT / 'src' / 'apps' / 'bitmappy' / 'src' / 'bitmappy'


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

    uv sync installs the member editable (the package imported is its source under
    src/apps/bitmappy/src/); nox installs it non-editable (site-packages).
    """
    imported_from = Path(bitmappy.__file__).resolve().parent
    distribution = importlib.metadata.distribution('bitmappy')
    direct_url = json.loads(distribution.read_text('direct_url.json') or '{}')

    if direct_url.get('dir_info', {}).get('editable', False):
        assert imported_from == MEMBER_PACKAGE_DIRECTORY.resolve()
    else:
        assert imported_from == Path(str(distribution.locate_file('bitmappy'))).resolve()


def test_bitmappy_is_imported_from_its_src_directory():
    """Bitmappy's package is under its member's src/ (or site-packages in a wheel install)."""
    member_source_directory = Path(__file__).resolve().parents[1] / 'src'
    package_directory = Path(bitmappy.__file__).resolve().parent

    assert (
        package_directory.parent == member_source_directory
        or 'site-packages' in package_directory.parts
    ), f'{package_directory} is not under {member_source_directory} or site-packages'
