"""Tests for the GlitchyGames API client module."""

import argparse
import base64
from pathlib import Path

import pytest

from glitchygames.api.client import (
    _handle_extract_frames,
    _handle_generate_sprite,
    _log_extraction_metadata,
    _save_apng_extracted_frames,
    _save_extracted_frames,
    create_apng_from_frames,
    create_parser,
    display_sprite_ascii,
    extract_apng_frames,
    find_available_directory,
    find_available_path,
    generate_sprite,
    main,
    save_files_locally,
)


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
        assert parsed_args.server_url == 'http://localhost:8000'
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
            '--server-url',
            'http://example.com:9000',
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
        assert parsed_args.server_url == 'http://example.com:9000'
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
    """Tests for the generate_sprite function."""

    def test_generate_sprite_basic(self, mocker):
        """Test basic sprite generation via API."""
        mock_response = mocker.Mock()
        mock_response.json.return_value = {
            'success': True,
            'sprite_name': 'test_sprite',
        }
        mock_response.raise_for_status.return_value = None

        mock_client_instance = mocker.Mock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__enter__ = mocker.Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = mocker.Mock(return_value=False)

        mocker.patch('glitchygames.api.client.httpx.Client', return_value=mock_client_instance)

        result = generate_sprite(
            server_url='http://localhost:8000',
            prompt='a red heart',
            output_formats=['toml'],
        )

        assert result['success'] is True
        assert result['sprite_name'] == 'test_sprite'
        mock_client_instance.post.assert_called_once()

    def test_generate_sprite_with_optional_params(self, mocker, tmp_path):
        """Test sprite generation with all optional parameters."""
        mock_response = mocker.Mock()
        mock_response.json.return_value = {'success': True}
        mock_response.raise_for_status.return_value = None

        mock_client_instance = mocker.Mock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__enter__ = mocker.Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = mocker.Mock(return_value=False)

        mocker.patch('glitchygames.api.client.httpx.Client', return_value=mock_client_instance)

        output_path = str(tmp_path / 'output')
        generate_sprite(
            server_url='http://localhost:8000/',
            prompt='test',
            output_formats=['toml', 'png'],
            output_path=output_path,
            width=16,
            height=16,
            frame_count=4,
            film_strip_count=2,
            animation_duration=2.0,
            png_scale=2,
            model='anthropic:claude-sonnet-4-5',
        )

        call_args = mock_client_instance.post.call_args
        payload = call_args.kwargs.get('json') or call_args[1].get('json')
        assert payload['prompt'] == 'test'
        assert payload['width'] == 16
        assert payload['height'] == 16
        assert payload['frame_count'] == 4
        assert payload['film_strip_count'] == 2
        assert payload['animation_duration'] == pytest.approx(2.0)
        assert payload['model'] == 'anthropic:claude-sonnet-4-5'
        assert payload['output_path'] == output_path

    def test_generate_sprite_url_trailing_slash(self, mocker):
        """Test that trailing slashes in server URL are handled."""
        mock_response = mocker.Mock()
        mock_response.json.return_value = {'success': True}
        mock_response.raise_for_status.return_value = None

        mock_client_instance = mocker.Mock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__enter__ = mocker.Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = mocker.Mock(return_value=False)

        mocker.patch('glitchygames.api.client.httpx.Client', return_value=mock_client_instance)

        generate_sprite(
            server_url='http://localhost:8000/',
            prompt='test',
            output_formats=['toml'],
        )

        call_args = mock_client_instance.post.call_args
        url = call_args.args[0] if call_args.args else call_args[0][0]
        assert url == 'http://localhost:8000/sprites/generate'


class TestExtractApngFrames:
    """Tests for the extract_apng_frames function."""

    def test_extract_apng_frames(self, mocker, tmp_path):
        """Test extracting frames from an APNG file."""
        # Create a dummy APNG file
        apng_file = tmp_path / 'test.apng'
        apng_file.write_bytes(b'\x89PNG\r\n\x1a\n')

        mock_response = mocker.Mock()
        mock_response.json.return_value = {
            'success': True,
            'frame_count': 3,
        }
        mock_response.raise_for_status.return_value = None

        mock_client_instance = mocker.Mock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__enter__ = mocker.Mock(return_value=mock_client_instance)
        mock_client_instance.__exit__ = mocker.Mock(return_value=False)

        mocker.patch('glitchygames.api.client.httpx.Client', return_value=mock_client_instance)

        result = extract_apng_frames(
            server_url='http://localhost:8000',
            apng_path=str(apng_file),
        )

        assert result['success'] is True
        assert result['frame_count'] == 3

        # Verify the payload had base64-encoded data
        call_args = mock_client_instance.post.call_args
        payload = call_args.kwargs.get('json') or call_args[1].get('json')
        assert 'apng_base64' in payload


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


