"""Step back by restarting a watched replay (glitchygames/replay/rebuild.py)."""

from __future__ import annotations

import argparse
import sys
import textwrap
import wave
from pathlib import Path
from types import SimpleNamespace

import pygame
import pytest

from glitchygames.debug import DebugPanel
from glitchygames.engine import GameEngine
from glitchygames.exit_codes import ExitCode
from glitchygames.replay import rebuild
from glitchygames.replay.rebuild import (
    REBUILD_PROGRESS_INTERVAL_SECONDS,
    REBUILD_PROGRESS_PRINT_INTERVAL_SECONDS,
    RESTART_HANDOFF_OPTION,
    VIEWER_STATE_OPTION,
    Rebuild,
    RestartHandoff,
    ViewerState,
    relaunch_replay,
    restart_command,
)
from glitchygames.replay.silence import FrameSilencer

# How long the real child processes of the end-to-end restart test may run
CHILD_TIMEOUT_SECONDS = 120.0


def parsed_engine_options(*, arguments: list[str]) -> dict[str, object]:
    """Parse arguments with the engine's own options, as a game would.

    Returns:
        The parsed options.

    """
    parser = argparse.ArgumentParser()
    GameEngine.args(parser)
    return vars(parser.parse_args(arguments))


class TestRestartCommand:
    """The command a restart runs: the original one, at a new pause frame."""

    def test_restart_command_replaces_the_pause_frame(self):
        command = restart_command(
            original=[
                'python',
                'game.py',
                '--replay-trace',
                'a.jsonl.gz',
                '--replay-pause-at-frame',
                '5',
            ],
            recording_path=Path('b.jsonl.gz'),
            pause_at_frame=9,
            debug_overlay_visible=False,
        )
        assert command == [
            'python',
            'game.py',
            '--no-debug-overlay',
            '--replay-trace',
            'b.jsonl.gz',
            '--replay-pause-at-frame',
            '9',
        ]

    def test_every_other_option_is_kept_in_order(self):
        command = restart_command(
            original=[
                'python',
                '-X',
                'dev',
                'game.py',
                '--replay-fps',
                'real',
                '--replay-trace=a.jsonl.gz',
                '--windowed',
            ],
            recording_path=Path('a.jsonl.gz'),
            pause_at_frame=3,
            debug_overlay_visible=True,
        )
        assert command == [
            'python',
            '-X',
            'dev',
            'game.py',
            '--replay-fps',
            'real',
            '--windowed',
            '--debug-overlay',
            '--replay-trace',
            'a.jsonl.gz',
            '--replay-pause-at-frame',
            '3',
        ]

    @pytest.mark.parametrize(
        ('original_flags', 'visible'),
        [
            ((), True),
            (('--debug-overlay',), False),
            (('--no-debug-overlay',), True),
            # An abbreviation argparse accepts (--debug alone is ambiguous since --debug-events)
            (('--debug-o',), False),
        ],
        ids=['shown', 'hidden', 'shown_after_hidden', 'abbreviated'],
    )
    def test_the_debug_overlay_is_always_named_and_wins(self, original_flags, visible):
        command = restart_command(
            original=['python', 'game.py', *original_flags, '--replay-trace', 'a.jsonl.gz'],
            recording_path=Path('a.jsonl.gz'),
            pause_at_frame=3,
            debug_overlay_visible=visible,
        )
        assert command[-5] == ('--debug-overlay' if visible else '--no-debug-overlay')
        assert parsed_engine_options(arguments=command[2:])['debug_overlay'] is visible

    @pytest.mark.parametrize(
        'trace_arguments',
        [('--replay-trace', 'a.jsonl.gz'), ('--replay-trace=a.jsonl.gz',)],
        ids=['separate_value', 'equals_form'],
    )
    def test_switching_to_the_bookmarked_copy_replaces_either_form(self, trace_arguments):
        command = restart_command(
            original=['python', 'game.py', *trace_arguments],
            recording_path=Path('a.bookmarked.jsonl.gz'),
            pause_at_frame=4,
            debug_overlay_visible=False,
        )
        assert not any(argument.startswith('--replay-trace=') for argument in command)
        assert command.count('--replay-trace') == 1
        assert parsed_engine_options(arguments=command[2:])['replay_trace'] == (
            'a.bookmarked.jsonl.gz'
        )

    def test_appended_options_go_before_a_bare_double_dash(self):
        command = restart_command(
            original=['python', 'game.py', '--replay-trace', 'a.jsonl.gz', '--', '--replay-trace'],
            recording_path=Path('b.jsonl.gz'),
            pause_at_frame=2,
            debug_overlay_visible=False,
        )
        assert command == [
            'python',
            'game.py',
            '--no-debug-overlay',
            '--replay-trace',
            'b.jsonl.gz',
            '--replay-pause-at-frame',
            '2',
            '--',
            '--replay-trace',
        ]

    def test_the_viewer_state_is_carried_and_parsed_back(self):
        viewer_state = ViewerState(speed=4.0, debug_panel=DebugPanel.CAMERA, divergence_frame=42)
        command = restart_command(
            original=['python', 'game.py', VIEWER_STATE_OPTION, '{"speed": 2.0}'],
            recording_path=Path('a.jsonl.gz'),
            pause_at_frame=3,
            debug_overlay_visible=True,
            viewer_state=viewer_state,
        )
        assert command.count(VIEWER_STATE_OPTION) == 1
        options = parsed_engine_options(arguments=command[2:])
        assert options['replay_viewer_state'] == viewer_state

    def test_a_viewer_state_out_of_range_is_refused(self):
        with pytest.raises(ValueError, match='speed'):
            ViewerState(speed=100.0)


