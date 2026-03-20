"""Coverage tests for glitchygames/services/renderer_service.py.

This module targets uncovered areas including:
- RenderedFrame dataclass
- RenderResult default field factories
- RendererService._get_frame_surface method
- RendererService._render_all_frames with no frames
- RendererService.render_from_file with read errors
- RendererService._render_animation_frames
"""

import sys
import tempfile
from pathlib import Path

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.services.renderer_service import (
    RenderedFrame,
    RendererService,
    RenderResult,
)


class TestRenderedFrame:
    """Test RenderedFrame dataclass."""

    def test_rendered_frame_creation(self):
        """Test RenderedFrame creation with all fields."""
        frame = RenderedFrame(
            animation_index=0,
            frame_index=1,
            png_base64='abc123',
        )
        assert frame.animation_index == 0
        assert frame.frame_index == 1
        assert frame.png_base64 == 'abc123'

    def test_rendered_frame_equality(self):
        """Test RenderedFrame equality comparison."""
        frame_a = RenderedFrame(animation_index=0, frame_index=0, png_base64='data')
        frame_b = RenderedFrame(animation_index=0, frame_index=0, png_base64='data')
        assert frame_a == frame_b


class TestRenderResultDefaults:
    """Test RenderResult dataclass default values."""

    def test_default_values(self):
        """Test RenderResult has correct default values."""
        result = RenderResult(success=True)
        assert result.png_bytes is None
        assert result.png_base64 is None
        assert result.width == 0
        assert result.height == 0
        assert result.frame_count == 1
        assert result.all_frames_png_base64 == []
        assert result.rendered_frames == []
        assert result.error is None

    def test_all_frames_default_is_independent(self):
        """Test that default list factory creates independent lists."""
        result_a = RenderResult(success=True)
        result_b = RenderResult(success=True)
        result_a.all_frames_png_base64.append('test')
        assert result_b.all_frames_png_base64 == []

    def test_rendered_frames_default_is_independent(self):
        """Test that default list factory creates independent lists."""
        result_a = RenderResult(success=True)
        result_b = RenderResult(success=True)
        result_a.rendered_frames.append(
            RenderedFrame(animation_index=0, frame_index=0, png_base64='x')
        )
        assert result_b.rendered_frames == []


class TestRendererServiceGetFrameSurface:
    """Test RendererService._get_frame_surface method."""

    def test_get_frame_surface_with_frame_manager(self, mocker):
        """Test _get_frame_surface uses frame_manager when available."""
        service = RendererService()
        mock_sprite = mocker.Mock()
        mock_frame = mocker.Mock()
        mock_surface = mocker.Mock()
        mock_sprite.get_current_frame.return_value = mocker.Mock(image=mock_surface)

        result = service._get_frame_surface(mock_sprite, mock_frame, has_frame_manager=True)
        assert result == mock_surface

    def test_get_frame_surface_fallback_to_sprite_frame(self, mocker):
        """Test _get_frame_surface falls back to sprite_frame.image."""
        service = RendererService()
        mock_sprite = mocker.Mock()
        mock_sprite.get_current_frame.return_value = None
        mock_surface = mocker.Mock()
        mock_frame = mocker.Mock()
        mock_frame.image = mock_surface

        result = service._get_frame_surface(mock_sprite, mock_frame, has_frame_manager=True)
        assert result == mock_surface

    def test_get_frame_surface_no_frame_manager(self, mocker):
        """Test _get_frame_surface without frame_manager uses sprite_frame.image."""
        service = RendererService()
        mock_sprite = mocker.Mock()
        mock_surface = mocker.Mock()
        mock_frame = mocker.Mock()
        mock_frame.image = mock_surface

        result = service._get_frame_surface(mock_sprite, mock_frame, has_frame_manager=False)
        assert result == mock_surface

    def test_get_frame_surface_no_image_returns_none(self, mocker):
        """Test _get_frame_surface returns None when no image available."""
        service = RendererService()
        mock_sprite = mocker.Mock()
        mock_sprite.get_current_frame.return_value = None
        mock_frame = mocker.Mock(spec=[])  # No image attribute

        result = service._get_frame_surface(mock_sprite, mock_frame, has_frame_manager=True)
        assert result is None


class TestRendererServiceRenderAllFrames:
    """Test RendererService._render_all_frames edge cases."""

    def test_render_all_frames_no_frames_attr(self, mocker):
        """Test _render_all_frames with sprite that has no frames attribute."""
        service = RendererService()
        mock_sprite = mocker.Mock(spec=[])  # No frames or _animations
        result_base64, result_frames = service._render_all_frames(mock_sprite)
        assert result_base64 == []
        assert result_frames == []

    def test_render_all_frames_empty_animations(self, mocker):
        """Test _render_all_frames with empty animations dict."""
        service = RendererService()
        mock_sprite = mocker.Mock()
        mock_sprite.frames = {}
        result_base64, result_frames = service._render_all_frames(mock_sprite)
        assert result_base64 == []
        assert result_frames == []

    def test_render_all_frames_uses_animations_fallback(self, mocker):
        """Test _render_all_frames uses _animations when frames is not available."""
        service = RendererService()
        mock_sprite = mocker.Mock(spec=['_animations'])
        mock_sprite._animations = {}
        result_base64, result_frames = service._render_all_frames(mock_sprite)
        assert result_base64 == []
        assert result_frames == []


class TestRendererServiceRenderFromFile:
    """Test RendererService.render_from_file error handling."""

    def test_render_from_file_os_error(self, mocker):
        """Test render_from_file handles OS read errors."""
        service = RendererService()
        # Create a directory path that can't be read as a file
        result = service.render_from_file('/dev/null/nonexistent')
        assert result.success is False
        assert result.error is not None

    def test_render_from_file_valid_toml(self):
        """Test render_from_file with a valid TOML sprite file."""
        service = RendererService()
        toml_content = """
[sprite]
name = "test"
pixels = \"\"\"
##
##
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
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.toml', delete=False, encoding='utf-8'
        ) as temp_file:
            temp_file.write(toml_content)
            temp_path = temp_file.name

        try:
            result = service.render_from_file(temp_path)
            assert result.success is True
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestRendererServiceTempFileError:
    """Test RendererService.render_from_toml temp file error handling."""

    def test_render_from_toml_temp_file_error(self, mocker):
        """Test render_from_toml handles temp file creation failure."""
        service = RendererService()
        mocker.patch('tempfile.NamedTemporaryFile', side_effect=OSError('disk full'))
        result = service.render_from_toml('[sprite]\nname = "test"')
        assert result.success is False
        assert result.error is not None
        assert 'temporary file' in result.error.lower()
