"""PaddleSlap's bundled demo plays inside a running PaddleSlap, the way the game plays it.

Moved from the engine's tests (tests/replay/test_bundled_demos.py), which still replay every
bundled demo headless through its console script. This one plays PaddleSlap's own demo through
``SceneManager.play_recording`` and checks it returns to the live scene.
"""

from __future__ import annotations

from glitchygames.live_sources import LiveSources
from glitchygames.replay.tools.golden_traces import FRAME_SECONDS
from glitchygames.tracing import FRAMES_FIELD, read_trace_result
from paddleslap import PADDLESLAP_DEMO_PATH, Game
from tests.replay.playback_fixtures import step_finishing
from tests.world.test_frame_integration import running_scene


def test_the_paddleslap_demo_plays_in_game(mocker):
    """The demo plays to its end inside a running PaddleSlap and returns to the live scene.

    Frames run with ``_finish_frame`` (``step_finishing``), where a playback's frames take the
    recording's dt; the golden harness's ``step`` never feeds a playback the recording's dt.
    The live frames get a fixed dt: measured, one slow frame (a busy machine, a real window's
    first frames) moved the live ball far enough to end the game before the assertions.
    """
    mocker.patch.object(LiveSources, 'frame_seconds', return_value=FRAME_SECONDS)
    recorded_frames = read_trace_result(path=PADDLESLAP_DEMO_PATH).trace[FRAMES_FIELD]
    with running_scene(Game) as manager:
        live_scene = manager.active_scene
        assert live_scene is not None
        manager.play_recording(path=PADDLESLAP_DEMO_PATH, then=live_scene)

        # The frame that asks runs live; the demo's frames follow
        step_finishing(manager, frames=len(recorded_frames) + 1)

        assert manager.playback_session is None
        assert manager.active_scene is live_scene
        outcome = manager.last_playback_outcome
        assert outcome is not None
        assert outcome.reason == 'end_of_recording'
        assert outcome.frames_played == len(recorded_frames)
