"""Tests for the sound cache: modes, compile counts, memory limit, eviction and recompiles."""

import numpy as np
import pygame
import pytest

from glitchygames.audio.instrument import Instrument
from glitchygames.audio.library import CacheMode, CacheStatistics
from glitchygames.audio.pitch import Tuning
from tests.audio.library_support import (
    FIXTURE_SOUNDS,
    PULSE_INSTRUMENT,
    make_library,
    start_mixer,
    write_wave_file,
)


@pytest.fixture(autouse=True)
def _mixer_stopped_afterwards():
    """Stop the mixer after each test so the harness restarts it with the run's format."""
    yield
    pygame.mixer.quit()


def _request(library, pitch='C5'):
    return library.sound(PULSE_INSTRUMENT, scene_sound_directory=None, pitch=pitch)


def test_equal_requests_return_the_same_object_and_compile_once():
    """Equal requests return the same object and compile once."""
    library, _ = make_library()
    first = _request(library)

    assert all(_request(library) is first for _ in range(100))
    assert library.statistics().compiles == 1


def test_statistics_count_hits_misses_compiles_and_bytes():
    """Statistics count hits, misses, compiles and held bytes."""
    library, _ = make_library()
    first = _request(library)
    _request(library)
    _request(library)

    statistics = library.statistics()
    assert statistics == CacheStatistics(
        hits=2, misses=1, compiles=1, bytes_held=first.retained_bytes
    )


def test_a_different_pitch_is_a_different_sound():
    """Each pitch is its own compiled sound."""
    library, _ = make_library()

    assert _request(library, 'C5') is not _request(library, 'E5')
    assert library.statistics().compiles == 2


def test_two_spellings_of_one_identity_share_one_sound():
    """Different arguments that resolve to the same spec return the same sound."""
    library, _ = make_library()

    assert _request(library, 440.0) is _request(library, 'A4')
    assert library.statistics().compiles == 1


def test_cache_none_keeps_no_audio_until_a_play():
    """Under cache none, sound() holds the spec and no samples, and renders nothing.

    Its length and rate are derived from the spec without rendering (they must not depend on
    the cache: a replay may run under another mode).
    """
    library, _ = make_library(CacheMode.NONE)
    sound = _request(library)

    assert sound.spec is not None
    assert sound.samples_float is None
    assert sound.samples_int16 is None
    assert not sound.is_compiled
    assert sound.mixer_sound() is None
    assert library.statistics().compiles == 0
    assert _request(library) is sound
    assert library.statistics().compiles == 0
    assert library.statistics().bytes_held == 0


def test_cache_none_compiles_on_every_play():
    """Under cache none, a sound played 5 times compiles 5 times (AUD-MEAS-001)."""
    library, accountant = make_library(CacheMode.NONE)
    sound = _request(library)
    assert library.statistics().compiles == 0

    compiled = [library.compile_for_play(sound) for _ in range(5)]

    assert library.statistics().compiles == 5
    assert len({id(each) for each in compiled}) == 5
    assert all(each.is_compiled and each.length == sound.length for each in compiled)
    assert not sound.is_compiled
    assert len(accountant.take_frame().audio_work) == 5
    np.testing.assert_array_equal(compiled[0].samples_float, compiled[1].samples_float)


def test_cache_ram_returns_the_same_sound_for_every_play():
    """Under cache ram, compile for play returns the same sound and does not compile."""
    library, _ = make_library()
    sound = _request(library)

    assert library.compile_for_play(sound) is sound
    assert library.compile_for_play(sound) is sound
    assert library.statistics().compiles == 1


def test_compiles_are_attributed_to_setup_or_their_frame():
    """A compile is attributed to setup, or to the frame that requested it."""
    library, accountant = make_library()
    _request(library, 'C5')
    assert accountant.compile_log[-1].during_setup
    assert accountant.compile_log[-1].frame_number is None

    accountant.setup_mode = False
    accountant.frame_number = 30
    _request(library, 'D5')

    assert accountant.compile_log[-1].frame_number == 30
    assert not accountant.compile_log[-1].during_setup
    assert accountant.compile_log[-1].name.startswith('instrument-')