def completed(*, returncode: int) -> SimpleNamespace:
    """Stand in for a finished child process (``run_command``'s result) with ``returncode``.

    Returns:
        The process's stand-in.

    """
    return SimpleNamespace(returncode=returncode)


def handoff_path_of(*, command: list[str]) -> Path:
    """Return the handoff file a supervised child's command names.

    Returns:
        The path.

    """
    return Path(command[command.index(RESTART_HANDOFF_OPTION) + 1])


class TestRelaunch:
    """The restart: a supervised child hands its command over; the first process supervises."""

    def test_a_supervised_replay_hands_its_restart_to_the_supervisor(self, mocker, tmp_path):
        run_spy = mocker.patch.object(rebuild, 'run_command')
        replace_spy = mocker.spy(Path, 'replace')
        handoff_path = tmp_path / 'restart.json'
        status = relaunch_replay(
            command=['python', 'game.py', '--replay-pause-at-frame', '4'],
            handoff_path=handoff_path,
            result_exit_code=ExitCode.REPLAY_DIVERGED,
        )
        assert status == ExitCode.SUCCESS
        run_spy.assert_not_called()
        # Written whole, then moved into place
        replace_spy.assert_called_once()
        assert RestartHandoff.model_validate_json(
            handoff_path.read_text(encoding='utf-8')
        ) == RestartHandoff(
            command=['python', 'game.py', '--replay-pause-at-frame', '4'],
            result_exit_code=ExitCode.REPLAY_DIVERGED,
        )
        assert list(tmp_path.iterdir()) == [handoff_path]

    def test_the_first_replay_runs_each_restart_until_one_ends(self, mocker):
        commands_run: list[list[str]] = []

        def fake_run(*, command, environment, timeout_seconds):
            assert timeout_seconds is None
            assert environment
            commands_run.append(list(command))
            if len(commands_run) == 1:
                # The child steps back again: it hands its next command over (built from its
                # own command line, which names the handoff file) and ends
                handoff_path = handoff_path_of(command=command)
                handed_over = RestartHandoff(
                    command=[
                        command[0],
                        'game.py',
                        RESTART_HANDOFF_OPTION,
                        str(handoff_path),
                        '--replay-pause-at-frame',
                        '2',
                    ],
                    result_exit_code=ExitCode.SUCCESS,
                )
                handoff_path.write_text(handed_over.model_dump_json(), encoding='utf-8')
                return completed(returncode=ExitCode.SUCCESS)
            return completed(returncode=ExitCode.SUCCESS)

        mocker.patch.object(rebuild, 'run_command', side_effect=fake_run)
        status = relaunch_replay(
            command=['python', 'game.py', '--replay-pause-at-frame', '4'],
            handoff_path=None,
            result_exit_code=ExitCode.SUCCESS,
        )
        assert status == ExitCode.SUCCESS
        first_command, second_command = commands_run
        handoff = first_command[-1]
        # This interpreter runs each child; the handoff file is named once
        assert first_command == [
            sys.executable,
            'game.py',
            '--replay-pause-at-frame',
            '4',
            RESTART_HANDOFF_OPTION,
            handoff,
        ]
        assert second_command == [
            sys.executable,
            'game.py',
            '--replay-pause-at-frame',
            '2',
            RESTART_HANDOFF_OPTION,
            handoff,
        ]
        # The handoff directory is removed afterwards
        assert not Path(handoff).parent.exists()

    @pytest.mark.parametrize(
        ('first_result', 'handed_over_result', 'last_status', 'expected'),
        [
            (
                ExitCode.REPLAY_DIVERGED,
                ExitCode.SUCCESS,
                ExitCode.SUCCESS,
                ExitCode.REPLAY_DIVERGED,
            ),
            (
                ExitCode.SUCCESS,
                ExitCode.REPLAY_DIVERGED,
                ExitCode.SUCCESS,
                ExitCode.REPLAY_DIVERGED,
            ),
            (
                ExitCode.SUCCESS,
                ExitCode.SUCCESS,
                ExitCode.REPLAY_DIVERGED,
                ExitCode.REPLAY_DIVERGED,
            ),
            (
                ExitCode.REPLAY_DIVERGED,
                ExitCode.SUCCESS,
                ExitCode.INTERNAL_ERROR,
                ExitCode.INTERNAL_ERROR,
            ),
            (ExitCode.SUCCESS, ExitCode.SUCCESS, ExitCode.SUCCESS, ExitCode.SUCCESS),
        ],
        ids=[
            'first_run_diverged',
            'a_restart_diverged',
            'last_run_diverged',
            'last_run_failed',
            'all_matched',
        ],
    )
    def test_a_divergence_in_any_run_is_kept(
        self, mocker, first_result, handed_over_result, last_status, expected
    ):
        commands_run: list[list[str]] = []

        def fake_run(*, command, environment, timeout_seconds):
            del environment, timeout_seconds
            commands_run.append(list(command))
            if len(commands_run) == 1:
                # The first restart steps back again, handing its own result over
                handoff = RestartHandoff(command=command, result_exit_code=handed_over_result)
                handoff_path_of(command=command).write_text(
                    handoff.model_dump_json(), encoding='utf-8'
                )
                return completed(returncode=ExitCode.SUCCESS)
            return completed(returncode=last_status)

        mocker.patch.object(rebuild, 'run_command', side_effect=fake_run)
        status = relaunch_replay(
            command=['python', 'game.py'], handoff_path=None, result_exit_code=first_result
        )
        assert status == expected

    def test_a_child_killed_by_a_signal_exits_as_a_shell_reports_it(self, mocker):
        mocker.patch.object(rebuild, 'run_command', return_value=completed(returncode=-15))
        status = relaunch_replay(
            command=['python', 'game.py'], handoff_path=None, result_exit_code=ExitCode.SUCCESS
        )
        assert status == 128 + 15

    def test_ctrl_c_while_supervising_is_interrupted(self, mocker):
        mocker.patch.object(rebuild, 'run_command', side_effect=KeyboardInterrupt)
        status = relaunch_replay(
            command=['python', 'game.py'], handoff_path=None, result_exit_code=ExitCode.SUCCESS
        )
        assert status == ExitCode.INTERRUPTED

    def test_a_signal_while_supervising_ends_it_and_cleans_up(self, mocker):
        """The engine's signal handler raises SystemExit; subprocess.run kills the child."""
        handoff_directories: list[Path] = []

        def interrupted_run(*, command, environment, timeout_seconds):
            del environment, timeout_seconds
            handoff_directories.append(handoff_path_of(command=command).parent)
            raise SystemExit(ExitCode.TERMINATED)

        mocker.patch.object(rebuild, 'run_command', side_effect=interrupted_run)
        with pytest.raises(SystemExit) as exit_info:
            relaunch_replay(
                command=['python', 'game.py'], handoff_path=None, result_exit_code=ExitCode.SUCCESS
            )
        assert exit_info.value.code == ExitCode.TERMINATED
        assert not handoff_directories[0].exists()

    @pytest.mark.parametrize(
        'handoff_text',
        ['{not json', '["python", "game.py"]', '{"command": [], "result_exit_code": 0}'],
        ids=['not_json', 'not_an_object', 'empty_command'],
    )
    def test_an_unreadable_handoff_is_an_internal_error(self, mocker, caplog, handoff_text):
        def fake_run(*, command, environment, timeout_seconds):
            del environment, timeout_seconds
            handoff_path_of(command=command).write_text(handoff_text, encoding='utf-8')
            return completed(returncode=ExitCode.SUCCESS)

        mocker.patch.object(rebuild, 'run_command', side_effect=fake_run)
        status = relaunch_replay(
            command=['python', 'game.py'], handoff_path=None, result_exit_code=ExitCode.SUCCESS
        )
        assert status == ExitCode.INTERNAL_ERROR
        assert 'Cannot restart the replay: the restart handoff' in caplog.text

    def test_a_handoff_that_is_not_text_is_an_internal_error(self, mocker, caplog):
        def fake_run(*, command, environment, timeout_seconds):
            del environment, timeout_seconds
            handoff_path_of(command=command).write_bytes(b'\xff\xfe\xfa')
            return completed(returncode=ExitCode.SUCCESS)

        mocker.patch.object(rebuild, 'run_command', side_effect=fake_run)
        status = relaunch_replay(
            command=['python', 'game.py'], handoff_path=None, result_exit_code=ExitCode.SUCCESS
        )
        assert status == ExitCode.INTERNAL_ERROR
        assert 'Cannot restart the replay: the restart handoff' in caplog.text

    def test_a_handoff_that_cannot_be_written_is_an_internal_error(self, tmp_path, caplog):
        """Not exit 1, which the supervisor would read as a divergence."""
        status = relaunch_replay(
            command=['python', 'game.py'],
            handoff_path=tmp_path / 'missing-directory' / 'restart.json',
            result_exit_code=ExitCode.SUCCESS,
        )
        assert status == ExitCode.INTERNAL_ERROR
        assert 'Cannot hand the restart over' in caplog.text

    def test_a_child_that_cannot_start_is_an_internal_error(self, mocker, caplog):
        mocker.patch.object(rebuild, 'run_command', side_effect=OSError('no such interpreter'))
        status = relaunch_replay(
            command=['python', 'game.py'], handoff_path=None, result_exit_code=ExitCode.SUCCESS
        )
        assert status == ExitCode.INTERNAL_ERROR
        assert 'no such interpreter' in caplog.text

    def test_real_children_hand_their_restarts_over(self, tmp_path):
        """End to end: run_command starts real children, which write real handoffs."""
        child_script = tmp_path / 'child.py'
        child_script.write_text(
            textwrap.dedent("""\
                import sys
                from pathlib import Path

                from glitchygames.replay.rebuild import RESTART_HANDOFF_OPTION, relaunch_replay

                arguments = sys.argv[1:]
                handoff = Path(arguments[arguments.index(RESTART_HANDOFF_OPTION) + 1])
                runs = Path(arguments[0])
                with runs.open('a', encoding='utf-8') as runs_file:
                    runs_file.write(arguments[1] + '\\n')
                if arguments[1] == 'first':
                    # Steps back after diverging: hands the next run over
                    raise SystemExit(relaunch_replay(
                        command=[sys.executable, sys.argv[0], arguments[0], 'second'],
                        handoff_path=handoff,
                        result_exit_code=1,
                    ))
                raise SystemExit(0)
            """),
            encoding='utf-8',
        )
        runs_path = tmp_path / 'runs.txt'
        status = relaunch_replay(
            command=[sys.executable, str(child_script), str(runs_path), 'first'],
            handoff_path=None,
            result_exit_code=ExitCode.SUCCESS,
        )
        assert runs_path.read_text(encoding='utf-8').split() == ['first', 'second']
        # The first child diverged before it stepped back: the run reports it
        assert status == ExitCode.REPLAY_DIVERGED


