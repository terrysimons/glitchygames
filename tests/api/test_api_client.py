"""Tests for the GlitchyGames API client module."""

import argparse
import base64
import binascii
import logging
from pathlib import Path

import pytest

from glitchygames.api import sprite_requests
from glitchygames.api.client import (
    _handle_extract_frames,
    _handle_generate_sprite,
    _log_extraction_metadata,
    _save_apng_extracted_frames,
    _save_extracted_frames,
    create_apng_from_frames,
    create_parser,
    display_sprite_ascii,
    extract_frames,
    find_available_directory,
    find_available_path,
    generate_sprite,
    main,
    save_files_locally,
)
from glitchygames.exit_codes import ExitCode
from glitchygames.services import AIProviderError
from tests.services.stand_in_ai_client import FakeAIClient


class TestCreateParser:
    """Tests for the CLI argument parser."""

    def test_parser_creation(self):
        """Test that the parser is created with expected arguments."""
        parser = create_parser()
        assert parser.prog == 'glitchygames-client'

    def test_parser_with_prompt(self):
        """Test parsing a simple prompt argument."""
        parser = create_parser()
        parsed_args = parser.parse_args(['a red heart sprite'])
        assert parsed_args.prompt == 'a red heart sprite'

    def test_parser_defaults(self):
        """Test parser default values."""
        parser = create_parser()
        parsed_args = parser.parse_args(['test prompt'])
        assert parsed_args.output_formats is None
        assert parsed_args.output_path is None
        assert parsed_args.width is None
        assert parsed_args.height is None
        assert parsed_args.frame_count is None
        assert parsed_args.film_strip_count is None
        assert parsed_args.animation_duration is None
        assert parsed_args.png_scale == 1
        assert parsed_args.extract_scale == 8
        assert parsed_args.verbose is False
        assert parsed_args.quiet is False

    def test_parser_with_all_options(self, tmp_path):
        """Test parsing with all options specified."""
        output_path = str(tmp_path / 'output')
        parser = create_parser()
        parsed_args = parser.parse_args([
            'test',
            '--output-format',
            'toml',
            '--output-format',
            'png',
            '--output-path',
            output_path,
            '--width',
            '32',
            '--height',
            '32',
            '--frame-count',
            '4',
            '--film-strip-count',
            '2',
            '--animation-duration',
            '1.5',
            '--png-scale',
            '4',
            '--extract-scale',
            '16',
            '--animation-language-model',
            'anthropic:claude-sonnet-4-5',
            '--verbose',
        ])
        assert parsed_args.output_formats == ['toml', 'png']
        assert parsed_args.output_path == output_path
        assert parsed_args.width == 32
        assert parsed_args.height == 32
        assert parsed_args.frame_count == 4
        assert parsed_args.film_strip_count == 2
        assert parsed_args.animation_duration == pytest.approx(1.5)
        assert parsed_args.png_scale == 4
        assert parsed_args.extract_scale == 16
        assert parsed_args.animation_language_model == 'anthropic:claude-sonnet-4-5'
        assert parsed_args.verbose is True

    def test_parser_extract_frames_flag(self):
        """Test parsing with --extract-frames flag."""
        parser = create_parser()
        parsed_args = parser.parse_args(['--extract-frames', 'sprite.apng'])
        assert parsed_args.extract_frames == 'sprite.apng'
        assert parsed_args.prompt is None

    def test_parser_short_flags(self, tmp_path):
        """Test parsing with short flag variants."""
        output_path = str(tmp_path)
        parser = create_parser()
        parsed_args = parser.parse_args(['test', '-f', 'toml', '-o', output_path, '-v'])
        assert parsed_args.output_formats == ['toml']
        assert parsed_args.output_path == output_path
        assert parsed_args.verbose is True

    def test_parser_quiet_flag(self):
        """Test parsing with quiet flag."""
        parser = create_parser()
        parsed_args = parser.parse_args(['test', '-q'])
        assert parsed_args.quiet is True


class TestGenerateSprite:
    """Tests for the generate_sprite function: the sprite request, in this process."""

    def test_generate_sprite_basic(self, ai_answering):
        """The AI's sprite comes back as the response's fields."""
        ai_answering(A_STATIC_SPRITE)

        result = generate_sprite(prompt='a red heart', output_formats=['toml'])

        assert result['success'] is True
        assert result['sprite_name'] == 'heart'
        assert 'name = "heart"' in result['toml_content']

    def test_generate_sprite_with_optional_params(self, ai_answering, mocker):
        """Every option reaches the request the sprite requests are given."""
        ai_answering(A_STATIC_SPRITE)
        generate_response = mocker.spy(sprite_requests, 'generate_response')

        generate_sprite(
            prompt='test',
            output_formats=['toml', 'png'],
            width=16,
            height=16,
            frame_count=4,
            film_strip_count=2,
            animation_duration=2.0,
            png_scale=2,
            model='bonsai-2-9b',
        )

        request = generate_response.call_args.args[0]
        assert request.prompt == 'test'
        assert request.output_format == ['toml', 'png']
        assert (request.width, request.height) == (16, 16)
        assert (request.frame_count, request.film_strip_count) == (4, 2)
        assert request.animation_duration == pytest.approx(2.0)
        assert request.png_scale == 2
        assert request.model == 'bonsai-2-9b'
        assert request.output_path is None  # files are saved by the client, never the request


class TestExtractFrames:
    """Tests for the extract_frames function: an APNG or a .toml sprite, in this process."""

    def test_extract_frames_of_a_png(self, tmp_path):
        """A plain PNG is an APNG of one frame."""
        from PIL import Image

        image_path = tmp_path / 'dot.png'
        Image.new('RGBA', (3, 2), (255, 0, 0, 255)).save(image_path)

        result = extract_frames(str(image_path))

        assert result['success'] is True
        assert result['frame_count'] == 1
        assert (result['width'], result['height']) == (3, 2)

    def test_extract_frames_of_a_toml_sprite(self, tmp_path):
        """A .toml file is read as a sprite, its frames rendered."""
        sprite = tmp_path / 'blink.toml'
        sprite.write_text(A_TWO_FRAME_SPRITE, encoding='utf-8')

        result = extract_frames(str(sprite))

        assert result['success'] is True
        assert [frame['delay_ms'] for frame in result['frames']] == [250, 250]


