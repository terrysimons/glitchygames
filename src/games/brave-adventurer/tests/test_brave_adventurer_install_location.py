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
    assert importlib.util.find_spec('glitchygames.examples') is None
    old_directory = PROJECT_ROOT.joinpath('src', *old_package.split('.'))
    assert not old_directory.exists()