class TestMainCli:
    """Tests for the main CLI entrypoint."""

    def test_main_no_prompt_no_extract_exits_error(self):
        """Test that missing prompt and no --extract-frames causes an error."""
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code != 0

    def test_main_connection_error(self, mocker):
        """Test handling of connection errors."""
        import httpx

        mocker.patch(
            'glitchygames.api.client.generate_sprite',
            side_effect=httpx.ConnectError('connection refused'),
        )

        result = main(['test prompt'])
        assert result == 1

    def test_main_http_error(self, mocker):
        """Test handling of HTTP errors."""
        import httpx

        mock_response = mocker.Mock()
        mock_response.status_code = 500
        mock_response.text = 'Internal Server Error'

        mocker.patch(
            'glitchygames.api.client.generate_sprite',
            side_effect=httpx.HTTPStatusError(
                'Server Error',
                request=mocker.Mock(),
                response=mock_response,
            ),
        )

        result = main(['test prompt'])
        assert result == 1

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
        assert result == 0

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
        assert result == 1

    def test_main_extract_frames_file_not_found(self):
        """Test extract-frames with missing file."""
        result = main(['--extract-frames', '/nonexistent/file.apng'])
        assert result == 1

    def test_main_verbose_logging(self, mocker):
        """Test verbose mode enables debug logging."""
        mocker.patch(
            'glitchygames.api.client.generate_sprite',
            return_value={'success': True, 'sprite_name': 'test'},
        )
        mocker.patch('glitchygames.api.client.display_sprite_ascii')

        result = main(['test prompt', '-v'])
        assert result == 0


