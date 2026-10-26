"""Watched-replay controls: pause, step, speed, quit, the status bar and the start screen.

A watched replay (``--replay-trace`` without ``--headless``; glitchygames/replay/driver.py)
hands every real key press and release to ``ReplayControls``; none reaches the game. The keys
(plans/2026-10-19-gameplay-replay.md, 4.1):

- Space: start the replay from the start screen, then pause or resume it.
- ``.``: while paused, run one frame.
- ``,``: while paused at frame N, step back to frame N - 1 (``restart_request``). The driver
  restarts the replay, which rebuilds up to that frame unpresented and pauses there
  (glitchygames/replay/rebuild.py). Held, it repeats like ``.``, but each repeat only moves the
  target back one more frame: the restart happens once, after the release
  (``take_restart_request``), as each restart re-runs the replay from frame 0. Resuming drops a
  pending step back, and a ``.`` step while ``,`` is held makes the target count back from the
  frame the step reaches.
- Home: restart at frame 0 (paused after frame 0, ``FIRST_PAUSED_FRAME``).
- D: restart at the divergence frame, once the replay has found one (``divergence_frame``).
- ``]`` / ``[``: double or halve the playback speed, within ``MIN_SPEED`` and ``MAX_SPEED``.
- B: bookmark the current frame (``bookmarks``: the frame the status line shows, the one to be
  served next; kept sorted, once each). S asks the driver to save a copy of the recording with
  the bookmarks as ``breakpoint`` control events (``take_save_request``); a replay of the copy
  pauses at each (``pause_at_breakpoint``, glitchygames/replay/driver.py, rule 16).
- Esc: quit the replay (the driver ends it with ``end_reason = 'quit'``; no event is posted, as
  a code-posted QUIT would be an internal event the recording does not have).
- F3 / F4: the debug overlay's keys (``OVERLAY_KEYS``), handed to the overlay.

While a restarted replay rebuilds (``rebuild_target_frame``) only Esc and the debug overlay's
keys act (``REBUILD_KEYS``), and the presented frame is the rebuild's progress line on a cleared
display instead of the status bar.

The controls run on their own real-time cadence (``ControlCadence``, 60 ticks a second),
whatever the replay's speed and whether it is paused: the driver reads the keys and refreshes
the status line once per tick. Each key acts once per press: the operating system's key repeat
(games turn it on: PaddleSlap calls ``pygame.key.set_repeat(1)``) is ignored until the key is
released. Step keys repeat by themselves instead: after ``STEP_REPEAT_DELAY_SECONDS`` held, every
``STEP_REPEAT_INTERVAL_SECONDS``. The real time comes from ``glitchygames.clock.measured_seconds``
(never replayed), which is sound because the controls never change what is simulated.

The status bar, a transient message, the driver's banner and the start screen are drawn on the
presented frame after the debug overlay (``SceneManager._present_frame``), so they are never in
a screenshot or a trace.
"""

from __future__ import annotations

import bisect
import sys
from typing import TYPE_CHECKING, ClassVar, Self, override

import pygame

from glitchygames.debug.overlay import (
    DEBUG_FONT_PATH,
    NEXT_PANEL_KEY,
    OVERLAY_KEYS,
    TOGGLE_KEY,
    DebugOverlay,
    load_debug_font,
)
from glitchygames.debug.panels import HUD_LINE_HEIGHT, HUD_MARGIN, HUD_TEXT_COLOR, blit_text
from glitchygames.ui.message_screen import MessageScreen

if TYPE_CHECKING:
    from glitchygames.supervision import ControlEvent

# Status line: 'frame 6120 / 9800 · 1:42.0 · x1 · paused · diverged at 6120', where the x
# before the speed is a multiplication sign
STATUS_SEPARATOR = ' · '
SPEED_PREFIX = '\N{MULTIPLICATION SIGN}'
SECONDS_PER_MINUTE = 60
TENTHS_PER_SECOND = 10
# Each speed key doubles or halves the speed
SPEED_STEP_FACTOR = 2.0
BANNER_COLOR: tuple[int, int, int] = (255, 220, 0)

