"""Tests for renderer service."""

import base64
import io
import logging
import os
import types

import pygame
import pytest
from PIL import Image

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
        # Reset the class variable for testing.
        # The actual class attribute is `pygame_initialized` (no leading underscore).
        RendererService.pygame_initialized = False

        # Set headless environment variables
        mocker.patch.dict(os.environ, {'SDL_VIDEODRIVER': 'dummy', 'SDL_AUDIODRIVER': 'dummy'})
        service = RendererService()
        assert RendererService.pygame_initialized is True

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


TWO_FRAME_ANIMATED_TOML = """
[sprite]
name = "two_frames"

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


def _solid_surface(color, size=(2, 3)):
    """Build an RGBA surface of one color.

    Returns:
        The surface.

    """
    surface = pygame.Surface(size, pygame.SRCALPHA)
    surface.fill(color)
    return surface


def _png_pixels(png_base64):
    """Decode a base64 PNG to its size and RGBA pixel list.

    Returns:
        (size, list of RGBA tuples).

    """
    image = Image.open(io.BytesIO(base64.b64decode(png_base64))).convert('RGBA')
    raw_bytes = image.tobytes()
    pixels = [tuple(raw_bytes[offset : offset + 4]) for offset in range(0, len(raw_bytes), 4)]
    return image.size, pixels


class FakeFrameManager:
    """Stands in for an AnimatedSprite's frame manager: current animation and frame."""

    def __init__(self, *, current_animation, current_frame):
        """Point at the given animation and frame."""
        self.current_animation = current_animation
        self.current_frame = current_frame
        self.visited: list[tuple[str, int]] = []


class FakeAnimatedSprite:
    """An animated sprite whose current frame follows its frame manager."""

    def __init__(self, frames, *, frame_manager=None):
        """Hold the animations' frames and, optionally, a frame manager."""
        self.frames = frames
        if frame_manager is not None:
            self.frame_manager = frame_manager

    def get_current_frame(self):
        """Return the frame the frame manager points at (recording the visit)."""
        manager = self.frame_manager
        manager.visited.append((manager.current_animation, manager.current_frame))
        return self.frames[manager.current_animation][manager.current_frame]


@pytest.fixture
def renderer():
    """A RendererService with pygame initialized headless.

    Returns:
        The service.

    """
    return RendererService()


class TestRenderFrameToPng:
    """_render_frame_to_png encodes the surface's pixels, scaled, as an uncompressed PNG."""

    def test_pixels_survive_the_round_trip(self, renderer):
        """The PNG decodes to the surface's size and color; base64 matches the bytes."""
        png_bytes, png_base64 = renderer._render_frame_to_png(_solid_surface((10, 20, 30, 255)))

        assert base64.b64decode(png_base64) == png_bytes
        size, pixels = _png_pixels(png_base64)
        assert size == (2, 3)
        assert set(pixels) == {(10, 20, 30, 255)}

    def test_scale_multiplies_the_size(self, renderer):
        """Scale 3 triples both dimensions."""
        _, png_base64 = renderer._render_frame_to_png(_solid_surface((1, 2, 3, 255)), scale=3)

        assert _png_pixels(png_base64)[0] == (6, 9)


