"""Tests for sound recipes and the sound bank."""

from typing import Any

import numpy as np
import pytest

from glitchygames.audio import synth
from glitchygames.audio.exceptions import AudioUnavailableError, SoundRecipeError
from glitchygames.audio.recipes import (
    RECIPE_NOISE_SEED,
    SoundBank,
    SoundRecipe,
    Tone,
    Tremolo,
    load_sound_recipes,
)
from glitchygames.audio.synth import Envelope, Waveform

RATE = 44100
ENVELOPE = Envelope(attack=0.001, decay=0.01, sustain_level=0.7, release=0.02)


def _two_tone_recipe():
    return SoundRecipe(
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

    def test_noise_is_repeatable(self):
        recipe = SoundRecipe(
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
        assert SoundRecipe.from_dict('ting', recipe.to_dict()) == recipe

    def test_from_dict_names_recipe_and_field(self):
        data = _two_tone_recipe().to_dict()
        data['tones'][1]['waveform'] = 'kazoo'
        with pytest.raises(SoundRecipeError, match=r'ting\.tones\[1\]\.waveform'):
            SoundRecipe.from_dict('ting', data)

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
        with pytest.raises(SoundRecipeError, match=match):
            SoundRecipe.from_dict('ting', data)

    def test_cutoff_at_nyquist_rejected_at_render(self):
        recipe = SoundRecipe(
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
        recipes = load_sound_recipes(path)
        assert recipes['beep'].name == 'beep'
        assert recipes['beep'].volume == 0.4
        assert recipes['beep'].tones[0].waveform is Waveform.SINE


class TestSoundBank:
    """Tests for playing recipes through the sound bank."""

    def test_renders_once_and_caches(self, mocker):
        mocker.patch('glitchygames.audio.recipes.mixer_sample_rate', return_value=RATE)
        to_sound = mocker.patch('glitchygames.audio.recipes.to_sound')
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
            'glitchygames.audio.recipes.to_sound',
            side_effect=AudioUnavailableError('x'),
        )
        warning = mocker.patch('glitchygames.audio.recipes.log.warning')
        bank = SoundBank([_two_tone_recipe()])
        bank.play('ting')
        bank.play('ting')
        assert warning.call_count == 1

    def test_busy_mixer_logs_debug(self, mocker):
        to_sound = mocker.patch('glitchygames.audio.recipes.to_sound')
        to_sound.return_value.play.return_value = None
        debug = mocker.patch('glitchygames.audio.recipes.log.debug')
        SoundBank([_two_tone_recipe()]).play('ting')
        assert debug.called

    def test_duplicate_names_rejected(self):
        with pytest.raises(ValueError, match='ting'):
            SoundBank([_two_tone_recipe(), _two_tone_recipe()])
