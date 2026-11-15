"""Tests for sound recipes and the sound bank."""

import dataclasses
from typing import Any

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from glitchygames.audio import synth
from glitchygames.audio.effects import (
    RECIPE_NOISE_SEED,
    Effect,
    SoundBank,
    Tone,
    Tremolo,
    load_effects,
)
from glitchygames.audio.exceptions import AudioUnavailableError, EffectError
from glitchygames.audio.synth import Envelope, Waveform

RATE = 44100
ENVELOPE = Envelope(attack=0.001, decay=0.01, sustain_level=0.7, release=0.02)


def _two_tone_recipe():
    return Effect(
        name='ting',
        tones=(
            Tone(
                waveform=Waveform.TRIANGLE,
                start_frequency=1318.5,
                duration=0.08,
                envelope=ENVELOPE,
            ),
            Tone(
                waveform=Waveform.SQUARE,
                start_frequency=200.0,
                end_frequency=100.0,
                easing='ease_out_quad',
                duration=0.1,
                envelope=ENVELOPE,
                offset=0.05,
                volume=0.5,
                low_pass_cutoff=2000.0,
                distortion=2.0,
                tremolo=Tremolo(rate_hz=12.0, depth=0.3),
            ),
        ),
    )


class TestRender:
    """Tests for rendering recipes into samples."""

    def test_render_equals_toolkit_composition(self):
        recipe = _two_tone_recipe()
        first = synth.apply_envelope(
            synth.oscillator(Waveform.TRIANGLE, 1318.5, 0.08, sample_rate=RATE)[0],
            ENVELOPE,
            sample_rate=RATE,
        )
        frequencies = synth.frequency_curve(
            200.0, 100.0, 0.1, easing='ease_out_quad', sample_rate=RATE
        )
        second = synth.oscillator(Waveform.SQUARE, frequencies, 0.1, sample_rate=RATE)[0]
        second = synth.distort(second, 2.0)
        second = synth.low_pass(second, 2000.0, sample_rate=RATE)
        second, _ = synth.tremolo(second, 12.0, 0.3, sample_rate=RATE)
        second = synth.apply_envelope(second, ENVELOPE, sample_rate=RATE) * 0.5
        expected = synth.normalize(synth.mix(first, (second, 0.05), sample_rate=RATE), peak=0.9)
        np.testing.assert_allclose(recipe.render(sample_rate=RATE), expected)

    def test_to_sound_wraps_the_render_at_the_mixer_rate_with_the_recipe_volume(self, mocker):
        mocker.patch('glitchygames.audio.effects.mixer_sample_rate', return_value=RATE)
        to_sound = mocker.patch('glitchygames.audio.effects.to_sound')
        recipe = _two_tone_recipe()

        sound = recipe.to_sound()

        assert sound is to_sound.return_value
        (samples,) = to_sound.call_args.args
        np.testing.assert_array_equal(samples, recipe.render(sample_rate=RATE))
        assert to_sound.call_args.kwargs == {'volume': recipe.volume}

    def test_noise_is_repeatable(self):
        recipe = Effect(
            name='hiss',
            tones=(
                Tone(
                    waveform=Waveform.NOISE,
                    start_frequency=0.0,
                    duration=0.05,
                    envelope=ENVELOPE,
                ),
            ),
        )
        np.testing.assert_array_equal(
            recipe.render(sample_rate=RATE), recipe.render(sample_rate=RATE)
        )
        assert RECIPE_NOISE_SEED == 0


