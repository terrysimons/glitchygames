"""Tests for a live instrument's voice: its parameters, routes and sources rendered per chunk.

Feature spec 5.3-5.4, implementation spec 4.3 and 7.5; plans/2026-11-14-sound-migration.md
step 5. The voice's channel and lifecycle are a ``LiveStream`` (tests/audio/test_live.py).
"""

from __future__ import annotations

import numpy as np
import pygame
import pytest

from glitchygames.audio import live
from glitchygames.audio.effects import Tremolo
from glitchygames.audio.instrument import Filter, Instrument, Noise, PitchCurve, Source
from glitchygames.audio.live import LiveAudio
from glitchygames.audio.live_controls import Parameter, Route, smoothed
from glitchygames.audio.live_instrument import InstrumentVoice
from glitchygames.audio.route import set_audible
from glitchygames.audio.synth import (
    DEFAULT_FILTER_TAPS,
    Waveform,
    apply_kernel,
    filter_kernel,
    oscillator,
    tremolo,
)
from glitchygames.audio.voices import inner_context_partition, reserve_inner_game_channels
from glitchygames.audio.waves import Wave
from glitchygames.engine_context import EngineContext
from tests.audio.library_support import stop_mixer
from tests.audio.voice_support import start_reserved_mixer

RATE = 44100
CHUNK = 4410  # 100 ms
SPEED = Parameter(range=(0.0, 1.0), default=0.0, smoothing_ms=0.0)


@pytest.fixture
def rendered_chunks(mocker):
    """Capture every chunk a stream renders (to_sound receives the samples).

    Returns:
        The list that collects each rendered chunk.
    """
    chunks = []

    def fake_to_sound(samples, *, volume):
        chunks.append(samples.copy())
        return mocker.Mock(name=f'sound{len(chunks)}')

    mocker.patch.object(live, 'to_sound', side_effect=fake_to_sound)
    return chunks


@pytest.fixture
def channel(mocker):
    """A mocked mixer channel that is busy with an empty queue.

    Returns:
        The mocked channel.
    """
    mocked_channel = mocker.Mock(id=0)  # pygame.mixer.Channel.id: the stream reads its table
    mocked_channel.get_queue.return_value = None
    mocked_channel.get_busy.return_value = True
    return mocked_channel


def _voice(channel, instrument, **overrides):
    settings = {
        'channel': channel,
        'owner': 'scene',
        'instrument': instrument,
        'frequency': 220.0,
        'volume': 1.0,
        'sample_rate': RATE,
        'random_source': np.random.default_rng(5),
    }
    return InstrumentVoice(**(settings | overrides))


def _chunks(voice, count):
    """Start a voice and render ``count`` chunks."""
    voice.stream.start()
    for _ in range(count - 1):
        voice.stream.update()


def _live(**arguments):
    return Instrument(live=True, **arguments)


def _speed_to(destination, output, *, curve='linear', **instrument):
    return _live(
        parameters={'speed': SPEED},
        routes=[Route(source='speed', destination=destination, curve=curve, output=output)],
        **({'wave': 'sine'} | instrument),
    )


def _zero_crossings(samples):
    return int(np.count_nonzero(np.diff(np.signbit(samples))))


def _the_older_voice_chunks(  # ruff: ignore[too-many-arguments] - the older voice's settings
    *,
    waveform: Waveform,
    frequency: float,
    volume: float,
    cutoff: float,
    flutter: Tremolo,
    count: int,
    random_source: np.random.Generator | None = None,
) -> list[np.ndarray]:
    """What the older ``LiveVoice`` rendered for steady settings, chunk by chunk.

    Its rendering as it was before migration step 7 removed it (``git show
    57fd8f30:src/glitchygames/audio/live.py``, ``LiveVoice._render_chunk``), with nothing
    changing: oscillator, the FIR low-pass with its raw-signal history, tremolo, then volume.

    Returns:
        The chunks.
    """
    phase = 0.0
    tremolo_phase = 0.0
    history = np.zeros(DEFAULT_FILTER_TAPS - 1)
    kernel = filter_kernel(cutoff, sample_rate=RATE, taps=DEFAULT_FILTER_TAPS, high_pass=False)
    chunks = []
    for _ in range(count):
        raw, phase = oscillator(
            waveform,
            np.full(CHUNK, frequency),
            CHUNK / RATE,
            sample_rate=RATE,
            phase=phase,
            random_source=random_source,
        )
        samples = apply_kernel(raw, kernel, history=history)
        history = np.concatenate((history, raw))[-(DEFAULT_FILTER_TAPS - 1) :]
        samples, tremolo_phase = tremolo(
            samples, flutter.rate_hz, flutter.depth, sample_rate=RATE, phase=tremolo_phase
        )
        chunks.append(samples * np.full(CHUNK, volume))
    return chunks


