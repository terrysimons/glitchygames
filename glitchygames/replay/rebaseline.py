"""Rebaseline: ``--replay-trace OLD --rebaseline NEW --headless``.

A rebaseline replays OLD's inputs on the current code and writes what that code did to a new
recording, NEW, with a summary of what changed. It is how a recording used as a regression test
(tests/fixtures/replays, glitchygames/testing/replays.py) follows an intentional change; replacing
OLD with NEW stays a deliberate, reviewed step: NEW is never OLD (refused), and nothing replaces
OLD.

The rules:

1. Options: ``--rebaseline NEW`` needs ``--replay-trace OLD`` and ``--headless`` (a watched
   replay holds frames and takes the viewer's keys, so it is refused rather than made headless
   behind the user's back), and refuses NEW or NEW's partial file (rule 4) naming OLD's file,
   ``--record-trace`` (the rebaseline writes its own recording), ``--audit`` and
   ``--replay-digest`` (the audit's tools: a rebaseline is not audited) and ``--replay-fps real``
   (FPS events from this machine's frame times would be recorded as the new baseline); each
   refusal exits
   ``ExitCode.OPTIONS_REFUSED`` (``rebaseline_refusal``). An unusable OLD is refused as by any
   replay (``ExitCode.UNUSABLE_INPUT``, ``ExitCode.MISSING_INPUT``).
2. Replay: OLD is replayed as usual (glitchygames/replay/driver.py, rule 17 there), but a
   divergence does not stop it (``ReplayOptions.stop_on_divergence`` False): it runs to OLD's
   last frame, or until the game ends, noting every frame that differs and every sprite that
   differs in them. OLD's input the run never received is never carried elsewhere (that would
   invent an input sequence OLD does not have); it is counted instead: the external events of
   batches a frame did not pump (it pumped fewer times than recorded), and OLD's frames after
   the game ended.
3. Recording: ``RecordingSources`` over the replay (``replayed``; glitchygames/recording.py)
   write NEW with OLD's inputs, as the replay's doors served them: the event batches (origins
   from the replay's merge, so code-posted events stay internal and replaying NEW delivers
   nothing twice), ``dt``, ``input_changes``, re-applied control events, and each frame's
   ``saves_opened``, ``devices_opened`` and ``device_enumeration`` copied from OLD's frame; and
   the current code's sprites and markers. The header is OLD's (``rebaseline_header``). NEW's
   frames stack this run's content hash and processing time in front of OLD's histories, and
   its header this run's ``measurement_runs`` entry in front of OLD's
   (glitchygames/recording_history.py), so an unchanged game shows the same hash one entry
   deeper, and a changed one shows which frames changed.
4. Writing: NEW is written to ``NEW.partial`` (``glitchygames.output_files.partial_path``)
   and moved into place once the run ended normally, so NEW is never left half written; a run
   that a crash, a signal or the game's own failing exit (``sys.exit(1)``) ended early writes
   nothing (the partial file is removed). The game's own successful exit (``sys.exit(0)``,
   ``sys.exit()``) is the game ending early, as ``quit_game()`` is: NEW holds the frames
   that ran (not the one it left part way through) and the run exits
   ``ExitCode.REBASELINE_INPUT_LOST`` (rule 5). A partial file that cannot be written is
   refused before the replay starts, on one line, with ``ExitCode.CANNOT_WRITE_OUTPUT``
   (``GameEngine._refuse_unwritable_outputs``). If
   the final move fails, the finished partial file is kept, its path logged and printed, and
   the run exits ``ExitCode.CANNOT_WRITE_OUTPUT``.
5. Output: the summary (``RebaselineSummary.describe``) is printed to stdout instead of the
   replay's report, e.g. ``Rebaselined 9800 frames to NEW: 412 frames differ (first at 6120:
   sprite Ball#2 rect expected [412, 300, 16, 16], got [412, 301, 16, 16]); sprites affected:
   Ball#2, Ball#3`` or ``Rebaselined 9800 frames to NEW: no frames differ``, followed by the
   lost input (rule 2) when there is any, e.g. ``; 3 recorded input events not delivered (first
   at frame 812); ended at frame 500 of 9800``, which is also logged as a warning. The run
   exits ``ExitCode.SUCCESS`` (``ReplayExitPolicy.SUCCESS_AFTER_WRITING``) however many frames
   differ, but ``ExitCode.REBASELINE_INPUT_LOST`` when input was lost
   (``ReplayResult.has_lost_input``), so a script notices: NEW is still written (it replays
   clean), but it is not a faithful re-run of OLD's session.

NEW replays on the current code with no divergence, as long as the rebaseline replayed all of
OLD: a truncated OLD gives a truncated NEW (``source_truncated``), whose replay matches to its
cut-off and exits ``ExitCode.UNUSABLE_INPUT``, as any truncated recording does; and a run that
ended before OLD's last frame (the lost input of rule 2) records only the frames it ran.
"""

