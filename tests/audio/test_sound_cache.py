"""Tests for the sound cache: modes, compile counts, memory limit, eviction and recompiles."""

import numpy as np
import pytest

from glitchygames.audio.library import CacheMode, CacheStatistics
from glitchygames.audio.pitch import Tuning
from tests.audio.library_support import PULSE_INSTRUMENT, make_library


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
        hits=2, misses=1, compiles=1, bytes_held=first.samples_int16.nbytes
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
    """Under cache none, sound() holds the spec and no samples."""
    library, _ = make_library(CacheMode.NONE)
    sound = _request(library)

    assert sound.spec is not None
    assert sound.samples_float is None
    assert sound.samples_int16 is None
    assert not sound.is_compiled
    assert sound.mixer_sound() is None
    assert library.statistics().compiles == 0
    assert _request(library) is sound
    assert library.statistics().bytes_held == 0


def test_cache_none_compiles_on_every_play():
    """Under cache none, every play compiles anew."""
    library, accountant = make_library(CacheMode.NONE)
    sound = _request(library)

    compiled = [library.compile_for_play(sound) for _ in range(5)]

    assert library.statistics().compiles == 5
    assert len({id(each) for each in compiled}) == 5
    assert all(each.is_compiled and each.length > 0.0 for each in compiled)
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
    one_sound_bytes = _request(probe).samples_int16.nbytes
    library, _ = make_library(memory_limit_bytes=one_sound_bytes * 2 + one_sound_bytes // 2)
    playing = set()
    library.playing_predicate = lambda sound: sound in playing

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
    library, _ = make_library(memory_limit_bytes=1)
    library.playing_predicate = lambda sound: True
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
    one_sound_bytes = _request(probe).samples_int16.nbytes
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
