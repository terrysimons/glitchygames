"""The ``glitchygames`` command: the engine's tools as subcommands (``registry.TOOLS``).

``glitchygames <tool> ...`` runs the tool of that name with the same options its game flag
takes (``glitchygames replay-trace run.jsonl.gz --headless`` is ``mygame --replay-trace
run.jsonl.gz --headless``). A tool that runs the game starts it as a child process; arguments
after a bare ``--`` go to that game unchanged.

Started as the ``glitchygames`` console script or as ``python -m glitchygames``, both through
glitchygames/__main__.py, which hides pygame's banner before anything imports pygame (importing
this module does, through ``glitchygames.replay``).
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from glitchygames.process import split_at_end_of_options
from glitchygames.replay.tools.registry import build_command_parser, tool_named

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glitchygames.replay.tools.registry import Tool


def main(arguments: Sequence[str] | None = None, *, tools: Sequence[Tool] | None = None) -> int:
    """Run the ``glitchygames`` command.

    Args:
        arguments: The command line after the program's name (None: ``sys.argv[1:]``).
        tools: The tools (``registry.TOOLS`` unless given).

    Returns:
        The tool's exit status (a child game's, when one ran). argparse exits with
        ``ExitCode.ARGUMENT_PARSER_ERROR`` itself on a usage error, and with ``SUCCESS`` after
        ``--help``.

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
    return tool.command_handler(tool=tool, arguments=parsed, game_arguments=game_arguments)
