"""The high-score table games share (plans/2026-11-20-game-code-into-the-engine.md, sub-plan 2).

Every test runs the table on an in-memory save store that records each ``load`` and ``save``,
because the save door's calls are recorded in every replay: the table must make the same calls,
in the same order, as the four games' own code did.
"""

from __future__ import annotations

import argparse
import logging
from typing import Any

import pydantic
import pytest

from glitchygames.events.game import GameEventManager
from glitchygames.state import SaveCorruptedError
from glitchygames.state.high_scores import (
    BestScore,
    HighScoreEntry,
    HighScoreTable,
    HighScoreTableSettings,
    InvalidEntries,
)
from tests.state.recording_saves import SLOT, RecordingSaves, saves_holding


class FloorEntry(HighScoreEntry):
    """An entry with one more field, as Clockwork Keep's adds the floor reached."""

    floor: int


def table_of(
    saves: RecordingSaves,
    *,
    entry_type: type[HighScoreEntry] = HighScoreEntry,
    **settings: Any,
) -> HighScoreTable[Any]:
    """Return a table over the store, with any settings given.

    Returns:
        The table.

    """
    return HighScoreTable(
        saves=saves, entry_type=entry_type, settings=HighScoreTableSettings(**settings)
    )


def scores_of(entries: list[Any]) -> list[int]:
    """Return the entries' scores, in order.

    Returns:
        The scores.

    """
    return [entry.score for entry in entries]


class TestEntries:
    """Entries are strict, frozen models whose dump is the shape save files hold."""

    def test_an_entry_dumps_its_fields_base_first(self):
        assert FloorEntry(score=900, floor=3).model_dump() == {'score': 900, 'floor': 3}
        assert list(FloorEntry(score=900, floor=3).model_dump()) == ['score', 'floor']

    @pytest.mark.parametrize(
        'data',
        [{'floor': 3}, {'score': '5'}, {'score': True}, {'score': 1.5}, {'score': 5, 'x': 1}],
    )
    def test_a_missing_field_a_wrong_type_or_an_unknown_field_is_invalid(self, data):
        with pytest.raises(pydantic.ValidationError):
            HighScoreEntry.model_validate(data)

    def test_an_entry_is_frozen(self):
        entry = HighScoreEntry(score=5)
        field = 'score'
        with pytest.raises(pydantic.ValidationError):
            setattr(entry, field, 6)


class TestRecording:
    """record() keeps the best scores, as each game's own code did."""

    def test_a_first_score_makes_a_table_of_one(self):
        saves = saves_holding(None)

        recorded = table_of(saves).record(HighScoreEntry(score=40))

        assert scores_of(recorded) == [40]
        assert saves.calls == [('load', SLOT, None), ('save', SLOT, {'scores': [{'score': 40}]})]

    def test_a_slot_without_scores_is_an_empty_table(self):
        saves = saves_holding({'other': 1})

        assert scores_of(table_of(saves).record(HighScoreEntry(score=7))) == [7]

    def test_scores_are_kept_best_first(self):
        saves = saves_holding({'scores': [{'score': 50}, {'score': 30}]})

        recorded = table_of(saves).record(HighScoreEntry(score=40))

        assert scores_of(recorded) == [50, 40, 30]

    def test_a_new_score_that_ties_an_old_one_goes_below_it(self):
        """The sort is stable: the older of two equal scores keeps the higher place."""
        saves = saves_holding({'scores': [{'score': 50, 'floor': 1}, {'score': 30, 'floor': 2}]})

        recorded = table_of(saves, entry_type=FloorEntry).record(FloorEntry(score=50, floor=9))

        assert [entry.model_dump() for entry in recorded] == [
            {'score': 50, 'floor': 1},
            {'score': 50, 'floor': 9},
            {'score': 30, 'floor': 2},
        ]

    def test_a_full_table_drops_the_lowest_and_a_tie_at_the_bottom_loses(self):
        saves = saves_holding({'scores': [{'score': score} for score in (90, 80, 70)]})

        recorded = table_of(saves, limit=3).record(HighScoreEntry(score=70))

        assert scores_of(recorded) == [90, 80, 70]
        assert saves.calls[-1] == (
            'save',
            SLOT,
            {'scores': [{'score': 90}, {'score': 80}, {'score': 70}]},
        )

    def test_a_lowest_first_table_keeps_the_smallest_scores(self):
        """A time trial's best is its lowest time: an explicit setting, both orders tested."""
        saves = saves_holding({'scores': [{'score': 30}, {'score': 50}]})

        recorded = table_of(saves, best=BestScore.LOWEST).record(HighScoreEntry(score=40))

        assert scores_of(recorded) == [30, 40, 50]

    def test_the_slot_name_is_a_setting(self):
        saves = RecordingSaves()

        table_of(saves, slot_name='times').record(HighScoreEntry(score=3))

        assert [call[:2] for call in saves.calls] == [('load', 'times'), ('save', 'times')]


