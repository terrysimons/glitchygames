"""Tests for bitmappy tool functionality and coverage."""

import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pygame
import pytest

from glitchygames.bitmappy import editor as bitmappy
from glitchygames.bitmappy.ai_worker import (
    _check_ollama_model_status,
    _configure_client_timeouts,
    _configure_ollama_provider,
    _configure_provider_client_timeout,
    _create_ollama_config,
    _get_provider_timeout_value,
    _initialize_ai_client,
    _set_ollama_env_timeout,
    run_ai_worker,
)
from glitchygames.bitmappy.alpha import parse_toml_sprite_data
from glitchygames.bitmappy.constants import ai_training_state
from glitchygames.bitmappy.models import AIRequest
from glitchygames.bitmappy.pixel_sprite import BitmapPixelSprite
from glitchygames.bitmappy.scroll_arrow import ScrollArrowSprite
from glitchygames.bitmappy.sprite_inspection import (
    _get_sprite_color_count,
    _pixels_have_alpha,
    _process_config_file,
    _sprite_has_per_pixel_alpha,
    load_ai_training_data,
)
from glitchygames.bitmappy.utils import detect_file_format, resource_path
from tests.mocks import MockFactory

LOG = logging.getLogger('test.bitmappy_coverage')


class TestBitmappyFunctionality:
    """Test bitmappy module functionality."""

    @pytest.mark.skip(reason='Not yet implemented')
    def test_bitmappy_classes_exist(self, mock_pygame_patches):
        """Test that bitmappy classes exist."""
        # Test that main classes are available
        assert hasattr(bitmappy, 'BitmapPixelSprite')
        assert hasattr(bitmappy, 'FilmStripSprite')
        assert hasattr(bitmappy, 'AnimatedCanvasSprite')
        assert hasattr(bitmappy, 'MiniView')
        assert hasattr(bitmappy, 'BitmapEditorScene')

        # Test that classes are callable
        assert callable(bitmappy.BitmapPixelSprite)
        assert callable(bitmappy.FilmStripSprite)
        assert callable(bitmappy.AnimatedCanvasSprite)
        assert callable(bitmappy.MiniView)  # type: ignore[unresolved-attribute]
        assert callable(bitmappy.BitmapEditorScene)

    def test_bitmappy_exceptions(self, mock_pygame_patches):
        """Test bitmappy exception classes.

        Raises:
            GGUnhandledMenuItemError: Raised intentionally to test the exception class.

        """
        from glitchygames.bitmappy.models import GGUnhandledMenuItemError

        # Test exception can be raised
        with pytest.raises(GGUnhandledMenuItemError):
            raise GGUnhandledMenuItemError('Test error')

    def test_bitmappy_ai_classes(self, mock_pygame_patches):
        """Test bitmappy AI classes."""
        from glitchygames.bitmappy.models import AIRequest, AIResponse

        assert callable(AIRequest)
        assert callable(AIResponse)

    @pytest.mark.skip(reason='Not yet implemented')
    def test_bitmappy_sprite_inheritance(self, mock_pygame_patches):
        """Test bitmappy sprite inheritance."""
        # Test that sprite classes exist and are callable
        assert callable(bitmappy.BitmapPixelSprite)  # type: ignore[unresolved-attribute]
        assert callable(bitmappy.FilmStripSprite)  # type: ignore[unresolved-attribute]
        assert callable(bitmappy.AnimatedCanvasSprite)  # type: ignore[unresolved-attribute]
        assert callable(bitmappy.MiniView)  # type: ignore[unresolved-attribute]

    def test_bitmappy_scene_inheritance(self, mock_pygame_patches):
        """Test bitmappy scene inheritance."""
        # Test that BitmapEditorScene exists and is callable
        assert callable(bitmappy.BitmapEditorScene)

    def test_bitmappy_module_imports(self, mock_pygame_patches):
        """Test bitmappy module imports."""
        # Test that bitmappy module exists and has expected attributes
        assert hasattr(bitmappy, '__file__')
        assert hasattr(bitmappy, '__name__')
        assert bitmappy.__name__ == 'glitchygames.bitmappy.editor'

    def test_bitmappy_module_structure(self, mock_pygame_patches):
        """Test bitmappy module structure."""
        # Test that module has expected attributes
        assert hasattr(bitmappy, '__file__')
        assert hasattr(bitmappy, '__name__')
        assert bitmappy.__name__ == 'glitchygames.bitmappy.editor'


@pytest.fixture(autouse=True)
def clear_pixel_cache():
    """Clear the BitmapPixelSprite PIXEL_CACHE before and after each test."""
    BitmapPixelSprite.PIXEL_CACHE.clear()
    yield
    BitmapPixelSprite.PIXEL_CACHE.clear()


@pytest.fixture
def pygame_mocks(mocker):
    """Set up pygame mocks for sprite tests."""
    return MockFactory.setup_pygame_mocks_with_mocker(mocker)


@pytest.fixture
def mock_groups():
    """Create a mock LayeredDirty group for sprite initialization."""
    return pygame.sprite.LayeredDirty()


@pytest.fixture
def mock_logger():
    """Create a logger for testing AI-related functions."""
    return logging.getLogger('test.ai_functions')


# ---------------------------------------------------------------------------
# TestSpriteHasPerPixelAlpha
# ---------------------------------------------------------------------------


class TestSpriteHasPerPixelAlpha:
    """Tests for _sprite_has_per_pixel_alpha function."""

    def test_no_animations_attribute(self):
        """Sprite without _animations returns False."""
        sprite = object()
        assert _sprite_has_per_pixel_alpha(sprite) is False  # type: ignore[invalid-argument-type]

    def test_empty_animations(self):
        """Sprite with empty _animations returns False."""
        sprite = MagicMock()
        sprite._animations = {}
        assert _sprite_has_per_pixel_alpha(sprite) is False

    def test_rgb_pixels_only(self):
        """All RGB pixels (no alpha component) should return False."""
        frame = MagicMock()
        frame.get_pixel_data.return_value = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        sprite = MagicMock()
        sprite._animations = {'idle': [frame]}
        assert _sprite_has_per_pixel_alpha(sprite) is False

    def test_rgba_pixels_all_opaque(self):
        """All RGBA pixels with alpha=255 should return False."""
        frame = MagicMock()
        frame.get_pixel_data.return_value = [
            (255, 0, 0, 255),
            (0, 255, 0, 255),
            (0, 0, 255, 255),
        ]
        sprite = MagicMock()
        sprite._animations = {'idle': [frame]}
        assert _sprite_has_per_pixel_alpha(sprite) is False

    def test_rgba_pixel_with_non_opaque_alpha(self):
        """RGBA pixel with alpha != 255 should return True."""
        frame = MagicMock()
        frame.get_pixel_data.return_value = [
            (255, 0, 0, 255),
            (0, 255, 0, 128),
            (0, 0, 255, 255),
        ]
        sprite = MagicMock()
        sprite._animations = {'idle': [frame]}
        assert _sprite_has_per_pixel_alpha(sprite) is True

    def test_alpha_zero_detected(self):
        """RGBA pixel with alpha=0 (fully transparent) should return True."""
        frame = MagicMock()
        frame.get_pixel_data.return_value = [(0, 0, 0, 0)]
        sprite = MagicMock()
        sprite._animations = {'default': [frame]}
        assert _sprite_has_per_pixel_alpha(sprite) is True

    def test_multiple_animations_second_has_alpha(self):
        """Alpha in a second animation should still be detected."""
        frame_opaque = MagicMock()
        frame_opaque.get_pixel_data.return_value = [(255, 0, 0, 255)]
        frame_transparent = MagicMock()
        frame_transparent.get_pixel_data.return_value = [(0, 0, 0, 100)]
        sprite = MagicMock()
        sprite._animations = {'idle': [frame_opaque], 'walk': [frame_transparent]}
        assert _sprite_has_per_pixel_alpha(sprite) is True

    def test_multiple_frames_last_has_alpha(self):
        """Alpha in a later frame should still be detected."""
        frame1 = MagicMock()
        frame1.get_pixel_data.return_value = [(255, 0, 0, 255)]
        frame2 = MagicMock()
        frame2.get_pixel_data.return_value = [(0, 0, 0, 50)]
        sprite = MagicMock()
        sprite._animations = {'idle': [frame1, frame2]}
        assert _sprite_has_per_pixel_alpha(sprite) is True


# ---------------------------------------------------------------------------
# TestPixelsHaveAlpha
# ---------------------------------------------------------------------------


