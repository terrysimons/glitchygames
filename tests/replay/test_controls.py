"""Watched-replay controls (glitchygames/replay/controls.py)."""

from __future__ import annotations

import pygame
import pytest

from glitchygames.debug.overlay import NEXT_PANEL_KEY, TOGGLE_KEY
from glitchygames.replay.controls import (
    ReplayControls,
    ReplayStartScreen,
    format_replay_time,
    overlay_key_label,
)
from glitchygames.ui.message_screen import MessageScreen

# A surface the size of the recording tests' window (tests/world/test_gameplay_recording.py)
SURFACE_SIZE = (320, 240)


@pytest.fixture
def initialized_pygame():
    """Start pygame (fonts and the key names need it); left running for later tests."""
    pygame.init()


def test_space_toggles_pause():
    """Space pauses, and Space again resumes."""
    controls = ReplayControls(total_frames=100)
    controls.handle_key(key=pygame.K_SPACE)
    assert controls.paused
    controls.handle_key(key=pygame.K_SPACE)
    assert not controls.paused


def test_step_only_while_paused_and_consumed_once():
    """A step (.) is taken only while paused, and only once."""
    controls = ReplayControls(total_frames=100)
    controls.handle_key(key=pygame.K_PERIOD)
    assert not controls.take_step()
    controls.handle_key(key=pygame.K_SPACE)
    controls.handle_key(key=pygame.K_PERIOD)
    assert controls.take_step()
    assert not controls.take_step()


def test_resuming_drops_a_pending_step():
    """A step asked for before resuming is not taken after the next pause."""
    controls = ReplayControls(total_frames=100)
    controls.handle_key(key=pygame.K_SPACE)
    controls.handle_key(key=pygame.K_PERIOD)
    controls.handle_key(key=pygame.K_SPACE)
    controls.handle_key(key=pygame.K_SPACE)
    assert not controls.take_step()


@pytest.mark.parametrize(
    ('presses', 'expected'),
    [
        ([pygame.K_RIGHTBRACKET], 2.0),
        ([pygame.K_RIGHTBRACKET] * 5, 8.0),
        ([pygame.K_LEFTBRACKET] * 4, 0.25),
    ],
)
def test_speed_doubles_and_halves_within_limits(presses, expected):
    """] doubles and [ halves the speed, within MIN_SPEED and MAX_SPEED."""
    controls = ReplayControls(total_frames=100)
    for key in presses:
        controls.handle_key(key=key)
    assert controls.speed == expected


def test_escape_requests_quit_without_posting_an_event(mocker):
    """Esc asks to quit; a posted QUIT would be an internal event the recording lacks."""
    post_event = mocker.patch('glitchygames.recording.post_event')
    controls = ReplayControls(total_frames=100)
    controls.handle_key(key=pygame.K_ESCAPE)
    assert controls.quit_requested
    post_event.assert_not_called()


def test_other_keys_do_nothing():
    """A key the controls do not use changes nothing."""
    controls = ReplayControls(total_frames=100)
    controls.handle_key(key=pygame.K_a)
    assert (controls.paused, controls.speed, controls.step_requested, controls.quit_requested) == (
        False,
        1.0,
        False,
        False,
    )


def test_a_message_lasts_a_fixed_number_of_presented_frames():
    """A message is counted down by presented frames, not by a clock."""
    controls = ReplayControls(total_frames=100)
    controls.show_message(text='no bookmarks to save')
    shown = [
        controls.message_for_presented_frame()
        for _ in range(ReplayControls.MESSAGE_PRESENTED_FRAMES + 1)
    ]
    assert shown[:-1] == ['no bookmarks to save'] * ReplayControls.MESSAGE_PRESENTED_FRAMES
    assert shown[-1] is None


def test_status_line():
    """Every part of the status line, in order."""
    controls = ReplayControls(total_frames=9800)
    controls.handle_key(key=pygame.K_SPACE)
    line = controls.status_line(frame_number=6120, seconds=102.0, divergence_frame=6120)
    assert line == (
        'frame 6120 / 9800 · 1:42.0 · \N{MULTIPLICATION SIGN}1 · paused · diverged at 6120'
    )


def test_status_line_leaves_out_what_does_not_apply():
    """Without a pause or a divergence, those parts are left out."""
    controls = ReplayControls(total_frames=9800)
    controls.handle_key(key=pygame.K_LEFTBRACKET)
    line = controls.status_line(frame_number=12, seconds=0.2, divergence_frame=None)
    assert line == 'frame 12 / 9800 · 0:00.2 · \N{MULTIPLICATION SIGN}0.5'


