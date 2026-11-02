"""Tests for the audio engine: one-call sounds, plays, scenes, pause, silence and diagnostics.

The engine runs on a real stereo mixer (SDL's dummy driver) under a real ``SceneManager`` whose
stand-in scene looks short names up in tests/audio/fixtures/sounds (impl spec 8, feature spec
3.1-3.2, W1-W2).
"""

import itertools
import logging
import math
import sys
import types
from pathlib import Path

import pygame
import pytest

from glitchygames.audio import (
    AudioEngine,
    CacheMode,
    Instrument,
    Sound,
    SoundHandle,
    Tuning,
)
from glitchygames.audio.engine import (
    SYSTEM_OWNER,
    AudioDiagnostics,
    AudioDiagnosticsSnapshot,
    discard_audio_engine,
    existing_audio_engine,
)
from glitchygames.audio.voices import ChannelPartition
from glitchygames.engine_context import EngineContext
from glitchygames.replay.silence import FrameSilencer
from glitchygames.scenes import Scene, SceneManager
from tests.audio.library_support import FIXTURE_SOUNDS, make_library, stop_mixer
from tests.audio.voice_support import start_reserved_mixer

FRAME_SECONDS = 1 / 60
NO_TRANSITIONS = (None, None)
# The default partition's library channels (global constraints: 4 live, 32 library, 8 legacy)
LIBRARY_CHANNELS = 32
ALL_CHANNELS = 44


class SoundFixtureScene(Scene):
    """A stand-in game scene whose short names are the fixture sounds.

    Its package is ``tests`` (this module's top-level package), so its sound directory is
    relative to tests/.
    """

    NAME = 'SoundFixtureScene'
    SOUND_DIRECTORY = 'audio/fixtures/sounds'


class OtherScene(Scene):
    """Another scene of the stand-in game."""

    NAME = 'OtherScene'


class NoSoundsScene(Scene):
    """A scene without a sound directory."""

    NAME = 'NoSoundsScene'
    SOUND_DIRECTORY = None


class PlayingInSetupScene(Scene):
    """A scene that plays a sound in its setup."""

    NAME = 'PlayingInSetupScene'
    SOUND_DIRECTORY = 'audio/fixtures/sounds'

    def setup(self):
        """Play the coin."""
        self.handle = self.scene_manager.audio.play('coin')


class AlwaysBusyChannel(pygame.mixer.Channel):
    """A real mixer channel that the device always reports busy (a fade that never ends)."""

    def get_busy(self):
        """Report busy.

        Returns:
            True.
        """
        return True


@pytest.fixture(autouse=True)
def _mixer_stopped_afterwards():
    """Close any audio engine without waiting, then stop the mixer for the next test."""
    yield
    discard_audio_engine(wait_seconds=0.0)
    stop_mixer()


@pytest.fixture
def scene_manager():
    """A scene manager on a reserved stereo mixer, with the fixture scene active.

    Returns:
        The scene manager.
    """
    start_reserved_mixer()
    manager = SceneManager()
    manager.switch_to_scene(SoundFixtureScene())
    return manager


@pytest.fixture
def engine(scene_manager):
    """The scene manager's audio engine.

    Returns:
        The engine.
    """
    return scene_manager.audio


def advance(engine, *, frames, active_scene, previous_scene=None, paused_owners=()):
    """Run ``frames`` audio updates of 1/60 s."""
    for _ in range(frames):
        engine.update(
            dt=FRAME_SECONDS,
            active_scene=active_scene,
            previous_scene=previous_scene,
            active_transitions=NO_TRANSITIONS,
            paused_owners=paused_owners,
        )


def frames_to_play(sound):
    """How many frames of 1/60 s a sound plays before it ends.

    Returns:
        The frame count.
    """
    return math.ceil(sound.length / FRAME_SECONDS)


