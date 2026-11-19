"""The intro (feature plan 12): its timeline of cues, and the scene that plays it.

The plan (plans/2026-11-19-zombies-aint-my-neighbors-12-intro-and-idle-loop.md) is the spec: the
cue times below are copied from its table, not read from the code.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from zombies_aint_my_neighbors.art import intro_rig
from zombies_aint_my_neighbors.intro_timeline import (
    INTRO_SECONDS,
    INTRO_TIMELINE,
    CueKind,
    IntroCue,
    cues_crossed,
)

FRAME_SECONDS = 1.0 / 60.0
# The plan's table: every time a cue fires at
PLAN_CUE_TIMES = (0.0, 4.0, 5.5, 6.0, 6.3, 6.8, 8.0)
BAGS = tuple(f'intro_bag_{name}' for name in ('dex', 'marisol', 'theo', 'june'))


def test_the_timeline_is_in_order_and_ends_once():
    """Sorted by time, at the plan's times, with one END, last, at 8 s."""
    times = [cue.at_seconds for cue in INTRO_TIMELINE]

    assert times == sorted(times)
    assert sorted(set(times)) == list(PLAN_CUE_TIMES)
    ends = [cue for cue in INTRO_TIMELINE if cue.kind is CueKind.END]
    assert ends == [INTRO_TIMELINE[-1]]
    assert INTRO_SECONDS == ends[0].at_seconds == 8.0


def test_the_burst_is_at_six_seconds_with_the_shake_the_rumble_and_the_kids_startled():
    """6.0 s: the TV bursts, the four kids start, the screen shakes and the pads rumble."""
    at_six = [cue for cue in INTRO_TIMELINE if cue.at_seconds == 6.0]

    assert {cue.kind for cue in at_six} == {CueKind.ANIMATE, CueKind.SHAKE, CueKind.RUMBLE}
    animated = {(cue.actor, cue.animation) for cue in at_six if cue.kind is CueKind.ANIMATE}
    assert animated == {('intro_tv', 'burst'), *((bag, 'startled') for bag in BAGS)}


def test_each_cue_fires_once_frame_by_frame():
    """Stepping 0 to 9 s a 60th at a time fires the whole timeline once, in order."""
    fired: list[IntroCue] = []
    before = 0.0
    for frame in range(1, 9 * 60 + 1):
        now = frame * FRAME_SECONDS
        fired.extend(cues_crossed(timeline=INTRO_TIMELINE, before_seconds=before, now_seconds=now))
        before = now

    assert fired == list(INTRO_TIMELINE)


def test_a_long_frame_fires_every_cue_it_crosses_in_order():
    """One frame from 3.9 to 6.5 s fires the 4.0, 5.5, 6.0 and 6.3 cues, in timeline order."""
    crossed = cues_crossed(timeline=INTRO_TIMELINE, before_seconds=3.9, now_seconds=6.5)

    assert crossed == tuple(cue for cue in INTRO_TIMELINE if 3.9 <= cue.at_seconds < 6.5)
    assert {cue.at_seconds for cue in crossed} == {4.0, 5.5, 6.0, 6.3}


def test_a_cue_on_a_frame_boundary_fires_on_the_frame_that_starts_at_it():
    """A frame starting at 6.0 fires the 6.0 cues; the frame ending at 6.0 does not."""
    ending_at_six = cues_crossed(timeline=INTRO_TIMELINE, before_seconds=5.9, now_seconds=6.0)
    starting_at_six = cues_crossed(timeline=INTRO_TIMELINE, before_seconds=6.0, now_seconds=6.1)

    assert all(cue.at_seconds != 6.0 for cue in ending_at_six)
    assert {cue.at_seconds for cue in starting_at_six} == {6.0}


@pytest.mark.parametrize(
    'arguments',
    [
        {'kind': CueKind.ANIMATE},
        {'kind': CueKind.ANIMATE, 'actor': 'intro_tv'},
        {'kind': CueKind.ANIMATE, 'animation': 'burst'},
        {'kind': CueKind.SHAKE, 'actor': 'intro_tv'},
        {'kind': CueKind.END, 'animation': 'burst'},
    ],
    ids=[
        'animate-bare',
        'animate-no-animation',
        'animate-no-actor',
        'shake-actor',
        'end-animation',
    ],
)
def test_a_cue_needs_an_actor_and_animation_exactly_when_it_animates(arguments):
    """ANIMATE needs both; every other kind takes neither."""
    with pytest.raises(ValidationError):
        IntroCue(at_seconds=1.0, **arguments)


def test_every_animate_cue_names_a_sprite_and_an_animation_it_has():
    """Each ANIMATE cue's actor is an intro sprite, and its animation is one of that sprite's."""
    for cue in INTRO_TIMELINE:
        if cue.kind is CueKind.ANIMATE:
            assert cue.actor in intro_rig.INTRO_ANIMATIONS, cue
            states = {spec.state for spec in intro_rig.INTRO_ANIMATIONS[cue.actor]}
            assert cue.animation in states, cue


def test_every_intro_sprite_starts_at_zero():
    """At 0 s every actor that shows from the start gets its first animation.

    The hands and the zombie wait for their own cues.
    """
    started = {cue.actor for cue in INTRO_TIMELINE if cue.at_seconds == 0.0 and cue.actor}

    assert started == set(intro_rig.INTRO_ANIMATIONS) - {'intro_hands', 'intro_zombie'}
