"""The Sound Board demo's console script and ``python -m sound_board_demo`` both run its main."""

from __future__ import annotations

import importlib.metadata
import runpy
from typing import TYPE_CHECKING

import sound_board_demo

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def test_the_sound_board_demo_console_script_runs_the_demos_main():
    """The ``sound-board-demo`` console script's entry point is the package's ``main``."""
    (entry_point,) = importlib.metadata.entry_points(
        group='console_scripts', name='sound-board-demo'
    )

    assert entry_point.value == 'sound_board_demo:main'
    assert entry_point.load() is sound_board_demo.main


def test_python_dash_m_sound_board_demo_runs_the_demos_main(mocker: MockerFixture):
    """``python -m sound_board_demo`` runs the package's ``__main__`` with ``main`` replaced."""
    main = mocker.patch.object(sound_board_demo, 'main')

    runpy.run_module('sound_board_demo', run_name='__main__')

    main.assert_called_once_with()
