"""Tests for mixes: several instrument parts compiled into one sound, optionally an exact loop.

A mix is cached exactly as every other sound is (memory, then the disk layer, else compiled and
written): the first request builds it, every later one plays the built copy.
"""

import numpy as np
import pygame
import pytest
from pydantic import ValidationError

from glitchygames.audio.disk_cache import DiskSoundCache
from glitchygames.audio.exceptions import SoundRenderError
from glitchygames.audio.instrument import Instrument
from glitchygames.audio.library import ENGINE_SOUND_CACHE, CacheMode
from glitchygames.audio.mix import Mix, MixPart
from glitchygames.audio.render import render_sound
from glitchygames.audio.synth import to_pcm16
from tests.audio.library_support import PULSE_INSTRUMENT, float_render, make_library

SINE_INSTRUMENT = Instrument(wave='sine', envelope='pad')
LOOP_SECONDS = 2.0


@pytest.fixture(autouse=True)
def _mixer_stopped_afterwards():
    """Stop the mixer after each test so the harness restarts it with the run's format."""
    yield
    pygame.mixer.quit()


def _mix(*, loop_seconds=None, volume=0.5, notes='A4:1 C5:1', name='tune'):
    return Mix(
        name=name,
        parts=(
            MixPart(instrument=PULSE_INSTRUMENT, notes=notes, volume=volume),
            MixPart(instrument=SINE_INSTRUMENT, notes='E4:2', volume=0.25),
        ),
        loop_seconds=loop_seconds,
    )


def _request(library, mix):
    return library.sound(mix, scene_sound_directory=None)


def test_a_mix_is_the_sum_of_its_parts_at_their_volumes():
    """Each part rendered and scaled by its volume, added sample by sample from the start."""
    library, _ = make_library()

    sound = _request(library, _mix())

    assert sound.mix is not None
    renders = [(render_sound(part.spec).samples, part.volume) for part in sound.mix.parts]
    expected = np.zeros(max(len(samples) for samples, _volume in renders))
    for samples, volume in renders:
        expected[: len(samples)] += volume * samples
    assert sound.samples_int16 is not None
    assert sound.samples_int16.tobytes() == to_pcm16(expected).tobytes()
    assert sound.peak == pytest.approx(float(np.max(np.abs(expected))))


def test_each_part_is_its_instrument_playing_its_notes():
    """A part sounds as the instrument asked for alone with the same notes: same length."""
    library, _ = make_library()

    sound = _request(library, _mix())
    alone = library.sound(PULSE_INSTRUMENT, scene_sound_directory=None, notes='A4:1 C5:1')

    assert sound.mix is not None
    first_part = render_sound(sound.mix.parts[0].spec)
    assert len(first_part.samples) == len(alone.samples_int16)


def test_a_looping_mix_is_exactly_its_loop_long():
    """No dropped trailing rest, no release tail added: the loop's own frames."""
    library, _ = make_library()

    sound = _request(library, _mix(loop_seconds=LOOP_SECONDS, notes='A4:0.5 _:1.5'))

    assert sound.samples_int16 is not None
    assert len(sound.samples_int16) == round(LOOP_SECONDS * sound.sample_rate)
    assert sound.length == LOOP_SECONDS


def test_a_looping_mix_folds_what_rings_past_its_end_onto_its_start():
    """The tails ring on into the next pass: frame i holds every pass's frame i added."""
    library, _ = make_library()
    open_ended = float_render(_request(library, _mix()))
    looping_sound = _request(library, _mix(loop_seconds=LOOP_SECONDS))
    looping = float_render(looping_sound)
    loop_frames = round(LOOP_SECONDS * looping_sound.sample_rate)
    assert len(open_ended) > loop_frames, 'the parts must ring past the loop'

    expected = np.zeros(loop_frames)
    for start in range(0, len(open_ended), loop_frames):
        chunk = open_ended[start : start + loop_frames]
        expected[: len(chunk)] += chunk

    np.testing.assert_allclose(looping, expected, atol=1e-12)


def test_the_same_mix_asked_for_again_is_the_built_copy():
    """The first request builds it; equal requests return the same sound, built once."""
    library, _ = make_library()
    first = _request(library, _mix())

    assert all(_request(library, _mix()) is first for _ in range(10))
    assert library.statistics().compiles == 1


@pytest.mark.parametrize(
    'changed',
    [
        pytest.param({'volume': 0.6}, id='a-part-volume'),
        pytest.param({'notes': 'A4:1 D5:1'}, id='a-part-melody'),
        pytest.param({'loop_seconds': LOOP_SECONDS}, id='the-loop'),
        pytest.param({'name': 'other'}, id='the-name'),
    ],
)
def test_anything_that_changes_the_mix_changes_its_identity(changed):
    """Never one mix's samples played for another."""
    library, _ = make_library()

    assert _request(library, _mix()).identity_key != _request(library, _mix(**changed)).identity_key


