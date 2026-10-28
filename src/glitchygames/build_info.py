"""Which source revision of the engine is running: the commit, and how that is known.

A recording names it in every run (``MeasurementRun.source_revision``,
glitchygames/recording_history.py), so measurements can be traced to the commit that made them.
``source_revision`` asks, in order, and returns the first answer:

1. **A git checkout** (``RevisionSource.GIT_CHECKOUT``): git itself, when this package's own
   files are tracked in the work tree that holds them (a package installed under some other
   repository, e.g. a game's ``.venv`` or a nox session's, is not): HEAD, its commit date, and
   whether tracked files differ from it. Always current, merges included.
2. **A git archive** (``RevisionSource.GIT_ARCHIVE``): ``_git_archival.txt``, committed with
   ``$Format:...$`` placeholders and marked ``export-subst`` in ``.gitattributes``, so ``git
   archive`` (and GitHub's source zips and tarballs, which use it) writes the archived commit
   into it. In a checkout the placeholders are still there, so it says nothing.
3. **A build stamp** (``RevisionSource.BUILD_STAMP``): ``_build_info.json``, written by
   ``scripts/write_build_stamp.py`` while ``nox -s build-wheel`` / ``build-binary`` build the
   package from a checkout (gitignored, packaged through hatch's ``artifacts``, and removed
   again after the build), with the build's time.
4. **Unknown** (``RevisionSource.UNKNOWN``): none of them answered; never guessed.

An archive is exactly its commit, so only a checkout or a stamp made from one says whether there
were uncommitted changes. Git runs through ``glitchygames.process.run_command`` (the one
launcher), with a short timeout and without this process's variables that point git at another
repository (``environment_without_git_variables``), so the revision is always the package's own
checkout's;
a missing or failing git is "no answer", never an error.
"""

from __future__ import annotations

import functools
import json
import os
import shutil
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, ValidationError

from glitchygames.process import OutputCapture, TimeoutExpired, run_command

PACKAGE_DIRECTORY = Path(__file__).resolve().parent
ARCHIVE_FILE_NAME = '_git_archival.txt'
BUILD_STAMP_FILE_NAME = '_build_info.json'
GIT_TIMEOUT_SECONDS = 5.0
# What git archive leaves in place of a placeholder it did not expand (a checkout's copy)
UNEXPANDED_PLACEHOLDER_PREFIX = '$Format:'
ARCHIVE_COMMIT_KEY = 'commit'
ARCHIVE_COMMITTED_AT_KEY = 'committed'
# The variables that move git off the repository its directory is in (a hook's, a worktree's, an
# alias's): which repository, work tree, index or object store it reads, under which namespace,
# and GIT_CEILING_DIRECTORIES, which can stop it finding the directory's own repository at all.
# The others (GIT_CONFIG_*: safe.directory given through the environment, say) reach git
REPOSITORY_LOCATION_VARIABLES = frozenset({
    'GIT_DIR',
    'GIT_WORK_TREE',
    'GIT_INDEX_FILE',
    'GIT_COMMON_DIR',
    'GIT_OBJECT_DIRECTORY',
    'GIT_ALTERNATE_OBJECT_DIRECTORIES',
    'GIT_NAMESPACE',
    'GIT_CEILING_DIRECTORIES',
})


class RevisionSource(StrEnum):
    """Where a source revision came from (most trustworthy first)."""

    GIT_CHECKOUT = 'git-checkout'
    GIT_ARCHIVE = 'git-archive'
    BUILD_STAMP = 'build-stamp'
    UNKNOWN = 'unknown'


