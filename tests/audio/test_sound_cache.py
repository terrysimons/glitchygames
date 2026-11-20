"""Tests for the sound cache: modes, compile counts, memory limit, eviction and recompiles."""

import numpy as np
import pygame
import pytest

from glitchygames.audio.disk_cache import DiskSoundCache
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
    np.testing.assert_array_equal(compiled[0].samples_int16, compiled[1].samples_int16)


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
    _new_process()  # the probe only measured; the library under test starts empty
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
    _new_process()  # the probe only measured; the library under test starts empty
    library, _ = make_library(memory_limit_bytes=one_sound_bytes + 1)
    first = _request(library, 'C5')
    before = first.samples_int16
    assert before is not None
    _request(library, 'D5')  # evicts C5
    assert not first.is_compiled
    assert library.statistics().compiles == 2

    again = _request(library, 'C5')

    assert again is first
    assert library.statistics().compiles == 3
    np.testing.assert_array_equal(again.samples_int16, before)
    # A play of an evicted sound recompiles it as well
    _request(library, 'D5')
    assert not first.is_compiled
    assert library.compile_for_play(first) is first
    assert first.is_compiled
    assert library.statistics().compiles == 5


def test_disk_mode_needs_a_disk_cache():
    """Cache ``disk`` without a disk layer to keep sounds in is a caller's mistake, said so."""
    with pytest.raises(ValueError, match='needs a disk cache'):
        make_library(CacheMode.DISK)


def _new_process():
    """Forget the process store, as a new process starts: the disk layer then answers."""
    from glitchygames.audio.library import ENGINE_SOUND_CACHE

    ENGINE_SOUND_CACHE.clear()


def _disk(directory):
    return DiskSoundCache(directory=directory, limit_bytes=64 * 1024 * 1024)


def test_disk_mode_writes_a_new_sound_once_and_a_second_library_reads_it(tmp_path):
    """The first library compiles and writes; a second over the same folder compiles nothing."""
    first_library, _ = make_library(CacheMode.DISK, disk=_disk(tmp_path))
    _request(first_library)
    _new_process()
    second_library, _ = make_library(CacheMode.DISK, disk=_disk(tmp_path))
    read = _request(second_library)

    assert (first_library.statistics().compiles, first_library.statistics().disk_writes) == (1, 1)
    assert first_library.statistics().disk_misses == 1
    assert (second_library.statistics().compiles, second_library.statistics().disk_hits) == (0, 1)
    assert second_library.statistics().disk_writes == 0


def test_a_disk_hit_is_exactly_the_compile(tmp_path):
    """Samples byte for byte, and the peak, length and rate a replay may read (rule 2)."""
    fresh_library, _ = make_library(CacheMode.RAM)
    fresh = _request(fresh_library)
    _new_process()
    _request(make_library(CacheMode.DISK, disk=_disk(tmp_path))[0])
    _new_process()
    from_disk = _request(make_library(CacheMode.DISK, disk=_disk(tmp_path))[0])

    assert from_disk.samples_int16 is not None
    assert fresh.samples_int16 is not None
    assert from_disk.samples_int16.tobytes() == fresh.samples_int16.tobytes()
    assert (from_disk.peak, from_disk.length, from_disk.sample_rate) == (
        fresh.peak,
        fresh.length,
        fresh.sample_rate,
    )


def test_a_disk_hit_holds_no_float_samples(tmp_path):
    """Only int16 samples and the peak are kept on disk; float samples are not invented."""
    _request(make_library(CacheMode.DISK, disk=_disk(tmp_path))[0])
    _new_process()
    from_disk = _request(make_library(CacheMode.DISK, disk=_disk(tmp_path))[0])

    assert from_disk.is_compiled
    assert from_disk.samples_float is None


def test_an_offline_render_of_a_disk_hit_equals_a_fresh_one(tmp_path):
    """A caller that needs float samples compiles them fresh (offline renders)."""
    from glitchygames.audio.offline import render_to_file

    fresh = _request(make_library(CacheMode.RAM)[0])
    _new_process()
    _request(make_library(CacheMode.DISK, disk=_disk(tmp_path / 'cache'))[0])
    _new_process()
    from_disk = _request(make_library(CacheMode.DISK, disk=_disk(tmp_path / 'cache'))[0])

    render_to_file(fresh, tmp_path / 'fresh.wav')
    render_to_file(from_disk, tmp_path / 'from-disk.wav')

    assert (tmp_path / 'fresh.wav').read_bytes() == (tmp_path / 'from-disk.wav').read_bytes()


