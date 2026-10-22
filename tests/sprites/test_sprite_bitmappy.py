"""Bitmappy sprite functionality tests."""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.sprites import (
    BitmappySprite,
    FocusableSingletonBitmappySprite,
    Singleton,
    SingletonBitmappySprite,
)

# Test constants
EXPECTED_ERROR_COUNT_2 = 2
EXPECTED_ERROR_COUNT_3 = 3


class TestBitmappySprite:
    """Test BitmappySprite functionality."""

    def test_bitmappy_sprite_initialization_with_filename(self, tmp_path):
        """A BitmappySprite given a filename loads that file's pixels and size."""
        sprite_path = tmp_path / 'two_colors.toml'
        sprite_path.write_text(
            '[sprite]\n'
            'name = "two_colors"\n'
            'pixels = """\n'
            'RG\n'
            'GR\n'
            'RG\n'
            '"""\n'
            '[colors.R]\nred = 255\ngreen = 0\nblue = 0\n'
            '[colors.G]\nred = 0\ngreen = 255\nblue = 0\n',
            encoding='utf-8',
        )

        sprite = BitmappySprite(x=5, y=7, filename=str(sprite_path))

        assert isinstance(sprite, BitmappySprite)
        assert sprite.filename == str(sprite_path)
        assert sprite.name == 'two_colors'
        assert (sprite.width, sprite.height) == (2, 3)
        assert (sprite.rect.x, sprite.rect.y, sprite.rect.width, sprite.rect.height) == (
            5,
            7,
            2,
            3,
        )
        red, green = [255, 0, 0], [0, 255, 0]
        assert pygame.surfarray.array3d(sprite.image).transpose(1, 0, 2).tolist() == [
            [red, green],
            [green, red],
            [red, green],
        ]

    def test_bitmappy_sprite_initialization_without_filename(self):
        """Test BitmappySprite initialization without filename."""
        sprite = BitmappySprite()

        assert isinstance(sprite, BitmappySprite)
        assert not sprite.filename

    def test_bitmappy_sprite_initialization_with_focusable(self):
        """Test BitmappySprite initialization with focusable."""
        sprite = BitmappySprite(focusable=True)

        assert isinstance(sprite, BitmappySprite)
        assert sprite.focusable

    def test_bitmappy_sprite_initialization_with_zero_dimensions(self):
        """A BitmappySprite with no file and no size cannot make its surface."""
        with pytest.raises(pygame.error, match=r'Can\'t create Surface\(\(0, 0\)\)'):
            BitmappySprite(x=0, y=0, width=0, height=0)

    def test_bitmappy_sprite_load_method(self, mocker):
        """Test BitmappySprite load method."""
        sprite = BitmappySprite()

        mock_load = mocker.patch('glitchygames.sprites.BitmappySprite._load_static_only')
        mock_factory = mocker.patch('glitchygames.sprites.SpriteFactory.load_sprite')
        mock_factory.side_effect = ValueError('Factory failed')
        sprite.load('test.toml')
        mock_load.assert_called_once_with('test.toml')

    def test_bitmappy_sprite_load_method_with_frame(self, mocker):
        """Test BitmappySprite load method with frame."""
        sprite = BitmappySprite()

        mock_load = mocker.patch('glitchygames.sprites.BitmappySprite._load_static_only')
        mock_factory = mocker.patch('glitchygames.sprites.SpriteFactory.load_sprite')
        mock_factory.side_effect = ValueError('Factory failed')
        sprite.load('test.toml')
        mock_load.assert_called_once_with('test.toml')

    def test_bitmappy_sprite_load_method_fallback(self, mocker):
        """Test BitmappySprite load method fallback."""
        sprite = BitmappySprite()

        mock_load = mocker.patch('glitchygames.sprites.BitmappySprite._load_static_only')
        mock_factory = mocker.patch('glitchygames.sprites.SpriteFactory.load_sprite')
        mock_factory.side_effect = ValueError('Factory failed')
        mock_load.side_effect = Exception('Load failed')
        with pytest.raises(Exception, match='Load failed'):
            sprite.load('test.toml')

    def test_bitmappy_sprite_save_method(self, mocker):
        """Test BitmappySprite save method."""
        sprite = BitmappySprite()

        mock_save = mocker.patch('glitchygames.sprites.BitmappySprite._save_static_only')
        sprite.save('test.toml')
        mock_save.assert_called_once_with('test.toml', 'toml')

    def test_bitmappy_sprite_deflate_method(self, mocker):
        """Test BitmappySprite deflate method."""
        sprite = BitmappySprite()
        sprite.pixels = [(255, 0, 0), (0, 255, 0)]

        mocker.patch(
            'glitchygames.sprites.BitmappySprite._create_color_map',
            return_value={'A': (255, 0, 0), 'B': (0, 255, 0), 'X': (255, 0, 255)},
        )

        # Use pytest logger wrapper to suppress logs during successful runs
        mock_log = mocker.patch.object(sprite, 'log')
        result = sprite.deflate('toml')
        assert result is not None

        # Verify the ERROR log message was called
        mock_log.error.assert_called_once()
        # Check that the log message contains the expected content
        call_args = mock_log.error.call_args[0][0]
        assert 'Pixels list length mismatch: 2 vs expected 1024' in call_args

    def test_bitmappy_sprite_deflate_method_unsupported_format(self, mocker):
        """Test BitmappySprite deflate method with unsupported format."""
        sprite = BitmappySprite()

        # Use pytest logger wrapper to suppress logs during successful runs
        mock_log = mocker.patch.object(sprite, 'log')
        with pytest.raises(ValueError, match='Unsupported format'):
            sprite.deflate('json')

        # Verify the ERROR log message was called for validation warnings
        assert mock_log.error.call_count >= 1
        # Check that the log messages contain the expected content
        error_args_list = [call[0][0] for call in mock_log.error.call_args_list]
        assert any(
            'Pixels list length mismatch: 0 vs expected 1024' in msg for msg in error_args_list
        )
        # "Error in deflate" is logged via LOG.exception (inside except block)
        assert mock_log.exception.call_count >= 1
        exception_args_list = [call[0][0] for call in mock_log.exception.call_args_list]
        assert any('Error in deflate' in msg for msg in exception_args_list)

    def test_bitmappy_sprite_deflate_method_too_many_colors(self, mocker):
        """Test BitmappySprite deflate method with too many colors."""
        sprite = BitmappySprite()
        # Create sprite with too many colors
        sprite.pixels = [(i, i, i) for i in range(100)]

        # Use pytest logger wrapper to suppress logs during successful runs
        mock_log = mocker.patch.object(sprite, 'log')
        with pytest.raises(ValueError, match='Too many colors'):
            sprite.deflate('toml')

        # Verify the ERROR log message was called for validation warnings
        assert mock_log.error.call_count >= 1
        # Check that the log messages contain the expected content
        error_args_list = [call[0][0] for call in mock_log.error.call_args_list]
        assert any(
            'Pixels list length mismatch: 100 vs expected 1024' in msg for msg in error_args_list
        )
        # "Error in deflate" is logged via LOG.exception (inside except block)
        assert mock_log.exception.call_count >= 1
        exception_args_list = [call[0][0] for call in mock_log.exception.call_args_list]
        assert any('Error in deflate' in msg for msg in exception_args_list)

    def test_bitmappy_sprite_deflate_pads_and_truncates_pixels(self, mocker):
        """Test BitmappySprite deflate method padding and truncating pixels."""
        sprite = BitmappySprite()
        sprite.pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]

        mocker.patch(
            'glitchygames.sprites.BitmappySprite._create_color_map',
            return_value={'A': (255, 0, 0), 'B': (0, 255, 0), 'C': (0, 0, 255), 'X': (255, 0, 255)},
        )

        # Use pytest logger wrapper to suppress logs during successful runs
        mock_log = mocker.patch.object(sprite, 'log')
        result = sprite.deflate('toml')
        assert result is not None

        # Verify the ERROR log message was called
        mock_log.error.assert_called_once()
        # Check that the log message contains the expected content
        call_args = mock_log.error.call_args[0][0]
        assert 'Pixels list length mismatch: 3 vs expected 1024' in call_args

    def test_bitmappy_sprite_deflate_dangerous_char_replacement(self, mocker):
        """Test BitmappySprite deflate method dangerous character replacement."""
        sprite = BitmappySprite()
        sprite.pixels = [(1, 1, 1)]  # Dangerous character

        mocker.patch(
            'glitchygames.sprites.BitmappySprite._create_color_map',
            return_value={'A': (1, 1, 1), 'X': (255, 0, 255)},
        )

        # Use pytest logger wrapper to suppress logs during successful runs
        mock_log = mocker.patch.object(sprite, 'log')
        result = sprite.deflate('toml')
        assert result is not None

        # Verify the ERROR log message was called
        mock_log.error.assert_called_once()
        # Check that the log message contains the expected content
        call_args = mock_log.error.call_args[0][0]
        assert 'Pixels list length mismatch: 1 vs expected 1024' in call_args

    def test_bitmappy_sprite_deflate_missing_color_in_map(self, mocker):
        """Test BitmappySprite deflate method with missing color in map."""
        sprite = BitmappySprite()
        sprite.pixels = [(255, 0, 0), (0, 255, 0)]

        mocker.patch(
            'glitchygames.sprites.BitmappySprite._create_color_map',
            return_value={'A': (255, 0, 0), 'X': (255, 0, 255)},  # Missing second color
        )

        # Use pytest logger wrapper to suppress logs during successful runs
        mock_log = mocker.patch.object(sprite, 'log')
        result = sprite.deflate('toml')
        assert result is not None

        # Verify the ERROR log messages were called
        assert mock_log.error.call_count == EXPECTED_ERROR_COUNT_2
        # Check that the log messages contain the expected content
        first_call = mock_log.error.call_args_list[0][0][0]
        second_call = mock_log.error.call_args_list[1][0][0]
        assert 'Pixels list length mismatch: 2 vs expected 1024' in first_call
        assert 'not found in color_map' in second_call

    def test_bitmappy_sprite_inflate_method(self, tmp_path):
        """inflate_from_file reads a TOML file's name, size and pixels."""
        sprite = BitmappySprite()
        sprite_path = tmp_path / 'test.toml'
        sprite_path.write_text(
            '[sprite]\nname = "tiny"\npixels = """\nRG\nG?\n"""\n'
            '[colors.R]\nred = 255\ngreen = 0\nblue = 0\n'
            '[colors.G]\nred = 0\ngreen = 255\nblue = 0\n',
            encoding='utf-8',
        )

        result = sprite.inflate_from_file(str(sprite_path))

        # '?' has no color, so it becomes magenta
        assert result == {
            'pixels': [(255, 0, 0), (0, 255, 0), (0, 255, 0), (255, 0, 255)],
            'width': 2,
            'height': 2,
            'name': 'tiny',
        }

    def test_bitmappy_sprite_save_static_only_method(self, tmp_path):
        """_save_static_only writes the sprite's pixels as TOML that loads back the same."""
        sprite = BitmappySprite(width=2, height=1, name='pair')
        sprite.pixels = [(255, 0, 0), (0, 0, 255)]
        saved_path = tmp_path / 'test.toml'

        sprite._save_static_only(str(saved_path))

        reloaded = BitmappySprite().inflate_from_file(str(saved_path))
        assert reloaded['name'] == 'pair'
        assert reloaded['pixels'] == [(255, 0, 0), (0, 0, 255)]

    def test_bitmappy_sprite_save_static_only_method_unsupported_format(self, mocker):
        """Test BitmappySprite save_static_only method with unsupported format."""
        sprite = BitmappySprite()

        mock_deflate = mocker.patch('glitchygames.sprites.BitmappySprite.deflate')
        mock_deflate.side_effect = ValueError('Unsupported format: xml')

        # Use pytest logger wrapper to suppress logs during successful runs
        mock_log = mocker.patch.object(sprite, 'log')
        with pytest.raises(ValueError, match='Unsupported format: xml'):
            sprite._save_static_only('test.xml')

        # Verify the EXCEPTION log message was called (inside except block)
        mock_log.exception.assert_called_once()
        # Check that the log message contains the expected content
        call_args = mock_log.exception.call_args[0][0]
        assert 'Error in save' in call_args

    def test_bitmappy_sprite_create_toml_config_coverage(self, mocker):
        """Test BitmappySprite create_toml_config coverage."""
        sprite = BitmappySprite()
        sprite.pixels = [(255, 0, 0), (0, 255, 0)]

        mocker.patch(
            'glitchygames.sprites.BitmappySprite._create_color_map',
            return_value={'A': (255, 0, 0), 'B': (0, 255, 0), 'X': (255, 0, 255)},
        )
        result = sprite._create_toml_config()
        assert 'sprite' in result