class TestTheSameSoundAsTheOlderVoice:
    """Steady settings render what the older live voice rendered (the plan: tested)."""

    def test_the_motors_saw_low_pass_and_tremolo(self, channel, rendered_chunks):
        chug = Tremolo(rate_hz=7.0, depth=0.5)
        expected = _the_older_voice_chunks(
            waveform=Waveform.SAWTOOTH,
            frequency=177.0,
            volume=0.6,
            cutoff=800.0,
            flutter=chug,
            count=3,
        )
        motor = _live(wave='saw', filter=Filter('low_pass', 800.0), tremolo=chug)

        _chunks(_voice(channel, motor, frequency=177.0, volume=0.6), 3)

        for chunk, old_chunk in zip(rendered_chunks, expected, strict=True):
            np.testing.assert_allclose(chunk, old_chunk, atol=1e-9)

    def test_the_projectors_white_noise(self, channel, rendered_chunks):
        flutter = Tremolo(rate_hz=18.0, depth=0.3)
        expected = _the_older_voice_chunks(
            waveform=Waveform.NOISE,
            frequency=1.0,
            volume=0.3,
            cutoff=2500.0,
            flutter=flutter,
            count=2,
            random_source=np.random.default_rng(9),
        )
        projector = _live(noise='white', filter=Filter('low_pass', 2500.0), tremolo=flutter)
        voice = _voice(
            channel, projector, frequency=1.0, volume=0.3, random_source=np.random.default_rng(9)
        )

        _chunks(voice, 2)

        for chunk, old_chunk in zip(rendered_chunks, expected, strict=True):
            np.testing.assert_allclose(chunk, old_chunk, atol=1e-9)


class TestParameters:
    """AUD-GAME-001 to 003: set by name, clamped and counted, coalesced per chunk."""

    def test_a_thousand_sets_before_a_chunk_render_as_the_last_one(self, channel, rendered_chunks):
        """Updates coalesce: only the latest value per chunk counts (implementation spec 4.3)."""
        instrument = _speed_to('pitch', (100.0, 400.0))
        many = _voice(channel, instrument)
        many.stream.start()
        for step in range(1000):
            many.set('speed', step / 999 * 0.25)
        many.set('speed', 0.75)
        many.stream.update()
        coalesced = rendered_chunks[1]
        rendered_chunks.clear()
        once = _voice(channel, instrument)
        once.stream.start()
        once.set('speed', 0.75)
        once.stream.update()

        np.testing.assert_array_equal(coalesced, rendered_chunks[1])

    def test_a_value_outside_the_range_is_clamped_and_counted(self, channel, rendered_chunks):
        voice = _voice(channel, _speed_to('pitch', (100.0, 400.0)))

        assert voice.set('speed', 3.0)
        assert voice.set('speed', 0.5)
        assert voice.set('speed', -1.0)

        assert voice.parameter_values == {'speed': 0.0}
        assert voice.clamp_count == 2

    def test_a_parameter_starts_at_its_default_or_the_value_given(self, channel):
        instrument = _live(
            wave='sine',
            parameters={'speed': SPEED, 'load': Parameter(range=(0.0, 10.0), default=4.0)},
        )

        voice = _voice(channel, instrument, parameters={'speed': 0.5})

        assert voice.parameter_values == {'speed': 0.5, 'load': 4.0}

    def test_an_unknown_parameter_is_refused(self, channel):
        voice = _voice(channel, _speed_to('pitch', (100.0, 400.0)))

        with pytest.raises(ValueError, match=r"no parameter 'rpm'.*speed"):
            voice.set('rpm', 1.0)
        with pytest.raises(ValueError, match="no parameter 'rpm'"):
            _voice(channel, _speed_to('pitch', (100.0, 400.0)), parameters={'rpm': 1.0})

    def test_a_set_after_the_voice_stops_is_ignored(self, channel, rendered_chunks):
        voice = _voice(channel, _speed_to('pitch', (100.0, 400.0)))
        voice.stream.start()
        voice.stream.stop()

        assert not voice.set('speed', 1.0)
        assert voice.parameter_values == {'speed': 0.0}


