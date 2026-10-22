"""Tests for glitchygames/fonts/font_manager.py.

Every test loads real fonts and renders onto real surfaces. The engine's default font is the
bundled Bitstream Vera, loaded from its file; only a font a game names goes through pygame's
system font lookup (SysFont). Tests that need a system font register one in pygame's own font
table (the fake_system_fonts fixture), so they never depend on the fonts this machine has.
"""

import argparse
import sys
import types
import warnings
from pathlib import Path

import pygame
import pygame.font
import pygame.freetype
import pygame.sysfont
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.fonts import FontManager
from glitchygames.fonts.font_manager import (
    BUNDLED_FONT_DIRECTORY,
    DEFAULT_FONT_NAME,
    bundled_font_path,
)
from glitchygames.ui import InputBox

# A system font name no machine has: the fake_system_fonts fixture registers it in pygame's
# system font table, pointing at the bundled bold Vera so the tests can tell it apart from the
# default (regular) Vera.
FAKE_SYSTEM_FONT_NAME = 'glitchytestsystemfont'
FAKE_SYSTEM_FONT_FILE = BUNDLED_FONT_DIRECTORY / 'VeraBd.ttf'
DEFAULT_FONT_FILE = BUNDLED_FONT_DIRECTORY / 'Vera.ttf'
SAMPLE_TEXT = 'Glitchy Games 123'


@pytest.fixture(autouse=True)
def font_manager_state():
    """Start and end every test with pygame's font modules up and FontManager's caches empty.

    Yields:
        None: Control to the test.

    """
    pygame.font.init()
    pygame.freetype.init()
    FontManager._font_cache.clear()
    FontManager.OPTIONS.clear()
    yield
    FontManager._font_cache.clear()
    FontManager.OPTIONS.clear()


@pytest.fixture
def fake_system_fonts(mocker):
    """Give pygame a system font table holding only FAKE_SYSTEM_FONT_NAME.

    pygame.sysfont scans the machine's fonts once (initsysfonts) and keeps them in Sysfonts and
    Sysalias. Marking the scan done and replacing both tables makes SysFont find exactly the
    fake font, whatever this machine has installed.

    Args:
        mocker: The pytest-mock fixture.

    """
    mocker.patch.object(pygame.sysfont, 'is_init', new=True)
    mocker.patch.dict(
        pygame.sysfont.Sysfonts,
        {FAKE_SYSTEM_FONT_NAME: {(False, False): str(FAKE_SYSTEM_FONT_FILE)}},
        clear=True,
    )
    mocker.patch.dict(pygame.sysfont.Sysalias, {}, clear=True)


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


def rendered_size(*, font_file: Path, size: int, text: str = SAMPLE_TEXT) -> tuple[int, int]:
    """Return the size of text rendered with pygame.font from a font file.

    Args:
        font_file: The font file.
        size: The point size.
        text: The text to measure.

    Returns:
        The rendered text's (width, height).

    """
    return pygame.font.Font(font_file, size).size(text)


class TestBundledFontPath:
    """bundled_font_path names the bundled Bitstream Vera files."""

    def test_the_default_font_name_is_the_bundled_vera(self):
        assert bundled_font_path(font_name=DEFAULT_FONT_NAME) == DEFAULT_FONT_FILE
        assert DEFAULT_FONT_FILE.is_file()

    @pytest.mark.parametrize(
        ('font_name', 'file_name'),
        [
            ('Vera', 'Vera.ttf'),
            ('VeraBd', 'VeraBd.ttf'),
            ('VeraIt', 'VeraIt.ttf'),
            ('VeraBI', 'VeraBI.ttf'),
            ('vera', 'Vera.ttf'),
            ('VERABD', 'VeraBd.ttf'),
        ],
    )
    def test_each_bundled_variant_is_nameable_in_any_case(self, font_name, file_name):
        font_path = bundled_font_path(font_name=font_name)

        assert font_path == BUNDLED_FONT_DIRECTORY / file_name
        assert font_path is not None
        assert font_path.is_file()

    @pytest.mark.parametrize('font_name', ['arial', 'Times', 'Courier', FAKE_SYSTEM_FONT_NAME])
    def test_other_names_are_not_bundled(self, font_name):
        assert bundled_font_path(font_name=font_name) is None


