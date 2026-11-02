"""Tests for sound files: the v1 TOML schema, v0 recipes and the malformed-file corpus."""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

import pytest

from glitchygames.audio.assets import (
    FIELDS_ARRIVING_LATER,
    SoundEntry,
    SoundFile,
    clear_sound_file_cache,
    is_path_reference,
    load_sound_file,
)
from glitchygames.audio.exceptions import GlitchyGamesAudioError, SoundAssetError
from glitchygames.audio.instrument import Instrument, Noise
from glitchygames.audio.recipes import SoundRecipe
from glitchygames.audio.spec import ENVELOPE_PRESETS, EnvelopeSpec, PlaybackDefaults
from glitchygames.audio.waves import Harmonics, Wave, current_wave_registry
from glitchygames.engine_context import EngineContext

FIXTURES = Path(__file__).parent / 'fixtures'
MALFORMED = FIXTURES / 'malformed'


@dataclass(frozen=True)
class MalformedCase:
    """One malformed file with the field path and reason its message must hold."""

    path: Path
    expected_path: str
    expected_reason: str

    @property
    def name(self) -> str:
        """The file's name, used as the test id."""
        return self.path.stem


def _malformed_cases() -> list[MalformedCase]:
    with (MALFORMED / 'expected.toml').open('rb') as expected_file:
        expected = tomllib.load(expected_file)
    return [
        MalformedCase(MALFORMED / file_name, table['path'], table['reason'])
        for file_name, table in expected.items()
    ]


MALFORMED_CASES = _malformed_cases()


@pytest.fixture(autouse=True)
def _fresh_cache():
    clear_sound_file_cache()
    yield
    clear_sound_file_cache()


def _write(directory: Path, name: str, text: str) -> Path:
    path = directory / name
    path.write_text(text)
    return path


VALID_HEADER = '[glitchygames]\nkind = "sounds"\nversion = 1\n\n'
VALID_INSTRUMENT = '[instruments.beep.sources.main]\nwave = "square"\n\n'


def test_the_corpus_has_at_least_twenty_cases_and_every_file_has_an_expectation():
    """The corpus has at least twenty cases and every file has an expectation."""
    on_disk = {path.name for path in MALFORMED.glob('*.toml')} - {'expected.toml'}
    assert len(MALFORMED_CASES) >= 20
    assert {case.path.name for case in MALFORMED_CASES} == on_disk


def test_the_pickup_example_loads():
    """The pickup example loads."""
    sound_file = load_sound_file(FIXTURES / 'sounds' / 'pickups.toml')

    assert sound_file.version == 1
    assert 'coin' in sound_file.sounds
    coin = sound_file.sounds['coin']
    assert isinstance(coin.instrument, Instrument)
    assert coin.instrument is sound_file.instruments['pickup']
    assert coin.instrument_reference == 'pickup'
    assert coin.notes == 'B5:0.06 E6:0.18'
    assert coin.playback_defaults == PlaybackDefaults(bus='effects', volume=0.6)
    assert coin.instrument.envelope == EnvelopeSpec(
        attack=0.002, decay=0.04, sustain=0.0, release=0.02, curve='steps(16)'
    )
    assert coin.file is None
    assert coin.legacy_recipe is None


def test_every_field_of_the_extras_file_reaches_its_object():
    """Every field of the extras file reaches its object."""
    sound_file = load_sound_file(FIXTURES / 'sounds' / 'extras.toml')

    assert set(sound_file.waves) == {'organ_pad', 'soft_square', 'fade', 'ghost'}
    assert sound_file.waves['organ_pad'] == Wave.from_harmonics(Harmonics.drawbars('888000000'))
    assert sound_file.waves['soft_square'] == Wave.mix(square=0.7, sine=0.3)
    assert sound_file.waves['fade'] == Wave('sine').blend('saw', amount=0.4)
    assert isinstance(sound_file.waves['ghost'], Wave)

    thump = sound_file.instruments['thump']
    assert thump.envelope == ENVELOPE_PRESETS['percussive']
    assert (thump.drive, thump.seed, thump.normalize, thump.hard_edges) == (2.0, 7, True, True)
    assert thump.filter is not None
    assert (thump.filter.kind, thump.filter.cutoff_hz) == ('low_pass', 1800.0)
    body, rattle = (source for _, source in thump.sources)
    assert body.pitch_curve is not None
    assert (body.pitch_curve.to, body.pitch_curve.seconds) == ('A1', 0.3)
    assert body.pitch_curve.easing == 'ease_out_quad'
    assert body.level == 0.8
    assert rattle.content == Noise('lfsr', bits=7, rate='C5')
    assert (rattle.semitones, rattle.detune_cents, rattle.pitch) == (2.0, 3.5, 'C4')
    assert rattle.envelope == ENVELOPE_PRESETS['pluck']
    assert rattle.filter is not None
    assert (rattle.filter.kind, rattle.filter.cutoff) == ('high_pass', 900.0)