# Restarting a watched replay (step back, Home, D) starts a new process
# (glitchygames/replay/rebuild.py), which a browser page cannot
RESTARTS_AVAILABLE: bool = sys.platform != 'emscripten'
RESTARTS_UNAVAILABLE_MESSAGE = 'restarting needs a new process: not in a browser'

# The controls' real-time cadence (ControlCadence)
CONTROL_TICKS_PER_SECOND = 60
CONTROL_TICK_SECONDS = 1.0 / CONTROL_TICKS_PER_SECOND
# Step keys act on press, then repeat while held: after this delay, at this interval (10 a second)
STEP_KEYS: frozenset[int] = frozenset({pygame.K_PERIOD, pygame.K_COMMA})
STEP_REPEAT_DELAY_SECONDS = 0.3
STEP_REPEAT_INTERVAL_SECONDS = 0.1
# Frame 0 always runs before a watched replay holds (the start screen's rule, and a restart's),
# so its picture is the first there is: the earliest frame a replay pauses at
FIRST_PAUSED_FRAME = 1
# Step back, Home and jump to the divergence: each asks for a restart (restart_request)
RESTART_KEYS: frozenset[int] = frozenset({pygame.K_COMMA, pygame.K_HOME, pygame.K_d})
# B bookmarks the current frame, S saves the bookmarks into a copy of the recording
BOOKMARK_KEYS: frozenset[int] = frozenset({pygame.K_b, pygame.K_s})
# A breakpoint control event's optional label (shown when it pauses the replay)
BREAKPOINT_LABEL_FIELD = 'label'
# The keys that act while a restarted replay rebuilds
REBUILD_KEYS: frozenset[int] = OVERLAY_KEYS | {pygame.K_ESCAPE}
REBUILD_BACKGROUND_COLOR: tuple[int, int, int] = (0, 0, 0)


def format_replay_time(*, seconds: float) -> str:
    """Format a replay time as minutes, seconds and tenths.

    Args:
        seconds: The frame clock (non-negative).

    Returns:
        For example ``1:42.0`` for 102 seconds, ``0:05.3`` for 5.3 (rounded to the tenth first,
        so 59.96 seconds reads ``1:00.0``).

    """
    total_tenths = round(seconds * TENTHS_PER_SECOND)
    minutes, tenths = divmod(total_tenths, SECONDS_PER_MINUTE * TENTHS_PER_SECOND)
    whole_seconds, tenth = divmod(tenths, TENTHS_PER_SECOND)
    return f'{minutes}:{whole_seconds:02d}.{tenth}'


def rebuild_progress_text(*, frame_index: int, target_frame: int) -> str:
    """Describe a rebuild's progress (printed and presented while it runs).

    Args:
        frame_index: The frame the rebuild has reached.
        target_frame: The frame it pauses at.

    Returns:
        For example ``Rebuilding: frame 60 / 130``.

    """
    return f'Rebuilding: frame {frame_index} / {target_frame}'


def overlay_key_label(*, key: int) -> str:
    """Name a debug overlay key as the keyboard shows it.

    Args:
        key: A pygame key constant.

    Returns:
        For example ``F3``.

    """
    return pygame.key.name(key).upper()


class ReplayStartScreen(MessageScreen):
    """The watched replay's start screen: the pause screen's drawing, its own message and look.

    A dark blue dim instead of the pause screen's black, the debug overlay's Vera Sans in yellow
    instead of pygame's default font in white, and a hint line naming the debug overlay's keys
    (read from glitchygames/debug/overlay.py).
    """

    MESSAGE = 'Press Spacebar to Start Game Replay'
    MESSAGE_FONT_PATH = DEBUG_FONT_PATH
    MESSAGE_FONT_SIZE = 28
    MESSAGE_COLOR = BANNER_COLOR
    HINT_FONT_PATH = DEBUG_FONT_PATH
    HINT_FONT_SIZE = 15
    HINT_COLOR = HUD_TEXT_COLOR
    HINT_GAP = 12
    DIM_COLOR = (0, 12, 40)
    DIM_ALPHA = 176

    @override
    def hint_text(self: Self) -> str:
        """Name the debug overlay's keys.

        Returns:
            For example ``F3: debug overlay   F4: next panel``.

        """
        return (
            f'{overlay_key_label(key=TOGGLE_KEY)}: debug overlay   '
            f'{overlay_key_label(key=NEXT_PANEL_KEY)}: next panel'
        )


