"""A project's settings for the engine's tools, from ``[tool.glitchygames]`` in its pyproject.toml.

Every setting has a default that fits a standard layout, so a project with no such table (a
player's own local runs, a game the engine has never seen) works as it is. The keys are
kebab-case, as pyproject.toml's are (stage D's settings table):

- ``games``: the console scripts the tools run when given no game (default: the project's
  ``[project.scripts]``).
- ``golden-globs``: where the golden replays are, as globs relative to the project root.
- ``ledger-directory``: where measured rows are kept as row files (a git pathspec too, so it is
  relative).
- ``pending-ledger``: where measured rows wait to be published (default: in the project's local
  directory, ``.glitchygames/``, outside the ledger directory so it is never committed with the
  rows).
- ``published-ledger``: where the ledger is published, as ``REF:PATH`` (what ``git show`` reads),
  or nothing published (the default).
- ``landed-ref``: the ref whose commits count as landed.
- ``measured-paths`` and ``unmeasured-paths``: what a code tree holds, as git pathspecs
  (glitchygames/code_tree.py).
- ``recording-renames``: recordings that moved, old repository path -> new, so a recording's
  history follows it. Each path is relative, no new path is itself an old one (lookups are one
  hop: an old path names the final one directly), and no two old paths are the same path
  written two ways; refused when read otherwise. ``recording_renames_problems`` finds a new path
  that does not exist (a check of the files, which reading settings never does).
- ``game-timeout-seconds``: how long ``glitchygames verify`` and ``glitchygames measure`` wait
  for each game they start (``GAME --verify``, ``GAME --measure``) before stopping it and
  failing it (default: an hour, ``DEFAULT_GAME_TIMEOUT_SECONDS``). A game replays each of its
  recordings in a child of its own with a timeout of its own (``REPLAY_TIMEOUT_SECONDS``); this
  bounds what never ends at all, such as an editor or a server among ``[project.scripts]``.

**Stored paths are relative to the project root.** Every path the tools write into a file (a
recording header's path options, a run's ``rebaselined_from``, a ledger row's recording) is
relative to the project root, the one these settings are read from (``find_project_root``: the
nearest project; ``--project-root`` where a tool's subcommand takes it), POSIX-style; a path
inside another checkout of the same project (the same ``[project] name``) relative to that
checkout's root; any other path outside the project as its file name only (``stored_path``),
so no user name, home or scratch directory is ever written into a file meant to be committed.

Settings only name paths, relative to the project root: nothing is created or checked on disk
when they are read. A path that doesn't exist yet (no ledger directory before the first
measurement) is created or reported by the tool that writes or reads it. A tool writing into the
project's local directory (``.glitchygames/``) creates it with ``ensure_local_directory``, which
puts a ``.gitignore`` of ``*`` there, as pytest does for its cache, so nothing in it is committed.

Part 3, Stage D, Task D2: these replaced the module constants of glitchygames/code_tree.py and
glitchygames/recording_metrics.py (``LEDGER_DIRECTORY``, ``MEASURED_PATHS``, the member-test
pathspecs, ``ORIGIN_MAIN``, ``PUBLISHED_LEDGER_PATH``/``_REF``, ``PENDING_LEDGER_RELATIVE_PATH``
and ``RECORDING_PATH_RENAMES``), whose values are now ours in the root pyproject.toml.
"""

from __future__ import annotations

import posixpath
import tomllib
from collections.abc import Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING, Any, Self, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from glitchygames.code_tree import CodeTreePaths

if TYPE_CHECKING:
    import os