def test_sounds_carry_identity_fields_playback_defaults_and_references():
    """Sounds carry identity fields playback defaults and references."""
    sound_file = load_sound_file(FIXTURES / 'sounds' / 'extras.toml')

    thump = sound_file.sounds['thump']
    assert (thump.pitch, thump.length, thump.transpose) == ('C2', 0.4, 0.0)
    assert thump.playback_defaults == PlaybackDefaults(priority=80, pan=-0.25, loop=False)
    stab = sound_file.sounds['chord_stab']
    assert stab.chord == ('C4', 'E4', 'G4')
    assert stab.transpose == 2.0
    assert stab.length is None
    cross = sound_file.sounds['cross']
    assert cross.instrument_reference == 'pickups.toml#pickup'
    assert (
        cross.instrument
        == load_sound_file(FIXTURES / 'sounds' / 'pickups.toml').instruments['pickup']
    )
    slap = sound_file.sounds['slap']
    assert slap.instrument is None
    assert slap.file == (FIXTURES / 'sounds' / 'sfx_slap.wav').resolve()
    assert slap.playback_defaults.bus == 'ui'


def test_notes_may_be_a_list_of_pitch_and_seconds_pairs(tmp_path):
    """Notes may be a list of pitch and seconds pairs."""
    path = _write(
        tmp_path,
        'pairs.toml',
        VALID_HEADER + VALID_INSTRUMENT + '[sounds.tune]\ninstrument = "beep"\n'
        'notes = [["C5", 0.1], [440.0, 0.2], ["_", 0.05]]\n',
    )

    assert load_sound_file(path).sounds['tune'].notes == (('C5', 0.1), (440.0, 0.2), ('_', 0.05))


def test_a_noise_source_and_a_pulse_with_duty_and_an_envelope_table(tmp_path):
    """A noise source and a pulse with duty and an envelope table."""
    path = _write(
        tmp_path,
        'duty.toml',
        VALID_HEADER + '[instruments.lead]\nenvelope = { attack = 0.0, decay = 0.1, sustain = 0.5, '
        'release = 0.1 }\n\n[instruments.lead.sources.main]\nwave = "pulse"\nduty = 0.3\n'
        'octave = 1\n\n[instruments.lead.sources.hiss]\nnoise = "white"\nlevel = 0.2\n'
        'detune_cents = -4\n',
    )

    lead = load_sound_file(path).instruments['lead']
    main, hiss = (source for _, source in lead.sources)
    assert lead.envelope == EnvelopeSpec(attack=0.0, decay=0.1, sustain=0.5, release=0.1)
    assert isinstance(main.content, Wave)
    assert main.content.duty == 0.3
    assert main.semitones == 12.0
    assert hiss.content == Noise('white')
    assert hiss.level == 0.2


def test_an_lfsr_source_takes_default_taps_and_a_pitch_rate_follows_the_note(tmp_path):
    """An lfsr source takes default taps and a pitch rate follows the note."""
    path = _write(
        tmp_path,
        'lfsr.toml',
        VALID_HEADER + '[instruments.hiss.sources.main]\nnoise = "lfsr"\n'
        'lfsr = { bits = 15, taps = [14, 13], rate = "pitch" }\n',
    )

    hiss = load_sound_file(path).instruments['hiss']
    assert hiss.sources[0][1].content == Noise('lfsr', bits=15, taps=(14, 13), rate=None)


