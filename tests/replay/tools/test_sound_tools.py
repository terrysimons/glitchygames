"""The ``sound-render`` and ``sound-migrate`` tools (replay/tools/sound_tools.py).

``sound-render SOURCE --sound-output PATH`` renders a sound offline to a WAV file
(``glitchygames.audio.render_to_file``); ``sound-migrate FILE`` rewrites a version 0 recipe file
as a version 1 sound file. Both run no game, on either front end.
"""

from __future__ import annotations

import errno
import tomllib
import wave

import numpy as np
import pytest

from glitchygames.audio.assets import clear_sound_file_cache, load_sound_file
from glitchygames.audio.library import CacheMode
from glitchygames.audio.render import NORMALIZED_PEAK
from glitchygames.engine_context import EngineContext
from glitchygames.exit_codes import ExitCode
from glitchygames.replay.tools import command
from glitchygames.replay.tools.sound_tools import (
    MIGRATED_SUFFIX,
    migrated_document,
    sound_migrate_on_the_game,
    sound_render_on_the_game,
)
from glitchygames.scenes import Scene
from tests.audio.library_support import make_library, stop_mixer

SAMPLE_RATE = 44100
# A version 1 sound file with one sound
COIN_FILE = """\
[glitchygames]
kind = "sounds"
version = 1

[instruments.pickup]
envelope = "pluck"

[instruments.pickup.sources.tone]
wave = "pulse_25"

[sounds.coin]
instrument = "pickup"
notes = "B5:0.06 E6:0.18"
"""
# A version 0 recipe file every recipe of which version 1 can say: tones starting together,
# held alike, with one envelope, at most one filter each, no tremolo or distortion
MIGRATABLE_RECIPES = """\
[recipes.zap]
volume = 0.4
peak = 0.9

[[recipes.zap.tones]]
waveform = "sine"
start_frequency = 880.0
end_frequency = 440.0
easing = "linear"
duration = 0.12
volume = 0.8

[recipes.zap.tones.envelope]
attack = 0.002
decay = 0.02
sustain_level = 0.6
release = 0.03

[recipes.hiss]
volume = 0.2
peak = 0.9

[[recipes.hiss.tones]]
waveform = "noise"
start_frequency = 0.0
duration = 0.08
volume = 1.0
high_pass_cutoff = 2000.0

[recipes.hiss.tones.envelope]
attack = 0.001
decay = 0.01
sustain_level = 0.5
release = 0.02

[[recipes.hiss.tones]]
waveform = "square"
start_frequency = 220.0
duration = 0.08
volume = 0.5
low_pass_cutoff = 3000.0

[recipes.hiss.tones.envelope]
attack = 0.001
decay = 0.01
sustain_level = 0.5
release = 0.02
"""
# A recipe version 1 cannot say yet: a tone that starts late and trembles, and tones held for
# different lengths
UNMIGRATABLE_RECIPES = """\
[recipes.flash]
volume = 0.3

[[recipes.flash.tones]]
waveform = "triangle"
start_frequency = 1318.5
duration = 0.06
offset = 0.05

[recipes.flash.tones.envelope]
attack = 0.005
decay = 0.05
sustain_level = 0.6
release = 0.05

[recipes.flash.tones.tremolo]
rate_hz = 30.0
depth = 0.4

[[recipes.flash.tones]]
waveform = "sawtooth"
start_frequency = 659.0
duration = 0.08

[recipes.flash.tones.envelope]
attack = 0.005
decay = 0.05
sustain_level = 0.6
release = 0.05
"""


@pytest.fixture(autouse=True)
def _isolated_context_without_a_mixer():
    stop_mixer()
    clear_sound_file_cache()
    with EngineContext(name='sound tools test').active():
        yield
    clear_sound_file_cache()
    stop_mixer()


def read_wav(path):
    """Read a 16-bit mono PCM WAV file.

    Returns:
        Its samples and rate.
    """
    with wave.open(str(path), 'rb') as wave_file:
        rate = wave_file.getframerate()
        raw = wave_file.readframes(wave_file.getnframes())
    return np.frombuffer(raw, dtype='<i2'), rate


