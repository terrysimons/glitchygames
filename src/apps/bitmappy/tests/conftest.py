"""Fixtures shared by the Bitmappy tool tests."""

import pytest

from bitmappy.controllers.manager import MultiControllerManager
from bitmappy.editor import BitmapEditorScene


@pytest.fixture(autouse=True)
def fresh_controller_manager(mocker) -> None:
    """Give every test its own MultiControllerManager (BUGS.md #234).

    The manager is a process-wide singleton (``_instance``), so a test that connects controllers
    (the benchmarks connect four) would otherwise leave them for the next test on the same
    worker. The patch drops the instance for the test and puts the earlier one back after it.
    """
    mocker.patch.object(MultiControllerManager, '_instance', None)


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