def test_a_source_may_use_a_wave_defined_in_the_file(tmp_path):
    """A source may use a wave defined in the file."""
    path = _write(
        tmp_path,
        'custom.toml',
        VALID_HEADER + '[waves.ghost]\nharmonics = { octave = 0.5, fundamental = 1.0 }\n\n'
        '[instruments.lead.sources.main]\nwave = "ghost"\n',
    )

    sound_file = load_sound_file(path)
    assert sound_file.instruments['lead'].sources[0][1].content is sound_file.waves['ghost']


def test_waves_may_mix_and_blend_waves_defined_in_the_same_file_in_any_order(tmp_path):
    """Waves may mix and blend waves defined in the same file in any order."""
    path = _write(
        tmp_path,
        'chain.toml',
        VALID_HEADER + '[waves.second]\nblend = { from = "first", to = "sine", amount = 0.5 }\n\n'
        '[waves.first]\nmix = { saw = 1.0, square = 1.0 }\n',
    )

    sound_file = load_sound_file(path)
    assert sound_file.waves['second'] == sound_file.waves['first'].blend('sine', amount=0.5)


def test_waves_that_refer_to_each_other_in_a_circle_are_refused(tmp_path):
    """Waves that refer to each other in a circle are refused."""
    path = _write(
        tmp_path,
        'circle.toml',
        VALID_HEADER + '[waves.a]\nmix = { b = 1.0 }\n\n[waves.b]\nmix = { a = 1.0 }\n',
    )

    with pytest.raises(SoundAssetError, match='circular'):
        load_sound_file(path)


def test_a_wave_may_use_points_with_every_shape_and_named_positions(tmp_path):
    """A wave may use points with every shape and named positions."""
    path = _write(
        tmp_path,
        'shapes.toml',
        VALID_HEADER + '[waves.steppy]\nshape = "steps"\nnormalize = false\n'
        'points = [{ at = 0.0, level = 0.5 }, { at = "half", level = "bottom" }, '
        '{ at = 1.0, level = 0.5 }]\n',
    )

    assert isinstance(load_sound_file(path).waves['steppy'], Wave)


def test_a_v0_recipe_file_loads_each_recipe_as_a_short_name():
    """A v0 recipe file loads each recipe as a short name."""
    sound_file = load_sound_file(FIXTURES / 'sounds' / 'legacy_recipes.toml')

    assert sound_file.version == 0
    assert set(sound_file.sounds) == {'crunch_one', 'sugar_rush', 'camera_flash'}
    entry = sound_file.sounds['sugar_rush']
    assert isinstance(entry.legacy_recipe, SoundRecipe)
    assert entry.legacy_recipe.name == 'sugar_rush'
    assert entry.instrument is None
    assert entry.playback_defaults == PlaybackDefaults()
    assert not sound_file.waves
    assert not sound_file.instruments


def test_a_bad_v0_recipe_names_the_recipe_and_the_file(tmp_path):
    """A bad v0 recipe names the recipe and the file."""
    path = _write(
        tmp_path,
        'legacy.toml',
        '[recipes.bad]\nvolume = 0.5\n[[recipes.bad.tones]]\nwaveform = "sine"\n',
    )

    with pytest.raises(SoundAssetError, match=r'legacy\.toml.*recipes\.bad'):
        load_sound_file(path)


def test_a_v0_file_with_another_table_is_refused(tmp_path):
    """A v0 file with another table is refused."""
    path = _write(tmp_path, 'legacy.toml', '[recipes.ok]\nvolume = 0.5\n\n[sounds.extra]\n')

    with pytest.raises(SoundAssetError, match=r'sounds: unknown table'):
        load_sound_file(path)


@pytest.mark.parametrize('case', MALFORMED_CASES, ids=lambda case: case.name)
def test_each_malformed_file_names_its_field_and_reason(case):
    """Each malformed file names its field and reason."""
    with pytest.raises(SoundAssetError) as raised:
        load_sound_file(case.path)

    assert case.expected_path in str(raised.value)
    assert case.expected_reason in str(raised.value)
    assert case.path.name in str(raised.value)


