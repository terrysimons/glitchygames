"""The text input demo's console script and ``python -m text_input_demo`` both run its ``main``."""

from __future__ import annotations

import importlib.metadata
import runpy
from typing import TYPE_CHECKING

import text_input_demo

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


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
