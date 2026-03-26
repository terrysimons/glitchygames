"""AnimatedCanvasSprite — main pixel-editing canvas for animated sprites."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self, override

import pygame

from glitchygames.color import RGBA_COMPONENT_COUNT
from glitchygames.sprites import BitmappySprite, SpriteFactory
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from glitchygames.sprites.constants import DEFAULT_FILE_FORMAT

from .canvas_interfaces import (
    AnimatedCanvasInterface,
    AnimatedCanvasRenderer,
    AnimatedSpriteSerializer,
)
from .constants import (
    LARGE_SPRITE_DIMENSION,
    LOG,
    MIN_PIXEL_DISPLAY_SIZE,
)
from .pixel_sprite import BitmapPixelSprite
from .utils import detect_file_format

if TYPE_CHECKING:
    from glitchygames import events
    from glitchygames.bitmappy.editor import BitmapEditorScene


class AnimatedCanvasSprite(BitmappySprite):
    """Animated Canvas Sprite for editing animated sprites."""

    log = LOG

    def __init__(
        self,
        animated_sprite: AnimatedSprite,
        name: str = 'Animated Canvas',
        x: int = 0,
        y: int = 0,
        pixels_across: int = 32,
        pixels_tall: int = 32,
        pixel_width: int = 16,
        pixel_height: int = 16,
        groups: pygame.sprite.LayeredDirty | None = None,  # type: ignore[type-arg]
    ) -> None:
        """Initialize the Animated Canvas Sprite."""
        # Initialize dimensions and get canvas size
        width, height = self._initialize_dimensions(
            pixels_across, pixels_tall, pixel_width, pixel_height,
        )

        # Initialize parent class first to create rect
        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            groups=groups,  # type: ignore[arg-type]
        )

        # Override pixels_across and pixels_tall with correct pixel dimensions
        # (BitmappySprite.__init__ sets them to screen dimensions)
        self.pixels_across = pixels_across
        self.pixels_tall = pixels_tall

        # Parent scene reference, set externally after construction
        self.parent_scene: BitmapEditorScene | None = None

        # Initialize sprite data and frame management
        self._initialize_sprite_data(animated_sprite)

        # Initialize pixel arrays and color settings
        self._initialize_pixel_arrays()

        # Initialize panning system
        self._initialize_simple_panning()

        # Initialize canvas surface and UI components
        self._initialize_canvas_surface(x, y, width, height, groups)  # type: ignore[arg-type]

        # Initialize hover tracking for pixel hover effects
        self.hovered_pixel: tuple[int, int] | None = None

        # Initialize hover tracking for canvas border effect
        self.is_hovered: bool = False

        # Mini view reference for synchronized pixel updates (set externally)
        self.mini_view: AnimatedCanvasSprite | None = None

    def _initialize_dimensions(
        self, pixels_across: int, pixels_tall: int, pixel_width: int, pixel_height: int,
    ) -> tuple[int, int]:
        """Initialize canvas dimensions and pixel sizing.

        Args:
            pixels_across: Number of pixels across the canvas
            pixels_tall: Number of pixels tall the canvas
            pixel_width: Width of each pixel in screen coordinates
            pixel_height: Height of each pixel in screen coordinates

        Returns:
            Tuple of (width, height) for the canvas surface

        """
        self.pixels_across = pixels_across
        self.pixels_tall = pixels_tall
        self.pixel_width = pixel_width
        self.pixel_height = pixel_height
        width = self.pixels_across * self.pixel_width
        height = self.pixels_tall * self.pixel_height
        return width, height

    def _initialize_sprite_data(self, animated_sprite: AnimatedSprite) -> None:
        """Initialize animated sprite and frame data.

        Args:
            animated_sprite: The animated sprite to associate with this canvas

        """
        self.animated_sprite: AnimatedSprite = animated_sprite
        # Use the sprite's current animation if set and not empty, otherwise start empty
        if hasattr(animated_sprite, 'current_animation') and animated_sprite.current_animation:
            self.current_animation = animated_sprite.current_animation
        else:
            self.current_animation = ''  # Start with empty animation
        # Sync the canvas frame with the animated sprite's current frame
        self.current_frame = animated_sprite.current_frame
        self.log.debug(
            'Canvas initialized - animated_sprite.current_frame='
            f'{animated_sprite.current_frame}, canvas.current_frame={self.current_frame}',
        )

        # Initialize manual frame selection flag to allow automatic animation updates
        self._manual_frame_selected = False

        # Sync canvas pixels with the current frame
        self._update_canvas_from_current_frame()

    def _initialize_pixel_arrays(self) -> None:
        """Initialize pixel arrays and color settings."""
        # Initialize pixels with magenta as the transparent/background color (RGBA)
        self.pixels = [(255, 0, 255, 255) for _ in range(self.pixels_across * self.pixels_tall)]
        self.dirty_pixels = [True] * len(self.pixels)
        self.background_color = (128, 128, 128)
        self.active_color = (0, 0, 0, 255)
        # Set border thickness using the internal method
        self._update_border_thickness()

    def _update_border_thickness(self) -> None:
        """Update border thickness based on pixel size.

        For large sprites where pixel size becomes very small, use no border
        to prevent grid from consuming all space. This happens when the 320x320
        constraint kicks in, making pixel size 2x2 or smaller.

        For very large sprites (128x128), also disable borders to prevent visual clutter.
        """
        # Disable borders for very small pixels (2x2 or smaller) or very large sprites (128x128)
        should_disable_borders = (
            (
                self.pixel_width <= MIN_PIXEL_DISPLAY_SIZE
                and self.pixel_height <= MIN_PIXEL_DISPLAY_SIZE
            )  # Very small pixels
            or (
                self.pixels_across >= LARGE_SPRITE_DIMENSION
                or self.pixels_tall >= LARGE_SPRITE_DIMENSION
            )  # Very large sprites
        )

        old_border_thickness = getattr(self, 'border_thickness', 1)
        self.border_thickness = 0 if should_disable_borders else 1

        # Clear pixel cache if border thickness changed
        if old_border_thickness != self.border_thickness:
            BitmapPixelSprite.PIXEL_CACHE.clear()
            self.log.info(
                f'Cleared pixel cache due to border thickness change ({old_border_thickness} ->'
                f' {self.border_thickness})',
            )

        self.log.info(
            f'Border thickness set to {self.border_thickness} (pixel size:'
            f' {self.pixel_width}x{self.pixel_height}, sprite size:'
            f' {self.pixels_across}x{self.pixels_tall})',
        )

    def _compute_panned_pixels(self, frame_pixels: list[tuple[int, ...]]) -> list[tuple[int, ...]]:
        """Compute panned pixel data by shifting source coordinates.

        Args:
            frame_pixels: Original pixel data from the frame.

        Returns:
            New pixel list with panning offsets applied.

        """
        frame_width = len(frame_pixels) // self.pixels_tall if self.pixels_tall > 0 else 0
        transparent = (255, 0, 255)
        panned_pixels: list[tuple[int, ...]] = []

        for y in range(self.pixels_tall):
            for x in range(self.pixels_across):
                source_x = x - self.pan_offset_x
                source_y = y - self.pan_offset_y

                if not (0 <= source_x < frame_width and 0 <= source_y < self.pixels_tall):
                    panned_pixels.append(transparent)
                    continue

                source_index = source_y * frame_width + source_x
                if source_index < len(frame_pixels):
                    panned_pixels.append(frame_pixels[source_index])
                else:
                    panned_pixels.append(transparent)

        return panned_pixels

    def _pan_frame_data(self) -> None:
        """Pan the frame data directly by shifting pixels within the frame."""
        if not hasattr(self, 'animated_sprite') or not self.animated_sprite:
            return

        current_animation = self.current_animation
        current_frame = self.current_frame

        if current_animation not in self.animated_sprite.frames:
            return
        if current_frame >= len(self.animated_sprite.frames[current_animation]):
            return

        frame = self.animated_sprite._animations[current_animation][current_frame]  # type: ignore[reportPrivateUsage]
        if not (hasattr(frame, 'get_pixel_data') and hasattr(frame, 'set_pixel_data')):
            return

        frame_pixels = frame.get_pixel_data()
        panned_pixels = self._compute_panned_pixels(frame_pixels)

        frame.set_pixel_data(panned_pixels)
        self.pixels = panned_pixels.copy()
        self.dirty_pixels = [True] * len(self.pixels)

        # Clear surface cache
        if hasattr(self.animated_sprite, '_surface_cache'):
            cache_key = f'{current_animation}_{current_frame}'
            if cache_key in self.animated_sprite._surface_cache:  # type: ignore[reportPrivateUsage]
                del self.animated_sprite._surface_cache[cache_key]  # type: ignore[reportPrivateUsage]

        self.log.debug(f'Frame data panned: offset=({self.pan_offset_x}, {self.pan_offset_y})')

    def _initialize_simple_panning(self) -> None:
        """Initialize the simple panning system for the canvas."""
        # Frame-specific panning state - each frame has its own panning
        # Format: {frame_key: {'pan_x': int, 'pan_y': int,
        #          'original_pixels': list, 'active': bool}}
        self._frame_panning: dict[str, dict[str, Any]] = {}

        self.log.debug('Simple panning system initialized with frame-specific state')

    def _get_current_frame_key(self) -> str:
        """Get a unique key for the current frame.

        Returns:
            str: The current frame key.

        """
        return f'{self.current_animation}_{self.current_frame}'

    def _store_original_frame_data_for_frame(self, frame_key: str) -> None:
        """Store the original frame data for a specific frame."""
        if hasattr(self, 'pixels') and self.pixels:
            self._frame_panning[frame_key]['original_pixels'] = list(self.pixels)
            self.log.debug('Stored original frame data for %s', frame_key)

    def _apply_panning_view_for_frame(self, frame_key: str) -> None:
        """Apply panning transformation for a specific frame."""
        frame_state = self._frame_panning[frame_key]
        if frame_state['original_pixels'] is None:
            return

        # Create panned view by shifting pixels
        panned_pixels: list[tuple[int, ...]] = []

        for y in range(self.pixels_tall):
            for x in range(self.pixels_across):
                # Calculate source coordinates (where to read from in original)
                source_x = x - frame_state['pan_x']
                source_y = y - frame_state['pan_y']

                # Check if source is within bounds
                if 0 <= source_x < self.pixels_across and 0 <= source_y < self.pixels_tall:
                    source_index = source_y * self.pixels_across + source_x
                    if source_index < len(frame_state['original_pixels']):
                        panned_pixels.append(frame_state['original_pixels'][source_index])
                    else:
                        panned_pixels.append((255, 0, 255))  # Transparent
                else:
                    panned_pixels.append((255, 0, 255))  # Transparent

        # Update canvas pixels with panned view
        self.pixels = panned_pixels
        self.dirty_pixels = [True] * len(self.pixels)

        self.log.debug(
            f'Applied panning view for {frame_key}: offset=({frame_state["pan_x"]},'
            f' {frame_state["pan_y"]})',
        )

    def reset_panning(self) -> None:
        """Reset panning for the current frame."""
        frame_key = self._get_current_frame_key()

        # Clear panning state for current frame
        if frame_key in self._frame_panning:
            self._frame_panning[frame_key] = {
                'pan_x': 0,
                'pan_y': 0,
                'original_pixels': None,
                'active': False,
            }

        # Reload the original frame data
        if hasattr(self, 'animated_sprite') and self.animated_sprite:
            current_animation = self.current_animation
            current_frame = self.current_frame

            if current_animation in self.animated_sprite.frames and current_frame < len(
                self.animated_sprite.frames[current_animation],
            ):
                frame = self.animated_sprite._animations[current_animation][current_frame]  # type: ignore[reportPrivateUsage]
                if hasattr(frame, 'get_pixel_data'):
                    self.pixels = frame.get_pixel_data().copy()
                    self.dirty_pixels = [True] * len(self.pixels)
                    self.dirty = 1

        self.log.debug('Panning reset for frame %s', frame_key)

    def is_panning_active(self) -> bool:
        """Check if panning is active for the current frame.

        Returns:
            bool: True if is panning active, False otherwise.

        """
        frame_key = self._get_current_frame_key()
        if frame_key in self._frame_panning:
            return self._frame_panning[frame_key]['active']
        return False

    def _initialize_canvas_surface(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        groups: pygame.sprite.LayeredDirty | None,  # type: ignore[type-arg]
    ) -> None:
        """Initialize canvas surface and interface components.

        Args:
            x: X position of the canvas
            y: Y position of the canvas
            width: Width of the canvas surface
            height: Height of the canvas surface
            groups: Sprite groups to add components to

        """
        # Create initial surface
        self.image = pygame.Surface((self.width, self.height))
        self.rect = self.image.get_rect(x=x, y=y)

        # Initialize interface components for animated sprites
        self.canvas_interface = AnimatedCanvasInterface(self)
        # Sync the canvas interface with the canvas's current frame
        self.canvas_interface.set_current_frame(self.current_animation, self.current_frame)
        self.sprite_serializer = AnimatedSpriteSerializer()
        self.canvas_renderer = AnimatedCanvasRenderer(self)

        # Multiple film strips disabled - only showing first animation

        # Film strips will be created in the main scene after canvas setup

        # Film strip sprites are added to groups in _create_multiple_film_strips

        # Show the first frame
        self.show_frame(self.current_animation, self.current_frame)

        # Force initial draw
        self.dirty = 1
        self.force_redraw()

    def _get_current_frame_pixels(self) -> list[tuple[int, int, int, int]]:
        """Get pixel data from the current frame of the animated sprite as RGBA.

        Returns:
            list[tuple[int, int, int, int]]: The current frame pixels.

        """
        pixels = []

        if hasattr(self, 'animated_sprite') and self.animated_sprite:
            # Check if this is a static sprite (no frames)
            if (
                not hasattr(self.animated_sprite, '_animations')
                or not self.animated_sprite._animations  # type: ignore[reportPrivateUsage]
            ):
                # Static sprite - get pixels directly
                if hasattr(self.animated_sprite, 'get_pixel_data'):
                    pixels = self.animated_sprite.get_pixel_data()  # type: ignore[union-attr]
                    self.log.debug(
                        f'Got pixels from animated_sprite.get_pixel_data(): {len(pixels)} pixels, '  # type: ignore[arg-type]
                        f'first few: {pixels[:5]}',
                    )
                elif hasattr(self.animated_sprite, 'pixels'):
                    pixels = self.animated_sprite.pixels.copy()  # type: ignore[union-attr]
                    self.log.debug(
                        f'Got pixels from animated_sprite.pixels: {len(pixels)} pixels, '  # type: ignore[arg-type]
                        f'first few: {pixels[:5]}',
                    )

            # Animated sprite with frames
            current_animation = self.current_animation
            current_frame = self.current_frame
            self.log.debug(
                "Getting frame pixels for animation '%s', frame %s", current_animation, current_frame,
            )

            if current_animation in self.animated_sprite._animations and current_frame < len(  # type: ignore[reportPrivateUsage]
                self.animated_sprite._animations[current_animation],  # type: ignore[reportPrivateUsage]
            ):
                frame = self.animated_sprite._animations[current_animation][current_frame]  # type: ignore[reportPrivateUsage]
                if hasattr(frame, 'get_pixel_data'):
                    pixels = frame.get_pixel_data()
                    self.log.debug(
                        f'Got pixels from frame.get_pixel_data(): {len(pixels)} pixels, '
                        f'first few: {pixels[:5]}',
                    )
                else:
                    self.log.warning('Frame has no get_pixel_data method')
            else:
                self.log.warning(
                    "Animation '%s' or frame %s not found", current_animation, current_frame,
                )

        # Fallback to static pixels
        if not pixels:
            pixels = self.pixels.copy()
            self.log.debug(
                f'Using fallback canvas pixels: {len(pixels)} pixels, first few: {pixels[:5]}',
            )

        # Ensure all pixels are RGBA format
        rgba_pixels: list[tuple[int, ...]] = []
        for pixel in pixels:  # type: ignore[union-attr]
            if len(pixel) == RGBA_COMPONENT_COUNT:  # type: ignore[arg-type]
                rgba_pixels.append(pixel)  # type: ignore[arg-type]
            else:
                # Convert RGB to RGBA with full opacity
                rgba_pixels.append((pixel[0], pixel[1], pixel[2], 255))  # type: ignore[arg-type]

        return rgba_pixels  # type: ignore[return-value]

    def _update_canvas_from_current_frame(self) -> None:
        """Update the canvas pixels with the current frame data."""
        if hasattr(self, 'animated_sprite') and self.animated_sprite:
            # Use the canvas's current animation and frame (not the animated sprite's)
            current_animation = self.current_animation
            current_frame = self.current_frame
            self.log.info('DEBUG: Syncing canvas with frame %s[%s]', current_animation, current_frame)
            if current_animation in self.animated_sprite._animations and current_frame < len(  # type: ignore[reportPrivateUsage]
                self.animated_sprite._animations[current_animation],  # type: ignore[reportPrivateUsage]
            ):
                frame = self.animated_sprite._animations[current_animation][current_frame]  # type: ignore[reportPrivateUsage]
                if hasattr(frame, 'get_pixel_data'):
                    frame_pixels = frame.get_pixel_data()
                    self.log.info(
                        f'DEBUG: Frame pixels: {len(frame_pixels)} pixels, first few:'
                        f' {frame_pixels[:5]}',
                    )
                    self.log.info(
                        f'DEBUG: Frame pixel types: {[type(p) for p in frame_pixels[:3]]}',
                    )
                    self.log.info(
                        f'DEBUG: All frame pixels same color: {len(set(frame_pixels)) == 1}',
                    )
                    self.pixels = frame_pixels
                    self.dirty_pixels = [True] * len(self.pixels)
                    self.log.info('Updated canvas pixels from frame %s', current_frame)
                    # Mark canvas dirty to ensure redraw applies per-pixel alpha on load
                    self.dirty = 1
                else:
                    self.log.info('DEBUG: Frame has no get_pixel_data method')
            else:
                self.log.info(
                    "DEBUG: Animation '%s' or frame %s not found", current_animation, current_frame,
                )
        else:
            self.log.info('DEBUG: No animated_sprite available for canvas sync')

    def set_frame(self, frame_index: int) -> None:
        """Set the current frame index for the current animation."""
        if hasattr(self, 'animated_sprite') and self.animated_sprite:
            frames = self.animated_sprite._animations  # type: ignore[reportPrivateUsage]
            if self.current_animation in frames and 0 <= frame_index < len(
                frames[self.current_animation],
            ):
                # Store the current playing state
                was_playing = self.animated_sprite.is_playing

                # Pause the animation when manually selecting frames
                self.animated_sprite.pause()

                self.current_frame = frame_index
                self.animated_sprite.set_frame(frame_index)

                # Mark that user manually selected a frame
                self._manual_frame_selected = True

                # Update the canvas interface
                self.canvas_interface.set_current_frame(self.current_animation, frame_index)

                # Update the undo/redo manager with the current frame for frame-specific operations
                if (
                    hasattr(self, 'parent_scene')
                    and self.parent_scene
                    and hasattr(self.parent_scene, 'undo_redo_manager')
                ):
                    self.parent_scene.undo_redo_manager.set_current_frame(
                        self.current_animation, frame_index,
                    )

                # Only restart animation if it was playing before
                if was_playing:
                    self.animated_sprite.play()
                    self._manual_frame_selected = False
                else:
                    # Keep it paused if it was already paused
                    self.log.debug(
                        'Animation was paused, keeping it paused at frame %s', frame_index,
                    )

                self.dirty = 1
                self.log.debug(
                    f'Set frame to {frame_index} for animation '
                    f"'{self.current_animation}' (was_playing: {was_playing})",
                )

    def _should_track_frame_selection(self) -> bool:
        """Check if frame selection changes should be tracked for undo/redo.

        Returns:
            True if frame selection should be tracked.

        """
        if not (hasattr(self, 'parent_scene') and self.parent_scene):
            return False
        parent = self.parent_scene
        if not hasattr(parent, 'undo_redo_manager'):
            return False
        return not (
            getattr(parent, '_applying_undo_redo', False)
            or getattr(parent, '_creating_frame', False)
            or getattr(parent, '_creating_animation', False)
        )

    def show_frame(self, animation: str, frame: int) -> None:
        """Show a specific frame of the animated sprite."""
        self.log.debug('show_frame called: animation=%s, frame=%s', animation, frame)
        frames = self.animated_sprite._animations  # type: ignore[reportPrivateUsage]
        if animation in frames and 0 <= frame < len(frames[animation]):
            self.current_animation = animation
            self.current_frame = frame
            self.log.debug(
                f'Canvas updated: current_animation={self.current_animation},'
                f' current_frame={self.current_frame}',
            )

            # Update the animated sprite to the new animation and frame
            if animation != self.animated_sprite.current_animation:
                self.animated_sprite.set_animation(animation)
            self.animated_sprite.set_frame(frame)

            # Update the canvas interface
            self.canvas_interface.set_current_frame(animation, frame)

            # Update the undo/redo manager with the current frame for frame-specific operations
            # Only track frame selection if we're not in the middle of an undo/redo operation
            # or creating a frame (which has its own undo tracking)
            # Also don't track frame selection if we're in the middle of film strip operations
            if self._should_track_frame_selection():
                # Track frame selection as a film strip operation instead of global
                assert self.parent_scene is not None
                self.parent_scene.film_strip_operation_tracker.add_frame_selection(animation, frame)

            # Force the canvas to redraw with the new frame
            self.force_redraw()

            # Notify the parent scene about the frame change
            if hasattr(self, 'parent_scene') and self.parent_scene:
                self.log.debug('Notifying parent scene about frame change: %s[%s]', animation, frame)
                self.parent_scene.film_strip_coordinator.update_film_strips_for_frame(
                    animation, frame,
                )
            else:
                self.log.debug('No parent scene found to notify about frame change')

            # Get the frame data
            frame_obj = frames[animation][frame]
            if hasattr(frame_obj, 'get_pixel_data'):
                self.pixels = frame_obj.get_pixel_data()
            else:
                # Fallback to frame pixels if available
                self.pixels = getattr(
                    frame_obj, 'pixels', [(255, 0, 255)] * (self.pixels_across * self.pixels_tall),
                )

            # Mark all pixels as dirty
            self.dirty_pixels = [True] * len(self.pixels)
            self.dirty = 1

            # Notify parent scene to update film strips
            if hasattr(self, 'parent_scene') and self.parent_scene:
                self.parent_scene.film_strip_coordinator.update_film_strips_for_frame(
                    animation, frame,
                )

            # Note: Live preview functionality is now integrated into the film strip

    def next_frame(self) -> None:
        """Move to the next frame in the current animation."""
        frames = self.animated_sprite._animations  # type: ignore[reportPrivateUsage]
        if self.current_animation in frames:
            frame_list = frames[self.current_animation]
            self.current_frame = (self.current_frame + 1) % len(frame_list)
            self.show_frame(self.current_animation, self.current_frame)

            # Notify the parent scene about the frame change
            if hasattr(self, 'parent_scene') and self.parent_scene:
                self.log.debug(
                    'Notifying parent scene about frame change:'
                    f' {self.current_animation}[{self.current_frame}]',
                )
                self.parent_scene.film_strip_coordinator.switch_to_film_strip(
                    self.current_animation, self.current_frame,
                )

    def previous_frame(self) -> None:
        """Move to the previous frame in the current animation."""
        frames = self.animated_sprite._animations  # type: ignore[reportPrivateUsage]
        if self.current_animation in frames:
            frame_list = frames[self.current_animation]
            self.current_frame = (self.current_frame - 1) % len(frame_list)
            self.show_frame(self.current_animation, self.current_frame)

            # Notify the parent scene about the frame change
            if hasattr(self, 'parent_scene') and self.parent_scene:
                self.log.debug(
                    'Notifying parent scene about frame change:'
                    f' {self.current_animation}[{self.current_frame}]',
                )
                self.parent_scene.film_strip_coordinator.switch_to_film_strip(
                    self.current_animation, self.current_frame,
                )

    def next_animation(self) -> None:
        """Move to the next animation."""
        self.log.debug(f'next_animation called, current_animation={self.current_animation}')
        frames = self.animated_sprite._animations  # type: ignore[reportPrivateUsage]
        animations = list(frames.keys())
        self.log.debug('Available animations: %s', animations)
        if animations:
            current_index = animations.index(self.current_animation)
            next_index = (current_index + 1) % len(animations)
            next_animation = animations[next_index]

            # Preserve the current frame number when switching animations
            preserved_frame = self.current_frame
            # Ensure the frame number is within bounds for the new animation
            if next_animation in frames and len(frames[next_animation]) > 0:
                max_frame = len(frames[next_animation]) - 1
                preserved_frame = min(preserved_frame, max_frame)
            else:
                preserved_frame = 0
            self.log.debug(
                f'Moving from animation {self.current_animation} (index {current_index}) to'
                f' {next_animation} (index {next_index}), preserving frame {preserved_frame}',
            )
            self.show_frame(next_animation, preserved_frame)
            self.log.debug(
                f'After show_frame: current_animation={self.current_animation},'
                f' current_frame={self.current_frame}',
            )

            # Notify the parent scene to switch film strips
            if hasattr(self, 'parent_scene') and self.parent_scene:
                self.log.debug('Notifying parent scene to switch to film strip %s', next_animation)
                self.parent_scene.film_strip_coordinator.switch_to_film_strip(
                    next_animation, preserved_frame,
                )

    def previous_animation(self) -> None:
        """Move to the previous animation."""
        self.log.debug(f'previous_animation called, current_animation={self.current_animation}')
        frames = self.animated_sprite._animations  # type: ignore[reportPrivateUsage]
        animations = list(frames.keys())
        self.log.debug('Available animations: %s', animations)
        if animations:
            current_index = animations.index(self.current_animation)
            prev_index = (current_index - 1) % len(animations)
            prev_animation = animations[prev_index]

            # Preserve the current frame number when switching animations
            preserved_frame = self.current_frame
            # Ensure the frame number is within bounds for the new animation
            if prev_animation in frames and len(frames[prev_animation]) > 0:
                max_frame = len(frames[prev_animation]) - 1
                preserved_frame = min(preserved_frame, max_frame)
            else:
                preserved_frame = 0
            self.log.debug(
                f'Moving from animation {self.current_animation} (index {current_index}) to'
                f' {prev_animation} (index {prev_index}), preserving frame {preserved_frame}',
            )
            self.show_frame(prev_animation, preserved_frame)
            self.log.debug(
                f'After show_frame: current_animation={self.current_animation},'
                f' current_frame={self.current_frame}',
            )

            # Notify the parent scene to switch film strips
            if hasattr(self, 'parent_scene') and self.parent_scene:
                self.log.debug('Notifying parent scene to switch to film strip %s', prev_animation)
                self.parent_scene.film_strip_coordinator.switch_to_film_strip(
                    prev_animation, preserved_frame,
                )

    def handle_keyboard_event(self, key: int) -> None:
        """Handle keyboard navigation events."""
        self.log.debug('Keyboard event received: key=%s', key)

        if key == pygame.K_LEFT:
            self.log.debug('LEFT arrow pressed')
            self.previous_frame()
        elif key == pygame.K_RIGHT:
            self.log.debug('RIGHT arrow pressed')
            self.next_frame()
        elif key == pygame.K_UP:
            self.log.debug('UP arrow pressed')
            self.previous_animation()
        elif key == pygame.K_DOWN:
            self.log.debug('DOWN arrow pressed')
            self.next_animation()
        elif pygame.K_0 <= key <= pygame.K_9:
            # Handle 0-9 keys for frame selection
            frame_index = key - pygame.K_0
            self.log.debug('Number key %s pressed', frame_index)
            self.set_frame(frame_index)
        elif key == pygame.K_SPACE:
            # Toggle animation play/pause
            self.log.debug('SPACE key pressed')
            if hasattr(self, 'animated_sprite') and self.animated_sprite:
                current_state = self.animated_sprite.is_playing
                self.log.debug('Current animation state: is_playing=%s', current_state)
                if self.animated_sprite.is_playing:
                    self.animated_sprite.pause()
                    self.log.debug('Animation paused')
                else:
                    # Restart animation from current frame
                    self.animated_sprite.play()
                    self.log.debug('Animation restarted')
                self.log.debug(f'New animation state: is_playing={self.animated_sprite.is_playing}')

                # Note: Live preview functionality is now integrated into the film strip
        else:
            self.log.debug('Unhandled key: %s', key)

    def copy_current_frame(self) -> None:
        """Copy the current frame to clipboard."""
        # Get the current frame data
        frames = self.animated_sprite._animations  # type: ignore[reportPrivateUsage]
        if self.current_animation in frames and self.current_frame < len(
            frames[self.current_animation],
        ):
            frame = frames[self.current_animation][self.current_frame]
            # Store the pixel data in a simple clipboard attribute
            self._clipboard = frame.get_pixel_data().copy()

    def paste_to_current_frame(self) -> None:
        """Paste clipboard content to current frame."""
        if hasattr(self, '_clipboard') and self._clipboard:
            # Get the current frame
            frames = self.animated_sprite._animations  # type: ignore[reportPrivateUsage]
            if self.current_animation in frames and self.current_frame < len(
                frames[self.current_animation],
            ):
                frame = frames[self.current_animation][self.current_frame]
                # Set the pixel data
                frame.set_pixel_data(self._clipboard)
                # Update the canvas pixels
                self.pixels = self._clipboard.copy()
                # Mark as dirty
                self.dirty_pixels = [True] * len(self.pixels)
                self.dirty = 1

    def save_animated_sprite(self, filename: str) -> None:
        """Save the animated sprite to a file."""
        if self.is_panning_active():
            # Save viewport only when panning is active
            self.log.info('Saving viewport only due to active panning')
            self._save_viewport_sprite(filename)
        else:
            # Save full sprite when not panning
            # Prefer canvas.animated_sprite if available
            sprite_to_save = None
            if hasattr(self, 'canvas') and self.canvas and hasattr(self.canvas, 'animated_sprite'):  # type: ignore[attr-defined]
                sprite_to_save = self.canvas.animated_sprite  # type: ignore[attr-defined]
            elif hasattr(self, 'animated_sprite'):
                sprite_to_save = self.animated_sprite

            if sprite_to_save:
                self.sprite_serializer.save(sprite_to_save, filename, DEFAULT_FILE_FORMAT)  # type: ignore[arg-type]
            else:
                self.log.error('No sprite found to save')

    @classmethod
    def from_file(
        cls,
        filename: str,
        x: int = 0,
        y: int = 0,
        pixels_across: int = 32,
        pixels_tall: int = 32,
        pixel_width: int = 16,
        pixel_height: int = 16,
        groups: pygame.sprite.LayeredDirty | None = None,  # type: ignore[type-arg]
    ) -> Self:
        """Create an AnimatedCanvasSprite from a file.

        Returns:
            AnimatedCanvasSprite: The newly created animated canvas sprite.

        Raises:
            ValueError: If the file does not contain animated sprite data.

        """
        # Load the animated sprite
        animated_sprite = SpriteFactory.load_sprite(filename=filename)

        if not hasattr(animated_sprite, 'frames'):
            raise ValueError(f'File {filename} does not contain animated sprite data')

        return cls(
            animated_sprite=animated_sprite,
            name='Animated Canvas',
            x=x,
            y=y,
            pixels_across=pixels_across,
            pixels_tall=pixels_tall,
            pixel_width=pixel_width,
            pixel_height=pixel_height,
            groups=groups,
        )

    def update_animation(self, dt: float) -> None:
        """Update the animated sprite with delta time."""
        if hasattr(self, 'animated_sprite') and self.animated_sprite:
            self.animated_sprite.update(dt)

    @override
    def update(self) -> None:
        """Update the canvas sprite."""
        # Animation timing is handled by the scene's update_animation method

        # Force redraw if dirty
        if self.dirty:
            self.force_redraw()
            self.dirty = 0

    def force_redraw(self) -> None:
        """Force a complete redraw of the canvas."""
        # Use the interface-based rendering while maintaining existing behavior
        self.image = self.canvas_renderer.force_redraw(self)

    @override
    def on_left_mouse_button_down_event(self, event: events.HashableEvent) -> None:
        """Handle the left mouse button down event."""
        # self.log.debug(f"AnimatedCanvasSprite mouse down event at {event.pos}, rect: {self.rect}")
        if self.rect.collidepoint(event.pos):
            x = (event.pos[0] - self.rect.x) // self.pixel_width
            y = (event.pos[1] - self.rect.y) // self.pixel_height
            # self.log.debug(f"AnimatedCanvasSprite clicked at pixel ({x}, {y})")

            # Mark that we're starting a potential drag operation
            self._drag_active = False  # Will be set to True on first drag event
            self._drag_pixels: dict[
                tuple[int, int], tuple[int, int, tuple[int, ...], tuple[int, ...]],
            ] = {}  # Track pixels changed during drag for batched updates

            # Check for control-click (flood fill mode)
            is_control_click = (
                pygame.key.get_pressed()[pygame.K_LCTRL] or pygame.key.get_pressed()[pygame.K_RCTRL]
            )

            if is_control_click:
                # Flood fill mode
                self.log.info('Control-click detected - performing flood fill at (%s, %s)', x, y)
                self._flood_fill(x, y, self.active_color)  # type: ignore[arg-type]
            else:
                # Normal click mode
                # Mark that user is editing (manual frame selection)
                self._manual_frame_selected = True

                # Don't sync the canvas frame - keep it on the frame being edited
                # The canvas should stay on the current frame, only the live preview should animate

                # Use the interface to set the pixel
                self.canvas_interface.set_pixel_at(x, y, self.active_color)

            # Force redraw the canvas to show the changes
            self.force_redraw()

            # Note: Live preview functionality is now integrated into the film strip
        else:
            self.log.debug(
                f'AnimatedCanvasSprite click missed - pos {event.pos} not in rect {self.rect}',
            )

    def _cache_drag_frame(self) -> None:
        """Cache the current frame reference for the active drag operation."""
        if hasattr(self, '_drag_frame'):
            return
        if (
            hasattr(self, 'animated_sprite')
            and hasattr(self, 'current_animation')
            and hasattr(self, 'current_frame')
            and self.current_animation in self.animated_sprite.frames
        ):
            self._drag_frame = self.animated_sprite._animations[self.current_animation][  # type: ignore[reportPrivateUsage]
                self.current_frame
            ]
        else:
            self._drag_frame = None

    def _get_old_pixel_color(self, pixel_num: int) -> tuple[int, ...]:
        """Get the old color at a pixel position, preferring frame data over canvas.

        Args:
            pixel_num: Linear pixel index.

        Returns:
            The pixel color tuple.

        """
        old_color = self.pixels[pixel_num]
        if self._drag_frame is None:
            return old_color

        # Fast path: directly access frame.pixels to avoid array copy
        if hasattr(self._drag_frame, 'pixels') and pixel_num < len(self._drag_frame.pixels):
            return self._drag_frame.pixels[pixel_num]

        # Fallback: use get_pixel_data() copy (rare)
        frame_pixels = self._drag_frame.get_pixel_data()
        return frame_pixels[pixel_num] if pixel_num < len(frame_pixels) else (255, 0, 255, 255)

    def _update_drag_frame_pixel(self, pixel_num: int, color: tuple[int, ...]) -> None:
        """Update a single pixel in the drag frame with optimized paths.

        Args:
            pixel_num: Linear pixel index.
            color: New color tuple.

        """
        if self._drag_frame is None:
            return

        # Fast path: directly modify frame.pixels (avoids array copies)
        if hasattr(self._drag_frame, 'pixels'):
            if pixel_num < len(self._drag_frame.pixels):
                self._drag_frame.pixels[pixel_num] = color
                if not hasattr(self._drag_frame, '_image_stale'):
                    self._drag_frame._image_stale = True  # type: ignore[attr-defined]
            return

        # Fallback: slower get/set_pixel_data path
        frame_pixels = self._drag_frame.get_pixel_data()
        if pixel_num < len(frame_pixels):
            frame_pixels[pixel_num] = color
            self._drag_frame.set_pixel_data(frame_pixels)
            self._clear_surface_cache()

    def _clear_surface_cache(self) -> None:
        """Clear the surface cache entry for the current animation frame."""
        if hasattr(self, 'animated_sprite') and hasattr(self.animated_sprite, '_surface_cache'):
            cache_key = f'{self.current_animation}_{self.current_frame}'
            if cache_key in self.animated_sprite._surface_cache:  # type: ignore[reportPrivateUsage]
                del self.animated_sprite._surface_cache[cache_key]  # type: ignore[reportPrivateUsage]

    def _rebuild_frame_image_from_pixels(self, frame: SpriteFrame) -> None:
        """Rebuild a frame's image surface from its pixel data.

        Args:
            frame: The frame object with pixels and _image attributes.

        """
        if not (hasattr(frame, 'pixels') and hasattr(frame, '_image') and frame._image is not None):  # type: ignore[reportPrivateUsage]
            return

        width, height = frame._image.get_size()  # type: ignore[reportPrivateUsage]
        for i, pixel in enumerate(frame.pixels):
            if i < width * height:
                frame._image.set_at((i % width, i // width), pixel)  # type: ignore[reportPrivateUsage]

        # Clear stale flag since image is now up to date
        if hasattr(frame, '_image_stale'):
            del frame._image_stale  # type: ignore[attr-defined]

    @override
    def on_left_mouse_drag_event(self, event: events.HashableEvent, trigger: object) -> None:
        """Handle mouse drag events.

        Optimized path that updates visuals but defers expensive ops.
        """
        if not self.rect.collidepoint(event.pos):
            return

        x = (event.pos[0] - self.rect.x) // self.pixel_width
        y = (event.pos[1] - self.rect.y) // self.pixel_height

        if not (0 <= x < self.pixels_across and 0 <= y < self.pixels_tall):
            return

        self._drag_active = True
        if not hasattr(self, '_drag_pixels'):
            self._drag_pixels = {}  # Already typed in on_left_mouse_button_down_event

        self._cache_drag_frame()

        pixel_key = (x, y)
        pixel_num = y * self.pixels_across + x

        # Store pixel change with old color (only once per unique pixel during drag)
        if pixel_key not in self._drag_pixels:
            old_color = self._get_old_pixel_color(pixel_num)
            self._drag_pixels[pixel_key] = (x, y, old_color, self.active_color)

        # Update pixel data for immediate visual feedback
        self.pixels[pixel_num] = self.active_color
        self.dirty_pixels[pixel_num] = True

        # Update frame data immediately so renderer shows the change
        self._update_drag_frame_pixel(pixel_num, self.active_color)

        # Throttle full redraws during drag - only redraw every 3 drag events
        if not hasattr(self, '_drag_redraw_counter'):
            self._drag_redraw_counter = 0
        self._drag_redraw_counter += 1

        if self._drag_redraw_counter % 3 == 0:
            if self._drag_frame is not None:
                self._rebuild_frame_image_from_pixels(self._drag_frame)

            self.dirty = 1
            if hasattr(self, 'parent_scene') and self.parent_scene:
                self.parent_scene.film_strip_coordinator._update_film_strips_for_pixel_update()  # type: ignore[reportPrivateUsage]

    def _flush_batched_drag_pixels(self) -> None:
        """Apply all batched pixel changes from a drag operation to the sprite frame."""
        if not hasattr(self, 'animated_sprite'):
            return

        current_animation = self.current_animation
        current_frame_index = self.current_frame

        if current_animation not in self.animated_sprite.frames:
            return

        frame = self.animated_sprite._animations[current_animation][current_frame_index]  # type: ignore[reportPrivateUsage]
        frame_pixels = frame.get_pixel_data()

        for x, y, _old_color, new_color in self._drag_pixels.values():
            pixel_num = y * self.pixels_across + x
            if pixel_num < len(frame_pixels):
                frame_pixels[pixel_num] = new_color

        frame.set_pixel_data(frame_pixels)
        self._clear_surface_cache()

    def _sync_drag_frame_surface(self) -> None:
        """Sync the drag frame surface from pixels when fast-path was used."""
        if not (hasattr(self, '_drag_frame') and self._drag_frame is not None):
            return

        frame_obj = self._drag_frame
        if hasattr(frame_obj, 'pixels') and frame_obj.pixels:
            try:
                frame_obj.set_pixel_data(list(frame_obj.pixels))
            except (AttributeError, TypeError, ValueError) as sync_error:
                LOG.debug(f'Best-effort frame sync failed: {sync_error}')

    def _submit_drag_pixel_changes_to_undo(self) -> None:
        """Submit batched drag pixel changes to the undo/redo system."""
        if not (
            hasattr(self, 'parent_scene')
            and self.parent_scene
            and hasattr(self.parent_scene, 'canvas_operation_tracker')
            and not getattr(self.parent_scene, '_applying_undo_redo', False)
        ):
            return

        pixel_changes = list(self._drag_pixels.values())
        if not pixel_changes:
            return

        if not hasattr(self.parent_scene, 'current_pixel_changes'):
            self.parent_scene.current_pixel_changes = []
        self.parent_scene.current_pixel_changes.extend(pixel_changes)  # type: ignore[reportArgumentType]

        if hasattr(self.parent_scene, '_submit_pixel_changes_if_ready'):
            self.parent_scene._submit_pixel_changes_if_ready()  # type: ignore[reportPrivateUsage]

    def _cleanup_drag_state(self) -> None:
        """Clear all drag-related state and ensure frame image is up to date."""
        self._drag_active = False
        self._drag_pixels = {}  # Already typed in on_left_mouse_button_down_event
        if hasattr(self, '_drag_redraw_counter'):
            del self._drag_redraw_counter
        if hasattr(self, '_drag_frame'):
            if self._drag_frame is not None:
                self._rebuild_frame_image_from_pixels(self._drag_frame)
            if hasattr(self._drag_frame, '_image_stale'):
                del self._drag_frame._image_stale  # type: ignore[reportPrivateUsage]
            del self._drag_frame

    @override
    def on_left_mouse_button_up_event(self, event: events.HashableEvent) -> None:
        """Handle mouse button up - flush batched drag updates."""
        if not (hasattr(self, '_drag_active') and self._drag_active):
            return

        if hasattr(self, '_drag_pixels') and self._drag_pixels:
            self._flush_batched_drag_pixels()
        else:
            self._sync_drag_frame_surface()
            self._submit_drag_pixel_changes_to_undo()

            if hasattr(self, 'animated_sprite'):
                self._update_animated_sprite_frame()

            if hasattr(self, 'parent_scene') and self.parent_scene:
                self.parent_scene.film_strip_coordinator._update_film_strips_for_pixel_update()  # type: ignore[reportPrivateUsage]

        self._cleanup_drag_state()
        self.dirty = 1

    @override
    def on_mouse_motion_event(self, event: events.HashableEvent) -> None:
        """Handle mouse motion events."""
        if self.rect.collidepoint(event.pos):
            # Mouse is over canvas - set hover state
            if not self.is_hovered:
                self.is_hovered = True
                self.dirty = 1  # Mark for redraw to show canvas border
                # Hide mouse cursor when entering canvas
                pygame.mouse.set_visible(False)

            # Convert mouse position to pixel coordinates
            x = (event.pos[0] - self.rect.x) // self.pixel_width
            y = (event.pos[1] - self.rect.y) // self.pixel_height

            # Check if the coordinates are within valid range
            if 0 <= x < self.pixels_across and 0 <= y < self.pixels_tall:
                # Update hovered pixel for white border effect
                self.hovered_pixel = (x, y)
                self.dirty = 1  # Mark for redraw to show hover effect

            # Mouse is over canvas but outside pixel grid - clear pixel hover
            elif hasattr(self, 'hovered_pixel') and self.hovered_pixel is not None:
                self.hovered_pixel = None
                self.dirty = 1  # Mark for redraw to remove pixel hover effect
        else:
            # Mouse is outside canvas - clear all hover effects
            if self.is_hovered:
                self.is_hovered = False
                self.dirty = 1  # Mark for redraw to remove canvas border
                # Show mouse cursor when leaving canvas
                pygame.mouse.set_visible(True)

            if hasattr(self, 'hovered_pixel') and self.hovered_pixel is not None:
                self.hovered_pixel = None
                self.dirty = 1  # Mark for redraw to remove pixel hover effect

    def on_pixel_update_event(self, event: events.HashableEvent, trigger: object) -> None:
        """Handle pixel update events."""
        if hasattr(trigger, 'pixel_number'):
            pixel_num: int = trigger.pixel_number  # type: ignore[union-attr]
            new_color: tuple[int, ...] = trigger.pixel_color  # type: ignore[union-attr]
            # self.log.debug(f"Animated canvas updating pixel {pixel_num} to color {new_color}")

            self.pixels[pixel_num] = new_color
            self.dirty_pixels[pixel_num] = True
            self.dirty = 1

            # Notify parent scene to update film strips
            if hasattr(self, 'parent_scene') and self.parent_scene:
                self.parent_scene.film_strip_coordinator._update_film_strips_for_pixel_update()  # type: ignore[reportPrivateUsage]

            # Update the animated sprite's frame data
            if hasattr(self, 'animated_sprite'):
                self._update_animated_sprite_frame()

    def on_mouse_leave_window_event(self, event: events.HashableEvent) -> None:
        """Handle mouse leaving window event."""

    def on_mouse_enter_sprite_event(self, event: events.HashableEvent) -> None:
        """Handle mouse entering canvas."""

    def on_mouse_exit_sprite_event(self, event: events.HashableEvent) -> None:
        """Handle mouse exiting canvas."""

    def _sync_all_frames_pixel_data(self) -> None:
        """Ensure all frames have their pixel data synchronized from pixels to surface.

        This is critical before saving because get_pixel_data() may read from
        frame.pixels if it exists, but we need to ensure _image is also up to date.

        For frames that don't have pixels attribute, we extract from _image first,
        then sync to ensure consistency.

        CRITICAL: If ANY frame has alpha pixels, normalize ALL frames to RGBA format
        to ensure consistent color map matching during save.
        """
        if not hasattr(self, 'animated_sprite') or not self.animated_sprite:
            return

        try:
            # Sync frames using ONLY the raw pixel data in memory
            # Don't extract from _image - just use frame.pixels if it exists
            # set_pixel_data() will update _image to match pixels
            for frames in self.animated_sprite._animations.values():  # type: ignore[reportPrivateUsage]
                for frame in frames:
                    try:
                        # Only sync if frame already has pixels in memory
                        # Don't extract from _image - use the raw pixel data we have
                        if hasattr(frame, 'pixels') and frame.pixels:
                            # Just sync pixels to surface - set_pixel_data updates _image to match
                            # pixels
                            # This ensures _image matches what's in frame.pixels
                            frame.set_pixel_data(list(frame.pixels))
                        # If frame doesn't have pixels, leave it alone - it will use
                        # get_pixel_data()
                        # which will extract from _image when needed, preserving original indexed
                        # colors
                    except (AttributeError, TypeError, ValueError) as frame_sync_error:
                        # Best-effort sync; continue if frame cannot be updated
                        LOG.debug(f'Best-effort frame sync failed: {frame_sync_error}')
                        continue
        except (AttributeError, KeyError, TypeError) as sync_error:
            # Best-effort sync; continue even if some frames fail
            LOG.debug(f'Best-effort pixel-to-surface sync failed: {sync_error}')

    def on_save_file_event(self, filename: str) -> None:
        """Handle save file events.

        Raises:
            OSError: If an I/O error occurs while saving.
            ValueError: If the sprite data is invalid for saving.
            KeyError: If a required key is missing during serialization.

        """
        self.log.info('Starting save to file: %s', filename)
        try:
            # CRITICAL: Sync all frame pixel data before saving
            # This ensures that any direct modifications to frame.pixels during drag
            # are properly reflected in the frame surface, which get_pixel_data() may read from
            self._sync_all_frames_pixel_data()

            # Detect file format from extension
            file_format = detect_file_format(filename)
            self.log.info('Detected file format: %s', file_format)

            # Check if this is a single-frame animation (converted from static sprite)
            if self._is_single_frame_animation():
                self.log.info('Detected single-frame animation, saving as static sprite')
                self._save_as_static_sprite(filename, file_format)
            else:
                # Use the interface-based save method for multi-frame animations
                self.sprite_serializer.save(
                    self.animated_sprite,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
                    filename=filename,
                    file_format=file_format,
                )
        except OSError, ValueError, KeyError:
            self.log.exception('Error saving file')
            raise

    def get_canvas_interface(self) -> AnimatedCanvasInterface:
        """Get the canvas interface for external access.

        Returns:
            AnimatedCanvasInterface: The canvas interface.

        """
        return self.canvas_interface

    def get_sprite_serializer(self) -> AnimatedSpriteSerializer:
        """Get the sprite serializer for external access.

        Returns:
            AnimatedSpriteSerializer: The sprite serializer.

        """
        return self.sprite_serializer

    def get_canvas_renderer(self) -> AnimatedCanvasRenderer:
        """Get the canvas renderer for external access.

        Returns:
            AnimatedCanvasRenderer: The canvas renderer.

        """
        return self.canvas_renderer

    def on_load_file_event(self, event: events.HashableEvent, trigger: object = None) -> None:
        """Handle load file event for animated sprites."""
        self.log.debug('=== Starting on_load_file_event for animated sprite ===')
        LOG.debug(f'DEBUG: Canvas on_load_file_event called with event: {event}')
        try:
            filename = event if isinstance(event, str) else event.text
            LOG.debug(f'DEBUG: Loading sprite from filename: {filename}')

            # Load the sprite from file
            loaded_sprite = self._load_sprite_from_file(filename)

            # Set the loaded sprite as the current animated sprite
            self.animated_sprite = loaded_sprite

            # Check if canvas needs resizing and resize if necessary
            self._check_and_resize_canvas(loaded_sprite)

            # Set up animation state
            self._setup_animation_state(loaded_sprite)

            # Update UI components
            self._update_ui_components(loaded_sprite)

            # Finalize the loading process
            self._finalize_sprite_loading(loaded_sprite, filename)

        except FileNotFoundError as e:
            self.log.exception('File not found')
            # Show user-friendly error message instead of crashing
            if hasattr(self, 'parent') and hasattr(self.parent, 'debug_text'):
                self.parent.debug_text.text = f'Error: File not found - {e}'
        except (OSError, ValueError, KeyError, TypeError, AttributeError, pygame.error) as e:
            self.log.exception('Error in on_load_file_event for animated sprite')
            self.log.exception(f'Exception type: {type(e).__name__}')
            import traceback

            self.log.exception(f'Traceback: {traceback.format_exc()}')
            # Show user-friendly error message instead of crashing
            if hasattr(self, 'parent') and hasattr(self.parent, 'debug_text'):
                self.parent.debug_text.text = f'Error loading sprite: {e}'

    def _load_sprite_from_file(self, filename: str) -> AnimatedSprite:
        """Load an animated sprite from a file.

        Args:
            filename: Path to the sprite file to load

        Returns:
            Loaded AnimatedSprite instance

        Raises:
            ValueError: If PNG conversion fails or other loading errors occur.

        """
        self.log.debug('Loading animated sprite from %s', filename)

        # Check if this is a PNG file and convert it first
        if filename.lower().endswith('.png'):
            self.log.info('PNG file detected - converting to bitmappy format first')
            converted_toml_path = self._convert_png_to_bitmappy(filename)  # type: ignore[attr-defined]
            if converted_toml_path:
                filename = converted_toml_path  # type: ignore[assignment]
                self.log.info('Using converted TOML file: %s', filename)
            else:
                raise ValueError('Failed to convert PNG to bitmappy format')

        # Detect file format and load the sprite
        file_format = detect_file_format(filename)  # type: ignore[arg-type]
        self.log.debug('Detected file format: %s', file_format)

        # Create a new animated sprite and load it
        loaded_sprite = AnimatedSprite()
        loaded_sprite.load(filename)  # type: ignore[arg-type]

        # Debug: Check what was loaded
        self.log.debug(f'Loaded sprite has _animations: {hasattr(loaded_sprite, "_animations")}')
        if hasattr(loaded_sprite, '_animations'):
            self.log.debug(f'Loaded sprite _animations: {list(loaded_sprite._animations.keys())}')  # type: ignore[reportPrivateUsage]
            self.log.debug(f'Loaded sprite current_animation: {loaded_sprite.current_animation}')
            self.log.debug(f'Loaded sprite is_playing: {loaded_sprite.is_playing}')

        return loaded_sprite

    def _check_and_resize_canvas(self, loaded_sprite: AnimatedSprite) -> None:
        """Check if canvas needs resizing and resize if necessary.

        Args:
            loaded_sprite: The loaded sprite to check dimensions against

        """
        # Check if the loaded sprite has different dimensions than the canvas
        if (
            loaded_sprite._animations  # type: ignore[reportPrivateUsage]
            and loaded_sprite.current_animation in loaded_sprite._animations  # type: ignore[reportPrivateUsage]
        ):
            first_frame = loaded_sprite._animations[loaded_sprite.current_animation][0]  # type: ignore[reportPrivateUsage]
            sprite_width, sprite_height = first_frame.get_size()
            self.log.debug('Loaded sprite dimensions: %sx%s', sprite_width, sprite_height)
            self.log.debug(f'Canvas dimensions: {self.pixels_across}x{self.pixels_tall}')

            # If sprite has different dimensions than canvas, resize canvas to match
            if sprite_width != self.pixels_across or sprite_height != self.pixels_tall:
                self.log.info(
                    f'Resizing canvas from {self.pixels_across}x{self.pixels_tall} to '
                    f'{sprite_width}x{sprite_height}',
                )
                self._resize_canvas_to_sprite_size(sprite_width, sprite_height)
        else:
            # No frames or animation - but the animated sprite loader already converted it
            self.log.info('Using already-converted animated sprite from static sprite')

            # Check if we need to resize the canvas
            if hasattr(loaded_sprite, 'get_size'):
                sprite_width, sprite_height = loaded_sprite.get_size()  # type: ignore[union-attr]
                self.log.debug('Static sprite dimensions: %sx%s', sprite_width, sprite_height)
                self.log.debug(f'Canvas dimensions: {self.pixels_across}x{self.pixels_tall}')

                # If sprite has different dimensions than canvas, resize canvas to match
                if sprite_width != self.pixels_across or sprite_height != self.pixels_tall:
                    self.log.info(
                        f'Resizing canvas from {self.pixels_across}x{self.pixels_tall} to '
                        f'{sprite_width}x{sprite_height}',
                    )
                    self._resize_canvas_to_sprite_size(sprite_width, sprite_height)  # type: ignore[arg-type]

    def _update_ui_components(self, loaded_sprite: AnimatedSprite) -> None:
        """Update UI components after loading a sprite.

        Args:
            loaded_sprite: The loaded sprite to update UI components with

        """
        # Update multiple film strips
        if hasattr(self, 'film_strips') and self.film_strips:  # type: ignore[attr-defined]
            for film_strip in self.film_strips.values():  # type: ignore[attr-defined]
                film_strip.mark_dirty()  # type: ignore[union-attr]
        if hasattr(self, 'film_strip_sprites') and self.film_strip_sprites:  # type: ignore[attr-defined]
            for film_strip_sprite in self.film_strip_sprites.values():  # type: ignore[attr-defined]
                film_strip_sprite.dirty = 1

        # Note: Live preview functionality is now integrated into the film strip

        # Clear existing multiple film strips and recreate them
        if hasattr(self, 'film_strips') and self.film_strips:  # type: ignore[attr-defined]
            # Clear existing film strips
            for film_strip_sprite in self.film_strip_sprites.values():  # type: ignore[attr-defined]
                if hasattr(film_strip_sprite, 'groups') and film_strip_sprite.groups():  # type: ignore[union-attr]
                    for group in film_strip_sprite.groups():  # type: ignore[union-attr]
                        group.remove(film_strip_sprite)  # type: ignore[union-attr]
            self.film_strips.clear()  # type: ignore[attr-defined]
            self.film_strip_sprites.clear()  # type: ignore[attr-defined]

        # Film strips will be created by the parent scene

        # Notify parent scene about sprite load
        LOG.debug(
            f'DEBUG: Checking callbacks - hasattr(parent_scene): {hasattr(self, "parent_scene")},'
            f' hasattr(on_sprite_loaded): {hasattr(self, "on_sprite_loaded")}',
        )
        if hasattr(self, 'parent_scene') and self.parent_scene:
            self.log.debug('Calling parent scene _on_sprite_loaded')
            LOG.debug('DEBUG: Calling parent scene _on_sprite_loaded')
            self.parent_scene.film_strip_coordinator.on_sprite_loaded(loaded_sprite)
        elif hasattr(self, 'on_sprite_loaded') and self.on_sprite_loaded:  # type: ignore[attr-defined]
            self.log.debug('Calling on_sprite_loaded callback')
            LOG.debug('DEBUG: Calling on_sprite_loaded callback')
            self.on_sprite_loaded(loaded_sprite)  # type: ignore[attr-defined]
        else:
            LOG.debug(
                'DEBUG: No callback found - hasattr(parent_scene):'
                f' {hasattr(self, "parent_scene")}, hasattr(on_sprite_loaded):'
                f' {hasattr(self, "on_sprite_loaded")}',
            )
            self.log.debug('No parent scene or callback found')

    def _setup_animation_state(self, loaded_sprite: AnimatedSprite) -> None:
        """Set up animation state after loading a sprite.

        Args:
            loaded_sprite: The loaded sprite to set up animation for

        """
        # Update the canvas sprite's current animation to match the loaded sprite
        self.current_animation = loaded_sprite.current_animation
        self.log.debug(f'Updated canvas animation to: {self.current_animation}')

        # Debug: Print available animations
        available_animations = (
            list(loaded_sprite._animations.keys()) if hasattr(loaded_sprite, '_animations') else []  # type: ignore[reportPrivateUsage]
        )
        self.log.info('AVAILABLE ANIMATIONS: %s', available_animations)
        self.log.info(f"CURRENT CANVAS ANIMATION: '{self.current_animation}'")

        # Start the animation after loading
        if loaded_sprite.current_animation:
            # Ensure looping is enabled before starting
            loaded_sprite._is_looping = True  # type: ignore[reportPrivateUsage]
            loaded_sprite.play()
            self.log.debug(
                f"Started animation '{loaded_sprite.current_animation}' using play() method",
            )
            # Verify animation state immediately after starting
            self.log.debug(
                f'Animation state after play(): is_playing={loaded_sprite.is_playing}, '
                f'is_looping={loaded_sprite._is_looping}, '  # type: ignore[reportPrivateUsage]
                f'current_frame={loaded_sprite.current_frame}',
            )

    def _finalize_sprite_loading(self, loaded_sprite: AnimatedSprite, filename: str) -> None:
        """Finalize sprite loading process.

        Args:
            loaded_sprite: The loaded sprite
            filename: The filename that was loaded

        """
        # Now copy the sprite data to canvas with the correct animation
        self._copy_sprite_to_canvas()
        self.dirty = 1
        self.force_redraw()

        # Force a complete redraw
        self.dirty = 1
        self.force_redraw()

        self.log.info('Successfully loaded animated sprite from %s', filename)

        # Update AI textbox with sprite description or default prompt
        self.log.debug('Checking parent and debug_text access...')
        self.log.debug(f"hasattr(self, 'parent_scene'): {hasattr(self, 'parent_scene')}")
        if hasattr(self, 'parent_scene'):
            self.log.debug(
                "hasattr(self.parent_scene, 'debug_text'):"
                f' {hasattr(self.parent_scene, "debug_text")}',
            )
            self.log.debug(f'self.parent_scene type: {type(self.parent_scene)}')

        if hasattr(self, 'parent_scene') and hasattr(self.parent_scene, 'debug_text'):
            assert self.parent_scene is not None
            # Get description from loaded sprite, or use default prompt if empty
            description = getattr(loaded_sprite, 'description', '')
            self.log.debug("Loaded sprite description: '%s'", description)
            self.log.debug(f'Description is not empty: {bool(description and description.strip())}')
            if description and description.strip():
                self.log.info("Setting AI textbox to description: '%s'", description)
                self.parent_scene.debug_text.text = description
            else:
                self.log.info('Setting AI textbox to default prompt')
                self.parent_scene.debug_text.text = (
                    'Enter a description of the sprite you want to create:'
                )
        else:
            self.log.warning('Cannot access parent or debug_text - description not updated')

    def _resize_canvas_to_sprite_size(self, sprite_width: int, sprite_height: int) -> None:
        """Resize the canvas to match the sprite dimensions."""
        self.log.debug('Resizing canvas to %sx%s', sprite_width, sprite_height)

        # Update canvas dimensions
        self.pixels_across = sprite_width
        self.pixels_tall = sprite_height

        # Get screen dimensions directly from pygame display
        screen = pygame.display.get_surface()
        assert screen is not None
        screen_width = screen.get_width()
        screen_height = screen.get_height()

        # Recalculate pixel dimensions to fit the screen
        available_height = screen_height - 80 - 24  # Adjust for bottom margin and menu bar
        # ===== DEBUG: CANVAS SIZING CALCULATIONS =====
        LOG.debug('===== DEBUG: CANVAS SIZING CALCULATIONS =====')
        LOG.debug(f'Screen: {screen_width}x{screen_height}, Sprite: {sprite_width}x{sprite_height}')
        LOG.debug(f'Available height: {available_height}')
        LOG.debug(f'Height constraint: {available_height // sprite_height}')
        LOG.debug(f'Width constraint: {(screen_width * 1 // 2) // sprite_width}')
        LOG.debug(f'320x320 constraint: {320 // max(sprite_width, sprite_height)}')

        # For large sprites (128x128), ensure we get at least 2x2 pixel size
        if sprite_width >= LARGE_SPRITE_DIMENSION and sprite_height >= LARGE_SPRITE_DIMENSION:
            pixel_size = MIN_PIXEL_DISPLAY_SIZE  # Force 2x2 pixel size for 128x128
            LOG.debug('*** FORCING 2x2 pixel size for 128x128 sprite ***')
        else:
            pixel_size = min(
                available_height // sprite_height,
                (screen_width * 1 // 2) // sprite_width,
                # Maximum canvas size constraint: 320x320
                320 // max(sprite_width, sprite_height),
            )
            LOG.debug(f'Calculated pixel_size: {pixel_size}')
        # Ensure minimum pixel size of 1x1
        pixel_size = max(pixel_size, 1)

        LOG.debug(f'Final pixel_size: {pixel_size}')
        LOG.debug(f'Canvas will be: {sprite_width * pixel_size}x{sprite_height * pixel_size}')
        LOG.debug('===== END DEBUG =====\n')

        # Update pixel dimensions
        self.pixel_width = pixel_size
        self.pixel_height = pixel_size

        # Create new pixel arrays
        self.pixels = [(255, 0, 255, 255)] * (  # ty: ignore[invalid-assignment]
            sprite_width * sprite_height
        )  # Initialize with magenta
        self.dirty_pixels = [True] * (sprite_width * sprite_height)

        # Update surface dimensions
        actual_width = sprite_width * pixel_size
        actual_height = sprite_height * pixel_size
        LOG.debug('===== DEBUG: SURFACE CREATION =====')
        LOG.debug(f'Creating surface: {actual_width}x{actual_height}')
        LOG.debug(f'pixel_size: {pixel_size}, sprite: {sprite_width}x{sprite_height}')
        self.image = pygame.Surface((actual_width, actual_height))
        LOG.debug('Surface created successfully')
        LOG.debug('===== END DEBUG =====\n')
        self.rect = self.image.get_rect(x=self.rect.x, y=self.rect.y)

        # Update class dimensions

        # Update AI sprite positioning after canvas resize
        if hasattr(self, 'parent_scene') and self.parent_scene:
            self.parent_scene._update_ai_sprite_position()  # type: ignore[reportPrivateUsage]
        AnimatedCanvasSprite.WIDTH = sprite_width  # ty: ignore[unresolved-attribute]
        AnimatedCanvasSprite.HEIGHT = sprite_height  # ty: ignore[unresolved-attribute]

        self.log.info(
            'Canvas resized to %sx%s with pixel size %s', sprite_width, sprite_height, pixel_size,
        )

    def _convert_static_to_animated(
        self, static_sprite: BitmappySprite, width: int, height: int,
    ) -> AnimatedSprite:
        """Convert a static sprite to an animated sprite with 1 frame.

        Returns:
            AnimatedSprite: The result.

        """
        # Create new animated sprite
        animated_sprite = AnimatedSprite()

        # Get pixel data from static sprite
        if hasattr(static_sprite, 'get_pixel_data'):
            pixel_data = static_sprite.get_pixel_data()  # type: ignore[union-attr]
            self.log.debug(
                f'Got pixel data from get_pixel_data(): {len(pixel_data)} pixels, '  # type: ignore[arg-type]
                f'first few: {pixel_data[:5]}',
            )
        elif hasattr(static_sprite, 'pixels'):
            pixel_data = static_sprite.pixels.copy()
            self.log.debug(
                f'Got pixel data from pixels attribute: {len(pixel_data)} pixels, '
                f'first few: {pixel_data[:5]}',
            )
        else:
            # Fallback - create magenta pixels
            pixel_data = [(255, 0, 255)] * (width * height)
            self.log.debug(f'Using fallback magenta pixels: {len(pixel_data)} pixels')

        # Create a single frame with the static sprite data
        frame = SpriteFrame(surface=pygame.Surface((width, height), pygame.SRCALPHA))
        frame.set_pixel_data(pixel_data)  # type: ignore[arg-type]

        # Get the animation name from the static sprite if available
        animation_name = 'idle'  # Default fallback
        if hasattr(static_sprite, 'name') and static_sprite.name:
            animation_name = static_sprite.name
        elif hasattr(static_sprite, 'animation_name') and static_sprite.animation_name:  # type: ignore[union-attr]
            animation_name = static_sprite.animation_name  # type: ignore[union-attr]

        # Add the frame to the animated sprite with the correct animation name
        animated_sprite.add_frame(animation_name, frame)  # type: ignore[arg-type]

        # Set the current animation to the actual animation name
        animated_sprite.frame_manager.current_animation = animation_name  # ty: ignore[invalid-assignment]
        animated_sprite.frame_manager.current_frame = 0

        # Debug: Verify the conversion worked
        self.log.debug(
            f'Converted static sprite to animated format with 1 frame: {len(pixel_data)} pixels',  # type: ignore[arg-type]
        )
        self.log.debug(f'Animated sprite has frames: {hasattr(animated_sprite, "frames")}')
        if hasattr(animated_sprite, 'frames'):
            self.log.debug(f'Available animations: {list(animated_sprite._animations.keys())}')  # type: ignore[reportPrivateUsage]
            if 'idle' in animated_sprite._animations:  # type: ignore[reportPrivateUsage]
                self.log.debug(
                    f'Idle animation has {len(animated_sprite._animations["idle"])} frames',  # type: ignore[reportPrivateUsage]
                )
                if animated_sprite._animations['idle']:  # type: ignore[reportPrivateUsage]
                    frame_pixels = animated_sprite._animations['idle'][0].get_pixel_data()  # type: ignore[reportPrivateUsage]
                    self.log.debug(
                        f'First frame pixels: {len(frame_pixels)} pixels, '
                        f'first few: {frame_pixels[:5]}',
                    )

        return animated_sprite

    def _is_single_frame_animation(self) -> bool:
        """Check if this is a single-frame animation (converted from static sprite).

        Returns:
            bool: True if the condition is met, False otherwise.

        """
        if not hasattr(self, 'animated_sprite') or not self.animated_sprite:
            return False

        # Check if there's only one animation with one frame
        if hasattr(self.animated_sprite, '_animations') and self.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
            animations = list(self.animated_sprite._animations.keys())  # type: ignore[reportPrivateUsage]
            if len(animations) == 1 and len(self.animated_sprite._animations[animations[0]]) == 1:  # type: ignore[reportPrivateUsage]
                return True

        return False

    def _save_as_static_sprite(self, filename: str, file_format: str) -> None:
        """Save a single-frame animation as a static sprite.

        Raises:
            ValueError: If there is no animated sprite, no animations, or no frames to save.

        """
        if not hasattr(self, 'animated_sprite') or not self.animated_sprite:
            raise ValueError('No animated sprite to save')

        # Get the single frame
        animations = list(self.animated_sprite._animations.keys())  # type: ignore[reportPrivateUsage]
        if not animations:
            raise ValueError('No animations found')

        animation_name = animations[0]
        frames = self.animated_sprite._animations[animation_name]  # type: ignore[reportPrivateUsage]
        if not frames:
            raise ValueError('No frames found in animation')

        frame = frames[0]  # Get the first (and only) frame

        # Create an AnimatedSprite from the frame (since everything is AnimatedSprite now)
        # Create a new AnimatedSprite with the frame data
        animated_sprite = AnimatedSprite()

        # Set up the frame data using the sprite's name or a default
        animation_name = getattr(frame, 'name', 'frame') or 'frame'
        animated_sprite._animations = {animation_name: [frame]}  # type: ignore[reportPrivateUsage]
        animated_sprite.frame_manager.current_animation = animation_name
        animated_sprite.frame_manager.current_frame = 0

        # Preserve the description from the original sprite
        if hasattr(self.animated_sprite, 'description'):
            animated_sprite.description = self.animated_sprite.description
            self.log.debug(f"Preserved description: '{animated_sprite.description}'")

        # Update the sprite's image to match the frame
        animated_sprite.image = frame.image.copy()
        animated_sprite.rect = animated_sprite.image.get_rect()

        # Save using the animated sprite's save method
        animated_sprite.save(filename, file_format)
        self.log.info('Saved single-frame animation as static sprite to %s', filename)

    def _copy_sprite_to_canvas(self) -> None:
        """Copy the current frame of the animated sprite to the canvas."""
        if not hasattr(self, 'animated_sprite') or not self.animated_sprite:
            return

        # Get the current frame pixels from the animated sprite
        current_frame_pixels = self._get_current_frame_pixels()
        if current_frame_pixels:
            # Copy the pixels to the canvas
            self.pixels = current_frame_pixels.copy()  # ty: ignore[invalid-assignment]
            self.dirty_pixels = [True] * len(self.pixels)
            self.dirty = 1  # Mark canvas as dirty for redraw
            self.log.debug(f'Copied {len(current_frame_pixels)} pixels to canvas')
            self.log.debug(
                f'Canvas pixels after copy: {self.pixels[:5] if self.pixels else "None"}',
            )
        else:
            self.log.warning('No current frame pixels to copy to canvas')

    def _build_surface_from_canvas_pixels(self) -> pygame.Surface:
        """Build a pygame Surface from current canvas pixel data.

        Returns:
            A new Surface with canvas pixels rendered, with alpha support.

        """
        surface = pygame.Surface((self.pixels_across, self.pixels_tall), pygame.SRCALPHA)
        magenta_keys = {(255, 0, 255), (255, 0, 255, 255)}
        for y in range(self.pixels_tall):
            for x in range(self.pixels_across):
                pixel_num = y * self.pixels_across + x
                if pixel_num >= len(self.pixels):
                    continue
                color = self.pixels[pixel_num]
                # Handle transparency key specially - keep it opaque
                if color in magenta_keys:
                    surface.set_at((x, y), (255, 0, 255, 255))
                else:
                    surface.set_at((x, y), color)
        return surface

    def _update_animated_sprite_frame(self) -> None:
        """Update the animated sprite's current frame with canvas data."""
        if not (
            hasattr(self, 'animated_sprite')
            and hasattr(self, 'current_animation')
            and hasattr(self, 'current_frame')
        ):
            return

        current_anim = self.current_animation
        current_frame = self.current_frame

        if not (
            current_anim
            and current_frame is not None  # type: ignore[reportUnnecessaryComparison]
            and current_anim in self.animated_sprite._animations  # type: ignore[reportPrivateUsage]
            and 0 <= current_frame < len(self.animated_sprite._animations[current_anim])  # type: ignore[reportPrivateUsage]
            and hasattr(self.animated_sprite._animations[current_anim][current_frame], 'image')  # type: ignore[reportPrivateUsage]
        ):
            return

        frame = self.animated_sprite._animations[current_anim][current_frame]  # type: ignore[reportPrivateUsage]
        frame.image = self._build_surface_from_canvas_pixels()

        if hasattr(self, 'parent_scene') and self.parent_scene:
            self.parent_scene.film_strip_coordinator.update_film_strips_for_animated_sprite_update()

    def get_canvas_surface(self) -> pygame.Surface:
        """Get the current canvas surface for the film strip.

        Returns:
            pygame.Surface: The canvas surface.

        """
        # Create a surface from the current canvas pixels with alpha support
        surface = pygame.Surface((self.pixels_across, self.pixels_tall), pygame.SRCALPHA)
        for y in range(self.pixels_tall):
            for x in range(self.pixels_across):
                pixel_num = y * self.pixels_across + x
                if pixel_num < len(self.pixels):
                    color = self.pixels[pixel_num]
                    # Handle transparency key specially - make it transparent for film strip
                    if color in {(255, 0, 255), (255, 0, 255, 255)}:
                        surface.set_at((x, y), (255, 0, 255, 0))  # Transparent magenta
                    else:
                        surface.set_at((x, y), color)
        return surface

    def _flood_fill(self, start_x: int, start_y: int, fill_color: tuple[int, int, int]) -> None:
        """Perform flood fill algorithm starting from the given coordinates.

        Args:
            start_x: Starting X coordinate
            start_y: Starting Y coordinate
            fill_color: Color to fill with

        """
        # Check bounds
        if not (0 <= start_x < self.pixels_across and 0 <= start_y < self.pixels_tall):
            self.log.warning('Flood fill coordinates out of bounds: (%s, %s)', start_x, start_y)
            return

        # Get the target color (the color we're replacing)
        target_color = self.canvas_interface.get_pixel_at(start_x, start_y)

        # If target color is the same as fill color, no work needed
        if target_color == fill_color:
            self.log.info('Target color same as fill color, no flood fill needed')
            return

        self.log.info(
            'Flood fill: replacing %s with %s starting at (%s, %s)', target_color, fill_color, start_x, start_y,
        )

        # Use iterative flood fill with a stack to avoid recursion depth issues
        stack = [(start_x, start_y)]
        filled_pixels = 0

        while stack:
            x, y = stack.pop()

            # Check bounds and color match
            if (
                0 <= x < self.pixels_across
                and 0 <= y < self.pixels_tall
                and self.canvas_interface.get_pixel_at(x, y) == target_color
            ):
                # Fill this pixel
                self.canvas_interface.set_pixel_at(x, y, fill_color)
                filled_pixels += 1

                # Add adjacent pixels to stack (4-connected)
                stack.extend([
                    (x + 1, y),  # Right
                    (x - 1, y),  # Left
                    (x, y + 1),  # Down
                    (x, y - 1),  # Up
                ])

        self.log.info('Flood fill completed: filled %s pixels', filled_pixels)

    def _initialize_panning_system(self) -> None:
        """Initialize the panning system for the canvas."""
        # Panning state
        self.pan_offset_x = 0  # Horizontal pan offset in pixels
        self.pan_offset_y = 0  # Vertical pan offset in pixels

        # Buffer dimensions (larger than canvas to allow panning)
        # Add extra space around the canvas for panning
        self.buffer_width = self.pixels_across + 20  # Extra 10 pixels on each side
        self.buffer_height = self.pixels_tall + 20  # Extra 10 pixels on each side

        # Viewport dimensions (same as canvas dimensions)
        self.viewport_width = self.pixels_across
        self.viewport_height = self.pixels_tall

        # Panning state flag
        self._panning_active = False

        # Initialize buffer with transparent pixels
        self._buffer_pixels = [
            (255, 0, 255, 255) for _ in range(self.buffer_width * self.buffer_height)
        ]

        # Copy current canvas pixels to center of buffer
        if hasattr(self, 'pixels') and self.pixels:
            buffer_center_x = (self.buffer_width - self.pixels_across) // 2
            buffer_center_y = (self.buffer_height - self.pixels_tall) // 2

            for y in range(self.pixels_tall):
                for x in range(self.pixels_across):
                    buffer_x = buffer_center_x + x
                    buffer_y = buffer_center_y + y
                    buffer_index = buffer_y * self.buffer_width + buffer_x
                    canvas_index = y * self.pixels_across + x

                    if buffer_index < len(self._buffer_pixels) and canvas_index < len(self.pixels):
                        self._buffer_pixels[buffer_index] = self.pixels[canvas_index]  # type: ignore[index]

        self.log.debug(
            f'Panning system initialized: buffer={self.buffer_width}x{self.buffer_height},'
            f' viewport={self.viewport_width}x{self.viewport_height}',
        )

    def pan_canvas(self, delta_x: int, delta_y: int) -> None:
        """Pan the canvas by the given delta values.

        Args:
            delta_x: Horizontal panning delta (-1, 0, or 1)
            delta_y: Vertical panning delta (-1, 0, or 1)

        """
        # Get current frame key
        frame_key = self._get_current_frame_key()

        # Get current pan offset from frame state (or default to 0, 0)
        if frame_key in self._frame_panning:
            current_pan_x = self._frame_panning[frame_key]['pan_x']
            current_pan_y = self._frame_panning[frame_key]['pan_y']
        else:
            current_pan_x = 0
            current_pan_y = 0

        # Calculate new pan offset
        new_pan_x = current_pan_x + delta_x
        new_pan_y = current_pan_y + delta_y

        # Check if panning is within bounds
        if self._can_pan(new_pan_x, new_pan_y):
            # Initialize frame panning state if needed
            if frame_key not in self._frame_panning:
                self._frame_panning[frame_key] = {
                    'pan_x': 0,
                    'pan_y': 0,
                    'original_pixels': None,
                    'active': False,
                }

            frame_state = self._frame_panning[frame_key]
            frame_state['pan_x'] = new_pan_x
            frame_state['pan_y'] = new_pan_y
            frame_state['active'] = True

            # Store original frame data if this is the first pan for this frame
            if frame_state['original_pixels'] is None:
                self._store_original_frame_data_for_frame(frame_key)

            # Apply panning transformation to show panned view
            self._apply_panning_view_for_frame(frame_key)
            self.dirty = 1
        else:
            self.log.debug('Cannot pan to (%s, %s) - out of bounds.', new_pan_x, new_pan_y)

    def _store_original_frame_data(self) -> None:
        """Store the original frame data before any panning."""
        if hasattr(self, 'pixels') and self.pixels:
            self._original_frame_pixels = list(self.pixels)
            self.log.debug('Stored original frame data for panning')

    def _apply_panning_view(self) -> None:
        """Apply panning transformation to show the panned view."""
        if not hasattr(self, '_original_frame_pixels'):
            return

        # Create panned view by shifting pixels
        panned_pixels: list[tuple[int, ...]] = []

        for y in range(self.pixels_tall):
            for x in range(self.pixels_across):
                # Calculate source coordinates (where to read from in original)
                source_x = x - self.pan_offset_x
                source_y = y - self.pan_offset_y

                # Check if source is within bounds
                if 0 <= source_x < self.pixels_across and 0 <= source_y < self.pixels_tall:
                    source_index = source_y * self.pixels_across + source_x
                    if source_index < len(self._original_frame_pixels):
                        panned_pixels.append(self._original_frame_pixels[source_index])
                    else:
                        panned_pixels.append((255, 0, 255))  # Transparent
                else:
                    panned_pixels.append((255, 0, 255))  # Transparent

        # Update canvas pixels with panned view
        self.pixels = panned_pixels
        self.dirty_pixels = [True] * len(self.pixels)

        self.log.debug(f'Applied panning view: offset=({self.pan_offset_x}, {self.pan_offset_y})')

    def _can_pan(self, new_pan_x: int, new_pan_y: int) -> bool:
        """Check if the new pan offset is within the allowed bounds.

        Returns:
            bool: True if the condition is met, False otherwise.

        """
        # For now, allow panning within reasonable bounds
        # Later we can add more sophisticated bounds checking
        max_pan = 10  # Maximum pan distance
        return abs(new_pan_x) <= max_pan and abs(new_pan_y) <= max_pan

    def _update_viewport_pixels(self) -> None:
        """Update the viewport pixels based on current panning offset."""
        if not self._panning_active:
            return

        # Clear viewport pixels
        viewport_pixels: list[tuple[int, ...]] = []

        # Calculate buffer center offset
        buffer_center_x = (self.buffer_width - self.pixels_across) // 2
        buffer_center_y = (self.buffer_height - self.pixels_tall) // 2

        # Fill viewport with pixels from buffer at pan offset
        for y in range(self.pixels_tall):
            for x in range(self.pixels_across):
                buffer_x = buffer_center_x + x + self.pan_offset_x
                buffer_y = buffer_center_y + y + self.pan_offset_y

                # Check if buffer coordinates are within bounds
                if 0 <= buffer_x < self.buffer_width and 0 <= buffer_y < self.buffer_height:
                    pixel_index = buffer_y * self.buffer_width + buffer_x
                    if pixel_index < len(self._buffer_pixels):
                        viewport_pixels.append(self._buffer_pixels[pixel_index])
                    else:
                        viewport_pixels.append((255, 0, 255))  # Transparent
                else:
                    viewport_pixels.append((255, 0, 255))  # Transparent

        # Update canvas pixels with viewport data
        self.pixels = viewport_pixels
        self.dirty_pixels = [True] * len(self.pixels)

        # Force redraw to update the visual display including borders
        self.force_redraw()

    def _save_viewport_sprite(self, filename: str) -> None:
        """Save only the viewport area when panning is active."""
        from glitchygames.sprites.animated import AnimatedSprite

        # Create a new animated sprite with viewport data
        viewport_sprite = AnimatedSprite()
        viewport_sprite.name = self.animated_sprite.name + '_viewport'
        viewport_sprite.description = f'Viewport of {self.animated_sprite.name} (panned)'

        # Copy viewport data for each animation
        for anim_name, frames in self.animated_sprite._animations.items():  # type: ignore[reportPrivateUsage]
            viewport_frames: list[SpriteFrame] = []
            for frame in frames:
                viewport_frame = self._create_viewport_frame(frame)
                viewport_frames.append(viewport_frame)
            viewport_sprite.add_animation(anim_name, viewport_frames)

        # Save the newly created viewport sprite
        self.sprite_serializer.save(viewport_sprite, filename, DEFAULT_FILE_FORMAT)  # type: ignore[arg-type]
        self.log.info('Viewport sprite saved to %s', filename)

    def _create_viewport_frame(self, original_frame: SpriteFrame) -> SpriteFrame:
        """Create a frame containing only the viewport data.

        Returns:
            SpriteFrame: The result.

        """
        from glitchygames.sprites.animated import SpriteFrame

        # Get viewport pixel data
        viewport_pixels = self._get_viewport_pixels_from_frame(original_frame)

        # Create new frame with viewport dimensions
        new_frame = SpriteFrame(
            surface=pygame.Surface((self.pixels_across, self.pixels_tall), pygame.SRCALPHA),
            duration=original_frame.duration,
        )

        # Set viewport pixel data
        new_frame.set_pixel_data(viewport_pixels)  # ty: ignore[invalid-argument-type]

        return new_frame

    def _get_viewport_pixels_from_frame(
        self, frame: SpriteFrame,
    ) -> list[tuple[int, int, int, int]]:
        """Get viewport pixels from a frame based on current panning offset.

        Returns:
            list[tuple[int, int, int, int]]: The viewport pixels from frame.

        """
        # Get the frame's pixel data
        frame_pixels = frame.get_pixel_data()
        frame_width, frame_height = frame.get_size()

        # Get current frame panning offset
        frame_key = self._get_current_frame_key()
        if frame_key in self._frame_panning and self._frame_panning[frame_key]['active']:
            pan_offset_x = self._frame_panning[frame_key]['pan_x']
            pan_offset_y = self._frame_panning[frame_key]['pan_y']
        else:
            pan_offset_x = 0
            pan_offset_y = 0

        # Create viewport pixels
        viewport_pixels: list[tuple[int, ...]] = []
        for y in range(self.pixels_tall):
            for x in range(self.pixels_across):
                buffer_x = x + pan_offset_x
                buffer_y = y + pan_offset_y

                # Check if buffer coordinates are within frame bounds
                if 0 <= buffer_x < frame_width and 0 <= buffer_y < frame_height:
                    pixel_index = buffer_y * frame_width + buffer_x
                    if pixel_index < len(frame_pixels):
                        viewport_pixels.append(frame_pixels[pixel_index])
                    else:
                        viewport_pixels.append((255, 0, 255))  # Transparent
                else:
                    viewport_pixels.append((255, 0, 255))  # Transparent

        return viewport_pixels  # type: ignore[return-value]
