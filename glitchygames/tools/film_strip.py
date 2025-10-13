"""Film strip widget for animated sprite frame selection.

This module provides a film reel-style interface for selecting and navigating
between frames in animated sprites, with sprocket separators between animations.
"""

# No typing imports needed

import pygame
from glitchygames.fonts import FontManager
from glitchygames.sprites import AnimatedSprite, SpriteFrame


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

    # Color cycling background colors (refactored from MiniView)
    BACKGROUND_COLORS: list[tuple[int, int, int]] = [
        (0, 255, 255),  # Cyan
        (0, 0, 0),  # Black
        (128, 128, 128),  # Gray
        (255, 255, 255),  # White
        (255, 0, 255),  # Magenta
        (0, 255, 0),  # Green
        (0, 0, 255),  # Blue
        (255, 255, 0),  # Yellow
        (64, 64, 64),  # Dark Gray
        (192, 192, 192),  # Light Gray
    ]

    def __init__(self, x: int, y: int, width: int, height: int):
        """Initialize the film strip widget."""
        self.rect = pygame.Rect(x, y, width, height)
        self.animated_sprite: AnimatedSprite | None = None
        self.current_animation = ""  # Will be set when sprite is loaded
        self.current_frame = 0
        self.is_selected = False  # Track if this film strip is currently selected
        self.hovered_frame: tuple[str, int] | None = None
        self.hovered_animation: str | None = None
        
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
        self.animation_border = (80, 60, 45)  # Even darker copper brown border for animation frame only

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
        self.tab_width = 13  # Width of each tab (narrower)
        self.tab_height = 30  # Height of each tab

        # Animation change detection threshold
        self.ANIMATION_CHANGE_THRESHOLD = 0.001
        
        # Copy/paste buffer for frames
        self._copied_frame = None  # Temporary storage for copied frame

    def set_animated_sprite(self, animated_sprite: AnimatedSprite) -> None:
        """Set the animated sprite to display."""
        print(f"FilmStripWidget: set_animated_sprite called with sprite: {animated_sprite}")
        print(f"FilmStripWidget: Sprite has {len(animated_sprite._animations)} animations: {list(animated_sprite._animations.keys())}")
        
        self.animated_sprite = animated_sprite
        # Use sprite introspection to find the first animation
        if animated_sprite._animations:
            if hasattr(animated_sprite, "_animation_order") and animated_sprite._animation_order:
                # Use the first animation in the file order
                self.current_animation = animated_sprite._animation_order[0]
                print(f"FilmStripWidget: Using first animation from _animation_order: {self.current_animation}")
            else:
                # Fall back to the first key in _animations
                self.current_animation = next(iter(animated_sprite._animations.keys()))
                print(f"FilmStripWidget: Using first animation from _animations: {self.current_animation}")
            
            # Configure the animated sprite to loop and start playing for preview
            print(f"FilmStripWidget: Setting animation to '{self.current_animation}'")
            animated_sprite.set_animation(self.current_animation)
            print(f"FilmStripWidget: After set_animation - current_animation: {getattr(animated_sprite, 'current_animation', 'None')}")
            
            print("FilmStripWidget: Setting is_looping to True")
            animated_sprite.is_looping = True  # Enable looping for continuous preview
            print(f"FilmStripWidget: After setting is_looping - is_looping: {getattr(animated_sprite, 'is_looping', 'None')}")
            
            print("FilmStripWidget: Calling play()")
            animated_sprite.play()  # Start playing the animation
            print(f"FilmStripWidget: After play() - is_playing: {getattr(animated_sprite, 'is_playing', 'None')}")
            print(f"FilmStripWidget: After play() - current_frame: {getattr(animated_sprite, 'current_frame', 'None')}")
        else:
            self.current_animation = ""
            print("FilmStripWidget: No animations found, setting current_animation to empty string")
        self.current_frame = 0
        self.scroll_offset = 0  # Horizontal scroll offset for rolling effect
        print(f"FilmStripWidget: Final state - current_animation: {self.current_animation}, current_frame: {self.current_frame}")

        # Initialize animation timing for previews
        self._initialize_preview_animations()
        
        # Mark as dirty since we've set up animations to play
        self.mark_dirty()
        print("FilmStripWidget: Marked as dirty after setting up animations")
        print(f"FilmStripWidget: _force_redraw after mark_dirty: {getattr(self, '_force_redraw', False)}")

        self._calculate_layout()
        self._update_height()

    def _initialize_preview_animations(self) -> None:
        """Initialize animation timing for all previews."""
        print("FilmStripWidget: _initialize_preview_animations called")
        
        if not self.animated_sprite:
            print("FilmStripWidget: No animated_sprite in _initialize_preview_animations, returning")
            return

        print(f"FilmStripWidget: Initializing preview animations for {len(self.animated_sprite._animations)} animations")

        for anim_name, frames in self.animated_sprite._animations.items():
            print(f"FilmStripWidget: Initializing animation '{anim_name}' with {len(frames)} frames")
            # Initialize timing for this animation
            # For single-frame animations, start with a small time offset to ensure animation advances
            if len(frames) == 1:
                # Single-frame animations need to start with a small time to ensure they advance
                self.preview_animation_times[anim_name] = 0.001  # Small offset to ensure animation starts
                print("FilmStripWidget: Single-frame animation, setting time to 0.001")
            else:
                self.preview_animation_times[anim_name] = 0.0
                print("FilmStripWidget: Multi-frame animation, setting time to 0.0")
            self.preview_animation_speeds[anim_name] = 1.0  # Normal speed
            print(f"FilmStripWidget: Set animation '{anim_name}' speed to 1.0")

            # Extract frame durations
            frame_durations = []
            for i, frame in enumerate(frames):
                if hasattr(frame, "duration"):
                    frame_durations.append(frame.duration)
                    print(f"FilmStripWidget: Frame {i} duration: {frame.duration}")
                else:
                    frame_durations.append(1.0)  # Default 1 second
                    print(f"FilmStripWidget: Frame {i} using default duration: 1.0")
            self.preview_frame_durations[anim_name] = frame_durations
            print(f"FilmStripWidget: Animation '{anim_name}' frame durations: {frame_durations}")
        
        print("FilmStripWidget: Preview animation initialization complete")
        print(f"FilmStripWidget: Final preview_animation_times: {self.preview_animation_times}")
        print(f"FilmStripWidget: Final preview_animation_speeds: {self.preview_animation_speeds}")
        print(f"FilmStripWidget: Final preview_frame_durations: {self.preview_frame_durations}")

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
        if self._debug_start_time - self._debug_last_dump_time >= 5.0:
                print("=" * 80)
                print(f"FILM STRIP ANIMATION STATE DUMP AT {self._debug_start_time:.1f} SECONDS")
                print("=" * 80)
                print("FilmStripWidget debug info:")
                print(f"  _debug_start_time: {self._debug_start_time}")
                print(f"  dt: {dt}")
                print(f"  animated_sprite: {self.animated_sprite}")
                print(f"  current_animation: {self.current_animation}")
                print(f"  current_frame: {self.current_frame}")
                print(f"  scroll_offset: {self.scroll_offset}")
                print(f"  _force_redraw: {getattr(self, '_force_redraw', False)}")
                print(f"  preview_animation_times: {getattr(self, 'preview_animation_times', {})}")
                print(f"  preview_animation_speeds: {getattr(self, 'preview_animation_speeds', {})}")
                print(f"  preview_frame_durations: {getattr(self, 'preview_frame_durations', {})}")
                
                if self.animated_sprite:
                    print("AnimatedSprite debug info:")
                    print(f"  current_animation: {getattr(self.animated_sprite, 'current_animation', 'None')}")
                    print(f"  current_frame: {getattr(self.animated_sprite, 'current_frame', 'None')}")
                    print(f"  is_playing: {getattr(self.animated_sprite, 'is_playing', 'None')}")
                    print(f"  is_looping: {getattr(self.animated_sprite, 'is_looping', 'None')}")
                    print(f"  _is_playing: {getattr(self.animated_sprite, '_is_playing', 'None')}")
                    print(f"  _is_looping: {getattr(self.animated_sprite, '_is_looping', 'None')}")
                    print(f"  _frame_timer: {getattr(self.animated_sprite, '_frame_timer', 'None')}")
                    print(f"  _animations: {getattr(self.animated_sprite, '_animations', {})}")
                    print(f"  _animation_order: {getattr(self.animated_sprite, '_animation_order', [])}")
                    print(f"  frame_manager.current_animation: {getattr(self.animated_sprite.frame_manager, 'current_animation', 'None')}")
                    print(f"  frame_manager.current_frame: {getattr(self.animated_sprite.frame_manager, 'current_frame', 'None')}")
                    
                    # Dump animation details
                    if hasattr(self.animated_sprite, "_animations") and self.animated_sprite._animations:
                        for anim_name, frames in self.animated_sprite._animations.items():
                            print(f"  Animation '{anim_name}':")
                            print(f"    frame count: {len(frames)}")
                            for i, frame in enumerate(frames):
                                print(f"    frame {i}: duration={getattr(frame, 'duration', 'None')}, image={getattr(frame, 'image', 'None')}")
                    
                    # Dump frame manager state
                    if hasattr(self.animated_sprite, "frame_manager"):
                        fm = self.animated_sprite.frame_manager
                        print("  FrameManager debug info:")
                        print(f"    _current_animation: {getattr(fm, '_current_animation', 'None')}")
                        print(f"    _current_frame: {getattr(fm, '_current_frame', 'None')}")
                        print(f"    _observers: {getattr(fm, '_observers', [])}")
                
                print("=" * 80)
                
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

        # Find which frame we should be showing during animation
        # This implements frame-based animation timing where each frame
        # has a specific duration, and we find which frame corresponds
        # to the current animation time
        accumulated_time = 0.0
        for frame_idx, duration in enumerate(frame_durations):
            if current_time <= accumulated_time + duration:
                return frame_idx
            accumulated_time += duration

        # Fallback to last frame
        # This should rarely happen due to the modulo operation in update_animations
        return len(frame_durations) - 1

    @staticmethod
    def _get_frame_image(frame) -> pygame.Surface:
        """Get the image surface for a frame."""
        if hasattr(frame, "image") and frame.image:
            return frame.image

        # Create a surface from the frame's pixel data
        if hasattr(frame, "get_pixel_data"):
            pixel_data = frame.get_pixel_data()
            if pixel_data:
                # Create a surface from the pixel data
                frame_surface = pygame.Surface((8, 8))  # Assuming 8x8 sprites
                for i, color in enumerate(pixel_data):
                    x = i % 8
                    y = i // 8
                    frame_surface.set_at((x, y), color)
                return frame_surface

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
        frames_per_view = 4
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
        
        print(f"FilmStripWidget: Scrolling to show frame {frame_index}, new window: {new_start_frame}-{new_start_frame + frames_per_view - 1}")

        # Recalculate layout with new scroll offset
        self._calculate_layout()
        self._update_height()
        self.mark_dirty()
    
    def copy_current_frame(self) -> bool:
        """Copy the currently selected frame to the clipboard.
        
        Returns:
            True if copy was successful, False otherwise

        """
        print("FilmStripWidget: [FILM STRIP COPY] copy_current_frame called")
        print(f"FilmStripWidget: [FILM STRIP COPY] animated_sprite: {self.animated_sprite}")
        print(f"FilmStripWidget: [FILM STRIP COPY] current_animation: {self.current_animation}")
        print(f"FilmStripWidget: [FILM STRIP COPY] current_frame: {self.current_frame}")
        
        if not self.animated_sprite or not self.current_animation:
            print("FilmStripWidget: [FILM STRIP COPY] No animation selected for copying")
            return False
            
        if self.current_animation not in self.animated_sprite._animations:
            print(f"FilmStripWidget: [FILM STRIP COPY] Animation '{self.current_animation}' not found")
            return False
            
        frames = self.animated_sprite._animations[self.current_animation]
        print(f"FilmStripWidget: [FILM STRIP COPY] Animation has {len(frames)} frames")
        if self.current_frame >= len(frames):
            print(f"FilmStripWidget: [FILM STRIP COPY] Frame {self.current_frame} out of range (max: {len(frames)-1})")
            return False
            
        # Get the current frame
        current_frame = frames[self.current_frame]
        print(f"FilmStripWidget: [FILM STRIP COPY] Got frame object: {current_frame}")
        
        # Create a deep copy of the frame data
        from copy import deepcopy
        self._copied_frame = deepcopy(current_frame)
        print("FilmStripWidget: [FILM STRIP COPY] Created deep copy, stored in _copied_frame")
        
        print(f"FilmStripWidget: [FILM STRIP COPY] Successfully copied frame {self.current_frame} from animation '{self.current_animation}'")
        return True
    
    def paste_to_current_frame(self) -> bool:
        """Paste the copied frame to the currently selected frame.
        
        Returns:
            True if paste was successful, False otherwise

        """
        print("FilmStripWidget: [FILM STRIP PASTE] paste_to_current_frame called")
        print(f"FilmStripWidget: [FILM STRIP PASTE] _copied_frame: {self._copied_frame}")
        print(f"FilmStripWidget: [FILM STRIP PASTE] animated_sprite: {self.animated_sprite}")
        print(f"FilmStripWidget: [FILM STRIP PASTE] current_animation: {self.current_animation}")
        print(f"FilmStripWidget: [FILM STRIP PASTE] current_frame: {self.current_frame}")
        
        if not self._copied_frame:
            print("FilmStripWidget: [FILM STRIP PASTE] No frame in clipboard to paste")
            return False
            
        if not self.animated_sprite or not self.current_animation:
            print("FilmStripWidget: [FILM STRIP PASTE] No animation selected for pasting")
            return False
            
        if self.current_animation not in self.animated_sprite._animations:
            print(f"FilmStripWidget: [FILM STRIP PASTE] Animation '{self.current_animation}' not found")
            return False
            
        frames = self.animated_sprite._animations[self.current_animation]
        print(f"FilmStripWidget: [FILM STRIP PASTE] Animation has {len(frames)} frames")
        if self.current_frame >= len(frames):
            print(f"FilmStripWidget: [FILM STRIP PASTE] Frame {self.current_frame} out of range (max: {len(frames)-1})")
            return False
            
        print(f"FilmStripWidget: [FILM STRIP PASTE] Replacing frame {self.current_frame} with copied frame")
        # Replace the current frame with the copied frame
        from copy import deepcopy
        frames[self.current_frame] = deepcopy(self._copied_frame)
        print("FilmStripWidget: [FILM STRIP PASTE] Frame replacement completed")
        
        print(f"FilmStripWidget: [FILM STRIP PASTE] Successfully pasted frame to frame {self.current_frame} in animation '{self.current_animation}'")
        
        # Mark as dirty to trigger redraw
        self.mark_dirty()
        print("FilmStripWidget: [FILM STRIP PASTE] Marked as dirty")
        
        # Notify parent scene if available
        if hasattr(self, "parent_scene") and self.parent_scene:
            print("FilmStripWidget: [FILM STRIP PASTE] Notifying parent scene")
            if hasattr(self.parent_scene, "_on_frame_pasted"):
                self.parent_scene._on_frame_pasted(self.current_animation, self.current_frame)
        else:
            print("FilmStripWidget: [FILM STRIP PASTE] No parent scene to notify")
        
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
        ) * visible_animations + 0

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
            ))
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
        y_offset = 0
        
        # Calculate the center position between sprocket groups
        # Left group ends at x=61, right group starts at preview_start_x + 10
        preview_start_x = available_width + self.preview_padding
        left_group_end = 61
        right_group_start = preview_start_x + 10
        center_x = (left_group_end + right_group_start) // 2
        
        # Calculate label width dynamically for each animation
        for anim_name in self.animated_sprite._animations.keys():
            # Get text width for this animation
            font = FontManager.get_font()
            text_surface = font.render(anim_name, fgcolor=(255, 255, 255), size=16)
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
            print("FilmStripWidget: No animated sprite, skipping frame layout calculation")
            return
        
        print(f"FilmStripWidget: Calculating frame layouts for {len(self.animated_sprite._animations)} animations")
        
        y_offset = 0
        
        # Calculate sprocket start position to align frames with sprockets
        sprocket_spacing = 17
        total_width = self.rect.width - 20  # Leave 10px margin on each side
        num_sprockets = (total_width // sprocket_spacing) + 1
        sprockets_width = (num_sprockets - 1) * sprocket_spacing
        sprocket_start_x = 10 + (total_width - sprockets_width) // 2
        
        # Calculate how many frames can fit before overlapping the animation box
        available_width_for_frames = self.rect.width - self.preview_width - self.preview_padding - 20  # Total width minus preview area minus margins
        frame_width_with_spacing = self.frame_width + self.frame_spacing  # 64 + 2 = 66 pixels
        max_frames_before_overlap = available_width_for_frames // frame_width_with_spacing
        print(f"Max frames before overlapping animation box: {max_frames_before_overlap}")
        
        for anim_name, frames in self.animated_sprite._animations.items():
            # Show only 4 frames at a time (0-3), with scrolling to navigate
            # Calculate which frames to show based on scroll offset
            frames_per_view = 4  # Show 4 frames at a time (indices 0, 1, 2, 3)
            start_frame = self.scroll_offset // (self.frame_width + self.tab_width + 2)  # Calculate starting frame based on scroll
            end_frame = min(start_frame + frames_per_view, len(frames))
            frames_to_show = frames[start_frame:end_frame]
            print(f"FilmStripWidget: Processing {len(frames_to_show)} frames for animation {anim_name} (frames {start_frame}-{end_frame-1})")
            for frame_idx, _frame in enumerate(frames_to_show):
                # Adjust frame_idx to be relative to the actual frame position
                actual_frame_idx = start_frame + frame_idx
                # Calculate frame position - frames stay in fixed positions, we just show different frames
                if frame_idx == 0:
                    # First frame starts 4px to the right of the "before" tab, then 6px more left
                    frame_x = sprocket_start_x - 1 + 4 - 6
                else:
                    # Subsequent frames start 2px after the previous frame's tab
                    # Account for the first frame's offset and 2px gap between frames
                    frame_x = sprocket_start_x + 4 - 6 + frame_idx * (self.frame_width + self.tab_width + 2) - 1
                
                # For single animation, all frames should be at the same Y position
                # Nudge up by 2 pixels to align with the right-side animation frame
                frame_y = self.animation_label_height - 2 if len(self.animated_sprite._animations) == 1 else y_offset + self.animation_label_height
                frame_rect = pygame.Rect(
                    frame_x,
                    frame_y,
                    self.frame_width,
                    self.frame_height,
                )
                print(f"FilmStripWidget: Created frame rect for {anim_name}[{actual_frame_idx}] at {frame_rect}")
                self.frame_layouts[anim_name, actual_frame_idx] = frame_rect
            
            # Only increment Y offset if there are multiple animations
            # For single animation, all frames should be at the same Y position
            if len(self.animated_sprite._animations) > 1:
                y_offset += self.animation_label_height + self.frame_height + 20

    def _calculate_preview_layouts(self) -> None:
        """Calculate layout for preview areas."""
        if not self.animated_sprite:
            return
        
        y_offset = 0
        preview_x = self.rect.width - self.preview_width - 1
        
        for anim_name in self.animated_sprite._animations.keys():
            # Center the preview vertically with this animation's frames
            frame_visual_start_y = y_offset + self.animation_label_height + 4  # Match per-frame Y position
            frame_visual_height = self.frame_height - 8  # 4px padding top and bottom
            frame_visual_center_y = frame_visual_start_y + frame_visual_height // 2
            preview_center_y = self.preview_height // 2
            preview_y = frame_visual_center_y - preview_center_y - 2  # Move up 2 pixels to match per-frame Y
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
        y_offset = 0
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
        print(f"FilmStripWidget: Checking position {pos} against {len(self.frame_layouts)} frame layouts")
        for (anim_name, frame_idx), frame_rect in self.frame_layouts.items():
            print(f"FilmStripWidget: Checking {anim_name}[{frame_idx}] at {frame_rect}")
            if frame_rect.collidepoint(pos):
                print(f"FilmStripWidget: Found collision with {anim_name}[{frame_idx}]")
                return (anim_name, frame_idx)
        print("FilmStripWidget: No collision found")
        return None

    def get_animation_at_position(self, pos: tuple[int, int]) -> str | None:
        """Get the animation at the given position."""
        for anim_name, anim_rect in self.animation_layouts.items():
            if anim_rect.collidepoint(pos):
                return anim_name
        return None

    def set_current_frame(self, animation: str, frame: int) -> None:
        """Set the current animation and frame."""
        if (
            self.animated_sprite
            and animation in self.animated_sprite._animations
            and 0 <= frame < len(self.animated_sprite._animations[animation])
        ):
            print(f"FilmStripWidget: Setting current frame to {animation}, {frame}")
            self.current_animation = animation
            self.current_frame = frame
            # Mark as dirty to trigger preview update
            self.mark_dirty()
            print(f"FilmStripWidget: Current selection is now {self.current_animation}, {self.current_frame}")
            
            # Notify parent scene about the selection change
            if hasattr(self, "parent_scene") and self.parent_scene:
                self.parent_scene._on_film_strip_frame_selected(self, animation, frame)

    def handle_click(self, pos: tuple[int, int]) -> tuple[str, int] | None:
        """Handle a click on the film strip."""
        print(f"FilmStripWidget: handle_click called with position {pos}")
        print(f"FilmStripWidget: frame_layouts has {len(self.frame_layouts)} entries")
        
        # First check if a tab was clicked
        if self._handle_tab_click(pos):
            print("FilmStripWidget: Tab was clicked, not processing frame click")
            return None  # Tab was clicked, don't process frame click
        
        # Check if clicking on a frame
        clicked_frame = self.get_frame_at_position(pos)
        if clicked_frame:
            animation, frame_idx = clicked_frame
            # Use this film strip's animation name instead of the frame's animation name
            # since each film strip represents a specific animation
            strip_animation = list(self.animated_sprite._animations.keys())[0] if self.animated_sprite and self.animated_sprite._animations else animation
            print(f"FilmStripWidget: Frame clicked, calling set_current_frame({strip_animation}, {frame_idx})")
            self.set_current_frame(strip_animation, frame_idx)
            return (strip_animation, frame_idx)

        # Check if clicking on an animation label
        clicked_animation = self.get_animation_at_position(pos)
        if clicked_animation and clicked_animation in self.animated_sprite._animations:
            # Use this film strip's animation name instead of the clicked animation name
            # since each film strip represents a specific animation
            strip_animation = list(self.animated_sprite._animations.keys())[0] if self.animated_sprite and self.animated_sprite._animations else clicked_animation
            print(f"FilmStripWidget: Animation clicked, calling set_current_frame({strip_animation}, 0)")
            self.set_current_frame(strip_animation, 0)
            return (strip_animation, 0)
        
        # Check if clicking on preview area
        preview_click = self.handle_preview_click(pos)
        if preview_click:
            return preview_click
        
        print("FilmStripWidget: No frame or animation clicked")
        return None

    def handle_hover(self, pos: tuple[int, int]) -> None:
        """Handle mouse hover over the film strip."""
        self.hovered_frame = self.get_frame_at_position(pos)
        self.hovered_animation = self.get_animation_at_position(pos)

    def handle_preview_click(self, pos: tuple[int, int]) -> tuple[str, int] | None:
        """Handle mouse click on the preview area (right side). Returns (animation, frame_idx) if click was handled."""
        # Check if click is on the animated preview frame (right side)
        for anim_name, preview_rect in self.preview_rects.items():
            if preview_rect.collidepoint(pos):
                # Cycle background color for all frames in this animation
                self.background_color_index = (self.background_color_index + 1) % len(self.BACKGROUND_COLORS)
                self.background_color = self.BACKGROUND_COLORS[self.background_color_index]
                print(f"Film strip background color changed to {self.background_color}")
                # Return the animation name and frame 0 to indicate selection
                return (anim_name, 0)
        return None

    def render_frame_thumbnail(
        self, frame, *, is_selected: bool = False, is_hovered: bool = False, frame_index: int = 0, animation_name: str = ""
    ) -> pygame.Surface:
        """Render a single frame thumbnail with 3D beveled border."""
        frame_surface = self._create_frame_surface()
        
        # Fill with cycling background color
        frame_surface.fill(self.background_color)
        
        
        frame_img = self._get_frame_image_for_rendering(frame, is_selected)
        
        if frame_img:
            self._draw_scaled_image(frame_surface, frame_img)
        else:
            self._draw_placeholder(frame_surface)
        
        # Add 3D beveled border like the right side animation frame
        self._add_3d_beveled_border(frame_surface)
        
        # Add red border for selected frame - check global selection state
        is_selected_frame = False
        if hasattr(self, "parent_scene") and self.parent_scene:
            is_selected_frame = (
                hasattr(self.parent_scene, "selected_animation") and 
                hasattr(self.parent_scene, "selected_frame") and
                self.parent_scene.selected_animation == animation_name and 
                self.parent_scene.selected_frame == frame_index
            )
        
        if is_selected_frame:
            pygame.draw.rect(frame_surface, self.selection_color, (0, 0, self.frame_width, self.frame_height), 3)
        
        return frame_surface

    def _create_frame_surface(self) -> pygame.Surface:
        """Create the base frame surface with transparent background."""
        frame_surface = pygame.Surface((self.frame_width, self.frame_height), pygame.SRCALPHA)
        # No background fill - transparent so only the 3D beveled border shows
        return frame_surface

    def _get_frame_image_for_rendering(self, frame, is_selected: bool):
        """Get the appropriate frame image for rendering."""
        # Always use the actual animation frame data, not canvas content
        if hasattr(frame, "image") and frame.image:
            # Use stored frame data for all frames
            frame_img = frame.image
        else:
            frame_img = None
            print("Film strip: No frame data available")

        # Always use animation frame data, never canvas content

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
        
        # Make magenta (255, 0, 255) transparent for testing
        scaled_image.set_colorkey((255, 0, 255))
        frame_surface.blit(scaled_image, (x_offset, y_offset))

    def _draw_placeholder(self, frame_surface: pygame.Surface) -> None:
        """Draw a placeholder when no frame data is available."""
        # If no frame data, create a placeholder
        placeholder = pygame.Surface((self.frame_width - 8, self.frame_height - 8))
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
        selection_border = pygame.Surface((self.frame_width + 4, self.frame_height + 4))
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
        separator = pygame.Surface((self.sprocket_width, height))
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
            # Clear the preview area with cycling background color
            surface.fill(self.background_color, preview_rect)

            # Draw preview border (animation frame only - use darker border)
            pygame.draw.rect(surface, self.animation_border, preview_rect, 2)

            # Get the current animated frame for this animation's preview
            if (
                anim_name in self.animated_sprite._animations
                and len(self.animated_sprite._animations[anim_name]) > 0
            ):
                # Get the current frame index based on animation timing
                current_frame_idx = self.get_current_preview_frame(anim_name)
                frame = self.animated_sprite._animations[anim_name][current_frame_idx]

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
            print(f"FilmStripWidget: Render #{self._render_count}, current_frame={self.current_frame}")

        # Clear the film strip area
        surface.fill(self.film_background, self.rect)

        # Check if we need to force a complete redraw
        force_redraw = getattr(self, "_force_redraw", False)
        if force_redraw:
            # Don't reset the flag here - let it persist for frame rendering
            pass

        # Render animation labels
        for anim_name, anim_rect in self.animation_layouts.items():
            # Draw animation label background
            label_surface = pygame.Surface((anim_rect.width, anim_rect.height))
            label_surface.fill(self.film_background)

            # Add animation name text
            font = FontManager.get_font()
            text = font.render(anim_name, fgcolor=(255, 255, 255), size=16)
            if isinstance(text, tuple):  # freetype returns (surface, rect)
                text, text_rect = text
            else:  # pygame.font returns surface
                text_rect = text.get_rect()
            text_rect.center = (anim_rect.width // 2, anim_rect.height // 2)
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

        # Render sprocket separators
        for sprocket_rect in self.sprocket_layouts:
            sprocket = self.render_sprocket_separator(0, 0, sprocket_rect.height)
            surface.blit(sprocket, sprocket_rect)

        # Render the animated preview
        self.render_preview(surface)
        
        # Reset the force redraw flag after all frames have been rendered
        if hasattr(self, "_force_redraw") and self._force_redraw:
            self._force_redraw = False
        
        # Draw film strip sprockets after everything else
        self._draw_film_sprockets(surface)
        
        # Draw white border around the entire film strip as the very last thing
        # pygame.draw.rect(surface, (255, 255, 255), self.rect, 2)
        
        # Mark as dirty to ensure sprockets are redrawn
        self.mark_dirty()

    def _draw_film_sprockets(self, surface: pygame.Surface) -> None:
        """Draw film strip sprockets on the main background."""
        
        sprocket_color = (60, 50, 40)  # Even darker grey-brown color
        
        # Draw sprockets along the top edge - aligned with bottom sprockets, avoiding label area
        # Calculate the label area to avoid overlapping
        available_width = self.rect.width - self.preview_width - self.preview_padding
        preview_start_x = available_width + self.preview_padding
        
        # Calculate label boundaries to avoid
        left_group_end = 61
        right_group_start = preview_start_x + 10
        center_x = (left_group_end + right_group_start) // 2
        
        # Get label width for this film strip's current animation
        label_left = center_x
        label_right = center_x
        if self.current_animation:
            # Use the film strip's current animation name (which gets updated when switching strips)
            anim_name = self.current_animation
            font = FontManager.get_font()
            text_surface = font.render(anim_name, fgcolor=(255, 255, 255), size=16)
            if isinstance(text_surface, tuple):  # freetype returns (surface, rect)
                text_surface, text_rect = text_surface
            else:  # pygame.font returns surface
                text_rect = text_surface.get_rect()
            label_width = text_rect.width + 20  # Add padding
            label_left = center_x - (label_width // 2)
            label_right = center_x + (label_width // 2)
        
        # Draw top sprockets aligned with bottom sprockets, avoiding label area
        # Use the same calculation as bottom sprockets to ensure perfect alignment
        sprocket_spacing = 17
        total_width = self.rect.width - 20  # Leave 10px margin on each side
        
        # Calculate how many sprockets fit and center them (same as bottom)
        num_sprockets = (total_width // sprocket_spacing) + 1
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
                    rect = pygame.Rect(x - 3, 7, 6, 6)  # 6x6 rectangle centered at (x, 10)
                    pygame.draw.rect(surface, sprocket_color, rect, border_radius=3)
        
        
        # Draw sprockets along the bottom edge - span the entire width
        bottom_y = self.rect.height - 10 - 5  # height - 10 - radius
        
        # Calculate how many sprockets we can fit across the full width
        sprocket_spacing = 17
        total_width = self.rect.width - 20  # Leave 10px margin on each side
        
        # Calculate how many sprockets fit and center them (add one more)
        num_sprockets = (total_width // sprocket_spacing) + 1
        if num_sprockets > 0:
            # Calculate the total space the sprockets will occupy
            sprockets_width = (num_sprockets - 1) * sprocket_spacing
            # Center the sprockets within the available space
            start_x = 10 + (total_width - sprockets_width) // 2
            
            # Draw sprockets across the entire width
            for i in range(num_sprockets):
                x = start_x + (i * sprocket_spacing)
                # Draw rounded rectangle instead of circle
                rect = pygame.Rect(x - 3, bottom_y - 3, 6, 6)  # 6x6 rectangle centered at (x, bottom_y)
                pygame.draw.rect(surface, sprocket_color, rect, border_radius=3)
        

    def _calculate_frames_width(self) -> int:
        """Calculate the total width needed for all frames and sprockets."""
        frames_width = 0
        animation_names = list(self.animated_sprite._animations.keys())
        for i, (anim_name, frames) in enumerate(self.animated_sprite._animations.items()):
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
    
    def _handle_tab_click(self, pos: tuple[int, int]) -> bool:
        """Handle mouse click on film tabs.
        
        Args:
            pos: Mouse position (x, y)
            
        Returns:
            True if a tab was clicked, False otherwise

        """
        for tab in self.film_tabs:
            if tab.handle_click(pos):
                # Create a new frame at the specified position
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
        if not self.animated_sprite or not self.parent_scene:
            return
            
        current_animation = self.current_animation
        if current_animation not in self.animated_sprite._animations:
            return
            
        # Create a new blank frame with magenta background
        frame_width = 32  # Default frame size
        frame_height = 32
        new_surface = pygame.Surface((frame_width, frame_height))
        new_surface.fill((255, 0, 255))  # Magenta background
        
        # Create a new SpriteFrame
        new_frame = SpriteFrame(new_surface, duration=0.5)
        
        # Determine insertion index
        if tab.insertion_type == "before":
            insert_index = tab.target_frame_index
        else:  # "after"
            insert_index = tab.target_frame_index + 1
            
        # Insert the frame into the animated sprite
        self.animated_sprite.add_frame(current_animation, new_frame, insert_index)
        
        # Notify the parent scene about the frame insertion
        if hasattr(self.parent_scene, "_on_frame_inserted"):
            self.parent_scene._on_frame_inserted(current_animation, insert_index)
        
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
        # Determine color based on state
        if self.is_clicked:
            color = self.click_color
        elif self.is_hovered:
            color = self.hover_color
        else:
            color = self.tab_color
            
        # Draw tab background
        pygame.draw.rect(surface, color, self.rect)
        
        # Draw border
        pygame.draw.rect(surface, self.border_color, self.rect, 2)
        
        # Draw plus sign in the center
        center_x = self.rect.centerx
        center_y = self.rect.centery
        plus_size = 8
        
        # Draw horizontal line (shorter on left side)
        pygame.draw.line(surface, self.border_color, 
                        (center_x - plus_size//2 + 1, center_y), 
                        (center_x + plus_size//2, center_y), 2)
        # Draw vertical line (shorter on top)
        pygame.draw.line(surface, self.border_color, 
                        (center_x, center_y - plus_size//2 + 1), 
                        (center_x, center_y + plus_size//2), 2)
    
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
