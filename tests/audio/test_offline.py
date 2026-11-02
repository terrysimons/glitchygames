"""Tests for offline rendering: ``render_to_file`` writes a sound (and events) to a WAV file."""

import dataclasses
import struct
import wave
from typing import TYPE_CHECKING

import numpy as np
import pygame
import pytest

from glitchygames.audio import OfflineEvent, RenderReport, render_to_file
from glitchygames.audio.assets import clear_sound_file_cache
from glitchygames.audio.instrument import Instrument
from glitchygames.audio.library import CacheMode
from glitchygames.audio.offline import (
    QUIET_LEVEL,
    QUIET_SECONDS,
    WAVE_FORMAT_IEEE_FLOAT,
    nominal_end_frame,
)
from glitchygames.audio.recipes import SoundRecipe, Tone
from glitchygames.audio.render import render_sound
from glitchygames.audio.spec import EnvelopeSpec
from glitchygames.audio.synth import Envelope, Waveform, to_pcm16
from glitchygames.audio.voices import constant_power_gains
from glitchygames.engine_context import EngineContext
from tests.audio.library_support import (
    PULSE_INSTRUMENT,
    make_library,
    stop_mixer,
    write_wave_file,
)

if TYPE_CHECKING:
    from pathlib import Path

SAMPLE_RATE = 44100
# A held tone whose release steps to silence for its last quarter (steps(2): a level under 0.25
# rounds to 0), so its tail is silent for 0.25 s after the release starts at a full level
STEPPED_RELEASE_INSTRUMENT = Instrument(
    wave='square',
    envelope=EnvelopeSpec(attack=0.0, decay=0.0, sustain=1.0, release=1.0, curve='steps(2)'),
)
# Two sounds on two buses, for the stems
BUSES_SOUND_FILE = """\
[glitchygames]
kind = "sounds"
version = 1

[instruments.blip.sources.tone]
wave = "square"

[sounds.hit]
instrument = "blip"
pitch = "C5"

[sounds.theme]
instrument = "blip"
pitch = "G4"
bus = "music"
"""
LEGACY_RECIPE = SoundRecipe(
    name='beep_like',
    tones=(
        Tone(
            waveform=Waveform.SINE,
            start_frequency=660.0,
            duration=0.05,
            envelope=Envelope(attack=0.001, decay=0.01, sustain_level=0.5, release=0.02),
        ),
    ),
)


@pytest.fixture(autouse=True)
def _isolated_context_and_file_cache():
    clear_sound_file_cache()
    with EngineContext(name='offline render test').active():
        yield
    clear_sound_file_cache()


@pytest.fixture
def library_without_mixer():
    """A ``ram`` library with no mixer running (the mixer is stopped again afterwards).

    Yields:
        The library.
    """
    stop_mixer()
    library, _ = make_library()
    yield library
    stop_mixer()


def read_wav_int16(path: Path) -> np.ndarray:
    """Read a 16-bit PCM WAV file.

    Returns:
        Its samples: one dimension when mono, (frames, channels) otherwise.
    """
    with wave.open(str(path), 'rb') as wave_file:
        assert wave_file.getsampwidth() == 2
        channels = wave_file.getnchannels()
        raw = wave_file.readframes(wave_file.getnframes())
    samples = np.frombuffer(raw, dtype='<i2')
    return samples if channels == 1 else samples.reshape(-1, channels)


def wav_rate(path: Path) -> int:
    """Return a PCM WAV file's sample rate."""
    with wave.open(str(path), 'rb') as wave_file:
        return wave_file.getframerate()


def read_wav_float32(path: Path) -> tuple[np.ndarray, int]:
    """Read an IEEE float WAV file (the standard library's ``wave`` reads only PCM).

    Returns:
        Its samples (one dimension when mono, (frames, channels) otherwise) and its rate.
    """
    data = path.read_bytes()
    assert data[:4] == b'RIFF'
    assert data[8:12] == b'WAVE'
    assert struct.unpack('<I', data[4:8])[0] == len(data) - 8
    position = 12
    chunks: dict[bytes, bytes] = {}
    while position < len(data):
        chunk_id = data[position : position + 4]
        size = struct.unpack('<I', data[position + 4 : position + 8])[0]
        chunks[chunk_id] = data[position + 8 : position + 8 + size]
        position += 8 + size + (size % 2)
    format_tag, channels, rate, byte_rate, block_align, bits = struct.unpack(
        '<HHIIHH', chunks[b'fmt '][:16]
    )
    assert format_tag == WAVE_FORMAT_IEEE_FLOAT
    assert bits == 32
    assert block_align == channels * 4
    assert byte_rate == rate * block_align
    samples = np.frombuffer(chunks[b'data'], dtype='<f4')
    frames = len(samples) // channels
    assert struct.unpack('<I', chunks[b'fact'])[0] == frames
    return (samples if channels == 1 else samples.reshape(-1, channels)), rate


