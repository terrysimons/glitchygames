"""Watched-replay controls: pause, step, speed, quit, the status bar and the start screen.

A watched replay (``--replay-trace`` without ``--headless``; glitchygames/replay/driver.py)
hands every real key press to ``ReplayControls.handle_key`` (the debug overlay's keys go to the
overlay instead); none reaches the game. The keys (plans/2026-10-19-gameplay-replay.md, 4.1):

- Space: start the replay from the start screen, then pause or resume it.
- ``.``: while paused, run one frame.
- ``]`` / ``[``: double or halve the playback speed, within ``MIN_SPEED`` and ``MAX_SPEED``.
- Esc: quit the replay (the driver ends it with ``end_reason = 'quit'``; no event is posted, as
  a code-posted QUIT would be an internal event the recording does not have).

The status bar, a transient message, the driver's banner and the start screen are drawn on the
presented frame after the debug overlay (``SceneManager._present_frame``), so they are never in
a screenshot or a trace. Nothing here reads a clock: a message lasts a number of presented
frames, because every clock follows the frame clock in a replay, which stands still while
paused.
"""

from __future__ import annotations

from typing import ClassVar, Self, override

import pygame

from glitchygames.debug.overlay import (
    DEBUG_FONT_PATH,
    NEXT_PANEL_KEY,
    TOGGLE_KEY,
    load_debug_font,
)
from glitchygames.debug.panels import HUD_LINE_HEIGHT, HUD_MARGIN, HUD_TEXT_COLOR, blit_text
from glitchygames.ui.message_screen import MessageScreen

# Status line: 'frame 6120 / 9800 · 1:42.0 · x1 · paused · diverged at 6120', where the x
# before the speed is a multiplication sign
STATUS_SEPARATOR = ' · '
SPEED_PREFIX = '\N{MULTIPLICATION SIGN}'
SECONDS_PER_MINUTE = 60
TENTHS_PER_SECOND = 10
# Each speed key doubles or halves the speed
SPEED_STEP_FACTOR = 2.0
BANNER_COLOR: tuple[int, int, int] = (255, 220, 0)


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


class ReplayControls:
    """The watched replay's control state, key handling and status bar (module docstring).

    Attributes:
        MIN_SPEED: The slowest playback speed.
        MAX_SPEED: The fastest playback speed.
        MESSAGE_PRESENTED_FRAMES: How many presented frames a ``show_message`` text is shown.
        total_frames: How many frames the recording holds.
        paused: True while the replay holds between frames.
        speed: The playback speed (1.0 plays at the recorded pace).
        step_requested: True when ``.`` asked for one frame while paused (``take_step``).
        quit_requested: True once Esc was pressed.
        awaiting_start: True while the start screen waits for Space (before frame 0).
        banner: A line shown above the status bar (the driver's divergence or end notice), or
            None.

    """

    MIN_SPEED: ClassVar[float] = 0.25
    MAX_SPEED: ClassVar[float] = 8.0
    MESSAGE_PRESENTED_FRAMES: ClassVar[int] = 120

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
        self._message: str | None = None
        self._message_frames_left = 0
        self._start_screen = ReplayStartScreen()
        self._font: pygame.font.Font | None = None

    def handle_key(self: Self, *, key: int) -> None:
        """Act on a real key press (module docstring); other keys do nothing.

        Args:
            key: The pressed key (a pygame key constant).

        """
        if key == pygame.K_ESCAPE:
            self.quit_requested = True
        elif key == pygame.K_SPACE and self.awaiting_start:
            self.awaiting_start = False
        elif key == pygame.K_SPACE:
            self.paused = not self.paused
            self.step_requested = False
        elif key == pygame.K_PERIOD and self.paused:
            self.step_requested = True
        elif key == pygame.K_RIGHTBRACKET:
            self.speed = min(self.speed * SPEED_STEP_FACTOR, self.MAX_SPEED)
        elif key == pygame.K_LEFTBRACKET:
            self.speed = max(self.speed / SPEED_STEP_FACTOR, self.MIN_SPEED)

    def show_message(self: Self, *, text: str) -> None:
        """Show ``text`` above the status bar for ``MESSAGE_PRESENTED_FRAMES`` presented frames.

        Args:
            text: The message (it replaces any message still shown).

        """
        self._message = text
        self._message_frames_left = self.MESSAGE_PRESENTED_FRAMES

    def message_for_presented_frame(self: Self) -> str | None:
        """Return the message to draw on the frame being presented, counting that frame.

        Returns:
            The message while it has presented frames left, else None.

        """
        if self._message_frames_left <= 0:
            return None
        self._message_frames_left -= 1
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
        self: Self, *, frame_number: int, seconds: float, divergence_frame: int | None
    ) -> str:
        """Describe where the replay is.

        Args:
            frame_number: The recording's frame index to be served next.
            seconds: The frame clock.
            divergence_frame: The frame the replay diverged at, or None.

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
        if self.paused:
            parts.append('paused')
        if divergence_frame is not None:
            parts.append(f'diverged at {divergence_frame}')
        return STATUS_SEPARATOR.join(parts)

    def draw(self: Self, *, surface: pygame.Surface, status_line: str) -> None:
        """Draw the start screen (while awaiting start), then the status bar and its notices.

        The status line sits at the bottom centre (the debug overlay's collision legend and
        frame-time graph take the bottom corners), a transient message above it (counted as one
        presented frame) and the banner above that, each on the debug overlay's translucent
        backing in its font.

        Args:
            surface: The presented frame to draw onto.
            status_line: The line ``status_line`` built for this frame.

        """
        if self.awaiting_start:
            self._start_screen.draw(surface=surface)
        if self._font is None:
            self._font = load_debug_font()
        lines = [(status_line, HUD_TEXT_COLOR)]
        message = self.message_for_presented_frame()
        if message is not None:
            lines.append((message, HUD_TEXT_COLOR))
        if self.banner is not None:
            lines.append((self.banner, BANNER_COLOR))
        line_top = surface.get_height() - HUD_MARGIN
        for text, color in lines:
            line_top -= HUD_LINE_HEIGHT
            text_surface = self._font.render(text, antialias=True, color=color)
            line_left = (surface.get_width() - text_surface.get_width()) // 2
            blit_text(surface=surface, text_surface=text_surface, position=(line_left, line_top))
