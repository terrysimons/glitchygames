"""The launcher (brave_adventurer_modes): one command for both games, and its title screen.

``brave-adventurer`` starts the game ``--game`` names, else the game a recording to replay was
made in, else the title screen, which offers both games. Every game is started by its own
``main()`` or, from the title screen, by its own scene in the same engine, so each game runs as
it always has.
"""

from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Self

import pygame
import pytest
from scripts.record_golden_traces import (
    SCREEN_RESOLUTION,
    GoldenTraceEngine,
    GoldenTraceSceneManager,
    command_line,
    deterministic_environment,
    discard_environment_events,
    press,
    release,
)

import brave_adventurer
import brave_adventurer_modes
import brave_adventurer_papyrus
from brave_adventurer import game as brave_adventurer_game
from brave_adventurer.game import BraveAdventurerScene
from brave_adventurer_modes import GAMES_BY_NAME, game_for_recording, launcher, recorded_game
from brave_adventurer_modes.title import GAME_CHOICES, GameChoiceCard, TitleScene
from brave_adventurer_papyrus import game as papyrus_game
from brave_adventurer_papyrus.game import PapyrusBraveAdventurerScene
from glitchygames.display_mode import set_display_mode
from glitchygames.events.base import HashableEvent
from glitchygames.exit_codes import ExitCode
from glitchygames.live_sources import LiveSources
from glitchygames.logical_names import logical_name
from glitchygames.recording import post_input_event
from glitchygames.scenes import SceneManager
from glitchygames.testing.replays import recording_console_script, replay_recording_headless
from glitchygames.tracing import read_trace_result, write_trace

if TYPE_CHECKING:
    from collections.abc import Generator

    from glitchygames.scenes import Scene

PROJECT_ROOT = Path(__file__).resolve().parents[4]
REPLAY_FIXTURES_DIRECTORY = Path(__file__).resolve().parent / 'fixtures' / 'replays'
CLASSIC_GOLDEN = REPLAY_FIXTURES_DIRECTORY / 'golden-classic.jsonl.gz'
PAPYRUS_GOLDEN = REPLAY_FIXTURES_DIRECTORY / 'golden-papyrus.jsonl.gz'
# Another game's recording: the launcher must refuse it, not show the title screen
MR_MUNCHER_GOLDEN = PROJECT_ROOT / 'src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz'
FRAME_SECONDS = 1 / 60
SCREEN_SIZE = (800, 480)


def _start_display():
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        set_display_mode(size=SCREEN_SIZE)


def _replay_arguments(recording: Path) -> list[str]:
    return ['--log-level', 'warning', '--replay-trace', str(recording), '--headless']


@contextlib.contextmanager
def _engine_run(mocker) -> Generator[None]:
    """Let an engine run end inside a test as it does in a process, then clean up after it."""
    # GameEngine._shutdown quits pygame; later tests on this worker still need it
    mocker.patch('pygame.quit')
    mocker.patch('pygame.display.quit')
    # --headless sets the SDL driver variables; the test's own values come back afterwards
    mocker.patch.dict(os.environ)
    SceneManager._reset()  # the engine starts from a fresh scene manager, as a process does
    try:
        yield
    finally:
        pygame.event.clear()
        SceneManager._reset()


@contextlib.contextmanager
def _title_screen(tmp_path: Path) -> Generator[GoldenTraceSceneManager]:
    """The real engine on the title screen, stepped a frame at a time by the test.

    Yields:
        The scene manager, with the title screen active.

    """
    with deterministic_environment(save_root=tmp_path):
        manager = GoldenTraceSceneManager.install()
        try:
            with command_line([
                '--windowed',
                '--resolution',
                SCREEN_RESOLUTION,
                '--log-level',
                'warning',
                '--input-mode',
                'joystick',
            ]):
                engine = GoldenTraceEngine(game=TitleScene)
            engine.install_game(scene_class=TitleScene)
            discard_environment_events()
            yield manager
        finally:
            pygame.event.clear()
            GoldenTraceSceneManager.uninstall()


def _run_frames(manager: GoldenTraceSceneManager, *events: pygame.event.Event) -> None:
    """Post each event before its own frame, then run one more frame (a switch lands there)."""
    for event in events:
        post_input_event(event)
        manager.dt = FRAME_SECONDS
        manager.run_frame()
    manager.dt = FRAME_SECONDS
    manager.run_frame()


