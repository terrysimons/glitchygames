"""Additional coverage tests for sprite API routes.

Tests cover: _save_sprite_files edge cases, _extract_png_dimensions,
_extract_single_frame, generate/refine with AI provider errors,
PNG render failure paths, and path traversal protection.
"""
# pyright: reportMissingImports=false

import base64
import struct
import tempfile
from pathlib import Path

import pytest

# Skip tests if FastAPI is not installed
pytest.importorskip('fastapi')

from fastapi.testclient import TestClient

from glitchygames.api.main import app
from glitchygames.api.routes.sprites import (
    _extract_png_dimensions,
    _extract_single_frame,
    _save_sprite_files,
)
from glitchygames.services.exceptions import AIProviderError
from glitchygames.services.renderer_service import RenderResult
from glitchygames.services.sprite_generation_service import GenerationResult

MOCK_TOML = (
    '[sprite]\nname = "test_sprite"\npixels = "##"\n\n'
    '[colors."#"]\nred = 255\ngreen = 0\nblue = 0\n'
)

RENDER_FAIL_TOML = (
    '[sprite]\nname = "test"\npixels = "#"\n\n[colors."#"]\nred = 0\ngreen = 0\nblue = 0\n'
)


@pytest.fixture
def client(mocker):
    """Create a test client with mocked renderer initialization.

    Returns:
        object: TestClient instance.

    """
    mocker.patch('glitchygames.services.renderer_service.RendererService')
    return TestClient(app)


@pytest.fixture
def successful_generation_result():
    """Provide a successful generation result fixture.

    Returns:
        object: GenerationResult instance.

    """
    return GenerationResult(
        success=True,
        toml_content=MOCK_TOML,
        sprite_name='test_sprite',
        is_animated=False,
        frame_count=1,
    )


@pytest.fixture
def successful_render_result():
    """Provide a successful render result fixture.

    Returns:
        object: RenderResult instance.

    """
    return RenderResult(
        success=True,
        png_bytes=b'fake png data',
        png_base64='ZmFrZSBwbmcgZGF0YQ==',
        width=16,
        height=16,
        frame_count=1,
    )


class TestExtractPngDimensions:
    """Test _extract_png_dimensions function."""

    def test_valid_png_header(self):
        """Test extracting dimensions from valid PNG header bytes."""
        # Build a minimal fake PNG header: 16 bytes of filler, then 4-byte width and height
        width = 32
        height = 48
        header = b'\x00' * 16 + struct.pack('>I', width) + struct.pack('>I', height)

        result_width, result_height = _extract_png_dimensions(header, 0, 0)

        assert result_width == width
        assert result_height == height

    def test_bytes_too_short(self):
        """Test that short byte sequences return defaults."""
        result_width, result_height = _extract_png_dimensions(b'\x00' * 10, 99, 77)

        assert result_width == 99
        assert result_height == 77

    def test_empty_bytes(self):
        """Test that empty bytes return defaults."""
        result_width, result_height = _extract_png_dimensions(b'', 5, 10)

        assert result_width == 5
        assert result_height == 10


