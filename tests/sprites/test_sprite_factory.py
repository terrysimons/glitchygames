"""Sprite factory and loading tests."""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.sprites import AnimatedSprite, BitmappySprite, SpriteFactory, SpriteFrame

RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)


def _rgb_rows(image):
    """Return an image's RGB pixels, row by row.

    Returns:
        list[list[tuple[int, int, int]]]: ``rows[y][x]``.

    """
    rows = pygame.surfarray.array3d(image).transpose(1, 0, 2).tolist()
    return [[tuple(pixel) for pixel in row] for row in rows]


def _solid_rgb(image):
    """Return the one RGB color an image is filled with (fails if it has more than one).

    Returns:
        tuple[int, int, int]: The image's only color.

    """
    unique_colors = {pixel for row in _rgb_rows(image) for pixel in row}
    assert len(unique_colors) == 1, f'expected one color, got {sorted(unique_colors)}'
    return unique_colors.pop()


def _two_color_static_sprite():
    """Create a 2x2 BitmappySprite: red, with a green bottom-right pixel.

    Returns:
        BitmappySprite: The sprite.

    """
    sprite = BitmappySprite(width=2, height=2, name='static_two')
    sprite.image.fill(RED)
    sprite.image.set_at((1, 1), GREEN)
    sprite.pixels = [RED, RED, RED, GREEN]
    return sprite


def _two_frame_animated_sprite():
    """Create an AnimatedSprite with a 'walk' animation: a red frame then a blue one.

    Returns:
        AnimatedSprite: The sprite.

    """
    frames = []
    for color, duration in ((RED, 0.25), (BLUE, 0.5)):
        surface = pygame.Surface((2, 2))
        surface.fill(color)
        frame = SpriteFrame(surface, duration=duration)
        frame.pixels = [color] * 4
        frames.append(frame)
    sprite = AnimatedSprite()
    sprite.name = 'walker'
    sprite.add_animation('walk', frames)
    return sprite