class TestFindAvailablePath:
    """Tests for the find_available_path function."""

    def test_path_does_not_exist(self, tmp_path):
        """Test that non-existent path is returned as-is."""
        path = tmp_path / 'nonexistent.toml'
        result = find_available_path(path)
        assert result == path

    def test_path_exists_increments(self, tmp_path):
        """Test that existing path gets incremented suffix."""
        path = tmp_path / 'sprite.toml'
        path.touch()

        result = find_available_path(path)
        assert result == tmp_path / 'sprite_001.toml'

    def test_path_exists_multiple_increments(self, tmp_path):
        """Test incrementing when multiple files exist."""
        path = tmp_path / 'sprite.toml'
        path.touch()
        (tmp_path / 'sprite_001.toml').touch()
        (tmp_path / 'sprite_002.toml').touch()

        result = find_available_path(path)
        assert result == tmp_path / 'sprite_003.toml'


class TestFindAvailableDirectory:
    """Tests for the find_available_directory function."""

    def test_first_directory(self, tmp_path):
        """Test first available directory gets -001 suffix."""
        base_dir = tmp_path / 'sprite'
        result = find_available_directory(base_dir)
        assert result == tmp_path / 'sprite-001'

    def test_directory_increments(self, tmp_path):
        """Test incrementing when directories already exist."""
        base_dir = tmp_path / 'sprite'
        (tmp_path / 'sprite-001').mkdir()
        (tmp_path / 'sprite-002').mkdir()

        result = find_available_directory(base_dir)
        assert result == tmp_path / 'sprite-003'


class TestDisplaySpriteAscii:
    """Tests for the display_sprite_ascii function."""

    def test_display_static_sprite(self, mocker, capsys):
        """Test displaying a static sprite as ASCII."""
        mock_renderer = mocker.Mock()
        mock_renderer.extract_colors_from_toml.return_value = {'#': (255, 0, 0)}
        mock_renderer.extract_pixels_from_toml.return_value = '##\n##'
        mock_renderer.colorize_pixels.return_value = '##\n##'

        mocker.patch(
            'glitchygames.api.client.ASCIIRenderer',
            return_value=mock_renderer,
        )

        toml_content = '''
[sprite]
name = "test"
pixels = """
##
##
"""

[colors."#"]
red = 255
green = 0
blue = 0
'''
        display_sprite_ascii(toml_content)
        captured = capsys.readouterr()
        assert 'Sprite Preview' in captured.out

    def test_display_invalid_toml_logs_warning(self):
        """Test that invalid TOML content logs a warning instead of crashing."""
        # display_sprite_ascii catches exceptions internally
        display_sprite_ascii('not valid toml {{{}}}')
        # Should not raise

    def test_display_animated_sprite(self, mocker, capsys):
        """Test displaying an animated sprite."""
        mock_renderer = mocker.Mock()
        mock_renderer.extract_colors_from_toml.return_value = {'#': (255, 0, 0)}
        mock_renderer.colorize_pixels.return_value = '##'

        mocker.patch(
            'glitchygames.api.client.ASCIIRenderer',
            return_value=mock_renderer,
        )

        toml_content = """
[[animation]]
namespace = "walk"

[[animation.frame]]
pixels = "##"
"""
        display_sprite_ascii(toml_content)
        captured = capsys.readouterr()
        assert 'Animation: walk' in captured.out

    def test_animated_frame_without_pixels_is_left_out(self, capsys):
        """A frame with no pixels gets no preview; the frames around it still do."""
        toml_content = """
[[animation]]
namespace = "walk"

[[animation.frame]]
pixels = ""

[[animation.frame]]
pixels = "#"

[colors."#"]
red = 255
green = 0
blue = 0
"""
        display_sprite_ascii(toml_content)

        printed = capsys.readouterr().out
        assert 'Animation: walk (2 frames)' in printed
        assert 'Frame 0' not in printed
        assert 'Frame 1' in printed

    def test_static_sprite_without_pixels_prints_no_preview(self, capsys):
        """A static sprite with no pixels prints no preview heading."""
        toml_content = """
[sprite]
name = "empty"
"""
        display_sprite_ascii(toml_content)

        assert 'Sprite Preview' not in capsys.readouterr().out


class TestCreateApngFromFrames:
    """Tests for the create_apng_from_frames function."""

    def test_create_apng_from_frames(self, mocker):
        """Test creating APNG from base64-encoded frames."""
        # Create minimal PNG data and mock the apng library
        mock_apng_instance = mocker.Mock()

        mocker.patch('glitchygames.api.client.APNG', return_value=mock_apng_instance)
        mocker.patch('glitchygames.api.client.PNG')

        # Mock save to write some bytes
        def mock_save(buffer):
            buffer.write(b'fake_apng_data')

        mock_apng_instance.save.side_effect = mock_save

        fake_frame_base64 = base64.b64encode(b'fake_png').decode('utf-8')
        result = create_apng_from_frames([fake_frame_base64], frame_delay_ms=200)

        assert result == b'fake_apng_data'
        mock_apng_instance.append.assert_called_once()


class TestSaveFilesLocally:
    """Tests for the save_files_locally function."""

    def test_save_toml_file(self, tmp_path):
        """Test saving TOML content to file."""
        response = {
            'sprite_name': 'test_sprite',
            'toml_content': '[sprite]\nname = "test"',
        }

        saved = save_files_locally(
            response=response,
            output_path=str(tmp_path),
            output_formats=['toml'],
        )

        assert len(saved) == 1
        assert saved[0].endswith('.toml')
        assert Path(saved[0]).exists()
        assert Path(saved[0]).read_text(encoding='utf-8') == '[sprite]\nname = "test"'

    def test_save_png_file(self, tmp_path):
        """Test saving PNG from base64 data."""
        fake_png_data = base64.b64encode(b'fake_png_bytes').decode('utf-8')
        response = {
            'sprite_name': 'test_sprite',
            'png_base64': fake_png_data,
        }

        saved = save_files_locally(
            response=response,
            output_path=str(tmp_path),
            output_formats=['png'],
        )

        assert len(saved) == 1
        assert saved[0].endswith('.png')

    def test_save_sanitizes_sprite_name(self, tmp_path):
        """Test that sprite names with special characters are sanitized."""
        response = {
            'sprite_name': 'test/sprite<>with:special|chars',
            'toml_content': 'test',
        }

        saved = save_files_locally(
            response=response,
            output_path=str(tmp_path),
            output_formats=['toml'],
        )

        assert len(saved) == 1
        # The path should not contain special characters
        assert '<' not in saved[0]
        assert '>' not in saved[0]

    def test_save_empty_sprite_name_fallback(self, tmp_path):
        """Test fallback when sprite name sanitizes to empty."""
        response = {
            'sprite_name': '/<>:',
            'toml_content': 'test',
        }

        saved = save_files_locally(
            response=response,
            output_path=str(tmp_path),
            output_formats=['toml'],
        )

        assert len(saved) == 1
        # Should use 'sprite' as fallback
        assert 'sprite' in saved[0]

    def test_save_empty_sprite_name_uses_sprite(self, tmp_path):
        """An empty sprite name, which sanitizes to nothing, saves as 'sprite'."""
        response = {'sprite_name': '', 'toml_content': 'test'}

        saved = save_files_locally(
            response=response,
            output_path=str(tmp_path),
            output_formats=['toml'],
        )

        assert saved == [str(tmp_path / 'sprite-001' / 'sprite.toml')]


