"""Brave Adventurer and Papyrus moved from glitchygames/examples: nothing is left there."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]


@pytest.mark.parametrize(
    'old_package',
    ['glitchygames.examples.brave_adventurer', 'glitchygames.examples.brave_adventurer_papyrus'],
)
def test_the_old_example_packages_are_gone(old_package):
    """Nothing is left in glitchygames/examples to import (a stale __pycache__ would be)."""
    spec = importlib.util.find_spec('glitchygames.examples')
    leftover_locations = [] if spec is None else list(spec.submodule_search_locations or [])

    assert spec is None, (
        f'glitchygames.examples still resolves, at {leftover_locations}: ignored leftovers of '
        'the move; rm -rf src/glitchygames/examples tests/examples'
    )
    old_directory = PROJECT_ROOT.joinpath('src', *old_package.split('.'))
    assert not old_directory.exists(), (
        f'{old_directory} still exists: an ignored leftover of the move; rm -rf {old_directory}'
    )