class TestDefaultFontWithoutFontconfig:
    """The default font loads from its file: no system font scan, so no warning (BUGS.md #156)."""

    @pytest.mark.parametrize('font_system', ['freetype', 'pygame'])
    def test_the_default_font_loads_without_a_system_font_scan(
        self, fontconfig_unavailable, font_system
    ):
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            loaded_font = FontManager.get_font(font_system=font_system, font_config={})

        fontconfig_unavailable.assert_not_called()
        if font_system == 'freetype':
            assert isinstance(loaded_font, pygame.freetype.Font)
            assert loaded_font.get_rect(SAMPLE_TEXT).width > 0
        else:
            assert isinstance(loaded_font, pygame.font.Font)
            assert loaded_font.size(SAMPLE_TEXT)[0] > 0

    def test_the_freetype_default_font_is_the_bundled_vera(self, fontconfig_unavailable):
        loaded_font = FontManager.font({})

        assert isinstance(loaded_font, pygame.freetype.Font)
        assert Path(loaded_font.path) == DEFAULT_FONT_FILE
        assert loaded_font.size == 14
        assert FontManager._font_cache[f'{DEFAULT_FONT_NAME}_14'] is loaded_font

    def test_the_pygame_default_font_is_the_bundled_vera(self, fontconfig_unavailable):
        loaded_font = FontManager.pygame_font({})

        assert isinstance(loaded_font, pygame.font.Font)
        assert loaded_font.size(SAMPLE_TEXT) == rendered_size(font_file=DEFAULT_FONT_FILE, size=14)
        assert FontManager._font_cache[f'pygame_{DEFAULT_FONT_NAME}_14'] is loaded_font

    def test_the_engine_options_default_font_is_the_bundled_vera(self, fontconfig_unavailable):
        parser = FontManager.args(argparse.ArgumentParser())
        engine_options = vars(parser.parse_args([]))
        FontManager(game=types.SimpleNamespace(OPTIONS=engine_options))

        with warnings.catch_warnings():
            warnings.simplefilter('error')
            loaded_font = FontManager.get_font()

        assert FontManager.OPTIONS['font_name'] == DEFAULT_FONT_NAME
        assert isinstance(loaded_font, pygame.freetype.Font)
        assert Path(loaded_font.path) == DEFAULT_FONT_FILE

    def test_a_bundled_variant_by_name_loads_its_file(self, fontconfig_unavailable):
        loaded_font = FontManager.font({'font_name': 'VeraBd', 'font_size': 20})

        fontconfig_unavailable.assert_not_called()
        assert Path(loaded_font.path) == BUNDLED_FONT_DIRECTORY / 'VeraBd.ttf'
        assert loaded_font.size == 20