class TestRebuildProgress:
    """The rebuild's progress, by real time: shown every 0.1 s, printed every second."""

    def test_progress_is_due_by_real_time_and_printed_less_often(self, capsys):
        progress = Rebuild(target_frame=1000)
        # One frame every 0.025 s for 2.5 s, asked twice per frame
        due_frames = [
            frame_index
            for frame_index in range(100)
            for _ in range(2)
            if progress.progress_is_due(frame_index=frame_index, now=10.0 + frame_index * 0.025)
        ]
        expected_count = round(2.5 / REBUILD_PROGRESS_INTERVAL_SECONDS)
        assert abs(len(due_frames) - expected_count) <= 1
        assert len(set(due_frames)) == len(due_frames)
        printed = capsys.readouterr().out.splitlines()
        assert abs(len(printed) - round(2.5 / REBUILD_PROGRESS_PRINT_INTERVAL_SECONDS)) <= 1
        assert all(line.startswith('Rebuilding: frame ') for line in printed)
        assert printed[0].endswith(' / 1000')

    def test_nothing_is_due_at_the_start(self):
        progress = Rebuild(target_frame=10)
        assert not progress.progress_is_due(frame_index=0, now=5.0)


@pytest.fixture
def dummy_mixer():
    """Start the mixer on SDL's dummy audio driver (the test suite's), and stop it after.

    Yields:
        Nothing.

    """
    was_started = pygame.mixer.get_init() is not None
    if not was_started:
        pygame.mixer.init()
    yield
    pygame.mixer.music.stop()
    pygame.mixer.stop()
    if not was_started:
        pygame.mixer.quit()


