"""Test the Sound Board demo (the sound_board_demo package): real pygame, display and mixer.

The demo shows one row per built-in wave and noise, each with the eight notes of the current
scale; number keys 1-8 play the current row's notes, Up and Down pick the row, L cycles the
labels (note names, hertz, scale steps) and C plays a C major chord on the current row.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pygame
import pytest

import sound_board_demo
from glitchygames.audio import Sound
from glitchygames.display_mode import set_display_mode
from glitchygames.events.base import HashableEvent
from tests.demo_runs import engine_run_environment, run_demo_main

if TYPE_CHECKING:
    from collections.abc import Generator

    from pytest_mock import MockerFixture

    from glitchygames.audio.engine import AudioEngine

DEMO_DISPLAY_SIZE = (800, 600)
# The engine's default window
DEFAULT_WINDOW_SIZE = (800, 480)
# Every built-in wave and noise, one row each, in the demo's order
EXPECTED_ROW_NAMES = (
    'sine',
    'triangle',
    'saw',
    'square',
    'pulse_12',
    'pulse_25',
    'pulse_75',
    'white noise',
    'lfsr 15-bit',
    'lfsr 7-bit',
)
STEPS_PER_ROW = 8
# Each row's eight notes and one C major chord are requested in setup()
EXPECTED_SETUP_SOUNDS = len(EXPECTED_ROW_NAMES) * (STEPS_PER_ROW + 1)
C_MAJOR_NOTE_NAMES = ('C4', 'D4', 'E4', 'F4', 'G4', 'A4', 'B4', 'C5')


@pytest.fixture
def engine_run(mocker: MockerFixture) -> Generator[None]:
    """Let the test start a real engine (see demo_runs.engine_run_environment).

    Yields:
        None, while the environment is in place.

    """
    yield from engine_run_environment(mocker)


@pytest.fixture
def scene() -> Generator[sound_board_demo.Game]:
    """Return the demo's scene, set up as the scene manager sets it up (compiles are setup's).

    Yields:
        The scene.

    """
    set_display_mode(size=DEMO_DISPLAY_SIZE)
    game = sound_board_demo.Game(options={})
    game.scene_manager.audio.begin_scene_setup()
    game.setup()
    game.scene_manager.audio.begin_logic_frame()
    yield game
    game.scene_manager.audio.stop_all(fade=0.005)


def _key_down(scancode: int) -> HashableEvent:
    """Return a key down event for a physical key.

    Returns:
        The event.

    """
    return HashableEvent(pygame.KEYDOWN, key=0, mod=0, unicode='', scancode=scancode)


def _audio(scene: sound_board_demo.Game) -> AudioEngine:
    """Return the scene's audio engine.

    Returns:
        The engine.

    """
    return scene.scene_manager.audio


def test_the_rows_are_every_built_in_wave_and_noise(scene: sound_board_demo.Game) -> None:
    """One row per built-in wave and noise (feature spec 3.1, 3.2 and W1)."""
    assert tuple(row.name for row in scene.rows) == EXPECTED_ROW_NAMES


def test_setup_requests_every_sound_so_gameplay_compiles_nothing(
    scene: sound_board_demo.Game,
) -> None:
    """Setup compiles every note and chord; playing all of them then compiles nothing more."""
    audio = _audio(scene)
    after_setup = audio.diagnostics()
    assert after_setup.setup_compiles == EXPECTED_SETUP_SOUNDS
    assert after_setup.gameplay_compiles == 0
    assert all(record.during_setup for record in audio.accountant.compile_log)

    for _row in scene.rows:
        for step_key in sound_board_demo.STEP_SCANCODES:
            scene.on_key_down_event(_key_down(step_key))
        scene.on_key_down_event(_key_down(pygame.KSCAN_C))
        scene.on_key_down_event(_key_down(pygame.KSCAN_DOWN))

    assert audio.diagnostics().gameplay_compiles == 0
    assert audio.diagnostics().compiles == EXPECTED_SETUP_SOUNDS


def test_a_number_key_plays_one_voice(scene: sound_board_demo.Game) -> None:
    """Key 1 plays the current row's first note: one voice is playing."""
    scene.on_key_down_event(_key_down(pygame.KSCAN_1))

    assert _audio(scene).diagnostics().voices_playing == 1


