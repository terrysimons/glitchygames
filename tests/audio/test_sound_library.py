"""Tests for the sound library: one-call sound(), sources, identity, recorded files, mixer."""

import dataclasses

import numpy as np
import pygame
import pytest

from glitchygames.audio.assets import clear_sound_file_cache
from glitchygames.audio.exceptions import SoundAssetError, SoundRenderError
from glitchygames.audio.instrument import Instrument
from glitchygames.audio.library import CacheMode, SoundRequest
from glitchygames.audio.recipes import SoundRecipe, Tone
from glitchygames.audio.spec import PlaybackDefaults
from glitchygames.audio.synth import Envelope, Waveform
from glitchygames.audio.waves import Harmonics, Wave, current_wave_registry
from glitchygames.engine_context import EngineContext
from tests.audio.library_support import (
    FIXTURE_SOUNDS,
    FIXTURES,
    PULSE_INSTRUMENT,
    make_library,
    start_mixer,
    stop_mixer,
    write_wave_file,
)

MUNCHER_LIKE_RECIPE = SoundRecipe(
    name='crunch_like',
    tones=(
        Tone(
            waveform=Waveform.NOISE,
            start_frequency=0.0,
            duration=0.045,
            envelope=Envelope(attack=0.001, decay=0.015, sustain_level=0.4, release=0.02),
            volume=0.8,
            high_pass_cutoff=1800.0,
        ),
        Tone(
            waveform=Waveform.SINE,
            start_frequency=700.0,
            end_frequency=350.0,
            duration=0.04,
            envelope=Envelope(attack=0.001, decay=0.01, sustain_level=0.5, release=0.02),
            volume=0.6,
        ),
    ),
    volume=0.18,
    peak=0.9,
)


@pytest.fixture(autouse=True)
def _isolated_context_and_file_cache():
    clear_sound_file_cache()
    with EngineContext(name='sound library test').active():
        yield
    clear_sound_file_cache()


@pytest.fixture
def no_mixer():
    """Run the test with no mixer."""
    stop_mixer()
    yield
    stop_mixer()


def test_an_instrument_compiles_to_a_named_sound_with_samples_and_a_peak():
    """An instrument compiles to a sound with float and int16 samples, a peak and a length."""
    library, _ = make_library()

    sound = library.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5')

    assert sound.name.startswith('instrument-')
    assert sound.is_compiled
    assert not sound.is_live
    assert sound.samples_float.dtype == np.float64
    assert sound.samples_int16.dtype == np.int16
    assert len(sound.samples_float) == len(sound.samples_int16)
    assert sound.length == pytest.approx(len(sound.samples_float) / 44100)
    assert 0.0 < sound.peak <= 1.0 + 1e-9
    assert sound.playback_defaults == PlaybackDefaults()


def test_the_generated_name_of_an_instrument_is_stable():
    """Equal instruments get the same generated name, different ones get different names."""
    library, _ = make_library()
    other_library, _ = make_library()

    first = library.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5')
    again = other_library.sound(
        Instrument(wave='square', envelope='pluck'), scene_sound_directory=None, pitch='C5'
    )
    different = library.sound(Instrument(wave='sine'), scene_sound_directory=None, pitch='C5')

    assert first.name == again.name
    assert first.name != different.name
    np.testing.assert_array_equal(first.samples_float, again.samples_float)


def test_notes_chords_length_and_transpose_are_part_of_the_identity():
    """Each identity argument gives a different compiled sound."""
    library, _ = make_library()
    requests = [
        {'notes': 'C5:0.1 E5:0.1'},
        {'notes': [('C5', 0.1), ('E5', 0.1)]},
        {'chord': ['C4', 'E4', 'G4']},
        {'chord': ['C4', 'E4', 'G4'], 'transpose': 2.0},
        {'pitch': 'C5', 'length': 0.1},
    ]

    sounds = [
        library.sound(PULSE_INSTRUMENT, scene_sound_directory=None, **request)
        for request in requests
    ]

    assert sounds[0] is sounds[1]  # a melody as text or as pairs is one identity
    assert len({id(sound) for sound in sounds}) == 4
    assert library.sound(PULSE_INSTRUMENT, scene_sound_directory=None, **requests[2]) is sounds[2]