class TestRoutes:
    """Each destination moves what the sound does, smoothed per sample."""

    def test_a_level_route_glides_one_pole_from_the_old_value(self, channel, rendered_chunks):
        """AUD-GAME-002: the chunk's level is the spec's closed-form glide, sample by sample."""
        gliding = Parameter(range=(0.0, 1.0), default=0.2, smoothing_ms=30.0)
        instrument = _live(
            wave='sine',
            parameters={'speed': gliding},
            routes=[Route(source='speed', destination='level', output=(0.0, 1.0))],
        )
        voice = _voice(channel, instrument)
        voice.stream.start()
        voice.set('speed', 0.9)
        voice.stream.update()
        steady = _voice(channel, _live(wave='sine'))
        steady.stream.start()
        steady.stream.update()
        gliding_chunk, plain_chunk = rendered_chunks[1], rendered_chunks[3]

        expected = smoothed(start=0.2, target=0.9, count=CHUNK, smoothing_ms=30.0, sample_rate=RATE)
        audible = np.abs(plain_chunk) > 0.1
        np.testing.assert_allclose(gliding_chunk[audible] / plain_chunk[audible], expected[audible])

    def test_a_glide_carries_on_across_chunks_from_where_it_got_to(self, channel, rendered_chunks):
        """A 200 ms glide spans two chunks: the second starts where the first ended."""
        slow = Parameter(range=(0.0, 1.0), default=0.0, smoothing_ms=200.0)
        instrument = _live(
            wave='sine',
            parameters={'speed': slow},
            routes=[Route(source='speed', destination='level', output=(0.0, 1.0))],
        )
        voice = _voice(channel, instrument)
        voice.set('speed', 1.0)
        _chunks(voice, 2)
        _chunks(_voice(channel, _live(wave='sine')), 2)
        gliding = np.concatenate(rendered_chunks[:2])
        plain = np.concatenate(rendered_chunks[2:])

        expected = smoothed(
            start=0.0, target=1.0, count=2 * CHUNK, smoothing_ms=200.0, sample_rate=RATE
        )
        audible = np.abs(plain) > 0.1
        np.testing.assert_allclose(gliding[audible] / plain[audible], expected[audible])

    def test_a_pitch_route_sets_the_frequency_by_its_curve(self, channel, rendered_chunks):
        """Exponential 100-400 Hz at the top of the range: 400 Hz, 80 crossings in 100 ms."""
        voice = _voice(channel, _speed_to('pitch', (100.0, 400.0), curve='exponential'))
        voice.stream.start()
        voice.set('speed', 1.0)
        voice.stream.update()

        assert abs(_zero_crossings(rendered_chunks[1]) - 80) <= 1
        assert abs(_zero_crossings(rendered_chunks[0]) - 20) <= 1  # 100 Hz before the set

    def test_a_source_level_route_moves_one_source(self, channel, rendered_chunks):
        """At level 0 the square source is gone: the chunk is the sine source alone."""
        instrument = _live(
            sources={'tone': Wave('sine'), 'buzz': Wave('square')},
            parameters={'speed': SPEED},
            routes=[Route(source='speed', destination='sources.buzz.level', output=(0.0, 1.0))],
        )
        _chunks(_voice(channel, instrument), 1)
        _chunks(_voice(channel, _live(wave='sine')), 1)

        np.testing.assert_allclose(rendered_chunks[0], rendered_chunks[1], atol=1e-12)

    def test_a_sources_own_level_and_semitones_are_rendered(self, channel, rendered_chunks):
        """A source an octave up at half level is the same as that sine at half volume."""
        instrument = _live(sources={'high': Source(Wave('sine'), level=0.5, semitones=12.0)})
        _chunks(_voice(channel, instrument), 1)
        _chunks(_voice(channel, _live(wave='sine'), frequency=440.0, volume=0.5), 1)

        np.testing.assert_allclose(rendered_chunks[0], rendered_chunks[1], atol=1e-9)

    def test_a_cutoff_route_moves_the_filter_without_a_click(self, channel, rendered_chunks):
        instrument = _speed_to(
            'filter.cutoff',
            (300.0, 4000.0),
            curve='exponential',
            wave='saw',
            filter=Filter('low_pass', 4000.0),
        )
        voice = _voice(channel, instrument, frequency=233.0)
        voice.stream.start()  # 0: at 300 Hz, where speed 0 puts it, from the first sample
        voice.set('speed', 1.0)
        voice.stream.update()  # 1: 300 to 4000 Hz
        voice.stream.update()  # 2: 4000 Hz
        voice.set('speed', 0.0)
        voice.stream.update()  # 3: 4000 to 300 Hz
        voice.stream.update()  # 4: 300 Hz

        def sharpest(chunk):
            return np.abs(np.diff(chunk)).max()

        assert abs(rendered_chunks[3][0] - rendered_chunks[2][-1]) < 0.2
        # 300 Hz keeps far less of a 233 Hz saw's edges than 4000 Hz does
        assert sharpest(rendered_chunks[0]) < sharpest(rendered_chunks[2]) / 3
        assert sharpest(rendered_chunks[4]) < sharpest(rendered_chunks[2]) / 3

    def test_a_filter_no_route_moves_keeps_its_own_cutoff(self, channel, rendered_chunks):
        """Routes elsewhere (here the level, at 1) leave the instrument's cutoff as it is."""
        routed = _speed_to('level', (0.5, 1.0), wave='saw', filter=Filter('low_pass', 900.0))
        _chunks(_voice(channel, routed, parameters={'speed': 1.0}), 2)
        _chunks(_voice(channel, _live(wave='saw', filter=Filter('low_pass', 900.0))), 2)

        np.testing.assert_allclose(rendered_chunks[1], rendered_chunks[3], atol=1e-12)

    def test_tremolo_depth_moves_live(self, channel, rendered_chunks):
        """Depth 0 by its route: the chunk is the untouched tone."""
        instrument = _speed_to('tremolo.depth', (0.0, 0.8), tremolo=Tremolo(rate_hz=6.0, depth=0.8))
        _chunks(_voice(channel, instrument), 1)
        _chunks(_voice(channel, _live(wave='sine')), 1)

        np.testing.assert_allclose(rendered_chunks[0], rendered_chunks[1], atol=1e-12)

    def test_tremolo_rate_moves_live(self, channel, rendered_chunks):
        """Rate 10 Hz from 1 Hz: the gain dips ten times in a second, not once."""
        instrument = _speed_to(
            'tremolo.rate', (1.0, 10.0), wave='square', tremolo=Tremolo(rate_hz=1.0, depth=1.0)
        )
        voice = _voice(channel, instrument, frequency=2000.0)
        voice.stream.start()
        voice.set('speed', 1.0)
        for _ in range(10):
            voice.stream.update()
        second = np.concatenate(rendered_chunks[1:11])
        envelope = np.abs(second).reshape(-1, 441).max(axis=1)  # 10 ms windows

        dips = np.count_nonzero(np.diff((envelope < 0.2).astype(int)) == 1)
        assert dips == 10