class TestSpriteFactory:
    """Test SpriteFactory functionality."""

    def test_get_default_sprite_path(self):
        """Test getting default sprite path."""
        path = SpriteFactory._get_default_sprite_path()

        assert isinstance(path, str)
        assert path.endswith('.toml')

    def test_determine_type_animated(self):
        """Test determining animated sprite type."""
        analysis = {
            'has_sprite_pixels': False,
            'has_animation_sections': True,
            'has_frame_sections': False,
        }

        sprite_type = SpriteFactory._determine_type(analysis)
        assert sprite_type == 'animated'

    def test_determine_type_static(self):
        """Test determining static sprite type."""
        analysis = {
            'has_sprite_pixels': True,
            'has_animation_sections': False,
            'has_frame_sections': False,
        }

        sprite_type = SpriteFactory._determine_type(analysis)
        assert sprite_type == 'static'

    def test_determine_type_error(self):
        """Test determining sprite type with error."""
        analysis = {
            'has_sprite_pixels': False,
            'has_animation_sections': False,
            'has_frame_sections': False,
        }

        sprite_type = SpriteFactory._determine_type(analysis)
        assert sprite_type == 'error'

    def test_save_sprite_animated(self, tmp_path):
        """save_sprite writes an AnimatedSprite's animations; loading draws the same frames."""
        sprite_path = tmp_path / 'walker.toml'
        SpriteFactory.save_sprite(
            sprite=_two_frame_animated_sprite(), filename=str(sprite_path), file_format='toml'
        )

        loaded = SpriteFactory.load_sprite(filename=str(sprite_path))
        assert list(loaded.animations) == ['walk']
        assert [frame.duration for frame in loaded.animations['walk']] == [0.25, 0.5]
        assert [_solid_rgb(frame.image) for frame in loaded.animations['walk']] == [
            RED,
            BLUE,
        ]

    def test_save_sprite_static(self, tmp_path):
        """save_sprite writes a BitmappySprite's pixels; loading draws the same image."""
        sprite_path = tmp_path / 'static.toml'
        SpriteFactory.save_sprite(
            sprite=_two_color_static_sprite(), filename=str(sprite_path), file_format='toml'
        )

        loaded = SpriteFactory.load_sprite(filename=str(sprite_path))
        assert _rgb_rows(loaded.image) == [[RED, RED], [RED, GREEN]]

    def test_save_static_sprite(self, tmp_path):
        """_save_static_sprite writes the sprite's own TOML (its _save)."""
        sprite_path = tmp_path / 'static.toml'
        SpriteFactory._save_static_sprite(_two_color_static_sprite(), str(sprite_path), 'toml')

        saved_text = sprite_path.read_text(encoding='utf-8')
        assert 'name = "static_two"' in saved_text
        loaded = SpriteFactory.load_sprite(filename=str(sprite_path))
        assert _rgb_rows(loaded.image) == [[RED, RED], [RED, GREEN]]

    def test_save_animated_sprite(self, tmp_path):
        """_save_animated_sprite writes every frame of every animation."""
        sprite_path = tmp_path / 'walker.toml'
        SpriteFactory._save_animated_sprite(_two_frame_animated_sprite(), str(sprite_path), 'toml')

        loaded = SpriteFactory.load_sprite(filename=str(sprite_path))
        assert [_solid_rgb(frame.image) for frame in loaded.animations['walk']] == [
            RED,
            BLUE,
        ]

    def test_analyze_file_with_nonexistent_file(self):
        """Test analyzing nonexistent file."""
        with pytest.raises(FileNotFoundError):
            SpriteFactory._analyze_file('nonexistent.toml')

    def test_analyze_toml_file_animation(self, mocker):
        """Test analyzing TOML file with animation."""
        mock_open = mocker.patch('pathlib.Path.open')
        mock_open.return_value.__enter__.return_value.read.return_value = b"""
            [sprite]
            pixels = [1, 2, 3]

            [animations.walk]
            frames = [1, 2, 3]
            """

        result = SpriteFactory._get_toml_data('test.toml')
        assert 'sprite' in result
        assert 'animations' in result

    def test_analyze_toml_file_basic(self, mocker):
        """Test analyzing basic TOML file."""
        mock_open = mocker.patch('pathlib.Path.open')
        mock_open.return_value.__enter__.return_value.read.return_value = b"""
            [sprite]
            pixels = [1, 2, 3]
            """

        result = SpriteFactory._get_toml_data('test.toml')
        assert 'sprite' in result
        assert 'animations' not in result

    def test_analyze_toml_file_empty_pixels(self, mocker):
        """Test analyzing TOML file with empty pixels."""
        mock_open = mocker.patch('pathlib.Path.open')
        mock_open.return_value.__enter__.return_value.read.return_value = b"""
            [sprite]
            pixels = []
            """

        result = SpriteFactory._get_toml_data('test.toml')
        assert 'sprite' in result

    def test_detect_file_format_default(self):
        """Test detecting default file format."""
        format_type = SpriteFactory.detect_file_format('test.toml')
        assert format_type == 'toml'

    def test_detect_file_format_unknown(self):
        """Test detecting unknown file format."""
        format_type = SpriteFactory.detect_file_format('test.unknown')
        assert format_type == 'unknown'

    def test_load_sprite_invalid_file(self):
        """Test loading sprite from invalid file."""
        with pytest.raises(FileNotFoundError):
            SpriteFactory.load_sprite(filename='nonexistent.toml')

    def test_load_sprite_mixed_content(self, mocker):
        """Test loading sprite with mixed content."""
        mocker.patch(
            'glitchygames.sprites.SpriteFactory._analyze_file',
            return_value={
                'has_sprite_pixels': True,
                'has_animation_sections': True,
                'has_frame_sections': False,
            },
        )

        with pytest.raises(ValueError, match='Invalid sprite file'):
            SpriteFactory.load_sprite(filename='mixed.toml')

    def test_sprite_factory_load_sprite_invalid_file(self):
        """Test SpriteFactory load_sprite with invalid file."""
        with pytest.raises(FileNotFoundError):
            SpriteFactory.load_sprite(filename='nonexistent.toml')

    def test_sprite_factory_analyze_toml_file_with_sprite_pixels(self, mocker):
        """Test analyzing TOML file with sprite pixels."""
        mock_open = mocker.patch('pathlib.Path.open')
        mock_open.return_value.__enter__.return_value.read.return_value = b"""
            [sprite]
            pixels = [1, 2, 3, 4, 5, 6]
            """

        result = SpriteFactory._get_toml_data('test.toml')
        assert 'sprite' in result
        assert result['sprite']['pixels'] == [1, 2, 3, 4, 5, 6]


class TestSpriteFactoryAnalyzeFrameSections:
    """_analyze_toml_file looks for frame tables in every animation (real files)."""

    def test_analyze_toml_file_animation_without_frames(self, tmp_path):
        """Animation tables with no frame tables report no frame sections."""
        sprite_file = tmp_path / 'frameless.toml'
        sprite_file.write_text(
            '[[animation]]\nnamespace = "idle"\n\n[[animation]]\nnamespace = "walk"\n',
            encoding='utf-8',
        )
        result = SpriteFactory._analyze_toml_file(str(sprite_file))
        assert result['has_animation_sections'] is True
        assert result['has_frame_sections'] is False
        assert result['has_sprite_pixels'] is False

    def test_analyze_toml_file_finds_frames_in_a_later_animation(self, tmp_path):
        """A frame table in any animation, not just the first, counts as a frame section."""
        sprite_file = tmp_path / 'late_frames.toml'
        sprite_file.write_text(
            '[[animation]]\nnamespace = "idle"\n\n'
            '[[animation]]\nnamespace = "walk"\n\n'
            '[[animation.frame]]\npixels = "#"\n',
            encoding='utf-8',
        )
        result = SpriteFactory._analyze_toml_file(str(sprite_file))
        assert result['has_frame_sections'] is True
