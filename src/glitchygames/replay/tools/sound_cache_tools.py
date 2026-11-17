"""The ``sound-cache-*`` tools: thin commands over the sound cache's API (``cache_inventory``).

plans/2026-11-14-sound-cache-on-first-use.md, decision 8: the logic is ``audio.cache_inventory``'s
(which GG Sound Studio and the tests call too); these only find the root and the games, call it
and print what it says. Each is a registry tool, so both forms exist:

- ``<game> --sound-cache-<action>`` works on that game's own folder: its package
  (``identity.game_package``) and, for ``fill``, its declared sounds (``Scene.SOUNDS``).
- ``glitchygames sound-cache-<action> --game GAME`` runs each named game that way, as a child.
- ``glitchygames sound-cache-<action>`` with no game: ``list``, ``size``, ``verify`` and
  ``clear`` work on the whole cache root (every game's folders, stale versions and ``no-game``
  included); ``fill`` needs each game's sounds, so it runs the project's
  ``[tool.glitchygames] games``, each as a child.

The root is ``GLITCHYGAMES_SOUND_CACHE_ROOT``'s (``disk_cache.sound_cache_root``; children inherit
it). With it empty there is no disk cache, and each tool says so and exits
``ExitCode.OPTIONS_REFUSED``, a command before it looks up or starts any game. Results go to
standard output, one line each. ``verify`` exits ``ExitCode.UNUSABLE_INPUT`` when it found a
damaged file, so a test or a CI step can rely on it; a command passes on the worst of its games'
exit codes (``measure.combined_exit_code``).

Only ``fill`` with no game reads the project's settings (``--project-root`` is the project, as
for ``verify``). The other four never do: a broken ``pyproject.toml`` is no reason to refuse to
size the cache, so their ``--project-root`` is only where a named game runs.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Any

from glitchygames.audio.cache_inventory import clear, fill, inventory, verify
from glitchygames.audio.disk_cache import SOUND_CACHE_ROOT_VARIABLE, sound_cache_root
from glitchygames.exit_codes import ExitCode
from glitchygames.process import OutputCapture, run_command
from glitchygames.replay.tools.children import UnknownGameError
from glitchygames.replay.tools.identity import game_package
from glitchygames.replay.tools.measure import combined_exit_code, games_to_run
from glitchygames.replay.tools.traces import FORM_DESCRIPTIONS, refused, resolve_named_game, say
from glitchygames.replay.tools.verify import verify_project_root

if TYPE_CHECKING:
    import argparse
    from collections.abc import Callable
    from pathlib import Path

    from glitchygames.audio.cache_inventory import CacheInventory, VerifyReport
    from glitchygames.replay.tools.registry import Tool
    from glitchygames.scenes import Scene

KILOBYTE = 1024
NO_ROOT_MESSAGE = (
    f'{SOUND_CACHE_ROOT_VARIABLE} is empty, so there is no sound cache (unset it for the '
    "platform's cache folder, or give it a folder)"
)


def _say_line(line: str) -> None:
    """Write one line of a tool's result to standard output."""
    sys.stdout.write(f'{line}\n')


def _kilobytes(size: int) -> str:
    """A byte count as kilobytes, for people.

    Returns:
        The text.
    """
    return f'{size / KILOBYTE:.1f} KB'


def _root_or_refusal(*, flag: str) -> Path | ExitCode:
    """The cache root, or the refusal when there is no disk cache.

    Returns:
        The root, or ``ExitCode.OPTIONS_REFUSED`` (said once).
    """
    root = sound_cache_root()
    if root is None:
        return refused(message=f'{flag}: {NO_ROOT_MESSAGE}', exit_code=ExitCode.OPTIONS_REFUSED)
    return root


# --listening names the listening WAVs, which belong to no game (cache_inventory, rule 4a)
LISTENING_IS_NO_GAMES = (
    "--sound-cache-clear --listening: the listening WAVs are no game's; clear them without a "
    'game (glitchygames sound-cache-clear --listening)'
)


# --- What each action says (one place, for the game flag and the command alike) ---


def describe_inventory(found: CacheInventory, *, game: str | None = None) -> list[str]:
    """One line per cache folder, then the total (``sound-cache-list``).

    Returns:
        The lines.
    """
    folders = [folder for folder in found.folders if game is None or folder.game == game]
    lines = [
        f'{folder.game} render {folder.render_version}: {folder.sound_count} sounds, '
        f'{_kilobytes(folder.size_bytes)}{" (stale)" if folder.stale else ""}'
        for folder in folders
    ]
    if game is None:  # the listening WAVs are no game's (cache_inventory, rule 4a)
        lines.extend(
            f'listening render {folder.render_version}: {folder.file_count} files, '
            f'{_kilobytes(folder.size_bytes)}{" (stale)" if folder.stale else ""}'
            for folder in found.listening
        )
    total = sum(folder.size_bytes for folder in folders)
    lines.append(f'total: {len(folders)} folders, {_kilobytes(total)} in {found.root}')
    return lines