class TestMainCli:
    """Tests for the main CLI entrypoint."""

    def test_main_no_prompt_no_extract_exits_error(self, capsys):
        """Test that missing prompt and no --extract-frames is argparse's usage error."""
        with pytest.raises(SystemExit) as exit_info:
            main([])
        assert exit_info.value.code == ExitCode.ARGUMENT_PARSER_ERROR
        assert 'prompt is required unless using --extract-frames' in capsys.readouterr().err

    @pytest.mark.parametrize(
        ('request_error_factory', 'expected_exit_code'),
        [
            (lambda: AIProviderError('down', provider='local'), ExitCode.SERVICE_UNAVAILABLE),
            (lambda: FileNotFoundError(2, 'No such file', 'x.png'), ExitCode.MISSING_INPUT),
            (lambda: PermissionError(13, 'Permission denied'), ExitCode.UNUSABLE_INPUT),
            (
                lambda: UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'invalid start byte'),
                ExitCode.UNUSABLE_INPUT,
            ),
        ],
        ids=['ai service', 'missing file', 'unreadable file', 'undecodable file'],
    )
    def test_main_request_errors_never_escape(
        self, mocker, request_error_factory, expected_exit_code
    ):
        """Every error a request can raise maps to a named code (nothing escapes as Python's 1)."""
        mocker.patch('glitchygames.api.client.generate_sprite', side_effect=request_error_factory())

        assert main(['test prompt']) == expected_exit_code

    def test_main_a_toml_that_is_not_text_is_unusable_input(self, tmp_path):
        """A .toml whose bytes are not UTF-8 cannot be read as a sprite."""
        not_text = tmp_path / 'binary.toml'
        not_text.write_bytes(b'\xff\xfe\x00 not text')

        assert main(['--extract-frames', str(not_text)]) == ExitCode.UNUSABLE_INPUT

    def test_main_extract_frames_from_a_directory_is_unusable_input(self, tmp_path):
        """An input path that exists but cannot be read as a file is unusable, not missing."""
        assert main(['--extract-frames', str(tmp_path)]) == ExitCode.UNUSABLE_INPUT

    def test_main_generate_success(self, mocker):
        """Test successful sprite generation via CLI."""
        mocker.patch(
            'glitchygames.api.client.generate_sprite',
            return_value={
                'success': True,
                'sprite_name': 'test_heart',
                'toml_content': '[sprite]\nname = "test"',
            },
        )
        mocker.patch('glitchygames.api.client.display_sprite_ascii')

        result = main(['test prompt', '-q'])
        assert result == ExitCode.SUCCESS

    def test_main_generate_failure(self, mocker):
        """Test handling of failed generation response."""
        mocker.patch(
            'glitchygames.api.client.generate_sprite',
            return_value={
                'success': False,
                'error': 'Generation failed',
            },
        )

        result = main(['test prompt', '-q'])
        assert result == ExitCode.GENERATION_REJECTED

    def test_main_extract_frames_file_not_found(self):
        """Test extract-frames with missing file."""
        result = main(['--extract-frames', '/nonexistent/file.apng'])
        assert result == ExitCode.MISSING_INPUT

    def test_main_verbose_logging(self, mocker):
        """Test verbose mode enables debug logging."""
        mocker.patch(
            'glitchygames.api.client.generate_sprite',
            return_value={'success': True, 'sprite_name': 'test'},
        )
        mocker.patch('glitchygames.api.client.display_sprite_ascii')

        result = main(['test prompt', '-v'])
        assert result == ExitCode.SUCCESS


class TestLogExtractionMetadata:
    """Tests for _log_extraction_metadata function (on the messages as logged)."""

    @staticmethod
    def _logged_info(caplog, response):
        """Return the INFO messages _log_extraction_metadata logs for response, as formatted.

        Returns:
            list[str]: The messages.

        """
        with caplog.at_level(logging.INFO, logger='glitchygames.api.client'):
            _log_extraction_metadata(response)
        return [record.getMessage() for record in caplog.records if record.levelno == logging.INFO]

    def test_logs_frame_count(self, caplog):
        """Test that frame count is logged."""
        assert 'Extracted 5 frames' in self._logged_info(caplog, {'frame_count': 5})

    def test_logs_canvas_size(self, caplog):
        """Test that canvas size is logged when width and height present."""
        messages = self._logged_info(caplog, {'frame_count': 3, 'width': 32, 'height': 32})

        assert '  Canvas size: 32x32 pixels' in messages

    def test_skips_canvas_size_when_missing(self, caplog):
        """Test that canvas size is not logged when width or height missing."""
        messages = self._logged_info(caplog, {'frame_count': 3, 'width': 32})

        # Should only have frame count log, not canvas size
        assert not any('Canvas size' in message for message in messages)

    def test_logs_total_duration(self, caplog):
        """Test that total duration is logged when present."""
        messages = self._logged_info(caplog, {'frame_count': 3, 'total_duration_ms': 500})

        assert '  Total duration: 500ms' in messages

    def test_logs_infinite_loop_count(self, caplog):
        """Test that loop_count of 0 is logged as infinite."""
        messages = self._logged_info(caplog, {'frame_count': 3, 'loop_count': 0})

        assert '  Loop count: infinite' in messages

    def test_logs_finite_loop_count(self, caplog):
        """Test that non-zero loop_count is logged as a number."""
        messages = self._logged_info(caplog, {'frame_count': 3, 'loop_count': 5})

        assert '  Loop count: 5' in messages

    def test_skips_loop_count_when_none(self, caplog):
        """Test that loop_count is not logged when not present."""
        messages = self._logged_info(caplog, {'frame_count': 3})

        assert not any('Loop count' in message for message in messages)


