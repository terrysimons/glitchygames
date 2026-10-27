"""A game's own recordings (glitchygames/replay/tools/recordings.py): its goldens and demos.

Every case uses stand-ins (tests/stand_in_games.py): distributions whose console scripts start
stand-in packages, and recordings that are a header line only (nothing here replays them).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from glitchygames.replay.driver import write_bookmarked_copy
from glitchygames.replay.tools.identity import GameIdentity
from glitchygames.replay.tools.recordings import Recording, game_recordings
from glitchygames.replay.tools.settings import ProjectSettings
from tests.stand_in_games import (
    write_header_only_recording,
    write_stand_in_distribution,
    write_stand_in_package,
    write_stand_in_recording,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

# The two stand-in games of one project: each a package with a console script of its own
RALLY = 'stand-in-rally'
RALLY_PACKAGE = 'stand_in_rally'
PONG = 'stand-in-pong'
PONG_PACKAGE = 'stand_in_pong'
# The members' layout, as our project's golden-globs reads it
MEMBER_GOLDEN_GLOB = 'src/*/*/tests/fixtures/replays/golden*.jsonl.gz'
# The default glob reads another project's layout: fixtures/replays/<console-script>/
DEFAULT_GOLDEN_GLOB = 'tests/fixtures/replays/**/*.jsonl.gz'
# A bookmark on frame 2 needs a source of at least 2 frames
BOOKMARKED_SOURCE_FRAMES = 3


def install_two_games(*, install_directory: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Install two stand-in games, each a package with one demo and a console script.

    Args:
        install_directory: Where they are installed (put on ``sys.path``).
        monkeypatch: pytest's fixture.

    """
    for console_script, package in ((RALLY, RALLY_PACKAGE), (PONG, PONG_PACKAGE)):
        write_stand_in_package(
            directory=install_directory, package=package, demo_names=('demo.jsonl.gz',)
        )
        write_stand_in_distribution(
            directory=install_directory,
            distribution=console_script,
            console_scripts={console_script: f'{package}:main'},
        )
    monkeypatch.syspath_prepend(install_directory)


def identity_of(
    *, console_script: str | None, package: str, install_directory: Path
) -> GameIdentity:
    """Return a stand-in game's identity, as ``game_identity`` would find it.

    Returns:
        The identity.

    """
    return GameIdentity(
        package=package,
        package_directory=install_directory / package,
        console_script=console_script,
        distribution=console_script,
    )


def write_golden(*, path: Path) -> Path:
    """Write a header-only golden (nothing here replays it).

    Returns:
        Its path.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header_only_recording(path=path, header={'game': 'stand_in:Scene'})
    return path


def test_a_game_finds_its_own_goldens_and_demos_and_no_other_games(tmp_path, monkeypatch):
    """Two stand-in games in one project: each finds its goldens and demos, never the other's.

    Goldens in both layouts the globs read (a member's ``<member>/tests/fixtures/replays/`` and
    another project's ``tests/fixtures/replays/<console-script>/``) belong to the console script
    that replays them (``recording_console_script``); the demos are in the game's own package.
    Bookmarked copies, and a golden whose console script can't be told, belong to no game.
    """
    install_directory = tmp_path / 'site-packages'
    install_two_games(install_directory=install_directory, monkeypatch=monkeypatch)
    project = tmp_path / 'project'
    replays = ('tests', 'fixtures', 'replays')
    rally_member_golden = write_golden(
        path=project.joinpath('src', 'games', RALLY, *replays, 'golden.jsonl.gz')
    )
    pong_member_golden = write_golden(
        path=project.joinpath('src', 'games', PONG, *replays, 'golden.jsonl.gz')
    )
    rally_golden = write_golden(path=project.joinpath(*replays, RALLY, 'serve.jsonl.gz'))
    pong_golden = write_golden(path=project.joinpath(*replays, PONG, 'serve.jsonl.gz'))
    # Matched by the default glob, but nothing replays it: no game's
    write_golden(path=project.joinpath(*replays, 'no-such-console-script', 'lost.jsonl.gz'))
    # A bookmarked copy beside a golden: no golden
    source = tmp_path / 'source.jsonl.gz'
    write_stand_in_recording(path=source, frame_count=BOOKMARKED_SOURCE_FRAMES)
    write_bookmarked_copy(
        recording_path=source,
        bookmarks=[2],
        destination=project.joinpath(*replays, RALLY, 'serve.bookmarked.jsonl.gz'),
    )
    settings = ProjectSettings(golden_globs=(MEMBER_GOLDEN_GLOB, DEFAULT_GOLDEN_GLOB))

    rally = game_recordings(
        identity=identity_of(
            console_script=RALLY, package=RALLY_PACKAGE, install_directory=install_directory
        ),
        settings=settings,
        project_root=project,
    )
    pong = game_recordings(
        identity=identity_of(
            console_script=PONG, package=PONG_PACKAGE, install_directory=install_directory
        ),
        settings=settings,
        project_root=project,
    )

    assert rally == [
        Recording(console_script=RALLY, path=rally_member_golden, kind='golden'),
        Recording(console_script=RALLY, path=rally_golden, kind='golden'),
        Recording(
            console_script=RALLY,
            path=install_directory / RALLY_PACKAGE / 'demos' / 'demo.jsonl.gz',
            kind='demo',
        ),
    ]
    assert pong == [
        Recording(console_script=PONG, path=pong_member_golden, kind='golden'),
        Recording(console_script=PONG, path=pong_golden, kind='golden'),
        Recording(
            console_script=PONG,
            path=install_directory / PONG_PACKAGE / 'demos' / 'demo.jsonl.gz',
            kind='demo',
        ),
    ]


def test_a_project_without_goldens_has_only_the_games_demos(tmp_path, monkeypatch):
    """The default globs find nothing in an empty project; the package's demos remain."""
    install_directory = tmp_path / 'site-packages'
    install_two_games(install_directory=install_directory, monkeypatch=monkeypatch)
    project = tmp_path / 'project'
    project.mkdir()

    recordings = game_recordings(
        identity=identity_of(
            console_script=RALLY, package=RALLY_PACKAGE, install_directory=install_directory
        ),
        settings=ProjectSettings(),
        project_root=project,
    )

    assert [recording.kind for recording in recordings] == ['demo']


def test_a_game_no_console_script_starts_has_no_recordings(tmp_path, monkeypatch):
    """Without a console script nothing can be told to be its, or replay it by name."""
    install_directory = tmp_path / 'site-packages'
    install_two_games(install_directory=install_directory, monkeypatch=monkeypatch)
    project = tmp_path / 'project'
    write_golden(path=project.joinpath('tests', 'fixtures', 'replays', RALLY, 'serve.jsonl.gz'))

    recordings = game_recordings(
        identity=identity_of(
            console_script=None, package=RALLY_PACKAGE, install_directory=install_directory
        ),
        settings=ProjectSettings(),
        project_root=project,
    )

    assert recordings == []