def test_a_cache_hit_is_not_a_compile_record():
    """Asking again does not log another compile."""
    library, accountant = make_library()
    _request(library)
    _request(library)

    assert len(accountant.compile_log) == 1


def test_a_tuning_change_is_another_identity_and_compiles_again():
    """A tuning change gives a new identity, compiled once more."""
    tunings = [Tuning()]
    library, _ = make_library(tuning_source=lambda: tunings[0])
    first = _request(library)
    tunings[0] = Tuning(a4=432.0)

    second = _request(library)

    assert second is not first
    assert library.statistics().compiles == 2


def test_memory_limit_evicts_least_recently_played_sounds_that_are_not_playing():
    """Past the memory limit the least recently played idle sounds lose their audio."""
    probe, _ = make_library()
    one_sound_bytes = _request(probe).retained_bytes
    playing = set()
    library, _ = make_library(
        memory_limit_bytes=one_sound_bytes * 2 + one_sound_bytes // 2,
        is_playing=lambda sound: sound in playing,
    )

    first = _request(library, 'C5')
    second = _request(library, 'D5')
    library.compile_for_play(first)  # the play order is now D5, then C5
    playing.add(second)  # the oldest is playing, so it is skipped
    third = _request(library, 'E5')

    assert not first.is_compiled  # the oldest idle sound was dropped
    assert second.is_compiled
    assert third.is_compiled
    assert library.statistics().bytes_held == one_sound_bytes * 2
    assert first.samples_float is None
    assert first.samples_int16 is None


def test_playing_sounds_are_never_evicted_even_over_the_limit():
    """When every other sound is playing, the cache stays over its limit."""
    library, _ = make_library(memory_limit_bytes=1, is_playing=lambda _sound: True)
    first = _request(library, 'C5')
    second = _request(library, 'D5')

    assert first.is_compiled
    assert second.is_compiled
    assert library.statistics().bytes_held > 1


def test_the_sound_just_compiled_is_kept_even_when_it_alone_exceeds_the_limit():
    """A single sound larger than the limit is kept, since it was just asked for."""
    library, _ = make_library(memory_limit_bytes=1)

    sound = _request(library)

    assert sound.is_compiled


def test_an_evicted_sound_is_recompiled_in_place_on_its_next_request_and_counted():
    """An evicted sound recompiles into the same object on its next request or play."""
    probe, _ = make_library()
    one_sound_bytes = _request(probe).retained_bytes
    library, _ = make_library(memory_limit_bytes=one_sound_bytes + 1)
    first = _request(library, 'C5')
    before = first.samples_float
    _request(library, 'D5')  # evicts C5
    assert not first.is_compiled
    assert library.statistics().compiles == 2

    again = _request(library, 'C5')

    assert again is first
    assert library.statistics().compiles == 3
    np.testing.assert_array_equal(again.samples_float, before)
    # A play of an evicted sound recompiles it as well
    _request(library, 'D5')
    assert not first.is_compiled
    assert library.compile_for_play(first) is first
    assert first.is_compiled
    assert library.statistics().compiles == 5


def test_disk_mode_is_refused_until_m3():
    """The disk cache arrives in M3."""
    with pytest.raises(ValueError, match='the disk cache arrives in M3'):
        make_library(CacheMode.DISK)


def test_eviction_stops_at_the_last_idle_sound_even_when_still_over_the_limit():
    """With nothing left to drop, the cache keeps the newest sound over its limit."""
    library, _ = make_library(memory_limit_bytes=1)
    first = _request(library, 'C5')

    second = _request(library, 'D5')

    assert not first.is_compiled
    assert second.is_compiled