class TestSaveApngExtractedFrames:
    """Tests for _save_apng_extracted_frames function."""

    def test_saves_frames_to_output_directory(self, tmp_path):
        """Test that frames are saved as numbered PNG files."""
        # Create minimal base64 PNG data
        fake_png_data = base64.b64encode(b'\x89PNG\r\n\x1a\nfake').decode('utf-8')
        response = {
            'frames': [
                {'index': 0, 'png_base64': fake_png_data},
                {'index': 1, 'png_base64': fake_png_data},
            ],
        }

        output_dir = tmp_path / 'extracted'
        _save_apng_extracted_frames(response, str(output_dir), '/path/to/sprite.apng')

        assert (output_dir / 'sprite_frame_000.png').exists()
        assert (output_dir / 'sprite_frame_001.png').exists()

    def test_creates_output_directory_if_missing(self, tmp_path):
        """Test that output directory is created if it does not exist."""
        response = {'frames': []}
        output_dir = tmp_path / 'nested' / 'output'

        _save_apng_extracted_frames(response, str(output_dir), '/path/to/test.apng')

        assert output_dir.exists()

    def test_handles_empty_frames_list(self, tmp_path):
        """Test that an empty frames list does not cause errors."""
        response = {'frames': []}
        output_dir = tmp_path / 'empty'

        _save_apng_extracted_frames(response, str(output_dir), '/path/to/test.apng')

        assert output_dir.exists()


class TestSaveExtractedFrames:
    """Tests for _save_extracted_frames function."""

    def test_saves_frames_with_metadata(self, tmp_path, mocker):
        """Test that frames are saved with PNG metadata embedded."""
        mock_image = mocker.Mock()
        mock_image.width = 16
        mock_image.height = 16

        # PIL is imported locally inside _save_extracted_frames, so mock at PIL level
        mocker.patch('PIL.Image.open', return_value=mock_image)
        mock_png_info_class = mocker.patch('PIL.PngImagePlugin.PngInfo')
        mock_png_info_instance = mock_png_info_class.return_value

        fake_frame_data = base64.b64encode(b'fake_png').decode('utf-8')
        frame_entries = [
            ('animation-0-frame-0', '0', '0', fake_frame_data),
            ('animation-0-frame-1', '0', '1', fake_frame_data),
        ]

        result = _save_extracted_frames(
            frame_entries=frame_entries,
            extracted_dir=tmp_path,
            frame_count=2,
            frame_delay_ms=100,
            extract_scale=1,
            model_used='test-model',
        )

        assert len(result) == 2
        assert mock_image.save.call_count == 2
        # Verify metadata was added including AIModel
        add_text_calls = [call.args for call in mock_png_info_instance.add_text.call_args_list]
        keys_added = [call[0] for call in add_text_calls]
        assert 'AIModel' in keys_added
        assert 'FrameName' in keys_added

    def test_saves_frames_without_model_metadata(self, tmp_path, mocker):
        """Test that frames are saved without AIModel when model_used is None."""
        mock_image = mocker.Mock()
        mock_image.width = 16
        mock_image.height = 16

        mocker.patch('PIL.Image.open', return_value=mock_image)
        mock_png_info_class = mocker.patch('PIL.PngImagePlugin.PngInfo')
        mock_png_info_instance = mock_png_info_class.return_value

        fake_frame_data = base64.b64encode(b'fake_png').decode('utf-8')
        frame_entries = [
            ('animation-0-frame-0', '0', '0', fake_frame_data),
        ]

        _save_extracted_frames(
            frame_entries=frame_entries,
            extracted_dir=tmp_path,
            frame_count=1,
            frame_delay_ms=100,
            extract_scale=1,
            model_used=None,
        )

        add_text_calls = [call.args for call in mock_png_info_instance.add_text.call_args_list]
        keys_added = [call[0] for call in add_text_calls]
        assert 'AIModel' not in keys_added

    def test_upscales_frames_when_scale_greater_than_one(self, tmp_path, mocker):
        """Test that frames are upscaled with nearest-neighbor when extract_scale > 1."""
        from PIL import Image as RealImageModule

        mock_image = mocker.Mock()
        mock_image.width = 8
        mock_image.height = 8
        mock_resized_image = mocker.Mock()
        mock_image.resize.return_value = mock_resized_image

        mocker.patch('PIL.Image.open', return_value=mock_image)
        mocker.patch('PIL.PngImagePlugin.PngInfo')

        fake_frame_data = base64.b64encode(b'fake_png').decode('utf-8')
        frame_entries = [
            ('animation-0-frame-0', '0', '0', fake_frame_data),
        ]

        _save_extracted_frames(
            frame_entries=frame_entries,
            extracted_dir=tmp_path,
            frame_count=1,
            frame_delay_ms=100,
            extract_scale=4,
            model_used=None,
        )

        mock_image.resize.assert_called_once_with((32, 32), RealImageModule.NEAREST)  # type: ignore[unresolved-attribute]