def test_the_chord_key_plays_one_chord_voice(scene: sound_board_demo.Game) -> None:
    """C plays the C major chord on the current row: it is one sound, so one voice."""
    scene.on_key_down_event(_key_down(pygame.KSCAN_C))

    assert _audio(scene).diagnostics().voices_playing == 1


def test_an_unbound_key_plays_nothing(scene: sound_board_demo.Game) -> None:
    """A key with no binding plays no voice."""
    scene.on_key_down_event(_key_down(pygame.KSCAN_Z))

    assert _audio(scene).diagnostics().voices_playing == 0


def test_down_and_up_pick_the_row_and_wrap(scene: sound_board_demo.Game) -> None:
    """Down moves to the next row, Up to the previous; both wrap around the ends."""
    assert scene.selected_row_index == 0

    scene.on_key_down_event(_key_down(pygame.KSCAN_DOWN))
    assert scene.selected_row_index == 1

    scene.on_key_down_event(_key_down(pygame.KSCAN_UP))
    scene.on_key_down_event(_key_down(pygame.KSCAN_UP))
    assert scene.selected_row_index == len(EXPECTED_ROW_NAMES) - 1

    scene.on_key_down_event(_key_down(pygame.KSCAN_DOWN))
    assert scene.selected_row_index == 0


def test_the_label_key_cycles_names_hertz_and_steps(scene: sound_board_demo.Game) -> None:
    """L cycles the labels: note names, then hertz, then scale steps, then back."""
    assert [scene.step_label(step_index=index) for index in range(STEPS_PER_ROW)] == list(
        C_MAJOR_NOTE_NAMES
    )

    scene.on_key_down_event(_key_down(pygame.KSCAN_L))
    hertz_labels = [scene.step_label(step_index=index) for index in range(STEPS_PER_ROW)]
    assert hertz_labels[0] == '261.63 Hz'
    assert hertz_labels[5] == '440.00 Hz'

    scene.on_key_down_event(_key_down(pygame.KSCAN_L))
    assert [scene.step_label(step_index=index) for index in range(STEPS_PER_ROW)] == [
        str(number) for number in range(1, STEPS_PER_ROW + 1)
    ]

    scene.on_key_down_event(_key_down(pygame.KSCAN_L))
    assert scene.step_label(step_index=0) == 'C4'


def test_the_label_mode_changes_only_the_label_not_the_pitch(
    scene: sound_board_demo.Game,
) -> None:
    """The same pitches play whatever the labels show: no new sound is compiled."""
    scene.on_key_down_event(_key_down(pygame.KSCAN_L))
    scene.on_key_down_event(_key_down(pygame.KSCAN_6))

    audio = _audio(scene)
    assert audio.diagnostics().voices_playing == 1
    assert audio.diagnostics().compiles == EXPECTED_SETUP_SOUNDS
    assert scene.step_pitch(step_index=5).to_hz() == pytest.approx(440.0)


def test_the_screen_shows_the_selected_row_and_is_not_black(scene: sound_board_demo.Game) -> None:
    """The last frame has pixels: the selected row's cells are coloured apart from the others."""
    assert scene.screen is not None
    scene.render(scene.screen)

    selected_cell = scene.cell_rect(row_index=0, step_index=0)
    other_cell = scene.cell_rect(row_index=1, step_index=0)
    selected_color = scene.screen.get_at((selected_cell.x + 1, selected_cell.y + 1))
    other_color = scene.screen.get_at((other_cell.x + 1, other_cell.y + 1))
    assert tuple(selected_color)[:3] == sound_board_demo.SELECTED_ROW_RGB
    assert tuple(other_color)[:3] == sound_board_demo.ROW_RGB
    assert any(
        scene.screen.get_at((x_position, y_position))[:3] != (0, 0, 0)
        for x_position in range(0, DEMO_DISPLAY_SIZE[0], 7)
        for y_position in range(0, DEMO_DISPLAY_SIZE[1], 7)
    )