from __future__ import annotations

import logging
import platform
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

import pygame
from pydantic import BaseModel, ConfigDict

from glitchygames.output_files import partial_path
from glitchygames.recording import GameplayRecorder, RecordingSources
from glitchygames.recording_history import (
    MEASUREMENT_RUNS_HEADER_FIELD,
    MeasurementRun,
    budget_seconds_for,
    stacked_measurement_runs,
)
from glitchygames.replay.driver import (
    ENGINE_VERSION_HEADER_FIELD,
    INPUT_CAPTURE_FORMAT_HEADER_FIELD,
    REAL_REPLAY_FPS,
    SOURCE_TRUNCATED_HEADER_FIELD,
    Divergence,
    ReplayResult,
    ReplaySources,
    installed_engine_version,
)
from glitchygames.sources import active_sources, install_sources
from glitchygames.tracing import BOOKMARKED_COPY_OF_HEADER_FIELD

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

LOG = logging.getLogger('game.replay.rebaseline')
LOG.addHandler(logging.NullHandler())

# The header field naming the recording a rebaselined one was made from
REBASELINED_FROM_HEADER_FIELD = 'rebaselined_from'
# Top-level header fields of 2026-10-20's unreleased format (now each run's, in
# measurement_runs): dropped if a recording from that day is rebaselined
UNRELEASED_HEADER_FIELDS = ('machine', 'processing_paced')
# Header fields that describe the code that produced the sprites, set to this run's
PYGAME_VERSION_HEADER_FIELD = 'pygame_version'
PYTHON_VERSION_HEADER_FIELD = 'python_version'


