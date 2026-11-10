"""Headless sprite rendering service.

This service renders sprites to PNG format without requiring a display.
It uses SDL_VIDEODRIVER=dummy for headless pygame operation.
"""

from __future__ import annotations

import base64
import io
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from glitchygames.services.config import ServiceConfig

if TYPE_CHECKING:
    import pygame

    from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame

LOG = logging.getLogger('glitchygames.services.renderer')


@dataclass
class RenderedFrame:
    """Data for a single rendered frame.

    Attributes:
        animation_index: Index of the animation (film strip) this frame belongs to
        frame_index: Index of the frame within its animation
        png_base64: Base64-encoded PNG data for this frame

    """

    animation_index: int
    frame_index: int
    png_base64: str


@dataclass
class RenderResult:
    """Result of a sprite render operation.

    Attributes:
        success: Whether rendering was successful
        png_bytes: PNG image bytes (if successful)
        png_base64: Base64-encoded PNG (if successful)
        width: Sprite width in pixels
        height: Sprite height in pixels
        frame_count: Number of frames rendered
        all_frames_png_base64: List of base64-encoded PNGs for each frame (if animated)
        rendered_frames: List of RenderedFrame with animation/frame indices (if animated)
        error: Error message (if unsuccessful)

    """

    success: bool
    png_bytes: bytes | None = None
    png_base64: str | None = None
    width: int = 0
    height: int = 0
    frame_count: int = 1
    all_frames_png_base64: list[str] = field(default_factory=list)
    rendered_frames: list[RenderedFrame] = field(default_factory=list)
    error: str | None = None