def test_a_version_zero_recipe_comes_back_from_disk_exactly(tmp_path):
    """Version 0 recipes go through the disk layer too, sample for sample."""
    source = str(FIXTURE_SOUNDS / 'legacy_recipes.toml') + '#crunch_one'
    fresh = make_library(CacheMode.RAM)[0].sound(source, scene_sound_directory=None)
    _new_process()
    make_library(CacheMode.DISK, disk=_disk(tmp_path))[0].sound(source, scene_sound_directory=None)
    _new_process()
    library, _ = make_library(CacheMode.DISK, disk=_disk(tmp_path))
    from_disk = library.sound(source, scene_sound_directory=None)

    assert library.statistics().disk_hits == 1
    assert from_disk.samples_int16 is not None
    assert fresh.samples_int16 is not None
    assert from_disk.samples_int16.tobytes() == fresh.samples_int16.tobytes()
    assert from_disk.peak == fresh.peak


def test_a_recorded_file_is_decoded_and_never_written_to_disk(tmp_path):
    """A recorded file is already a file: decoding it again costs what reading a copy would."""
    library, _ = make_library(CacheMode.DISK, disk=_disk(tmp_path))
    library.sound(str(FIXTURE_SOUNDS / 'extras.toml') + '#slap', scene_sound_directory=None)

    assert library.statistics().disk_writes == 0
    assert not list(tmp_path.rglob('*.wav'))


def test_a_damaged_disk_file_is_compiled_again_and_rewritten(tmp_path):
    """A bad file is a miss: the sound compiles (counted) and the file is written anew."""
    _request(make_library(CacheMode.DISK, disk=_disk(tmp_path))[0])
    (kept,) = tmp_path.rglob('*.wav')
    kept.write_bytes(b'damaged')
    _new_process()
    library, _ = make_library(CacheMode.DISK, disk=_disk(tmp_path))
    _request(library)

    statistics = library.statistics()
    assert (statistics.compiles, statistics.disk_misses, statistics.disk_writes) == (1, 1, 1)
    assert kept.read_bytes() != b'damaged'


def test_a_disk_library_prunes_its_folder_when_made(tmp_path):
    """The limit is applied once, at startup (spec 6.4)."""
    _request(make_library(CacheMode.DISK, disk=_disk(tmp_path))[0], 'C5')
    _request(make_library(CacheMode.DISK, disk=_disk(tmp_path))[0], 'E5')

    make_library(CacheMode.DISK, disk=DiskSoundCache(directory=tmp_path, limit_bytes=0))

    assert not list(tmp_path.rglob('*.wav'))


def test_the_engines_own_sounds_go_through_the_disk_layer(tmp_path):
    """A new process (an empty process-wide cache) reads the engine's sounds from disk."""
    from glitchygames.audio.library import ENGINE_SOUND_CACHE

    first, _ = make_library(CacheMode.DISK, disk=_disk(tmp_path))
    first.engine_sound(PULSE_INSTRUMENT, pitch='C5', length=0.1)
    ENGINE_SOUND_CACHE.clear()
    second, _ = make_library(CacheMode.DISK, disk=_disk(tmp_path))
    second.engine_sound(PULSE_INSTRUMENT, pitch='C5', length=0.1)

    assert first.statistics().disk_writes == 1
    assert (second.statistics().compiles, second.statistics().disk_hits) == (0, 1)


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


def test_retained_bytes_count_the_int16_samples_and_the_pygame_sound():
    """The limit counts the int16 samples and the pygame sound's buffer (no float64 is kept)."""
    start_mixer(frequency=44100, channels=2)
    library, _ = make_library()
    sound = _request(library)
    samples_only = sound.samples_int16.nbytes
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

    assert sound.retained_bytes == 1000 * (2 + 2)  # int16, 16-bit mixer buffer (no float64)
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
    _new_process()  # the probe only measured; the library under test starts empty
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


def _truncated_wave_file(path):
    """A WAV whose header claims 1000 frames but whose data stops 200 frames short.

    Returns:
        The path.
    """
    write_wave_file(path, frames=1000, sample_rate=22050)
    size = path.stat().st_size
    with path.open('r+b') as wave_bytes:
        wave_bytes.truncate(size - 200 * 2)
    return path


