"""Tests for the audio engine inside real engine runs: its options, channels, frames and shutdown.

A stand-in game (this module's scenes; the engine never imports a member) runs through the real
engine loop on SDL's dummy drivers (impl spec 4.2, 10.2, 10.3 and 11.0).
"""

import logging
import sys
from typing import Any, ClassVar

import pygame
import pytest

from glitchygames.audio import CacheMode, Instrument
from glitchygames.audio import voices as voices_module
from glitchygames.audio.accounting import CompileRecord
from glitchygames.audio.effects import Effect, Tone
from glitchygames.audio.engine import AudioEngine, existing_audio_engine
from glitchygames.audio.synth import Envelope, Waveform
from glitchygames.audio.voices import (
    ChannelPartition,
    ChannelsHeldError,
    inner_context_partition,
    inner_game_channels_declared,
    release_inner_context_channels,
    reserved_channel_count,
)
from glitchygames.engine_context import EngineContext
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


def build_engine(
    mocker, *, game: type[Scene], extra_arguments: tuple[str, ...] = ()
) -> GoldenTraceEngine:
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
        options = build_engine(mocker, game=SoundingGame).options
        assert options['sound_channels'] == 32
        assert options['sound_cache'] == 'disk'  # the owner, 2026-11-15
        assert options['sound_cache_memory'] == 256
        assert options['crt_power_on_sound'] == 'on'
        assert options['sound_diagnostics'] is False

    def test_the_sound_options_are_read_as_given(self, mocker):
        engine = build_engine(
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

        options = engine.options
        assert options['sound_channels'] == 12
        assert options['sound_cache'] == 'none'
        assert options['sound_cache_memory'] == 64
        assert options['crt_power_on_sound'] == 'off'
        assert options['sound_diagnostics'] is True

    def test_the_disk_cache_option_is_accepted(self, mocker):
        engine = build_engine(mocker, game=SoundingGame, extra_arguments=('--sound-cache', 'disk'))

        assert engine.options['sound_cache'] == 'disk'

    def test_a_live_sound_starts_on_the_scene_managers_live_pool(self, mocker):
        """The scene manager gives its audio engine its own live pool (``_live_pool``)."""
        engine = build_engine(mocker, game=SoundingGame)
        manager = engine.scene_manager
        pool = mocker.Mock(name='live pool')
        mocker.patch.object(type(manager), '_live_pool', return_value=pool)
        audio = manager.audio_for(game_engine=engine)
        instrument = Instrument(wave='sine', live=True)

        audio.sound(instrument, pitch='A4').start(owner='scene')

        pool.create_instrument_voice.assert_called_once_with(
            owner='scene',
            instrument=instrument,
            frequency=440.0,
            volume=1.0,
            parameters=None,
            options=mocker.ANY,  # its contents: tests/audio/test_live_instrument.py
        )
        pool.create_instrument_voice.return_value.stream.start.assert_called_once_with()

    def test_a_games_live_sound_is_kept_fed_by_the_frame_loop(self, mocker):
        """End to end: the scene manager's frame step, the audio engine's update, the pool.

        A ride's motor, started before transition_to runs the ride (the pending transition
        owns it), gets its next chunk queued by the frame.
        """
        from glitchygames.audio.live import LiveAudio

        engine = build_engine(mocker, game=SoundingGame)
        manager = engine.scene_manager
        assert pygame.mixer.get_init() is not None  # the harness's dummy-driver mixer
        manager._live_audio = LiveAudio(channel_indices=(0,))
        ride = object()
        manager._pending_transition = (mocker.Mock(), ride)
        audio = manager.audio_for(game_engine=engine)
        motor = audio.sound(Instrument(wave='saw', live=True), pitch='A1').start(owner=ride)
        channel = pygame.mixer.Channel(0)
        try:
            assert channel.get_queue() is None  # only the first chunk, playing

            manager._update_frame_services()

            assert motor.is_playing
            assert channel.get_queue() is not None
        finally:
            motor.cancel()
            manager._pending_transition = None

    def test_a_games_sounds_go_in_its_own_cache_folder(self, mocker, tmp_path, monkeypatch):
        """The scene manager names the game's package as the audio engine's cache folder."""
        from glitchygames.audio.disk_cache import SOUND_CACHE_ROOT_VARIABLE

        monkeypatch.setenv(SOUND_CACHE_ROOT_VARIABLE, str(tmp_path))
        engine = build_engine(mocker, game=SoundingGame)

        audio = engine.scene_manager.audio_for(game_engine=engine)
        audio.sound(Instrument(wave='square'), pitch='C5')

        assert audio.cache_mode is CacheMode.DISK
        assert [path.name for path in tmp_path.iterdir()] == ['tests']  # SoundingGame's package

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
def test_a_failing_audio_close_still_runs_the_rest_of_the_teardown_then_fails_it(mocker, caplog):
    """GameEngine._shutdown: the reservation is given back and pygame quits, then the error.

    The close's error is the teardown's failure (logged with its traceback, exit
    INTERNAL_ERROR), as any other teardown error is, but only after the rest of the teardown ran.
    """
    SoundingGame.seen.clear()
    mocker.patch.object(AudioEngine, 'close', side_effect=RuntimeError('the fades went wrong'))
    release_channels = mocker.spy(voices_module, 'release_channels')
    engine = build_engine(mocker, game=SoundingGame)

    with (
        caplog.at_level(logging.ERROR, logger='game.engine'),
        pytest.raises(SystemExit) as exit_info,
    ):
        engine.start()

    assert exit_info.value.code == ExitCode.INTERNAL_ERROR
    assert release_channels.call_count == 1
    assert pygame.quit.call_count >= 1  # the engine_run_environment fixture's stand-in
    assert existing_audio_engine() is None
    (record,) = [record for record in caplog.records if record.exc_info is not None]
    assert 'the fades went wrong' in str(record.exc_info[1])


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


FIRST_AUDIO_FRAME = 3


class LateSoundingGame(Scene):
    """A stand-in game that first asks for audio in gameplay, at FIRST_AUDIO_FRAME."""

    NAME = 'LateSoundingGame'
    VERSION = '1.0'
    SOUND_DIRECTORY = 'audio/fixtures/sounds'
    seen: ClassVar[dict[str, Any]] = {}

    def __init__(self, options: dict[str, Any] | None = None, groups: Any = None) -> None:
        """Start on frame 0."""
        super().__init__(options=options, groups=groups)
        self.frames_run = 0

    def dt_tick(self, dt: float) -> None:
        """Play the coin at FIRST_AUDIO_FRAME (the first audio access), then quit."""
        super().dt_tick(dt)
        if self.frames_run == FIRST_AUDIO_FRAME:
            audio = self.scene_manager.audio
            audio.play('coin')
            LateSoundingGame.seen['diagnostics'] = audio.diagnostics()
            self.scene_manager.quit()
        self.frames_run += 1


@pytest.mark.usefixtures('engine_run_environment')
def test_a_first_audio_access_in_gameplay_is_a_gameplay_compile(mocker, caplog):
    """No setup() use: the compile belongs to its frame, and no setup line is logged."""
    LateSoundingGame.seen.clear()

    with caplog.at_level(logging.INFO, logger='game.audio.engine'):
        build_engine(mocker, game=LateSoundingGame).start()

    diagnostics = LateSoundingGame.seen['diagnostics']
    (record,) = diagnostics.compiles_in_gameplay
    assert (record.name, record.frame_number, record.during_setup) == (
        'coin',
        FIRST_AUDIO_FRAME,
        False,
    )
    assert diagnostics.setup_compiles == 0
    assert 'Setup compiled sounds' not in caplog.text


@pytest.mark.usefixtures('engine_run_environment')
class TestTheReservedPartition:
    """GameEngine.reserved_channel_partition keeps only a partition made on a running mixer."""

    def test_a_partition_made_without_a_mixer_is_not_kept(self, mocker):
        engine = build_engine(mocker, game=quiet_game())
        mocker.patch('pygame.mixer.get_init', return_value=None)

        empty = engine.reserved_channel_partition()

        assert empty == ChannelPartition(live=(), library=(), legacy_count=0)
        assert engine.channel_partition is None
        mocker.stopall()
        assert engine.reserved_channel_partition().library == tuple(range(4, 36))

    def test_a_partition_made_on_a_mixer_is_kept(self, mocker):
        engine = build_engine(mocker, game=quiet_game())

        partition = engine.reserved_channel_partition()

        assert engine.reserved_channel_partition() is partition

    def test_a_host_scene_declares_its_inner_games_with_the_partition_at_construction(self, mocker):
        """INNER_GAMES = 2: declared as the engine is made; nothing grows afterwards.

        The partition and the declaration are made before the engine starts (and so before the
        CRT power-on plays), and an inner game's partition then takes a live pool inside them.
        """
        host_game = type(
            'HostGame', (Scene,), {'NAME': 'HostGame', 'INNER_GAMES': 2, 'dt_tick': _quit_at_once}
        )

        engine = build_engine(mocker, game=host_game)
        set_num_channels = mocker.spy(pygame.mixer, 'set_num_channels')
        with EngineContext(name='tile').active():
            inner = inner_context_partition(live_pool=4, library_channels=32)

        assert engine.reserved_channel_partition().library == tuple(range(4, 36))
        assert inner_game_channels_declared()
        # Two heard sets of 32 (channels 36-99), then the first inner game's live pool
        assert inner.live == (100, 101, 102, 103)
        set_num_channels.assert_not_called()
        assert pygame.mixer.get_num_channels() >= 116
        assert reserved_channel_count() == 36

    def test_a_second_host_engine_while_the_first_ones_inner_games_hold_channels_is_refused(
        self, mocker
    ):
        """ChannelsHeldError says what to do; once the inner game gave its channels back, it builds.

        A second host in one process (a launcher starting another Arcade) would move the
        declaration under the first one's running inner games.
        """
        host_game = type(
            'HostGame', (Scene,), {'NAME': 'HostGame', 'INNER_GAMES': 2, 'dt_tick': _quit_at_once}
        )
        build_engine(mocker, game=host_game)
        tile = EngineContext(name='tile')
        with tile.active():
            held = inner_context_partition(live_pool=4, library_channels=32)

        with pytest.raises(
            ChannelsHeldError,
            match=r'^inner games hold channels of the earlier declaration: finish them before an '
            r'engine declares its own$',
        ):
            build_engine(mocker, game=host_game)
        with tile.active():
            release_inner_context_channels()
        second_host = build_engine(mocker, game=host_game)

        assert held.live == (100, 101, 102, 103)
        assert second_host.reserved_channel_partition().library == tuple(range(4, 36))
        assert inner_game_channels_declared()


class EarlyAskingGame(Scene):
    """A stand-in game whose constructor asks for audio, as a sprite loading a sound would."""

    NAME = 'EarlyAskingGame'
    VERSION = '1.0'

    def __init__(self, *args, **kwargs):
        """Ask for the audio engine while the game is being built."""
        super().__init__(*args, **kwargs)
        self.cache_mode_seen = self.scene_manager.audio.cache_mode

    def dt_tick(self, dt):
        """Quit in the first frame."""
        del dt
        self.scene_manager.quit()


def test_a_constructor_that_asks_for_audio_gets_the_games_sound_options(mocker):
    """The game engine is set before the game is built, so its sound options apply from there.

    Built while the CRT power-on is skipped (the dummy driver), before this the audio engine was
    made without the game engine: cache ram whatever --sound-cache said.
    """
    engine = build_engine(mocker, game=EarlyAskingGame, extra_arguments=('--sound-cache', 'none'))
    engine.start()

    assert engine.running_game.instance.cache_mode_seen.value == 'none'


def _declared_effect(name: str, frequency: float) -> Effect:
    """A short one-tone effect for a game to declare."""
    envelope = Envelope(attack=0.001, decay=0.0, sustain_level=1.0, release=0.01)
    tone = Tone(waveform=Waveform.SINE, start_frequency=frequency, duration=0.02, envelope=envelope)
    return Effect(name=name, tones=(tone,))


# Declared sounds are complete sounds: effects, or a sound file's path#name entries
DECLARED = (
    _declared_effect('low', 220.0),
    _declared_effect('mid', 330.0),
    _declared_effect('high', 440.0),
)


class DeclaringGame(Scene):
    """A stand-in game that declares its sounds and records what was compiled when it was built."""

    NAME = 'DeclaringGame'
    VERSION = '1.0'
    SOUNDS = DECLARED

    def __init__(self, *args, **kwargs):
        """Count the compiles done before the game was built, then ask for its sounds."""
        super().__init__(*args, **kwargs)
        audio = self.scene_manager.audio
        self.compiles_before_build = audio.sounds.statistics().compiles
        self.compiled_at_build = [audio.sound(source).is_compiled for source in self.SOUNDS]

    def dt_tick(self, dt):
        """Quit in the first frame."""
        del dt
        self.scene_manager.quit()


def test_a_games_declared_sounds_are_compiled_before_it_is_built(mocker):
    """Where the power-on is skipped (the dummy driver), every declared sound compiles first."""
    engine = build_engine(mocker, game=DeclaringGame)
    engine.start()

    game = engine.running_game.instance
    assert game.compiles_before_build == len(DECLARED)
    assert all(game.compiled_at_build)


def test_the_declared_sounds_compile_in_the_power_ons_idle_time(mocker):
    """With the power-on playing, its frames' idle work compiles them; the rest before the build."""
    from glitchygames.audio.startup import StartupSounds

    mocker.patch('glitchygames.clock.raw_sleep')
    slices = mocker.spy(StartupSounds, 'compile_for')
    finish = mocker.spy(StartupSounds, 'finish')
    engine = build_engine(
        mocker,
        game=DeclaringGame,
        extra_arguments=('--crt-power-on', 'on', '--crt-power-on-sound', 'off'),
    )
    engine.start()

    assert slices.call_count >= 1
    finish.assert_called_once()
    game = engine.running_game.instance
    assert game.compiles_before_build == len(DECLARED)
    assert all(game.compiled_at_build)


def test_a_declared_sound_that_cannot_compile_ends_the_run_through_the_crash_boundary(mocker):
    """It is raised where it compiles, inside start()'s boundary: logged, exit INTERNAL_ERROR."""
    broken = type('BrokenGame', (DeclaringGame,), {'SOUNDS': ('/nowhere/sounds.toml#gone',)})
    engine = build_engine(mocker, game=broken)

    with pytest.raises(SystemExit) as exit_information:
        engine.start()

    assert exit_information.value.code == ExitCode.INTERNAL_ERROR
