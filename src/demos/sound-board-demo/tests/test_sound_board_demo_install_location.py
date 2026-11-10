"""The Sound Board demo is imported from its member's src/ directory."""

from __future__ import annotations

from pathlib import Path

import sound_board_demo


def test_sound_board_demo_is_imported_from_its_src_directory():
    """The demo's package is under its member's src/ (or site-packages in a wheel install)."""
    member_source_directory = Path(__file__).resolve().parents[1] / 'src'
    package_directory = Path(sound_board_demo.__file__).resolve().parent

    assert (
        package_directory.parent == member_source_directory
        or 'site-packages' in package_directory.parts
    ), f'{package_directory} is not under {member_source_directory} or site-packages'