def compiled_coin(sound_file):
    """Compile the coin through a library, as a game would.

    Returns:
        Its int16 samples.
    """
    library, _ = make_library(CacheMode.RAM)
    return library.sound(f'{sound_file}#coin', scene_sound_directory=None).samples_int16


def test_sound_render_tool_writes_the_file_and_exits_success(tmp_path, capsys):
    """``glitchygames sound-render FILE#name --sound-output PATH`` writes the compiled buffer."""
    sound_file = tmp_path / 'pickups.toml'
    sound_file.write_text(COIN_FILE, encoding='utf-8')
    output = tmp_path / 'out' / 'coin.wav'

    status = command.main(['sound-render', f'{sound_file}#coin', '--sound-output', str(output)])

    samples, rate = read_wav(output)
    assert status == ExitCode.SUCCESS
    assert rate == SAMPLE_RATE
    assert np.array_equal(samples, compiled_coin(sound_file))
    assert f'wrote {output}: {len(samples)} frames at {SAMPLE_RATE} Hz' in capsys.readouterr().out


def test_sound_render_on_the_game_runs_in_place_of_the_game(tmp_path, capsys):
    """``<game> --sound-render ...``: the game handler renders; the game takes no part."""
    sound_file = tmp_path / 'pickups.toml'
    sound_file.write_text(COIN_FILE, encoding='utf-8')
    output = tmp_path / 'coin.wav'

    status = sound_render_on_the_game(
        options={
            'sound_render': f'{sound_file}#coin',
            'sound_output': str(output),
            'sample_format': 'float32',
        },
        game=Scene,
    )

    assert status == ExitCode.SUCCESS
    assert output.read_bytes()[20:22] == (3).to_bytes(2, 'little')  # IEEE float format tag
    assert 'wrote' in capsys.readouterr().out


def test_sound_render_of_a_recorded_wav(tmp_path):
    """A WAV path (no ``#name``) renders as its decoded samples."""
    source = tmp_path / 'ramp.wav'
    ramp = np.linspace(-20000, 20000, 441).astype(np.int16)
    with wave.open(str(source), 'wb') as wave_file:
        wave_file.setnchannels(1)
        wave_file.setsampwidth(2)
        wave_file.setframerate(SAMPLE_RATE)
        wave_file.writeframes(ramp.tobytes())
    output = tmp_path / 'copy.wav'

    status = command.main(['sound-render', str(source), '--sound-output', str(output)])

    assert status == ExitCode.SUCCESS
    assert np.array_equal(read_wav(output)[0], ramp)


def test_sound_render_of_a_missing_file_is_missing_input(tmp_path, capsys):
    """A source whose file does not exist is MISSING_INPUT, naming it; nothing is written."""
    output = tmp_path / 'coin.wav'

    status = command.main([
        'sound-render',
        f'{tmp_path / "absent.toml"}#coin',
        '--sound-output',
        str(output),
    ])

    assert status == ExitCode.MISSING_INPUT
    assert f'{tmp_path / "absent.toml"}: no such sound file' in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize(
    ('source_suffix', 'contents', 'message'),
    [
        ('#coin', 'not toml [', 'not valid TOML'),
        ('', COIN_FILE, 'name a sound in the file'),
        ('#nothing', COIN_FILE, "has no sound 'nothing'"),
    ],
    ids=['malformed', 'no-sound-named', 'unknown-sound'],
)
def test_sound_render_of_an_unusable_source_is_unusable_input(
    tmp_path, capsys, source_suffix, contents, message
):
    """A malformed file, a file with no ``#name`` or an unknown name is UNUSABLE_INPUT."""
    sound_file = tmp_path / 'pickups.toml'
    sound_file.write_text(contents, encoding='utf-8')
    output = tmp_path / 'coin.wav'

    status = command.main([
        'sound-render',
        f'{sound_file}{source_suffix}',
        '--sound-output',
        str(output),
    ])

    assert status == ExitCode.UNUSABLE_INPUT
    assert message in capsys.readouterr().err
    assert not output.exists()


