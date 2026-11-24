"""Sprite factory and loading tests."""

import pygame
import pytest

from glitchygames.sprites import AnimatedSprite, BitmappySprite, SpriteFactory, SpriteFrame
from glitchygames.sprites import factory as factory_module
from glitchygames.sprites import sprite_toml as sprite_toml_module

RED = (255, 0, 0)

_COLORS_TOML = (
    '[colors."a"]\nred = 1\ngreen = 2\nblue = 3\n\n[colors."b"]\nred = 4\ngreen = 5\nblue = 6\n'
)
ANIMATED_SPRITE_TOML = (
    '[sprite]\nname = "square"\n\n[[animation]]\nnamespace = "walk"\n\n'
    '[[animation.frame]]\nframe_index = 0\npixels = """\nab\n"""\n\n'
    f'{_COLORS_TOML}'
)
# Static pixels in [sprite] and an animation both: the factory refuses it, the loader does not
MIXED_SPRITE_TOML = (
    '[sprite]\nname = "mixed"\npixels = """\nab\n"""\n\n[[animation]]\nnamespace = "walk"\n\n'
    '[[animation.frame]]\nframe_index = 0\npixels = """\nab\n"""\n\n'
    f'{_COLORS_TOML}'
)
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

    def test_analyze_toml_file_animation(self, tmp_path):
        """Test analyzing TOML file with animation."""
        sprite_file = tmp_path / 'test.toml'
        sprite_file.write_text(
            """
            [sprite]
            pixels = [1, 2, 3]

            [animations.walk]
            frames = [1, 2, 3]
            """,
            encoding='utf-8',
        )

        result = SpriteFactory._get_toml_data(str(sprite_file))
        assert 'sprite' in result
        assert 'animations' in result

    def test_analyze_toml_file_basic(self, tmp_path):
        """Test analyzing basic TOML file."""
        sprite_file = tmp_path / 'test.toml'
        sprite_file.write_text(
            """
            [sprite]
            pixels = [1, 2, 3]
            """,
            encoding='utf-8',
        )

        result = SpriteFactory._get_toml_data(str(sprite_file))
        assert 'sprite' in result
        assert 'animations' not in result

    def test_analyze_toml_file_empty_pixels(self, tmp_path):
        """Test analyzing TOML file with empty pixels."""
        sprite_file = tmp_path / 'test.toml'
        sprite_file.write_text(
            """
            [sprite]
            pixels = []
            """,
            encoding='utf-8',
        )

        result = SpriteFactory._get_toml_data(str(sprite_file))
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

    def test_load_sprite_refuses_a_file_that_is_not_toml(self, tmp_path):
        """Only TOML sprite files load: another format is refused before the file is read."""
        yaml_file = tmp_path / 'sprite.yaml'
        yaml_file.write_text('sprite: {}\n', encoding='utf-8')

        with pytest.raises(ValueError, match='Unsupported format: yaml'):
            SpriteFactory.load_sprite(filename=str(yaml_file))

    def test_load_sprite_mixed_content(self, tmp_path):
        """A file with static pixels and animations both is refused."""
        mixed_file = tmp_path / 'mixed.toml'
        mixed_file.write_text(MIXED_SPRITE_TOML, encoding='utf-8')

        with pytest.raises(ValueError, match='Invalid sprite file'):
            SpriteFactory.load_sprite(filename=str(mixed_file))

    def test_sprite_factory_load_sprite_invalid_file(self):
        """Test SpriteFactory load_sprite with invalid file."""
        with pytest.raises(FileNotFoundError):
            SpriteFactory.load_sprite(filename='nonexistent.toml')

    def test_sprite_factory_analyze_toml_file_with_sprite_pixels(self, tmp_path):
        """Test analyzing TOML file with sprite pixels."""
        sprite_file = tmp_path / 'test.toml'
        sprite_file.write_text(
            """
            [sprite]
            pixels = [1, 2, 3, 4, 5, 6]
            """,
            encoding='utf-8',
        )

        result = SpriteFactory._get_toml_data(str(sprite_file))
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


class TestLoadSpriteParsesOnce:
    """load_sprite checks a file's content on the parse its load makes, kept with the compile."""

    def test_two_loads_of_a_file_parse_it_once(self, tmp_path, mocker):
        """The first load parses the file once; the second, from the compile, not at all."""
        sprite_file = tmp_path / 'square.toml'
        sprite_file.write_text(ANIMATED_SPRITE_TOML, encoding='utf-8')
        factory_parses = mocker.spy(factory_module, 'parse_sprite_toml')
        loader_parses = mocker.spy(sprite_toml_module, 'parse_sprite_toml')

        SpriteFactory.load_sprite(filename=str(sprite_file))
        SpriteFactory.load_sprite(filename=str(sprite_file))

        assert factory_parses.call_count + loader_parses.call_count == 1

    def test_text_loads_parse_once_too(self, mocker):
        """load_sprite_from_text checks on the same one parse."""
        factory_parses = mocker.spy(factory_module, 'parse_sprite_toml')
        loader_parses = mocker.spy(sprite_toml_module, 'parse_sprite_toml')

        SpriteFactory.load_sprite_from_text(text=ANIMATED_SPRITE_TOML, source_name='square')
        SpriteFactory.load_sprite_from_text(text=ANIMATED_SPRITE_TOML, source_name='square')

        assert factory_parses.call_count + loader_parses.call_count == 1

    def test_a_file_compiled_without_the_check_is_still_refused(self, tmp_path):
        """A plain load keeps a mixed file's compile; load_sprite still refuses the file."""
        mixed_file = tmp_path / 'mixed.toml'
        mixed_file.write_text(MIXED_SPRITE_TOML, encoding='utf-8')
        AnimatedSprite(str(mixed_file))

        with pytest.raises(ValueError, match='Invalid sprite file'):
            SpriteFactory.load_sprite(filename=str(mixed_file))

    def test_a_refused_file_loads_as_a_plain_sprite_afterwards(self, tmp_path):
        """A refusal keeps nothing: a plain load of the same file still loads it."""
        mixed_file = tmp_path / 'mixed.toml'
        mixed_file.write_text(MIXED_SPRITE_TOML, encoding='utf-8')
        with pytest.raises(ValueError, match='Invalid sprite file'):
            SpriteFactory.load_sprite(filename=str(mixed_file))

        sprite = AnimatedSprite(str(mixed_file))

        assert list(sprite.animation_data) == ['walk']


@pytest.mark.parametrize('line_end', ['\r\n', '\r'], ids=['crlf', 'lone-cr'])
def test_a_crlf_sprite_file_loads_as_an_lf_one(tmp_path, line_end):
    """Windows' CRLF and old Macs' lone CR are read as line feeds before parsing."""
    text = (
        '[sprite]\nname = "two_colors"\npixels = """\nRG\nGR\n"""\n'
        '[colors.R]\nred = 255\ngreen = 0\nblue = 0\n'
        '[colors.G]\nred = 0\ngreen = 255\nblue = 0\n'
    )
    lf_path = tmp_path / 'lf.toml'
    lf_path.write_bytes(text.encode('utf-8'))
    other_path = tmp_path / 'other.toml'
    other_path.write_bytes(text.replace('\n', line_end).encode('utf-8'))

    from_lf = SpriteFactory.load_sprite(filename=str(lf_path))
    from_other = SpriteFactory.load_sprite(filename=str(other_path))

    assert pygame.image.tobytes(from_other.image, 'RGBA') == pygame.image.tobytes(
        from_lf.image, 'RGBA'
    )