class TestWhatALiveVoiceRenders:
    """M2's live voices: sine, square, saw, triangle and white noise (the owner, 2026-11-14)."""

    @pytest.mark.parametrize(
        ('content', 'what'),
        [
            (Wave('pulse', duty=0.25), 'pulse'),
            (Wave.mix(square=0.5, triangle=0.5), 'mix'),
            ('my_registered_wave', 'my_registered_wave'),
            (Noise('lfsr'), 'lfsr'),
            (Noise('white', seed=4), 'seed'),
        ],
    )
    def test_a_source_a_live_voice_cannot_render_yet_is_refused(self, channel, content, what):
        with pytest.raises(ValueError, match=rf'live voice.*{what}'):
            _voice(channel, _live(sources={'main': content}))

    @pytest.mark.parametrize(
        ('source', 'what'),
        [
            (Source('sine', pitch=440.0), 'pitch'),
            (Source('sine', pitch_curve=PitchCurve(to=880.0, seconds=0.1)), 'pitch_curve'),
            (Source('sine', envelope='pad'), 'envelope'),
            (Source('sine', filter=Filter('low_pass', 900.0)), 'filter'),
        ],
    )
    def test_a_source_setting_a_live_voice_cannot_render_yet_is_refused(
        self, channel, source, what
    ):
        with pytest.raises(ValueError, match=rf'live voice.*{what}'):
            _voice(channel, _live(sources={'main': source}))

    def test_drive_is_refused(self, channel):
        with pytest.raises(ValueError, match=r'live voice.*drive'):
            _voice(channel, _live(wave='saw', drive=2.0))

    def test_an_instrument_that_is_not_live_is_refused(self, channel):
        with pytest.raises(ValueError, match='live=True'):
            _voice(channel, Instrument(wave='saw'))

    def test_a_cutoff_at_or_above_nyquist_is_refused(self, channel):
        instrument = _speed_to('filter.cutoff', (300.0, 30000.0), filter=Filter('low_pass', 1000.0))
        with pytest.raises(ValueError, match='Nyquist'):
            _voice(channel, instrument)


class TestOnTheLivePool:
    """An instrument voice is a pool voice: owner rules, silent tiles, channels returned."""

    @pytest.fixture(autouse=True)
    def partitioned_mixer(self):
        """Partition a stereo mixer as an outer engine does, declare one inner game.

        Yields:
            The default context's partition.
        """
        partition = start_reserved_mixer()
        reserve_inner_game_channels(games=1)
        yield partition
        pygame.mixer.stop()
        stop_mixer()

    def test_its_owner_leaving_releases_it_and_its_channel(self, partitioned_mixer):
        audio = LiveAudio(channel_indices=partitioned_mixer.live)
        voice = audio.create_instrument_voice(
            owner='scene', instrument=_live(wave='sine'), frequency=220.0
        )
        voice.stream.start()
        assert audio.playing_voice_count == 1

        audio.update(active_scene='another scene', previous_scene=None, active_transitions=())

        assert audio.playing_voice_count == 0
        assert voice.stream.is_finished
        audio.create_instrument_voice(owner='scene', instrument=_live(wave='sine'), frequency=1.0)

    def test_a_silent_tiles_voice_plays_at_volume_zero(self, partitioned_mixer):
        tile = EngineContext(name='tile')
        with tile.active():
            set_audible(audible=False)
            block = inner_context_partition(live_pool=4, library_channels=32)
            voice = LiveAudio(channel_indices=block.live).create_instrument_voice(
                owner='scene', instrument=_live(wave='sine'), frequency=220.0
            )
            voice.stream.start()

        assert pygame.mixer.Channel(block.live[0]).get_sound().get_volume() == 0.0
        voice.stream.stop_now()

    def test_without_a_mixer_it_is_silent(self, mocker):
        mocker.patch.object(pygame.mixer, 'get_init', return_value=None)
        audio = LiveAudio(channel_indices=(0,))

        voice = audio.create_instrument_voice(
            owner='scene', instrument=_live(wave='sine'), frequency=220.0
        )
        voice.stream.start()

        assert not voice.stream.is_playing
        assert audio.playing_voice_count == 0

    def test_without_a_mixer_a_refused_instrument_is_still_refused(self, mocker):
        """No channel was taken, so none goes back; the refusal is the same."""
        mocker.patch.object(pygame.mixer, 'get_init', return_value=None)

        with pytest.raises(ValueError, match='live=True'):
            LiveAudio(channel_indices=(0,)).create_instrument_voice(
                owner='scene', instrument=Instrument(wave='sine'), frequency=220.0
            )


