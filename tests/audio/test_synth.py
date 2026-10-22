"""Tests for the synth toolkit (numpy only unless marked)."""

import numpy as np
import pygame
import pytest

from glitchygames.audio import synth
from glitchygames.audio.exceptions import AudioUnavailableError
from glitchygames.audio.synth import Envelope, Waveform
from glitchygames.randomness import NUMPY_STREAM_KIND, reset_streams, stream_seed

RATE = 44100
NOISE_STREAM_TEST_SEED = 77


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

    def test_noise_without_a_random_source_draws_from_the_synth_stream(self):
        """Unseeded noise comes from numpy_stream('audio.synth') of the run's seed."""
        reset_streams(seed=NOISE_STREAM_TEST_SEED)
        samples, _ = synth.oscillator(Waveform.NOISE, 0.0, 0.01, sample_rate=RATE)

        reference_generator = np.random.default_rng(
            stream_seed(
                kind=NUMPY_STREAM_KIND, master_seed=NOISE_STREAM_TEST_SEED, name='audio.synth'
            )
        )
        expected, _ = synth.oscillator(
            Waveform.NOISE, 0.0, 0.01, sample_rate=RATE, random_source=reference_generator
        )
        np.testing.assert_array_equal(samples, expected)


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


class TestOscillatorEdgeCases:
    """Tests for oscillator fixes carried from review."""

    def test_sub_half_sample_duration_returns_empty(self):
        samples, end_phase = synth.oscillator(
            Waveform.SINE, 440.0, 1e-6, sample_rate=RATE, phase=0.25
        )
        assert len(samples) == 0
        assert end_phase == pytest.approx(0.25)

    def test_nan_frequency_raises(self):
        with pytest.raises(ValueError, match='frequency'):
            synth.oscillator(
                Waveform.SINE, np.array([440.0, np.nan, 440.0]), 3 / RATE, sample_rate=RATE
            )


class TestEnvelope:
    """Tests for amplitude envelopes."""

    def test_stage_boundaries(self):
        samples = np.ones(100)
        envelope = Envelope(attack=10 / RATE, decay=10 / RATE, sustain_level=0.5, release=20 / RATE)
        shaped = synth.apply_envelope(samples, envelope, sample_rate=RATE)
        assert shaped[0] == 0.0
        assert shaped[9] == pytest.approx(1.0)
        assert shaped[19] == pytest.approx(0.5)
        assert shaped[50] == pytest.approx(0.5)
        assert shaped[-1] == 0.0

    def test_release_keeps_priority_when_too_long(self):
        samples = np.ones(30)
        envelope = Envelope(attack=20 / RATE, decay=0.0, sustain_level=1.0, release=20 / RATE)
        shaped = synth.apply_envelope(samples, envelope, sample_rate=RATE)
        # Release keeps all 20 samples (ending at 0); attack is cut to the 10 left
        assert shaped[-1] == 0.0
        assert shaped[9] == pytest.approx(1.0)
        assert np.all(np.diff(shaped[10:]) <= 0)

    def test_matches_brave_adventurer_shape(self):
        """Attack + release with sustain 1.0 equals the old attack/decay envelope."""
        count = synth.sample_count(0.12, RATE)
        envelope = Envelope(attack=0.005, decay=0.0, sustain_level=1.0, release=0.08)
        shaped = synth.apply_envelope(np.ones(count), envelope, sample_rate=RATE)
        attack = synth.sample_count(0.005, RATE)
        release = synth.sample_count(0.08, RATE)
        np.testing.assert_allclose(shaped[:attack], np.linspace(0, 1, attack))
        np.testing.assert_allclose(shaped[-release:], np.linspace(1, 0, release))