class TestGettingAndPlaying:
    """sound() compiles and never plays; play() plays (feature spec 3.1)."""

    def test_getting_a_sound_never_plays_it(self, engine):
        sound = engine.sound('coin')

        assert isinstance(sound, Sound)
        assert sound.is_compiled
        assert engine.diagnostics().voices_playing == 0
        assert all(
            channel.state == 'idle'
            for channel in engine.snapshot().channels
            if channel.group == 'library'
        )

    def test_a_got_sound_plays_through_the_engine(self, engine):
        handle = engine.sound('coin').play()

        assert isinstance(handle, SoundHandle)
        assert handle.is_playing
        assert engine.diagnostics().voices_playing == 1

    def test_play_shorthand_splits_identity_and_playback_arguments(
        self, engine, scene_manager, mocker
    ):
        play = mocker.spy(engine._voices, 'play')
        coin = engine.sound('coin')

        handle = engine.play('coin', volume=0.5, pan=-0.5, priority=70, persist=True)
        engine.play('coin')

        assert handle.is_playing
        # The identity went to sound(): the same compiled sound, a cache hit each time
        assert engine.sounds.statistics().hits == 2
        first, second = play.call_args_list
        assert first.args == (coin,)
        assert first.kwargs == {
            'volume': 0.5,
            'pan': -0.5,
            'bus': 'effects',
            'priority': 70,
            'loop': False,
            'persist': True,
            'owner': scene_manager.active_scene,
        }
        # Playback arguments left out take the sound file's defaults (pickups.toml: 0.6)
        assert second.kwargs['volume'] == pytest.approx(0.6)
        assert second.kwargs['persist'] is False

    def test_identity_arguments_make_different_sounds(self, engine):
        e5 = engine.sound('coin', pitch='E5')

        assert engine.sound('coin', pitch='E5') is e5
        assert engine.sound('coin', pitch='G5') is not e5
        assert engine.sound('coin') is not e5

    def test_pitch_with_notes_is_refused(self, engine):
        with pytest.raises(ValueError, match='pitch'):
            engine.sound(Instrument(wave='square'), pitch='A4', notes='C5:0.1')

    def test_a_scheduled_play_arrives_in_m2(self, engine):
        with pytest.raises(NotImplementedError, match='M2'):
            engine.play('coin', at_frame=10)

    def test_a_positioned_play_arrives_in_m4(self, engine):
        with pytest.raises(NotImplementedError, match='M4'):
            engine.sound('coin').play(position=(1.0, 2.0))

    def test_a_sound_from_a_bare_library_plays_silently(self, caplog):
        library, _ = make_library()
        sound = library.sound('coin', scene_sound_directory=FIXTURE_SOUNDS)

        with caplog.at_level(logging.WARNING):
            handle = sound.play()
            sound.play()

        assert handle.is_playing is False
        assert handle.stop() is False
        assert caplog.text.count('not got from an audio engine') == 1

    def test_the_tuning_is_part_of_what_a_sound_is(self, engine):
        concert = engine.sound(Instrument(wave='sine'), pitch='A4')
        engine.tuning = Tuning(a4=432.0)

        assert engine.sound(Instrument(wave='sine'), pitch='A4') is not concert

    def test_beep_plays_a_cached_square_on_the_effects_bus(self, engine, mocker):
        play = mocker.spy(engine._voices, 'play')

        handle = engine.beep()
        engine.beep()

        assert handle.is_playing
        assert engine.sounds.statistics().hits == 1
        # beep plays the sound of an Instrument with its wave, at its pitch, for its length
        assert play.call_args.args[0] is engine.sound(
            Instrument(wave='square'), pitch='A4', length=0.1
        )
        assert play.call_args.kwargs['bus'] == 'effects'
        assert play.call_args.kwargs['volume'] == pytest.approx(0.5)

    def test_beep_takes_a_pitch_wave_and_length(self, engine, mocker):
        play = mocker.spy(engine._voices, 'play')

        engine.beep(pitch=880.0, wave='triangle', length=0.25, volume=0.25, bus='ui')

        assert play.call_args.args[0] is engine.sound(
            Instrument(wave='triangle'), pitch=880.0, length=0.25
        )
        assert play.call_args.kwargs['bus'] == 'ui'
        assert play.call_args.kwargs['volume'] == pytest.approx(0.25)


class TestWithoutAMixer:
    """No mixer: sound() still compiles; play() is a silent no-op, warned once (Errors table)."""

    def test_without_a_mixer_sound_compiles_and_play_is_a_logged_once_no_op(self, caplog):
        stop_mixer()
        engine = AudioEngine(partition=ChannelPartition(live=(), library=(), legacy_count=0))

        sound = engine.sound(Instrument(wave='square'), pitch='C5')
        with caplog.at_level(logging.WARNING):
            first = sound.play()
            second = engine.play(Instrument(wave='square'), pitch='C5')

        assert sound.is_compiled
        assert first.stop() is False
        assert first.is_playing is False
        assert second.is_playing is False
        assert caplog.text.count('no mixer') == 1
        assert engine.snapshot().device == 'no mixer'
        engine.close()