class TestBitmappySpriteHelpers:
    """Test BitmappySprite helper methods for save, pixel string, and color map."""

    def test_bitmappy_sprite_process_pixel_rows_missing_color(self, mocker):
        """Test BitmappySprite process_pixel_rows with missing color."""
        sprite = BitmappySprite(width=2, height=2)  # 2x2 = 4 pixels
        sprite.pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]  # 4 pixels

        mocker.patch(
            'glitchygames.sprites.BitmappySprite._create_color_map',
            return_value={'A': (255, 0, 0), 'X': (255, 0, 255)},  # Missing second color
        )
        color_map = {'A': (255, 0, 0), 'X': (255, 0, 255)}

        # Use pytest logger wrapper to suppress logs during successful runs
        mock_log = mocker.patch.object(sprite, 'log')
        result = sprite._process_pixel_rows(color_map)
        assert result is not None

        # Verify the ERROR log messages were called
        assert mock_log.error.call_count == EXPECTED_ERROR_COUNT_3
        # Check that the log messages contain the expected content
        first_call = mock_log.error.call_args_list[0][0][0]
        second_call = mock_log.error.call_args_list[1][0][0]
        third_call = mock_log.error.call_args_list[2][0][0]
        assert 'not found in color_map' in first_call
        assert 'not found in color_map' in second_call
        assert 'not found in color_map' in third_call

    def test_bitmappy_sprite_save_static_only_unsupported_format_error(self, mocker):
        """Test BitmappySprite save_static_only with unsupported format error."""
        sprite = BitmappySprite()

        mock_deflate = mocker.patch('glitchygames.sprites.BitmappySprite.deflate')
        mock_deflate.side_effect = ValueError('Unsupported format: xml')

        # Use pytest logger wrapper to suppress logs during successful runs
        mock_log = mocker.patch.object(sprite, 'log')
        with pytest.raises(ValueError, match='Unsupported format: xml'):
            sprite._save_static_only('test.xml')

        # Verify the EXCEPTION log message was called (inside except block)
        mock_log.exception.assert_called_once()
        # Check that the log message contains the expected content
        call_args = mock_log.exception.call_args[0][0]
        assert 'Error in save' in call_args

    def test_bitmappy_sprite_save_static_only_method_unsupported_format_json(self, mocker):
        """Test BitmappySprite save_static_only method with unsupported format."""
        sprite = BitmappySprite()

        mock_deflate = mocker.patch('glitchygames.sprites.BitmappySprite.deflate')
        mock_deflate.side_effect = ValueError('Unsupported format: json')

        # Use pytest logger wrapper to suppress logs during successful runs
        mock_log = mocker.patch.object(sprite, 'log')
        with pytest.raises(ValueError, match='Unsupported format: json'):
            sprite._save_static_only('test.json')

        # Verify the EXCEPTION log message was called (inside except block)
        mock_log.exception.assert_called_once()
        # Check that the log message contains the expected content
        call_args = mock_log.exception.call_args[0][0]
        assert 'Error in save' in call_args

    def test_get_pixel_string_method(self, mocker):
        """Test get_pixel_string method."""
        sprite = BitmappySprite(width=2, height=2)  # 2x2 = 4 pixels
        sprite.pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]  # 4 pixels

        mocker.patch(
            'glitchygames.sprites.BitmappySprite._create_color_map',
            return_value={'A': (255, 0, 0), 'B': (0, 255, 0), 'X': (255, 0, 255)},
        )
        result = sprite._get_pixel_string()  # type: ignore[unresolved-attribute]
        assert result is not None

    def test_get_pixel_string_method_no_pixels(self):
        """Test get_pixel_string method with no pixels."""
        sprite = BitmappySprite()
        sprite.pixels = []

        result = sprite._get_pixel_string()  # type: ignore[unresolved-attribute]
        assert not result

    def test_get_color_map_method(self):
        """Test get_color_map method."""
        sprite = BitmappySprite()
        sprite.pixels = [(255, 0, 0), (0, 255, 0)]

        result = sprite._get_color_map()  # type: ignore[unresolved-attribute]
        assert isinstance(result, dict)

    def test_get_color_map_method_no_pixels(self):
        """Test get_color_map method with no pixels."""
        sprite = BitmappySprite()
        sprite.pixels = []

        result = sprite._get_color_map()  # type: ignore[unresolved-attribute]
        assert result == {}


