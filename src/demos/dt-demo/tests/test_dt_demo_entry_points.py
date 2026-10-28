"""The dt demo's console script and ``python -m dt_demo`` both run its ``main``."""

from __future__ import annotations

import importlib.metadata
import runpy
from typing import TYPE_CHECKING

import dt_demo

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


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