class TestNamedSystemFont:
    """A font a game names that is not bundled still goes through pygame's SysFont."""

    def test_freetype_loads_a_named_system_font_through_sysfont(self, fake_system_fonts, mocker):
        system_font = mocker.spy(pygame.freetype, 'SysFont')

        loaded_font = FontManager.font({'font_name': FAKE_SYSTEM_FONT_NAME, 'font_size': 18})

        system_font.assert_called_once_with(name=FAKE_SYSTEM_FONT_NAME, size=18)
        assert isinstance(loaded_font, pygame.freetype.Font)
        assert Path(loaded_font.path) == FAKE_SYSTEM_FONT_FILE

    def test_pygame_loads_a_named_system_font_through_sysfont(self, fake_system_fonts, mocker):
        system_font = mocker.spy(pygame.font, 'SysFont')

        loaded_font = FontManager.pygame_font({'font_name': FAKE_SYSTEM_FONT_NAME, 'font_size': 18})

        system_font.assert_called_once_with(FAKE_SYSTEM_FONT_NAME, 18)
        assert isinstance(loaded_font, pygame.font.Font)
        assert loaded_font.size(SAMPLE_TEXT) == rendered_size(
            font_file=FAKE_SYSTEM_FONT_FILE, size=18
        )

    def test_a_named_system_font_without_fontconfig_warns(self, fontconfig_unavailable):
        """Naming a system font still asks the system: pygame's warnings are not hidden.

        Without fontconfig pygame warns that it cannot scan, then that the named font is missing.
        """
        with warnings.catch_warnings(record=True) as caught_warnings:
            warnings.simplefilter('always')
            FontManager.pygame_font({'font_name': 'arial', 'font_size': 14})

        fontconfig_unavailable.assert_called_once()
        messages = [str(caught_warning.message) for caught_warning in caught_warnings]
        assert any('system fonts cannot be loaded' in message for message in messages)
        assert any("The system font 'arial' couldn't be found" in message for message in messages)

    def test_pygame_font_without_a_size_uses_14(self, fake_system_fonts, mocker):
        """A configuration naming only the font gets the default size."""
        system_font = mocker.spy(pygame.font, 'SysFont')

        loaded_font = FontManager.pygame_font({'font_name': FAKE_SYSTEM_FONT_NAME})

        system_font.assert_called_once_with(FAKE_SYSTEM_FONT_NAME, 14)
        assert FontManager._font_cache[f'pygame_{FAKE_SYSTEM_FONT_NAME}_14'] is loaded_font


class TestFontCache:
    """Each font is loaded once per name and size."""

    @pytest.mark.parametrize('font_system', ['freetype', 'pygame'])
    def test_the_same_name_and_size_returns_the_cached_font(self, font_system, mocker):
        file_font = mocker.spy(pygame.freetype, 'Font')
        pygame_file_font = mocker.spy(pygame.font, 'Font')
        font_config = {'font_name': DEFAULT_FONT_NAME, 'font_size': 15}

        first_font = FontManager.get_font(font_system=font_system, font_config=dict(font_config))
        second_font = FontManager.get_font(font_system=font_system, font_config=dict(font_config))

        assert second_font is first_font
        assert file_font.call_count + pygame_file_font.call_count == 1

    def test_another_size_loads_another_font(self):
        small_font = FontManager.font({'font_name': DEFAULT_FONT_NAME, 'font_size': 10})
        large_font = FontManager.font({'font_name': DEFAULT_FONT_NAME, 'font_size': 30})

        assert small_font is not large_font
        assert small_font.size == 10
        assert large_font.size == 30

    def test_freetype_and_pygame_fonts_are_cached_apart(self):
        freetype_font = FontManager.get_font(font_system='freetype', font_config={})
        pygame_font = FontManager.get_font(font_system='pygame', font_config={})

        assert isinstance(freetype_font, pygame.freetype.Font)
        assert isinstance(pygame_font, pygame.font.Font)


class TestFontManagerGetFont:
    """FontManager.get_font chooses the font system."""

    def test_get_font_explicit_freetype(self):
        loaded_font = FontManager.get_font(font_system='freetype')

        assert isinstance(loaded_font, pygame.freetype.Font)

    def test_get_font_explicit_pygame(self):
        loaded_font = FontManager.get_font(font_system='pygame')

        assert isinstance(loaded_font, pygame.font.Font)

    def test_get_font_default_uses_options(self):
        FontManager.OPTIONS['use_freetype'] = False

        loaded_font = FontManager.get_font(font_system=None, font_config={'font_size': 22})

        assert isinstance(loaded_font, pygame.font.Font)
        assert loaded_font.size(SAMPLE_TEXT) == rendered_size(font_file=DEFAULT_FONT_FILE, size=22)

    def test_get_font_freetype_fallback_on_error(self, mocker):
        """When freetype cannot load the font, get_font falls back to pygame.font."""
        mocker.patch.object(pygame.freetype, 'Font', side_effect=OSError('unreadable font'))

        FontManager.OPTIONS['use_freetype'] = True
        loaded_font = FontManager.get_font(font_system=None, font_config={'font_size': 17})

        assert isinstance(loaded_font, pygame.font.Font)
        assert loaded_font.size(SAMPLE_TEXT) == rendered_size(font_file=DEFAULT_FONT_FILE, size=17)