def test_a_live_instrument_is_refused_until_m2():
    """A live sound has no baked audio in M1."""
    library, _ = make_library()

    for mode in (CacheMode.RAM, CacheMode.NONE):
        library, _ = make_library(mode)
        with pytest.raises(SoundRenderError, match='live'):
            library.sound(Instrument(wave='sine', live=True), scene_sound_directory=None)


def test_v0_recipes_compile_bit_identical_to_today():
    """A v0 recipe compiles through today's renderer, unchanged (impl 10.4)."""
    library, _ = make_library()
    library.add_recipes([MUNCHER_LIKE_RECIPE])

    compiled = library.sound('crunch_like', scene_sound_directory=None)

    np.testing.assert_array_equal(
        compiled.samples_float, MUNCHER_LIKE_RECIPE.render(sample_rate=44100)
    )
    assert compiled.name == 'crunch_like'
    assert compiled.peak == pytest.approx(0.9)
    assert library.sound('crunch_like', scene_sound_directory=None) is compiled
    assert 'crunch_like' in library.names()


def test_v0_recipe_files_in_a_directory_compile_bit_identical():
    """A v0 recipe found through the directory index renders as the recipe does."""
    library, _ = make_library()

    compiled = library.sound('sugar_rush', scene_sound_directory=FIXTURE_SOUNDS)

    from glitchygames.audio.assets import load_sound_file

    recipe = (
        load_sound_file(FIXTURE_SOUNDS / 'legacy_recipes.toml').sounds['sugar_rush'].legacy_recipe
    )
    np.testing.assert_array_equal(compiled.samples_float, recipe.render(sample_rate=44100))


def test_a_name_in_add_recipes_and_in_the_directory_names_both():
    """A name in add_recipes and in the directory raises, naming both."""
    library, _ = make_library()
    library.add_recipes([dataclasses.replace(MUNCHER_LIKE_RECIPE, name='sugar_rush')])

    with pytest.raises(SoundAssetError, match=r'sugar_rush.*add_recipes.*legacy_recipes\.toml'):
        library.sound('sugar_rush', scene_sound_directory=FIXTURE_SOUNDS)


def test_recipes_win_when_the_directory_has_no_such_name():
    """A recipe name the directory lacks resolves from add_recipes even with a directory."""
    library, _ = make_library()
    library.add_recipes([MUNCHER_LIKE_RECIPE])

    assert library.sound('crunch_like', scene_sound_directory=FIXTURE_SOUNDS).name == 'crunch_like'


def test_short_names_resolve_through_the_scene_sound_directory():
    """A short name compiles the sound file's entry and carries its playback defaults."""
    library, _ = make_library()

    coin = library.sound('coin', scene_sound_directory=FIXTURE_SOUNDS)

    assert coin.name == 'coin'
    assert coin.is_compiled
    assert coin.playback_defaults.volume == pytest.approx(0.6)
    assert library.sound('coin', scene_sound_directory=FIXTURE_SOUNDS) is coin
    assert 'coin' in library.names()


def test_call_arguments_replace_the_entrys_identity_fields():
    """A pitch in the call replaces the file entry's pitch, notes and chord."""
    library, _ = make_library()

    default = library.sound('thump', scene_sound_directory=FIXTURE_SOUNDS)
    higher = library.sound('thump', scene_sound_directory=FIXTURE_SOUNDS, pitch='C3')
    shorter = library.sound('thump', scene_sound_directory=FIXTURE_SOUNDS, length=0.2)
    stab = library.sound('chord_stab', scene_sound_directory=FIXTURE_SOUNDS)
    stab_melody = library.sound(
        'chord_stab', scene_sound_directory=FIXTURE_SOUNDS, notes='C4:0.1', transpose=1.0
    )

    assert len({id(sound) for sound in (default, higher, shorter, stab, stab_melody)}) == 5
    assert shorter.length < default.length


def test_path_references_name_a_file_and_a_sound_in_it():
    """A path with # names a sound in a file, relative to the package root."""
    library, _ = make_library()

    coin = library.sound(
        'sounds/pickups.toml#coin', scene_sound_directory=None, package_root=FIXTURES
    )

    assert coin.is_compiled
    assert coin.playback_defaults.volume == pytest.approx(0.6)


