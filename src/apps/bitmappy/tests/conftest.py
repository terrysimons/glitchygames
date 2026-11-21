"""Fixtures shared by the Bitmappy tool tests."""

import pytest

from bitmappy import constants, onion_skinning
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


@pytest.fixture(autouse=True)
def fresh_onion_skinning_manager(mocker) -> None:
    """Give every test an onion skinning manager in its startup state.

    The manager is process-wide (``onion_skinning.onion_skinning_manager``, reached only through
    ``get_onion_skinning_manager()``), so a test that switches a frame on would otherwise leave it
    on for the next test on the same worker. Code covered only through that leftover state had
    coverage that followed the test order
    (bugs/2026-11-20-onion-skin-indicator-covered-only-by-leaked-state.md). The patch gives the
    test a new manager and puts the earlier one back after it.
    """
    mocker.patch.object(
        onion_skinning, 'onion_skinning_manager', onion_skinning.OnionSkinningManager()
    )


@pytest.fixture(autouse=True)
def fresh_ai_training_state(mocker) -> None:
    """Give every test the AI training state's startup values: no examples, no format.

    The state is a process-wide dict (``constants.ai_training_state``) that
    ``load_ai_training_data()`` appends to and sets the format of, so a test would otherwise see
    what an earlier test loaded. The patch empties it for the test and puts the earlier contents
    back after it (``clear=True``: only the startup keys, whatever a test added).
    """
    mocker.patch.dict(constants.ai_training_state, {'data': [], 'format': None}, clear=True)


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