@pytest.mark.parametrize('with_mixer', [True, False], ids=['mixer', 'no-mixer'])
@pytest.mark.parametrize(
    'source_kind', ['fixture-wav', 'stereo-22050-wav', 'truncated-wav', 'one-frame-wav']
)
def test_a_recorded_file_under_none_decodes_only_when_its_metadata_is_first_read(
    tmp_path, with_mixer, source_kind
):
    """Under none a recorded sound's request decodes nothing (Ruling R50).

    Its length and rate come from one decode on their first read (counted), then are kept, and
    equal ram's: a header could claim more frames than a truncated file decodes.
    """
    if with_mixer:
        start_mixer(frequency=44100)
    else:
        pygame.mixer.quit()
    sources = {
        'fixture-wav': lambda: 'sfx_slap',
        'stereo-22050-wav': lambda: str(
            write_wave_file(tmp_path / 'stereo.wav', frames=4411, sample_rate=22050, channels=2)
        ),
        'truncated-wav': lambda: str(_truncated_wave_file(tmp_path / 'truncated.wav')),
        'one-frame-wav': lambda: str(
            write_wave_file(tmp_path / 'one.wav', frames=1, sample_rate=8000)
        ),
    }
    source = sources[source_kind]()
    none_library, accountant = make_library(CacheMode.NONE)
    ram_library, _ = make_library(CacheMode.RAM)

    uncompiled = none_library.sound(source, scene_sound_directory=FIXTURE_SOUNDS)
    held = ram_library.sound(source, scene_sound_directory=FIXTURE_SOUNDS)

    assert none_library.statistics().compiles == 0
    accountant.setup_mode = False
    accountant.frame_number = 7
    assert uncompiled.length == held.length
    assert none_library.statistics().compiles == 1
    assert accountant.compile_log[-1].frame_number == 7
    assert uncompiled.sample_rate == held.sample_rate
    assert uncompiled.peak == held.peak
    assert none_library.statistics().compiles == 1
    assert not uncompiled.is_compiled


def test_a_recorded_files_rate_read_first_under_none_decodes_it_once(tmp_path):
    """Read before its length, a recorded file's rate comes from one decode, kept for length."""
    pygame.mixer.quit()
    path = str(write_wave_file(tmp_path / 'low.wav', frames=2205, sample_rate=22050))
    library, _ = make_library(CacheMode.NONE)
    sound = library.sound(path, scene_sound_directory=None)

    assert sound.sample_rate == 22050
    assert library.statistics().compiles == 1
    assert sound.length == 2205 / 22050
    assert library.statistics().compiles == 1


def test_a_truncated_wav_reports_its_decoded_length_under_none_and_ram(tmp_path):
    """The length is what the decode reads (800 frames), never the header's 1000."""
    pygame.mixer.quit()
    path = str(_truncated_wave_file(tmp_path / 'truncated.wav'))
    none_library, _ = make_library(CacheMode.NONE)
    ram_library, _ = make_library(CacheMode.RAM)

    uncompiled = none_library.sound(path, scene_sound_directory=None)
    held = ram_library.sound(path, scene_sound_directory=None)

    assert held.length == 800 / 22050
    assert uncompiled.length == held.length


def test_sfx_slap_under_none_with_a_mixer_compiles_once_per_play():
    """Under none with a mixer, sound('sfx_slap') compiles 0 times and 5 plays compile 5."""
    start_mixer(frequency=44100, channels=2)
    library, _ = make_library(CacheMode.NONE)

    sound = library.sound('sfx_slap', scene_sound_directory=FIXTURE_SOUNDS)
    assert library.statistics().compiles == 0

    played = [library.compile_for_play(sound) for _ in range(5)]

    assert library.statistics().compiles == 5
    assert all(each.is_compiled for each in played)
    assert not sound.is_compiled


@pytest.mark.parametrize(
    'arguments',
    [{'source': PULSE_INSTRUMENT, 'pitch': 'C5'}, {'source': 'crunch_one'}, {'source': 'sfx_slap'}],
    ids=['instrument', 'version-0-recipe', 'recorded-file'],
)
def test_metadata_read_after_a_play_reuses_that_plays_compile(arguments):
    """A peak, length or rate read after a play compiles nothing more (Ruling R50)."""
    start_mixer(frequency=44100, channels=2)
    none_library, _ = make_library(CacheMode.NONE)
    ram_library, _ = make_library(CacheMode.RAM)
    uncompiled = none_library.sound(scene_sound_directory=FIXTURE_SOUNDS, **arguments)
    held = ram_library.sound(scene_sound_directory=FIXTURE_SOUNDS, **arguments)

    none_library.compile_for_play(uncompiled)
    assert none_library.statistics().compiles == 1

    assert _metadata(uncompiled) == _metadata(held)
    assert none_library.statistics().compiles == 1


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


def test_an_uncompiled_sound_outside_a_library_reads_peak_and_length_as_zero():
    """A sound no library described (an offline render's fresh copy) reads 0.0 until compiled."""
    library, _ = make_library()
    copy = _request(library).fresh_copy()

    assert copy.length == 0.0
    assert copy.peak == 0.0


def test_a_second_engine_context_compiles_nothing_the_first_compiled():
    """Compiled samples are shared by the process: an Arcade tile's restart compiles nothing.

    Each context has its own library and its own Sound, over the same read-only samples.
    """
    from glitchygames.engine_context import EngineContext

    first, _ = make_library()
    first_sound = _request(first)
    with EngineContext(name='second').active():
        second, _ = make_library()
        second_sound = _request(second)

    assert first.statistics().compiles == 1
    assert (second.statistics().compiles, second.statistics().shared_hits) == (0, 1)
    assert second_sound is not first_sound
    assert second_sound.samples_int16 is first_sound.samples_int16


