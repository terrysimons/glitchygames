"""Tests for the audio engine inside real engine runs: its options, channels, frames and shutdown.

A stand-in game (this module's scenes; the engine never imports a member) runs through the real
engine loop on SDL's dummy drivers (impl spec 4.2, 10.2, 10.3 and 11.0).
"""

import sys
from typing import Any, ClassVar

import pygame
import pytest

from glitchygames.audio import CacheMode, Instrument
from glitchygames.audio.accounting import CompileRecord
from glitchygames.audio.engine import existing_audio_engine
from glitchygames.audio.voices import reserved_channel_count
from glitchygames.engine import GameEngine
from glitchygames.exit_codes import ExitCode
from glitchygames.recording_history import (
    AUDIO_SECONDS_FIELD,
    AUDIO_WORK_FIELD,
    CONTENT_HASH_FIELD,
    MEASUREMENT_FRAME_FIELDS,
    frame_content_hash,
)
from glitchygames.replay.driver import REPLAY_LOCAL_OPTIONS
from glitchygames.replay.tools.golden_traces import GoldenTraceEngine
from glitchygames.scenes import Scene
from glitchygames.tracing import read_trace_result
from tests import demo_runs

ENGINE_ARGUMENTS = ('--resolution', '320x240', '--log-level', 'warning', '--target-fps', '0')
# The frame whose logic asks for a sound no one asked for before (a gameplay compile)
GAMEPLAY_COMPILE_FRAME = 1
QUIT_FRAME = 2


@pytest.fixture
def engine_run_environment(mocker):
    """Let the test construct and start a real engine, leaving pygame usable for later tests.

    Yields:
        None, while the environment is in place.
    """
    yield from demo_runs.engine_run_environment(mocker)


def build_engine(mocker, *, game: type[Scene], extra_arguments: tuple[str, ...] = ()):
    """Construct a real engine for ``game`` on ENGINE_ARGUMENTS plus ``extra_arguments``.

    Returns:
        GoldenTraceEngine: The engine, constructed (not started).
    """
    mocker.patch.object(sys, 'argv', ['test_audio_engine', *ENGINE_ARGUMENTS, *extra_arguments])
    return GoldenTraceEngine(game=game)


class SoundingGame(Scene):
    """A stand-in game: gets the coin in setup, plays it, compiles a new sound, then quits."""

    NAME = 'SoundingGame'
    VERSION = '1.0'
    # This module's package is tests/, so this is tests/audio/fixtures/sounds
    SOUND_DIRECTORY = 'audio/fixtures/sounds'
    # What the run saw, for the test to read after the engine shut down
    seen: ClassVar[dict[str, Any]] = {}

    def __init__(self, options: dict[str, Any] | None = None, groups: Any = None) -> None:
        """Start on frame 0."""
        super().__init__(options=options, groups=groups)
        self.frames_run = 0

    def setup(self) -> None:
        """Get the coin: compiled before the first logic frame, so attributed to setup."""
        self.coin = self.scene_manager.audio.sound('coin')

    def dt_tick(self, dt: float) -> None:
        """Play the coin, get a sound first asked for in gameplay, then quit."""
        super().dt_tick(dt)
        audio = self.scene_manager.audio
        if self.frames_run == 0:
            SoundingGame.seen['handle'] = self.coin.play()
        if self.frames_run == GAMEPLAY_COMPILE_FRAME:
            audio.sound(Instrument(wave='triangle'), pitch='C6')
        if self.frames_run == QUIT_FRAME:
            SoundingGame.seen['compile_log'] = audio.snapshot().compile_log
            SoundingGame.seen['cache_mode'] = audio.snapshot().cache_mode
            SoundingGame.seen['library_channels'] = [
                channel.index for channel in audio.snapshot().channels if channel.group == 'library'
            ]
            self.scene_manager.quit()
        self.frames_run += 1


@pytest.mark.usefixtures('engine_run_environment')
class TestSoundOptions:
    """The options impl spec 10.2 adds to every game."""

    def test_the_sound_options_have_the_spec_defaults(self, mocker):
        build_engine(mocker, game=SoundingGame)

        options = GameEngine.OPTIONS
        assert options['sound_channels'] == 32
        assert options['sound_cache'] == 'ram'
        assert options['sound_cache_memory'] == 256
        assert options['crt_power_on_sound'] == 'on'
        assert options['sound_diagnostics'] is False

    def test_the_sound_options_are_read_as_given(self, mocker):
        build_engine(
            mocker,
            game=SoundingGame,
            extra_arguments=(
                '--sound-channels',
                '12',
                '--sound-cache',
                'none',
                '--sound-cache-memory',
                '64',
                '--crt-power-on-sound',
                'off',
                '--sound-diagnostics',
            ),
        )

        options = GameEngine.OPTIONS
        assert options['sound_channels'] == 12
        assert options['sound_cache'] == 'none'
        assert options['sound_cache_memory'] == 64
        assert options['crt_power_on_sound'] == 'off'
        assert options['sound_diagnostics'] is True

    def test_disk_cache_option_is_refused_until_m3(self, mocker, caplog):
        with pytest.raises(SystemExit) as exit_information:
            build_engine(mocker, game=SoundingGame, extra_arguments=('--sound-cache', 'disk'))

        assert exit_information.value.code == ExitCode.OPTIONS_REFUSED
        assert 'arrives in M3' in caplog.text

    def test_the_channels_are_partitioned_from_the_options(self, mocker):
        engine = build_engine(
            mocker,
            game=quiet_game(),
            extra_arguments=('--live-voice-pool', '2', '--sound-channels', '12'),
        )

        engine.start()

        assert engine.live_voice_channels == (0, 1)
        assert engine.channel_partition.live == (0, 1)
        assert engine.channel_partition.library == tuple(range(2, 14))
        assert engine.channel_partition.legacy_count >= 8


