"""Record golden traces of our games, driven headless with their scripted input.

A golden trace is the rect and visibility of every sprite in the active scene's
``all_sprites``, recorded after each frame of a scripted, fully deterministic run, by the
engine's harness (glitchygames/replay/tools/golden_traces.py: ``record_trace``, which says how
the run is made deterministic). The traces in ``tests/world/golden/`` were recorded before the
engine world-space change (plans/2026-10-18-engine-world-space.md);
``tests/world/test_golden_traces.py`` replays the same scripts and fails on any difference that
is not listed and justified there. Only the games in ``GOLDEN_TRACE_GAMES`` have one; every game
in ``GAME_SCENES`` has a golden input script (``SCRIPT_BUILDERS``, from scripts/golden_inputs.py),
which scripts/record_scripted_session.py records as its golden replay.

This script holds only this repository's policy: which of our games there are, their input
scripts and where their traces go. The harness is the engine's, and any game's own traces are
recorded with ``--record-golden-trace`` (or ``glitchygames record-golden-trace``).

Games are loaded only when needed: many tests import this script for its tables and run no
game, so importing it imports no workspace member. ``GAME_SCENES`` imports a game's scene class
the first time it is looked up (``GameSceneClasses``), and each input script imports what it
reads of its game where it reads it.

Usage:
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python -m scripts.record_golden_traces
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

from glitchygames.replay.tools.golden_traces import (
    GOLDEN_TRACE_SOURCE,
    RANDOM_SEED,
    GameSceneClasses,
    record_trace,
)
from glitchygames.tracing import write_trace
from scripts.golden_inputs import (
    brave_adventurer_script,
    clockwork_keep_script,
    drawing_fire_script,
    mr_muncher_script,
    paddleslap_script,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from glitchygames.replay.tools.golden_traces import InputScript

# Project root (scripts/ is one level below project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIRECTORY = PROJECT_ROOT / 'tests' / 'world' / 'golden'

DEFAULT_FRAME_COUNT = 900

# Game key -> the game's scene class, for every game with a golden input script: each in its
# own workspace member's package, imported only when the game is looked up
GAME_SCENES = GameSceneClasses({
    'clockwork_keep': 'clockwork_keep.game:ClockworkKeepScene',
    'brave_adventurer': 'brave_adventurer.game:BraveAdventurerScene',
    'brave_adventurer_papyrus': 'brave_adventurer_papyrus.game:PapyrusBraveAdventurerScene',
    'paddleslap': 'paddleslap:Game',
    'mr_muncher': 'mr_muncher.game:MrMuncherScene',
    'drawing_fire': 'drawing_fire.game:DrawingFireScene',
})

# Game key -> the package holding the game: every game is in its own workspace member's package
# (plans/2026-10-24-workspace-packages.md), which scripts/record_scripted_session.py finds its
# fixtures directory by. A member's console script may be a launcher instead
# (Brave Adventurer's, brave_adventurer_modes, starts both its games; scripts/
# record_scripted_session.py GAME_CONSOLE_SCRIPTS)
GAME_MODULES: dict[str, str] = {
    'clockwork_keep': 'clockwork_keep',
    'brave_adventurer': 'brave_adventurer',
    'brave_adventurer_papyrus': 'brave_adventurer_papyrus',
    'paddleslap': 'paddleslap',
    'mr_muncher': 'mr_muncher',
    'drawing_fire': 'drawing_fire',
}

# The games whose golden traces (tests/world/golden/) were recorded before the world-space
# change: tests/world/test_golden_traces.py compares these. Games written after it (Mr. Muncher,
# Drawing Fire) have no such baseline; their golden replays cover them, each in its member's
# tests/fixtures/replays/ (src/games/mr-muncher/, src/games/drawing-fire/).
GOLDEN_TRACE_GAMES: tuple[str, ...] = (
    'clockwork_keep',
    'brave_adventurer',
    'brave_adventurer_papyrus',
    'paddleslap',
)

# Game key -> its golden input script's builder (scripts/golden_inputs.py)
SCRIPT_BUILDERS: dict[str, Callable[[], InputScript]] = {
    'clockwork_keep': clockwork_keep_script,
    'brave_adventurer': brave_adventurer_script,
    'brave_adventurer_papyrus': brave_adventurer_script,
    'paddleslap': paddleslap_script,
    'mr_muncher': mr_muncher_script,
    'drawing_fire': drawing_fire_script,
}


def golden_path(game_key: str) -> Path:
    """Return where a game's golden trace is stored.

    Args:
        game_key: Which game.

    Returns:
        The trace file path (gzip-compressed JSON Lines, see glitchygames/tracing.py).

    """
    return GOLDEN_DIRECTORY / f'{game_key}.jsonl.gz'


def main() -> None:
    """Record and write the golden trace of every game that has one (GOLDEN_TRACE_GAMES).

    It takes no arguments: ``--help`` prints the usage and records nothing, and any other
    argument is refused (argparse exits 2). Before it read its arguments, ``--help`` re-recorded
    every trace in tests/world/golden/.
    """
    argparse.ArgumentParser(
        description=(
            'Record the golden trace of every game that has one (GOLDEN_TRACE_GAMES) into '
            f'{GOLDEN_DIRECTORY.relative_to(PROJECT_ROOT)}; it overwrites the committed traces, so '
            'only deliberately (tests/world/test_golden_traces.py says when)'
        )
    ).parse_args()
    for game_key in GOLDEN_TRACE_GAMES:
        trace = record_trace(
            scene_class=GAME_SCENES[game_key],
            script=SCRIPT_BUILDERS[game_key](),
            frame_count=DEFAULT_FRAME_COUNT,
            # Our goldens' fixed seed: without one the harness rolls a random seed, as any run
            random_seed=RANDOM_SEED,
        )
        # Our golden traces name their game by its key (the harness's default is the scene's
        # logical name); the key stays where it was in the header
        trace['game'] = game_key
        path = golden_path(game_key)
        write_trace(trace={'source': GOLDEN_TRACE_SOURCE, **trace}, path=path)
        sys.stdout.write(f'{game_key}: {len(trace["frames"])} frames -> {path}\n')


if __name__ == '__main__':
    main()
