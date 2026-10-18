"""Tests for the synth toolkit (numpy only unless marked)."""

import numpy as np
import pytest

from glitchygames.audio import synth
from glitchygames.audio.synth import Waveform

RATE = 44100


def _peak_frequency(samples, sample_rate=RATE):
    spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))
    return np.fft.rfftfreq(len(samples), d=1.0 / sample_rate)[np.argmax(spectrum)]


class TestSampleRate:
    """Tests for sample rate resolution."""

    def test_mixer_rate_when_initialized(self, mocker):
        mocker.patch('pygame.mixer.get_init', return_value=(48000, -16, 2))
        assert synth.mixer_sample_rate() == 48000

    def test_default_when_mixer_missing(self, mocker):
        mocker.patch('pygame.mixer.get_init', return_value=None)
        assert synth.mixer_sample_rate() == 44100

    def test_sample_count_rounds(self):
        assert synth.sample_count(0.05, 22050) == 1102  # 1102.5 rounds half to even
        assert synth.sample_count(0.1, 44100) == 4410


class TestOscillator:
    """Tests for oscillator waveforms."""

    @pytest.mark.parametrize(
        'waveform', [Waveform.SINE, Waveform.SQUARE, Waveform.SAWTOOTH, Waveform.TRIANGLE]
    )
    def test_peak_at_requested_frequency(self, waveform):
        samples, _ = synth.oscillator(waveform, 440.0, 0.5, sample_rate=RATE)
        assert _peak_frequency(samples) == pytest.approx(440.0, abs=3.0)

    @pytest.mark.parametrize('waveform', list(Waveform))
    def test_range_and_length(self, waveform):
        samples, _ = synth.oscillator(
            waveform, 220.0, 0.1, sample_rate=RATE, random_source=np.random.default_rng(1)
        )
        assert len(samples) == 4410
        assert np.max(np.abs(samples)) <= 1.0 + 0.1  # PolyBLEP may overshoot slightly

    def test_sine_phase_origin_is_zero(self):
        samples, _ = synth.oscillator(Waveform.SINE, 1000.0, 0.01, sample_rate=RATE)
        expected = np.sin(2 * np.pi * 1000.0 * np.arange(441) / RATE)
        np.testing.assert_allclose(samples, expected, atol=1e-12)

    @pytest.mark.parametrize('waveform', [Waveform.SINE, Waveform.SQUARE, Waveform.SAWTOOTH])
    def test_end_phase_continues_seamlessly(self, waveform):
        whole, _ = synth.oscillator(waveform, 330.0, 0.2, sample_rate=RATE)
        first, end_phase = synth.oscillator(waveform, 330.0, 0.1, sample_rate=RATE)
        second, _ = synth.oscillator(waveform, 330.0, 0.1, sample_rate=RATE, phase=end_phase)
        np.testing.assert_allclose(np.concatenate((first, second)), whole, atol=1e-9)

    def test_end_phase_wrapped(self):
        _, end_phase = synth.oscillator(Waveform.SINE, 440.0, 1.0, sample_rate=RATE)
        assert 0.0 <= end_phase < 1.0

    @pytest.mark.parametrize('waveform', [Waveform.SQUARE, Waveform.SAWTOOTH])
    def test_polyblep_reduces_aliasing(self, waveform):
        """At 5 kHz naive aliasing is 0.10-0.13; PolyBLEP keeps off-harmonic energy far lower."""
        samples, _ = synth.oscillator(waveform, 5000.0, 0.5, sample_rate=RATE)
        frequencies = np.fft.rfftfreq(len(samples), d=1.0 / RATE)
        spectrum = np.abs(np.fft.rfft(samples * np.hanning(len(samples)))) ** 2
        harmonic = np.isclose((frequencies / 5000.0) % 1.0, 0.0, atol=0.01) | np.isclose(
            (frequencies / 5000.0) % 1.0, 1.0, atol=0.01
        )
        alias_fraction = spectrum[~harmonic].sum() / spectrum.sum()
        assert alias_fraction < 0.05

    def test_frequency_array_length_must_match(self):
        with pytest.raises(ValueError, match='length'):
            synth.oscillator(Waveform.SINE, np.full(10, 440.0), 0.5, sample_rate=RATE)

    @pytest.mark.parametrize('frequency', [-1.0, RATE / 2 + 1])
    def test_frequency_outside_nyquist_raises(self, frequency):
        with pytest.raises(ValueError, match='frequency'):
            synth.oscillator(Waveform.SINE, frequency, 0.1, sample_rate=RATE)

    @pytest.mark.parametrize('duration', [0.0, -0.1])
    def test_duration_must_be_positive(self, duration):
        with pytest.raises(ValueError, match='duration'):
            synth.oscillator(Waveform.SINE, 440.0, duration, sample_rate=RATE)

    def test_noise_is_seeded(self):
        first, _ = synth.oscillator(
            Waveform.NOISE, 0.0, 0.01, sample_rate=RATE, random_source=np.random.default_rng(9)
        )
        second, _ = synth.oscillator(
            Waveform.NOISE, 0.0, 0.01, sample_rate=RATE, random_source=np.random.default_rng(9)
        )
        np.testing.assert_array_equal(first, second)


class TestFrequencyCurve:
    """Tests for pitch curves."""

    def test_endpoints_exact(self):
        curve = synth.frequency_curve(220.0, 660.0, 0.12, sample_rate=RATE)
        assert curve[0] == 220.0
        assert curve[-1] == 660.0
        assert len(curve) == synth.sample_count(0.12, RATE)

    def test_easing_shapes_curve(self):
        linear = synth.frequency_curve(100.0, 200.0, 0.1, sample_rate=RATE)
        eased = synth.frequency_curve(100.0, 200.0, 0.1, easing='ease_in_quad', sample_rate=RATE)
        middle = len(linear) // 2
        assert eased[middle] < linear[middle]

    def test_overshoot_outside_range_raises(self):
        with pytest.raises(ValueError, match='frequency'):
            synth.frequency_curve(10.0, 200.0, 0.1, easing='ease_in_back', sample_rate=RATE)
