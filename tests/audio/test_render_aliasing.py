"""Aliasing checks on the band-limited mip tables (AUD-WAVE-006).

Rendering 1 s of square and saw at 3520 Hz through the renderer is Task 4's check; this file
tests the mip tables the renderer reads.
"""

import math

import numpy as np
import pytest

from glitchygames.audio.waves import WAVE_TABLE_LENGTH, Wave

SAMPLE_RATE = 44100
HIGHEST_FREQUENCY = 3520.0
ALIAS_FLOOR = 1e-9


@pytest.mark.parametrize('name', ['square', 'saw'])
def test_mip_table_has_no_harmonic_above_nyquist(name):
    """Mip table has no harmonic above nyquist."""
    table = Wave(name).band_limited_table(
        highest_frequency=HIGHEST_FREQUENCY, sample_rate=SAMPLE_RATE
    )
    magnitudes = np.abs(np.fft.rfft(table))
    last_allowed = math.floor(SAMPLE_RATE / 2 / HIGHEST_FREQUENCY)
    assert last_allowed == 6
    assert np.max(magnitudes[last_allowed + 1 :]) < ALIAS_FLOOR * magnitudes[1]
    assert magnitudes[1] > 0.0


def test_a_low_band_keeps_every_harmonic_the_table_can_hold():
    """A low band keeps every harmonic the table can hold."""
    wave = Wave('saw')
    table = wave.band_limited_table(highest_frequency=20.0, sample_rate=SAMPLE_RATE)
    assert table.shape == (WAVE_TABLE_LENGTH,)
    np.testing.assert_allclose(table, wave.table(), atol=1e-9)


def test_frequencies_in_one_octave_band_share_a_cached_table():
    """Frequencies in one octave band share a cached table."""
    wave = Wave('saw')
    first = wave.band_limited_table(highest_frequency=3000.0, sample_rate=SAMPLE_RATE)
    second = wave.band_limited_table(highest_frequency=4000.0, sample_rate=SAMPLE_RATE)
    assert first is second


def test_the_highest_band_still_holds_the_fundamental():
    """The highest band still holds the fundamental."""
    table = Wave('saw').band_limited_table(highest_frequency=22050.0, sample_rate=SAMPLE_RATE)
    magnitudes = np.abs(np.fft.rfft(table))
    assert magnitudes[1] > 0.0
    assert np.max(magnitudes[2:]) < ALIAS_FLOOR * magnitudes[1]


@pytest.mark.parametrize('highest_frequency', [0.0, -5.0, 30000.0])
def test_frequencies_outside_zero_to_nyquist_are_refused(highest_frequency):
    """Frequencies outside zero to nyquist are refused."""
    with pytest.raises(ValueError, match='highest_frequency must be'):
        Wave('saw').band_limited_table(highest_frequency=highest_frequency, sample_rate=SAMPLE_RATE)