def test_a_typo_suggests_the_field():
    """A typo suggests the field."""
    with pytest.raises(SoundAssetError, match="did you mean 'envelope'"):
        load_sound_file(MALFORMED / 'envelope_typo.toml')


def test_a_later_milestone_field_says_when_it_arrives():
    """A later milestone field says when it arrives."""
    with pytest.raises(SoundAssetError, match='routes arrives in M2'):
        load_sound_file(MALFORMED / 'routes_in_m1.toml')


def test_every_later_milestone_field_names_its_milestone():
    """Every later milestone field names its milestone."""
    assert FIELDS_ARRIVING_LATER['routes'] == 'M2'
    assert FIELDS_ARRIVING_LATER['wavetable'] == 'M4'
    assert FIELDS_ARRIVING_LATER['reverb'] == 'M5'


def test_every_problem_in_a_file_is_reported_at_once(tmp_path):
    """Every problem in a file is reported at once."""
    path = _write(
        tmp_path,
        'two.toml',
        VALID_HEADER + VALID_INSTRUMENT + '[sounds.a]\ninstrument = "beep"\nvolume = 2.0\n'
        '[sounds.b]\ninstrument = "beep"\nbus = "radio"\n',
    )

    with pytest.raises(SoundAssetError) as raised:
        load_sound_file(path)

    assert 'sounds.a.volume' in str(raised.value)
    assert 'sounds.b.bus' in str(raised.value)


def test_newer_versions_are_refused_and_v0_recipes_load():
    """Newer versions are refused and v0 recipes load."""
    with pytest.raises(SoundAssetError, match='version 99'):
        load_sound_file(MALFORMED / 'version_99.toml')
    assert load_sound_file(FIXTURES / 'sounds' / 'legacy_recipes.toml').version == 0


def test_a_version_below_one_in_a_header_is_refused(tmp_path):
    """A version below one in a header is refused."""
    path = _write(tmp_path, 'zero.toml', '[glitchygames]\nkind = "sounds"\nversion = 0\n')

    with pytest.raises(SoundAssetError, match='version 0'):
        load_sound_file(path)


def test_a_header_without_a_version_is_refused(tmp_path):
    """A header without a version is refused."""
    path = _write(tmp_path, 'noversion.toml', '[glitchygames]\nkind = "sounds"\n')

    with pytest.raises(SoundAssetError, match=r'glitchygames\.version'):
        load_sound_file(path)


def test_a_file_that_is_not_toml_is_refused(tmp_path):
    """A file that is not toml is refused."""
    path = _write(tmp_path, 'broken.toml', '[glitchygames\nkind = ')

    with pytest.raises(SoundAssetError, match=r'broken\.toml.*not valid TOML'):
        load_sound_file(path)


def test_a_missing_file_is_a_sound_asset_error(tmp_path):
    """A missing file is a sound asset error."""
    with pytest.raises(SoundAssetError, match=r'nothing\.toml.*cannot be read'):
        load_sound_file(tmp_path / 'nothing.toml')


def test_sound_asset_errors_are_audio_errors():
    """Sound asset errors are audio errors."""
    assert issubclass(SoundAssetError, GlitchyGamesAudioError)


@pytest.mark.parametrize(
    'reference',
    ['../../outside/slap.wav', '/usr/share/slap.wav', 'sub/../../up.wav'],
)
def test_paths_escaping_the_package_are_refused(tmp_path, reference):
    """Paths escaping the package are refused."""
    path = _write(tmp_path, 'escape.toml', VALID_HEADER + f'[sounds.coin]\nfile = "{reference}"\n')

    with pytest.raises(SoundAssetError, match='escapes'):
        load_sound_file(path)


def test_a_recorded_file_must_exist_and_be_wav_or_ogg(tmp_path):
    """A recorded file must exist and be wav or ogg."""
    missing = _write(tmp_path, 'missing.toml', VALID_HEADER + '[sounds.coin]\nfile = "gone.wav"\n')
    (tmp_path / 'clip.mp3').write_bytes(b'')
    wrong = _write(tmp_path, 'wrong.toml', VALID_HEADER + '[sounds.coin]\nfile = "clip.mp3"\n')

    with pytest.raises(SoundAssetError, match=r'gone\.wav does not exist'):
        load_sound_file(missing)
    with pytest.raises(SoundAssetError, match=r'\.wav or \.ogg'):
        load_sound_file(wrong)


