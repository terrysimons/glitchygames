"""Fixtures shared by the Bitmappy tool tests."""

import pytest

from bitmappy.editor import BitmapEditorScene


@pytest.fixture
def bitmap_editor(mocker) -> BitmapEditorScene:
    """Build a real Bitmappy editor on the real display, with a fresh controller manager.

    The editor starts with one animation of one blank 32x32 frame.

    Returns:
        The editor.

    """
    from bitmappy.controllers.manager import MultiControllerManager

    # The autouse conftest fixture already opened the real 800x600 display
    mocker.patch.object(MultiControllerManager, '_instance', None)
    return BitmapEditorScene(options={})