class TestExtractSingleFrame:
    """Test _extract_single_frame function."""

    def test_frame_without_control_chunk(self, mocker):
        """Test extracting a frame when control is None."""
        mock_png = mocker.Mock()
        # Build a minimal valid PNG so dimension extraction works
        width = 4
        height = 4
        fake_png_bytes = b'\x00' * 16 + struct.pack('>I', width) + struct.pack('>I', height)
        mock_png.save = lambda buf: buf.write(fake_png_bytes)

        frame_info, delay_ms = _extract_single_frame(mock_png, None, 0)

        assert frame_info.index == 0
        assert delay_ms == 100  # Default when control is None
        assert frame_info.x_offset == 0
        assert frame_info.y_offset == 0
        assert frame_info.width == width
        assert frame_info.height == height

    def test_frame_with_control_chunk(self, mocker):
        """Test extracting a frame with a control chunk."""
        mock_png = mocker.Mock()
        width = 8
        height = 8
        fake_png_bytes = b'\x00' * 16 + struct.pack('>I', width) + struct.pack('>I', height)
        mock_png.save = lambda buf: buf.write(fake_png_bytes)

        mock_control = mocker.Mock()
        mock_control.delay = 200
        mock_control.delay_den = 1000
        mock_control.width = width
        mock_control.height = height
        mock_control.x_offset = 2
        mock_control.y_offset = 3

        frame_info, delay_ms = _extract_single_frame(mock_png, mock_control, 1)

        assert frame_info.index == 1
        assert delay_ms == 200
        assert frame_info.x_offset == 2
        assert frame_info.y_offset == 3

    def test_frame_with_zero_delay_den(self, mocker):
        """Test extracting a frame when delay_den is zero (should default to 1000)."""
        mock_png = mocker.Mock()
        fake_png_bytes = b'\x00' * 24
        mock_png.save = lambda buf: buf.write(fake_png_bytes)

        mock_control = mocker.Mock()
        mock_control.delay = 500
        mock_control.delay_den = 0  # Zero denominator
        mock_control.width = 4
        mock_control.height = 4
        mock_control.x_offset = 0
        mock_control.y_offset = 0

        _frame_info, delay_ms = _extract_single_frame(mock_png, mock_control, 0)

        # delay_den=0 should be treated as 1000, so 500/1000 * 1000 = 500
        assert delay_ms == 500


