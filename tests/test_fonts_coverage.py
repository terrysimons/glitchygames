"""Test coverage for the fonts module."""

import argparse
from unittest.mock import Mock, patch

import pygame
from glitchygames.fonts import FontManager


class TestFontManagerCoverage:
    """Test coverage for FontManager class."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock game object with required options
        self.mock_game = Mock()
        self.mock_game.OPTIONS = {
            "font_name": "arial",
            "font_size": 14,
            "font_bold": False,
            "font_italic": False,
            "font_antialias": True,
            "font_dpi": 72,
            "font_system": "freetype"
        }

        # Clear any existing cache
        FontManager._font_cache.clear()
        FontManager.OPTIONS.clear()

    def test_font_manager_initialization(self):
        """Test FontManager initialization."""
        self.setUp()

        expected_font_size = 14

        with patch("pygame.freetype.init") as mock_init, \
             patch("pygame.freetype.get_cache_size", return_value=100), \
             patch("pygame.freetype.get_default_resolution", return_value=72):

            FontManager(self.mock_game)

            mock_init.assert_called_once()
            assert FontManager.OPTIONS["font_name"] == "arial"
            assert FontManager.OPTIONS["font_size"] == expected_font_size
            assert FontManager.OPTIONS["use_freetype"] is True

    def test_font_proxy_initialization(self):
        """Test FontProxy initialization."""
        self.setUp()

        # Create a concrete subclass that implements the abstract method
        class ConcreteFontProxy(FontManager.FontProxy):
            def on_font_changed_event(self, event):
                pass

        with patch("pygame.freetype.init"):
            FontManager(self.mock_game)
            proxy = ConcreteFontProxy(self.mock_game)

            assert proxy.game == self.mock_game
            assert pygame.freetype in proxy.proxies

    def test_font_method_freetype_success(self):
        """Test font method with successful freetype loading."""
        self.setUp()

        mock_font = Mock()
        with patch("pygame.freetype.SysFont", return_value=mock_font) as mock_sysfont:

            font_config = {"font_name": "arial", "font_size": 16}
            result = FontManager.font(font_config)

            mock_sysfont.assert_called_once_with(name="arial", size=16)
            assert result == mock_font
            assert "arial_16" in FontManager._font_cache

    def test_font_method_freetype_fallback(self):
        """Test font method with freetype fallback to built-in font."""
        self.setUp()

        mock_font = Mock()
        with patch("pygame.freetype.SysFont", side_effect=TypeError("Font not found")), \
             patch("pygame.freetype.Font", return_value=mock_font) as mock_font_class, \
             patch("pathlib.Path") as mock_path:

            mock_path.return_value.parent = Mock()
            mock_path.return_value.parent.__truediv__ = Mock(return_value="path/to/font.ttf")

            font_config = {"font_name": "arial", "font_size": 16}
            result = FontManager.font(font_config)

            mock_font_class.assert_called_once()
            assert result == mock_font

    def test_pygame_font_method_success(self):
        """Test pygame_font method with successful loading."""
        self.setUp()

        mock_font = Mock()
        with patch("pygame.font.SysFont", return_value=mock_font) as mock_sysfont:

            font_config = {"font_name": "arial", "font_size": 16}
            result = FontManager.pygame_font(font_config)

            mock_sysfont.assert_called_once_with("arial", 16)
            assert result == mock_font
            assert "pygame_arial_16" in FontManager._font_cache

    def test_pygame_font_method_fallback(self):
        """Test pygame_font method with fallback to default font."""
        self.setUp()

        mock_font = Mock()
        with patch("pygame.font.SysFont", side_effect=TypeError("Font not found")), \
             patch("pygame.font.Font", return_value=mock_font) as mock_font_class:

            font_config = {"font_name": "arial", "font_size": 16}
            result = FontManager.pygame_font(font_config)

            mock_font_class.assert_called_once_with(None, 16)
            assert result == mock_font

    def test_pygame_font_method_default_config(self):
        """Test pygame_font method with default configuration."""
        self.setUp()

        mock_font = Mock()
        with patch("pygame.font.SysFont", return_value=mock_font):

            # Test with no font_config
            result = FontManager.pygame_font()

            assert result == mock_font
            assert "pygame_arial_14" in FontManager._font_cache

    def test_get_font_method_freetype_success(self):
        """Test get_font method with freetype success."""
        self.setUp()

        mock_font = Mock()
        with patch.object(FontManager, "font", return_value=mock_font) as mock_font_method:

            result = FontManager.get_font("freetype")

            mock_font_method.assert_called_once()
            assert result == mock_font

    def test_get_font_method_pygame_success(self):
        """Test get_font method with pygame success."""
        self.setUp()

        mock_font = Mock()
        with patch.object(FontManager, "pygame_font", return_value=mock_font) as mock_pygame_font:

            result = FontManager.get_font("pygame")

            mock_pygame_font.assert_called_once()
            assert result == mock_font

    def test_get_font_method_freetype_fallback(self):
        """Test get_font method with freetype fallback to pygame."""
        self.setUp()

        mock_font = Mock()
        with patch.object(FontManager, "font", side_effect=OSError("Freetype failed")), \
             patch.object(FontManager, "pygame_font", return_value=mock_font) as mock_pygame_font:

            result = FontManager.get_font("freetype")

            mock_pygame_font.assert_called_once()
            assert result == mock_font

    def test_get_font_method_default_system(self):
        """Test get_font method with default system."""
        self.setUp()

        mock_font = Mock()
        FontManager.OPTIONS["use_freetype"] = True
        with patch.object(FontManager, "font", return_value=mock_font) as mock_font_method:

            result = FontManager.get_font()

            mock_font_method.assert_called_once()
            assert result == mock_font

    def test_set_font_system_method(self):
        """Test set_font_system method."""
        self.setUp()

        FontManager.set_font_system("pygame")
        assert FontManager.OPTIONS["use_freetype"] is False

        FontManager.set_font_system("freetype")
        assert FontManager.OPTIONS["use_freetype"] is True

    def test_get_font_system_method(self):
        """Test get_font_system method."""
        self.setUp()

        FontManager.OPTIONS["use_freetype"] = True
        assert FontManager.get_font_system() == "freetype"

        FontManager.OPTIONS["use_freetype"] = False
        assert FontManager.get_font_system() == "pygame"

        # Test default case
        FontManager.OPTIONS.clear()
        assert FontManager.get_font_system() == "pygame"

    def test_compare_font_systems_method(self):
        """Test compare_font_systems method."""
        self.setUp()

        mock_pygame_font = Mock()
        mock_freetype_font = Mock()
        mock_pygame_surface = Mock()
        mock_freetype_surface = Mock()

        mock_pygame_surface.get_size.return_value = (100, 20)
        mock_freetype_surface.get_size.return_value = (120, 24)

        # Mock the render methods directly on the font objects
        mock_pygame_font.render.return_value = mock_pygame_surface
        mock_freetype_font.render.return_value = (mock_freetype_surface, None)

        with patch.object(FontManager, "get_font") as mock_get_font:
            mock_get_font.side_effect = [mock_pygame_font, mock_freetype_font]

            result = FontManager.compare_font_systems("Test", 24)

            assert "pygame" in result
            assert "freetype" in result
            assert result["pygame"]["font"] == mock_pygame_font
            assert result["freetype"]["font"] == mock_freetype_font
            assert result["pygame"]["size"] == (100, 20)
            assert result["freetype"]["size"] == (120, 24)

    def test_font_cache_behavior(self):
        """Test font caching behavior."""
        self.setUp()

        mock_font = Mock()
        with patch("pygame.font.SysFont", return_value=mock_font):

            # First call should create and cache
            result1 = FontManager.pygame_font({"font_name": "arial", "font_size": 16})
            assert result1 == mock_font
            assert "pygame_arial_16" in FontManager._font_cache

            # Second call should return cached font
            result2 = FontManager.pygame_font({"font_name": "arial", "font_size": 16})
            assert result2 == mock_font
            assert result1 is result2  # Same object from cache

    def test_font_config_defaults(self):
        """Test font configuration defaults."""
        self.setUp()

        mock_font = Mock()
        with patch("pygame.font.SysFont", return_value=mock_font):

            # Test with minimal config
            result = FontManager.pygame_font({"font_name": "arial"})

            assert result == mock_font
            # Should use default size of 14
            assert "pygame_arial_14" in FontManager._font_cache

    def test_font_method_with_none_config(self):
        """Test font method with None configuration."""
        self.setUp()

        # Set up OPTIONS
        FontManager.OPTIONS = {
            "font_name": "arial",
            "font_size": 16
        }

        mock_font = Mock()
        with patch("pygame.freetype.SysFont", return_value=mock_font):

            result = FontManager.font(None)

            assert result == mock_font
            assert "arial_16" in FontManager._font_cache

    def test_pygame_font_method_with_none_config(self):
        """Test pygame_font method with None configuration."""
        self.setUp()

        # Set up OPTIONS
        FontManager.OPTIONS = {
            "font_name": "arial",
            "font_size": 16
        }

        mock_font = Mock()
        with patch("pygame.font.SysFont", return_value=mock_font):

            result = FontManager.pygame_font(None)

            assert result == mock_font
            assert "pygame_arial_16" in FontManager._font_cache

    def test_args_method(self):  # noqa: PLR6301
        """Test args class method."""
        parser = argparse.ArgumentParser()
        result = FontManager.args(parser)

        assert result is parser
        # Check that the Font Options group was added
        group_titles = [group.title for group in parser._action_groups]
        assert "Font Options" in group_titles

    def test_font_method_with_default_config(self):
        """Test font method with default configuration."""
        self.setUp()

        # Set up OPTIONS
        FontManager.OPTIONS = {
            "font_name": "arial",
            "font_size": 16
        }

        mock_font = Mock()
        with patch("pygame.freetype.SysFont", return_value=mock_font):

            result = FontManager.font()

            assert result == mock_font
            assert "arial_16" in FontManager._font_cache

    def test_font_method_with_partial_config(self):
        """Test font method with partial configuration."""
        self.setUp()

        # Set up OPTIONS
        FontManager.OPTIONS = {
            "font_name": "arial",
            "font_size": 16
        }

        mock_font = Mock()
        with patch("pygame.freetype.SysFont", return_value=mock_font):

            # Test with partial config (missing font_size)
            result = FontManager.font({"font_name": "times"})

            assert result == mock_font
            assert "times_14" in FontManager._font_cache  # Should use default size

    def test_pygame_font_method_with_partial_config(self):
        """Test pygame_font method with partial configuration."""
        self.setUp()

        # Set up OPTIONS
        FontManager.OPTIONS = {
            "font_name": "arial",
            "font_size": 16
        }

        mock_font = Mock()
        with patch("pygame.font.SysFont", return_value=mock_font):

            # Test with partial config (missing font_size)
            result = FontManager.pygame_font({"font_name": "times"})

            assert result == mock_font
            assert "pygame_times_14" in FontManager._font_cache  # Should use default size


class TestFontsFinalCoverage:
    """Test coverage for final missing lines in fonts module."""

    def test_font_method_with_missing_font_name_config(self):  # noqa: PLR6301
        """Test font method with missing font_name in config."""
        # Create config without font_name to trigger line 189
        config = {"font_size": 16}

        with patch("pygame.freetype.SysFont") as mock_sysfont:
            mock_font = Mock()
            mock_sysfont.return_value = mock_font

            FontManager.font(config)

            # Verify that font_name was set to default "arial"
            assert config["font_name"] == "arial"
            font_size = 16
            assert config["font_size"] == font_size
            mock_sysfont.assert_called_once()

    def test_font_method_cache_hit(self):  # noqa: PLR6301
        """Test font method cache hit to cover line 198."""
        # Pre-populate cache
        cache_key = "arial_14"
        mock_cached_font = Mock()
        FontManager._font_cache[cache_key] = mock_cached_font

        config = {"font_name": "arial", "font_size": 14}

        result = FontManager.font(config)

        # Verify cache hit
        assert result == mock_cached_font

    def test_type_checking_import_coverage(self):  # noqa: PLR6301
        """Test TYPE_CHECKING import coverage."""
        # This test covers the TYPE_CHECKING import by reloading the module
        import sys  # noqa: PLC0415, F401
        import types  # noqa: PLC0415, F401
        import typing  # noqa: PLC0415
        from importlib import reload  # noqa: PLC0415

        import glitchygames.fonts  # noqa: PLC0415

        # Save original state
        original_type_checking = typing.TYPE_CHECKING

        try:
            # Temporarily set TYPE_CHECKING to True
            typing.TYPE_CHECKING = True
            # Reload the module to re-execute the TYPE_CHECKING block
            reload(glitchygames.fonts)

            # If we get here without error, the TYPE_CHECKING block executed
            assert True

        finally:
            # Restore original state
            typing.TYPE_CHECKING = original_type_checking
            # Reload the module again to ensure it's back to its original runtime state
            reload(glitchygames.fonts)