class TestFontManagerSetGetFontSystem:
    """Test FontManager.set_font_system and get_font_system methods."""

    def test_set_font_system_freetype(self):
        """Test set_font_system with 'freetype'."""
        FontManager.set_font_system('freetype')
        assert FontManager.OPTIONS['use_freetype'] is True

    def test_set_font_system_pygame(self):
        """Test set_font_system with 'pygame'."""
        FontManager.set_font_system('pygame')
        assert FontManager.OPTIONS['use_freetype'] is False

    def test_get_font_system_freetype(self):
        """Test get_font_system returns 'freetype' when use_freetype is True."""
        FontManager.OPTIONS['use_freetype'] = True
        assert FontManager.get_font_system() == 'freetype'

    def test_get_font_system_pygame(self):
        """Test get_font_system returns 'pygame' when use_freetype is False."""
        FontManager.OPTIONS['use_freetype'] = False
        assert FontManager.get_font_system() == 'pygame'

    def test_get_font_system_default(self):
        """Test get_font_system returns 'pygame' when OPTIONS is empty."""
        assert FontManager.get_font_system() == 'pygame'


class TestFontManagerCompareFontSystems:
    """FontManager.compare_font_systems renders the same text with both systems."""

    def test_compare_font_systems_renders_with_both(self):
        comparison = FontManager.compare_font_systems(text='Test', size=55)

        assert comparison['pygame']['type'] == 'pygame.font.Font'
        assert comparison['freetype']['type'] == 'pygame.freetype.Font'
        assert isinstance(comparison['pygame']['font'], pygame.font.Font)
        assert isinstance(comparison['freetype']['font'], pygame.freetype.Font)
        for system in ('pygame', 'freetype'):
            surface = comparison[system]['surface']
            assert isinstance(surface, pygame.Surface)
            assert comparison[system]['size'] == surface.get_size()
            assert surface.get_width() > 0


class TestFontManagerPygameFontFallback:
    """FontManager.pygame_font falls back to pygame's own font when SysFont fails."""

    @pytest.mark.parametrize('system_font_error', [TypeError, FileNotFoundError])
    def test_pygame_font_fallback_to_default(self, mocker, system_font_error):
        real_font_class = pygame.font.Font
        mocker.patch.object(pygame.font, 'SysFont', side_effect=system_font_error('no font'))
        file_font = mocker.spy(pygame.font, 'Font')

        loaded_font = FontManager.pygame_font({'font_name': 'nonexistent_font', 'font_size': 16})

        file_font.assert_called_once_with(None, 16)
        assert isinstance(loaded_font, real_font_class)


class TestFontProxy:
    """FontManager.FontProxy forwards font events to the game."""

    def test_font_changed_event_reaches_the_game(self, mocker):
        game = mocker.Mock()
        proxy = FontManager.FontProxy(game=game)
        event = mocker.Mock(name='font_changed_event')

        proxy.on_font_changed_event(event)

        game.on_font_changed_event.assert_called_once_with(event)


class TestFontManagerInit:
    """FontManager copies the engine's font options."""

    @pytest.mark.parametrize(
        ('font_system', 'use_freetype'), [('freetype', True), ('pygame', False)]
    )
    def test_options_are_copied_from_the_game(self, font_system, use_freetype):
        parser = FontManager.args(argparse.ArgumentParser())
        engine_options = vars(
            parser.parse_args(['--font-name', 'courier', '--font-system', font_system])
        )

        manager = FontManager(game=types.SimpleNamespace(OPTIONS=engine_options))

        assert FontManager.OPTIONS['font_name'] == 'courier'
        assert FontManager.OPTIONS['font_size'] == 14
        assert FontManager.OPTIONS['use_freetype'] is use_freetype
        assert pygame.freetype in manager.proxies