class SourceRevision(BaseModel):
    """The engine's source revision, as far as it is known.

    Attributes:
        source: How it is known.
        commit: The full commit hash, or None when unknown.
        committed_at: The commit's date (ISO 8601 with its offset), or None when unknown.
        uncommitted_changes: Whether tracked files differed from the commit (a checkout, or the
            checkout a stamp was built from); None when unknowable (an archive, unknown).
        built_at: When the package was built (ISO 8601), only for a build stamp.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    source: RevisionSource
    commit: str | None = None
    committed_at: str | None = None
    uncommitted_changes: bool | None = None
    built_at: str | None = None

    def to_json(self: Self) -> dict[str, object]:
        """Return the revision as recordings and the build stamp store it.

        Returns:
            Its fields.

        """
        return self.model_dump(mode='json')


UNKNOWN_REVISION = SourceRevision(source=RevisionSource.UNKNOWN)


def environment_without_git_variables() -> dict[str, str]:
    """Return this process's environment without the variables that move git to another repository.

    A ``GIT_DIR``, ``GIT_WORK_TREE``, ``GIT_INDEX_FILE`` or ``GIT_COMMON_DIR`` (and the others of
    ``REPOSITORY_LOCATION_VARIABLES``) in the environment (a git hook's, a worktree's, an
    alias's) would make ``git -C <package directory>`` read that repository instead, so a game's
    rows would name another repository's commit. Every other variable stays: ``GIT_CONFIG_*``
    may be what lets git trust the checkout at all (``safe.directory``).

    Returns:
        A copy of ``os.environ`` without ``REPOSITORY_LOCATION_VARIABLES``.

    """
    return {
        name: value
        for name, value in os.environ.items()
        if name not in REPOSITORY_LOCATION_VARIABLES
    }


def _git_output(*, arguments: list[str], directory: Path) -> str | None:
    """Run git in a directory and return its standard output, stripped.

    git runs without this process's variables that point it at another repository
    (``environment_without_git_variables``), so ``directory``'s own repository answers.

    Args:
        arguments: git's arguments.
        directory: The directory git runs in (``git -C``).

    Returns:
        The output, or None when git is missing, fails or times out.

    """
    git_program = shutil.which('git')
    if git_program is None:
        return None
    try:
        completed = run_command(
            command=[git_program, '-C', str(directory), *arguments],
            environment=environment_without_git_variables(),
            timeout_seconds=GIT_TIMEOUT_SECONDS,
            capture_output=OutputCapture.TOGETHER,
        )
    except OSError, TimeoutExpired:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def git_checkout_revision(*, package_directory: Path) -> SourceRevision | None:
    """Return the revision git reports for a package directory that is part of a checkout.

    Args:
        package_directory: The package's directory.

    Returns:
        The revision, or None when the directory is not tracked by a git work tree (or git is
        unavailable).

    """
    # Tracked, not merely inside a work tree: a package installed under another repository
    # (a game's .venv, .nox/) sits inside that work tree, but git tracks none of its files
    tracked = _git_output(arguments=['ls-files', '--', '.'], directory=package_directory)
    if not tracked:
        return None
    commit = _git_output(arguments=['rev-parse', 'HEAD'], directory=package_directory)
    if commit is None:
        return None
    committed_at = _git_output(
        arguments=['log', '-1', '--format=%cI', 'HEAD'], directory=package_directory
    )
    status = _git_output(
        arguments=['status', '--porcelain', '--untracked-files=no'], directory=package_directory
    )
    return SourceRevision(
        source=RevisionSource.GIT_CHECKOUT,
        commit=commit,
        committed_at=committed_at or None,
        uncommitted_changes=None if status is None else bool(status),
    )


def archive_revision(*, package_directory: Path) -> SourceRevision | None:
    """Return the revision ``git archive`` wrote into the archive file.

    Args:
        package_directory: The package's directory.

    Returns:
        The revision, or None when the file is missing, unreadable or unexpanded (a checkout).

    """
    try:
        text = (package_directory / ARCHIVE_FILE_NAME).read_text(encoding='utf-8')
    except OSError, UnicodeDecodeError:
        return None
    values: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.partition(':')
        if separator:
            values[key.strip()] = value.strip()
    commit = values.get(ARCHIVE_COMMIT_KEY)
    if not commit or commit.startswith(UNEXPANDED_PLACEHOLDER_PREFIX):
        return None
    committed_at = values.get(ARCHIVE_COMMITTED_AT_KEY)
    if committed_at is not None and committed_at.startswith(UNEXPANDED_PLACEHOLDER_PREFIX):
        committed_at = None
    return SourceRevision(
        source=RevisionSource.GIT_ARCHIVE, commit=commit, committed_at=committed_at or None
    )


def stamped_revision(*, package_directory: Path) -> SourceRevision | None:
    """Return the revision a build stamped into the package.

    Args:
        package_directory: The package's directory.

    Returns:
        The revision (source ``BUILD_STAMP``), or None when there is no readable stamp.

    """
    try:
        fields = json.loads((package_directory / BUILD_STAMP_FILE_NAME).read_text(encoding='utf-8'))
    except OSError, UnicodeDecodeError, json.JSONDecodeError:
        return None
    if not isinstance(fields, dict):
        return None
    try:
        return SourceRevision.model_validate({**fields, 'source': RevisionSource.BUILD_STAMP})
    except ValidationError:
        return None


def source_revision(*, package_directory: Path = PACKAGE_DIRECTORY) -> SourceRevision:
    """Return the package's source revision: checkout, then archive, then stamp, else unknown.

    Args:
        package_directory: The package's directory (this engine's by default; a game can ask
            about its own package).

    Returns:
        The first revision found, or ``UNKNOWN_REVISION``.

    """
    for lookup in (git_checkout_revision, archive_revision, stamped_revision):
        revision = lookup(package_directory=package_directory)
        if revision is not None:
            return revision
    return UNKNOWN_REVISION


@functools.cache
def package_source_revision(*, package_directory: Path) -> SourceRevision:
    """Return a package's source revision, looked up once per process (git takes a while).

    A game's package (``glitchygames.replay.tools.identity.game_source_revision``): every run
    of a process names the revision its first run found, as for the engine's.

    Args:
        package_directory: The package's directory.

    Returns:
        The revision (``source_revision``).

    """
    return source_revision(package_directory=package_directory)


@functools.cache
def engine_source_revision() -> SourceRevision:
    """Return this engine's source revision, looked up once per process (git takes a while).

    Returns:
        The revision.

    """
    return source_revision()


def write_build_stamp(*, package_directory: Path, built_at: str) -> SourceRevision:
    """Write the build stamp for a package built from a checkout (or an archive).

    Args:
        package_directory: The package's directory.
        built_at: The build's time (ISO 8601; the caller reads the clock, so the package never
            does outside the engine's doors).

    Returns:
        The revision written (source ``BUILD_STAMP``).

    """
    found = git_checkout_revision(package_directory=package_directory) or archive_revision(
        package_directory=package_directory
    )
    found_fields = (found or UNKNOWN_REVISION).to_json()
    stamp = SourceRevision.model_validate({
        **found_fields,
        'source': RevisionSource.BUILD_STAMP,
        'built_at': built_at,
    })
    stamp_fields = stamp.to_json()
    del stamp_fields['source']
    (package_directory / BUILD_STAMP_FILE_NAME).write_text(
        json.dumps(stamp_fields, indent=2, sort_keys=True) + '\n', encoding='utf-8'
    )
    return stamp