def test_sound_cache_is_replay_local():
    """A recording replays under any cache mode, and diagnostics are the watcher's choice."""
    assert {'sound_cache', 'sound_diagnostics'} <= REPLAY_LOCAL_OPTIONS


def test_the_audio_measurements_never_enter_a_content_hash():
    """Both fields are measurements (recording_history.MEASUREMENT_FRAME_FIELDS)."""
    assert {AUDIO_SECONDS_FIELD, AUDIO_WORK_FIELD} <= MEASUREMENT_FRAME_FIELDS


@pytest.mark.usefixtures('engine_run_environment')
class TestARecordedRun:
    """A recorded run of the stand-in game, start to shutdown."""

    @pytest.fixture
    def recorded_frames(self, mocker, tmp_path):
        """Run the stand-in game under --record-trace with cache ``ram`` and 12 library channels.

        Returns:
            The recorded frames.
        """
        SoundingGame.seen.clear()
        path = tmp_path / 'run.jsonl.gz'
        engine = build_engine(
            mocker,
            game=SoundingGame,
            extra_arguments=('--record-trace', str(path), '--sound-channels', '12'),
        )
        engine.start()
        return read_trace_result(path=path).trace['frames']

    def test_recorded_frames_carry_audio_seconds_and_work_as_measurements(self, recorded_frames):
        setup_frame, gameplay_compile_frame, quit_frame = recorded_frames

        # Setup ran before frame 0, so its compile is frame 0's work
        assert [entry[:2] for entry in setup_frame[AUDIO_WORK_FIELD]] == [['compile', 'coin']]
        # The total is rounded to the microsecond, each piece truncated to it: within 2 microseconds
        assert setup_frame[AUDIO_SECONDS_FIELD] == pytest.approx(
            setup_frame[AUDIO_WORK_FIELD][0][2] / 1_000_000, abs=2e-6
        )
        ((kind, name, microseconds),) = gameplay_compile_frame[AUDIO_WORK_FIELD]
        assert (kind, name.startswith('instrument-'), microseconds > 0) == ('compile', True, True)
        # A frame without audio work carries neither field
        assert AUDIO_SECONDS_FIELD not in quit_frame
        assert AUDIO_WORK_FIELD not in quit_frame
        # Measurements stay out of the content hash
        for frame in recorded_frames:
            assert frame[CONTENT_HASH_FIELD] == [frame_content_hash(frame_record=frame)]

    def test_compiles_are_attributed_to_setup_or_their_frame(self, recorded_frames):
        del recorded_frames
        setup_record, gameplay_record = SoundingGame.seen['compile_log']

        assert setup_record == CompileRecord(
            frame_number=0,
            name='coin',
            milliseconds=setup_record.milliseconds,
            during_setup=True,
        )
        assert gameplay_record.frame_number == GAMEPLAY_COMPILE_FRAME
        assert gameplay_record.during_setup is False

    def test_the_engine_uses_the_options_cache_and_channels(self, recorded_frames):
        del recorded_frames

        assert SoundingGame.seen['cache_mode'] is CacheMode.RAM
        assert SoundingGame.seen['library_channels'] == list(range(4, 16))

    def test_shutdown_closes_the_audio_engine(self, recorded_frames):
        del recorded_frames

        assert existing_audio_engine() is None
        assert SoundingGame.seen['handle'].is_playing is False

    def test_shutdown_gives_the_channel_reservation_back(self, recorded_frames):
        del recorded_frames
        # A mixer started again in this process (SDL keeps a reservation across a restart)
        pygame.mixer.quit()
        pygame.mixer.init()

        assert reserved_channel_count() == 0
        assert pygame.mixer.Sound(buffer=bytes(4 * 44100)).play() is not None


@pytest.mark.usefixtures('engine_run_environment')
def test_a_run_without_sound_makes_no_audio_engine(mocker):
    """A game that never asks for audio never makes an audio engine."""
    build_engine(mocker, game=quiet_game()).start()

    assert existing_audio_engine() is None


def quiet_game() -> type[Scene]:
    """A game that quits in its first frame without asking for audio.

    Returns:
        A new scene class.
    """
    return type('QuietGame', (Scene,), {'NAME': 'QuietGame', 'dt_tick': _quit_at_once})


def _quit_at_once(scene: Scene, dt: float) -> None:
    """A dt_tick that quits."""
    del dt
    scene.scene_manager.quit()