class TestFontManagerBuiltInFallback:
    """The built-in fallback (used by PyInstaller-packaged games) loads the bundled Vera.ttf."""

    @pytest.mark.parametrize('system_font_error', [TypeError, FileNotFoundError])
    def test_fallback_loads_the_bundled_font(self, mocker, system_font_error):
        """When SysFont fails, a real freetype font is loaded from the bundled file."""
        mocker.patch.object(pygame.freetype, 'SysFont', side_effect=system_font_error('no font'))

        loaded_font = FontManager.font({'font_name': 'missing_font', 'font_size': 16})

        assert isinstance(loaded_font, pygame.freetype.Font)
        assert Path(loaded_font.path) == DEFAULT_FONT_FILE

    def test_fallback_keeps_the_requested_size(self, mocker):
        mocker.patch.object(pygame.freetype, 'SysFont', side_effect=TypeError('no font'))

        loaded_font = FontManager.font({'font_name': 'missing_font', 'font_size': 16})

        assert loaded_font.size == 16


class TestFontManagerArgs:
    """Test FontManager.args class method."""

    def test_args_adds_font_system_argument(self):
        """Test args method adds --font-system argument."""
        parser = argparse.ArgumentParser()
        result = FontManager.args(parser)
        assert result is parser

        # Parse with --font-system
        args = result.parse_args(['--font-system', 'pygame'])
        assert args.font_system == 'pygame'

        args = result.parse_args(['--font-system', 'freetype'])
        assert args.font_system == 'freetype'

    def test_args_adds_font_dpi_argument(self):
        """Test args method adds --font-dpi argument."""
        parser = argparse.ArgumentParser()
        result = FontManager.args(parser)

        args = result.parse_args(['--font-dpi', '96'])
        assert args.font_dpi == 96

    def test_font_name_defaults_to_the_bundled_vera(self):
        parser = FontManager.args(argparse.ArgumentParser())

        assert parser.parse_args([]).font_name == DEFAULT_FONT_NAME
        assert parser.parse_args(['--font-name', 'arial']).font_name == 'arial'


class TestInputBoxFont:
    """ui.inputs.InputBox draws its text with the bundled Vera, not a system font."""

    @pytest.fixture
    def display(self):
        """A real display surface (InputBox converts its image for the display).

        Returns:
            The display surface.

        """
        if not pygame.get_init():
            pygame.init()
        return pygame.display.set_mode((320, 240))

    def test_input_box_loads_no_system_font(self, display, fontconfig_unavailable):
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            input_box = InputBox(x=10, y=20, width=200, height=30, text=SAMPLE_TEXT)

        fontconfig_unavailable.assert_not_called()
        assert input_box.text_image.get_size() == rendered_size(
            font_file=DEFAULT_FONT_FILE, size=14
        )

    def test_input_box_font_comes_from_the_font_manager(self, display):
        input_box = InputBox(x=10, y=20, width=200, height=30)

        assert input_box.font is FontManager._font_cache[f'pygame_{DEFAULT_FONT_NAME}_14']
        assert isinstance(input_box.font, pygame.font.Font)


class TestBitmappyFonts:
    """The Bitmappy editor draws its text with the bundled Vera, not system fonts."""

    def test_building_the_editor_scans_no_system_fonts(self, mocker, fontconfig_unavailable):
        """Its options and slider labels named 'arial' and 'Courier', so it scanned them.

        On a machine without fontconfig (or a busy one where the scan times out) the scan's
        warning failed every editor test (BUGS.md #156).
        """
        from glitchygames.bitmappy.controllers.manager import MultiControllerManager
        from glitchygames.bitmappy.editor import BitmapEditorScene

        mocker.patch.object(MultiControllerManager, '_instance', None)
        mocker.patch.dict(FontManager._font_cache, {}, clear=True)

        with warnings.catch_warnings():
            warnings.simplefilter('error')
            editor = BitmapEditorScene(options={})

        fontconfig_unavailable.assert_not_called()
        assert editor.options['font_name'] == DEFAULT_FONT_NAME