def _disk(directory):
    return DiskSoundCache(directory=directory, limit_bytes=64 * 1024 * 1024)


def test_a_mix_is_written_to_disk_once_and_read_back_exactly(tmp_path):
    """A later process reads the built mix from the disk layer, compiling nothing."""
    first_library, _ = make_library(CacheMode.DISK, disk=_disk(tmp_path))
    built = _request(first_library, _mix(loop_seconds=LOOP_SECONDS))
    ENGINE_SOUND_CACHE.clear()
    second_library, _ = make_library(CacheMode.DISK, disk=_disk(tmp_path))
    read = _request(second_library, _mix(loop_seconds=LOOP_SECONDS))

    assert (first_library.statistics().compiles, first_library.statistics().disk_writes) == (1, 1)
    assert (second_library.statistics().compiles, second_library.statistics().disk_hits) == (0, 1)
    assert built.samples_int16 is not None
    assert read.samples_int16 is not None
    assert read.samples_int16.tobytes() == built.samples_int16.tobytes()
    assert (read.peak, read.length) == (built.peak, built.length)


@pytest.mark.parametrize('loop_seconds', [None, LOOP_SECONDS])
def test_cache_none_knows_a_mix_length_without_compiling(loop_seconds):
    """The length a game may read is ram's, bit for bit, with nothing rendered."""
    ram_sound = _request(make_library()[0], _mix(loop_seconds=loop_seconds))
    ENGINE_SOUND_CACHE.clear()
    library, _ = make_library(CacheMode.NONE)

    sound = _request(library, _mix(loop_seconds=loop_seconds))

    assert sound.length == ram_sound.length
    assert library.statistics().compiles == 0


def test_cache_none_compiles_a_mix_at_each_play_into_the_same_samples():
    """Under ``none`` a play compiles the mix afresh: ram's samples, sample for sample."""
    ram_sound = _request(make_library()[0], _mix(loop_seconds=LOOP_SECONDS))
    ENGINE_SOUND_CACHE.clear()
    library, _ = make_library(CacheMode.NONE)

    played = library.compile_for_play(_request(library, _mix(loop_seconds=LOOP_SECONDS)))

    assert played.samples_int16 is not None
    assert ram_sound.samples_int16 is not None
    assert played.samples_int16.tobytes() == ram_sound.samples_int16.tobytes()
    assert library.statistics().compiles == 1


def test_a_copy_at_another_rate_is_the_loop_at_that_rate():
    """An offline render at another rate keeps the loop exact at that rate."""
    library, _ = make_library()
    sound = _request(library, _mix(loop_seconds=LOOP_SECONDS))

    copy = sound.fresh_copy(sample_rate=22050)
    library._compile(copy)

    assert copy.samples_int16 is not None
    assert len(copy.samples_int16) == round(LOOP_SECONDS * 22050)


def test_a_mix_takes_no_pitch_notes_chord_length_or_transpose():
    """Its parts carry their own notes."""
    library, _ = make_library()

    with pytest.raises(ValueError, match="'tune' is a mix"):
        library.sound(_mix(), scene_sound_directory=None, pitch='C5')


def test_a_live_instrument_cannot_be_mixed():
    """A live sound has no baked samples to add."""
    library, _ = make_library()
    live = Mix(
        name='live', parts=(MixPart(instrument=Instrument(wave='sine', live=True), notes='A4:1'),)
    )

    with pytest.raises(SoundRenderError, match='live'):
        _request(library, live)


@pytest.mark.parametrize(
    'arguments',
    [
        pytest.param({'parts': ()}, id='no-parts'),
        pytest.param({'loop_seconds': 0.0}, id='an-empty-loop'),
        pytest.param({'name': ''}, id='no-name'),
    ],
)
def test_a_mix_that_cannot_sound_is_refused(arguments):
    """Refused when made, not when compiled."""
    values = {
        'name': 'tune',
        'parts': (MixPart(instrument=PULSE_INSTRUMENT, notes='A4:1'),),
        **arguments,
    }

    with pytest.raises(ValidationError):
        Mix(**values)


@pytest.mark.parametrize('volume', [-0.1, 1.1])
def test_a_part_volume_is_from_zero_to_one(volume):
    """As every play's volume."""
    with pytest.raises(ValidationError):
        MixPart(instrument=PULSE_INSTRUMENT, notes='A4:1', volume=volume)
