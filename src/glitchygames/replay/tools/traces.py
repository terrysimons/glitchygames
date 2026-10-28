"""``glitchygames record-trace``, ``replay-trace``, ``record-golden-trace``, ``record-session``.

Each of these tools runs the game, so its subcommand starts it as a child process with the
tool's flag (``Tool.child_arguments``: ``--record-trace PATH``, ``--replay-trace PATH``,
``--record-golden-trace PATH``, ``--record-session PATH`` and the options given), where the
game's own engine records or replays exactly as the flag on the game does. The child's exit
status is the command's.

- ``record-trace GAME PATH``: ``GAME`` is read by ``children.resolve_game`` (a script path, an
  entry point, a console script or a module).
- ``record-golden-trace GAME PATH --input-script MODULE:NAME --frame-count N``: ``GAME`` is read
  as ``record-trace``'s is. On the game, the flag runs the golden-trace harness in place of the
  game's own run (``record_golden_trace_on_the_game``): the game's scene class, driven by the
  input script for N frames at a fixed 1/60 second, every sprite sampled each frame
  (glitchygames/replay/tools/golden_traces.py).
- ``record-session GAME PATH --input-script MODULE:NAME --frame-count N``: ``GAME`` is read as
  ``record-trace``'s is. On the game, the flag records a scripted session in place of the game's
  own run (``record_session_on_the_game``): the game's scene class run for real, its own frame
  loop recorded with ``--record-trace``, while a supervisor plays the input script (and a
  ``--controls-tail``) as a player's input (glitchygames/replay/tools/scripted_sessions.py).
- ``replay-trace PATH``: the game is the one the recording's header names: the installed console
  script that starts its module (``children.console_script_for_game_module``). When that module
  no longer imports (a moved script), or no console script starts it, the command asks for
  ``--game GAME``, read as ``record-trace``'s ``GAME`` is.

Arguments after a bare ``--`` go to the game unchanged (``--resolution 640x480``).
The command says on standard error which game it runs and how it read it.
"""

from __future__ import annotations

import dataclasses
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glitchygames.exit_codes import ExitCode
from glitchygames.process import TimeoutExpired
from glitchygames.replay.tools.children import (
    GAME_FORMS,
    GameLaunch,
    UnknownGameError,
    console_script_for_game_module,
    entry_point_command,
    game_entry_point,
    installed_console_scripts,
    launch_game,
    module_is_importable,
    recorded_game_module,
    resolve_game,
)

if TYPE_CHECKING:
    import argparse

    from glitchygames.replay.tools.registry import Tool
    from glitchygames.scenes import Scene

LOG = logging.getLogger('game.tools')

# How each form of GAME is named when the command says which game it runs
FORM_DESCRIPTIONS = {
    'script': 'a script',
    'entry-point': 'an entry point',
    'console-script': 'an installed console script',
    'module': 'a module',
}


def project_root(*, arguments: argparse.Namespace) -> Path:
    """Return the subcommand's ``--project-root``, or the current directory.

    Args:
        arguments: The subcommand's parsed arguments.

    Returns:
        The directory.

    """
    root: Path | None = arguments.project_root
    return Path.cwd() if root is None else root


def say(*, tool: Tool, message: str) -> None:
    """Write one line from the command to standard error (standard output is the game's).

    Args:
        tool: The tool running.
        message: The line.

    """
    sys.stderr.write(f'glitchygames {tool.name}: {message}\n')


def run_game_with_tool(
    *,
    tool: Tool,
    arguments: argparse.Namespace,
    game_arguments: list[str],
    game: str,
    launch: GameLaunch,
) -> int:
    """Start the game as a child with the tool's flags and the game's own arguments.

    Args:
        tool: The tool.
        arguments: The subcommand's parsed arguments.
        game_arguments: The arguments after a bare ``--``.
        game: The game, as named (for the message).
        launch: How to start it (with its timeout, for ``verify`` and ``measure``: the project's
            ``game-timeout-seconds``).

    Returns:
        The child's exit status, or ``ExitCode.INTERNAL_ERROR`` for a game stopped at its
        timeout (said on standard error, naming the game and the timeout).

    """
    say(tool=tool, message=f'running {game} ({FORM_DESCRIPTIONS[launch.form]})')
    try:
        finished = launch_game(
            launch=launch,
            arguments=[*tool.child_arguments(arguments=arguments), *game_arguments],
            working_directory=project_root(arguments=arguments),
        )
    except TimeoutExpired as timeout:
        say(
            tool=tool,
            message=(
                f'{game} was stopped: still running after {timeout.timeout:g} seconds '
                '([tool.glitchygames] game-timeout-seconds)'
            ),
        )
        return ExitCode.INTERNAL_ERROR
    return finished.returncode


