"""Film strip coordination for the Bitmappy editor.

Manages film strip lifecycle, animation operations, frame management,
selection/navigation, and display synchronization. Extracted from
BitmapEditorScene to reduce class complexity.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import pygame

from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame

from .constants import (
    LOG,
    MIN_FILM_STRIPS_FOR_PANEL_POSITIONING,
)
from .film_strip import FilmStripWidget
from .film_strip_sprite import FilmStripSprite
from .scroll_arrow import ScrollArrowSprite

if TYPE_CHECKING:
    from .protocols import EditorContext


class FilmStripCoordinator:  # noqa: PLR0904
    """Coordinates film strip operations for the Bitmappy editor.

    Manages film strip lifecycle, animation add/delete/rename,
    frame operations, selection/navigation, scrolling, and display
    synchronization. Operates on editor state via the EditorContext protocol.
    """

    def __init__(self, editor: EditorContext) -> None:
        """Initialize the FilmStripCoordinator.

        Args:
            editor: The editor context providing access to shared state.

        """
        self.editor = editor
        self.log = logging.getLogger('game.tools.bitmappy.film_strip_coordinator')
        self.log.addHandler(logging.NullHandler())

        # Internal state
        self._creating_animation = False
        self._creating_frame = False
        self._preserved_controller_selections: dict[int, Any] | None = None
        self.selected_strip: FilmStripWidget | None = None

    def _create_blank_frame(self, width: int, height: int, duration: float = 0.5) -> SpriteFrame:
        """Create a blank frame with magenta background and proper alpha support.

        This is the canonical method for creating blank frames to ensure consistency
        across the codebase and proper per-pixel alpha support.

        Args:
            width: Width of the frame in pixels
            height: Height of the frame in pixels
            duration: Frame duration in seconds (default: 0.5)

        Returns:
            A new SpriteFrame with magenta background and SRCALPHA support

        """
        from glitchygames.sprites.animated import SpriteFrame

        # Create surface with SRCALPHA to support per-pixel alpha transparency
        surface = pygame.Surface((width, height), pygame.SRCALPHA)
        surface.fill((255, 0, 255))  # Magenta background

        # Create the SpriteFrame
        frame = SpriteFrame(surface, duration=duration)

        # Initialize pixel data (magenta with full alpha)
        frame.pixels = [(255, 0, 255, 255)] * (width * height)  # ty: ignore[invalid-assignment]

        return frame

    def _create_film_strips(self, groups: pygame.sprite.LayeredDirty | None) -> None:  # type: ignore[type-arg]
        """Create film strips for the current animated sprite - handles all loading scenarios."""
        self._log_film_strip_debug_state()

        if (
            not hasattr(self.editor, 'canvas')
            or not self.editor.canvas
            or not hasattr(self.editor.canvas, 'animated_sprite')
            or not self.editor.canvas.animated_sprite
        ):
            LOG.debug('DEBUG: _create_film_strips returning early - conditions not met')
            return

        animated_sprite = self.editor.canvas.animated_sprite
        LOG.debug(f'DEBUG: _create_film_strips proceeding with animated_sprite: {animated_sprite}')

        self._ensure_default_animation_exists(animated_sprite)

        film_strip_x, film_strip_width = self._calculate_film_strip_dimensions()
        film_strip_y_start = self.editor.canvas.rect.y  # Start at same vertical position as canvas

        # Calculate vertical spacing between strips
        strip_spacing = -19
        # Height of each film strip (increased by 20 pixels to
        # accommodate delete button and proper spacing)
        strip_height = 180

        # Create a separate film strip for each animation
        LOG.debug('DEBUG: Starting film strip creation loop')
        for strip_index, (anim_name, frames) in enumerate(animated_sprite._animations.items()):  # type: ignore[reportPrivateUsage]
            self._create_single_film_strip(  # type: ignore[arg-type]
                strip_index=strip_index,
                anim_name=anim_name,
                frames=frames,
                film_strip_x=film_strip_x,
                film_strip_y_start=int(film_strip_y_start),
                film_strip_width=film_strip_width,
                strip_height=strip_height,
                strip_spacing=strip_spacing,
                groups=groups,
            )

        # Create scroll arrows
        self._create_scroll_arrows()

        # Update visibility — this shows only 2 strips and calls mark_dirty()
        # on the visible ones, so they'll be rendered on the next update cycle.
        # No need to force_redraw() all strips here.
        self.update_film_strip_visibility()

        # Select the first film strip and set its frame 0 as active
        LOG.debug('DEBUG: About to call _select_initial_film_strip')
        self._select_initial_film_strip()

        # OLD SYSTEM REMOVED - Using new multi-controller system instead

        LOG.debug('DEBUG: _create_film_strips completed successfully')

        # Reinitialize multi-controller system for existing controllers AFTER film strips are fully
        # set up
        # Pass preserved controller selections if available
        preserved_selections = getattr(self, '_preserved_controller_selections', None)
        self.editor.controller_handler.reinitialize_multi_controller_system(preserved_selections)

    def _create_single_film_strip(  # noqa: PLR0913
        self,
        *,
        strip_index: int,
        anim_name: str,
        frames: list[SpriteFrame],
        film_strip_x: int,
        film_strip_y_start: int,
        film_strip_width: int,
        strip_height: int,
        strip_spacing: int,
        groups: pygame.sprite.LayeredDirty | None,  # type: ignore[type-arg]
    ) -> None:
        """Create a single film strip widget and sprite for one animation.

        Args:
            strip_index: Index of this strip in the animation list
            anim_name: Name of the animation
            frames: List of animation frames
            film_strip_x: X position for the film strip
            film_strip_y_start: Starting Y position for film strips
            film_strip_width: Width of each film strip
            strip_height: Height of each film strip
            strip_spacing: Vertical spacing between strips
            groups: Sprite groups to add the film strip sprite to

        """
        LOG.debug(
            f'DEBUG: Creating film strip {strip_index} for animation {anim_name} with'
            f' {len(frames)} frames',
        )
        LOG.debug(
            'Creating film strip %s for animation %s with %s frames',
            strip_index,
            anim_name,
            len(frames),
        )
        # Create a single animated sprite with just this animation
        # Use the proper constructor to ensure all attributes are initialized
        single_anim_sprite = AnimatedSprite()
        single_anim_sprite._animations = {anim_name: frames}  # type: ignore[reportPrivateUsage]
        single_anim_sprite._animation_order = [anim_name]  # type: ignore[reportPrivateUsage]  # Set animation order

        # Properly initialize the frame manager state
        single_anim_sprite.frame_manager.current_animation = anim_name
        single_anim_sprite.frame_manager.current_frame = 0

        # Set up the sprite to be ready for animation
        single_anim_sprite.set_animation(anim_name)
        single_anim_sprite.is_looping = True
        single_anim_sprite.play()

        # DEBUG: Log the sprite state
        LOG.debug(f'Created single_anim_sprite for {anim_name}:')
        LOG.debug(f'  _animations: {list(single_anim_sprite._animations.keys())}')  # type: ignore[reportPrivateUsage]
        LOG.debug(f'  _animation_order: {single_anim_sprite._animation_order}')  # type: ignore[reportPrivateUsage]
        LOG.debug(f'  current_animation: {single_anim_sprite.current_animation}')
        LOG.debug(f'  is_playing: {single_anim_sprite.is_playing}')
        LOG.debug(f'  is_looping: {single_anim_sprite.is_looping}')

        # Calculate Y position with scrolling
        base_y = film_strip_y_start + (strip_index * (strip_height + strip_spacing))
        scroll_y = base_y - (self.editor.film_strip_scroll_offset * (strip_height + strip_spacing))

        # Create film strip widget for this animation
        film_strip = FilmStripWidget(
            x=film_strip_x,
            y=scroll_y,
            width=film_strip_width,
            height=strip_height,
        )
        film_strip.set_animated_sprite(single_anim_sprite)
        film_strip.strip_index = strip_index  # type: ignore[attr-defined] # ty: ignore[unresolved-attribute]  # Track which strip this is

        # CRITICAL FIX: Ensure all frames in the single animation sprite have proper image data
        # This fixes the issue where film strips show empty gray squares
        self._ensure_frames_have_image_data(single_anim_sprite)

        # Update the layout to calculate frame positions
        LOG.debug(f'Updating layout for film strip {strip_index} ({anim_name})')
        film_strip.update_layout()
        LOG.debug(
            f'Film strip {strip_index} layout updated, frame_layouts has'
            f' {len(film_strip.frame_layouts)} entries',
        )

        # Set parent scene reference for selection handling
        film_strip.parent_scene = self.editor

        # Store the strip in the film strips dictionary
        self.editor.film_strips[anim_name] = film_strip

        # Create film strip sprite for rendering
        film_strip_sprite = FilmStripSprite(
            film_strip_widget=film_strip,
            x=film_strip_x,
            y=scroll_y,
            width=film_strip_width,
            height=film_strip.rect.height,
            groups=groups,
        )

        # Debug: Check if film strip sprite was added to groups
        self.log.debug(
            f'Created film strip sprite for {anim_name}, groups: {film_strip_sprite.groups()}',
        )
        LOG.debug(
            f'DEBUG: Film strip sprite {anim_name} added to {len(film_strip_sprite.groups())}'
            f' groups: {film_strip_sprite.groups()}',
        )

        # Connect the film strip to the canvas
        film_strip_sprite.set_parent_canvas(self.editor.canvas)
        film_strip.set_parent_canvas(self.editor.canvas)

        # Set parent scene reference for the film strip sprite
        film_strip_sprite.parent_scene = self.editor  # type: ignore[reportAttributeAccessIssue] # ty: ignore[invalid-assignment]

        # Set parent scene reference for the film strip widget
        film_strip.parent_scene = self.editor

        # Set up bidirectional reference between film strip widget and sprite
        film_strip.film_strip_sprite = film_strip_sprite
        film_strip_sprite.film_strip_widget = film_strip

        # Store the film strip sprite
        self.editor.film_strip_sprites[anim_name] = film_strip_sprite

        # CRITICAL: Mark film strip sprite as dirty and force initial redraw
        # This ensures the film strip updates properly on first load
        film_strip_sprite.dirty = 1
        film_strip.mark_dirty()
        film_strip_sprite.force_redraw()

    def _log_film_strip_debug_state(self) -> None:
        """Log debug state for film strip creation diagnostics."""
        LOG.debug(f"DEBUG: hasattr(self.editor, 'canvas'): {hasattr(self.editor, 'canvas')}")
        if not hasattr(self.editor, 'canvas'):
            return
        LOG.debug(f'DEBUG: self.editor.canvas: {self.editor.canvas}')
        if not self.editor.canvas:
            return
        LOG.debug(
            "DEBUG: hasattr(self.editor.canvas, 'animated_sprite'):"
            f' {hasattr(self.editor.canvas, "animated_sprite")}',
        )
        if not hasattr(self.editor.canvas, 'animated_sprite'):
            return
        LOG.debug(
            f'DEBUG: self.editor.canvas.animated_sprite: {self.editor.canvas.animated_sprite}',
        )
        if not self.editor.canvas.animated_sprite:
            return
        LOG.debug(
            "DEBUG: hasattr(self.editor.canvas.animated_sprite, '_animations'):"
            f' {hasattr(self.editor.canvas.animated_sprite, "_animations")}',
        )
        if hasattr(self.editor.canvas.animated_sprite, '_animations'):
            LOG.debug(
                'DEBUG: self.editor.canvas.animated_sprite._animations:'
                f' {self.editor.canvas.animated_sprite._animations}',  # type: ignore[reportPrivateUsage]
            )

    def _ensure_default_animation_exists(self, animated_sprite: AnimatedSprite) -> None:
        """Ensure there's always at least one animation with one frame for film strip creation."""
        if hasattr(animated_sprite, '_animations') and animated_sprite._animations:  # type: ignore[reportPrivateUsage]
            return

        LOG.debug('DEBUG: No animations found, creating default animation with one frame')
        from glitchygames.sprites.animated import SpriteFrame

        frame_width = self.editor.canvas.pixels_across
        frame_height = self.editor.canvas.pixels_tall
        frame_surface = pygame.Surface((frame_width, frame_height))
        frame_surface.fill((255, 0, 255))  # Magenta background

        default_frame = SpriteFrame(frame_surface)
        default_frame.set_pixel_data([(255, 0, 255)] * (frame_width * frame_height))  # ty: ignore[invalid-argument-type]

        animated_sprite._animations = {'default': [default_frame]}  # type: ignore[reportPrivateUsage]
        animated_sprite._animation_order = ['default']  # type: ignore[reportPrivateUsage]
        animated_sprite.frame_manager.current_animation = 'default'
        animated_sprite.frame_manager.current_frame = 0

    def _calculate_film_strip_dimensions(self) -> tuple[int, int]:
        """Calculate the x position and width for film strips.

        Returns:
            Tuple of (film_strip_x, film_strip_width).

        """
        if hasattr(self.editor, 'color_well') and self.editor.color_well:
            film_strip_x = (
                self.editor.color_well.rect.right + 1
            )  # Film strip left x = color well right x + 1
        else:
            film_strip_x = self.editor.canvas.rect.right + 4  # 4 pixels to the right of canvas edge

        screen = pygame.display.get_surface()
        assert screen is not None
        screen_width = screen.get_width()
        available_width = screen_width - film_strip_x
        film_strip_width = max(300, available_width)

        return int(film_strip_x), int(film_strip_width)

    def _create_frame_image_from_pixels(self, frame: SpriteFrame, frame_idx: int) -> None:
        """Create a frame's image surface from its pixel data.

        Args:
            frame: The sprite frame object.
            frame_idx: Frame index for debug logging.

        """
        try:
            pixel_data = frame.get_pixel_data()
            if not pixel_data:
                return

            width, height = frame.get_size()
            surface = pygame.Surface((width, height), pygame.SRCALPHA)

            for i, color in enumerate(pixel_data):
                if i < width * height:
                    surface.set_at((i % width, i // width), color)

            frame.image = surface
            LOG.debug(f'DEBUG: Created image for frame {frame_idx} from pixel data')

        except pygame.error, AttributeError, TypeError, ValueError, IndexError:
            LOG.exception(f'DEBUG: Failed to create image for frame {frame_idx}')

    def _create_default_magenta_frame(self, frame: SpriteFrame, frame_idx: int) -> None:
        """Create a default magenta frame image and pixel data.

        Args:
            frame: The sprite frame object.
            frame_idx: Frame index for debug logging.

        """
        try:
            width, height = frame.get_size()
            surface = pygame.Surface((width, height), pygame.SRCALPHA)
            surface.fill((255, 0, 255, 255))
            frame.image = surface

            pixel_data = [(255, 0, 255, 255)] * (width * height)
            frame.set_pixel_data(pixel_data)  # ty: ignore[invalid-argument-type]

            LOG.debug(f'DEBUG: Created default magenta frame for frame {frame_idx}')

        except pygame.error, AttributeError, TypeError, ValueError:
            LOG.exception(f'DEBUG: Failed to create default frame for frame {frame_idx}')

    def _ensure_frames_have_image_data(self, animated_sprite: AnimatedSprite) -> None:
        """Ensure all frames in the animated sprite have proper image data.

        This fixes the issue where film strips show empty gray squares because
        frames don't have their image property properly set.
        """
        if not hasattr(animated_sprite, '_animations') or not animated_sprite._animations:  # type: ignore[reportPrivateUsage]
            return

        LOG.debug('DEBUG: Ensuring frames have image data')

        for anim_name, frames in animated_sprite._animations.items():  # type: ignore[reportPrivateUsage]
            LOG.debug(f"DEBUG: Checking animation '{anim_name}' with {len(frames)} frames")

            for frame_idx, frame in enumerate(frames):
                if not frame:
                    continue

                has_image = hasattr(frame, 'image') and frame.image is not None  # type: ignore[reportUnnecessaryComparison]
                has_pixel_data = (
                    hasattr(frame, 'get_pixel_data') and frame.get_pixel_data() is not None  # type: ignore[reportUnnecessaryComparison]
                )

                LOG.debug(
                    f'DEBUG: Frame {frame_idx}: has_image={has_image},'
                    f' has_pixel_data={has_pixel_data}',
                )

                if not has_image and has_pixel_data:
                    self._create_frame_image_from_pixels(frame, frame_idx)
                elif not has_image and not has_pixel_data:
                    self._create_default_magenta_frame(frame, frame_idx)

    def _select_initial_film_strip(self) -> None:
        """Select the first film strip and set its frame 0 as active on initialization."""
        if not hasattr(self.editor, 'film_strips') or not self.editor.film_strips:
            return

        # Get all animation names in order
        if (
            hasattr(self.editor, 'canvas')
            and self.editor.canvas
            and hasattr(self.editor.canvas, 'animated_sprite')
        ):
            animation_names = list(self.editor.canvas.animated_sprite._animations.keys())  # type: ignore[reportPrivateUsage]
        else:
            animation_names = list(self.editor.film_strips.keys())

        if animation_names:
            first_animation = animation_names[0]

            # Select this animation and frame 0
            if hasattr(self.editor, 'canvas') and self.editor.canvas:
                self.editor.canvas.show_frame(first_animation, 0)

            # Update global selection state
            self.editor.selected_animation = first_animation
            self.editor.selected_frame = 0

            # Mark all film strips as dirty so they redraw with correct selection state
            if hasattr(self.editor, 'film_strips') and self.editor.film_strips:
                for strip_widget in self.editor.film_strips.values():
                    strip_widget.mark_dirty()

    def update_film_strip_visibility(self) -> None:
        """Update which film strips are visible based on scroll offset."""
        if not hasattr(self.editor, 'film_strips') or not self.editor.film_strips:
            return

        # Get all animation names in order
        if (
            hasattr(self.editor, 'canvas')
            and self.editor.canvas
            and hasattr(self.editor.canvas, 'animated_sprite')
        ):
            animation_names = list(self.editor.canvas.animated_sprite._animations.keys())  # type: ignore[reportPrivateUsage]
        else:
            animation_names = list(self.editor.film_strips.keys())

        # Show only the visible range of strips
        start_index = self.editor.film_strip_scroll_offset
        end_index = min(start_index + self.editor.max_visible_strips, len(animation_names))

        # Get canvas position for reference
        film_strip_y_start = (
            self.editor.canvas.rect.y
            if hasattr(self.editor, 'canvas')
            and self.editor.canvas
            and self.editor.canvas.rect is not None  # pyright: ignore[reportUnnecessaryComparison]
            else 0
        )
        strip_height = 145
        strip_spacing = -19

        # Hide all strips first
        for anim_name in self.editor.film_strips:
            if (
                hasattr(self.editor, 'film_strip_sprites')
                and anim_name in self.editor.film_strip_sprites
            ):
                self.editor.film_strip_sprites[anim_name].visible = False

        # Show only the visible strips and position them in fixed slots
        for i in range(start_index, end_index):
            if i < len(animation_names):
                anim_name = animation_names[i]
                if (
                    anim_name in self.editor.film_strips
                    and anim_name in self.editor.film_strip_sprites
                ):
                    film_strip = self.editor.film_strips[anim_name]
                    film_strip_sprite = self.editor.film_strip_sprites[anim_name]

                    # Position in fixed slot (0 or 1)
                    slot_index = i - start_index
                    fixed_y = film_strip_y_start + (slot_index * (strip_height + strip_spacing))

                    # Update positions
                    film_strip.rect.y = fixed_y
                    film_strip_sprite.rect.y = fixed_y
                    film_strip_sprite.visible = True

                    # Mark as dirty to ensure redraw after repositioning
                    film_strip.mark_dirty()

        # Update scroll arrows
        self.update_scroll_arrows()

    def _create_scroll_arrows(self) -> None:
        """Create scroll arrow sprites."""
        if not hasattr(self.editor, 'canvas') or not self.editor.canvas:
            return

        # Get canvas position for reference
        # Position film strip so its left x is 2 pixels to the right of color well's right edge
        if hasattr(self.editor, 'color_well') and self.editor.color_well:
            film_strip_x = (
                self.editor.color_well.rect.right + 1
            )  # Film strip left x = color well right x + 1
        else:
            # Fallback: position to the right of the canvas
            film_strip_x = self.editor.canvas.rect.right + 4  # 4 pixels to the right of canvas edge
        film_strip_y_start = (
            self.editor.canvas.rect.y
            if hasattr(self.editor, 'canvas') and self.editor.canvas
            else 0
        )

        # Create up arrow (above first strip)
        up_arrow_y = film_strip_y_start - 30
        self.editor.scroll_up_arrow = ScrollArrowSprite(
            x=int(film_strip_x) + 10,
            y=int(up_arrow_y),
            width=20,
            height=20,
            groups=self.editor.all_sprites,
            direction='up',
        )

    def update_scroll_arrows(self) -> None:
        """Update scroll arrow visibility based on scroll state."""
        if (
            not hasattr(self.editor, 'canvas')
            or not self.editor.canvas
            or not hasattr(self.editor.canvas, 'animated_sprite')
        ):
            return

        # Show up arrow if we can scroll up
        if hasattr(self.editor, 'scroll_up_arrow') and self.editor.scroll_up_arrow:
            should_show = self.editor.film_strip_scroll_offset > 0
            if self.editor.scroll_up_arrow.visible != should_show:
                self.editor.scroll_up_arrow.visible = should_show
                self.editor.scroll_up_arrow.dirty = 1

    def _add_new_animation(self, insert_after_index: int | None = None) -> None:
        """Add a new animation (film strip) and scroll to it.

        Args:
            insert_after_index: Index to insert the new strip after (None for end)

        """
        if (
            not hasattr(self.editor, 'canvas')
            or not self.editor.canvas
            or not hasattr(self.editor.canvas, 'animated_sprite')
        ):
            return

        # Create a new animation (film strip)
        new_animation_name = f'strip_{len(self.editor.canvas.animated_sprite._animations) + 1}'  # type: ignore[reportPrivateUsage]

        # Create a blank frame for the new animation using the canonical helper
        if hasattr(self.editor, 'canvas') and self.editor.canvas:
            # Get the canvas pixel dimensions (same as original canvas)
            pixels_across = self.editor.canvas.pixels_across
            pixels_tall = self.editor.canvas.pixels_tall

            # Use the shared helper to create a blank frame with proper SRCALPHA support
            animated_frame = self._create_blank_frame(pixels_across, pixels_tall, duration=1.0)

            # Insert the new animation at the specified position
            if insert_after_index is not None:
                # Get current animations as a list to maintain order
                current_animations = list(self.editor.canvas.animated_sprite._animations.items())  # type: ignore[reportPrivateUsage]

                # Create new ordered dict with the new animation inserted
                new_animations = {}
                for i, (anim_name, frames) in enumerate(current_animations):
                    new_animations[anim_name] = frames
                    if i == insert_after_index:
                        # Insert the new animation after this one
                        new_animations[new_animation_name] = [animated_frame]

                # If we didn't insert yet (insert_after_index >= len), add at end
                if insert_after_index >= len(current_animations):
                    new_animations[new_animation_name] = [animated_frame]

                # Replace the animations dict
                self.editor.canvas.animated_sprite._animations = new_animations  # type: ignore[reportPrivateUsage]
            else:
                # Add at the end (original behavior)
                self.editor.canvas.animated_sprite._animations[new_animation_name] = [  # type: ignore[reportPrivateUsage]
                    animated_frame,
                ]

            # Track animation creation for undo/redo
            if hasattr(self.editor, 'film_strip_operation_tracker'):
                # Set flag to prevent frame selection tracking during animation creation
                self._creating_animation = True
                try:
                    # Create animation data for undo/redo
                    animation_data = {
                        'frames': [
                            {
                                'width': animated_frame.image.get_width(),
                                'height': animated_frame.image.get_height(),
                                'pixels': animated_frame.pixels.copy()
                                if hasattr(animated_frame, 'pixels')
                                else [],
                                'duration': animated_frame.duration,
                            },
                        ],
                        'frame_count': 1,
                    }

                    # Track animation addition for undo/redo
                    self.editor.film_strip_operation_tracker.add_animation_added(
                        new_animation_name,
                        animation_data,
                    )
                finally:
                    self._creating_animation = False

            # Add just the new strip incrementally instead of rebuilding all strips
            self._add_single_film_strip(new_animation_name, [animated_frame])

            # Select, scroll to, and activate the new animation
            self._activate_new_animation(new_animation_name)

    def _add_single_film_strip(
        self, anim_name: str, frames: list[SpriteFrame],
    ) -> None:
        """Add a single film strip incrementally without rebuilding all existing strips.

        Args:
            anim_name: Name of the new animation.
            frames: List of frames for the new animation.

        """
        film_strip_x, film_strip_width = self._calculate_film_strip_dimensions()
        film_strip_y_start = (
            self.editor.canvas.rect.y
            if hasattr(self.editor, 'canvas') and self.editor.canvas
            else 0
        )
        strip_height = 180
        strip_spacing = -19
        strip_index = len(self.editor.film_strips)

        self._create_single_film_strip(
            strip_index=strip_index,
            anim_name=anim_name,
            frames=frames,
            film_strip_x=film_strip_x,
            film_strip_y_start=int(film_strip_y_start),
            film_strip_width=film_strip_width,
            strip_height=strip_height,
            strip_spacing=strip_spacing,
            groups=self.editor.all_sprites,  # type: ignore[arg-type]
        )

        self.update_film_strip_visibility()

    def _activate_new_animation(self, new_animation_name: str) -> None:
        """Select, scroll to, and activate a newly created animation.

        Args:
            new_animation_name: Name of the newly created animation to activate

        """
        # Select the 0th frame of the new animation so the user can immediately start editing it
        LOG.debug(
            'BitmapEditorScene: Selecting frame 0 of newly created animation'
            f" '{new_animation_name}'",
        )
        # Set flag to prevent frame selection tracking during animation creation
        self._creating_frame = True
        try:
            self.editor.canvas.show_frame(new_animation_name, 0)

            # Update the undo/redo manager with the current frame for frame-specific operations
            if hasattr(self.editor, 'undo_redo_manager'):
                self.editor.undo_redo_manager.set_current_frame(new_animation_name, 0)
                LOG.debug(
                    'BitmapEditorScene: Updated undo/redo manager to track frame 0 of'
                    f" '{new_animation_name}'",
                )
        finally:
            self._creating_frame = False

        # Scroll to the new animation (last one)
        total_animations = len(self.editor.canvas.animated_sprite._animations)  # type: ignore[reportPrivateUsage]
        max_scroll = max(0, total_animations - self.editor.max_visible_strips)
        self.editor.film_strip_scroll_offset = max_scroll

        # Update visibility and scroll arrows with the new offset
        self.update_film_strip_visibility()
        self.update_scroll_arrows()

        # Select the new frame and notify the canvas
        self.editor.selected_animation = new_animation_name
        self.editor.selected_frame = 0

        # Notify the canvas to switch to the new frame
        if hasattr(self.editor, 'canvas') and self.editor.canvas:
            self._notify_canvas_of_new_animation(new_animation_name)

    def _notify_canvas_of_new_animation(self, new_animation_name: str) -> None:
        """Switch the canvas to display the new animation and force a redraw.

        Args:
            new_animation_name: Name of the animation to switch to

        """
        LOG.debug(f"DEBUG: Switching to new animation '{new_animation_name}', frame 0")
        LOG.debug(
            'DEBUG: Animated sprite current animation:'
            f' {self.editor.canvas.animated_sprite.current_animation}',
        )
        current_frame = self.editor.canvas.animated_sprite.current_frame
        LOG.debug(f'DEBUG: Animated sprite current frame: {current_frame}')
        self.editor.canvas.show_frame(new_animation_name, 0)
        current_anim = self.editor.canvas.animated_sprite.current_animation
        current_frame = self.editor.canvas.animated_sprite.current_frame
        LOG.debug(f'DEBUG: After switch - current animation: {current_anim}')
        LOG.debug(f'DEBUG: After switch - current frame: {current_frame}')
        LOG.debug(
            f'DEBUG: New frame surface size: {self.editor.canvas.animated_sprite.image.get_size()}',
        )

        # Force the animated sprite to update its surface
        self.editor.canvas.animated_sprite._update_surface_and_mark_dirty()  # type: ignore[reportPrivateUsage]

        # Force the canvas to redraw with the new frame
        self.editor.canvas.dirty = 1
        self.editor.canvas.force_redraw()

    def _delete_animation(self, animation_name: str, *, confirmed: bool = False) -> None:
        """Delete an animation (film strip).

        Args:
            animation_name: The name of the animation to delete
            confirmed: If True, skip confirmation dialog and delete immediately

        """
        if (
            not hasattr(self.editor, 'canvas')
            or not self.editor.canvas
            or not hasattr(self.editor.canvas, 'animated_sprite')
        ):
            return

        # Check if we have more than one animation
        animations = list(self.editor.canvas.animated_sprite._animations.keys())  # type: ignore[reportPrivateUsage]
        if len(animations) <= 1:
            self.log.warning('Cannot delete the last remaining animation')
            return

        # Show confirmation dialog unless already confirmed
        if not confirmed:
            self._show_delete_animation_confirmation(animation_name)
            return

        # Remove the animation from the sprite
        if animation_name not in self.editor.canvas.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
            return

        # Get the position of the deleted animation before deletion
        all_animations = list(self.editor.canvas.animated_sprite._animations.keys())  # type: ignore[reportPrivateUsage]
        deleted_index = all_animations.index(animation_name)

        # Capture animation data for undo/redo before deletion
        self._capture_animation_deletion_for_undo(animation_name)

        del self.editor.canvas.animated_sprite._animations[animation_name]  # type: ignore[reportPrivateUsage]
        self.log.info('Deleted animation: %s at index %s', animation_name, deleted_index)

        # Switch to the first remaining animation and select the previous frame
        remaining_animations = list(self.editor.canvas.animated_sprite._animations.keys())  # type: ignore[reportPrivateUsage]
        if remaining_animations:
            self._select_animation_after_deletion(remaining_animations, animation_name)
            return

        # No remaining animations - clear selection
        self._handle_no_remaining_animations(remaining_animations, all_animations, deleted_index)

    def _capture_animation_deletion_for_undo(self, animation_name: str) -> None:
        """Capture animation data for undo/redo before deletion.

        Args:
            animation_name: Name of the animation being deleted

        """
        if not hasattr(self.editor, 'film_strip_operation_tracker'):
            return

        # Get the animation data before deletion
        animation = self.editor.canvas.animated_sprite._animations[animation_name]  # type: ignore[reportPrivateUsage]
        animation_data: dict[str, Any] = {'frames': [], 'frame_count': len(animation)}

        # Capture frame data for each frame in the animation
        for frame in animation:
            frame_data = {
                'width': frame.image.get_width(),
                'height': frame.image.get_height(),
                'pixels': frame.pixels.copy() if hasattr(frame, 'pixels') else [],
                'duration': frame.duration,
            }
            animation_data['frames'].append(frame_data)

        # Track animation deletion for undo/redo
        self.editor.film_strip_operation_tracker.add_animation_deleted(
            animation_name,
            animation_data,
        )

    def _select_animation_after_deletion(
        self,
        remaining_animations: list[str],
        deleted_animation_name: str,
    ) -> None:
        """Select a frame in the first remaining animation after a deletion.

        Args:
            remaining_animations: List of remaining animation names
            deleted_animation_name: Name of the animation that was deleted

        """
        new_animation = remaining_animations[0]

        # Try to select the previous frame in the remaining animation
        # If the deleted animation had frames, try to select a frame at a similar position
        if (
            hasattr(self.editor, 'selected_frame')
            and self.editor.selected_frame is not None
            and self.editor.selected_frame > 0
        ):
            # Select the previous frame if available
            target_frame = max(0, self.editor.selected_frame - 1)
        else:
            # If no previous frame, select the last frame of the remaining animation
            target_frame = max(
                0,
                len(self.editor.canvas.animated_sprite._animations[new_animation]) - 1,  # type: ignore[reportPrivateUsage]
            )

        # Ensure the target frame is within bounds
        max_frame = len(self.editor.canvas.animated_sprite._animations[new_animation]) - 1  # type: ignore[reportPrivateUsage]
        target_frame = min(target_frame, max_frame)

        self.editor.canvas.show_frame(new_animation, target_frame)

        # Update selection state
        self.editor.selected_animation = new_animation
        self.editor.selected_frame = target_frame

        self.log.info(
            "Selected frame %s in animation '%s' after deleting '%s'",
            target_frame,
            new_animation,
            deleted_animation_name,
        )

        # Recreate film strips to reflect the deletion
        self.log.debug(
            'Recreating film strips after animation deletion. Remaining animations: %s',
            remaining_animations,
        )
        self.on_sprite_loaded(self.editor.canvas.animated_sprite)

    def _handle_no_remaining_animations(
        self,
        remaining_animations: list[str],
        all_animations: list[str],
        deleted_index: int,
    ) -> None:
        """Handle post-deletion state when no animations remain (or updating scroll).

        Args:
            remaining_animations: List of remaining animation names (may be empty)
            all_animations: List of all animation names before deletion
            deleted_index: Index of the deleted animation in the original list

        """
        self.log.info('No remaining animations after deletion')
        self.editor.selected_animation = None
        self.editor.selected_frame = None

        # Force update of all film strip widgets to ensure they reflect the deletion
        if hasattr(self.editor, 'film_strip_sprites') and self.editor.film_strip_sprites:
            for film_strip_sprite in self.editor.film_strip_sprites.values():
                if (
                    hasattr(film_strip_sprite, 'film_strip_widget')
                    and film_strip_sprite.film_strip_widget
                ):
                    # Force the film strip widget to update its layout
                    film_strip_sprite.film_strip_widget.update_layout()
                    film_strip_sprite.film_strip_widget._create_film_tabs()  # type: ignore[reportPrivateUsage]
                    film_strip_sprite.film_strip_widget.mark_dirty()
                    film_strip_sprite.dirty = 1

        # Ensure we show up to 2 strips after deletion
        if len(remaining_animations) <= MIN_FILM_STRIPS_FOR_PANEL_POSITIONING:
            # If we have 2 or fewer strips, show them all starting from index 0
            self.editor.film_strip_scroll_offset = 0
        # If we deleted the last strip, show the previous 2 strips
        elif deleted_index == len(all_animations) - 1:
            # We deleted the last strip, show the previous 2 strips
            self.editor.film_strip_scroll_offset = max(0, len(remaining_animations) - 2)
        else:
            # We deleted a strip that wasn't the last, show current and one more
            self.editor.film_strip_scroll_offset = max(0, deleted_index - 1)

        # Update visibility and scroll arrows
        self.update_film_strip_visibility()
        self.update_scroll_arrows()

    def _show_delete_animation_confirmation(self, animation_name: str) -> None:
        """Show confirmation dialog before deleting an animation.

        Args:
            animation_name: Name of the animation to potentially delete

        """
        self.log.info('Showing delete confirmation dialog for animation: %s', animation_name)

        from glitchygames.ui.dialogs import DeleteAnimationDialogScene

        # Create confirmation callback that deletes the animation
        def on_confirm() -> None:
            self.log.info('User confirmed deletion of animation: %s', animation_name)
            self._delete_animation(animation_name, confirmed=True)

        # Create cancel callback that resets tab states
        def on_cancel() -> None:
            self.log.info('User cancelled deletion of animation: %s', animation_name)
            # Reset all film strip tab states to unhighlight the delete button
            if hasattr(self.editor, 'film_strip_sprites'):
                for film_strip_sprite in self.editor.film_strip_sprites.values():
                    if (
                        hasattr(film_strip_sprite, 'film_strip_widget')
                        and film_strip_sprite.film_strip_widget is not None
                    ):
                        film_strip_sprite.film_strip_widget.reset_all_tab_states()
                        film_strip_sprite.dirty = 1  # Force redraw

        # Create the confirmation dialog scene
        confirmation_scene = DeleteAnimationDialogScene(
            previous_scene=self.editor,  # type: ignore[reportArgumentType] # ty: ignore[invalid-argument-type]
            animation_name=animation_name,
            on_confirm_callback=on_confirm,
            on_cancel_callback=on_cancel,
        )

        # Set the dialog's background to the screenshot
        confirmation_scene.background = self.editor.screenshot

        # Switch to the confirmation dialog scene
        self.game_engine.scene_manager.switch_to_scene(confirmation_scene)  # type: ignore[union-attr] # ty: ignore[unresolved-attribute]

    def _show_delete_frame_confirmation(self, animation_name: str, frame_index: int) -> None:
        """Show confirmation dialog before deleting a frame.

        Args:
            animation_name: Name of the animation containing the frame
            frame_index: Index of the frame to potentially delete

        """
        self.log.info(
            'Showing delete frame confirmation dialog for %s[%s]',
            animation_name,
            frame_index,
        )

        from glitchygames.ui.dialogs import DeleteFrameDialogScene

        # Create confirmation callback that deletes the frame
        def on_confirm() -> None:
            self.log.info(
                'User confirmed deletion of frame %s from animation: %s',
                frame_index,
                animation_name,
            )
            # Find the film strip widget for this animation and call its _remove_frame method
            if (
                hasattr(self.editor, 'film_strip_sprites')
                and animation_name in self.editor.film_strip_sprites
            ):
                film_strip_sprite = self.editor.film_strip_sprites[animation_name]
                if (
                    hasattr(film_strip_sprite, 'film_strip_widget')
                    and film_strip_sprite.film_strip_widget is not None
                ):
                    film_strip_sprite.film_strip_widget._remove_frame(animation_name, frame_index)  # type: ignore[reportPrivateUsage]

        # Create cancel callback that resets removal button highlight
        def on_cancel() -> None:
            self.log.info(
                'User cancelled deletion of frame %s from animation: %s',
                frame_index,
                animation_name,
            )
            # Reset the removal button highlight by clearing hover state
            if (
                hasattr(self.editor, 'film_strip_sprites')
                and animation_name in self.editor.film_strip_sprites
            ):
                film_strip_sprite = self.editor.film_strip_sprites[animation_name]
                if (
                    hasattr(film_strip_sprite, 'film_strip_widget')
                    and film_strip_sprite.film_strip_widget is not None
                ):
                    film_strip_sprite.film_strip_widget.hovered_removal_button = None
                    film_strip_sprite.dirty = 1  # Force redraw

        # Create the confirmation dialog scene
        confirmation_scene = DeleteFrameDialogScene(
            previous_scene=self.editor,  # type: ignore[reportArgumentType] # ty: ignore[invalid-argument-type]
            animation_name=animation_name,
            frame_index=frame_index,
            on_confirm_callback=on_confirm,
            on_cancel_callback=on_cancel,
        )

        # Set the dialog's background to the screenshot
        confirmation_scene.background = self.editor.screenshot

        # Switch to the confirmation dialog scene
        self.game_engine.scene_manager.switch_to_scene(confirmation_scene)  # type: ignore[union-attr] # ty: ignore[unresolved-attribute]

    def is_mouse_in_film_strip_area(self, mouse_pos: tuple[int, int]) -> bool:
        """Check if mouse position is within the film strip area.

        Args:
            mouse_pos: (x, y) mouse position

        Returns:
            True if mouse is in film strip area, False otherwise

        """
        if not hasattr(self.editor, 'film_strip_sprites') or not self.editor.film_strip_sprites:
            self.log.debug('No film strip sprites available for mouse pos %s', mouse_pos)
            return False

        # Check if mouse is within any film strip sprite bounds
        for anim_name, film_strip_sprite in self.editor.film_strip_sprites.items():
            if film_strip_sprite.rect.collidepoint(mouse_pos):
                self.log.debug(
                    f"Mouse {mouse_pos} is in film strip '{anim_name}' at {film_strip_sprite.rect}",
                )
                return True

        self.log.debug('Mouse %s is not in any film strip area', mouse_pos)
        return False

    def handle_film_strip_drag_scroll(self, mouse_y: int) -> None:
        """Handle mouse drag scrolling for film strips.

        Args:
            mouse_y: Current mouse Y position

        """
        if not self.editor.is_dragging_film_strips or self.editor.film_strip_drag_start_y is None:
            self.log.debug('Not dragging film strips or no start Y')
            return

        # Calculate drag distance
        drag_distance = mouse_y - self.editor.film_strip_drag_start_y
        start_y = self.editor.film_strip_drag_start_y
        self.log.debug(
            'Drag distance: %s, start Y: %s, current Y: %s',
            drag_distance,
            start_y,
            mouse_y,
        )

        # Convert drag distance to scroll offset change.
        # Each film strip is ~100px tall, so scroll by 1 per 100 pixels.
        strip_height = 100
        scroll_change = int(drag_distance / strip_height)

        # Calculate new scroll offset
        if self.editor.film_strip_drag_start_offset is None:
            return
        new_offset = self.editor.film_strip_drag_start_offset + scroll_change

        # Clamp to valid range
        if (
            hasattr(self.editor, 'canvas')
            and self.editor.canvas
            and hasattr(self.editor.canvas, 'animated_sprite')
            and self.editor.canvas.animated_sprite
        ):
            total_animations = len(self.editor.canvas.animated_sprite._animations)  # type: ignore[reportPrivateUsage]
            max_scroll = max(0, total_animations - self.editor.max_visible_strips)
            new_offset = max(0, min(new_offset, max_scroll))
            self.log.debug(
                'Scroll change: %s, new offset: %s, max scroll: %s',
                scroll_change,
                new_offset,
                max_scroll,
            )

        # Update scroll offset if it changed
        if new_offset != self.editor.film_strip_scroll_offset:
            old_offset = self.editor.film_strip_scroll_offset
            self.log.debug('Updating scroll offset from %s to %s', old_offset, new_offset)
            self.editor.film_strip_scroll_offset = new_offset
            self.update_film_strip_visibility()
            self.update_scroll_arrows()
        else:
            self.log.debug('No scroll offset change needed')

    def setup_film_strips(self) -> None:
        """Set up film strips for the current animated sprite."""
        # Initialize film strip storage
        self.editor.film_strips = {}
        self.editor.film_strip_sprites = {}

        # Create film strips if we have an animated sprite
        LOG.debug('DEBUG: Checking conditions for _create_film_strips')
        LOG.debug(f'DEBUG: hasattr(animated_sprite): {hasattr(self, "animated_sprite")}')
        if (
            hasattr(self.editor, 'canvas')
            and self.editor.canvas
            and hasattr(self.editor.canvas, 'animated_sprite')
            and self.editor.canvas.animated_sprite
        ):
            LOG.debug(
                f'DEBUG: self.editor.canvas.animated_sprite: {self.editor.canvas.animated_sprite}',
            )
            has_anims = hasattr(self.editor.canvas.animated_sprite, '_animations')
            LOG.debug(f'DEBUG: hasattr(_animations): {has_anims}')
            if hasattr(self.editor.canvas.animated_sprite, '_animations'):
                LOG.debug(f'DEBUG: _animations: {self.editor.canvas.animated_sprite._animations}')  # type: ignore[reportPrivateUsage]
                if self.editor.canvas.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
                    LOG.debug('DEBUG: About to call _create_film_strips (first call)')
                    self._create_film_strips(self.editor.all_sprites)  # type: ignore[arg-type]
                    LOG.debug('DEBUG: Finished calling _create_film_strips (first call)')

        # Set up parent scene reference for canvas
        if hasattr(self.editor, 'canvas') and self.editor.canvas:
            self.editor.canvas.parent_scene = self.editor  # type: ignore[reportAttributeAccessIssue] # ty: ignore[invalid-assignment]

    def on_sprite_loaded(self, loaded_sprite: AnimatedSprite) -> None:
        """Handle when a new sprite is loaded - recreate film strips."""
        self.log.debug('=== _on_sprite_loaded called ===')
        LOG.debug(f'DEBUG: _on_sprite_loaded called with sprite: {loaded_sprite}')
        LOG.debug(f'DEBUG: Sprite has animations: {hasattr(loaded_sprite, "_animations")}')
        if hasattr(loaded_sprite, '_animations'):
            LOG.debug(f'DEBUG: Sprite animations: {list(loaded_sprite._animations.keys())}')  # type: ignore[reportPrivateUsage]

        # Preserve controller selections before clearing film strips
        preserved_controller_selections = {}
        if hasattr(self.editor, 'controller_selections'):
            for controller_id, controller_selection in self.editor.controller_selections.items():
                if controller_selection.is_active():
                    animation, frame = controller_selection.get_selection()
                    preserved_controller_selections[controller_id] = (animation, frame)

        # Store preserved selections for use in _create_film_strips
        self._preserved_controller_selections = preserved_controller_selections

        # Clear existing film strips
        LOG.debug(f'DEBUG: Checking film_strips - hasattr: {hasattr(self, "film_strips")}')
        if hasattr(self.editor, 'film_strips') and self.editor.film_strips:
            self.log.debug(f'Clearing {len(self.editor.film_strips)} existing film strips')
            LOG.debug(f'DEBUG: Clearing {len(self.editor.film_strips)} existing film strips')
            for film_strip_sprite in self.editor.film_strip_sprites.values():
                film_strip_sprite.kill()
            self.editor.film_strips.clear()
            self.editor.film_strip_sprites.clear()

        # Create new film strips for the loaded sprite
        if loaded_sprite and loaded_sprite._animations:  # type: ignore[reportPrivateUsage]
            self.log.debug(
                f'Creating new film strips for loaded sprite with {len(loaded_sprite._animations)}'  # type: ignore[reportPrivateUsage]
                f' animations',
            )
            LOG.debug(
                f'DEBUG: _on_sprite_loaded recreating {len(loaded_sprite._animations)} film strips',  # type: ignore[reportPrivateUsage]
            )

            # Update the canvas to use the loaded sprite's animations
            if hasattr(self.editor, 'canvas') and self.editor.canvas:
                self.editor.canvas.animated_sprite = loaded_sprite

                # CRITICAL FIX: Update the scene's animated_sprite reference to the loaded sprite
                # This ensures film strips use the correct sprite data
                self.editor.canvas.animated_sprite = loaded_sprite

                # Check if canvas needs resizing and resize if necessary
                self.editor.canvas._check_and_resize_canvas(loaded_sprite)  # type: ignore[reportPrivateUsage]

                # Set the canvas to show the first frame of the first animation
                first_animation = next(iter(loaded_sprite._animations.keys()))  # type: ignore[reportPrivateUsage]
                self.editor.canvas.current_animation = first_animation
                self.editor.canvas.current_frame = 0

                # Update the canvas interface to sync with the new sprite
                self.editor.canvas.canvas_interface.set_current_frame(first_animation, 0)

                # Force the canvas to redraw with the new sprite
                self.editor.canvas.force_redraw()

                # Note: The loaded sprite will be configured to play by the film strip widgets
                # The canvas should remain static for editing

                # Initialize pixels if needed (for mock sprites)
                self.log.debug(
                    f'Checking canvas pixels: has_pixels={hasattr(self.editor.canvas, "pixels")},'
                    f' is_list={isinstance(getattr(self.editor.canvas, "pixels", None), list)}',
                )
                if not hasattr(self.editor.canvas, 'pixels') or not isinstance(
                    self.editor.canvas.pixels,
                    list,
                ):  # type: ignore[reportUnnecessaryIsInstance]
                    self.log.debug('Initializing canvas pixels')
                    # Create a blank pixel array
                    pixel_count = self.editor.canvas.pixels_across * self.editor.canvas.pixels_tall
                    self.editor.canvas.pixels = [(255, 0, 255, 255)] * pixel_count  # ty: ignore[invalid-assignment]  # Magenta background
                    self.editor.canvas.dirty_pixels = [True] * pixel_count
                    self.log.debug(
                        f'Canvas pixels initialized: len={len(self.editor.canvas.pixels)}',
                    )

            LOG.debug('DEBUG: About to call _create_film_strips (second call)')
            self._create_film_strips(self.editor.all_sprites)  # type: ignore[arg-type]
            LOG.debug('DEBUG: Finished calling _create_film_strips (second call)')
            self.log.debug('Film strips created for loaded sprite')

            # Initialize global selection to first frame of first animation
            first_animation = next(iter(loaded_sprite._animations.keys()))  # type: ignore[reportPrivateUsage]
            self.editor.selected_animation = first_animation
            self.editor.selected_frame = 0
            self.selected_strip = None  # Will be set when first frame is selected
        else:
            self.log.debug('No animations found in loaded sprite')

    def on_film_strip_frame_selected(
        self,
        film_strip_widget: FilmStripWidget,
        animation: str,
        frame: int,
    ) -> None:
        """Handle frame selection in a film strip."""
        # Find the strip name by looking up the film_strip_widget in film_strips
        strip_name = 'unknown'
        if hasattr(self.editor, 'film_strips') and self.editor.film_strips:
            for name, strip in self.editor.film_strips.items():
                if strip == film_strip_widget:
                    strip_name = name
                    break
        LOG.debug(
            f"BitmapEditorScene: Frame selected - {animation}[{frame}] in strip '{strip_name}'",
        )

        # Update canvas to show the selected frame
        if hasattr(self.editor, 'canvas') and self.editor.canvas:
            LOG.debug(f'BitmapEditorScene: Updating canvas to show {animation}[{frame}]')
            self.editor.canvas.show_frame(animation, frame)

        # Store global selection state
        self.editor.selected_animation = animation
        self.editor.selected_frame = frame

        # Update keyboard selection in all film strips using SelectionManager
        # OLD SYSTEM REMOVED - Using new multi-controller system instead
        # OLD SYSTEM DISABLED - Using new multi-controller system instead
        # The old SelectionManager system has been replaced by the new multi-controller system
        # Update film strip selection state
        self.update_film_strip_selection_state()
        self.selected_strip = film_strip_widget

        # OLD SYSTEM REMOVED - Using new multi-controller system instead

    def _get_sprite_to_update_for_rename(self) -> AnimatedSprite | None:
        """Determine which sprite object to update for animation rename.

        Prefers canvas.animated_sprite over self.editor.canvas.animated_sprite.

        Returns:
            The sprite object to update, or None if no suitable sprite found.

        """
        if (
            hasattr(self.editor, 'canvas')
            and self.editor.canvas
            and hasattr(self.editor.canvas, 'animated_sprite')
        ):
            self.log.debug('BitmapEditorScene: Using canvas.animated_sprite for rename')
            return self.editor.canvas.animated_sprite
        if (
            hasattr(self.editor, 'canvas')
            and self.editor.canvas
            and hasattr(self.editor.canvas, 'animated_sprite')
            and self.editor.canvas.animated_sprite
        ):
            self.log.debug('BitmapEditorScene: Using self.editor.canvas.animated_sprite for rename')
            return self.editor.canvas.animated_sprite
        return None

    def _rename_animation_in_sprite(
        self,
        sprite_to_update: AnimatedSprite,
        old_name: str,
        new_name: str,
    ) -> None:
        """Rename an animation within an animated sprite's internal data structures.

        Args:
            sprite_to_update: The animated sprite whose animation dict should be updated.
            old_name: The current animation name.
            new_name: The new animation name.

        """
        frames = sprite_to_update._animations[old_name]  # type: ignore[reportPrivateUsage]
        del sprite_to_update._animations[old_name]  # type: ignore[reportPrivateUsage]
        sprite_to_update._animations[new_name] = frames  # type: ignore[reportPrivateUsage]
        # Maintain animation order list if present
        if hasattr(sprite_to_update, '_animation_order'):
            order = list(getattr(sprite_to_update, '_animation_order', []))
            sprite_to_update._animation_order = [  # type: ignore[attr-defined]
                (new_name if name == old_name else name) for name in order
            ]

    def _rename_film_strip_widget_internals(
        self,
        strip_widget: FilmStripWidget,
        old_name: str,
        new_name: str,
    ) -> None:
        """Update a FilmStripWidget's internal animated_sprite after animation rename.

        Args:
            strip_widget: The FilmStripWidget to update.
            old_name: The old animation name.
            new_name: The new animation name.

        """
        # CRITICAL: Update the FilmStripWidget's own animated_sprite
        if not (
            hasattr(strip_widget, 'animated_sprite')
            and strip_widget.animated_sprite
            and old_name in strip_widget.animated_sprite._animations  # type: ignore[reportPrivateUsage]
        ):
            return

        # Rename in the widget's sprite
        widget_frames = strip_widget.animated_sprite._animations[old_name]  # type: ignore[reportPrivateUsage]
        del strip_widget.animated_sprite._animations[old_name]  # type: ignore[reportPrivateUsage]
        strip_widget.animated_sprite._animations[new_name] = widget_frames  # type: ignore[reportPrivateUsage]

        # Update animation order
        if hasattr(strip_widget.animated_sprite, '_animation_order'):
            strip_widget.animated_sprite._animation_order = [new_name]  # type: ignore[reportPrivateUsage]

            # Update frame manager
            if strip_widget.animated_sprite.frame_manager.current_animation == old_name:
                strip_widget.animated_sprite.frame_manager.current_animation = new_name

            self.log.debug(
                "Updated FilmStripWidget's internal sprite: '%s' -> '%s'",
                old_name,
                new_name,
            )

    def _update_film_strip_layout_after_rename(
        self,
        strip_widget: FilmStripWidget,
        new_name: str,
    ) -> None:
        """Recalculate film strip layout and sprite dimensions after rename.

        Args:
            strip_widget: The FilmStripWidget to update.
            new_name: The new animation name.

        """
        try:
            # Recalculate layout to update animation_layouts with new name
            strip_widget.update_layout()
            # Update bounding box (rect) after layout recalculation
            if hasattr(strip_widget, '_update_height'):
                strip_widget._update_height()  # type: ignore[reportPrivateUsage]
            # Update film strip sprite rect if it exists
            if (
                hasattr(self.editor, 'film_strip_sprites')
                and new_name in self.editor.film_strip_sprites
            ):
                film_strip_sprite = self.editor.film_strip_sprites[new_name]
                film_strip_sprite.rect.height = strip_widget.rect.height
                film_strip_sprite.rect.width = strip_widget.rect.width
                # Update sprite surface size
                film_strip_sprite.image = pygame.Surface(
                    (strip_widget.rect.width, strip_widget.rect.height),
                    pygame.SRCALPHA,
                )
                film_strip_sprite.dirty = 1
        except (AttributeError, KeyError, TypeError, pygame.error) as e:
            self.log.warning('FilmStripWidget layout update failed after rename: %s', e)
        # Ensure redraw
        if hasattr(strip_widget, 'mark_dirty'):
            strip_widget.mark_dirty()

    def _rename_in_film_strips_dict(self, old_name: str, new_name: str) -> None:
        """Rename an animation in the film_strips and film_strip_sprites dictionaries.

        Args:
            old_name: The old animation name.
            new_name: The new animation name.

        """
        if not (hasattr(self.editor, 'film_strips') and old_name in self.editor.film_strips):
            return

        self.editor.film_strips[new_name] = self.editor.film_strips[old_name]
        del self.editor.film_strips[old_name]

        # Update the specific FilmStripWidget's internal state
        strip_widget = self.editor.film_strips[new_name]
        if getattr(strip_widget, 'current_animation', None) == old_name:
            strip_widget.current_animation = new_name

        self._rename_film_strip_widget_internals(strip_widget, old_name, new_name)

        # Update film_strip_sprites dictionary (keyed by animation name)
        if (
            hasattr(self.editor, 'film_strip_sprites')
            and old_name in self.editor.film_strip_sprites
        ):
            self.editor.film_strip_sprites[new_name] = self.editor.film_strip_sprites[old_name]
            del self.editor.film_strip_sprites[old_name]
            self.log.debug("Updated film_strip_sprites dict: '%s' -> '%s'", old_name, new_name)

        self._update_film_strip_layout_after_rename(strip_widget, new_name)

    def _mark_all_film_strips_dirty(self) -> None:
        """Mark all film strips and their sprites as dirty for redraw."""
        if not (hasattr(self.editor, 'film_strips') and self.editor.film_strips):
            return

        for strip_name, strip_widget in self.editor.film_strips.items():
            strip_widget.mark_dirty()
            # Mark the film strip sprite as dirty=2 for full surface blit
            if (
                hasattr(self.editor, 'film_strip_sprites')
                and strip_name in self.editor.film_strip_sprites
            ):
                self.editor.film_strip_sprites[strip_name].dirty = 1

            # Mark the animated sprite as dirty to ensure animation updates
            if hasattr(strip_widget, 'animated_sprite') and strip_widget.animated_sprite:
                strip_widget.animated_sprite.dirty = 1

    def on_animation_rename(self, old_name: str, new_name: str) -> None:
        """Handle animation name changes from film strip editing."""
        self.log.debug("BitmapEditorScene: Animation renamed from '%s' to '%s'", old_name, new_name)

        sprite_to_update = self._get_sprite_to_update_for_rename()

        # Update the animated sprite's animation names
        if sprite_to_update:
            if old_name not in sprite_to_update._animations:  # type: ignore[reportPrivateUsage]
                self.log.warning(
                    "BitmapEditorScene: Animation '%s' not found for renaming",
                    old_name,
                )
            else:
                self._rename_animation_in_sprite(sprite_to_update, old_name, new_name)

                # Update current animation if it was the renamed one
                if (
                    hasattr(self.editor, 'selected_animation')
                    and self.editor.selected_animation == old_name
                ):
                    self.editor.selected_animation = new_name

                self._rename_in_film_strips_dict(old_name, new_name)

                # Force redraw of all film strips
                self.update_film_strips_for_animated_sprite_update()

                self.log.debug(
                    "BitmapEditorScene: Successfully renamed animation '%s' to '%s'",
                    old_name,
                    new_name,
                )

        # Mark all film strips as dirty so they redraw with correct selection state
        self._mark_all_film_strips_dirty()

    def on_frame_inserted(self, animation: str, frame_index: int) -> None:
        """Handle when a new frame is inserted into an animation.

        Args:
            animation: The animation name where the frame was inserted
            frame_index: The index where the frame was inserted

        """
        LOG.debug(f'BitmapEditorScene: Frame inserted at {animation}[{frame_index}]')

        # Update canvas to show the new frame if it's the current animation
        if (
            hasattr(self.editor, 'canvas')
            and self.editor.canvas
            and self.editor.selected_animation == animation
        ):
            LOG.debug(
                f'BitmapEditorScene: Updating canvas to show new frame {animation}[{frame_index}]',
            )
            self.editor.canvas.show_frame(animation, frame_index)
            self.editor.selected_frame = frame_index

        # Update the selected_frame in the film strip widget for the current animation
        if hasattr(self.editor, 'film_strips') and self.editor.film_strips:
            for strip_name, strip_widget in self.editor.film_strips.items():
                if strip_name == animation:
                    # Update the selected_frame in the film strip widget
                    strip_widget.selected_frame = frame_index
                    LOG.debug(
                        f'BitmapEditorScene: Updated film strip {strip_name} selected_frame to'
                        f' {frame_index}',
                    )

                strip_widget.mark_dirty()
                # Mark the film strip sprite as dirty=2 for full surface blit
                if (
                    hasattr(self.editor, 'film_strip_sprites')
                    and strip_name in self.editor.film_strip_sprites
                ):
                    self.editor.film_strip_sprites[strip_name].dirty = 1

                # Mark the animated sprite as dirty to ensure animation updates
                if hasattr(strip_widget, 'animated_sprite') and strip_widget.animated_sprite:
                    strip_widget.animated_sprite.dirty = 1

    def _adjust_selected_frame_after_removal(self, animation: str, _frame_index: int) -> None:
        """Adjust the selected frame index after a frame removal and update the canvas.

        Args:
            animation: The animation name where the frame was removed.
            _frame_index: The index of the removed frame (unused, kept for API compatibility).

        """
        # If we removed a frame before or at the current position, adjust the selected frame
        if self.editor.selected_frame is not None and self.editor.selected_frame > 0:
            self.editor.selected_frame -= 1
        else:
            # If we were at frame 0 and removed it, stay at frame 0 (which is now the next
            # frame)
            self.editor.selected_frame = 0

        # Ensure the selected frame is within bounds
        if (
            hasattr(self.editor, 'canvas')
            and self.editor.canvas
            and hasattr(self.editor.canvas, 'animated_sprite')
            and animation in self.editor.canvas.animated_sprite._animations  # type: ignore[reportPrivateUsage]
        ):
            max_frame = len(self.editor.canvas.animated_sprite._animations[animation]) - 1  # type: ignore[reportPrivateUsage]
            if self.editor.selected_frame > max_frame:
                self.editor.selected_frame = max(0, max_frame)

        # Update canvas to show the adjusted frame
        if hasattr(self.editor, 'canvas') and self.editor.canvas:
            LOG.debug(
                'BitmapEditorScene: Updating canvas to show adjusted frame'
                f' {animation}[{self.editor.selected_frame}]',
            )
            try:
                self.editor.canvas.show_frame(animation, self.editor.selected_frame)
            except (IndexError, KeyError) as e:
                LOG.debug(f'BitmapEditorScene: Error updating canvas: {e}')
                # Fallback to frame 0 if there's an error
                self.editor.selected_frame = 0
                if (
                    animation in self.editor.canvas.animated_sprite._animations  # type: ignore[reportPrivateUsage]
                    and len(self.editor.canvas.animated_sprite._animations[animation]) > 0  # type: ignore[reportPrivateUsage]
                ):
                    self.editor.canvas.show_frame(animation, 0)

    def on_frame_removed(self, animation: str, frame_index: int) -> None:
        """Handle when a frame is removed from an animation.

        Args:
            animation: The animation name where the frame was removed
            frame_index: The index where the frame was removed

        """
        LOG.debug(f'BitmapEditorScene: Frame removed at {animation}[{frame_index}]')

        # Adjust selected frame if necessary
        if (
            hasattr(self.editor, 'selected_animation')
            and self.editor.selected_animation == animation
            and hasattr(self.editor, 'selected_frame')
            and self.editor.selected_frame is not None
            and self.editor.selected_frame >= frame_index
        ):
            self._adjust_selected_frame_after_removal(animation, frame_index)

        # Update the selected_frame in the film strip widget for the current animation
        if hasattr(self.editor, 'film_strips') and self.editor.film_strips:
            for strip_name, strip_widget in self.editor.film_strips.items():
                if strip_name == animation:
                    # Update the selected_frame in the film strip widget
                    strip_widget.selected_frame = (  # type: ignore[attr-defined]
                        self.editor.selected_frame if hasattr(self.editor, 'selected_frame') else 0
                    )
                    LOG.debug(
                        f'BitmapEditorScene: Updated film strip {strip_name} selected_frame to'
                        f' {strip_widget.selected_frame}',
                    )

                strip_widget.mark_dirty()
                # Mark the film strip sprite as dirty=2 for full surface blit
                if (
                    hasattr(self.editor, 'film_strip_sprites')
                    and strip_name in self.editor.film_strip_sprites
                ):
                    self.editor.film_strip_sprites[strip_name].dirty = 1

                # Mark the animated sprite as dirty to ensure animation updates
                if hasattr(strip_widget, 'animated_sprite') and strip_widget.animated_sprite:
                    strip_widget.animated_sprite.dirty = 1

    def _copy_current_frame(self) -> bool:
        """Copy the currently selected frame from the active film strip.

        Returns:
            bool: True if the condition is met, False otherwise.

        """
        LOG.debug('BitmapEditorScene: [SCENE COPY] _copy_current_frame called')

        if not hasattr(self.editor, 'film_strips') or not self.editor.film_strips:
            LOG.debug('BitmapEditorScene: [SCENE COPY] No film strips available for copying')
            return False

        LOG.debug(
            f'BitmapEditorScene: [SCENE COPY] Found {len(self.editor.film_strips)} film strips',
        )
        LOG.debug(
            'BitmapEditorScene: [SCENE COPY] Looking for animation:'
            f' {getattr(self.editor, "selected_animation", "None")}',
        )

        # Find the active film strip (the one with the current animation)
        active_film_strip = None
        if hasattr(self.editor, 'selected_animation') and self.editor.selected_animation:
            for strip_name, film_strip in self.editor.film_strips.items():
                LOG.debug(
                    f"BitmapEditorScene: [SCENE COPY] Checking film strip '{strip_name}' with"
                    f" animation '{getattr(film_strip, 'current_animation', 'None')}'",
                )
                if (
                    hasattr(film_strip, 'current_animation')
                    and film_strip.current_animation == self.editor.selected_animation
                ):
                    active_film_strip = film_strip
                    LOG.debug(
                        f"BitmapEditorScene: [SCENE COPY] Found active film strip: '{strip_name}'",
                    )
                    break

        if not active_film_strip:
            LOG.debug('BitmapEditorScene: [SCENE COPY] No active film strip found for copying')
            return False

        LOG.debug('BitmapEditorScene: [SCENE COPY] Calling film strip copy method')
        # Call the film strip's copy method
        return active_film_strip.copy_current_frame()

    def _paste_to_current_frame(self) -> bool:
        """Paste the copied frame to the currently selected frame in the active film strip.

        Returns:
            bool: True if the condition is met, False otherwise.

        """
        LOG.debug('BitmapEditorScene: [SCENE PASTE] _paste_to_current_frame called')

        if not hasattr(self.editor, 'film_strips') or not self.editor.film_strips:
            LOG.debug('BitmapEditorScene: [SCENE PASTE] No film strips available for pasting')
            return False

        LOG.debug(
            f'BitmapEditorScene: [SCENE PASTE] Found {len(self.editor.film_strips)} film strips',
        )
        LOG.debug(
            'BitmapEditorScene: [SCENE PASTE] Looking for animation:'
            f' {getattr(self.editor, "selected_animation", "None")}',
        )

        # Find the active film strip (the one with the current animation)
        active_film_strip = None
        if hasattr(self.editor, 'selected_animation') and self.editor.selected_animation:
            for strip_name, film_strip in self.editor.film_strips.items():
                LOG.debug(
                    f"BitmapEditorScene: [SCENE PASTE] Checking film strip '{strip_name}' with"
                    f" animation '{getattr(film_strip, 'current_animation', 'None')}'",
                )
                if (
                    hasattr(film_strip, 'current_animation')
                    and film_strip.current_animation == self.editor.selected_animation
                ):
                    active_film_strip = film_strip
                    LOG.debug(
                        f"BitmapEditorScene: [SCENE PASTE] Found active film strip: '{strip_name}'",
                    )
                    break

        if not active_film_strip:
            LOG.debug('BitmapEditorScene: [SCENE PASTE] No active film strip found for pasting')
            return False

        LOG.debug('BitmapEditorScene: [SCENE PASTE] Calling film strip paste method')
        # Call the film strip's paste method
        return active_film_strip.paste_to_current_frame()

    def update_film_strip_selection_state(self) -> None:
        """Update the selection state of all film strips based on current selection."""
        if not hasattr(self.editor, 'film_strips') or not self.editor.film_strips:
            return

        current_animation = getattr(self.editor, 'selected_animation', '')
        current_frame = getattr(self.editor, 'selected_frame', 0)

        for strip_name, strip_widget in self.editor.film_strips.items():
            # Each film strip should have its current_animation set to its own animation name
            # for proper sprocket rendering
            strip_widget.current_animation = strip_name

            if strip_name == current_animation:
                # This is the selected strip - mark it as selected
                strip_widget.is_selected = True
                strip_widget.selected_frame = current_frame
                LOG.debug(
                    f'BitmapEditorScene: Marking strip {strip_name} as selected with frame'
                    f' {current_frame}',
                )
            else:
                # This is not the selected strip - deselect it but preserve its selected_frame
                strip_widget.is_selected = False
                # Don't reset selected_frame - each strip maintains its own selection
                LOG.debug(
                    f'BitmapEditorScene: Deselecting strip {strip_name} (preserving'
                    f' selected_frame={strip_widget.selected_frame})',
                )

            # Mark the strip as dirty to trigger full redraw
            strip_widget.mark_dirty()
            # Also mark the film strip sprite as dirty=2 for full surface blit
            if (
                hasattr(self.editor, 'film_strip_sprites')
                and strip_name in self.editor.film_strip_sprites
            ):
                self.editor.film_strip_sprites[strip_name].dirty = 1

            # Mark the animated sprite as dirty to ensure animation updates
            if hasattr(strip_widget, 'animated_sprite') and strip_widget.animated_sprite:
                strip_widget.animated_sprite.dirty = 1

    def switch_to_film_strip(self, animation_name: str, frame: int = 0) -> None:
        """Switch to a specific film strip and frame, deselecting the previous one."""
        LOG.debug(f'BitmapEditorScene: Switching to film strip {animation_name}[{frame}]')

        # Deselect the current strip if there is one
        if hasattr(self, 'selected_strip') and self.selected_strip:
            LOG.debug('BitmapEditorScene: Deselecting current strip')
            self.selected_strip.is_selected = False
            self.selected_strip.current_animation = ''
            self.selected_strip.current_frame = 0
            self.selected_strip.mark_dirty()
            # Mark the film strip sprite as dirty=2 for full surface blit
            if hasattr(self.editor, 'film_strip_sprites'):
                for strip_sprite in self.editor.film_strip_sprites.values():
                    if strip_sprite.film_strip_widget == self.selected_strip:
                        strip_sprite.dirty = 1
                        break

            # Mark the animated sprite as dirty to ensure animation updates
            if (
                hasattr(self.selected_strip, 'animated_sprite')
                and self.selected_strip.animated_sprite
            ):
                self.selected_strip.animated_sprite.dirty = 1

        # Select the new strip
        if hasattr(self.editor, 'film_strips') and animation_name in self.editor.film_strips:
            new_strip = self.editor.film_strips[animation_name]
            new_strip.is_selected = True
            # Set current_animation to the strip's own animation name for sprocket rendering
            new_strip.current_animation = animation_name
            new_strip.current_frame = frame
            new_strip.mark_dirty()

            # Mark the new film strip sprite as dirty=2 for full surface blit
            if (
                hasattr(self.editor, 'film_strip_sprites')
                and animation_name in self.editor.film_strip_sprites
            ):
                self.editor.film_strip_sprites[animation_name].dirty = 1

            # Mark the animated sprite as dirty to ensure animation updates
            if hasattr(new_strip, 'animated_sprite') and new_strip.animated_sprite:
                new_strip.animated_sprite.dirty = 1

            # Update global selection state
            self.editor.selected_animation = animation_name
            self.editor.selected_frame = frame
            self.selected_strip = new_strip

            # Update canvas to show the selected frame
            if hasattr(self.editor, 'canvas') and self.editor.canvas:
                self.editor.canvas.show_frame(animation_name, frame)

            LOG.debug(f'BitmapEditorScene: Selected strip {animation_name} with frame {frame}')
        else:
            LOG.debug(f'BitmapEditorScene: Film strip {animation_name} not found')

    def scroll_to_current_animation(self) -> None:
        """Scroll the film strip view to show the selected animation.

        Shows the currently selected animation if it's not visible.
        """
        if (
            not hasattr(self.editor, 'canvas')
            or not self.editor.canvas
            or not hasattr(self.editor.canvas, 'animated_sprite')
        ):
            return

        # Get the current animation name
        current_animation = self.editor.canvas.current_animation
        if not current_animation:
            return

        # Get all animation names in order
        animation_names = list(self.editor.canvas.animated_sprite._animations.keys())  # type: ignore[reportPrivateUsage]
        if current_animation not in animation_names:
            return

        # Find the index of the current animation
        current_index = animation_names.index(current_animation)

        # Calculate the scroll offset needed to show this animation
        # We want to show the current animation in the visible area
        if current_index < self.editor.film_strip_scroll_offset:
            # Current animation is above the visible area, scroll up
            self.editor.film_strip_scroll_offset = current_index
            self.log.debug(
                'Scrolling up to show animation %s at index %s',
                current_animation,
                current_index,
            )
        elif current_index >= self.editor.film_strip_scroll_offset + self.editor.max_visible_strips:
            # Current animation is below the visible area, scroll down
            self.editor.film_strip_scroll_offset = (
                current_index - self.editor.max_visible_strips + 1
            )
            self.log.debug(
                'Scrolling down to show animation %s at index %s',
                current_animation,
                current_index,
            )
        else:
            # Current animation is already visible, no scrolling needed
            self.log.debug(
                'Animation %s is already visible at index %s',
                current_animation,
                current_index,
            )
            return

        # Update visibility and scroll arrows
        self.update_film_strip_visibility()
        self.update_scroll_arrows()

        # Update the film strip selection to show the current frame
        self._update_film_strip_selection()

    def scroll_film_strips_up(self) -> None:
        """Scroll film strips up (show earlier animations)."""
        if (
            hasattr(self.editor, 'film_strip_scroll_offset')
            and self.editor.film_strip_scroll_offset > 0
        ):
            self.editor.film_strip_scroll_offset -= 1
            self.update_film_strip_visibility()

    def _select_first_visible_film_strip(self) -> None:
        """Select the first visible film strip and set its frame 0 as active."""
        if not hasattr(self.editor, 'film_strips') or not self.editor.film_strips:
            return

        # Get all animation names in order
        if (
            hasattr(self.editor, 'canvas')
            and self.editor.canvas
            and hasattr(self.editor.canvas, 'animated_sprite')
        ):
            animation_names = list(self.editor.canvas.animated_sprite._animations.keys())  # type: ignore[reportPrivateUsage]
        else:
            animation_names = list(self.editor.film_strips.keys())

        # Find the first visible animation
        start_index = self.editor.film_strip_scroll_offset
        if start_index < len(animation_names):
            first_visible_animation = animation_names[start_index]

            # Select this animation and frame 0
            if hasattr(self.editor, 'canvas') and self.editor.canvas:
                self.editor.canvas.show_frame(first_visible_animation, 0)

            # Update the film strip widget to show the correct frame selection
            if first_visible_animation in self.editor.film_strips:
                film_strip_widget = self.editor.film_strips[first_visible_animation]
                film_strip_widget.set_current_frame(first_visible_animation, 0)

            # Update global selection state
            self.editor.selected_animation = first_visible_animation
            self.editor.selected_frame = 0

            # Mark all film strips as dirty so they redraw with correct selection state
            if hasattr(self.editor, 'film_strips') and self.editor.film_strips:
                for strip_widget in self.editor.film_strips.values():
                    strip_widget.mark_dirty()

    def _navigate_frame(self, direction: int) -> None:
        """Navigate to the next or previous frame in the current animation.

        Args:
            direction: 1 for next frame, -1 for previous frame

        """
        if (
            not hasattr(self.editor, 'canvas')
            or not self.editor.canvas
            or not hasattr(self.editor.canvas, 'animated_sprite')
        ):
            LOG.debug(
                'BitmapEditorScene: No canvas or animated sprite available for frame navigation',
            )
            return

        current_animation = self.editor.canvas.current_animation
        if not current_animation:
            LOG.debug('BitmapEditorScene: No current animation selected for frame navigation')
            return

        # Get the current frame index
        current_frame = getattr(self.editor, 'selected_frame', 0)

        # Get all frames for the current animation
        if current_animation not in self.editor.canvas.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
            LOG.debug(
                f"BitmapEditorScene: Animation '{current_animation}' not found in animated sprite",
            )
            return

        frames = self.editor.canvas.animated_sprite._animations[current_animation]  # type: ignore[reportPrivateUsage]
        total_frames = len(frames)

        if total_frames == 0:
            LOG.debug(f"BitmapEditorScene: Animation '{current_animation}' has no frames")
            return

        # Calculate new frame index with wrapping
        new_frame = (current_frame + direction) % total_frames

        LOG.debug(
            f'BitmapEditorScene: Navigating from frame {current_frame} to frame {new_frame} in'
            f" animation '{current_animation}' (total frames: {total_frames})",
        )

        # Update the canvas to show the new frame
        self.editor.canvas.show_frame(current_animation, new_frame)

        # Update the film strip widget to show the correct frame selection
        if hasattr(self.editor, 'film_strips') and current_animation in self.editor.film_strips:
            film_strip_widget = self.editor.film_strips[current_animation]
            film_strip_widget.set_current_frame(current_animation, new_frame)
            film_strip_widget.mark_dirty()

        # Update global selection state
        self.editor.selected_animation = current_animation
        self.editor.selected_frame = new_frame

        # Mark the film strip sprite as dirty for redraw
        if (
            hasattr(self.editor, 'film_strip_sprites')
            and current_animation in self.editor.film_strip_sprites
        ):
            self.editor.film_strip_sprites[current_animation].dirty = 1

    def scroll_film_strips_down(self) -> None:
        """Scroll film strips down (show later animations)."""
        if (
            hasattr(self.editor, 'canvas')
            and self.editor.canvas
            and hasattr(self.editor.canvas, 'animated_sprite')
        ):
            total_animations = len(self.editor.canvas.animated_sprite._animations)  # type: ignore[reportPrivateUsage]
            max_scroll = max(0, total_animations - self.editor.max_visible_strips)

            # Check if there are more strips below that we can scroll to
            if (
                hasattr(self.editor, 'film_strip_scroll_offset')
                and self.editor.film_strip_scroll_offset < max_scroll
            ):
                self.editor.film_strip_scroll_offset += 1
                self.update_film_strip_visibility()

    def _select_last_visible_film_strip(self) -> None:
        """Select the last visible film strip and set its frame 0 as active."""
        if not hasattr(self.editor, 'film_strips') or not self.editor.film_strips:
            return

        # Get all animation names in order
        if (
            hasattr(self.editor, 'canvas')
            and self.editor.canvas
            and hasattr(self.editor.canvas, 'animated_sprite')
        ):
            animation_names = list(self.editor.canvas.animated_sprite._animations.keys())  # type: ignore[reportPrivateUsage]
        else:
            animation_names = list(self.editor.film_strips.keys())

        # Find the last visible animation
        start_index = self.editor.film_strip_scroll_offset
        end_index = min(start_index + self.editor.max_visible_strips, len(animation_names))

        if end_index > start_index:
            last_visible_animation = animation_names[end_index - 1]

            # Select this animation and frame 0
            if hasattr(self.editor, 'canvas') and self.editor.canvas:
                self.editor.canvas.show_frame(last_visible_animation, 0)

            # Update the film strip widget to show the correct frame selection
            if last_visible_animation in self.editor.film_strips:
                film_strip_widget = self.editor.film_strips[last_visible_animation]
                film_strip_widget.set_current_frame(last_visible_animation, 0)

            # Update global selection state
            self.editor.selected_animation = last_visible_animation
            self.editor.selected_frame = 0

            # Mark all film strips as dirty so they redraw with correct selection state
            if hasattr(self.editor, 'film_strips') and self.editor.film_strips:
                for strip_widget in self.editor.film_strips.values():
                    strip_widget.mark_dirty()

    def update_film_strips_for_frame(self, animation: str, frame: int) -> None:
        """Update film strips when frame changes."""
        self.log.debug(
            '_update_film_strips_for_frame called: animation=%s, frame=%s',
            animation,
            frame,
        )
        if hasattr(self.editor, 'film_strips') and self.editor.film_strips:
            strip_keys = list(self.editor.film_strips.keys())
            self.log.debug(f'Found {len(self.editor.film_strips)} film strips: {strip_keys}')
            # Update the film strip for the current animation
            if animation in self.editor.film_strips:
                film_strip = self.editor.film_strips[animation]
                self.log.debug('Updating film strip for animation %s', animation)
                # Directly update the selection without triggering handlers to avoid infinite loops
                film_strip.current_animation = animation
                film_strip.current_frame = frame
                film_strip.update_scroll_for_frame(frame)
                film_strip.update_layout()
                film_strip.mark_dirty()
                self.log.debug(
                    f'Film strip updated: current_animation={film_strip.current_animation},'
                    f' current_frame={film_strip.current_frame}',
                )
            else:
                self.log.debug('Animation %s not found in film strips', animation)

            # Mark visible film strip sprites as dirty
            if hasattr(self.editor, 'film_strip_sprites') and self.editor.film_strip_sprites:
                for film_strip_sprite in self.editor.film_strip_sprites.values():
                    if film_strip_sprite.visible:
                        film_strip_sprite.dirty = 1

    def _update_film_strips_for_pixel_update(self) -> None:
        """Update visible film strips when pixel data changes."""
        film_strip_sprites = getattr(self.editor, 'film_strip_sprites', {})

        for strip_name, film_strip in getattr(self.editor, 'film_strips', {}).items():
            strip_sprite = film_strip_sprites.get(strip_name)
            if strip_sprite and not strip_sprite.visible:
                continue
            film_strip.mark_dirty()

        # Film strip animated sprites should use original animation frames, not canvas content

    def update_film_strips_for_animated_sprite_update(self) -> None:
        """Update visible film strips when animated sprite frame data changes."""
        film_strip_sprites = getattr(self.editor, 'film_strip_sprites', {})

        for strip_name, film_strip in getattr(self.editor, 'film_strips', {}).items():
            strip_sprite = film_strip_sprites.get(strip_name)
            if strip_sprite and not strip_sprite.visible:
                continue
            film_strip.update_layout()
            film_strip.mark_dirty()

    def _update_film_strip_selection(self) -> None:
        """Update film strip selection to show the current animation and frame."""
        if not hasattr(self.editor, 'canvas') or not self.editor.canvas:
            return

        # Get the current animation and frame
        current_animation = self.editor.canvas.current_animation
        current_frame = self.editor.canvas.current_frame

        # Update all film strips
        if hasattr(self.editor, 'film_strips') and self.editor.film_strips:
            for strip_name, strip_widget in self.editor.film_strips.items():
                if strip_name == current_animation:
                    # This is the current animation - set it as selected
                    strip_widget.set_current_frame(current_animation, current_frame)
                    # Call the selection handler to update the scene state
                    self.on_film_strip_frame_selected(
                        strip_widget,
                        current_animation,
                        current_frame,
                    )
                else:
                    # This is not the current animation - clear selection
                    strip_widget.current_animation = ''
                    strip_widget.current_frame = 0
                    strip_widget.mark_dirty()

    def clear_film_strips_for_new_canvas(self) -> None:
        """Remove existing film strips and recreate for new canvas."""
        if hasattr(self.editor, 'film_strips') and self.editor.film_strips:
            self.log.info('Clearing existing film strips for new canvas')
            for film_strip_sprite in self.editor.film_strip_sprites.values():
                if hasattr(film_strip_sprite, 'groups') and film_strip_sprite.groups():
                    for group in film_strip_sprite.groups():
                        group.remove(film_strip_sprite)
            self.editor.film_strips.clear()
            self.editor.film_strip_sprites.clear()

        self.log.info('Creating new film strip for new canvas')
        self._create_film_strips(self.editor.all_sprites)  # type: ignore[arg-type]

    def update_film_strip_animation_timing(self) -> None:
        """Update film strip animations for visible strips only.

        Each strip's update_animations() will call mark_dirty() internally
        when the animation frame actually changes, so there is no need to
        blanket-dirty all strips here.
        """
        if not (hasattr(self.editor, 'film_strips') and self.editor.film_strips):
            return

        film_strip_sprites = getattr(self.editor, 'film_strip_sprites', {})

        for strip_name, film_strip in self.editor.film_strips.items():
            # Only update animations for visible strips
            strip_sprite = film_strip_sprites.get(strip_name)
            if strip_sprite and not strip_sprite.visible:
                continue

            if hasattr(film_strip, 'update_animations'):
                film_strip.update_animations(self.editor.dt)

    def refresh_all_film_strip_widgets(self, animation_name: str | None = None) -> None:
        """Refresh all film strip widgets to reflect current animation data.

        Args:
            animation_name: If provided, also update frame selection for this animation.

        """
        if hasattr(self.editor, 'film_strip_widget') and self.editor.film_strip_widget:
            self.editor.film_strip_widget._initialize_preview_animations()  # type: ignore[reportPrivateUsage]
            self.editor.film_strip_widget.update_layout()
            self.editor.film_strip_widget._create_film_tabs()  # type: ignore[reportPrivateUsage]
            self.editor.film_strip_widget.mark_dirty()

        if not (hasattr(self.editor, 'film_strip_sprites') and self.editor.film_strip_sprites):
            return

        for film_strip_sprite in self.editor.film_strip_sprites.values():
            if not (
                hasattr(film_strip_sprite, 'film_strip_widget')
                and film_strip_sprite.film_strip_widget
            ):
                continue

            # Completely refresh the film strip widget to ensure it shows current data
            film_strip_sprite.film_strip_widget._initialize_preview_animations()  # type: ignore[reportPrivateUsage]
            film_strip_sprite.film_strip_widget._calculate_layout()  # type: ignore[reportPrivateUsage]
            film_strip_sprite.film_strip_widget.update_layout()
            film_strip_sprite.film_strip_widget._create_film_tabs()  # type: ignore[reportPrivateUsage]
            film_strip_sprite.film_strip_widget.mark_dirty()
            film_strip_sprite.dirty = 1

            # Update the film strip to show the current frame selection
            if (
                animation_name
                and hasattr(self.editor.canvas, 'current_animation')
                and hasattr(self.editor.canvas, 'current_frame')
                and self.editor.canvas.current_animation == animation_name
            ):
                film_strip_sprite.film_strip_widget.set_frame_index(
                    self.editor.canvas.current_frame,
                )