class TestStartingALiveSound:
    """Sound.start() -> LiveSoundHandle (set, release, stop, is_playing; owner=)."""

    MOTOR = Instrument(
        wave='saw',
        live=True,
        parameters={'speed': SPEED},
        routes=[Route(source='speed', destination='pitch', output=(45.0, 110.0))],
    )

    @pytest.fixture(autouse=True)
    def partitioned_mixer(self):
        """A stereo mixer partitioned as an outer engine does; stopped after.

        Yields:
            The partition.
        """
        yield start_reserved_mixer()
        pygame.mixer.stop()
        stop_mixer()

    @pytest.fixture
    def pool(self, partitioned_mixer):
        """The live pool the audio engine starts live sounds on; its voices released after.

        Yields:
            The pool.
        """
        live_pool = LiveAudio(channel_indices=partitioned_mixer.live)
        yield live_pool
        live_pool.release_every_voice()

    def _engine(self, pool, *, scene='scene'):
        from glitchygames.audio.engine import AudioEngine
        from glitchygames.audio.voices import ChannelPartition

        return AudioEngine(
            partition=ChannelPartition(live=(), library=(), legacy_count=0),
            scene_source=lambda: scene,
            live_pool=lambda: pool,
        )

    def test_start_plays_on_the_pool_owned_by_the_scene(self, pool):
        handle = self._engine(pool).sound(self.MOTOR, pitch='A1').start(parameters={'speed': 0.5})

        assert handle.is_playing
        assert pool.playing_voice_count == 1
        assert handle.parameter_values == {'speed': 0.5}
        pool.update(active_scene='another scene', previous_scene=None, active_transitions=())
        assert not handle.is_playing

    def test_set_moves_it_and_counts_clamps(self, pool):
        handle = self._engine(pool).sound(self.MOTOR).start()

        assert handle.set('speed', 2.0)

        assert handle.parameter_values == {'speed': 1.0}
        assert handle.clamp_count == 1

    def test_release_fades_it_out_then_its_channel_returns(self, pool):
        handle = self._engine(pool).sound(self.MOTOR).start()

        assert handle.release()

        assert handle.is_playing  # fading
        assert not handle.set('speed', 1.0)
        assert not handle.release()

    def test_stop_ends_it_with_a_short_fade(self, pool):
        handle = self._engine(pool).sound(self.MOTOR).start()

        assert handle.stop(fade=0.005)
        assert not handle.stop()

    def test_cancel_ends_it_at_once_queued_chunk_and_all(self, pool, partitioned_mixer):
        """A fade renders into the next chunk, behind the queued one; cancel cuts both now."""
        handle = self._engine(pool).sound(self.MOTOR).start()
        pool.update(active_scene='scene', previous_scene=None, active_transitions=())

        assert handle.cancel()

        assert not handle.is_playing
        assert not pygame.mixer.Channel(partitioned_mixer.live[0]).get_busy()
        assert not handle.cancel()
        assert not handle.set('speed', 1.0)

    def test_a_transition_owned_voice_plays_through_the_ride_and_stops_with_it(self, pool):
        """The plan's test for start(owner=transition) (the elevator motor)."""
        ride = object()
        handle = self._engine(pool).sound(self.MOTOR).start(owner=ride)

        pool.update(active_scene='next floor', previous_scene=None, active_transitions=(ride,))
        assert handle.is_playing
        pool.update(active_scene='next floor', previous_scene=None, active_transitions=())
        assert not handle.is_playing

    def test_with_no_scene_and_no_owner_it_is_refused(self, pool):
        """No owner rule would keep it: the pool would release it on the next update."""
        with pytest.raises(ValueError, match='owner'):
            self._engine(pool, scene=None).sound(self.MOTOR).start()

    def test_the_volume_defaults_to_the_sound_files(self, pool, mocker):
        create = mocker.spy(pool, 'create_instrument_voice')

        self._engine(pool).sound(self.MOTOR).start()
        self._engine(pool).sound(self.MOTOR).start(volume=0.25)

        assert [call.kwargs['volume'] for call in create.call_args_list] == [1.0, 0.25]

    def test_start_passes_persist_pan_priority_the_bus_gain_and_the_instruments_chunk(
        self, pool, mocker
    ):
        create = mocker.spy(pool, 'create_instrument_voice')
        engine = self._engine(pool)
        engine.buses['music'].volume = 0.4

        quick = Instrument(
            wave='saw',
            live=True,
            chunk_seconds=0.05,
            parameters=dict(self.MOTOR.parameters),
            routes=self.MOTOR.routes,
        )

        engine.sound(quick).start(persist=True, pan=0.25, bus='music', priority=70)

        options = create.call_args.kwargs['options']
        assert (options.persist, options.pan, options.priority) == (True, 0.25, 70)
        assert options.chunk_seconds == 0.05  # the instrument's
        assert options.gain_source() == pytest.approx(0.4)

    def test_the_bus_and_priority_default_to_the_sound_files(self, pool, mocker):
        create = mocker.spy(pool, 'create_instrument_voice')

        self._engine(pool).sound(self.MOTOR).start()

        options = create.call_args.kwargs['options']
        assert (options.priority, options.pan, options.persist) == (50, 0.0, False)
        assert options.gain_source() == pytest.approx(1.0)  # the effects bus, untouched

    def test_with_no_pan_given_it_takes_the_sound_files_as_play_does(self, pool, mocker):
        from glitchygames.audio.spec import PlaybackDefaults

        create = mocker.spy(pool, 'create_instrument_voice')
        sound = self._engine(pool).sound(self.MOTOR)
        sound.playback_defaults = PlaybackDefaults(pan=-0.5)

        sound.start()
        sound.start(pan=0.75)

        assert [call.kwargs['options'].pan for call in create.call_args_list] == [-0.5, 0.75]

    def test_an_unknown_bus_is_refused(self, pool):
        with pytest.raises(KeyError, match='nowhere'):
            self._engine(pool).sound(self.MOTOR).start(bus='nowhere')

    def test_an_engine_with_no_pool_starts_it_silently(self, caplog):
        from glitchygames.audio.engine import AudioEngine
        from glitchygames.audio.voices import ChannelPartition

        engine = AudioEngine(
            partition=ChannelPartition(live=(), library=(), legacy_count=0),
            scene_source=lambda: 'scene',
        )

        handles = [engine.sound(self.MOTOR).start() for _ in range(2)]

        assert not any(handle.is_playing or handle.set('speed', 1.0) for handle in handles)
        assert not any(handle.cancel() for handle in handles)
        assert caplog.text.count('no live voice pool') == 1