class TestSaveSpritFilesEdgeCases:
    """Test _save_sprite_files edge cases."""

    def test_absolute_path_rejected(self):
        """Test that absolute output paths are rejected with HTTPException."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exception_info:
            _save_sprite_files(
                output_path='/etc/passwd',
                sprite_name='evil',
                toml_content='content',
                png_bytes=None,
                rendered_frames=None,
                output_format=['toml'],
            )

        assert exception_info.value.status_code == 400
        # Either "Absolute output paths are not allowed." or "Invalid output path."
        # depending on test isolation (parallel mocking can affect Path.is_absolute)
        assert 'Absolute' in exception_info.value.detail or 'Invalid' in exception_info.value.detail

    def test_path_traversal_rejected(self, mocker):
        """Test that path traversal attempts are rejected."""
        from fastapi import HTTPException

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir).resolve()
            mocker.patch('glitchygames.api.routes.sprites.ALLOWED_OUTPUT_ROOT', temp_root)

            with pytest.raises(HTTPException) as exception_info:
                _save_sprite_files(
                    output_path='../../etc',
                    sprite_name='evil',
                    toml_content='content',
                    png_bytes=None,
                    rendered_frames=None,
                    output_format=['toml'],
                )

            assert exception_info.value.status_code == 400

    def test_empty_sprite_name_sanitized_to_default(self, mocker):
        """Test that an empty sprite name is sanitized to 'sprite'."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir).resolve()
            mocker.patch('glitchygames.api.routes.sprites.ALLOWED_OUTPUT_ROOT', temp_root)

            saved_files = _save_sprite_files(
                output_path='output',
                sprite_name='',  # Empty name triggers fallback to 'sprite'
                toml_content='toml content',
                png_bytes=None,
                rendered_frames=None,
                output_format=['toml'],
            )

            assert len(saved_files) == 1
            assert 'sprite.toml' in saved_files[0]

    def test_special_chars_in_sprite_name_sanitized(self, mocker):
        """Test that special characters in sprite name are replaced with underscores."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir).resolve()
            mocker.patch('glitchygames.api.routes.sprites.ALLOWED_OUTPUT_ROOT', temp_root)

            saved_files = _save_sprite_files(
                output_path='output',
                sprite_name='my sprite!',  # Spaces and punctuation are sanitized
                toml_content='toml content',
                png_bytes=None,
                rendered_frames=None,
                output_format=['toml'],
            )

            assert len(saved_files) == 1
            assert 'my_sprite_.toml' in saved_files[0]

    def test_save_rendered_frames(self, mocker):
        """Test saving rendered animation frames."""
        from glitchygames.api.models import RenderedFrameInfo

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir).resolve()
            mocker.patch('glitchygames.api.routes.sprites.ALLOWED_OUTPUT_ROOT', temp_root)

            frame_data = base64.b64encode(b'fake frame png').decode('utf-8')
            frames = [
                RenderedFrameInfo(animation_index=0, frame_index=0, png_base64=frame_data),
                RenderedFrameInfo(animation_index=0, frame_index=1, png_base64=frame_data),
            ]

            saved_files = _save_sprite_files(
                output_path='anim_output',
                sprite_name='walk',
                toml_content=None,
                png_bytes=None,
                rendered_frames=frames,
                output_format=['png'],
            )

            assert len(saved_files) == 2
            assert 'animation-0-frame-0.png' in saved_files[0]
            assert 'animation-0-frame-1.png' in saved_files[1]


class TestGenerateSpriteAIProviderError:
    """Test generate_sprite endpoint with AIProviderError."""

    def test_generate_sprite_ai_provider_error_returns_503(self, client, mocker):
        """Test that AIProviderError results in 503."""
        mock_services = mocker.patch('glitchygames.api.routes.sprites._get_services')
        mock_gen_service = mocker.MagicMock()
        mock_gen_service.generate_sprite.side_effect = AIProviderError(
            'Provider down',
            provider='anthropic',
        )
        mock_render_service = mocker.MagicMock()
        mock_services.return_value = (mock_gen_service, mock_render_service)

        response = client.post(
            '/sprites/generate',
            json={
                'prompt': 'a red heart',
                'output_format': ['toml'],
            },
        )

        assert response.status_code == 503

    def test_generate_sprite_unexpected_error_returns_500(self, client, mocker):
        """Test that unexpected errors result in 500."""
        mock_services = mocker.patch('glitchygames.api.routes.sprites._get_services')
        mock_gen_service = mocker.MagicMock()
        mock_gen_service.generate_sprite.side_effect = RuntimeError('unexpected')
        mock_render_service = mocker.MagicMock()
        mock_services.return_value = (mock_gen_service, mock_render_service)

        response = client.post(
            '/sprites/generate',
            json={
                'prompt': 'a red heart',
                'output_format': ['toml'],
            },
        )

        assert response.status_code == 500


class TestRefineSpriteErrors:
    """Test refine_sprite endpoint error paths."""

    def test_refine_sprite_ai_provider_error_returns_503(self, client, mocker):
        """Test that AIProviderError during refinement results in 503."""
        mock_services = mocker.patch('glitchygames.api.routes.sprites._get_services')
        mock_gen_service = mocker.MagicMock()
        mock_gen_service.refine_sprite.side_effect = AIProviderError(
            'Provider down',
            provider='anthropic',
        )
        mock_render_service = mocker.MagicMock()
        mock_services.return_value = (mock_gen_service, mock_render_service)

        response = client.post(
            '/sprites/refine',
            json={
                'prompt': 'make it blue',
                'current_toml': "[sprite]\nname = 'test'",
                'output_format': ['toml'],
            },
        )

        assert response.status_code == 503

    def test_refine_sprite_unexpected_error_returns_500(self, client, mocker):
        """Test that unexpected errors during refinement result in 500."""
        mock_services = mocker.patch('glitchygames.api.routes.sprites._get_services')
        mock_gen_service = mocker.MagicMock()
        mock_gen_service.refine_sprite.side_effect = RuntimeError('unexpected')
        mock_render_service = mocker.MagicMock()
        mock_services.return_value = (mock_gen_service, mock_render_service)

        response = client.post(
            '/sprites/refine',
            json={
                'prompt': 'make it red',
                'current_toml': "[sprite]\nname = 'test'",
                'output_format': ['toml'],
            },
        )

        assert response.status_code == 500


class TestPNGRenderFailurePaths:
    """Test PNG rendering failure paths."""

    def test_generate_png_only_render_failure(self, client, mocker):
        """Test that PNG-only format returns failure when rendering fails."""
        mock_services = mocker.patch('glitchygames.api.routes.sprites._get_services')

        gen_result = GenerationResult(
            success=True,
            toml_content=RENDER_FAIL_TOML,
            sprite_name='test',
            is_animated=False,
            frame_count=1,
        )
        mock_gen_service = mocker.MagicMock()
        mock_gen_service.generate_sprite.return_value = gen_result

        failed_render = RenderResult(success=False, error='SDL init failed')
        mock_render_service = mocker.MagicMock()
        mock_render_service.render_from_toml.return_value = failed_render
        mock_services.return_value = (mock_gen_service, mock_render_service)

        response = client.post(
            '/sprites/generate',
            json={
                'prompt': 'a test sprite',
                'output_format': ['png'],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
        assert 'PNG rendering failed' in data['error']

    def test_generate_both_formats_render_failure_still_returns_toml(self, client, mocker):
        """Test that TOML+PNG format still succeeds with TOML when PNG rendering fails."""
        mock_services = mocker.patch('glitchygames.api.routes.sprites._get_services')

        gen_result = GenerationResult(
            success=True,
            toml_content=RENDER_FAIL_TOML,
            sprite_name='test',
            is_animated=False,
            frame_count=1,
        )
        mock_gen_service = mocker.MagicMock()
        mock_gen_service.generate_sprite.return_value = gen_result

        failed_render = RenderResult(success=False, error='SDL init failed')
        mock_render_service = mocker.MagicMock()
        mock_render_service.render_from_toml.return_value = failed_render
        mock_services.return_value = (mock_gen_service, mock_render_service)

        response = client.post(
            '/sprites/generate',
            json={
                'prompt': 'a test sprite',
                'output_format': ['toml', 'png'],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['toml_content'] is not None

    def test_refine_png_only_render_failure(self, client, mocker):
        """Test that PNG-only refinement returns failure when rendering fails."""
        mock_services = mocker.patch('glitchygames.api.routes.sprites._get_services')

        gen_result = GenerationResult(
            success=True,
            toml_content=RENDER_FAIL_TOML,
            sprite_name='test',
            is_animated=False,
            frame_count=1,
        )
        mock_gen_service = mocker.MagicMock()
        mock_gen_service.refine_sprite.return_value = gen_result

        failed_render = RenderResult(success=False, error='SDL init failed')
        mock_render_service = mocker.MagicMock()
        mock_render_service.render_from_toml.return_value = failed_render
        mock_services.return_value = (mock_gen_service, mock_render_service)

        response = client.post(
            '/sprites/refine',
            json={
                'prompt': 'make it blue',
                'current_toml': "[sprite]\nname = 'test'",
                'output_format': ['png'],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
        assert 'PNG rendering failed' in data['error']


class TestGenerateWithModelOverride:
    """Test generate endpoint with model override."""

    def test_generate_sprite_with_model_override(
        self,
        client,
        successful_generation_result,
        mocker,
    ):
        """Test that model override is passed through to the service."""
        mock_services = mocker.patch('glitchygames.api.routes.sprites._get_services')
        mock_gen_service = mocker.MagicMock()
        mock_gen_service.generate_sprite.return_value = successful_generation_result
        mock_render_service = mocker.MagicMock()
        mock_services.return_value = (mock_gen_service, mock_render_service)

        response = client.post(
            '/sprites/generate',
            json={
                'prompt': 'a red heart',
                'output_format': ['toml'],
                'model': 'openai:gpt-4o',
            },
        )

        assert response.status_code == 200
        call_kwargs = mock_gen_service.generate_sprite.call_args.kwargs
        assert call_kwargs['model'] == 'openai:gpt-4o'
