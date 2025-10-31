"""Canvas interfaces for supporting multiple sprite types in the bitmap editor.

This module defines the abstract interfaces that allow the bitmap editor to work
with both static BitmappySprites and animated sprites through a unified API.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Protocol

import pygame

# Import the default file format constant
from glitchygames.sprites.constants import DEFAULT_FILE_FORMAT

LOG = logging.getLogger("game.tools.canvas_interfaces")
LOG.addHandler(logging.NullHandler())


class CanvasInterface(Protocol):
    """Interface for canvas operations that work with any sprite type."""

    def get_pixel_data(self) -> list[tuple[int, int, int, int]]:
        """Get the current pixel data as a list of RGBA tuples."""
        ...

    def set_pixel_data(self, pixels: list[tuple[int, int, int, int]]) -> None:
        """Set the pixel data from a list of RGBA tuples."""
        ...

    def get_dimensions(self) -> tuple[int, int]:
        """Get the canvas dimensions as (width, height) in pixels."""
        ...

    def get_pixel_at(self, x: int, y: int) -> tuple[int, int, int, int]:
        """Get the color of a pixel at the given coordinates."""
        ...

    def set_pixel_at(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        """Set the color of a pixel at the given coordinates."""
        ...

    def get_surface(self) -> pygame.Surface:
        """Get the current rendered surface."""
        ...

    def mark_dirty(self) -> None:
        """Mark the canvas as needing a redraw."""
        ...


class SpriteSerializer(ABC):
    """Abstract base class for sprite serialization."""

    @abstractmethod
    def save(self, sprite: Any, filename: str, file_format: str = DEFAULT_FILE_FORMAT) -> None:
        """Save a sprite to a file.

        Args:
            sprite: The sprite to save
            filename: Path where to save the file
            file_format: Format to save in ("ini" or "yaml")

        """

    @abstractmethod
    def load(self, filename: str) -> Any:
        """Load a sprite from a file.

        Args:
            filename: Path to the sprite file

        Returns:
            The loaded sprite

        """


class CanvasRenderer(ABC):
    """Abstract base class for canvas rendering."""

    @abstractmethod
    def render(self, sprite: Any) -> pygame.Surface:
        """Render a sprite to a surface.

        Args:
            sprite: The sprite to render

        Returns:
            The rendered surface

        """

    @abstractmethod
    def force_redraw(self, sprite: Any) -> pygame.Surface:
        """Force a complete redraw of the sprite.

        Args:
            sprite: The sprite to redraw

        Returns:
            The redrawn surface

        """

    @abstractmethod
    def get_pixel_size(self) -> tuple[int, int]:
        """Get the size of individual pixels in the renderer.

        Returns:
            Tuple of (pixel_width, pixel_height)

        """


class StaticCanvasInterface:
    """Canvas interface implementation for static BitmappySprites."""

    def __init__(self, canvas_sprite):
        """Initialize with a CanvasSprite instance."""
        self.canvas_sprite = canvas_sprite

    def get_pixel_data(self) -> list[tuple[int, int, int, int]]:
        """Get the current pixel data as a list of RGBA tuples."""
        return self.canvas_sprite.pixels.copy()

    def set_pixel_data(self, pixels: list[tuple[int, int, int, int]]) -> None:
        """Set the pixel data from a list of RGBA tuples."""
        self.canvas_sprite.pixels = pixels.copy()
        # Mark all pixels as dirty
        self.canvas_sprite.dirty_pixels = [True] * len(pixels)
        self.canvas_sprite.dirty = 1

    def get_dimensions(self) -> tuple[int, int]:
        """Get the canvas dimensions as (width, height) in pixels."""
        return (self.canvas_sprite.pixels_across, self.canvas_sprite.pixels_tall)

    def get_pixel_at(self, x: int, y: int) -> tuple[int, int, int, int]:
        """Get the color of a pixel at the given coordinates."""
        if 0 <= x < self.canvas_sprite.pixels_across and 0 <= y < self.canvas_sprite.pixels_tall:
            pixel_num = y * self.canvas_sprite.pixels_across + x
            pixel = self.canvas_sprite.pixels[pixel_num]
            if len(pixel) == 4:
                return pixel
            else:
                return (pixel[0], pixel[1], pixel[2], 255)
        return (255, 0, 255, 255)  # Return magenta for out-of-bounds

    def set_pixel_at(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        """Set the color of a pixel at the given coordinates."""
        if 0 <= x < self.canvas_sprite.pixels_across and 0 <= y < self.canvas_sprite.pixels_tall:
            pixel_num = y * self.canvas_sprite.pixels_across + x
            self.canvas_sprite.pixels[pixel_num] = color
            self.canvas_sprite.dirty_pixels[pixel_num] = True
            self.canvas_sprite.dirty = 1

    def get_surface(self) -> pygame.Surface:
        """Get the current rendered surface."""
        return self.canvas_sprite.image

    def mark_dirty(self) -> None:
        """Mark the canvas as needing a redraw."""
        self.canvas_sprite.dirty = 1


class StaticSpriteSerializer(SpriteSerializer):
    """Serializer for static BitmappySprites."""

    @staticmethod
    def save(sprite: Any, filename: str, file_format: str = DEFAULT_FILE_FORMAT) -> None:
        """Save a static sprite to a file."""
        # Delegate to the sprite's save method
        sprite.save(filename, file_format)

    def load(self, filename: str) -> Any:
        """Load a static sprite from a file."""
        # This will be handled by the CanvasSprite's load method
        # which maintains the existing event callback structure


class StaticCanvasRenderer(CanvasRenderer):
    """Renderer for static BitmappySprites."""

    def __init__(self, canvas_sprite):
        """Initialize with a CanvasSprite instance."""
        self.canvas_sprite = canvas_sprite

    def render(self, sprite: Any) -> pygame.Surface:
        """Render a static sprite to a surface."""
        # Use the force_redraw method to avoid recursion
        return self.force_redraw(sprite)

    def force_redraw(self, sprite: Any) -> pygame.Surface:
        """Force a complete redraw of the static sprite."""
        # Directly implement the redraw logic to avoid recursion
        self.canvas_sprite.image.fill(self.canvas_sprite.background_color)

        # Draw all pixels, regardless of dirty state
        for i, pixel in enumerate(self.canvas_sprite.pixels):
            x = (i % self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_width
            y = (i // self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_height
            
            # Handle transparency key color specially
            if pixel == (255, 0, 255) or pixel == (255, 0, 255, 255):
                # Skip drawing transparent pixels - they should show the background
                continue
            
            # Draw normal pixel
            pygame.draw.rect(
                self.canvas_sprite.image,
                pixel,
                (x, y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height),
            )
            
            # Check if any controller is active on this pixel
            controller_indicator_color = self._get_controller_indicator_for_pixel(i)
            if controller_indicator_color:
                # Draw plus sign indicator on top
                self._draw_plus_indicator(
                    self.canvas_sprite.image,
                    controller_indicator_color,
                    x, y,
                    self.canvas_sprite.pixel_width,
                    self.canvas_sprite.pixel_height
                )
            
            # Only draw border if border_thickness > 0
            if self.canvas_sprite.border_thickness > 0:
                pygame.draw.rect(
                    self.canvas_sprite.image,
                    (64, 64, 64),
                    (x, y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height),
                    self.canvas_sprite.border_thickness,
                )
            self.canvas_sprite.dirty_pixels[i] = False

        return self.canvas_sprite.image

    def get_pixel_size(self) -> tuple[int, int]:
        """Get the size of individual pixels in the renderer."""
        return (self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height)
    
    def _get_controller_indicator_for_pixel(self, pixel_index: int) -> Optional[tuple[int, int, int]]:
        """Check if any controller is active on this pixel and return indicator color."""
        # Get the parent scene to access controller data
        if hasattr(self.canvas_sprite, 'parent_scene') and self.canvas_sprite.parent_scene:
            scene = self.canvas_sprite.parent_scene
            if hasattr(scene, 'controller_selections') and hasattr(scene, 'mode_switcher'):
                # Check all controllers for canvas mode
                for controller_id, controller_selection in scene.controller_selections.items():
                    controller_mode = scene.mode_switcher.get_controller_mode(controller_id)
                    if controller_mode and controller_mode.value == 'canvas':
                        # Get controller position
                        position = scene.mode_switcher.get_controller_position(controller_id)
                        if position and position.is_valid:
                            # Convert position to pixel index
                            x, y = position.position
                            if 0 <= x < self.canvas_sprite.pixels_across and 0 <= y < self.canvas_sprite.pixels_tall:
                                controller_pixel_index = y * self.canvas_sprite.pixels_across + x
                                if controller_pixel_index == pixel_index:
                                    # Get controller color
                                    if hasattr(scene, 'multi_controller_manager'):
                                        controller_info = scene.multi_controller_manager.get_controller_info(controller_id)
                                        if controller_info:
                                            return controller_info.color
        return None

    def _draw_plus_indicator(self, surface: pygame.Surface, color: tuple[int, int, int], x: int, y: int, width: int, height: int) -> None:
        """Draw a box indicator with controller color and inverse color borders."""
        
        # The x,y coordinates are the top-left corner of the pixel box
        # Calculate the center of the pixel box in screen coordinates
        center_x = x + self.canvas_sprite.pixel_width // 2
        center_y = y + self.canvas_sprite.pixel_height // 2
        
        # Convert screen coordinates to pixel coordinates
        pixel_x = center_x // self.canvas_sprite.pixel_width
        pixel_y = center_y // self.canvas_sprite.pixel_height
        
        # Get the color of the specific pixel
        pixel_color = self._get_pixel_color_at_position(pixel_x, pixel_y)
        inverse_color = self._get_inverse_color(pixel_color)
        
        # Draw outer box with controller color (1 pixel wide)
        pygame.draw.rect(surface, color, (x + 1, y + 1, width - 2, height - 2), 1)
        
        # Draw inner box with inverse color for contrast (2 pixels wide)
        pygame.draw.rect(surface, inverse_color, (x + 2, y + 2, width - 4, height - 4), 2)

    def _get_pixel_color_at_position(self, x: int, y: int) -> tuple[int, int, int]:
        """Get the pixel color at the specified position."""
        if hasattr(self, 'canvas_sprite') and self.canvas_sprite:
            if 0 <= x < self.canvas_sprite.pixels_across and 0 <= y < self.canvas_sprite.pixels_tall:
                pixel_index = y * self.canvas_sprite.pixels_across + x
                if pixel_index < len(self.canvas_sprite.pixels):
                    pixel_color = self.canvas_sprite.pixels[pixel_index]
                    return pixel_color
                else:
                    print(f"DEBUG: Pixel index {pixel_index} out of range (max: {len(self.canvas_sprite.pixels) - 1})")
            else:
                print(f"DEBUG: Coordinates ({x}, {y}) out of bounds")
        print(f"DEBUG: Pixel not found at ({x}, {y}), returning black")
        return (0, 0, 0)  # Default to black if pixel not found

    def _get_inverse_color(self, color: tuple[int, int, int]) -> tuple[int, int, int]:
        """Get the inverse color for contrast."""
        return (255 - color[0], 255 - color[1], 255 - color[2])


class AnimatedCanvasInterface:
    """Canvas interface implementation for animated sprites."""

    def __init__(self, canvas_sprite):
        """Initialize with a CanvasSprite instance."""
        self.canvas_sprite = canvas_sprite
        # Set initial animation using sprite introspection
        if hasattr(canvas_sprite, "animated_sprite") and canvas_sprite.animated_sprite:
            if canvas_sprite.animated_sprite._animations:
                if (
                    hasattr(canvas_sprite.animated_sprite, "_animation_order")
                    and canvas_sprite.animated_sprite._animation_order
                ):
                    # Use the first animation in the file order
                    self.current_animation = canvas_sprite.animated_sprite._animation_order[0]
                else:
                    # Fall back to the first key in _animations
                    self.current_animation = next(
                        iter(canvas_sprite.animated_sprite._animations.keys())
                    )
            else:
                self.current_animation = ""
        else:
            self.current_animation = ""
        self.current_frame = 0

    def get_pixel_data(self) -> list[tuple[int, int, int, int]]:
        """Get the current pixel data as a list of RGBA tuples."""
        if hasattr(self.canvas_sprite, "animated_sprite"):
            frame = self.canvas_sprite.animated_sprite._animations[self.current_animation][
                self.current_frame
            ]
            pixels = frame.get_pixel_data()
        else:
            pixels = self.canvas_sprite.pixels.copy()
        
        # Ensure all pixels are RGBA format
        rgba_pixels = []
        for pixel in pixels:
            if len(pixel) == 4:
                rgba_pixels.append(pixel)
            else:
                # Convert RGB to RGBA with full opacity
                rgba_pixels.append((pixel[0], pixel[1], pixel[2], 255))
        
        return rgba_pixels

    def set_pixel_data(self, pixels: list[tuple[int, int, int, int]]) -> None:
        """Set the pixel data from a list of RGBA tuples."""
        if hasattr(self.canvas_sprite, "animated_sprite"):
            frame = self.canvas_sprite.animated_sprite._animations[self.current_animation][
                self.current_frame
            ]
            frame.set_pixel_data(pixels)
        else:
            self.canvas_sprite.pixels = pixels.copy()
            # Mark all pixels as dirty
            self.canvas_sprite.dirty_pixels = [True] * len(pixels)
            self.canvas_sprite.dirty = 1

    def get_dimensions(self) -> tuple[int, int]:
        """Get the canvas dimensions as (width, height) in pixels."""
        return (self.canvas_sprite.pixels_across, self.canvas_sprite.pixels_tall)

    def get_pixel_at(self, x: int, y: int) -> tuple[int, int, int, int]:
        """Get the color of a pixel at the given coordinates."""
        if 0 <= x < self.canvas_sprite.pixels_across and 0 <= y < self.canvas_sprite.pixels_tall:
            pixel_num = y * self.canvas_sprite.pixels_across + x
            if hasattr(self.canvas_sprite, "animated_sprite"):
                # Get the current frame from the canvas (not the animated sprite)
                current_animation = self.canvas_sprite.current_animation
                current_frame_index = self.canvas_sprite.current_frame

                # Access the frame through the animated sprite's frames property
                if current_animation in self.canvas_sprite.animated_sprite.frames:
                    frame = self.canvas_sprite.animated_sprite._animations[current_animation][
                        current_frame_index
                    ]
                    pixel = frame.get_pixel_data()[pixel_num]
                    if len(pixel) == 4:
                        return pixel
                    else:
                        return (pixel[0], pixel[1], pixel[2], 255)
            pixel = self.canvas_sprite.pixels[pixel_num]
            if len(pixel) == 4:
                return pixel
            else:
                return (pixel[0], pixel[1], pixel[2], 255)
        return (255, 0, 255, 255)  # Return magenta for out-of-bounds

    def set_pixel_at(self, x: int, y: int, color: tuple[int, int, int], skip_drag_ops: bool = False) -> None:
        """Set the color of a pixel at the given coordinates.
        
        Args:
            x: X coordinate
            y: Y coordinate
            color: Color tuple
            skip_drag_ops: If True, skip expensive operations during drag (used for optimization)
        """
        if 0 <= x < self.canvas_sprite.pixels_across and 0 <= y < self.canvas_sprite.pixels_tall:
            pixel_num = y * self.canvas_sprite.pixels_across + x
            
            # Get the old color for undo tracking
            old_color = None
            if hasattr(self.canvas_sprite, "animated_sprite"):
                current_animation = self.canvas_sprite.current_animation
                current_frame_index = self.canvas_sprite.current_frame
                
                if current_animation in self.canvas_sprite.animated_sprite.frames:
                    frame = self.canvas_sprite.animated_sprite._animations[current_animation][
                        current_frame_index
                    ]
                    frame_pixels = frame.get_pixel_data()
                    old_color = frame_pixels[pixel_num]
            else:
                old_color = self.canvas_sprite.pixels[pixel_num]
            
            # Skip expensive operations during drag if flag is set
            if skip_drag_ops:
                # Fast path: just update the pixel data, skip everything else
                self.canvas_sprite.pixels[pixel_num] = color
                self.canvas_sprite.dirty_pixels[pixel_num] = True
                self.canvas_sprite.dirty = 1
                return
            
            # Track the pixel change for undo/redo if we have a parent scene with operation tracker
            # Skip tracking if we're currently applying undo/redo to prevent feedback loops
            # Skip tracking if a controller drag is active (controller drag handles its own tracking)
            # But allow the initial pixel to be painted and tracked normally
            controller_drag_active = False
            if (hasattr(self.canvas_sprite, "parent_scene") and 
                self.canvas_sprite.parent_scene and 
                hasattr(self.canvas_sprite.parent_scene, "controller_drags")):
                # Check if any controller has an active drag with multiple pixels
                for controller_id, drag_info in self.canvas_sprite.parent_scene.controller_drags.items():
                    if drag_info.get('active', False) and len(drag_info.get('pixels_drawn', [])) > 0:
                        controller_drag_active = True
                        print(f"DEBUG: Controller drag active with pixels for controller {controller_id}, skipping canvas interface tracking")
                        break
            
            if (hasattr(self.canvas_sprite, "parent_scene") and 
                self.canvas_sprite.parent_scene and 
                hasattr(self.canvas_sprite.parent_scene, "canvas_operation_tracker") and
                not getattr(self.canvas_sprite.parent_scene, "_applying_undo_redo", False) and
                not controller_drag_active and
                old_color != color):  # Only track if color actually changed
                
                # Collect pixel changes during drag operations
                if not hasattr(self.canvas_sprite.parent_scene, "_current_pixel_changes"):
                    self.canvas_sprite.parent_scene._current_pixel_changes = []
                if not hasattr(self.canvas_sprite.parent_scene, "_current_pixel_changes_dict"):
                    # Use a dict for O(1) deduplication lookups during drag
                    # Maps (x, y) -> (x, y, old_color, new_color) for fast replacement
                    self.canvas_sprite.parent_scene._current_pixel_changes_dict = {}
                
                # Performance optimization: Use dict for O(1) deduplication to prevent memory bloat
                # If the same pixel was already changed in this drag, replace the old entry
                # This prevents unbounded growth during long drags on the same pixels
                pixel_key = (x, y)
                pixel_changes_dict = self.canvas_sprite.parent_scene._current_pixel_changes_dict
                
                # Store or update the pixel change (keeps original old_color, updates new_color)
                if pixel_key in pixel_changes_dict:
                    # Update existing: keep original old_color, update to latest new_color
                    existing = pixel_changes_dict[pixel_key]
                    pixel_changes_dict[pixel_key] = (x, y, existing[2], color)
                else:
                    # New pixel change
                    pixel_changes_dict[pixel_key] = (x, y, old_color, color)
                
                # Convert dict to list format for compatibility (only when needed, not every time)
                # We'll convert to list format when submitting, but keep dict for efficient updates
                # Update the list periodically or convert on-demand
                if not hasattr(self.canvas_sprite.parent_scene, "_pixel_changes_list_dirty"):
                    self.canvas_sprite.parent_scene._pixel_changes_list_dirty = True
                
                # Only convert to list occasionally or when submitting - this avoids O(n) conversion every drag event
                # The dict will be converted to list when _submit_pixel_changes_if_ready is called
                
                # Safety limit: If collection grows beyond 2000 unique pixels, trim oldest entries
                # (Unlikely with deduplication, but protects against edge cases)
                max_pixel_changes = 2000
                if len(pixel_changes_dict) > max_pixel_changes:
                    # Keep only the most recent entries (dict keeps insertion order in Python 3.7+)
                    items = list(pixel_changes_dict.items())[-1500:]
                    pixel_changes_dict.clear()
                    pixel_changes_dict.update(items)
                
                # Only log debug info occasionally to reduce overhead
                if len(pixel_changes_dict) % 100 == 0:
                    LOG.debug(f"Canvas interface pixel changes: {len(pixel_changes_dict)} unique pixels")
                
                # Start a timer for single clicks (if this is the first pixel)
                if len(self.canvas_sprite.parent_scene._current_pixel_changes_dict) == 1:
                    import time
                    self.canvas_sprite.parent_scene._pixel_change_timer = time.time()
                    LOG.debug(f"Canvas interface started pixel change timer for single click")
            elif controller_drag_active:
                # Controller drag is active with pixels, don't collect pixels in canvas interface
                print(f"DEBUG: Controller drag active with pixels, skipping canvas interface pixel collection")
                # But still update the frame data - don't return early
            
            if hasattr(self.canvas_sprite, "animated_sprite"):
                # Get the current frame from the canvas (not the animated sprite)
                current_animation = self.canvas_sprite.current_animation
                current_frame_index = self.canvas_sprite.current_frame

                # Access the frame through the animated sprite's frames property
                if current_animation in self.canvas_sprite.animated_sprite.frames:
                    frame = self.canvas_sprite.animated_sprite._animations[current_animation][
                        current_frame_index
                    ]
                    frame_pixels = frame.get_pixel_data()
                    frame_pixels[pixel_num] = color
                    frame.set_pixel_data(frame_pixels)

                    # Clear the surface cache for this frame so it gets regenerated
                    if hasattr(self.canvas_sprite.animated_sprite, "_surface_cache"):
                        cache_key = f"{current_animation}_{current_frame_index}"
                        if cache_key in self.canvas_sprite.animated_sprite._surface_cache:
                            del self.canvas_sprite.animated_sprite._surface_cache[cache_key]

                    # Mark canvas as dirty so it will redraw
                    self.canvas_sprite.dirty_pixels[pixel_num] = True
                    self.canvas_sprite.dirty = 1

                    # Trigger pixel update event to notify film strip
                    if hasattr(self.canvas_sprite, "on_pixel_update_event"):
                        # Create a mock event and trigger object
                        class MockEvent:
                            pass

                        class MockTrigger:
                            def __init__(self, pixel_num, color):
                                self.pixel_number = pixel_num
                                self.pixel_color = color

                        mock_event = MockEvent()
                        mock_trigger = MockTrigger(pixel_num, color)
                        self.canvas_sprite.on_pixel_update_event(mock_event, mock_trigger)
            else:
                self.canvas_sprite.pixels[pixel_num] = color
                self.canvas_sprite.dirty_pixels[pixel_num] = True
                self.canvas_sprite.dirty = 1

    def get_surface(self) -> pygame.Surface:
        """Get the current rendered surface."""
        return self.canvas_sprite.image

    def mark_dirty(self) -> None:
        """Mark the canvas as needing a redraw."""
        self.canvas_sprite.dirty = 1

    def set_current_frame(self, animation: str, frame: int) -> None:
        """Set the current animation and frame."""
        self.current_animation = animation
        self.current_frame = frame
        # Don't call show_frame here to avoid recursion
        # The canvas sprite will handle the frame switching

    def get_current_frame(self) -> tuple[str, int]:
        """Get the current animation and frame."""
        return (self.current_animation, self.current_frame)


class AnimatedSpriteSerializer(SpriteSerializer):
    """Serializer for animated sprites."""

    @staticmethod
    def save(sprite: Any, filename: str, file_format: str = DEFAULT_FILE_FORMAT) -> None:
        """Save an animated sprite to a file."""
        # Delegate to the sprite's save method
        sprite.save(filename, file_format)

    def load(self, filename: str) -> Any:
        """Load an animated sprite from a file."""
        # This will be handled by the CanvasSprite's load method
        # which maintains the existing event callback structure


class AnimatedCanvasRenderer(CanvasRenderer):
    """Renderer for animated sprites."""

    def __init__(self, canvas_sprite):
        """Initialize with a CanvasSprite instance."""
        self.canvas_sprite = canvas_sprite

    def render(self, sprite: Any) -> pygame.Surface:
        """Render an animated sprite to a surface."""
        # Use the force_redraw method to avoid recursion
        return self.force_redraw(sprite)

    def force_redraw(self, sprite: Any) -> pygame.Surface:
        """Force a complete redraw of the animated sprite."""
        LOG.debug("DEBUG: AnimatedCanvasRenderer.force_redraw called")
        if hasattr(self.canvas_sprite, "animated_sprite"):
            # Get the current frame from the canvas (not the animated sprite)
            current_animation = self.canvas_sprite.current_animation
            current_frame = self.canvas_sprite.current_frame
            frames = self.canvas_sprite.animated_sprite.frames
            
            LOG.debug(f"DEBUG: current_animation={current_animation}, current_frame={current_frame}")
            LOG.debug(f"DEBUG: frames keys={list(frames.keys()) if frames else 'None'}")
            LOG.debug(f"DEBUG: frames[current_animation] length={len(frames[current_animation]) if current_animation in frames else 'N/A'}")

            if current_animation in frames and current_frame < len(frames[current_animation]):
                # Create a single transparent buffer for all frames (hardware accelerated)
                self.canvas_sprite.image = pygame.Surface((
                    self.canvas_sprite.width,
                    self.canvas_sprite.height,
                ), pygame.SRCALPHA)
                self.canvas_sprite.image = self.canvas_sprite.image.convert_alpha()
                self.canvas_sprite.image.fill((255, 0, 255, 255))  # Magenta background at 100% opacity

                # Get onion skinning manager
                from .onion_skinning import get_onion_skinning_manager
                onion_manager = get_onion_skinning_manager()
                
                # If onion skinning is enabled, blend only explicitly enabled frames
                if onion_manager.is_global_onion_skinning_enabled():
                    # Get only frames that have onion skinning explicitly enabled
                    onion_frames = set()
                    for frame_idx in range(len(frames[current_animation])):
                        if frame_idx != current_frame and onion_manager.is_frame_onion_skinned(current_animation, frame_idx):
                            onion_frames.add(frame_idx)
                    LOG.debug(f"Rendering onion frames: {onion_frames}")
                    
                    # Create a temporary surface to accumulate onion layers (hardware accelerated)
                    onion_accumulator = pygame.Surface((
                        self.canvas_sprite.width,
                        self.canvas_sprite.height,
                    ), pygame.SRCALPHA)
                    onion_accumulator = onion_accumulator.convert_alpha()
                    onion_accumulator.fill((0, 0, 0, 0))  # Transparent background
                    
                    # Blend each onion frame into the accumulator
                    for frame_idx in onion_frames:
                        if frame_idx < len(frames[current_animation]):
                            frame = frames[current_animation][frame_idx]
                            if hasattr(frame, "get_pixel_data"):
                                frame_pixels = frame.get_pixel_data()
                            else:
                                frame_pixels = getattr(
                                    frame,
                                    "pixels",
                                    [(255, 0, 255)] * (self.canvas_sprite.pixels_across * self.canvas_sprite.pixels_tall),
                                )
                            
                            # Create a temporary surface for this onion frame (hardware accelerated)
                            frame_surface = pygame.Surface((
                                self.canvas_sprite.width,
                                self.canvas_sprite.height,
                            ), pygame.SRCALPHA)
                            frame_surface = frame_surface.convert_alpha()
                            frame_surface.fill((0, 0, 0, 0))  # Transparent background
                            
                            # Draw each pixel with onion transparency (skip 255,0,255 pixels)
                            # NOTE: Onion layers should NOT be panned - they stay in original position
                            for i, pixel in enumerate(frame_pixels):
                                # Skip transparent pixels (magenta) - 100% transparent
                                if pixel == (255, 0, 255) or pixel == (255, 0, 255, 255):
                                    continue
                                    
                                x = (i % self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_width
                                y = (i // self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_height
                                
                                # Do NOT apply panning offset to onion layers - they stay in original position
                                
                                # Draw pixel with onion transparency
                                alpha = int(255 * onion_manager.onion_transparency)
                                
                                # Handle both RGB and RGBA pixels
                                if len(pixel) == 4:
                                    # Already RGBA - combine with onion transparency
                                    r, g, b, pixel_alpha = pixel
                                    combined_alpha = int((pixel_alpha * alpha) / 255)
                                    transparent_pixel = (r, g, b, combined_alpha)
                                else:
                                    # RGB pixel - add onion transparency
                                    transparent_pixel = (*pixel, alpha)
                                
                                pygame.draw.rect(
                                    frame_surface,
                                    transparent_pixel,
                                    (x, y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height)
                                )
                            
                            # Blend this frame into the accumulator using alpha blending
                            onion_accumulator.blit(frame_surface, (0, 0), special_flags=pygame.BLEND_ALPHA_SDL2)
                    
                    # Blit the accumulated onion layers onto the main canvas
                    self.canvas_sprite.image.blit(onion_accumulator, (0, 0))

                # Finally, blit the selected frame at 100% opacity (skip 255,0,255 pixels)
                # Check if selected frame should be visible (for comparison mode)
                selected_frame_visible = True
                if hasattr(self.canvas_sprite, 'parent_scene') and self.canvas_sprite.parent_scene:
                    selected_frame_visible = getattr(self.canvas_sprite.parent_scene, 'selected_frame_visible', True)
                
                # Always get frame data for controller indicators, even if frame is hidden
                frame = frames[current_animation][current_frame]
                
                # Use panned pixel data if panning is active, otherwise use original frame data
                if (hasattr(self.canvas_sprite, '_panning_active') and 
                    self.canvas_sprite._panning_active and 
                    hasattr(self.canvas_sprite, 'pixels')):
                    frame_pixels = self.canvas_sprite.pixels
                    LOG.debug(f"DEBUG: Using panned canvas pixels: {len(frame_pixels)} pixels, first few: {frame_pixels[:3]}")
                else:
                    if hasattr(frame, "get_pixel_data"):
                        frame_pixels = frame.get_pixel_data()
                        LOG.debug(f"DEBUG: Using frame.get_pixel_data(): {len(frame_pixels)} pixels, first few: {frame_pixels[:3]}")
                    else:
                        frame_pixels = getattr(
                            frame,
                            "pixels",
                            [(255, 0, 255)]
                            * (self.canvas_sprite.pixels_across * self.canvas_sprite.pixels_tall),
                        )
                        LOG.debug(f"DEBUG: Using fallback frame pixels: {len(frame_pixels)} pixels, first few: {frame_pixels[:3]}")

                # Use the border thickness set by the canvas sprite
                border_thickness = self.canvas_sprite.border_thickness
                LOG.debug(f"DEBUG RENDERER: border_thickness={border_thickness}")
                
                if selected_frame_visible:
                    # Blit each pixel of the selected frame at 100% opacity
                    for i, pixel in enumerate(frame_pixels):
                        x = (i % self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_width
                        y = (i // self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_height
                        
                        # Do NOT apply panning offset to drawing coordinates - grid stays fixed
                        # Panning is handled by extracting different pixel data, not moving the grid
                        
                        # Check if any controller is active on this pixel (even for transparent pixels)
                        controller_indicator_color = self._get_controller_indicator_for_pixel(i)
                        
                        # Skip transparent pixels (magenta) - they should show the background
                        if pixel == (255, 0, 255) or pixel == (255, 0, 255, 255):
                            # Still draw controller indicators even for transparent pixels
                            if controller_indicator_color:
                                self._draw_plus_indicator(
                                    self.canvas_sprite.image,
                                    controller_indicator_color,
                                    x, y,
                                    self.canvas_sprite.pixel_width,
                                    self.canvas_sprite.pixel_height
                                )
                            continue
                        
                        if controller_indicator_color:
                            # Draw normal pixel first with alpha blending if RGBA
                            if len(pixel) == 4:
                                # RGBA pixel - use alpha blending
                                pygame.draw.rect(
                                    self.canvas_sprite.image,
                                    pixel,
                                    (x, y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height),
                                )
                            else:
                                # RGB pixel - convert to RGBA for alpha surface
                                rgba_pixel = (pixel[0], pixel[1], pixel[2], 255)
                                pygame.draw.rect(
                                    self.canvas_sprite.image,
                                    rgba_pixel,
                                    (x, y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height),
                                )
                            # Draw plus sign indicator on top
                            self._draw_plus_indicator(
                                self.canvas_sprite.image,
                                controller_indicator_color,
                                x, y,
                                self.canvas_sprite.pixel_width,
                                self.canvas_sprite.pixel_height
                            )
                        else:
                            # Draw normal pixel with alpha blending if RGBA
                            if len(pixel) == 4:
                                # RGBA pixel - use alpha blending
                                pygame.draw.rect(
                                    self.canvas_sprite.image,
                                    pixel,
                                    (x, y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height),
                                )
                            else:
                                # RGB pixel - convert to RGBA for alpha surface
                                rgba_pixel = (pixel[0], pixel[1], pixel[2], 255)
                                pygame.draw.rect(
                                    self.canvas_sprite.image,
                                    rgba_pixel,
                                    (x, y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height),
                                )
                else:
                    # Selected frame is hidden, but still draw controller indicators
                    for i, pixel in enumerate(frame_pixels):
                        x = (i % self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_width
                        y = (i // self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_height
                        
                        # Do NOT apply panning offset to drawing coordinates - grid stays fixed
                        
                        # Check if any controller is active on this pixel
                        controller_indicator_color = self._get_controller_indicator_for_pixel(i)
                        
                        # Only draw controller indicators, no pixels
                        if controller_indicator_color:
                            self._draw_plus_indicator(
                                self.canvas_sprite.image,
                                controller_indicator_color,
                                x, y,
                                self.canvas_sprite.pixel_width,
                                self.canvas_sprite.pixel_height
                            )
                
                # Draw borders on the main canvas (only if selected frame is visible)
                if selected_frame_visible and border_thickness > 0:
                    for i, pixel in enumerate(frame_pixels):
                        x = (i % self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_width
                        y = (i // self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_height
                        
                        # Do NOT apply panning offset to drawing coordinates - grid stays fixed
                        
                        pygame.draw.rect(
                            self.canvas_sprite.image,
                            (64, 64, 64),
                            (x, y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height),
                            border_thickness,
                        )
            else:
                # Fall back to static rendering if frame not found
                self.canvas_sprite.image.fill(self.canvas_sprite.background_color)
                # Use the border thickness set by the canvas sprite
                border_thickness = self.canvas_sprite.border_thickness

                for i, pixel in enumerate(self.canvas_sprite.pixels):
                    x = (i % self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_width
                    y = (i // self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_height
                    
                    # Do NOT apply panning offset to drawing coordinates - grid stays fixed
                    
                    # Check if any controller is active on this pixel
                    controller_indicator_color = self._get_controller_indicator_for_pixel(i)
                    if controller_indicator_color:
                        # Draw normal pixel first
                        pygame.draw.rect(
                            self.canvas_sprite.image,
                            pixel,
                            (x, y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height),
                        )
                        # Draw plus sign indicator on top
                        self._draw_plus_indicator(
                            self.canvas_sprite.image,
                            controller_indicator_color,
                            x, y,
                            self.canvas_sprite.pixel_width,
                            self.canvas_sprite.pixel_height
                        )
                    else:
                        # Draw normal pixel
                        pygame.draw.rect(
                            self.canvas_sprite.image,
                            pixel,
                            (x, y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height),
                        )
                    
                    # Only draw border if border_thickness > 0
                    if border_thickness > 0:
                        pygame.draw.rect(
                            self.canvas_sprite.image,
                            (64, 64, 64),
                            (x, y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height),
                            border_thickness,
                        )
        else:
            # Fall back to static rendering
            self.canvas_sprite.image.fill(self.canvas_sprite.background_color)
            # Use the border thickness set by the canvas sprite
            border_thickness = self.canvas_sprite.border_thickness

            for i, pixel in enumerate(self.canvas_sprite.pixels):
                x = (i % self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_width
                y = (i // self.canvas_sprite.pixels_across) * self.canvas_sprite.pixel_height
                
                # Do NOT apply panning offset to drawing coordinates - grid stays fixed
                
                # Check if any controller is active on this pixel
                controller_indicator_color = self._get_controller_indicator_for_pixel(i)
                if controller_indicator_color:
                    # Draw controller indicator instead of normal pixel
                    pygame.draw.rect(
                        self.canvas_sprite.image,
                        controller_indicator_color,
                        (x, y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height),
                    )
                else:
                    # Draw normal pixel
                    pygame.draw.rect(
                        self.canvas_sprite.image,
                        pixel,
                        (x, y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height),
                    )
                
                # Only draw border if border_thickness > 0
                if border_thickness > 0:
                    pygame.draw.rect(
                        self.canvas_sprite.image,
                        (64, 64, 64),
                        (x, y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height),
                        border_thickness,
                    )

        # Draw hover effect for the hovered pixel (white border to match keyboard selector)
        if (hasattr(self.canvas_sprite, 'hovered_pixel') and 
            self.canvas_sprite.hovered_pixel is not None):
            hover_x, hover_y = self.canvas_sprite.hovered_pixel
            pixel_x = hover_x * self.canvas_sprite.pixel_width
            pixel_y = hover_y * self.canvas_sprite.pixel_height
            
            # Draw white border around the hovered pixel (2px thick to match keyboard selector style)
            pygame.draw.rect(
                self.canvas_sprite.image,
                (255, 255, 255),  # White color
                (pixel_x, pixel_y, self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height),
                2  # 2px border thickness
            )

        # Draw canvas hover border (1px white border around entire canvas perimeter)
        if (hasattr(self.canvas_sprite, 'is_hovered') and 
            self.canvas_sprite.is_hovered):
            # Draw white border around the entire canvas perimeter
            pygame.draw.rect(
                self.canvas_sprite.image,
                (255, 255, 255),  # White color
                (0, 0, self.canvas_sprite.image.get_width(), self.canvas_sprite.image.get_height()),
                1  # 1px border thickness
            )

        return self.canvas_sprite.image

    def get_pixel_size(self) -> tuple[int, int]:
        """Get the size of individual pixels in the renderer."""
        return (self.canvas_sprite.pixel_width, self.canvas_sprite.pixel_height)
    
    def _get_controller_indicator_for_pixel(self, pixel_index: int) -> Optional[tuple[int, int, int]]:
        """Check if any controller is active on this pixel and return indicator color."""
        # Get the parent scene to access controller data
        if hasattr(self.canvas_sprite, 'parent_scene') and self.canvas_sprite.parent_scene:
            scene = self.canvas_sprite.parent_scene
            if hasattr(scene, 'controller_selections') and hasattr(scene, 'mode_switcher'):
                # Check all controllers for canvas mode
                for controller_id, controller_selection in scene.controller_selections.items():
                    controller_mode = scene.mode_switcher.get_controller_mode(controller_id)
                    if controller_mode and controller_mode.value == 'canvas':
                        # Get controller position
                        position = scene.mode_switcher.get_controller_position(controller_id)
                        if position and position.is_valid:
                            # Convert position to pixel index
                            x, y = position.position
                            if 0 <= x < self.canvas_sprite.pixels_across and 0 <= y < self.canvas_sprite.pixels_tall:
                                controller_pixel_index = y * self.canvas_sprite.pixels_across + x
                                if controller_pixel_index == pixel_index:
                                    # Get controller color
                                    if hasattr(scene, 'multi_controller_manager'):
                                        controller_info = scene.multi_controller_manager.get_controller_info(controller_id)
                                        if controller_info:
                                            return controller_info.color
        return None

    def _draw_plus_indicator(self, surface: pygame.Surface, color: tuple[int, int, int], x: int, y: int, width: int, height: int) -> None:
        """Draw a box indicator with controller color and inverse color borders."""
        
        # The x,y coordinates are the top-left corner of the pixel box
        # Calculate the center of the pixel box in screen coordinates
        center_x = x + self.canvas_sprite.pixel_width // 2
        center_y = y + self.canvas_sprite.pixel_height // 2
        
        # Convert screen coordinates to pixel coordinates
        pixel_x = center_x // self.canvas_sprite.pixel_width
        pixel_y = center_y // self.canvas_sprite.pixel_height
        
        # Get the color of the specific pixel
        pixel_color = self._get_pixel_color_at_position(pixel_x, pixel_y)
        inverse_color = self._get_inverse_color(pixel_color)
        
        # Draw outer box with controller color (1 pixel wide)
        pygame.draw.rect(surface, color, (x + 1, y + 1, width - 2, height - 2), 1)
        
        # Draw inner box with inverse color for contrast (2 pixels wide)
        pygame.draw.rect(surface, inverse_color, (x + 2, y + 2, width - 4, height - 4), 2)

    def _get_pixel_color_at_position(self, x: int, y: int) -> tuple[int, int, int]:
        """Get the pixel color at the specified position."""
        if hasattr(self, 'canvas_sprite') and self.canvas_sprite:
            if 0 <= x < self.canvas_sprite.pixels_across and 0 <= y < self.canvas_sprite.pixels_tall:
                pixel_index = y * self.canvas_sprite.pixels_across + x
                if pixel_index < len(self.canvas_sprite.pixels):
                    pixel_color = self.canvas_sprite.pixels[pixel_index]
                    return pixel_color
                else:
                    print(f"DEBUG: Pixel index {pixel_index} out of range (max: {len(self.canvas_sprite.pixels) - 1})")
            else:
                print(f"DEBUG: Coordinates ({x}, {y}) out of bounds")
        print(f"DEBUG: Pixel not found at ({x}, {y}), returning black")
        return (0, 0, 0)  # Default to black if pixel not found

    def _get_inverse_color(self, color: tuple[int, int, int]) -> tuple[int, int, int]:
        """Get the inverse color for contrast."""
        return (255 - color[0], 255 - color[1], 255 - color[2])