class TestReading:
    """entries() and best() read the table with one load each, and change nothing."""

    def test_entries_are_in_the_files_order(self):
        """A table is saved best first; reading it does not sort it again."""
        saves = saves_holding({'scores': [{'score': 10}, {'score': 30}]})

        assert scores_of(table_of(saves).entries()) == [10, 30]
        assert saves.calls == [('load', SLOT, None)]

    def test_no_slot_is_an_empty_table_and_a_best_of_zero(self):
        saves = saves_holding(None)

        assert table_of(saves).entries() == []
        assert table_of(saves).best() == 0

    def test_the_best_score_is_the_first_entry(self):
        saves = saves_holding({'scores': [{'score': 70}, {'score': 90}]})

        assert table_of(saves).best() == 70
        assert saves.calls == [('load', SLOT, None)]


INVALID_PAYLOAD = {'scores': [{'score': 50}, {'floor': 3}, {'score': 20, 'extra': 1}]}


class TestInvalidEntries:
    """An invalid saved entry is refused (the default) or dropped, by an explicit setting."""

    def test_refusing_raises_naming_the_slot_and_the_entry_and_saves_nothing(self):
        saves = saves_holding(INVALID_PAYLOAD)
        before = saves.load_raw(SLOT)
        saves.calls.clear()

        with pytest.raises(SaveCorruptedError, match=r"high_scores.*\{'floor': 3\}"):
            table_of(saves).record(HighScoreEntry(score=60))

        assert saves.calls == [('load', SLOT, None)]
        assert saves.load_raw(SLOT) == before

    def test_refusing_is_the_default(self):
        assert HighScoreTableSettings().invalid_entries is InvalidEntries.REFUSE

    @pytest.mark.parametrize('read', ['entries', 'best'])
    def test_reading_an_invalid_table_is_refused_too(self, read):
        with pytest.raises(SaveCorruptedError):
            getattr(table_of(saves_holding(INVALID_PAYLOAD)), read)()

    def test_dropping_keeps_the_valid_entries_and_warns_once_for_each(self, caplog):
        saves = saves_holding(INVALID_PAYLOAD)
        table = table_of(saves, invalid_entries=InvalidEntries.DROP)

        with caplog.at_level(logging.WARNING, logger='glitchygames.state.high_scores'):
            entries = table.entries()

        assert scores_of(entries) == [50]
        warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
        assert len(warnings) == 2
        assert "{'floor': 3}" in warnings[0].getMessage()

    def test_dropping_saves_the_table_without_the_invalid_entries(self):
        saves = saves_holding(INVALID_PAYLOAD)

        table_of(saves, invalid_entries=InvalidEntries.DROP).record(HighScoreEntry(score=60))

        assert saves.calls[-1] == ('save', SLOT, {'scores': [{'score': 60}, {'score': 50}]})

    @pytest.mark.parametrize('policy', list(InvalidEntries))
    def test_a_valid_table_behaves_the_same_under_both_policies(self, policy):
        saves = saves_holding({'scores': [{'score': 50}, {'score': 30}]})

        recorded = table_of(saves, invalid_entries=policy).record(HighScoreEntry(score=40))

        assert scores_of(recorded) == [50, 40, 30]


class TestTheOption:
    """--invalid-high-scores chooses the policy from the command line."""

    @staticmethod
    def parse(*arguments: str) -> argparse.Namespace:
        """Parse arguments with the game options the engine adds.

        Returns:
            The parsed options.

        """
        return GameEventManager.args(argparse.ArgumentParser()).parse_args(list(arguments))

    def test_the_default_refuses(self):
        assert self.parse().invalid_high_scores == 'refuse'

    @pytest.mark.parametrize('choice', ['refuse', 'drop'])
    def test_each_policy_parses(self, choice):
        assert InvalidEntries(self.parse('--invalid-high-scores', choice).invalid_high_scores)

    def test_any_other_value_is_refused_naming_the_choices(self, capsys):
        with pytest.raises(SystemExit):
            self.parse('--invalid-high-scores', 'ignore')

        assert "choose from 'refuse', 'drop'" in capsys.readouterr().err

    def test_settings_take_the_option(self):
        options = vars(self.parse('--invalid-high-scores', 'drop'))

        settings = HighScoreTableSettings.from_options(options=options)

        assert settings.invalid_entries is InvalidEntries.DROP
