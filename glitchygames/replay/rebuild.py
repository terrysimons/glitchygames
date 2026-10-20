"""Step back in a watched replay: restart the replay process and rebuild up to a frame.

A replay cannot run backwards, and the engine cannot be rebuilt in-process (its scenes, sprites
and singletons hold the state of every frame run so far). So ``,`` (step back), Home and D
(glitchygames/replay/controls.py) restart the replay in a fresh process at a pause frame N:

1. The watched replay ends its run with ``ReplayResult.restart_frame`` set (no divergence: the
   result's end reason is ``'restart'``) and tears down as usual, which closes its window.
2. ``GameEngine.start`` builds the restart's command (``restart_command``): this process's own
   command line (``sys.orig_argv``, so every option is kept, replay-local ones such as
   ``--replay-fps`` included) with ``--replay-pause-at-frame N`` and the recording path
   (``--replay-trace``) replaced, and ``--debug-overlay`` following whether the overlay was shown.
3. ``relaunch_replay`` runs it. The first replay process becomes the supervisor: it runs each
   restarted replay as a child with ``audit.run_command`` (the engine's one child-process
   launcher), adding ``--replay-restart-handoff PATH``. A child that steps back again does not
   start a grandchild: it writes its restart command to that handoff file and ends, and the
   supervisor runs it next. So there are never more than two replay processes, however often
   the viewer steps back, and no process restarts itself. The supervisor exits with the status
   of the first child that ends without a handoff (the replay's own result).
4. The restarted replay (``ReplayOptions.pause_at_frame``) skips the start screen (the viewer
   already started it) and rebuilds: frames 0 to N - 1 run in full but unpresented and unpaced,
   with the mixer muted (``MixerMute``), presenting and printing ``Rebuilding: frame k / N``
   every ``FAST_FORWARD_PROGRESS_INTERVAL_FRAMES`` frames (``Rebuild``) so the window does not
   look frozen. At frame N it pauses, showing frame N - 1's picture. Frame 0 always runs first
   (``FIRST_PAUSED_FRAME``), so a pause frame of 0 (Home) pauses after it.

``os.execv`` would replace the process in place, but it is not used: starting a process without
a shell is a security lint finding everywhere but the one authorised launcher
(``audit.run_command``).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Self

import pygame

from glitchygames.exit_codes import ExitCode
from glitchygames.replay.audit import run_command
from glitchygames.replay.controls import rebuild_progress_text

if TYPE_CHECKING:
    from collections.abc import Sequence

# The options a restart command replaces or sets
REPLAY_TRACE_OPTION = '--replay-trace'
PAUSE_AT_FRAME_OPTION = '--replay-pause-at-frame'
RESTART_HANDOFF_OPTION = '--replay-restart-handoff'
DEBUG_OVERLAY_OPTION = '--debug-overlay'
# The supervisor's handoff file, in a temporary directory of its own
RESTART_HANDOFF_FILE_NAME = 'restart.json'

# A rebuild presents and prints its progress once per this many frames
FAST_FORWARD_PROGRESS_INTERVAL_FRAMES = 60

# A child killed by signal N reports -N; a shell reports 128 + N (ExitCode's signal members)
SIGNAL_EXIT_STATUS_BASE = 128


def without_option(*, arguments: Sequence[str], option: str, takes_value: bool) -> list[str]:
    """Return ``arguments`` without any occurrence of a long option.

    Args:
        arguments: A command line.
        option: The option, e.g. ``--replay-trace``.
        takes_value: True for an option given as ``option VALUE`` or ``option=VALUE`` (both
            removed); False for a flag.

    Returns:
        The other arguments, in order.

    """
    kept: list[str] = []
    skips_next = False
    for argument in arguments:
        if skips_next:
            skips_next = False
            continue
        if argument == option:
            skips_next = takes_value
            continue
        if takes_value and argument.startswith(f'{option}='):
            continue
        kept.append(argument)
    return kept


def restart_command(
    *,
    original: Sequence[str],
    recording_path: Path,
    pause_at_frame: int,
    debug_overlay_visible: bool | None = None,
) -> list[str]:
    """Return the command that restarts this replay at a pause frame.

    Args:
        original: This process's command line (``sys.orig_argv``: the interpreter, its options,
            the game and its arguments).
        recording_path: The recording the restart replays (``--replay-trace``).
        pause_at_frame: The frame the restart pauses at (``--replay-pause-at-frame``).
        debug_overlay_visible: True to start with the debug overlay shown, False hidden
            (``--debug-overlay`` added or removed), None to leave the command line's choice.

    Returns:
        ``original`` without its ``--replay-trace`` and ``--replay-pause-at-frame`` (and their
        values), then ``--debug-overlay`` if it is to be shown and was not given, then
        ``--replay-trace recording_path --replay-pause-at-frame pause_at_frame``. Every other
        argument is kept in order.

    """
    command = without_option(arguments=original, option=REPLAY_TRACE_OPTION, takes_value=True)
    command = without_option(arguments=command, option=PAUSE_AT_FRAME_OPTION, takes_value=True)
    if debug_overlay_visible is False:
        command = without_option(arguments=command, option=DEBUG_OVERLAY_OPTION, takes_value=False)
    elif debug_overlay_visible and DEBUG_OVERLAY_OPTION not in command:
        command.append(DEBUG_OVERLAY_OPTION)
    return [
        *command,
        REPLAY_TRACE_OPTION,
        str(recording_path),
        PAUSE_AT_FRAME_OPTION,
        str(pause_at_frame),
    ]


def relaunch_replay(*, command: Sequence[str], handoff_path: Path | None) -> int:
    """Perform a restart: hand it to the supervisor, or supervise the restarted replays.

    Called once this replay's run is over and torn down (module docstring, step 3).

    Args:
        command: The restart's command (``restart_command``).
        handoff_path: The supervisor's handoff file when this replay is a supervised child
            (``ReplayOptions.restart_handoff_path``), or None in the first replay process.

    Returns:
        The status this process exits with: ``ExitCode.SUCCESS`` once a supervised child has
        handed its restart over; for the supervisor, the status of the last restarted replay
        (128 + N for one killed by signal N), or ``ExitCode.INTERRUPTED`` after Ctrl-C.

    """
    if handoff_path is not None:
        handoff_path.write_text(json.dumps(list(command)), encoding='utf-8')
        return ExitCode.SUCCESS
    # The children write to the same streams: this process's output comes first
    sys.stdout.flush()
    sys.stderr.flush()
    with tempfile.TemporaryDirectory(prefix='glitchygames-replay-restart-') as directory:
        supervisor_handoff_path = Path(directory) / RESTART_HANDOFF_FILE_NAME
        next_command: list[str] | None = list(command)
        returncode = ExitCode.SUCCESS.value
        try:
            while next_command is not None:
                child_command = [
                    # This interpreter, as the audit runs its children (no PATH lookup)
                    sys.executable,
                    *without_option(
                        arguments=next_command[1:], option=RESTART_HANDOFF_OPTION, takes_value=True
                    ),
                    RESTART_HANDOFF_OPTION,
                    str(supervisor_handoff_path),
                ]
                supervisor_handoff_path.unlink(missing_ok=True)
                # A watched replay runs as long as the viewer watches: no timeout
                returncode = run_command(
                    command=child_command, environment=os.environ, timeout_seconds=None
                ).returncode
                next_command = (
                    json.loads(supervisor_handoff_path.read_text(encoding='utf-8'))
                    if supervisor_handoff_path.exists()
                    else None
                )
        except KeyboardInterrupt:
            # The child got the same Ctrl-C and ended (subprocess.run waits briefly, then kills)
            return ExitCode.INTERRUPTED
    if returncode < 0:
        return SIGNAL_EXIT_STATUS_BASE - returncode
    return returncode


class MixerMute:
    """Silence every mixer channel while a replay rebuilds, then cut its sounds off.

    The rebuild runs frames unpaced, so their sounds would all play at once. Channel volumes
    persist across plays, so a zero volume silences every sound the rebuild starts. Not game
    state: audio is played, never compared, so muting cannot change the replay.
    """

    def __init__(self: Self) -> None:
        """Start unmuted."""
        # Each channel's volume before muting, or None while not muted
        self._channel_volumes: list[float] | None = None

    def mute(self: Self) -> None:
        """Set every channel's volume to 0, keeping the volumes (once; nothing without a mixer)."""
        if self._channel_volumes is not None or pygame.mixer.get_init() is None:
            return
        channels = [pygame.mixer.Channel(index) for index in range(pygame.mixer.get_num_channels())]
        self._channel_volumes = [channel.get_volume() for channel in channels]
        for channel in channels:
            channel.set_volume(0.0)

    def unmute(self: Self) -> None:
        """Stop every sound the rebuild started, then give each channel its volume back."""
        channel_volumes = self._channel_volumes
        if channel_volumes is None:
            return
        self._channel_volumes = None
        if pygame.mixer.get_init() is None:
            return
        pygame.mixer.stop()
        for index, volume in enumerate(channel_volumes[: pygame.mixer.get_num_channels()]):
            pygame.mixer.Channel(index).set_volume(volume)