PYPROJECT_FILE_NAME = 'pyproject.toml'
# The table the settings are in: [tool.glitchygames]
SETTINGS_TABLE = 'glitchygames'
# What separates the ref from the path in published-ledger (a ref name never holds one:
# git check-ref-format)
PUBLISHED_LEDGER_SEPARATOR = ':'
# pydantic's error type for a key the model doesn't have
UNKNOWN_KEY_ERROR = 'extra_forbidden'
# The project's local directory for what the tools write and nobody commits (the pending ledger)
LOCAL_DIRECTORY_NAME = '.glitchygames'
# What ensure_local_directory writes into it: git ignores everything there, this file included
LOCAL_DIRECTORY_GITIGNORE = '# Created by glitchygames: nothing in this directory is committed\n*\n'
GITIGNORE_FILE_NAME = '.gitignore'
# How long verify and measure wait for each game they start, by default: an hour, which a game
# replaying every one of its recordings (each within its own timeout) fits in many times over
DEFAULT_GAME_TIMEOUT_SECONDS = 3600.0

# Recordings that moved, old repository path -> new: read-only on the frozen settings (pydantic
# builds the field from this alias at runtime, so Mapping is imported at runtime too)
type RecordingRenames = Mapping[str, str]


class ProjectSettingsError(ValueError):
    """A project's ``[tool.glitchygames]`` can't be read (the message names the file and key)."""


def kebab_case(name: str) -> str:
    """Return a setting's key in pyproject.toml: its field name with ``-`` for ``_``.

    Returns:
        The key.

    """
    return name.replace('_', '-')


class ProjectSettings(BaseModel):
    """A project's settings for the engine's tools (see the module docstring for each).

    Attributes:
        games: The console scripts the tools run when given no game.
        golden_globs: Where the golden replays are, as globs relative to the project root.
        ledger_directory: Where measured rows are kept as row files, relative to the project
            root.
        pending_ledger: Where measured rows wait to be published, relative to the project root.
        published_ledger: Where the ledger is published, as ``REF:PATH``, or None.
        landed_ref: The ref whose commits count as landed.
        measured_paths: The git pathspecs a code tree holds.
        unmeasured_paths: The git pathspecs left out of them.
        recording_renames: Recordings that moved, old repository path -> new.
        game_timeout_seconds: How long ``verify`` and ``measure`` wait for each game they start
            before stopping it (a finite number above 0).

    """

    model_config = ConfigDict(
        frozen=True,
        extra='forbid',
        alias_generator=kebab_case,
        validate_by_alias=True,
        validate_by_name=True,
    )

    games: tuple[str, ...] = ()
    golden_globs: tuple[str, ...] = ('tests/fixtures/replays/**/*.jsonl.gz',)
    ledger_directory: str = 'replay-ledger'
    pending_ledger: str = f'{LOCAL_DIRECTORY_NAME}/pending-ledger.jsonl'
    published_ledger: str | None = None
    landed_ref: str = 'origin/main'
    measured_paths: tuple[str, ...] = ('src', 'tests/fixtures/replays', 'pyproject.toml')
    unmeasured_paths: tuple[str, ...] = ()
    recording_renames: RecordingRenames = {}
    game_timeout_seconds: float = Field(
        default=DEFAULT_GAME_TIMEOUT_SECONDS, gt=0, allow_inf_nan=False
    )

    @field_validator('ledger_directory')
    @classmethod
    def _relative_ledger_directory(cls, value: str) -> str:
        """Refuse an absolute ledger directory: git reads it as a pathspec of the repository.

        Returns:
            The value.

        Raises:
            ValueError: If it is absolute.

        """
        if PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute():
            message = f'{value!r} must be relative to the project root (it is a git pathspec)'
            raise ValueError(message)
        return value

    @field_validator('recording_renames')
    @classmethod
    def _one_hop_renames(cls, value: RecordingRenames) -> RecordingRenames:
        """Refuse a renames table a one-hop lookup would misread.

        Returns:
            The value.

        Raises:
            ValueError: If a path is absolute, an old path is the same as its new one or the
                same path as another old one, or a new path is itself an old one (a chain).

        """
        normalized_sources: dict[str, str] = {}
        for source, target in value.items():
            for path in (source, target):
                if is_absolute_path(text=path):
                    message = f'{path!r} must be relative to the project root'
                    raise ValueError(message)
            normalized_source = posixpath.normpath(source)
            if normalized_source == posixpath.normpath(target):
                message = f'{source!r} is renamed to itself'
                raise ValueError(message)
            if normalized_source in normalized_sources:
                message = (
                    f'{source!r} and {normalized_sources[normalized_source]!r} are the same old '
                    'path'
                )
                raise ValueError(message)
            normalized_sources[normalized_source] = source
        for source, target in value.items():
            chained = normalized_sources.get(posixpath.normpath(target))
            if chained is not None:
                message = (
                    f'{source!r} is renamed to {target!r}, which is itself renamed: lookups take '
                    f'one hop, so name the final path ({value[chained]!r}) instead'
                )
                raise ValueError(message)
        return value

    @field_validator('published_ledger')
    @classmethod
    def _ref_and_path(cls, value: str | None) -> str | None:
        """Refuse a published ledger that is not ``REF:PATH``.

        Returns:
            The value.

        Raises:
            ValueError: If the ref or the path is missing.

        """
        if value is None:
            return value
        ref, separator, path = value.partition(PUBLISHED_LEDGER_SEPARATOR)
        if not (ref and separator and path):
            message = f'{value!r} is not REF:PATH (origin/gh-pages:metrics/ledger.jsonl)'
            raise ValueError(message)
        return value

    @property
    def published_ledger_ref(self: Self) -> str | None:
        """The ref the ledger is published on, or None when nothing is published."""
        if self.published_ledger is None:
            return None
        return self.published_ledger.partition(PUBLISHED_LEDGER_SEPARATOR)[0]

    @property
    def published_ledger_path(self: Self) -> str | None:
        """The ledger's path on its ref, or None when nothing is published."""
        if self.published_ledger is None:
            return None
        return self.published_ledger.partition(PUBLISHED_LEDGER_SEPARATOR)[2]

    @property
    def code_tree_paths(self: Self) -> CodeTreePaths:
        """What a code tree holds (glitchygames/code_tree.py)."""
        return CodeTreePaths(measured=self.measured_paths, unmeasured=self.unmeasured_paths)


