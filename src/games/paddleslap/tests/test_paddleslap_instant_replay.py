"""PaddleSlap's golden script, paused and resumed, plays back from its instant-replay journal.

Moved from the engine's tests (tests/replay/test_instant_replay.py), which keep the engine's
instant replay covered with stand-in scenes (``InstantCountingScene`` and others). This runs
PaddleSlap's own golden script through ``record_trace('paddleslap')``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scripts.record_golden_traces import GAME_SCENES, record_trace

from glitchygames.instant_replay import JOURNAL_START_FRAME, InstantReplayJournal
from glitchygames.replay.playback import INSTANT_PLAYBACK, PlaybackOptions, start_playback
from glitchygames.scenes import Scene, SceneManager

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from glitchygames.replay.playback import PlaybackOutcome

# The seconds of journal the test opts PaddleSlap into (tests/replay/test_instant_replay.py's)
INSTANT_REPLAY_TEST_SECONDS = 10.0
# PaddleSlap's golden script pauses at frame 450 and resumes at 510: both are journaled
PADDLESLAP_JOURNALED_FRAMES = 600


def journal_of(manager: SceneManager) -> InstantReplayJournal:
    """Return the scene manager's journal, checked to exist.

    Copied from tests/replay/test_instant_replay.py, whose stand-in tests still use it.

    Returns:
        The journal.

    """
    journal = manager.instant_replay_journal
    assert journal is not None
    return journal


class TestAnExampleGame:
    """PaddleSlap's golden script, paused and resumed, plays back from its journal exactly."""

    def test_paddleslaps_journal_plays_back_exactly(self, mocker: MockerFixture):
        scene_class = GAME_SCENES['paddleslap']
        mocker.patch.object(scene_class, 'INSTANT_REPLAY_SECONDS', INSTANT_REPLAY_TEST_SECONDS)
        outcomes: list[PlaybackOutcome] = []

        def start_and_watch(*, frame_number: int, scene: Scene, sprite_ids: object) -> None:
            """Start playing the journal after its last frame; keep how the playback ends."""
            del sprite_ids
            # The harness installs its own scene manager singleton for the run
            manager = SceneManager()
            if frame_number == PADDLESLAP_JOURNALED_FRAMES - 1:
                recording = journal_of(manager).as_recording()
                assert len(recording.frames) == JOURNAL_START_FRAME + PADDLESLAP_JOURNALED_FRAMES
                assert start_playback(
                    manager=manager,
                    header=recording.header,
                    frames=recording.frames,
                    then=scene,
                    options=PlaybackOptions(
                        kind=INSTANT_PLAYBACK, start_frame=recording.start_frame
                    ),
                )
            outcome = manager.last_playback_outcome
            if outcome is not None and not outcomes:
                outcomes.append(outcome)
                result = manager.last_playback_result
                assert result is not None
                assert result.divergence is None, result.report()

        record_trace(
            'paddleslap',
            frame_count=2 * PADDLESLAP_JOURNALED_FRAMES + 1,
            frame_observer=start_and_watch,
        )
        assert [outcome.reason for outcome in outcomes] == ['end_of_recording']
        assert outcomes[0].frames_played == PADDLESLAP_JOURNALED_FRAMES
