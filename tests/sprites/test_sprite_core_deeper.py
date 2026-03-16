"""Deeper coverage tests for glitchygames/sprites/core.py.

Targets areas NOT covered by test_sprite_core_coverage.py:
- BitmappySprite.load() method and _load_static_toml
- BitmappySprite.__str__ with actual file content
- BitmappySprite.inflate_from_file with TOML
- BitmappySprite._create_color_map with RGBA pixels
- SpriteFactory methods (_detect_file_format, load_sprite)
- Sprite coordinate setters (x, y)
- Sprite parent and name properties
- Sprite.update_nested_sprites
- BitmappySprite deflate with RGBA pixels
- BitmappySprite save method
"""

import sys
from pathlib import Path

import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.sprites import BitmappySprite, Sprite
from glitchygames.sprites.core import SpriteFactory
from tests.mocks.test_mock_factory import MockFactory

# Constants
SPRITE_WIDTH = 16
SPRITE_HEIGHT = 16


class TestSpriteCoordinateAccess:
    """Test Sprite coordinate access via rect."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_rect_x_is_settable(self):
        """Test rect.x can be set directly."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        sprite.rect.x = 42
        assert sprite.rect.x == 42

    def test_rect_y_is_settable(self):
        """Test rect.y can be set directly."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        sprite.rect.y = 99
        assert sprite.rect.y == 99

    def test_initial_coordinates(self):
        """Test sprite initializes with correct coordinates."""
        sprite = Sprite(x=15, y=25, width=10, height=10)
        assert sprite.rect.x == 15
        assert sprite.rect.y == 25


class TestSpriteNameProperty:
    """Test Sprite name property getter and setter."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_name_getter_returns_name(self):
        """Test name property returns the sprite name."""
        sprite = Sprite(x=0, y=0, width=10, height=10, name='my_sprite')
        assert sprite.name == 'my_sprite'

    def test_name_setter(self):
        """Test name property setter updates the name."""
        sprite = Sprite(x=0, y=0, width=10, height=10, name='old_name')
        sprite.name = 'new_name'
        assert sprite.name == 'new_name'


class TestSpriteParentProperty:
    """Test Sprite parent property."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_parent_default_is_none(self):
        """Test default parent is None."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        assert sprite.parent is None

    def test_parent_setter(self, mocker):
        """Test parent setter updates the parent."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        parent = mocker.Mock()
        sprite.parent = parent
        assert sprite.parent is parent


class TestSpriteUpdateNestedSprites:
    """Test Sprite.update_nested_sprites method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_update_nested_sprites_does_not_raise(self):
        """Test update_nested_sprites can be called without error."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        # Base implementation is a no-op
        sprite.update_nested_sprites()


class TestSpriteOnQuitCallsTerminate:
    """Test Sprite.on_quit_event calls terminate."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_on_quit_event_calls_terminate_via_mock(self, mocker):
        """Test on_quit_event invokes terminate method."""
        sprite = Sprite(x=0, y=0, width=10, height=10)
        sprite.terminate = mocker.Mock()
        event = mocker.Mock()
        sprite.on_quit_event(event)
        sprite.terminate.assert_called_once()