@pytest.mark.parametrize(
    ('seconds', 'expected'),
    [(0.0, '0:00.0'), (5.34, '0:05.3'), (59.96, '1:00.0'), (102.0, '1:42.0'), (3725.5, '62:05.5')],
)
def test_replay_time_is_minutes_seconds_and_tenths(seconds, expected):
    """The time is rounded to the tenth before it is split into minutes and seconds."""
    assert format_replay_time(seconds=seconds) == expected


class TestStartScreen:
    """Held before frame 0 until Space; drawn like the pause screen, but its own."""

    def test_space_starts_the_replay_without_pausing_it(self):
        controls = ReplayControls(total_frames=100, awaiting_start=True)
        controls.handle_key(key=pygame.K_PERIOD)
        assert controls.awaiting_start
        controls.handle_key(key=pygame.K_SPACE)
        assert not controls.awaiting_start
        assert not controls.paused

    def test_escape_quits_from_the_start_screen(self):
        controls = ReplayControls(total_frames=100, awaiting_start=True)
        controls.handle_key(key=pygame.K_ESCAPE)
        assert controls.quit_requested

    def test_it_is_the_pause_screens_drawing_with_its_own_message_and_look(self):
        start_screen = ReplayStartScreen()
        pause_screen = MessageScreen()
        assert isinstance(start_screen, MessageScreen)
        assert start_screen.MESSAGE == 'Press Spacebar to Start Game Replay'
        assert start_screen.MESSAGE != pause_screen.MESSAGE
        assert (start_screen.DIM_COLOR, start_screen.MESSAGE_COLOR) != (
            pause_screen.DIM_COLOR,
            pause_screen.MESSAGE_COLOR,
        )

    def test_the_message_is_centred_with_the_hint_under_it(self, initialized_pygame):
        message_rect, hint_rect = ReplayStartScreen().text_rects(size=SURFACE_SIZE)
        assert message_rect.center == (SURFACE_SIZE[0] // 2, SURFACE_SIZE[1] // 2)
        assert hint_rect is not None
        assert hint_rect.centerx == SURFACE_SIZE[0] // 2
        assert hint_rect.top == message_rect.bottom + ReplayStartScreen.HINT_GAP
        assert hint_rect.height < message_rect.height

    def test_the_hint_names_the_debug_overlay_keys(self, initialized_pygame):
        hint = ReplayStartScreen().hint_text()
        assert hint == 'F3: debug overlay   F4: next panel'
        assert overlay_key_label(key=TOGGLE_KEY) in hint
        assert overlay_key_label(key=NEXT_PANEL_KEY) in hint

    def test_the_hint_line_is_drawn(self, initialized_pygame):
        surface = pygame.Surface(SURFACE_SIZE)
        start_screen = ReplayStartScreen()
        start_screen.draw(surface=surface)
        _, hint_rect = start_screen.text_rects(size=SURFACE_SIZE)
        assert hint_rect is not None
        # Text pixels over the dimmed background: more than one colour inside the hint's rect
        hint_colors = {
            tuple(surface.get_at((x, y)))
            for x in range(hint_rect.left, hint_rect.right)
            for y in range(hint_rect.top, hint_rect.bottom)
        }
        assert len(hint_colors) > 1

    def test_the_controls_draw_it_only_while_awaiting_start(self, initialized_pygame, mocker):
        draw_spy = mocker.spy(ReplayStartScreen, 'draw')
        controls = ReplayControls(total_frames=100, awaiting_start=True)
        surface = pygame.Surface(SURFACE_SIZE)
        controls.draw(surface=surface, status_line='frame 0 / 100')
        controls.handle_key(key=pygame.K_SPACE)
        controls.draw(surface=surface, status_line='frame 0 / 100')
        assert draw_spy.call_count == 1


class TestStatusBar:
    """The status bar, its message and the banner, drawn at the bottom centre."""

    def test_the_status_bar_draws_at_the_bottom_centre(self, initialized_pygame):
        surface = pygame.Surface(SURFACE_SIZE)
        ReplayControls(total_frames=100).draw(surface=surface, status_line='frame 1 / 100')
        bottom_row = SURFACE_SIZE[1] - 8
        assert surface.get_at((SURFACE_SIZE[0] // 2, bottom_row)) != pygame.Color(0, 0, 0)
        # The corners stay clear for the debug overlay's legend and graph
        assert surface.get_at((6, bottom_row)) == pygame.Color(0, 0, 0)
        assert surface.get_at((SURFACE_SIZE[0] - 6, bottom_row)) == pygame.Color(0, 0, 0)

    def test_drawing_counts_a_message_frame(self, initialized_pygame):
        controls = ReplayControls(total_frames=100)
        controls.show_message(text='hello')
        surface = pygame.Surface(SURFACE_SIZE)
        for _ in range(ReplayControls.MESSAGE_PRESENTED_FRAMES):
            controls.draw(surface=surface, status_line='frame 1 / 100')
        assert controls.message_for_presented_frame() is None
