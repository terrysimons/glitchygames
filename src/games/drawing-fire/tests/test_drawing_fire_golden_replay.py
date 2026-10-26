"""Drawing Fire's golden replay holds the game events its session is meant to cover.

Moved from the engine's tests (tests/replay/test_golden_replays.py), which still check every
golden's controls; this checks Drawing Fire's own game events (``SOLDIER_KILLED_SUBTYPE``,
``SEAT_CHANGED_SUBTYPE``, ``SeatChange``) in its own golden.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from drawing_fire.game import SEAT_CHANGED_SUBTYPE, SOLDIER_KILLED_SUBTYPE
from drawing_fire.seats import SeatChange
from glitchygames.events import GAMEEVENT
from glitchygames.recording import EVENT_BATCHES_FIELD, INTERNAL_ORIGIN
from glitchygames.tracing import read_trace_result

# The member's golden replay, directly in its tests/fixtures/replays/
GOLDEN_REPLAY_PATH = Path(__file__).parent / 'fixtures' / 'replays' / 'golden.jsonl.gz'


def received_events(*, recording: dict[str, Any]) -> list[tuple[int, str, dict[str, Any]]]:
    """Return every recorded event with its frame and the scene that received it.

    A frame's events reach the scene active when the frame starts: the scene the frame before
    ended on (a switch an event asks for happens after the frame's events). Copied from
    tests/replay/test_golden_replays.py, whose control checks still use it.

    Args:
        recording: A decoded trace.

    Returns:
        (frame number, receiving scene's class name, event record), in order.

    """
    events: list[tuple[int, str, dict[str, Any]]] = []
    frames = recording['frames']
    for index, frame in enumerate(frames):
        receiving_scene = frames[max(index - 1, 0)]['scene']
        events.extend(
            (frame['frame'], receiving_scene, record)
            for batch in frame.get(EVENT_BATCHES_FIELD, [])
            for record in batch
        )
    return events


def test_the_drawing_fire_golden_replay_holds_a_death_and_a_takeover():
    """The keyboard player (P1) is killed and takes over another soldier, as the game posted.

    Drawing Fire posts an internal game event for every death and seat change, so the replay
    compares them; this checks the session really holds the player's death and takeover, so a
    re-recording without one fails here instead of passing by luck.
    """
    game_events = [
        record['attributes']
        for _frame_number, _scene, record in received_events(
            recording=read_trace_result(path=GOLDEN_REPLAY_PATH).trace
        )
        if record['type'] == GAMEEVENT and record['origin'] == INTERNAL_ORIGIN
    ]
    deaths = [
        event
        for event in game_events
        if event['subtype'] == SOLDIER_KILLED_SUBTYPE and event['driver'] == 'P1'
    ]
    takeovers = [
        event
        for event in game_events
        if event['subtype'] == SEAT_CHANGED_SUBTYPE
        and event['change'] == SeatChange.TOOK_OVER
        and event['player'] == 'P1'
    ]
    assert deaths, 'the golden session never kills the player'
    assert takeovers, 'the golden session never hands the player another soldier'