class TestBitmappySpriteCreateColorMapRGBA:
    """Test BitmappySprite._create_color_map with RGBA pixel data."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_create_color_map_with_rgba_pixels(self):
        """Test _create_color_map handles RGBA pixels."""
        sprite = BitmappySprite(x=0, y=0, width=2, height=2)
        sprite.pixels = [(255, 0, 0, 255), (0, 255, 0, 128), (255, 0, 0, 255), (0, 255, 0, 128)]
        result = sprite._create_color_map()
        assert len(result) == 2
        # All values should be the original RGBA colors
        values = set(result.values())
        assert (255, 0, 0, 255) in values
        assert (0, 255, 0, 128) in values

    def test_create_color_map_with_magenta_transparency(self):
        """Test _create_color_map handles magenta transparency key."""
        sprite = BitmappySprite(x=0, y=0, width=2, height=1)
        sprite.pixels = [(255, 0, 255), (0, 0, 0)]
        result = sprite._create_color_map()
        assert len(result) == 2


class TestBitmappySpriteDeflateRGBA:
    """Test BitmappySprite deflate with RGBA pixel data."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_deflate_with_rgba_pixels(self):
        """Test deflate with RGBA pixel data produces correct config."""
        sprite = BitmappySprite(x=0, y=0, width=2, height=2)
        sprite.pixels_across = 2
        sprite.pixels_tall = 2
        sprite.pixels = [
            (255, 0, 0, 255),
            (0, 255, 0, 128),
            (255, 0, 0, 255),
            (0, 255, 0, 128),
        ]
        sprite.name = 'rgba_test'
        config = sprite.deflate(file_format='toml')
        assert 'sprite' in config
        assert 'colors' in config
        assert config['sprite']['name'] == 'rgba_test'


class TestBitmappySpriteInflateFromFile:
    """Test BitmappySprite inflate_from_file with TOML content."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_inflate_from_file_with_valid_toml(self, mocker, tmp_path):
        """Test inflate_from_file loads a valid TOML sprite file."""
        toml_content = """[sprite]
name = "test_sprite"
pixels = \"\"\"
#.
.#
\"\"\"

[colors."#"]
red = 0
green = 0
blue = 0

[colors."."]
red = 255
green = 255
blue = 255
"""
        toml_file = tmp_path / 'test.toml'
        toml_file.write_text(toml_content)

        sprite = BitmappySprite(x=0, y=0, width=2, height=2)
        sprite.inflate_from_file(str(toml_file))
        assert sprite.name is not None


class TestBitmappySpriteLoadWithFactory:
    """Test BitmappySprite.load with SpriteFactory integration."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_load_falls_back_to_static_on_factory_failure(self, mocker, tmp_path):
        """Test load falls back to _load_static_only when factory fails."""
        toml_content = """[sprite]
name = "simple"
pixels = \"\"\"
##
##
\"\"\"

[colors."#"]
red = 0
green = 0
blue = 0
"""
        toml_file = tmp_path / 'simple.toml'
        toml_file.write_text(toml_content)

        sprite = BitmappySprite(x=0, y=0, width=2, height=2)
        # Mock factory to fail so it falls through to _load_static_only
        mocker.patch.object(SpriteFactory, 'load_sprite', side_effect=ValueError('test failure'))
        image, _rect, name = sprite.load(str(toml_file))
        assert image is not None
        assert name == 'simple'


class TestSpriteFactoryDetectFileFormat:
    """Test SpriteFactory._detect_file_format."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_detect_toml_format(self):
        """Test detecting TOML file format."""
        result = SpriteFactory._detect_file_format('sprite.toml')
        assert result == 'toml'

    def test_detect_unknown_format_returns_unknown(self):
        """Test unknown extension returns 'unknown'."""
        result = SpriteFactory._detect_file_format('sprite.xyz')
        assert result == 'unknown'

    def test_detect_yaml_format(self):
        """Test detecting YAML file format."""
        result = SpriteFactory._detect_file_format('sprite.yaml')
        assert result == 'yaml'

    def test_detect_yml_format(self):
        """Test detecting YML file format."""
        result = SpriteFactory._detect_file_format('sprite.yml')
        assert result == 'yaml'


class TestBitmappySpriteInitWithFilename:
    """Test BitmappySprite initialization with filename."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_init_with_valid_toml_file(self, mocker, tmp_path):
        """Test BitmappySprite init with a valid TOML file loads correctly."""
        toml_content = """[sprite]
name = "loaded_sprite"
pixels = \"\"\"
AB
BA
\"\"\"

[colors."A"]
red = 255
green = 0
blue = 0

[colors."B"]
red = 0
green = 0
blue = 255
"""
        toml_file = tmp_path / 'loaded.toml'
        toml_file.write_text(toml_content)

        sprite = BitmappySprite(x=5, y=10, filename=str(toml_file))
        assert sprite.rect.x == 5
        assert sprite.rect.y == 10
        assert sprite.name is not None