def test_sound_render_to_an_unwritable_path_cannot_write_output(tmp_path, capsys):
    """An output that cannot be written (a directory) is CANNOT_WRITE_OUTPUT, in one line."""
    sound_file = tmp_path / 'pickups.toml'
    sound_file.write_text(COIN_FILE, encoding='utf-8')
    directory = tmp_path / 'taken'
    directory.mkdir()

    status = command.main(['sound-render', f'{sound_file}#coin', '--sound-output', str(directory)])

    assert status == ExitCode.CANNOT_WRITE_OUTPUT
    assert f'{directory} is a directory' in capsys.readouterr().err


def test_sound_render_without_an_output_is_refused(tmp_path):
    """``--sound-output`` is required: without it the tool is refused, OPTIONS_REFUSED."""
    sound_file = tmp_path / 'pickups.toml'
    sound_file.write_text(COIN_FILE, encoding='utf-8')

    assert command.main(['sound-render', f'{sound_file}#coin']) == ExitCode.OPTIONS_REFUSED


def write_recipes(tmp_path, text, name='recipes.toml'):
    """Write a version 0 recipe file.

    Returns:
        Its path.
    """
    path = tmp_path / name
    path.write_text(text, encoding='utf-8')
    return path


def legacy_and_migrated(original, migrated, *, name):
    """Compile a recipe as version 0 and its migrated sound, each in a library of its own.

    Returns:
        The two float sample arrays: the recipe's, then the migrated sound's.
    """
    library, _ = make_library(CacheMode.RAM)
    recipe = original.sounds[name].legacy_recipe
    assert recipe is not None
    library.add_recipes([recipe])
    legacy = library.sound(name, scene_sound_directory=None).samples_float
    migrated_samples = library.sound(f'{migrated}#{name}', scene_sound_directory=None).samples_float
    assert legacy is not None
    assert migrated_samples is not None
    return legacy, migrated_samples


def test_migrate_round_trips_a_v0_recipe_file(tmp_path, capsys):
    """The migrated file is a version 1 sound file holding the same sounds, that sound alike.

    Every recipe becomes an instrument and a sound of the same name; the file reads back as the
    document written. Compiled, each migrated sound is as long as its recipe, and a tone without
    noise follows the recipe's samples to within the two renderers' differences (version 1's
    envelope stages and normalization to -1 dBFS rather than the recipe's peak); noise differs
    by its seed, so only its length is compared.
    """
    recipes = write_recipes(tmp_path, MIGRATABLE_RECIPES)

    status = command.main(['sound-migrate', str(recipes)])

    migrated = tmp_path / f'recipes{MIGRATED_SUFFIX}'
    assert status == ExitCode.SUCCESS
    assert f'wrote {migrated}: 2 sounds' in capsys.readouterr().out
    assert recipes.read_text(encoding='utf-8') == MIGRATABLE_RECIPES  # the input is untouched
    original = load_sound_file(recipes)
    with migrated.open('rb') as migrated_file:
        assert tomllib.load(migrated_file) == migrated_document(original)
    sound_file = load_sound_file(migrated)
    assert sound_file.version == 1
    assert set(sound_file.sounds) == set(original.sounds) == {'zap', 'hiss'}
    legacy_zap, migrated_zap = legacy_and_migrated(original, migrated, name='zap')
    assert len(migrated_zap) == len(legacy_zap)
    rescaled = migrated_zap * (0.9 / NORMALIZED_PEAK)
    assert np.max(np.abs(rescaled - legacy_zap)) < 0.02
    legacy_hiss, migrated_hiss = legacy_and_migrated(original, migrated, name='hiss')
    assert len(migrated_hiss) == len(legacy_hiss)
    migrated_volume = load_sound_file(migrated).sounds['zap'].playback_defaults.volume
    assert migrated_volume == pytest.approx(0.4 * 0.9 / NORMALIZED_PEAK)