class RendererService:
    """Service for rendering sprites to PNG format headlessly.

    This service initializes pygame in headless mode and provides methods
    to render TOML sprites to PNG images.
    """

    pygame_initialized: bool = False

    def __init__(self, config: ServiceConfig | None = None) -> None:
        """Initialize the renderer service.

        Args:
            config: Service configuration. Uses defaults if not provided.

        """
        self.config = config or ServiceConfig.from_env()
        self._ensure_pygame_initialized()

    @classmethod
    def pygame_running(cls) -> bool:
        """Report whether this service started pygame and pygame is still running.

        pygame_initialized alone stays True after pygame.quit() until the next RendererService
        is made (BUGS.md #113), so pygame.get_init() is checked as well.

        Returns:
            True while pygame started by this service has not been quit.

        """
        import pygame

        return cls.pygame_initialized and pygame.get_init()

    @classmethod
    def _ensure_pygame_initialized(cls) -> None:
        """Ensure pygame is initialized in headless mode.

        The class variable records that this service started pygame, but pygame.quit() (from
        anywhere) does not reset it, so pygame.get_init() is checked as well and a quit pygame
        is started again (BUGS.md #110).
        """
        # Headless by default, set before importing/initializing pygame. A driver already chosen
        # is kept, the same rule as tests/harness.py's (BUGS.md #110)
        os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
        os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

        import pygame

        if cls.pygame_initialized and pygame.get_init():
            return

        pygame.init()
        # Create a dummy display surface (required even in headless mode), unless one exists
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1), pygame.HIDDEN)

        cls.pygame_initialized = True
        LOG.info('Pygame initialized in headless mode')

    def render_from_toml(
        self,
        toml_content: str,
        scale: int = 1,
        *,
        render_all_frames: bool = False,
    ) -> RenderResult:
        """Render a sprite from TOML content to PNG.

        Args:
            toml_content: TOML sprite content
            scale: Scale factor for output PNG (1 = original size)
            render_all_frames: If True, render all frames for animated sprites

        Returns:
            RenderResult with PNG data or error

        """
        # Write TOML to a temporary file
        try:
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.toml',
                delete=False,
                encoding='utf-8',
            ) as temp_file:
                temp_file.write(toml_content)
                temp_path = temp_file.name
        except OSError as e:
            LOG.exception('Failed to create temporary file')
            return RenderResult(
                success=False,
                error=f'Failed to create temporary file: {e}',
            )

        try:
            return self._render_sprite_file(
                sprite_path=temp_path, scale=scale, render_all_frames=render_all_frames
            )
        except (ValueError, KeyError, TypeError, AttributeError, OSError) as e:
            LOG.exception('Failed to render sprite')
            return RenderResult(
                success=False,
                error=f'Failed to render sprite: {e}',
            )
        finally:
            # Clean up temporary file
            try:
                Path(temp_path).unlink()
            except OSError as unlink_error:
                LOG.debug('Failed to clean up temporary file %s: %s', temp_path, unlink_error)

    def _render_sprite_file(
        self, *, sprite_path: str, scale: int, render_all_frames: bool
    ) -> RenderResult:
        """Load a sprite file and render it to PNG.

        Args:
            sprite_path: The sprite's TOML file.
            scale: Scale factor for output PNG (1 = original size)
            render_all_frames: If True, render all frames for animated sprites

        Returns:
            RenderResult with PNG data, or the error when the sprite has no frame

        """
        # Load sprite using SpriteFactory
        from glitchygames.sprites import SpriteFactory

        sprite = SpriteFactory.load_sprite(filename=sprite_path)

        # Get sprite dimensions
        current_frame = sprite.get_current_frame()
        if not current_frame:
            return RenderResult(
                success=False,
                error='Failed to get sprite frame',
            )

        width, height = current_frame.get_size()
        LOG.info('Loaded sprite: %sx%s', width, height)

        # Render first frame (or current frame)
        png_bytes, png_base64 = self._render_frame_to_png(current_frame.image, scale)

        # Get frame count - use get_total_frame_count() method on AnimatedSprite
        frame_count = 1
        all_frames_base64 = []

        # Log sprite type for debugging
        LOG.info('Loaded sprite type: %s', type(sprite).__name__)

        if hasattr(sprite, 'get_total_frame_count'):
            frame_count = sprite.get_total_frame_count()
            LOG.info('Sprite has %s total frames (via get_total_frame_count)', frame_count)
        elif hasattr(sprite, 'frames'):
            # Fallback: count frames from the frames property
            total = sum(len(frames) for frames in sprite.frames.values())
            frame_count = total if total > 0 else 1
            LOG.info('Sprite has %s total frames (via frames property)', frame_count)
        else:
            LOG.info('Sprite has no frame count method, type=%s', type(sprite).__name__)

        # Render all frames if requested and sprite is animated
        rendered_frames = []
        LOG.info('render_all_frames=%s, frame_count=%s', render_all_frames, frame_count)
        if render_all_frames and frame_count > 1:
            all_frames_base64, rendered_frames = self._render_all_frames(sprite, scale)
            LOG.info('Rendered %s frames', len(all_frames_base64))
        else:
            LOG.info(
                'Skipping frame rendering: render_all_frames=%s, frame_count=%s',
                render_all_frames,
                frame_count,
            )

        return RenderResult(
            success=True,
            png_bytes=png_bytes,
            png_base64=png_base64,
            width=width * scale,
            height=height * scale,
            frame_count=frame_count,
            all_frames_png_base64=all_frames_base64,
            rendered_frames=rendered_frames,
        )

    def _render_frame_to_png(self, surface: pygame.Surface, scale: int = 1) -> tuple[bytes, str]:
        """Render a pygame surface to PNG bytes with no compression.

        Args:
            surface: Pygame surface to render
            scale: Scale factor (1 = original size)

        Returns:
            Tuple of (png_bytes, png_base64)

        """
        import pygame
        from PIL import Image

        # Scale if needed
        if scale != 1:
            width, height = surface.get_size()
            surface = pygame.transform.scale(surface, (width * scale, height * scale))

        # Convert pygame surface to PIL Image for uncompressed PNG output
        # Get the raw pixel data from the pygame surface
        width, height = surface.get_size()
        raw_data = pygame.image.tobytes(surface, 'RGBA')

        # Create PIL Image from raw data
        pil_image = Image.frombytes('RGBA', (width, height), raw_data)

        # Save to bytes with no compression (compress_level=0)
        buffer = io.BytesIO()
        pil_image.save(buffer, format='PNG', compress_level=0)
        png_bytes = buffer.getvalue()
        png_base64 = base64.b64encode(png_bytes).decode('utf-8')

        return png_bytes, png_base64

    def _get_frame_surface(
        self,
        sprite: AnimatedSprite,
        sprite_frame: SpriteFrame,
        *,
        has_frame_manager: bool,
    ) -> pygame.Surface | None:
        """Get the surface for a single sprite frame.

        Tries frame_manager first, then falls back to direct attribute access.

        Args:
            sprite: The animated sprite
            sprite_frame: The individual frame object
            has_frame_manager: Whether the sprite has a frame_manager

        Returns:
            The frame surface, or None if unavailable

        """
        frame_surface = None

        # First try: get_current_frame() if frame_manager was set
        if has_frame_manager:
            frame = sprite.get_current_frame()
            if frame:
                frame_surface = frame.image

        # Second try: direct access to sprite_frame.image
        if frame_surface is None and hasattr(sprite_frame, 'image'):
            frame_surface = sprite_frame.image

        return frame_surface

    def _render_animation_frames(
        self,
        sprite: AnimatedSprite,
        all_animations: dict[str, list[SpriteFrame]],
        scale: int,
        *,
        has_frame_manager: bool,
    ) -> tuple[list[str], list[RenderedFrame]]:
        """Render frames from all animations of a sprite.

        Args:
            sprite: The animated sprite
            all_animations: Dictionary of animation name to frame lists
            scale: Scale factor for output
            has_frame_manager: Whether the sprite has a frame_manager

        Returns:
            Tuple of (flat list of base64 PNGs, list of RenderedFrame with indices)

        """
        frames_base64: list[str] = []
        rendered_frames: list[RenderedFrame] = []

        for animation_index, (animation_name, frames) in enumerate(all_animations.items()):
            LOG.debug("Animation '%s' has %s frames", animation_name, len(frames))

            if has_frame_manager:
                # Set current animation via frame_manager
                sprite.frame_manager.current_animation = animation_name

            for frame_index, sprite_frame in enumerate(frames):
                if has_frame_manager:
                    # Set current frame via frame_manager
                    sprite.frame_manager.current_frame = frame_index

                frame_surface = self._get_frame_surface(
                    sprite,
                    sprite_frame,
                    has_frame_manager=has_frame_manager,
                )

                if frame_surface is not None:
                    _, png_base64 = self._render_frame_to_png(frame_surface, scale)
                    frames_base64.append(png_base64)
                    rendered_frames.append(
                        RenderedFrame(
                            animation_index=animation_index,
                            frame_index=frame_index,
                            png_base64=png_base64,
                        ),
                    )
                else:
                    LOG.warning(
                        "Could not get surface for frame %s of animation '%s'",
                        frame_index,
                        animation_name,
                    )

        return frames_base64, rendered_frames

    def _render_all_frames(
        self,
        sprite: AnimatedSprite,
        scale: int = 1,
    ) -> tuple[list[str], list[RenderedFrame]]:
        """Render all frames of an animated sprite to PNG.

        Args:
            sprite: AnimatedSprite to render
            scale: Scale factor for output

        Returns:
            Tuple of (flat list of base64 PNGs, list of RenderedFrame with indices)

        """
        # Use public 'frames' property if available, fallback to animation_data
        if hasattr(sprite, 'frames'):
            all_animations = sprite.frames
        elif hasattr(sprite, 'animation_data'):
            all_animations = sprite.animation_data
        else:
            LOG.debug('Sprite has no frames or _animations attribute')
            return [], []

        if not all_animations:
            LOG.debug('Sprite has empty animations dict')
            return [], []

        LOG.debug('Rendering %s animations', len(all_animations))

        # Check if sprite has frame_manager for state restoration
        has_frame_manager = hasattr(sprite, 'frame_manager')

        if has_frame_manager:
            frame_manager = sprite.frame_manager
            original_animation = frame_manager.current_animation
            original_frame = frame_manager.current_frame
            try:
                frames_base64, rendered_frames = self._render_animation_frames(
                    sprite,
                    all_animations,
                    scale,
                    has_frame_manager=has_frame_manager,
                )
            finally:
                # Restore the original state in every case, whatever the starting animation
                # (BUGS.md #110). The animation first: setting it resets the frame
                frame_manager.current_animation = original_animation
                frame_manager.current_frame = original_frame
        else:
            frames_base64, rendered_frames = self._render_animation_frames(
                sprite,
                all_animations,
                scale,
                has_frame_manager=has_frame_manager,
            )

        LOG.debug('Rendered %s total frames', len(frames_base64))
        return frames_base64, rendered_frames

    def render_from_file(
        self,
        file_path: str,
        scale: int = 1,
        *,
        render_all_frames: bool = False,
    ) -> RenderResult:
        """Render a sprite from a file to PNG.

        Args:
            file_path: Path to sprite file (TOML)
            scale: Scale factor for output PNG
            render_all_frames: If True, render all frames for animated sprites

        Returns:
            RenderResult with PNG data or error

        """
        try:
            toml_content = Path(file_path).read_text(encoding='utf-8')
            return self.render_from_toml(toml_content, scale, render_all_frames=render_all_frames)
        except FileNotFoundError:
            return RenderResult(
                success=False,
                error=f'File not found: {file_path}',
            )
        except OSError as e:
            return RenderResult(
                success=False,
                error=f'Failed to read file: {e}',
            )