def test_an_instrument_in_another_file_resolves_relative_to_this_file(tmp_path):
    """An instrument in another file resolves relative to this file."""
    (tmp_path / 'library').mkdir()
    _write(tmp_path / 'library', 'shared.toml', VALID_HEADER + VALID_INSTRUMENT)
    path = _write(
        tmp_path,
        'user.toml',
        VALID_HEADER + '[sounds.hello]\ninstrument = "library/shared.toml#beep"\npitch = "C4"\n',
    )

    assert load_sound_file(path).sounds['hello'].instrument is not None


def test_a_missing_instrument_in_another_file_names_the_file(tmp_path):
    """A missing instrument in another file names the file."""
    _write(tmp_path, 'shared.toml', VALID_HEADER + VALID_INSTRUMENT)
    path = _write(
        tmp_path,
        'user.toml',
        VALID_HEADER + '[sounds.hello]\ninstrument = "shared.toml#bep"\npitch = "C4"\n',
    )

    with pytest.raises(SoundAssetError, match=r"shared\.toml has no instrument 'bep'"):
        load_sound_file(path)


def test_an_invalid_file_named_by_an_instrument_reference_is_reported(tmp_path):
    """An invalid file named by an instrument reference is reported."""
    _write(tmp_path, 'shared.toml', '[glitchygames]\nkind = "sprite"\nversion = 1\n')
    path = _write(
        tmp_path,
        'user.toml',
        VALID_HEADER + '[sounds.hello]\ninstrument = "shared.toml#beep"\npitch = "C4"\n',
    )

    with pytest.raises(SoundAssetError, match=r'sounds\.hello\.instrument.*shared\.toml'):
        load_sound_file(path)


def test_files_whose_instruments_refer_to_each_other_in_a_circle_are_refused(tmp_path):
    """Files whose instruments refer to each other in a circle are refused."""
    _write(tmp_path, 'a.toml', VALID_HEADER + '[sounds.one]\ninstrument = "b.toml#beep"\n')
    _write(
        tmp_path,
        'b.toml',
        VALID_HEADER + VALID_INSTRUMENT + '[sounds.two]\ninstrument = "a.toml#beep"\n',
    )

    with pytest.raises(SoundAssetError, match='circular'):
        load_sound_file(tmp_path / 'a.toml')


def test_a_v0_file_cannot_supply_an_instrument(tmp_path):
    """A v0 file cannot supply an instrument."""
    _write(tmp_path, 'old.toml', '[recipes.ok]\nvolume = 0.5\n')
    path = _write(
        tmp_path,
        'user.toml',
        VALID_HEADER + '[sounds.hello]\ninstrument = "old.toml#ok"\npitch = "C4"\n',
    )

    with pytest.raises(SoundAssetError, match='version 0'):
        load_sound_file(path)


def test_loading_twice_returns_the_cached_file(tmp_path):
    """Loading twice returns the cached file."""
    path = _write(tmp_path, 'one.toml', VALID_HEADER + VALID_INSTRUMENT)

    assert load_sound_file(path) is load_sound_file(path)
    assert load_sound_file(path) is load_sound_file(tmp_path / '.' / 'one.toml')


def test_a_changed_modification_time_reloads_the_file(tmp_path):
    """A changed modification time reloads the file."""
    path = _write(tmp_path, 'one.toml', VALID_HEADER + VALID_INSTRUMENT)
    first = load_sound_file(path)

    path.write_text(VALID_HEADER + VALID_INSTRUMENT + '[sounds.hi]\ninstrument = "beep"\n')
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000_000))
    second = load_sound_file(path)

    assert second is not first
    assert 'hi' in second.sounds


