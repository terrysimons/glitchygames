"""The ``glitchygames`` command: the engine's tools as subcommands (``registry.TOOLS``).

``glitchygames <tool> ...`` runs the tool of that name with the same options its game flag
takes (``glitchygames replay-trace run.jsonl.gz --headless`` is ``mygame --replay-trace
run.jsonl.gz --headless``). A tool that runs the game starts it as a child process; arguments
after a bare ``--`` go to that game unchanged.

The tool runs inside the crash boundary a game flag's tool runs in
(``game_engine.run_inside_tool_crash_boundary``), so both front ends end alike: an uncaught
exception exits ``ExitCode.INTERNAL_ERROR`` (logged with its traceback), Ctrl-C
``ExitCode.INTERRUPTED``, and a terminating signal (SIGTERM, SIGHUP) its own code, after a child
game the tool waits for is stopped and reaped. A child killed by a signal is reported as a shell
reports it, 128 + the signal (``exit_codes.shell_exit_status``). A missing required option is
refused as on the game (``registry.missing_required_options``: ``ExitCode.OPTIONS_REFUSED``).

Started as the ``glitchygames`` console script or as ``python -m glitchygames``, both through
glitchygames/__main__.py, which hides pygame's banner before anything imports pygame (importing
this module does, through ``glitchygames.replay``).
"""

from __future__ import annotations

import functools
import logging
import sys
from typing import TYPE_CHECKING

from glitchygames.engine.game_engine import LOG_FORMAT, run_inside_tool_crash_boundary
from glitchygames.exit_codes import ExitCode, shell_exit_status
from glitchygames.process import split_at_end_of_options
from glitchygames.replay.tools.registry import (
    COMMAND_NAME,
    build_command_parser,
    missing_required_options,
    tool_named,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glitchygames.replay.tools.registry import Tool


def main(arguments: Sequence[str] | None = None, *, tools: Sequence[Tool] | None = None) -> int:
    """Run the ``glitchygames`` command.

    Args:
        arguments: The command line after the program's name (None: ``sys.argv[1:]``).
        tools: The tools (``registry.TOOLS`` unless given).

    Returns:
        The tool's exit status (a child game's, when one ran; 128 + N for one killed by signal
        N), ``ExitCode.INTERNAL_ERROR`` or ``ExitCode.INTERRUPTED`` for a tool that raised, or
        ``ExitCode.OPTIONS_REFUSED`` for a missing required option. argparse exits with
        ``ExitCode.ARGUMENT_PARSER_ERROR`` itself on any other usage error, and with
        ``SUCCESS`` after ``--help``; a terminating signal exits with its own code
        (SystemExit).

    """
    command_line = list(sys.argv[1:] if arguments is None else arguments)
    tool_arguments, rest = split_at_end_of_options(arguments=command_line)
    parser = build_command_parser(tools=tools)
    parsed = parser.parse_args(tool_arguments)
    tool = tool_named(name=parsed.tool, tools=tools)
    # rest starts with the bare -- itself
    game_arguments = rest[1:]
    if game_arguments and not tool.runs_game:
        parser.error(f'{tool.name} runs no game: nothing takes the arguments after --')
    refusal = missing_required_options(tool=tool, values=vars(parsed))
    if refusal is not None:
        sys.stderr.write(f'{COMMAND_NAME} {tool.name}: {refusal}\n')
        return ExitCode.OPTIONS_REFUSED
    # The engine's log format, as a game's run sets it (GameEngine.initialize_arguments), so the
    # boundary's report of a crash reads as it does on the game; a no-op where logging is set up
    logging.basicConfig(format=LOG_FORMAT, level=logging.WARNING)
    exit_status, _cause = run_inside_tool_crash_boundary(
        run_tool=functools.partial(
            tool.command_handler, tool=tool, arguments=parsed, game_arguments=game_arguments
        ),
        tool_description=tool.flag,
    )
    return shell_exit_status(returncode=exit_status)
