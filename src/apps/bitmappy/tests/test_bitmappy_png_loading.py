"""Tests for PNG loading functionality in bitmappy.py."""

import tempfile
import tomllib
import types
from pathlib import Path
from typing import cast

import pygame
import pytest

from bitmappy.animated_canvas import AnimatedCanvasSprite
from bitmappy.editor import BitmapEditorScene
from bitmappy.file_io import FileIOManager
from bitmappy.toml_processing import normalize_toml_data

# Test constants to avoid magic values
TEST_SIZE_64 = 64
TEST_SIZE_32 = 32
TEST_SIZE_1024 = 1024


class TestPNGLoading:
    """Test PNG loading functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up a BitmapEditorScene and canvas without their heavy setup."""
        # Store mocker first so it's available for use below
        self._mocker = mocker

        # Create a real BitmapEditorScene instance with mocked dependencies
        mocker.patch.object(BitmapEditorScene, '__init__', return_value=None)
        self.mock_scene = BitmapEditorScene({})
        self.mock_scene.log = mocker.Mock()
        self.mock_scene.all_sprites = []
        self.mock_scene.canvas = types.SimpleNamespace(pixels_across=32, pixels_tall=32)

        # Create a real AnimatedCanvasSprite instance with mocked dependencies
        mocker.patch.object(AnimatedCanvasSprite, '__init__', return_value=None)
        self.mock_canvas = AnimatedCanvasSprite()  # type: ignore[missing-argument]
        self.mock_canvas.log = mocker.Mock()
        self.mock_canvas.pixels_across = 32
        self.mock_canvas.pixels_tall = 32
        canvas_pixel_data = cast(
            'list[tuple[int, ...]]',
            [(255, 255, 255)] * (32 * 32),
        )  # White pixels
        self.mock_canvas.pixels = canvas_pixel_data  # type: ignore[invalid-assignment]
        self.mock_canvas.on_load_file_event = mocker.Mock()
        self.mock_canvas._update_border_thickness = mocker.Mock()
        self.mock_canvas.force_redraw = mocker.Mock()
        self.mock_canvas.parent = self.mock_scene
        # Attributes needed by __str__ and __repr__ inherited from parent classes
        self.mock_canvas.filename = None  # type: ignore[invalid-assignment]
        self.mock_canvas.name = 'test_canvas'

        self.mock_scene.all_sprites = [self.mock_canvas]

    def test_detect_png_file_in_load_function(self):
        """Test that PNG files are detected and converted in _load_sprite_from_file."""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_png:
            tmp_png_path = Path(tmp_png.name)
        tmp_png_path.write_bytes(b'fake png data')

        try:
            # _convert_png_to_bitmappy lives on the editor's file I/O delegate; the canvas
            # converts through its parent scene's (BUGS.md #89)
            mock_convert = self._mocker.Mock(return_value='mock_converted_file.toml')
            self.mock_scene._file_io = self._mocker.Mock(spec=FileIOManager)
            self.mock_scene._file_io._convert_png_to_bitmappy = mock_convert
            self.mock_canvas.parent_scene = self.mock_scene

            # Mock the AnimatedSprite.load method
            mock_sprite_class = self._mocker.patch(
                'bitmappy.animated_canvas.AnimatedSprite',
            )
            mock_sprite = self._mocker.Mock()
            # A sprite with something to draw: a load with nothing to draw is an error
            mock_sprite._animations = {'idle': [self._mocker.Mock()]}
            mock_sprite_class.return_value = mock_sprite

            # Call the method
            result = self.mock_canvas._load_sprite_from_file(str(tmp_png_path))

            # Verify PNG conversion was called
            mock_convert.assert_called_once_with(str(tmp_png_path))

            # Verify AnimatedSprite.load was called with the converted TOML path
            mock_sprite.load.assert_called_once_with('mock_converted_file.toml')

            assert result == mock_sprite
        finally:
            # Clean up
            tmp_png_path.unlink(missing_ok=True)

    def test_png_conversion_failure_handling(self):
        """Test that PNG conversion failures are handled gracefully."""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_png:
            tmp_png_path = Path(tmp_png.name)
        tmp_png_path.write_bytes(b'fake png data')

        try:
            # _convert_png_to_bitmappy lives on the editor's file I/O delegate; the canvas
            # converts through its parent scene's (BUGS.md #89)
            mock_convert = self._mocker.Mock(return_value=None)
            self.mock_scene._file_io = self._mocker.Mock(spec=FileIOManager)
            self.mock_scene._file_io._convert_png_to_bitmappy = mock_convert
            self.mock_canvas.parent_scene = self.mock_scene

            with pytest.raises(ValueError, match='Failed to convert PNG to bitmappy format'):
                self.mock_canvas._load_sprite_from_file(str(tmp_png_path))
        finally:
            tmp_png_path.unlink(missing_ok=True)

    def test_non_png_files_passthrough(self):
        """Test that non-PNG files are passed through unchanged."""
        mock_sprite_class = self._mocker.patch(
            'bitmappy.animated_canvas.AnimatedSprite',
        )
        mock_sprite = self._mocker.Mock()
        # A sprite with something to draw: a load with nothing to draw is an error
        mock_sprite._animations = {'idle': [self._mocker.Mock()]}
        mock_sprite_class.return_value = mock_sprite

        # Call with a TOML file
        result = self.mock_canvas._load_sprite_from_file('/path/to/test.toml')

        # Should not call PNG conversion (since it's a TOML file, not PNG)
        # The method exists but shouldn't be called for non-PNG files

        # Should call AnimatedSprite.load with original filename
        mock_sprite.load.assert_called_once_with('/path/to/test.toml')
        assert result == mock_sprite