class Rebuild:
    """A restarted replay's run up to its pause frame (module docstring, step 4).

    Attributes:
        target_frame: The frame the replay pauses at.

    """

    def __init__(self: Self, *, target_frame: int) -> None:
        """Prepare to rebuild up to ``target_frame``.

        Args:
            target_frame: The frame the replay pauses at (at least ``FIRST_PAUSED_FRAME``).

        """
        self.target_frame = target_frame
        self._mute = MixerMute()
        self._last_progress_frame = 0

    def begin(self: Self) -> None:
        """Mute the mixer for the rebuild (again: nothing)."""
        self._mute.mute()

    def progress_is_due(self: Self, *, frame_index: int) -> bool:
        """Report whether the rebuild shows its progress before ``frame_index`` runs.

        Due once per ``FAST_FORWARD_PROGRESS_INTERVAL_FRAMES`` frames; when due, the progress
        line is printed to stdout too.

        Args:
            frame_index: The frame about to run.

        Returns:
            True the first time it is asked at each interval's frame.

        """
        if (
            frame_index == self._last_progress_frame
            or frame_index % FAST_FORWARD_PROGRESS_INTERVAL_FRAMES != 0
        ):
            return False
        self._last_progress_frame = frame_index
        sys.stdout.write(
            f'{rebuild_progress_text(frame_index=frame_index, target_frame=self.target_frame)}\n'
        )
        sys.stdout.flush()
        return True

    def finish(self: Self) -> None:
        """End the rebuild: the rebuild's sounds stop and the mixer is heard again."""
        self._mute.unmute()