class TestSaveFilesLocallyAnimatedFrames:
    """Tests for save_files_locally with animation frames."""

    def test_save_animated_frames_with_rendered_frames(self, tmp_path, mocker):
        """Test saving animated sprite with rendered_frames metadata."""
        mock_apng_creator = mocker.patch('glitchygames.api.client.create_apng_from_frames')
        mock_apng_creator.return_value = b'fake_apng'

        mock_save_extracted = mocker.patch('glitchygames.api.client._save_extracted_frames')
        mock_save_extracted.return_value = ['/path/to/frame0.png']

        fake_frame_data = base64.b64encode(b'fake_png').decode('utf-8')
        response = {
            'sprite_name': 'animated_sprite',
            'toml_content': '[sprite]\nname = "test"',
            'all_frames_png_base64': [fake_frame_data, fake_frame_data],
            'rendered_frames': [
                {'animation_index': 0, 'frame_index': 0, 'png_base64': fake_frame_data},
                {'animation_index': 0, 'frame_index': 1, 'png_base64': fake_frame_data},
            ],
        }

        saved = save_files_locally(
            response=response,
            output_path=str(tmp_path),
            output_formats=['toml', 'png'],
            animation_duration=0.5,
            extract_scale=4,
            model_used='test-model',
        )

        # TOML + APNG + extracted frames
        assert any(path.endswith('.toml') for path in saved)
        assert any(path.endswith('.apng') for path in saved)
        mock_save_extracted.assert_called_once()

        # Verify frame delay calculation from animation_duration
        call_kwargs = mock_save_extracted.call_args.kwargs
        assert call_kwargs['frame_delay_ms'] == 250  # 500ms / 2 frames

    def test_save_animated_frames_without_rendered_frames_fallback(self, tmp_path, mocker):
        """Test saving animated sprite falls back to old naming without rendered_frames."""
        mock_apng_creator = mocker.patch('glitchygames.api.client.create_apng_from_frames')
        mock_apng_creator.return_value = b'fake_apng'

        mock_save_extracted = mocker.patch('glitchygames.api.client._save_extracted_frames')
        mock_save_extracted.return_value = []

        fake_frame_data = base64.b64encode(b'fake_png').decode('utf-8')
        response = {
            'sprite_name': 'animated_sprite',
            'all_frames_png_base64': [fake_frame_data],
            # No rendered_frames key - should use fallback naming
        }

        save_files_locally(
            response=response,
            output_path=str(tmp_path),
            output_formats=['png'],
        )

        # Verify fallback frame entries format
        call_kwargs = mock_save_extracted.call_args.kwargs
        frame_entries = call_kwargs['frame_entries']
        assert frame_entries[0][0] == 'animation-0-frame-0'
        assert frame_entries[0][1] == '0'
        assert frame_entries[0][2] == '0'

    def test_save_default_frame_delay_without_animation_duration(self, tmp_path, mocker):
        """Test that default 100ms frame delay is used when no animation_duration."""
        mock_apng_creator = mocker.patch('glitchygames.api.client.create_apng_from_frames')
        mock_apng_creator.return_value = b'fake_apng'

        mock_save_extracted = mocker.patch('glitchygames.api.client._save_extracted_frames')
        mock_save_extracted.return_value = []

        fake_frame_data = base64.b64encode(b'fake_png').decode('utf-8')
        response = {
            'sprite_name': 'test',
            'all_frames_png_base64': [fake_frame_data],
        }

        save_files_locally(
            response=response,
            output_path=str(tmp_path),
            output_formats=['png'],
            animation_duration=None,
        )

        call_kwargs = mock_save_extracted.call_args.kwargs
        assert call_kwargs['frame_delay_ms'] == 100

    def test_save_missing_sprite_name_uses_default(self, tmp_path):
        """Test that missing sprite_name in response uses 'sprite' default."""
        response = {
            'toml_content': 'test = true',
        }

        saved = save_files_locally(
            response=response,
            output_path=str(tmp_path),
            output_formats=['toml'],
        )

        assert len(saved) == 1
        assert 'sprite' in saved[0]


class TestFindAvailablePathTimestampFallback:
    """Tests for find_available_path timestamp fallback."""

    def test_timestamp_fallback_when_many_files_exist(self, tmp_path, mocker):
        """Test that timestamp is used when MAX_FILE_NUMBERING_ATTEMPTS files exist."""
        mocker.patch('glitchygames.api.client.MAX_FILE_NUMBERING_ATTEMPTS', 3)
        # The wall clock comes through the clock door (glitchygames/clock.py)
        mocker.patch('glitchygames.clock.wall_clock_epoch_seconds', return_value=1234567890.5)

        base_path = tmp_path / 'sprite.toml'
        base_path.touch()
        (tmp_path / 'sprite_001.toml').touch()
        (tmp_path / 'sprite_002.toml').touch()

        result = find_available_path(base_path)

        assert '1234567890' in result.name

    def test_returns_original_when_path_does_not_exist(self, tmp_path):
        """Test that non-existent path is returned unchanged."""
        path = tmp_path / 'new_sprite.toml'
        result = find_available_path(path)
        assert result == path


class TestFindAvailableDirectoryTimestampFallback:
    """Tests for find_available_directory timestamp fallback."""

    def test_timestamp_fallback_when_many_directories_exist(self, tmp_path, mocker):
        """Test that timestamp is used when MAX_FILE_NUMBERING_ATTEMPTS dirs exist."""
        mocker.patch('glitchygames.api.client.MAX_FILE_NUMBERING_ATTEMPTS', 3)
        # The wall clock comes through the clock door (glitchygames/clock.py)
        mocker.patch('glitchygames.clock.wall_clock_epoch_seconds', return_value=9876543210.5)

        (tmp_path / 'sprite-001').mkdir()
        (tmp_path / 'sprite-002').mkdir()

        result = find_available_directory(tmp_path / 'sprite')

        assert '9876543210' in result.name


class TestHandleExtractFrames:
    """Tests for _handle_extract_frames function."""

    def _make_parsed_args(self, mocker, **overrides):
        """Create a mock parsed_args namespace for extract-frames testing.

        Returns:
            argparse.Namespace with default and overridden values.

        """
        defaults = {
            'extract_frames': '/path/to/test.apng',
            'output_path': None,
            'verbose': False,
        }
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    def test_successful_extraction_without_output_path(self, mocker, capsys):
        """Test successful extraction prints JSON to stdout."""
        parsed_args = self._make_parsed_args(mocker)

        mock_extract = mocker.patch('glitchygames.api.client.extract_frames')
        mock_extract.return_value = {
            'success': True,
            'frame_count': 2,
            'frames': [
                {'index': 0, 'png_base64': 'abc123'},
            ],
        }
        mocker.patch('glitchygames.api.client._log_extraction_metadata')

        result = _handle_extract_frames(parsed_args)

        assert result == ExitCode.SUCCESS
        captured = capsys.readouterr()
        # Should print JSON with base64 data replaced
        assert '<6 chars>' in captured.out

    def test_successful_extraction_with_output_path(self, mocker, tmp_path):
        """Test successful extraction saves frames to output path."""
        parsed_args = self._make_parsed_args(mocker, output_path=str(tmp_path))

        mock_extract = mocker.patch('glitchygames.api.client.extract_frames')
        mock_extract.return_value = {
            'success': True,
            'frame_count': 2,
        }
        mocker.patch('glitchygames.api.client._log_extraction_metadata')
        mock_save = mocker.patch('glitchygames.api.client._save_apng_extracted_frames')

        result = _handle_extract_frames(parsed_args)

        assert result == ExitCode.SUCCESS
        mock_save.assert_called_once()

    def test_extraction_failure_response(self, mocker):
        """Test handling of failed extraction response."""
        parsed_args = self._make_parsed_args(mocker)

        mock_extract = mocker.patch('glitchygames.api.client.extract_frames')
        mock_extract.return_value = {
            'success': False,
            'error': 'Bad APNG data',
        }

        result = _handle_extract_frames(parsed_args)

        assert result == ExitCode.EXTRACTION_REJECTED

    def test_extraction_file_not_found(self, mocker):
        """Test handling of FileNotFoundError."""
        parsed_args = self._make_parsed_args(mocker)

        mocker.patch(
            'glitchygames.api.client.extract_frames',
            side_effect=FileNotFoundError('file not found'),
        )

        result = _handle_extract_frames(parsed_args)

        assert result == ExitCode.MISSING_INPUT

    def test_extraction_unreadable_file(self, mocker):
        """A file that exists but cannot be read is unusable input."""
        parsed_args = self._make_parsed_args(mocker)

        mocker.patch(
            'glitchygames.api.client.extract_frames',
            side_effect=PermissionError(13, 'Permission denied'),
        )

        result = _handle_extract_frames(parsed_args)

        assert result == ExitCode.UNUSABLE_INPUT

    def test_extraction_os_error_with_verbose_traceback(self, mocker, capsys):
        """Test that verbose mode prints traceback on OSError."""
        parsed_args = self._make_parsed_args(mocker, verbose=True)

        mocker.patch(
            'glitchygames.api.client.extract_frames',
            side_effect=OSError('disk error'),
        )

        result = _handle_extract_frames(parsed_args)

        assert result == ExitCode.UNUSABLE_INPUT
        captured = capsys.readouterr()
        assert 'Traceback' in captured.err or 'disk error' in captured.err

    def test_extraction_verbose_outputs_full_json(self, mocker, capsys):
        """Test that verbose mode outputs full JSON including base64 data."""
        parsed_args = self._make_parsed_args(mocker, verbose=True)

        mock_extract = mocker.patch('glitchygames.api.client.extract_frames')
        mock_extract.return_value = {
            'success': True,
            'frame_count': 1,
            'frames': [
                {'index': 0, 'png_base64': 'fullbase64data'},
            ],
        }
        mocker.patch('glitchygames.api.client._log_extraction_metadata')

        result = _handle_extract_frames(parsed_args)

        assert result == ExitCode.SUCCESS
        captured = capsys.readouterr()
        # Verbose should include full base64, not truncated
        assert 'fullbase64data' in captured.out