def test_cache_none_shares_nothing():
    """Under none every play compiles: nothing is kept, in the library or the process."""
    from glitchygames.audio.library import ENGINE_SOUND_CACHE

    library, _ = make_library(CacheMode.NONE)
    library.compile_for_play(_request(library))

    assert len(ENGINE_SOUND_CACHE) == 0


def test_the_process_store_keeps_game_sounds_within_its_limit_least_recently_used_first():
    """Game sounds past the store's byte limit go, oldest request first; the engine's never do."""
    from glitchygames.audio.library import ENGINE_SOUND_CACHE

    library, _ = make_library()
    engine_sound = library.engine_sound(PULSE_INSTRUMENT, pitch='A3', length=0.05)
    sounds = [_request(library, pitch) for pitch in ('C5', 'E5', 'G5')]
    one_sound = sounds[0].samples_int16.nbytes
    ENGINE_SOUND_CACHE.limit_bytes = one_sound * 2

    ENGINE_SOUND_CACHE.compiled(sounds[1].identity_key)  # used, so newer than G5
    _request(library, 'B5')

    kept = {
        sound.identity_key for sound in sounds if ENGINE_SOUND_CACHE.compiled(sound.identity_key)
    }
    assert kept == {sounds[1].identity_key}
    assert ENGINE_SOUND_CACHE.compiled(engine_sound.identity_key) is not None


def test_threads_asking_for_one_sound_compile_it_once(mocker):
    """The per-key lock: whoever is first compiles, the others wait and read what it published."""
    import threading
    import time

    from glitchygames.audio import library as library_module
    from glitchygames.engine_context import EngineContext

    real_compile = library_module.compile_sound

    def slow_compile(sound):
        time.sleep(0.05)  # long enough for every thread to arrive
        real_compile(sound)

    compiles = mocker.patch.object(library_module, 'compile_sound', side_effect=slow_compile)

    def request_in_a_context_of_its_own():
        with EngineContext(name='thread').active():
            library, _ = make_library()
            _request(library)

    threads = [threading.Thread(target=request_in_a_context_of_its_own) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert compiles.call_count == 1


def test_a_file_another_process_wrote_while_this_one_waited_is_read_not_compiled(tmp_path, mocker):
    """Under the write lock the library reads again: a sound just written elsewhere is read."""
    _request(make_library(CacheMode.DISK, disk=_disk(tmp_path))[0])
    _new_process()
    disk = _disk(tmp_path)
    real_read = disk.read
    reads: list[str] = []

    def miss_first_then_read(**kwargs):
        """The first, lock-free read misses (the other process had not finished writing)."""
        reads.append(kwargs['identity_key'])
        return None if len(reads) == 1 else real_read(**kwargs)

    mocker.patch.object(disk, 'read', side_effect=miss_first_then_read)
    library, _ = make_library(CacheMode.DISK, disk=disk)

    _request(library)

    statistics = library.statistics()
    assert (statistics.compiles, statistics.disk_hits, statistics.disk_writes) == (0, 1, 0)
    assert len(reads) == 2  # the miss, then the read under the lock


def test_a_lock_another_process_holds_past_the_timeout_means_compile_without_writing(
    tmp_path, mocker
):
    """A writer never waits forever: without the lock in time it compiles and writes nothing."""
    from filelock import FileLock

    from glitchygames.audio import disk_cache

    mocker.patch.object(disk_cache, 'WRITE_LOCK_TIMEOUT_SECONDS', 0.05)
    disk = _disk(tmp_path)
    probe, _ = make_library()
    key = _request(probe).identity_key
    _new_process()
    path = disk.path_for(identity_key=key)
    path.parent.mkdir(parents=True)
    held = FileLock(f'{path}.lock')
    held.acquire()
    try:
        library, _ = make_library(CacheMode.DISK, disk=disk)
        sound = _request(library)
    finally:
        held.release()

    statistics = library.statistics()
    assert (statistics.compiles, statistics.disk_writes) == (1, 0)
    assert sound.is_compiled
    assert not path.exists()


def test_a_write_the_system_refuses_is_logged_and_the_sound_still_plays(tmp_path, mocker, caplog):
    """Windows will not replace a file another process has open: logged, never raised."""
    import logging
    from pathlib import Path

    mocker.patch.object(Path, 'replace', side_effect=PermissionError('in use'))
    library, _ = make_library(CacheMode.DISK, disk=_disk(tmp_path))

    with caplog.at_level(logging.WARNING, logger='game.audio.disk_cache'):
        sound = _request(library)

    assert sound.is_compiled
    assert library.statistics().disk_writes == 0
    assert 'was not written to the disk cache' in caplog.text