class TestFilters:
    """Tests for FIR filters."""

    def _tone(self, frequency):
        return synth.oscillator(Waveform.SINE, frequency, 0.2, sample_rate=RATE)[0]

    def test_low_pass_attenuates_above_cutoff(self):
        low = synth.low_pass(self._tone(200.0), 1000.0, sample_rate=RATE)
        high = synth.low_pass(self._tone(8000.0), 1000.0, sample_rate=RATE)
        assert np.max(np.abs(low[500:])) > 0.9
        assert np.max(np.abs(high[500:])) < 0.05

    def test_high_pass_attenuates_below_cutoff(self):
        low = synth.high_pass(self._tone(100.0), 2000.0, sample_rate=RATE)
        high = synth.high_pass(self._tone(8000.0), 2000.0, sample_rate=RATE)
        assert np.max(np.abs(low[500:])) < 0.1
        assert np.max(np.abs(high[500:])) > 0.9

    @pytest.mark.parametrize('length', [0, 10, 5000])
    def test_output_length_equals_input(self, length):
        assert len(synth.low_pass(np.ones(length), 1000.0, sample_rate=RATE)) == length

    def test_no_onset_click(self):
        """A sound starting at full level ramps through the filter instead of jumping."""
        filtered = synth.low_pass(np.ones(500), 500.0, sample_rate=RATE)
        assert abs(filtered[0]) < 0.05

    def test_chunked_with_history_equals_whole(self):
        signal = synth.oscillator(Waveform.SAWTOOTH, 300.0, 0.2, sample_rate=RATE)[0]
        whole = synth.low_pass(signal, 900.0, sample_rate=RATE)
        taps = synth.DEFAULT_FILTER_TAPS
        history = np.zeros(taps - 1)
        pieces = []
        for chunk in np.array_split(signal, 7):
            pieces.append(synth.low_pass(chunk, 900.0, sample_rate=RATE, history=history))
            history = np.concatenate((history, chunk))[-(taps - 1) :]
        np.testing.assert_allclose(np.concatenate(pieces), whole, atol=1e-12)

    @pytest.mark.parametrize('cutoff', [0.0, RATE / 2])
    def test_cutoff_bounds(self, cutoff):
        with pytest.raises(ValueError, match='cutoff'):
            synth.low_pass(np.ones(10), cutoff, sample_rate=RATE)

    def test_taps_must_be_odd(self):
        with pytest.raises(ValueError, match='taps'):
            synth.low_pass(np.ones(10), 1000.0, sample_rate=RATE, taps=100)