class TestTheHandlesControls:
    """Volume, pause and pan on a started live sound (migration step 7b)."""

    def _handle(self, channel, **voice_settings):
        from glitchygames.audio.live_instrument import LiveSoundHandle

        voice = _voice(channel, _live(wave='sine'), **voice_settings)
        voice.stream.start()
        return LiveSoundHandle(voice)

    def test_set_volume_glides_linearly_over_the_fade(self, channel, rendered_chunks):
        """0.5 to 0 over 200 ms: the next chunk goes 0.5 to 0.25, the one after 0.25 to 0."""
        handle = self._handle(channel, volume=0.5)
        _chunks(_voice(channel, _live(wave='sine')), 3)
        plain = rendered_chunks[1:]

        assert handle.set_volume(0.0, fade=0.2)
        handle._voice.stream.update()
        handle._voice.stream.update()

        steps = np.arange(1, 2 * CHUNK + 1) / (2 * CHUNK)
        expected = 0.5 + (0.0 - 0.5) * steps
        gliding = np.concatenate(rendered_chunks[-2:])
        reference = np.concatenate(plain[:2])
        audible = np.abs(reference) > 0.1
        np.testing.assert_allclose(gliding[audible] / reference[audible], expected[audible])

    def test_set_volume_without_a_fade_takes_one_chunk(self, channel, rendered_chunks):
        """The old voice's volume ramp: across the next chunk, so it never clicks."""
        handle = self._handle(channel, volume=0.5)

        handle.set_volume(1.0)
        handle._voice.stream.update()

        envelope = np.abs(rendered_chunks[-1])
        assert envelope[:100].max() < 0.55
        assert envelope[-200:].max() > 0.95

    @pytest.mark.parametrize('volume', [-0.1, 1.1])
    def test_a_volume_outside_zero_to_one_is_refused(self, channel, volume):
        with pytest.raises(ValueError, match='volume'):
            self._handle(channel).set_volume(volume)

    def test_a_negative_fade_is_refused(self, channel):
        with pytest.raises(ValueError, match='fade'):
            self._handle(channel).set_volume(0.5, fade=-0.1)

    def test_pause_and_resume(self, channel, rendered_chunks):
        handle = self._handle(channel)

        assert handle.pause()
        assert handle.is_paused
        assert not handle.pause()
        assert handle.resume()

        assert not handle.is_paused
        assert not handle.resume()

    def test_set_pan_takes_the_constant_power_law(self, channel, rendered_chunks):
        from glitchygames.audio.voices import constant_power_gains

        handle = self._handle(channel)

        assert handle.set_pan(-0.5)
        channel.set_volume.assert_called_with(*constant_power_gains(pan=-0.5, gain=1.0))

    def test_every_control_on_a_stopped_or_silent_handle_answers_false(self, channel):
        from glitchygames.audio.live_instrument import LiveSoundHandle

        stopped = self._handle(channel)
        stopped.cancel()
        for handle in (stopped, LiveSoundHandle(None)):
            assert not handle.set_volume(0.5)
            assert not handle.pause()
            assert not handle.resume()
            assert not handle.set_pan(0.0)
            assert not handle.is_paused


