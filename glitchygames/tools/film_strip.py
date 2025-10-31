"""Film strip widget for animated sprite frame selection.

This module provides a film reel-style interface for selecting and navigating
between frames in animated sprites, with sprocket separators between animations.
"""

# No typing imports needed

import logging
from copy import deepcopy
from typing import ClassVar

import pygame
from glitchygames.fonts import FontManager
from glitchygames.sprites import AnimatedSprite, SpriteFrame

LOG = logging.getLogger("game.tools.film_strip")
LOG.addHandler(logging.NullHandler())


class FilmStripWidget:
    """Film reel-style widget for frame selection in animated sprites.

    ARCHITECTURE OVERVIEW:
    This widget provides a film strip interface for displaying and interacting with
    animated sprite frames. It supports both static frame selection and continuous
    preview animations.

    KEY COMPONENTS:
    1. Preview Animation System:
       - Each film strip has independent animation timing via preview_animation_times
       - Animations run continuously in the background, independent of user interaction
       - Multiple film strips can show different animations at different speeds

    2. Frame Selection System:
       - Users can click on frames to select them for editing
       - Selected frames are highlighted with a red border
       - Frame selection updates the main canvas for editing

    3. Dirty Propagation System:
       - Film strips mark themselves as dirty when animations advance
       - This triggers redraws in the sprite group system
       - Ensures smooth, continuous animation updates

    DEBUGGING GUIDE:
    - If animations don't run: Check that update_animations() is called every frame
    - If animations are choppy: Verify delta time (dt) is reasonable (0.016 = 60fps)
    - If wrong frames show: Check preview_animation_times calculation
    - If animations don't loop: Verify total_duration and modulo operation
    - If film strips don't redraw: Check dirty flag propagation
    """

    # Color cycling background colors (RGBA for transparency support)
    BACKGROUND_COLORS: ClassVar[list[tuple[int, int, int, int]]] = [
        (0, 255, 255, 255),  # Cyan
        (0, 0, 0, 255),  # Black
        (128, 128, 128, 255),  # Gray
        (255, 255, 255, 255),  # White
        (255, 0, 255, 255),  # Magenta
        (0, 255, 0, 255),  # Green
        (0, 0, 255, 255),  # Blue
        (255, 255, 0, 255),  # Yellow
        (64, 64, 64, 255),  # Dark Gray
        (192, 192, 192, 255),  # Light Gray
    ]

    # Debug dump interval in seconds
    DEBUG_DUMP_INTERVAL: ClassVar[float] = 5.0

    # Number of frames to show at a time in the film strip
    FRAMES_PER_VIEW: ClassVar[int] = 4

    def __init__(self, x: int, y: int, width: int, height: int):
        """Initialize the film strip widget."""
        self.rect = pygame.Rect(x, y, width, height)
        self.animated_sprite: AnimatedSprite | None = None
        self.current_animation = ""  # Will be set when sprite is loaded
        self.current_frame = 0  # Animation preview frame (right side)
        self.selected_frame = 0  # Selected frame in static thumbnails (left side)
        self.is_selected = False  # Track if this film strip is currently selected
        self.hovered_frame: tuple[str, int] | None = None
        self.hovered_animation: str | None = None
        self.hovered_preview: str | None = None
        self.is_hovering_strip: bool = False
        self.hovered_removal_button: tuple[str, int] | None = None  # Track which removal button is hovered

        # Color cycling state
        self.background_color_index = 2  # Start with gray instead of cyan
        self.background_color = self.BACKGROUND_COLORS[self.background_color_index]

        # Film strip styling
        self.frame_width = 64
        self.frame_height = 64
        self.sprocket_width = 20
        self.frame_spacing = 2
        self.animation_label_height = 20

        # Preview area styling
        self.preview_width = 64  # Width reserved for individual animation previews
        self.preview_height = 64  # Height of each preview area
        self.preview_padding = 4  # Padding around each preview

        # Colors
        self.film_background = (100, 70, 55)  # Darker copper brown color
        self.sprocket_color = (20, 20, 20)
        self.frame_border = (120, 90, 70)  # Copper brown frame borders
        self.selection_color = (255, 0, 0)  # Red selection border
        self.first_frame_color = (255, 0, 0)  # Red border for first frame
        self.hover_color = (140, 110, 85)  # Lighter copper brown for hover
        self.frame_background = (100, 70, 55)  # Copper brown film strip background
        self.preview_background = (120, 90, 70)  # Copper brown background for preview area
        self.preview_border = (140, 110, 85)  # Lighter copper brown border for preview
        # Even darker copper brown border for animation frame only
        self.animation_border = (80, 60, 45)

        # Layout cache
        self.frame_layouts: dict[tuple[str, int], pygame.Rect] = {}
        self.animation_layouts: dict[str, pygame.Rect] = {}
        self.sprocket_layouts: list[pygame.Rect] = []
        self.preview_rects: dict[str, pygame.Rect] = {}  # Individual previews for each animation

        # Animation timing for previews
        self.preview_animation_times: dict[str, float] = {}  # Current time for each animation

        self.preview_animation_speeds: dict[str, float] = {}  # Speed multiplier for each animation
        self.preview_frame_durations: dict[str, list[float]] = {}  # Frame durations

        # Initialize film tabs for frame insertion
        self.film_tabs = []  # List of FilmTabWidget instances
        self.tab_width = 11  # Width of each tab (increased by 2, 1 pixel on each side)
        self.tab_height = 30  # Height of each tab

        # Frame spacing constants
        self.inter_frame_gap = 0  # Gap between frames (reduced by 2 pixels)

        # Animation change detection threshold
        self.ANIMATION_CHANGE_THRESHOLD = 0.001

        # Copy/paste buffer for frames
        self._copied_frame = None  # Temporary storage for copied frame

    def set_animated_sprite(self, animated_sprite: AnimatedSprite) -> None:
        """Set the animated sprite to display."""
        LOG.debug(f"FilmStripWidget: set_animated_sprite called with sprite: {animated_sprite}")
        LOG.debug(f"FilmStripWidget: Sprite has {len(animated_sprite._animations)} animations: "
                  f"{list(animated_sprite._animations.keys())}")

        self.animated_sprite = animated_sprite

        # Clear any stale animation state from previous sprites
        self.preview_animation_times.clear()
        self.preview_animation_speeds.clear()
        self.preview_frame_durations.clear()

        # Use sprite introspection to find the first animation
        if animated_sprite._animations:
            if hasattr(animated_sprite, "_animation_order") and animated_sprite._animation_order:
                # Use the first animation in the file order
                self.current_animation = animated_sprite._animation_order[0]
                LOG.debug(f"FilmStripWidget: Using first animation from _animation_order: "
                          f"{self.current_animation}")
            else:
                # Fall back to the first key in _animations
                self.current_animation = next(iter(animated_sprite._animations.keys()))
                LOG.debug(f"FilmStripWidget: Using first animation from _animations: "
                          f"{self.current_animation}")

            # Configure the animated sprite to loop and start playing for preview
            LOG.debug(f"FilmStripWidget: Setting animation to '{self.current_animation}'")
            animated_sprite.set_animation(self.current_animation)
            LOG.debug(f"FilmStripWidget: After set_animation - current_animation: "
                      f"{getattr(animated_sprite, 'current_animation', 'None')}")

            LOG.debug("FilmStripWidget: Setting is_looping to True")
            animated_sprite.is_looping = True  # Enable looping for continuous preview
            LOG.debug(f"FilmStripWidget: After setting is_looping - is_looping: "
                      f"{getattr(animated_sprite, 'is_looping', 'None')}")

            LOG.debug("FilmStripWidget: Calling play()")
            animated_sprite.play()  # Start playing the animation
            LOG.debug(f"FilmStripWidget: After play() - is_playing: "
                      f"{getattr(animated_sprite, 'is_playing', 'None')}")
            LOG.debug(f"FilmStripWidget: After play() - current_frame: "
                      f"{getattr(animated_sprite, 'current_frame', 'None')}")
        else:
            self.current_animation = ""
            LOG.debug(
                "FilmStripWidget: No animations found, setting current_animation to empty string"
            )
        self.current_frame = 0
        self.scroll_offset = 0  # Horizontal scroll offset for rolling effect
        LOG.debug(f"FilmStripWidget: Final state - current_animation: {self.current_animation}, "
                  f"current_frame: {self.current_frame}")

        # Initialize animation timing for previews
        self._initialize_preview_animations()

        # Mark as dirty since we've set up animations to play
        self.mark_dirty()
        LOG.debug("FilmStripWidget: Marked as dirty after setting up animations")
        LOG.debug(f"FilmStripWidget: _force_redraw after mark_dirty: "
                  f"{getattr(self, '_force_redraw', False)}")

        self._calculate_layout()
        self._update_height()

    def _initialize_preview_animations(self) -> None:
        """Initialize animation timing for all previews."""
        LOG.debug("FilmStripWidget: _initialize_preview_animations called")

        if not self.animated_sprite:
            LOG.debug("FilmStripWidget: No animated_sprite in _initialize_preview_animations, "
                      "returning")
            return

        LOG.debug(f"FilmStripWidget: Initializing preview animations for "
                  f"{len(self.animated_sprite._animations)} animations")

        for anim_name, frames in self.animated_sprite._animations.items():
            LOG.debug(f"FilmStripWidget: Initializing animation '{anim_name}' with "
                      f"{len(frames)} frames")
            # Initialize timing for this animation
            # For single-frame animations, start with a small time offset to ensure animation advances
            if len(frames) == 1:
                # Single-frame animations need to start with a small time to ensure they advance
                # Small offset to ensure animation starts
                self.preview_animation_times[anim_name] = 0.001
                LOG.debug("FilmStripWidget: Single-frame animation, setting time to 0.001")
            else:
                self.preview_animation_times[anim_name] = 0.0
                LOG.debug("FilmStripWidget: Multi-frame animation, setting time to 0.0")
            # Normal speed
            self.preview_animation_speeds[anim_name] = 1.0
            LOG.debug(f"FilmStripWidget: Set animation '{anim_name}' speed to 1.0")

            # Extract frame durations
            frame_durations = []
            for i, frame in enumerate(frames):
                if hasattr(frame, "duration"):
                    frame_durations.append(frame.duration)
                    LOG.debug(f"FilmStripWidget: Frame {i} duration: {frame.duration}")
                else:
                    # Default 1 second
                    frame_durations.append(1.0)
                    LOG.debug(f"FilmStripWidget: Frame {i} using default duration: 1.0")
            self.preview_frame_durations[anim_name] = frame_durations
            LOG.debug(f"FilmStripWidget: Animation '{anim_name}' frame durations: "
                      f"{frame_durations}")

        LOG.debug("FilmStripWidget: Preview animation initialization complete")
        LOG.debug(f"FilmStripWidget: Final preview_animation_times: "
                  f"{self.preview_animation_times}")
        LOG.debug(f"FilmStripWidget: Final preview_animation_speeds: "
                  f"{self.preview_animation_speeds}")
        LOG.debug(f"FilmStripWidget: Final preview_frame_durations: "
                  f"{self.preview_frame_durations}")

    def update_animations(self, dt: float) -> None:
        """Update animation timing for all previews.

        This is the core method that drives the film strip preview animations.
        It advances animation timing independently for each animation, allowing
        multiple film strips to show different animations at different speeds.

        DEBUGGING NOTES:
        - If animations don't advance, check that dt > 0 and is reasonable (0.016 = 60fps)
        - If animations are choppy, verify that this method is called every frame
        - If animations loop incorrectly, check preview_animation_times calculation
        - If animations don't start, verify animated_sprite is set and has animations
        """
        if not self.animated_sprite:
            return

        # Track total time for debugging
        if not hasattr(self, "_debug_start_time"):
            self._debug_start_time = 0.0
        if not hasattr(self, "_debug_last_dump_time"):
            self._debug_last_dump_time = 0.0

        self._debug_start_time += dt

        # Debug dump every 5 seconds
        if self._debug_start_time - self._debug_last_dump_time >= self.DEBUG_DUMP_INTERVAL:
            LOG.debug("=" * 80)
            LOG.debug(f"FILM STRIP ANIMATION STATE DUMP AT {self._debug_start_time:.1f} SECONDS")
            LOG.debug("=" * 80)
            LOG.debug("FilmStripWidget debug info:")
            LOG.debug(f"  _debug_start_time: {self._debug_start_time}")
            LOG.debug(f"  dt: {dt}")
            LOG.debug(f"  animated_sprite: {self.animated_sprite}")
            LOG.debug(f"  current_animation: {self.current_animation}")
            LOG.debug(f"  current_frame: {self.current_frame}")
            LOG.debug(f"  scroll_offset: {self.scroll_offset}")
            LOG.debug(f"  _force_redraw: {getattr(self, '_force_redraw', False)}")
            LOG.debug(f"  preview_animation_times: {getattr(self, 'preview_animation_times', {})}")
            LOG.debug(f"  preview_animation_speeds: {getattr(self, 'preview_animation_speeds', {})}")
            LOG.debug(f"  preview_frame_durations: {getattr(self, 'preview_frame_durations', {})}")

            if self.animated_sprite:
                LOG.debug("AnimatedSprite debug info:")
                LOG.debug(f"  current_animation: {getattr(self.animated_sprite, 'current_animation', 'None')}")
                LOG.debug(f"  current_frame: {getattr(self.animated_sprite, 'current_frame', 'None')}")
                LOG.debug(f"  is_playing: {getattr(self.animated_sprite, 'is_playing', 'None')}")
                LOG.debug(f"  is_looping: {getattr(self.animated_sprite, 'is_looping', 'None')}")
                LOG.debug(f"  _is_playing: {getattr(self.animated_sprite, '_is_playing', 'None')}")
                LOG.debug(f"  _is_looping: {getattr(self.animated_sprite, '_is_looping', 'None')}")
                LOG.debug(f"  _frame_timer: {getattr(self.animated_sprite, '_frame_timer', 'None')}")
                LOG.debug(f"  _animations: {getattr(self.animated_sprite, '_animations', {})}")
                LOG.debug(f"  _animation_order: {getattr(self.animated_sprite, '_animation_order', [])}")
                LOG.debug(f"  frame_manager.current_animation: {getattr(self.animated_sprite.frame_manager, 'current_animation', 'None')}")
                LOG.debug(f"  frame_manager.current_frame: {getattr(self.animated_sprite.frame_manager, 'current_frame', 'None')}")

                # Dump animation details
                if hasattr(self.animated_sprite, "_animations") and self.animated_sprite._animations:
                    for anim_name, frames in self.animated_sprite._animations.items():
                        LOG.debug(f"  Animation '{anim_name}':")
                        LOG.debug(f"    frame count: {len(frames)}")
                        for i, frame in enumerate(frames):
                            LOG.debug(f"    frame {i}: duration={getattr(frame, 'duration', 'None')}, image={getattr(frame, 'image', 'None')}")

                # Dump frame manager state
                if hasattr(self.animated_sprite, "frame_manager"):
                    fm = self.animated_sprite.frame_manager
                    LOG.debug("  FrameManager debug info:")
                    LOG.debug(f"    _current_animation: {getattr(fm, '_current_animation', 'None')}")
                    LOG.debug(f"    _current_frame: {getattr(fm, '_current_frame', 'None')}")
                    LOG.debug(f"    _observers: {getattr(fm, '_observers', [])}")

            LOG.debug("=" * 80)

            # Update last dump time for next 5-second interval
            self._debug_last_dump_time = self._debug_start_time

        # Update the animated sprite with delta time to advance frames
        # This is the main animation advancement - it updates the sprite's internal
        # frame timing and current_frame property based on elapsed time
        self.animated_sprite.update(dt)

        # CRITICAL FIX: Sync the widget's current_frame with the sprite's current_frame
        # This was the missing piece - the widget wasn't tracking the animation progress!
        self.current_frame = self.animated_sprite.current_frame

        # Always mark as dirty when animations are running to ensure continuous updates
        # This ensures the film strip redraws even when animations are smoothly transitioning
        # CRITICAL: Without this, the film strip won't redraw when frames advance
        has_animations = len(self.animated_sprite._animations) > 0
        if has_animations:
            self.mark_dirty()

        # Update independent timing for each animation preview
        # This allows each film strip to have its own animation timing, independent
        # of the main canvas animation or other film strips
        for anim_name in self.animated_sprite._animations:
            if anim_name in self.preview_animation_times:
                # Update animation time based on delta time and animation speed
                # This creates smooth, frame-rate independent animation timing
                speed = self.preview_animation_speeds[anim_name]
                self.preview_animation_times[anim_name] += dt * speed

                # Get total duration of this animation
                # This is the sum of all frame durations in the animation
                total_duration = sum(self.preview_frame_durations.get(anim_name, [1.0]))

                # Loop animation time continuously (no pause)
                # This ensures animations loop seamlessly without gaps
                if total_duration > 0:
                    self.preview_animation_times[anim_name] %= total_duration

    def get_current_preview_frame(self, anim_name: str) -> int:
        """Get the current frame index for a preview animation.

        This method calculates which frame should be displayed based on the
        current animation time. It's used by the rendering system to show
        the correct frame in the film strip preview.

        DEBUGGING NOTES:
        - If wrong frames are shown, check that preview_animation_times is advancing
        - If frames don't change, verify update_animations() is being called
        - If animations skip frames, check frame_durations are correct
        - If animations don't loop, verify total_duration calculation
        """
        if (
            anim_name not in self.preview_animation_times
            or anim_name not in self.preview_frame_durations
        ):
            return 0

        current_time = self.preview_animation_times[anim_name]
        frame_durations = self.preview_frame_durations[anim_name]

        # CRITICAL: Add bounds checking to prevent invalid frame indices
        if not frame_durations or len(frame_durations) == 0:
            LOG.error(f"FilmStripWidget: CRITICAL - No frame durations for animation '{anim_name}'")
            return 0

        # Find which frame we should be showing during animation
        # This implements frame-based animation timing where each frame
        # has a specific duration, and we find which frame corresponds
        # to the current animation time
        accumulated_time = 0.0
        for frame_idx, duration in enumerate(frame_durations):
            if current_time <= accumulated_time + duration:
                # Ensure the frame index is within bounds
                if frame_idx >= len(frame_durations):
                    LOG.error(f"FilmStripWidget: CRITICAL - Frame index {frame_idx} out of bounds for {len(frame_durations)} frames")
                    return max(0, len(frame_durations) - 1)
                return frame_idx
            accumulated_time += duration

        # Fallback to last frame
        # This should rarely happen due to the modulo operation in update_animations
        return max(0, len(frame_durations) - 1)

    @staticmethod
    def _get_frame_image(frame) -> pygame.Surface:
        """Get the image surface for a frame."""
        # First, try to get the normal image property
        # This works for loaded frames that have _image set
        try:
            if hasattr(frame, "image"):
                frame_img = frame.image
                if frame_img is not None:
                    # If image is not marked as stale, use it directly
                    if not (hasattr(frame, "_image_stale") and frame._image_stale):
                        return frame_img
                    # If image is stale, we need to rebuild from pixels
                    # But only if pixels exists and is populated
                    if hasattr(frame, "pixels") and frame.pixels and len(frame.pixels) > 0:
                        # Rebuild from pixels during drag
                        try:
                            width, height = frame_img.get_size()
                            frame_surface = pygame.Surface((width, height), pygame.SRCALPHA)
                            for i, color in enumerate(frame.pixels):
                                if i < width * height:
                                    x = i % width
                                    y = i // width
                                    frame_surface.set_at((x, y), color)
                            return frame_surface
                        except (AttributeError, TypeError, pygame.error):
                            # If rebuilding fails, fall back to original image
                            return frame_img
                    else:
                        # Image is marked stale but no pixels available - use image anyway
                        return frame_img
        except (AttributeError, TypeError):
            pass

        # Fallback: Create a surface from the frame's pixel data
        # This handles frames that don't have image set but have pixel data
        try:
            if hasattr(frame, "get_pixel_data"):
                pixel_data = frame.get_pixel_data()
                if pixel_data:
                    # Try to get dimensions safely
                    try:
                        width, height = frame.get_size()
                    except (AttributeError, TypeError):
                        # If get_size() fails, try _image directly
                        if hasattr(frame, "_image") and frame._image:
                            width, height = frame._image.get_size()
                        else:
                            return None
                    
                    # Create a surface with alpha support from the pixel data
                    frame_surface = pygame.Surface((width, height), pygame.SRCALPHA)
                    for i, color in enumerate(pixel_data):
                        if i < width * height:
                            x = i % width
                            y = i // width
                            frame_surface.set_at((x, y), color)
                    return frame_surface
        except (AttributeError, TypeError, pygame.error):
            pass

        return None

    def update_layout(self) -> None:
        """Update the layout of frames and sprockets."""
        self._calculate_layout()

        # Create film tabs after layout is calculated
        self._create_film_tabs()

        # Mark the parent film strip sprite as dirty if it exists
        if (
            hasattr(self, "parent_canvas")
            and self.parent_canvas
            and hasattr(self.parent_canvas, "film_strip_sprite")
        ):
            self.parent_canvas.film_strip_sprite.dirty = 1

    def set_parent_canvas(self, canvas):
        """Set the parent canvas for getting current canvas data."""
        self.parent_canvas = canvas

    def mark_dirty(self):
        """Mark the film strip widget as needing a re-render."""
        # Force a complete re-render by clearing any cached data
        # This ensures that frame thumbnails and preview are updated
        self._force_redraw = True

        # Propagate dirty flags through sprite groups
        if hasattr(self, "film_strip_sprite") and self.film_strip_sprite:
            film_strip_sprite = self.film_strip_sprite
            self._propagate_dirty_to_sprite_groups(film_strip_sprite)

            # Mark the film strip sprite itself as dirty
            film_strip_sprite.dirty = 2

            # Note: Not propagating dirty up the parent chain to avoid circular dirty propagation

    def _propagate_dirty_to_sprite_groups(self, sprite, visited=None):
        """Propagate dirty flags to all sprites in the sprite's groups."""
        if visited is None:
            visited = set()

        # Prevent infinite recursion by tracking visited sprites
        if sprite in visited:
            return
        visited.add(sprite)

        if hasattr(sprite, "groups"):
            try:
                # Handle both function and list cases
                groups = sprite.groups() if callable(sprite.groups) else sprite.groups
                if groups:
                    for group in groups:
                        for other_sprite in group:
                            if other_sprite != sprite:  # Don't dirty ourselves
                                other_sprite.dirty = 1
                                # Recursively propagate to other sprite's groups with visited set
                                self._propagate_dirty_to_sprite_groups(other_sprite, visited)
            except (TypeError, AttributeError):
                # If groups is not iterable or doesn't exist, skip propagation
                pass

    def _propagate_dirty_up_parent_chain(self, parent):
        """Propagate dirty flags up the parent chain until parent=None or parent=parent."""
        if parent is None:
            return

        # Mark parent as dirty
        if hasattr(parent, "dirty"):
            parent.dirty = 1

        # If parent has a parent and it's not the same object (avoid infinite loops)
        if hasattr(parent, "parent") and parent.parent is not None and parent.parent != parent:
            self._propagate_dirty_up_parent_chain(parent.parent)

    def _calculate_scroll_offset(self, frame_index: int, frames: list) -> int:
        """Calculate the scroll offset to center a frame.

        Returns the scroll offset that centers the specified frame.
        """
        frame_width = self.frame_width + self.frame_spacing
        selected_frame_x = frame_index * frame_width
        visible_center = self.rect.width // 2
        target_scroll = selected_frame_x - visible_center + (self.frame_width // 2)
        max_scroll = max(0, len(frames) * frame_width - self.rect.width)
        return max(0, min(target_scroll, max_scroll))

    def update_scroll_for_frame(self, frame_index: int) -> None:
        """Update scroll offset to keep the selected frame visible and centered."""
        if (
            not self.animated_sprite
            or self.current_animation not in self.animated_sprite._animations
        ):
            return

        frames = self.animated_sprite._animations[self.current_animation]
        if frame_index >= len(frames):
            return

        # Calculate which 4-frame window should be shown
        frames_per_view = self.FRAMES_PER_VIEW
        current_start_frame = self.scroll_offset // (self.frame_width + self.tab_width + 2)
        current_end_frame = min(current_start_frame + frames_per_view, len(frames))

        # Check if the selected frame is in the current view
        if current_start_frame <= frame_index < current_end_frame:
            # Frame is already visible, no need to scroll
            return

        # Frame is off-screen, calculate new window
        if frame_index < current_start_frame:
            # Frame is to the left, shift left by 1 frame
            new_start_frame = max(0, frame_index)
        else:
            # Frame is to the right, shift right by 1 frame
            new_start_frame = min(frame_index - frames_per_view + 1, len(frames) - frames_per_view)
            new_start_frame = max(0, new_start_frame)

        # Update scroll offset to show the new window
        self.scroll_offset = new_start_frame * (self.frame_width + self.tab_width + 2)

        LOG.debug(f"FilmStripWidget: Scrolling to show frame {frame_index}, new window: {new_start_frame}-{new_start_frame + frames_per_view - 1}")

        # Recalculate layout with new scroll offset
        self._calculate_layout()
        self._update_height()
        self.mark_dirty()

    def copy_current_frame(self) -> bool:
        """Copy the currently selected frame to the clipboard.

        Returns:
            True if copy was successful, False otherwise

        """
        LOG.debug("FilmStripWidget: [FILM STRIP COPY] copy_current_frame called")
        LOG.debug(f"FilmStripWidget: [FILM STRIP COPY] animated_sprite: {self.animated_sprite}")
        LOG.debug(f"FilmStripWidget: [FILM STRIP COPY] current_animation: {self.current_animation}")
        LOG.debug(f"FilmStripWidget: [FILM STRIP COPY] current_frame: {self.current_frame}")

        if not self.animated_sprite or not self.current_animation:
            LOG.debug("FilmStripWidget: [FILM STRIP COPY] No animation selected for copying")
            return False

        if self.current_animation not in self.animated_sprite._animations:
            LOG.debug(f"FilmStripWidget: [FILM STRIP COPY] Animation '{self.current_animation}' not found")
            return False

        frames = self.animated_sprite._animations[self.current_animation]
        LOG.debug(
            f"FilmStripWidget: [FILM STRIP COPY] Animation has {len(frames)} frames"
        )
        if self.current_frame >= len(frames):
            LOG.debug(
            f"FilmStripWidget: [FILM STRIP COPY] Frame {self.current_frame} "
            f"out of range (max: {len(frames) - 1})"
        )
            return False

        # Get the current frame
        current_frame = frames[self.current_frame]
        LOG.debug(
            f"FilmStripWidget: [FILM STRIP COPY] Got frame object: {current_frame}"
        )

        # Create a deep copy of the frame data
        self._copied_frame = deepcopy(current_frame)
        LOG.debug(
            "FilmStripWidget: [FILM STRIP COPY] Created deep copy, stored in _copied_frame"
        )

        LOG.debug(
            f"FilmStripWidget: [FILM STRIP COPY] Successfully copied frame "
            f"{self.current_frame} from animation '{self.current_animation}'"
        )
        return True

    def paste_to_current_frame(self) -> bool:
        """Paste the copied frame to the currently selected frame.

        Returns:
            True if paste was successful, False otherwise

        """
        LOG.debug("FilmStripWidget: [FILM STRIP PASTE] paste_to_current_frame called")
        LOG.debug(f"FilmStripWidget: [FILM STRIP PASTE] _copied_frame: {self._copied_frame}")
        LOG.debug(f"FilmStripWidget: [FILM STRIP PASTE] animated_sprite: {self.animated_sprite}")
        LOG.debug(f"FilmStripWidget: [FILM STRIP PASTE] current_animation: {self.current_animation}")
        LOG.debug(f"FilmStripWidget: [FILM STRIP PASTE] current_frame: {self.current_frame}")

        if not self._copied_frame:
            LOG.debug("FilmStripWidget: [FILM STRIP PASTE] No frame in clipboard to paste")
            return False

        if not self.animated_sprite or not self.current_animation:
            LOG.debug("FilmStripWidget: [FILM STRIP PASTE] No animation selected for pasting")
            return False

        if self.current_animation not in self.animated_sprite._animations:
            LOG.debug(
            f"FilmStripWidget: [FILM STRIP PASTE] Animation '{self.current_animation}' not found"
        )
            return False

        frames = self.animated_sprite._animations[self.current_animation]
        LOG.debug(
            f"FilmStripWidget: [FILM STRIP PASTE] Animation has {len(frames)} frames"
        )
        if self.current_frame >= len(frames):
            LOG.debug(
                f"FilmStripWidget: [FILM STRIP PASTE] Frame {self.current_frame} "
                f"out of range (max: {len(frames) - 1})"
            )
            return False

        LOG.debug(
            f"FilmStripWidget: [FILM STRIP PASTE] Replacing frame {self.current_frame} "
            f"with copied frame"
        )
        # Replace the current frame with the copied frame
        frames[self.current_frame] = deepcopy(self._copied_frame)
        LOG.debug("FilmStripWidget: [FILM STRIP PASTE] Frame replacement completed")

        LOG.debug(
            f"FilmStripWidget: [FILM STRIP PASTE] Successfully pasted frame to "
            f"frame {self.current_frame} in animation '{self.current_animation}'"
        )

        # Mark as dirty to trigger redraw
        self.mark_dirty()
        LOG.debug("FilmStripWidget: [FILM STRIP PASTE] Marked as dirty")

        # Notify parent scene if available
        if hasattr(self, "parent_scene") and self.parent_scene:
            LOG.debug("FilmStripWidget: [FILM STRIP PASTE] Notifying parent scene")
            if hasattr(self.parent_scene, "_on_frame_pasted"):
                self.parent_scene._on_frame_pasted(self.current_animation, self.current_frame)
        else:
            LOG.debug("FilmStripWidget: [FILM STRIP PASTE] No parent scene to notify")

        return True

    def _update_height(self) -> None:
        """Update the film strip height based on the number of animations (up to 5 rows max)."""
        if not self.animated_sprite:
            return

        # Calculate required height based on number of animations
        num_animations = len(self.animated_sprite._animations)
        max_animations = 5  # Maximum 5 rows

        # Limit to maximum 5 animations
        visible_animations = min(num_animations, max_animations)

        # Calculate height: (label_height + frame_height + spacing) * num_animations + padding
        required_height = (
            self.animation_label_height + self.frame_height + 20
        ) * visible_animations + 20  # Increased by 20 pixels

        # Update the rect height
        self.rect.height = required_height

        # Update the parent film strip sprite height if it exists
        if (
            hasattr(self, "parent_canvas")
            and self.parent_canvas
            and hasattr(self.parent_canvas, "film_strip_sprite")
        ):
            self.parent_canvas.film_strip_sprite.rect.height = required_height
            # Also update the surface size
            self.parent_canvas.film_strip_sprite.image = pygame.Surface((
                self.parent_canvas.film_strip_sprite.rect.width,
                required_height,
            ), pygame.SRCALPHA)
            self.parent_canvas.film_strip_sprite.dirty = 1

    def _calculate_layout(self) -> None:
        """Calculate the layout of frames and sprockets."""
        if not self.animated_sprite:
            return

        self._clear_layouts()
        self._calculate_animation_layouts()
        self._calculate_frame_layouts()
        self._calculate_preview_layouts()
        self._calculate_sprocket_layouts()

    def _clear_layouts(self) -> None:
        """Clear all layout caches."""
        self.frame_layouts.clear()
        self.animation_layouts.clear()
        self.sprocket_layouts.clear()
        self.preview_rects.clear()

    def _calculate_animation_layouts(self) -> None:
        """Calculate layout for animation labels."""
        if not self.animated_sprite:
            return

        available_width = self.rect.width - self.preview_width - self.preview_padding
        # Add top margin for delete button
        top_margin = 20  # Space for the [-] delete button at the top
        y_offset = top_margin - 3  # Move labels up 3 pixels to keep them visible

        # Calculate the center position between sprocket groups
        # Left group ends at x=61, right group starts at preview_start_x + 10
        preview_start_x = available_width + self.preview_padding
        left_group_end = 61
        right_group_start = preview_start_x + 10
        center_x = (left_group_end + right_group_start) // 2

        # Calculate label width dynamically for each animation
        for anim_name in self.animated_sprite._animations:
            # Get text width for this animation
            font = FontManager.get_font()
            text_surface = font.render(anim_name, fgcolor=(255, 255, 255), size=12)
            if isinstance(text_surface, tuple):  # freetype returns (surface, rect)
                text_surface, text_rect = text_surface
            else:  # pygame.font returns surface
                text_rect = text_surface.get_rect()

            label_width = text_rect.width + 20  # Add padding
            label_x = center_x - (label_width // 2)  # Center the label

            self.animation_layouts[anim_name] = pygame.Rect(
                label_x, y_offset, label_width, self.animation_label_height
            )
            # Only increment Y offset if there are multiple animations
            # For single animation, all elements should be at the same Y position
            if len(self.animated_sprite._animations) > 1:
                y_offset += self.animation_label_height + self.frame_height + 20

    def _calculate_frame_layouts(self) -> None:
        """Calculate layout for frame positions."""
        if not self.animated_sprite:
            LOG.debug("FilmStripWidget: No animated sprite, skipping frame layout calculation")
            return

        LOG.debug(f"FilmStripWidget: Calculating frame layouts for {len(self.animated_sprite._animations)} animations")

        # CRITICAL: Clear old removal button layouts to prevent stale data
        self.removal_button_layouts = {}

        # Add top margin for delete button
        top_margin = 20  # Space for the [-] delete button at the top
        y_offset = top_margin

        # Calculate sprocket start position to align frames with sprockets
        sprocket_spacing = 17
        total_width = self.rect.width - 20  # Leave 10px margin on each side
        num_sprockets = (total_width // sprocket_spacing) + 1
        sprockets_width = (num_sprockets - 1) * sprocket_spacing
        sprocket_start_x = 10 + (total_width - sprockets_width) // 2

        # Calculate how many frames can fit before overlapping the animation box
        available_width_for_frames = self.rect.width - self.preview_width - self.preview_padding - 20  # Total width minus preview area minus margins
        frame_width_with_spacing = self.frame_width + self.inter_frame_gap  # 64 + 0 = 64 pixels
        max_frames_before_overlap = available_width_for_frames // frame_width_with_spacing
        LOG.debug(f"Max frames before overlapping animation box: {max_frames_before_overlap}")

        for anim_name, frames in self.animated_sprite._animations.items():
            # Show only frames at a time (0-3), with scrolling to navigate
            # Calculate which frames to show based on scroll offset
            frames_per_view = self.FRAMES_PER_VIEW  # Show frames at a time (indices 0, 1, 2, 3)
            start_frame = self.scroll_offset // (self.frame_width + self.tab_width + 2)  # Calculate starting frame based on scroll
            end_frame = min(start_frame + frames_per_view, len(frames))
            frames_to_show = frames[start_frame:end_frame]
            LOG.debug(f"FilmStripWidget: Processing {len(frames_to_show)} frames for animation {anim_name} (frames {start_frame}-{end_frame - 1})")
            for frame_idx, _frame in enumerate(frames_to_show):
                # Adjust frame_idx to be relative to the actual frame position
                actual_frame_idx = start_frame + frame_idx
                # Calculate frame position - frames stay in fixed positions, we just show different frames
                # Use consistent removal button width (11px)
                removal_button_width = 11 if len(frames) > 1 else 0

                if frame_idx == 0:
                    # First frame positioned 2 pixels after the [+] button
                    # [+] button right edge is at: sprocket_start_x - 2 + self.tab_width
                    # First frame starts 2 pixels after that: sprocket_start_x + self.tab_width
                    frame_x = sprocket_start_x + self.tab_width
                else:
                    # Subsequent frames: positioned 11 pixels after the previous frame's [+] button
                    # Need to account for: frame width + [+] button width + 11px gap
                    # Calculate the spacing: frame_width + tab_width + 11
                    frame_spacing = self.frame_width + self.tab_width + 11
                    frame_x = sprocket_start_x + self.tab_width + frame_idx * frame_spacing

                # For single animation, all frames should be at the same Y position
                # Center frames between top and bottom sprockets, moved down 3 pixels
                if len(self.animated_sprite._animations) == 1:
                    # Calculate center between top sprockets (y=7) and bottom sprockets (y=rect.height-15)
                    top_sprocket_y = 7
                    bottom_sprocket_y = self.rect.height - 15
                    center_y = (top_sprocket_y + bottom_sprocket_y) // 2
                    frame_y = center_y - (self.frame_height // 2) + 3  # Center the frame vertically, moved down 3 pixels
                else:
                    frame_y = y_offset + self.animation_label_height + 3  # Moved down 3 pixels
                frame_rect = pygame.Rect(
                    frame_x,
                    frame_y,
                    self.frame_width,
                    self.frame_height,
                )
                LOG.debug(f"FilmStripWidget: Created frame rect for {anim_name}[{actual_frame_idx}] at {frame_rect}")
                self.frame_layouts[anim_name, actual_frame_idx] = frame_rect

                # Add removal button rectangle to the left of each frame (only if not single-frame)
                # Don't create removal buttons for single-frame animations
                # Allow removal buttons for all strips if there are multiple frames
                if len(frames) > 1:
                    # Make removal buttons narrower than insertion tabs
                    removal_button_width = 11  # Narrower than insertion tabs, reduced by 4
                    removal_button_height = 30  # Same as tab_height
                    removal_button_x = frame_x - removal_button_width  # No gap - touching the frame
                    removal_button_y = frame_y + (self.frame_height - removal_button_height) // 2  # Center vertically
                    removal_button_rect = pygame.Rect(
                        removal_button_x,
                        removal_button_y,
                        removal_button_width,
                        removal_button_height,
                    )
                    LOG.debug(f"FilmStripWidget: Created removal button rect for {anim_name}[{actual_frame_idx}] at {removal_button_rect}")
                    # Store removal button rectangles in a separate dictionary
                    if not hasattr(self, "removal_button_layouts"):
                        self.removal_button_layouts = {}
                        LOG.debug("FilmStripWidget: Initialized removal_button_layouts dictionary")
                    self.removal_button_layouts[anim_name, actual_frame_idx] = removal_button_rect
                    LOG.debug(f"FilmStripWidget: Added removal button to layouts: {anim_name}[{actual_frame_idx}]")
                else:
                    LOG.debug(f"FilmStripWidget: Skipping removal button for {anim_name}[{actual_frame_idx}] - only {len(frames)} frame(s)")

            # Only increment Y offset if there are multiple animations
            # For single animation, all frames should be at the same Y position
            if len(self.animated_sprite._animations) > 1:
                y_offset += self.animation_label_height + self.frame_height + 20

    def _calculate_preview_layouts(self) -> None:
        """Calculate layout for preview areas."""
        if not self.animated_sprite:
            return

        # Add top margin for delete button
        top_margin = 20  # Space for the [-] delete button at the top
        y_offset = top_margin
        preview_x = self.rect.width - self.preview_width - 1

        for anim_name in self.animated_sprite._animations:
            # Center the preview between top and bottom sprockets, moved down 3 pixels
            if len(self.animated_sprite._animations) == 1:
                # Calculate center between top sprockets (y=7) and bottom sprockets (y=rect.height-15)
                top_sprocket_y = 7
                bottom_sprocket_y = self.rect.height - 15
                center_y = (top_sprocket_y + bottom_sprocket_y) // 2
                preview_center_y = self.preview_height // 2
                preview_y = center_y - preview_center_y + 3  # Center the preview vertically, moved down 3 pixels
            else:
                # Center the preview vertically with this animation's frames
                frame_visual_start_y = y_offset + self.animation_label_height + 4  # Match per-frame Y position
                frame_visual_height = self.frame_height - 8  # 4px padding top and bottom
                frame_visual_center_y = frame_visual_start_y + frame_visual_height // 2
                preview_center_y = self.preview_height // 2
                preview_y = frame_visual_center_y - preview_center_y - 2 + 3  # Move up 2 pixels to match per-frame Y, moved down 3 pixels
            # Ensure preview doesn't go above the film strip
            preview_y = max(0, preview_y)
            self.preview_rects[anim_name] = pygame.Rect(
                preview_x, preview_y, self.preview_width, self.preview_height
            )

            # Only increment Y offset if there are multiple animations
            # For single animation, all elements should be at the same Y position
            if len(self.animated_sprite._animations) > 1:
                y_offset += self.animation_label_height + self.frame_height + 20

    def _calculate_sprocket_layouts(self) -> None:
        """Calculate layout for sprocket separators."""
        if not self.animated_sprite:
            return

        x_offset = 0
        # Add top margin for delete button
        top_margin = 20  # Space for the [-] delete button at the top
        y_offset = top_margin
        animation_names = list(self.animated_sprite._animations.keys())

        for anim_name in animation_names:
            # Add sprocket separator (except for last animation)
            if anim_name != animation_names[-1]:
                sprocket_rect = pygame.Rect(
                    x_offset,
                    0,
                    self.sprocket_width,
                    self.frame_height + self.animation_label_height,
                )
                self.sprocket_layouts.append(sprocket_rect)
                x_offset += self.sprocket_width

            # Only increment Y offset if there are multiple animations
            # For single animation, all elements should be at the same Y position
            if len(self.animated_sprite._animations) > 1:
                y_offset += self.animation_label_height + self.frame_height + 20

    def get_frame_at_position(self, pos: tuple[int, int]) -> tuple[str, int] | None:
        """Get the animation and frame at the given position."""
        LOG.debug(f"FilmStripWidget: Checking position {pos} against {len(self.frame_layouts)} frame layouts")
        for (anim_name, frame_idx), frame_rect in self.frame_layouts.items():
            LOG.debug(f"FilmStripWidget: Checking {anim_name}[{frame_idx}] at {frame_rect}")
            if frame_rect.collidepoint(pos):
                LOG.debug(f"FilmStripWidget: Found collision with {anim_name}[{frame_idx}]")
                return (anim_name, frame_idx)
        LOG.debug("FilmStripWidget: No collision found")
        return None

    def get_animation_at_position(self, pos: tuple[int, int]) -> str | None:
        """Get the animation at the given position."""
        for anim_name, anim_rect in self.animation_layouts.items():
            if anim_rect.collidepoint(pos):
                return anim_name
        return None

    def get_preview_at_position(self, pos: tuple[int, int]) -> str | None:
        """Get the preview animation at the given position."""
        for anim_name, preview_rect in self.preview_rects.items():
            if preview_rect.collidepoint(pos):
                return anim_name
        return None

    def set_current_frame(self, animation: str, frame: int) -> None:
        """Set the current animation and selected frame."""
        if (
            self.animated_sprite
            and animation in self.animated_sprite._animations
            and 0 <= frame < len(self.animated_sprite._animations[animation])
        ):
            LOG.debug(f"FilmStripWidget: Setting selected frame to {animation}, {frame}")
            self.current_animation = animation
            self.selected_frame = frame  # Update the selected frame (static thumbnails)
            # Mark as dirty to trigger preview update
            self.mark_dirty()
            LOG.debug(f"FilmStripWidget: Selected frame is now {self.current_animation}, {self.selected_frame}")

            # Notify parent scene about the selection change
            if hasattr(self, "parent_scene") and self.parent_scene:
                self.parent_scene._on_film_strip_frame_selected(self, animation, frame)

    def handle_click(self, pos: tuple[int, int], *, is_right_click: bool = False, is_shift_click: bool = False) -> tuple[str, int] | None:
        """Handle a click on the film strip."""
        LOG.debug(f"FilmStripWidget: handle_click called with position {pos}, right_click={is_right_click}, shift_click={is_shift_click}")
        LOG.debug(f"FilmStripWidget: frame_layouts has {len(self.frame_layouts)} entries")

        # First check if a removal button was clicked
        if self._handle_removal_button_click(pos):
            LOG.debug("FilmStripWidget: Removal button was clicked, not processing frame click")
            return None  # Removal button was clicked, don't process frame click

        # Check if a tab was clicked
        if self._handle_tab_click(pos):
            LOG.debug("FilmStripWidget: Tab was clicked, not processing frame click")
            return None  # Tab was clicked, don't process frame click

        # Check if clicking on a frame
        clicked_frame = self.get_frame_at_position(pos)
        if clicked_frame:
            animation, frame_idx = clicked_frame
            # Use this film strip's animation name instead of the frame's animation name
            # since each film strip represents a specific animation
            strip_animation = next(iter(self.animated_sprite._animations.keys())) if self.animated_sprite and self.animated_sprite._animations else animation
            
            # Handle onion skinning toggle for right-click or shift-click
            if is_right_click or is_shift_click:
                self._toggle_onion_skinning(strip_animation, frame_idx)
                LOG.debug(f"FilmStripWidget: Toggled onion skinning for {strip_animation}[{frame_idx}]")
                return None  # Don't change frame selection for onion skinning toggle
            
            LOG.debug(f"FilmStripWidget: Frame clicked, calling set_current_frame({strip_animation}, {frame_idx})")
            self.set_current_frame(strip_animation, frame_idx)
            return (strip_animation, frame_idx)

        # Check if clicking on an animation label
        clicked_animation = self.get_animation_at_position(pos)
        if clicked_animation and clicked_animation in self.animated_sprite._animations:
            # Use this film strip's animation name instead of the clicked animation name
            # since each film strip represents a specific animation
            strip_animation = next(iter(self.animated_sprite._animations.keys())) if self.animated_sprite and self.animated_sprite._animations else clicked_animation
            # When clicking on an animation strip, use the scene's global selected_frame
            # instead of the strip's own selected_frame
            global_selected_frame = 0
            if hasattr(self, "parent_scene") and self.parent_scene:
                global_selected_frame = getattr(self.parent_scene, "selected_frame", 0)
            LOG.debug(f"FilmStripWidget: Animation clicked, calling set_current_frame({strip_animation}, {global_selected_frame})")
            self.set_current_frame(strip_animation, global_selected_frame)
            return (strip_animation, global_selected_frame)

        # Check if clicking on preview area
        preview_click = self.handle_preview_click(pos)
        if preview_click:
            return preview_click

        # Check if clicking on the parent strip itself (outside of frames, labels, and preview)
        if self.rect.collidepoint(pos):
            # Click is within the film strip widget but not on any specific element
            # This means the user clicked on the parent strip itself
            strip_animation = next(iter(self.animated_sprite._animations.keys())) if self.animated_sprite and self.animated_sprite._animations else ""
            # Use the scene's global selected_frame to maintain consistency
            global_selected_frame = 0
            if hasattr(self, "parent_scene") and self.parent_scene:
                global_selected_frame = getattr(self.parent_scene, "selected_frame", 0)
            LOG.debug(f"FilmStripWidget: Parent strip clicked, selecting strip and calling set_current_frame({strip_animation}, {global_selected_frame})")
            self.set_current_frame(strip_animation, global_selected_frame)
            return (strip_animation, global_selected_frame)

        LOG.debug("FilmStripWidget: No frame or animation clicked")
        return None

    def handle_hover(self, pos: tuple[int, int]) -> None:
        """Handle mouse hover over the film strip."""
        self.hovered_frame = self.get_frame_at_position(pos)
        self.hovered_animation = self.get_animation_at_position(pos)
        
        # Check for removal button hover
        self.hovered_removal_button = self.get_removal_button_at_position(pos)
        
        # Handle tab hover effects
        self._handle_tab_hover(pos)

    def get_removal_button_at_position(self, pos: tuple[int, int]) -> tuple[str, int] | None:
        """Get the removal button at the given position.
        
        Args:
            pos: The position to check (x, y)
            
        Returns:
            Tuple of (animation_name, frame_idx) if a removal button is found, None otherwise
        """
        if not hasattr(self, "removal_button_layouts") or not self.removal_button_layouts:
            return None
            
        for (anim_name, frame_idx), button_rect in self.removal_button_layouts.items():
            if button_rect.collidepoint(pos):
                return (anim_name, frame_idx)
        return None

    def handle_preview_click(self, pos: tuple[int, int]) -> tuple[str, int] | None:
        """Handle mouse click on the preview area (right side). Returns (animation, frame_idx) if click was handled."""
        # Check if click is on the animated preview frame (right side)
        for anim_name, preview_rect in self.preview_rects.items():
            if preview_rect.collidepoint(pos):
                # Cycle background color for all frames in this animation
                self.background_color_index = (self.background_color_index + 1) % len(self.BACKGROUND_COLORS)
                self.background_color = self.BACKGROUND_COLORS[self.background_color_index]
                LOG.debug(f"Film strip background color changed to {self.background_color}")
                # When clicking on preview area, use the scene's global selected_frame
                # instead of the strip's own selected_frame
                global_selected_frame = 0
                if hasattr(self, "parent_scene") and self.parent_scene:
                    global_selected_frame = getattr(self.parent_scene, "selected_frame", 0)
                return (anim_name, global_selected_frame)
        return None

    def render_frame_thumbnail(
        self, frame, *, is_selected: bool = False, is_hovered: bool = False, frame_index: int = 0, animation_name: str = ""
    ) -> pygame.Surface:
        """Render a single frame thumbnail with 3D beveled border."""
        frame_surface = self._create_frame_surface()

        # Fill with cycling background color (with alpha support)
        frame_surface.fill(self.background_color)

        frame_img = self._get_frame_image_for_rendering(frame, is_selected=is_selected)

        if frame_img:
            self._draw_scaled_image(frame_surface, frame_img)
        else:
            self._draw_placeholder(frame_surface)

        # Add 3D beveled border like the right side animation frame
        self._add_3d_beveled_border(frame_surface)

        # Add border for selected frame - use same color as indicator
        selection_color = None
        
        # Check keyboard selection (white indicator)
        if hasattr(self, "parent_scene") and self.parent_scene:
            if (hasattr(self.parent_scene, "selected_animation") and
                hasattr(self.parent_scene, "selected_frame") and
                self.parent_scene.selected_animation == animation_name and
                self.parent_scene.selected_frame == frame_index):
                selection_color = (255, 255, 255)  # White for keyboard
        
        # Check controller selection (use controller's color)
        if not selection_color and hasattr(self, "parent_scene") and self.parent_scene:
            if hasattr(self.parent_scene, "controller_selections"):
                for controller_id, controller_selection in self.parent_scene.controller_selections.items():
                    if controller_selection.is_active():
                        controller_animation, controller_frame = controller_selection.get_selection()
                        if controller_animation == animation_name and controller_frame == frame_index:
                            # Get controller color from multi-controller manager singleton
                            from .multi_controller_manager import MultiControllerManager
                            manager = MultiControllerManager.get_instance()
                            for instance_id, info in manager.controllers.items():
                                if info.controller_id == controller_id:
                                    selection_color = info.color
                                    break
                            break

        # Draw selection border with the appropriate color
        if selection_color:
            pygame.draw.rect(frame_surface, selection_color, (0, 0, self.frame_width, self.frame_height), 3)

        # Draw hover effect
        if is_hovered:
            # Draw a bright blue border for hover effect
            pygame.draw.rect(frame_surface, (0, 255, 255), (0, 0, self.frame_width, self.frame_height), 2)

        # Draw frame number at the bottom center
        self._draw_frame_number(frame_surface, frame_index)
        
        # Draw onion skinning indicator
        self._draw_onion_skinning_indicator(frame_surface, animation_name, frame_index)

        return frame_surface

    def _create_frame_surface(self) -> pygame.Surface:
        """Create the base frame surface with transparent background."""
        # No background fill - transparent so only the 3D beveled border shows
        return pygame.Surface((self.frame_width, self.frame_height), pygame.SRCALPHA)

    def _draw_frame_number(self, surface: pygame.Surface, frame_index: int) -> None:
        """Draw the frame number at the bottom center of the frame."""
        try:
            # Create font for frame number
            font = pygame.font.Font(None, 12)  # Small font size

            # Get total frames for current animation
            total_frames = 1  # Default fallback
            if (hasattr(self, "animated_sprite") and self.animated_sprite and
                hasattr(self, "current_animation") and self.current_animation and
                self.current_animation in self.animated_sprite._animations):
                total_frames = len(self.animated_sprite._animations[self.current_animation])

            # Render frame number text in format "current+1/total"
            frame_text = f"{frame_index + 1}/{total_frames}"
            text_surface = font.render(frame_text, True, (255, 255, 255))  # White text
            text_rect = text_surface.get_rect()

            # Position at bottom center of the frame (like animation preview)
            target_rect = pygame.Rect(0, 0, self.frame_width, self.frame_height)
            text_rect.centerx = target_rect.centerx
            text_rect.bottom = target_rect.bottom - 2  # Small margin from bottom edge

            # Draw text
            surface.blit(text_surface, text_rect)
        except Exception:
            # Log font rendering failures
            LOG.exception("Font rendering failed")

    def _draw_onion_skinning_indicator(self, surface: pygame.Surface, animation_name: str, frame_index: int) -> None:
        """Draw onion skinning indicator on the frame thumbnail."""
        try:
            # Import onion skinning manager
            from .onion_skinning import get_onion_skinning_manager
            
            # Check if this frame has onion skinning enabled
            onion_manager = get_onion_skinning_manager()
            is_onion_skinned = onion_manager.is_frame_onion_skinned(animation_name, frame_index)
            
            if is_onion_skinned:
                # Draw a small semi-transparent overlay in the top-right corner
                overlay_size = 12
                overlay_x = self.frame_width - overlay_size - 2  # 2 pixels from right edge
                overlay_y = 2  # 2 pixels from top edge
                
                # Create semi-transparent surface for overlay
                overlay_surface = pygame.Surface((overlay_size, overlay_size), pygame.SRCALPHA)
                overlay_surface.fill((255, 255, 0, 128))  # Semi-transparent yellow
                
                # Draw a small circle or square to indicate onion skinning
                pygame.draw.circle(overlay_surface, (255, 255, 0, 200), (overlay_size // 2, overlay_size // 2), overlay_size // 2 - 1)
                
                # Blit the overlay to the frame surface
                surface.blit(overlay_surface, (overlay_x, overlay_y))
                
        except Exception:
            # Log onion skinning indicator failures
            LOG.exception("Onion skinning indicator rendering failed")

    def _toggle_onion_skinning(self, animation_name: str, frame_index: int) -> None:
        """Toggle onion skinning for a specific frame."""
        try:
            from .onion_skinning import get_onion_skinning_manager
            
            onion_manager = get_onion_skinning_manager()
            new_state = onion_manager.toggle_frame_onion_skinning(animation_name, frame_index)
            
            LOG.debug(f"Onion skinning toggled for {animation_name}[{frame_index}]: {new_state}")
            
            # Mark the film strip as dirty to trigger a redraw
            self._force_redraw = True
            
            # Force canvas redraw to show onion skinning changes
            if hasattr(self, "parent_scene") and self.parent_scene:
                if hasattr(self.parent_scene, "canvas") and self.parent_scene.canvas:
                    self.parent_scene.canvas.force_redraw()
                    LOG.debug("Forced canvas redraw for onion skinning toggle")
            
        except Exception:
            LOG.exception("Failed to toggle onion skinning")

    def _get_frame_image_for_rendering(self, frame, *, is_selected: bool):
        """Get the appropriate frame image for rendering."""
        # Use the same logic as _get_frame_image which handles stale image flag
        # This ensures film strip sees updated pixels during drag operations
        frame_img = self._get_frame_image(frame)
        if not frame_img:
            LOG.debug("Film strip: No frame data available")

        return frame_img

    def _draw_scaled_image(self, frame_surface: pygame.Surface, frame_img) -> None:
        """Draw a scaled image onto the frame surface."""
        # Calculate scaling to fit within the frame area (leaving some padding)
        max_width = self.frame_width - 8  # Leave 4px padding on each side
        max_height = self.frame_height - 8  # Leave 4px padding on top/bottom

        # Calculate scale factor to fit the image
        scale_x = max_width / frame_img.get_width()
        scale_y = max_height / frame_img.get_height()
        scale = min(scale_x, scale_y)  # Use the smaller scale to fit both dimensions

        # Scale the image
        new_width = int(frame_img.get_width() * scale)
        new_height = int(frame_img.get_height() * scale)
        scaled_image = pygame.transform.scale(frame_img, (new_width, new_height))

        # Center the scaled image within the frame, nudged right by 1 pixel
        x_offset = (self.frame_width - new_width) // 2 + 1
        y_offset = (self.frame_height - new_height) // 2

        # Always convert magenta pixels to transparent, regardless of surface type
        # Create a new surface with alpha support
        rgba_surface = pygame.Surface(scaled_image.get_size(), pygame.SRCALPHA)
        
        # Copy pixels, converting magenta (255, 0, 255) to transparent (alpha = 0)
        for y in range(scaled_image.get_height()):
            for x in range(scaled_image.get_width()):
                color = scaled_image.get_at((x, y))
                if len(color) == 3:  # RGB
                    r, g, b = color
                    if (r, g, b) == (255, 0, 255):  # Magenta - make transparent
                        rgba_surface.set_at((x, y), (255, 0, 255, 0))  # Transparent magenta
                    else:
                        rgba_surface.set_at((x, y), (r, g, b, 255))  # Full opacity other colors
                else:  # Already RGBA
                    r, g, b, a = color
                    if (r, g, b) == (255, 0, 255):  # Magenta - make transparent
                        rgba_surface.set_at((x, y), (255, 0, 255, 0))  # Transparent magenta
                    else:
                        rgba_surface.set_at((x, y), color)  # Keep original color and alpha
        
        frame_surface.blit(rgba_surface, (x_offset, y_offset))

    def _draw_placeholder(self, frame_surface: pygame.Surface) -> None:
        """Draw a placeholder when no frame data is available."""
        # If no frame data, create a placeholder
        placeholder = pygame.Surface((self.frame_width - 8, self.frame_height - 8), pygame.SRCALPHA)
        placeholder.fill((120, 90, 70))  # Copper brown placeholder
        # Center the placeholder
        x_offset = (self.frame_width - placeholder.get_width()) // 2
        y_offset = (self.frame_height - placeholder.get_height()) // 2
        frame_surface.blit(placeholder, (x_offset, y_offset))

    def _add_film_strip_styling(self, frame_surface: pygame.Surface) -> None:
        """Add film strip edges to the frame surface."""
        # Add film strip edges (no sprockets on individual frames)
        pygame.draw.line(frame_surface, self.frame_border, (0, 0), (0, self.frame_height), 1)
        pygame.draw.line(
            frame_surface,
            self.frame_border,
            (self.frame_width - 1, 0),
            (self.frame_width - 1, self.frame_height),
            1,
        )

    def _create_selection_border(self, frame_surface: pygame.Surface) -> pygame.Surface:
        """Create a selection border for the selected frame."""
        # Yellow film leader color for selection
        selection_border = pygame.Surface((self.frame_width + 4, self.frame_height + 4), pygame.SRCALPHA)
        selection_border.fill(self.selection_color)
        # Add film strip perforations to selection border
        for hole_x in range(4, self.frame_width, 8):
            pygame.draw.circle(selection_border, (200, 200, 0), (hole_x, 2), 1)
            pygame.draw.circle(
                selection_border, (200, 200, 0), (hole_x, self.frame_height + 1), 1
            )
        # Blit the frame content onto the selection border (centered)
        selection_border.blit(frame_surface, (2, 2))
        return selection_border

    def _add_hover_highlighting(self, frame_surface: pygame.Surface) -> None:
        """Add hover highlighting to the frame surface."""
        pygame.draw.rect(
            frame_surface, self.hover_color, (0, 0, self.frame_width, self.frame_height), 2
        )

    def _add_3d_beveled_border(self, frame_surface: pygame.Surface) -> None:
        """Add 3D beveled border like the right side animation frame."""
        # Draw the same border as preview, aligned with sprockets
        pygame.draw.rect(frame_surface, self.preview_border, (0, 0, self.frame_width, self.frame_height), 2)

    def render_sprocket_separator(self, x: int, y: int, height: int) -> pygame.Surface:
        """Render a sprocket separator between animations."""
        separator = pygame.Surface((self.sprocket_width, height), pygame.SRCALPHA)
        separator.fill(self.film_background)

        # Draw sprocket holes (perforations)
        hole_spacing = 8
        for hole_y in range(4, height - 4, hole_spacing):
            # Left side holes
            pygame.draw.circle(separator, self.sprocket_color, (6, hole_y), 2)
            # Right side holes
            pygame.draw.circle(separator, self.sprocket_color, (14, hole_y), 2)

        # Draw film strip edges
        pygame.draw.line(separator, self.frame_border, (0, 0), (0, height), 1)
        pygame.draw.line(
            separator,
            self.frame_border,
            (self.sprocket_width - 1, 0),
            (self.sprocket_width - 1, height),
            1,
        )

        return separator

    def render_preview(self, surface: pygame.Surface) -> None:
        """Render individual previews for each animation."""
        if not self.animated_sprite:
            return

        # Render preview for each animation
        for anim_name, preview_rect in self.preview_rects.items():
            # Fill with cycling background color (with alpha support)
            surface.fill(self.background_color, preview_rect)

            # Draw preview border (animation frame only - use darker border)
            pygame.draw.rect(surface, self.animation_border, preview_rect, 2)
            
            # Draw preview hover effect (different color to distinguish from static frames)
            if self.hovered_preview == anim_name:
                # Draw a distinct hover effect for preview area (orange/yellow to distinguish from cyan frames)
                pygame.draw.rect(surface, (255, 165, 0), preview_rect, 3)  # Orange border for preview hover

            # Get the current animated frame for this animation's preview
            if (
                anim_name in self.animated_sprite._animations
                and len(self.animated_sprite._animations[anim_name]) > 0
            ):
                # Get the current frame index based on animation timing
                current_frame_idx = self.get_current_preview_frame(anim_name)

                # CRITICAL: Add bounds checking to prevent index out of range errors
                frames = self.animated_sprite._animations[anim_name]
                if current_frame_idx >= len(frames) or current_frame_idx < 0:
                    LOG.error(f"FilmStripWidget: CRITICAL - Invalid preview frame index {current_frame_idx} for animation '{anim_name}' with {len(frames)} frames")
                    # Reset to frame 0 if invalid
                    current_frame_idx = 0
                    # Also reset the preview animation time to prevent future issues
                    if hasattr(self, "preview_animation_times") and anim_name in self.preview_animation_times:
                        self.preview_animation_times[anim_name] = 0.0

                frame = frames[current_frame_idx]

                # Get the frame image for the current animation frame
                frame_img = self._get_frame_image(frame)

                if frame_img:
                    self._draw_scaled_preview_image(surface, frame_img, preview_rect)
                else:
                    # Draw placeholder if no frame data
                    placeholder_rect = pygame.Rect(
                        preview_rect.x + self.preview_padding,
                        preview_rect.y + self.preview_padding,
                        self.preview_width - (self.preview_padding * 2),
                        self.preview_height - (self.preview_padding * 2),
                    )
                    pygame.draw.rect(surface, (128, 128, 128), placeholder_rect)
                    pygame.draw.rect(surface, (200, 200, 200), placeholder_rect, 1)

            # Draw triangle underneath the animation preview
            self._draw_preview_triangle(surface, preview_rect)

            # Draw current frame index on the animation preview
            self._draw_preview_frame_index(surface, preview_rect, anim_name)

    def _draw_scaled_preview_image(self, surface: pygame.Surface, frame_img: pygame.Surface, preview_rect: pygame.Rect) -> None:
        """Draw a scaled and centered image within a preview area."""
        # Calculate scaling to fit within the preview area
        preview_inner_width = self.preview_width - (self.preview_padding * 2)
        preview_inner_height = self.preview_height - (self.preview_padding * 2)

        # Calculate scale factor
        scale_x = preview_inner_width / frame_img.get_width()
        scale_y = preview_inner_height / frame_img.get_height()
        scale = min(scale_x, scale_y)

        # Scale the image
        new_width = int(frame_img.get_width() * scale)
        new_height = int(frame_img.get_height() * scale)
        scaled_image = pygame.transform.scale(frame_img, (new_width, new_height))

        # Center the scaled image within the preview area
        center_x = preview_rect.x + (self.preview_width - new_width) // 2
        center_y = preview_rect.y + (self.preview_height - new_height) // 2

        # Make magenta (255, 0, 255) transparent for testing
        scaled_image.set_colorkey((255, 0, 255))
        surface.blit(scaled_image, (center_x, center_y))

    def _render_vertical_divider(self, surface: pygame.Surface) -> None:
        """Render a vertical divider between the frames and preview area."""
        if not self.animated_sprite:
            return

        # Calculate divider position - 2 pixels wide, positioned between frames and preview
        divider_x = self.rect.width - self.preview_width - 2 - 4  # 2 pixels before preview area, then 4 pixels left
        divider_y = 0
        divider_width = 2
        divider_height = self.rect.height

        # Draw the divider as a dark copper/bronze line
        divider_rect = pygame.Rect(divider_x, divider_y, divider_width, divider_height)
        pygame.draw.rect(surface, (92, 58, 26), divider_rect)

    def _render_preview_background(self, surface: pygame.Surface) -> None:
        """Render a darker background for the preview area (right of the divider)."""
        if not self.animated_sprite:
            return

        # Calculate preview background area - from divider to end of film strip
        divider_x = self.rect.width - self.preview_width - 2 - 4  # Same as divider position
        preview_bg_x = divider_x + 2  # Start after the divider (2px wide)
        preview_bg_y = 0
        preview_bg_width = self.rect.width - preview_bg_x
        preview_bg_height = self.rect.height

        # Draw darker background - slightly darker than the divider
        preview_bg_rect = pygame.Rect(preview_bg_x, preview_bg_y, preview_bg_width, preview_bg_height)
        pygame.draw.rect(surface, (80, 50, 22), preview_bg_rect)

    def render(self, surface: pygame.Surface) -> None:
        """Render the film strip to the given surface."""
        if not self.animated_sprite:
            return

        # Debug: Track render calls
        if not hasattr(self, "_render_count"):
            self._render_count = 0
        self._render_count += 1

        # Debug: Print render count every 50 renders
        if self._render_count % 50 == 0:
            LOG.debug(f"FilmStripWidget: Render #{self._render_count}, current_frame={self.current_frame}")

        # Clear the film strip area
        surface.fill(self.film_background)
        

        # Check if we need to force a complete redraw
        force_redraw = getattr(self, "_force_redraw", False)
        if force_redraw:
            # Don't reset the flag here - let it persist for frame rendering
            pass

        # Render animation labels
        for anim_name, anim_rect in self.animation_layouts.items():
            # Draw animation label background
            label_surface = pygame.Surface((anim_rect.width, anim_rect.height), pygame.SRCALPHA)
            label_surface.fill(self.film_background)

            # Add animation name text
            font = FontManager.get_font()
            text = font.render(anim_name, fgcolor=(255, 255, 255), size=12)
            if isinstance(text, tuple):  # freetype returns (surface, rect)
                text, text_rect = text
            else:  # pygame.font returns surface
                text_rect = text.get_rect()
            text_rect.center = (anim_rect.width // 2, anim_rect.height // 2 - 5)
            label_surface.blit(text, text_rect)

            # Add hover highlighting
            if self.hovered_animation == anim_name:
                pygame.draw.rect(
                    label_surface, self.hover_color, (0, 0, anim_rect.width, anim_rect.height), 2
                )

            surface.blit(label_surface, anim_rect)

        # Render film tabs for frame insertion (before frames so they appear behind borders)
        for tab in self.film_tabs:
            tab.render(surface)

        # Render frames
        for (anim_name, frame_idx), frame_rect in self.frame_layouts.items():
            if anim_name in self.animated_sprite._animations and frame_idx < len(
                self.animated_sprite._animations[anim_name]
            ):
                frame = self.animated_sprite._animations[anim_name][frame_idx]

                # Determine if this frame is selected or hovered
                is_selected = (
                    anim_name == self.current_animation and frame_idx == self.current_frame
                )
                is_hovered = self.hovered_frame == (anim_name, frame_idx)

                # Render frame thumbnail for ALL frames (not just selected ones)
                frame_thumbnail = self.render_frame_thumbnail(
                    frame, is_selected=is_selected, is_hovered=is_hovered, frame_index=frame_idx, animation_name=anim_name
                )

                # Blit to surface - use consistent positioning for all frames
                surface.blit(frame_thumbnail, frame_rect)

                # Render removal button for this frame
                self._render_removal_button(surface, anim_name, frame_idx)

        # Render sprocket separators
        for sprocket_rect in self.sprocket_layouts:
            sprocket = self.render_sprocket_separator(0, 0, sprocket_rect.height)
            surface.blit(sprocket, sprocket_rect)

        # Render vertical divider between frames and preview
        self._render_vertical_divider(surface)

        # Render darker background for preview area
        self._render_preview_background(surface)

        # Render the animated preview
        self.render_preview(surface)

        # Reset the force redraw flag after all frames have been rendered
        if hasattr(self, "_force_redraw") and self._force_redraw:
            self._force_redraw = False

        # Draw film strip sprockets after everything else
        self._draw_film_sprockets(surface)

        # Draw white border around the entire film strip as the very last thing
        # pygame.draw.rect(surface, (255, 255, 255), self.rect, 2)

        # Draw hover effect for film strip area (when actively hovering over strip)
        # This must be drawn after all other content to appear on top
        if self.is_hovering_strip:
            # Draw a subtle hover effect around the entire film strip
            # Use the surface dimensions, not the rect dimensions
            hover_rect = pygame.Rect(0, 0, surface.get_width(), surface.get_height())
            pygame.draw.rect(surface, (100, 100, 255), hover_rect, 2)

        # Draw multi-controller indicators using new unified system
        self._draw_multi_controller_indicators_new(surface)

    def _draw_multi_controller_indicators_new(self, surface: pygame.Surface) -> None:
        """Draw multi-controller indicators using the controller selections system."""
        
        # Check if this film strip has any selections
        if not self.animated_sprite or not self.current_animation:
            return

        # Get keyboard selection info
        keyboard_animation = ""
        keyboard_frame = -1
        if hasattr(self, "parent_scene") and self.parent_scene:
            if hasattr(self.parent_scene, "selected_animation") and hasattr(self.parent_scene, "selected_frame"):
                keyboard_animation = self.parent_scene.selected_animation
                keyboard_frame = self.parent_scene.selected_frame

        # Get controller selections from the parent scene
        controller_selections = []
        if hasattr(self, "parent_scene") and self.parent_scene:
            if hasattr(self.parent_scene, "film_strip_controller_selections"):
                # Use the pre-filtered controller selections from the parent scene
                controller_selections = self.parent_scene.film_strip_controller_selections.get(self.current_animation, [])
        
        # Draw all indicators using the existing system (collision avoidance handles both keyboard and controllers)
        self._draw_multi_controller_indicators(surface, keyboard_animation, keyboard_frame, controller_selections)

    def _draw_triforce_indicator(self, surface: pygame.Surface) -> None:
        """Draw triangle indicators for keyboard and multi-controller selections."""
        LOG.debug(f"Drawing triforce indicator for animation: {self.current_animation}")

        # Check if this film strip has any selections
        if not self.animated_sprite or not self.current_animation:
            LOG.debug("No animated sprite or current animation")
            return

        # Get keyboard selection info
        keyboard_animation = ""
        keyboard_frame = -1
        if hasattr(self, "parent_scene") and self.parent_scene:
            if hasattr(self.parent_scene, "selected_animation") and hasattr(self.parent_scene, "selected_frame"):
                keyboard_animation = self.parent_scene.selected_animation
                keyboard_frame = self.parent_scene.selected_frame
                # Only print if state changed
                if (hasattr(self.parent_scene, '_last_debug_keyboard_animation') and 
                    hasattr(self.parent_scene, '_last_debug_keyboard_frame') and
                    (self.parent_scene._last_debug_keyboard_animation != keyboard_animation or 
                     self.parent_scene._last_debug_keyboard_frame != keyboard_frame)):
                    self.parent_scene._last_debug_keyboard_animation = keyboard_animation
                    self.parent_scene._last_debug_keyboard_frame = keyboard_frame

        # Get multi-controller selections
        controller_selections = []
        if hasattr(self, "parent_scene") and self.parent_scene:
            if hasattr(self.parent_scene, "controller_selections"):
                for controller_id, controller_selection in self.parent_scene.controller_selections.items():
                    if controller_selection.is_active():
                        animation, frame = controller_selection.get_selection()
                        if animation == self.current_animation:
                            # Get controller color
                            controller_info = None
                            for instance_id, info in self.parent_scene.multi_controller_manager.controllers.items():
                                if info.controller_id == controller_id:
                                    controller_info = info
                                    break
                            
                            if controller_info:
                                controller_selections.append({
                                    'controller_id': controller_id,
                                    'frame': frame,
                                    'color': controller_info.color
                                })

        # Draw all indicators
        self._draw_multi_controller_indicators(surface, keyboard_animation, keyboard_frame, controller_selections)

    def _draw_multi_controller_indicators(self, surface: pygame.Surface, keyboard_animation: str, 
                                        keyboard_frame: int, controller_selections: list) -> None:
        """Draw indicators for keyboard and multiple controllers with collision avoidance."""
        
        # Collect all selections for this animation
        all_selections = []
        
        # Add keyboard selection
        if keyboard_animation == self.current_animation:
            all_selections.append({
                'type': 'keyboard',
                'frame': keyboard_frame,
                'color': (255, 255, 255),  # White for keyboard (distinct from controllers)
                'priority': 0  # Keyboard has highest priority
            })
        
        # Add controller selections
        for controller_selection in controller_selections:
            # Calculate color-based priority (Red=0, Green=1, Blue=2, Yellow=3)
            color = controller_selection['color']
            if color == (255, 0, 0):    # Red
                priority = 0
            elif color == (0, 255, 0):  # Green
                priority = 1
            elif color == (0, 0, 255):  # Blue
                priority = 2
            elif color == (255, 255, 0): # Yellow
                priority = 3
            else:
                priority = 999  # Unknown colors go last
            
            all_selections.append({
                'type': f'controller_{controller_selection["controller_id"]}',
                'frame': controller_selection['frame'],
                'color': controller_selection['color'],
                'priority': priority
            })
        
        # Group selections by frame
        frame_groups = {}
        for selection in all_selections:
            frame = selection['frame']
            if frame not in frame_groups:
                frame_groups[frame] = []
            frame_groups[frame].append(selection)
        
        # Draw indicators for each frame group
        for frame, selections in frame_groups.items():
            frame_key = (self.current_animation, frame)
            if frame_key in self.frame_layouts:
                frame_rect = self.frame_layouts[frame_key]
                self._draw_frame_indicators(surface, frame_rect, selections)

    def _draw_frame_indicators(self, surface: pygame.Surface, frame_rect: pygame.Rect, selections: list) -> None:
        """Draw indicators for a specific frame with collision avoidance."""
        
        # Unified positioning for all scenarios
        self._draw_unified_indicators(surface, frame_rect, selections)

    def _draw_unified_indicators(self, surface: pygame.Surface, frame_rect: pygame.Rect, selections: list) -> None:
        """Unified positioning for all scenarios with proper centering."""
        
        # Separate keyboard from controllers
        keyboard_selection = None
        controller_selections = []
        
        for selection in selections:
            if selection['color'] == (255, 255, 255):  # White = keyboard
                keyboard_selection = selection
            else:
                controller_selections.append(selection)
        
        # Sort controllers by color order (Red, Green, Blue, Yellow)
        def get_color_priority(selection):
            color = selection['color']
            if color == (255, 0, 0):    # Red
                return 0
            elif color == (0, 255, 0):  # Green
                return 1
            elif color == (0, 0, 255):  # Blue
                return 2
            elif color == (255, 255, 0): # Yellow
                return 3
            else:
                return 999  # Unknown colors go last
        
        controller_selections.sort(key=get_color_priority)
        
        # Calculate total number of indicators
        total_indicators = len(controller_selections) + (1 if keyboard_selection else 0)
        
        if total_indicators == 0:
            return  # Nothing to draw
        
        # Define spacing between indicators (in pixels)
        indicator_spacing = 8  # 8 pixels between triangle centers
        
        # Calculate total width needed for all indicators
        total_width = (total_indicators - 1) * indicator_spacing
        
        # Calculate starting position to center the group
        start_x = frame_rect.centerx - (total_width // 2)
        
        # Draw indicators with consistent spacing
        current_x = start_x
        y = frame_rect.top - 4
        
        # Always draw keyboard first (if present)
        if keyboard_selection:
            self._draw_triangle(surface, current_x, y, keyboard_selection['color'])
            current_x += indicator_spacing
        
        # Draw controllers in priority order
        for selection in controller_selections:
            self._draw_triangle(surface, current_x, y, selection['color'])
            current_x += indicator_spacing


    def _draw_preview_triangle(self, surface: pygame.Surface, preview_rect: pygame.Rect) -> None:
        """Draw a triangle underneath the animation preview that moves from left to right."""
        # Calculate position below the preview
        preview_bottom_y = preview_rect.bottom

        # Position triangle 4 pixels below the preview
        triangle_y = preview_bottom_y + 4

        # Calculate animation progress for this preview
        anim_name = None
        for name, rect in self.preview_rects.items():
            if rect == preview_rect:
                anim_name = name
                break

        if anim_name and anim_name in self.preview_animation_times:
            # Get animation progress using actual frame timings
            current_time = self.preview_animation_times[anim_name]

            # Get the current frame index and progress within that frame
            current_frame_idx = self.get_current_preview_frame(anim_name)
            frames = self.animated_sprite._animations.get(anim_name, [])

            # Check if there's only one frame - if so, center the triangle and disable animation
            if frames and len(frames) == 1:
                # Single frame: center the triangle and don't animate
                triangle_x = preview_rect.centerx
            elif frames and current_frame_idx < len(frames):
                # Multiple frames: animate the triangle
                # Get the actual frame duration from the sprite frame
                # frame = frames[current_frame_idx]
                # frame_duration = getattr(frame, "duration", 0.5)  # Default to 0.5 if no duration

                # Calculate progress within the current frame (0.0 to 1.0)
                # frame_start_time = sum(self.preview_frame_durations.get(anim_name, [0.5])[:current_frame_idx])
                # frame_elapsed = current_time - frame_start_time

                # Calculate overall animation progress
                total_duration = sum(self.preview_frame_durations.get(anim_name, [0.5]))
                overall_progress = (current_time % total_duration) / total_duration if total_duration > 0 else 0.0

                # Calculate triangle x position from left to right
                triangle_width = preview_rect.width - 4  # Leave 2px margin on each side
                triangle_x = preview_rect.left + 2 + (triangle_width * overall_progress)
            else:
                # Fallback to center if no frame data
                triangle_x = preview_rect.centerx
        else:
            # Default to center if no animation data
            triangle_x = preview_rect.centerx

        # Draw triangle with different color (blue)
        self._draw_triangle_preview(surface, triangle_x, triangle_y)

    def _draw_preview_frame_index(self, surface: pygame.Surface, preview_rect: pygame.Rect, anim_name: str) -> None:
        """Draw the current frame index on the animation preview."""
        try:
            # Get the current frame index for this animation
            current_frame_idx = self.get_current_preview_frame(anim_name)

            # Get total frames for this animation
            total_frames = 1  # Default fallback
            if (hasattr(self, "animated_sprite") and self.animated_sprite and
                anim_name in self.animated_sprite._animations):
                total_frames = len(self.animated_sprite._animations[anim_name])

            # Create font for frame index
            font = pygame.font.Font(None, 14)  # Slightly larger than frame numbers

            # Render frame index text in format "current+1/total"
            frame_text = f"{current_frame_idx + 1}/{total_frames}"
            text_surface = font.render(frame_text, True, (255, 255, 255))  # White text
            text_rect = text_surface.get_rect()

            # Position at bottom center of the preview
            text_x = preview_rect.x + (preview_rect.width - text_rect.width) // 2
            text_y = preview_rect.y + preview_rect.height - text_rect.height - 4  # 4 pixels from bottom

            # Draw text
            surface.blit(text_surface, (text_x, text_y))
        except Exception:
            # Log font rendering failures
            LOG.exception("Font rendering failed")

    def _draw_triangle_preview(self, surface: pygame.Surface, center_x: int, center_y: int) -> None:
        """Draw a triangle for the preview with different color."""
        # Triangle properties
        size = 2  # Same size as frame triangle
        color = (0, 0, 255)  # Blue color
        border_color = (255, 255, 255)  # White border

        # Calculate positions for a simple triangle pointing up
        triangle_points = [
            (center_x, center_y - size),  # Top point
            (center_x - size, center_y + size),  # Bottom left
            (center_x + size, center_y + size)  # Bottom right
        ]

        # Draw filled triangle
        pygame.draw.polygon(surface, color, triangle_points)
        # Draw border
        pygame.draw.polygon(surface, border_color, triangle_points, 1)

    def _draw_triangle(self, surface: pygame.Surface, center_x: int, center_y: int, color: tuple = (255, 0, 0)) -> None:
        """Draw a simple triangle pointing to the given center coordinates."""
        # Triangle properties
        size = 2  # Smaller size
        border_color = color  # Same color as fill

        # Calculate positions for a simple triangle pointing down
        triangle_points = [
            (center_x, center_y + size),  # Bottom point
            (center_x - size, center_y - size),  # Top left
            (center_x + size, center_y - size)  # Top right
        ]

        # Draw filled triangle
        pygame.draw.polygon(surface, color, triangle_points)
        # Draw border
        pygame.draw.polygon(surface, border_color, triangle_points, 1)

    def _draw_film_sprockets(self, surface: pygame.Surface) -> None:
        """Draw film strip sprockets on the main background."""
        sprocket_color = (60, 50, 40)  # Even darker grey-brown color

        # Draw sprockets along the top edge - aligned with bottom sprockets, avoiding label area
        # Calculate the label area to avoid overlapping
        # available_width = self.rect.width - self.preview_width - self.preview_padding

        # Use pre-calculated animation layouts to avoid label area
        label_left = 0
        label_right = 0
        if self.current_animation and self.current_animation in self.animation_layouts:
            # Use the pre-calculated animation layout
            label_rect = self.animation_layouts[self.current_animation]
            label_left = label_rect.left
            label_right = label_rect.right

        # Draw top sprockets aligned with bottom sprockets, avoiding label area
        # Use the same calculation as bottom sprockets to ensure perfect alignment
        sprocket_spacing = 17
        total_width = self.rect.width - 20  # Leave 10px margin on each side

        # Calculate how many sprockets fit and center them (same as bottom)
        num_sprockets = (total_width // sprocket_spacing) + 3
        if num_sprockets > 0:
            # Calculate the total space the sprockets will occupy
            sprockets_width = (num_sprockets - 1) * sprocket_spacing
            # Center the sprockets within the available space
            start_x = 10 + (total_width - sprockets_width) // 2

            # Draw sprockets across the entire width, skipping label area
            for i in range(num_sprockets):
                x = start_x + (i * sprocket_spacing)
                # Skip the label area
                if x < label_left or x > label_right:
                    # Draw rounded rectangle instead of circle
                    # Add top margin for delete button
                    top_margin = 20  # Space for the [-] delete button at the top
                    rect = pygame.Rect(x - 3, 7 + top_margin - 20, 6, 6)  # 6x6 rectangle centered at (x, 10 + top_margin - 20)
                    pygame.draw.rect(surface, sprocket_color, rect, border_radius=3)

        # Draw two sets of sprockets along the bottom edge - same distance from bottom as top sprockets are from top
        # Top sprockets are at y=7, so bottom sprockets should be at height-7
        bottom_sprocket_y = self.rect.height - 7

        # Calculate how many sprockets we can fit across the full width
        sprocket_spacing = 17
        total_width = self.rect.width - 20  # Leave 10px margin on each side

        # Calculate how many sprockets fit and center them (add three more)
        num_sprockets = (total_width // sprocket_spacing) + 3
        if num_sprockets > 0:
            # Calculate the total space the sprockets will occupy
            sprockets_width = (num_sprockets - 1) * sprocket_spacing
            # Center the sprockets within the available space
            start_x = 10 + (total_width - sprockets_width) // 2

            # Draw bottom sprockets
            for i in range(num_sprockets):
                x = start_x + (i * sprocket_spacing)
                # Skip the label area
                if x < label_left or x > label_right:
                    # Draw rounded rectangle instead of circle
                    rect = pygame.Rect(x - 3, bottom_sprocket_y - 5, 6, 6)  # 6x6 rectangle 5 pixels above first set
                    pygame.draw.rect(surface, sprocket_color, rect, border_radius=3)

    def _calculate_frames_width(self) -> int:
        """Calculate the total width needed for all frames and sprockets."""
        frames_width = 0
        animation_names = list(self.animated_sprite._animations.keys())
        for i, (_, frames) in enumerate(self.animated_sprite._animations.items()):
            frames_width += len(frames) * (self.frame_width + self.frame_spacing)
            # Add sprocket width between animations (not after the last one)
            if i < len(animation_names) - 1:
                frames_width += self.sprocket_width
        return frames_width

    def get_total_width(self) -> int:
        """Get the total width needed for the film strip."""
        if not self.animated_sprite:
            return 0

        frames_width = self._calculate_frames_width()
        # Add individual preview area width and padding
        return frames_width + self.preview_width + self.preview_padding

    def set_frame_index(self, frame_index: int) -> None:
        """Set the current frame and update the canvas."""
        if not self.animated_sprite:
            return

        # Update the current frame
        self.current_frame = frame_index

        # Update scroll to keep the selected frame visible and centered
        self.update_scroll_for_frame(frame_index)

        # Update the parent canvas to show this frame
        if self.parent_canvas and hasattr(self.parent_canvas, "canvas_interface"):
            self.parent_canvas.canvas_interface.set_current_frame(
                self.current_animation, frame_index
            )

    def _find_clicked_frame(self, local_x: int, local_y: int) -> tuple[str, int] | None:
        """Find which frame was clicked at the given coordinates.

        Returns (animation, frame) if a frame was clicked, None otherwise.
        """
        for (anim_name, frame_idx), frame_rect in self.frame_layouts.items():
            if frame_rect.collidepoint(local_x, local_y):
                return (anim_name, frame_idx)
        return None

    def handle_frame_click(self, pos: tuple[int, int]) -> tuple[str, int] | None:
        """Handle mouse click on the film strip.

        Returns (animation, frame) if a frame was clicked.
        """
        if not self.animated_sprite:
            return None

        # Coordinates are already local to the film strip widget
        local_x, local_y = pos

        # Check if click is within film strip bounds
        if not (0 <= local_x < self.rect.width and 0 <= local_y < self.rect.height):
            return None

        return self._find_clicked_frame(local_x, local_y)

    def _create_film_tabs(self) -> None:
        """Create film tabs for frame insertion points."""
        self.film_tabs.clear()

        if not self.animated_sprite or not self.animated_sprite._animations:
            return

        # Get the current animation frames
        current_animation = self.current_animation
        if current_animation not in self.animated_sprite._animations:
            return

        frames = self.animated_sprite._animations[current_animation]
        if not frames:
            return

        # Calculate tab positions based on frame layouts
        for frame_idx in range(len(frames)):
            frame_key = (current_animation, frame_idx)
            if frame_key in self.frame_layouts:
                frame_rect = self.frame_layouts[frame_key]

                # Create "before" tab (to the left of the frame) - only for the first frame
                if frame_idx == 0:
                    before_tab = FilmTabWidget(
                        x=-2,  # Move 2px left of film strip border
                        y=frame_rect.y + (frame_rect.height - self.tab_height) // 2,  # Center vertically
                        width=self.tab_width,
                        height=self.tab_height
                    )
                    before_tab.set_insertion_type("before", frame_idx)
                    self.film_tabs.append(before_tab)

                # Create "after" tab (to the right of the frame) - for all frames
                after_tab = FilmTabWidget(
                    x=frame_rect.x + frame_rect.width - 2,  # 2px overlap with frame
                    y=frame_rect.y + (frame_rect.height - self.tab_height) // 2,  # Center vertically
                    width=self.tab_width,
                    height=self.tab_height
                )
                after_tab.set_insertion_type("after", frame_idx)
                self.film_tabs.append(after_tab)
            else:
                continue

        # Add a horizontal top tab (delete) at the center of the film strip
        # Don't create delete button for the first strip (strip_index = 0)
        if frames and getattr(self, 'strip_index', 0) > 0:  # Only add top tab if there are frames and not the first strip
            # Calculate center x position of the film strip
            center_x = self.rect.width // 2
            top_tab = FilmStripDeleteTab(
                x=center_x - 20,  # Center horizontally (40px wide, so 20px offset)
                y=5,  # Position at top of film strip with small margin
                width=40,  # Wider than vertical tabs
                height=10  # Shorter than vertical tabs
            )
            top_tab.set_insertion_type("delete", 0)  # Delete current strip
            self.film_tabs.append(top_tab)

        # Add a horizontal bottom tab (add) at the center of the film strip
        if frames:  # Only add bottom tab if there are frames
            # Calculate center x position of the film strip
            center_x = self.rect.width // 2
            bottom_tab = FilmStripTab(
                x=center_x - 20,  # Center horizontally (40px wide, so 20px offset)
                y=self.rect.height - 13,  # Position 13 pixels from bottom (moved down 2 pixels)
                width=40,  # Wider than vertical tabs
                height=10  # Shorter than vertical tabs (reduced by half)
            )
            bottom_tab.set_insertion_type("after", len(frames) - 1)  # Insert after last frame
            self.film_tabs.append(bottom_tab)

    def _handle_tab_click(self, pos: tuple[int, int]) -> bool:
        """Handle mouse click on film tabs.

        Args:
            pos: Mouse position (x, y)

        Returns:
            True if a tab was clicked, False otherwise

        """
        for tab in self.film_tabs:
            if tab.handle_click(pos):
                # Check if this is a FilmStripTab (horizontal bottom tab)
                if isinstance(tab, FilmStripTab):
                    # Add a new animation (film strip) after the current one
                    if hasattr(self, "parent_scene") and self.parent_scene:
                        # Find the current strip's index in the animation list
                        current_animation = self.current_animation
                        if hasattr(self.parent_scene, "canvas") and self.parent_scene.canvas:
                            animations = list(self.parent_scene.canvas.animated_sprite._animations.keys())
                            try:
                                current_index = animations.index(current_animation)
                                self.parent_scene._add_new_animation(insert_after_index=current_index)
                            except ValueError:
                                # Fallback to end if current animation not found
                                self.parent_scene._add_new_animation()
                        else:
                            self.parent_scene._add_new_animation()
                    return True
                if isinstance(tab, FilmStripDeleteTab):
                    # Delete the current animation (film strip)
                    if hasattr(self, "parent_scene") and self.parent_scene:
                        current_animation = self.current_animation
                        if hasattr(self.parent_scene, "canvas") and self.parent_scene.canvas:
                            # Only delete if there's more than one animation
                            animations = list(self.parent_scene.canvas.animated_sprite._animations.keys())
                            if len(animations) > 1:
                                self.parent_scene._delete_animation(current_animation)
                    return True
                # Regular frame tab - create a new frame at the specified position
                self._insert_frame_at_tab(tab)
                return True
        return False

    def _handle_tab_hover(self, pos: tuple[int, int]) -> bool:
        """Handle mouse hover over film tabs.

        Args:
            pos: Mouse position (x, y)

        Returns:
            True if hovering over a tab, False otherwise

        """
        hovered_any = False
        for tab in self.film_tabs:
            if tab.handle_hover(pos):
                hovered_any = True
        return hovered_any

    def _insert_frame_at_tab(self, tab: "FilmTabWidget") -> None:
        """Insert a new frame at the position specified by the tab.

        Args:
            tab: The film tab that was clicked

        """
        if not self.animated_sprite:
            return

        current_animation = self.current_animation
        if current_animation not in self.animated_sprite._animations:
            return

        # Create a new blank frame with magenta background
        # Get the canvas dimensions from the parent scene
        if not (hasattr(self, "parent_scene") and self.parent_scene and hasattr(self.parent_scene, "canvas")):
            return  # Cannot create frame without parent scene canvas dimensions

        frame_width = self.parent_scene.canvas.pixels_across
        frame_height = self.parent_scene.canvas.pixels_tall

        new_surface = pygame.Surface((frame_width, frame_height), pygame.SRCALPHA)
        new_surface.fill((255, 0, 255))  # Magenta background

        # Create a new SpriteFrame
        new_frame = SpriteFrame(new_surface, duration=0.5)

        # Initialize the pixel data for the new frame
        new_frame.pixels = [(255, 0, 255)] * (frame_width * frame_height)

        # Determine insertion index
        if tab.insertion_type == "before":
            insert_index = tab.target_frame_index
        else:  # "after"
            insert_index = tab.target_frame_index + 1

        # Insert the frame into the animated sprite
        self.animated_sprite.add_frame(current_animation, new_frame, insert_index)

        # Track frame addition for undo/redo
        if (hasattr(self, "parent_scene") and 
            self.parent_scene and 
            hasattr(self.parent_scene, "film_strip_operation_tracker")):
            
            # Create frame data for undo/redo tracking
            frame_data = {
                "width": new_frame.image.get_width(),
                "height": new_frame.image.get_height(),
                "pixels": new_frame.pixels.copy() if hasattr(new_frame, 'pixels') else [],
                "duration": new_frame.duration
            }
            
            self.parent_scene.film_strip_operation_tracker.add_frame_added(
                insert_index, current_animation, frame_data
            )

        # CRITICAL: Reinitialize preview animations after adding a frame
        # This ensures the film strip picks up the new frame count and starts animating
        # if it was previously a single-frame animation
        self._initialize_preview_animations()

        # Notify the parent scene about the frame insertion
        if hasattr(self.parent_scene, "_on_frame_inserted"):
            self.parent_scene._on_frame_inserted(current_animation, insert_index)

        # Select the newly created frame so the user can immediately start editing it
        LOG.debug(f"FilmStripWidget: Selecting newly created frame {insert_index} in animation '{current_animation}'")
        self.set_current_frame(current_animation, insert_index)
        
        # Also update the canvas to show the new frame
        if (hasattr(self, "parent_scene") and self.parent_scene and 
            hasattr(self.parent_scene, "canvas") and self.parent_scene.canvas):
            # Set flag to prevent frame selection tracking during frame creation
            self.parent_scene._creating_frame = True
            try:
                self.parent_scene.canvas.show_frame(current_animation, insert_index)
                LOG.debug(f"FilmStripWidget: Updated canvas to show new frame {insert_index}")
            finally:
                self.parent_scene._creating_frame = False

        # Recalculate layouts to include the new frame
        self.update_layout()

        # Recreate tabs for the new frame layout
        self._create_film_tabs()

        # Mark as dirty to trigger redraw
        self.mark_dirty()

        # Reset debug timer for new frame dump
        if hasattr(self, "_debug_start_time"):
            self._debug_start_time = 0.0
        if hasattr(self, "_debug_last_dump_time"):
            self._debug_last_dump_time = 0.0

    def _handle_removal_button_click(self, pos: tuple[int, int]) -> bool:
        """Handle clicks on removal buttons.

        Args:
            pos: Click position (x, y)

        Returns:
            True if a removal button was clicked, False otherwise

        """
        LOG.debug(f"FilmStripWidget: Checking removal button click at {pos}")
        
        if not hasattr(self, "removal_button_layouts") or not self.removal_button_layouts:
            LOG.debug("FilmStripWidget: No removal button layouts found")
            return False

        LOG.debug(f"FilmStripWidget: Checking {len(self.removal_button_layouts)} removal buttons")
        
        for (anim_name, frame_idx), button_rect in self.removal_button_layouts.items():
            LOG.debug(f"FilmStripWidget: Checking button {anim_name}[{frame_idx}] at {button_rect}")
            if button_rect.collidepoint(pos):
                LOG.debug(f"FilmStripWidget: Click hit removal button for {anim_name}[{frame_idx}]")
                # CRITICAL: Add bounds checking to prevent invalid frame removal
                if (self.animated_sprite and
                    anim_name in self.animated_sprite._animations and
                    frame_idx < len(self.animated_sprite._animations[anim_name])):
                    LOG.debug(f"FilmStripWidget: Removal button clicked for {anim_name}[{frame_idx}]")
                    self._remove_frame(anim_name, frame_idx)
                    return True
                LOG.debug(f"FilmStripWidget: Cannot remove frame - index {frame_idx} out of range")
                return False
        LOG.debug("FilmStripWidget: No removal button was clicked")
        return False

    def _remove_frame(self, animation_name: str, frame_index: int) -> None:
        """Remove a frame from the animated sprite.

        Args:
            animation_name: Name of the animation
            frame_index: Index of the frame to remove

        """
        if not self.animated_sprite or animation_name not in self.animated_sprite._animations:
            LOG.debug(f"FilmStripWidget: Cannot remove frame - animation '{animation_name}' not found")
            return

        frames = self.animated_sprite._animations[animation_name]
        if frame_index < 0 or frame_index >= len(frames):
            LOG.debug(f"FilmStripWidget: Cannot remove frame - index {frame_index} out of range")
            return

        # Don't allow removing the last frame of an animation
        if len(frames) <= 1:
            LOG.debug(f"FilmStripWidget: Cannot remove the last frame of animation '{animation_name}'")
            return

        LOG.debug(f"FilmStripWidget: Removing frame {frame_index} from animation '{animation_name}'")

        # CRITICAL: Stop animation and reset frame index before deletion to prevent race conditions
        if (self.animated_sprite and
            hasattr(self.animated_sprite, "frame_manager") and
            self.animated_sprite.frame_manager.current_animation == animation_name):
            
            # Stop the animation to prevent it from accessing frames during deletion
            self.animated_sprite._is_playing = False
            
            # Adjust the current frame index before deletion
            if self.animated_sprite.frame_manager.current_frame >= frame_index:
                if self.animated_sprite.frame_manager.current_frame > 0:
                    self.animated_sprite.frame_manager.current_frame -= 1
                else:
                    self.animated_sprite.frame_manager.current_frame = 0
            
            LOG.debug(f"FilmStripWidget: Stopped animation and adjusted frame index to {self.animated_sprite.frame_manager.current_frame}")

        # Capture frame data for undo/redo before removing
        frame_data = None
        if (hasattr(self, "parent_scene") and 
            self.parent_scene and 
            hasattr(self.parent_scene, "film_strip_operation_tracker")):
            
            # Get the frame data before deletion
            frame_to_remove = frames[frame_index]
            frame_data = {
                "width": frame_to_remove.image.get_width(),
                "height": frame_to_remove.image.get_height(),
                "pixels": frame_to_remove.pixels.copy() if hasattr(frame_to_remove, 'pixels') else [],
                "duration": frame_to_remove.duration
            }
            
            # Track frame deletion for undo/redo
            self.parent_scene.film_strip_operation_tracker.add_frame_deleted(
                frame_index, animation_name, frame_data
            )

        # Remove the frame
        frames.pop(frame_index)

        # Adjust current frame if necessary and select the previous frame
        if (hasattr(self, "current_animation") and self.current_animation == animation_name and
            hasattr(self, "current_frame") and self.current_frame >= frame_index):
            
            # If we removed a frame before or at the current position, select the previous frame
            if self.current_frame > 0:
                # Select the previous frame
                self.current_frame -= 1
                LOG.debug(f"FilmStripWidget: Selected previous frame {self.current_frame} after deletion")
            else:
                # If we were at frame 0 and removed it, stay at frame 0 (which is now the next frame)
                self.current_frame = 0
                LOG.debug(f"FilmStripWidget: Stayed at frame 0 after deleting frame 0")

        # Ensure the current frame is within bounds after deletion
        if (self.animated_sprite and
            hasattr(self.animated_sprite, "frame_manager") and
            self.animated_sprite.frame_manager.current_animation == animation_name):
            
            remaining_frames = len(frames)
            if remaining_frames > 0:
                if self.animated_sprite.frame_manager.current_frame >= remaining_frames:
                    self.animated_sprite.frame_manager.current_frame = max(0, remaining_frames - 1)
            
            LOG.debug(f"FilmStripWidget: After removal - animated sprite current_frame: {self.animated_sprite.frame_manager.current_frame}, frames count: {len(frames)}")

            # Mark the animated sprite as dirty to ensure it updates properly
            self.animated_sprite.dirty = 2

        # Notify the parent scene about the frame removal
        if hasattr(self.parent_scene, "_on_frame_removed"):
            self.parent_scene._on_frame_removed(animation_name, frame_index)

        # CRITICAL: Reinitialize preview animations after frame removal
        # This ensures the preview animation system is updated with the new frame count
        self._initialize_preview_animations()

        # CRITICAL: Adjust scroll offset to ensure 4 frames are visible after removal
        # Calculate the maximum scroll offset based on remaining frames
        remaining_frames = len(frames)
        if remaining_frames > self.FRAMES_PER_VIEW:
            # Calculate frame spacing for scroll offset adjustment
            max_scroll = max(0, remaining_frames - self.FRAMES_PER_VIEW)
            # Ensure scroll offset doesn't exceed the maximum
            self.scroll_offset = min(self.scroll_offset, max_scroll)
        else:
            # If FRAMES_PER_VIEW or fewer frames remain, reset scroll to show all frames
            self.scroll_offset = 0

        # Recalculate layouts after frame removal
        self.update_layout()

        # Recreate tabs for the new frame layout
        self._create_film_tabs()

        # Mark as dirty to trigger redraw
        self.mark_dirty()

        LOG.debug(f"FilmStripWidget: Frame removed. Animation '{animation_name}' now has {len(frames)} frames")

    def _render_removal_button(self, surface: pygame.Surface, anim_name: str, frame_idx: int) -> None:
        """Render a removal button for a specific frame.

        Args:
            surface: Surface to render on
            anim_name: Animation name
            frame_idx: Frame index

        """
        if not hasattr(self, "removal_button_layouts") or not self.removal_button_layouts:
            LOG.debug(f"FilmStripWidget: No removal button layouts for {anim_name}[{frame_idx}]")
            return

        button_key = (anim_name, frame_idx)
        if button_key not in self.removal_button_layouts:
            LOG.debug(f"FilmStripWidget: No removal button layout for {anim_name}[{frame_idx}]")
            return

        button_rect = self.removal_button_layouts[button_key]

        # Don't render removal button if this is the last frame (can't remove it)
        if (anim_name in self.animated_sprite._animations and
            len(self.animated_sprite._animations[anim_name]) <= 1):
            LOG.debug(f"FilmStripWidget: Skipping removal button for {anim_name}[{frame_idx}] - only one frame")
            return

        LOG.debug(f"FilmStripWidget: Rendering removal button for {anim_name}[{frame_idx}] at {button_rect}")

        # Check if this removal button is being hovered
        is_hovered = (self.hovered_removal_button == (anim_name, frame_idx))
        
        # Use inverted colors when hovered (black to white, white to black)
        if is_hovered:
            tab_color = (0, 0, 0)  # Black background when hovered
            border_color = (255, 255, 255)  # White border when hovered
        else:
            tab_color = (200, 200, 200)  # Light gray - same as insertion tabs
            border_color = (0, 0, 0)  # Black border - same as insertion tabs

        # Draw button background
        pygame.draw.rect(surface, tab_color, button_rect)

        # Draw border
        pygame.draw.rect(surface, border_color, button_rect, 2)

        # Draw minus sign in the center (similar to how insertion tabs draw plus)
        center_x = button_rect.centerx
        center_y = button_rect.centery

        # Draw horizontal bar (3 pixels wide, 1 pixel tall) - use border color for consistency
        pygame.draw.rect(surface, border_color,
                        (center_x - 1, center_y, 3, 1))


class FilmTabWidget:
    """Film tab widget for inserting frames before or after existing frames.

    ARCHITECTURE OVERVIEW:
    This widget provides a small tab interface that can be attached to film strips
    to allow users to insert new frames at specific positions. Each tab represents
    an insertion point and can be clicked to add a new frame.

    KEY COMPONENTS:
    1. Tab Positioning:
       - Tabs are positioned to the left of the film strip
       - Each tab corresponds to an insertion point (before/after frames)
       - Tabs are visually distinct and clickable

    2. Frame Insertion:
       - Clicking a tab creates a new frame at the specified position
       - New frames are inserted into the animated sprite's frame list
       - Film strip layout is recalculated after insertion

    3. Visual Design:
       - Small, unobtrusive tabs that don't interfere with frame display
       - Clear visual indication of insertion points
       - Hover effects for better user experience
    """

    def __init__(self, x: int, y: int, width: int = 20, height: int = 30):
        """Initialize the film tab widget.

        Args:
            x: X position of the tab
            y: Y position of the tab
            width: Width of the tab
            height: Height of the tab

        """
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.rect = pygame.Rect(x, y, width, height)

        # Tab state
        self.is_hovered = False
        self.is_clicked = False

        # Tab properties
        self.tab_color = (200, 200, 200)  # Light gray
        self.hover_color = (255, 255, 255)  # White when hovered
        self.click_color = (100, 100, 100)  # Dark gray when clicked
        self.border_color = (0, 0, 0)  # Black border

        # Insertion properties
        self.insertion_type = "before"  # "before" or "after"
        self.target_frame_index = 0  # Which frame this tab is associated with

    def render(self, surface: pygame.Surface) -> None:
        """Render the film tab to the given surface.

        Args:
            surface: The pygame surface to render to

        """
        # Determine color based on state - invert colors on hover
        if self.is_clicked:
            color = self.click_color
            border_color = self.border_color
        elif self.is_hovered:
            # Invert colors on hover: black background, white border
            color = (0, 0, 0)  # Black background
            border_color = (255, 255, 255)  # White border
        else:
            color = self.tab_color
            border_color = self.border_color

        # Draw tab background
        pygame.draw.rect(surface, color, self.rect)

        # Draw border
        pygame.draw.rect(surface, border_color, self.rect, 2)

        # Draw plus sign in the center
        center_x = self.rect.centerx
        center_y = self.rect.centery

        # Draw horizontal bar (3 pixels wide, 1 pixel tall)
        pygame.draw.rect(surface, border_color,
                        (center_x - 1, center_y, 3, 1))
        # Draw vertical bar (1 pixel wide, 3 pixels tall)
        pygame.draw.rect(surface, border_color,
                        (center_x, center_y - 1, 1, 3))

    def handle_click(self, pos: tuple[int, int]) -> bool:
        """Handle mouse click on the tab.

        Args:
            pos: Mouse position (x, y)

        Returns:
            True if the tab was clicked, False otherwise

        """
        if self.rect.collidepoint(pos):
            self.is_clicked = True
            return True
        return False

    def handle_hover(self, pos: tuple[int, int]) -> bool:
        """Handle mouse hover over the tab.

        Args:
            pos: Mouse position (x, y)

        Returns:
            True if the tab is being hovered, False otherwise

        """
        self.is_hovered = self.rect.collidepoint(pos)
        return self.is_hovered

    def reset_click_state(self) -> None:
        """Reset the clicked state."""
        self.is_clicked = False

    def set_insertion_type(self, insertion_type: str, target_frame_index: int) -> None:
        """Set the insertion type and target frame for this tab.

        Args:
            insertion_type: "before" or "after"
            target_frame_index: The frame index this tab is associated with

        """
        self.insertion_type = insertion_type
        self.target_frame_index = target_frame_index


class FilmStripDeleteTab:
    """Horizontal film tab widget for deleting film strips at the top.

    ARCHITECTURE OVERVIEW:
    This widget provides a horizontal tab interface that appears at the top
    of film strips to allow users to delete film strips. It's wider than it is tall
    and behaves differently from the vertical FilmTabWidget.

    KEY COMPONENTS:
    1. Horizontal Design:
       - Wider than tall for better visual balance at the top
       - Centered horizontally on the film strip
       - Positioned at the top of the film strip

    2. Strip Deletion:
       - Clicking the tab deletes the current film strip
       - Film strip layout is recalculated after deletion
       - User is switched to the next available strip

    3. Visual Design:
       - Horizontal orientation with appropriate proportions
       - Clear visual indication of strip deletion capability
       - Hover effects for better user experience
    """

    def __init__(self, x: int, y: int, width: int = 40, height: int = 10):
        """Initialize a horizontal film delete tab widget.

        Args:
            x: X position of the tab
            y: Y position of the tab
            width: Width of the tab (default 40, wider than vertical tabs)
            height: Height of the tab (default 10, shorter than vertical tabs)

        """
        self.rect = pygame.Rect(x, y, width, height)
        self.is_clicked = False
        self.is_hovered = False

        # Visual properties (matching vertical tabs)
        self.tab_color = (200, 200, 200)  # Light gray
        self.hover_color = (255, 255, 255)  # White
        self.click_color = (100, 100, 100)  # Dark gray
        self.border_color = (0, 0, 0)  # Black border (matching vertical tabs)

        # Tab behavior
        self.insertion_type = "delete"  # Always deletes the current strip
        self.target_frame_index = 0  # Will be set when tab is created

    def render(self, surface: pygame.Surface) -> None:
        """Render the horizontal film delete tab to the surface.

        Args:
            surface: The pygame surface to render to

        """
        # Determine color based on state - invert colors on hover
        if self.is_clicked:
            color = self.click_color
            border_color = self.border_color
        elif self.is_hovered:
            # Invert colors on hover: black background, white border
            color = (0, 0, 0)  # Black background
            border_color = (255, 255, 255)  # White border
        else:
            color = self.tab_color
            border_color = self.border_color

        # Draw tab background
        pygame.draw.rect(surface, color, self.rect)

        # Draw border
        pygame.draw.rect(surface, border_color, self.rect, 2)

        # Draw minus sign in the center (matching vertical tabs)
        center_x = self.rect.centerx
        center_y = self.rect.centery

        # Draw horizontal bar (3 pixels wide, 1 pixel tall) - same as vertical tabs
        pygame.draw.rect(surface, border_color,
                        (center_x - 1, center_y, 3, 1))

    def handle_click(self, pos: tuple[int, int]) -> bool:
        """Handle mouse click on the horizontal tab.

        Args:
            pos: Mouse position (x, y)

        Returns:
            True if the tab was clicked, False otherwise

        """
        if self.rect.collidepoint(pos):
            self.is_clicked = True
            return True
        return False

    def handle_hover(self, pos: tuple[int, int]) -> bool:
        """Handle mouse hover over the horizontal tab.

        Args:
            pos: Mouse position (x, y)

        Returns:
            True if the tab is being hovered, False otherwise

        """
        self.is_hovered = self.rect.collidepoint(pos)
        return self.is_hovered

    def reset_click_state(self) -> None:
        """Reset the clicked state."""
        self.is_clicked = False

    def set_insertion_type(self, insertion_type: str, target_frame_index: int) -> None:
        """Set the insertion type and target frame for this tab.

        Args:
            insertion_type: "delete" for strip deletion
            target_frame_index: The frame index this tab is associated with

        """
        self.insertion_type = insertion_type
        self.target_frame_index = target_frame_index


class FilmStripTab:
    """Horizontal film tab widget for adding frames at the bottom of film strips.

    ARCHITECTURE OVERVIEW:
    This widget provides a horizontal tab interface that appears at the bottom
    of film strips to allow users to add new frames. It's wider than it is tall
    and behaves differently from the vertical FilmTabWidget.

    KEY COMPONENTS:
    1. Horizontal Design:
       - Wider than tall for better visual balance at the bottom
       - Centered horizontally on the film strip
       - Positioned at the bottom of the film strip

    2. Frame Addition:
       - Clicking the tab adds a new frame to the end of the animation
       - New frames are appended to the animated sprite's frame list
       - Film strip layout is recalculated after addition

    3. Visual Design:
       - Horizontal orientation with appropriate proportions
       - Clear visual indication of frame addition capability
       - Hover effects for better user experience
    """

    def __init__(self, x: int, y: int, width: int = 40, height: int = 10):
        """Initialize a horizontal film tab widget.

        Args:
            x: X position of the tab
            y: Y position of the tab
            width: Width of the tab (default 40, wider than vertical tabs)
            height: Height of the tab (default 10, shorter than vertical tabs)

        """
        self.rect = pygame.Rect(x, y, width, height)
        self.is_clicked = False
        self.is_hovered = False

        # Visual properties (matching vertical tabs)
        self.tab_color = (200, 200, 200)  # Light gray
        self.hover_color = (255, 255, 255)  # White
        self.click_color = (100, 100, 100)  # Dark gray
        self.border_color = (0, 0, 0)  # Black border (matching vertical tabs)

        # Tab behavior
        self.insertion_type = "after"  # Always adds after the last frame
        self.target_frame_index = 0  # Will be set when tab is created

    def render(self, surface: pygame.Surface) -> None:
        """Render the horizontal film tab to the surface.

        Args:
            surface: The pygame surface to render to

        """
        # Determine color based on state - invert colors on hover
        if self.is_clicked:
            color = self.click_color
            border_color = self.border_color
        elif self.is_hovered:
            # Invert colors on hover: black background, white border
            color = (0, 0, 0)  # Black background
            border_color = (255, 255, 255)  # White border
        else:
            color = self.tab_color
            border_color = self.border_color

        # Draw tab background
        pygame.draw.rect(surface, color, self.rect)

        # Draw border
        pygame.draw.rect(surface, border_color, self.rect, 2)

        # Draw plus sign in the center (matching vertical tabs)
        center_x = self.rect.centerx
        center_y = self.rect.centery

        # Draw horizontal bar (3 pixels wide, 1 pixel tall) - same as vertical tabs
        pygame.draw.rect(surface, border_color,
                        (center_x - 1, center_y, 3, 1))
        # Draw vertical bar (1 pixel wide, 3 pixels tall) - same as vertical tabs
        pygame.draw.rect(surface, border_color,
                        (center_x, center_y - 1, 1, 3))

    def handle_click(self, pos: tuple[int, int]) -> bool:
        """Handle mouse click on the horizontal tab.

        Args:
            pos: Mouse position (x, y)

        Returns:
            True if the tab was clicked, False otherwise

        """
        if self.rect.collidepoint(pos):
            self.is_clicked = True
            return True
        return False

    def handle_hover(self, pos: tuple[int, int]) -> bool:
        """Handle mouse hover over the horizontal tab.

        Args:
            pos: Mouse position (x, y)

        Returns:
            True if the tab is being hovered, False otherwise

        """
        self.is_hovered = self.rect.collidepoint(pos)
        return self.is_hovered

    def reset_click_state(self) -> None:
        """Reset the clicked state."""
        self.is_clicked = False

    def set_insertion_type(self, insertion_type: str, target_frame_index: int) -> None:
        """Set the insertion type and target frame for this tab.

        Args:
            insertion_type: "before" or "after" (typically "after" for bottom tabs)
            target_frame_index: The frame index this tab is associated with

        """
        self.insertion_type = insertion_type
        self.target_frame_index = target_frame_index