class TestLogExtractionMetadata:
    """Tests for _log_extraction_metadata function."""

    def test_logs_frame_count(self, mocker):
        """Test that frame count is logged."""
        mock_log = mocker.patch('glitchygames.api.client.LOG')
        response = {'frame_count': 5}

        _log_extraction_metadata(response)

        mock_log.info.assert_any_call('Extracted 5 frames')

    def test_logs_canvas_size(self, mocker):
        """Test that canvas size is logged when width and height present."""
        mock_log = mocker.patch('glitchygames.api.client.LOG')
        response = {'frame_count': 3, 'width': 32, 'height': 32}

        _log_extraction_metadata(response)

        mock_log.info.assert_any_call('  Canvas size: 32x32 pixels')

    def test_skips_canvas_size_when_missing(self, mocker):
        """Test that canvas size is not logged when width or height missing."""
        mock_log = mocker.patch('glitchygames.api.client.LOG')
        response = {'frame_count': 3, 'width': 32}

        _log_extraction_metadata(response)

        # Should only have frame count log, not canvas size
        calls = [str(call) for call in mock_log.info.call_args_list]
        assert not any('Canvas size' in call for call in calls)

    def test_logs_total_duration(self, mocker):
        """Test that total duration is logged when present."""
        mock_log = mocker.patch('glitchygames.api.client.LOG')
        response = {'frame_count': 3, 'total_duration_ms': 500}

        _log_extraction_metadata(response)

        mock_log.info.assert_any_call('  Total duration: 500ms')

    def test_logs_infinite_loop_count(self, mocker):
        """Test that loop_count of 0 is logged as infinite."""
        mock_log = mocker.patch('glitchygames.api.client.LOG')
        response = {'frame_count': 3, 'loop_count': 0}

        _log_extraction_metadata(response)

        mock_log.info.assert_any_call('  Loop count: infinite')

    def test_logs_finite_loop_count(self, mocker):
        """Test that non-zero loop_count is logged as a number."""
        mock_log = mocker.patch('glitchygames.api.client.LOG')
        response = {'frame_count': 3, 'loop_count': 5}

        _log_extraction_metadata(response)

        mock_log.info.assert_any_call('  Loop count: 5')

    def test_skips_loop_count_when_none(self, mocker):
        """Test that loop_count is not logged when not present."""
        mock_log = mocker.patch('glitchygames.api.client.LOG')
        response = {'frame_count': 3}

        _log_extraction_metadata(response)

        calls = [str(call) for call in mock_log.info.call_args_list]
        assert not any('Loop count' in call for call in calls)


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
        mock_time = mocker.patch('time.time', return_value=1234567890)

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
        mock_time = mocker.patch('time.time', return_value=9876543210)

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
            'server_url': 'http://localhost:8000',
            'output_path': None,
            'verbose': False,
        }
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    def test_successful_extraction_without_output_path(self, mocker, capsys):
        """Test successful extraction prints JSON to stdout."""
        parsed_args = self._make_parsed_args(mocker)

        mock_extract = mocker.patch('glitchygames.api.client.extract_apng_frames')
        mock_extract.return_value = {
            'success': True,
            'frame_count': 2,
            'frames': [
                {'index': 0, 'png_base64': 'abc123'},
            ],
        }
        mocker.patch('glitchygames.api.client._log_extraction_metadata')

        result = _handle_extract_frames(parsed_args)

        assert result == 0
        captured = capsys.readouterr()
        # Should print JSON with base64 data replaced
        assert '<6 chars>' in captured.out

    def test_successful_extraction_with_output_path(self, mocker, tmp_path):
        """Test successful extraction saves frames to output path."""
        parsed_args = self._make_parsed_args(mocker, output_path=str(tmp_path))

        mock_extract = mocker.patch('glitchygames.api.client.extract_apng_frames')
        mock_extract.return_value = {
            'success': True,
            'frame_count': 2,
        }
        mocker.patch('glitchygames.api.client._log_extraction_metadata')
        mock_save = mocker.patch('glitchygames.api.client._save_apng_extracted_frames')

        result = _handle_extract_frames(parsed_args)

        assert result == 0
        mock_save.assert_called_once()

    def test_extraction_failure_response(self, mocker):
        """Test handling of failed extraction response."""
        parsed_args = self._make_parsed_args(mocker)

        mock_extract = mocker.patch('glitchygames.api.client.extract_apng_frames')
        mock_extract.return_value = {
            'success': False,
            'error': 'Bad APNG data',
        }

        result = _handle_extract_frames(parsed_args)

        assert result == 1

    def test_extraction_file_not_found(self, mocker):
        """Test handling of FileNotFoundError."""
        parsed_args = self._make_parsed_args(mocker)

        mocker.patch(
            'glitchygames.api.client.extract_apng_frames',
            side_effect=FileNotFoundError('file not found'),
        )

        result = _handle_extract_frames(parsed_args)

        assert result == 1

    def test_extraction_connection_error(self, mocker):
        """Test handling of connection error during extraction."""
        import httpx

        parsed_args = self._make_parsed_args(mocker)

        mocker.patch(
            'glitchygames.api.client.extract_apng_frames',
            side_effect=httpx.ConnectError('connection refused'),
        )

        result = _handle_extract_frames(parsed_args)

        assert result == 1

    def test_extraction_http_status_error(self, mocker):
        """Test handling of HTTP status error during extraction."""
        import httpx

        parsed_args = self._make_parsed_args(mocker)

        mock_response = mocker.Mock()
        mock_response.status_code = 500
        mock_response.text = 'Internal Server Error'

        mocker.patch(
            'glitchygames.api.client.extract_apng_frames',
            side_effect=httpx.HTTPStatusError(
                'Server Error',
                request=mocker.Mock(),
                response=mock_response,
            ),
        )

        result = _handle_extract_frames(parsed_args)

        assert result == 1

    def test_extraction_os_error_with_verbose_traceback(self, mocker, capsys):
        """Test that verbose mode prints traceback on OSError."""
        parsed_args = self._make_parsed_args(mocker, verbose=True)

        mocker.patch(
            'glitchygames.api.client.extract_apng_frames',
            side_effect=OSError('disk error'),
        )

        result = _handle_extract_frames(parsed_args)

        assert result == 1
        captured = capsys.readouterr()
        assert 'Traceback' in captured.err or 'disk error' in captured.err

    def test_extraction_verbose_outputs_full_json(self, mocker, capsys):
        """Test that verbose mode outputs full JSON including base64 data."""
        parsed_args = self._make_parsed_args(mocker, verbose=True)

        mock_extract = mocker.patch('glitchygames.api.client.extract_apng_frames')
        mock_extract.return_value = {
            'success': True,
            'frame_count': 1,
            'frames': [
                {'index': 0, 'png_base64': 'fullbase64data'},
            ],
        }
        mocker.patch('glitchygames.api.client._log_extraction_metadata')

        result = _handle_extract_frames(parsed_args)

        assert result == 0
        captured = capsys.readouterr()
        # Verbose should include full base64, not truncated
        assert 'fullbase64data' in captured.out


