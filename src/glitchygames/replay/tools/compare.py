"""``--compare-trace OLD``: the onion skin, OLD's frames drawn over a watched replay of NEW.

The contract (decision 18 of plans/2026-10-26-workspace-packages-3-demos.md, Task D11):

1. **What is shown.** ``--replay-trace NEW --compare-trace OLD [--compare-alpha PERCENT]`` (on
   the game, or ``glitchygames replay-trace NEW --compare-trace OLD ...``) replays NEW watched,
   as any watched replay, drawn solid. On each presented frame, OLD's frame of the same number is
   drawn over it at ``PERCENT`` opacity (``DEFAULT_COMPARE_ALPHA_PERCENT`` when not given; 0 to
   100, the parser refuses any other: ``argument_types.percent_from_zero_to_one_hundred``), then
   the viewer's status bar over both (``ReplaySources.draw_overlay``; the debug overlay, drawn
   before the doors' overlay, is under OLD too). Only the presented copy is drawn on, so nothing
   in NEW's replay changes: its frames, comparisons, result and exit code are a plain watched
   replay's. While a restarted replay rebuilds, nothing is drawn over its progress screen.
2. **OLD's child.** OLD is replayed headless by a child process (``OnionSkin``): OLD's own game,
   the console script that starts the module its header names (``traces.find_recorded_game``),
   or, when none does (a game started as a script), this game started again
   (``children.running_game_command``), with ``--replay-trace OLD --headless`` and the hidden
   ``--replay-frame-stream PORT``. It replays under OLD's own seed, so it compares as a plain
   headless replay does and stops at its first divergence (it then ends there, and its exit and
   output are logged). The child is started on the first presented frame, so it runs only inside
   the run, whose teardown (``GameEngine._shutdown``) always stops it and waits for it
   (``OnionSkin.stop``): when the replay ends, fails, is interrupted or restarts.
3. **The frame stream.** The parent listens on a port of ``FRAME_STREAM_HOST`` (loopback only),
   and the child connects to it (``FrameStream``) before its first frame. After each replayed
   frame, ``ReplaySources.end_frame`` hands the display surface (the frame as presented, overlays
   never on it) to the stream, which writes ``FRAME_HEADER`` (the frame's number, width and
   height: three little-endian unsigned 32-bit integers), then its pixels: width x height x 3
   bytes of RGB, rows top to bottom (``pygame.image.tobytes``, ``FRAME_PIXEL_FORMAT``). A socket,
   not an inherited pipe: the one child launcher (``glitchygames.process.start_command``) passes
   no descriptors, and a socket works the same on every platform.
4. **Lockstep.** The parent reads frames only when it draws one: it reads (and drops) OLD's
   frames until it holds the one numbered as the frame presented, and keeps that one (memory
   holds one frame). Paused, it reads nothing, so the child blocks on the full socket within a
   few frames: the two runs move together, through pause and frame steps too.
5. **OLD shorter than NEW.** When OLD's stream ends, its last frame stays, labelled
   ``OLD_ENDED_LABEL`` ("OLD ended at frame N"). NEW shorter: NEW's replay ends as usual and the
   teardown stops the child. A child that streams nothing (it exits or never connects within
   ``CHILD_CONNECT_TIMEOUT_SECONDS``) draws nothing over NEW, labelled ``OLD_NOT_REPLAYED_LABEL``,
   with its output logged.
6. **Refused before anything runs** (``compare_trace_refusal``, ``old_recording_refusal``):
   with ``--headless`` (an onion skin is watched; a headless replay under another seed, or
   ``--rebaseline``, is the headless way to see what changed), ``--audit`` or ``--rebaseline``
   (``ExitCode.OPTIONS_REFUSED``); an OLD recorded on a display of another size than NEW's, or
   that is not a readable recording (``ExitCode.UNUSABLE_INPUT``); a missing OLD
   (``ExitCode.MISSING_INPUT``). A frame stream without ``--headless`` is refused too
   (``frame_stream_refusal``): it is a headless child's.
7. **Every seed row.** NEW may be OLD itself under another seed
   (``--replay-trace OLD --random-seed N --compare-trace OLD``: the seed rule's row 5, which
   compares and writes nothing), so OLD's run under its own seed is shown over the new seed's.
8. **Step back.** The viewer's step back (and Home, D) restarts NEW's process with
   ``--replay-pause-at-frame N`` (glitchygames/replay/rebuild.py), keeping every other option,
   ``--compare-trace`` included. The restarted process starts its own child with the same
   ``--replay-pause-at-frame N``: a headless replay does not pause, but its stream then writes
   nothing before the frame the restart shows paused (``first_streamed_frame``: N - 1, the
   rebuild's own pause rule), so the child runs on through the frames NEW rebuilds unshown.
"""