def test_migrate_maps_each_recipe_field_to_its_version_1_field(tmp_path):
    """Waveforms, pitches, pitch curves, envelopes, filters and levels land where they belong."""
    recipes = write_recipes(tmp_path, MIGRATABLE_RECIPES)

    document = migrated_document(load_sound_file(recipes))

    assert document['glitchygames'] == {'kind': 'sounds', 'version': 1}
    assert document['instruments']['zap'] == {
        'envelope': {
            'attack': 0.002,
            'decay': 0.02,
            'sustain': 0.6,
            'release': 0.03,
            'curve': 'linear',
        },
        'normalize': True,
        'sources': {
            'tone_1': {
                'wave': 'sine',
                'pitch': 880.0,
                'pitch_curve': {'to': 440.0, 'seconds': 0.12, 'easing': 'linear'},
                'level': 0.8,
            }
        },
    }
    assert document['sounds']['zap'] == {
        'instrument': 'zap',
        'pitch': 880.0,
        'length': pytest.approx(0.09),
        'volume': pytest.approx(0.4 * 0.9 / NORMALIZED_PEAK),
    }
    hiss_sources = document['instruments']['hiss']['sources']
    assert hiss_sources['tone_1'] == {
        'noise': 'white',
        'filter': {'type': 'high_pass', 'cutoff': 2000.0},
        'level': 1.0,
    }
    assert hiss_sources['tone_2'] == {
        'wave': 'square',
        'pitch': 220.0,
        'filter': {'type': 'low_pass', 'cutoff': 3000.0},
        'level': 0.5,
    }
    # A sound whose first pitched tone is not the first: the sound takes that tone's pitch
    assert document['sounds']['hiss']['pitch'] == 220.0


def test_migrate_names_every_field_version_1_cannot_say_and_writes_nothing(tmp_path, capsys):
    """An offset, a tremolo and tones held for different lengths are each named; UNUSABLE_INPUT."""
    recipes = write_recipes(tmp_path, UNMIGRATABLE_RECIPES)

    status = command.main(['sound-migrate', str(recipes)])

    errors = capsys.readouterr().err
    assert status == ExitCode.UNUSABLE_INPUT
    assert 'recipes.flash.tones[0].offset' in errors
    assert 'recipes.flash.tones[0].tremolo' in errors
    assert 'recipes.flash.tones[1].duration' in errors
    assert not (tmp_path / f'recipes{MIGRATED_SUFFIX}').exists()


@pytest.mark.parametrize(
    ('recipe', 'field', 'reason'),
    [
        (
            'waveform = "sine"\nstart_frequency = 440.0\nduration = 0.1\ndistortion = 0.5\n',
            'tones[0].distortion',
            'no version 1 form',
        ),
        (
            (
                'waveform = "sine"\nstart_frequency = 440.0\nduration = 0.1\n'
                'low_pass_cutoff = 2000.0\nhigh_pass_cutoff = 100.0\n'
            ),
            'tones[0].high_pass_cutoff',
            'one filter',
        ),
        (
            'waveform = "sine"\nstart_frequency = 440.0\nduration = 0.01\n',
            'tones[0].duration',
            'longer than its envelope',
        ),
    ],
    ids=['distortion', 'two-filters', 'shorter-than-its-envelope'],
)
def test_migrate_refuses_each_tone_field_without_a_version_1_form(
    tmp_path, capsys, recipe, field, reason
):
    """Each field a version 1 source cannot hold is named with its reason."""
    text = (
        '[recipes.one]\n[[recipes.one.tones]]\n'
        + recipe
        + '[recipes.one.tones.envelope]\nattack = 0.001\ndecay = 0.01\n'
        + 'sustain_level = 0.5\nrelease = 0.02\n'
    )
    recipes = write_recipes(tmp_path, text)

    status = command.main(['sound-migrate', str(recipes)])

    errors = capsys.readouterr().err
    assert status == ExitCode.UNUSABLE_INPUT
    assert f'recipes.one.{field}' in errors
    assert reason in errors


def test_migrate_refuses_a_recipe_too_loud_for_a_version_1_volume(tmp_path, capsys):
    """A recipe whose volume and peak would need a sound volume above 1 is named."""
    text = MIGRATABLE_RECIPES.replace('volume = 0.4\n', 'volume = 1.0\n', 1)
    recipes = write_recipes(tmp_path, text)

    status = command.main(['sound-migrate', str(recipes)])

    assert status == ExitCode.UNUSABLE_INPUT
    assert 'recipes.zap.volume' in capsys.readouterr().err