class TestRenderSpriteFile:
    """_render_sprite_file loads the sprite and renders its frames."""

    def test_two_frame_animation_renders_every_frame(self, renderer):
        """All frames are rendered with their animation and frame indices, at scale."""
        result = renderer.render_from_toml(TWO_FRAME_ANIMATED_TOML, scale=2, render_all_frames=True)

        assert result.success is True
        assert result.frame_count == 2
        assert (result.width, result.height) == (4, 4)
        assert [(frame.animation_index, frame.frame_index) for frame in result.rendered_frames] == [
            (0, 0),
            (0, 1),
        ]
        assert result.all_frames_png_base64 == [
            frame.png_base64 for frame in result.rendered_frames
        ]
        first_size, first_pixels = _png_pixels(result.rendered_frames[0].png_base64)
        _, second_pixels = _png_pixels(result.rendered_frames[1].png_base64)
        assert first_size == (4, 4)
        assert set(first_pixels) == {(255, 255, 255, 255)}
        assert set(second_pixels) == {(0, 0, 0, 255)}

    def test_without_render_all_frames_only_the_first_frame(self, renderer):
        """Frames are counted but not rendered unless asked."""
        result = renderer.render_from_toml(TWO_FRAME_ANIMATED_TOML)

        assert result.frame_count == 2
        assert result.rendered_frames == []
        assert result.all_frames_png_base64 == []

    def test_sprite_without_a_frame_fails(self, renderer, mocker):
        """No current frame: 'Failed to get sprite frame'."""
        sprite = mocker.Mock(name='sprite')
        sprite.get_current_frame.return_value = None
        mocker.patch('glitchygames.sprites.SpriteFactory.load_sprite', return_value=sprite)

        result = renderer.render_from_toml('[sprite]')

        assert result.success is False
        assert result.error == 'Failed to get sprite frame'

    def test_frame_count_from_the_frames_property(self, renderer, mocker):
        """Without get_total_frame_count, frames across animations are summed."""
        frame = types.SimpleNamespace(image=_solid_surface((5, 5, 5, 255)), get_size=lambda: (2, 3))
        sprite = types.SimpleNamespace(
            get_current_frame=lambda: frame,
            frames={'walk': [frame, frame], 'jump': [frame]},
        )
        mocker.patch('glitchygames.sprites.SpriteFactory.load_sprite', return_value=sprite)

        result = renderer.render_from_toml('[sprite]', render_all_frames=True)

        assert result.success is True
        assert result.frame_count == 3
        assert [(frame.animation_index, frame.frame_index) for frame in result.rendered_frames] == [
            (0, 0),
            (0, 1),
            (1, 0),
        ]

    def test_empty_frames_property_counts_one(self, renderer, mocker):
        """A frames property with no frames still counts one frame."""
        frame = types.SimpleNamespace(image=_solid_surface((5, 5, 5, 255)), get_size=lambda: (2, 3))
        sprite = types.SimpleNamespace(get_current_frame=lambda: frame, frames={})
        mocker.patch('glitchygames.sprites.SpriteFactory.load_sprite', return_value=sprite)

        assert renderer.render_from_toml('[sprite]').frame_count == 1

    def test_sprite_with_no_frame_information(self, renderer, mocker):
        """A sprite with neither frame count nor frames is a one-frame sprite."""
        frame = types.SimpleNamespace(image=_solid_surface((5, 5, 5, 255)), get_size=lambda: (2, 3))
        sprite = types.SimpleNamespace(get_current_frame=lambda: frame)
        mocker.patch('glitchygames.sprites.SpriteFactory.load_sprite', return_value=sprite)

        result = renderer.render_from_toml('[sprite]', render_all_frames=True)

        assert result.success is True
        assert result.frame_count == 1
        assert result.rendered_frames == []


