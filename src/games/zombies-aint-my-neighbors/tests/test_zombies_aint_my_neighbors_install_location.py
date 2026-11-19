"""Zombies Ain't My Neighbors is imported from its member's src/ (or site-packages in a wheel)."""

from __future__ import annotations

from pathlib import Path


def test_zombies_aint_my_neighbors_is_imported_from_its_src_directory():
    """The game's package is under its member's src/ (or site-packages in a wheel install)."""
    import zombies_aint_my_neighbors

    member_source_directory = Path(__file__).resolve().parents[1] / 'src'
    package_directory = Path(zombies_aint_my_neighbors.__file__).resolve().parent

    assert (
        package_directory.parent == member_source_directory
        or 'site-packages' in package_directory.parts
    ), f'{package_directory} is not under {member_source_directory} or site-packages'
