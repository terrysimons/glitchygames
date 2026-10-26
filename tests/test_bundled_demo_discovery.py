"""glitchygames/bundled_demos.py: the demos games ship in their installed packages."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import pytest

from glitchygames.bundled_demos import (
    BUNDLED_DEMO_DIRECTORY_NAME,
    BundledDemo,
    bundled_demos,
    console_script_in_module,
    package_demo_paths,
)
from glitchygames.replay.driver import write_bookmarked_copy
from paddleslap import PADDLESLAP_DEMO_PATH

if TYPE_CHECKING:
    from pathlib import Path


def write_stand_in_package(*, directory: Path, package: str, demo_names: tuple[str, ...]) -> Path:
    """Write an import package with no console script, holding files in its demos/ directory.

    Returns:
        The package's demos directory.

    """
    demo_directory = directory / package / BUNDLED_DEMO_DIRECTORY_NAME
    demo_directory.mkdir(parents=True)
    (directory / package / '__init__.py').write_text('', encoding='utf-8')
    for name in demo_names:
        (demo_directory / name).write_bytes(b'')
    return demo_directory


def test_paddleslaps_demo_is_found_with_its_console_script_and_install_name():
    """The rally demo, wherever paddleslap is installed, named the same under any install."""
    (demo,) = bundled_demos(packages=('paddleslap',))

    assert demo == BundledDemo(
        package='paddleslap',
        console_script='paddleslap',
        path=PADDLESLAP_DEMO_PATH,
        install_name='paddleslap/demos/rally.jsonl.gz',
    )


def test_a_bundled_demo_is_a_frozen_record():
    """A demo's fields cannot be changed in place."""
    (demo,) = bundled_demos(packages=('paddleslap',))

    with pytest.raises(dataclasses.FrozenInstanceError):
        demo.console_script = 'other'  # type: ignore[misc]


def test_package_demo_paths_lists_only_recordings_and_leaves_out_bookmarked_copies(tmp_path):
    """Only demos/*.jsonl.gz, sorted; a bookmarked copy beside a demo is no demo."""
    demo_directory = write_stand_in_package(
        directory=tmp_path,
        package='stand_in_game',
        demo_names=('serve.jsonl.gz', 'rally.jsonl.gz', 'notes.txt'),
    )
    (tmp_path / 'stand_in_game' / 'sprites').mkdir()
    (tmp_path / 'stand_in_game' / 'sprites' / 'ball.jsonl.gz').write_bytes(b'')
    write_bookmarked_copy(
        recording_path=PADDLESLAP_DEMO_PATH,
        bookmarks=[2],
        destination=demo_directory / 'rally.bookmarked.jsonl.gz',
    )

    demos = package_demo_paths(package_directory=tmp_path / 'stand_in_game')

    assert demos == [demo_directory / 'rally.jsonl.gz', demo_directory / 'serve.jsonl.gz']


def test_a_demo_of_a_package_without_a_console_script_names_none(tmp_path, monkeypatch):
    """The lookup reports it; each caller decides what a demo nothing replays means."""
    demo_directory = write_stand_in_package(
        directory=tmp_path, package='stand_in_game_without_a_script', demo_names=('rally.jsonl.gz',)
    )
    monkeypatch.syspath_prepend(tmp_path)

    demos = bundled_demos(packages=('stand_in_game_without_a_script',))

    assert demos == [
        BundledDemo(
            package='stand_in_game_without_a_script',
            console_script=None,
            path=demo_directory / 'rally.jsonl.gz',
            install_name='stand_in_game_without_a_script/demos/rally.jsonl.gz',
        )
    ]


def test_packages_without_demos_and_those_not_installed_have_none(tmp_path, monkeypatch):
    """No demos directory, an empty one, a plain module, or a package not installed: no demos."""
    write_stand_in_package(directory=tmp_path, package='stand_in_game_with_no_demos', demo_names=())
    (tmp_path / 'stand_in_module.py').write_text('', encoding='utf-8')
    monkeypatch.syspath_prepend(tmp_path)

    demos = bundled_demos(
        packages=(
            'glitchygames',
            'stand_in_game_with_no_demos',
            'stand_in_module',
            'no_such_installed_package',
        )
    )

    assert demos == []


def test_every_member_package_is_searched_by_default():
    """Without packages, the demos come from every workspace member's (MEMBER_LAYERS), sorted."""
    demos = bundled_demos()

    assert [demo.install_name for demo in demos if demo.package == 'paddleslap'] == [
        'paddleslap/demos/rally.jsonl.gz'
    ]
    assert all(demo.path.parent.name == BUNDLED_DEMO_DIRECTORY_NAME for demo in demos)
    assert [demo.path for demo in demos] == sorted(demo.path for demo in demos)


def test_a_console_script_is_found_by_the_module_of_its_entry_point():
    """The first installed console script whose entry point's module is the one asked for."""
    assert console_script_in_module(module='paddleslap') == 'paddleslap'
    assert console_script_in_module(module='no_such_module') is None
