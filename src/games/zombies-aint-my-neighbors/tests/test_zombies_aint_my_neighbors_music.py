"""The score: the stage's loop and the two stings, each compiled into one sound (an engine mix).

Feature plan 11 (plans/2026-11-18-zombies-aint-my-neighbors-11-the-rest-of-the-sounds.md). These
tests hold the score to its bars: every layer of a cue fills its cue exactly, every note is one its
instrument can play, and each cue's mix is its layers, at their volumes, looping only if the cue
loops, exactly the cue's length.
"""

from __future__ import annotations

from typing import Final

import pytest

from glitchygames.audio import instruments
from glitchygames.audio.pitch import Note
from zombies_aint_my_neighbors import music
from zombies_aint_my_neighbors.game_over import GAME_OVER_SECONDS, SWITCH_OFF_SECONDS
from zombies_aint_my_neighbors.music import (
    BEAT_SECONDS,
    CUES,
    GAME_OVER,
    LOOP_SECONDS,
    REST,
    STAGE,
    STAGE_CLEAR,
)
from zombies_aint_my_neighbors.neighborhood import CHEER_SECONDS

EVERY_LAYER: Final = tuple(
    pytest.param(cue, layer, id=f'{cue.name}-{layer.instrument}')
    for cue in CUES
    for layer in cue.layers
)


def test_the_stage_loop_is_eight_bars_of_four_at_120_beats_a_minute():
    """16 s: long enough not to wear thin, short enough to compile ahead."""
    assert pytest.approx(0.5) == BEAT_SECONDS
    assert pytest.approx(8 * 4 * BEAT_SECONDS) == LOOP_SECONDS
    assert STAGE.seconds == LOOP_SECONDS
    assert STAGE.loops
    assert not STAGE_CLEAR.loops
    assert not GAME_OVER.loops


@pytest.mark.parametrize(('cue', 'layer'), EVERY_LAYER)
def test_every_layer_fills_its_cue_exactly(cue, layer):
    """Its notes and rests add up to the cue's length, so every layer keeps the same bars."""
    assert sum(beats for _pitch, beats in layer.notes) * BEAT_SECONDS == pytest.approx(cue.seconds)


@pytest.mark.parametrize(('cue', 'layer'), EVERY_LAYER)
def test_every_note_is_one_its_instrument_can_play(cue, layer):
    """Within the catalog entry's playing range: no note an instrument would mangle."""
    lowest, highest = instruments.entry(layer.instrument).playing_range
    for pitch, _beats in layer.notes:
        if pitch == REST:
            continue
        assert lowest.midi_number <= Note(pitch).midi_number <= highest.midi_number, (
            cue.name,
            pitch,
        )


@pytest.mark.parametrize(('cue', 'layer'), EVERY_LAYER)
def test_a_layer_is_written_for_the_engine_in_seconds(cue, layer):
    """The engine's melody text: each note or rest and its seconds, in order."""
    text = music.notes_text(layer)

    assert text.split() == [f'{pitch}:{beats * BEAT_SECONDS:g}' for pitch, beats in layer.notes]


def test_the_stage_clear_lasts_the_cheer():
    """The sting is over when the next card comes."""
    assert STAGE_CLEAR.seconds == pytest.approx(CHEER_SECONDS)


def test_the_game_over_sting_fits_between_the_words_and_the_title():
    """It begins as GAME OVER shows and ends before the title returns."""
    assert SWITCH_OFF_SECONDS + GAME_OVER.seconds <= GAME_OVER_SECONDS


def test_every_cue_is_made_of_catalog_instruments():
    """Each instrument is one the engine's catalog builds."""
    for cue in CUES:
        for layer in cue.layers:
            assert instruments.get(layer.instrument) is not None


def test_cue_names_are_distinct():
    """A cue's name keys its sounds."""
    assert len({cue.name for cue in CUES}) == len(CUES)


@pytest.mark.parametrize('cue', CUES, ids=[cue.name for cue in CUES])
def test_a_cue_is_mixed_from_its_layers_at_their_volumes(cue):
    """One part a layer: its instrument, its melody in seconds, its own volume."""
    mix = music.cue_mix(cue)

    assert mix.name == cue.name
    assert [(part.instrument, part.notes, part.volume) for part in mix.parts] == [
        (instruments.get(layer.instrument), music.notes_text(layer), layer.volume)
        for layer in cue.layers
    ]


def test_only_the_stage_loop_is_mixed_as_a_loop_of_its_own_length():
    """The loop exactly 16 s, so it repeats in time; the stings as long as they ring."""
    assert music.cue_mix(STAGE).loop_seconds == LOOP_SECONDS
    assert music.cue_mix(STAGE_CLEAR).loop_seconds is None
    assert music.cue_mix(GAME_OVER).loop_seconds is None


def test_the_score_is_declared_so_the_engine_builds_it_while_the_game_starts():
    """Every cue's mix is in SOUNDS: built during the power-on, never in a frame of play."""
    from zombies_aint_my_neighbors.roster_scene import RosterScene

    declared = set(RosterScene.SOUNDS)

    for cue in CUES:
        assert music.cue_mix(cue) in declared, cue.name