class TestPixelsHaveAlpha:
    """Tests for _pixels_have_alpha function."""

    def test_empty_pixel_list(self):
        """Empty list returns False."""
        assert _pixels_have_alpha([]) is False

    def test_rgb_pixels_no_alpha(self):
        """RGB-only pixels return False."""
        pixels = cast('list[tuple[int, ...]]', [(255, 0, 0), (0, 255, 0)])
        assert _pixels_have_alpha(pixels) is False

    def test_rgba_all_opaque(self):
        """All-opaque RGBA pixels return False."""
        pixels = cast('list[tuple[int, ...]]', [(255, 0, 0, 255), (0, 255, 0, 255)])
        assert _pixels_have_alpha(pixels) is False

    def test_rgba_with_transparency(self):
        """Non-opaque RGBA pixel returns True."""
        pixels = cast('list[tuple[int, ...]]', [(255, 0, 0, 255), (0, 255, 0, 127)])
        assert _pixels_have_alpha(pixels) is True

    def test_single_fully_transparent_pixel(self):
        """Single pixel with alpha=0 returns True."""
        pixels = cast('list[tuple[int, ...]]', [(0, 0, 0, 0)])
        assert _pixels_have_alpha(pixels) is True

    def test_mixed_rgb_and_rgba(self):
        """Mix of RGB and RGBA pixels, only RGBA checked for alpha."""
        pixels = cast('list[tuple[int, ...]]', [(255, 0, 0), (0, 0, 0, 200)])
        assert _pixels_have_alpha(pixels) is True

    def test_alpha_254_detected(self):
        """Alpha=254 (just below opaque) returns True."""
        pixels = cast('list[tuple[int, ...]]', [(100, 100, 100, 254)])
        assert _pixels_have_alpha(pixels) is True


# ---------------------------------------------------------------------------
# TestGetSpriteColorCount
# ---------------------------------------------------------------------------


class TestGetSpriteColorCount:
    """Tests for _get_sprite_color_count function."""

    def test_no_color_map_attributes(self):
        """Sprite with neither color_map nor _color_map returns 0."""
        sprite = object()
        assert _get_sprite_color_count(sprite) == 0  # type: ignore[invalid-argument-type]

    def test_color_map_attribute(self):
        """Sprite with color_map returns its length."""
        sprite = MagicMock()
        sprite.color_map = {'#': (0, 0, 0), '.': (255, 255, 255), 'X': (255, 0, 0)}
        # Remove _color_map so hasattr check for color_map comes first
        del sprite._color_map
        assert _get_sprite_color_count(sprite) == 3

    def test_private_color_map_attribute(self):
        """Sprite with _color_map (no public) returns its length."""
        sprite = MagicMock(spec=[])
        sprite._color_map = {'a': (0, 0, 0), 'b': (255, 255, 255)}
        assert _get_sprite_color_count(sprite) == 2

    def test_empty_color_map(self):
        """Empty color_map returns 0."""
        sprite = MagicMock()
        sprite.color_map = {}
        del sprite._color_map
        assert _get_sprite_color_count(sprite) == 0

    def test_color_map_preferred_over_private(self):
        """color_map is checked before _color_map."""
        sprite = MagicMock()
        sprite.color_map = {'#': (0, 0, 0)}
        sprite._color_map = {'a': (0, 0, 0), 'b': (1, 1, 1)}
        assert _get_sprite_color_count(sprite) == 1


# ---------------------------------------------------------------------------
# TestDetectFileFormat
# ---------------------------------------------------------------------------


class TestDetectFileFormat:
    """Tests for detect_file_format function."""

    def test_toml_extension(self):
        """TOML files return 'toml'."""
        assert detect_file_format('sprite.toml') == 'toml'

    def test_toml_extension_uppercase(self):
        """TOML extension is case-insensitive."""
        assert detect_file_format('SPRITE.TOML') == 'toml'

    def test_no_extension(self):
        """File with no extension defaults to 'toml'."""
        assert detect_file_format('spritefile') == 'toml'

    def test_unsupported_extension_raises(self):
        """Unsupported file extension raises ValueError."""
        with pytest.raises(ValueError, match='Unsupported file format'):
            detect_file_format('sprite.yaml')

    def test_unsupported_ini_raises(self):
        """INI extension (removed support) raises ValueError."""
        with pytest.raises(ValueError, match='Unsupported file format'):
            detect_file_format('sprite.ini')

    def test_unsupported_json_raises(self):
        """JSON extension raises ValueError."""
        with pytest.raises(ValueError, match='Unsupported file format'):
            detect_file_format('sprite.json')

    def test_toml_with_path(self):
        """Full path with .toml extension works."""
        assert detect_file_format('/some/path/to/sprite.toml') == 'toml'

    def test_empty_extension_after_dot(self):
        """File ending with dot has empty extension, defaults to toml."""
        # Path('.test.').suffix returns '' so this should default to 'toml'
        assert detect_file_format('myfile.') == 'toml'


# ---------------------------------------------------------------------------
# TestResourcePath
# ---------------------------------------------------------------------------


class TestResourcePath:
    """Tests for resource_path function."""

    def test_returns_path_object(self):
        """Should return a Path instance."""
        result = resource_path('glitchygames', 'assets', 'test.png')
        assert isinstance(result, Path)

    def test_normal_environment_strips_first_segment(self):
        """In normal mode (no _MEIPASS), first segment is stripped."""
        result = resource_path('glitchygames', 'assets', 'test.png')
        # Should contain assets/test.png in the path
        assert 'assets' in str(result)
        assert str(result).endswith('test.png')

    def test_pyinstaller_environment(self, mocker, tmp_path):
        """In PyInstaller mode, _MEIPASS is used as base path."""
        bundle_path = str(tmp_path / 'pyinstaller_bundle')
        mocker.patch.object(sys, '_MEIPASS', bundle_path, create=True)
        result = resource_path('glitchygames', 'assets', 'test.png')
        assert str(result).startswith(bundle_path)

    def test_single_segment(self):
        """Single path segment still works."""
        result = resource_path('file.txt')
        assert isinstance(result, Path)


# ---------------------------------------------------------------------------
# TestParseTomlSpriteData
# ---------------------------------------------------------------------------


class TestParseTomlSpriteData:
    """Tests for parse_toml_sprite_data function."""

    def test_parse_static_sprite(self):
        """Parses a simple static sprite TOML file."""
        toml_content = b"""
[sprite]
name = "test"
pixels = \"\"\"
##
##
\"\"\"

[colors."#"]
red = 0
green = 0
blue = 0
"""
        with tempfile.NamedTemporaryFile(suffix='.toml', delete=False) as temp_file:
            temp_file.write(toml_content)
            temp_file.flush()
            _config_data, sprite_data = parse_toml_sprite_data(Path(temp_file.name))

        assert sprite_data['name'] == 'test'
        assert sprite_data['sprite_type'] == 'static'
        assert 'pixels' in sprite_data
        Path(temp_file.name).unlink()

    def test_parse_animated_sprite(self):
        """Parses a TOML file with animation data."""
        toml_content = b"""
[sprite]
name = "animated_test"

[[animation]]
namespace = "idle"

[[animation.frame]]
pixels = \"\"\"
##
##
\"\"\"
"""
        with tempfile.NamedTemporaryFile(suffix='.toml', delete=False) as temp_file:
            temp_file.write(toml_content)
            temp_file.flush()
            _config_data, sprite_data = parse_toml_sprite_data(Path(temp_file.name))

        assert sprite_data['name'] == 'animated_test'
        assert sprite_data['sprite_type'] == 'animated'
        assert 'animations' in sprite_data
        Path(temp_file.name).unlink()

    def test_parse_sprite_with_alpha(self):
        """Detects alpha channel in TOML sprite data."""
        toml_content = b"""
[sprite]
name = "alpha_test"
pixels = \"\"\"
#.
.#
\"\"\"

[colors."#"]
red = 255
green = 0
blue = 0
alpha = 128

[colors."."]
red = 0
green = 0
blue = 0
"""
        with tempfile.NamedTemporaryFile(suffix='.toml', delete=False) as temp_file:
            temp_file.write(toml_content)
            temp_file.flush()
            _config_data, sprite_data = parse_toml_sprite_data(Path(temp_file.name))

        assert sprite_data['has_alpha'] is True
        Path(temp_file.name).unlink()

    def test_parse_missing_sprite_section(self):
        """TOML without [sprite] section still parses."""
        toml_content = b"""
[colors."#"]
red = 0
green = 0
blue = 0
"""
        with tempfile.NamedTemporaryFile(suffix='.toml', delete=False) as temp_file:
            temp_file.write(toml_content)
            temp_file.flush()
            _config_data, sprite_data = parse_toml_sprite_data(Path(temp_file.name))

        assert sprite_data['name'] == 'Unknown'
        assert sprite_data['sprite_type'] == 'static'
        Path(temp_file.name).unlink()

    def test_parse_nonexistent_file_raises(self):
        """Non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            parse_toml_sprite_data(Path('/nonexistent/file.toml'))


# ---------------------------------------------------------------------------
# TestProcessConfigFile
# ---------------------------------------------------------------------------


class TestProcessConfigFile:
    """Tests for _process_config_file function."""

    def test_unsupported_format_skipped(self, mocker):
        """Non-TOML format is skipped with a warning."""
        original_format = ai_training_state['format']
        ai_training_state['format'] = 'yaml'
        training_data = []
        _process_config_file(Path('/dummy/file.toml'), training_data)
        assert len(training_data) == 0
        ai_training_state['format'] = original_format

    def test_file_not_found_handled(self):
        """Missing file is handled gracefully."""
        original_format = ai_training_state['format']
        ai_training_state['format'] = 'toml'
        training_data = []
        _process_config_file(Path('/nonexistent/sprite.toml'), training_data)
        assert len(training_data) == 0
        ai_training_state['format'] = original_format

    def test_valid_toml_file_appended(self, mocker):
        """Valid TOML file gets added to training_data."""
        original_format = ai_training_state['format']
        ai_training_state['format'] = 'toml'
        toml_content = b"""
