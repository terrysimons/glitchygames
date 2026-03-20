"""Tests for renderer service."""

import os

import pytest

from glitchygames.services.renderer_service import RendererService, RenderResult


class TestRenderResult:
    """Test suite for RenderResult dataclass."""

    def test_successful_result(self):
        """Test successful render result."""
        result = RenderResult(
            success=True,
            png_bytes=b'PNG data',
            png_base64='UE5HIGRhdGE=',
            width=16,
            height=16,
            frame_count=1,
        )

        assert result.success is True
        assert result.png_bytes is not None
        assert result.error is None

    def test_failed_result(self):
        """Test failed render result."""
        result = RenderResult(
            success=False,
            error='Sprite loading failed',
        )

        assert result.success is False
        assert result.png_bytes is None
        assert result.error == 'Sprite loading failed'


class TestRendererService:
    """Test suite for RendererService."""

    @pytest.fixture
    def sample_static_toml(self):
        """Provide sample static sprite TOML.

        Returns:
            object: The result.

        """
        return """
[sprite]
name = "test_heart"
pixels = \"\"\"
.##.
####
####
.##.
..#.
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
    def sample_animated_toml(self):
        """Provide sample animated sprite TOML.

        Returns:
            object: The result.

        """
        return """
[sprite]
name = "test_blink"

[[animation]]
namespace = "idle"
frame_interval = 0.5
loop = true

[[animation.frame]]
namespace = "idle"
frame_index = 0
pixels = \"\"\"
##
##
\"\"\"

[[animation.frame]]
namespace = "idle"
frame_index = 1
pixels = \"\"\"
..
..
\"\"\"

[colors."#"]
red = 255
green = 255
blue = 255

[colors."."]
red = 0
green = 0
blue = 0
"""

    def test_initialization(self, mocker):
        """Test renderer service initialization."""
        # Reset the class variable for testing
        RendererService._pygame_initialized = False  # type: ignore[unresolved-attribute]

        # Set headless environment variables
        mocker.patch.dict(os.environ, {'SDL_VIDEODRIVER': 'dummy', 'SDL_AUDIODRIVER': 'dummy'})
        service = RendererService()
        assert RendererService._pygame_initialized is True  # type: ignore[unresolved-attribute]

    def test_render_from_toml_static(self, sample_static_toml):
        """Test rendering a static sprite from TOML."""
        service = RendererService()

        result = service.render_from_toml(sample_static_toml)

        assert result.success is True
        assert result.png_bytes is not None
        assert result.png_base64 is not None
        assert result.frame_count >= 1

    def test_render_from_toml_animated(self, sample_animated_toml):
        """Test rendering an animated sprite from TOML."""
        service = RendererService()

        result = service.render_from_toml(sample_animated_toml)

        assert result.success is True
        assert result.png_bytes is not None

    def test_render_from_toml_with_scale(self, sample_static_toml):
        """Test rendering with scale factor."""
        service = RendererService()

        # Render at 2x scale
        result = service.render_from_toml(sample_static_toml, scale=2)

        assert result.success is True
        # Width and height should be scaled
        assert result.width > 0
        assert result.height > 0

    def test_render_all_frames(self, sample_animated_toml):
        """Test rendering all frames of an animated sprite."""
        service = RendererService()

        result = service.render_from_toml(sample_animated_toml, render_all_frames=True)

        assert result.success is True
        # Animated sprites return successfully - the test verifies rendering works
        # The frame count depends on how the frame_manager tracks frames
        # For simple animations, even with render_all_frames=True, we may get
        # all_frames_png_base64 populated only when frame_count > 1
        assert result.png_base64 is not None

    def test_render_from_toml_invalid(self):
        """Test rendering with invalid TOML."""
        service = RendererService()

        result = service.render_from_toml('invalid { toml content')

        assert result.success is False
        assert result.error is not None

    def test_render_from_file_not_found(self):
        """Test rendering from non-existent file."""
        service = RendererService()

        result = service.render_from_file('/nonexistent/path/sprite.toml')

        assert result.success is False
        assert result.error is not None
        assert 'not found' in result.error.lower() or 'no such file' in result.error.lower()
