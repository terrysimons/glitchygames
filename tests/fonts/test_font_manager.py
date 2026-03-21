"""Coverage tests for glitchygames/fonts/font_manager.py.

This module targets uncovered areas of FontManager including:
- get_font method with different font_system values
- set_font_system method
- get_font_system method
- compare_font_systems method
- pygame_font cache hit
- font method with FileNotFoundError fallback
- get_font with freetype fallback on error
"""

import argparse
import sys
from pathlib import Path

import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.fonts import FontManager


class TestFontManagerGetFont:
    """Test FontManager.get_font method branches."""

    @pytest.fixture(autouse=True)
    def clear_caches(self):
        """Clear font caches before each test."""
        FontManager._font_cache.clear()
        FontManager.OPTIONS.clear()
        yield
        FontManager._font_cache.clear()
        FontManager.OPTIONS.clear()

    def test_get_font_explicit_freetype(self, mocker):
        """Test get_font with explicit freetype system calls font()."""
        mock_font = mocker.Mock()
        mocker.patch('pygame.freetype.SysFont', return_value=mock_font)

        result = FontManager.get_font(font_system='freetype')
        assert result == mock_font

    def test_get_font_explicit_pygame(self, mocker):
        """Test get_font with explicit pygame system calls pygame_font()."""
        mock_font = mocker.Mock()
        mocker.patch('pygame.font.SysFont', return_value=mock_font)

        config = {'font_name': 'uniquefont_pg', 'font_size': 99}
        result = FontManager.get_font(font_system='pygame', font_config=config)
        assert result == mock_font

    def test_get_font_default_uses_options(self, mocker):
        """Test get_font with None font_system uses OPTIONS default."""
        FontManager.OPTIONS['use_freetype'] = False
        mock_font = mocker.Mock()
        mocker.patch('pygame.font.SysFont', return_value=mock_font)

        config = {'font_name': 'uniquefont_opt', 'font_size': 88}
        result = FontManager.get_font(font_system=None, font_config=config)
        assert result == mock_font

    def test_get_font_freetype_fallback_on_error(self, mocker):
        """Test get_font falls back to pygame when freetype fails."""
        mocker.patch('pygame.freetype.SysFont', side_effect=TypeError('no freetype'))
        mocker.patch('pygame.freetype.Font', side_effect=OSError('no font'))
        mock_pygame_font = mocker.Mock()
        mocker.patch('pygame.font.SysFont', return_value=mock_pygame_font)

        FontManager.OPTIONS['use_freetype'] = True
        config = {'font_name': 'uniquefont_fb', 'font_size': 77}
        result = FontManager.get_font(font_system=None, font_config=config)
        assert result == mock_pygame_font

    def test_get_font_with_custom_config(self, mocker):
        """Test get_font passes custom font_config."""
        mock_font = mocker.Mock()
        mocker.patch('pygame.font.SysFont', return_value=mock_font)

        config = {'font_name': 'uniquefont_cc', 'font_size': 66}
        result = FontManager.get_font(font_system='pygame', font_config=config)
        assert result == mock_font


class TestFontManagerSetGetFontSystem:
    """Test FontManager.set_font_system and get_font_system methods."""

    @pytest.fixture(autouse=True)
    def clear_caches(self):
        """Clear font caches before each test."""
        FontManager._font_cache.clear()
        FontManager.OPTIONS.clear()
        yield
        FontManager._font_cache.clear()
        FontManager.OPTIONS.clear()

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
    """Test FontManager.compare_font_systems method."""

    @pytest.fixture(autouse=True)
    def clear_caches(self):
        """Clear font caches before each test."""
        FontManager._font_cache.clear()
        FontManager.OPTIONS.clear()
        yield
        FontManager._font_cache.clear()
        FontManager.OPTIONS.clear()

    def test_compare_font_systems_returns_dict(self, mocker):
        """Test compare_font_systems returns a dict with both systems."""
        mock_pygame_font = mocker.Mock()
        mock_surface = mocker.Mock()
        mock_surface.get_size.return_value = (100, 24)
        mock_pygame_font.render.return_value = mock_surface
        mocker.patch('pygame.font.SysFont', return_value=mock_pygame_font)

        mock_ft_font = mocker.Mock()
        # freetype render returns (surface, rect) tuple
        mock_ft_surface = mocker.Mock()
        mock_ft_surface.get_size.return_value = (100, 24)
        mock_ft_font.render.return_value = (mock_ft_surface, mocker.Mock())
        mock_ft_font.render_to = mocker.Mock()
        mocker.patch('pygame.freetype.SysFont', return_value=mock_ft_font)

        result = FontManager.compare_font_systems(text='Test', size=55)
        assert 'pygame' in result
        assert 'freetype' in result
        assert result['pygame']['type'] == 'pygame.font.Font'
        assert result['freetype']['type'] == 'pygame.freetype.Font'
        assert 'font' in result['pygame']
        assert 'surface' in result['pygame']
        assert 'size' in result['pygame']


class TestFontManagerPygameFontCacheHit:
    """Test FontManager.pygame_font cache hit behavior."""

    @pytest.fixture(autouse=True)
    def clear_caches(self):
        """Clear font caches before each test."""
        FontManager._font_cache.clear()
        FontManager.OPTIONS.clear()
        yield
        FontManager._font_cache.clear()
        FontManager.OPTIONS.clear()

    def test_pygame_font_cache_hit(self, mock_pygame_patches, mocker):
        """Test pygame_font returns cached font on cache hit."""
        mock_cached_font = mocker.Mock()
        FontManager._font_cache['pygame_arial_14'] = mock_cached_font

        config = {'font_name': 'arial', 'font_size': 14}
        result = FontManager.pygame_font(config)
        assert result == mock_cached_font

    def test_pygame_font_fallback_to_default(self, mock_pygame_patches, mocker):
        """Test pygame_font falls back to Font(None, size) on error."""
        mock_font = mocker.Mock()
        mocker.patch('pygame.font.SysFont', side_effect=TypeError('font not found'))
        mocker.patch('pygame.font.Font', return_value=mock_font)

        config = {'font_name': 'nonexistent_font', 'font_size': 16}
        result = FontManager.pygame_font(config)
        assert result == mock_font


class TestFontManagerFontMethodBranches:
    """Test FontManager.font method additional branches."""

    @pytest.fixture(autouse=True)
    def clear_caches(self):
        """Clear font caches before each test."""
        FontManager._font_cache.clear()
        FontManager.OPTIONS.clear()
        yield
        FontManager._font_cache.clear()
        FontManager.OPTIONS.clear()

    def test_font_method_file_not_found_fallback(self, mock_pygame_patches, mocker):
        """Test font method falls back to built-in on FileNotFoundError."""
        mock_font = mocker.Mock()
        mocker.patch('pygame.freetype.SysFont', side_effect=FileNotFoundError('no font'))
        mocker.patch('pygame.freetype.Font', return_value=mock_font)

        config = {'font_name': 'missing_font', 'font_size': 16}
        result = FontManager.font(config)
        assert result == mock_font

    def test_font_method_empty_config_uses_defaults(self, mock_pygame_patches, mocker):
        """Test font method provides default config values when empty dict passed."""
        mock_font = mocker.Mock()
        mocker.patch('pygame.freetype.SysFont', return_value=mock_font)

        result = FontManager.font({})
        assert result == mock_font
        # Should have used default font_name 'arial' and font_size 14
        assert 'arial_14' in FontManager._font_cache


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