def test_offline_render_equals_the_compiled_buffer_bit_for_bit(tmp_path, library_without_mixer):
    """A sound alone, at offset 0, is written as its compiled int16 buffer (AUD-FUNC-008)."""
    sound = library_without_mixer.sound(
        PULSE_INSTRUMENT, scene_sound_directory=None, notes='B5:0.06 E6:0.18'
    )

    report = render_to_file(sound, tmp_path / 'coin.wav')

    assert isinstance(report, RenderReport)
    assert report.path == tmp_path / 'coin.wav'
    assert np.array_equal(read_wav_int16(report.path), sound.samples_int16)
    assert report.frames == len(sound.samples_int16)
    assert report.peak == pytest.approx(float(np.max(np.abs(sound.samples_float))))
    assert report.clip_count == 0
    assert wav_rate(report.path) == SAMPLE_RATE


def test_offline_rendering_opens_no_audio_device(tmp_path, library_without_mixer):
    """Rendering runs with no mixer and leaves none running."""
    sound = library_without_mixer.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5')

    render_to_file(sound, tmp_path / 'tone.wav')

    assert pygame.mixer.get_init() is None


def test_a_sound_not_yet_compiled_is_compiled_through_the_librarys_path(tmp_path):
    """Under cache ``none`` the sound holds no samples; the render compiles a copy of it.

    The written samples equal a ``ram`` library's compile of the same request, and the sound
    itself stays uncompiled (its cache mode is the library's business).
    """
    stop_mixer()
    uncached_library, _ = make_library(CacheMode.NONE)
    cached_library, _ = make_library(CacheMode.RAM)
    uncompiled = uncached_library.sound(
        PULSE_INSTRUMENT, scene_sound_directory=None, notes='B5:0.06 E6:0.18'
    )
    compiled = cached_library.sound(
        PULSE_INSTRUMENT, scene_sound_directory=None, notes='B5:0.06 E6:0.18'
    )
    assert not uncompiled.is_compiled

    report = render_to_file(uncompiled, tmp_path / 'coin.wav')

    assert compiled.samples_int16 is not None
    assert np.array_equal(read_wav_int16(report.path), compiled.samples_int16)
    assert not uncompiled.is_compiled


def test_a_version_0_recipe_renders_as_it_compiles(tmp_path, library_without_mixer):
    """A version 0 recipe's render is its legacy compile, bit for bit."""
    library_without_mixer.add_recipes([LEGACY_RECIPE])
    sound = library_without_mixer.sound('beep_like', scene_sound_directory=None)

    report = render_to_file(sound, tmp_path / 'beep.wav')

    assert np.array_equal(read_wav_int16(report.path), sound.samples_int16)


def test_a_recorded_wav_renders_as_it_decodes(tmp_path, library_without_mixer):
    """A recorded WAV sound is written as its decoded samples."""
    source = write_wave_file(tmp_path / 'ramp.wav', frames=441)
    sound = library_without_mixer.sound(str(source), scene_sound_directory=None)

    report = render_to_file(sound, tmp_path / 'out.wav')

    assert np.array_equal(read_wav_int16(report.path), sound.samples_int16)


