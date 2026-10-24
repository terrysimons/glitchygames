"""Step back in a watched replay: restart the replay process and rebuild up to a frame.

A replay cannot run backwards, and the engine cannot be rebuilt in-process (its scenes, sprites
and singletons hold the state of every frame run so far). So ``,`` (step back), Home and D
(glitchygames/replay/controls.py) restart the replay in a fresh process at a pause frame N:

1. The watched replay ends its run with ``ReplayResult.restart_frame`` set (the result's end
   reason is ``'restart'``, unless it already diverged or ended) and tears down as usual, which
   closes its window; the end-of-run performance and unhandled-event reports are skipped.
2. ``GameEngine._restart_replay`` builds the restart's command (``restart_command``): this
   process's own command line (``sys.orig_argv``, so every option is kept, replay-local ones
   such as ``--replay-fps`` included) with ``--replay-trace`` (the recording) and
   ``--replay-pause-at-frame N`` replaced, an explicit ``--debug-overlay`` or
   ``--no-debug-overlay`` (whether the overlay was shown) and ``--replay-viewer-state`` (the
   speed, the debug overlay's panel and the divergence found so far, so D works at once:
   ``ViewerState``). They are appended, the last occurrence of an option winning (an earlier
   abbreviation such as ``--debug-o`` included), before any bare ``--``.
3. ``relaunch_replay`` runs it, with the engine's signal handlers installed again (a SIGTERM or
   SIGHUP raises SystemExit, and ``subprocess.run`` then kills the child with SIGKILL, without
   its teardown, and reaps it: acceptable, as a replay never records). The first
   replay process becomes the supervisor: it runs each restarted replay as a child with
   ``glitchygames.process.run_command`` (the engine's one child-process launcher), adding
   ``--replay-restart-handoff PATH``. A child that steps back again does not start a grandchild:
   it writes a ``RestartHandoff`` (its restart command and its own result's exit code) to that
   file, whole (written aside, then moved into place), and ends; the supervisor runs it next. So
   there are never more than two replay processes, however often the viewer steps back, and no
   process restarts itself. The supervisor exits with the last child's status, but a divergence
   in any earlier run is kept: when the last child ends with ``SUCCESS``, the first non-success
   result handed over (or the first run's own) is the status. An unreadable handoff or a child
   that cannot start is logged and exits ``ExitCode.INTERNAL_ERROR``.

   The supervisor keeps the memory its own replay used (the engine's scenes, sprites, the
   recording's frames and pygame's modules: pygame is quit, the rest is not released) while the
   children run; only the first process supervises, so this is paid once, not per restart.
4. The restarted replay (``ReplayOptions.pause_at_frame``) skips the start screen (the viewer
   already started it) and rebuilds: frames 0 to N - 1 run in full but unpresented and unpaced,
   in silence (``FrameSilencer``, glitchygames/replay/silence.py, which an instant replay's
   fast-forward shares: ``Rebuild.silence_frame`` stops every sound a frame started after it,
   as ``Sound.play()`` gives its channel full volume again, and music is paused until the
   rebuild ends; ``Rebuild.begin`` follows the game's own music pauses, so music the game
   paused itself stays paused), presenting ``Rebuilding: frame k / N`` every
   ``REBUILD_PROGRESS_INTERVAL_SECONDS`` of real time and printing it every
   ``REBUILD_PROGRESS_PRINT_INTERVAL_SECONDS``
   (``Rebuild.progress_is_due``), so the window does not look frozen. At frame N it pauses,
   showing frame N - 1's picture. Frame 0 always runs first (``FIRST_PAUSED_FRAME``), so a pause
   frame of 0 (Home) pauses after it. A game that asks the mixer what is playing may get a
   different answer during the rebuild than when it was recorded (glitchygames/replay/
   silence.py says why the replay is unaffected).

``os.execv`` would replace the process in place, but it is not used: starting a process without
a shell is a security lint finding everywhere but the one authorised launcher
(``glitchygames.process.run_command``).
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from glitchygames.debug.overlay import DebugPanel
from glitchygames.exit_codes import ExitCode
from glitchygames.output_files import write_aside_then_replace
from glitchygames.process import run_command, with_options_appended, without_option
from glitchygames.replay.controls import ReplayControls, rebuild_progress_text
from glitchygames.replay.silence import FrameSilencer

if TYPE_CHECKING:
    from collections.abc import Sequence

LOG = logging.getLogger('game.replay')
LOG.addHandler(logging.NullHandler())

# The options a restart command replaces or sets
REPLAY_TRACE_OPTION = '--replay-trace'
PAUSE_AT_FRAME_OPTION = '--replay-pause-at-frame'
RESTART_HANDOFF_OPTION = '--replay-restart-handoff'
VIEWER_STATE_OPTION = '--replay-viewer-state'
DEBUG_OVERLAY_OPTION = '--debug-overlay'
NO_DEBUG_OVERLAY_OPTION = '--no-debug-overlay'
# The supervisor's handoff file, in a temporary directory of its own (written aside, then moved
# into place: glitchygames.output_files.write_aside_then_replace)
RESTART_HANDOFF_FILE_NAME = 'restart.json'

# A rebuild presents its progress this often (real time), and prints it this often
REBUILD_PROGRESS_INTERVAL_SECONDS = 0.1
REBUILD_PROGRESS_PRINT_INTERVAL_SECONDS = 1.0

# A child killed by signal N reports -N; a shell reports 128 + N (ExitCode's signal members)
SIGNAL_EXIT_STATUS_BASE = 128


class ViewerState(BaseModel):
    """What the viewer had set, carried into a restarted replay (``--replay-viewer-state``).

    Attributes:
        speed: The playback speed.
        debug_panel: The debug overlay's panel (F4).
        divergence_frame: The frame the replay diverged at, if it had (so D works at once).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    speed: float = Field(default=1.0, ge=ReplayControls.MIN_SPEED, le=ReplayControls.MAX_SPEED)
    debug_panel: DebugPanel = DebugPanel.ALL
    divergence_frame: int | None = Field(default=None, ge=0)


