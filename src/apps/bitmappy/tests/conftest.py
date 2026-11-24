"""Fixtures shared by the Bitmappy tool tests."""

from typing import TYPE_CHECKING

import pytest

from bitmappy import onion_skinning, training_library
from bitmappy.controllers.manager import MultiControllerManager
from bitmappy.editor import BitmapEditorScene
from glitchygames.engine_context import default_context

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(autouse=True)
def fresh_controller_manager(mocker) -> None:
    """Give every test its own MultiControllerManager (BUGS.md #234).

    The manager is a process-wide singleton (``_instance``), so a test that connects controllers
    (the benchmarks connect four) would otherwise leave them for the next test on the same
    worker. The patch drops the instance for the test and puts the earlier one back after it.
    """
    mocker.patch.object(MultiControllerManager, '_instance', None)


@pytest.fixture(autouse=True)
def fresh_onion_skinning_manager() -> Generator[None]:
    """Give every test a new onion skinning manager, and drop it after the test.

    The manager is the default engine context's (``onion_skinning.ONION_SKINNING_MANAGER_SLOT``),
    and every test runs in the default context, so a test that switches a frame on would otherwise
    leave it on for the next test on the same worker. Code covered only through that leftover
    state had coverage that followed the test order
    (bugs/2026-11-20-onion-skin-indicator-covered-only-by-leaked-state.md). The engine's own slots
    are reset by tests/harness.py; the engine never imports a member, so a member resets its own.
    """
    default_context().reset_value(slot=onion_skinning.ONION_SKINNING_MANAGER_SLOT)
    yield
    default_context().reset_value(slot=onion_skinning.ONION_SKINNING_MANAGER_SLOT)


@pytest.fixture(autouse=True)
def fresh_ai_training_library(mocker) -> None:
    """Give every test the training library's startup state: none installed, readers see it empty.

    The library is installed once per process by ``load_ai_training_data()`` and a later load is
    ignored (bitmappy.training_library), so without this a test would read whatever an earlier
    test loaded. The patch drops it for the test and puts the earlier one back after it.
    """
    mocker.patch.object(training_library._INSTALLED, 'library', None)  # pyright: ignore[reportPrivateUsage]


@pytest.fixture
def bitmap_editor() -> BitmapEditorScene:
    """Build a real Bitmappy editor on the real display, with a fresh controller manager.

    The editor starts with one animation of one blank 32x32 frame. The controller manager is
    fresh because of ``fresh_controller_manager`` (autouse).

    Returns:
        The editor.

    """
    # The autouse conftest fixture already opened the real 800x600 display
    return BitmapEditorScene(options={})
