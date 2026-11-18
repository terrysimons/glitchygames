"""The ``listening-*`` tools: thin commands over the listening renders (audio/listening).

plans/2026-11-14-sound-cache-on-first-use.md, decision 8: ``listening-instruments [--family F]
[--only TEXT]`` renders each catalog instrument's demo that is missing, ``listening-pipes
[--only TEXT]`` each pipe demo and tune, into the listening folder under the cache root
(``GLITCHYGAMES_SOUND_CACHE_ROOT``'s; with it empty, each tool is refused with
``ExitCode.OPTIONS_REFUSED``). Each file's path goes to standard output, written or already
kept, so a player can open it; the summary goes to standard error. The listening files are no
game's, so a game's flag renders them as the command does.

The renders are imported when a tool runs, never with the registry: every game's start imports
the registry, and the pipe instruments are built at import.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

from glitchygames.audio.disk_cache import sound_cache_root
from glitchygames.exit_codes import ExitCode
from glitchygames.replay.tools.sound_cache_tools import NO_ROOT_MESSAGE
from glitchygames.replay.tools.traces import refused, say

if TYPE_CHECKING:
    import argparse
    from collections.abc import Callable
    from pathlib import Path

    from glitchygames.audio.listening import ListeningReport
    from glitchygames.replay.tools.registry import Tool
    from glitchygames.scenes import Scene


def _render(
    *, flag: str, render: Callable[[Path], ListeningReport], tool: Tool | None = None
) -> ExitCode:
    """Render into the cache root's listening folder and print each file, then the summary.

    Args:
        flag: How the run is named in what it says (the game flag, or the subcommand).
        render: What renders the files asked for into a root.
        tool: The tool, for a command (its refusal is said on standard error, as every
            command's is); None on a game (logged as an error, as every game handler's is).

    Returns:
        ``ExitCode.SUCCESS``, or ``ExitCode.OPTIONS_REFUSED`` without a disk cache.
    """
    root = sound_cache_root()
    if root is None:
        if tool is not None:
            say(tool=tool, message=NO_ROOT_MESSAGE)
            return ExitCode.OPTIONS_REFUSED
        return refused(message=f'{flag}: {NO_ROOT_MESSAGE}', exit_code=ExitCode.OPTIONS_REFUSED)
    report = render(root)
    for path in (*report.written, *report.already_kept):
        sys.stdout.write(f'{path}\n')
    sys.stderr.write(
        f'{flag}: {len(report.written)} written, {len(report.already_kept)} already kept\n'
    )
    return ExitCode.SUCCESS


def _instruments(*, family: str | None, only: str | None) -> Callable[[Path], ListeningReport]:
    """What renders the instrument demos asked for.

    Returns:
        A render of the root.
    """
    from glitchygames.audio import instruments
    from glitchygames.audio.listening.renders import render_instruments

    chosen = None if family is None else instruments.Family(family)
    return lambda root: render_instruments(root=root, family=chosen, only=only or '')


def _pipes(*, only: str | None) -> Callable[[Path], ListeningReport]:
    """What renders the pipe demos and tunes asked for.

    Returns:
        A render of the root.
    """
    from glitchygames.audio.listening.renders import render_pipes

    return lambda root: render_pipes(root=root, only=only or '')


def listening_instruments_on_the_game(
    *, options: dict[str, Any], game: type[Scene] | Scene
) -> ExitCode:
    """Run ``--listening-instruments [--family F] [--only TEXT]`` on a game (no game's files).

    Returns:
        The exit code.
    """
    del game
    return _render(
        flag='--listening-instruments',
        render=_instruments(family=options.get('family'), only=options.get('only')),
    )


def listening_pipes_on_the_game(*, options: dict[str, Any], game: type[Scene] | Scene) -> ExitCode:
    """Run ``--listening-pipes [--only TEXT]`` on a game (no game's files).

    Returns:
        The exit code.
    """
    del game
    return _render(flag='--listening-pipes', render=_pipes(only=options.get('only')))


def listening_instruments_command(
    *, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]
) -> int:
    """Run ``glitchygames listening-instruments [--family F] [--only TEXT]``.

    Returns:
        The exit code.
    """
    del game_arguments
    return _render(
        flag='listening-instruments',
        render=_instruments(family=arguments.family, only=arguments.only),
        tool=tool,
    )


def listening_pipes_command(
    *, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]
) -> int:
    """Run ``glitchygames listening-pipes [--only TEXT]``.

    Returns:
        The exit code.
    """
    del game_arguments
    return _render(flag='listening-pipes', render=_pipes(only=arguments.only), tool=tool)