class TestHandleExtractFramesOutput:
    """Writing the extracted frames: failures map to exit codes instead of a traceback."""

    @pytest.mark.parametrize(
        ('save_error', 'expected_exit_code'),
        [
            (OSError('disk full'), ExitCode.CANNOT_WRITE_OUTPUT),
            (FileNotFoundError('directory vanished'), ExitCode.CANNOT_WRITE_OUTPUT),
            (binascii.Error('incorrect padding'), ExitCode.UNUSABLE_INPUT),
        ],
        ids=['disk full', 'directory vanished', 'bad base64 from the server'],
    )
    def test_frame_write_failures(self, mocker, tmp_path, save_error, expected_exit_code):
        parsed_args = argparse.Namespace(
            extract_frames=str(tmp_path / 'in.apng'),
            output_path=str(tmp_path / 'frames'),
            verbose=False,
        )
        mocker.patch(
            'glitchygames.api.client.extract_frames',
            return_value={'success': True, 'frame_count': 1},
        )
        mocker.patch('glitchygames.api.client._log_extraction_metadata')
        mocker.patch('glitchygames.api.client._save_apng_extracted_frames', side_effect=save_error)

        assert _handle_extract_frames(parsed_args) == expected_exit_code


class TestHandleGenerateSprite:
    """Tests for _handle_generate_sprite function."""

    def _make_parsed_args(self, mocker, **overrides):
        """Create a mock parsed_args namespace for generate sprite testing.

        Returns:
            argparse.Namespace with default and overridden values.

        """
        defaults = {
            'prompt': 'a red heart',
            'output_path': None,
            'width': None,
            'height': None,
            'frame_count': None,
            'film_strip_count': None,
            'animation_duration': None,
            'png_scale': 1,
            'extract_scale': 8,
            'animation_language_model': None,
            'verbose': False,
            'quiet': False,
        }
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    def test_successful_generation_with_toml_output(self, mocker, capsys):
        """Test successful generation outputs TOML to stdout when no output_path."""
        parsed_args = self._make_parsed_args(mocker)

        mocker.patch(
            'glitchygames.api.client.generate_sprite',
            return_value={
                'success': True,
                'sprite_name': 'heart',
                'toml_content': '[sprite]\nname = "heart"',
            },
        )
        mocker.patch('glitchygames.api.client.display_sprite_ascii')

        result = _handle_generate_sprite(parsed_args, ['toml'])

        assert result == ExitCode.SUCCESS
        captured = capsys.readouterr()
        assert '[sprite]' in captured.out
        assert 'TOML Content' in captured.out

    def test_successful_generation_quiet_mode(self, mocker, capsys):
        """Test quiet mode suppresses TOML header but still prints content."""
        parsed_args = self._make_parsed_args(mocker, quiet=True)

        mocker.patch(
            'glitchygames.api.client.generate_sprite',
            return_value={
                'success': True,
                'sprite_name': 'heart',
                'toml_content': '[sprite]\nname = "heart"',
            },
        )
        mocker.patch('glitchygames.api.client.display_sprite_ascii')

        result = _handle_generate_sprite(parsed_args, ['toml'])

        assert result == ExitCode.SUCCESS
        captured = capsys.readouterr()
        assert 'TOML Content' not in captured.out
        assert '[sprite]' in captured.out

    def test_generation_with_model_override(self, mocker):
        """Test that model override is passed and logged."""
        parsed_args = self._make_parsed_args(
            mocker,
            animation_language_model='anthropic:claude-sonnet-4-5',
        )

        mock_generate = mocker.patch(
            'glitchygames.api.client.generate_sprite',
            return_value={'success': True, 'sprite_name': 'test'},
        )
        mocker.patch('glitchygames.api.client.display_sprite_ascii')

        result = _handle_generate_sprite(parsed_args, ['toml'])

        assert result == ExitCode.SUCCESS
        call_kwargs = mock_generate.call_args.kwargs
        assert call_kwargs['model'] == 'anthropic:claude-sonnet-4-5'

    def test_generation_failure(self, mocker):
        """Test handling of failed generation response."""
        parsed_args = self._make_parsed_args(mocker)

        mocker.patch(
            'glitchygames.api.client.generate_sprite',
            return_value={
                'success': False,
                'error': 'Model unavailable',
            },
        )

        result = _handle_generate_sprite(parsed_args, ['toml'])

        assert result == ExitCode.GENERATION_REJECTED

    def test_generation_with_animated_response(self, mocker):
        """Test that animated sprite info is logged."""
        parsed_args = self._make_parsed_args(mocker)

        mocker.patch(
            'glitchygames.api.client.generate_sprite',
            return_value={
                'success': True,
                'sprite_name': 'walk_cycle',
                'is_animated': True,
                'frame_count': 4,
                'width': 16,
                'height': 16,
            },
        )
        mocker.patch('glitchygames.api.client.display_sprite_ascii')

        result = _handle_generate_sprite(parsed_args, ['toml'])

        assert result == ExitCode.SUCCESS

    def test_generation_saves_files_when_output_path_set(self, mocker, tmp_path):
        """Test that files are saved when output_path is provided."""
        parsed_args = self._make_parsed_args(mocker, output_path=str(tmp_path))

        mocker.patch(
            'glitchygames.api.client.generate_sprite',
            return_value={
                'success': True,
                'sprite_name': 'test',
                'toml_content': 'test = true',
            },
        )
        mocker.patch('glitchygames.api.client.display_sprite_ascii')
        mock_save = mocker.patch(
            'glitchygames.api.client.save_files_locally',
            return_value=[str(tmp_path / 'test.toml')],
        )

        result = _handle_generate_sprite(parsed_args, ['toml'])

        assert result == ExitCode.SUCCESS
        mock_save.assert_called_once()

    def test_output_path_with_nothing_to_save_logs_and_prints_nothing(
        self, mocker, tmp_path, caplog, capsys
    ):
        """With --output-path but no savable content, no files are listed and no TOML printed."""
        parsed_args = self._make_parsed_args(mocker, output_path=str(tmp_path))
        mocker.patch(
            'glitchygames.api.client.generate_sprite',
            return_value={'success': True, 'sprite_name': 'test'},
        )
        mocker.patch('glitchygames.api.client.display_sprite_ascii')

        with caplog.at_level(logging.INFO, logger='glitchygames.api.client'):
            result = _handle_generate_sprite(parsed_args, ['toml'])

        assert result == ExitCode.SUCCESS
        assert 'Saved files:' not in caplog.text
        assert not capsys.readouterr().out