def test_path_reference_errors():
    """A TOML path needs a sound name and a # needs a sound file."""
    library, _ = make_library()

    with pytest.raises(SoundAssetError, match='name a sound'):
        library.sound('sounds/pickups.toml', scene_sound_directory=None, package_root=FIXTURES)
    with pytest.raises(SoundAssetError, match=r'\.toml'):
        library.sound('sounds/sfx_slap.wav#coin', scene_sound_directory=None, package_root=FIXTURES)
    with pytest.raises(KeyError, match='nothing'):
        library.sound(
            'sounds/pickups.toml#nothing', scene_sound_directory=None, package_root=FIXTURES
        )


def test_unknown_names_are_key_errors():
    """An unknown short name, or a short name with no sound directory, is a KeyError."""
    library, _ = make_library()

    with pytest.raises(KeyError, match='nothing_here'):
        library.sound('nothing_here', scene_sound_directory=FIXTURE_SOUNDS)
    with pytest.raises(KeyError, match='no sound directory'):
        library.sound('coin', scene_sound_directory=None)


def test_file_waves_are_registered_before_their_instruments_are_built():
    """Loading a file registers its [waves.*] in the registry."""
    library, _ = make_library()
    assert 'organ_pad' not in current_wave_registry()

    library.sound('chord_stab', scene_sound_directory=FIXTURE_SOUNDS)

    assert 'organ_pad' in current_wave_registry()
    assert 'ghost' in current_wave_registry()


def test_registering_the_same_wave_again_is_a_no_op():
    """A second library requesting from the same file registers equal waves without error."""
    library, _ = make_library()
    other_library, _ = make_library()
    library.sound('chord_stab', scene_sound_directory=FIXTURE_SOUNDS)
    registered = current_wave_registry()['organ_pad']

    other_library.sound('chord_stab', scene_sound_directory=FIXTURE_SOUNDS)

    assert current_wave_registry()['organ_pad'] is registered


def test_a_different_wave_under_a_registered_name_names_the_file():
    """A different wave under an existing name raises, naming the file."""
    current_wave_registry().register(
        'organ_pad', Wave.from_harmonics(Harmonics.drawbars('800000000'))
    )
    library, _ = make_library()

    with pytest.raises(SoundAssetError, match=r'extras\.toml.*organ_pad'):
        library.sound('chord_stab', scene_sound_directory=FIXTURE_SOUNDS)


def test_a_missing_recorded_file_raises_when_first_requested_in_every_mode(tmp_path):
    """A recorded sound whose file is missing raises on request, naming the field."""
    (tmp_path / 'sounds.toml').write_text(
        '[glitchygames]\nkind = "sounds"\nversion = 1\n\n[sounds.slap]\nfile = "missing.wav"\n'
    )
    for mode in (CacheMode.RAM, CacheMode.NONE):
        library, _ = make_library(mode)
        with pytest.raises(SoundAssetError, match=r'sounds\.slap\.file.*does not exist'):
            library.sound('slap', scene_sound_directory=tmp_path)


def test_a_recorded_or_v0_sound_takes_no_identity_arguments(tmp_path):
    """A pitch (or notes, chord, length, transpose) on a recorded or v0 sound is refused."""
    write_wave_file(tmp_path / 'thud.wav')
    library, _ = make_library()
    library.add_recipes([MUNCHER_LIKE_RECIPE])

    with pytest.raises(ValueError, match='takes no pitch'):
        library.sound('thud', scene_sound_directory=tmp_path, pitch='C4')
    with pytest.raises(ValueError, match='takes no pitch'):
        library.sound('crunch_like', scene_sound_directory=None, transpose=2.0)


def test_a_recorded_file_compiles_through_the_mixer_when_there_is_one(tmp_path):
    """A recorded file loads as a pygame sound when a mixer exists."""
    path = write_wave_file(tmp_path / 'blip.wav', frames=4410)
    start_mixer(frequency=44100)
    library, accountant = make_library()

    sound = library.sound(str(path), scene_sound_directory=None)

    assert isinstance(sound.mixer_sound(), pygame.mixer.Sound)
    assert sound.name == 'blip'
    assert sound.length == pytest.approx(0.1, abs=0.01)
    assert sound.samples_int16 is not None
    assert sound.peak == pytest.approx(20000 / 32767, abs=0.01)
    assert accountant.compile_log[-1].name == 'blip'
    assert library.sound(str(path), scene_sound_directory=None) is sound