class TestTOMLNormalization:
    """Test TOML normalization functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Keep the mocker fixture for the tests."""
        self._mocker = mocker

    def testnormalize_toml_data_with_escaped_newlines(self):
        """Test that escaped newlines are converted to actual newlines."""
        # Test data with escaped newlines
        config_data = {
            'sprite': {'name': 'test_sprite', 'pixels': 'ABC\\nDEF\\nGHI\\n'},
            'colors': {
                'A': {'red': 255, 'green': 0, 'blue': 0},
                'B': {'red': 0, 'green': 255, 'blue': 0},
            },
        }

        # Normalize the data
        normalized = normalize_toml_data(config_data)

        # Check that escaped newlines were converted
        assert normalized['sprite']['pixels'] == 'ABC\nDEF\nGHI\n'
        assert '\\n' not in normalized['sprite']['pixels']
        assert '\n' in normalized['sprite']['pixels']

    def testnormalize_toml_data_with_double_escaped_newlines(self):
        """Test that double-escaped newlines are converted to actual newlines."""
        # Test data with double-escaped newlines
        config_data = {'sprite': {'name': 'test_sprite', 'pixels': 'ABC\\\\nDEF\\\\nGHI\\\\n'}}

        # Normalize the data
        normalized = normalize_toml_data(config_data)

        # Check that double-escaped newlines were converted
        assert normalized['sprite']['pixels'] == 'ABC\nDEF\nGHI\n'
        assert '\\\\n' not in normalized['sprite']['pixels']
        assert '\n' in normalized['sprite']['pixels']

    def testnormalize_toml_data_with_animation_frames(self):
        """Test normalization with animation frame data."""
        config_data = {
            'animation': [
                {
                    'namespace': 'test_anim',
                    'frame_interval': 100,
                    'loop': True,
                    'frame': [
                        {'frame_index': 0, 'pixels': 'ABC\\nDEF\\nGHI\\n'},
                        {'frame_index': 1, 'pixels': 'XYZ\\n123\\n456\\n'},
                    ],
                },
            ],
        }

        # Normalize the data
        normalized = normalize_toml_data(config_data)

        # Check that both frames were normalized
        assert normalized['animation'][0]['frame'][0]['pixels'] == 'ABC\nDEF\nGHI\n'
        assert normalized['animation'][0]['frame'][1]['pixels'] == 'XYZ\n123\n456\n'

    def testnormalize_toml_data_error_handling(self):
        """Test that normalization handles errors gracefully."""
        # Test with invalid data structure
        config_data = 'invalid_data'

        # Should return original data on error
        result = normalize_toml_data(config_data)  # type: ignore[invalid-argument-type]
        assert result == config_data


