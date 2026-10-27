"""A project's settings for the engine's tools, from ``[tool.glitchygames]`` in its pyproject.toml.

Every setting has a default that fits a standard layout, so a project with no such table (a
player's own local runs, a game the engine has never seen) works as it is. The keys are
kebab-case, as pyproject.toml's are (stage D's settings table):

- ``games``: the console scripts the tools run when given no game (default: the project's
  ``[project.scripts]``).
- ``golden-globs``: where the golden replays are, as globs relative to the project root.
- ``ledger-directory``: where measured rows are kept as row files (a git pathspec too, so it is
  relative).
- ``pending-ledger``: where measured rows wait to be published.
- ``published-ledger``: where the ledger is published, as ``REF:PATH`` (what ``git show`` reads),
  or nothing published (the default).
- ``landed-ref``: the ref whose commits count as landed.
- ``measured-paths`` and ``unmeasured-paths``: what a code tree holds, as git pathspecs
  (glitchygames/code_tree.py).
- ``recording-renames``: recordings that moved, old repository path -> new, so a recording's
  history follows it.

Settings only name paths, relative to the project root: nothing is created or checked on disk
when they are read. A path that doesn't exist yet (no ledger directory before the first
measurement) is created or reported by the tool that writes or reads it.

Part 3, Stage D, Task D2: these replaced the module constants of glitchygames/code_tree.py and
glitchygames/recording_metrics.py (``LEDGER_DIRECTORY``, ``MEASURED_PATHS``, the member-test
pathspecs, ``ORIGIN_MAIN``, ``PUBLISHED_LEDGER_PATH``/``_REF``, ``PENDING_LEDGER_RELATIVE_PATH``
and ``RECORDING_PATH_RENAMES``), whose values are now ours in the root pyproject.toml.
"""

from __future__ import annotations

import tomllib
from pathlib import PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING, Any, Self, cast

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from glitchygames.code_tree import CodeTreePaths

if TYPE_CHECKING:
    from pathlib import Path

PYPROJECT_FILE_NAME = 'pyproject.toml'
# The table the settings are in: [tool.glitchygames]
SETTINGS_TABLE = 'glitchygames'
# What separates the ref from the path in published-ledger (a ref name never holds one:
# git check-ref-format)
PUBLISHED_LEDGER_SEPARATOR = ':'
# pydantic's error type for a key the model doesn't have
UNKNOWN_KEY_ERROR = 'extra_forbidden'


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
    pending_ledger: str = 'replay-ledger/pending.jsonl'
    published_ledger: str | None = None
    landed_ref: str = 'origin/main'
    measured_paths: tuple[str, ...] = ('src', 'tests/fixtures/replays', 'pyproject.toml')
    unmeasured_paths: tuple[str, ...] = ()
    recording_renames: dict[str, str] = {}

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
    table = cast('dict[str, Any]', document.get('tool', {})).get(SETTINGS_TABLE, {})
    if not isinstance(table, dict):
        message = f'{pyproject}: [tool.{SETTINGS_TABLE}] is not a table'
        raise ProjectSettingsError(message)
    settings = dict(cast('dict[str, Any]', table))
    if 'games' not in settings:
        project = cast('dict[str, Any]', document.get('project', {}))
        settings['games'] = list(cast('dict[str, str]', project.get('scripts', {})))
    try:
        # Only the kebab-case keys are settings: ledger_directory is a misspelling
        return ProjectSettings.model_validate(settings, by_alias=True, by_name=False)
    except ValidationError as error:
        raise ProjectSettingsError(_refusal(pyproject=pyproject, error=error)) from None
