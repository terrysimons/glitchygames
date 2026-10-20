"""Rebaseline: ``--replay-trace OLD --rebaseline NEW --headless``.

A rebaseline replays OLD's inputs on the current code and writes what that code did to a new
recording, NEW, with a summary of what changed. It is how a recording used as a regression test
(tests/fixtures/replays, glitchygames/testing/replays.py) follows an intentional change; replacing
OLD with NEW stays a deliberate, reviewed step: NEW is never OLD (refused), and nothing replaces
OLD.

The rules:

1. Options: ``--rebaseline NEW`` needs ``--replay-trace OLD`` and ``--headless`` (a watched
   replay holds frames and takes the viewer's keys, so it is refused rather than made headless
   behind the user's back), and refuses NEW naming OLD's file, ``--record-trace`` (the
   rebaseline writes its own recording), ``--audit`` and ``--replay-fps real`` (FPS events from
   this machine's frame times would be recorded as the new baseline); each refusal exits
   ``ExitCode.OPTIONS_REFUSED`` (``rebaseline_refusal``). An unusable OLD is refused as by any
   replay (``ExitCode.UNUSABLE_INPUT``, ``ExitCode.MISSING_INPUT``).
2. Replay: OLD is replayed as usual (glitchygames/replay/driver.py, rule 17 there), but a
   divergence does not stop it (``ReplayOptions.stop_on_divergence`` False): it runs to OLD's
   last frame, or until the game ends, noting every frame that differs and every sprite that
   differs in them.
3. Recording: ``RecordingSources`` over the replay (``replayed``; glitchygames/recording.py)
   write NEW with OLD's inputs, as the replay's doors served them: the event batches (origins
   from the replay's merge, so code-posted events stay internal and replaying NEW delivers
   nothing twice), ``dt``, ``input_changes``, re-applied control events, and each frame's
   ``saves_opened``, ``devices_opened`` and ``device_enumeration`` copied from OLD's frame; and
   the current code's sprites and markers. The header is OLD's (``rebaseline_header``).
4. Writing: NEW is written to ``NEW.partial`` and moved into place once the run ended normally,
   so NEW is never left half written; a run that a crash, signal or the game's own exit ended
   early writes nothing (the partial file is removed).
5. Output: the summary (``RebaselineSummary.describe``) is printed to stdout instead of the
   replay's report, e.g. ``Rebaselined 9800 frames to NEW: 412 frames differ (first at 6120:
   sprite Ball#2 rect expected [412, 300, 16, 16], got [412, 301, 16, 16]); sprites affected:
   Ball#2, Ball#3`` or ``Rebaselined 9800 frames to NEW: no frames differ``, and the run exits
   ``ExitCode.SUCCESS`` (``ReplayExitPolicy.SUCCESS_AFTER_WRITING``).

NEW replays on the current code with no divergence.
"""

from __future__ import annotations

import importlib.metadata
import logging
import platform
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

import pygame
from pydantic import BaseModel, ConfigDict

from glitchygames.recording import GameplayRecorder, RecordingSources
from glitchygames.replay.driver import (
    ENGINE_VERSION_HEADER_FIELD,
    INPUT_CAPTURE_FORMAT_HEADER_FIELD,
    REAL_REPLAY_FPS,
    SOURCE_TRUNCATED_HEADER_FIELD,
    Divergence,
    ReplayResult,
    ReplaySources,
)
from glitchygames.sources import active_sources, install_sources

if TYPE_CHECKING:
    from collections.abc import Mapping

LOG = logging.getLogger('game.replay.rebaseline')
LOG.addHandler(logging.NullHandler())

# The header field naming the recording a rebaselined one was made from
REBASELINED_FROM_HEADER_FIELD = 'rebaselined_from'
# Header fields that describe the code that produced the sprites, set to this run's
PYGAME_VERSION_HEADER_FIELD = 'pygame_version'
PYTHON_VERSION_HEADER_FIELD = 'python_version'
# The file NEW is written to before it is moved into place (rule 4)
PARTIAL_REBASELINE_SUFFIX = '.partial'