class TestMainCliExtended:
    """Extended tests for the main CLI entrypoint."""

    def test_main_extract_frames_dispatches_to_handler(self, mocker, tmp_path):
        """Test that --extract-frames dispatches to _handle_extract_frames."""
        apng_file = tmp_path / 'test.apng'
        apng_file.write_bytes(b'\x89PNG\r\n\x1a\n')

        mock_handler = mocker.patch(
            'glitchygames.api.client._handle_extract_frames',
            return_value=ExitCode.SUCCESS,
        )

        result = main(['--extract-frames', str(apng_file)])

        assert result == ExitCode.SUCCESS
        mock_handler.assert_called_once()

    def test_main_uses_default_output_formats(self, mocker):
        """With no -f, a sprite is written as .toml only (the owner, 2026-11-17)."""
        mock_handler = mocker.patch(
            'glitchygames.api.client._handle_generate_sprite',
            return_value=ExitCode.SUCCESS,
        )

        main(['test prompt'])

        call_args = mock_handler.call_args
        output_formats = call_args[0][1]
        assert output_formats == ['toml']

    def test_main_uses_specified_output_formats(self, mocker):
        """Test that specified output formats override defaults."""
        mock_handler = mocker.patch(
            'glitchygames.api.client._handle_generate_sprite',
            return_value=ExitCode.SUCCESS,
        )

        main(['test prompt', '-f', 'toml'])

        call_args = mock_handler.call_args
        output_formats = call_args[0][1]
        assert output_formats == ['toml']

    @pytest.mark.parametrize(
        'write_error',
        [OSError('disk full'), FileNotFoundError('no such directory')],
        ids=['disk full', 'output directory missing'],
    )
    def test_main_output_that_cannot_be_written(self, mocker, tmp_path, write_error):
        """A failure writing the output is CANNOT_WRITE_OUTPUT, never missing input."""
        mocker.patch(
            'glitchygames.api.client.generate_sprite',
            return_value={'success': True, 'sprite_name': 'heart'},
        )
        mocker.patch('glitchygames.api.client.save_files_locally', side_effect=write_error)

        result = main(['test prompt', '-q', '-o', str(tmp_path)])

        assert result == ExitCode.CANNOT_WRITE_OUTPUT

    def test_main_value_error(self, mocker):
        """A response that cannot be decoded is unusable input."""
        mocker.patch(
            'glitchygames.api.client.generate_sprite',
            side_effect=ValueError('bad value'),
        )

        result = main(['test prompt'])

        assert result == ExitCode.UNUSABLE_INPUT

    def test_main_verbose_with_error_prints_traceback(self, mocker, capsys):
        """A malformed server response (TypeError) prints its traceback in verbose mode."""
        mocker.patch(
            'glitchygames.api.client.generate_sprite',
            return_value={'success': True, 'sprite_name': 'heart'},
        )
        mocker.patch(
            'glitchygames.api.client._log_generation_results',
            side_effect=TypeError('type mismatch'),
        )

        result = main(['test prompt', '-v'])

        assert result == ExitCode.UNUSABLE_INPUT
        captured = capsys.readouterr()
        assert 'Traceback' in captured.err or 'type mismatch' in captured.err

    def test_main_client_bug_is_an_internal_error(self, mocker, caplog):
        """An exception no handler expects is a client bug: INTERNAL_ERROR, with its traceback."""
        client_bug = AttributeError('no such attribute')
        mocker.patch('glitchygames.api.client._handle_generate_sprite', side_effect=client_bug)

        result = main(['test prompt'])

        assert result == ExitCode.INTERNAL_ERROR
        assert any(
            record.exc_info and record.exc_info[1] is client_bug for record in caplog.records
        )

    def test_main_logs_the_exit_code(self, mocker, caplog):
        mocker.patch(
            'glitchygames.api.client._handle_generate_sprite',
            return_value=ExitCode.GENERATION_REJECTED,
        )

        with caplog.at_level(logging.INFO, logger='glitchygames.api.client'):
            main(['test prompt'])

        assert f'Exiting with {ExitCode.GENERATION_REJECTED.describe()}' in caplog.text

    def test_main_quiet_logging_setup(self, mocker):
        """Test that quiet mode sets ERROR logging level."""
        mocker.patch(
            'glitchygames.api.client._handle_generate_sprite',
            return_value=ExitCode.SUCCESS,
        )

        result = main(['test prompt', '-q'])

        assert result == ExitCode.SUCCESS