def test_every_label_fits_inside_its_cell_and_the_screen(scene: sound_board_demo.Game) -> None:
    """In every label mode, every row's labels fit their cells."""
    assert scene.screen is not None
    for _mode in sound_board_demo.LABEL_MODES:
        for row_index in range(len(scene.rows)):
            for step_index in range(STEPS_PER_ROW):
                cell = scene.cell_rect(row_index=row_index, step_index=step_index)
                label_width = scene.font.size(scene.step_label(step_index=step_index))[0]
                assert label_width + 2 * sound_board_demo.CELL_TEXT_INSET <= cell.width, (
                    f'{scene.step_label(step_index=step_index)} is too wide for its cell'
                )
                assert cell.right <= DEFAULT_WINDOW_SIZE[0]
                assert cell.bottom <= DEFAULT_WINDOW_SIZE[1]
        scene.on_key_down_event(_key_down(pygame.KSCAN_L))


def test_args_adds_the_version_flag() -> None:
    """``--version`` prints the demo's name and version and exits."""
    import argparse

    parser = argparse.ArgumentParser()
    sound_board_demo.Game.args(parser)

    with pytest.raises(SystemExit):
        parser.parse_args(['--version'])


def test_main_turns_on_the_audio_panel_when_given_no_flags(mocker: MockerFixture) -> None:
    """With no command line flags, main() passes --sound-diagnostics to the engine."""
    mocker.patch.object(sys, 'argv', ['sound-board-demo'])
    engine_class = mocker.patch.object(sound_board_demo, 'GameEngine')
    arguments_seen: list[str] = []
    engine_class.return_value.start.side_effect = lambda: arguments_seen.extend(sys.argv)

    sound_board_demo.main()

    engine_class.assert_called_once_with(game=sound_board_demo.Game)
    assert arguments_seen == ['sound-board-demo', '--sound-diagnostics']


def test_main_keeps_the_users_own_flags(mocker: MockerFixture) -> None:
    """When the user passes any flags, main() leaves the command line as it is."""
    mocker.patch.object(sys, 'argv', ['sound-board-demo', '--log-level', 'warning'])
    engine_class = mocker.patch.object(sound_board_demo, 'GameEngine')
    arguments_seen: list[str] = []
    engine_class.return_value.start.side_effect = lambda: arguments_seen.extend(sys.argv)

    sound_board_demo.main()

    assert arguments_seen == ['sound-board-demo', '--log-level', 'warning']


@pytest.mark.usefixtures('engine_run')
def test_main_runs_the_demo_and_plays_a_key(mocker: MockerFixture) -> None:
    """A real engine run: key 1 then the chord key play, and the run quits on its own."""
    play = mocker.spy(Sound, 'play')
    script = run_demo_main(
        mocker=mocker,
        module=sound_board_demo,
        main=sound_board_demo.main,
        resolution='x'.join(str(length) for length in DEMO_DISPLAY_SIZE),
        events_by_frame={
            0: [
                pygame.event.Event(
                    pygame.KEYDOWN,
                    key=pygame.K_1,
                    mod=0,
                    unicode='1',
                    scancode=pygame.KSCAN_1,
                    window=None,
                )
            ],
            1: [
                pygame.event.Event(
                    pygame.KEYDOWN,
                    key=pygame.K_c,
                    mod=0,
                    unicode='c',
                    scancode=pygame.KSCAN_C,
                    window=None,
                )
            ],
        },
    )

    scenes = [seen for seen in script.scenes_seen if seen is not None]
    assert isinstance(scenes[-1], sound_board_demo.Game)
    # Key 1 and the chord key each got a real voice slot (a dropped play's handle has slot -1)
    assert play.call_count == 2
    for handle in play.spy_return_list:
        assert handle.slot >= 0, 'the play was dropped: it got the silent handle'
        assert handle.table is not None
        assert handle.table.counters.dropped_plays == 0


def test_a_scene_given_sprite_groups_keeps_them() -> None:
    """The scene is added to the groups it is given (and makes its own when it is given none)."""
    group = pygame.sprite.LayeredDirty()

    game = sound_board_demo.Game(options={}, groups=group)

    assert game.all_sprites is group