class TestHandlesAndOwners:
    """Voices belong to the scene that started them (feature spec 7.4)."""

    def test_a_handle_after_close_returns_false(self, engine):
        handle = engine.play('coin')

        engine.close()

        assert handle.stop() is False
        assert handle.is_playing is False
        assert engine.play('coin').is_playing is False

    def test_closing_twice_is_harmless(self, engine):
        engine.close()
        engine.close()

    def test_a_handle_after_its_scene_switched_returns_false(self, engine, scene_manager):
        handle = engine.play('coin')

        advance(engine, frames=1, active_scene=OtherScene())

        assert handle.stop() is False
        assert handle.is_playing is False

    def test_scene_cleanup_fades_the_scenes_voices_unless_persisted(self, engine, scene_manager):
        game_scene = scene_manager.active_scene
        ending = engine.play('coin')
        persisting = engine.play('coin', persist=True, loop=True)

        advance(engine, frames=1, active_scene=OtherScene())

        assert ending.is_playing is False
        assert persisting.is_playing
        library_states = [
            channel.state for channel in engine.snapshot().channels if channel.group == 'library'
        ]
        assert library_states.count('fading') == 1
        assert library_states.count('playing') == 1
        # The scene came back: its persisted voice plays on with it
        advance(engine, frames=1, active_scene=game_scene)
        assert persisting.is_playing

    def test_a_transitions_voices_play_while_it_runs(self, scene_manager):
        transition = object()
        engine = AudioEngine(
            partition=ChannelPartition(live=(), library=tuple(range(4, 36)), legacy_count=8),
            scene_source=lambda: transition,
        )
        handle = engine.play(Instrument(wave='square'), pitch='C5', loop=True)

        engine.update(
            dt=FRAME_SECONDS,
            active_scene=None,
            previous_scene=None,
            active_transitions=(transition, None),
            paused_owners=(),
        )

        assert handle.is_playing
        engine.update(
            dt=FRAME_SECONDS,
            active_scene=None,
            previous_scene=None,
            active_transitions=NO_TRANSITIONS,
            paused_owners=(),
        )
        assert handle.is_playing is False
        engine.close(wait_seconds=0.0)

    def test_system_voices_outlive_every_scene(self, scene_manager):
        engine = AudioEngine(
            partition=ChannelPartition(live=(), library=tuple(range(4, 36)), legacy_count=8),
            scene_source=lambda: None,
        )
        handle = engine.play(Instrument(wave='square'), pitch='C5', loop=True)

        advance(engine, frames=3, active_scene=OtherScene())

        assert handle.is_playing
        assert 'system owner' in repr(SYSTEM_OWNER)
        engine.close(wait_seconds=0.0)

    def test_pause_screen_pauses_and_resumes_voices(self, engine, scene_manager):
        game_scene = scene_manager.active_scene
        pause_scene = OtherScene()
        handle = engine.play('coin')
        coin = engine.sound('coin')
        frames_left = frames_to_play(coin)

        # A pause longer than the sound: it waits, its channel paused, its time stopped
        advance(
            engine,
            frames=frames_left * 3,
            active_scene=pause_scene,
            previous_scene=game_scene,
        )

        assert handle.is_playing
        library_states = [
            channel.state for channel in engine.snapshot().channels if channel.group == 'library'
        ]
        assert library_states.count('paused') == 1
        # The pausing frame counted once; the rest of the sound plays after the resume
        advance(engine, frames=frames_left - 3, active_scene=game_scene)
        assert handle.is_playing
        advance(engine, frames=3, active_scene=game_scene)
        assert handle.is_playing is False

    def test_a_playback_scopes_paused_owners_hold_their_voices(self, engine, scene_manager):
        game_scene = scene_manager.active_scene
        handle = engine.play('coin', loop=True)

        advance(engine, frames=5, active_scene=OtherScene(), paused_owners=(game_scene,))

        assert handle.is_playing


