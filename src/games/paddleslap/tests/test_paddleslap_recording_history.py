"""PaddleSlap's own recording history, as scripts/recording_report.py reports it.

Split from the engine's tests (tests/test_recording_report.py, whose end-to-end test of the
report stays there). PaddleSlap's golden predates the game's move out of
``glitchygames.examples``, so its frame-0 scene start names the old module; a rebaseline names
the new one, both under the logical name ``games.paddleslap:Game``. The report shows that as the
one behaviour change between the golden's newest run and the rebaseline.
"""

from __future__ import annotations

from pathlib import Path

from scripts.recording_report import run

from glitchygames.exit_codes import ExitCode
from glitchygames.testing.replays import rebaseline_recording_headless
from glitchygames.tracing import FRAMES_FIELD, read_trace

# The member's golden replay, directly in its tests/fixtures/replays/
GOLDEN_REPLAY_PATH = Path(__file__).parent / 'fixtures' / 'replays' / 'golden.jsonl.gz'


def test_a_rebaseline_shows_the_games_move_as_a_frame_0_behaviour_change(tmp_path, capsys):
    """The scene start's module moved; the report shows frame 0 changed, and nothing else."""
    rebaselined = tmp_path / 'rebaselined.jsonl.gz'
    completed = rebaseline_recording_headless(
        console_script='paddleslap', path=GOLDEN_REPLAY_PATH, new_path=rebaselined
    )
    assert completed.returncode == ExitCode.SUCCESS, completed.stdout

    assert run(arguments=[str(rebaselined)]) == ExitCode.SUCCESS

    output = capsys.readouterr().out
    # The first of the new runs differs from the golden's newest run in frame 0 only: a scene
    # start records the scene's module, and PaddleSlap's moved from
    # glitchygames.examples.paddleslap to paddleslap (Part 2 of
    # plans/2026-10-24-workspace-packages.md; docs/architecture/game_packages.md, "Verify")
    golden_scene_start = read_trace(path=GOLDEN_REPLAY_PATH)[FRAMES_FIELD][0]['scene_start']
    new_scene_start = read_trace(path=rebaselined)[FRAMES_FIELD][0]['scene_start']
    assert golden_scene_start['scene_module'] == 'glitchygames.examples.paddleslap'
    assert new_scene_start['scene_module'] == 'paddleslap'
    assert golden_scene_start['scene'] == new_scene_start['scene'] == 'games.paddleslap:Game'
    behaviour_changes = output.split('Behaviour changes (content hash, adjacent runs):')[1]
    # Run 0 is the newest (the rebaseline); run 1 is the golden's newest
    new_against_golden = behaviour_changes.split('run 1 -> run 0 (')[1].split('\n')[0]
    assert new_against_golden.endswith('behaviour changed in frame 0 (scene Game), 1 span, 1 frame')
