"""Brave Adventurer's sounds: five effects on the engine's sound library.

Each was a ``_generate_*_sound()`` function on the synth toolkit; they are effects now
(plans/2026-11-14-sound-migration.md, decision 2: tones mixed straight, ``normalize=False``).
The 16-bit samples, what plays and what the disk cache keeps, are byte-identical to the old
functions' at 44.1 and 48 kHz; the old algorithm is written out here as the reference, so it
outlives the code it replaced. (Their float samples differ in the last bit, at most 1.1e-16: the
old code scaled by PEAK before the envelope, a tone scales after it.) The original recordings in
brave_adventurer_golden/ still bound them as before.
"""

from pathlib import Path

import numpy as np
import pytest

from brave_adventurer_core import sounds
from glitchygames.audio import synth
from glitchygames.audio.synth import Envelope, Waveform

GOLDEN = Path(__file__).parent / 'brave_adventurer_golden'
RATE = 44100
NAMES = ['jump', 'land', 'collect', 'death', 'game_over']
# The volumes the old functions passed to to_sound
OLD_VOLUMES = {'jump': 0.35, 'land': 0.25, 'collect': 0.3, 'death': 0.4, 'game_over': 0.4}


def _old_sine(frequency: float, duration: float, rate: int) -> np.ndarray:
    return synth.oscillator(Waveform.SINE, frequency, duration, sample_rate=rate)[0] * sounds.PEAK


def _old_sweep(start: float, end: float, duration: float, rate: int) -> np.ndarray:
    frequencies = synth.frequency_curve(start, end, duration, sample_rate=rate)
    return synth.oscillator(Waveform.SINE, frequencies, duration, sample_rate=rate)[0] * sounds.PEAK


def _old_fade(samples: np.ndarray, *, attack: float, release: float, rate: int) -> np.ndarray:
    return synth.apply_envelope(
        samples,
        Envelope(attack=attack, decay=0.0, sustain_level=1.0, release=release),
        sample_rate=rate,
    )


def _old_samples(name: str, rate: int) -> np.ndarray:
    """The old generators' samples, before to_sound (the reference)."""
    if name == 'jump':
        return _old_fade(_old_sweep(220, 660, 0.12, rate), attack=0.005, release=0.08, rate=rate)
    if name == 'land':
        return _old_fade(_old_sine(80, 0.06, rate), attack=0.002, release=0.05, rate=rate)
    if name == 'collect':
        return synth.concatenate(*[
            _old_fade(_old_sine(frequency, 0.06, rate), attack=0.003, release=0.04, rate=rate)
            for frequency in (523, 659, 784)
        ])
    if name == 'death':
        return _old_fade(_old_sweep(500, 80, 0.3, rate), attack=0.005, release=0.2, rate=rate)
    return synth.concatenate(
        _old_fade(_old_sine(330, 0.25, rate), attack=0.01, release=0.15, rate=rate),
        _old_fade(_old_sine(262, 0.25, rate), attack=0.01, release=0.15, rate=rate),
        _old_fade(_old_sine(220, 0.375, rate), attack=0.01, release=0.25, rate=rate),
    )


def _rendered(name: str, rate: int = RATE) -> np.ndarray:
    return synth.to_pcm16(sounds.EFFECTS[name].render(sample_rate=rate))


@pytest.mark.parametrize('rate', [44100, 48000])
@pytest.mark.parametrize('name', NAMES)
def test_each_effect_plays_exactly_what_the_old_function_made(name, rate):
    """The 16-bit samples are the old function's, byte for byte, at either mixer rate."""
    assert _rendered(name, rate).tobytes() == synth.to_pcm16(_old_samples(name, rate)).tobytes()


@pytest.mark.parametrize('name', NAMES)
def test_each_effect_plays_at_the_old_volume(name):
    """An effect plays at its own volume, which is the volume the old function set."""
    assert sounds.EFFECTS[name].volume == OLD_VOLUMES[name]


@pytest.mark.parametrize('name', NAMES)
def test_each_effect_mixes_straight(name):
    """No normalizing: the old functions scaled by PEAK and never rescaled the result."""
    assert sounds.EFFECTS[name].normalize is False


def _window_rms(samples, window=int(0.005 * RATE)):
    trimmed = samples[: len(samples) // window * window].astype(np.float64)
    return np.sqrt(np.mean(trimmed.reshape(-1, window) ** 2, axis=1))


def _zero_crossing_frequency(samples):
    crossings = np.count_nonzero(np.diff(np.signbit(samples)))
    return crossings / 2 / (len(samples) / RATE)


@pytest.mark.parametrize('name', ['land', 'collect'])
def test_constant_pitch_sounds_match_goldens(name):
    """Land and collect are constant pitch, so they match the goldens sample for sample."""
    golden = np.load(GOLDEN / f'{name}.npy').astype(np.int32)
    rendered = _rendered(name).astype(np.int32)
    assert len(rendered) == len(golden)
    assert np.max(np.abs(rendered - golden)) <= 2


@pytest.mark.parametrize('name', ['jump', 'death', 'game_over'])
def test_match_length_envelope_and_pitch(name):
    """Sweeps differ in phase origin; game_over in int() vs round() note sizing."""
    golden = np.load(GOLDEN / f'{name}.npy').astype(np.int32)
    rendered = _rendered(name).astype(np.int32)
    assert abs(len(rendered) - len(golden)) <= 1
    shared = min(len(rendered), len(golden))
    rendered, golden = rendered[:shared], golden[:shared]
    np.testing.assert_allclose(_window_rms(rendered), _window_rms(golden), rtol=0.02, atol=60)
    edge = int(0.02 * RATE)
    for portion in (slice(0, edge), slice(-edge, None)):
        assert _zero_crossing_frequency(rendered[portion]) == pytest.approx(
            _zero_crossing_frequency(golden[portion]), rel=0.02, abs=30
        )


def test_requested_sounds_are_the_librarys_sounds_of_the_effects():
    """request_sounds gives the audio engine's own Sound for each effect (no mixer needed)."""
    from glitchygames.audio.engine import AudioEngine
    from glitchygames.audio.voices import ChannelPartition

    audio = AudioEngine(partition=ChannelPartition(live=(), library=(), legacy_count=0))

    requested = sounds.request_sounds(audio=audio)

    for name in NAMES:
        sound = getattr(requested, name)
        assert sound is audio.sound(sounds.EFFECTS[name])
        assert sound.effect is sounds.EFFECTS[name]
        assert sound.playback_defaults.volume == OLD_VOLUMES[name]