def test_parameters_identify_a_request_but_not_a_baked_sound():
    """Equal parameters, in any order, are one request; a baked sound ignores them."""
    library, _ = make_library()
    plain = _request(library)

    with_parameters = library.sound(
        PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5', parameters={'b': 1.0, 'a': 2.0}
    )
    reordered = library.sound(
        PULSE_INSTRUMENT, scene_sound_directory=None, pitch='C5', parameters={'a': 2.0, 'b': 1.0}
    )

    assert with_parameters is plain
    assert reordered is plain
    assert library.statistics().compiles == 1


def test_retained_bytes_count_both_sample_arrays_and_the_pygame_sound():
    """The limit counts float samples, int16 samples and the pygame sound's buffer."""
    start_mixer(frequency=44100, channels=2)
    library, _ = make_library()
    sound = _request(library)
    samples_only = sound.samples_float.nbytes + sound.samples_int16.nbytes
    assert sound.retained_bytes == samples_only
    assert library.statistics().bytes_held == samples_only

    sound.mixer_sound()  # a stereo buffer of 16-bit frames

    assert sound.retained_bytes == samples_only + len(sound.samples_int16) * 2 * 2
    assert library.statistics().bytes_held == sound.retained_bytes
    sound_bytes = sound.retained_bytes
    small_library, _ = make_library(memory_limit_bytes=sound_bytes + 1)
    first = _request(small_library, 'C5')
    first.mixer_sound()
    _request(small_library, 'D5')  # the first now counts its pygame buffer too
    assert not first.is_compiled
    assert first.retained_bytes == 0


def test_a_recorded_sound_counts_its_pygame_buffer(tmp_path):
    """A recorded file loaded through the mixer counts the mixer sound it holds."""
    path = write_wave_file(tmp_path / 'blip.wav', frames=1000)
    start_mixer(frequency=44100)
    library, _ = make_library()

    sound = library.sound(str(path), scene_sound_directory=None)

    assert sound.retained_bytes == 1000 * (8 + 2 + 2)  # float64, int16, 16-bit mixer buffer
    assert library.statistics().bytes_held == sound.retained_bytes


def _metadata(sound):
    """What a game may read of a sound whatever the cache: length, peak and rate.

    Returns:
        The three values.
    """
    return (sound.length, sound.peak, sound.sample_rate)


@pytest.mark.parametrize(
    'arguments',
    [
        {'source': PULSE_INSTRUMENT, 'pitch': 'C5'},
        {'source': 'coin'},
        {'source': 'crunch_one'},
        {'source': 'sfx_slap'},
    ],
    ids=['instrument', 'version-1-file', 'version-0-recipe', 'recorded-file'],
)
def test_length_peak_and_rate_are_the_same_under_none_and_ram(arguments):
    """sound_cache is replay-local, so what a game reads of a sound must not depend on it."""
    start_mixer(frequency=44100, channels=2)
    by_mode = {}
    for mode in (CacheMode.NONE, CacheMode.RAM):
        library, _ = make_library(mode)
        by_mode[mode] = library.sound(scene_sound_directory=FIXTURE_SOUNDS, **arguments)

    assert _metadata(by_mode[CacheMode.NONE]) == _metadata(by_mode[CacheMode.RAM])
    assert by_mode[CacheMode.RAM].length > 0.0
    assert by_mode[CacheMode.RAM].peak > 0.0
    assert not by_mode[CacheMode.NONE].is_compiled


def test_an_evicted_sound_keeps_its_length_peak_and_rate():
    """The memory limit drops samples, never what the game may read of the sound."""
    probe, _ = make_library()
    one_sound_bytes = _request(probe).retained_bytes
    library, _ = make_library(memory_limit_bytes=one_sound_bytes + 1)
    first = _request(library, 'C5')
    before = _metadata(first)

    _request(library, 'D5')  # evicts C5

    assert not first.is_compiled
    assert _metadata(first) == before
    assert before[0] > 0.0
    assert before[1] > 0.0