def write_silent_wave(*, path: Path) -> None:
    """Write one second of 16-bit stereo silence as a WAV file (for pygame.mixer.music)."""
    frequency, _, channels = pygame.mixer.get_init()
    with wave.open(str(path), 'wb') as wave_file:
        wave_file.setnchannels(channels)
        wave_file.setsampwidth(2)
        wave_file.setframerate(frequency)
        wave_file.writeframes(bytes(2 * channels * frequency))


class TestRebuildSilence:
    """The rebuild runs silent on a real mixer: Sound.play() resets a channel's volume."""

    def test_sounds_played_in_a_rebuild_frame_are_stopped_after_it(self, dummy_mixer):
        sound = pygame.mixer.Sound(buffer=bytes(4 * 44100))
        progress = Rebuild(target_frame=10)
        sound.play()
        assert pygame.mixer.get_busy()
        progress.silence_frame()
        assert not pygame.mixer.get_busy()

    def test_music_is_paused_for_the_rebuild_and_resumed_after(self, dummy_mixer, tmp_path):
        music_path = tmp_path / 'music.wav'
        write_silent_wave(path=music_path)
        pygame.mixer.music.load(str(music_path))
        pygame.mixer.music.play(loops=-1)
        progress = Rebuild(target_frame=10)
        progress.silence_frame()
        assert not pygame.mixer.music.get_busy()
        progress.silence_frame()
        progress.finish()
        assert pygame.mixer.music.get_busy()

    def test_music_not_paused_by_the_rebuild_is_left_alone(self, dummy_mixer, mocker):
        unpause = mocker.spy(pygame.mixer.music, 'unpause')
        progress = Rebuild(target_frame=10)
        progress.silence_frame()
        progress.finish()
        unpause.assert_not_called()

    def test_music_the_game_paused_during_the_rebuild_stays_paused(self, dummy_mixer, tmp_path):
        music_path = tmp_path / 'music.wav'
        write_silent_wave(path=music_path)
        pygame.mixer.music.load(str(music_path))
        pygame.mixer.music.play(loops=-1)
        original_pause = pygame.mixer.music.pause
        progress = Rebuild(target_frame=10)
        progress.begin()
        progress.silence_frame()  # the rebuild pauses it
        pygame.mixer.music.unpause()  # a frame's game code resumes it...
        pygame.mixer.music.pause()  # ...and a later one pauses it itself
        progress.silence_frame()
        progress.finish()
        assert not pygame.mixer.music.get_busy()
        # The game's own music calls are no longer followed
        assert pygame.mixer.music.pause is original_pause

    def test_music_the_game_resumed_during_the_rebuild_plays_on(self, dummy_mixer, tmp_path):
        music_path = tmp_path / 'music.wav'
        write_silent_wave(path=music_path)
        pygame.mixer.music.load(str(music_path))
        pygame.mixer.music.play(loops=-1)
        progress = Rebuild(target_frame=10)
        progress.begin()
        pygame.mixer.music.pause()
        pygame.mixer.music.unpause()
        progress.silence_frame()
        progress.finish()
        assert pygame.mixer.music.get_busy()

    def test_without_a_mixer_nothing_happens(self, mocker):
        mocker.patch.object(pygame.mixer, 'get_init', return_value=None)
        stop = mocker.patch.object(pygame.mixer, 'stop')
        progress = Rebuild(target_frame=10)
        progress.silence_frame()
        progress.finish()
        stop.assert_not_called()