def parse_viewer_state(text: str) -> ViewerState:
    """Read ``--replay-viewer-state`` (argparse's ``type``: a ValueError is a usage error).

    Args:
        text: The state as JSON.

    Returns:
        The state.

    """
    return ViewerState.model_validate_json(text)


class RestartHandoff(BaseModel):
    """What a supervised replay hands the supervisor when it steps back (module docstring).

    Attributes:
        command: The restart's command (``restart_command``).
        result_exit_code: The exit code the handing-over replay's own result has
            (``ReplayResult.exit_code``): ``REPLAY_DIVERGED`` once it diverged.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    command: list[str] = Field(min_length=1)
    result_exit_code: int


def restart_command(
    *,
    original: Sequence[str],
    recording_path: Path,
    pause_at_frame: int,
    debug_overlay_visible: bool,
    viewer_state: ViewerState | None = None,
) -> list[str]:
    """Return the command that restarts this replay at a pause frame.

    Args:
        original: This process's command line (``sys.orig_argv``: the interpreter, its options,
            the game and its arguments).
        recording_path: The recording the restart replays (``--replay-trace``).
        pause_at_frame: The frame the restart pauses at (``--replay-pause-at-frame``).
        debug_overlay_visible: Whether the restart starts with the debug overlay shown.
        viewer_state: The viewer's state to carry over (``--replay-viewer-state``), or None.

    Returns:
        ``original`` without its ``--replay-trace``, ``--replay-pause-at-frame``,
        ``--replay-viewer-state``, ``--debug-overlay`` and ``--no-debug-overlay``, then
        ``--debug-overlay`` or ``--no-debug-overlay``, the viewer state when given, and
        ``--replay-trace recording_path --replay-pause-at-frame pause_at_frame``, all before
        any bare ``--``. Every other argument is kept in order.

    """
    command = list(original)
    for option, takes_value in (
        (REPLAY_TRACE_OPTION, True),
        (PAUSE_AT_FRAME_OPTION, True),
        (VIEWER_STATE_OPTION, True),
        (DEBUG_OVERLAY_OPTION, False),
        (NO_DEBUG_OVERLAY_OPTION, False),
    ):
        command = without_option(arguments=command, option=option, takes_value=takes_value)
    appended = [DEBUG_OVERLAY_OPTION if debug_overlay_visible else NO_DEBUG_OVERLAY_OPTION]
    if viewer_state is not None:
        appended += [VIEWER_STATE_OPTION, viewer_state.model_dump_json()]
    appended += [
        REPLAY_TRACE_OPTION,
        str(recording_path),
        PAUSE_AT_FRAME_OPTION,
        str(pause_at_frame),
    ]
    return with_options_appended(arguments=command, appended=appended)


def relaunch_replay(
    *, command: Sequence[str], handoff_path: Path | None, result_exit_code: int
) -> int:
    """Perform a restart: hand it to the supervisor, or supervise the restarted replays.

    Called once this replay's run is over and torn down (module docstring, step 3).

    Args:
        command: The restart's command (``restart_command``).
        handoff_path: The supervisor's handoff file when this replay is a supervised child
            (``ReplayOptions.restart_handoff_path``), or None in the first replay process.
        result_exit_code: The exit code this replay's own result has
            (``ReplayResult.exit_code``).

    Returns:
        The status this process exits with: ``ExitCode.SUCCESS`` once a supervised child has
        handed its restart over; for the supervisor, the last restarted replay's status (128 +
        N for one killed by signal N) or, when that is ``SUCCESS``, the first non-success result
        of an earlier run; ``ExitCode.INTERRUPTED`` after Ctrl-C, ``ExitCode.INTERNAL_ERROR``
        when a child cannot start or its handoff cannot be read, or when this supervised
        child cannot write its handoff.

    """
    handoff = RestartHandoff(command=list(command), result_exit_code=result_exit_code)
    if handoff_path is not None:
        try:
            # Moved into place whole: the supervisor never reads half a handoff
            write_aside_then_replace(
                destination=handoff_path,
                write=lambda aside: aside.write_text(handoff.model_dump_json(), encoding='utf-8'),
            )
        except OSError:
            # Not exit 1 (REPLAY_DIVERGED), which the supervisor would report as a divergence
            LOG.exception('Cannot hand the restart over to the supervising replay')
            return ExitCode.INTERNAL_ERROR
        return ExitCode.SUCCESS
    # The children write to the same streams: this process's output comes first
    sys.stdout.flush()
    sys.stderr.flush()
    with tempfile.TemporaryDirectory(prefix='glitchygames-replay-restart-') as directory:
        try:
            return _supervise(
                first_handoff=handoff, handoff_path=Path(directory) / RESTART_HANDOFF_FILE_NAME
            )
        except KeyboardInterrupt:
            # The child got the same Ctrl-C and ended (subprocess.run waits briefly, then kills)
            return ExitCode.INTERRUPTED


def _supervise(*, first_handoff: RestartHandoff, handoff_path: Path) -> int:
    """Run restarted replays until one ends without handing a restart over.

    Args:
        first_handoff: The first restart, with the first replay's own result.
        handoff_path: The handoff file each child is told about.

    Returns:
        The supervisor's status (``relaunch_replay``).

    """
    handoff: RestartHandoff | None = first_handoff
    earlier_result = ExitCode.SUCCESS.value
    returncode = ExitCode.SUCCESS.value
    while handoff is not None:
        if earlier_result == ExitCode.SUCCESS:
            earlier_result = handoff.result_exit_code
        child_command = [
            # This interpreter, as the audit runs its children (no PATH lookup)
            sys.executable,
            *with_options_appended(
                arguments=without_option(
                    arguments=handoff.command[1:], option=RESTART_HANDOFF_OPTION, takes_value=True
                ),
                appended=[RESTART_HANDOFF_OPTION, str(handoff_path)],
            ),
        ]
        handoff_path.unlink(missing_ok=True)
        try:
            # A watched replay runs as long as the viewer watches: no timeout
            returncode = run_command(
                command=child_command, environment=os.environ, timeout_seconds=None
            ).returncode
            handoff = (
                RestartHandoff.model_validate_json(handoff_path.read_text(encoding='utf-8'))
                if handoff_path.exists()
                else None
            )
        except ValidationError, UnicodeDecodeError:
            LOG.exception('Cannot restart the replay: the restart handoff is unusable')
            return ExitCode.INTERNAL_ERROR
        except OSError:
            # The child could not start, or its handoff could not be read
            LOG.exception('Cannot restart the replay')
            return ExitCode.INTERNAL_ERROR
    if returncode < 0:
        return SIGNAL_EXIT_STATUS_BASE - returncode
    if returncode == ExitCode.SUCCESS:
        return earlier_result
    return returncode


class Rebuild(FrameSilencer):
    """A restarted replay's run up to its pause frame (module docstring, step 4).

    Its frames run in silence as an instant replay's fast-forward does: ``begin``,
    ``silence_frame``, ``stop_following_music`` and ``finish`` are ``FrameSilencer``'s
    (glitchygames/replay/silence.py).

    Attributes:
        target_frame: The frame the replay pauses at.

    """

    def __init__(self: Self, *, target_frame: int) -> None:
        """Prepare to rebuild up to ``target_frame``.

        Args:
            target_frame: The frame the replay pauses at (at least ``FIRST_PAUSED_FRAME``).

        """
        super().__init__()
        self.target_frame = target_frame
        # When the progress is next shown and printed (set by the first question)
        self._next_progress_seconds: float | None = None
        self._next_print_seconds: float | None = None

    def progress_is_due(self: Self, *, frame_index: int, now: float) -> bool:
        """Report whether the rebuild shows its progress before ``frame_index`` runs.

        Due every ``REBUILD_PROGRESS_INTERVAL_SECONDS`` of real time from the first question
        (which is never due); the progress line is printed to stdout at most every
        ``REBUILD_PROGRESS_PRINT_INTERVAL_SECONDS``, when a showing is due.

        Args:
            frame_index: The frame about to run.
            now: The measured time (``glitchygames.clock.measured_seconds``).

        Returns:
            True when the progress is to be shown now.

        """
        if self._next_progress_seconds is None or self._next_print_seconds is None:
            self._next_progress_seconds = now + REBUILD_PROGRESS_INTERVAL_SECONDS
            self._next_print_seconds = now + REBUILD_PROGRESS_PRINT_INTERVAL_SECONDS
            return False
        if now < self._next_progress_seconds:
            return False
        self._next_progress_seconds = max(
            self._next_progress_seconds + REBUILD_PROGRESS_INTERVAL_SECONDS, now
        )
        if now >= self._next_print_seconds:
            self._next_print_seconds = max(
                self._next_print_seconds + REBUILD_PROGRESS_PRINT_INTERVAL_SECONDS, now
            )
            progress_text = rebuild_progress_text(
                frame_index=frame_index, target_frame=self.target_frame
            )
            sys.stdout.write(f'{progress_text}\n')
            sys.stdout.flush()
        return True
