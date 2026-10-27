"""``glitchygames record-trace``, ``replay-trace`` and ``record-golden-trace``: the game runs.

Each tool runs the game, so its subcommand starts it as a child process with the tool's flag
(``Tool.child_arguments``: ``--record-trace PATH``, ``--replay-trace PATH``,
``--record-golden-trace PATH`` and the options given), where the game's own engine records or
replays exactly as the flag on the game does. The child's exit status is the command's.

- ``record-trace GAME PATH``: ``GAME`` is read by ``children.resolve_game`` (a script path, an
  entry point, a console script or a module).
- ``record-golden-trace GAME PATH --input-script MODULE:NAME --frame-count N``: ``GAME`` is read
  as ``record-trace``'s is. On the game, the flag runs the golden-trace harness in place of the
  game's own run (``record_golden_trace_on_the_game``): the game's scene class, driven by the
  input script for N frames at a fixed 1/60 second, every sprite sampled each frame
  (glitchygames/replay/tools/golden_traces.py).
- ``replay-trace PATH``: the game is the one the recording's header names: the installed console
  script that starts its module (``children.console_script_for_game_module``). When that module
  no longer imports (a moved script), or no console script starts it, the command asks for
  ``--game GAME``, read as ``record-trace``'s ``GAME`` is.

Arguments after a bare ``--`` go to the game unchanged (``--resolution 640x480``).
The command says on standard error which game it runs and how it read it.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glitchygames.exit_codes import ExitCode
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
        launch: How to start it.

    Returns:
        The child's exit status.

    """
    say(tool=tool, message=f'running {game} ({FORM_DESCRIPTIONS[launch.form]})')
    finished = launch_game(
        launch=launch,
        arguments=[*tool.child_arguments(arguments=arguments), *game_arguments],
        working_directory=project_root(arguments=arguments),
    )
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


def ask_for_game(*, tool: Tool, reason: str) -> ExitCode:
    """Say that the recording's game can't be found, and how to name it with ``--game``.

    Args:
        tool: The tool.
        reason: Why the recording's game can't be found.

    Returns:
        ``ExitCode.OPTIONS_REFUSED``.

    """
    say(tool=tool, message=f'{reason}; name the game with --game GAME ({"; ".join(GAME_FORMS)})')
    return ExitCode.OPTIONS_REFUSED


def recorded_game_launch(
    *, tool: Tool, recording: Path, arguments: argparse.Namespace
) -> tuple[str, GameLaunch] | ExitCode:
    """Find the game a recording's header names: the console script that starts its module.

    Args:
        tool: The replay-trace tool.
        recording: The recording.
        arguments: The subcommand's parsed arguments (``--project-root``).

    Returns:
        The console script and how to start it; or the exit code when it can't be found:
        ``ExitCode.MISSING_INPUT`` (no recording), ``ExitCode.UNUSABLE_INPUT`` (not a
        recording) or ``ExitCode.OPTIONS_REFUSED`` (its game can't be found: ``--game``).

    """
    try:
        game_module = recorded_game_module(path=recording)
    except FileNotFoundError:
        say(tool=tool, message=f'{recording}: no such recording')
        return ExitCode.MISSING_INPUT
    # A TraceFormatError is a ValueError
    except OSError, ValueError:
        say(tool=tool, message=f'{recording}: not a readable recording')
        return ExitCode.UNUSABLE_INPUT
    except KeyError as error:
        return ask_for_game(tool=tool, reason=f'{error.args[0]}, so it names no game')
    if not module_is_importable(
        module=game_module, search_directory=project_root(arguments=arguments)
    ):
        return ask_for_game(
            tool=tool,
            reason=f"{recording}: its game's module {game_module!r} no longer imports",
        )
    try:
        console_script = console_script_for_game_module(
            entry_points=installed_console_scripts(), game_module=game_module
        )
    except KeyError as error:
        return ask_for_game(
            tool=tool, reason=f'{recording}: no one console script starts it ({error.args[0]})'
        )
    entry_point = game_entry_point(console_script=console_script)
    return console_script, GameLaunch(
        form='console-script', command=entry_point_command(entry_point=entry_point)
    )


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
    frames, seeded by ``--random-seed`` (the harness's ``RANDOM_SEED`` when not given, so a
    golden trace is reproducible without one). The trace is written to PATH with the golden
    source (``GOLDEN_TRACE_SOURCE``), as scripts/record_golden_traces.py writes ours.

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
    random_seed: int | None = options.get('random_seed')
    trace = golden_traces.record_trace(
        scene_class=type(game) if isinstance(game, Scene) else game,
        script=script,
        frame_count=options['frame_count'],
        random_seed=golden_traces.RANDOM_SEED if random_seed is None else random_seed,
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
