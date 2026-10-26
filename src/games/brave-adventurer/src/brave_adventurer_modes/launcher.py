"""Brave Adventurer's launcher: ``main()``, the one command (``brave-adventurer``) for both games.

The project holds two games on shared primitives: Classic (``brave_adventurer``), whose sprites
are drawn in code, and Papyrus (``brave_adventurer_papyrus``), the Egyptian edition with
sprite-sheet art. ``main()`` starts one of them, in this order:

1. ``--game classic|papyrus``: read (``parse_known_args``) and removed from ``sys.argv``, then
   that game's own ``main()`` runs unchanged, so its arguments, scene flow, recording header and
   recordings stay its own. With a recording to replay as well, the flag still decides: the
   game's own replay refuses another game's recording.
2. A recording to replay (``--replay-trace PATH``, as the golden-replay plugin, the run ledger's
   rebaselines, watched replays and their restarts start one): its header names the game it was
   made in by logical name (glitchygames/logical_names.py), and that game's own ``main()`` runs,
   without the title screen (``game_for_recording``). So a member with one console script
   replays both games' goldens (glitchygames/testing/replays.py ``recording_console_script``). A
   recording made from the title screen names the title screen: it is replayed from there. A
   recording of any other game is refused (``ExitCode.UNUSABLE_INPUT``, naming the games this
   command replays); one whose header cannot be read goes to the engine, which refuses it as it
   refuses any unusable or missing recording.
3. Otherwise the title screen (brave_adventurer_modes/title.py) offers both games and starts the
   chosen one's scene in the same engine.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

import brave_adventurer
import brave_adventurer_papyrus
from brave_adventurer_modes.title import GAME_CHOICES, TitleScene, add_game_argument
from glitchygames.engine import GameEngine
from glitchygames.exit_codes import ExitCode
from glitchygames.logical_names import logical_name
from glitchygames.replay.driver import GAME_HEADER_FIELD
from glitchygames.replay.rebuild import REPLAY_TRACE_OPTION
from glitchygames.tracing import TraceReader

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

log = logging.getLogger('game')

# Each game's own main(), by its name on the command line (GAME_CHOICES holds its scene)
GAMES_BY_NAME: dict[str, Callable[[], None]] = {
    'classic': brave_adventurer.main,
    'papyrus': brave_adventurer_papyrus.main,
}


def recorded_game(*, path: Path) -> str | None:
    """Return the logical name a recording's header names its game by.

    A file that cannot be read raises what ``TraceReader`` raises: an OSError
    (FileNotFoundError when it does not exist), or a ValueError when it is not a recording
    (glitchygames.tracing.TraceFormatError).

    Args:
        path: The recording.

    Returns:
        The header's ``game`` (``games.brave_adventurer.game:BraveAdventurerScene``), or None
        for a recording made before logical names (it has none).

    """
    with TraceReader(path=path) as reader:
        recorded = reader.header.get(GAME_HEADER_FIELD)
    return recorded if isinstance(recorded, str) else None


def game_named_by(*, logical_game: str | None) -> str | None:
    """Return the name of the game whose scene has a logical name.

    Args:
        logical_game: A recording's ``game`` (``recorded_game``), or None.

    Returns:
        ``'classic'`` or ``'papyrus'``, or None when it is neither game's scene.

    """
    for choice in GAME_CHOICES:
        if logical_name(scene_class=choice.scene_class) == logical_game:
            return choice.name
    return None


def game_for_recording(*, path: Path) -> str | None:
    """Return the name of the game a recording was made in.

    Args:
        path: The recording.

    Returns:
        ``'classic'`` or ``'papyrus'``: the game whose scene the recording's header names by
        logical name; None when the recording is not one of these games' (another game's, the
        title screen's, one made before logical names, or a file that cannot be read).

    """
    try:
        logical_game = recorded_game(path=path)
    # A TraceFormatError is a ValueError
    except OSError, ValueError:
        return None
    return game_named_by(logical_game=logical_game)


def launcher_arguments() -> argparse.ArgumentParser:
    """Return the parser of the launcher's own argument, ``--game``.

    No help of its own (``-h`` goes on to the engine's parser, which lists ``--game`` too:
    TitleScene.args).

    Returns:
        The parser.

    """
    parser = argparse.ArgumentParser(add_help=False)
    add_game_argument(parser)
    return parser


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


def start_title_screen() -> None:
    """Run the engine on the title screen."""
    GameEngine(game=TitleScene).start()


def recorded_games_start(*, recording: Path) -> Callable[[], None]:
    """Return what starts the game a recording to replay was made in.

    Args:
        recording: The recording (``--replay-trace``).

    Returns:
        That game's own ``main()``; or ``start_title_screen`` for a recording made from the
        title screen, and for one whose header cannot be read (the engine refuses it with its
        own exit code and message, missing or unusable, as any game's would).

    """
    try:
        logical_game = recorded_game(path=recording)
    # A TraceFormatError is a ValueError
    except OSError, ValueError:
        return start_title_screen
    if logical_game == logical_name(scene_class=TitleScene):
        return start_title_screen
    game = game_named_by(logical_game=logical_game)
    if game is None:
        refuse_recording(recording=recording, logical_game=logical_game)
    return GAMES_BY_NAME[game]


def refuse_recording(*, recording: Path, logical_game: str | None) -> NoReturn:
    """Refuse to replay a recording none of this command's scenes made.

    Args:
        recording: The recording.
        logical_game: The game its header names, or None for a recording made before logical
            names (it names none: ``--game`` names it, and the game's replay then checks the
            recording's class and module as it always has).

    Raises:
        SystemExit: Always, with ``ExitCode.UNUSABLE_INPUT``.

    """
    if logical_game is None:
        log.error(
            'Cannot replay %s: it was made before logical names, so its header names no game '
            'to start; name the game: --game %s',
            recording,
            ' or --game '.join(GAMES_BY_NAME),
        )
    else:
        log.error(
            'Cannot replay %s: it is a recording of %s; this command replays only %s',
            recording,
            logical_game,
            ', '.join([
                *(logical_name(scene_class=choice.scene_class) for choice in GAME_CHOICES),
                logical_name(scene_class=TitleScene),
            ]),
        )
    raise SystemExit(ExitCode.UNUSABLE_INPUT)


def main() -> None:
    """Start the game ``--game`` names, else a recording's game, else the title screen."""
    launcher_options, remaining_arguments = launcher_arguments().parse_known_args(sys.argv[1:])
    # Each game's own parser (and the title screen's) reads sys.argv: without --game
    sys.argv = [sys.argv[0], *remaining_arguments]
    recording = recording_to_replay(arguments=remaining_arguments)
    if launcher_options.game is not None:
        start = GAMES_BY_NAME[launcher_options.game]
    elif recording is not None:
        start = recorded_games_start(recording=recording)
    else:
        start = start_title_screen
    start()
