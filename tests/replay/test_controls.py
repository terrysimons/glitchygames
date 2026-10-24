"""Watched-replay controls (glitchygames/replay/controls.py)."""

from __future__ import annotations

import itertools
import sys

import pygame
import pytest

from glitchygames.debug import DebugPanel
from glitchygames.debug.overlay import NEXT_PANEL_KEY, TOGGLE_KEY
from glitchygames.replay import controls as controls_module
from glitchygames.replay.controls import (
    CONTROL_TICK_SECONDS,
    CONTROL_TICKS_PER_SECOND,
    FIRST_PAUSED_FRAME,
    STEP_REPEAT_DELAY_SECONDS,
    STEP_REPEAT_INTERVAL_SECONDS,
    ControlCadence,
    ReplayControls,
    ReplayStartScreen,
    format_replay_time,
    overlay_key_label,
    rebuild_progress_text,
)
from glitchygames.supervision import BREAKPOINT_KIND, ControlEvent
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


def test_step_back_requests_the_previous_frame_while_paused():
    """, while paused at frame N asks for a restart at N - 1, and says so."""
    controls = ReplayControls(total_frames=100)
    controls.handle_key(key=pygame.K_SPACE)
    controls.current_frame = 10
    controls.handle_key(key=pygame.K_COMMA)
    assert controls.restart_request == 9
    assert controls.message_for_control_tick() == 'back to frame 9'
    assert controls.take_restart_request() == 9
    assert controls.restart_request is None
    assert controls.take_restart_request() is None


@pytest.mark.parametrize('current_frame', [0, FIRST_PAUSED_FRAME])
def test_step_back_at_the_first_frame_does_nothing(current_frame):
    """Frame 0 always runs before a pause, so nothing comes before the first paused frame."""
    controls = ReplayControls(total_frames=100)
    controls.handle_key(key=pygame.K_SPACE)
    controls.current_frame = current_frame
    controls.handle_key(key=pygame.K_COMMA)
    assert controls.restart_request is None


def test_step_back_does_nothing_while_running():
    """Like a step, a step back needs a pause."""
    controls = ReplayControls(total_frames=100)
    controls.current_frame = 10
    controls.handle_key(key=pygame.K_COMMA)
    assert controls.restart_request is None


@pytest.mark.parametrize('key', [pygame.K_COMMA, pygame.K_HOME, pygame.K_d])
def test_restarts_are_refused_where_no_process_can_start(mocker, key):
    """In a browser a restart (a new process) cannot run: the key says so and asks nothing."""
    mocker.patch.object(controls_module, 'RESTARTS_AVAILABLE', new=False)
    controls = ReplayControls(total_frames=100)
    controls.handle_key(key=pygame.K_SPACE)
    controls.current_frame = 50
    controls.divergence_frame = 42

    controls.handle_key(key=key)

    assert controls.restart_request is None
    assert controls.message_for_control_tick() == controls_module.RESTARTS_UNAVAILABLE_MESSAGE


def test_restarts_are_available_but_in_a_browser():
    """Restarting starts a new process (glitchygames/replay/rebuild.py): never in a page."""
    assert controls_module.RESTARTS_AVAILABLE is (sys.platform != 'emscripten')


def test_home_and_jump_to_divergence():
    """D asks for the divergence frame once there is one; Home for frame 0."""
    controls = ReplayControls(total_frames=100)
    controls.current_frame = 50
    controls.handle_key(key=pygame.K_d)
    assert controls.restart_request is None  # no divergence yet
    controls.divergence_frame = 42
    controls.handle_key(key=pygame.K_d)
    assert controls.restart_request == 42
    controls.handle_key(key=pygame.K_HOME)
    assert controls.restart_request == 0


@pytest.mark.parametrize(('key', 'current_frame'), [(pygame.K_HOME, 1), (pygame.K_d, 42)])
def test_home_and_jump_do_nothing_at_the_frame_already_shown(key, current_frame):
    """A restart that would rebuild the frame already shown is not asked for."""
    controls = ReplayControls(total_frames=100)
    controls.divergence_frame = 42
    controls.current_frame = current_frame
    controls.handle_key(key=key)
    assert controls.restart_request is None


def test_holding_step_back_accumulates_until_the_release():
    """Held, , repeats like a step; the restart is taken once, at the release."""
    controls = ReplayControls(total_frames=100)
    controls.paused = True
    controls.current_frame = 20
    tick_count = 60  # one second of control ticks
    for tick in range(tick_count):
        now = tick * CONTROL_TICK_SECONDS
        controls.press_key(key=pygame.K_COMMA, now=now)
        controls.repeat_held_keys(now=now)
        assert controls.take_restart_request() is None
    # One on the press, then ten a second after the delay
    expected_steps = 1 + round((1.0 - STEP_REPEAT_DELAY_SECONDS) / STEP_REPEAT_INTERVAL_SECONDS)
    target = controls.restart_request
    assert target is not None
    assert abs(target - (20 - expected_steps)) <= 1
    controls.release_key(key=pygame.K_COMMA)
    assert controls.take_restart_request() == target
    assert controls.take_restart_request() is None


def test_resuming_drops_a_pending_restart():
    """Space resumes the replay: a step back still held is forgotten."""
    controls = ReplayControls(total_frames=100)
    controls.paused = True
    controls.current_frame = 20
    controls.press_key(key=pygame.K_COMMA, now=0.0)
    controls.handle_key(key=pygame.K_SPACE)
    controls.release_key(key=pygame.K_COMMA)
    assert controls.restart_request is None
    assert controls.take_restart_request() is None