class TestTOMLConstruction:
    """Test TOML construction with preserved formatting."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Keep the mocker fixture for the tests."""
        self._mocker = mocker

        # Create a real BitmapEditorScene instance with mocked dependencies
        mocker.patch.object(BitmapEditorScene, '__init__', return_value=None)
        self.mock_scene = BitmapEditorScene({})
        self.mock_scene.log = self._mocker.Mock()

        # Initialize extracted AI subsystem manager
        from bitmappy.ai_manager import AIManager

        mocker.patch.object(AIManager, '__init__', return_value=None)
        self.mock_scene._ai_integration = AIManager(self.mock_scene)  # type: ignore[arg-type]
        self.mock_scene._ai_integration.editor = self.mock_scene  # type: ignore[assignment]
        self.mock_scene._ai_integration.log = self._mocker.Mock()

    def test_construct_toml_with_sprite_section(self):
        """Test TOML construction with sprite section."""
        data = {
            'sprite': {
                'name': 'test_sprite',
                'description': 'A test sprite',
                'pixels': 'ABC\nDEF\nGHI\n',
            },
        }

        result = self.mock_scene._ai_integration._construct_toml_with_preserved_formatting(data)

        # Check that the TOML is properly formatted
        assert '[sprite]' in result
        assert 'name = "test_sprite"' in result
        assert 'description = """A test sprite"""' in result
        assert 'pixels = """' in result
        assert 'ABC\nDEF\nGHI\n' in result
        assert '"""' in result

    def test_construct_toml_with_animation_section(self):
        """Test TOML construction with animation section."""
        data = {
            'animation': [
                {
                    'namespace': 'test_anim',
                    'frame_interval': 100,
                    'loop': True,
                    'frame': [{'frame_index': 0, 'pixels': 'ABC\nDEF\nGHI\n'}],
                },
            ],
        }

        result = self.mock_scene._ai_integration._construct_toml_with_preserved_formatting(data)

        # Check animation structure
        assert '[[animation]]' in result
        assert 'namespace = "test_anim"' in result
        assert 'frame_interval = 100' in result
        assert 'loop = true' in result

        # Check frame structure
        assert '[[animation.frame]]' in result
        assert 'frame_index = 0' in result
        assert 'pixels = """' in result
        assert 'ABC\nDEF\nGHI\n' in result

    def test_construct_toml_with_colors_section(self):
        """Test TOML construction with colors section."""
        data = {
            'colors': {
                'A': {'red': 255, 'green': 0, 'blue': 0},
                'B': {'red': 0, 'green': 255, 'blue': 0},
            },
        }

        result = self.mock_scene._ai_integration._construct_toml_with_preserved_formatting(data)

        # Check colors structure
        assert '[colors]' in result
        assert '[colors."A"]' in result
        assert 'red = 255' in result
        assert 'green = 0' in result
        assert 'blue = 0' in result
        assert '[colors."B"]' in result

    def test_construct_toml_preserves_newlines(self):
        """Test that TOML construction preserves actual newlines in pixel data."""
        data = {'sprite': {'name': 'test', 'pixels': 'ABC\nDEF\nGHI\n'}}

        result = self.mock_scene._ai_integration._construct_toml_with_preserved_formatting(data)

        # Check that actual newlines are preserved (not escaped)
        assert 'ABC\nDEF\nGHI\n' in result
        assert 'ABC\\nDEF\\nGHI\\n' not in result


PNG_SIZE = 8
PNG_BLUE = (0, 0, 255)
PNG_RED = (255, 0, 0)
MAGENTA = (255, 0, 255)
TRANSPARENT_CORNER = pygame.Rect(0, 0, 2, 2)


