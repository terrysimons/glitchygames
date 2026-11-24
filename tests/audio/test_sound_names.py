"""Tests for the short-name index: names, recorded-file stems, duplicates and unknown names."""

from pathlib import Path

import pytest

from glitchygames.audio.assets import (
    ShortNameIndex,
    SoundLocation,
    clear_sound_file_cache,
    load_sound_file,
)
from glitchygames.audio.exceptions import SoundAssetError

FIXTURES = Path(__file__).parent / 'fixtures'
SOUNDS = FIXTURES / 'sounds'
HEADER = '[glitchygames]\nkind = "sounds"\nversion = 1\n\n'


@pytest.fixture(autouse=True)
def _fresh_cache():
    clear_sound_file_cache()
    yield
    clear_sound_file_cache()


def test_short_names_and_recorded_file_stems_resolve():
    """Short names and recorded file stems resolve."""
    index = ShortNameIndex(SOUNDS)

    assert index.resolve('coin') == SoundLocation(path=SOUNDS / 'pickups.toml', table_name='coin')
    assert index.resolve('thump') == SoundLocation(path=SOUNDS / 'extras.toml', table_name='thump')
    assert index.resolve('sugar_rush') == SoundLocation(
        path=SOUNDS / 'legacy_recipes.toml', table_name='sugar_rush'
    )
    recorded = index.resolve('sfx_slap')
    assert recorded == SoundLocation(path=SOUNDS / 'sfx_slap.wav', table_name=None)
    assert recorded.is_recorded_file
    assert not index.resolve('coin').is_recorded_file


def test_indexing_reads_table_names_only_and_skips_other_kinds_of_toml(tmp_path):
    """Indexing reads table names only and skips other kinds of toml."""
    (tmp_path / 'sprite.toml').write_text('[sprite]\nname = "hero"\n\n[sounds]\nfake = 1\n')
    (tmp_path / 'other_kind.toml').write_text(
        '[glitchygames]\nkind = "sprite"\nversion = 1\n[sounds.hidden]\n'
    )
    (tmp_path / 'real.toml').write_text(HEADER + '[sounds.visible]\ninstrument = "nothing"\n')
    index = ShortNameIndex(tmp_path)

    assert index.resolve('visible').path == tmp_path / 'real.toml'
    for hidden in ('hidden', 'fake', 'hero'):
        with pytest.raises(KeyError):
            index.resolve(hidden)


def test_a_duplicate_short_name_names_both_files():
    """A duplicate short name names both files."""
    index = ShortNameIndex(SOUNDS / 'dup')

    with pytest.raises(SoundAssetError) as raised:
        index.resolve('zap')

    assert 'a.toml' in str(raised.value)
    assert 'b.toml' in str(raised.value)
    assert "'zap'" in str(raised.value)


def test_a_duplicate_is_only_raised_for_that_name(tmp_path):
    """A duplicate is only raised for that name."""
    (tmp_path / 'one.toml').write_text(HEADER + '[sounds.same]\n[sounds.alone]\n')
    (tmp_path / 'two.toml').write_text(HEADER + '[sounds.same]\n')
    index = ShortNameIndex(tmp_path)

    assert index.resolve('alone').path == tmp_path / 'one.toml'
    with pytest.raises(SoundAssetError):
        index.resolve('same')


def test_a_recorded_file_and_a_sound_with_the_same_name_are_a_duplicate(tmp_path):
    """A recorded file and a sound with the same name are a duplicate."""
    (tmp_path / 'one.toml').write_text(HEADER + '[sounds.slap]\n')
    (tmp_path / 'slap.ogg').write_bytes(b'')

    with pytest.raises(SoundAssetError, match=r'one\.toml.*slap\.ogg'):
        ShortNameIndex(tmp_path).resolve('slap')


def test_an_unknown_name_names_the_directory_and_suggests_close_matches():
    """An unknown name names the directory and suggests close matches."""
    with pytest.raises(KeyError) as raised:
        ShortNameIndex(SOUNDS).resolve('coinn')

    message = raised.value.args[0]  # a KeyError's str() is the message's repr
    assert str(SOUNDS) in message
    assert "did you mean 'coin'" in message


def test_an_unknown_name_with_no_close_match_has_no_suggestion():
    """An unknown name with no close match has no suggestion."""
    with pytest.raises(KeyError) as raised:
        ShortNameIndex(SOUNDS).resolve('zzzzzzzz')

    message = raised.value.args[0]  # a KeyError's str() is the message's repr
    assert 'did you mean' not in message
    assert str(SOUNDS) in message


def test_a_missing_sound_directory_is_a_key_error_naming_it(tmp_path):
    """A missing sound directory is a key error naming it."""
    with pytest.raises(KeyError) as raised:
        ShortNameIndex(tmp_path / 'sounds').resolve('coin')

    # A KeyError's str() is the message's repr, which doubles a Windows path's backslashes
    message = raised.value.args[0]
    assert f'the sound directory {tmp_path / "sounds"} does not exist' in message


