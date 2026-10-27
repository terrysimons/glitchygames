"""Bitmappy moved out of the engine into src/apps/bitmappy: its scene and worker keep names."""

from __future__ import annotations

import importlib

from bitmappy.ai_worker import run_ai_worker_process
from bitmappy.editor import BitmapEditorScene
from glitchygames.logical_names import logical_name


def test_the_editor_is_named_in_the_apps_layer():
    """The editor's scene is named by the apps layer, from its own package."""
    assert logical_name(scene_class=BitmapEditorScene) == 'apps.bitmappy.editor:BitmapEditorScene'
    assert BitmapEditorScene.__module__ == 'bitmappy.editor'


def test_the_ai_worker_target_is_importable_by_name():
    """The AI worker process's target is found again by its module and name.

    The spawn start method (macOS, Windows) pickles the target by reference, and the child
    imports it by those two names, so they must name an importable function.
    """
    assert run_ai_worker_process.__module__ == 'bitmappy.ai_worker'
    module = importlib.import_module(run_ai_worker_process.__module__)

    assert getattr(module, run_ai_worker_process.__qualname__) is run_ai_worker_process