def blue_left_red_right_surface():
    """Draw an 8x8 image, blue on the left half and red on the right half.

    Returns:
        pygame.Surface: The image, with an alpha channel.

    """
    surface = pygame.Surface((PNG_SIZE, PNG_SIZE), pygame.SRCALPHA)
    surface.fill((*PNG_RED, 255))
    surface.fill((*PNG_BLUE, 255), pygame.Rect(0, 0, PNG_SIZE // 2, PNG_SIZE))
    return surface


def decode_converted_sprite(toml_path):
    """Decode a converted sprite's pixels back into colours.

    Returns:
        list[list[tuple[int, int, int]]]: The colour of every pixel, row by row.

    """
    toml_data = tomllib.loads(Path(toml_path).read_text(encoding='utf-8'))
    glyph_colors = {
        glyph: (color['red'], color['green'], color['blue'])
        for glyph, color in toml_data['colors'].items()
    }
    return [
        [glyph_colors[glyph] for glyph in row] for row in toml_data['sprite']['pixels'].splitlines()
    ]


class TestPNGConversionIntegration:
    """Integration tests for PNG conversion, run on real PNG files."""

    @staticmethod
    def file_io_for_canvas_size(*, pixels_across, pixels_tall):
        """Create a FileIOManager whose editor canvas has the given size.

        Returns:
            FileIOManager: The manager; conversion reads only the canvas size.

        """
        editor = types.SimpleNamespace(
            canvas=types.SimpleNamespace(pixels_across=pixels_across, pixels_tall=pixels_tall),
        )
        return FileIOManager(editor)  # type: ignore[arg-type]

    def test_png_conversion_generates_valid_toml(self, tmp_path):
        """Test that PNG conversion writes a TOML sprite that decodes to the PNG's pixels."""
        png_path = tmp_path / 'blue_red.png'
        pygame.image.save(blue_left_red_right_surface(), str(png_path))
        file_io = self.file_io_for_canvas_size(pixels_across=PNG_SIZE, pixels_tall=PNG_SIZE)

        result = file_io._convert_png_to_bitmappy(str(png_path))

        assert result == str(tmp_path / 'blue_red.toml')
        content = Path(result).read_text(encoding='utf-8')
        # The pixels keep real newlines in a multi-line string, never escaped ones
        assert 'pixels = """' in content
        assert '\\n' not in content
        expected_row = [PNG_BLUE] * (PNG_SIZE // 2) + [PNG_RED] * (PNG_SIZE // 2)
        assert decode_converted_sprite(result) == [expected_row] * PNG_SIZE

    def test_png_conversion_handles_transparency(self, tmp_path):
        """Test that transparent PNG pixels become the magenta transparency key (BUGS.md #92)."""
        surface = blue_left_red_right_surface()
        surface.fill((0, 0, 0, 0), TRANSPARENT_CORNER)
        png_path = tmp_path / 'transparent_corner.png'
        pygame.image.save(surface, str(png_path))
        file_io = self.file_io_for_canvas_size(pixels_across=PNG_SIZE, pixels_tall=PNG_SIZE)

        result = file_io._convert_png_to_bitmappy(str(png_path))

        assert result is not None
        decoded_pixels = decode_converted_sprite(result)
        for row_index in range(TRANSPARENT_CORNER.height):
            for column_index in range(TRANSPARENT_CORNER.width):
                assert decoded_pixels[row_index][column_index] == MAGENTA


class TestDragAndDropPNG:
    """Test PNG drag and drop functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up a BitmapEditorScene and canvas without their heavy setup."""
        self._mocker = mocker

        # Create a real BitmapEditorScene instance with mocked dependencies
        mocker.patch.object(BitmapEditorScene, '__init__', return_value=None)
        self.mock_scene = BitmapEditorScene({})
        self.mock_scene.log = mocker.Mock()
        # A drop lands on the canvas when the mouse is over its rect; this rect covers the
        # whole mouse range, so the drop is on the canvas wherever the mouse is
        self.mock_scene.canvas = types.SimpleNamespace(
            pixels_across=32,
            pixels_tall=32,
            rect=pygame.Rect(-100_000, -100_000, 200_000, 200_000),
        )

        # Initialize extracted subsystem managers
        from bitmappy.file_io import FileIOManager

        self.mock_scene._file_io = FileIOManager(self.mock_scene)  # type: ignore[arg-type]

    def test_drag_drop_png_file(self):
        """Test drag and drop of PNG file."""
        # Create a simple PNG

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_png:
            tmp_png_path = Path(tmp_png.name)
        tmp_png_path.write_bytes(b'fake png data')

        try:
            # Mock the conversion and loading methods
            mock_convert = self._mocker.patch.object(
                self.mock_scene._file_io,
                '_convert_png_to_bitmappy',
            )
            mock_load = self._mocker.patch.object(
                self.mock_scene._file_io,
                '_load_converted_sprite',
            )

            mock_convert.return_value = '/tmp/test.toml'  # ruff: ignore[hardcoded-temp-file]

            # Create a mock event with the correct attribute
            class MockEvent:
                def __init__(self, file_path):
                    self.file = file_path

            mock_event = MockEvent(str(tmp_png_path))

            # Call the drag and drop handler
            self.mock_scene.on_drop_file_event(mock_event)  # type: ignore[invalid-argument-type]

            # Verify conversion was called
            mock_convert.assert_called_once_with(str(tmp_png_path))

            # Verify loading was called
            mock_load.assert_called_once_with('/tmp/test.toml')  # ruff: ignore[hardcoded-temp-file]
        finally:
            tmp_png_path.unlink(missing_ok=True)

    def test_drag_drop_non_png_file(self):
        """Test drag and drop of non-PNG file."""
        # Create a text file
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp_file:
            tmp_file_path = Path(tmp_file.name)
        tmp_file_path.write_bytes(b'Not a PNG file')

        try:
            # Mock the conversion method (should not be called)
            mock_convert = self._mocker.patch.object(
                self.mock_scene._file_io,
                '_convert_png_to_bitmappy',
            )

            # Create a mock event with the correct attribute
            class MockEvent:
                def __init__(self, file_path):
                    self.file = file_path

            mock_event = MockEvent(str(tmp_file_path))

            # Call the drag and drop handler
            self.mock_scene.on_drop_file_event(mock_event)  # type: ignore[invalid-argument-type]

            # Verify conversion was NOT called
            mock_convert.assert_not_called()
        finally:
            tmp_file_path.unlink(missing_ok=True)


def hundred_colour_pixels():
    """Build 32x32 pixels cycling through 100 distinct RGB colours.

    Returns:
        list[tuple[int, int, int]]: The pixels, row by row.

    """
    pixels = []
    for pixel_index in range(32 * 32):
        color_index = pixel_index % 100
        pixels.append(((color_index * 2) % 256, (color_index * 3) % 256, (color_index * 5) % 256))
    return pixels


class TestColorQuantization:
    """Test the frame TOML the AI is trained on, through the real AIManager."""

    @pytest.fixture(autouse=True)
    def setup_scene(self, mocker):
        """Build an editor with a 32x32 canvas of 100 colours and its AI manager."""
        self._mocker = mocker

        # A BitmapEditorScene without its heavy setup: the AI manager reads only its canvas
        mocker.patch.object(BitmapEditorScene, '__init__', return_value=None)
        self.mock_scene = BitmapEditorScene({})
        self.mock_scene.log = mocker.Mock()
        self.mock_scene.canvas = types.SimpleNamespace(
            pixels_across=32,
            pixels_tall=32,
            pixels=hundred_colour_pixels(),
        )

        from bitmappy.ai_manager import AIManager

        mocker.patch.object(AIManager, '__init__', return_value=None)
        self.mock_scene._ai_integration = AIManager(self.mock_scene)  # type: ignore[arg-type]
        self.mock_scene._ai_integration.editor = self.mock_scene  # type: ignore[assignment]
        self.mock_scene._ai_integration.log = mocker.Mock()

    def test_generate_frame_toml_without_quantization(self):
        """Without quantization, a frame of few colours keeps every colour and every pixel."""
        ten_colours = [(index * 2, index * 3, index * 5) for index in range(10)]
        pixels = (ten_colours * 103)[: 32 * 32]

        toml_content = self.mock_scene._ai_integration._generate_frame_toml_content(
            pixels,
            force_single_char_glyphs=False,
        )

        data = tomllib.loads(toml_content)
        assert data['sprite']['name'] == 'current_frame'
        colours = {
            (color['red'], color['green'], color['blue']) for color in data['colors'].values()
        }
        assert colours == set(ten_colours)
        rows = data['sprite']['pixels'].strip().split('\n')
        assert len(rows) == TEST_SIZE_32
        glyph_colours = {
            glyph: (color['red'], color['green'], color['blue'])
            for glyph, color in data['colors'].items()
        }
        assert [glyph_colours[glyph] for glyph in rows[0]] == pixels[:32]

    @pytest.mark.xfail(
        strict=True,
        reason=(
            'AIManager._generate_frame_toml_content(force_single_char_glyphs=False) writes one '
            '[colors."<glyph>"] table per colour, but past the 64 sprite glyphs several colours '
            'share a glyph, so the TOML declares a table twice and cannot be parsed'
        ),
    )
    def test_generate_frame_toml_without_quantization_many_colours_is_valid_toml(self):
        """Without quantization, more colours than glyphs must still produce valid TOML."""
        toml_content = self.mock_scene._ai_integration._generate_frame_toml_content(
            self.mock_scene.canvas.pixels,
            force_single_char_glyphs=False,
        )

        data = tomllib.loads(toml_content)
        assert len(data['colors']) <= TEST_SIZE_64

    def test_generate_frame_toml_with_quantization(self):
        """With quantization, 100 colours become at most 64 single-character glyphs."""
        toml_content = self.mock_scene._ai_integration._generate_frame_toml_content(
            self.mock_scene.canvas.pixels,
            force_single_char_glyphs=True,
        )

        data = tomllib.loads(toml_content)
        assert 1 < len(data['colors']) <= TEST_SIZE_64
        assert all(len(glyph) == 1 for glyph in data['colors'])
        rows = data['sprite']['pixels'].strip().split('\n')
        assert len(rows) == TEST_SIZE_32
        assert all(len(row) == TEST_SIZE_32 for row in rows)
        assert set(''.join(rows)) <= set(data['colors'])

    def test_save_current_frame_to_temp_toml_uses_quantization(self):
        """The frame saved for AI training is quantized to single-character glyphs."""
        temp_path = self.mock_scene._ai_integration._save_current_frame_to_temp_toml()

        assert temp_path is not None
        try:
            data = tomllib.loads(Path(temp_path).read_text(encoding='utf-8'))
        finally:
            Path(temp_path).unlink(missing_ok=True)
        assert len(data['colors']) <= TEST_SIZE_64
        assert all(len(glyph) == 1 for glyph in data['colors'])

    def test_color_quantization_preserves_most_common_colors(self):
        """Quantization keeps the colour most of the frame is painted in."""
        common_color = (255, 0, 0)
        rare_colors = [(index, index, index) for index in range(1, 100)]
        pixels = ([common_color] * 1000 + rare_colors)[:TEST_SIZE_1024]

        toml_content = self.mock_scene._ai_integration._generate_frame_toml_content(
            pixels,
            force_single_char_glyphs=True,
        )

        data = tomllib.loads(toml_content)
        assert {'red': 255, 'green': 0, 'blue': 0} in data['colors'].values()
        assert len(data['colors']) <= TEST_SIZE_64

    def test_color_quantization_handles_edge_cases(self):
        """A single-colour frame produces exactly one colour."""
        single_color_pixels = cast('list[tuple[int, ...]]', [(255, 0, 0)] * (32 * 32))

        toml_content = self.mock_scene._ai_integration._generate_frame_toml_content(
            single_color_pixels,
            force_single_char_glyphs=True,
        )

        data = tomllib.loads(toml_content)
        assert list(data['colors'].values()) == [{'red': 255, 'green': 0, 'blue': 0}]

    def test_color_quantization_with_integer_pixels(self):
        """Integer-packed RGB pixels are not a canvas pixel format: no TOML is produced.

        The canvas always holds colour tuples; packed integers fail while collecting the
        colours, which is logged, and the result is an empty string.
        """
        pixels = [
            (((index * 2) % 256) << 16) | (((index * 3) % 256) << 8) | ((index * 5) % 256)
            for index in range(32 * 32)
        ]

        toml_content = self.mock_scene._ai_integration._generate_frame_toml_content(
            pixels,  # type: ignore[arg-type]
            force_single_char_glyphs=True,
        )

        assert not toml_content
        self.mock_scene._ai_integration.log.exception.assert_called_once()


class TestDescriptionFeature:
    """Test sprite description loading and display functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Keep the mocker fixture for the tests."""
        # Store mocker for use in test methods
        self._mocker = mocker

    def test_description_loading_from_toml(self):
        """Test that description is properly loaded from TOML files."""
        # Create a test TOML file with a description
        test_toml_content = '''[sprite]
name = "test_sprite"
description = "A test sprite with a description"
pixels = """
@@@
@@@
@@@
"""

[colors."@"]
red = 255
green = 0
blue = 255
'''

        # Create temporary TOML file
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.toml',
            delete=False,
            encoding='utf-8',
        ) as f:
            f.write(test_toml_content)
            temp_path = f.name

        try:
            # Load the TOML file
            data = tomllib.loads(Path(temp_path).read_text(encoding='utf-8'))

            # Extract description
            description = data.get('sprite', {}).get('description', '')

            # Verify description was loaded correctly
            assert description == 'A test sprite with a description'

        finally:
            # Clean up
            Path(temp_path).unlink()

    def test_description_display_in_ai_textbox(self):
        """Test that sprite description is displayed in AI textbox when loading."""
        # Create a real BitmapEditorScene instance with mocked dependencies
        self._mocker.patch.object(BitmapEditorScene, '__init__', return_value=None)
        scene = BitmapEditorScene({})
        scene.log = self._mocker.Mock()
        scene.all_sprites = []
        scene.canvas = types.SimpleNamespace(pixels_across=32, pixels_tall=32)

        # Create a mock debug_text (AI textbox)
        scene.debug_text = self._mocker.Mock()
        scene.debug_text.text = 'Enter a description of the sprite you want to create:'

        # Create a real AnimatedCanvasSprite instance with mocked dependencies
        self._mocker.patch.object(AnimatedCanvasSprite, '__init__', return_value=None)
        canvas = AnimatedCanvasSprite()  # type: ignore[missing-argument]
        canvas.log = self._mocker.Mock()
        canvas.pixels_across = 32
        canvas.pixels_tall = 32
        canvas_pixel_data = cast('list[tuple[int, ...]]', [(255, 255, 255)] * (32 * 32))
        canvas.pixels = canvas_pixel_data  # type: ignore[invalid-assignment]
        canvas.parent_scene = scene
        # Mock required methods and attributes
        canvas.force_redraw = self._mocker.Mock()
        canvas._copy_sprite_to_canvas = self._mocker.Mock()
        canvas._update_mini_view_from_current_frame = self._mocker.Mock()  # type: ignore[unresolved-attribute]
        canvas.dirty = 1

        # Create a mock loaded sprite with description
        loaded_sprite = self._mocker.Mock()
        loaded_sprite.description = 'A test sprite description'

        # Test the _finalize_sprite_loading method
        canvas._finalize_sprite_loading(loaded_sprite, 'test.toml')

        # Verify that the AI textbox was updated with the description
        assert scene.debug_text.text == 'A test sprite description'

    def test_empty_description_falls_back_to_default(self):
        """Test that empty description falls back to default prompt."""
        # Create a real BitmapEditorScene instance with mocked dependencies
        self._mocker.patch.object(BitmapEditorScene, '__init__', return_value=None)
        scene = BitmapEditorScene({})
        scene.log = self._mocker.Mock()
        scene.all_sprites = []
        scene.canvas = types.SimpleNamespace(pixels_across=32, pixels_tall=32)

        # Create a mock debug_text (AI textbox)
        scene.debug_text = self._mocker.Mock()
        scene.debug_text.text = 'Enter a description of the sprite you want to create:'

        # Create a real AnimatedCanvasSprite instance with mocked dependencies
        self._mocker.patch.object(AnimatedCanvasSprite, '__init__', return_value=None)
        canvas = AnimatedCanvasSprite()  # type: ignore[missing-argument]
        canvas.log = self._mocker.Mock()
        canvas.pixels_across = 32
        canvas.pixels_tall = 32
        canvas_pixel_data = cast('list[tuple[int, ...]]', [(255, 255, 255)] * (32 * 32))
        canvas.pixels = canvas_pixel_data  # type: ignore[invalid-assignment]
        canvas.parent_scene = scene
        # Mock required methods and attributes
        canvas.force_redraw = self._mocker.Mock()
        canvas._copy_sprite_to_canvas = self._mocker.Mock()
        canvas._update_mini_view_from_current_frame = self._mocker.Mock()  # type: ignore[unresolved-attribute]
        canvas.dirty = 1

        # Create a mock loaded sprite with empty description
        loaded_sprite = self._mocker.Mock()
        loaded_sprite.description = ''

        # Test the _finalize_sprite_loading method
        canvas._finalize_sprite_loading(loaded_sprite, 'test.toml')

        # Verify that the AI textbox shows the default prompt
        assert scene.debug_text.text == 'Enter a description of the sprite you want to create:'

    def test_whitespace_only_description_falls_back_to_default(self):
        """Test that whitespace-only description falls back to default prompt."""
        # Create a real BitmapEditorScene instance with mocked dependencies
        self._mocker.patch.object(BitmapEditorScene, '__init__', return_value=None)
        scene = BitmapEditorScene({})
        scene.log = self._mocker.Mock()
        scene.all_sprites = []
        scene.canvas = types.SimpleNamespace(pixels_across=32, pixels_tall=32)

        # Create a mock debug_text (AI textbox)
        scene.debug_text = self._mocker.Mock()
        scene.debug_text.text = 'Enter a description of the sprite you want to create:'

        # Create a real AnimatedCanvasSprite instance with mocked dependencies
        self._mocker.patch.object(AnimatedCanvasSprite, '__init__', return_value=None)
        canvas = AnimatedCanvasSprite()  # type: ignore[missing-argument]
        canvas.log = self._mocker.Mock()
        canvas.pixels_across = 32
        canvas.pixels_tall = 32
        canvas_pixel_data = cast('list[tuple[int, ...]]', [(255, 255, 255)] * (32 * 32))
        canvas.pixels = canvas_pixel_data  # type: ignore[invalid-assignment]
        canvas.parent_scene = scene
        # Mock required methods and attributes
        canvas.force_redraw = self._mocker.Mock()
        canvas._copy_sprite_to_canvas = self._mocker.Mock()
        canvas._update_mini_view_from_current_frame = self._mocker.Mock()  # type: ignore[unresolved-attribute]
        canvas.dirty = 1

        # Create a mock loaded sprite with whitespace-only description
        loaded_sprite = self._mocker.Mock()
        loaded_sprite.description = '   \n\t   '

        # Test the _finalize_sprite_loading method
        canvas._finalize_sprite_loading(loaded_sprite, 'test.toml')

        # Verify that the AI textbox shows the default prompt
        assert scene.debug_text.text == 'Enter a description of the sprite you want to create:'


if __name__ == '__main__':
    pytest.main([__file__])
