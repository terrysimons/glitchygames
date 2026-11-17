"""The listening WAVs (glitchygames/audio/listening): where they go and what is rendered.

The move from scripts/ was proven sample for sample against the scripts while they existed
(commit 155cc1fa): all 733 files matched, and the rewritten transposition search chose as the
script did in every key and on a tie. These tests hold the package to its own behaviour.
"""

from __future__ import annotations

import re
import wave
from fractions import Fraction
from typing import TYPE_CHECKING

import pytest

from glitchygames.audio import instruments
from glitchygames.audio.listening import listening_directory, pipe_tunes, pipes
from glitchygames.audio.listening.renders import render_instruments, render_pipes
from glitchygames.audio.spec import AUDIO_RENDER_VERSION

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


def _wave_file(path: Path) -> tuple[tuple[int, int, int], bytes]:
    """A WAV file's format (channels, sample width, rate) and its frames.

    Returns:
        Both.
    """
    with wave.open(str(path), 'rb') as wave_file:
        return (
            (wave_file.getnchannels(), wave_file.getsampwidth(), wave_file.getframerate()),
            wave_file.readframes(wave_file.getnframes()),
        )


def test_a_tie_between_two_transpositions_goes_to_the_first_tried():
    """D flat major from B flat 3 to E6: down 6 and up 6 score alike; the first tried, -6, wins.

    Found by searching every relative major and span (the 20 tunes never tie); the script's
    search chose -6 too (commit 155cc1fa), so the order candidates are tried in stays its.
    """
    text = "X:1\nT:t\nM:4/4\nL:1/8\nK:Db\nB,2 =e'2 |\n"

    assert pipe_tunes.uilleann_transposition(pipe_tunes.read_tune(text)) == -6


# --- The ABC reader: what each notation means (abcnotation.com, the 2.1 standard) ---

ABC_HEADER = 'X:1\nT:t\nM:4/4\nL:1/8\nK:C\n'
A4, B4, C5, D5 = 69, 71, 72, 74


def _bars(body: str) -> list[list[int | None]]:
    """A C major tune's bars in playing order, as MIDI numbers (None for a rest).

    Returns:
        The bars.
    """
    tune = pipe_tunes.read_tune(ABC_HEADER + body)
    return [[note.midi for note in bar] for bar in tune.bars]


def _lengths(body: str) -> list[Fraction]:
    """A C major tune's note lengths in whole notes, in playing order.

    Returns:
        The lengths.
    """
    tune = pipe_tunes.read_tune(ABC_HEADER + body)
    return [note.whole_notes for bar in tune.bars for note in bar]


@pytest.mark.parametrize(
    ('body', 'bars'),
    [
        ('|: A B |1 c :|2 d |', [[A4, B4], [C5], [A4, B4], [D5]]),
        ('|: A | [1 B :| [2 c |', [[A4], [B4], [A4], [C5]]),
        ('|: A |1 B |2 c :|', [[A4], [B4], [A4], [C5]]),
        ('|: A :|: B :|', [[A4], [A4], [B4], [B4]]),
        ('A | |: B :|', [[A4], [B4], [B4]]),
        ('A B', [[A4, B4]]),
        ('A |\n\nB |', [[A4], [B4]]),
        ('|: A |1 B :|2 c | d |', [[A4], [B4], [A4], [C5], [D5]]),
        ('|: A |1 B :| |2 c |', [[A4], [B4], [A4], [C5]]),
        ('|: A |1 B :|2 c', [[A4], [B4], [A4], [C5]]),
    ],
    ids=[
        'endings after bar lines',
        'endings on their own',
        'both endings inside the repeat',
        'a double repeat',
        'a repeat after music',
        'a last bar with no bar line',
        'a blank line',
        'music after the second ending',
        'a bar line before the second ending',
        'a second ending with no bar line',
    ],
)
def test_repeats_and_endings_are_played_in_order(body: str, bars: list[list[int]]):
    """A repeat plays twice; ``[1`` the first time, ``[2`` the second; ``:|:`` closes and opens."""
    assert _bars(body) == bars


@pytest.mark.parametrize(
    ('body', 'lengths'),
    [
        ('A>B C<D |', [Fraction(3, 16), Fraction(1, 16), Fraction(1, 16), Fraction(3, 16)]),
        ('| >A |', [Fraction(1, 8)]),
        ('(3ABc |', [Fraction(1, 12)] * 3),
        ('(2AB |', [Fraction(3, 16)] * 2),
        ('(4ABcd |', [Fraction(3, 32)] * 4),
    ],
    ids=['broken rhythm', 'broken rhythm with no note before', 'triplet', 'duplet', 'quadruplet'],
)
def test_rhythm_marks_change_note_lengths(body: str, lengths: list[Fraction]):
    """``>`` gives the first of a pair three quarters; ``(n`` fits n notes in the time of n-1."""
    assert _lengths(body) == lengths


@pytest.mark.parametrize(
    ('key', 'message'),
    [('H', "unreadable key 'H'"), ('Dxyz', "unknown mode 'xyz' in key 'Dxyz'")],
)
def test_a_key_that_cannot_be_read_is_refused(key: str, message: str):
    """A tune in no key the reader knows fails, rather than playing in the wrong one."""
    with pytest.raises(ValueError, match=re.escape(message)):
        pipe_tunes.key_signature(key)


