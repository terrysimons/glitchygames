"""scripts/record_golden_traces.py loads a game only when it needs one.

Many engine tests import the golden-trace harness for its pieces (``GoldenTraceEngine``,
``GoldenTraceSceneManager``, ``command_line``) and run no game, so importing the script imports
no workspace member: ``GAME_SCENES`` holds each game's scene class by reference and imports it
the first time it is looked up (``GameSceneClasses``), and the input scripts import what they
read of a game where they read it.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from scripts.record_golden_traces import GameSceneClasses

from glitchygames.process import run_command
from glitchygames.scenes import Scene

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHILD_TIMEOUT_SECONDS = 60.0
# A child that imports the harness's scripts and prints every member package it then holds
IMPORTED_MEMBERS_PROGRAM = """
import json
import sys

import scripts.record_golden_traces
import scripts.record_scripted_session

from glitchygames.logical_names import MEMBER_LAYERS

loaded = {module.partition('.')[0] for module in sys.modules}
print(json.dumps(sorted(loaded & set(MEMBER_LAYERS))))
"""
# A child that looks up one game: only that game's member is imported
LOOKED_UP_GAME_PROGRAM = """
import json
import sys

from scripts.record_golden_traces import GAME_SCENES

from glitchygames.logical_names import MEMBER_LAYERS

scene_class = GAME_SCENES['clockwork_keep']
loaded = {module.partition('.')[0] for module in sys.modules}
print(json.dumps([scene_class.__name__, sorted(loaded & set(MEMBER_LAYERS))]))
"""
# A stand-in game module, written to tmp_path: its import is visible in sys.modules
STAND_IN_MODULE = 'stand_in_lazy_scene'
STAND_IN_SOURCE = """
from glitchygames.scenes import Scene


class LazyScene(Scene):
    pass
"""
STAND_IN_REFERENCE = f'{STAND_IN_MODULE}:LazyScene'


def run_child(*, program: str) -> object:
    """Run a Python program in a fresh interpreter from the repository; return its JSON line.

    Returns:
        The decoded last line it printed.

    """
    completed = run_command(
        command=[sys.executable, '-c', program],
        environment={**os.environ, 'SDL_VIDEODRIVER': 'dummy', 'SDL_AUDIODRIVER': 'dummy'},
        timeout_seconds=CHILD_TIMEOUT_SECONDS,
        capture_output=True,
        working_directory=PROJECT_ROOT,
    )
    assert completed.returncode == 0, completed.stdout
    return json.loads(completed.stdout.strip().splitlines()[-1])


def test_importing_the_harness_imports_no_member():
    """A fresh interpreter that imports the harness's scripts holds no member package."""
    assert run_child(program=IMPORTED_MEMBERS_PROGRAM) == []


def test_looking_up_a_game_imports_only_its_member():
    """GAME_SCENES['clockwork_keep'] imports Clockwork Keep, and nothing else of the members."""
    assert run_child(program=LOOKED_UP_GAME_PROGRAM) == [
        'ClockworkKeepScene',
        ['clockwork_keep'],
    ]


@pytest.fixture
def stand_in_module(tmp_path, monkeypatch):
    """Write the stand-in game module to tmp_path; forget it again afterwards.

    Yields:
        The module's name.

    """
    (tmp_path / f'{STAND_IN_MODULE}.py').write_text(STAND_IN_SOURCE, encoding='utf-8')
    monkeypatch.syspath_prepend(tmp_path)
    monkeypatch.delitem(sys.modules, STAND_IN_MODULE, raising=False)
    yield STAND_IN_MODULE
    sys.modules.pop(STAND_IN_MODULE, None)


@pytest.mark.usefixtures('stand_in_module')
def test_a_game_is_imported_when_it_is_first_looked_up():
    """Keys, length and membership import nothing; the lookup imports the class, once."""
    scenes = GameSceneClasses({'stand_in': STAND_IN_REFERENCE})

    assert list(scenes) == ['stand_in']
    assert len(scenes) == 1
    assert 'stand_in' in scenes
    assert 'other' not in scenes
    assert STAND_IN_MODULE not in sys.modules
    scene_class = scenes['stand_in']
    assert STAND_IN_MODULE in sys.modules
    assert scene_class.__name__ == 'LazyScene'
    assert issubclass(scene_class, Scene)
    assert scenes['stand_in'] is scene_class


def test_a_reference_that_is_not_a_scene_class_is_refused():
    """A reference to anything but a Scene subclass fails at its lookup, naming it."""
    scenes = GameSceneClasses({'not_a_scene': 'glitchygames.scenes:SceneManager'})

    with pytest.raises(TypeError, match=r"'glitchygames\.scenes:SceneManager' is not a Scene"):
        scenes['not_a_scene']


@pytest.mark.usefixtures('stand_in_module')
def test_patching_registers_a_stand_in_and_restores_without_importing(mocker):
    """mocker.patch.dict (register_stand_in_game) adds and removes a key: nothing is imported.

    Its copy, clear and update keep the other games as references, so a test that registers a
    stand-in game imports no game at all.
    """
    scenes = GameSceneClasses({'stand_in': STAND_IN_REFERENCE})

    class RegisteredScene(Scene):
        pass

    mocker.patch.dict(scenes, {'registered': RegisteredScene})
    assert scenes['registered'] is RegisteredScene
    assert sorted(scenes) == ['registered', 'stand_in']
    mocker.stopall()

    assert list(scenes) == ['stand_in']
    assert STAND_IN_MODULE not in sys.modules


@pytest.mark.usefixtures('stand_in_module')
def test_a_copy_keeps_references_and_resolved_classes_apart():
    """A copy is a new mapping: deleting from it leaves the original."""
    scenes = GameSceneClasses({'stand_in': STAND_IN_REFERENCE})
    copied = scenes.copy()

    del copied['stand_in']

    assert list(scenes) == ['stand_in']
    assert list(copied) == []
    assert STAND_IN_MODULE not in sys.modules
