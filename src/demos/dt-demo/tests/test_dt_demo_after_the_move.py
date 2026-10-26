"""The dt demo moved out of glitchygames/examples: the first member of the demos layer."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import runpy
from pathlib import Path
from typing import TYPE_CHECKING

import dt_demo
from dt_demo import Game
from glitchygames.logical_names import logical_name

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_the_demo_is_named_in_the_demos_layer():
    """Game stays defined in the package itself, so its logical name is demos.dt_demo:Game."""
    assert logical_name(scene_class=Game) == 'demos.dt_demo:Game'
    assert Game.__module__ == 'dt_demo'


def test_the_old_example_module_is_gone():
    """Nothing is left in glitchygames/examples to import (a stale __pycache__ would be)."""
    assert importlib.util.find_spec('glitchygames.examples') is None


def test_the_dt_demo_console_script_runs_the_demos_main():
    """The ``dt-demo`` console script's entry point is the package's ``main``."""
    (entry_point,) = importlib.metadata.entry_points(group='console_scripts', name='dt-demo')

    assert entry_point.value == 'dt_demo:main'
    assert entry_point.load() is dt_demo.main


def test_python_dash_m_dt_demo_runs_the_demos_main(mocker: MockerFixture):
    """The old ``python -m glitchygames.examples.dt_demo`` is ``python -m dt_demo`` now.

    The package's ``__main__`` runs as ``__main__`` (as ``python -m`` runs it), with ``main``
    replaced, so no game starts.
    """
    main = mocker.patch.object(dt_demo, 'main')

    runpy.run_module('dt_demo', run_name='__main__')

    main.assert_called_once_with()


def test_dt_demo_is_imported_from_its_src_directory():
    """The dt demo's package is under its member's src/ (or site-packages in a wheel install)."""
    member_source_directory = Path(__file__).resolve().parents[1] / 'src'
    package_directory = Path(dt_demo.__file__).resolve().parent

    assert (
        package_directory.parent == member_source_directory
        or 'site-packages' in package_directory.parts
    ), f'{package_directory} is not under {member_source_directory} or site-packages'