from __future__ import annotations

import contextlib
import dataclasses
import logging
import os
import socket
import struct
import tempfile
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Self

import pygame

from glitchygames.clock import measured_seconds
from glitchygames.debug.overlay import load_debug_font
from glitchygames.debug.panels import HUD_MARGIN, HUD_TEXT_COLOR, blit_text
from glitchygames.exit_codes import ExitCode
from glitchygames.process import (
    STOP_GRACE_SECONDS,
    TimeoutExpired,
    start_command,
    stop_command,
)
from glitchygames.replay.controls import FIRST_PAUSED_FRAME
from glitchygames.replay.driver import recorded_screen_size
from glitchygames.replay.tools.children import running_game_command
from glitchygames.replay.tools.traces import RecordedGameRefusal, find_recorded_game
from glitchygames.tracing import TraceFormatError, TraceReader

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from glitchygames.process import RunningProcess

LOG = logging.getLogger('game.replay')
LOG.addHandler(logging.NullHandler())

# OLD's opacity over NEW when --compare-alpha is not given
DEFAULT_COMPARE_ALPHA_PERCENT = 50.0
# The frame stream's host: loopback only, so nothing outside this machine can connect
FRAME_STREAM_HOST = '127.0.0.1'
# Each streamed frame: its number, width and height (little-endian unsigned 32-bit integers),
# then width x height x 3 bytes of RGB, rows top to bottom
FRAME_HEADER = struct.Struct('<III')
FRAME_PIXEL_FORMAT = 'RGB'
BYTES_PER_PIXEL = 3
# The opacity a blit's alpha gives at 100%
FULLY_OPAQUE_ALPHA = 255
ONE_HUNDRED_PERCENT = 100.0
# How long the parent waits for OLD's child to connect (it imports the game and reads OLD
# first), and how often it looks whether the child ended instead
CHILD_CONNECT_TIMEOUT_SECONDS = 60.0
ACCEPT_POLL_SECONDS = 0.1
# Options of OLD's child besides --replay-trace OLD --headless (rules 2, 3 and 8)
FRAME_STREAM_OPTION = '--replay-frame-stream'
PAUSE_AT_FRAME_OPTION = '--replay-pause-at-frame'
# The labels drawn at the top of the presented frame
OLD_ENDED_LABEL = 'OLD ended at frame {frame_index}'
OLD_NOT_REPLAYED_LABEL = 'OLD could not be replayed (see the log)'


@dataclasses.dataclass(frozen=True)
class CompareRefusal:
    """Why ``--compare-trace OLD`` cannot run, and the exit code it is refused with.

    Attributes:
        exit_code: How the run ends.
        reason: Why, in a line (logged as ``Cannot compare with OLD: <reason>``).

    """

    exit_code: ExitCode
    reason: str


def compare_trace_refusal(*, options: Mapping[str, Any]) -> str | None:
    """Return why ``--compare-trace`` cannot go with the run's other options (rule 6), if it can't.

    Args:
        options: The run's parsed options.

    Returns:
        The reason, or None (also when ``--compare-trace`` is not given).

    """
    if options.get('compare_trace') is None:
        return None
    if options.get('headless'):
        return (
            'an onion skin is watched, so not with --headless (headless, a replay under '
            '--random-seed N, or --rebaseline NEW, reports what changed)'
        )
    if options.get('audit'):
        return 'not with --audit'
    if options.get('rebaseline') is not None:
        return 'not with --rebaseline'
    return None


def frame_stream_refusal(*, options: Mapping[str, Any]) -> str | None:
    """Return why ``--replay-frame-stream`` cannot run (rule 6), if it can't.

    Args:
        options: The run's parsed options.

    Returns:
        The reason, or None (also when no frame stream is given).

    """
    if options.get('replay_frame_stream') is None or options.get('headless'):
        return None
    return '--replay-frame-stream needs --headless: it streams a headless replay of OLD'


