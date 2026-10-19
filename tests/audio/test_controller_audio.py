"""Tests for controller audio haptics (glitchygames/audio/controller_audio.py)."""

from __future__ import annotations

from glitchygames.audio import controller_audio
from glitchygames.randomness import reset_streams

NOISE_STREAM_TEST_SEED = 79
TEXTURE_DURATION_SECONDS = 0.01


def _texture_samples() -> list[int]:
    left_samples, right_samples = controller_audio.get_haptic_preset(
        'texture', duration=TEXTURE_DURATION_SECONDS
    )
    assert list(left_samples) == list(right_samples)
    return list(left_samples)


def test_texture_noise_comes_from_the_controller_noise_stream(mocker):
    """Texture haptics draw from random_stream('audio.controller_noise'): a seed repeats them."""
    stream_lookup = mocker.patch.object(
        controller_audio, 'random_stream', wraps=controller_audio.random_stream
    )
    reset_streams(seed=NOISE_STREAM_TEST_SEED)
    first_run = _texture_samples()
    reset_streams(seed=NOISE_STREAM_TEST_SEED)

    assert _texture_samples() == first_run
    assert any(sample != 0 for sample in first_run)
    stream_lookup.assert_called_with('audio.controller_noise')


def test_different_seeds_give_different_texture_noise():
    """The noise depends on the run's seed."""
    reset_streams(seed=NOISE_STREAM_TEST_SEED)
    first_run = _texture_samples()
    reset_streams(seed=NOISE_STREAM_TEST_SEED + 1)

    assert _texture_samples() != first_run