class TestStopAll:
    """stop_all fades every voice, or one bus's subtree."""

    def test_stop_all_fades_every_voice_persisted_or_not(self, engine):
        handles = [engine.play('coin'), engine.play('coin', persist=True, bus='ui')]

        engine.stop_all()

        assert [handle.is_playing for handle in handles] == [False, False]

    def test_stop_all_of_a_bus_takes_its_subtree_only(self, engine):
        engine.buses.add('pickups', parent='effects')
        on_effects = engine.play('coin')
        on_pickups = engine.play('coin', bus='pickups')
        on_ui = engine.play('coin', bus='ui')

        engine.stop_all(fade=0.1, bus='effects')

        assert on_effects.is_playing is False
        assert on_pickups.is_playing is False
        assert on_ui.is_playing

    def test_stop_all_refuses_a_negative_fade(self, engine):
        with pytest.raises(ValueError, match='fade'):
            engine.stop_all(fade=-1.0)

    def test_stop_all_of_an_unknown_bus_names_the_buses(self, engine):
        with pytest.raises(KeyError, match='effects'):
            engine.stop_all(bus='nowhere')


class TestSilencedFrames:
    """FrameSilencer's stops end the voices in the table (impl spec 7.3)."""

    def test_replay_rebuild_silence_ends_voices_in_the_table(self, engine):
        silencer = FrameSilencer()
        silencer.begin()
        handle = engine.play('coin')

        silencer.silence_frame()
        silencer.finish()

        assert handle.is_playing is False
        assert engine.play('coin').is_playing

    def test_a_fast_forwards_silence_ends_the_voices_it_stops(self, engine):
        spared = engine.play('coin', loop=True)
        silencer = FrameSilencer(spares_playing_sounds=True)
        silencer.begin()
        started_unseen = engine.play('coin', bus='ui')

        silencer.silence_frame()
        silencer.finish()

        assert spared.is_playing
        assert started_unseen.is_playing is False

    def test_silencing_one_channel_ends_only_its_voice(self, engine):
        first = engine.play('coin')
        second = engine.play('coin')
        first_channel = next(
            channel.index
            for channel in engine.snapshot().channels
            if channel.group == 'library' and channel.state == 'playing'
        )
        pygame.mixer.Channel(first_channel).stop()

        engine.silenced(first_channel)

        assert first.is_playing is False
        assert second.is_playing


class TestAccounting:
    """Frame numbers, setup attribution, the frame account and the setup report (impl 6.5)."""

    def test_compiles_name_their_frame_and_whether_setup_ran_them(self, engine):
        engine.begin_scene_setup()
        engine.sound(Instrument(wave='square'), pitch='C5')
        engine.begin_frame(frame_number=7)
        engine.begin_logic_frame()
        engine.sound(Instrument(wave='square'), pitch='D5')

        setup_record, gameplay_record = engine.snapshot().compile_log[-2:]
        assert setup_record.during_setup is True
        assert gameplay_record.during_setup is False
        assert gameplay_record.frame_number == 7
        diagnostics = engine.diagnostics()
        assert diagnostics.compiles_in_gameplay == (gameplay_record,)
        assert diagnostics.gameplay_compiles == 1

    def test_a_scene_switched_to_compiles_in_its_setup(self, engine, scene_manager):
        engine.begin_logic_frame()

        scene_manager.switch_to_scene(PlayingInSetupScene())
        engine.sound(Instrument(wave='sine'), pitch='C5')

        assert engine.snapshot().compile_log[-1].during_setup is True

    def test_a_slow_setup_logs_one_info_line_naming_its_slowest_sounds(
        self, engine, mocker, caplog
    ):
        # Each piece of work lasts 30 ms on this counter
        mocker.patch(
            'glitchygames.clock.raw_counter_ns', side_effect=itertools.count(0, 30_000_000)
        )
        engine.begin_scene_setup()
        engine.sound(Instrument(wave='square'), pitch='C5')
        engine.sound(Instrument(wave='triangle'), pitch='C5')

        with caplog.at_level(logging.INFO, logger='game.audio.engine'):
            engine.begin_logic_frame()
            engine.begin_logic_frame()

        (record,) = [line for line in caplog.records if line.name == 'game.audio.engine']
        assert record.levelno == logging.INFO
        assert 'instrument-' in record.getMessage()
        assert '60.0 ms' in record.getMessage()

    def test_a_quick_setup_logs_nothing(self, engine, mocker, caplog):
        mocker.patch(
            'glitchygames.clock.raw_counter_ns', side_effect=itertools.count(0, 30_000_000)
        )
        engine.begin_scene_setup()
        engine.sound(Instrument(wave='square'), pitch='C5')

        with caplog.at_level(logging.INFO, logger='game.audio.engine'):
            engine.begin_logic_frame()

        assert not [line for line in caplog.records if line.name == 'game.audio.engine']

    def test_the_frame_account_is_taken_once_per_frame(self, engine):
        engine.sound(Instrument(wave='square'), pitch='E5')

        account = engine.take_frame_account(processing_seconds=0.004)

        assert account.audio_seconds > 0
        assert [kind for kind, _name, _microseconds in account.audio_work] == ['compile']
        assert engine.take_frame_account().audio_work == ()
        snapshot = engine.snapshot()
        assert snapshot.frame_work_by_kind == {}
        assert snapshot.frame_processing_seconds is None