def test_a_22050_hz_recorded_wav_reports_its_own_rate_before_and_after_compile(tmp_path):
    """Without a mixer a WAV decodes at its own rate, under either cache mode, before or after.

    (With a mixer, pygame converts the file to the mixer's rate as it loads it, so the samples,
    and the rate the sound reports, are the mixer's.)
    """
    pygame.mixer.quit()
    path = write_wave_file(tmp_path / 'low.wav', frames=2205, sample_rate=22050)
    none_library, _ = make_library(CacheMode.NONE)
    ram_library, _ = make_library(CacheMode.RAM)

    uncompiled = none_library.sound(str(path), scene_sound_directory=None)
    compiled_for_play = none_library.compile_for_play(uncompiled)
    held = ram_library.sound(str(path), scene_sound_directory=None)

    assert not uncompiled.is_compiled
    assert uncompiled.sample_rate == 22050
    assert compiled_for_play.sample_rate == 22050
    assert held.sample_rate == 22050
    assert uncompiled.length == compiled_for_play.length == held.length == pytest.approx(0.1)


NOISE_INSTRUMENT = Instrument(noise='white', envelope='pluck')


@pytest.mark.parametrize('mixer_rate', [44100, 22050])
@pytest.mark.parametrize(
    'arguments',
    [
        {'source': PULSE_INSTRUMENT, 'pitch': 'C5'},
        {'source': PULSE_INSTRUMENT, 'pitch': 'C5', 'length': 0.123457},
        {'source': PULSE_INSTRUMENT, 'notes': 'C5:0.0731 E5:0.1179 G5:0.0013'},
        {'source': PULSE_INSTRUMENT, 'chord': ['C4', 'E4', 'G4'], 'length': 0.3001},
        {'source': NOISE_INSTRUMENT},
        {'source': 'coin'},
        {'source': 'chord_stab'},
        {'source': 'thump'},
        {'source': 'crunch_one'},
    ],
    ids=[
        'instrument',
        'instrument-odd-length',
        'notes',
        'chord',
        'unpitched-noise',
        'version-1-file-notes',
        'version-1-file-chord',
        'version-1-file-layered',
        'version-0-recipe',
    ],
)
def test_length_and_rate_under_none_equal_rams_without_rendering(arguments, mixer_rate):
    """Under none, sound() renders nothing, yet its length and rate equal ram's bit for bit."""
    start_mixer(frequency=mixer_rate, channels=2)
    none_library, none_accountant = make_library(CacheMode.NONE)
    ram_library, _ = make_library(CacheMode.RAM)

    uncompiled = none_library.sound(scene_sound_directory=FIXTURE_SOUNDS, **arguments)
    held = ram_library.sound(scene_sound_directory=FIXTURE_SOUNDS, **arguments)

    assert none_library.statistics().compiles == 0
    assert not none_accountant.compile_log
    assert not uncompiled.is_compiled
    assert uncompiled.length > 0.0
    # Exact equality: a game timing on length must replay the same under either mode
    assert uncompiled.length == held.length
    assert uncompiled.sample_rate == held.sample_rate
    assert none_library.statistics().compiles == 0


@pytest.mark.parametrize(
    ('frames', 'sample_rate', 'channels'), [(2205, 22050, 1), (4411, 44100, 2), (1, 8000, 1)]
)
def test_a_recorded_wav_without_a_mixer_reads_its_header_under_none(
    tmp_path, frames, sample_rate, channels
):
    """Without a mixer, a WAV's length and rate come from its header: nothing is decoded."""
    pygame.mixer.quit()
    path = write_wave_file(
        tmp_path / 'clip.wav', frames=frames, sample_rate=sample_rate, channels=channels
    )
    none_library, _ = make_library(CacheMode.NONE)
    ram_library, _ = make_library(CacheMode.RAM)

    uncompiled = none_library.sound(str(path), scene_sound_directory=None)
    held = ram_library.sound(str(path), scene_sound_directory=None)

    assert none_library.statistics().compiles == 0
    assert uncompiled.length == held.length
    assert uncompiled.sample_rate == held.sample_rate == sample_rate
    played = none_library.compile_for_play(uncompiled)
    assert played.length == uncompiled.length
    assert none_library.statistics().compiles == 1