class TestSingleton:
    """Test Singleton functionality."""

    def test_singleton_creation(self):
        """Test singleton creation."""
        singleton = Singleton()
        assert isinstance(singleton, Singleton)


class TestSingletonBitmappySprite:
    """Test SingletonBitmappySprite functionality."""

    def test_singleton_bitmappy_sprite_creation(self):
        """Test SingletonBitmappySprite creation."""
        sprite = SingletonBitmappySprite()

        assert isinstance(sprite, SingletonBitmappySprite)
        assert isinstance(sprite, BitmappySprite)
        # The default size: a real 32x32 surface
        assert (sprite.pixels_across, sprite.pixels_tall) == (32, 32)
        assert sprite.image.get_size() == (32, 32)
        assert sprite.rect.size == (32, 32)
        assert not sprite.filename
        assert sprite.pixels == []


class TestFocusableSingletonBitmappySprite:
    """Test FocusableSingletonBitmappySprite functionality."""

    def test_focusable_singleton_bitmappy_sprite_creation(self):
        """Test FocusableSingletonBitmappySprite creation."""
        sprite = FocusableSingletonBitmappySprite()

        assert isinstance(sprite, FocusableSingletonBitmappySprite)
        assert isinstance(sprite, BitmappySprite)
        # The default size: a real 32x32 surface
        assert (sprite.pixels_across, sprite.pixels_tall) == (32, 32)
        assert sprite.image.get_size() == (32, 32)
        assert sprite.rect.size == (32, 32)
        assert not sprite.filename
        assert sprite.pixels == []
        assert sprite.focusable
