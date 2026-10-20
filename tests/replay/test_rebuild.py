"""Step back by restarting a watched replay (glitchygames/replay/rebuild.py)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pygame
import pytest

from glitchygames.exit_codes import ExitCode
from glitchygames.replay import rebuild
from glitchygames.replay.rebuild import (
    FAST_FORWARD_PROGRESS_INTERVAL_FRAMES,
    RESTART_HANDOFF_OPTION,
    MixerMute,
    Rebuild,
    relaunch_replay,
    restart_command,
)


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
        )
        assert command == [
            'python',
            'game.py',
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
        )
        assert command == [
            'python',
            '-X',
            'dev',
            'game.py',
            '--replay-fps',
            'real',
            '--windowed',
            '--replay-trace',
            'a.jsonl.gz',
            '--replay-pause-at-frame',
            '3',
        ]

    @pytest.mark.parametrize(
        ('original_flags', 'visible', 'expected_flags'),
        [
            ((), True, ('--debug-overlay',)),
            (('--debug-overlay',), False, ()),
            (('--debug-overlay',), True, ('--debug-overlay',)),
            (('--debug-overlay',), None, ('--debug-overlay',)),
        ],
        ids=['shown', 'hidden', 'still_shown', 'left_as_given'],
    )
    def test_the_debug_overlay_is_carried_over(self, original_flags, visible, expected_flags):
        command = restart_command(
            original=['python', 'game.py', *original_flags, '--replay-trace', 'a.jsonl.gz'],
            recording_path=Path('a.jsonl.gz'),
            pause_at_frame=3,
            debug_overlay_visible=visible,
        )
        assert command == [
            'python',
            'game.py',
            *expected_flags,
            '--replay-trace',
            'a.jsonl.gz',
            '--replay-pause-at-frame',
            '3',
        ]


def completed(*, returncode: int) -> SimpleNamespace:
    """Stand in for a finished child process (``run_command``'s result) with ``returncode``.

    Returns:
        The process's stand-in.

    """
    return SimpleNamespace(returncode=returncode)


class TestRelaunch:
    """The restart: a supervised child hands its command over; the first process supervises."""

    def test_a_supervised_replay_hands_its_restart_to_the_supervisor(self, mocker, tmp_path):
        run_spy = mocker.patch.object(rebuild, 'run_command')
        handoff_path = tmp_path / 'restart.json'
        status = relaunch_replay(
            command=['python', 'game.py', '--replay-pause-at-frame', '4'],
            handoff_path=handoff_path,
        )
        assert status == ExitCode.SUCCESS
        run_spy.assert_not_called()
        assert json.loads(handoff_path.read_text(encoding='utf-8')) == [
            'python',
            'game.py',
            '--replay-pause-at-frame',
            '4',
        ]

    def test_the_first_replay_runs_each_restart_until_one_ends(self, mocker):
        commands_run: list[list[str]] = []

        def fake_run(*, command, environment, timeout_seconds):
            assert timeout_seconds is None
            assert environment
            commands_run.append(list(command))
            if len(commands_run) == 1:
                # The child steps back again: it hands its next command over and ends
                # (as restart_command builds it from the child's own command line, which names
                # the handoff file)
                handoff = command[command.index(RESTART_HANDOFF_OPTION) + 1]
                handed_over = [
                    command[0],
                    'game.py',
                    RESTART_HANDOFF_OPTION,
                    handoff,
                    '--replay-pause-at-frame',
                    '2',
                ]
                Path(handoff).write_text(json.dumps(handed_over), encoding='utf-8')
                return completed(returncode=ExitCode.SUCCESS)
            return completed(returncode=ExitCode.REPLAY_DIVERGED)

        mocker.patch.object(rebuild, 'run_command', side_effect=fake_run)
        status = relaunch_replay(
            command=['python', 'game.py', '--replay-pause-at-frame', '4'], handoff_path=None
        )
        assert status == ExitCode.REPLAY_DIVERGED
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

    def test_a_child_killed_by_a_signal_exits_as_a_shell_reports_it(self, mocker):
        mocker.patch.object(rebuild, 'run_command', return_value=completed(returncode=-15))
        assert relaunch_replay(command=['python', 'game.py'], handoff_path=None) == 128 + 15

    def test_ctrl_c_while_supervising_is_interrupted(self, mocker):
        mocker.patch.object(rebuild, 'run_command', side_effect=KeyboardInterrupt)
        status = relaunch_replay(command=['python', 'game.py'], handoff_path=None)
        assert status == ExitCode.INTERRUPTED


class TestRebuildProgress:
    """The rebuild's progress, every FAST_FORWARD_PROGRESS_INTERVAL_FRAMES frames."""

    def test_progress_is_due_once_per_interval_and_printed(self, capsys):
        progress = Rebuild(target_frame=130)
        due = [
            frame_index
            for frame_index in range(131)
            for _ in range(2)  # asked twice per frame: due once
            if progress.progress_is_due(frame_index=frame_index)
        ]
        assert due == [
            FAST_FORWARD_PROGRESS_INTERVAL_FRAMES,
            2 * FAST_FORWARD_PROGRESS_INTERVAL_FRAMES,
        ]
        assert capsys.readouterr().out == (
            'Rebuilding: frame 60 / 130\nRebuilding: frame 120 / 130\n'
        )


class TestMixerMute:
    """The rebuild runs silent; its sounds are cut off when it ends."""

    def test_mute_zeroes_every_channel_and_unmute_restores_them(self, mocker):
        mocker.patch.object(pygame.mixer, 'get_init', return_value=(44100, -16, 2))
        mocker.patch.object(pygame.mixer, 'get_num_channels', return_value=2)
        stop = mocker.patch.object(pygame.mixer, 'stop')
        channels = [mocker.Mock(), mocker.Mock()]
        channels[0].get_volume.return_value = 1.0
        channels[1].get_volume.return_value = 0.5
        mocker.patch.object(pygame.mixer, 'Channel', side_effect=lambda index: channels[index])
        mute = MixerMute()
        mute.mute()
        mute.mute()  # once only: the volumes kept are the game's
        for channel in channels:
            channel.set_volume.assert_called_once_with(0.0)
        mute.unmute()
        stop.assert_called_once_with()
        assert channels[0].set_volume.call_args_list[-1].args == (1.0,)
        assert channels[1].set_volume.call_args_list[-1].args == (0.5,)
        mute.unmute()
        stop.assert_called_once_with()

    def test_without_a_mixer_nothing_happens(self, mocker):
        mocker.patch.object(pygame.mixer, 'get_init', return_value=None)
        channel = mocker.patch.object(pygame.mixer, 'Channel')
        mute = MixerMute()
        mute.mute()
        mute.unmute()
        channel.assert_not_called()