class ControlCadence:
    """The viewer controls' own real-time tick, ``CONTROL_TICKS_PER_SECOND`` a second.

    Independent of the replay's speed and pauses: the replayed frames follow the recording, the
    controls follow real time (``glitchygames.clock.measured_seconds``, never replayed; the
    controls never change what is simulated). A tick that falls more than one period behind
    (a long frame) is re-anchored to now instead of being caught up tick after tick.
    """

    def __init__(self: Self) -> None:
        """Start with a tick due at once."""
        self._next_tick_seconds: float | None = None

    def tick_is_due(self: Self, *, now: float) -> bool:
        """Report whether a tick is due at ``now``, and if so schedule the next one.

        Args:
            now: The measured time.

        Returns:
            True when the controls should run a tick now.

        """
        if self._next_tick_seconds is not None and now < self._next_tick_seconds:
            return False
        scheduled = (
            now if self._next_tick_seconds is None else self._next_tick_seconds
        ) + CONTROL_TICK_SECONDS
        self._next_tick_seconds = scheduled if scheduled > now else now + CONTROL_TICK_SECONDS
        return True

    def next_tick_seconds(self: Self, *, now: float) -> float:
        """Return when the next tick is due.

        Args:
            now: The measured time (the answer before any tick has run).

        Returns:
            The measured time of the next tick.

        """
        return now if self._next_tick_seconds is None else self._next_tick_seconds