def test_both_kinds_of_handle_are_a_playing_sound():
    """Code that only stops or fades a sound takes either kind (a menu's "fade all out")."""
    from glitchygames.audio.live_instrument import LiveSoundHandle
    from glitchygames.audio.voices import PlayingSound, SoundHandle

    baked: PlayingSound = SoundHandle(slot=-1, generation=-1)
    live: PlayingSound = LiveSoundHandle(None)

    for handle in (baked, live):
        assert isinstance(handle, PlayingSound)
        assert not handle.stop(fade=0.05)
        assert not handle.is_playing


class TestDirectSettings:
    """Frequency, cutoff and tremolo set straight on a playing sound (migration step 7b)."""

    def _handle(self, channel, instrument, **voice_settings):
        from glitchygames.audio.live_instrument import LiveSoundHandle

        voice = _voice(channel, instrument, **voice_settings)
        voice.stream.start()
        return LiveSoundHandle(voice)

    def test_set_frequency_glides_over_one_chunk_then_holds(self, channel, rendered_chunks):
        """The old voice's ramp: 220 to 440 Hz across the next chunk, then 88 crossings."""
        handle = self._handle(channel, _live(wave='sine'), frequency=220.0)

        assert handle.set_frequency(440.0)
        handle._voice.stream.update()
        handle._voice.stream.update()

        assert abs(rendered_chunks[1][0] - rendered_chunks[0][-1]) < 0.1  # no click
        assert abs(_zero_crossings(rendered_chunks[2]) - 88) <= 1

    def test_set_cutoff_adds_a_low_pass_and_none_removes_it(self, channel, rendered_chunks):
        def sharpest(chunk):
            return np.abs(np.diff(chunk)).max()

        handle = self._handle(channel, _live(wave='saw'), frequency=233.0)
        assert handle.set_cutoff(300.0)
        for _ in range(2):
            handle._voice.stream.update()
        assert handle.set_cutoff(None)
        for _ in range(2):
            handle._voice.stream.update()

        assert sharpest(rendered_chunks[2]) < sharpest(rendered_chunks[0]) / 3
        assert sharpest(rendered_chunks[4]) == pytest.approx(sharpest(rendered_chunks[0]), rel=0.2)

    def test_set_tremolo_adds_one_and_none_takes_it_away(self, channel, rendered_chunks):
        """Off again, the chunk is the untouched tone, phase and all."""
        handle = self._handle(channel, _live(wave='sine'))
        _chunks(_voice(channel, _live(wave='sine')), 3)
        plain = rendered_chunks[-3:]
        del rendered_chunks[-3:]

        assert handle.set_tremolo(Tremolo(rate_hz=10.0, depth=1.0))
        handle._voice.stream.update()
        assert handle.set_tremolo(None)
        handle._voice.stream.update()

        assert np.abs(rendered_chunks[1]).min() < 0.01  # dipping to silence
        np.testing.assert_allclose(rendered_chunks[2], plain[2], atol=1e-12)

    @pytest.mark.parametrize(
        ('destination', 'output', 'setting'),
        [
            ('pitch', (100.0, 400.0), ('set_frequency', 300.0)),
            ('filter.cutoff', (300.0, 3000.0), ('set_cutoff', 800.0)),
            ('tremolo.rate', (2.0, 9.0), ('set_tremolo', None)),
        ],
    )
    def test_a_direct_setting_of_what_a_route_moves_is_refused(
        self, channel, destination, output, setting
    ):
        """[Call, the plan's 7b.6] One of them would silently win; neither does."""
        instrument = _speed_to(
            destination,
            output,
            filter=Filter('low_pass', 3000.0),
            tremolo=Tremolo(rate_hz=4.0, depth=0.5),
        )
        name, value = setting

        with pytest.raises(ValueError, match=rf'route.*{destination}'):
            getattr(self._handle(channel, instrument), name)(value)

    def test_a_direct_setting_beside_routes_elsewhere_is_taken(self, channel, rendered_chunks):
        """Only what a route moves is refused: a level route leaves the pitch free."""
        handle = self._handle(channel, _speed_to('level', (0.2, 1.0)), frequency=220.0)

        assert handle.set_frequency(440.0)

    @pytest.mark.parametrize(
        ('setting', 'match'),
        [
            (('set_frequency', 0.0), 'frequency'),
            (('set_cutoff', 30000.0), 'Nyquist'),
            (('set_cutoff', 0.0), 'cutoff'),
            (('set_tremolo', Tremolo(rate_hz=5.0, depth=1.5)), 'depth'),
            (('set_tremolo', Tremolo(rate_hz=0.0, depth=0.5)), 'rate'),
        ],
    )
    def test_a_setting_that_cannot_sound_is_refused(self, channel, setting, match):
        name, value = setting

        with pytest.raises(ValueError, match=match):
            getattr(self._handle(channel, _live(wave='sine')), name)(value)

    def test_a_stopped_or_silent_handle_takes_no_settings(self, channel):
        from glitchygames.audio.live_instrument import LiveSoundHandle

        stopped = self._handle(channel, _live(wave='sine'))
        stopped.cancel()
        for handle in (stopped, LiveSoundHandle(None)):
            assert not handle.set_frequency(330.0)
            assert not handle.set_cutoff(800.0)
            assert not handle.set_tremolo(None)