class RebaselineSummary(BaseModel):
    """What changed between OLD and the current code (rule 5).

    Attributes:
        path: Where the new recording was written.
        first_divergence: The first difference (of any kind), or None when nothing differs.
        frames_differing: How many compared frames differed.
        sprites_affected: Every sprite that differed in them, in the order first found.
        frames_replayed: How many of OLD's frames were replayed (and written).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    path: Path
    first_divergence: Divergence | None
    frames_differing: int
    sprites_affected: list[str]
    frames_replayed: int

    @classmethod
    def from_result(cls, *, result: ReplayResult, path: Path) -> RebaselineSummary:
        """Summarize a rebaseline's replay result.

        Args:
            result: The replay's settled result (after ``ReplaySources.finish_run``).
            path: Where the new recording was written.

        Returns:
            The summary.

        """
        return cls(
            path=path,
            first_divergence=result.divergence,
            frames_differing=result.differing_frame_count,
            sprites_affected=list(result.affected_sprite_ids),
            frames_replayed=result.frames_replayed,
        )

    def describe(self: Self) -> str:
        """Describe the rebaseline on one line (printed to stdout).

        Returns:
            ``Rebaselined N frames to NEW: `` then ``no frames differ``, ``K frames differ
            (first at F: <what differed>)`` with ``; sprites affected: A, B`` when sprites
            differed, or ``the run differs (at F: <what differed>)`` when no compared frame
            differed but the run did (it ended before OLD's last frame).

        """
        head = f'Rebaselined {self.frames_replayed} frames to {self.path}: '
        divergence = self.first_divergence
        if divergence is None:
            return f'{head}no frames differ'
        where = f'{divergence.frame_number}: {divergence.describe_difference()}'
        if self.frames_differing == 0:
            return f'{head}the run differs (at {where})'
        count = (
            '1 frame differs'
            if self.frames_differing == 1
            else f'{self.frames_differing} frames differ'
        )
        line = f'{head}{count} (first at {where})'
        if self.sprites_affected:
            line = f'{line}; sprites affected: {", ".join(self.sprites_affected)}'
        return line


def _installed_engine_version() -> str | None:
    try:
        return importlib.metadata.version('glitchygames')
    except importlib.metadata.PackageNotFoundError:
        return None


def rebaseline_header(
    *,
    original_header: Mapping[str, Any],
    original_path: Path,
    source_truncated: bool = False,
) -> dict[str, Any]:
    """Return the header of a recording rebaselined from another (rule 3).

    OLD's header is kept (the seed, start time, options, screen size, saves, devices and device
    enumeration answers: the replay ran with them, so NEW replays with them), with:
    ``rebaselined_from`` naming OLD, the engine, pygame and Python versions of this run (they
    produced NEW's sprites), ``source_truncated`` when OLD was cut off (NEW then ends as
    truncated, as OLD's replay did), and no ``input_capture_format_version`` (NEW records the
    polled input and markers the replay saw, as format 3; a bookmarked copy's
    ``bookmarked_copy_of`` is kept, as NEW holds the same bookmarks).

    Args:
        original_header: OLD's header fields (without ``format_version`` and ``frames``).
        original_path: OLD's file.
        source_truncated: True when OLD was cut off part way.

    Returns:
        NEW's header fields.

    """
    header = dict(original_header)
    header.pop(INPUT_CAPTURE_FORMAT_HEADER_FIELD, None)
    header[ENGINE_VERSION_HEADER_FIELD] = _installed_engine_version()
    header[PYGAME_VERSION_HEADER_FIELD] = pygame.version.ver
    header[PYTHON_VERSION_HEADER_FIELD] = platform.python_version()
    header[REBASELINED_FROM_HEADER_FIELD] = str(original_path)
    if source_truncated:
        header[SOURCE_TRUNCATED_HEADER_FIELD] = True
    return header


def _is_same_file(*, first: Path, second: Path) -> bool:
    if first.resolve() == second.resolve():
        return True
    return first.exists() and second.exists() and first.samefile(second)


def rebaseline_refusal(*, options: Mapping[str, Any]) -> str | None:
    """Say why a rebaseline's options cannot run (rule 1), given ``--replay-trace``.

    Args:
        options: The parsed options (``rebaseline`` and ``replay_trace`` set).

    Returns:
        The reason, for the log, or None when the rebaseline can run.

    """
    new_path = Path(options['rebaseline'])
    old_path = Path(options['replay_trace'])
    if not options.get('headless'):
        return (
            '--rebaseline needs --headless: a watched replay holds frames and takes the '
            "viewer's keys"
        )
    if _is_same_file(first=new_path, second=old_path):
        return f'--rebaseline {new_path} would overwrite the recording it replays'
    if options.get('record_trace') is not None:
        return '--rebaseline writes its own recording, not with --record-trace'
    if options.get('audit'):
        return '--rebaseline replays once, not with --audit'
    if options.get('replay_fps') == REAL_REPLAY_FPS:
        return (
            f'--rebaseline would record FPS events from measured frame times, not with '
            f'--replay-fps {REAL_REPLAY_FPS}'
        )
    return None


class Rebaseline:
    """Records a rebaseline's replay into the new recording and writes it (rules 3 to 5).

    ``GameEngine`` creates it for ``--rebaseline``, calls ``start_recording`` before the first
    frame and, once the run is over and the recorder closed, ``write`` (a normal end) or
    ``discard``.
    """

    def __init__(
        self: Self, *, replay_sources: ReplaySources, source_path: Path, destination: Path
    ) -> None:
        """Keep what the rebaseline needs.

        Args:
            replay_sources: The replay of OLD (``ReplayOptions.stop_on_divergence`` False).
            source_path: OLD's file.
            destination: NEW's file.

        """
        self._replay_sources = replay_sources
        self._source_path = source_path
        self.destination = destination
        self._partial_path = destination.with_name(destination.name + PARTIAL_REBASELINE_SUFFIX)

    def start_recording(self: Self) -> GameplayRecorder:
        """Open the partial file and install recording doors over the replay (rule 3).

        Returns:
            The recorder (the engine closes it at teardown).

        """
        header = rebaseline_header(
            original_header=self._replay_sources.header,
            original_path=self._source_path,
            source_truncated=self._replay_sources.recording.is_truncated,
        )
        recorder = GameplayRecorder(path=self._partial_path, header=header)
        install_sources(
            sources=RecordingSources(
                inner=active_sources(), recorder=recorder, replayed=self._replay_sources
            )
        )
        LOG.info('Rebaselining %s to %s', self._source_path, self.destination)
        return recorder

    def write(self: Self, *, result: ReplayResult) -> str:
        """Move the closed recording into place and summarize the rebaseline (rules 4 and 5).

        Args:
            result: The replay's settled result.

        Returns:
            The summary line.

        """
        try:
            self._partial_path.replace(self.destination)
        finally:
            self._partial_path.unlink(missing_ok=True)
        return RebaselineSummary.from_result(result=result, path=self.destination).describe()

    def discard(self: Self) -> None:
        """Remove the partial recording of a run that ended early (rule 4)."""
        self._partial_path.unlink(missing_ok=True)
        LOG.warning('The rebaseline ended early; %s was not written', self.destination)