def resolve_named_game(*, tool: Tool, game: str, arguments: argparse.Namespace) -> GameLaunch:
    """Read a game the user named (``GAME``, ``--game``).

    Args:
        tool: The tool (for the message).
        game: What the user typed.
        arguments: The subcommand's parsed arguments (``--project-root``).

    Returns:
        How to start it.

    Raises:
        UnknownGameError: If it names no game (said on standard error first).

    """
    try:
        return resolve_game(game=game, project_root=project_root(arguments=arguments))
    except UnknownGameError as error:
        say(tool=tool, message=str(error))
        raise


def record_trace_command(
    *, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]
) -> int:
    """Run ``glitchygames record-trace GAME PATH``: the game records its session to PATH.

    Args:
        tool: The record-trace tool.
        arguments: The subcommand's parsed arguments.
        game_arguments: The arguments after a bare ``--``, for the game.

    Returns:
        The game's exit status, or ``ExitCode.OPTIONS_REFUSED`` when ``GAME`` names no game.

    """
    game: str = arguments.game
    try:
        launch = resolve_named_game(tool=tool, game=game, arguments=arguments)
    except UnknownGameError:
        return ExitCode.OPTIONS_REFUSED
    return run_game_with_tool(
        tool=tool, arguments=arguments, game_arguments=game_arguments, game=game, launch=launch
    )


def asking_for_game(*, reason: str) -> str:
    """Say that a recording's game can't be found, and how to name it with ``--game``.

    Args:
        reason: Why the recording's game can't be found.

    Returns:
        The message.

    """
    return f'{reason}; name the game with --game GAME ({"; ".join(GAME_FORMS)})'


@dataclasses.dataclass(frozen=True)
class RecordedGameRefusal:
    """Why a recording's own game can't replay it (``find_recorded_game``).

    Attributes:
        exit_code: How the tool ends for it: ``ExitCode.MISSING_INPUT`` (no recording),
            ``ExitCode.UNUSABLE_INPUT`` (not a recording) or ``ExitCode.OPTIONS_REFUSED`` (its
            game can't be found: ``--game`` names it).
        reason: Why, in a line (``asking_for_game``'s, for a game that can't be found).

    """

    exit_code: ExitCode
    reason: str


def find_recorded_game(
    *, recording: Path, project_root: Path
) -> tuple[str, GameLaunch] | RecordedGameRefusal:
    """Find the game a recording's header names: the console script that starts its module.

    Args:
        recording: The recording.
        project_root: The project (where the game's module may be found too).

    Returns:
        The console script and how to start it, or why it can't be found.

    """
    try:
        game_module = recorded_game_module(path=recording)
    except FileNotFoundError:
        return RecordedGameRefusal(
            exit_code=ExitCode.MISSING_INPUT, reason=f'{recording.as_posix()}: no such recording'
        )
    # A TraceFormatError is a ValueError
    except OSError, ValueError:
        return RecordedGameRefusal(
            exit_code=ExitCode.UNUSABLE_INPUT,
            reason=f'{recording.as_posix()}: not a readable recording',
        )
    except KeyError as error:
        return game_not_found(reason=f'{error.args[0]}, so it names no game')
    if not module_is_importable(module=game_module, search_directory=project_root):
        return game_not_found(
            reason=f"{recording.as_posix()}: its game's module {game_module!r} no longer imports"
        )
    try:
        console_script = console_script_for_game_module(
            entry_points=installed_console_scripts(), game_module=game_module
        )
    except KeyError as error:
        return game_not_found(
            reason=f'{recording.as_posix()}: no one console script starts it ({error.args[0]})'
        )
    entry_point = game_entry_point(console_script=console_script)
    return console_script, GameLaunch(
        form='console-script', command=entry_point_command(entry_point=entry_point)
    )


def game_not_found(*, reason: str) -> RecordedGameRefusal:
    """Refuse a recording whose game can't be found, asking for ``--game``.

    Args:
        reason: Why its game can't be found.

    Returns:
        ``ExitCode.OPTIONS_REFUSED``, with ``asking_for_game``'s message.

    """
    return RecordedGameRefusal(
        exit_code=ExitCode.OPTIONS_REFUSED, reason=asking_for_game(reason=reason)
    )


