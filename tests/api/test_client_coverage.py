"""Tests to increase coverage for glitchygames/api/client.py.

Targets uncovered methods and branches including:
- _save_extracted_frames
- _log_extraction_metadata
- _save_apng_extracted_frames
- _handle_extract_frames (various branches)
- _handle_generate_sprite (various branches)
- save_files_locally (animation frames paths)
- find_available_path (timestamp fallback)
- find_available_directory (timestamp fallback)
- main() error handling branches
- run() entry point
"""

import argparse
import base64

from glitchygames.api.client import (
    _handle_extract_frames,
    _handle_generate_sprite,
    _log_extraction_metadata,
    _save_apng_extracted_frames,
    _save_extracted_frames,
    find_available_directory,
    find_available_path,
    main,
    save_files_locally,
)


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
            ]
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

        mock_image.resize.assert_called_once_with((32, 32), RealImageModule.NEAREST)


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
            mocker, animation_language_model='anthropic:claude-sonnet-4-5'
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
