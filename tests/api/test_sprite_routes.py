"""Tests for sprite generation API routes."""

import tempfile
from pathlib import Path

import pytest

# Skip tests if FastAPI is not installed
pytest.importorskip('fastapi')

from fastapi.testclient import TestClient

from glitchygames.api.main import app
from glitchygames.services.renderer_service import RenderResult
from glitchygames.services.sprite_generation_service import GenerationResult


@pytest.fixture
def client():
    """Create a test client for the API.

    Returns:
        object: The result.

    """
    return TestClient(app)


@pytest.fixture
def mock_generation_result():
    """Provide a mock successful generation result.

    Returns:
        object: The result.

    """
    return GenerationResult(
        success=True,
        toml_content="""
[sprite]
name = "test_heart"
pixels = \"\"\"
##
##
\"\"\"

[colors."#"]
red = 255
green = 0
blue = 0
""",
        sprite_name='test_heart',
        is_animated=False,
        frame_count=1,
    )


@pytest.fixture
def mock_render_result():
    """Provide a mock successful render result.

    Returns:
        object: The result.

    """
    return RenderResult(
        success=True,
        png_bytes=b'fake png data',
        png_base64='ZmFrZSBwbmcgZGF0YQ==',
        width=16,
        height=16,
        frame_count=1,
    )


class TestHealthEndpoints:
    """Test suite for health check endpoints."""

    def test_root_endpoint(self, client):
        """Test root endpoint returns API info."""
        response = client.get('/')

        assert response.status_code == 200
        data = response.json()
        assert 'name' in data
        assert 'version' in data
        assert 'docs' in data

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get('/health')

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert 'version' in data
        assert 'ai_provider' in data
        assert 'ai_model' in data