def test_a_recorded_file_through_a_mixer_still_decodes_at_its_request_under_none(tmp_path):
    """Through a mixer, a recorded file's request decodes it once under none too.

    pygame converts the file to the mixer's format as it loads it, so its length is known only
    by loading it: the request decodes it for its length, peak and rate and drops the samples
    (a play decodes again, counted).
    """
    start_mixer(frequency=44100)
    path = write_wave_file(tmp_path / 'clip.wav', frames=1000, sample_rate=22050)
    none_library, _ = make_library(CacheMode.NONE)
    ram_library, _ = make_library(CacheMode.RAM)

    uncompiled = none_library.sound(str(path), scene_sound_directory=None)
    held = ram_library.sound(str(path), scene_sound_directory=None)

    assert none_library.statistics().compiles == 1
    assert not uncompiled.is_compiled
    assert _metadata(uncompiled) == _metadata(held)
    none_library.compile_for_play(uncompiled)
    assert none_library.statistics().compiles == 2


@pytest.mark.parametrize(
    'arguments',
    [
        {'source': PULSE_INSTRUMENT, 'pitch': 'C5'},
        {'source': PULSE_INSTRUMENT, 'chord': ['C4', 'E4', 'G4'], 'length': 0.3},
        {'source': 'coin'},
        {'source': 'crunch_one'},
    ],
    ids=['instrument', 'chord', 'version-1-file', 'version-0-recipe'],
)
def test_reading_peak_under_none_compiles_once_then_keeps_it(arguments):
    """Under none, peak is rendered on its first read (counted, attributed), then kept."""
    none_library, accountant = make_library(CacheMode.NONE)
    ram_library, _ = make_library(CacheMode.RAM)
    uncompiled = none_library.sound(scene_sound_directory=FIXTURE_SOUNDS, **arguments)
    held = ram_library.sound(scene_sound_directory=FIXTURE_SOUNDS, **arguments)
    assert none_library.statistics().compiles == 0
    accountant.setup_mode = False
    accountant.frame_number = 12

    first_read = uncompiled.peak

    assert none_library.statistics().compiles == 1
    assert accountant.compile_log[-1].frame_number == 12
    assert accountant.compile_log[-1].name == uncompiled.name
    assert first_read == held.peak
    assert first_read > 0.0
    assert not uncompiled.is_compiled
    assert none_library.statistics().bytes_held == 0

    assert uncompiled.peak == first_read
    assert none_library.statistics().compiles == 1
    assert len(accountant.compile_log) == 1


def test_a_recorded_wav_without_a_mixer_renders_its_peak_on_first_read(tmp_path):
    """A header gives a WAV's length and rate; its peak is decoded on first read, once."""
    pygame.mixer.quit()
    path = write_wave_file(tmp_path / 'clip.wav', frames=441)
    none_library, _ = make_library(CacheMode.NONE)
    ram_library, _ = make_library(CacheMode.RAM)
    uncompiled = none_library.sound(str(path), scene_sound_directory=None)
    held = ram_library.sound(str(path), scene_sound_directory=None)

    assert uncompiled.peak == held.peak
    assert uncompiled.peak == held.peak
    assert none_library.statistics().compiles == 1


def test_an_uncompiled_sound_outside_a_library_reads_peak_and_length_as_zero():
    """A sound no library described (an offline render's fresh copy) reads 0.0 until compiled."""
    library, _ = make_library()
    copy = _request(library).fresh_copy()

    assert copy.length == 0.0
    assert copy.peak == 0.0
