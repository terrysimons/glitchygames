"""The joystick demo moved out of glitchygames/examples into its own member of the demos layer."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import runpy
from pathlib import Path
from typing import TYPE_CHECKING

import joystick_demo
from glitchygames.logical_names import logical_name
from joystick_demo import Game

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_the_demo_is_named_in_the_demos_layer():
    """Game stays defined in the package itself, so its logical name is demos.joystick_demo:Game."""
    assert logical_name(scene_class=Game) == 'demos.joystick_demo:Game'
    assert Game.__module__ == 'joystick_demo'


def test_the_old_example_module_is_gone():
    """Nothing is left in glitchygames/examples to import (a stale __pycache__ would be)."""
    assert importlib.util.find_spec('glitchygames.examples') is None


def test_the_joystick_demo_console_script_runs_the_demos_main():
    """The ``joystick-demo`` console script's entry point is the package's ``main``."""
    (entry_point,) = importlib.metadata.entry_points(group='console_scripts', name='joystick-demo')

    assert entry_point.value == 'joystick_demo:main'
    assert entry_point.load() is joystick_demo.main


def test_python_dash_m_joystick_demo_runs_the_demos_main(mocker: MockerFixture):
    """The old ``python -m glitchygames.examples.joystick_demo`` is ``python -m joystick_demo`` now.

    The package's ``__main__`` runs as ``__main__`` (as ``python -m`` runs it), with ``main``
    replaced, so no game starts.
    """
    main = mocker.patch.object(joystick_demo, 'main')

    runpy.run_module('joystick_demo', run_name='__main__')

    main.assert_called_once_with()


def test_joystick_demo_is_imported_from_its_src_directory():
    """The joystick demo's package is under its member's src/ (or site-packages in a wheel)."""
    member_source_directory = Path(__file__).resolve().parents[1] / 'src'
    package_directory = Path(joystick_demo.__file__).resolve().parent

    assert (
        package_directory.parent == member_source_directory
        or 'site-packages' in package_directory.parts
    ), f'{package_directory} is not under {member_source_directory} or site-packages'