def recorded_game_launch(
    *, tool: Tool, recording: Path, arguments: argparse.Namespace
) -> tuple[str, GameLaunch] | ExitCode:
    """Find the game a recording's header names, saying on standard error why when it can't.

    Args:
        tool: The replay-trace tool.
        recording: The recording.
        arguments: The subcommand's parsed arguments (``--project-root``).

    Returns:
        The console script and how to start it (``find_recorded_game``); or the exit code
        when it can't be found.

    """
    found = find_recorded_game(recording=recording, project_root=project_root(arguments=arguments))
    if isinstance(found, RecordedGameRefusal):
        say(tool=tool, message=found.reason)
        return found.exit_code
    return found


def replay_trace_command(
    *, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]
) -> int:
    """Run ``glitchygames replay-trace PATH``: the recording's game replays it.

    Args:
        tool: The replay-trace tool.
        arguments: The subcommand's parsed arguments.
        game_arguments: The arguments after a bare ``--``, for the game.

    Returns:
        The game's exit status (the replay's ``ExitCode``), or the exit code that says why no
        game ran (``recorded_game_launch``; ``ExitCode.OPTIONS_REFUSED`` for a ``--game`` that
        names no game).

    """
    named_game: str | None = arguments.game
    if named_game is not None:
        try:
            launch = resolve_named_game(tool=tool, game=named_game, arguments=arguments)
        except UnknownGameError:
            return ExitCode.OPTIONS_REFUSED
        game = named_game
    else:
        found = recorded_game_launch(
            tool=tool, recording=Path(arguments.replay_trace), arguments=arguments
        )
        if isinstance(found, ExitCode):
            return found
        game, launch = found
    return run_game_with_tool(
        tool=tool, arguments=arguments, game_arguments=game_arguments, game=game, launch=launch
    )


def refused(*, message: str, exit_code: ExitCode) -> ExitCode:
    """Log why a tool run on the game is refused, as an error (no traceback: it is the user's).

    Args:
        message: Why.
        exit_code: How the run ends.

    Returns:
        ``exit_code``.

    """
    LOG.error('%s', message)
    return exit_code


def record_golden_trace_command(
    *, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]
) -> int:
    """Run ``glitchygames record-golden-trace GAME PATH``: the game records its golden trace.

    ``GAME`` is read and started as ``record-trace``'s is (``record_trace_command``); the child
    gets ``--record-golden-trace PATH`` and the input script, frame count and seed given.

    Args:
        tool: The record-golden-trace tool.
        arguments: The subcommand's parsed arguments.
        game_arguments: The arguments after a bare ``--``, for the game.

    Returns:
        The game's exit status, or ``ExitCode.OPTIONS_REFUSED`` when ``GAME`` names no game.

    """
    return record_trace_command(tool=tool, arguments=arguments, game_arguments=game_arguments)


def record_golden_trace_on_the_game(
    *, options: dict[str, Any], game: type[Scene] | Scene
) -> ExitCode:
    """Run ``--record-golden-trace PATH`` on a game: record its golden trace in place of its run.

    The game's scene class (a scene the game passed in is run by its class) runs in the
    golden-trace harness, driven by ``--input-script MODULE:NAME`` (``load_input_script``: a
    callable taking no arguments that returns an ``InputScript``) for ``--frame-count N``
    frames, seeded by ``--random-seed`` (a random seed when not given, as any run rolls one,
    which the trace then names as ``random_seed``, so the golden can be made again under it).
    The trace is written to PATH with the golden source (``GOLDEN_TRACE_SOURCE``), as
    scripts/record_golden_traces.py writes ours.

    Args:
        options: The game's parsed options (``GameEngine.OPTIONS``).
        game: The game (its class, or a scene the game passed in).

    Returns:
        ``ExitCode.SUCCESS`` once the trace is written; ``ExitCode.OPTIONS_REFUSED`` when the
        input script reference names no input script; ``ExitCode.CANNOT_WRITE_OUTPUT`` when
        the trace can't be written.

    """
    # Imported here: the harness imports the engine, which imports the tool table (this module)
    from glitchygames.replay.tools import golden_traces
    from glitchygames.scenes import Scene
    from glitchygames.tracing import write_trace

    try:
        script = golden_traces.load_input_script(reference=options['input_script'])
    except golden_traces.InputScriptError as error:
        return refused(message=f'--input-script: {error}', exit_code=ExitCode.OPTIONS_REFUSED)
    trace = golden_traces.record_trace(
        scene_class=type(game) if isinstance(game, Scene) else game,
        script=script,
        frame_count=options['frame_count'],
        random_seed=options.get('random_seed'),
    )
    path = Path(options['record_golden_trace'])
    try:
        write_trace(trace={'source': golden_traces.GOLDEN_TRACE_SOURCE, **trace}, path=path)
    except OSError as error:
        return refused(
            message=f'--record-golden-trace: cannot write {path} ({error})',
            exit_code=ExitCode.CANNOT_WRITE_OUTPUT,
        )
    return ExitCode.SUCCESS