class TestValidationAndSerialization:
    """Tests for tone validation, serialization and TOML loading."""

    @pytest.mark.parametrize(
        ('field', 'value'),
        [('duration', -0.1), ('offset', -0.01), ('volume', -1.0)],
    )
    def test_tone_validation(self, field, value):
        settings: dict[str, Any] = {
            'waveform': Waveform.SINE,
            'start_frequency': 440.0,
            'duration': 0.1,
            'envelope': ENVELOPE,
            field: value,
        }
        with pytest.raises(ValueError, match=field):
            Tone(**settings)

    def test_round_trip(self):
        recipe = _two_tone_recipe()
        assert Effect.from_dict('ting', recipe.to_dict()) == recipe

    def test_from_dict_names_recipe_and_field(self):
        data = _two_tone_recipe().to_dict()
        data['tones'][1]['waveform'] = 'kazoo'
        with pytest.raises(EffectError, match=r'ting\.tones\[1\]\.waveform'):
            Effect.from_dict('ting', data)

    @pytest.mark.parametrize(
        ('field', 'value', 'match'),
        [
            ('envelope', {'attack': 0.1}, r'ting\.tones\[1\]\.envelope'),
            ('tremolo', {'rate_hz': 12.0}, r'ting\.tones\[1\]'),
            ('volume', 'loud', r'ting\.tones\[1\]'),
        ],
    )
    def test_from_dict_reports_bad_tone_fields(self, field, value, match):
        data = _two_tone_recipe().to_dict()
        data['tones'][1][field] = value
        with pytest.raises(EffectError, match=match):
            Effect.from_dict('ting', data)

    @pytest.mark.parametrize(('field', 'value'), [('volume', 'loud'), ('peak', [0.9])])
    def test_from_dict_reports_bad_recipe_fields(self, field, value):
        """A recipe-level value that is not a number names the recipe."""
        data = _two_tone_recipe().to_dict()
        data[field] = value
        with pytest.raises(EffectError, match=r'^ting: '):
            Effect.from_dict('ting', data)

    def test_cutoff_at_nyquist_rejected_at_render(self):
        recipe = Effect(
            name='bad',
            tones=(
                Tone(
                    waveform=Waveform.SINE,
                    start_frequency=440.0,
                    duration=0.05,
                    envelope=ENVELOPE,
                    low_pass_cutoff=RATE / 2,
                ),
            ),
        )
        with pytest.raises(ValueError, match='cutoff'):
            recipe.render(sample_rate=RATE)

    def test_load_toml(self, tmp_path):
        path = tmp_path / 'sounds.toml'
        path.write_text(
            '[recipes.beep]\nvolume = 0.4\n'
            '[[recipes.beep.tones]]\nwaveform = "sine"\nstart_frequency = 880.0\n'
            'duration = 0.1\n'
            '[recipes.beep.tones.envelope]\nattack = 0.001\ndecay = 0.01\n'
            'sustain_level = 0.5\nrelease = 0.05\n',
            encoding='utf-8',
        )
        recipes = load_effects(path)
        assert recipes['beep'].name == 'beep'
        assert recipes['beep'].volume == 0.4
        assert recipes['beep'].tones[0].waveform is Waveform.SINE


class TestSoundBank:
    """Tests for playing recipes through the sound bank."""

    def test_renders_once_and_caches(self, mocker):
        mocker.patch('glitchygames.audio.effects.mixer_sample_rate', return_value=RATE)
        to_sound = mocker.patch('glitchygames.audio.effects.to_sound')
        bank = SoundBank([_two_tone_recipe()])
        bank.play('ting')
        bank.play('ting')
        assert to_sound.call_count == 1
        assert to_sound.return_value.play.call_count == 2

    def test_unknown_name_raises(self):
        with pytest.raises(KeyError):
            SoundBank([]).play('missing')

    def test_no_audio_is_a_logged_no_op(self, mocker):
        mocker.patch(
            'glitchygames.audio.effects.to_sound',
            side_effect=AudioUnavailableError('x'),
        )
        warning = mocker.patch('glitchygames.audio.effects.log.warning')
        bank = SoundBank([_two_tone_recipe()])
        bank.play('ting')
        bank.play('ting')
        assert warning.call_count == 1

    def test_busy_mixer_logs_debug(self, mocker):
        to_sound = mocker.patch('glitchygames.audio.effects.to_sound')
        to_sound.return_value.play.return_value = None
        debug = mocker.patch('glitchygames.audio.effects.log.debug')
        SoundBank([_two_tone_recipe()]).play('ting')
        assert debug.called

    def test_prerender_caches_every_recipe_so_play_does_not_render(self, mocker):
        mocker.patch('glitchygames.audio.effects.mixer_sample_rate', return_value=RATE)
        to_sound = mocker.patch('glitchygames.audio.effects.to_sound')
        other_recipe = dataclasses.replace(_two_tone_recipe(), name='other')
        bank = SoundBank([_two_tone_recipe(), other_recipe])
        bank.prerender()
        assert to_sound.call_count == 2
        bank.play('ting')
        bank.play('other')
        assert to_sound.call_count == 2

    def test_prerender_without_audio_warns_once_and_does_not_raise(self, mocker):
        mocker.patch(
            'glitchygames.audio.effects.to_sound',
            side_effect=AudioUnavailableError('x'),
        )
        warning = mocker.patch('glitchygames.audio.effects.log.warning')
        bank = SoundBank([_two_tone_recipe()])
        bank.prerender()
        bank.prerender()
        bank.play('ting')
        assert warning.call_count == 1

    def test_duplicate_names_rejected(self):
        with pytest.raises(ValueError, match='ting'):
            SoundBank([_two_tone_recipe(), _two_tone_recipe()])