def test_events_mix_at_exact_sample_offsets(tmp_path, library_without_mixer):
    """Each event's samples are added at round(seconds x rate), scaled by its volume."""
    first = library_without_mixer.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5')
    second = library_without_mixer.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='G5')
    event_seconds = 0.1234567
    offset = round(event_seconds * SAMPLE_RATE)

    report = render_to_file(
        first,
        tmp_path / 'mix.wav',
        sample_format='float32',
        events=[OfflineEvent(seconds=event_seconds, sound=second, volume=0.5)],
    )

    expected = np.zeros(max(len(first.samples_float), offset + len(second.samples_float)))
    expected[: len(first.samples_float)] += first.samples_float
    expected[offset : offset + len(second.samples_float)] += 0.5 * second.samples_float
    written, rate = read_wav_float32(report.path)
    assert rate == SAMPLE_RATE
    assert written.ndim == 1
    assert np.array_equal(written, expected.astype(np.float32))
    assert report.frames == len(expected)


def test_a_panned_event_makes_the_output_stereo_with_the_voices_pan_law(
    tmp_path, library_without_mixer
):
    """Any panned event makes the output stereo; every event takes the constant-power gains."""
    sound = library_without_mixer.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5')
    other = library_without_mixer.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='E5')

    report = render_to_file(
        sound,
        tmp_path / 'stereo.wav',
        sample_format='float32',
        events=[OfflineEvent(seconds=0.0, sound=other, volume=0.8, pan=-0.5)],
    )

    written, _ = read_wav_float32(report.path)
    assert written.shape == (len(sound.samples_float), 2)
    centre_left, centre_right = constant_power_gains(pan=0.0, gain=1.0)
    other_left, other_right = constant_power_gains(pan=-0.5, gain=0.8)
    expected_left = centre_left * sound.samples_float + other_left * other.samples_float
    expected_right = centre_right * sound.samples_float + other_right * other.samples_float
    assert np.array_equal(written[:, 0], expected_left.astype(np.float32))
    assert np.array_equal(written[:, 1], expected_right.astype(np.float32))


def test_loops_repeat_the_sound_back_to_back(tmp_path, library_without_mixer):
    """``loops=3`` writes the buffer three times in a row."""
    sound = library_without_mixer.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5')

    report = render_to_file(sound, tmp_path / 'looped.wav', loops=3)

    assert np.array_equal(read_wav_int16(report.path), np.tile(sound.samples_int16, 3))
    assert report.frames == 3 * len(sound.samples_int16)


def test_the_nominal_end_of_an_instrument_sound_is_its_last_gate(library_without_mixer):
    """An instrument sound's nominal end is where its last note's gate ends; others' their end."""
    sound = library_without_mixer.sound(
        PULSE_INSTRUMENT, scene_sound_directory=None, notes='B5:0.06 E6:0.18'
    )
    library_without_mixer.add_recipes([LEGACY_RECIPE])
    legacy = library_without_mixer.sound('beep_like', scene_sound_directory=None)

    assert nominal_end_frame(sound, sample_rate=SAMPLE_RATE) == round(0.06 * SAMPLE_RATE) + round(
        0.18 * SAMPLE_RATE
    )
    assert nominal_end_frame(legacy, sample_rate=SAMPLE_RATE) == len(legacy.samples_float)


def test_tail_stops_after_100_ms_below_minus_90_dbfs(tmp_path, library_without_mixer):
    """After the last nominal end, the render stops once the output stays quiet for 100 ms.

    The stepped release is silent for its last 0.25 s: the file keeps 100 ms of that silence
    and drops the rest.
    """
    sound = library_without_mixer.sound(
        STEPPED_RELEASE_INSTRUMENT, scene_sound_directory=None, pitch='A4', length=0.2
    )
    samples = sound.samples_float
    gate_end = round(0.2 * SAMPLE_RATE)
    loud = np.flatnonzero(np.abs(samples[gate_end:]) >= QUIET_LEVEL)
    quiet_from = gate_end + int(loud[-1]) + 1
    window = round(QUIET_SECONDS * SAMPLE_RATE)
    assert len(samples) - quiet_from > window  # the sound's own tail is longer than the window

    report = render_to_file(sound, tmp_path / 'tail.wav')

    assert pytest.approx(10.0 ** (-90.0 / 20.0)) == QUIET_LEVEL
    assert pytest.approx(0.1) == QUIET_SECONDS
    assert report.frames == quiet_from + window
    assert np.array_equal(read_wav_int16(report.path), sound.samples_int16[: quiet_from + window])