def test_migrate_refuses_tones_with_different_envelopes_or_too_many_tones(tmp_path, capsys):
    """Tones of one sound share one envelope, and a sound has at most four."""
    tone = (
        '[[recipes.many.tones]]\nwaveform = "sine"\nstart_frequency = 440.0\nduration = 0.1\n'
        '[recipes.many.tones.envelope]\nattack = 0.001\ndecay = 0.01\n'
        'sustain_level = {sustain}\nrelease = 0.02\n'
    )
    text = '[recipes.many]\n' + ''.join(
        tone.format(sustain=sustain) for sustain in (0.5, 0.5, 0.5, 0.5, 0.4)
    )
    recipes = write_recipes(tmp_path, text)

    status = command.main(['sound-migrate', str(recipes)])

    errors = capsys.readouterr().err
    assert status == ExitCode.UNUSABLE_INPUT
    assert 'recipes.many.tones: 5 tones' in errors
    assert 'recipes.many.tones[4].envelope' in errors


def test_migrate_writes_where_it_is_told(tmp_path):
    """``--migrated-output PATH`` writes the version 1 file there instead."""
    recipes = write_recipes(tmp_path, MIGRATABLE_RECIPES)
    output = tmp_path / 'elsewhere' / 'sounds.toml'

    status = sound_migrate_on_the_game(
        options={'sound_migrate': str(recipes), 'migrated_output': str(output)},
        game=Scene,
    )

    assert status == ExitCode.SUCCESS
    assert load_sound_file(output).version == 1
    assert not (tmp_path / f'recipes{MIGRATED_SUFFIX}').exists()


def test_migrate_never_overwrites_its_input(tmp_path, capsys):
    """An output that is the input itself is refused, OPTIONS_REFUSED; the input is untouched."""
    recipes = write_recipes(tmp_path, MIGRATABLE_RECIPES)

    status = command.main(['sound-migrate', str(recipes), '--migrated-output', str(recipes)])

    assert status == ExitCode.OPTIONS_REFUSED
    assert 'would overwrite the file it migrates' in capsys.readouterr().err
    assert recipes.read_text(encoding='utf-8') == MIGRATABLE_RECIPES


def test_migrate_of_a_missing_file_is_missing_input(tmp_path, capsys):
    """A file that does not exist is MISSING_INPUT."""
    status = command.main(['sound-migrate', str(tmp_path / 'absent.toml')])

    assert status == ExitCode.MISSING_INPUT
    assert 'no such recipe file' in capsys.readouterr().err


@pytest.mark.parametrize(
    ('contents', 'message'),
    [('not toml [', 'not valid TOML'), (COIN_FILE, 'is already a version 1 sound file')],
    ids=['malformed', 'already-version-1'],
)
def test_migrate_of_an_unusable_file_is_unusable_input(tmp_path, capsys, contents, message):
    """A malformed file, or one already at version 1, is UNUSABLE_INPUT."""
    recipes = write_recipes(tmp_path, contents)

    status = command.main(['sound-migrate', str(recipes)])

    assert status == ExitCode.UNUSABLE_INPUT
    assert message in capsys.readouterr().err


def test_migrate_to_an_unwritable_path_cannot_write_output(tmp_path, capsys):
    """An output that cannot be written is CANNOT_WRITE_OUTPUT."""
    recipes = write_recipes(tmp_path, MIGRATABLE_RECIPES)
    directory = tmp_path / 'taken'
    directory.mkdir()

    status = command.main(['sound-migrate', str(recipes), '--migrated-output', str(directory)])

    assert status == ExitCode.CANNOT_WRITE_OUTPUT
    assert f'{directory} is a directory' in capsys.readouterr().err


