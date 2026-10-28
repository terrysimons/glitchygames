"""PaddleSlap's ``python -m paddleslap`` runs its ``main``."""

from __future__ import annotations

import importlib

import paddleslap


def test_python_dash_m_paddleslap_runs_the_games_main():
    """The old ``python -m glitchygames.examples.paddleslap`` is ``python -m paddleslap`` now."""
    package_main = importlib.import_module('paddleslap.__main__')

    assert package_main.main is paddleslap.main