class TestLinearGlides:
    """Parameter(glide='linear'): a straight line to the target over smoothing_ms."""

    def test_a_linear_glide_reaches_its_target_in_a_straight_line(self, channel, rendered_chunks):
        """100 ms to go from 0 to 1: exactly the next chunk, then it holds."""
        straight = Parameter(range=(0.0, 1.0), default=0.0, smoothing_ms=100.0, glide='linear')
        instrument = _live(
            wave='sine',
            parameters={'speed': straight},
            routes=[Route(source='speed', destination='level', output=(0.0, 1.0))],
        )
        voice = _voice(channel, instrument)
        voice.stream.start()
        voice.set('speed', 1.0)
        voice.stream.update()
        voice.stream.update()
        _chunks(_voice(channel, _live(wave='sine')), 3)
        gliding, held = rendered_chunks[1], rendered_chunks[2]
        plain_gliding, plain_held = rendered_chunks[4], rendered_chunks[5]

        audible = np.abs(plain_gliding) > 0.1
        expected = np.arange(1, CHUNK + 1) / CHUNK
        np.testing.assert_allclose(gliding[audible] / plain_gliding[audible], expected[audible])
        np.testing.assert_allclose(held, plain_held, atol=1e-12)

    def test_a_new_target_mid_glide_starts_a_new_line_from_where_it_got_to(
        self, channel, rendered_chunks
    ):
        """Half way to 1 after 100 ms of a 200 ms glide, then back to 0 over 200 ms from 0.5."""
        straight = Parameter(range=(0.0, 1.0), default=0.0, smoothing_ms=200.0, glide='linear')
        instrument = _live(
            wave='sine',
            parameters={'speed': straight},
            routes=[Route(source='speed', destination='level', output=(0.0, 1.0))],
        )
        voice = _voice(channel, instrument)
        voice.stream.start()
        voice.set('speed', 1.0)
        voice.stream.update()
        voice.set('speed', 0.0)
        voice.stream.update()
        _chunks(_voice(channel, _live(wave='sine')), 3)
        plain = rendered_chunks[3:]

        audible = np.abs(plain[2]) > 0.1
        steps = np.arange(1, CHUNK + 1) / (2 * CHUNK)
        expected = 0.5 + (0.0 - 0.5) * steps
        np.testing.assert_allclose(
            rendered_chunks[2][audible] / plain[2][audible], expected[audible]
        )


class TestAnAudioEngineOutsideAGame:
    """A tool's own audio engine (what SoundBank offered): plays, live sounds, one update."""

    @pytest.fixture(autouse=True)
    def partitioned_mixer(self):
        """A stereo mixer partitioned as an engine does; stopped after.

        Yields:
            The partition.
        """
        yield start_reserved_mixer()
        pygame.mixer.stop()
        stop_mixer()

    def test_baked_and_live_sounds_play_and_one_update_a_frame_moves_both(self, partitioned_mixer):
        """The baked click ends by played time; the live drone plays on until stopped."""
        from glitchygames.audio import AudioEngine, Effect, LiveAudio, Tone
        from glitchygames.audio.synth import Envelope

        tool = object()  # what owns the tool's sounds, as a scene owns a game's
        pool = LiveAudio(channel_indices=partitioned_mixer.live)
        engine = AudioEngine(
            partition=partitioned_mixer, scene_source=lambda: tool, live_pool=lambda: pool
        )
        blip = Tone(
            waveform=Waveform.SQUARE,
            start_frequency=880.0,
            duration=0.05,
            envelope=Envelope(attack=0.001, decay=0.0, sustain_level=1.0, release=0.01),
        )
        click = engine.sound(Effect(name='click', tones=(blip,))).play()
        drone = engine.sound(Instrument(wave='sine', live=True), pitch='A3').start()

        for _ in range(12):  # 0.2 s of frames
            engine.update(dt=1 / 60, active_scene=tool, previous_scene=None, active_transitions=())

        assert not click.is_playing
        assert drone.is_playing
        assert pygame.mixer.Channel(partitioned_mixer.live[0]).get_queue() is not None
        assert drone.stop()
        pool.release_every_voice()

    def test_the_engines_update_applies_the_live_owner_rules(self, partitioned_mixer):
        """When its owner is no longer active, a live sound is released by the next update."""
        from glitchygames.audio import AudioEngine, LiveAudio

        tool, other = object(), object()
        pool = LiveAudio(channel_indices=partitioned_mixer.live)
        engine = AudioEngine(
            partition=partitioned_mixer, scene_source=lambda: tool, live_pool=lambda: pool
        )
        drone = engine.sound(Instrument(wave='sine', live=True), pitch='A3').start()

        engine.update(dt=1 / 60, active_scene=other, previous_scene=None, active_transitions=())

        assert not drone.is_playing
        assert pool.playing_voice_count == 0
