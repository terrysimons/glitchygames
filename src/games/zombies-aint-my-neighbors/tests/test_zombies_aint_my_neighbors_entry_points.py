"""The game's console script and ``python -m zombies_aint_my_neighbors`` both run its main."""

from __future__ import annotations

import importlib.metadata
import runpy
from typing import TYPE_CHECKING

import zombies_aint_my_neighbors

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

    runpy.run_module('zombies_aint_my_neighbors', run_name='__main__')

    main.assert_called_once_with()