def test_a_step_while_stepping_back_moves_the_base_to_the_new_frame():
    """. while , is held: the target counts back from the frame the step reaches."""
    controls = ReplayControls(total_frames=100)
    controls.paused = True
    controls.current_frame = 20
    controls.press_key(key=pygame.K_COMMA, now=0.0)
    assert controls.restart_request == 19
    controls.handle_key(key=pygame.K_PERIOD)
    assert controls.restart_request is None
    controls.current_frame = 21  # the step ran
    controls.handle_key(key=pygame.K_COMMA)  # the held , repeats
    assert controls.restart_request == 20


def test_holding_step_back_stops_at_the_first_paused_frame():
    """Repeats never move the target before the first paused frame."""
    controls = ReplayControls(total_frames=100)
    controls.paused = True
    controls.current_frame = 3
    for _ in range(5):
        controls.handle_key(key=pygame.K_COMMA)
    assert controls.restart_request == FIRST_PAUSED_FRAME


class TestRebuilding:
    """While a restarted replay rebuilds up to its pause frame."""

    def test_only_escape_and_the_overlay_keys_act(self):
        controls = ReplayControls(total_frames=100)
        controls.rebuild_target_frame = 50
        controls.current_frame = 30
        controls.divergence_frame = 10
        for key in (
            pygame.K_SPACE,
            pygame.K_HOME,
            pygame.K_d,
            pygame.K_RIGHTBRACKET,
            pygame.K_b,
            pygame.K_s,
        ):
            controls.handle_key(key=key)
        assert (controls.paused, controls.restart_request, controls.speed) == (False, None, 1.0)
        assert controls.bookmarks == []
        assert not controls.take_save_request()
        controls.handle_key(key=TOGGLE_KEY)
        controls.handle_key(key=pygame.K_ESCAPE)
        assert controls.debug_overlay.is_visible
        assert controls.quit_requested

    def test_the_progress_text(self):
        assert rebuild_progress_text(frame_index=60, target_frame=130) == (
            'Rebuilding: frame 60 / 130'
        )

    def test_the_rebuild_screen_replaces_the_status_bar(self, initialized_pygame, mocker):
        font = mocker.Mock()
        font.render.return_value = pygame.Surface((40, 10))
        mocker.patch.object(controls_module, 'load_debug_font', return_value=font)
        surface = pygame.Surface(SURFACE_SIZE)
        surface.fill((200, 10, 10))
        controls = ReplayControls(total_frames=100)
        controls.rebuild_target_frame = 130
        controls.current_frame = 60
        controls.update_status(status_line='frame 60 / 100')
        controls.draw(surface=surface)
        rendered_texts = [call.args[0] for call in font.render.call_args_list]
        assert rendered_texts == ['Rebuilding: frame 60 / 130']
        # The display is cleared around the one line
        assert surface.get_at((2, 2)) == pygame.Color(0, 0, 0)
        assert surface.get_at((2, SURFACE_SIZE[1] - 2)) == pygame.Color(0, 0, 0)


class TestBookmarks:
    """B bookmarks the frame, S asks for a saved copy, and a recorded breakpoint pauses."""

    def test_bookmarks_are_unique_and_sorted(self):
        controls = ReplayControls(total_frames=100)
        for frame in (30, 10, 30):
            controls.current_frame = frame
            controls.handle_key(key=pygame.K_b)
        assert controls.bookmarks == [10, 30]

    def test_a_bookmark_says_which_frame_it_marked(self):
        controls = ReplayControls(total_frames=100)
        controls.current_frame = 30
        controls.handle_key(key=pygame.K_b)
        assert controls.message_for_control_tick() == 'bookmarked frame 30'

    def test_bookmarking_a_frame_again_says_so(self):
        controls = ReplayControls(total_frames=100)
        controls.current_frame = 30
        controls.handle_key(key=pygame.K_b)
        controls.handle_key(key=pygame.K_b)
        assert controls.bookmarks == [30]
        assert controls.message_for_control_tick() == 'frame 30 already bookmarked'

    def test_a_bookmark_before_frame_zero_ran_marks_the_first_paused_frame(self):
        controls = ReplayControls(total_frames=100)
        controls.handle_key(key=pygame.K_b)
        assert controls.bookmarks == [FIRST_PAUSED_FRAME]

    def test_save_is_requested_once_per_press(self):
        controls = ReplayControls(total_frames=100)
        assert not controls.take_save_request()
        controls.handle_key(key=pygame.K_s)
        assert controls.take_save_request()
        assert not controls.take_save_request()

    def test_a_breakpoint_pauses_and_names_its_label(self):
        controls = ReplayControls(total_frames=100)
        controls.step_requested = True
        controls.pause_at_breakpoint(ControlEvent(kind=BREAKPOINT_KIND, data={'label': 'bookmark'}))
        assert controls.paused
        assert not controls.step_requested
        assert controls.message_for_control_tick() == 'breakpoint: bookmark'

    def test_a_breakpoint_without_a_label_pauses(self):
        controls = ReplayControls(total_frames=100)
        controls.pause_at_breakpoint(ControlEvent(kind=BREAKPOINT_KIND, data={}))
        assert controls.paused
        assert controls.message_for_control_tick() == 'breakpoint'

    def test_a_breakpoint_does_not_pause_a_rebuild(self):
        controls = ReplayControls(total_frames=100)
        controls.rebuild_target_frame = 50
        controls.pause_at_breakpoint(ControlEvent(kind=BREAKPOINT_KIND, data={'label': 'bookmark'}))
        assert not controls.paused
        assert controls.message_for_control_tick() is None


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