def test_a_changed_instrument_file_reloads_the_file_that_uses_it(tmp_path):
    """A changed instrument file reloads the file that uses it."""
    shared = _write(tmp_path, 'shared.toml', VALID_HEADER + VALID_INSTRUMENT)
    path = _write(
        tmp_path,
        'user.toml',
        VALID_HEADER + '[sounds.hello]\ninstrument = "shared.toml#beep"\npitch = "C4"\n',
    )
    first = load_sound_file(path)

    shared.write_text(
        VALID_HEADER + '[instruments.beep]\ndrive = 3.0\n[instruments.beep.sources.main]\n'
        'wave = "sine"\n'
    )
    stat = shared.stat()
    os.utime(shared, ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000_000))
    second = load_sound_file(path)

    assert second is not first
    entry = second.sounds['hello']
    assert entry.instrument is not None
    assert entry.instrument.drive == 3.0


@pytest.mark.parametrize(
    ('source', 'expected'),
    [
        ('coin', False),
        ('sfx_slap', False),
        ('sounds/pickups.toml#coin', True),
        ('sounds/pickups.toml', True),
        ('pickups.toml#coin', True),
        ('sfx_slap.wav', True),
        ('music.ogg', True),
        ('sounds/sfx_slap', True),
        ('a.b', False),
    ],
)
def test_is_path_reference(source, expected):
    """Is path reference."""
    assert is_path_reference(source) is expected


def test_sound_entries_and_files_are_frozen():
    """Sound entries and files are frozen."""
    sound_file = load_sound_file(FIXTURES / 'sounds' / 'pickups.toml')

    assert isinstance(sound_file, SoundFile)
    assert isinstance(sound_file.sounds['coin'], SoundEntry)
    with pytest.raises(AttributeError):
        sound_file.version = 2  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[invalid-assignment]
    with pytest.raises(TypeError):
        sound_file.sounds['other'] = sound_file.sounds['coin']  # pyright: ignore[reportIndexIssue]  # ty: ignore[invalid-assignment]


def _sound_text(body):
    return VALID_HEADER + VALID_INSTRUMENT + '[sounds.coin]\ninstrument = "beep"\n' + body


# (file text, TOML path, reason) for problems that need only a few lines of TOML
INLINE_CASES = {
    'filter_is_not_a_table': (
        VALID_HEADER + '[instruments.beep]\nfilter = 5\n' + VALID_INSTRUMENT,
        'instruments.beep.filter',
        'valid dictionary',
    ),
    'pitch_is_a_list': (_sound_text('pitch = ["C4"]\n'), 'sounds.coin.pitch', 'note name'),
    'note_is_not_a_pair': (
        _sound_text('notes = ["C5:0.1"]\n'),
        'sounds.coin.notes',
        'each note is [pitch, seconds]',
    ),
    'note_seconds_are_text': (
        _sound_text('notes = [["C5", "long"]]\n'),
        'sounds.coin.notes',
        'must be a number',
    ),
    'notes_is_a_number': (_sound_text('notes = 5\n'), 'sounds.coin.notes', 'array of [pitch'),
    'two_hundred_fifty_seven_notes': (
        _sound_text('notes = "' + 'C5:0.01 ' * 257 + '"\n'),
        'sounds.coin.notes',
        'at most 256',
    ),
    'unknown_point_position': (
        VALID_HEADER + '[waves.odd]\npoints = [{ at = "middle", level = 0.0 }]\n',
        'waves.odd.points[0].at',
        "unknown position 'middle'",
    ),
    'point_that_is_not_a_table': (
        VALID_HEADER
        + '[waves.odd]\npoints = [{ at = 0.0, level = 0.0 }, { at = 1.0, level = 0.0 }, 5]\n',
        'waves.odd.points[2]',
        'valid dictionary',
    ),
    'unknown_shape': (
        VALID_HEADER + '[waves.odd]\nshape = "wavy"\npoints = [{ at = 0.0, level = 0.0 }]\n',
        'waves.odd.shape',
        "unknown shape 'wavy'",
    ),
    'shape_on_a_mix': (
        VALID_HEADER + '[waves.odd]\nshape = "smooth"\nmix = { sine = 1.0 }\n',
        'waves.odd',
        'applies only to a wave drawn with points',
    ),
    'unknown_filter_type': (
        VALID_HEADER
        + '[instruments.beep]\nfilter = { type = "notch", cutoff = 10.0 }\n'
        + VALID_INSTRUMENT,
        'instruments.beep.filter.type',
        "unknown filter type 'notch'",
    ),
    'unknown_easing': (
        VALID_HEADER + '[instruments.beep.sources.main]\nwave = "sine"\n'
        'pitch_curve = { to = "C5", seconds = 0.1, easing = "bouncy" }\n',
        'instruments.beep.sources.main.pitch_curve.easing',
        "Unknown easing function 'bouncy'",
    ),
    'unknown_noise_kind': (
        VALID_HEADER + '[instruments.beep.sources.main]\nnoise = "brown"\n',
        'instruments.beep.sources.main.noise',
        "unknown noise 'brown'",
    ),
    'unknown_profile': (
        VALID_HEADER + '[instruments.beep]\nprofile = "analog"\n' + VALID_INSTRUMENT,
        'instruments.beep.profile',
        "unknown profile 'analog'",
    ),
    'recorded_file_with_a_pitch': (
        VALID_HEADER + '[sounds.coin]\nfile = "clip.wav"\npitch = "C4"\n',
        'sounds.coin',
        'a recorded file takes no pitch',
    ),
    'sound_named_like_a_path': (
        VALID_HEADER + VALID_INSTRUMENT + '[sounds."a/b"]\ninstrument = "beep"\n',
        'sounds.a/b',
        'would be read as a path',
    ),
    'drawbars_with_levels': (
        VALID_HEADER + '[waves.odd]\nharmonics = { drawbars = "888000000", octave = 0.5 }\n',
        'waves.odd.harmonics',
        'drawbars cannot be combined',
    ),
    'harmonics_all_silent': (
        VALID_HEADER + '[waves.odd]\nharmonics = { fundamental = 0.0 }\n',
        'waves.odd',
        'every level is zero',
    ),
    'instrument_in_a_file_above': (
        VALID_HEADER + VALID_INSTRUMENT + '[sounds.coin]\ninstrument = "../other.toml#beep"\n',
        'sounds.coin.instrument',
        "escapes the sound file's directory",
    ),
    'name_that_is_a_builtin_wave': (
        VALID_HEADER + '[waves.sine]\nmix = { square = 1.0 }\n',
        'waves.sine',
        'built-in wave name',
    ),
}