class TestSpriteGenerationEndpoint:
    """Test suite for sprite generation endpoint."""

    def test_generate_sprite_toml_only(self, client, mock_generation_result, mocker):
        """Test generating sprite with TOML output only."""
        mock_services = mocker.patch('glitchygames.api.routes.sprites._get_services')
        mock_gen_service = mocker.MagicMock()
        mock_gen_service.generate_sprite.return_value = mock_generation_result
        mock_render_service = mocker.MagicMock()
        mock_services.return_value = (mock_gen_service, mock_render_service)

        response = client.post(
            '/sprites/generate',
            json={
                'prompt': '16x16 red heart',
                'output_format': ['toml'],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['toml_content'] is not None
        assert data['png_base64'] is None

    def test_generate_sprite_png_only(
        self, client, mock_generation_result, mock_render_result, mocker
    ):
        """Test generating sprite with PNG output only."""
        mock_services = mocker.patch('glitchygames.api.routes.sprites._get_services')
        mock_gen_service = mocker.MagicMock()
        mock_gen_service.generate_sprite.return_value = mock_generation_result
        mock_render_service = mocker.MagicMock()
        mock_render_service.render_from_toml.return_value = mock_render_result
        mock_services.return_value = (mock_gen_service, mock_render_service)

        response = client.post(
            '/sprites/generate',
            json={
                'prompt': '16x16 red heart',
                'output_format': ['png'],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['png_base64'] is not None

    def test_generate_sprite_both_outputs(
        self, client, mock_generation_result, mock_render_result, mocker
    ):
        """Test generating sprite with both TOML and PNG output."""
        mock_services = mocker.patch('glitchygames.api.routes.sprites._get_services')
        mock_gen_service = mocker.MagicMock()
        mock_gen_service.generate_sprite.return_value = mock_generation_result
        mock_render_service = mocker.MagicMock()
        mock_render_service.render_from_toml.return_value = mock_render_result
        mock_services.return_value = (mock_gen_service, mock_render_service)

        response = client.post(
            '/sprites/generate',
            json={
                'prompt': '16x16 red heart',
                'output_format': ['toml', 'png'],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['toml_content'] is not None
        assert data['png_base64'] is not None

    def test_generate_sprite_with_dimensions(self, client, mock_generation_result, mocker):
        """Test generating sprite with explicit dimensions."""
        mock_services = mocker.patch('glitchygames.api.routes.sprites._get_services')
        mock_gen_service = mocker.MagicMock()
        mock_gen_service.generate_sprite.return_value = mock_generation_result
        mock_render_service = mocker.MagicMock()
        mock_services.return_value = (mock_gen_service, mock_render_service)

        response = client.post(
            '/sprites/generate',
            json={
                'prompt': 'red heart',
                'width': 32,
                'height': 32,
                'output_format': ['toml'],
            },
        )

        assert response.status_code == 200
        # Verify generate_sprite was called with dimensions
        mock_gen_service.generate_sprite.assert_called_once()
        call_args = mock_gen_service.generate_sprite.call_args
        assert call_args.kwargs['width'] == 32
        assert call_args.kwargs['height'] == 32

    def test_generate_sprite_generation_failure(self, client, mocker):
        """Test handling of generation failure."""
        failed_result = GenerationResult(
            success=False,
            error='AI response invalid',
        )

        mock_services = mocker.patch('glitchygames.api.routes.sprites._get_services')
        mock_gen_service = mocker.MagicMock()
        mock_gen_service.generate_sprite.return_value = failed_result
        mock_render_service = mocker.MagicMock()
        mock_services.return_value = (mock_gen_service, mock_render_service)

        response = client.post(
            '/sprites/generate',
            json={
                'prompt': 'bad request',
                'output_format': ['toml'],
            },
        )

        assert response.status_code == 200  # Returns 200 with success=False
        data = response.json()
        assert data['success'] is False
        assert data['error'] is not None

    def test_generate_sprite_invalid_request(self, client):
        """Test handling of invalid request data."""
        response = client.post(
            '/sprites/generate',
            json={
                'prompt': '',  # Empty prompt should fail validation
            },
        )

        assert response.status_code == 422  # Validation error


class TestSpriteRefinementEndpoint:
    """Test suite for sprite refinement endpoint."""

    def test_refine_sprite(self, client, mock_generation_result, mock_render_result, mocker):
        """Test refining an existing sprite."""
        mock_services = mocker.patch('glitchygames.api.routes.sprites._get_services')
        mock_gen_service = mocker.MagicMock()
        mock_gen_service.refine_sprite.return_value = mock_generation_result
        mock_render_service = mocker.MagicMock()
        mock_render_service.render_from_toml.return_value = mock_render_result
        mock_services.return_value = (mock_gen_service, mock_render_service)

        response = client.post(
            '/sprites/refine',
            json={
                'prompt': 'make it blue',
                'current_toml': "[sprite]\nname = 'test'",
                'output_format': ['toml', 'png'],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True

    def test_refine_sprite_failure(self, client, mocker):
        """Test handling of refinement failure."""
        failed_result = GenerationResult(
            success=False,
            error='Refinement failed',
        )

        mock_services = mocker.patch('glitchygames.api.routes.sprites._get_services')
        mock_gen_service = mocker.MagicMock()
        mock_gen_service.refine_sprite.return_value = failed_result
        mock_render_service = mocker.MagicMock()
        mock_services.return_value = (mock_gen_service, mock_render_service)

        response = client.post(
            '/sprites/refine',
            json={
                'prompt': 'make it fail',
                'current_toml': "[sprite]\nname = 'test'",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
        assert data['error'] is not None


class TestOutputDirFunctionality:
    """Test suite for output_dir file saving functionality."""

    def test_generate_sprite_with_output_dir(
        self, client, mock_generation_result, mock_render_result, mocker
    ):
        """Test generating sprite saves files when output_dir specified."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_services = mocker.patch('glitchygames.api.routes.sprites._get_services')
            mock_gen_service = mocker.MagicMock()
            mock_gen_service.generate_sprite.return_value = mock_generation_result
            mock_render_service = mocker.MagicMock()
            mock_render_service.render_from_toml.return_value = mock_render_result
            mock_services.return_value = (mock_gen_service, mock_render_service)

            response = client.post(
                '/sprites/generate',
                json={
                    'prompt': '16x16 red heart',
                    'output_format': ['toml', 'png'],
                    'output_path': temp_dir,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data['success'] is True
            assert data['saved_files'] is not None
            assert len(data['saved_files']) == 2  # TOML and PNG

            # Verify files were actually created
            output_path = Path(temp_dir)
            toml_files = list(output_path.glob('*.toml'))
            png_files = list(output_path.glob('*.png'))
            assert len(toml_files) == 1
            assert len(png_files) == 1

    def test_generate_sprite_creates_output_dir(self, client, mock_generation_result, mocker):
        """Test that output_dir is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a path to a subdirectory that doesn't exist
            new_subdir = Path(temp_dir) / 'new_sprites' / 'hearts'

            mock_services = mocker.patch('glitchygames.api.routes.sprites._get_services')
            mock_gen_service = mocker.MagicMock()
            mock_gen_service.generate_sprite.return_value = mock_generation_result
            mock_render_service = mocker.MagicMock()
            mock_services.return_value = (mock_gen_service, mock_render_service)

            response = client.post(
                '/sprites/generate',
                json={
                    'prompt': '16x16 red heart',
                    'output_format': ['toml'],
                    'output_path': str(new_subdir),
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data['success'] is True
            assert data['saved_files'] is not None

            # Verify directory was created
            assert new_subdir.exists()
            assert new_subdir.is_dir()

    def test_refine_sprite_with_output_dir(
        self, client, mock_generation_result, mock_render_result, mocker
    ):
        """Test refining sprite saves files when output_dir specified."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_services = mocker.patch('glitchygames.api.routes.sprites._get_services')
            mock_gen_service = mocker.MagicMock()
            mock_gen_service.refine_sprite.return_value = mock_generation_result
            mock_render_service = mocker.MagicMock()
            mock_render_service.render_from_toml.return_value = mock_render_result
            mock_services.return_value = (mock_gen_service, mock_render_service)

            response = client.post(
                '/sprites/refine',
                json={
                    'prompt': 'make it blue',
                    'current_toml': "[sprite]\nname = 'test'",
                    'output_format': ['toml', 'png'],
                    'output_path': temp_dir,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data['success'] is True
            assert data['saved_files'] is not None

            # Verify files were actually created
            output_path = Path(temp_dir)
            assert any(output_path.iterdir())


class TestApngExtractFramesEndpoint:
    """Test suite for APNG frame extraction endpoint."""

    def test_extract_frames_success(self, client):
        """Test extracting frames from a valid APNG."""
        import base64
        from io import BytesIO

        from apng import APNG, PNG

        # Create a simple APNG with 2 frames
        apng = APNG()

        # Create two simple 2x2 PNG frames using PIL
        from PIL import Image

        # Frame 1: red
        img1 = Image.new('RGBA', (2, 2), (255, 0, 0, 255))
        buf1 = BytesIO()
        img1.save(buf1, format='PNG')
        png1 = PNG.from_bytes(buf1.getvalue())
        apng.append(png1, delay=100, delay_den=1000)

        # Frame 2: blue
        img2 = Image.new('RGBA', (2, 2), (0, 0, 255, 255))
        buf2 = BytesIO()
        img2.save(buf2, format='PNG')
        png2 = PNG.from_bytes(buf2.getvalue())
        apng.append(png2, delay=200, delay_den=1000)

        # Save APNG to bytes
        apng_buffer = BytesIO()
        apng.save(apng_buffer)
        apng_base64 = base64.b64encode(apng_buffer.getvalue()).decode('utf-8')

        response = client.post(
            '/sprites/extract-frames',
            json={'apng_base64': apng_base64},
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['frame_count'] == 2
        assert len(data['frames']) == 2
        assert data['frames'][0]['index'] == 0
        assert data['frames'][1]['index'] == 1

    def test_extract_frames_invalid_base64(self, client):
        """Test handling of invalid base64 data."""
        response = client.post(
            '/sprites/extract-frames',
            json={'apng_base64': 'not-valid-base64!!!'},
        )

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is False
        assert 'Invalid base64' in data['error']

    def test_extract_frames_empty_apng(self, client):
        """Test handling of empty APNG data (validation error)."""
        import base64

        # Empty base64 triggers validation error due to min_length=1
        empty_base64 = base64.b64encode(b'').decode('utf-8')

        response = client.post(
            '/sprites/extract-frames',
            json={'apng_base64': empty_base64},
        )

        # Empty string fails validation (min_length=1)
        assert response.status_code == 422