def test_tied_notes_are_held_as_one():
    """``A-A`` sounds one A for both lengths (on the Highland chanter, which adds no cut)."""
    tune = pipe_tunes.read_tune(ABC_HEADER + 'A4-A4 |')

    events = pipe_tunes.chanter_events(
        tune, seconds_per_whole=2.0, instrument='highland', transposition=0
    )

    assert events == [(pipes.HIGHLAND_SCALE['LA'], pytest.approx(2.0))]


def test_a_highland_note_off_the_chanter_follows_equal_temperament_from_its_a():
    """The nine written notes are the chanter's own; any other is tempered from its 480 Hz A."""
    assert pipe_tunes.highland_frequency(69) == pipes.HIGHLAND_SCALE['LA']
    assert pipe_tunes.highland_frequency(60) == pytest.approx(480.0 * 2 ** (-9 / 12))


def test_no_regulator_chords_fit_a_key_other_than_d_or_g():
    """The regulators are tuned to D: a tune left in another key gets no chords."""
    tune = pipe_tunes.read_tune(ABC_HEADER + 'C8 |')

    layers = pipe_tunes.regulator_layers(
        tune, seconds_per_whole=2.0, transposition=0, start_frame=0
    )

    assert layers == []


def test_a_highland_tune_with_a_note_off_the_chanter_goes_on_the_uilleann_pipes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
):
    """Middle C is not one of the Highland chanter's nine notes: the uilleann pipes play it."""
    (tmp_path / 'low.abc').write_text(ABC_HEADER + 'C2 D2 |', encoding='utf-8')
    monkeypatch.setattr(pipe_tunes, 'TUNES_DIRECTORY', tmp_path)
    arrange = mocker.spy(pipe_tunes, 'arrange')

    pipe_tunes.tune_samples({'file': 'low.abc', 'suggested_instrument': 'highland'})

    assert arrange.call_args.kwargs['instrument'] == 'uilleann'


def test_a_bar_of_rests_gets_no_regulator_chords_but_its_time_passes():
    """Sí Bheag's chords: none under a silent bar; the next bar's fall after it."""
    layers = pipes.si_bheag_regulator_layers([[('_', 6)], [('D5', 6)]], start_frame=0)

    eighth_frames = pipes.SI_BHEAG_EIGHTH_SECONDS * pipes.SAMPLE_RATE
    assert [start for _samples, start, _gain in layers] == [
        round((6 + 2) * eighth_frames),
        round((6 + 4) * eighth_frames),
    ]


# --- Rendering into the listening folder ---


def test_a_render_writes_only_what_is_missing(tmp_path: Path):
    """The second render finds every file kept and writes none."""
    first = render_pipes(root=tmp_path, only='chanter_A')

    again = render_pipes(root=tmp_path, only='chanter_A')

    names = ['highland_chanter_A.wav', 'uilleann_chanter_A.wav']
    assert [path.name for path in first.written] == names
    assert first.already_kept == ()
    assert again.written == ()
    assert again.already_kept == first.written


def test_only_and_family_choose_the_instruments(tmp_path: Path):
    """``only`` matches the name, ``family`` the family; a filtered render writes no index."""
    report = render_instruments(root=tmp_path, family=instruments.Family.BAGPIPES, only='uilleann')

    directory = listening_directory(root=tmp_path) / 'instruments'
    assert report.written
    assert {path.parent.name for path in report.written} == {'bagpipes'}
    assert all('uilleann' in path.stem for path in report.written)
    assert not (directory / 'index.txt').exists()


def test_the_listening_folder_is_the_render_versions_under_the_root(tmp_path: Path):
    """``<root>/listening/<render version>``: a newer engine's files never mix with these."""
    assert listening_directory(root=str(tmp_path)) == (
        tmp_path / 'listening' / str(AUDIO_RENDER_VERSION)
    )


def _assert_listenable(path: Path) -> None:
    """A listening file: 16-bit mono PCM at 44100 Hz, with something in it."""
    (channels, width, rate), frames = _wave_file(path)
    assert (channels, width, rate) == (1, 2, 44100), path
    assert any(frames), f'{path} is silent'


def test_every_pipe_demo_and_tune_renders(tmp_path: Path):
    """The six demos and every tune in the index, each a file to listen to."""
    report = render_pipes(root=tmp_path)

    directory = listening_directory(root=tmp_path) / 'pipes'
    expected = sorted(
        [directory / f'{name}.wav' for name in pipes.PIPE_DEMOS]
        + [
            directory / 'tunes' / f'{pipe_tunes.tune_name(entry)}.wav'
            for entry in pipe_tunes.tune_entries()
        ]
    )
    assert sorted(report.written) == expected
    for path in expected:
        _assert_listenable(path)


def test_every_catalog_instrument_renders_with_the_index(tmp_path: Path):
    """Each instrument under its family's folder; the index has a line for each, in order."""
    report = render_instruments(root=tmp_path)

    directory = listening_directory(root=tmp_path) / 'instruments'
    entries = list(instruments.entries())
    assert report.written == tuple(
        directory / entry.family.value / f'{entry.name}.wav' for entry in entries
    )
    for path in report.written:
        _assert_listenable(path)
    index = (directory / 'index.txt').read_text(encoding='utf-8').splitlines()
    assert [line.split('  ')[0].strip() for line in index] == [
        entry.family.value for entry in entries
    ]
    assert all(entry.name in line for entry, line in zip(entries, index, strict=True))
