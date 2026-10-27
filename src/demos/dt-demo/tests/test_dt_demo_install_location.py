"""The dt demo moved out of glitchygames/examples: it is imported from its member's src/."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import dt_demo


def test_the_old_example_module_is_gone():
    """Nothing is left in glitchygames/examples to import (a stale __pycache__ would be)."""
    assert importlib.util.find_spec('glitchygames.examples') is None


def test_dt_demo_is_imported_from_its_src_directory():
    """The dt demo's package is under its member's src/ (or site-packages in a wheel install)."""
    member_source_directory = Path(__file__).resolve().parents[1] / 'src'
    package_directory = Path(dt_demo.__file__).resolve().parent

    assert (
        package_directory.parent == member_source_directory
        or 'site-packages' in package_directory.parts
    ), f'{package_directory} is not under {member_source_directory} or site-packages'
