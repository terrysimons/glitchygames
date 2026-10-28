"""Our measurement covers exactly what scripts/replay_metrics.py measured before it moved.

``glitchygames measure`` (glitchygames/replay/tools/measure.py) starts each of this repository's
``[tool.glitchygames] games`` with ``--measure``, and each measures its own recordings
(``recordings.game_recordings``); ``glitchygames unmeasured`` reads them the same way, by console
script (``measure.ledger_names``). Before Task D6 (Part 3, Stage D) one script found them all
itself: every games-layer member's goldens and every member package's bundled demos. These pin
that the games together still find exactly that set, each golden once and by the console script
of its member, and that no golden is left to nobody (``measure.unclaimed_goldens``). Moved from
tests/test_replay_metrics.py (``TestTheRecordings``), whose engine tests went to
tests/replay/tools/test_measure.py.
"""

from __future__ import annotations

from pathlib import Path

from scripts.workspace_packages import members_in_layer, workspace_members

from glitchygames.bundled_demos import bundled_demos
from glitchygames.replay.tools.identity import console_script_identity
from glitchygames.replay.tools.measure import (
    ledger_names,
    unclaimed_demos,
    unclaimed_goldens,
)
from glitchygames.replay.tools.recordings import game_recordings
from glitchygames.replay.tools.settings import load_project_settings
from tests.workspace_expectations import EXPECTED_BUNDLED_DEMOS, GAMES_LAYER, MEMBER_PACKAGES
from tests.workspace_goldens import check_every_game_holds_a_golden

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUR_SETTINGS = load_project_settings(project_root=PROJECT_ROOT)


def recordings_by_game() -> dict[str, list[Path]]:
    """Return each of our games' own recordings, as ``--measure`` and ``unmeasured`` find them.

    Returns:
        Console script -> its recordings' paths.

    """
    return {
        console_script: [
            recording.path
            for recording in game_recordings(
                identity=console_script_identity(console_script=console_script),
                settings=OUR_SETTINGS,
                project_root=PROJECT_ROOT,
            )
        ]
        for console_script in OUR_SETTINGS.games
    }


def member_console_scripts() -> dict[str, tuple[str, ...]]:
    """Return each games-layer member's console scripts, by its distribution.

    Returns:
        Distribution -> console scripts.

    """
    return {
        member.distribution: member.console_scripts
        for member in workspace_members(project_root=PROJECT_ROOT)
    }


def test_our_games_measure_every_members_goldens_and_every_bundled_demo_once():
    """Exactly every games-layer member's goldens and every bundled demo, none twice.

    Each golden is its own member's (one of the member's console scripts measures it; Brave
    Adventurer's launcher both of its); the demos by ``(package, name)`` (nox installs
    non-editable copies, so not by path).
    """
    goldens = check_every_game_holds_a_golden(project_root=PROJECT_ROOT)
    expected_goldens = {
        path
        for member in members_in_layer(project_root=PROJECT_ROOT, layer=GAMES_LAYER)
        for path in goldens[member.distribution]
    }
    by_game = recordings_by_game()
    found = [path for paths in by_game.values() for path in paths]
    golden_owners = {
        path: console_script
        for console_script, paths in by_game.items()
        for path in paths
        if path in expected_goldens
    }
    scripts_of = member_console_scripts()

    assert len(found) == len(set(found))
    assert set(golden_owners) == expected_goldens
    assert all(
        golden_owners[path] in scripts_of[distribution]
        for distribution, paths in goldens.items()
        for path in paths
    )
    assert {
        (path.parent.parent.name, path.name) for path in found if path not in expected_goldens
    } == EXPECTED_BUNDLED_DEMOS
    assert by_game['brave-adventurer'][:2] == [
        path for path in goldens['brave-adventurer'] if path.name.startswith('golden-')
    ]


def test_the_measured_demos_are_exactly_the_engines_bundled_demos():
    """One lookup (glitchygames.bundled_demos), under an editable install or a built one."""
    by_game = recordings_by_game()
    goldens = {
        path
        for paths in check_every_game_holds_a_golden(project_root=PROJECT_ROOT).values()
        for path in paths
    }
    measured = {
        (console_script, path.parent.parent.name, path.name)
        for console_script, paths in by_game.items()
        for path in paths
        if path not in goldens
    }
    engine_demos = {
        (demo.console_script, demo.package, demo.path.name)
        for demo in bundled_demos(packages=MEMBER_PACKAGES)
    }

    assert measured == engine_demos
    assert {(package, name) for _, package, name in engine_demos} == EXPECTED_BUNDLED_DEMOS


def test_no_golden_or_demo_is_left_to_no_game():
    """Every golden and bundled demo in the repository is one of our games' (none unclaimed)."""
    assert not unclaimed_goldens(
        games=OUR_SETTINGS.games, settings=OUR_SETTINGS, project_root=PROJECT_ROOT
    )
    assert not unclaimed_demos(games=OUR_SETTINGS.games, project_root=PROJECT_ROOT)


def test_a_recording_in_the_repository_is_named_by_its_repository_path():
    """Our ledger names: repository paths (an editable install's), as the rows always had."""
    names = [
        name
        for console_script in OUR_SETTINGS.games
        for name in ledger_names(
            identity=console_script_identity(console_script=console_script),
            settings=OUR_SETTINGS,
            project_root=PROJECT_ROOT,
        )
    ]

    assert 'src/games/paddleslap/tests/fixtures/replays/golden.jsonl.gz' in names