class RebaselineSummary(BaseModel):
    """What changed between OLD and the current code (rule 5).

    Attributes:
        path: Where the new recording was written.
        first_divergence: The first difference (of any kind), or None when nothing differs.
        frames_differing: How many compared frames differed.
        sprites_affected: Every sprite that differed in them, in the order first found.
        frames_replayed: How many of OLD's frames were replayed (and written).
        frames_recorded: How many complete frames OLD holds.
        undelivered_input_count: OLD's external events in batches the run never pumped.
        first_undelivered_input_frame: The frame of the first of them, or None.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    path: Path
    first_divergence: Divergence | None
    frames_differing: int
    sprites_affected: list[str]
    frames_replayed: int
    frames_recorded: int
    undelivered_input_count: int
    first_undelivered_input_frame: int | None

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
            frames_recorded=result.frames_recorded,
            undelivered_input_count=result.undelivered_input_count,
            first_undelivered_input_frame=result.first_undelivered_input_frame,
        )

    def describe_lost_input(self: Self) -> str | None:
        """Describe OLD's input the run never received (rule 2), if any.

        Returns:
            ``N recorded input events not delivered (first at frame F)`` and/or ``ended at
            frame R of T``, joined with ``; ``, or None when every recorded input was delivered.

        """
        parts: list[str] = []
        if self.undelivered_input_count > 0:
            events = (
                '1 recorded input event'
                if self.undelivered_input_count == 1
                else f'{self.undelivered_input_count} recorded input events'
            )
            parts.append(
                f'{events} not delivered (first at frame {self.first_undelivered_input_frame})'
            )
        if self.frames_replayed < self.frames_recorded:
            parts.append(f'ended at frame {self.frames_replayed} of {self.frames_recorded}')
        return '; '.join(parts) if parts else None

    def describe(self: Self) -> str:
        """Describe the rebaseline on one line (printed to stdout).

        Returns:
            ``Rebaselined N frames to NEW: `` then ``no frames differ``, ``K frames differ
            (first at F: <what differed>)`` with ``; sprites affected: A, B`` when sprites
            differed, or ``the run differs (at F: <what differed>)`` when no compared frame
            differed but the run did (it ended before OLD's last frame); then ``; `` and
            ``describe_lost_input()`` when input was lost.

        """
        line = f'Rebaselined {self.frames_replayed} frames to {self.path}: '
        line += self._describe_differences()
        lost_input = self.describe_lost_input()
        if lost_input is not None:
            line = f'{line}; {lost_input}'
        return line

    def _describe_differences(self: Self) -> str:
        divergence = self.first_divergence
        if divergence is None:
            return 'no frames differ'
        where = f'{divergence.frame_number}: {divergence.describe_difference()}'
        if self.frames_differing == 0:
            return f'the run differs (at {where})'
        count = (
            '1 frame differs'
            if self.frames_differing == 1
            else f'{self.frames_differing} frames differ'
        )
        differences = f'{count} (first at {where})'
        if self.sprites_affected:
            differences = f'{differences}; sprites affected: {", ".join(self.sprites_affected)}'
        return differences


def rebaseline_header(
    *,
    original_header: Mapping[str, Any],
    original_path: Path,
    measurement_run: MeasurementRun,
    original_frames: Sequence[Mapping[str, Any]] | None = None,
    source_truncated: bool = False,
) -> dict[str, Any]:
    """Return the header of a recording rebaselined from another (rule 3).

    OLD's header is kept (the seed, start time, options, screen size, saves, devices and device
    enumeration answers: the replay ran with them, so NEW replays with them), with:
    ``rebaselined_from`` naming OLD, the engine, pygame and Python versions of this run (they
    produced NEW's sprites), this run's ``measurement_run`` in front of OLD's
    ``measurement_runs``, ``source_truncated`` when OLD was cut off (NEW then ends as
    truncated, as OLD's replay did), no ``input_capture_format_version`` (NEW records the
    polled input and markers the replay saw, as format 3) and no ``bookmarked_copy_of``: NEW
    is an original, never a bookmarked copy that S may rewrite in place (it may be moved over
    a golden fixture); it holds OLD's bookmark breakpoints, which a watched replay of NEW still
    loads as its bookmarks (glitchygames/replay/driver.py, rule 16).

    Args:
        original_header: OLD's header fields (without ``format_version`` and ``frames``).
        original_path: OLD's file.
        measurement_run: This run's provenance, put in front of OLD's ``measurement_runs``
            (its ``rebaselined_from`` is set to the header's, so both name OLD one way).
        original_frames: OLD's complete frames, decoded, or None: their count is OLD's newest
            run's ``frame_count``, and every earlier run without a ``summary`` gets one from
            them (``stacked_measurement_runs``).
        source_truncated: True when OLD was cut off part way.

    Returns:
        NEW's header fields.

    """
    header = dict(original_header)
    header.pop(INPUT_CAPTURE_FORMAT_HEADER_FIELD, None)
    header.pop(BOOKMARKED_COPY_OF_HEADER_FIELD, None)
    header[ENGINE_VERSION_HEADER_FIELD] = installed_engine_version()
    header[PYGAME_VERSION_HEADER_FIELD] = pygame.version.ver
    header[PYTHON_VERSION_HEADER_FIELD] = platform.python_version()
    # Each run's provenance, newest first; NEW's frames stack this run's histories the same way,
    # as glitchygames/recording_history.py describes
    for unreleased_field in UNRELEASED_HEADER_FIELDS:
        header.pop(unreleased_field, None)
    header[MEASUREMENT_RUNS_HEADER_FIELD] = stacked_measurement_runs(
        newest=measurement_run.model_copy(update={'rebaselined_from': str(original_path)}),
        previous=original_header.get(MEASUREMENT_RUNS_HEADER_FIELD),
        previous_frame_count=None if original_frames is None else len(original_frames),
        previous_frames=() if original_frames is None else original_frames,
        budget_seconds=budget_seconds_for(header=original_header),
    )
    header[REBASELINED_FROM_HEADER_FIELD] = str(original_path)
    if source_truncated:
        header[SOURCE_TRUNCATED_HEADER_FIELD] = True
    return header


def _is_same_file(*, first: Path, second: Path) -> bool:
    if first.resolve() == second.resolve():
        return True
    return first.exists() and second.exists() and first.samefile(second)


def _path_refusal(*, new_path: Path, old_path: Path) -> str | None:
    """Say why NEW (or NEW's partial file) cannot be written: it is OLD's file (rule 1).

    Returns:
        The reason, or None.

    """
    if _is_same_file(first=new_path, second=old_path):
        return f'--rebaseline {new_path} would overwrite the recording it replays'
    new_partial_path = partial_path(destination=new_path)
    if _is_same_file(first=new_partial_path, second=old_path):
        return (
            f'--rebaseline {new_path} would write its partial file {new_partial_path} over the '
            'recording it replays'
        )
    return None


def rebaseline_refusal(*, options: Mapping[str, Any]) -> str | None:
    """Say why a rebaseline's options cannot run (rule 1), given ``--replay-trace``.

    Args:
        options: The parsed options (``rebaseline`` and ``replay_trace`` set).

    Returns:
        The reason, for the log, or None when the rebaseline can run.

    """
    if not options.get('headless'):
        return (
            '--rebaseline needs --headless: a watched replay holds frames and takes the '
            "viewer's keys"
        )
    path_refusal = _path_refusal(
        new_path=Path(options['rebaseline']), old_path=Path(options['replay_trace'])
    )
    if path_refusal is not None:
        return path_refusal
    # (the conflicting option is given, why it is refused), checked in order
    conflicting_options = (
        (
            options.get('record_trace') is not None,
            '--rebaseline writes its own recording, not with --record-trace',
        ),
        (bool(options.get('audit')), '--rebaseline replays once, not with --audit'),
        (
            options.get('replay_digest') is not None,
            '--rebaseline is not audited, not with --replay-digest',
        ),
        (
            options.get('replay_fps') == REAL_REPLAY_FPS,
            (
                '--rebaseline would record FPS events from measured frame times, not with '
                f'--replay-fps {REAL_REPLAY_FPS}'
            ),
        ),
    )
    return next((reason for is_given, reason in conflicting_options if is_given), None)


class Rebaseline:
    """Records a rebaseline's replay into the new recording and writes it (rules 3 to 5).

    ``GameEngine`` creates it for ``--rebaseline``, calls ``start_recording`` before the first
    frame and, once the run is over and the recorder closed, ``write`` (a normal end) or
    ``discard``.

    Attributes:
        destination: NEW's file.
        write_failed: True once ``write`` could not move the partial file into place (the
            engine then exits ``ExitCode.CANNOT_WRITE_OUTPUT``).

    """

    def __init__(
        self: Self,
        *,
        replay_sources: ReplaySources,
        source_path: Path,
        destination: Path,
        measurement_run: MeasurementRun,
    ) -> None:
        """Keep what the rebaseline needs.

        Args:
            replay_sources: The replay of OLD (``ReplayOptions.stop_on_divergence`` False).
            source_path: OLD's file.
            destination: NEW's file.
            measurement_run: This run's provenance, put in front of OLD's runs in NEW's header
                (``GameEngine.measurement_run``).

        """
        self._replay_sources = replay_sources
        self._measurement_run = measurement_run
        self._source_path = source_path
        self.destination = destination
        self.write_failed = False
        self._partial_path = partial_path(destination=destination)

    def start_recording(self: Self) -> GameplayRecorder:
        """Open the partial file and install recording doors over the replay (rule 3).

        Returns:
            The recorder (the engine closes it at teardown).

        """
        header = rebaseline_header(
            original_header=self._replay_sources.header,
            original_path=self._source_path,
            measurement_run=self._measurement_run,
            original_frames=self._replay_sources.recording.frames,
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

        Lost input (rule 2) is logged as a warning. A failed move keeps the partial file, logs
        it as an error and sets ``write_failed``.

        Args:
            result: The replay's settled result.

        Returns:
            The summary line, then (after a failed move) a line saying where the recording is.

        """
        summary = RebaselineSummary.from_result(result=result, path=self.destination)
        lost_input = summary.describe_lost_input()
        if lost_input is not None:
            LOG.warning('The rebaseline lost recorded input: %s', lost_input)
        move_error: OSError | None = None
        try:
            self._partial_path.replace(self.destination)
        except OSError as error:
            move_error = error
        if move_error is None:
            return summary.describe()
        self.write_failed = True
        # Logged without a traceback: the message says what failed and where the recording is
        LOG.error(
            'Could not move the rebaselined recording %s to %s (%s); it is kept at %s',
            self._partial_path,
            self.destination,
            move_error,
            self._partial_path,
        )
        return (
            f'{summary.describe()}\n{self._partial_path} could not be moved to '
            f'{self.destination} ({move_error}); the rebaselined recording is kept there'
        )

    def discard(self: Self) -> None:
        """Remove the partial recording of a run that ended early (rule 4)."""
        self._partial_path.unlink(missing_ok=True)
        LOG.warning('The rebaseline ended early; %s was not written', self.destination)