def test_a_stereo_recorded_file_through_the_mixer_is_mixed_to_mono_samples(tmp_path):
    """The mono samples of a stereo recorded file are the channels' average."""
    path = write_wave_file(tmp_path / 'wide.wav', frames=441, channels=2)
    start_mixer(frequency=44100, channels=2)
    library, _ = make_library()

    sound = library.sound(str(path), scene_sound_directory=None)

    assert sound.samples_int16.ndim == 1
    assert len(sound.samples_int16) == 441


def test_a_recorded_wav_decodes_without_a_mixer(tmp_path, no_mixer):
    """Without a mixer a WAV decodes with the wave module at its own rate."""
    path = write_wave_file(tmp_path / 'blip.wav', frames=480, sample_rate=48000)
    library, _ = make_library()

    sound = library.sound(str(path), scene_sound_directory=None)

    assert sound.samples_int16 is not None
    assert sound.samples_float is not None
    assert sound.length == pytest.approx(0.01)
    assert sound.samples_int16[0] == -20000
    assert sound.samples_float[0] == pytest.approx(-20000 / 32767)
    assert sound.mixer_sound() is None


def test_a_stereo_wav_decodes_to_mono_without_a_mixer(tmp_path, no_mixer):
    """A stereo WAV is averaged to mono when decoded without a mixer."""
    path = write_wave_file(tmp_path / 'wide.wav', frames=100, channels=2)
    library, _ = make_library()

    sound = library.sound(str(path), scene_sound_directory=None)

    assert len(sound.samples_int16) == 100


def test_a_corrupt_wav_with_a_mixer_is_a_sound_asset_error(tmp_path):
    """A recorded file the mixer cannot load names the file."""
    broken = tmp_path / 'broken.wav'
    broken.write_bytes(b'not a wave file at all')
    start_mixer()
    library, _ = make_library()

    with pytest.raises(SoundAssetError, match=r'broken\.wav.*cannot be loaded'):
        library.sound(str(broken), scene_sound_directory=None)


def test_ogg_and_odd_wav_formats_need_a_mixer(tmp_path, no_mixer):
    """OGG and non-16-bit WAV files cannot be decoded without a mixer."""
    library, _ = make_library()
    ogg = tmp_path / 'music.ogg'
    ogg.write_bytes(b'OggS')
    eight_bit = write_wave_file(tmp_path / 'eight.wav', frames=10, width=1)

    with pytest.raises(SoundAssetError, match='mixer'):
        library.sound(str(ogg), scene_sound_directory=None)
    with pytest.raises(SoundAssetError, match='16-bit'):
        library.sound(str(eight_bit), scene_sound_directory=None)


def test_a_corrupt_wav_without_a_mixer_is_a_sound_asset_error(tmp_path, no_mixer):
    """A WAV the wave module cannot read names the file."""
    broken = tmp_path / 'broken.wav'
    broken.write_bytes(b'not a wave file at all')
    library, _ = make_library()

    with pytest.raises(SoundAssetError, match=r'broken\.wav'):
        library.sound(str(broken), scene_sound_directory=None)


def test_a_recorded_file_recompiles_under_cache_none_every_play(tmp_path, no_mixer):
    """Recorded sounds follow the cache mode too."""
    path = write_wave_file(tmp_path / 'blip.wav')
    library, _ = make_library(CacheMode.NONE)
    sound = library.sound(str(path), scene_sound_directory=None)

    assert not sound.is_compiled
    played = library.compile_for_play(sound)

    assert played.is_compiled
    assert played is not sound
    assert library.statistics().compiles == 1


def test_a_recorded_short_name_resolves_by_its_stem(tmp_path, no_mixer):
    """A recorded file in the directory is a short name by its stem."""
    write_wave_file(tmp_path / 'thud.wav')
    library, _ = make_library()

    assert library.sound('thud', scene_sound_directory=tmp_path).name == 'thud'


