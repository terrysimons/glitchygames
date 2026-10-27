"""glitchygames/bundled_demos.py: the demos games ship in their installed packages."""

from __future__ import annotations

import dataclasses
import inspect
from typing import TYPE_CHECKING, cast

import pytest

from glitchygames.bundled_demos import (
    BUNDLED_DEMO_DIRECTORY_NAME,
    BundledDemo,
    bundled_demos,
    console_script_in_module,
    package_demo_paths,
)
from glitchygames.replay.driver import write_bookmarked_copy
from glitchygames.testing.replays import bundled_demo_paths
from tests.stand_in_games import (
    write_stand_in_distribution,
    write_stand_in_package,
    write_stand_in_recording,
)

if TYPE_CHECKING:
    from collections.abc import Callable

# A stand-in recording's frames: a bookmark on frame 2 needs at least 2, and 3 leaves a frame
# after the bookmark
STAND_IN_RECORDING_FRAMES = 3


def test_a_games_demo_is_found_with_its_console_script_and_install_name(tmp_path, monkeypatch):
    """A package's rally demo, with the console script in it, named the same under any install.

    A stand-in package with one demo, installed with a stand-in distribution whose one console
    script's entry point is in the package (as PaddleSlap's is; its real demo is checked in
    tests/test_bundled_demos.py).
    """
    install_directory = tmp_path / 'site-packages'
    demo_directory = write_stand_in_package(
        directory=install_directory, package='stand_in_rally', demo_names=('rally.jsonl.gz',)
    )
    write_stand_in_distribution(
        directory=install_directory,
        distribution='stand-in-rally',
        console_scripts={'stand-in-rally': 'stand_in_rally:main'},
    )
    monkeypatch.syspath_prepend(install_directory)

    (demo,) = bundled_demos(packages=('stand_in_rally',))

    assert demo == BundledDemo(
        package='stand_in_rally',
        console_script='stand-in-rally',
        path=demo_directory / 'rally.jsonl.gz',
        install_name='stand_in_rally/demos/rally.jsonl.gz',
    )


def test_a_bundled_demo_is_a_frozen_record(tmp_path):
    """A demo's fields cannot be changed in place."""
    demo = BundledDemo(
        package='stand_in_game',
        console_script='stand-in-game',
        path=tmp_path / 'stand_in_game' / BUNDLED_DEMO_DIRECTORY_NAME / 'rally.jsonl.gz',
        install_name='stand_in_game/demos/rally.jsonl.gz',
    )

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
    # The copy's source: a small stand-in recording, written beside the package
    stand_in_recording_path = tmp_path / 'stand_in_rally.jsonl.gz'
    write_stand_in_recording(path=stand_in_recording_path, frame_count=STAND_IN_RECORDING_FRAMES)
    write_bookmarked_copy(
        recording_path=stand_in_recording_path,
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


def test_the_packages_to_search_are_always_given():
    """No default: a caller names the packages it searches (Stage D, Task D5).

    The default was every workspace member's (``MEMBER_LAYERS``), which an unseen game is not;
    a game's own demos are its package's (``glitchygames.replay.tools.recordings``).
    """
    for lookup in (bundled_demos, bundled_demo_paths):
        packages = inspect.signature(lookup).parameters['packages']

        assert packages.default is inspect.Parameter.empty, lookup.__name__
        with pytest.raises(TypeError, match='packages'):
            # Called as a caller that names no packages would call it
            cast('Callable[[], object]', lookup)()


def test_a_console_script_is_found_by_the_module_of_its_entry_point(tmp_path, monkeypatch):
    """The first installed console script whose entry point's module is the one asked for.

    A stand-in distribution whose one console script's entry point is in the stand-in module.
    """
    write_stand_in_distribution(
        directory=tmp_path,
        distribution='stand-in-rally',
        console_scripts={'stand-in-rally': 'stand_in_rally:main'},
    )
    monkeypatch.syspath_prepend(tmp_path)

    assert console_script_in_module(module='stand_in_rally') == 'stand-in-rally'
    assert console_script_in_module(module='no_such_module') is None
