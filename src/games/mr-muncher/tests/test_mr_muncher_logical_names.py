"""Mr. Muncher moved from glitchygames/examples/mr_muncher: its logical names did not change."""

from __future__ import annotations

import gzip
import inspect
import json
from pathlib import Path

import mr_muncher.game
from glitchygames.exit_codes import ExitCode
from glitchygames.logical_names import logical_name
from glitchygames.replay.tools.children import (
    rebaseline_recording_headless,
    replay_recording_headless,
)
from glitchygames.scenes import Scene

# The member's golden replay, directly in its tests/fixtures/replays/
GOLDEN_REPLAY_PATH = Path(__file__).parent / 'fixtures' / 'replays' / 'golden.jsonl.gz'
# Where Mr. Muncher's game module was before it moved into its own package
FORMER_GAME_MODULE = 'glitchygames.examples.mr_muncher.game'
CONSOLE_SCRIPT = 'mr-muncher'


def test_every_scene_keeps_the_logical_name_its_recordings_hold():
    """Recordings made before the move name games.mr_muncher.game:<scene>, as moved code does."""
    scenes = [
        scene_class
        for _name, scene_class in inspect.getmembers(mr_muncher.game, inspect.isclass)
        if issubclass(scene_class, Scene) and scene_class.__module__ == mr_muncher.game.__name__
    ]

    assert scenes, 'mr_muncher.game defines its scenes'
    for scene_class in scenes:
        assert logical_name(scene_class=scene_class) == (
            f'games.mr_muncher.game:{scene_class.__qualname__}'
        )


def write_old_format_recording(*, path: Path) -> None:
    """Write the golden replay as it was recorded before logical names, from the old module.

    The header loses ``game`` and every scene start its ``scene`` (the logical names), and both
    name the module the game had before it moved: what main's golden replay held.

    Args:
        path: Where the old-format recording goes.

    """
    with gzip.open(GOLDEN_REPLAY_PATH, 'rt', encoding='utf-8') as golden:
        lines = golden.read().splitlines()
    header = json.loads(lines[0])
    header.pop('game')
    header['game_module'] = FORMER_GAME_MODULE
    old_lines = [json.dumps(header)]
    for line in lines[1:]:
        frame = json.loads(line)
        scene_start = frame.get('scene_start')
        if scene_start is not None:
            scene_start.pop('scene', None)
            scene_start['scene_module'] = FORMER_GAME_MODULE
        old_lines.append(json.dumps(frame))
    with gzip.open(path, 'wt', encoding='utf-8') as old_recording:
        old_recording.write('\n'.join(old_lines) + '\n')


class TestRecordingsMadeBeforeLogicalNames:
    """An old-format recording of the moved game: refused by a replay, converted by a rebaseline."""

    def test_a_plain_replay_refuses_it_and_names_the_rebaseline(self, tmp_path: Path):
        old_path = tmp_path / 'old.jsonl.gz'
        write_old_format_recording(path=old_path)

        completed = replay_recording_headless(console_script=CONSOLE_SCRIPT, path=old_path)

        assert completed.returncode == ExitCode.UNUSABLE_INPUT, completed.stdout
        assert 'before logical names' in completed.stdout
        assert '--replay-trace OLD --rebaseline NEW --headless' in completed.stdout

    def test_a_rebaseline_converts_it_and_the_new_recording_replays_strictly(self, tmp_path: Path):
        old_path = tmp_path / 'old.jsonl.gz'
        new_path = tmp_path / 'new.jsonl.gz'
        write_old_format_recording(path=old_path)

        rebaselined = rebaseline_recording_headless(
            console_script=CONSOLE_SCRIPT, path=old_path, new_path=new_path
        )

        assert rebaselined.returncode == ExitCode.SUCCESS, rebaselined.stdout
        assert 'no frames differ' in rebaselined.stdout
        with gzip.open(new_path, 'rt', encoding='utf-8') as new_recording:
            new_lines = new_recording.read().splitlines()
        new_header = json.loads(new_lines[0])
        assert new_header['game'] == 'games.mr_muncher.game:MrMuncherScene'
        assert new_header['game_module'] == mr_muncher.game.__name__
        first_start = json.loads(new_lines[1])['scene_start']
        assert first_start['scene'] == 'games.mr_muncher.game:MrMuncherScene'
        replayed = replay_recording_headless(console_script=CONSOLE_SCRIPT, path=new_path)
        assert replayed.returncode == ExitCode.SUCCESS, replayed.stdout