class ReplayControls:
    """The watched replay's control state, key handling and status bar (module docstring).

    Attributes:
        MIN_SPEED: The slowest playback speed.
        MAX_SPEED: The fastest playback speed.
        MESSAGE_CONTROL_TICKS: How many control ticks a ``show_message`` text is shown.
        total_frames: How many frames the recording holds.
        paused: True while the replay holds between frames.
        speed: The playback speed (1.0 plays at the recorded pace).
        step_requested: True when ``.`` asked for one frame while paused (``take_step``).
        quit_requested: True once Esc was pressed.
        awaiting_start: True while the start screen waits for Space.
        banner: A line shown above the status bar (the driver's divergence or end notice), or
            None.
        debug_overlay: The debug overlay F3 and F4 act on: its own until the engine hands it
            the scene manager's (``GameEngine.__init__``).
        current_frame: The recording's frame index to be served next (the driver keeps it).
        divergence_frame: The frame the replay diverged at once it has (the driver sets it), or
            None.
        restart_request: The frame ``,``, Home or D asked to restart at, or None
            (``take_restart_request``).
        rebuild_target_frame: The frame a restarted replay is rebuilding up to, or None once
            it is there (the driver keeps it).
        bookmarks: The frames B marked, sorted, each once (in ``current_frame``'s numbering:
            a bookmark N pauses a replay of the saved copy with frame N next).
        save_requested: True when S asked for a saved copy (``take_save_request``).

    """

    MIN_SPEED: ClassVar[float] = 0.25
    MAX_SPEED: ClassVar[float] = 8.0
    MESSAGE_CONTROL_TICKS: ClassVar[int] = 120

    def __init__(self: Self, *, total_frames: int, awaiting_start: bool = False) -> None:
        """Start unpaused at speed 1.

        Args:
            total_frames: How many frames the recording holds (for the status line).
            awaiting_start: True to show the start screen until Space is pressed.

        """
        self.total_frames = total_frames
        self.paused = False
        self.speed = 1.0
        self.step_requested = False
        self.quit_requested = False
        self.awaiting_start = awaiting_start
        self.banner: str | None = None
        self.debug_overlay = DebugOverlay()
        self.current_frame = 0
        self.divergence_frame: int | None = None
        self.restart_request: int | None = None
        self.rebuild_target_frame: int | None = None
        self.bookmarks: list[int] = []
        self.save_requested = False
        self._message: str | None = None
        self._message_ticks_left = 0
        # Each key held down -> when it repeats next (step keys) or None (acts once per press)
        self._held_keys: dict[int, float | None] = {}
        self._status_line = ''
        self._shown_message: str | None = None
        # The lines last rendered, with their surfaces (rendered again only when they change)
        self._rendered_lines: list[tuple[str, tuple[int, int, int], pygame.Surface]] = []
        self._start_screen = ReplayStartScreen()
        self._font: pygame.font.Font | None = None

    def press_key(self: Self, *, key: int, now: float) -> None:
        """Take a real key press: act once per press (a key already held is a repeat, ignored).

        Step keys (``STEP_KEYS``) also repeat by themselves while held: after
        ``STEP_REPEAT_DELAY_SECONDS``, every ``STEP_REPEAT_INTERVAL_SECONDS``
        (``repeat_held_keys``).

        Args:
            key: The pressed key.
            now: The measured time of the viewer tick reading it.

        """
        if key in self._held_keys:
            return
        self._held_keys[key] = now + STEP_REPEAT_DELAY_SECONDS if key in STEP_KEYS else None
        self.handle_key(key=key)

    def note_key_already_down(self: Self, *, key: int) -> None:
        """Count a key held before the replay could read it as held, without acting on it.

        Its operating-system repeats are then not new presses; it acts again after its release.

        Args:
            key: The key (its press was queued before the replay's first drain).

        """
        self._held_keys.setdefault(key, None)

    def release_key(self: Self, *, key: int) -> None:
        """Take a real key release: the next press of the key acts again.

        Args:
            key: The released key.

        """
        self._held_keys.pop(key, None)

    def repeat_held_keys(self: Self, *, now: float) -> None:
        """Repeat each held step key whose repeat is due (once per control tick at most).

        Args:
            now: The measured time of the control tick.

        """
        for key, repeat_seconds in self._held_keys.items():
            if repeat_seconds is not None and now >= repeat_seconds:
                self._held_keys[key] = max(repeat_seconds + STEP_REPEAT_INTERVAL_SECONDS, now)
                self.handle_key(key=key)

    def handle_key(self: Self, *, key: int) -> None:
        """Act on a key (module docstring); other keys do nothing.

        Args:
            key: The key (a pygame key constant).

        """
        if self.rebuild_target_frame is not None and key not in REBUILD_KEYS:
            return
        if key in OVERLAY_KEYS:
            self.debug_overlay.handle_key(key=key)
        elif key == pygame.K_ESCAPE:
            self.quit_requested = True
        elif key == pygame.K_SPACE:
            self._handle_space()
        elif key == pygame.K_PERIOD and self.paused:
            self.step_requested = True
            # A held , counts back from the frame the step reaches, not the one before it
            self.restart_request = None
        elif key in RESTART_KEYS:
            self._handle_restart_key(key=key)
        elif key == pygame.K_RIGHTBRACKET:
            self.speed = min(self.speed * SPEED_STEP_FACTOR, self.MAX_SPEED)
        elif key == pygame.K_LEFTBRACKET:
            self.speed = max(self.speed / SPEED_STEP_FACTOR, self.MIN_SPEED)
        elif key in BOOKMARK_KEYS:
            self._handle_bookmark_key(key=key)

    def _handle_bookmark_key(self: Self, *, key: int) -> None:
        """Act on B (bookmark the current frame) or S (ask for a saved copy).

        A bookmark is at least ``FIRST_PAUSED_FRAME``: frame 0 always runs.

        Args:
            key: One of ``BOOKMARK_KEYS``.

        """
        if key == pygame.K_s:
            self.save_requested = True
            return
        frame_index = max(self.current_frame, FIRST_PAUSED_FRAME)
        if frame_index in self.bookmarks:
            self.show_message(text=f'frame {frame_index} already bookmarked')
            return
        bisect.insort(self.bookmarks, frame_index)
        self.show_message(text=f'bookmarked frame {frame_index}')

    def take_save_request(self: Self) -> bool:
        """Consume the request S made for a saved copy.

        Returns:
            True once per S press.

        """
        save_requested = self.save_requested
        self.save_requested = False
        return save_requested

    def pause_at_breakpoint(self: Self, control_event: ControlEvent) -> None:
        """Pause at a recorded ``breakpoint`` control event, unless a restart is rebuilding.

        A ``SceneManager`` control event handler (``Callable[[ControlEvent], None]``, so the
        event is positional): the engine registers it for a watched replay. It runs at the
        frame's supervisor slot, so the replay pauses once that frame ends. A rebuild runs past
        breakpoints to its own pause frame.

        Args:
            control_event: The breakpoint (its ``label``, if any, is shown).

        """
        if self.rebuild_target_frame is not None:
            return
        self.paused = True
        self.step_requested = False
        label = control_event.data.get(BREAKPOINT_LABEL_FIELD)
        self.show_message(text='breakpoint' if label is None else f'breakpoint: {label}')

    def _handle_space(self: Self) -> None:
        """Start the replay from the start screen, else pause or resume it."""
        if self.awaiting_start:
            self.awaiting_start = False
            return
        self.paused = not self.paused
        self.step_requested = False
        if not self.paused:
            # Resumed, the frame a step back counted from is gone
            self.restart_request = None

    def _handle_restart_key(self: Self, *, key: int) -> None:
        """Act on ``,`` (while paused), Home or D (once the replay diverged).

        Args:
            key: One of ``RESTART_KEYS``.

        """
        if not RESTARTS_AVAILABLE:
            self.show_message(text=RESTARTS_UNAVAILABLE_MESSAGE)
            return
        if key == pygame.K_COMMA:
            if self.paused:
                self._step_back()
        elif key == pygame.K_HOME:
            self._request_restart(frame_index=0)
        elif self.divergence_frame is not None:
            self._request_restart(frame_index=self.divergence_frame)

    def _step_back(self: Self) -> None:
        """Move the restart target one frame back from it (or from the current frame)."""
        target_frame = self.current_frame if self.restart_request is None else self.restart_request
        if target_frame <= FIRST_PAUSED_FRAME:
            return
        self.restart_request = target_frame - 1
        self.show_message(text=f'back to frame {self.restart_request}')

    def _request_restart(self: Self, *, frame_index: int) -> None:
        """Ask to restart at ``frame_index``, unless that rebuilds the frame already shown.

        Args:
            frame_index: The frame to pause at (one before ``FIRST_PAUSED_FRAME`` pauses there).

        """
        if max(frame_index, FIRST_PAUSED_FRAME) != self.current_frame:
            self.restart_request = frame_index

    def take_restart_request(self: Self) -> int | None:
        """Consume the restart request, unless ``,`` is still held (it moves the target back).

        Returns:
            The frame to restart at, or None (no request, or ``,`` held).

        """
        if self.restart_request is None or pygame.K_COMMA in self._held_keys:
            return None
        frame_index = self.restart_request
        self.restart_request = None
        return frame_index

    def show_message(self: Self, *, text: str) -> None:
        """Show ``text`` above the status bar for ``MESSAGE_CONTROL_TICKS`` control ticks.

        Args:
            text: The message (it replaces any message still shown).

        """
        self._message = text
        self._message_ticks_left = self.MESSAGE_CONTROL_TICKS

    def message_for_control_tick(self: Self) -> str | None:
        """Return the message to show until the next control tick, counting this tick.

        Returns:
            The message while it has ticks left, else None.

        """
        if self._message_ticks_left <= 0:
            return None
        self._message_ticks_left -= 1
        return self._message

    def take_step(self: Self) -> bool:
        """Consume one pending step.

        Returns:
            True when paused with a step requested (now consumed), else False.

        """
        if not (self.paused and self.step_requested):
            return False
        self.step_requested = False
        return True

    def status_line(
        self: Self,
        *,
        frame_number: int,
        seconds: float,
        divergence_frame: int | None,
        effective_speed: float | None = None,
    ) -> str:
        """Describe where the replay is.

        Args:
            frame_number: The recording's frame index to be served next.
            seconds: The frame clock.
            divergence_frame: The frame the replay diverged at, or None.
            effective_speed: The speed the replay really runs at when it cannot keep up with
                ``speed`` (the viewer's ``effective_speed`` while behind), or None.

        Returns:
            For example ``frame 6120 / 9800 · 1:42.0 · x1 · paused · diverged at 6120`` (the x
            is ``SPEED_PREFIX``, a multiplication sign; ``paused`` and ``diverged at`` only
            when they apply).

        """
        parts = [
            f'frame {frame_number} / {self.total_frames}',
            format_replay_time(seconds=seconds),
            f'{SPEED_PREFIX}{self.speed:g}',
        ]
        if effective_speed is not None:
            parts.append(f"can't keep up: {SPEED_PREFIX}{effective_speed:.2g}")
        if self.paused:
            parts.append('paused')
        if divergence_frame is not None:
            parts.append(f'diverged at {divergence_frame}')
        return STATUS_SEPARATOR.join(parts)

    def update_status(self: Self, *, status_line: str) -> None:
        """Take the status line for the control tick, and count the tick for the message.

        Args:
            status_line: The line ``status_line`` built for this tick.

        """
        self._status_line = status_line
        self._shown_message = self.message_for_control_tick()

    def draw(self: Self, *, surface: pygame.Surface) -> None:
        """Draw the start screen (while awaiting start), then the status bar and its notices.

        Drawn on every presented frame from what the last control tick set
        (``update_status``); text is rendered again only when it changed. The status line sits
        at the bottom centre (the debug overlay's collision legend and frame-time graph take
        the bottom corners), the message above it and the banner above that, each on the debug
        overlay's translucent backing in its font.

        Args:
            surface: The presented frame to draw onto.

        """
        if self.rebuild_target_frame is not None:
            self._draw_rebuild_screen(surface=surface, target_frame=self.rebuild_target_frame)
            return
        if self.awaiting_start:
            self._start_screen.draw(surface=surface)
        lines = [(self._status_line, HUD_TEXT_COLOR)]
        if self._shown_message is not None:
            lines.append((self._shown_message, HUD_TEXT_COLOR))
        if self.banner is not None:
            lines.append((self.banner, BANNER_COLOR))
        if [(text, color) for text, color, _ in self._rendered_lines] != lines:
            font = self._loaded_font()
            self._rendered_lines = [
                (text, color, font.render(text, antialias=True, color=color))
                for text, color in lines
            ]
        line_top = surface.get_height() - HUD_MARGIN
        for _, _, text_surface in self._rendered_lines:
            line_top -= HUD_LINE_HEIGHT
            line_left = (surface.get_width() - text_surface.get_width()) // 2
            blit_text(surface=surface, text_surface=text_surface, position=(line_left, line_top))

    def _draw_rebuild_screen(self: Self, *, surface: pygame.Surface, target_frame: int) -> None:
        """Draw a rebuild's progress line, centred on the cleared display (instead of the bar).

        Args:
            surface: The presented frame.
            target_frame: The frame the rebuild pauses at.

        """
        surface.fill(REBUILD_BACKGROUND_COLOR)
        text_surface = self._loaded_font().render(
            rebuild_progress_text(frame_index=self.current_frame, target_frame=target_frame),
            antialias=True,
            color=HUD_TEXT_COLOR,
        )
        surface.blit(
            text_surface,
            (
                (surface.get_width() - text_surface.get_width()) // 2,
                (surface.get_height() - text_surface.get_height()) // 2,
            ),
        )

    def _loaded_font(self: Self) -> pygame.font.Font:
        """Return the debug overlay's font, loaded on first use.

        Returns:
            The font.

        """
        if self._font is None:
            self._font = load_debug_font()
        return self._font
