"""Film strip event handling delegate.

This module contains all event/interaction methods for the FilmStripWidget,
including click handling, hover handling, keyboard input, frame selection,
copy/paste, tab click handling, onion skinning toggles, frame insertion,
and frame removal.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import TYPE_CHECKING, Any

import pygame

if TYPE_CHECKING:
    from glitchygames.bitmappy.film_strip import (
        FilmStripWidget,
        FilmTabWidget,
    )
    from glitchygames.events.base import HashableEvent
    from glitchygames.sprites import SpriteFrame

ANIMATION_NAME_MAX_LENGTH = 50

LOG = logging.getLogger('game.tools.film_strip')


class FilmStripEventHandler:  # noqa: PLR0904
    """Delegate providing event/interaction methods for FilmStripWidget."""

    def __init__(self, widget: FilmStripWidget) -> None:
        """Initialize the event handler delegate.

        Args:
            widget: The parent FilmStripWidget instance.

        """
        self.widget = widget

    def set_current_frame(self, animation: str, frame: int) -> None:
        """Set the current animation and selected frame."""
        if (
            self.widget.animated_sprite
            and animation in self.widget.animated_sprite.animations
            and 0 <= frame < len(self.widget.animated_sprite.animations[animation])
        ):
            LOG.debug(
                f'FilmStripWidget: Setting selected frame to {animation}, {frame}',
            )
            self.widget.current_animation = animation
            self.widget.selected_frame = frame  # Update the selected frame (static thumbnails)
            # Mark as dirty to trigger preview update
            self.widget.mark_dirty()
            LOG.debug(
                'FilmStripWidget: Selected frame is now '
                f'{self.widget.current_animation}, {self.widget.selected_frame}',
            )

            # Notify parent scene about the selection change
            if hasattr(self.widget, 'parent_scene') and self.widget.parent_scene:
                self.widget.parent_scene.on_film_strip_frame_selected(self.widget, animation, frame)

    def handle_click(  # noqa: PLR0911
        self,
        pos: tuple[int, int],
        *,
        is_right_click: bool = False,
        is_shift_click: bool = False,
    ) -> tuple[str, int] | None:
        """Handle a click on the film strip.

        Returns:
            tuple[str, int] | None: The result.

        """
        LOG.debug(
            'FilmStripWidget: handle_click called with position '
            f'{pos}, right_click={is_right_click}, '
            f'shift_click={is_shift_click}',
        )
        LOG.debug(
            f'FilmStripWidget: frame_layouts has {len(self.widget.frame_layouts)} entries',
        )

        # First check if a removal button was clicked
        if self.handle_removal_button_click(pos):
            LOG.debug(
                'FilmStripWidget: Removal button was clicked, not processing frame click',
            )
            return None  # Removal button was clicked, don't process frame click

        # Check if a tab was clicked
        if self.handle_tab_click(pos):
            LOG.debug('FilmStripWidget: Tab was clicked, not processing frame click')
            return None  # Tab was clicked, don't process frame click

        # Check if clicking on a frame
        clicked_frame = self.widget.layout.get_frame_at_position(pos)
        if clicked_frame:
            animation, frame_idx = clicked_frame
            # Use this film strip's animation name instead of the frame's animation name
            # since each film strip represents a specific animation
            strip_animation = (
                next(iter(self.widget.animated_sprite.animations.keys()))
                if self.widget.animated_sprite and self.widget.animated_sprite.animations
                else animation
            )

            # Handle onion skinning toggle for right-click or shift-click
            if is_right_click or is_shift_click:
                self.toggle_onion_skinning(strip_animation, frame_idx)
                LOG.debug(
                    f'FilmStripWidget: Toggled onion skinning for {strip_animation}[{frame_idx}]',
                )
                return None  # Don't change frame selection for onion skinning toggle

            LOG.debug(
                'FilmStripWidget: Frame clicked, calling '
                f'set_current_frame({strip_animation}, {frame_idx})',
            )
            self.set_current_frame(strip_animation, frame_idx)
            return (strip_animation, frame_idx)

        # Check if clicking on an animation label
        clicked_animation = self.widget.layout.get_animation_at_position(pos)
        if (
            clicked_animation
            and self.widget.animated_sprite
            and clicked_animation in self.widget.animated_sprite.animations
        ):
            # Enter edit mode for animation renaming
            self.widget.editing_animation = clicked_animation
            self.widget.editing_text = ''  # Start with blank buffer
            self.widget.original_animation_name = clicked_animation
            # Initialize cursor blink state
            self.widget.cursor_blink_time = pygame.time.get_ticks()
            self.widget.cursor_visible = True
            LOG.debug(
                f"FilmStripWidget: Entered edit mode for animation '{clicked_animation}'",
            )
            self.widget.mark_dirty()  # Force redraw to show edit state
            # Don't change frame selection when entering edit mode
            return None

        # Check if clicking on preview area
        preview_click = self.handle_preview_click(pos)
        if preview_click:
            return preview_click

        # Check if clicking on the parent strip itself (outside of frames, labels, and preview)
        if self.widget.rect.collidepoint(pos):
            # Click is within the film strip widget but not on any specific element
            # This means the user clicked on the parent strip itself
            strip_animation = (
                next(iter(self.widget.animated_sprite.animations.keys()))
                if self.widget.animated_sprite and self.widget.animated_sprite.animations
                else ''
            )
            # Use the scene's global selected_frame to maintain consistency
            global_selected_frame = 0
            if hasattr(self.widget, 'parent_scene') and self.widget.parent_scene:
                global_selected_frame = getattr(self.widget.parent_scene, 'selected_frame', 0)
            LOG.debug(
                'FilmStripWidget: Parent strip clicked, selecting '
                'strip and calling set_current_frame'
                f'({strip_animation}, {global_selected_frame})',
            )
            self.set_current_frame(strip_animation, global_selected_frame)
            return (strip_animation, global_selected_frame)

        LOG.debug('FilmStripWidget: No frame or animation clicked')
        return None

    def handle_hover(self, pos: tuple[int, int]) -> None:
        """Handle mouse hover over the film strip."""
        self.widget.hovered_frame = self.widget.layout.get_frame_at_position(pos)
        self.widget.hovered_animation = self.widget.layout.get_animation_at_position(pos)

        # Check for removal button hover
        self.widget.hovered_removal_button = self.widget.layout.get_removal_button_at_position(pos)

        # Handle tab hover effects
        self.handle_tab_hover(pos)

    def handle_preview_click(self, pos: tuple[int, int]) -> tuple[str, int] | None:
        """Handle mouse click on the preview area (right side).

        Returns (animation, frame_idx) if click was handled.

        Returns:
            tuple[str, int] | None: The result.

        """
        # Check if click is on the animated preview frame (right side)
        for anim_name, preview_rect in self.widget.preview_rects.items():
            if preview_rect.collidepoint(pos):
                # Cycle background color for all frames in this animation
                self.widget.background_color_index = (self.widget.background_color_index + 1) % len(
                    self.widget.BACKGROUND_COLORS
                )
                self.widget.background_color = self.widget.BACKGROUND_COLORS[
                    self.widget.background_color_index
                ]
                LOG.debug(
                    f'Film strip background color changed to {self.widget.background_color}',
                )
                # When clicking on preview area, use the scene's global selected_frame
                # instead of the strip's own selected_frame
                global_selected_frame = 0
                if hasattr(self.widget, 'parent_scene') and self.widget.parent_scene:
                    global_selected_frame = getattr(self.widget.parent_scene, 'selected_frame', 0)
                return (anim_name, global_selected_frame)
        return None

    def handle_keyboard_input(self, event: HashableEvent) -> bool:
        """Handle keyboard input for animation renaming.

        Args:
            event: Keyboard event with 'key' and optionally 'unicode' attributes

        Returns:
            True if the event was handled, False otherwise

        """
        # Only handle keyboard input if we're in edit mode
        if not self.widget.editing_animation:
            return False

        # Handle Enter key to commit rename
        if hasattr(event, 'key') and event.key == pygame.K_RETURN:
            if self.widget.editing_text and self.widget.original_animation_name:
                new_name = self.widget.editing_text.strip()
                LOG.debug(
                    'FilmStripWidget: Attempting to rename '
                    f"'{self.widget.original_animation_name}' to '{new_name}'",
                )
                if new_name and new_name != self.widget.original_animation_name:
                    # Notify parent scene to handle the rename
                    if hasattr(self.widget, 'parent_scene') and self.widget.parent_scene:
                        LOG.debug(
                            'FilmStripWidget: Calling parent_scene.on_animation_rename',
                        )
                        self.widget.parent_scene.on_animation_rename(
                            self.widget.original_animation_name,
                            new_name,
                        )
                    else:
                        LOG.warning(
                            'FilmStripWidget: No parent_scene found! Cannot rename animation.',
                        )
                else:
                    LOG.debug(
                        'FilmStripWidget: Name unchanged or empty, not renaming',
                    )
            else:
                LOG.debug(
                    'FilmStripWidget: editing_text='
                    f"'{self.widget.editing_text}', "
                    'original_animation_name='
                    f"'{self.widget.original_animation_name}'",
                )

            # Clear edit mode
            self.widget.editing_animation = None
            self.widget.editing_text = ''
            self.widget.original_animation_name = None
            self.widget.mark_dirty()
            LOG.debug('FilmStripWidget: Committed animation rename')
            return True

        # Handle Escape key to cancel editing
        if hasattr(event, 'key') and event.key == pygame.K_ESCAPE:
            # Clear edit mode without committing
            self.widget.editing_animation = None
            self.widget.editing_text = ''
            self.widget.original_animation_name = None
            self.widget.mark_dirty()
            LOG.debug('FilmStripWidget: Cancelled animation rename')
            return True

        # Handle backspace
        if hasattr(event, 'key') and event.key == pygame.K_BACKSPACE and self.widget.editing_text:
            self.widget.editing_text = self.widget.editing_text[:-1]
            # Reset cursor blink to show cursor after typing
            self.widget.cursor_blink_time = pygame.time.get_ticks()
            self.widget.cursor_visible = True
            self.widget.mark_dirty()
            return True

        # Handle printable characters
        # Limit length to prevent overflow
        if (
            hasattr(event, 'unicode')
            and event.unicode
            and event.unicode.isprintable()
            and len(self.widget.editing_text) < ANIMATION_NAME_MAX_LENGTH
        ):
            self.widget.editing_text += event.unicode
            # Reset cursor blink to show cursor after typing
            self.widget.cursor_blink_time = pygame.time.get_ticks()
            self.widget.cursor_visible = True
            self.widget.mark_dirty()
            return True

        return False

    def is_keyboard_selected(self, animation_name: str, frame_index: int) -> bool:
        """Check if a frame is selected via keyboard navigation.

        Args:
            animation_name: The animation name to check.
            frame_index: The frame index to check.

        Returns:
            True if the frame is keyboard-selected.

        """
        if not (hasattr(self.widget, 'parent_scene') and self.widget.parent_scene):
            return False
        parent = self.widget.parent_scene
        return (
            hasattr(parent, 'selected_animation')
            and hasattr(parent, 'selected_frame')
            and parent.selected_animation == animation_name
            and parent.selected_frame == frame_index
        )

    def get_controller_selection_color(
        self,
        animation_name: str,
        frame_index: int,
    ) -> tuple[int, int, int] | None:
        """Get the controller color if a controller has this frame selected.

        Returns:
            The controller color tuple, or None if not selected.

        """
        if not (
            hasattr(self.widget, 'parent_scene')
            and self.widget.parent_scene
            and hasattr(self.widget.parent_scene, 'controller_selections')
        ):
            return None

        for (
            controller_id,
            controller_selection,
        ) in self.widget.parent_scene.controller_selections.items():
            if not controller_selection.is_active():
                continue
            controller_animation, controller_frame = controller_selection.get_selection()
            if controller_animation != animation_name or controller_frame != frame_index:
                continue
            # Get controller color from multi-controller manager singleton
            from .controllers.manager import MultiControllerManager

            manager = MultiControllerManager.get_instance()
            for info in manager.controllers.values():
                if info.controller_id == controller_id:
                    return info.color
        return None

    def toggle_onion_skinning(self, animation_name: str, frame_index: int) -> None:
        """Toggle onion skinning for a specific frame."""
        try:
            from .onion_skinning import get_onion_skinning_manager

            onion_manager = get_onion_skinning_manager()
            new_state = onion_manager.toggle_frame_onion_skinning(animation_name, frame_index)

            LOG.debug(
                f'Onion skinning toggled for {animation_name}[{frame_index}]: {new_state}',
            )

            # Mark the film strip as dirty to trigger a redraw
            self.widget.force_redraw = True

            # Force canvas redraw to show onion skinning changes
            if (
                hasattr(self.widget, 'parent_scene')
                and self.widget.parent_scene
                and hasattr(self.widget.parent_scene, 'canvas')
                and self.widget.parent_scene.canvas
            ):
                self.widget.parent_scene.canvas.force_redraw()
                LOG.debug('Forced canvas redraw for onion skinning toggle')

        except Exception:
            LOG.exception('Failed to toggle onion skinning')

    def copy_current_frame(self) -> bool:
        """Copy the currently selected frame to the clipboard.

        Returns:
            True if copy was successful, False otherwise

        """
        LOG.debug('FilmStripWidget: [FILM STRIP COPY] copy_current_frame called')
        LOG.debug(
            f'FilmStripWidget: [FILM STRIP COPY] animated_sprite: {self.widget.animated_sprite}',
        )
        LOG.debug(
            f'FilmStripWidget: [FILM STRIP COPY] current_animation: '
            f'{self.widget.current_animation}',
        )
        LOG.debug(
            f'FilmStripWidget: [FILM STRIP COPY] current_frame: {self.widget.current_frame}',
        )

        if not self.widget.animated_sprite or not self.widget.current_animation:
            LOG.debug(
                'FilmStripWidget: [FILM STRIP COPY] No animation selected for copying',
            )
            return False

        if self.widget.current_animation not in self.widget.animated_sprite.animations:
            LOG.debug(
                "FilmStripWidget: [FILM STRIP COPY] Animation '%s' not found",
                self.widget.current_animation,
            )
            return False

        frames = self.widget.animated_sprite.animations[self.widget.current_animation]
        LOG.debug(
            f'FilmStripWidget: [FILM STRIP COPY] Animation has {len(frames)} frames',
        )
        if self.widget.current_frame >= len(frames):
            LOG.debug(
                f'FilmStripWidget: [FILM STRIP COPY] Frame {self.widget.current_frame} '
                f'out of range (max: {len(frames) - 1})',
            )
            return False

        # Get the current frame
        current_frame = frames[self.widget.current_frame]
        LOG.debug(
            f'FilmStripWidget: [FILM STRIP COPY] Got frame object: {current_frame}',
        )

        # Create a deep copy of the frame data
        self.widget.copied_frame = deepcopy(current_frame)
        LOG.debug(
            'FilmStripWidget: [FILM STRIP COPY] Created deep copy, stored in copied_frame',
        )

        LOG.debug(
            'FilmStripWidget: [FILM STRIP COPY] Successfully copied frame '
            f"{self.widget.current_frame} from animation '{self.widget.current_animation}'",
        )
        return True

    def paste_to_current_frame(self) -> bool:
        """Paste the copied frame to the currently selected frame.

        Returns:
            True if paste was successful, False otherwise

        """
        LOG.debug(
            'FilmStripWidget: [FILM STRIP PASTE] paste_to_current_frame called',
        )
        LOG.debug(
            f'FilmStripWidget: [FILM STRIP PASTE] copied_frame: {self.widget.copied_frame}',
        )
        LOG.debug(
            f'FilmStripWidget: [FILM STRIP PASTE] animated_sprite: {self.widget.animated_sprite}',
        )
        LOG.debug(
            f'FilmStripWidget: [FILM STRIP PASTE] current_animation: '
            f'{self.widget.current_animation}',
        )
        LOG.debug(
            f'FilmStripWidget: [FILM STRIP PASTE] current_frame: {self.widget.current_frame}',
        )

        if not self.widget.copied_frame:
            LOG.debug(
                'FilmStripWidget: [FILM STRIP PASTE] No frame in clipboard to paste',
            )
            return False

        if not self.widget.animated_sprite or not self.widget.current_animation:
            LOG.debug(
                'FilmStripWidget: [FILM STRIP PASTE] No animation selected for pasting',
            )
            return False

        if self.widget.current_animation not in self.widget.animated_sprite.animations:
            LOG.debug(
                'FilmStripWidget: [FILM STRIP PASTE] '
                f"Animation '{self.widget.current_animation}' not found",
            )
            return False

        frames = self.widget.animated_sprite.animations[self.widget.current_animation]
        LOG.debug(
            f'FilmStripWidget: [FILM STRIP PASTE] Animation has {len(frames)} frames',
        )
        if self.widget.current_frame >= len(frames):
            LOG.debug(
                f'FilmStripWidget: [FILM STRIP PASTE] Frame {self.widget.current_frame} '
                f'out of range (max: {len(frames) - 1})',
            )
            return False

        LOG.debug(
            f'FilmStripWidget: [FILM STRIP PASTE] Replacing frame '
            f'{self.widget.current_frame} with copied frame',
        )
        # Replace the current frame with the copied frame
        frames[self.widget.current_frame] = deepcopy(self.widget.copied_frame)
        LOG.debug(
            'FilmStripWidget: [FILM STRIP PASTE] Frame replacement completed',
        )

        LOG.debug(
            'FilmStripWidget: [FILM STRIP PASTE] Successfully pasted frame to '
            f'frame {self.widget.current_frame} in animation '
            f"'{self.widget.current_animation}'",
        )

        # Mark as dirty to trigger redraw
        self.widget.mark_dirty()
        LOG.debug('FilmStripWidget: [FILM STRIP PASTE] Marked as dirty')

        # Notify parent scene if available
        if hasattr(self.widget, 'parent_scene') and self.widget.parent_scene:
            LOG.debug(
                'FilmStripWidget: [FILM STRIP PASTE] Notifying parent scene',
            )
            if hasattr(self.widget.parent_scene, '_on_frame_pasted'):
                self.widget.parent_scene._on_frame_pasted(
                    self.widget.current_animation, self.widget.current_frame
                )
        else:
            LOG.debug(
                'FilmStripWidget: [FILM STRIP PASTE] No parent scene to notify',
            )

        return True

    def set_frame_index(self, frame_index: int) -> None:
        """Set the current frame and update the canvas."""
        if not self.widget.animated_sprite:
            return

        # Update the current frame
        self.widget.current_frame = frame_index

        # Update scroll to keep the selected frame visible and centered
        self.widget.layout.update_scroll_for_frame(frame_index)

        # Update the parent canvas to show this frame
        if self.widget.parent_canvas and hasattr(self.widget.parent_canvas, 'canvas_interface'):
            self.widget.parent_canvas.canvas_interface.set_current_frame(
                self.widget.current_animation,
                frame_index,
            )

    def _find_clicked_frame(self, local_x: int, local_y: int) -> tuple[str, int] | None:
        """Find which frame was clicked at the given coordinates.

        Returns (animation, frame) if a frame was clicked, None otherwise.

        Returns:
            tuple[str, int] | None: The result.

        """
        for (anim_name, frame_idx), frame_rect in self.widget.frame_layouts.items():
            if frame_rect.collidepoint(local_x, local_y):
                return (anim_name, frame_idx)
        return None

    def handle_frame_click(self, pos: tuple[int, int]) -> tuple[str, int] | None:
        """Handle mouse click on the film strip.

        Returns (animation, frame) if a frame was clicked.

        Returns:
            tuple[str, int] | None: The result.

        """
        if not self.widget.animated_sprite:
            return None

        # Coordinates are already local to the film strip widget
        local_x, local_y = pos

        # Check if click is within film strip bounds
        if not (0 <= local_x < self.widget.rect.width and 0 <= local_y < self.widget.rect.height):
            return None

        return self._find_clicked_frame(local_x, local_y)

    def handle_tab_click(self, pos: tuple[int, int]) -> bool:
        """Handle mouse click on film tabs.

        Args:
            pos: Mouse position (x, y)

        Returns:
            True if a tab was clicked, False otherwise

        """
        from glitchygames.bitmappy.film_strip import FilmStripDeleteTab, FilmStripTab

        for tab in self.widget.film_tabs:
            if not tab.handle_click(pos):
                continue
            # Check if this is a FilmStripTab (horizontal bottom tab)
            if isinstance(tab, FilmStripTab):
                self.handle_add_animation_tab_click()
                tab.reset_click_state()
                return True
            if isinstance(tab, FilmStripDeleteTab):
                self.handle_delete_animation_tab_click()
                tab.reset_click_state()
                return True
            # Regular frame tab - create a new frame at the specified position
            self.insert_frame_at_tab(tab)
            tab.reset_click_state()
            return True
        return False

    def handle_add_animation_tab_click(self) -> None:
        """Handle click on the add-animation tab (horizontal bottom tab)."""
        if not (hasattr(self.widget, 'parent_scene') and self.widget.parent_scene):
            return
        current_animation = self.widget.current_animation
        if not (hasattr(self.widget.parent_scene, 'canvas') and self.widget.parent_scene.canvas):
            self.widget.parent_scene.film_strip_coordinator._add_new_animation()
            return
        animations = list(self.widget.parent_scene.canvas.animated_sprite.animations.keys())
        try:
            current_index = animations.index(current_animation)
            self.widget.parent_scene.film_strip_coordinator._add_new_animation(
                insert_after_index=current_index,
            )
        except ValueError:
            # Fallback to end if current animation not found
            self.widget.parent_scene.film_strip_coordinator._add_new_animation()

    def handle_delete_animation_tab_click(self) -> None:
        """Handle click on the delete-animation tab."""
        if not (hasattr(self.widget, 'parent_scene') and self.widget.parent_scene):
            return
        current_animation = self.widget.current_animation
        if not (hasattr(self.widget.parent_scene, 'canvas') and self.widget.parent_scene.canvas):
            return
        animations = list(self.widget.parent_scene.canvas.animated_sprite.animations.keys())
        if len(animations) > 1:
            self.widget.parent_scene.film_strip_coordinator._delete_animation(current_animation)

    def handle_tab_hover(self, pos: tuple[int, int]) -> bool:
        """Handle mouse hover over film tabs.

        Args:
            pos: Mouse position (x, y)

        Returns:
            True if hovering over a tab, False otherwise

        """
        hovered_any = False
        for tab in self.widget.film_tabs:
            if tab.handle_hover(pos):
                hovered_any = True
        return hovered_any

    def reset_all_tab_states(self) -> None:
        """Reset click and hover states for all tabs."""
        for tab in self.widget.film_tabs:
            tab.reset_click_state()
            tab.is_hovered = False

    def insert_frame_at_tab(self, tab: FilmTabWidget) -> None:
        """Insert a new frame at the position specified by the tab.

        Args:
            tab: The film tab that was clicked

        """
        if not self.widget.animated_sprite:
            return

        current_animation = self.widget.current_animation
        if current_animation not in self.widget.animated_sprite.animations:
            return

        # Create a new blank frame using the canonical helper from parent scene
        if not (
            hasattr(self.widget, 'parent_scene')
            and self.widget.parent_scene
            and hasattr(self.widget.parent_scene, 'canvas')
        ):
            return  # Cannot create frame without parent scene canvas dimensions

        frame_width = self.widget.parent_scene.canvas.pixels_across
        frame_height = self.widget.parent_scene.canvas.pixels_tall

        # Use the shared helper to create a blank frame with proper SRCALPHA support
        new_frame = self.widget.parent_scene.film_strip_coordinator._create_blank_frame(
            frame_width, frame_height, duration=0.5
        )

        # Determine insertion index
        if tab.insertion_type == 'before':
            insert_index = tab.target_frame_index
        else:  # "after"
            insert_index = tab.target_frame_index + 1

        # Insert the frame into the animated sprite
        self.widget.animated_sprite.add_frame(current_animation, new_frame, insert_index)

        # Track frame addition for undo/redo
        if (
            hasattr(self.widget, 'parent_scene')
            and self.widget.parent_scene
            and hasattr(self.widget.parent_scene, 'film_strip_operation_tracker')
        ):
            # Create frame data for undo/redo tracking
            frame_data: dict[str, Any] = {
                'width': new_frame.image.get_width(),
                'height': new_frame.image.get_height(),
                'pixels': (new_frame.pixels.copy() if hasattr(new_frame, 'pixels') else []),
                'duration': new_frame.duration,
            }

            self.widget.parent_scene.film_strip_operation_tracker.add_frame_added(
                insert_index,
                current_animation,
                frame_data,
            )

        # CRITICAL: Reinitialize preview animations after adding a frame
        # This ensures the film strip picks up the new frame count and starts animating
        # if it was previously a single-frame animation
        self.widget.animation.initialize_preview_animations()

        # Notify the parent scene about the frame insertion
        if hasattr(self.widget.parent_scene, 'on_frame_inserted'):
            self.widget.parent_scene.on_frame_inserted(current_animation, insert_index)

        # Select the newly created frame so the user can immediately start editing it
        LOG.debug(
            'FilmStripWidget: Selecting newly created frame '
            f"{insert_index} in animation '{current_animation}'",
        )
        self.set_current_frame(current_animation, insert_index)

        # Also update the canvas to show the new frame
        if (
            hasattr(self.widget, 'parent_scene')
            and self.widget.parent_scene
            and hasattr(self.widget.parent_scene, 'canvas')
            and self.widget.parent_scene.canvas
        ):
            # Set flag to prevent frame selection tracking during frame creation
            self.widget.parent_scene._creating_frame = True
            try:
                self.widget.parent_scene.canvas.show_frame(current_animation, insert_index)
                LOG.debug(
                    f'FilmStripWidget: Updated canvas to show new frame {insert_index}',
                )
            finally:
                self.widget.parent_scene._creating_frame = False

        # Recalculate layouts to include the new frame
        self.widget.layout.update_layout()

        # Recreate tabs for the new frame layout
        self.widget.layout.create_film_tabs()

        # Mark as dirty to trigger redraw
        self.widget.mark_dirty()

        # Reset debug timer for new frame dump
        if hasattr(self.widget, 'debug_start_time'):
            self.widget.debug_start_time = 0.0
        if hasattr(self.widget, 'debug_last_dump_time'):
            self.widget.debug_last_dump_time = 0.0

    def handle_removal_button_click(self, pos: tuple[int, int]) -> bool:
        """Handle clicks on removal buttons.

        Args:
            pos: Click position (x, y)

        Returns:
            True if a removal button was clicked, False otherwise

        """
        LOG.debug(f'FilmStripWidget: Checking removal button click at {pos}')

        if (
            not hasattr(self.widget, 'removal_button_layouts')
            or not self.widget.removal_button_layouts
        ):
            LOG.debug('FilmStripWidget: No removal button layouts found')
            return False

        LOG.debug(
            f'FilmStripWidget: Checking {len(self.widget.removal_button_layouts)} removal buttons',
        )

        for (anim_name, frame_idx), button_rect in self.widget.removal_button_layouts.items():
            LOG.debug(
                f'FilmStripWidget: Checking button {anim_name}[{frame_idx}] at {button_rect}',
            )
            if button_rect.collidepoint(pos):
                LOG.debug(
                    f'FilmStripWidget: Click hit removal button for {anim_name}[{frame_idx}]',
                )
                # CRITICAL: Add bounds checking to prevent invalid frame removal
                if (
                    self.widget.animated_sprite
                    and anim_name in self.widget.animated_sprite.animations
                    and frame_idx < len(self.widget.animated_sprite.animations[anim_name])
                ):
                    LOG.debug(
                        f'FilmStripWidget: Removal button clicked for {anim_name}[{frame_idx}]',
                    )
                    # Show confirmation dialog instead of directly removing
                    if hasattr(self.widget, 'parent_scene') and self.widget.parent_scene:
                        self.widget.parent_scene._show_delete_frame_confirmation(
                            anim_name, frame_idx
                        )
                    return True
                LOG.debug(
                    f'FilmStripWidget: Cannot remove frame - index {frame_idx} out of range',
                )
                return False
        LOG.debug('FilmStripWidget: No removal button was clicked')
        return False

    def stop_animation_before_deletion(self, animation_name: str, frame_index: int) -> None:
        """Stop animation and adjust frame index before frame deletion."""
        if not (
            self.widget.animated_sprite
            and hasattr(self.widget.animated_sprite, 'frame_manager')
            and self.widget.animated_sprite.frame_manager.current_animation == animation_name
        ):
            return
        # Stop the animation to prevent it from accessing frames during deletion
        self.widget.animated_sprite.stop()

        # Adjust the current frame index before deletion
        if self.widget.animated_sprite.frame_manager.current_frame >= frame_index:
            self.widget.animated_sprite.frame_manager.current_frame = max(
                0,
                self.widget.animated_sprite.frame_manager.current_frame - 1,
            )

        LOG.debug(
            'FilmStripWidget: Stopped animation and adjusted '
            'frame index to '
            f'{self.widget.animated_sprite.frame_manager.current_frame}',
        )

    def track_frame_deletion_for_undo(
        self,
        frames: list[SpriteFrame],
        animation_name: str,
        frame_index: int,
    ) -> None:
        """Capture frame data and track deletion for undo/redo."""
        if not (
            hasattr(self.widget, 'parent_scene')
            and self.widget.parent_scene
            and hasattr(self.widget.parent_scene, 'film_strip_operation_tracker')
        ):
            return
        frame_to_remove = frames[frame_index]
        frame_data: dict[str, Any] = {
            'width': frame_to_remove.image.get_width(),
            'height': frame_to_remove.image.get_height(),
            'pixels': (frame_to_remove.pixels.copy() if hasattr(frame_to_remove, 'pixels') else []),
            'duration': frame_to_remove.duration,
        }
        self.widget.parent_scene.film_strip_operation_tracker.add_frame_deleted(
            frame_index,
            animation_name,
            frame_data,
        )

    def adjust_current_frame_after_deletion(self, animation_name: str, frame_index: int) -> None:
        """Adjust the widget's current frame after a frame deletion."""
        if not (
            hasattr(self.widget, 'current_animation')
            and self.widget.current_animation == animation_name
            and hasattr(self.widget, 'current_frame')
            and self.widget.current_frame >= frame_index
        ):
            return
        if self.widget.current_frame > 0:
            self.widget.current_frame -= 1
            LOG.debug(
                'FilmStripWidget: Selected previous frame '
                f'{self.widget.current_frame} after deletion',
            )
        else:
            self.widget.current_frame = 0
            LOG.debug(
                'FilmStripWidget: Stayed at frame 0 after deleting frame 0',
            )

    def clamp_animated_sprite_frame(self, animation_name: str, frames: list[SpriteFrame]) -> None:
        """Ensure the animated sprite's current frame is within bounds after deletion."""
        if not (
            self.widget.animated_sprite
            and hasattr(self.widget.animated_sprite, 'frame_manager')
            and self.widget.animated_sprite.frame_manager.current_animation == animation_name
        ):
            return
        remaining_frames = len(frames)
        if (
            remaining_frames > 0
            and self.widget.animated_sprite.frame_manager.current_frame >= remaining_frames
        ):
            self.widget.animated_sprite.frame_manager.current_frame = max(0, remaining_frames - 1)

        LOG.debug(
            'FilmStripWidget: After removal - animated sprite '
            'current_frame: '
            f'{self.widget.animated_sprite.frame_manager.current_frame}'
            f', frames count: {len(frames)}',
        )
        self.widget.animated_sprite.dirty = 1

    def remove_frame(self, animation_name: str, frame_index: int) -> None:
        """Remove a frame from the animated sprite.

        Args:
            animation_name: Name of the animation
            frame_index: Index of the frame to remove

        """
        if (
            not self.widget.animated_sprite
            or animation_name not in self.widget.animated_sprite.animations
        ):
            LOG.debug(
                f"FilmStripWidget: Cannot remove frame - animation '{animation_name}' not found",
            )
            return

        frames = self.widget.animated_sprite.animations[animation_name]
        if frame_index < 0 or frame_index >= len(frames):
            LOG.debug(
                f'FilmStripWidget: Cannot remove frame - index {frame_index} out of range',
            )
            return

        # Don't allow removing the last frame of an animation
        if len(frames) <= 1:
            LOG.debug(
                f"FilmStripWidget: Cannot remove the last frame of animation '{animation_name}'",
            )
            return

        LOG.debug(
            f"FilmStripWidget: Removing frame {frame_index} from animation '{animation_name}'",
        )

        # CRITICAL: Stop animation and reset frame index before deletion
        # to prevent race conditions
        self.stop_animation_before_deletion(animation_name, frame_index)

        # Capture frame data for undo/redo before removing
        self.track_frame_deletion_for_undo(frames, animation_name, frame_index)

        # Remove the frame
        frames.pop(frame_index)

        # Adjust current frame if necessary and select the previous frame
        self.adjust_current_frame_after_deletion(animation_name, frame_index)

        # Ensure the current frame is within bounds after deletion
        self.clamp_animated_sprite_frame(animation_name, frames)

        # Notify the parent scene about the frame removal
        if hasattr(self.widget.parent_scene, 'on_frame_removed'):
            self.widget.parent_scene.on_frame_removed(animation_name, frame_index)

        # CRITICAL: Reinitialize preview animations after frame removal
        # This ensures the preview animation system is updated with the new frame count
        self.widget.animation.initialize_preview_animations()

        # CRITICAL: Adjust scroll offset to ensure 4 frames are visible after removal
        # Calculate the maximum scroll offset based on remaining frames
        remaining_frames = len(frames)
        if remaining_frames > self.widget.FRAMES_PER_VIEW:
            # Calculate frame spacing for scroll offset adjustment
            max_scroll = max(0, remaining_frames - self.widget.FRAMES_PER_VIEW)
            # Ensure scroll offset doesn't exceed the maximum
            self.widget.scroll_offset = min(self.widget.scroll_offset, max_scroll)
        else:
            # If FRAMES_PER_VIEW or fewer frames remain, reset scroll to show all frames
            self.widget.scroll_offset = 0

        # Recalculate layouts after frame removal
        self.widget.layout.update_layout()

        # Recreate tabs for the new frame layout
        self.widget.layout.create_film_tabs()

        # Mark as dirty to trigger redraw
        self.widget.mark_dirty()

        LOG.debug(
            'FilmStripWidget: Frame removed. Animation '
            f"'{animation_name}' now has {len(frames)} frames",
        )