class TestFrameSilencer:
    """The silence an instant replay's fast-forward shares with the rebuild."""

    def test_sounds_playing_at_the_start_play_on_and_new_ones_are_stopped(self, dummy_mixer):
        live_sound = pygame.mixer.Sound(buffer=bytes(4 * 44100))
        live_channel = live_sound.play()
        assert live_channel is not None
        silencer = FrameSilencer(spares_playing_sounds=True)
        silencer.begin()
        new_channel = pygame.mixer.Sound(buffer=bytes(4 * 44100)).play()
        assert new_channel is not None
        silencer.silence_frame()
        assert live_channel.get_busy()
        assert not new_channel.get_busy()
        silencer.finish()

    def test_a_spared_channel_playing_something_else_is_stopped(self, dummy_mixer):
        live_channel = pygame.mixer.Sound(buffer=bytes(4 * 44100)).play()
        assert live_channel is not None
        silencer = FrameSilencer(spares_playing_sounds=True)
        silencer.begin()
        live_channel.play(pygame.mixer.Sound(buffer=bytes(4 * 44100)))
        silencer.silence_frame()
        assert not live_channel.get_busy()
        silencer.finish()

    def test_without_sparing_every_sound_is_stopped(self, dummy_mixer):
        live_channel = pygame.mixer.Sound(buffer=bytes(4 * 44100)).play()
        assert live_channel is not None
        silencer = FrameSilencer()
        silencer.begin()
        silencer.silence_frame()
        assert not live_channel.get_busy()
        silencer.finish()

    @pytest.mark.parametrize('first_to_stop', [0, 1], ids=['outer-first', 'inner-first'])
    def test_stacked_silencers_give_pygame_its_own_music_controls_back(self, first_to_stop):
        pygame_pause, pygame_unpause = pygame.mixer.music.pause, pygame.mixer.music.unpause
        silencers = [FrameSilencer(), FrameSilencer()]
        for silencer in silencers:
            silencer.begin()
        silencers[first_to_stop].stop_following_music()
        silencers[1 - first_to_stop].stop_following_music()
        assert pygame.mixer.music.pause is pygame_pause
        assert pygame.mixer.music.unpause is pygame_unpause

    def test_an_unpause_set_over_the_wrappers_is_kept_and_pause_still_restored(self, mocker):
        """Each control is given back only while still the silencer's wrapper."""
        pygame_pause, pygame_unpause = pygame.mixer.music.pause, pygame.mixer.music.unpause
        silencer = FrameSilencer()
        silencer.begin()
        game_unpause = mocker.Mock()
        mocker.patch.object(pygame.mixer.music, 'unpause', game_unpause)
        silencer.stop_following_music()
        assert pygame.mixer.music.pause is pygame_pause
        assert pygame.mixer.music.unpause is game_unpause
        # mocker puts pygame's own unpause back after the test
        assert pygame_unpause is not game_unpause

    def test_stacked_silencers_both_see_the_games_music_pause(self, dummy_mixer, tmp_path):
        music_path = tmp_path / 'music.wav'
        write_silent_wave(path=music_path)
        pygame.mixer.music.load(str(music_path))
        pygame.mixer.music.play(loops=-1)
        outer, inner = FrameSilencer(), FrameSilencer()
        outer.begin()
        inner.begin()
        outer.silence_frame()
        inner.silence_frame()
        pygame.mixer.music.pause()
        # The game paused the music itself: neither silencer resumes it
        inner.finish()
        outer.finish()
        assert not pygame.mixer.music.get_busy()