class TestRenderAllFrames:
    """_render_all_frames walks every animation and restores the frame manager."""

    def test_frame_manager_drives_the_frames_and_is_restored(self, renderer):
        """Each frame is reached through the frame manager, which is put back afterwards."""
        red = types.SimpleNamespace(image=_solid_surface((255, 0, 0, 255)))
        blue = types.SimpleNamespace(image=_solid_surface((0, 0, 255, 255)))
        manager = FakeFrameManager(current_animation='b', current_frame=0)
        sprite = FakeAnimatedSprite({'a': [red, blue], 'b': [blue]}, frame_manager=manager)

        frames_base64, rendered_frames = renderer._render_all_frames(sprite)

        assert manager.visited == [('a', 0), ('a', 1), ('b', 0)]
        assert (manager.current_animation, manager.current_frame) == ('b', 0)
        colors = [set(_png_pixels(encoded)[1]) for encoded in frames_base64]
        assert colors == [{(255, 0, 0, 255)}, {(0, 0, 255, 255)}, {(0, 0, 255, 255)}]
        assert [(frame.animation_index, frame.frame_index) for frame in rendered_frames] == [
            (0, 0),
            (0, 1),
            (1, 0),
        ]

    def test_falls_back_to_the_frame_image_when_the_manager_has_none(self, renderer, mocker):
        """When get_current_frame gives nothing, the frame's own image is used."""
        green = types.SimpleNamespace(image=_solid_surface((0, 255, 0, 255)))
        manager = FakeFrameManager(current_animation='a', current_frame=0)
        sprite = FakeAnimatedSprite({'a': [green]}, frame_manager=manager)
        mocker.patch.object(sprite, 'get_current_frame', return_value=None)

        frames_base64, _ = renderer._render_all_frames(sprite)

        assert [set(_png_pixels(encoded)[1]) for encoded in frames_base64] == [{(0, 255, 0, 255)}]

    def test_manager_frame_without_image_falls_back_too(self, renderer, mocker):
        """A current frame whose image is None also falls back to the frame's image."""
        green = types.SimpleNamespace(image=_solid_surface((0, 255, 0, 255)))
        manager = FakeFrameManager(current_animation='a', current_frame=0)
        sprite = FakeAnimatedSprite({'a': [green]}, frame_manager=manager)
        mocker.patch.object(
            sprite, 'get_current_frame', return_value=types.SimpleNamespace(image=None)
        )

        frames_base64, _ = renderer._render_all_frames(sprite)

        assert len(frames_base64) == 1

    def test_frames_without_a_surface_are_skipped(self, renderer, caplog):
        """A frame with no image and no frame manager is skipped with a warning."""
        sprite = types.SimpleNamespace(
            frames={'idle': [object(), types.SimpleNamespace(image=_solid_surface((9, 9, 9, 255)))]}
        )

        with caplog.at_level(logging.WARNING, logger='glitchygames.services.renderer'):
            frames_base64, rendered_frames = renderer._render_all_frames(sprite)

        assert len(frames_base64) == 1
        assert [(frame.animation_index, frame.frame_index) for frame in rendered_frames] == [(0, 1)]
        assert "Could not get surface for frame 0 of animation 'idle'" in caplog.text

    def test_animation_data_is_the_fallback(self, renderer):
        """Without frames, animation_data supplies the animations."""
        sprite = types.SimpleNamespace(
            animation_data={'idle': [types.SimpleNamespace(image=_solid_surface((1, 1, 1, 255)))]}
        )

        frames_base64, _ = renderer._render_all_frames(sprite)

        assert len(frames_base64) == 1

    def test_no_animations_at_all(self, renderer):
        """A sprite with neither frames nor animation_data renders nothing."""
        assert renderer._render_all_frames(types.SimpleNamespace()) == ([], [])

    def test_empty_animations(self, renderer):
        """An empty animations dict renders nothing."""
        assert renderer._render_all_frames(types.SimpleNamespace(frames={})) == ([], [])

    def test_manager_without_an_animation_is_not_restored(self, renderer):
        """A frame manager that started with no animation is left where rendering ended."""
        image_frame = types.SimpleNamespace(image=_solid_surface((1, 1, 1, 255)))
        manager = FakeFrameManager(current_animation=None, current_frame=0)
        sprite = FakeAnimatedSprite({'a': [image_frame, image_frame]}, frame_manager=manager)

        renderer._render_all_frames(sprite)

        assert (manager.current_animation, manager.current_frame) == ('a', 1)

    def test_manager_is_restored_after_a_failure(self, renderer, mocker):
        """A failure while rendering still restores the frame manager."""
        image_frame = types.SimpleNamespace(image=_solid_surface((1, 1, 1, 255)))
        manager = FakeFrameManager(current_animation='a', current_frame=1)
        sprite = FakeAnimatedSprite({'a': [image_frame, image_frame]}, frame_manager=manager)
        mocker.patch.object(renderer, '_render_frame_to_png', side_effect=ValueError('bad'))

        with pytest.raises(ValueError, match='bad'):
            renderer._render_all_frames(sprite)

        assert (manager.current_animation, manager.current_frame) == ('a', 1)


class TestRenderFromTomlFailures:
    """render_from_toml reports file and render failures as unsuccessful results."""

    def test_temporary_file_failure(self, renderer, mocker):
        """No temporary file: an error result."""
        mocker.patch(
            'glitchygames.services.renderer_service.tempfile.NamedTemporaryFile',
            side_effect=OSError('disk full'),
        )

        result = renderer.render_from_toml('[sprite]')

        assert result.success is False
        assert result.error == 'Failed to create temporary file: disk full'

    def test_cleanup_failure_is_only_logged(self, renderer, mocker, caplog):
        """A temporary file that cannot be removed does not change the result."""
        mocker.patch(
            'glitchygames.services.renderer_service.Path.unlink',
            side_effect=OSError('busy'),
        )

        with caplog.at_level(logging.DEBUG, logger='glitchygames.services.renderer'):
            result = renderer.render_from_toml(TWO_FRAME_ANIMATED_TOML)

        assert result.success is True
        assert 'Failed to clean up temporary file' in caplog.text


class TestRenderFromFile:
    """render_from_file reads the file and renders it."""

    def test_renders_an_existing_file(self, renderer, tmp_path):
        """A sprite file on disk renders like its TOML."""
        sprite_path = tmp_path / 'two_frames.toml'
        sprite_path.write_text(TWO_FRAME_ANIMATED_TOML, encoding='utf-8')

        result = renderer.render_from_file(str(sprite_path), scale=3)

        assert result.success is True
        assert (result.width, result.height) == (6, 6)

    def test_unreadable_file(self, renderer, tmp_path):
        """A directory is not readable as a file: 'Failed to read file'."""
        result = renderer.render_from_file(str(tmp_path))

        assert result.success is False
        assert result.error is not None
        assert result.error.startswith('Failed to read file:')
