"""Tests for the debug overlay state, protocols and rolling frame-time history."""

import pygame
import pytest

from glitchygames.debug import DebugDrawable, DebugOverlay, DebugPanel, HasPhysicsBody
from glitchygames.debug.overlay import NEXT_PANEL_KEY, OVERLAY_KEYS, TOGGLE_KEY


class TestToggleAndCycle:
    """Visibility toggling and panel cycling."""

    def test_starts_hidden_by_default_and_toggles(self):
        """The overlay starts hidden and F3 toggles it visible."""
        overlay = DebugOverlay()
        assert overlay.is_visible is False
        overlay.toggle()
        assert overlay.is_visible is True

    def test_cycle_order_wraps(self):
        """F4 cycles through the panels in declaration order and wraps to ALL."""
        overlay = DebugOverlay(visible=True)
        seen_panels = []
        for _ in range(6):
            seen_panels.append(overlay.panel)
            overlay.cycle_panel()
        assert seen_panels == [
            DebugPanel.ALL,
            DebugPanel.COLLISION,
            DebugPanel.PHYSICS,
            DebugPanel.CAMERA,
            DebugPanel.PERFORMANCE,
            DebugPanel.ALL,
        ]

    def test_handle_key_toggles_cycles_and_ignores_other_keys(self):
        """F3 toggles, F4 cycles, any other key changes nothing (a watched replay's route)."""
        overlay = DebugOverlay()
        overlay.handle_key(key=TOGGLE_KEY)
        overlay.handle_key(key=NEXT_PANEL_KEY)
        overlay.handle_key(key=pygame.K_a)
        assert (overlay.is_visible, overlay.panel) == (True, DebugPanel.COLLISION)
        assert {pygame.K_F3, pygame.K_F4} == OVERLAY_KEYS

    def test_shows(self):
        """ALL shows every panel; a single panel shows only itself."""
        overlay = DebugOverlay()
        assert overlay.shows(DebugPanel.PHYSICS)
        overlay.cycle_panel()  # COLLISION
        assert overlay.shows(DebugPanel.COLLISION)
        assert not overlay.shows(DebugPanel.PHYSICS)


class TestFrameHistory:
    """Rolling frame-time history and the FPS statistics derived from it."""

    def test_current_fps_from_last_frame(self):
        """Current FPS is the reciprocal of the newest frame time."""
        overlay = DebugOverlay()
        assert overlay.current_fps() is None
        overlay.record_frame(frame_seconds=1 / 50)
        assert overlay.current_fps() == pytest.approx(50.0)

    def test_one_percent_low_uses_window_and_slowest_frames(self):
        """The 1% low uses only frames inside the window and averages the slowest ones."""
        overlay = DebugOverlay()
        # Older than the 5 s window once followed by 5 s of frames.
        overlay.record_frame(frame_seconds=1.0)
        for _ in range(500):
            overlay.record_frame(frame_seconds=0.01)  # 5.0 s of 100 FPS frames
        # The window keeps the newest frames totalling <= 5 s: the 1.0 s frame is excluded.
        assert overlay.one_percent_low_fps() == pytest.approx(100.0)
        overlay.record_frame(frame_seconds=0.05)  # one slow 20 FPS frame inside the window
        # Window = the 0.05 s frame + 495 frames of 0.01 s (4.95 s) -> n = 496, ceil(4.96) = 5.
        # Slowest five: one 20 FPS frame and four 100 FPS frames.
        assert overlay.one_percent_low_fps() == pytest.approx((20 + 4 * 100) / 5)

    def test_window_boundary_is_inclusive_despite_float_error(self):
        """A window that sums to exactly its length keeps every frame in it.

        Summing 500 frames of 0.007 s in floating point gives 3.500000000000011 s, a hair
        above the 3.5 s window. The tolerance keeps the boundary frame included.
        """
        overlay = DebugOverlay()
        for _ in range(500):
            overlay.record_frame(frame_seconds=0.007)
        assert len(overlay.graph_frame_times(window_seconds=3.5)) == 500

    def test_graph_window(self):
        """The graph shows the newest two seconds of frame times, oldest first."""
        overlay = DebugOverlay()
        for _ in range(300):
            overlay.record_frame(frame_seconds=0.01)
        assert len(overlay.graph_frame_times()) == 200  # 2 s of 10 ms frames

    def test_frame_times_are_oldest_first(self):
        """frame_times() returns recorded frames in the order they were recorded."""
        overlay = DebugOverlay()
        overlay.record_frame(frame_seconds=0.01)
        overlay.record_frame(frame_seconds=0.02)
        assert overlay.frame_times() == [0.01, 0.02]

    def test_one_percent_low_is_none_without_frames(self):
        """With no recorded frames there is no 1% low."""
        assert DebugOverlay().one_percent_low_fps() is None

    def test_zero_or_negative_frame_times_ignored(self):
        """Non-positive frame times are discarded rather than recorded."""
        overlay = DebugOverlay()
        overlay.record_frame(frame_seconds=0.0)
        overlay.record_frame(frame_seconds=-1.0)
        assert overlay.frame_times() == []


class TestProtocols:
    """Structural protocols the overlay recognises without inheritance."""

    def test_has_physics_body(self):
        """An object with a `physics` attribute carrying the body fields matches."""

        class Body:
            velocity_x = 1.0
            velocity_y = 2.0
            world_x = 0.0
            world_y = 0.0
            on_ground = True

        class Thing:
            physics = Body()

        assert isinstance(Thing(), HasPhysicsBody)
        assert not isinstance(object(), HasPhysicsBody)

    def test_debug_drawable(self):
        """An object with a `debug_draw` method matches."""

        class Drawer:
            def debug_draw(self, surface, camera):
                """Do nothing; only the method's presence matters here."""

        assert isinstance(Drawer(), DebugDrawable)