class TestDiagnosticsAndSnapshot:
    """diagnostics() for the game, snapshot() for the debug panel (W8, ruling R3)."""

    def test_diagnostics_count_voices_compiles_and_the_device(self, engine):
        engine.play('coin')

        diagnostics = engine.diagnostics()

        assert isinstance(diagnostics, AudioDiagnostics)
        assert diagnostics.voices_playing == 1
        assert diagnostics.voices_limit == LIBRARY_CHANNELS
        assert diagnostics.compiles == 1
        assert diagnostics.setup_compiles == 1
        assert diagnostics.compile_milliseconds > 0
        assert diagnostics.stolen_voices == 0
        assert diagnostics.dropped_plays == 0
        assert diagnostics.delayed_plays == 0
        assert diagnostics.device == '44100 Hz, 16-bit signed, 2 channels, driver dummy'
        assert diagnostics.cache.compiles == 1

    def test_the_snapshot_describes_the_mixer_for_the_debug_panel(self, engine, scene_manager):
        engine.sound('coin')
        engine.play('coin')
        engine.buses['music'].mute = True
        engine.buses['effects'].volume = 0.5
        account = engine.take_frame_account(processing_seconds=0.004)
        advance(engine, frames=1, active_scene=scene_manager.active_scene)

        snapshot = engine.snapshot()

        assert isinstance(snapshot, AudioDiagnosticsSnapshot)
        assert snapshot.cache_mode is CacheMode.RAM
        assert snapshot.voices_library == 1
        assert snapshot.voices_live == 0
        assert snapshot.voices_legacy == 0
        assert snapshot.compiles_last_second == 1
        assert snapshot.cache_hit_rate == pytest.approx(0.5)
        # Whole microseconds per piece
        assert snapshot.frame_work_by_kind == {
            'compile': pytest.approx(account.audio_seconds, abs=1e-6)
        }
        assert snapshot.frame_processing_seconds == pytest.approx(0.004)
        assert len(snapshot.channels) == ALL_CHANNELS
        assert snapshot.bus_levels['effects'] == pytest.approx(0.5)
        assert snapshot.bus_levels['music'] == 0.0
        assert snapshot.muted_buses == frozenset({'music'})
        assert [record.name for record in snapshot.compile_log] == ['coin']

    def test_compiles_leave_the_last_second_after_a_second(self, engine, scene_manager):
        engine.sound('coin')
        advance(engine, frames=1, active_scene=scene_manager.active_scene)
        assert engine.snapshot().compiles_last_second == 1

        advance(engine, frames=61, active_scene=scene_manager.active_scene)

        assert engine.snapshot().compiles_last_second == 0

    def test_a_fresh_engine_has_no_hit_rate(self, engine):
        assert engine.snapshot().cache_hit_rate is None


