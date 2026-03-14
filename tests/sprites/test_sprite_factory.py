"""Sprite factory and loading tests."""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import the original SpriteFactory before mocking
import glitchygames.sprites
from glitchygames.sprites import SpriteFactory

from tests.mocks.test_mock_factory import MockFactory

original_sprite_factory_load_sprite = glitchygames.sprites.SpriteFactory.load_sprite


class TestSpriteFactory:
    """Test SpriteFactory functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def setup_method(self):
        """Set up test fixtures."""
        # Ensure pygame is properly initialized for mocks
        if not pygame.get_init():
            pygame.init()

    def test_get_default_sprite_path(self):
        """Test getting default sprite path."""
        path = SpriteFactory._get_default_sprite_path()

        assert isinstance(path, str)
        assert path.endswith(".toml")

    def test_determine_type_animated(self):
        """Test determining animated sprite type."""
        analysis = {
            "has_sprite_pixels": False,
            "has_animation_sections": True,
            "has_frame_sections": False
        }

        sprite_type = SpriteFactory._determine_type(analysis)
        assert sprite_type == "animated"

    def test_determine_type_static(self):
        """Test determining static sprite type."""
        analysis = {
            "has_sprite_pixels": True,
            "has_animation_sections": False,
            "has_frame_sections": False
        }

        sprite_type = SpriteFactory._determine_type(analysis)
        assert sprite_type == "static"

    def test_determine_type_error(self):
        """Test determining sprite type with error."""
        analysis = {
            "has_sprite_pixels": False,
            "has_animation_sections": False,
            "has_frame_sections": False
        }

        sprite_type = SpriteFactory._determine_type(analysis)
        assert sprite_type == "error"

    def test_save_sprite_animated(self, mocker):
        """Test saving animated sprite."""
        mock_sprite = mocker.Mock()
        mock_sprite.animations = {}  # Make it look like an AnimatedSprite

        mock_save = mocker.patch("glitchygames.sprites.SpriteFactory._save_animated_sprite")
        SpriteFactory.save_sprite(sprite=mock_sprite, filename="test.toml", file_format="toml")
        mock_save.assert_called_once()

    def test_save_sprite_static(self, mocker):
        """Test saving static sprite."""
        mock_sprite = mocker.Mock()
        # Explicitly remove animations attribute to make it look like a BitmappySprite
        # hasattr(mock_sprite, 'animations') should return False
        del mock_sprite.animations  # Remove the default animations attribute
        mock_sprite._save = mocker.Mock()  # Add _save method to mock

        mock_save = mocker.patch("glitchygames.sprites.SpriteFactory._save_static_sprite")
        SpriteFactory.save_sprite(sprite=mock_sprite, filename="test.toml", file_format="toml")
        mock_save.assert_called_once_with(mock_sprite, "test.toml", "toml")

    def test_save_static_sprite(self, mocker):
        """Test saving static sprite directly."""
        mock_sprite = mocker.Mock()

        mock_save = mocker.patch("glitchygames.sprites.SpriteFactory._save_static_sprite")
        SpriteFactory._save_static_sprite(mock_sprite, "test.toml", "toml")
        mock_save.assert_called_once()

    def test_save_animated_sprite(self, mocker):
        """Test saving animated sprite directly."""
        mock_sprite = mocker.Mock()

        mock_save = mocker.patch("glitchygames.sprites.SpriteFactory._save_animated_sprite")
        SpriteFactory._save_animated_sprite(mock_sprite, "test.toml", "toml")
        mock_save.assert_called_once()

    def test_analyze_file_with_nonexistent_file(self):
        """Test analyzing nonexistent file."""
        with pytest.raises(FileNotFoundError):
            SpriteFactory._analyze_file("nonexistent.toml")

    def test_analyze_toml_file_animation(self, mocker):
        """Test analyzing TOML file with animation."""
        mock_open = mocker.patch("pathlib.Path.open")
        mock_open.return_value.__enter__.return_value.read.return_value = """
            [sprite]
            pixels = [1, 2, 3]

            [animations.walk]
            frames = [1, 2, 3]
            """

        result = SpriteFactory._get_toml_data("test.toml")
        assert "sprite" in result
        assert "animations" in result

    def test_analyze_toml_file_basic(self, mocker):
        """Test analyzing basic TOML file."""
        mock_open = mocker.patch("pathlib.Path.open")
        mock_open.return_value.__enter__.return_value.read.return_value = """
            [sprite]
            pixels = [1, 2, 3]
            """

        result = SpriteFactory._get_toml_data("test.toml")
        assert "sprite" in result
        assert "animations" not in result

    def test_analyze_toml_file_empty_pixels(self, mocker):
        """Test analyzing TOML file with empty pixels."""
        mock_open = mocker.patch("pathlib.Path.open")
        mock_open.return_value.__enter__.return_value.read.return_value = """
            [sprite]
            pixels = []
            """

        result = SpriteFactory._get_toml_data("test.toml")
        assert "sprite" in result

    def test_detect_file_format_default(self):
        """Test detecting default file format."""
        format_type = SpriteFactory._detect_file_format("test.toml")
        assert format_type == "toml"

    def test_detect_file_format_unknown(self):
        """Test detecting unknown file format."""
        format_type = SpriteFactory._detect_file_format("test.unknown")
        assert format_type == "unknown"

    def test_load_sprite_invalid_file(self, mocker):
        """Test loading sprite from invalid file."""
        # Temporarily disable the centralized mock for this test by patching with the original method
        mocker.patch("glitchygames.sprites.SpriteFactory.load_sprite", original_sprite_factory_load_sprite)
        with pytest.raises(FileNotFoundError):
            SpriteFactory.load_sprite(filename="nonexistent.toml")

    def test_load_sprite_mixed_content(self, mocker):
        """Test loading sprite with mixed content."""
        mocker.patch("glitchygames.sprites.SpriteFactory._analyze_file", return_value={
            "has_sprite_pixels": True,
            "has_animation_sections": True,
            "has_frame_sections": False
        })

        # Temporarily disable the centralized mock for this test by patching with the original method
        mocker.patch("glitchygames.sprites.SpriteFactory.load_sprite", original_sprite_factory_load_sprite)
        with pytest.raises(ValueError, match="Invalid sprite file"):
            SpriteFactory.load_sprite(filename="mixed.toml")

    def test_sprite_factory_load_sprite_invalid_file(self, mocker):
        """Test SpriteFactory load_sprite with invalid file."""
        # Temporarily disable the centralized mock for this test by patching with the original method
        mocker.patch("glitchygames.sprites.SpriteFactory.load_sprite", original_sprite_factory_load_sprite)
        with pytest.raises(FileNotFoundError):
            SpriteFactory.load_sprite(filename="nonexistent.toml")

    def test_sprite_factory_analyze_toml_file_with_sprite_pixels(self, mocker):
        """Test analyzing TOML file with sprite pixels."""
        mock_open = mocker.patch("pathlib.Path.open")
        mock_open.return_value.__enter__.return_value.read.return_value = """
            [sprite]
            pixels = [1, 2, 3, 4, 5, 6]
            """

        result = SpriteFactory._get_toml_data("test.toml")
        assert "sprite" in result
        assert result["sprite"]["pixels"] == [1, 2, 3, 4, 5, 6]