def _setting_keys() -> str:
    """Return every setting's key, for the messages.

    Returns:
        The keys, comma-separated.

    """
    return ', '.join(kebab_case(name) for name in ProjectSettings.model_fields)


def _refusal(*, pyproject: Path, error: ValidationError) -> str:
    """Describe why a settings table was refused, naming each key.

    Returns:
        The message.

    """
    problems: list[str] = []
    for detail in error.errors():
        key = '.'.join(str(part) for part in detail['loc'])
        if detail['type'] == UNKNOWN_KEY_ERROR:
            problems.append(f'unknown setting {key!r} (the settings are: {_setting_keys()})')
        else:
            problems.append(f'{key}: {detail["msg"]}')
    return f'{pyproject}: [tool.{SETTINGS_TABLE}]: {"; ".join(problems)}'


def _read_pyproject(*, pyproject: Path) -> dict[str, Any]:
    """Read a pyproject.toml (a missing one is empty).

    Returns:
        Its tables.

    Raises:
        ProjectSettingsError: If it is not valid TOML.

    """
    if not pyproject.is_file():
        return {}
    try:
        return tomllib.loads(pyproject.read_text(encoding='utf-8'))
    except tomllib.TOMLDecodeError as error:
        message = f'{pyproject} is not valid TOML: {error}'
        raise ProjectSettingsError(message) from None


def _table(*, pyproject: Path, parent: dict[str, Any], key: str, name: str) -> dict[str, Any]:
    """Return a table of a pyproject.toml (a missing one is empty).

    Args:
        pyproject: The file (for the message).
        parent: The table it is in.
        key: Its key there.
        name: Its full dotted name (for the message).

    Returns:
        The table.

    Raises:
        ProjectSettingsError: If the key holds something other than a table.

    """
    table = parent.get(key, {})
    if not isinstance(table, dict):
        message = f'{pyproject}: [{name}] is not a table'
        raise ProjectSettingsError(message)
    return cast('dict[str, Any]', table)


