"""The game's start: the title screen, or, to replay a recording, the scene that recording began on.

A golden replay records the neighborhood as its first scene (the golden rules: the recording's
game is the gameplay scene, tests/replay/test_golden_replays.py), while a player's run starts on
the title. The engine refuses a recording whose header names another game, so ``main`` reads the
header of ``--replay-trace``'s recording and starts that scene. Brave Adventurer's launcher does
the same (src/games/brave-adventurer/src/brave_adventurer_modes/launcher.py), from which
``recorded_game`` and ``recording_to_replay`` are adapted.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from glitchygames.engine import GameEngine
from glitchygames.logical_names import logical_name
from glitchygames.replay.driver import GAME_HEADER_FIELD
from glitchygames.replay.rebuild import REPLAY_TRACE_OPTION
from glitchygames.tracing import TraceReader
from zombies_aint_my_neighbors.demo_neighborhood import DemoNeighborhoodScene
from zombies_aint_my_neighbors.neighborhood import NeighborhoodScene
from zombies_aint_my_neighbors.title import TitleScene

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glitchygames.scenes import Scene


def recording_to_replay(*, arguments: Sequence[str]) -> Path | None:
    """Return the recording the arguments ask the engine to replay, without removing it.

    Args:
        arguments: The command-line arguments (without the program).

    Returns:
        ``--replay-trace``'s path, or None.

    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(REPLAY_TRACE_OPTION, default=None)
    known, _others = parser.parse_known_args(list(arguments))
    return None if known.replay_trace is None else Path(known.replay_trace)


def recorded_game(*, path: Path) -> str | None:
    """Return the logical name a recording's header gives its game, or None if it has none.

    Raises what ``TraceReader`` raises for a file that cannot be read: an OSError, or a
    ValueError when it is not a recording.

    Returns:
        The header's ``game``.

    """
    with TraceReader(path=path) as reader:
        recorded = reader.header.get(GAME_HEADER_FIELD)
    return recorded if isinstance(recorded, str) else None


def first_scene(*, arguments: Sequence[str]) -> type[Scene]:
    """Return the scene to start: the neighborhood a recording was made in, else the title.

    A recording that cannot be read, or that names another game, starts on the title too: the
    engine then refuses it with its own exit code and message, as any game's would.

    Args:
        arguments: The command-line arguments (without the program).

    Returns:
        The scene class.

    """
    recording = recording_to_replay(arguments=arguments)
    if recording is None:
        return TitleScene
    try:
        game = recorded_game(path=recording)
    # A TraceFormatError is a ValueError
    except OSError, ValueError:
        return TitleScene
    for scene_class in (NeighborhoodScene, DemoNeighborhoodScene):
        if game == logical_name(scene_class=scene_class):
            return scene_class
    return TitleScene


def main() -> None:
    """Run the game."""
    GameEngine(game=first_scene(arguments=sys.argv[1:])).start()