[sprite]
name = "training_test"
pixels = \"\"\"
##
##
\"\"\"

[colors."#"]
red = 0
green = 0
blue = 0
"""
        with tempfile.NamedTemporaryFile(suffix='.toml', delete=False) as temp_file:
            temp_file.write(toml_content)
            temp_file.flush()
            training_data = []
            # Mock SpriteFactory.load_sprite to avoid full sprite loading
            mocker.patch(
                'glitchygames.bitmappy.sprite_inspection.SpriteFactory.load_sprite',
                side_effect=ValueError('mocked'),
            )
            _process_config_file(Path(temp_file.name), training_data)

        assert len(training_data) == 1
        assert training_data[0]['name'] == 'training_test'
        ai_training_state['format'] = original_format
        Path(temp_file.name).unlink()


# ---------------------------------------------------------------------------
# TestLoadAiTrainingData
# ---------------------------------------------------------------------------


class TestLoadAiTrainingData:
    """Tests for load_ai_training_data function."""

    def test_non_list_data_raises_type_error(self):
        """Raises TypeError when data is not a list."""
        original_data = ai_training_state['data']
        ai_training_state['data'] = 'not_a_list'
        with pytest.raises(TypeError, match='must be a list'):
            load_ai_training_data()
        ai_training_state['data'] = original_data

    def test_missing_directory_handled(self, mocker):
        """Missing sprite config directory is handled gracefully."""
        original_data = ai_training_state['data']
        ai_training_state['data'] = []
        mocker.patch(
            'glitchygames.bitmappy.sprite_inspection.SPRITE_CONFIG_DIR',
            Path('/nonexistent/directory'),
        )
        load_ai_training_data()
        # Should not crash, data remains empty
        assert isinstance(ai_training_state['data'], list)
        ai_training_state['data'] = original_data

    def test_empty_directory_no_files(self, mocker):
        """Empty directory produces no training data."""
        original_data = ai_training_state['data']
        ai_training_state['data'] = []
        with tempfile.TemporaryDirectory() as temp_dir:
            mocker.patch(
                'glitchygames.bitmappy.sprite_inspection.SPRITE_CONFIG_DIR',
                Path(temp_dir),
            )
            load_ai_training_data()
        assert len(ai_training_state['data']) == 0
        ai_training_state['data'] = original_data


# ---------------------------------------------------------------------------
# TestCheckOllamaModelStatus
# ---------------------------------------------------------------------------


class TestCheckOllamaModelStatus:
    """Tests for _check_ollama_model_status function."""

    def test_non_ollama_model(self, mock_logger):
        """Non-ollama model returns downloaded=True."""
        import glitchygames.bitmappy.ai_worker as ai_worker_module

        original = ai_worker_module.AI_MODEL
        ai_worker_module.AI_MODEL = 'anthropic:claude-sonnet-4-5'
        result = _check_ollama_model_status(mock_logger)
        assert result['downloaded'] is True
        assert result['reason'] == 'not_ollama'
        ai_worker_module.AI_MODEL = original

    def test_ollama_model_api_error(self, mock_logger, mocker):
        """Non-OK HTTP status returns downloaded=False with api_error reason.

        The function uses urllib.request.urlopen; we mock the response's
        status attribute to simulate a non-200 response.
        """
        import glitchygames.bitmappy.ai_worker as ai_worker_module

        original = ai_worker_module.AI_MODEL
        ai_worker_module.AI_MODEL = 'ollama:testmodel'
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.read.return_value = b'{}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mocker.patch('urllib.request.urlopen', return_value=mock_response)
        result = _check_ollama_model_status(mock_logger)
        assert result['downloaded'] is False
        assert result['reason'] == 'api_error'
        ai_worker_module.AI_MODEL = original

    def test_ollama_model_already_downloaded(self, mock_logger, mocker):
        """Model found in local list returns downloaded=True.

        The function uses urllib.request.urlopen and reads JSON via
        response.read().decode().
        """
        import json

        import glitchygames.bitmappy.ai_worker as ai_worker_module

        original = ai_worker_module.AI_MODEL
        ai_worker_module.AI_MODEL = 'ollama:testmodel'
        response_data = json.dumps({'models': [{'name': 'testmodel:latest'}]}).encode()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = response_data
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mocker.patch('urllib.request.urlopen', return_value=mock_response)
        result = _check_ollama_model_status(mock_logger)
        assert result['downloaded'] is True
        assert result['reason'] == 'already_downloaded'
        ai_worker_module.AI_MODEL = original

    def test_ollama_model_needs_download(self, mock_logger, mocker):
        """Model not found in local list returns needs_download.

        The function uses urllib.request.urlopen and reads JSON via
        response.read().decode().
        """
        import json

        import glitchygames.bitmappy.ai_worker as ai_worker_module

        original = ai_worker_module.AI_MODEL
        ai_worker_module.AI_MODEL = 'ollama:newmodel'
        response_data = json.dumps({'models': [{'name': 'othermodel:latest'}]}).encode()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = response_data
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mocker.patch('urllib.request.urlopen', return_value=mock_response)
        result = _check_ollama_model_status(mock_logger)
        assert result['downloaded'] is False
        assert result['reason'] == 'needs_download'
        ai_worker_module.AI_MODEL = original

    def test_ollama_connection_error(self, mock_logger, mocker):
        """Connection error (OSError) returns check_failed.

        The function catches OSError from urllib.request.urlopen.
        """
        import glitchygames.bitmappy.ai_worker as ai_worker_module

        original = ai_worker_module.AI_MODEL
        ai_worker_module.AI_MODEL = 'ollama:testmodel'
        mocker.patch('urllib.request.urlopen', side_effect=OSError('connection refused'))
        result = _check_ollama_model_status(mock_logger)
        assert result['downloaded'] is False
        assert result['reason'] == 'check_failed'
        ai_worker_module.AI_MODEL = original

    def test_ollama_import_error(self, mock_logger, mocker):
        """ValueError from urllib returns check_failed.

        The function catches (OSError, ValueError, KeyError), so we use
        ValueError since ImportError is not in the exception list and
        urllib is a stdlib module that cannot fail to import.
        """
        import glitchygames.bitmappy.ai_worker as ai_worker_module

        original = ai_worker_module.AI_MODEL
        ai_worker_module.AI_MODEL = 'ollama:testmodel'
        mocker.patch('urllib.request.urlopen', side_effect=ValueError('bad url'))
        result = _check_ollama_model_status(mock_logger)
        assert result['downloaded'] is False
        assert result['reason'] == 'check_failed'
        ai_worker_module.AI_MODEL = original


# ---------------------------------------------------------------------------
# TestSetOllamaEnvTimeout
# ---------------------------------------------------------------------------


class TestSetOllamaEnvTimeout:
    """Tests for _set_ollama_env_timeout function."""

    def test_non_ollama_model_no_env_set(self, mock_logger, mocker):
        """Non-ollama model does not set environment variable."""
        import glitchygames.bitmappy.ai_worker as ai_worker_module

        original = ai_worker_module.AI_MODEL
        ai_worker_module.AI_MODEL = 'anthropic:claude-sonnet-4-5'
        _set_ollama_env_timeout(mock_logger)
        # Should not set OLLAMA_TIMEOUT for non-ollama models
        ai_worker_module.AI_MODEL = original

    def test_ollama_model_sets_env(self, mock_logger, mocker):
        """Ollama model sets OLLAMA_TIMEOUT environment variable."""
        import glitchygames.bitmappy.ai_worker as ai_worker_module

        original = ai_worker_module.AI_MODEL
        ai_worker_module.AI_MODEL = 'ollama:testmodel'
        mocker.patch(
            'glitchygames.bitmappy.ai_worker._check_ollama_model_status',
            return_value={'downloaded': True, 'reason': 'already_downloaded'},
        )
        _set_ollama_env_timeout(mock_logger)
        assert 'OLLAMA_TIMEOUT' in os.environ
        # Clean up
        del os.environ['OLLAMA_TIMEOUT']
        ai_worker_module.AI_MODEL = original

    def test_ollama_model_not_downloaded_uses_longer_timeout(self, mock_logger, mocker):
        """Ollama model needing download uses longer timeout."""
        import glitchygames.bitmappy.ai_worker as ai_worker_module

        original = ai_worker_module.AI_MODEL
        ai_worker_module.AI_MODEL = 'ollama:testmodel'
        mocker.patch(
            'glitchygames.bitmappy.ai_worker._check_ollama_model_status',
            return_value={'downloaded': False, 'reason': 'needs_download'},
        )
        _set_ollama_env_timeout(mock_logger)
        assert os.environ.get('OLLAMA_TIMEOUT') == str(ai_worker_module.AI_MODEL_DOWNLOAD_TIMEOUT)
        del os.environ['OLLAMA_TIMEOUT']
        ai_worker_module.AI_MODEL = original


# ---------------------------------------------------------------------------
# TestCreateOllamaConfig
# ---------------------------------------------------------------------------


class TestCreateOllamaConfig:
    """Tests for _create_ollama_config function."""

    def test_non_ollama_model_returns_empty(self, mock_logger):
        """Non-ollama model returns empty config."""
        import glitchygames.bitmappy.ai_worker as ai_worker_module

        original = ai_worker_module.AI_MODEL
        ai_worker_module.AI_MODEL = 'anthropic:claude-sonnet-4-5'
        result = _create_ollama_config(mock_logger)
        assert result == {}
        ai_worker_module.AI_MODEL = original

    def test_ollama_model_downloaded(self, mock_logger, mocker):
        """Ollama model already downloaded uses normal timeout."""
        import glitchygames.bitmappy.ai_worker as ai_worker_module

        original = ai_worker_module.AI_MODEL
        ai_worker_module.AI_MODEL = 'ollama:testmodel'
        mocker.patch(
            'glitchygames.bitmappy.ai_worker._check_ollama_model_status',
            return_value={'downloaded': True},
        )
        result = _create_ollama_config(mock_logger)
        assert 'ollama' in result
        assert result['ollama']['timeout'] == ai_worker_module.AI_TIMEOUT
        ai_worker_module.AI_MODEL = original

    def test_ollama_model_needs_download(self, mock_logger, mocker):
        """Ollama model needing download uses longer timeout."""
        import glitchygames.bitmappy.ai_worker as ai_worker_module

        original = ai_worker_module.AI_MODEL
        ai_worker_module.AI_MODEL = 'ollama:testmodel'
        mocker.patch(
            'glitchygames.bitmappy.ai_worker._check_ollama_model_status',
            return_value={'downloaded': False},
        )
        result = _create_ollama_config(mock_logger)
        assert result['ollama']['timeout'] == ai_worker_module.AI_MODEL_DOWNLOAD_TIMEOUT
        ai_worker_module.AI_MODEL = original


# ---------------------------------------------------------------------------
# TestGetProviderTimeoutValue
# ---------------------------------------------------------------------------


class TestGetProviderTimeoutValue:
    """Tests for _get_provider_timeout_value function."""

    def test_non_ollama_returns_default(self, mock_logger):
        """Non-ollama model returns AI_TIMEOUT."""
        import glitchygames.bitmappy.ai_worker as ai_worker_module

        original = ai_worker_module.AI_MODEL
        ai_worker_module.AI_MODEL = 'anthropic:claude-sonnet-4-5'
        result = _get_provider_timeout_value(mock_logger)
        assert result == ai_worker_module.AI_TIMEOUT
        ai_worker_module.AI_MODEL = original

    def test_ollama_downloaded_returns_default(self, mock_logger, mocker):
        """Downloaded ollama model returns AI_TIMEOUT."""
        import glitchygames.bitmappy.ai_worker as ai_worker_module

        original = ai_worker_module.AI_MODEL
        ai_worker_module.AI_MODEL = 'ollama:testmodel'
        mocker.patch(
            'glitchygames.bitmappy.ai_worker._check_ollama_model_status',
            return_value={'downloaded': True},
        )
        result = _get_provider_timeout_value(mock_logger)
        assert result == ai_worker_module.AI_TIMEOUT
        ai_worker_module.AI_MODEL = original

    def test_ollama_not_downloaded_returns_download_timeout(self, mock_logger, mocker):
        """Not-downloaded ollama model returns AI_MODEL_DOWNLOAD_TIMEOUT."""
        import glitchygames.bitmappy.ai_worker as ai_worker_module

        original = ai_worker_module.AI_MODEL
        ai_worker_module.AI_MODEL = 'ollama:testmodel'
        mocker.patch(
            'glitchygames.bitmappy.ai_worker._check_ollama_model_status',
            return_value={'downloaded': False},
        )
        result = _get_provider_timeout_value(mock_logger)
        assert result == ai_worker_module.AI_MODEL_DOWNLOAD_TIMEOUT
        ai_worker_module.AI_MODEL = original


# ---------------------------------------------------------------------------
# TestConfigureProviderClientTimeout
# ---------------------------------------------------------------------------


class TestConfigureProviderClientTimeout:
    """Tests for _configure_provider_client_timeout function."""

    def test_provider_without_client(self, mock_logger):
        """Provider without client attribute does nothing."""
        provider = MagicMock(spec=[])  # No 'client' attribute
        _configure_provider_client_timeout(mock_logger, 'test_provider', provider, 600)

    def test_client_with_timeout_attribute(self, mock_logger):
        """Sets timeout on provider.client.timeout."""
        provider = MagicMock()
        provider.client.timeout = 30
        _configure_provider_client_timeout(mock_logger, 'anthropic', provider, 600)
        assert provider.client.timeout == 600

    def test_client_with_nested_client_timeout(self, mock_logger):
        """Sets timeout on provider.client._client.timeout when no direct timeout."""
        provider = MagicMock()
        # Remove direct timeout attribute
        del provider.client.timeout
        provider.client._client.timeout = 30
        _configure_provider_client_timeout(mock_logger, 'test', provider, 600)
        assert provider.client._client.timeout == 600

    def test_ollama_additional_timeout_attrs(self, mock_logger, mocker):
        """Ollama model configures additional timeout attributes."""
        import glitchygames.bitmappy.ai_worker as ai_worker_module

        original = ai_worker_module.AI_MODEL
        ai_worker_module.AI_MODEL = 'ollama:testmodel'
        provider = MagicMock()
        provider.client.timeout = 30
        provider.client.request_timeout = 30
        provider.client.read_timeout = 30
        _configure_provider_client_timeout(mock_logger, 'ollama', provider, 600)
        assert provider.client.timeout == 600
        assert provider.client.request_timeout == ai_worker_module.AI_TIMEOUT
        assert provider.client.read_timeout == ai_worker_module.AI_TIMEOUT
        ai_worker_module.AI_MODEL = original


# ---------------------------------------------------------------------------
# TestConfigureClientTimeouts
# ---------------------------------------------------------------------------


class TestConfigureClientTimeouts:
    """Tests for _configure_client_timeouts function."""

    def test_client_without_providers(self, mock_logger):
        """Client without _providers attribute logs warning."""
        client = MagicMock(spec=[])  # No _providers
        _configure_client_timeouts(mock_logger, client)
        # Should not raise

    def test_client_with_providers(self, mock_logger, mocker):
        """Client with providers configures timeouts."""
        mocker.patch(
            'glitchygames.bitmappy.ai_worker._get_provider_timeout_value',
            return_value=600,
        )
        provider = MagicMock()
        provider.client.timeout = 30
        client = MagicMock()
        client._providers = {'anthropic': provider}
        _configure_client_timeouts(mock_logger, client)
        assert provider.client.timeout == 600

    def test_client_exception_handled(self, mock_logger, mocker):
        """Exception during configuration is handled gracefully."""
        client = MagicMock()
        client._providers = MagicMock(side_effect=Exception('config error'))
        # The items() call raises an exception
        client._providers.items.side_effect = Exception('config error')
        _configure_client_timeouts(mock_logger, client)
        # Should not raise


# ---------------------------------------------------------------------------
# TestConfigureOllamaProvider
# ---------------------------------------------------------------------------


class TestConfigureOllamaProvider:
    """Tests for _configure_ollama_provider function."""

    def test_non_ollama_model_skipped(self, mock_logger):
        """Non-ollama model skips provider configuration."""
        import glitchygames.bitmappy.ai_worker as ai_worker_module

        original = ai_worker_module.AI_MODEL
        ai_worker_module.AI_MODEL = 'anthropic:claude-sonnet-4-5'
        client = MagicMock()
        _configure_ollama_provider(mock_logger, client)
        ai_worker_module.AI_MODEL = original

    def test_client_without_providers_skipped(self, mock_logger):
        """Client without _providers skips configuration."""
        import glitchygames.bitmappy.ai_worker as ai_worker_module

        original = ai_worker_module.AI_MODEL
        ai_worker_module.AI_MODEL = 'ollama:testmodel'
        client = MagicMock(spec=[])  # No _providers
        _configure_ollama_provider(mock_logger, client)
        ai_worker_module.AI_MODEL = original

    def test_ollama_provider_configured(self, mock_logger):
        """Ollama provider gets timeout configured."""
        import glitchygames.bitmappy.ai_worker as ai_worker_module

        original = ai_worker_module.AI_MODEL
        ai_worker_module.AI_MODEL = 'ollama:testmodel'
        provider = MagicMock()
        provider.timeout = 30
        provider.client.timeout = 30
        provider.client.request_timeout = 30
        client = MagicMock()
        client._providers = {'ollama': provider}
        _configure_ollama_provider(mock_logger, client)
        assert provider.timeout == ai_worker_module.AI_MODEL_DOWNLOAD_TIMEOUT
        assert provider.client.timeout == ai_worker_module.AI_MODEL_DOWNLOAD_TIMEOUT
        ai_worker_module.AI_MODEL = original

    def test_non_ollama_provider_in_dict_skipped(self, mock_logger):
        """Non-ollama provider in providers dict is skipped."""
        import glitchygames.bitmappy.ai_worker as ai_worker_module

        original = ai_worker_module.AI_MODEL
        ai_worker_module.AI_MODEL = 'ollama:testmodel'
        anthropic_provider = MagicMock()
        anthropic_provider.timeout = 30
        client = MagicMock()
        client._providers = {'anthropic': anthropic_provider}
        _configure_ollama_provider(mock_logger, client)
        # anthropic provider should not be modified
        assert anthropic_provider.timeout == 30
        ai_worker_module.AI_MODEL = original


# ---------------------------------------------------------------------------
# TestInitializeAiClient
# ---------------------------------------------------------------------------


class TestInitializeAiClient:
    """Tests for _initialize_ai_client function."""

    def test_aisuite_not_available(self, mock_logger, mocker):
        """Returns None when aisuite is not available."""
        mocker.patch('glitchygames.bitmappy.ai_worker.ai', None)
        result = _initialize_ai_client(mock_logger)
        assert result is None

    def test_aisuite_available(self, mock_logger, mocker):
        """Returns client when aisuite is available."""
        mock_ai = MagicMock()
        mock_client = MagicMock()
        mock_ai.Client.return_value = mock_client
        mocker.patch('glitchygames.bitmappy.ai_worker.ai', mock_ai)
        mocker.patch('glitchygames.bitmappy.ai_worker._set_ollama_env_timeout')
        mocker.patch(
            'glitchygames.bitmappy.ai_worker._create_ollama_config',
            return_value={},
        )
        mocker.patch('glitchygames.bitmappy.ai_worker._configure_ollama_provider')
        mocker.patch('glitchygames.bitmappy.ai_worker._configure_client_timeouts')
        result = _initialize_ai_client(mock_logger)
        assert result == mock_client

    def test_aisuite_with_provider_config(self, mock_logger, mocker):
        """Passes provider config to aisuite Client when present."""
        mock_ai = MagicMock()
        mock_client = MagicMock()
        mock_ai.Client.return_value = mock_client
        mocker.patch('glitchygames.bitmappy.ai_worker.ai', mock_ai)
        mocker.patch('glitchygames.bitmappy.ai_worker._set_ollama_env_timeout')
        provider_config = {'ollama': {'timeout': 600}}
        mocker.patch(
            'glitchygames.bitmappy.ai_worker._create_ollama_config',
            return_value=provider_config,
        )
        mocker.patch('glitchygames.bitmappy.ai_worker._configure_ollama_provider')
        mocker.patch('glitchygames.bitmappy.ai_worker._configure_client_timeouts')
        result = _initialize_ai_client(mock_logger)
        mock_ai.Client.assert_called_once_with(provider_config)
        assert result == mock_client


# ---------------------------------------------------------------------------
# TestAiWorker
# ---------------------------------------------------------------------------


class TestAiWorker:
    """Tests for run_ai_worker function error paths."""

    def test_shutdown_signal(self, mocker):
        """Worker exits cleanly on None shutdown signal."""
        mocker.patch('glitchygames.bitmappy.ai_worker._setup_ai_worker_logging')
        mocker.patch(
            'glitchygames.bitmappy.ai_worker._initialize_ai_client',
            return_value=MagicMock(),
        )
        request_queue = MagicMock()
        response_queue = MagicMock()
        # First call returns None (shutdown signal)
        request_queue.get.return_value = None
        run_ai_worker(request_queue, response_queue)
        # Should have exited without putting anything on response queue
        response_queue.put.assert_not_called()

    def test_processing_error_sends_error_response(self, mocker):
        """Processing error sends error response back."""
        mocker.patch('glitchygames.bitmappy.ai_worker._setup_ai_worker_logging')
        mocker.patch(
            'glitchygames.bitmappy.ai_worker._initialize_ai_client',
            return_value=MagicMock(),
        )
        mocker.patch(
            'glitchygames.bitmappy.ai_worker._process_ai_request',
            side_effect=ValueError('test error'),
        )
        request_queue = MagicMock()
        response_queue = MagicMock()
        test_request = AIRequest(
            prompt='test', request_id='req1', messages=[{'role': 'user', 'content': 'test'}],
        )
        # First call returns request, second returns None
        request_queue.get.side_effect = [test_request, None]
        run_ai_worker(request_queue, response_queue)
        # Should have sent an error response
        response_queue.put.assert_called_once()
        call_args = response_queue.put.call_args[0][0]
        assert call_args[0] == 'req1'
        assert call_args[1].error is not None

    def test_import_error_raised(self, mocker):
        """ImportError is re-raised from worker."""
        mocker.patch('glitchygames.bitmappy.ai_worker._setup_ai_worker_logging')
        mocker.patch(
            'glitchygames.bitmappy.ai_worker._initialize_ai_client',
            side_effect=ImportError('no aisuite'),
        )
        request_queue = MagicMock()
        response_queue = MagicMock()
        with pytest.raises(ImportError):
            run_ai_worker(request_queue, response_queue)


# ---------------------------------------------------------------------------
# TestScrollArrowSprite
# ---------------------------------------------------------------------------


class TestScrollArrowSprite:
    """Tests for ScrollArrowSprite class."""

    def test_up_arrow_creation(self, pygame_mocks, mock_groups):
        """Up arrow sprite initializes correctly."""
        arrow = ScrollArrowSprite(
            x=10, y=20, width=20, height=20, groups=mock_groups, direction='up',
        )
        assert arrow.direction == 'up'
        assert arrow.name == 'Scroll up Arrow'
        assert arrow.visible is False

    def test_down_arrow_creation(self, pygame_mocks, mock_groups):
        """Down arrow sprite initializes correctly."""
        arrow = ScrollArrowSprite(
            x=10, y=20, width=20, height=20, groups=mock_groups, direction='down',
        )
        assert arrow.direction == 'down'
        assert arrow.name == 'Scroll down Arrow'

    def test_plus_arrow_creation(self, pygame_mocks, mock_groups):
        """Plus arrow sprite initializes correctly."""
        arrow = ScrollArrowSprite(
            x=0, y=0, width=20, height=20, groups=mock_groups, direction='plus',
        )
        assert arrow.direction == 'plus'

    def test_set_direction_changes(self, pygame_mocks, mock_groups):
        """set_direction changes direction and redraws."""
        arrow = ScrollArrowSprite(x=0, y=0, width=20, height=20, groups=mock_groups, direction='up')
        arrow.set_direction('down')
        assert arrow.direction == 'down'
        assert arrow.dirty == 1

    def test_set_direction_same_no_change(self, pygame_mocks, mock_groups):
        """set_direction with same direction does nothing."""
        arrow = ScrollArrowSprite(x=0, y=0, width=20, height=20, groups=mock_groups, direction='up')
        arrow.dirty = 0
        arrow.set_direction('up')
        # Direction unchanged, dirty should not be set
        assert arrow.dirty == 0

    def test_default_dimensions(self, pygame_mocks, mock_groups):
        """Default dimensions are 20x20."""
        arrow = ScrollArrowSprite(groups=mock_groups)
        assert arrow.rect is not None
        assert arrow.rect.width == 20
        assert arrow.rect.height == 20


# ---------------------------------------------------------------------------
# TestFilmStripSpriteGetFramePixelData
# ---------------------------------------------------------------------------


class TestFilmStripSpriteGetFramePixelData:
    """Tests for FilmStripSprite._get_frame_pixel_data method."""

    def _make_film_strip_sprite(self, pygame_mocks, mock_groups, animated_sprite=None):
        """Create a FilmStripSprite with mocked dependencies."""
        from glitchygames.bitmappy.film_strip_sprite import FilmStripSprite

        widget = MagicMock()
        widget.animated_sprite = animated_sprite
        return FilmStripSprite(
            film_strip_widget=widget, x=0, y=0, width=200, height=50, groups=mock_groups,
        )

    def test_no_animated_sprite(self, pygame_mocks, mock_groups):
        """Returns None when no animated sprite is available."""
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups, animated_sprite=None)
        result = sprite._get_frame_pixel_data('idle', 0)
        assert result is None

    def test_frame_index_out_of_range(self, pygame_mocks, mock_groups):
        """Returns None when frame index is out of range."""
        animated = MagicMock()
        animated._animations = {'idle': [MagicMock()]}
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups, animated_sprite=animated)
        result = sprite._get_frame_pixel_data('idle', 5)
        assert result is None

    def test_animation_not_found(self, pygame_mocks, mock_groups):
        """Returns None when animation name is not found."""
        animated = MagicMock()
        animated._animations = {'idle': [MagicMock()]}
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups, animated_sprite=animated)
        result = sprite._get_frame_pixel_data('walk', 0)
        assert result is None

    def test_frame_with_get_pixel_data(self, pygame_mocks, mock_groups):
        """Returns pixel data from frame.get_pixel_data()."""
        frame = MagicMock()
        pixel_data = [(255, 0, 0, 255), (0, 255, 0, 255)]
        frame.get_pixel_data.return_value = pixel_data
        animated = MagicMock()
        animated._animations = {'idle': [frame]}
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups, animated_sprite=animated)
        result = sprite._get_frame_pixel_data('idle', 0)
        assert result is not None
        assert result[1] == pixel_data

    def test_frame_with_pixels_attribute(self, pygame_mocks, mock_groups):
        """Falls back to frame.pixels when no get_pixel_data."""
        frame = MagicMock(spec=['pixels'])
        frame.pixels = [(255, 0, 0), (0, 255, 0)]
        animated = MagicMock()
        animated._animations = {'idle': [frame]}
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups, animated_sprite=animated)
        result = sprite._get_frame_pixel_data('idle', 0)
        assert result is not None
        assert result[1] == [(255, 0, 0), (0, 255, 0)]

    def test_frame_without_pixel_data(self, pygame_mocks, mock_groups):
        """Returns None when frame has neither get_pixel_data nor pixels."""
        frame = MagicMock(spec=[])
        animated = MagicMock()
        animated._animations = {'idle': [frame]}
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups, animated_sprite=animated)
        result = sprite._get_frame_pixel_data('idle', 0)
        assert result is None

    def test_frame_with_empty_pixel_data(self, pygame_mocks, mock_groups):
        """Returns None when pixel data is empty."""
        frame = MagicMock()
        frame.get_pixel_data.return_value = []
        animated = MagicMock()
        animated._animations = {'idle': [frame]}
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups, animated_sprite=animated)
        result = sprite._get_frame_pixel_data('idle', 0)
        assert result is None


# ---------------------------------------------------------------------------
# TestFilmStripSpriteGetFrameDimensions
# ---------------------------------------------------------------------------


class TestFilmStripSpriteGetFrameDimensions:
    """Tests for FilmStripSprite._get_frame_dimensions method."""

    def _make_film_strip_sprite(self, pygame_mocks, mock_groups):
        from glitchygames.bitmappy.film_strip_sprite import FilmStripSprite

        widget = MagicMock()
        widget.parent_canvas = None
        return FilmStripSprite(
            film_strip_widget=widget, x=0, y=0, width=200, height=50, groups=mock_groups,
        )

    def test_frame_with_image(self, pygame_mocks, mock_groups):
        """Returns dimensions from frame.image.get_size()."""
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups)
        frame = MagicMock()
        frame.image.get_size.return_value = (16, 16)
        assert sprite._get_frame_dimensions(frame) == (16, 16)

    def test_frame_without_image_uses_canvas(self, pygame_mocks, mock_groups):
        """Falls back to parent canvas dimensions."""
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups)
        sprite.film_strip_widget.parent_canvas = MagicMock()
        sprite.film_strip_widget.parent_canvas.pixels_across = 64
        sprite.film_strip_widget.parent_canvas.pixels_tall = 48
        frame = MagicMock(spec=[])  # No 'image'
        assert sprite._get_frame_dimensions(frame) == (64, 48)

    def test_frame_without_image_no_canvas(self, pygame_mocks, mock_groups):
        """Falls back to default 32x32 when no canvas available."""
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups)
        sprite.film_strip_widget.parent_canvas = None
        frame = MagicMock(spec=[])
        assert sprite._get_frame_dimensions(frame) == (32, 32)


# ---------------------------------------------------------------------------
# TestFilmStripSpriteFindFrameLayout
# ---------------------------------------------------------------------------


class TestFilmStripSpriteFindFrameLayout:
    """Tests for FilmStripSprite._find_frame_layout method."""

    def _make_film_strip_sprite(self, pygame_mocks, mock_groups):
        from glitchygames.bitmappy.film_strip_sprite import FilmStripSprite

        widget = MagicMock()
        return FilmStripSprite(
            film_strip_widget=widget, x=0, y=0, width=200, height=50, groups=mock_groups,
        )

    def test_frame_found(self, pygame_mocks, mock_groups):
        """Returns frame layout when found."""
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups)
        mock_rect = pygame.Rect(10, 10, 40, 40)
        sprite.film_strip_widget.frame_layouts = {('idle', 0): mock_rect}
        result = sprite._find_frame_layout('idle', 0)
        assert result == mock_rect

    def test_frame_not_found(self, pygame_mocks, mock_groups):
        """Returns None when frame layout is not found."""
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups)
        sprite.film_strip_widget.frame_layouts = {}
        result = sprite._find_frame_layout('idle', 0)
        assert result is None


# ---------------------------------------------------------------------------
# TestFilmStripSpriteScreenToPixelCoords
# ---------------------------------------------------------------------------


class TestFilmStripSpriteScreenToPixelCoords:
    """Tests for FilmStripSprite._screen_to_pixel_coords method."""

    def _make_film_strip_sprite(self, pygame_mocks, mock_groups):
        from glitchygames.bitmappy.film_strip_sprite import FilmStripSprite

        widget = MagicMock()
        return FilmStripSprite(
            film_strip_widget=widget, x=0, y=0, width=200, height=50, groups=mock_groups,
        )

    def test_coords_inside_frame(self, pygame_mocks, mock_groups):
        """Returns pixel coordinates when click is inside frame."""
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups)
        frame_layout = pygame.Rect(10, 10, 40, 40)
        # Click at center of frame
        result = sprite._screen_to_pixel_coords(30, 30, frame_layout, 16, 16)
        assert result is not None
        pixel_x, pixel_y = result
        assert 0 <= pixel_x < 16
        assert 0 <= pixel_y < 16

    def test_coords_outside_frame(self, pygame_mocks, mock_groups):
        """Returns None when click is outside frame."""
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups)
        frame_layout = pygame.Rect(10, 10, 40, 40)
        result = sprite._screen_to_pixel_coords(100, 100, frame_layout, 16, 16)
        assert result is None

    def test_coords_at_frame_edge(self, pygame_mocks, mock_groups):
        """Coords at frame edge are clamped to valid range."""
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups)
        frame_layout = pygame.Rect(0, 0, 40, 40)
        result = sprite._screen_to_pixel_coords(0, 0, frame_layout, 16, 16)
        assert result is not None
        pixel_x, pixel_y = result
        assert pixel_x >= 0
        assert pixel_y >= 0


# ---------------------------------------------------------------------------
# TestFilmStripSpriteUpdateColorSliders
# ---------------------------------------------------------------------------


class TestFilmStripSpriteUpdateColorSliders:
    """Tests for FilmStripSprite._update_color_sliders method."""

    def _make_film_strip_sprite(self, pygame_mocks, mock_groups):
        from glitchygames.bitmappy.film_strip_sprite import FilmStripSprite

        widget = MagicMock()
        return FilmStripSprite(
            film_strip_widget=widget, x=0, y=0, width=200, height=50, groups=mock_groups,
        )

    def test_no_parent_scene(self, pygame_mocks, mock_groups):
        """Does nothing when no parent_scene."""
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups)
        sprite.parent_scene = None
        # Should not raise
        sprite._update_color_sliders(255, 128, 0, 200)

    def test_with_parent_scene(self, pygame_mocks, mock_groups):
        """Calls on_slider_event for each RGBA channel."""
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups)
        mock_scene = MagicMock()
        sprite.parent_scene = mock_scene
        sprite._update_color_sliders(100, 150, 200, 250)
        assert mock_scene.on_slider_event.call_count == 4


# ---------------------------------------------------------------------------
# TestFilmStripSpriteSampleColorFromFrame
# ---------------------------------------------------------------------------


class TestFilmStripSpriteSampleColorFromFrame:
    """Tests for FilmStripSprite._sample_color_from_frame method."""

    def _make_film_strip_sprite(self, pygame_mocks, mock_groups):
        from glitchygames.bitmappy.film_strip_sprite import FilmStripSprite

        widget = MagicMock()
        widget.animated_sprite = None
        widget.frame_layouts = {}
        return FilmStripSprite(
            film_strip_widget=widget, x=0, y=0, width=200, height=50, groups=mock_groups,
        )

    def test_no_pixel_data_returns_early(self, pygame_mocks, mock_groups):
        """Returns early when no pixel data available."""
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups)
        # No animated sprite, so _get_frame_pixel_data returns None
        sprite._sample_color_from_frame('idle', 0, 20, 20)
        # Should not raise

    def test_no_frame_layout_returns_early(self, pygame_mocks, mock_groups):
        """Returns early when frame layout not found."""
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups)
        frame = MagicMock()
        frame.get_pixel_data.return_value = [(255, 0, 0, 255)]
        frame.image.get_size.return_value = (16, 16)
        animated = MagicMock()
        animated._animations = {'idle': [frame]}
        sprite.film_strip_widget.animated_sprite = animated
        sprite.film_strip_widget.frame_layouts = {}
        sprite._sample_color_from_frame('idle', 0, 20, 20)
        # Should not raise

    def test_successful_color_sampling_rgba(self, pygame_mocks, mock_groups):
        """Successfully samples an RGBA color."""
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups)
        frame = MagicMock()
        pixel_data = [(255, 0, 0, 128)] * 256  # 16x16 pixels
        frame.get_pixel_data.return_value = pixel_data
        frame.image.get_size.return_value = (16, 16)
        animated = MagicMock()
        animated._animations = {'idle': [frame]}
        sprite.film_strip_widget.animated_sprite = animated
        frame_rect = pygame.Rect(0, 0, 40, 40)
        sprite.film_strip_widget.frame_layouts = {('idle', 0): frame_rect}
        mock_scene = MagicMock()
        sprite.parent_scene = mock_scene
        sprite._sample_color_from_frame('idle', 0, 20, 20)
        assert mock_scene.on_slider_event.call_count == 4

    def test_successful_color_sampling_rgb(self, pygame_mocks, mock_groups):
        """Successfully samples an RGB color (no alpha)."""
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups)
        frame = MagicMock()
        pixel_data = [(0, 255, 0)] * 256  # 16x16 pixels
        frame.get_pixel_data.return_value = pixel_data
        frame.image.get_size.return_value = (16, 16)
        animated = MagicMock()
        animated._animations = {'idle': [frame]}
        sprite.film_strip_widget.animated_sprite = animated
        frame_rect = pygame.Rect(0, 0, 40, 40)
        sprite.film_strip_widget.frame_layouts = {('idle', 0): frame_rect}
        mock_scene = MagicMock()
        sprite.parent_scene = mock_scene
        sprite._sample_color_from_frame('idle', 0, 20, 20)
        assert mock_scene.on_slider_event.call_count == 4


# ---------------------------------------------------------------------------
# TestFilmStripSpriteHoverEffects
# ---------------------------------------------------------------------------


class TestFilmStripSpriteHoverEffects:
    """Tests for FilmStripSprite hover effect methods."""

    def _make_film_strip_sprite(self, pygame_mocks, mock_groups):
        from glitchygames.bitmappy.film_strip_sprite import FilmStripSprite

        widget = MagicMock()
        return FilmStripSprite(
            film_strip_widget=widget, x=0, y=0, width=200, height=50, groups=mock_groups,
        )

    def test_show_frame_hover_effect(self, pygame_mocks, mock_groups):
        """Sets hovered_frame and marks dirty."""
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups)
        sprite._show_frame_hover_effect(('idle', 0))
        assert sprite.film_strip_widget.hovered_frame == ('idle', 0)
        assert sprite.dirty == 1

    def test_show_preview_hover_effect(self, pygame_mocks, mock_groups):
        """Sets hovered_preview and marks dirty."""
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups)
        sprite._show_preview_hover_effect('idle')
        assert sprite.film_strip_widget.hovered_preview == 'idle'
        assert sprite.dirty == 1

    def test_show_strip_hover_effect(self, pygame_mocks, mock_groups):
        """Sets strip hover state and marks dirty."""
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups)
        sprite._show_strip_hover_effect()
        assert sprite.film_strip_widget.hovered_frame is None
        assert sprite.film_strip_widget.is_hovering_strip is True
        assert sprite.dirty == 1

    def test_clear_hover_effects(self, pygame_mocks, mock_groups):
        """Clears all hover state and marks dirty."""
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups)
        sprite._clear_hover_effects()
        assert sprite.film_strip_widget.hovered_frame is None
        assert sprite.film_strip_widget.hovered_preview is None
        assert sprite.film_strip_widget.is_hovering_strip is False
        assert sprite.film_strip_widget.hovered_removal_button is None
        assert sprite.dirty == 1


# ---------------------------------------------------------------------------
# TestFilmStripSpriteOnMouseMotionEvent
# ---------------------------------------------------------------------------


class TestFilmStripSpriteOnMouseMotionEvent:
    """Tests for FilmStripSprite.on_mouse_motion_event method."""

    def _make_film_strip_sprite(self, pygame_mocks, mock_groups):
        from glitchygames.bitmappy.film_strip_sprite import FilmStripSprite

        widget = MagicMock()
        widget.get_frame_at_position.return_value = None
        widget.get_preview_at_position.return_value = None
        widget.hovered_preview = None
        return FilmStripSprite(
            film_strip_widget=widget, x=0, y=0, width=200, height=50, groups=mock_groups,
        )

    def test_motion_over_frame(self, pygame_mocks, mock_groups):
        """Mouse over a frame sets frame hover."""
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups)
        sprite.film_strip_widget.get_frame_at_position.return_value = ('idle', 0)
        event = MagicMock()
        event.pos = (50, 25)
        sprite.on_mouse_motion_event(event)
        assert sprite.film_strip_widget.hovered_frame == ('idle', 0)
        assert sprite.dirty == 1

    def test_motion_over_preview(self, pygame_mocks, mock_groups):
        """Mouse over preview area sets preview hover."""
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups)
        sprite.film_strip_widget.get_frame_at_position.return_value = None
        sprite.film_strip_widget.get_preview_at_position.return_value = 'idle'
        event = MagicMock()
        event.pos = (50, 25)
        sprite.on_mouse_motion_event(event)
        assert sprite.film_strip_widget.hovered_preview == 'idle'

    def test_motion_over_strip_area(self, pygame_mocks, mock_groups):
        """Mouse over strip area (not frame/preview) sets strip hover."""
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups)
        sprite.film_strip_widget.get_frame_at_position.return_value = None
        sprite.film_strip_widget.get_preview_at_position.return_value = None
        sprite.film_strip_widget.hovered_preview = None
        event = MagicMock()
        event.pos = (50, 25)
        sprite.on_mouse_motion_event(event)
        assert sprite.film_strip_widget.is_hovering_strip is True

    def test_motion_outside_strip(self, pygame_mocks, mock_groups):
        """Mouse outside film strip clears hover effects."""
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups)
        event = MagicMock()
        event.pos = (500, 500)  # Outside the 200x50 rect
        sprite.on_mouse_motion_event(event)
        assert sprite.film_strip_widget.hovered_frame is None
        assert sprite.film_strip_widget.hovered_preview is None
        assert sprite.film_strip_widget.is_hovering_strip is False

    def test_motion_clears_preview_hover_when_leaving_preview(self, pygame_mocks, mock_groups):
        """Leaving preview area clears preview hover."""
        sprite = self._make_film_strip_sprite(pygame_mocks, mock_groups)
        sprite.film_strip_widget.get_frame_at_position.return_value = None
        sprite.film_strip_widget.get_preview_at_position.return_value = None
        # Simulate that we were previously hovering over a preview
        sprite.film_strip_widget.hovered_preview = 'idle'
        event = MagicMock()
        event.pos = (50, 25)
        sprite.on_mouse_motion_event(event)
        assert sprite.film_strip_widget.hovered_preview is None


# ---------------------------------------------------------------------------
# TestAnimatedCanvasSpriteDragMethods
# ---------------------------------------------------------------------------


class TestAnimatedCanvasSpriteDragMethods:
    """Tests for AnimatedCanvasSprite drag-related methods."""

    def _make_canvas_sprite(self, pygame_mocks, mock_groups):
        """Create an AnimatedCanvasSprite with mocked dependencies."""
        from glitchygames.bitmappy.animated_canvas import AnimatedCanvasSprite

        animated_sprite = MagicMock()
        animated_sprite.current_animation = 'idle'
        animated_sprite.current_frame = 0
        animated_sprite._animations = {
            'idle': [MagicMock()],
        }
        animated_sprite.frames = {'idle': [MagicMock()]}
        animated_sprite.is_playing = False
        animated_sprite.is_static_sprite.return_value = False

        frame = animated_sprite._animations['idle'][0]
        frame.get_pixel_data.return_value = [(255, 0, 0, 255)] * (32 * 32)
        frame.pixels = [(255, 0, 0, 255)] * (32 * 32)
        frame._image = pygame.Surface((32, 32))

        return AnimatedCanvasSprite(
            animated_sprite=animated_sprite,
            name='test_canvas',
            x=0,
            y=0,
            pixels_across=32,
            pixels_tall=32,
            pixel_width=10,
            pixel_height=10,
            groups=mock_groups,
        )

    def test_cache_drag_frame_first_time(self, pygame_mocks, mock_groups):
        """Caching drag frame stores frame reference."""
        canvas = self._make_canvas_sprite(pygame_mocks, mock_groups)
        # Remove _drag_frame if it was set during init
        if hasattr(canvas, '_drag_frame'):
            del canvas._drag_frame
        canvas._cache_drag_frame()
        assert hasattr(canvas, '_drag_frame')

    def test_cache_drag_frame_already_cached(self, pygame_mocks, mock_groups):
        """Second cache call does not overwrite existing cached frame."""
        canvas = self._make_canvas_sprite(pygame_mocks, mock_groups)
        sentinel = object()
        canvas._drag_frame = sentinel
        canvas._cache_drag_frame()
        assert canvas._drag_frame is sentinel

    def test_get_old_pixel_color_no_drag_frame(self, pygame_mocks, mock_groups):
        """Without drag frame, returns canvas pixel color."""
        canvas = self._make_canvas_sprite(pygame_mocks, mock_groups)
        canvas._drag_frame = None
        canvas.pixels[0] = (100, 200, 50, 255)
        result = canvas._get_old_pixel_color(0)
        assert result == (100, 200, 50, 255)

    def test_get_old_pixel_color_from_drag_frame_pixels(self, pygame_mocks, mock_groups):
        """With drag frame.pixels, returns frame pixel color."""
        canvas = self._make_canvas_sprite(pygame_mocks, mock_groups)
        frame = MagicMock()
        frame.pixels = [(10, 20, 30, 255)] * (32 * 32)
        canvas._drag_frame = frame
        result = canvas._get_old_pixel_color(0)
        assert result == (10, 20, 30, 255)

    def test_get_old_pixel_color_fallback_get_pixel_data(self, pygame_mocks, mock_groups):
        """Falls back to get_pixel_data() when frame has no pixels attribute."""
        canvas = self._make_canvas_sprite(pygame_mocks, mock_groups)
        frame = MagicMock(spec=['get_pixel_data'])
        frame.get_pixel_data.return_value = [(50, 60, 70, 255)] * (32 * 32)
        canvas._drag_frame = frame
        result = canvas._get_old_pixel_color(0)
        assert result == (50, 60, 70, 255)

    def test_update_drag_frame_pixel_no_drag_frame(self, pygame_mocks, mock_groups):
        """Does nothing when drag frame is None."""
        canvas = self._make_canvas_sprite(pygame_mocks, mock_groups)
        canvas._drag_frame = None
        canvas._update_drag_frame_pixel(0, (255, 0, 0, 255))
        # Should not raise

    def test_update_drag_frame_pixel_fast_path(self, pygame_mocks, mock_groups):
        """Updates pixel directly in frame.pixels."""
        canvas = self._make_canvas_sprite(pygame_mocks, mock_groups)
        frame = MagicMock()
        frame.pixels = [(0, 0, 0, 255)] * (32 * 32)
        canvas._drag_frame = frame
        canvas._update_drag_frame_pixel(5, (255, 0, 0, 255))
        assert frame.pixels[5] == (255, 0, 0, 255)

    def test_update_drag_frame_pixel_slow_path(self, pygame_mocks, mock_groups):
        """Falls back to get/set_pixel_data when no pixels attribute."""
        canvas = self._make_canvas_sprite(pygame_mocks, mock_groups)
        frame = MagicMock(spec=['get_pixel_data', 'set_pixel_data'])
        frame_pixels = [(0, 0, 0, 255)] * (32 * 32)
        frame.get_pixel_data.return_value = frame_pixels
        canvas._drag_frame = frame
        canvas._update_drag_frame_pixel(5, (255, 0, 0, 255))
        frame.set_pixel_data.assert_called_once()

    def test_clear_surface_cache(self, pygame_mocks, mock_groups):
        """Clears cache entry for current animation frame."""
        canvas = self._make_canvas_sprite(pygame_mocks, mock_groups)
        canvas.animated_sprite._surface_cache = {'idle_0': MagicMock()}
        canvas._clear_surface_cache()
        assert 'idle_0' not in canvas.animated_sprite._surface_cache

    def test_clear_surface_cache_no_cache(self, pygame_mocks, mock_groups):
        """Does nothing when no surface cache exists."""
        canvas = self._make_canvas_sprite(pygame_mocks, mock_groups)
        if hasattr(canvas.animated_sprite, '_surface_cache'):
            del canvas.animated_sprite._surface_cache
        canvas._clear_surface_cache()
        # Should not raise

    def test_rebuild_frame_image_from_pixels(self, pygame_mocks, mock_groups):
        """Rebuilds frame image from pixel data."""
        canvas = self._make_canvas_sprite(pygame_mocks, mock_groups)
        frame = MagicMock()
        frame._image = pygame.Surface((4, 4))
        frame.pixels = [(255, 0, 0, 255)] * 16
        canvas._rebuild_frame_image_from_pixels(frame)
        # Should not raise; the image should be updated

    def test_rebuild_frame_image_no_image(self, pygame_mocks, mock_groups):
        """Does nothing when frame has no _image."""
        canvas = self._make_canvas_sprite(pygame_mocks, mock_groups)
        frame = MagicMock(spec=['pixels'])
        frame.pixels = [(255, 0, 0, 255)] * 16
        canvas._rebuild_frame_image_from_pixels(frame)
        # Should not raise

    def test_rebuild_frame_image_clears_stale_flag(self, pygame_mocks, mock_groups):
        """Clears _image_stale flag after rebuild."""
        canvas = self._make_canvas_sprite(pygame_mocks, mock_groups)
        frame = MagicMock()
        frame._image = pygame.Surface((4, 4))
        frame.pixels = [(255, 0, 0, 255)] * 16
        frame._image_stale = True
        canvas._rebuild_frame_image_from_pixels(frame)
        assert not hasattr(frame, '_image_stale')

    def test_flush_batched_drag_pixels(self, pygame_mocks, mock_groups):
        """Flushes drag pixel changes to frame."""
        canvas = self._make_canvas_sprite(pygame_mocks, mock_groups)
        canvas._drag_pixels = {
            (0, 0): (0, 0, (0, 0, 0, 255), (255, 0, 0, 255)),
            (1, 0): (1, 0, (0, 0, 0, 255), (0, 255, 0, 255)),
        }
        frame = canvas.animated_sprite._animations['idle'][0]
        frame.get_pixel_data.return_value = [(0, 0, 0, 255)] * (32 * 32)
        canvas._flush_batched_drag_pixels()
        frame.set_pixel_data.assert_called_once()

    def test_flush_batched_drag_pixels_no_animated_sprite(self, pygame_mocks, mock_groups):
        """Does nothing when no animated sprite."""
        canvas = self._make_canvas_sprite(pygame_mocks, mock_groups)
        del canvas.animated_sprite
        canvas._drag_pixels = {(0, 0): (0, 0, (0, 0, 0), (255, 0, 0))}
        canvas._flush_batched_drag_pixels()
        # Should not raise

    def test_sync_drag_frame_surface(self, pygame_mocks, mock_groups):
        """Syncs drag frame surface from pixels."""
        canvas = self._make_canvas_sprite(pygame_mocks, mock_groups)
        frame = MagicMock()
        frame.pixels = [(255, 0, 0, 255)] * 16
        canvas._drag_frame = frame
        canvas._sync_drag_frame_surface()
        frame.set_pixel_data.assert_called_once()

    def test_sync_drag_frame_surface_no_drag_frame(self, pygame_mocks, mock_groups):
        """Does nothing when no drag frame."""
        canvas = self._make_canvas_sprite(pygame_mocks, mock_groups)
        if hasattr(canvas, '_drag_frame'):
            del canvas._drag_frame
        canvas._sync_drag_frame_surface()
        # Should not raise

    def test_sync_drag_frame_surface_error_handled(self, pygame_mocks, mock_groups):
        """Handles error during frame sync gracefully."""
        canvas = self._make_canvas_sprite(pygame_mocks, mock_groups)
        frame = MagicMock()
        frame.pixels = [(255, 0, 0, 255)]
        frame.set_pixel_data.side_effect = TypeError('test')
        canvas._drag_frame = frame
        canvas._sync_drag_frame_surface()
        # Should not raise

    def test_submit_drag_pixel_changes_to_undo(self, pygame_mocks, mock_groups):
        """Submits pixel changes to undo system."""
        canvas = self._make_canvas_sprite(pygame_mocks, mock_groups)
        mock_scene = MagicMock()
        mock_scene._applying_undo_redo = False
        mock_scene.current_pixel_changes = []
        canvas.parent_scene = mock_scene
        canvas._drag_pixels = {
            (0, 0): (0, 0, (0, 0, 0, 255), (255, 0, 0, 255)),
        }
        canvas._submit_drag_pixel_changes_to_undo()
        assert len(mock_scene.current_pixel_changes) == 1

    def test_submit_drag_pixel_changes_no_parent_scene(self, pygame_mocks, mock_groups):
        """Does nothing when no parent scene."""
        canvas = self._make_canvas_sprite(pygame_mocks, mock_groups)
        canvas.parent_scene = None
        canvas._drag_pixels = {(0, 0): (0, 0, (0, 0, 0), (255, 0, 0))}
        canvas._submit_drag_pixel_changes_to_undo()
        # Should not raise

    def test_submit_drag_pixel_changes_applying_undo(self, pygame_mocks, mock_groups):
        """Does nothing during undo/redo application."""
        canvas = self._make_canvas_sprite(pygame_mocks, mock_groups)
        mock_scene = MagicMock()
        mock_scene._applying_undo_redo = True
        canvas.parent_scene = mock_scene
        canvas._drag_pixels = {(0, 0): (0, 0, (0, 0, 0), (255, 0, 0))}
        canvas._submit_drag_pixel_changes_to_undo()
        # Should not modify scene

    def test_submit_drag_pixel_changes_empty(self, pygame_mocks, mock_groups):
        """Does nothing when no pixel changes."""
        canvas = self._make_canvas_sprite(pygame_mocks, mock_groups)
        mock_scene = MagicMock()
        mock_scene._applying_undo_redo = False
        canvas.parent_scene = mock_scene
        canvas._drag_pixels = {}
        canvas._submit_drag_pixel_changes_to_undo()
        # Should not raise

    def test_cleanup_drag_state(self, pygame_mocks, mock_groups):
        """Cleans up all drag-related state."""
        canvas = self._make_canvas_sprite(pygame_mocks, mock_groups)
        frame = MagicMock()
        frame.pixels = [(255, 0, 0, 255)] * 16
        frame._image = pygame.Surface((4, 4))
        frame._image_stale = True
        canvas._drag_frame = frame
        canvas._drag_active = True
        canvas._drag_pixels = {(0, 0): (0, 0, (0, 0, 0), (255, 0, 0))}
        canvas._drag_redraw_counter = 10
        canvas._cleanup_drag_state()
        assert canvas._drag_active is False
        assert canvas._drag_pixels == {}
        assert not hasattr(canvas, '_drag_redraw_counter')
        assert not hasattr(canvas, '_drag_frame')

    def test_cleanup_drag_state_no_drag_frame(self, pygame_mocks, mock_groups):
        """Cleanup works even without a drag frame."""
        canvas = self._make_canvas_sprite(pygame_mocks, mock_groups)
        canvas._drag_active = True
        canvas._drag_pixels = {}
        if hasattr(canvas, '_drag_frame'):
            del canvas._drag_frame
        canvas._cleanup_drag_state()
        assert canvas._drag_active is False