def load_project_settings(*, project_root: Path) -> ProjectSettings:
    """Read a project's settings from ``[tool.glitchygames]`` in its pyproject.toml.

    A missing file or table gives the defaults; ``games`` defaults to the keys of the project's
    ``[project.scripts]``, in their order. Nothing on disk is created or checked.

    Args:
        project_root: The project's root directory (where its pyproject.toml is).

    Returns:
        The settings.

    Raises:
        ProjectSettingsError: If the file is not valid TOML, the table is not a table, or a
            key is unknown or its value of the wrong shape (named in the message).

    """
    pyproject = project_root / PYPROJECT_FILE_NAME
    document = _read_pyproject(pyproject=pyproject)
    tool = _table(pyproject=pyproject, parent=document, key='tool', name='tool')
    settings = dict(
        _table(pyproject=pyproject, parent=tool, key=SETTINGS_TABLE, name=f'tool.{SETTINGS_TABLE}')
    )
    if 'games' not in settings:
        project = _table(pyproject=pyproject, parent=document, key='project', name='project')
        scripts = _table(pyproject=pyproject, parent=project, key='scripts', name='project.scripts')
        settings['games'] = list(scripts)
    try:
        # Only the kebab-case keys are settings: ledger_directory is a misspelling
        return ProjectSettings.model_validate(settings, by_alias=True, by_name=False)
    except ValidationError as error:
        raise ProjectSettingsError(_refusal(pyproject=pyproject, error=error)) from None


def project_name(*, project_root: Path) -> str | None:
    """Return the distribution a project builds: ``[project] name`` in its pyproject.toml.

    Args:
        project_root: The project's root directory (where its pyproject.toml is).

    Returns:
        The name, or None when there is no pyproject.toml or it names none. A file that is not
        valid TOML, or whose ``[project]`` is not a table, raises ``ProjectSettingsError``.

    """
    pyproject = project_root / PYPROJECT_FILE_NAME
    document = _read_pyproject(pyproject=pyproject)
    project = _table(pyproject=pyproject, parent=document, key='project', name='project')
    name = project.get('name')
    return name if isinstance(name, str) else None


def _names_project(*, project_root: Path, name: str) -> bool:
    """Tell whether a directory's pyproject.toml is the project ``name`` (unreadable: no).

    Args:
        project_root: The directory (its pyproject.toml exists).
        name: The project's name.

    Returns:
        True when its ``[project] name`` is ``name``.

    """
    try:
        return project_name(project_root=project_root) == name
    except ProjectSettingsError:
        return False


def has_settings_table(*, pyproject: Path) -> bool:
    """Tell whether a pyproject.toml has a ``[tool.glitchygames]`` table.

    Args:
        pyproject: The file.

    Returns:
        True if it holds the table; False if it doesn't, or isn't TOML (its settings are refused
        when they are read, by ``load_project_settings``).

    """
    try:
        document = tomllib.loads(pyproject.read_text(encoding='utf-8'))
    except tomllib.TOMLDecodeError:
        return False
    tool = document.get('tool')
    return isinstance(tool, dict) and SETTINGS_TABLE in tool


def find_project_root(*, start: Path, named: str | None = None) -> Path | None:
    """Return the project a directory is in, as git finds its repository.

    How a tool run from inside a project (``tests/fixtures/``, a workspace member's directory)
    finds the project's settings and recordings. The nearest pyproject.toml with a
    ``[tool.glitchygames]`` table wins, so inside a workspace member without one the workspace
    root that has them is the project (the controller's ruling, Part 3 Stage D, Task D5's fix
    round: the member would otherwise own the ledger); a project with no such table anywhere is
    its nearest pyproject.toml.

    With ``named``, the checkout of that project a path lies in (``stored_path``): the nearest
    of ``start`` and its ancestors whose ``pyproject.toml`` names that ``[project] name`` (a
    workspace member's own pyproject.toml, of another name, is passed by), whether or not it
    has the settings table; a pyproject.toml that cannot be read is passed by too.

    Args:
        start: The directory to look from (the current directory, usually).
        named: The project's name to look for, or None for the project's settings above.

    Returns:
        The nearest of ``start`` and its ancestors whose ``pyproject.toml`` has
        ``[tool.glitchygames]``; else the nearest holding a ``pyproject.toml``; else None. With
        ``named``: the nearest whose ``pyproject.toml`` is that project's, else None.

    """
    absolute = start.absolute()
    nearest: Path | None = None
    for directory in (absolute, *absolute.parents):
        pyproject = directory / PYPROJECT_FILE_NAME
        if not pyproject.is_file():
            continue
        if named is not None:
            if _names_project(project_root=directory, name=named):
                return directory
            continue
        if has_settings_table(pyproject=pyproject):
            return directory
        if nearest is None:
            nearest = directory
    return nearest


