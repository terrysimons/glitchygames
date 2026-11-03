"""Sprite tags: one spelling per tag, and the problems a file's tags can have (sprites/tags.py)."""

from __future__ import annotations

import tomllib

import pytest

from glitchygames.sprites.animated import toml_tags_line
from glitchygames.sprites.tags import normalize_sprite_tags, sprite_tags_problems


class TestNormalizeSpriteTags:
    """Each tag stripped, case-folded and single-spaced; empties and repeats dropped; order kept."""

    def test_tags_are_given_one_spelling(self):
        assert normalize_sprite_tags(['  Item ', 'WEAPON', 'Short   Sword']) == [
            'item',
            'weapon',
            'short sword',
        ]

    def test_empty_tags_and_repeats_are_dropped_keeping_the_first(self):
        assert normalize_sprite_tags(['sword', '', '  ', 'Sword', 'item', 'SWORD']) == [
            'sword',
            'item',
        ]

    def test_order_is_kept(self):
        assert normalize_sprite_tags(['weapon', 'item']) == ['weapon', 'item']

    def test_case_folding_is_unicode_aware(self):
        """casefold, not lower: the German sharp s matches its capital spelling."""
        assert normalize_sprite_tags(['Straße', 'STRASSE']) == ['strasse']

    def test_no_tags_is_an_empty_list(self):
        assert normalize_sprite_tags(None) == []

    @pytest.mark.parametrize('raw', ['item', 3, {'item': True}], ids=['string', 'number', 'table'])
    def test_tags_that_are_not_a_list_give_none(self, raw):
        assert normalize_sprite_tags(raw) == []

    def test_items_that_are_not_strings_are_skipped(self):
        assert normalize_sprite_tags(['item', 3, None, 'weapon']) == ['item', 'weapon']


class TestSpriteTagsProblems:
    """What a sprite-file check reports about a file's ``tags``."""

    def test_well_formed_tags_have_no_problems(self):
        assert sprite_tags_problems(['item', 'Weapon']) == []
        assert sprite_tags_problems(None) == []

    def test_tags_that_are_not_a_list(self):
        assert sprite_tags_problems('item') == ["tags must be an array of strings, not 'item'"]

    def test_items_that_are_not_strings(self):
        assert sprite_tags_problems(['item', 3]) == ['tag 2 is not a string: 3']


class TestTomlTagsLine:
    """The writers' ``tags = [...]`` line: quoted, escaped, readable back as written."""

    def test_the_line_reads_back_as_the_tags(self):
        tags = ['item', 'say "hi"', 'back\\slash']

        line = toml_tags_line(tags)

        assert line.startswith('tags = [')
        assert tomllib.loads(line)['tags'] == tags

    def test_no_tags_writes_no_line(self):
        assert not toml_tags_line([])