def describe_size(found: CacheInventory, *, game: str | None = None) -> str:
    """The cache's size in one line, stale versions counted apart (``sound-cache-size``).

    Returns:
        The line.
    """
    folders = [folder for folder in found.folders if game is None or folder.game == game]
    total = sum(folder.size_bytes for folder in folders)
    stale = sum(folder.size_bytes for folder in folders if folder.stale)
    sounds = sum(folder.sound_count for folder in folders)
    line = f'{sounds} sounds, {_kilobytes(total)} ({_kilobytes(stale)} stale) in {found.root}'
    if game is None and found.listening:  # the listening WAVs are no game's (rule 4a)
        files = sum(folder.file_count for folder in found.listening)
        listening_bytes = sum(folder.size_bytes for folder in found.listening)
        line += f'; listening: {files} files, {_kilobytes(listening_bytes)}'
    return line


def describe_verify(report: VerifyReport) -> list[str]:
    """Each damaged file and why, then the count (``sound-cache-verify``).

    Returns:
        The lines.
    """
    lines = [f'{damaged.path}: {damaged.reason}' for damaged in report.damaged]
    lines.append(f'checked {report.checked} sounds: {len(report.damaged)} damaged')
    return lines


# --- The game flags: one game's own folder ---


def _game_action(
    *, flag: str, game: type[Scene] | Scene, action: Callable[[Path, str], ExitCode]
) -> ExitCode:
    """Run an action on one game's folder, once the root is found.

    Returns:
        The action's exit code, or the refusal.
    """
    root = _root_or_refusal(flag=flag)
    if isinstance(root, ExitCode):
        return root
    return action(root, game_package(game=game))


def sound_cache_list_on_the_game(*, options: dict[str, Any], game: type[Scene] | Scene) -> ExitCode:
    """Run ``--sound-cache-list`` on a game: its folders.

    Returns:
        ``ExitCode.SUCCESS``, or the refusal without a disk cache.
    """
    del options

    def list_folders(root: Path, name: str) -> ExitCode:
        for line in describe_inventory(inventory(root=root), game=name):
            _say_line(line)
        return ExitCode.SUCCESS

    return _game_action(flag='--sound-cache-list', game=game, action=list_folders)


def sound_cache_size_on_the_game(*, options: dict[str, Any], game: type[Scene] | Scene) -> ExitCode:
    """Run ``--sound-cache-size`` on a game: what its folders hold.

    Returns:
        ``ExitCode.SUCCESS``, or the refusal without a disk cache.
    """
    del options

    def size(root: Path, name: str) -> ExitCode:
        _say_line(describe_size(inventory(root=root), game=name))
        return ExitCode.SUCCESS

    return _game_action(flag='--sound-cache-size', game=game, action=size)


def sound_cache_verify_on_the_game(
    *, options: dict[str, Any], game: type[Scene] | Scene
) -> ExitCode:
    """Run ``--sound-cache-verify`` on a game: read its files back.

    Returns:
        ``ExitCode.SUCCESS``, ``ExitCode.UNUSABLE_INPUT`` for a damaged file, or the refusal
        without a disk cache.
    """
    del options

    def check(root: Path, name: str) -> ExitCode:
        report = verify(root=root, game=name)
        for line in describe_verify(report):
            _say_line(line)
        return ExitCode.UNUSABLE_INPUT if report.damaged else ExitCode.SUCCESS

    return _game_action(flag='--sound-cache-verify', game=game, action=check)


def sound_cache_clear_on_the_game(
    *, options: dict[str, Any], game: type[Scene] | Scene
) -> ExitCode:
    """Run ``--sound-cache-clear`` on a game: remove its folders (``--stale-only``: older ones).

    Returns:
        ``ExitCode.SUCCESS``, or the refusal without a disk cache.
    """
    if options.get('listening'):
        return refused(message=LISTENING_IS_NO_GAMES, exit_code=ExitCode.OPTIONS_REFUSED)

    def remove(root: Path, name: str) -> ExitCode:
        report = clear(root=root, game=name, stale_only=bool(options.get('stale_only')))
        _say_line(f'removed {report.removed_sounds} sounds ({_kilobytes(report.freed_bytes)})')
        return ExitCode.SUCCESS

    return _game_action(flag='--sound-cache-clear', game=game, action=remove)


def sound_cache_fill_on_the_game(*, options: dict[str, Any], game: type[Scene] | Scene) -> ExitCode:
    """Run ``--sound-cache-fill`` on a game: compile its sounds into its folder ahead of time.

    Returns:
        ``ExitCode.SUCCESS``, or the refusal without a disk cache.
    """
    del options
    scene_class = game if isinstance(game, type) else type(game)

    def fill_folder(root: Path, name: str) -> ExitCode:
        report = fill(root=root, game_name=name, sounds=scene_class.SOUNDS)
        _say_line(
            f'{name}: {report.written} sounds written, {report.already_kept} already kept, '
            f'{report.skipped} never cached, in {report.folder}'
        )
        return ExitCode.SUCCESS

    return _game_action(flag='--sound-cache-fill', game=game, action=fill_folder)