class TestTheGameFlag:
    """``--game classic|papyrus`` runs that game's own main(), without the flag."""

    @pytest.mark.parametrize(
        ('game', 'game_module', 'version'),
        [
            ('classic', brave_adventurer_game, 'Brave Adventurer 1.0\n'),
            ('papyrus', papyrus_game, 'Brave Adventurer: Papyrus Edition 1.0\n'),
        ],
    )
    def test_the_game_flag_starts_that_game_without_its_flag(
        self, mocker, capsys, game, game_module, version
    ):
        """The game's own parser sees the arguments minus --game (it would refuse the flag)."""
        mocker.patch.object(game_module, 'GameEngine', GoldenTraceEngine)
        start = mocker.patch.object(GoldenTraceEngine, 'start')
        title_screen = mocker.spy(TitleScene, '__init__')
        with command_line(['--game', game, '--version']):
            with pytest.raises(SystemExit) as exit_info:
                brave_adventurer_modes.main()
            remaining_arguments = list(sys.argv)

        assert exit_info.value.code == ExitCode.SUCCESS
        assert capsys.readouterr().out == version
        assert remaining_arguments == ['record_golden_traces', '--version']
        start.assert_not_called()
        title_screen.assert_not_called()

    def test_an_unknown_game_is_an_error(self, capsys):
        with command_line(['--game', 'pong']), pytest.raises(SystemExit) as exit_info:
            brave_adventurer_modes.main()

        assert exit_info.value.code == ExitCode.ARGUMENT_PARSER_ERROR
        error = capsys.readouterr().err
        assert "invalid choice: 'pong'" in error
        assert 'classic' in error
        assert 'papyrus' in error

    def test_the_games_are_each_games_own_main(self):
        assert {
            'classic': brave_adventurer.main,
            'papyrus': brave_adventurer_papyrus.main,
        } == GAMES_BY_NAME
        assert [choice.name for choice in GAME_CHOICES] == list(GAMES_BY_NAME)
        assert [choice.scene_class for choice in GAME_CHOICES] == [
            BraveAdventurerScene,
            PapyrusBraveAdventurerScene,
        ]

    def test_the_flag_wins_over_a_recordings_game(self, mocker):
        """--game with another game's recording: that game's own replay refuses it."""
        mocker.patch.object(brave_adventurer_game, 'GameEngine', GoldenTraceEngine)
        with (
            _engine_run(mocker),
            command_line(['--game', 'classic', *_replay_arguments(PAPYRUS_GOLDEN)]),
            pytest.raises(SystemExit) as exit_info,
        ):
            brave_adventurer_modes.main()

        assert exit_info.value.code == ExitCode.UNUSABLE_INPUT