def test_tail_seconds_ends_the_render_earlier(tmp_path, library_without_mixer):
    """``tail_seconds`` stops the render that long after the nominal end, if that is sooner."""
    sound = library_without_mixer.sound(
        STEPPED_RELEASE_INSTRUMENT, scene_sound_directory=None, pitch='A4', length=0.2
    )

    report = render_to_file(sound, tmp_path / 'short.wav', tail_seconds=0.05)

    expected_frames = round(0.2 * SAMPLE_RATE) + round(0.05 * SAMPLE_RATE)
    assert report.frames == expected_frames
    assert np.array_equal(read_wav_int16(report.path), sound.samples_int16[:expected_frames])


def test_a_quiet_stretch_cut_short_by_the_end_keeps_the_whole_buffer(
    tmp_path, library_without_mixer
):
    """A quiet stretch shorter than 100 ms at the end stops nothing: the whole mix is written."""
    sound = library_without_mixer.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5')
    late = library_without_mixer.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C6')
    # Silence between the two (a gap of 50 ms after the first ends), then the second sound
    gap_start = len(sound.samples_float) / SAMPLE_RATE
    event_seconds = gap_start + 0.05

    report = render_to_file(
        sound, tmp_path / 'gap.wav', events=[OfflineEvent(seconds=event_seconds, sound=late)]
    )

    assert report.frames == round(event_seconds * SAMPLE_RATE) + len(late.samples_float)


def test_float32_output_keeps_overs_and_reports_clips(tmp_path, library_without_mixer):
    """Overs stay in float32 output and are counted; int16 output clips them, counted alike."""
    sound = library_without_mixer.sound(
        Instrument(wave='square', envelope='organ', normalize=True),
        scene_sound_directory=None,
        pitch='C4',
    )
    stacked = [OfflineEvent(seconds=0.0, sound=sound) for _ in range(2)]

    floating = render_to_file(sound, tmp_path / 'over.wav', sample_format='float32', events=stacked)
    clipped = render_to_file(sound, tmp_path / 'clipped.wav', events=stacked)

    tripled = 3.0 * sound.samples_float
    expected_clips = int(np.count_nonzero(np.abs(tripled) > 1.0))
    assert expected_clips > 0
    written, _ = read_wav_float32(floating.path)
    assert np.array_equal(written, tripled.astype(np.float32))
    assert float(np.max(np.abs(written))) > 1.0
    assert floating.clip_count == clipped.clip_count == expected_clips
    assert floating.peak == pytest.approx(float(np.max(np.abs(tripled))))
    assert np.array_equal(read_wav_int16(clipped.path), to_pcm16(tripled))


def test_another_sample_rate_compiles_the_sound_at_that_rate(tmp_path, library_without_mixer):
    """``sample_rate`` renders an instrument sound's spec at that rate, through its compile."""
    sound = library_without_mixer.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5')
    assert sound.spec is not None

    report = render_to_file(sound, tmp_path / 'low.wav', sample_rate=22050)

    expected = to_pcm16(render_sound(dataclasses.replace(sound.spec, sample_rate=22050)).samples)
    assert wav_rate(report.path) == 22050
    assert np.array_equal(read_wav_int16(report.path), expected)
    assert sound.sample_rate == SAMPLE_RATE  # the sound itself is unchanged


def test_a_recorded_sound_at_another_rate_is_resampled(tmp_path, library_without_mixer):
    """A recorded sound's samples are resampled (linearly) to the render's rate."""
    source = write_wave_file(tmp_path / 'ramp.wav', frames=441, sample_rate=22050)
    sound = library_without_mixer.sound(str(source), scene_sound_directory=None)

    report = render_to_file(sound, tmp_path / 'up.wav', sample_rate=44100)

    written = read_wav_int16(report.path)
    assert wav_rate(report.path) == 44100
    assert len(written) == 882
    assert written[0] == sound.samples_int16[0]
    assert written[-2] == sound.samples_int16[-1]


