"""Debug overlay state: visibility, panel selection and a rolling frame-time history."""

from __future__ import annotations

import collections
import enum
import math

PHYSICS_ARROW_SECONDS = 0.1
PHYSICS_ARROW_MAXIMUM_PIXELS = 80
PERFORMANCE_WINDOW_SECONDS = 5.0
GRAPH_WINDOW_SECONDS = 2.0
FRAME_HISTORY_LENGTH = 5000  # 5 s at up to 1000 FPS
ONE_PERCENT = 0.01
# Summing frame times in floating point can land a hair above a window length that is
# exactly reached (for example 500 frames of 0.007 s sum to 3.500000000000011 s). Without
# this tolerance the boundary frame would be dropped, so the window would depend on rounding.
WINDOW_TOLERANCE_SECONDS = 1e-9


class DebugPanel(enum.Enum):
    """Which panels the overlay draws; F4 cycles in declaration order.

    Attributes:
        ALL (str): Every panel is drawn.
        COLLISION (str): Collision hitbox outlines.
        PHYSICS (str): Velocity arrows and physics state.
        CAMERA (str): Camera position and bounds.
        PERFORMANCE (str): FPS readout, 1% low and frame-time graph.

    """

    ALL = 'all'
    COLLISION = 'collision'
    PHYSICS = 'physics'
    CAMERA = 'camera'
    PERFORMANCE = 'performance'


class DebugOverlay:
    """State for the engine's debug overlay (drawing lives in the panels module).

    The overlay is read-only: it never changes positions, velocities, camera state or
    sprite dirty flags.
    """

    def __init__(self, *, visible: bool = False) -> None:
        """Create the overlay with an empty frame history.

        Args:
            visible (bool): Whether the overlay starts drawn. Defaults to hidden.

        """
        self.is_visible = visible
        self.panel = DebugPanel.ALL
        self._frame_times: collections.deque[float] = collections.deque(
            maxlen=FRAME_HISTORY_LENGTH,
        )

    def toggle(self) -> None:
        """Show the overlay if it is hidden, hide it if it is shown."""
        self.is_visible = not self.is_visible

    def cycle_panel(self) -> None:
        """Advance to the next panel in declaration order, wrapping after the last one."""
        panels = list(DebugPanel)
        self.panel = panels[(panels.index(self.panel) + 1) % len(panels)]

    def shows(self, panel: DebugPanel) -> bool:
        """Report whether a panel should be drawn.

        Args:
            panel (DebugPanel): The panel to check.

        Returns:
            bool: True when the selected panel is ALL or the same as `panel`.

        """
        return self.panel in {DebugPanel.ALL, panel}

    def record_frame(self, *, frame_seconds: float) -> None:
        """Append one frame's duration to the history.

        Non-positive durations are ignored, since they cannot produce a meaningful FPS.

        Args:
            frame_seconds (float): How long the frame took, in seconds.

        """
        if frame_seconds > 0.0:
            self._frame_times.append(frame_seconds)

    def frame_times(self) -> list[float]:
        """Return the recorded frame durations.

        Returns:
            list[float]: Frame durations in seconds, oldest first.

        """
        return list(self._frame_times)

    def current_fps(self) -> float | None:
        """Return the FPS implied by the newest frame.

        Returns:
            float | None: Frames per second, or None when no frame has been recorded.

        """
        return 1.0 / self._frame_times[-1] if self._frame_times else None

    def _window(self, window_seconds: float) -> list[float]:
        """Return the newest frames whose durations fit inside a time window.

        Frames are walked newest first, accumulating their durations. A frame is included
        while the running total stays within `window_seconds` (plus a rounding tolerance),
        and the walk stops at the first frame that would exceed it.

        Args:
            window_seconds (float): The window length in seconds.

        Returns:
            list[float]: The frames inside the window, oldest first.

        """
        selected_frame_times: list[float] = []
        running_total_seconds = 0.0
        for frame_seconds in reversed(self._frame_times):
            if running_total_seconds + frame_seconds > window_seconds + WINDOW_TOLERANCE_SECONDS:
                break
            running_total_seconds += frame_seconds
            selected_frame_times.append(frame_seconds)
        selected_frame_times.reverse()
        return selected_frame_times

    def one_percent_low_fps(
        self,
        *,
        window_seconds: float = PERFORMANCE_WINDOW_SECONDS,
    ) -> float | None:
        """Return the 1% low FPS over the newest window of frames.

        Takes the window from `_window`, then the slowest `max(1, ceil(0.01 * n))` of its
        `n` frames, and returns the mean of their FPS (1 / frame time).

        Args:
            window_seconds (float): The window length in seconds. Defaults to
                PERFORMANCE_WINDOW_SECONDS.

        Returns:
            float | None: The 1% low in frames per second, or None when the window is empty.

        """
        window_frame_times = self._window(window_seconds)
        if not window_frame_times:
            return None
        slowest_count = max(1, math.ceil(ONE_PERCENT * len(window_frame_times)))
        slowest_frame_times = sorted(window_frame_times, reverse=True)[:slowest_count]
        return sum(1.0 / frame_seconds for frame_seconds in slowest_frame_times) / slowest_count

    def graph_frame_times(self, *, window_seconds: float = GRAPH_WINDOW_SECONDS) -> list[float]:
        """Return the frame durations to plot in the frame-time graph.

        Args:
            window_seconds (float): The window length in seconds. Defaults to
                GRAPH_WINDOW_SECONDS.

        Returns:
            list[float]: Frame durations inside the window, oldest first.

        """
        return self._window(window_seconds)