class TestSceneDirectories:
    """Short names resolve against the scene's SOUND_DIRECTORY, in its package (ruling R21)."""

    def test_short_names_come_from_the_scenes_sound_directory(self, engine):
        assert engine.sound('sfx_slap').name == 'sfx_slap'

    def test_paths_are_relative_to_the_scenes_package(self, engine):
        assert engine.sound('audio/fixtures/sounds/pickups.toml#coin').name == 'coin'

    def test_a_scene_without_a_sound_directory_has_no_short_names(self, scene_manager):
        scene_manager.switch_to_scene(NoSoundsScene())

        with pytest.raises(KeyError, match='no sound directory'):
            scene_manager.audio.sound('coin')

    def test_an_absolute_sound_directory_needs_no_package(self, monkeypatch):
        monkeypatch.delitem(sys.modules, 'no_such_package_anywhere', raising=False)
        absolute = type(
            'AbsoluteNowhereScene',
            (),
            {'__module__': 'no_such_package_anywhere', 'SOUND_DIRECTORY': str(FIXTURE_SOUNDS)},
        )
        relative = type(
            'RelativeNowhereScene',
            (),
            {'__module__': 'no_such_package_anywhere', 'SOUND_DIRECTORY': 'sounds'},
        )
        no_channels = ChannelPartition(live=(), library=(), legacy_count=0)

        assert AudioEngine(partition=no_channels, scene_source=absolute).sound('coin').name == (
            'coin'
        )
        with pytest.raises(KeyError, match='no sound directory'):
            AudioEngine(partition=no_channels, scene_source=relative).sound('coin')

    def test_without_a_package_the_scenes_own_module_directory_is_used(self, monkeypatch, tmp_path):
        module = types.ModuleType('absent_top_package.scenes')
        module.__file__ = str(tmp_path / 'scenes.py')
        monkeypatch.setitem(sys.modules, 'absent_top_package.scenes', module)
        sounds = tmp_path / 'sounds'
        sounds.mkdir()
        (sounds / 'pickups.toml').write_text((FIXTURE_SOUNDS / 'pickups.toml').read_text())
        scene_class = type(
            'AbsentScene',
            (),
            {'__module__': 'absent_top_package.scenes', 'SOUND_DIRECTORY': 'sounds'},
        )
        engine = AudioEngine(
            partition=ChannelPartition(live=(), library=(), legacy_count=0),
            scene_source=scene_class,
        )

        assert engine.sound('coin').name == 'coin'

    def test_the_scene_setting_up_owns_its_plays(self, scene_manager):
        scene = PlayingInSetupScene()
        scene_manager.switch_to_scene(scene)

        advance(scene_manager.audio, frames=1, active_scene=scene)
        assert scene.handle.is_playing
        advance(scene_manager.audio, frames=1, active_scene=OtherScene())
        assert scene.handle.is_playing is False


class TestTheContextSlot:
    """Each engine context has its own audio engine (CLAUDE.md, Engine Context)."""

    def test_the_scene_manager_gives_the_current_contexts_engine(self, scene_manager):
        engine = scene_manager.audio

        assert scene_manager.audio is engine
        assert existing_audio_engine() is engine
        with EngineContext(name='other').active():
            assert existing_audio_engine() is None

    def test_discarding_closes_the_engine(self, engine):
        handle = engine.play('coin')

        discard_audio_engine(wait_seconds=0.0)

        assert existing_audio_engine() is None
        assert handle.is_playing is False
        discard_audio_engine(wait_seconds=0.0)

    def test_without_a_game_engine_the_default_partition_is_reserved(self, engine):
        library_channels = [
            channel.index for channel in engine.snapshot().channels if channel.group == 'library'
        ]

        assert library_channels == list(range(4, 36))

    def test_close_waits_for_the_fades_at_most_its_limit(self, engine, mocker):
        engine.play('coin')
        readings = itertools.count(0.0, 0.03)
        mocker.patch('glitchygames.clock.raw_counter_seconds', side_effect=lambda: next(readings))
        sleep = mocker.patch('glitchygames.clock.raw_sleep')
        mocker.patch('pygame.mixer.Channel', AlwaysBusyChannel)

        engine.close()

        # 0.03 s per reading: the 0.1 s limit passes after three sleeps
        assert sleep.call_count == 3

    def test_close_on_a_mixer_restarted_with_fewer_channels_ends_the_voices(self, engine):
        handle = engine.play('coin')
        pygame.mixer.set_num_channels(8)

        engine.close()

        assert handle.is_playing is False

    def test_close_without_a_mixer_does_not_wait(self, engine, mocker):
        sleep = mocker.patch('glitchygames.clock.raw_sleep')
        engine.play('coin')
        stop_mixer()

        engine.close()

        sleep.assert_not_called()


def test_the_fixture_directory_is_where_the_stand_in_scene_looks():
    """The stand-in scene's package root is tests/, so its directory is the fixtures'."""
    package_root = Path(__file__).resolve().parent.parent
    assert SoundFixtureScene.SOUND_DIRECTORY is not None
    assert package_root / SoundFixtureScene.SOUND_DIRECTORY == FIXTURE_SOUNDS.resolve()
