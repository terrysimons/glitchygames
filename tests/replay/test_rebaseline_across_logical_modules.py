"""A recording whose classes moved to another logical module: converted only by a rebaseline."""

from __future__ import annotations

import gc
import gzip
import json
from typing import TYPE_CHECKING, Any

from scripts.record_scripted_session import fixture_path

from glitchygames.exit_codes import ExitCode
from glitchygames.replay.driver import REBASELINE_REMEDY, ReplayRefusedError, check_recorded_game
from glitchygames.replay.playback import find_scene_class
from glitchygames.scenes import Scene
from glitchygames.testing.replays import (
    rebaseline_recording_headless,
    replay_recording_headless,
)

if TYPE_CHECKING:
    from pathlib import Path

import pytest

# Mr. Muncher's golden stands in for any game that moved to another layer
CURRENT_NAME = 'games.mr_muncher.game:MrMuncherScene'
NAME_IN_ANOTHER_LAYER = 'apps.mr_muncher.game:MrMuncherScene'
CONSOLE_SCRIPT = 'mr-muncher'
FORMER_LAYER_MOVED_NAME = 'apps.space_game.game:LayerMovedScene'


class LayerMovedScene(Scene):
    """A scene whose recordings name it in another layer."""


def write_recording_naming_logical_names(
    *, golden_path: Path, path: Path, renames: dict[str, str]
) -> None:
    """Write a golden replay with its game and scene logical names renamed.

    Args:
        golden_path: The recording to copy.
        path: Where the renamed recording goes.
        renames: Each logical name to replace, and what replaces it.

    """
    with gzip.open(golden_path, 'rt', encoding='utf-8') as golden:
        lines = golden.read().splitlines()
    header = json.loads(lines[0])
    header['game'] = renames.get(header['game'], header['game'])
    renamed_lines = [json.dumps(header)]
    for line in lines[1:]:
        frame: dict[str, Any] = json.loads(line)
        scene_start = frame.get('scene_start')
        if scene_start is not None and 'scene' in scene_start:
            scene_start['scene'] = renames.get(scene_start['scene'], scene_start['scene'])
        renamed_lines.append(json.dumps(frame))
    with gzip.open(path, 'wt', encoding='utf-8') as renamed:
        renamed.write('\n'.join(renamed_lines) + '\n')


class TestTheHeaderCheck:
    """check_recorded_game compares logical names; only a rebaseline accepts a moved module."""

    def test_a_rebaseline_accepts_the_same_class_at_another_logical_module(self):
        check_recorded_game(
            header={'game': FORMER_LAYER_MOVED_NAME}, game_class=LayerMovedScene, is_rebaseline=True
        )

    def test_a_plain_replay_refuses_it_naming_the_remedy(self):
        with pytest.raises(ReplayRefusedError, match='--replay-trace') as refusal:
            check_recorded_game(
                header={'game': FORMER_LAYER_MOVED_NAME},
                game_class=LayerMovedScene,
                is_rebaseline=False,
            )

        assert REBASELINE_REMEDY in str(refusal.value)

    def test_a_different_qualified_name_is_refused_even_by_a_rebaseline(self):
        with pytest.raises(ReplayRefusedError, match='refusing to replay it'):
            check_recorded_game(
                header={'game': 'apps.space_game.game:OtherScene'},
                game_class=LayerMovedScene,
                is_rebaseline=True,
            )


class TestTheSceneLookup:
    """find_scene_class takes a scene that moved only under a rebaseline, and only if unique."""

    def test_a_rebaseline_finds_the_moved_scene(self):
        found = find_scene_class(
            name='LayerMovedScene', logical=FORMER_LAYER_MOVED_NAME, is_rebaseline=True
        )

        assert found is LayerMovedScene

    def test_a_plain_replay_does_not(self):
        found = find_scene_class(
            name='LayerMovedScene', logical=FORMER_LAYER_MOVED_NAME, is_rebaseline=False
        )

        assert found is None

    def test_two_loaded_classes_of_that_name_are_still_refused(self):
        twin = type('LayerMovedScene', (Scene,), {'__module__': 'twin_module'})
        try:
            found = find_scene_class(
                name='LayerMovedScene', logical=FORMER_LAYER_MOVED_NAME, is_rebaseline=True
            )
        finally:
            # The twin stays in Scene.__subclasses__() until collected: remove it now, so no
            # other test sees it
            del twin
            gc.collect()

        assert found is None
        assert (
            find_scene_class(
                name='LayerMovedScene', logical=FORMER_LAYER_MOVED_NAME, is_rebaseline=True
            )
            is LayerMovedScene
        )


class TestThroughTheRealGame:
    """Mr. Muncher's golden, renamed as if recorded in another layer."""

    def test_a_plain_replay_refuses_and_names_the_remedy(self, tmp_path: Path):
        renamed_path = tmp_path / 'renamed.jsonl.gz'
        write_recording_naming_logical_names(
            golden_path=fixture_path(game_key='mr_muncher'),
            path=renamed_path,
            renames={CURRENT_NAME: NAME_IN_ANOTHER_LAYER},
        )

        completed = replay_recording_headless(console_script=CONSOLE_SCRIPT, path=renamed_path)

        assert completed.returncode == ExitCode.UNUSABLE_INPUT, completed.stdout
        assert REBASELINE_REMEDY in completed.stdout

    def test_a_rebaseline_converts_it_and_the_new_recording_replays_strictly(self, tmp_path: Path):
        renamed_path = tmp_path / 'renamed.jsonl.gz'
        new_path = tmp_path / 'new.jsonl.gz'
        write_recording_naming_logical_names(
            golden_path=fixture_path(game_key='mr_muncher'),
            path=renamed_path,
            renames={CURRENT_NAME: NAME_IN_ANOTHER_LAYER},
        )

        rebaselined = rebaseline_recording_headless(
            console_script=CONSOLE_SCRIPT, path=renamed_path, new_path=new_path
        )

        assert rebaselined.returncode == ExitCode.SUCCESS, rebaselined.stdout
        assert 'no frames differ' in rebaselined.stdout
        with gzip.open(new_path, 'rt', encoding='utf-8') as new_recording:
            new_lines = new_recording.read().splitlines()
        assert json.loads(new_lines[0])['game'] == CURRENT_NAME
        scene_names = [
            json.loads(line)['scene_start']['scene']
            for line in new_lines[1:]
            if json.loads(line).get('scene_start') is not None
        ]
        assert scene_names
        assert set(scene_names) == {CURRENT_NAME}
        replayed = replay_recording_headless(console_script=CONSOLE_SCRIPT, path=new_path)
        assert replayed.returncode == ExitCode.SUCCESS, replayed.stdout

    def test_a_different_qualified_name_is_refused_and_writes_nothing(self, tmp_path: Path):
        renamed_path = tmp_path / 'renamed.jsonl.gz'
        new_path = tmp_path / 'new.jsonl.gz'
        write_recording_naming_logical_names(
            golden_path=fixture_path(game_key='mr_muncher'),
            path=renamed_path,
            renames={CURRENT_NAME: 'apps.mr_muncher.game:SomeOtherScene'},
        )

        rebaselined = rebaseline_recording_headless(
            console_script=CONSOLE_SCRIPT, path=renamed_path, new_path=new_path
        )

        assert rebaselined.returncode == ExitCode.UNUSABLE_INPUT, rebaselined.stdout
        assert not new_path.exists()