fuzzed_envelopes = st.builds(
    Envelope,
    attack=st.floats(min_value=0.0, max_value=0.05),
    decay=st.floats(min_value=0.0, max_value=0.05),
    sustain_level=st.floats(min_value=0.0, max_value=1.0),
    release=st.floats(min_value=0.0, max_value=0.05),
)
fuzzed_tones = st.builds(
    Tone,
    waveform=st.sampled_from(list(Waveform)),
    # Under the Nyquist frequency of the lowest rate drawn (8000 Hz)
    start_frequency=st.floats(min_value=20.0, max_value=3900.0),
    # From under half a frame (no samples) to a quarter second
    duration=st.floats(min_value=1e-6, max_value=0.25),
    envelope=fuzzed_envelopes,
    offset=st.floats(min_value=0.0, max_value=0.2),
)
fuzzed_recipes = st.builds(
    Effect, name=st.just('fuzzed'), tones=st.lists(fuzzed_tones, max_size=4).map(tuple)
)


@settings(derandomize=True, database=None, max_examples=200)
@given(recipe=fuzzed_recipes, sample_rate=st.sampled_from([8000, 22050, 44100, 48000]))
def test_a_recipes_frame_count_is_its_render_length(recipe, sample_rate):
    """``Effect.frame_count`` (a v0 sound's length without rendering) is what render gives."""
    assert recipe.frame_count(sample_rate=sample_rate) == len(
        recipe.render(sample_rate=sample_rate)
    )


def _two_tones() -> tuple[Tone, Tone]:
    """Two sine tones, one offset, whose straight sum peaks below 1."""
    return (
        Tone(
            waveform=Waveform.SINE,
            start_frequency=440.0,
            duration=0.05,
            envelope=ENVELOPE,
            volume=0.3,
        ),
        Tone(
            waveform=Waveform.SINE,
            start_frequency=660.0,
            duration=0.05,
            envelope=ENVELOPE,
            volume=0.2,
            offset=0.02,
        ),
    )


def test_an_effect_that_does_not_normalize_is_its_tones_mixed_straight():
    """normalize=False: the tones summed at their offsets, untouched (straight channel mixing)."""
    tones = _two_tones()
    effect = Effect(name='straight', tones=tones, normalize=False)

    expected = synth.mix(
        *((tone.render(sample_rate=RATE), tone.offset) for tone in tones), sample_rate=RATE
    )

    assert np.array_equal(effect.render(sample_rate=RATE), expected)


def test_an_effect_normalizes_to_its_peak_by_default():
    """The default keeps every existing effect's sound: the mix scaled to peak."""
    effect = Effect(name='scaled', tones=_two_tones(), peak=0.8)

    assert np.max(np.abs(effect.render(sample_rate=RATE))) == pytest.approx(0.8)


def test_normalize_survives_a_round_trip_through_plain_data():
    """to_dict and from_dict keep normalize, so a file can say it."""
    effect = Effect(name='straight', tones=_two_tones(), normalize=False)

    assert Effect.from_dict('straight', effect.to_dict()) == effect
    assert Effect.from_dict('straight', effect.to_dict()).normalize is False


def test_a_normalize_that_is_not_true_or_false_is_refused():
    """TOML has booleans; 1 or "no" is a mistake, said with the effect's name."""
    data = Effect(name='straight', tones=_two_tones()).to_dict() | {'normalize': 1}

    with pytest.raises(EffectError, match='straight: normalize must be true or false'):
        Effect.from_dict('straight', data)
