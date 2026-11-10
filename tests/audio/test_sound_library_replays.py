"""A game that plays library sounds replays exactly: under each cache mode, and through a rebuild.

What a game can observe of the sound engine (a handle's ``is_playing``, a sound's ``length`` and
``peak``, the steals) must be the same in a replay whatever ``--sound-cache`` it runs under (a
replay-local option) and whether frames were silenced (a watched replay's step-back rebuild, an
instant replay's fast-forward: glitchygames/replay/silence.py). The stand-in game
(``SoundingRallyScene``, tests/stand_in_harness_games.py) puts what it reads into its sprites, so
the replay compares it frame by frame.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
import pytest

from glitchygames.exit_codes import ExitCode
from glitchygames.replay.tools.golden_traces import (
    GoldenTraceEngine,
    GoldenTraceSceneManager,
    command_line,
)
from glitchygames.tracing import read_trace_result
from tests.replay.replay_helpers import replay_through_engine
from tests.stand_in_harness_games import (
    BURST_FRAME,
    LONG_NOTE_FRAME,
    SOUNDING_RALLY_FRAMES,
    SoundingRallyScene,
)

if TYPE_CHECKING:
    from pathlib import Path

# The rebuild runs frames 0 .. PAUSE_FRAME - 1 silenced: from before the long note to after the
# burst, so every play and steal happens in silenced frames
PAUSE_FRAME = 25
# The stand-in's probes, in the order it adds them
LENGTH_PROBE, PLAYING_PROBE, BURST_PROBE = range(3)
# No FPS events: the frame-stepped watched replay below runs the frames without the frame loop's
# finish (glitchygames/replay/tools/golden_traces.py ``run_frame``), where they are posted
NO_FPS_EVENTS_INTERVAL_MS = '1000000000'
# The recording's clock advances this much on every read, so its frame times are fixed (a few
# reads a frame: about a 60 Hz frame), the same on every run and driver, and the sounds end
# within the recording
FAKE_CLOCK_STEP_SECONDS = 1 / 240


class FakeCounter:
    """``clock.raw_counter_seconds`` for the recording: a fixed step on every read."""

    def __init__(self) -> None:
        """Start at 100 seconds."""
        self.now_seconds = 100.0

    def __call__(self) -> float:
        """Advance, then return the time.

        Returns:
            The fake time in seconds.
        """
        self.now_seconds += FAKE_CLOCK_STEP_SECONDS
        return self.now_seconds


@pytest.fixture
def recording(mocker, tmp_path) -> Path:
    """Record the stand-in's live run through the real engine loop (cache ``ram``, the default).

    Returns:
        The recording's path.
    """
    # GameEngine._shutdown quits pygame; later tests on this worker still need it
    mocker.patch('pygame.quit')
    mocker.patch('pygame.display.quit')
    fake_counter = mocker.patch('glitchygames.clock.raw_counter_seconds', new=FakeCounter())
    path = tmp_path / 'sounding-rally.jsonl.gz'
    GoldenTraceSceneManager.install()
    try:
        with command_line([
            '--log-level',
            'warning',
            '--target-fps',
            '0',
            '--fps-log-interval-ms',
            NO_FPS_EVENTS_INTERVAL_MS,
            '--record-trace',
            str(path),
        ]):
            engine = GoldenTraceEngine(game=SoundingRallyScene)
        engine.start()
    finally:
        pygame.event.clear()
        GoldenTraceSceneManager.uninstall()
        mocker.stop(fake_counter)
    return path


def _probe_positions(*, path: Path, probe: int) -> list[tuple[int, int]]:
    """Each recorded frame's top-left of one probe.

    Returns:
        The positions, by frame.
    """
    frames = read_trace_result(path=path).trace['frames']
    return [tuple(frame['sprites'][probe]['rect'][:2]) for frame in frames]


def test_the_recording_holds_what_the_game_read_of_the_sound_engine(recording):
    """The stand-in really exercises it: a length and peak, a note that plays, and steals."""
    lengths = _probe_positions(path=recording, probe=LENGTH_PROBE)
    playing = _probe_positions(path=recording, probe=PLAYING_PROBE)
    bursts = _probe_positions(path=recording, probe=BURST_PROBE)

    assert len(set(lengths)) == 1
    blip_milliseconds, blip_peak_hundredths = lengths[0]
    assert blip_milliseconds > 0
    assert blip_peak_hundredths > 0
    # The long note plays from its frame on, then is the burst's first steal
    assert playing[LONG_NOTE_FRAME + 1][0] > playing[LONG_NOTE_FRAME][0]
    assert playing[-1][0] == playing[BURST_FRAME][0]
    burst_still_playing, steals = bursts[BURST_FRAME]
    assert steals > 1
    assert burst_still_playing > 0
    assert bursts[-1] == (0, steals)


@pytest.mark.parametrize('cache_mode', ['ram', 'none'])
def test_the_recording_replays_exactly_under_each_cache_mode(mocker, recording, cache_mode):
    """``--sound-cache`` is replay-local: what the game read is the same under each mode."""
    replay = replay_through_engine(
        mocker=mocker,
        scene_class=SoundingRallyScene,
        path=recording,
        extra_arguments=('--sound-cache', cache_mode),
    )

    assert replay.result.divergence is None, replay.result.report()
    assert replay.exit_status == ExitCode.SUCCESS
    assert replay.result.frames_replayed == SOUNDING_RALLY_FRAMES


def test_the_recording_replays_exactly_through_a_silenced_rebuild(mocker, recording):
    """A watched replay restarted at PAUSE_FRAME rebuilds frames 0 .. PAUSE_FRAME - 1 silenced.

    Those frames are compared with the recording as any other, so the silence must not change
    what the game reads; resumed, the replay then plays on to the recording's end.
    """
    mocker.patch('pygame.quit')
    mocker.patch('pygame.display.quit')
    manager = GoldenTraceSceneManager.install()
    try:
        with command_line([
            '--log-level',
            'warning',
            '--replay-trace',
            str(recording),
            '--replay-pause-at-frame',
            str(PAUSE_FRAME),
        ]):
            engine = GoldenTraceEngine(game=SoundingRallyScene)
        engine.install_game(scene_class=SoundingRallyScene)
        sources = engine.replay_sources
        assert sources is not None
        while not sources.controls.paused:
            manager.dt = sources.frame_seconds(measured=0.0)
            manager.run_frame()
        assert sources.result.divergence is None, sources.result.report()
        assert sources.controls.current_frame == PAUSE_FRAME
        sources.controls.handle_key(key=pygame.K_SPACE)  # resume
        while not sources.controls.paused:
            manager.dt = sources.frame_seconds(measured=0.0)
            manager.run_frame()
    finally:
        GoldenTraceSceneManager.uninstall()

    assert sources.result.divergence is None, sources.result.report()
    assert sources.result.end_reason == 'end_of_recording'
    assert sources.result.frames_replayed == SOUNDING_RALLY_FRAMES
