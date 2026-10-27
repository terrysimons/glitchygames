"""PaddleSlap moved out of glitchygames/examples: it is imported from its member's src/."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import paddleslap


def test_the_old_example_module_is_gone():
    """Nothing is left in glitchygames/examples to import (a stale __pycache__ would be)."""
    spec = importlib.util.find_spec('glitchygames.examples')
    leftover_locations = [] if spec is None else list(spec.submodule_search_locations or [])

    assert spec is None, (
        f'glitchygames.examples still resolves, at {leftover_locations}: ignored leftovers of '
        'the move; rm -rf src/glitchygames/examples tests/examples'
    )


def test_paddleslap_is_imported_from_its_src_directory():
    """PaddleSlap's package is under its member's src/ (or site-packages in a wheel install)."""
    member_source_directory = Path(__file__).resolve().parents[1] / 'src'
    package_directory = Path(paddleslap.__file__).resolve().parent

    assert (
        package_directory.parent == member_source_directory
        or 'site-packages' in package_directory.parts
    ), f'{package_directory} is not under {member_source_directory} or site-packages'