def test_stems_write_one_stereo_file_per_bus_beside_the_mix(tmp_path, library_without_mixer):
    """``stems=True``: the mix is stereo, and each bus's events go to ``<stem>.<bus>.wav``."""
    sound_file = tmp_path / 'buses.toml'
    sound_file.write_text(BUSES_SOUND_FILE, encoding='utf-8')
    effect = library_without_mixer.sound(f'{sound_file}#hit', scene_sound_directory=None)
    music_sound = library_without_mixer.sound(f'{sound_file}#theme', scene_sound_directory=None)

    report = render_to_file(
        effect,
        tmp_path / 'mix.wav',
        sample_format='float32',
        stems=True,
        events=[OfflineEvent(seconds=0.01, sound=music_sound)],
    )

    mix, _ = read_wav_float32(report.path)
    effects_stem, _ = read_wav_float32(tmp_path / 'mix.effects.wav')
    music_stem, _ = read_wav_float32(tmp_path / 'mix.music.wav')
    assert report.stem_paths == (tmp_path / 'mix.effects.wav', tmp_path / 'mix.music.wav')
    assert mix.shape[1] == effects_stem.shape[1] == music_stem.shape[1] == 2
    assert mix.shape == effects_stem.shape == music_stem.shape
    assert np.allclose(mix, effects_stem + music_stem, atol=1e-6)
    left, _ = constant_power_gains(pan=0.0, gain=1.0)
    assert np.array_equal(
        effects_stem[: len(effect.samples_float), 0],
        (left * effect.samples_float).astype(np.float32),
    )


def test_a_parameter_timeline_is_refused_until_live_sounds_arrive(tmp_path, library_without_mixer):
    """Live sounds (and so parameter timelines) arrive in M2."""
    sound = library_without_mixer.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5')

    with pytest.raises(ValueError, match='live sounds arrive in M2'):
        render_to_file(sound, tmp_path / 'live.wav', parameter_timeline={'rpm': [(0.0, 800.0)]})

    assert not (tmp_path / 'live.wav').exists()


@pytest.mark.parametrize(
    ('arguments', 'message'),
    [
        ({'sample_format': 'int24'}, "sample_format must be 'int16' or 'float32'"),
        ({'loops': 0}, 'loops must be at least 1'),
        ({'tail_seconds': -0.1}, 'tail_seconds must be at least 0'),
        ({'sample_rate': 0}, 'sample_rate must be positive'),
    ],
)
def test_invalid_arguments_are_refused(tmp_path, library_without_mixer, arguments, message):
    """Each argument out of its range is a ValueError naming it; nothing is written."""
    sound = library_without_mixer.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5')

    with pytest.raises(ValueError, match=message):
        render_to_file(sound, tmp_path / 'bad.wav', **arguments)

    assert not (tmp_path / 'bad.wav').exists()


def test_an_event_before_the_start_is_refused(tmp_path, library_without_mixer):
    """An event at a negative time is a ValueError."""
    sound = library_without_mixer.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5')

    with pytest.raises(ValueError, match='an event starts at 0 seconds or later'):
        render_to_file(
            sound, tmp_path / 'bad.wav', events=[OfflineEvent(seconds=-1.0, sound=sound)]
        )


def test_an_event_panned_out_of_range_is_refused(tmp_path, library_without_mixer):
    """An event's pan outside -1..1 is a ValueError."""
    sound = library_without_mixer.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5')

    with pytest.raises(ValueError, match=r'pan must be between -1\.0 and 1\.0'):
        render_to_file(
            sound, tmp_path / 'bad.wav', events=[OfflineEvent(seconds=0.0, sound=sound, pan=2.0)]
        )


def test_an_unwritable_output_raises_and_leaves_no_partial_file(tmp_path, library_without_mixer):
    """A path that cannot be written raises OSError; no partial file is left beside it."""
    sound = library_without_mixer.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5')
    directory = tmp_path / 'taken'
    directory.mkdir()

    with pytest.raises(OSError, match='taken'):
        render_to_file(sound, directory)

    assert sorted(path.name for path in tmp_path.iterdir()) == ['taken']


def test_the_offline_names_are_exported_from_the_audio_package():
    """``render_to_file``, ``OfflineEvent`` and ``RenderReport`` come from glitchygames.audio."""
    from glitchygames import audio

    assert {'render_to_file', 'OfflineEvent', 'RenderReport'} <= set(audio.__all__)


def test_an_event_with_a_negative_volume_is_refused(library_without_mixer):
    """An event's volume below 0 is a ValueError."""
    sound = library_without_mixer.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5')

    with pytest.raises(ValueError, match=r'an event volume is 0 or more, got -0\.5'):
        OfflineEvent(seconds=0.0, sound=sound, volume=-0.5)