def test_sound_render_of_a_sound_that_cannot_compile_is_unusable_input(tmp_path, capsys):
    """A pitched sound given no pitch fails to compile: UNUSABLE_INPUT, naming why."""
    sound_file = tmp_path / 'pickups.toml'
    sound_file.write_text(COIN_FILE.replace('notes = "B5:0.06 E6:0.18"\n', ''), encoding='utf-8')
    output = tmp_path / 'coin.wav'

    status = command.main(['sound-render', f'{sound_file}#coin', '--sound-output', str(output)])

    assert status == ExitCode.UNUSABLE_INPUT
    assert 'needs a pitch, notes or chord' in capsys.readouterr().err
    assert not output.exists()


def test_sound_render_whose_write_fails_cannot_write_output(tmp_path, capsys, mocker):
    """A write that fails part way (the disk filling) is CANNOT_WRITE_OUTPUT, in one line."""
    sound_file = tmp_path / 'pickups.toml'
    sound_file.write_text(COIN_FILE, encoding='utf-8')
    output = tmp_path / 'coin.wav'
    mocker.patch(
        'glitchygames.replay.tools.sound_tools.render_to_file',
        side_effect=OSError(errno.ENOSPC, 'No space left on device'),
    )

    status = command.main(['sound-render', f'{sound_file}#coin', '--sound-output', str(output)])

    assert status == ExitCode.CANNOT_WRITE_OUTPUT
    assert f'{output} cannot be written (No space left on device)' in capsys.readouterr().err


def test_migrate_whose_write_fails_cannot_write_output(tmp_path, capsys, mocker):
    """A migrated file whose write fails part way is CANNOT_WRITE_OUTPUT, in one line."""
    recipes = write_recipes(tmp_path, MIGRATABLE_RECIPES)
    mocker.patch(
        'glitchygames.replay.tools.sound_tools.write_aside_then_replace',
        side_effect=OSError(errno.ENOSPC, 'No space left on device'),
    )

    status = command.main(['sound-migrate', str(recipes)])

    assert status == ExitCode.CANNOT_WRITE_OUTPUT
    assert 'cannot be written (No space left on device)' in capsys.readouterr().err


def test_migrate_reports_a_value_version_1_refuses_as_its_loader_does(tmp_path, capsys):
    """A sustain level above 1 (version 0 never checked it) fails the written file's load.

    Nothing replaces anything: neither the migrated file nor its partial file is left.
    """
    text = MIGRATABLE_RECIPES.replace('sustain_level = 0.6', 'sustain_level = 1.5')
    recipes = write_recipes(tmp_path, text)

    status = command.main(['sound-migrate', str(recipes)])

    errors = capsys.readouterr().err
    assert status == ExitCode.UNUSABLE_INPUT
    assert 'the migrated file would not load' in errors
    assert 'sustain' in errors
    assert sorted(path.name for path in tmp_path.iterdir()) == ['recipes.toml']


def test_migrate_refuses_a_recipe_without_tones_or_with_a_tone_too_loud(tmp_path, capsys):
    """A recipe without tones has no version 1 source; a tone above level 1 cannot be one."""
    text = (
        '[recipes.empty]\nvolume = 0.5\n\n'
        '[recipes.loud]\n[[recipes.loud.tones]]\nwaveform = "sine"\nstart_frequency = 440.0\n'
        'duration = 0.1\nvolume = 1.5\n[recipes.loud.tones.envelope]\nattack = 0.001\n'
        'decay = 0.01\nsustain_level = 0.5\nrelease = 0.02\n'
    )
    recipes = write_recipes(tmp_path, text)

    status = command.main(['sound-migrate', str(recipes)])

    errors = capsys.readouterr().err
    assert status == ExitCode.UNUSABLE_INPUT
    assert 'recipes.empty.tones: a version 1 instrument needs at least one source' in errors
    assert 'recipes.loud.tones[0].volume: 1.5' in errors


def test_the_migrated_document_of_a_file_it_cannot_migrate_is_a_value_error(tmp_path):
    """``migrated_document`` refuses a file ``migration_problems`` finds problems in."""
    recipes = write_recipes(tmp_path, UNMIGRATABLE_RECIPES)

    with pytest.raises(ValueError, match=r'recipes\.flash\.tones\[0\]\.offset'):
        migrated_document(load_sound_file(recipes))
