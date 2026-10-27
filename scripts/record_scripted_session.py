r"""Record a scripted session of one of our games through the real engine: its golden replay.

Used for the golden replay fixtures in the workspace members'
``<member>/tests/fixtures/replays/`` (and later for bundled demos). The engine's scripted-session
recorder does the recording (glitchygames/replay/tools/scripted_sessions.py, which says how a
session runs: the supervisor, the controls tail and its quit, the real frame loop, placements
and polled input); any game's own sessions are recorded with ``--record-session`` (or
``glitchygames record-session``). This script holds only this repository's policy: each of our
games' golden input script (scripts/record_golden_traces.py: SCRIPT_BUILDERS) and controls tail
(``CONTROLS_TAIL_BUILDERS``, scripts/golden_inputs.py), which of them may place sprites inside a
session (``INPUT_ONLY_PLACEMENT_GAMES``) or read polled input (``POLLED_INPUT_GAMES``), the seed
they are recorded under (``RANDOM_SEED``) and where each golden goes (``fixture_path``).
``--frames N`` plays the script's frames 0 to N - 1.

The controls rule (golden replays): after the script's frames the supervisor plays the game's
controls tail (session-only, so the golden traces, which replay the same scripts, never see it).
Its first frame releases every key the script left held; then it presses the controls the script
does not (each key of an action bound to several, every pause key, a pause where the script's
frames hold none), and ends with the game's own quit control, so the recording's last frame holds
the QUIT the game posted. tests/replay/test_golden_replays.py checks that every control the game
binds is exercised (or listed with the reason it cannot be: no gamepad in the session), that the
game pauses and resumes, and that the recording ends on the game's own QUIT.

``--script-only`` (demos, and short test sessions) leaves the tail out: at frame N - 1 the
session ends, so the recording holds frames 0 to N - 1 and no quit.

Script placements move sprites directly, so a session may not run a frame a placement is
scheduled before, except for games whose placements only steer the script's own input
(INPUT_ONLY_PLACEMENT_GAMES: PaddleSlap's placements release its tracked keys and resume
tracking). Clockwork Keep (first placement before frame 330) and both Brave Adventurer editions
(first placement before frame 400) are therefore recorded for fewer frames than their placements.

Regenerating the fixtures: only deliberately, after reviewing why they changed, never just to make
a failing golden replay pass (the same rule as the golden traces in tests/world/golden/). A
failing golden replay means the engine or a game no longer reproduces a recorded session; find out
why first. A re-recorded fixture never matches the one it replaces, in content as well as bytes:
each frame's dt is measured in real time, game logic moves by dt (so sprites differ by a few
pixels), FPS events carry the measured rate, and processing times and the header's recorded_at
differ. So diffing an old fixture with a new one shows mostly noise; what counts is that the new
one replays clean and holds the same scenes and scripted input. (A rebaseline keeps the inputs,
dt included: plans/2026-10-20-recording-content-hash-and-history.md.) Then, one command per game:

    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python -m scripts.record_scripted_session \
        --game paddleslap --frames 600
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python -m scripts.record_scripted_session \
        --game clockwork_keep --frames 330
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python -m scripts.record_scripted_session \
        --game brave_adventurer --frames 400
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python -m scripts.record_scripted_session \
        --game brave_adventurer_papyrus --frames 400
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python -m scripts.record_scripted_session \
        --game mr_muncher --frames 1950
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run python -m scripts.record_scripted_session \
        --game drawing_fire --frames 1600

With their controls tails the recordings hold 622 (PaddleSlap), 532 (Clockwork Keep), 472 (each
Brave Adventurer edition), 2072 (Mr. Muncher) and 1614 (Drawing Fire) frames. Mr. Muncher's
script runs 1950 frames, not more (its death at about frame 1650 and the next life's READY
included), so its fixture stays under 100 KB. Drawing Fire's cannot: its first frame alone is
about 125 KB compressed (the scene start holds every random stream's state, a Mersenne Twister's
625 numbers for each of its 19 streams, twice: at setup and at the first logic frame), so its
fixture is about 185 KB. Its player's first death came between frames 740 and 920 in trial
recordings (frame 809 in the fixture); a re-recording must still hold his death and takeover,
which tests/replay/test_golden_replays.py checks in the recorded internal events.

Drawing Fire reads its controls from the frame's polled input (``current_input()``), which a
posted event never changes in SDL: for the games in POLLED_INPUT_GAMES (Drawing Fire alone) the
session's live snapshots show the supervisor's posted input, as a real player's would. Only for
them: every other game's session records the snapshots it always did, so its re-recordings keep
their content hashes.

Without ``--output`` the recording goes to its game's workspace member,
``<member>/tests/fixtures/replays/golden.jsonl.gz`` (``golden-<game>.jsonl.gz`` for each game
of a member holding several: ``GOLDEN_FIXTURE_NAMES``; ``fixture_path``). Keep each fixture
under 100 KB.

The recorder itself moved to the engine (Stage D, Task D4b), re-keyed from our game keys to a
scene class, an input script and flags; this script calls it.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

from glitchygames.replay.tools.children import recording_console_script
from glitchygames.replay.tools.golden_traces import RANDOM_SEED
from glitchygames.replay.tools.scripted_sessions import record_scripted_session
from scripts.golden_inputs import (
    brave_adventurer_controls,
    clockwork_keep_controls,
    drawing_fire_controls,
    mr_muncher_controls,
    paddleslap_controls,
)
from scripts.record_golden_traces import GAME_MODULES, GAME_SCENES, PROJECT_ROOT, SCRIPT_BUILDERS
from scripts.workspace_packages import workspace_members

if TYPE_CHECKING:
    from collections.abc import Callable

    from glitchygames.replay.tools.golden_traces import InputScript

# Games whose script placements only steer the script's own input (they move no sprite)
INPUT_ONLY_PLACEMENT_GAMES = frozenset({'paddleslap'})
# Games that read their controls from the frame's polled input (current_input()), not from
# events: their sessions' live snapshots show the posted input (polled_input). Only these:
# another game's re-recording keeps the snapshots it had (held keys absent), so its content
# hashes, and the metrics ledger's behavior changes, stay as they were
POLLED_INPUT_GAMES = frozenset({'drawing_fire'})

# Golden replay fixtures: each game's are directly in its workspace member's replay fixtures
# directory. Game key -> the fixtures directory of the workspace member whose package holds the
# game (src/games/mr-muncher/tests/fixtures/replays); every game is in one since Drawing Fire,
# the last in the engine's examples, moved (the root's tests/fixtures/replays/<console-script>/
# layout, which the replay plugin still collects, holds no game's golden)
REPLAY_FIXTURE_DIRECTORIES: dict[str, Path] = {
    game_key: member.replay_fixtures_directory
    for member in workspace_members(project_root=PROJECT_ROOT)
    for game_key, module in GAME_MODULES.items()
    if module.partition('.')[0] in member.import_packages
}
REPLAY_FIXTURE_SUFFIX = '.jsonl.gz'
DEFAULT_FIXTURE_NAME = 'golden'
# Game key -> its golden's name, for the games of a workspace member that holds several: their
# goldens share the member's fixtures directory, so each is named apart (golden-<game>;
# docs/architecture/game_packages.md, "Several games in one project")
GOLDEN_FIXTURE_NAMES: dict[str, str] = {
    'brave_adventurer': 'golden-classic',
    'brave_adventurer_papyrus': 'golden-papyrus',
}

# Game key -> its controls tail (scripts/golden_inputs.py): input a golden replay session plays
# after the golden script's frames (never part of the script, so the golden traces never see
# it). It exercises the controls the script does not, pauses where the script's frames hold no
# pause, and ends with the game's own quit control: the recorded QUIT is posted by the game, so
# a replay whose game no longer quits diverges. tests/replay/test_golden_replays.py checks every
# bound control is exercised.
CONTROLS_TAIL_BUILDERS: dict[str, Callable[[], InputScript]] = {
    'clockwork_keep': clockwork_keep_controls,
    'brave_adventurer': brave_adventurer_controls,
    'brave_adventurer_papyrus': brave_adventurer_controls,
    'paddleslap': paddleslap_controls,
    'mr_muncher': mr_muncher_controls,
    'drawing_fire': drawing_fire_controls,
}


def fixture_path(*, game_key: str, name: str | None = None) -> Path:
    """Return where a game's golden replay fixture is stored.

    Args:
        game_key: Which game (a key of GAME_SCENES).
        name: The fixture's name, without the suffix; by default the game's golden
            (``GOLDEN_FIXTURE_NAMES``, else ``DEFAULT_FIXTURE_NAME``).

    Returns:
        ``<member>/tests/fixtures/replays/<name>.jsonl.gz``: every game is in a workspace member
        (``REPLAY_FIXTURE_DIRECTORIES``).

    Raises:
        KeyError: If no workspace member's package holds the game (its member is missing from
            the workspace, or the game from GAME_MODULES).

    """
    if game_key not in REPLAY_FIXTURE_DIRECTORIES:
        message = f'{game_key!r}: no workspace member holds this game, so it has no fixtures'
        raise KeyError(message)
    if name is None:
        name = GOLDEN_FIXTURE_NAMES.get(game_key, DEFAULT_FIXTURE_NAME)
    return REPLAY_FIXTURE_DIRECTORIES[game_key] / f'{name}{REPLAY_FIXTURE_SUFFIX}'


def game_console_script(*, game_key: str) -> str:
    """Return the installed console script that replays a game's golden replay.

    It is found as the replay pytest plugin finds it, so [project.scripts] is the one list: a
    game is replayed by its workspace member's console script (``recording_console_script``),
    and one console script may start several games (Brave Adventurer's launcher starts Classic
    and Papyrus, choosing by the recording's header).

    Args:
        game_key: Which game (a key of GAME_SCENES).

    Returns:
        The console script.

    """
    return recording_console_script(path=fixture_path(game_key=game_key))


# Game key -> the console script (a pyproject.toml's [project.scripts]) that replays its golden
# replay (game_console_script). Keyed by game, not by console script: Classic and Papyrus share
# the member's one script, brave-adventurer
GAME_CONSOLE_SCRIPTS: dict[str, str] = {
    game_key: game_console_script(game_key=game_key) for game_key in SCRIPT_BUILDERS
}


def record_golden_session(
    *, game_key: str, frame_count: int, path: Path, exercise_controls: bool
) -> None:
    """Record one of our games' scripted session, as its golden replay is recorded.

    Our policy for the game, given to the engine's recorder (``record_scripted_session``): its
    golden script, its controls tail when ``exercise_controls``, whether it reads polled input
    or may place sprites inside the session, and our goldens' seed (``RANDOM_SEED``).

    Args:
        game_key: Which game (a key of GAME_SCENES).
        frame_count: How many of the script's frames to record.
        path: Where the recording goes.
        exercise_controls: Play the game's controls tail (CONTROLS_TAIL_BUILDERS) after the
            script, so the session ends when the game quits (golden replays); False ends it
            after the script's frames (demos, short sessions).

    """
    # The script is built before the tail, as the recorder did before the move
    script = SCRIPT_BUILDERS[game_key]()
    record_scripted_session(
        scene_class=GAME_SCENES[game_key],
        script=script,
        frame_count=frame_count,
        path=path,
        controls_tail=CONTROLS_TAIL_BUILDERS[game_key]() if exercise_controls else None,
        polled_input=game_key in POLLED_INPUT_GAMES,
        input_only_placements=game_key in INPUT_ONLY_PLACEMENT_GAMES,
        random_seed=RANDOM_SEED,
    )


def main() -> None:
    """Command line: --game KEY --frames N [--script-only] [--output PATH]."""
    parser = argparse.ArgumentParser(description='Record a scripted session through the engine')
    parser.add_argument('--game', required=True, choices=sorted(GAME_SCENES))
    parser.add_argument(
        '--frames',
        required=True,
        type=int,
        help="how many of the golden script's frames to record",
    )
    parser.add_argument(
        '--script-only',
        action='store_true',
        help="end after the script's frames, without the controls tail and its quit (demos)",
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=None,
        help="where the recording goes (default: the game's golden replay fixture)",
    )
    arguments = parser.parse_args()
    path = arguments.output or fixture_path(game_key=arguments.game)
    record_golden_session(
        game_key=arguments.game,
        frame_count=arguments.frames,
        path=path,
        exercise_controls=not arguments.script_only,
    )
    sys.stdout.write(f'{arguments.game}: {arguments.frames} script frames -> {path}\n')


if __name__ == '__main__':
    main()