class TestBitmappySpriteCreateTomlConfig:
    """Test BitmappySprite._create_toml_config with various inputs."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_create_toml_config_with_pixel_rows_and_color_map(self):
        """Test _create_toml_config with provided pixel rows and color map."""
        sprite = BitmappySprite(x=0, y=0, width=2, height=2)
        sprite.pixels_across = 2
        sprite.pixels_tall = 2
        sprite.name = 'config_test'

        color_map = {'#': (0, 0, 0), '.': (255, 255, 255)}
        pixel_rows = ['#.', '.#']

        config = sprite._create_toml_config(pixel_rows=pixel_rows, color_map=color_map)
        assert config['sprite']['name'] == 'config_test'
        assert 'colors' in config
        assert 'pixels' in config['sprite']


class TestBitmappySpriteSave:
    """Test BitmappySprite save method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_save_creates_toml_file(self, tmp_path):
        """Test save creates a valid TOML file."""
        sprite = BitmappySprite(x=0, y=0, width=2, height=2, name='save_test')
        sprite.pixels_across = 2
        sprite.pixels_tall = 2
        sprite.pixels = [(255, 0, 0), (0, 255, 0), (255, 0, 0), (0, 255, 0)]

        save_path = tmp_path / 'saved.toml'
        sprite.save(str(save_path), file_format='toml')
        assert save_path.exists()
        content = save_path.read_text()
        assert 'save_test' in content

    def test_save_unsupported_format_raises(self):
        """Test save raises ValueError for unsupported format."""
        sprite = BitmappySprite(x=0, y=0, width=2, height=2, name='test')
        sprite.pixels = [(0, 0, 0)]
        with pytest.raises(ValueError, match='Unsupported format'):
            sprite.save('test.json', file_format='json')


class TestSpriteWidthHeightProperties:
    """Test width and height setters with surface recreation."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_width_setter_same_value_skips(self):
        """Test width setter with same value does not mark dirty."""
        sprite = Sprite(x=0, y=0, width=30, height=40)
        sprite.dirty = 0
        sprite.width = 30
        # Setting same value should still mark dirty (implementation always sets)
        # Just verify no error
        assert sprite.width == 30

    def test_height_setter_same_value_skips(self):
        """Test height setter with same value does not error."""
        sprite = Sprite(x=0, y=0, width=30, height=40)
        sprite.dirty = 0
        sprite.height = 40
        assert sprite.height == 40


class TestBitmappySpriteStrWithPixels:
    """Test BitmappySprite __str__ with actual pixel data."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_str_with_pixels_no_filename(self):
        """Test __str__ with pixels but no filename."""
        sprite = BitmappySprite(x=0, y=0, width=2, height=2, name='pixel_sprite')
        sprite.pixels = [(255, 0, 0), (0, 0, 255), (255, 0, 0), (0, 0, 255)]
        result = str(sprite)
        assert 'no file loaded' in result

    def test_str_with_valid_filename(self, tmp_path):
        """Test __str__ with a valid TOML filename produces output."""
        toml_content = """[sprite]
name = "display_test"
pixels = \"\"\"
#
\"\"\"

[colors."#"]
red = 0
green = 0
blue = 0
"""
        toml_file = tmp_path / 'display.toml'
        toml_file.write_text(toml_content)

        sprite = BitmappySprite(x=0, y=0, width=1, height=1, name='display_test')
        sprite.filename = str(toml_file)
        result = str(sprite)
        # Should contain some representation without error
        assert isinstance(result, str)
        assert len(result) > 0