def test_a_file_that_is_not_toml_is_reported_by_name(tmp_path):
    """A file that is not toml is reported by name."""
    (tmp_path / 'broken.toml').write_text('[glitchygames\n')

    with pytest.raises(SoundAssetError, match=r'broken\.toml.*not valid TOML'):
        ShortNameIndex(tmp_path).resolve('anything')


def test_the_index_is_built_on_the_first_lookup_and_kept(tmp_path):
    """The index is built on the first lookup and kept."""
    index = ShortNameIndex(tmp_path)
    (tmp_path / 'late.toml').write_text(HEADER + '[sounds.late]\n')

    assert index.resolve('late').path == tmp_path / 'late.toml'
    (tmp_path / 'later.toml').write_text(HEADER + '[sounds.later]\n')
    with pytest.raises(KeyError):
        index.resolve('later')
    assert index.directory == tmp_path


def test_the_index_loads_a_file_with_its_package_root(tmp_path):
    """The index loads a file with its package root."""
    package = tmp_path / 'game'
    (package / 'sounds').mkdir(parents=True)
    (package / 'samples').mkdir()
    (package / 'samples' / 'coin.wav').write_bytes(b'')
    (package / 'sounds' / 'pickups.toml').write_text(
        HEADER + '[sounds.coin]\nfile = "../samples/coin.wav"\n'
    )
    index = ShortNameIndex(package / 'sounds', package_root=package)

    loaded = index.load(index.resolve('coin'))

    assert loaded.sounds['coin'].file == (package / 'samples' / 'coin.wav').resolve()


EFFECT_TABLE = (
    '[effects.jump]\nvolume = 0.35\n\n'
    '[[effects.jump.tones]]\nwaveform = "sine"\nstart_frequency = 220.0\nend_frequency = 660.0\n'
    'duration = 0.12\nenvelope = { attack = 0.005, decay = 0.0, sustain_level = 1.0, '
    'release = 0.08 }\n'
)
REPOSITORY = Path(__file__).resolve().parents[2]


def test_an_effects_table_is_a_short_name(tmp_path):
    """An ``[effects.<name>]`` table is one of a file's sounds, so its name is a short name."""
    (tmp_path / 'sfx.toml').write_text(HEADER + EFFECT_TABLE)

    assert ShortNameIndex(tmp_path).resolve('jump') == SoundLocation(
        path=tmp_path / 'sfx.toml', table_name='jump'
    )


def _sound_files() -> list[Path]:
    """Every sound file the engine's fixtures and the games ship (version 1 and version 0).

    Returns:
        Their paths, sorted.
    """
    # The dup fixtures are for the index alone: their instruments are not valid, so no load
    candidates = [*SOUNDS.glob('*.toml'), *(REPOSITORY / 'src').rglob('sounds/*.toml')]
    return sorted(
        path
        for path in candidates
        if 'kind = "sounds"' in (text := path.read_text(encoding='utf-8')) or '[recipes.' in text
    )


def _every_kind_file(directory: Path) -> Path:
    """Write a version 1 file holding one table of every kind the loader reads.

    Returns:
        Its path.
    """
    path = directory / 'every_kind.toml'
    path.write_text(
        HEADER
        + '[waves.hollow]\nmix = { square = 0.7, sine = 0.3 }\n\n'
        + '[instruments.pluck]\n\n[instruments.pluck.sources.tone]\nwave = "hollow"\n\n'
        + '[sounds.ping]\ninstrument = "pluck"\npitch = "A4"\nlength = 0.1\n\n'
        + EFFECT_TABLE
    )
    return path


def test_the_corpus_holds_the_shipped_sound_files_and_both_versions():
    """The invariant below reads real files: the games', and version 0 and 1 fixtures."""
    names = {path.name for path in _sound_files()}

    assert {'pickups.toml', 'legacy_recipes.toml', 'sounds.toml'} <= names


@pytest.mark.parametrize(
    'sound_file',
    [*_sound_files(), None],
    ids=lambda path: 'every-table-kind' if path is None else str(path.relative_to(REPOSITORY)),
)
def test_every_sound_a_file_loads_is_a_short_name_for_it(sound_file, tmp_path):
    """Whatever kind of table a sound comes from, its name finds it in its directory's index.

    The conservation rule between the loader and the index: a new table kind the loader turns
    into a sound fails here until the index reads it too (``[effects.*]`` once did:
    bugs/2026-11-22-effects-tables-are-not-short-names.md).
    """
    path = _every_kind_file(tmp_path) if sound_file is None else sound_file
    loaded = load_sound_file(path, package_root=path.parent)
    index = ShortNameIndex(path.parent)

    assert loaded.sounds
    for name in loaded.sounds:
        # Several files of a directory may define one name (a duplicate the index reports when
        # the name is asked for); the index must still list this file's
        locations = index._index()[name]  # pyright: ignore[reportPrivateUsage]
        assert SoundLocation(path=path, table_name=name) in locations
