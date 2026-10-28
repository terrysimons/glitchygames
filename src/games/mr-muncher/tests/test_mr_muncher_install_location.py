"""Mr. Muncher is imported from its member's src/ (or site-packages in a wheel install)."""

from __future__ import annotations

from pathlib import Path


def test_mr_muncher_is_imported_from_its_src_directory():
    """Mr. Muncher's package is under its member's src/ (or site-packages in a wheel install)."""
    import mr_muncher

    member_source_directory = Path(__file__).resolve().parents[1] / 'src'
    package_directory = Path(mr_muncher.__file__).resolve().parent

    assert (
        package_directory.parent == member_source_directory
        or 'site-packages' in package_directory.parts
    ), f'{package_directory} is not under {member_source_directory} or site-packages'