class TestHandleGenerateSprite:
    """Tests for _handle_generate_sprite function."""

    def _make_parsed_args(self, mocker, **overrides):
        """Create a mock parsed_args namespace for generate sprite testing.

        Returns:
            argparse.Namespace with default and overridden values.

        """
        defaults = {
            'prompt': 'a red heart',
            'server_url': 'http://localhost:8000',
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

        assert result == 0
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

        assert result == 0
        captured = capsys.readouterr()
        assert 'TOML Content' not in captured.out
        assert '[sprite]' in captured.out

    def test_generation_with_model_override(self, mocker):
        """Test that model override is passed and logged."""
        parsed_args = self._make_parsed_args(
            mocker, animation_language_model='anthropic:claude-sonnet-4-5',
        )

        mock_generate = mocker.patch(
            'glitchygames.api.client.generate_sprite',
            return_value={'success': True, 'sprite_name': 'test'},
        )
        mocker.patch('glitchygames.api.client.display_sprite_ascii')

        result = _handle_generate_sprite(parsed_args, ['toml'])

        assert result == 0
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

        assert result == 1

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

        assert result == 0

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

        assert result == 0
        mock_save.assert_called_once()


class TestMainCliExtended:
    """Extended tests for the main CLI entrypoint."""

    def test_main_extract_frames_dispatches_to_handler(self, mocker, tmp_path):
        """Test that --extract-frames dispatches to _handle_extract_frames."""
        apng_file = tmp_path / 'test.apng'
        apng_file.write_bytes(b'\x89PNG\r\n\x1a\n')

        mock_handler = mocker.patch(
            'glitchygames.api.client._handle_extract_frames',
            return_value=0,
        )

        result = main(['--extract-frames', str(apng_file)])

        assert result == 0
        mock_handler.assert_called_once()

    def test_main_uses_default_output_formats(self, mocker):
        """Test that default output formats are used when none specified."""
        mock_handler = mocker.patch(
            'glitchygames.api.client._handle_generate_sprite',
            return_value=0,
        )

        main(['test prompt'])

        call_args = mock_handler.call_args
        output_formats = call_args[0][1]
        assert output_formats == ['toml', 'png']

    def test_main_uses_specified_output_formats(self, mocker):
        """Test that specified output formats override defaults."""
        mock_handler = mocker.patch(
            'glitchygames.api.client._handle_generate_sprite',
            return_value=0,
        )

        main(['test prompt', '-f', 'toml'])

        call_args = mock_handler.call_args
        output_formats = call_args[0][1]
        assert output_formats == ['toml']

    def test_main_general_os_error(self, mocker):
        """Test handling of general OS errors in main."""
        mocker.patch(
            'glitchygames.api.client._handle_generate_sprite',
            side_effect=OSError('disk full'),
        )

        result = main(['test prompt'])

        assert result == 1

    def test_main_value_error(self, mocker):
        """Test handling of ValueError in main."""
        mocker.patch(
            'glitchygames.api.client._handle_generate_sprite',
            side_effect=ValueError('bad value'),
        )

        result = main(['test prompt'])

        assert result == 1

    def test_main_verbose_with_error_prints_traceback(self, mocker, capsys):
        """Test that verbose mode prints traceback on errors."""
        mocker.patch(
            'glitchygames.api.client._handle_generate_sprite',
            side_effect=TypeError('type mismatch'),
        )

        result = main(['test prompt', '-v'])

        assert result == 1
        captured = capsys.readouterr()
        assert 'Traceback' in captured.err or 'type mismatch' in captured.err

    def test_main_quiet_logging_setup(self, mocker):
        """Test that quiet mode sets ERROR logging level."""
        mocker.patch(
            'glitchygames.api.client._handle_generate_sprite',
            return_value=0,
        )

        result = main(['test prompt', '-q'])

        assert result == 0


class TestRunEntryPoint:
    """Tests for the run() entry point."""

    def test_run_calls_sys_exit_with_main_result(self, mocker):
        """Test that run() calls sys.exit with the result of main()."""
        mocker.patch('glitchygames.api.client.main', return_value=0)
        mock_exit = mocker.patch('glitchygames.api.client.sys.exit')

        from glitchygames.api.client import run

        run()

        mock_exit.assert_called_once_with(0)

    def test_run_propagates_nonzero_exit(self, mocker):
        """Test that run() propagates non-zero exit codes."""
        mocker.patch('glitchygames.api.client.main', return_value=1)
        mock_exit = mocker.patch('glitchygames.api.client.sys.exit')

        from glitchygames.api.client import run

        run()

        mock_exit.assert_called_once_with(1)