class TestEffectsAndMixing:
    """Tests for effects, mixing and normalization."""

    def test_distort_keeps_peak_at_one(self):
        assert synth.distort(np.array([1.0, -1.0, 0.0]), 4.0) == pytest.approx([1.0, -1.0, 0.0])

    def test_tremolo_depth_and_phase(self):
        shaped, end_phase = synth.tremolo(np.ones(RATE), 1.0, 0.5, sample_rate=RATE)
        assert shaped[0] == pytest.approx(1.0)
        assert shaped[RATE // 2] == pytest.approx(0.5, abs=1e-3)
        assert end_phase == pytest.approx(0.0, abs=1e-9)

    def test_mix_offsets_and_overhang(self):
        mixed = synth.mix(np.ones(4), (np.ones(4), 2 / RATE), sample_rate=RATE)
        np.testing.assert_allclose(mixed, [1, 1, 2, 2, 1, 1])

    def test_mix_negative_offset_raises(self):
        with pytest.raises(ValueError, match='offset'):
            synth.mix((np.ones(4), -0.1), sample_rate=RATE)

    def test_normalize_silence_unchanged(self):
        np.testing.assert_array_equal(synth.normalize(np.zeros(5)), np.zeros(5))

    def test_normalize_peak(self):
        assert np.max(np.abs(synth.normalize(np.array([0.1, -0.5]), peak=0.9))) == 0.9

    def test_silence_zero_is_empty(self):
        assert len(synth.silence(0.0, sample_rate=RATE)) == 0

    def test_to_pcm16_clips_and_scales(self):
        np.testing.assert_array_equal(
            synth.to_pcm16(np.array([2.0, -2.0, 0.5])),
            np.array([32767, -32767, 16384], dtype=np.int16),
        )


class TestToSound:
    """Tests for Sound conversion with a mocked mixer."""

    def test_raises_without_mixer(self, mocker):
        mocker.patch('pygame.mixer.get_init', return_value=None)
        with pytest.raises(AudioUnavailableError):
            synth.to_sound(np.zeros(10))

    def test_raises_on_other_format(self, mocker):
        mocker.patch('pygame.mixer.get_init', return_value=(44100, 32784, 2))
        with pytest.raises(AudioUnavailableError, match='format'):
            synth.to_sound(np.zeros(10))

    @pytest.mark.parametrize('channels', [1, 2])
    def test_tiles_to_mixer_channels(self, mocker, channels):
        mocker.patch('pygame.mixer.get_init', return_value=(44100, -16, channels))
        make_sound = mocker.patch('pygame.sndarray.make_sound')
        synth.to_sound(np.zeros(10), volume=0.3)
        frames = make_sound.call_args.args[0]
        assert frames.dtype == np.int16
        assert frames.flags['C_CONTIGUOUS']
        assert frames.shape == ((10,) if channels == 1 else (10, channels))
        make_sound.return_value.set_volume.assert_called_once_with(0.3)


class TestToSoundRealMixer:
    """Tests for Sound conversion with a real dummy-driver mixer."""

    def test_make_sound_accepts_frames(self, monkeypatch):
        monkeypatch.setenv('SDL_AUDIODRIVER', 'dummy')
        pygame.mixer.quit()
        pygame.mixer.init(44100, -16, 2)
        try:
            sound = synth.to_sound(np.zeros(441))
            assert sound.get_length() == pytest.approx(0.01, abs=1e-3)
        finally:
            pygame.mixer.quit()


class TestArgumentValidation:
    """Each toolkit function refuses out-of-range arguments with a ValueError naming them."""

    @pytest.mark.parametrize('duty', [0.0, 1.0, -0.5, 1.5])
    def test_oscillator_duty_outside_zero_to_one_raises(self, duty):
        """A square wave's duty must be strictly between 0 and 1."""
        with pytest.raises(ValueError, match='duty'):
            synth.oscillator(Waveform.SQUARE, 440.0, 0.1, sample_rate=RATE, duty=duty)

    @pytest.mark.parametrize('duration', [0.0, -0.1])
    def test_frequency_curve_duration_must_be_positive(self, duration):
        """A pitch curve needs a positive duration."""
        with pytest.raises(ValueError, match='duration'):
            synth.frequency_curve(440.0, 880.0, duration, sample_rate=RATE)

    def test_apply_kernel_history_of_wrong_length_raises(self):
        """The history must hold exactly taps - 1 samples."""
        kernel = synth.filter_kernel(1000.0, sample_rate=RATE, taps=5, high_pass=False)
        with pytest.raises(ValueError, match='history must have 4 samples, got 2'):
            synth.apply_kernel(np.ones(8), kernel, history=np.zeros(2))

    def test_apply_kernel_continues_from_history(self):
        """Filtering in two halves with the first half's tail as history equals one pass."""
        kernel = synth.filter_kernel(2000.0, sample_rate=RATE, taps=7, high_pass=False)
        samples = np.sin(np.arange(40) * 0.3)
        whole = synth.apply_kernel(samples, kernel)
        first_half = synth.apply_kernel(samples[:20], kernel)
        second_half = synth.apply_kernel(samples[20:], kernel, history=samples[14:20])
        np.testing.assert_allclose(np.concatenate((first_half, second_half)), whole)

    def test_apply_kernel_empty_input_gives_empty_output(self):
        """No samples in, no samples out (np.convolve alone would return some)."""
        kernel = synth.filter_kernel(1000.0, sample_rate=RATE, taps=5, high_pass=False)
        assert len(synth.apply_kernel(np.zeros(0), kernel)) == 0

    @pytest.mark.parametrize('drive', [0.0, -1.0])
    def test_distort_drive_must_be_positive(self, drive):
        """A drive of zero or less is refused."""
        with pytest.raises(ValueError, match='drive'):
            synth.distort(np.ones(3), drive)

    @pytest.mark.parametrize('depth', [-0.1, 1.1])
    def test_tremolo_depth_outside_zero_to_one_raises(self, depth):
        """Tremolo depth is a fraction of the gain."""
        with pytest.raises(ValueError, match='depth'):
            synth.tremolo(np.ones(10), 5.0, depth, sample_rate=RATE)

    @pytest.mark.parametrize('rate_hz', [0.0, -2.0])
    def test_tremolo_rate_must_be_positive(self, rate_hz):
        """Tremolo needs a positive modulation rate."""
        with pytest.raises(ValueError, match='rate_hz'):
            synth.tremolo(np.ones(10), rate_hz, 0.5, sample_rate=RATE)

    @pytest.mark.parametrize('peak', [0.0, -0.5, 1.01])
    def test_normalize_peak_outside_range_raises(self, peak):
        """The target peak must be in (0, 1]."""
        with pytest.raises(ValueError, match='peak'):
            synth.normalize(np.array([0.5]), peak=peak)

    def test_normalize_empty_samples_unchanged(self):
        """An empty array has no loudest sample and comes back empty."""
        assert len(synth.normalize(np.zeros(0))) == 0