def old_recording_refusal(
    *, old_path: Path, new_header: Mapping[str, Any]
) -> CompareRefusal | None:
    """Return why OLD cannot be drawn over NEW (rule 6), if it can't.

    Args:
        old_path: OLD.
        new_header: NEW's header (its ``screen_size`` already read by the replay).

    Returns:
        The refusal, or None.

    """
    try:
        with TraceReader(path=old_path) as reader:
            old_size = recorded_screen_size(header=reader.header)
    except FileNotFoundError:
        return CompareRefusal(exit_code=ExitCode.MISSING_INPUT, reason='no such recording')
    # A TraceFormatError is a ValueError; an unreadable file (gzip.BadGzipFile) an OSError
    except OSError, TraceFormatError:
        return CompareRefusal(exit_code=ExitCode.UNUSABLE_INPUT, reason='not a readable recording')
    new_size = recorded_screen_size(header=new_header)
    if old_size is None or new_size is None or old_size == new_size:
        return None
    return CompareRefusal(
        exit_code=ExitCode.UNUSABLE_INPUT,
        reason=(
            f'OLD was recorded on a {old_size[0]}x{old_size[1]} display and NEW on a '
            f'{new_size[0]}x{new_size[1]} one: an onion skin needs the same size'
        ),
    )


def first_streamed_frame(*, pause_at_frame: int | None) -> int:
    """Return the first frame a stream writes: the one a restart at ``pause_at_frame`` shows.

    A restarted watched replay pauses with frame ``max(N, FIRST_PAUSED_FRAME)`` next, showing the
    frame before it (glitchygames/replay/rebuild.py); the frames before that are rebuilt unshown.

    Args:
        pause_at_frame: The restart's ``--replay-pause-at-frame``, or None (no restart).

    Returns:
        The frame's number (0 without a restart).

    """
    if pause_at_frame is None:
        return 0
    return max(pause_at_frame, FIRST_PAUSED_FRAME) - 1


def old_game_command(*, old_path: Path) -> list[str]:
    """Return the command that starts OLD's game, without its arguments (rule 2).

    Args:
        old_path: OLD.

    Returns:
        The console script that starts the game OLD's header names, else this process's game
        started again (``running_game_command``: a game started as a script names its module
        ``__main__``, which no console script starts).

    """
    found = find_recorded_game(recording=old_path, project_root=Path.cwd())
    if isinstance(found, RecordedGameRefusal):
        return running_game_command()
    _, launch = found
    return launch.command


