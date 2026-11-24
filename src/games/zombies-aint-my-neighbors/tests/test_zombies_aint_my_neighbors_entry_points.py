"""The game's console script and ``python -m zombies_aint_my_neighbors`` both run its main."""

from __future__ import annotations

import importlib
import importlib.metadata
from typing import TYPE_CHECKING

import zombies_aint_my_neighbors
from glitchygames.testing.entry_points import run_package_as_main

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_the_console_script_runs_the_games_main():
    """The ``zombies-aint-my-neighbors`` console script's entry point is the package's ``main``."""
    (entry_point,) = importlib.metadata.entry_points(
        group='console_scripts', name='zombies-aint-my-neighbors'
    )

    assert entry_point.value == 'zombies_aint_my_neighbors:main'
    assert entry_point.load() is zombies_aint_my_neighbors.main


def test_python_dash_m_runs_the_games_main(mocker: MockerFixture):
    """``python -m zombies_aint_my_neighbors`` runs the package's ``__main__``."""
    main = mocker.patch.object(zombies_aint_my_neighbors, 'main')

    run_package_as_main(package='zombies_aint_my_neighbors')

    main.assert_called_once_with()


def test_python_dash_m_runs_the_games_main_after_its_main_was_imported(mocker: MockerFixture):
    """An earlier import of ``__main__`` (a walk of the package's modules) can't break the run.

    runpy warns when the package's ``__main__`` is already in sys.modules, and the suite makes
    the warning an error: the scene-name test's walk imported it first under a shuffled order
    (CircleCI job 4458, seed 4083822362), which the files' fixed order never ran.
    """
    importlib.import_module('zombies_aint_my_neighbors.__main__')
    main = mocker.patch.object(zombies_aint_my_neighbors, 'main')

    run_package_as_main(package='zombies_aint_my_neighbors')

    main.assert_called_once_with()
