"""Brave Adventurer sounds after moving to the engine synth (restore as written)."""

from pathlib import Path

import numpy as np
import pytest

from glitchygames.audio import synth
from glitchygames.examples.brave_adventurer import sounds

GOLDEN = Path(__file__).parent / 'brave_adventurer_golden'
RATE = 44100
GENERATORS = {
    'jump': sounds._generate_jump_sound,
    'land': sounds._generate_land_sound,
    'collect': sounds._generate_collect_sound,
    'death': sounds._generate_death_sound,
    'game_over': sounds._generate_game_over_sound,
}


def _render(mocker, name):
    mocker.patch('glitchygames.audio.synth.mixer_sample_rate', return_value=RATE)
    to_sound = mocker.patch.object(sounds, 'to_sound')
    GENERATORS[name]()
    return synth.to_pcm16(to_sound.call_args.args[0]).astype(np.int32)


def _window_rms(samples, window=int(0.005 * RATE)):
    trimmed = samples[: len(samples) // window * window].astype(np.float64)
    return np.sqrt(np.mean(trimmed.reshape(-1, window) ** 2, axis=1))


def _zero_crossing_frequency(samples):
    crossings = np.count_nonzero(np.diff(np.signbit(samples)))
    return crossings / 2 / (len(samples) / RATE)


@pytest.mark.parametrize('name', ['land', 'collect'])
def test_constant_pitch_sounds_match_goldens(mocker, name):
    """Land and collect are constant pitch, so they match the goldens sample for sample."""
    golden = np.load(GOLDEN / f'{name}.npy').astype(np.int32)
    rendered = _render(mocker, name)
    assert len(rendered) == len(golden)
    assert np.max(np.abs(rendered - golden)) <= 2


@pytest.mark.parametrize('name', ['jump', 'death', 'game_over'])
def test_match_length_envelope_and_pitch(mocker, name):
    """Sweeps differ in phase origin; game_over in int() vs round() note sizing."""
    golden = np.load(GOLDEN / f'{name}.npy').astype(np.int32)
    rendered = _render(mocker, name)
    assert abs(len(rendered) - len(golden)) <= 1
    shared = min(len(rendered), len(golden))
    rendered, golden = rendered[:shared], golden[:shared]
    np.testing.assert_allclose(_window_rms(rendered), _window_rms(golden), rtol=0.02, atol=60)
    edge = int(0.02 * RATE)
    for portion in (slice(0, edge), slice(-edge, None)):
        assert _zero_crossing_frequency(rendered[portion]) == pytest.approx(
            _zero_crossing_frequency(golden[portion]), rel=0.02, abs=30
        )


def test_game_sounds_initialize_without_mixer(mocker):
    """No audio device: initialize logs and leaves every sound None (no crash)."""
    mocker.patch('pygame.mixer.get_init', return_value=None)
    game_sounds = sounds.GameSounds()
    game_sounds.initialize()
    game_sounds.play_jump()  # No-op, no exception
    assert game_sounds.jump is None


def test_game_sounds_set_none_when_audio_fails_part_way(mocker):
    """Audio lost after some sounds were made: no sound is set, so the game plays silent."""
    mocker.patch.object(sounds, '_generate_collect_sound', side_effect=sounds.AudioUnavailableError)
    game_sounds = sounds.GameSounds()
    game_sounds.initialize()
    assert game_sounds.jump is None
    assert game_sounds.land is None
    assert game_sounds.collect is None