def test_a_sound_compiled_without_a_mixer_plays_once_the_mixer_starts(no_mixer):
    """A sound compiled before the mixer started gets its pygame sound once there is a mixer."""
    library, _ = make_library()
    sound = library.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5')
    assert sound.mixer_sound() is None

    start_mixer(frequency=44100)
    mixer_sound = sound.mixer_sound()

    assert isinstance(mixer_sound, pygame.mixer.Sound)
    assert sound.mixer_sound() is mixer_sound  # built once
    assert mixer_sound.get_length() == pytest.approx(sound.length, abs=0.01)
    channel = pygame.mixer.Channel(0)
    channel.play(mixer_sound)
    assert channel.get_busy()


def test_a_stereo_mixer_gets_the_samples_on_both_channels():
    """With a two-channel mixer the pygame sound duplicates the mono samples."""
    start_mixer(frequency=44100, channels=2)
    library, _ = make_library()

    sound = library.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5')
    assert sound.samples_int16 is not None
    frames = pygame.sndarray.array(sound.mixer_sound())

    assert frames.shape == (len(sound.samples_int16), 2)
    np.testing.assert_array_equal(frames[:, 0], sound.samples_int16)
    np.testing.assert_array_equal(frames[:, 1], sound.samples_int16)


def test_a_48000_hz_mixer_compiles_at_its_rate_with_another_identity():
    """A 48 kHz mixer compiles at 48 kHz, a separate identity from the 44.1 kHz sound."""
    start_mixer(frequency=44100)
    library, _ = make_library()
    at_44100 = library.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5')
    start_mixer(frequency=48000)

    at_48000 = library.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5')

    assert at_44100.spec.sample_rate == 44100
    assert at_48000.spec.sample_rate == 48000
    assert at_48000 is not at_44100
    assert at_48000.identity_key != at_44100.identity_key
    assert len(at_48000.samples_float) == pytest.approx(
        len(at_44100.samples_float) * 48000 / 44100, abs=2
    )
    assert library.statistics().compiles == 2


def test_a_sound_at_another_rate_than_the_mixer_is_resampled_to_keep_its_pitch():
    """A held sound compiled at 44.1 kHz still lasts its length on a 48 kHz mixer."""
    start_mixer(frequency=44100)
    library, _ = make_library()
    sound = library.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5')
    start_mixer(frequency=48000)

    mixer_sound = sound.mixer_sound()

    assert mixer_sound.get_length() == pytest.approx(sound.length, abs=0.01)


def test_a_mixer_that_is_not_signed_16_bit_is_refused(mocker):
    """A mixer whose format is not signed 16-bit cannot play the samples."""
    from glitchygames.audio.exceptions import AudioUnavailableError

    library, _ = make_library()
    sound = library.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5')
    mocker.patch('pygame.mixer.get_init', return_value=(44100, 32, 1))

    with pytest.raises(AudioUnavailableError, match='signed 16-bit'):
        sound.mixer_sound()


def test_warm_compiles_what_fits_the_budget_and_reports_progress():
    """Warm compiles requests while the budget lasts and returns the fraction done."""
    library, _ = make_library()
    requests = [
        SoundRequest(source=PULSE_INSTRUMENT, scene_sound_directory=None, pitch=pitch)
        for pitch in ('C5', 'D5', 'E5', 'F5')
    ]

    assert library.warm(requests, budget_ms=0.0) == pytest.approx(0.25)  # one at least
    assert library.statistics().compiles == 1
    assert library.warm(requests, budget_ms=1e9) == 1.0  # a huge budget finishes the rest
    assert library.statistics().compiles == 4
    assert library.warm(requests, budget_ms=0.0) == 1.0  # nothing left to compile
    assert library.warm([]) == 1.0
    assert library.statistics().compiles == 4


def test_warm_without_a_budget_compiles_everything():
    """No budget means compile every request."""
    library, _ = make_library()
    requests = [
        SoundRequest(source=PULSE_INSTRUMENT, scene_sound_directory=None, pitch=pitch)
        for pitch in ('C5', 'D5')
    ]

    assert library.warm(requests) == 1.0
    assert library.statistics().compiles == 2


def test_warm_under_cache_none_only_resolves():
    """With cache none there is nothing to keep, so warm resolves and reports done."""
    library, _ = make_library(CacheMode.NONE)
    requests = [SoundRequest(source=PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5')]

    assert library.warm(requests) == 1.0
    assert library.statistics().compiles == 0