def record_session_command(
    *, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]
) -> int:
    """Run ``glitchygames record-session GAME PATH``: the game records a scripted session.

    ``GAME`` is read and started as ``record-trace``'s is (``record_trace_command``); the child
    gets ``--record-session PATH`` and the input script, frame count, controls tail, flags and
    seed given.

    Args:
        tool: The record-session tool.
        arguments: The subcommand's parsed arguments.
        game_arguments: The arguments after a bare ``--``, for the game.

    Returns:
        The game's exit status, or ``ExitCode.OPTIONS_REFUSED`` when ``GAME`` names no game.

    """
    return record_trace_command(tool=tool, arguments=arguments, game_arguments=game_arguments)


def record_session_on_the_game(*, options: dict[str, Any], game: type[Scene] | Scene) -> ExitCode:
    """Run ``--record-session PATH`` on a game: record a scripted session in place of its run.

    The game's scene class (a scene the game passed in is run by its class) runs for real in
    the scripted-session recorder (glitchygames/replay/tools/scripted_sessions.py), recorded to
    PATH, while ``--input-script MODULE:NAME`` is played for ``--frame-count N`` frames, then
    ``--controls-tail MODULE:NAME`` when given (both read by ``load_input_script``), seeded by
    ``--random-seed`` (a random seed when not given), with ``--polled-input`` and
    ``--input-only-placements`` as given.

    Args:
        options: The game's parsed options (``GameEngine.OPTIONS``).
        game: The game (its class, or a scene the game passed in).

    Returns:
        ``ExitCode.SUCCESS`` once the session is recorded; ``ExitCode.OPTIONS_REFUSED`` when an
        input script reference names no input script, or the script cannot be recorded as
        input for that many frames (a placement inside the session, input before frame 0, a
        controls tail that is not key events only); ``ExitCode.UNUSABLE_INPUT`` when the
        controls tail's quit did not end the game (the recording is written, but does not end
        with the game quitting); ``ExitCode.CANNOT_WRITE_OUTPUT`` when the recording's
        directory can't be made.

    """
    # Imported here: the recorder imports the engine, which imports the tool table (this module)
    from glitchygames.replay.tools import golden_traces, scripted_sessions
    from glitchygames.scenes import Scene

    controls_tail_reference: str | None = options.get('controls_tail')
    try:
        script = golden_traces.load_input_script(reference=options['input_script'])
        controls_tail = (
            None
            if controls_tail_reference is None
            else golden_traces.load_input_script(reference=controls_tail_reference)
        )
    except golden_traces.InputScriptError as error:
        return refused(message=f'--record-session: {error}', exit_code=ExitCode.OPTIONS_REFUSED)
    scene_class = type(game) if isinstance(game, Scene) else game
    frame_count: int = options['frame_count']
    input_only_placements = bool(options.get('input_only_placements'))
    # The session's own checks, before anything runs; the game's own errors are not caught
    # here, so they end the run as any game's do (the engine's crash boundary)
    refusal = scripted_sessions.scripted_session_refusal(
        script=script,
        frame_count=frame_count,
        controls_tail=controls_tail,
        input_only_placements=input_only_placements,
    )
    if refusal is not None:
        return refused(message=f'--record-session: {refusal}', exit_code=ExitCode.OPTIONS_REFUSED)
    path = Path(options['record_session'])
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        return refused(
            message=f'--record-session: cannot write {path} ({error})',
            exit_code=ExitCode.CANNOT_WRITE_OUTPUT,
        )
    try:
        scripted_sessions.record_scripted_session(
            scene_class=scene_class,
            script=script,
            frame_count=frame_count,
            path=path,
            controls_tail=controls_tail,
            polled_input=bool(options.get('polled_input')),
            input_only_placements=input_only_placements,
            random_seed=options.get('random_seed'),
        )
    except scripted_sessions.GameDidNotQuitError as error:
        return refused(message=f'--record-session: {error}', exit_code=ExitCode.UNUSABLE_INPUT)
    return ExitCode.SUCCESS
