"""The game's tests run on its own display size: 800x480, as the game runs by default.

A seeded test that fails (by an assertion or any exception) reports its seed and where to save
it (tests/regressed_seeds.py; the owner's rule, 2026-11-15).
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

import pygame
import pytest

from glitchygames.display_mode import set_display_mode

if TYPE_CHECKING:
    from collections.abc import Generator

regressed_seeds = importlib.import_module(
    'src.games.zombies-aint-my-neighbors.tests.regressed_seeds'
)

SCREEN_SIZE = (800, 480)


@pytest.fixture(autouse=True)
def display():
    """The game's display: 800x480."""
    if not pygame.get_init():
        pygame.init()
    surface = pygame.display.get_surface()
    if surface is None or surface.get_size() != SCREEN_SIZE:
        set_display_mode(size=SCREEN_SIZE)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    """Add a failed seeded test's seed, and where to save it, to its report."""
    report = yield
    note = regressed_seeds.seed_report(item)
    if report.failed and note is not None:
        report.sections.append(('regressed seed', note))
    del call
    return report
