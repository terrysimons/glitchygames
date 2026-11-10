"""The sprite catalog: sprite files' text, searched fuzzily and exported (sprites/catalog.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from glitchygames.exit_codes import ExitCode
from glitchygames.sprites.catalog import (
    TAG_WEIGHT,
    SpriteText,
    export_sprite_texts,
    main,
    read_sprite_text,
    read_sprite_texts,
    score_sprite,
    search_sprites,
)


def _write(directory: Path, name: str, sprite_table: str) -> Path:
    """Write a sprite file holding only its ``[sprite]`` table (all the catalog reads).

    Returns:
        The file.

    """
    path = directory / name
    path.write_text(f'[sprite]\n{sprite_table}\n', encoding='utf-8')
    return path


@pytest.fixture
def library(tmp_path: Path) -> Path:
    """Return a directory of sprites: tagged, untagged, nested, and a TOML file that is not one.

    Returns:
        The directory.

    """
    _write(tmp_path, 'sword.toml', 'name = "Iron Sword"\ntags = ["Item", "weapon", "sword"]')
    _write(tmp_path, 'shield.toml', 'name = "Shield"\ndescription = "Blocks a sword."')
    nested = tmp_path / 'nested'
    nested.mkdir()
    _write(nested, 'ghost.toml', 'name = "Ghost"\ntags = ["enemy", "undead"]')
    (tmp_path / 'settings.toml').write_text('volume = 3\n', encoding='utf-8')
    return tmp_path


class TestReading:
    """Each sprite file's [sprite] text; TOML files that are not sprites are skipped."""

    def test_a_sprite_files_text(self, library):
        sprite = read_sprite_text(library / 'sword.toml')

        assert sprite == SpriteText(
            path=library / 'sword.toml',
            name='Iron Sword',
            description='',
            tags=('item', 'weapon', 'sword'),
        )

    def test_a_directory_is_read_recursively_skipping_what_is_not_a_sprite(self, library, caplog):
        """A TOML file without [sprite] is skipped quietly; one that is not TOML, with a warning."""
        (library / 'broken.toml').write_text('[sprite\n', encoding='utf-8')

        sprites = read_sprite_texts([library])

        assert [sprite.name for sprite in sprites] == ['Ghost', 'Shield', 'Iron Sword']
        assert 'broken.toml: not valid TOML' in caplog.text

    def test_a_file_and_its_directory_count_once(self, library):
        sprites = read_sprite_texts([library / 'sword.toml', library])

        assert [sprite.name for sprite in sprites].count('Iron Sword') == 1


class TestSearching:
    """Each query word's best weighted match, summed; tags weigh most."""

    def test_a_tag_outranks_a_word_of_another_sprites_description(self, library):
        matches = search_sprites('sword', read_sprite_texts([library]))

        assert [match.sprite.name for match in matches] == ['Iron Sword', 'Shield']
        assert matches[0].score == TAG_WEIGHT

    def test_a_plural_still_matches(self, library):
        matches = search_sprites('swords', read_sprite_texts([library]))

        assert matches[0].sprite.name == 'Iron Sword'

    def test_unrelated_words_match_nothing(self, library):
        assert search_sprites('banana', read_sprite_texts([library])) == []

    def test_the_limit_keeps_the_best(self, library):
        matches = search_sprites('sword', read_sprite_texts([library]), limit=1)

        assert [match.sprite.name for match in matches] == ['Iron Sword']

    def test_equal_scores_are_ordered_by_path(self, tmp_path):
        _write(tmp_path, 'b.toml', 'name = "Rock"')
        _write(tmp_path, 'a.toml', 'name = "Rock"')

        matches = search_sprites('rock', read_sprite_texts([tmp_path]))

        assert [match.sprite.path.name for match in matches] == ['a.toml', 'b.toml']

    def test_words_add_up(self):
        sprite = SpriteText(path=Path('x.toml'), name='Ghost', description='', tags=('enemy',))

        assert score_sprite('enemy ghost', sprite) > score_sprite('ghost', sprite)


class TestExport:
    """One JSON line per sprite, its path the key, with a text passage for embedding."""

    def test_each_sprite_is_a_line(self, library, tmp_path):
        output = tmp_path / 'sprites.jsonl'

        count = export_sprite_texts(read_sprite_texts([library / 'sword.toml']), output)

        assert count == 1
        assert json.loads(output.read_text(encoding='utf-8')) == {
            'path': str(library / 'sword.toml'),
            'name': 'Iron Sword',
            'description': '',
            'tags': ['item', 'weapon', 'sword'],
            'text': 'Iron Sword. Tags: item, weapon, sword.',
        }

    def test_the_text_passage_joins_what_is_present(self):
        both = SpriteText(path=Path('x.toml'), name='Shield', description='Blocks.', tags=())
        nothing = SpriteText(path=Path('y.toml'), name='', description='', tags=())

        assert both.text() == 'Shield. Blocks.'
        assert not nothing.text()


class TestCommandLine:
    """``python -m glitchygames.sprites.catalog search|export``."""

    def test_search_prints_the_matches_best_first(self, library, capsys):
        assert main(['search', 'sword', str(library)]) == ExitCode.SUCCESS

        lines = capsys.readouterr().out.splitlines()
        assert lines[0].endswith('Iron Sword  [item, weapon, sword]')
        assert lines[1].endswith('Shield')

    def test_export_writes_the_file(self, library, tmp_path, capsys):
        output = tmp_path / 'out.jsonl'

        assert main(['export', str(output), str(library)]) == ExitCode.SUCCESS

        assert len(output.read_text(encoding='utf-8').splitlines()) == 3
        assert 'Wrote 3 sprites' in capsys.readouterr().out

    def test_a_missing_path_is_refused(self, tmp_path, capsys):
        missing = tmp_path / 'nowhere'

        assert main(['search', 'sword', str(missing)]) == ExitCode.MISSING_INPUT
        assert str(missing) in capsys.readouterr().err

    def test_an_export_that_cannot_be_written(self, library, tmp_path, capsys):
        output = tmp_path / 'no-such-folder' / 'out.jsonl'

        assert main(['export', str(output), str(library)]) == ExitCode.CANNOT_WRITE_OUTPUT
        assert 'Cannot write' in capsys.readouterr().err