# --- The commands ---


def _run_each_game(*, tool: Tool, arguments: argparse.Namespace, games: list[str]) -> int:
    """Run each game as a child with the tool's flag (it works on its own folder).

    Returns:
        The games' combined exit code (``ExitCode.OPTIONS_REFUSED`` for one not found).
    """
    statuses: list[int] = []
    for game in games:
        try:
            launch = resolve_named_game(tool=tool, game=game, arguments=arguments)
        except UnknownGameError:
            statuses.append(ExitCode.OPTIONS_REFUSED)
            continue
        say(tool=tool, message=f'running {game} ({FORM_DESCRIPTIONS[launch.form]})')
        finished = run_command(
            command=[*launch.command, *tool.child_arguments(arguments=arguments)],
            environment=dict(os.environ),
            timeout_seconds=None,
            capture_output=OutputCapture.NONE,
            working_directory=arguments.project_root,
        )
        statuses.append(finished.returncode)
    return combined_exit_code(statuses=statuses)


def _command(
    *,
    tool: Tool,
    arguments: argparse.Namespace,
    whole_root: Callable[[Path], int] | None,
) -> int:
    """Run a command: each ``--game`` as a child, else the whole root (or the project's games).

    Args:
        tool: The tool.
        arguments: The subcommand's parsed arguments.
        whole_root: What the command does with no game named, given the root; None to run the
            project's ``[tool.glitchygames] games`` instead (``fill``).

    Returns:
        The exit code.
    """
    # Refused before any game is looked up or started: each would only refuse in turn
    root = sound_cache_root()
    if root is None:
        say(tool=tool, message=NO_ROOT_MESSAGE)
        return ExitCode.OPTIONS_REFUSED
    named: list[str] | None = arguments.game
    if named is not None:
        # --project-root is only where each game runs (None: the current directory)
        return _run_each_game(tool=tool, arguments=arguments, games=named)
    if whole_root is not None:
        return whole_root(root)
    # fill alone reads the project's settings, for its games
    arguments.project_root = verify_project_root(given=arguments.project_root)
    found = games_to_run(tool=tool, arguments=arguments)
    if isinstance(found, ExitCode):
        return found
    games, _settings, _from_settings = found
    if not games:
        say(
            tool=tool,
            message=(
                'no games to fill: the project names none in [tool.glitchygames] games (or '
                '[project.scripts]), and no --game was given'
            ),
        )
        return ExitCode.SUCCESS
    return _run_each_game(tool=tool, arguments=arguments, games=games)


def sound_cache_list_command(
    *, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]
) -> int:
    """Run ``glitchygames sound-cache-list [--game GAME ...]``.

    Returns:
        The exit code.
    """
    del game_arguments

    def list_folders(root: Path) -> int:
        for line in describe_inventory(inventory(root=root)):
            _say_line(line)
        return ExitCode.SUCCESS

    return _command(tool=tool, arguments=arguments, whole_root=list_folders)


def sound_cache_size_command(
    *, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]
) -> int:
    """Run ``glitchygames sound-cache-size [--game GAME ...]``.

    Returns:
        The exit code.
    """
    del game_arguments

    def size(root: Path) -> int:
        _say_line(describe_size(inventory(root=root)))
        return ExitCode.SUCCESS

    return _command(tool=tool, arguments=arguments, whole_root=size)


def sound_cache_verify_command(
    *, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]
) -> int:
    """Run ``glitchygames sound-cache-verify [--game GAME ...]``.

    Returns:
        The exit code (``ExitCode.UNUSABLE_INPUT`` for a damaged file).
    """
    del game_arguments

    def check(root: Path) -> int:
        report = verify(root=root)
        for line in describe_verify(report):
            _say_line(line)
        return ExitCode.UNUSABLE_INPUT if report.damaged else ExitCode.SUCCESS

    return _command(tool=tool, arguments=arguments, whole_root=check)


def sound_cache_clear_command(
    *, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]
) -> int:
    """Run ``glitchygames sound-cache-clear [--stale-only] [--listening] [--game GAME ...]``.

    Returns:
        The exit code.
    """
    del game_arguments
    if arguments.listening and arguments.game is not None:
        say(tool=tool, message=LISTENING_IS_NO_GAMES)
        return ExitCode.OPTIONS_REFUSED

    def remove(root: Path) -> int:
        report = clear(
            root=root, stale_only=bool(arguments.stale_only), listening=bool(arguments.listening)
        )
        _say_line(f'removed {report.removed_sounds} sounds ({_kilobytes(report.freed_bytes)})')
        return ExitCode.SUCCESS

    return _command(tool=tool, arguments=arguments, whole_root=remove)


def sound_cache_fill_command(
    *, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]
) -> int:
    """Run ``glitchygames sound-cache-fill [--game GAME ...]`` (default: the project's games).

    Returns:
        The games' combined exit code.
    """
    del game_arguments
    return _command(tool=tool, arguments=arguments, whole_root=None)