class TestRecordings:
    """A recording to replay starts the game it was made in, without the title screen."""

    @pytest.mark.parametrize(
        ('golden', 'game'), [(CLASSIC_GOLDEN, 'classic'), (PAPYRUS_GOLDEN, 'papyrus')]
    )
    def test_a_recording_names_its_game(self, golden, game):
        assert game_for_recording(path=golden) == game

    def test_a_recording_of_another_game_names_none(self):
        assert game_for_recording(path=MR_MUNCHER_GOLDEN) is None
        assert recorded_game(path=MR_MUNCHER_GOLDEN) == 'games.mr_muncher.game:MrMuncherScene'

    def test_an_unreadable_recording_names_no_game(self, tmp_path):
        assert game_for_recording(path=tmp_path / 'missing.jsonl.gz') is None

    def test_a_recording_without_a_game_names_none(self, tmp_path):
        """A recording made before logical names has no ``game`` in its header."""
        path = tmp_path / 'before-logical-names.jsonl.gz'
        trace = read_trace_result(path=CLASSIC_GOLDEN).trace
        del trace['game']
        write_trace(path=path, trace=trace)

        assert recorded_game(path=path) is None
        assert game_for_recording(path=path) is None

    def test_a_recording_without_a_game_is_refused_until_the_game_is_named(self, tmp_path, caplog):
        path = tmp_path / 'before-logical-names.jsonl.gz'
        trace = read_trace_result(path=CLASSIC_GOLDEN).trace
        del trace['game']
        write_trace(path=path, trace=trace)

        with command_line(_replay_arguments(path)), pytest.raises(SystemExit) as exit_info:
            brave_adventurer_modes.main()

        assert exit_info.value.code == ExitCode.UNUSABLE_INPUT
        assert 'made before logical names' in caplog.text
        assert '--game classic or --game papyrus' in caplog.text

    @pytest.mark.parametrize(
        ('golden', 'game_module'),
        [(CLASSIC_GOLDEN, brave_adventurer_game), (PAPYRUS_GOLDEN, papyrus_game)],
    )
    def test_a_recording_starts_its_own_game(self, mocker, golden, game_module):
        """Each golden replays clean through the launcher: its own game ran, not the title."""
        mocker.patch.object(game_module, 'GameEngine', GoldenTraceEngine)
        title_screen = mocker.spy(TitleScene, '__init__')
        with (
            _engine_run(mocker),
            command_line(_replay_arguments(golden)),
            pytest.raises(SystemExit) as exit_info,
        ):
            brave_adventurer_modes.main()

        assert exit_info.value.code == ExitCode.SUCCESS
        title_screen.assert_not_called()

    def test_a_recording_of_another_game_is_an_error(self, mocker, caplog):
        """A Mr. Muncher recording: a clear refusal naming both games, not the title screen."""
        title_screen = mocker.spy(TitleScene, '__init__')
        with (
            command_line(_replay_arguments(MR_MUNCHER_GOLDEN)),
            pytest.raises(SystemExit) as exit_info,
        ):
            brave_adventurer_modes.main()

        assert exit_info.value.code == ExitCode.UNUSABLE_INPUT
        title_screen.assert_not_called()
        assert 'games.mr_muncher.game:MrMuncherScene' in caplog.text
        assert logical_name(scene_class=BraveAdventurerScene) in caplog.text
        assert logical_name(scene_class=PapyrusBraveAdventurerScene) in caplog.text

    def test_a_missing_recording_is_refused_by_the_engine(self, mocker, tmp_path):
        """With no header to read, the engine refuses it as it refuses any missing recording."""
        mocker.patch.object(launcher, 'GameEngine', GoldenTraceEngine)
        with (
            _engine_run(mocker),
            command_line(_replay_arguments(tmp_path / 'missing.jsonl.gz')),
            pytest.raises(SystemExit) as exit_info,
        ):
            brave_adventurer_modes.main()

        assert exit_info.value.code == ExitCode.MISSING_INPUT

    @pytest.mark.parametrize('golden', [CLASSIC_GOLDEN, PAPYRUS_GOLDEN], ids=lambda path: path.name)
    def test_both_goldens_replay_through_the_launcher(self, golden):
        """The member's one console script replays both goldens, as the replay plugin runs it."""
        assert recording_console_script(path=golden) == 'brave-adventurer'

        finished = replay_recording_headless(console_script='brave-adventurer', path=golden)

        assert finished.returncode == ExitCode.SUCCESS, finished.stdout


class ChooseThenQuit:
    """A supervisor playing a player on the title screen: Down, Space, then Q in the game."""

    def __init__(self: Self) -> None:
        """Hold the input, frame by frame (posted one frame ahead, as a player's arrives)."""
        self.events_by_frame: dict[int, pygame.event.Event] = {
            2: press(pygame.K_DOWN),
            3: release(pygame.K_DOWN),
            5: press(pygame.K_SPACE),
            6: release(pygame.K_SPACE),
            20: press(pygame.K_q),
        }

    def on_frame(self: Self, *, frame_number: int, scene: Scene | None) -> None:
        """Post the next frame's input (the Supervisor protocol's hook; the scene is unused)."""
        event = self.events_by_frame.get(frame_number + 1)
        if event is not None:
            post_input_event(event)


