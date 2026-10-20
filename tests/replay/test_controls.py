"""Watched-replay controls (glitchygames/replay/controls.py)."""

from __future__ import annotations

import itertools

import pygame
import pytest

from glitchygames.debug import DebugPanel
from glitchygames.debug.overlay import NEXT_PANEL_KEY, TOGGLE_KEY
from glitchygames.replay.controls import (
    CONTROL_TICK_SECONDS,
    CONTROL_TICKS_PER_SECOND,
    STEP_REPEAT_DELAY_SECONDS,
    STEP_REPEAT_INTERVAL_SECONDS,
    ControlCadence,
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


def test_step_back_says_it_arrives_later():
    """The , key (step back) only shows a status message for now."""
    controls = ReplayControls(total_frames=100)
    controls.handle_key(key=pygame.K_COMMA)
    assert controls.message_for_control_tick() == 'step back arrives in a later version'


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


def test_a_message_lasts_a_fixed_number_of_control_ticks():
    """A message is counted down by control ticks (60 a second of real time)."""
    controls = ReplayControls(total_frames=100)
    controls.show_message(text='no bookmarks to save')
    shown = [
        controls.message_for_control_tick() for _ in range(ReplayControls.MESSAGE_CONTROL_TICKS + 1)
    ]
    assert shown[:-1] == ['no bookmarks to save'] * ReplayControls.MESSAGE_CONTROL_TICKS
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


def test_status_line_shows_the_real_speed_when_it_cannot_keep_up():
    """The viewer passes its effective speed while behind."""
    controls = ReplayControls(total_frames=100)
    controls.speed = 8.0
    line = controls.status_line(
        frame_number=5, seconds=0.0, divergence_frame=None, effective_speed=3.2
    )
    assert line == (
        'frame 5 / 100 · 0:00.0 · \N{MULTIPLICATION SIGN}8 · '
        "can't keep up: \N{MULTIPLICATION SIGN}3.2"
    )


def test_a_key_already_down_acts_only_after_its_release():
    """A key held before the replay began: its repeats are not presses."""
    controls = ReplayControls(total_frames=100)
    controls.note_key_already_down(key=pygame.K_SPACE)
    controls.press_key(key=pygame.K_SPACE, now=0.0)
    assert not controls.paused
    controls.release_key(key=pygame.K_SPACE)
    controls.press_key(key=pygame.K_SPACE, now=0.1)
    assert controls.paused


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
        controls.update_status(status_line='frame 1 / 100')
        controls.draw(surface=surface)
        controls.handle_key(key=pygame.K_SPACE)
        controls.draw(surface=surface)
        assert draw_spy.call_count == 1


class TestStatusBar:
    """The status bar, its message and the banner, drawn at the bottom centre."""

    def test_the_status_bar_draws_at_the_bottom_centre(self, initialized_pygame):
        surface = pygame.Surface(SURFACE_SIZE)
        controls = ReplayControls(total_frames=100)
        controls.update_status(status_line='frame 1 / 100')
        controls.draw(surface=surface)
        bottom_row = SURFACE_SIZE[1] - 8
        assert surface.get_at((SURFACE_SIZE[0] // 2, bottom_row)) != pygame.Color(0, 0, 0)
        # The corners stay clear for the debug overlay's legend and graph
        assert surface.get_at((6, bottom_row)) == pygame.Color(0, 0, 0)
        assert surface.get_at((SURFACE_SIZE[0] - 6, bottom_row)) == pygame.Color(0, 0, 0)

    def test_each_status_update_counts_a_message_tick(self, initialized_pygame):
        controls = ReplayControls(total_frames=100)
        controls.show_message(text='hello')
        surface = pygame.Surface(SURFACE_SIZE)
        for _ in range(ReplayControls.MESSAGE_CONTROL_TICKS):
            controls.update_status(status_line='frame 1 / 100')
            controls.draw(surface=surface)
        assert controls.message_for_control_tick() is None


class TestKeyPresses:
    """One action per press; step keys repeat by themselves while held."""

    @pytest.mark.parametrize(
        'key', [pygame.K_SPACE, pygame.K_F3, pygame.K_F4, pygame.K_RIGHTBRACKET]
    )
    def test_one_press_is_one_action_under_one_millisecond_key_repeat(self, key):
        controls = ReplayControls(total_frames=100)
        for repeat in range(50):
            controls.press_key(key=key, now=repeat * 0.001)
            controls.repeat_held_keys(now=repeat * 0.001)
        controls.release_key(key=key)
        assert (
            controls.paused,
            controls.debug_overlay.is_visible,
            controls.debug_overlay.panel is not DebugPanel.ALL,
            controls.speed,
        ) == (
            key == pygame.K_SPACE,
            key == pygame.K_F3,
            key == pygame.K_F4,
            2.0 if key == pygame.K_RIGHTBRACKET else 1.0,
        )

    def test_a_released_key_acts_again_on_its_next_press(self):
        controls = ReplayControls(total_frames=100)
        controls.press_key(key=pygame.K_SPACE, now=0.0)
        controls.release_key(key=pygame.K_SPACE)
        controls.press_key(key=pygame.K_SPACE, now=0.1)
        assert not controls.paused

    def test_holding_step_steps_once_then_repeats_ten_times_a_second_after_the_delay(self):
        controls = ReplayControls(total_frames=100)
        controls.paused = True
        steps_at: list[float] = []
        tick_count = 120  # two seconds of control ticks
        for tick in range(tick_count):
            now = tick * CONTROL_TICK_SECONDS
            # The operating system repeats the held key every millisecond meanwhile
            controls.press_key(key=pygame.K_PERIOD, now=now)
            controls.repeat_held_keys(now=now)
            if controls.take_step():
                steps_at.append(now)
        assert steps_at[0] == 0.0
        assert steps_at[1] >= STEP_REPEAT_DELAY_SECONDS
        assert steps_at[1] - steps_at[0] < STEP_REPEAT_DELAY_SECONDS + CONTROL_TICK_SECONDS
        later_intervals = [later - earlier for earlier, later in itertools.pairwise(steps_at[1:])]
        assert sum(later_intervals) / len(later_intervals) == pytest.approx(
            STEP_REPEAT_INTERVAL_SECONDS, abs=CONTROL_TICK_SECONDS
        )
        controls.release_key(key=pygame.K_PERIOD)
        controls.repeat_held_keys(now=tick_count * CONTROL_TICK_SECONDS + 1.0)
        assert not controls.take_step()


class TestControlCadence:
    """The controls' real-time tick."""

    def test_ticks_sixty_times_a_second(self):
        cadence = ControlCadence()
        ticks = sum(cadence.tick_is_due(now=millisecond / 1000) for millisecond in range(1000))
        assert ticks == CONTROL_TICKS_PER_SECOND

    def test_a_late_tick_starts_again_from_now(self):
        cadence = ControlCadence()
        assert cadence.tick_is_due(now=0.0)
        assert cadence.tick_is_due(now=5.0)
        assert cadence.next_tick_seconds(now=5.0) == pytest.approx(5.0 + CONTROL_TICK_SECONDS)