@pytest.mark.parametrize('name', INLINE_CASES)
def test_inline_problems_name_their_field_and_reason(tmp_path, name):
    """Inline problems name their field and reason."""
    text, expected_path, expected_reason = INLINE_CASES[name]
    (tmp_path / 'clip.wav').write_bytes(b'')
    path = _write(tmp_path, f'{name}.toml', text)

    with pytest.raises(SoundAssetError) as raised:
        load_sound_file(path)

    assert expected_path in str(raised.value)
    assert expected_reason in str(raised.value)


def test_a_wave_may_mix_a_wave_registered_in_the_engine_context(tmp_path):
    """A wave may mix a wave registered in the engine context."""
    with EngineContext(name='assets test').active():
        current_wave_registry().register('game_wave', Wave('triangle'))
        path = _write(
            tmp_path,
            'registered.toml',
            VALID_HEADER + '[waves.both]\nmix = { game_wave = 1.0, sine = 1.0 }\n\n'
            '[instruments.lead.sources.main]\nwave = "game_wave"\n',
        )

        sound_file = load_sound_file(path)

    assert isinstance(sound_file.waves['both'], Wave)
    assert sound_file.instruments['lead'].sources[0][1].content == 'game_wave'


def test_a_directory_is_not_a_readable_sound_file(tmp_path):
    """A directory is not a readable sound file."""
    with pytest.raises(SoundAssetError, match='cannot be read'):
        load_sound_file(tmp_path)


def test_a_dependency_that_disappears_makes_the_cached_file_stale(tmp_path):
    """A dependency that disappears makes the cached file stale."""
    shared = _write(tmp_path, 'shared.toml', VALID_HEADER + VALID_INSTRUMENT)
    path = _write(
        tmp_path,
        'user.toml',
        VALID_HEADER + '[sounds.hello]\ninstrument = "shared.toml#beep"\npitch = "C4"\n',
    )
    load_sound_file(path)

    shared.unlink()

    with pytest.raises(SoundAssetError, match=r'shared\.toml'):
        load_sound_file(path)