class TestTheTitleScreen:
    """The title screen offers both games and starts the chosen one in the same engine."""

    def test_the_title_screen_has_its_own_logical_name(self):
        assert logical_name(scene_class=TitleScene) == (
            'games.brave_adventurer_modes.title:TitleScene'
        )

    def test_it_shows_both_games_with_how_each_differs(self, tmp_path):
        with _title_screen(tmp_path) as manager:
            scene = manager.active_scene
            assert isinstance(scene, TitleScene)
            cards = [sprite for sprite in scene.all_sprites if isinstance(sprite, GameChoiceCard)]

            assert [card.choice for card in cards] == list(GAME_CHOICES)
            assert [card.selected for card in cards] == [True, False]
            assert 'code' in GAME_CHOICES[0].description
            assert 'Egyptian' in GAME_CHOICES[1].description
            assert 'sprite-sheet' in GAME_CHOICES[1].description

    @pytest.mark.parametrize(
        ('keys', 'scene_class'),
        [
            ((), BraveAdventurerScene),
            ((pygame.K_DOWN,), PapyrusBraveAdventurerScene),
            ((pygame.K_RIGHT,), PapyrusBraveAdventurerScene),
            ((pygame.K_UP,), PapyrusBraveAdventurerScene),
            ((pygame.K_LEFT,), PapyrusBraveAdventurerScene),
            ((pygame.K_DOWN, pygame.K_DOWN), BraveAdventurerScene),
        ],
        ids=['classic', 'down', 'right', 'up-wraps', 'left-wraps', 'down-down'],
    )
    @pytest.mark.parametrize('choose_key', [pygame.K_SPACE, pygame.K_RETURN])
    def test_choosing_on_the_title_screen_starts_that_game(
        self, tmp_path, keys, scene_class, choose_key
    ):
        with _title_screen(tmp_path) as manager:
            moves = [event for key in keys for event in (press(key), release(key))]
            _run_frames(manager, *moves, press(choose_key))
            # The press only arms the choice: the game starts on its release
            assert isinstance(manager.active_scene, TitleScene)

            _run_frames(manager, release(choose_key))

            assert type(manager.active_scene) is scene_class
            assert manager.active_scene.options is manager.game_engine.OPTIONS

    def test_a_release_without_its_press_on_the_title_screen_chooses_nothing(self, tmp_path):
        with _title_screen(tmp_path) as manager:
            _run_frames(manager, release(pygame.K_SPACE), press(pygame.K_a), release(pygame.K_a))

            assert isinstance(manager.active_scene, TitleScene)

    def test_q_quits_on_its_press(self, tmp_path):
        with _title_screen(tmp_path) as manager:
            _run_frames(manager, press(pygame.K_q))

            assert manager.quit_requested
            assert isinstance(manager.active_scene, TitleScene)

    def test_escape_does_nothing_on_the_title_screen(self, tmp_path):
        """The browser's touch Pause button sends Escape: it must not end the run from here."""
        with _title_screen(tmp_path) as manager:
            _run_frames(manager, press(pygame.K_ESCAPE))
            _run_frames(manager, release(pygame.K_ESCAPE))

            assert not manager.quit_requested
            assert isinstance(manager.active_scene, TitleScene)

    @pytest.mark.parametrize(
        ('input_mode', 'down_type', 'up_type'),
        [
            ('controller', pygame.CONTROLLERBUTTONDOWN, pygame.CONTROLLERBUTTONUP),
            ('joystick', pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP),
        ],
    )
    def test_a_gamepad_chooses_with_the_d_pad_and_a(self, input_mode, down_type, up_type):
        """The engine dispatches an opened pad's buttons to the scene's handlers, as here."""
        _start_display()
        scene = TitleScene(options={'input_mode': input_mode})

        def button(event_type, button_number):
            return HashableEvent(event_type, joy=0, instance_id=0, button=button_number)

        scene_handlers = {
            pygame.CONTROLLERBUTTONDOWN: scene.on_controller_button_down_event,
            pygame.CONTROLLERBUTTONUP: scene.on_controller_button_up_event,
            pygame.JOYBUTTONDOWN: scene.on_joy_button_down_event,
            pygame.JOYBUTTONUP: scene.on_joy_button_up_event,
        }
        for event_type, button_number in (
            (down_type, pygame.CONTROLLER_BUTTON_DPAD_DOWN),
            (up_type, pygame.CONTROLLER_BUTTON_DPAD_DOWN),
            (down_type, pygame.CONTROLLER_BUTTON_A),
        ):
            scene_handlers[event_type](button(event_type, button_number))
        # The press only arms the choice: nothing is switched to yet
        assert scene.next_scene is None

        scene_handlers[up_type](button(up_type, pygame.CONTROLLER_BUTTON_A))

        assert isinstance(scene.next_scene, PapyrusBraveAdventurerScene)

    @pytest.mark.parametrize(
        'quit_button', [pygame.CONTROLLER_BUTTON_B, pygame.CONTROLLER_BUTTON_BACK]
    )
    def test_a_gamepads_b_or_back_quits(self, quit_button):
        _start_display()
        scene = TitleScene(options={'input_mode': 'controller'})
        pygame.event.clear()

        scene.on_controller_button_down_event(
            HashableEvent(pygame.CONTROLLERBUTTONDOWN, instance_id=0, button=quit_button)
        )

        assert [event.type for event in pygame.event.get()] == [pygame.QUIT]

    def test_moving_redraws_both_cards(self):
        _start_display()
        scene = TitleScene(options={'input_mode': 'controller'})
        cards = [sprite for sprite in scene.all_sprites if isinstance(sprite, GameChoiceCard)]
        images_before = [pygame.image.tobytes(card.image, 'RGBA') for card in cards]

        scene.on_controller_button_down_event(
            HashableEvent(
                pygame.CONTROLLERBUTTONDOWN,
                instance_id=0,
                button=pygame.CONTROLLER_BUTTON_DPAD_UP,
            )
        )

        assert [card.selected for card in cards] == [False, True]
        assert [card.dirty for card in cards] == [1, 1]
        assert [pygame.image.tobytes(card.image, 'RGBA') for card in cards] != images_before

    def test_an_unbound_gamepad_button_does_nothing(self):
        _start_display()
        scene = TitleScene(options={'input_mode': 'controller'})
        pygame.event.clear()

        scene.on_controller_button_down_event(
            HashableEvent(
                pygame.CONTROLLERBUTTONDOWN, instance_id=0, button=pygame.CONTROLLER_BUTTON_X
            )
        )
        scene.on_controller_button_up_event(
            HashableEvent(
                pygame.CONTROLLERBUTTONUP, instance_id=0, button=pygame.CONTROLLER_BUTTON_X
            )
        )

        assert [card.selected for card in scene.cards] == [True, False]
        assert scene.next_scene is None
        assert not pygame.event.get(pygame.QUIT)

    def test_the_title_screen_draws_into_the_groups_it_is_given(self):
        _start_display()
        groups = pygame.sprite.LayeredDirty()

        scene = TitleScene(options={}, groups=groups)

        assert scene.all_sprites is groups
        assert set(scene.cards) <= set(groups)

    def test_the_version_flag_still_works(self, mocker, capsys):
        mocker.patch.object(launcher, 'GameEngine', GoldenTraceEngine)
        start = mocker.patch.object(GoldenTraceEngine, 'start')
        for version_flag in ('-v', '--version'):
            with command_line([version_flag]), pytest.raises(SystemExit) as exit_info:
                brave_adventurer_modes.main()

            assert exit_info.value.code == ExitCode.SUCCESS
            assert capsys.readouterr().out == 'Brave Adventurer 1.0\n'
        start.assert_not_called()

    def test_the_help_names_the_game_flag(self, mocker, capsys):
        mocker.patch.object(launcher, 'GameEngine', GoldenTraceEngine)
        with command_line(['--help']), pytest.raises(SystemExit) as exit_info:
            brave_adventurer_modes.main()

        assert exit_info.value.code == ExitCode.SUCCESS
        assert '--game {classic,papyrus}' in capsys.readouterr().out

    def test_without_a_game_or_a_recording_the_title_screen_starts(self, mocker):
        started_games = []

        class RecordingEngine:
            def __init__(self, *, game):
                started_games.append(game)

            def start(self):
                started_games.append('started')

        mocker.patch.object(launcher, 'GameEngine', RecordingEngine)
        with command_line(['--log-level', 'warning']):
            brave_adventurer_modes.main()

        assert started_games == [TitleScene, 'started']

    def test_a_recording_made_from_the_launcher_replays_through_it(self, mocker, tmp_path):
        """It names the title screen first, then the game; the launcher replays it from there.

        The live session gets a fixed dt, as the golden harness's frames do. Measured, each
        frame's dt is wall-clock time (the frame after the switch to the game holds the game's
        construction, 30 ms or so, different on every run), and Papyrus's scarabs bob by the dt
        they accumulate, so every run, on either driver, presented different frames.
        """
        mocker.patch.object(LiveSources, 'frame_seconds', return_value=FRAME_SECONDS)
        recording = tmp_path / 'from-the-title.jsonl.gz'
        with (
            _engine_run(mocker),
            deterministic_environment(save_root=tmp_path / 'saves'),
        ):
            manager = GoldenTraceSceneManager.install()
            with command_line([
                '--windowed',
                '--resolution',
                SCREEN_RESOLUTION,
                '--log-level',
                'warning',
                '--record-trace',
                str(recording),
            ]):
                engine = GoldenTraceEngine(game=TitleScene)
            manager.add_supervisor(supervisor=ChooseThenQuit())
            discard_environment_events()
            engine.start()

        trace = read_trace_result(path=recording).trace
        scenes = [frame['scene'] for frame in trace['frames']]
        assert trace['game'] == logical_name(scene_class=TitleScene)
        assert scenes[0] == TitleScene.__name__
        assert scenes[-1] == PapyrusBraveAdventurerScene.__name__
        assert recorded_game(path=recording) == logical_name(scene_class=TitleScene)
        assert game_for_recording(path=recording) is None

        mocker.patch.object(launcher, 'GameEngine', GoldenTraceEngine)
        with (
            _engine_run(mocker),
            command_line(_replay_arguments(recording)),
            pytest.raises(SystemExit) as exit_info,
        ):
            brave_adventurer_modes.main()

        assert exit_info.value.code == ExitCode.SUCCESS
