"""The text input demo moved out of glitchygames/examples into its own member of the demos layer."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import runpy
from pathlib import Path
from typing import TYPE_CHECKING

import text_input_demo
from glitchygames.logical_names import logical_name
from text_input_demo import Game

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_the_demo_is_named_in_the_demos_layer():
    """Game stays defined in the package itself: its logical name is demos.text_input_demo:Game."""
    assert logical_name(scene_class=Game) == 'demos.text_input_demo:Game'
    assert Game.__module__ == 'text_input_demo'


def test_the_old_example_module_is_gone():
    """Nothing is left in glitchygames/examples to import (a stale __pycache__ would be)."""
    assert importlib.util.find_spec('glitchygames.examples.text_input_demo') is None


def test_the_text_input_demo_console_script_runs_the_demos_main():
    """The ``text-input-demo`` console script's entry point is the package's ``main``."""
    (entry_point,) = importlib.metadata.entry_points(
        group='console_scripts', name='text-input-demo'
    )

    assert entry_point.value == 'text_input_demo:main'
    assert entry_point.load() is text_input_demo.main


def test_python_dash_m_text_input_demo_runs_the_demos_main(mocker: MockerFixture):
    """``python -m glitchygames.examples.text_input_demo`` is ``python -m text_input_demo`` now.

    The package's ``__main__`` runs as ``__main__`` (as ``python -m`` runs it), with ``main``
    replaced, so no game starts.
    """
    main = mocker.patch.object(text_input_demo, 'main')

    runpy.run_module('text_input_demo', run_name='__main__')

    main.assert_called_once_with()


def test_text_input_demo_is_imported_from_its_src_directory():
    """The text input demo's package is under its member's src/ (or site-packages in a wheel)."""
    member_source_directory = Path(__file__).resolve().parents[1] / 'src'
    package_directory = Path(text_input_demo.__file__).resolve().parent

    assert (
        package_directory.parent == member_source_directory
        or 'site-packages' in package_directory.parts
    ), f'{package_directory} is not under {member_source_directory} or site-packages'