class TestRunEntryPoint:
    """Tests for the run() entry point."""

    def test_run_calls_sys_exit_with_main_result(self, mocker):
        """Test that run() calls sys.exit with the result of main()."""
        mocker.patch('glitchygames.api.client.main', return_value=ExitCode.SUCCESS)
        mock_exit = mocker.patch('glitchygames.api.client.sys.exit')

        from glitchygames.api.client import run

        run()

        mock_exit.assert_called_once_with(ExitCode.SUCCESS)

    def test_run_propagates_nonzero_exit(self, mocker):
        """Test that run() propagates non-zero exit codes."""
        mocker.patch('glitchygames.api.client.main', return_value=ExitCode.GENERATION_REJECTED)
        mock_exit = mocker.patch('glitchygames.api.client.sys.exit')

        from glitchygames.api.client import run

        run()

        mock_exit.assert_called_once_with(ExitCode.GENERATION_REJECTED)


# --- No server: the client calls the sprite requests in its own process ---

A_STATIC_SPRITE = """[sprite]
name = "heart"
pixels = \"\"\"
##
##
\"\"\"
[colors."#"]
red = 255
green = 0
blue = 0
"""

A_TWO_FRAME_SPRITE = """[sprite]
name = "blink"

[[animation]]
namespace = "blink"
frame_interval = 0.25

[[animation.frame]]
pixels = \"\"\"
#.
.#
\"\"\"

[[animation.frame]]
pixels = \"\"\"
.#
#.
\"\"\"

[colors."#"]
red = 255
green = 0
blue = 0

[colors."."]
red = 255
green = 0
blue = 255
"""


@pytest.fixture
def no_http_of_its_own(mocker):
    """Fail the test if the client builds an HTTP client itself (review focus 3)."""
    mocker.patch('httpx2.Client', side_effect=AssertionError('the client opened an HTTP client'))


@pytest.fixture
def ai_answering(mocker):
    """Stand the local AI service in, answering a given reply.

    Returns:
        A function taking the reply (a string or an exception).
    """

    def answer(reply):
        mocker.patch(
            'glitchygames.ai.local_service.create_chat_client',
            return_value=FakeAIClient(reply=reply),
        )

    return answer


@pytest.mark.usefixtures('no_http_of_its_own')
class TestWithoutAServer:
    """The client generates and extracts with no glitchygames-server and no port of its own."""

    def test_generation_writes_only_the_toml_by_default(self, ai_answering, tmp_path):
        """The engine's sprite format is the default output."""
        ai_answering(A_STATIC_SPRITE)

        status = main(['a heart', '-o', str(tmp_path)])

        assert status == ExitCode.SUCCESS
        assert sorted(path.suffix for path in tmp_path.rglob('*') if path.is_file()) == ['.toml']

    def test_both_formats_on_request(self, ai_answering, tmp_path):
        """-f toml -f png writes the sprite file and its image."""
        ai_answering(A_STATIC_SPRITE)

        status = main(['a heart', '-f', 'toml', '-f', 'png', '-o', str(tmp_path)])

        assert status == ExitCode.SUCCESS
        suffixes = sorted(path.suffix for path in tmp_path.rglob('*') if path.is_file())
        assert suffixes == ['.png', '.toml']

    def test_an_ai_service_not_installed_is_unavailable_and_named(self, mocker, caplog):
        """Review focus 1: the address it needs is in what it says."""
        from glitchygames.ai.local_service import LocalAIServiceNotInstalledError

        mocker.patch(
            'glitchygames.ai.local_service.create_chat_client',
            side_effect=LocalAIServiceNotInstalledError('not installed'),
        )

        status = main(['a heart'])

        assert status == ExitCode.SERVICE_UNAVAILABLE
        assert 'http://127.0.0.1:23231' in caplog.text

    def test_the_ai_services_own_error_is_unavailable_with_its_message(self, ai_answering, caplog):
        """Review focus 2: an unknown model, as the service says it."""
        from glitchygames.ai.local_service import LocalAIServiceError

        ai_answering(LocalAIServiceError('unknown model bonsai-99', status_code=400))

        status = main(['a heart', '--animation-language-model', 'bonsai-99'])

        assert status == ExitCode.SERVICE_UNAVAILABLE
        assert 'unknown model bonsai-99' in caplog.text

    def test_png_only_with_rendering_failing_is_rejected(self, ai_answering, mocker):
        """Review focus 4: nothing usable came back."""
        from glitchygames.services.renderer_service import RenderResult

        ai_answering(A_STATIC_SPRITE)
        mocker.patch(
            'glitchygames.services.RendererService.render_from_toml',
            return_value=RenderResult(success=False, error='x'),
        )

        assert main(['a heart', '-f', 'png']) == ExitCode.GENERATION_REJECTED

    def test_extracting_a_file_that_is_not_a_png_is_rejected(self, tmp_path):
        """Review focus 5: no server, and the refusal is the extraction's."""
        not_a_png = tmp_path / 'notes.png'
        not_a_png.write_bytes(b'not a png')

        assert main(['--extract-frames', str(not_a_png)]) == ExitCode.EXTRACTION_REJECTED

    def test_extracting_a_toml_sprite_writes_its_frames(self, tmp_path):
        """A .toml sprite's frames are written as PNGs, as an APNG's are."""
        sprite = tmp_path / 'blink.toml'
        sprite.write_text(A_TWO_FRAME_SPRITE, encoding='utf-8')
        output = tmp_path / 'frames'

        status = main(['--extract-frames', str(sprite), '-o', str(output)])

        assert status == ExitCode.SUCCESS
        assert sorted(path.name for path in output.iterdir()) == [
            'blink_frame_000.png',
            'blink_frame_001.png',
        ]

    def test_extracting_a_toml_that_is_not_a_sprite_is_rejected(self, tmp_path):
        """Review focus 5: a .toml with no sprite in it."""
        not_a_sprite = tmp_path / 'settings.toml'
        not_a_sprite.write_text('title = "not a sprite"\n', encoding='utf-8')

        assert main(['--extract-frames', str(not_a_sprite)]) == ExitCode.EXTRACTION_REJECTED

    def test_server_url_is_no_longer_an_option(self):
        """There is no server to name."""
        with pytest.raises(SystemExit) as usage_error:
            main(['a heart', '--server-url', 'http://localhost:8000'])

        assert usage_error.value.code == ExitCode.ARGUMENT_PARSER_ERROR
