"""Bitmappy's fonts (split from tests/fonts/test_font_manager.py; they move with Bitmappy)."""

import warnings

import pygame.sysfont
import pytest

from glitchygames.fonts import FontManager
from glitchygames.fonts.font_manager import DEFAULT_FONT_NAME


@pytest.fixture
def fontconfig_unavailable(mocker):
    """Make pygame's system font scan fail as it does on a machine without fontconfig.

    pygame warns "'fc-list' is missing, system fonts cannot be loaded on your platform" when
    the scan cannot run (and a similar warning when it times out under load). The scan runs on
    the first SysFont call, so the fixture marks it not yet done, empties the font tables it
    would fill, and replaces it with one that only warns.

    Args:
        mocker: The pytest-mock fixture.

    Returns:
        The replaced scan, to check whether anything asked for system fonts.

    """

    def scan_without_fontconfig() -> None:
        warnings.warn(
            "'fc-list' is missing, system fonts cannot be loaded on your platform",
            stacklevel=2,
        )

    mocker.patch.object(pygame.sysfont, 'is_init', new=False)
    mocker.patch.dict(pygame.sysfont.Sysfonts, {}, clear=True)
    mocker.patch.dict(pygame.sysfont.Sysalias, {}, clear=True)
    return mocker.patch.object(
        pygame.sysfont,
        'initsysfonts',
        side_effect=scan_without_fontconfig,
    )


class TestBitmappyFonts:
    """The Bitmappy editor draws its text with the bundled Vera, not system fonts."""

    def test_building_the_editor_scans_no_system_fonts(self, mocker, fontconfig_unavailable):
        """Its options and slider labels named 'arial' and 'Courier', so it scanned them.

        On a machine without fontconfig (or a busy one where the scan times out) the scan's
        warning failed every editor test (BUGS.md #156).
        """
        from bitmappy.controllers.manager import MultiControllerManager
        from bitmappy.editor import BitmapEditorScene

        mocker.patch.object(MultiControllerManager, '_instance', None)
        mocker.patch.dict(FontManager._font_cache, {}, clear=True)

        with warnings.catch_warnings():
            warnings.simplefilter('error')
            editor = BitmapEditorScene(options={})

        fontconfig_unavailable.assert_not_called()
        assert editor.options['font_name'] == DEFAULT_FONT_NAME
