"""Tests for the GlitchyGames API client module."""

import base64
from pathlib import Path

import pytest

from glitchygames.api.client import (
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
        mock_renderer._extract_colors_from_toml.return_value = {'#': (255, 0, 0)}
        mock_renderer._extract_pixels_from_toml.return_value = '##\n##'
        mock_renderer._colorize_pixels.return_value = '##\n##'

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
        mock_renderer._extract_colors_from_toml.return_value = {'#': (255, 0, 0)}
        mock_renderer._colorize_pixels.return_value = '##'

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