class FrameStream:
    """The child's end of the frame stream: each replayed frame, as presented (rule 3).

    Attributes:
        first_frame: The first frame written (``first_streamed_frame``); earlier ones are not.

    """

    def __init__(self: Self, *, connection: socket.socket, first_frame: int) -> None:
        """Stream into a connected socket.

        Args:
            connection: The connection to the parent.
            first_frame: The first frame to write.

        """
        self._connection: socket.socket | None = connection
        self.first_frame = first_frame

    @classmethod
    def connect(cls, *, port: int, first_frame: int) -> FrameStream:
        """Connect to the parent listening on ``port`` (``FRAME_STREAM_HOST``).

        Args:
            port: The parent's port (``--replay-frame-stream``).
            first_frame: The first frame to write.

        Returns:
            The stream (nothing listening there: ``socket.create_connection``'s OSError).

        """
        return cls(
            connection=socket.create_connection((FRAME_STREAM_HOST, port)), first_frame=first_frame
        )

    def write_frame(self: Self, *, frame_index: int, surface: pygame.Surface) -> bool:
        """Write a replayed frame, unless it comes before the first one.

        Args:
            frame_index: The frame's number.
            surface: The display surface, holding the frame as presented.

        Returns:
            True while the parent reads; False once it is gone (or the stream was closed), so
            the replay stops instead of running on unseen.

        """
        if self._connection is None:
            return False
        if frame_index < self.first_frame:
            return True
        width, height = surface.get_size()
        try:
            self._connection.sendall(FRAME_HEADER.pack(frame_index, width, height))
            self._connection.sendall(pygame.image.tobytes(surface, FRAME_PIXEL_FORMAT))
        except OSError:
            self.close()
            return False
        return True

    def close(self: Self) -> None:
        """Close the stream (the parent then reads its end); once only."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None


@dataclasses.dataclass(frozen=True)
class HeldFrame:
    """The one OLD frame the onion skin keeps.

    Attributes:
        frame_index: Its number.
        surface: Its picture, at the onion skin's alpha.

    """

    frame_index: int
    surface: pygame.Surface


class OnionSkin:
    """The parent's end: OLD's child, and OLD's frames drawn over NEW's (rules 2 to 5).

    Attributes:
        old_path: OLD.
        alpha_percent: How opaque OLD is drawn, from 0 to 100.
        game_command: How OLD's game is started, without its arguments (``old_game_command``).
        pause_at_frame: NEW's restart pause frame, passed on to the child (rule 8), or None.
        command: The child's whole command, once started (else empty).
        process: The child, once started (else None).
        frames_received: How many frames the child has sent.
        label: The label drawn over the frame (OLD ended, or never replayed), or None.

    """

    def __init__(
        self: Self,
        *,
        old_path: Path,
        alpha_percent: float,
        game_command: Sequence[str],
        pause_at_frame: int | None,
    ) -> None:
        """Prepare the onion skin; the child starts on the first ``draw``.

        Args:
            old_path: OLD.
            alpha_percent: How opaque OLD is drawn, from 0 to 100.
            game_command: How OLD's game is started, without its arguments.
            pause_at_frame: NEW's restart pause frame, or None.

        """
        self.old_path = old_path
        self.alpha_percent = alpha_percent
        self.game_command = list(game_command)
        self.pause_at_frame = pause_at_frame
        self.command: list[str] = []
        self.process: RunningProcess[str] | None = None
        self.frames_received = 0
        self.label: str | None = None
        self._listener: socket.socket | None = None
        self._connection: socket.socket | None = None
        self._output: IO[str] | None = None
        self._output_path: Path | None = None
        self._held: HeldFrame | None = None
        # True once OLD has no more frames to send (its stream ended, or it never streamed)
        self._has_ended = False
        self._is_stopped = False
        self._font: pygame.font.Font | None = None

    @property
    def held_frame_index(self: Self) -> int | None:
        """The number of the OLD frame held, or None before one arrived."""
        return None if self._held is None else self._held.frame_index

    @property
    def is_stopped(self: Self) -> bool:
        """True once ``stop`` ran: the child ended and was waited for."""
        return self._is_stopped

    def draw(self: Self, *, surface: pygame.Surface, frame_index: int) -> None:
        """Draw OLD's frame ``frame_index`` over NEW's presented frame (rules 1, 4 and 5).

        Starts the child on the first call. Reads OLD's frames up to ``frame_index``; draws the
        one held at the alpha when it is that frame, or OLD's last one (labelled) once OLD has
        ended before it. A frame OLD did not stream (before its first) draws nothing.

        Args:
            surface: NEW's presented frame (a copy: the display's clean frame comes back after).
            frame_index: The NEW frame it shows.

        """
        if self.process is None and not self._has_ended:
            self._start()
        self._read_up_to(frame_index=frame_index)
        held = self._held
        if held is None:
            # _read_up_to returns without a frame only when OLD ended before sending one
            self._draw_label(surface=surface, text=OLD_NOT_REPLAYED_LABEL)
            return
        if held.frame_index > frame_index:
            return
        surface.blit(held.surface, (0, 0))
        if held.frame_index < frame_index:
            self._draw_label(
                surface=surface, text=OLD_ENDED_LABEL.format(frame_index=held.frame_index)
            )

    def stop(self: Self) -> None:
        """Stop the child (if it still runs) and wait for it; close the stream. Idempotent."""
        self._close_sockets()
        if self.process is not None:
            stop_command(process=self.process)
        if self._output is not None:
            self._output.close()
            self._output = None
        if self._output_path is not None:
            self._output_path.unlink(missing_ok=True)
            self._output_path = None
        self._is_stopped = True

    def _close_sockets(self: Self) -> None:
        """Close the connection to the child and the listener (each once)."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        if self._listener is not None:
            self._listener.close()
            self._listener = None

    def _start(self: Self) -> None:
        """Listen on a loopback port and start OLD's child, its output kept for the log."""
        self._listener = socket.create_server((FRAME_STREAM_HOST, 0))
        self._listener.settimeout(ACCEPT_POLL_SECONDS)
        port: int = self._listener.getsockname()[1]
        self.command = [
            *self.game_command,
            '--replay-trace',
            str(self.old_path),
            '--headless',
            '--log-level',
            'warning',
            FRAME_STREAM_OPTION,
            str(port),
        ]
        if self.pause_at_frame is not None:
            self.command += [PAUSE_AT_FRAME_OPTION, str(self.pause_at_frame)]
        # The child's output, kept for the log for its whole run (closed and removed by stop())
        descriptor, output_path = tempfile.mkstemp(prefix='compare-trace-', suffix='.log')
        self._output_path = Path(output_path)
        self._output = os.fdopen(descriptor, 'w+', encoding='utf-8')
        self.process = start_command(
            command=self.command, environment=os.environ, output=self._output
        )
        LOG.info('Comparing with %s, replayed by a child process', self.old_path)

    def _read_up_to(self: Self, *, frame_index: int) -> None:
        """Read OLD's frames until the one held is ``frame_index`` (or later), or OLD ended.

        Args:
            frame_index: The frame wanted.

        """
        while not self._has_ended and (self._held is None or self._held.frame_index < frame_index):
            if self._connection is None and not self._accept():
                return
            self._read_one_frame()

    def _accept(self: Self) -> bool:
        """Wait for the child to connect, unless it ends or takes too long (rule 5).

        Returns:
            True once connected; False when OLD ended without connecting.

        """
        assert self._listener is not None
        assert self.process is not None
        deadline = measured_seconds() + CHILD_CONNECT_TIMEOUT_SECONDS
        while True:
            try:
                connection, _ = self._listener.accept()
            except TimeoutError:
                if self.process.poll() is None and measured_seconds() < deadline:
                    continue
                # Ended, or too slow: stopped either way (stop_command reaps an ended one)
                stop_command(process=self.process)
                self._end(reason='it never connected to stream its frames')
                return False
            connection.settimeout(None)
            self._connection = connection
            return True

    def _read_one_frame(self: Self) -> None:
        """Read the next frame into the one held, or note that OLD's stream ended."""
        header = self._receive(count=FRAME_HEADER.size)
        if header is None:
            self._end(reason='its stream ended')
            return
        frame_index, width, height = FRAME_HEADER.unpack(header)
        pixels = self._receive(count=width * height * BYTES_PER_PIXEL)
        if pixels is None:
            self._end(reason='its stream ended part way through a frame')
            return
        image = pygame.image.frombytes(pixels, (width, height), FRAME_PIXEL_FORMAT)
        image.set_alpha(round(FULLY_OPAQUE_ALPHA * self.alpha_percent / ONE_HUNDRED_PERCENT))
        self._held = HeldFrame(frame_index=frame_index, surface=image)
        self.frames_received += 1

    def _receive(self: Self, *, count: int) -> bytes | None:
        """Read exactly ``count`` bytes from the child.

        Returns:
            The bytes, or None when the stream ended first.

        """
        assert self._connection is not None
        received = bytearray()
        while len(received) < count:
            try:
                chunk = self._connection.recv(count - len(received))
            except OSError:
                return None
            if not chunk:
                return None
            received.extend(chunk)
        return bytes(received)

    def _end(self: Self, *, reason: str) -> None:
        """OLD has no more frames: wait for its child, and log how it ended.

        A child that streamed is logged at info level when it ended ``SUCCESS``; otherwise (it
        diverged, failed, or never streamed) its exit and its output are a warning.

        Args:
            reason: Why it has no more frames.

        """
        self._has_ended = True
        # Closed first: a child still streaming then fails its next write and stops itself
        self._close_sockets()
        assert self.process is not None
        with contextlib.suppress(TimeoutExpired):
            # A child whose stream ended is ending itself: its exit status says how
            self.process.wait(timeout=STOP_GRACE_SECONDS)
        stop_command(process=self.process)
        status = self.process.returncode
        if self._held is not None and status == ExitCode.SUCCESS:
            LOG.info('%s ended at frame %d (%s)', self.old_path, self._held.frame_index, reason)
            return
        # Started (_start) before anything ends
        assert self._output is not None
        self._output.seek(0)
        output = self._output.read()
        what = (
            'OLD could not be replayed'
            if self._held is None
            else f'OLD ended at frame {self._held.frame_index}'
        )
        LOG.warning(
            '%s: %s: %s (exit %s); its output:\n%s',
            what,
            self.old_path,
            reason,
            ExitCode.describe_status(status),
            output.rstrip(),
        )

    def _draw_label(self: Self, *, surface: pygame.Surface, text: str) -> None:
        """Draw a label at the top centre, on the debug overlay's backing, in its font.

        Args:
            surface: The presented frame.
            text: The label.

        """
        self.label = text
        if self._font is None:
            self._font = load_debug_font()
        text_surface = self._font.render(text, antialias=True, color=HUD_TEXT_COLOR)
        blit_text(
            surface=surface,
            text_surface=text_surface,
            position=((surface.get_width() - text_surface.get_width()) // 2, HUD_MARGIN),
        )