def is_absolute_path(*, text: str) -> bool:
    """Tell whether a stored path is absolute on any platform, or starts at a home directory.

    Args:
        text: The path as stored.

    Returns:
        True for a POSIX root (``/...``), a home directory (``~...``), a Windows drive
        (``X:`` then a slash or backslash) or a Windows share (two backslashes, a server).

    """
    return (
        text.startswith('~')
        or PurePosixPath(text).is_absolute()
        or PureWindowsPath(text).is_absolute()
    )


def stored_path(*, path: str | os.PathLike[str], project_root: Path | None) -> str:
    """Return a path as the tools store it in a file: relative to the project root.

    A relative path is read from the current directory, as the tool read it. A path inside the
    project is stored relative to its root, POSIX-style (``src/games/x/golden.jsonl.gz``). A
    path inside another checkout of the same project (a clone or worktree: the nearest
    directory above it whose pyproject.toml has the project's ``[project] name``,
    ``find_project_root(named=...)``) is stored relative to that checkout's root, the same way
    (the user, 2026-10-27). Any other path (a scratch directory, another project), or any path
    when there is no project, is stored as its file name only, so no user name or home
    directory is written.

    Args:
        path: The path as given.
        project_root: The project's root (``find_project_root``), or None.

    Returns:
        The stored path.

    """
    resolved = Path(path).expanduser().resolve()
    if project_root is None:
        return resolved.name
    root = project_root.resolve()
    if resolved.is_relative_to(root):
        return resolved.relative_to(root).as_posix()
    name = _project_name_or_none(project_root=root)
    checkout = None if name is None else find_project_root(start=resolved.parent, named=name)
    if checkout is None:
        return resolved.name
    return resolved.relative_to(checkout).as_posix()


def _project_name_or_none(*, project_root: Path) -> str | None:
    """Return a project's ``[project] name``, or None when it has none or cannot be read.

    Args:
        project_root: The project's root.

    Returns:
        The name, or None.

    """
    try:
        return project_name(project_root=project_root)
    except ProjectSettingsError:
        return None


def recording_renames_problems(*, settings: ProjectSettings, project_root: Path) -> list[str]:
    """Return each recording rename whose new path does not exist in the project.

    The table's shape is checked as it is read (``ProjectSettings``); this checks the files.

    Args:
        settings: The project's settings.
        project_root: The project's root.

    Returns:
        One line per missing new path (empty when every one exists).

    """
    return [
        f'{source} is renamed to {target}, which does not exist'
        for source, target in settings.recording_renames.items()
        if not (project_root / target).is_file()
    ]


def ensure_local_directory(*, directory: Path) -> Path:
    """Create a project's local directory (``.glitchygames/``) and keep git out of it.

    Every tool that writes there (the default pending ledger) calls this first. A ``.gitignore``
    holding ``*`` is written when the directory has none, as pytest does for its cache, so a
    file there never shows in ``git status``; an existing one is left as it is.

    Args:
        directory: The directory (``<project root>/.glitchygames``).

    Returns:
        The directory.

    """
    directory.mkdir(parents=True, exist_ok=True)
    gitignore = directory / GITIGNORE_FILE_NAME
    if not gitignore.exists():
        gitignore.write_text(LOCAL_DIRECTORY_GITIGNORE, encoding='utf-8')
    return directory
