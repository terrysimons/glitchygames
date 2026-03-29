"""Film strip layout calculation delegate.

This module contains all layout calculation methods for the FilmStripWidget,
including position/size geometry, layout caches, scroll offsets, film tabs,
and hit-testing helpers.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import pygame

from glitchygames.fonts import FontManager

if TYPE_CHECKING:
    from glitchygames.bitmappy.film_strip import FilmStripWidget
    from glitchygames.sprites import SpriteFrame

LOG = logging.getLogger('game.tools.film_strip')


class FilmStripLayout:  # noqa: PLR0904
    """Delegate providing layout calculation methods for FilmStripWidget."""

    def __init__(self, widget: FilmStripWidget) -> None:
        """Initialize the layout delegate.

        Args:
            widget: The parent FilmStripWidget instance.

        """
        self.widget = widget

    def initialize_styling(self) -> None:
        """Initialize film strip styling constants and colors."""
        # Film strip styling
        self.widget.frame_width = 64
        self.widget.frame_height = 64
        self.widget.sprocket_width = 20
        self.widget.frame_spacing = 2
        self.widget.animation_label_height = 20

        # Preview area styling
        self.widget.preview_width = 64  # Width reserved for individual animation previews
        self.widget.preview_height = 64  # Height of each preview area
        self.widget.preview_padding = 4  # Padding around each preview

        # Colors
        self.widget.film_background = (100, 70, 55)  # Darker copper brown color
        self.widget.sprocket_color = (20, 20, 20)
        self.widget.frame_border = (120, 90, 70)  # Copper brown frame borders
        self.widget.selection_color = (255, 0, 0)  # Red selection border
        self.widget.first_frame_color = (255, 0, 0)  # Red border for first frame
        self.widget.hover_color = (140, 110, 85)  # Lighter copper brown for hover
        self.widget.frame_background = (100, 70, 55)  # Copper brown film strip background
        self.widget.preview_background = (
            120,
            90,
            70,
        )  # Copper brown background for preview area
        self.widget.preview_border = (
            140,
            110,
            85,
        )  # Lighter copper brown border for preview
        # Even darker copper brown border for animation frame only
        self.widget.animation_border = (80, 60, 45)

        # Initialize film tabs for frame insertion
        self.widget.film_tabs = []  # List of FilmTabWidget instances
        self.widget.tab_width = 11  # Width of each tab (increased by 2, 1 pixel on each side)
        self.widget.tab_height = 30  # Height of each tab

        # Frame spacing constants
        self.widget.inter_frame_gap = 0  # Gap between frames (reduced by 2 pixels)

        # Animation change detection threshold
        self.widget.ANIMATION_CHANGE_THRESHOLD = 0.001

    def initialize_layout_caches(self) -> None:
        """Initialize layout caches and animation timing state."""
        # Layout cache
        self.widget.frame_layouts = {}
        self.widget.animation_layouts = {}
        self.widget.sprocket_layouts = []
        self.widget.preview_rects = {}  # Individual previews for each animation

        # Animation timing for previews
        self.widget.preview_animation_times = {}  # Current time for each animation
        self.widget.preview_animation_speeds = {}  # Speed multiplier for each animation
        self.widget.preview_frame_durations = {}  # Frame durations

        # Removal button layout cache
        self.widget.removal_button_layouts = {}

    def initialize_external_references(self) -> None:
        """Initialize external references set by parent components."""
        # Copy/paste buffer for frames
        self.widget.copied_frame = None  # Temporary storage for copied frame

        # Parent canvas reference (set externally via set_parent_canvas)
        self.widget.parent_canvas = None

        # Parent scene reference (set externally by BitmapEditorScene)
        self.widget.parent_scene = None

        # Film strip sprite reference (set externally)
        self.widget.film_strip_sprite = None

    def update_height(self) -> None:
        """Update the film strip height based on the number of animations (up to 5 rows max)."""
        if not self.widget.animated_sprite:
            return

        # Calculate required height based on number of animations
        num_animations = len(self.widget.animated_sprite.animations)
        max_animations = 5  # Maximum 5 rows

        # Limit to maximum 5 animations
        visible_animations = min(num_animations, max_animations)

        # Calculate height: (label_height + frame_height + spacing) * num_animations + padding
        required_height = (
            self.widget.animation_label_height + self.widget.frame_height + 20
        ) * visible_animations + 20  # Increased by 20 pixels

        # Update the rect height
        self.widget.rect.height = required_height

        # Update the parent film strip sprite height if it exists
        if (
            hasattr(self.widget, 'parent_canvas')
            and self.widget.parent_canvas
            and hasattr(self.widget.parent_canvas, 'film_strip_sprite')
        ):
            parent_canvas_any: Any = self.widget.parent_canvas
            parent_canvas_any.film_strip_sprite.rect.height = required_height  # ty: ignore[unresolved-attribute]
            # Also update the surface size
            parent_canvas_any.film_strip_sprite.image = pygame.Surface(  # ty: ignore[unresolved-attribute]
                (
                    parent_canvas_any.film_strip_sprite.rect.width,  # ty: ignore[unresolved-attribute]
                    required_height,
                ),
                pygame.SRCALPHA,
            )
            parent_canvas_any.film_strip_sprite.dirty = 1  # ty: ignore[unresolved-attribute]

    def update_layout(self) -> None:
        """Update the layout of frames and sprockets."""
        self.calculate_layout()

        # Create film tabs after layout is calculated
        self.create_film_tabs()

        # Mark the parent film strip sprite as dirty if it exists
        if (
            hasattr(self.widget, 'parent_canvas')
            and self.widget.parent_canvas
            and hasattr(self.widget.parent_canvas, 'film_strip_sprite')
        ):
            parent_canvas_any: Any = self.widget.parent_canvas
            parent_canvas_any.film_strip_sprite.dirty = 1  # ty: ignore[unresolved-attribute]

    def calculate_scroll_offset(self, frame_index: int, frames: list[SpriteFrame]) -> int:
        """Calculate the scroll offset to center a frame.

        Returns the scroll offset that centers the specified frame.

        Returns:
            int: The resulting integer value.

        """
        frame_width = self.widget.frame_width + self.widget.frame_spacing
        selected_frame_x = frame_index * frame_width
        visible_center = self.widget.rect.width // 2
        target_scroll = selected_frame_x - visible_center + (self.widget.frame_width // 2)
        max_scroll = max(0, len(frames) * frame_width - self.widget.rect.width)
        return max(0, min(target_scroll, max_scroll))

    def update_scroll_for_frame(self, frame_index: int) -> None:
        """Update scroll offset to keep the selected frame visible and centered."""
        if (
            not self.widget.animated_sprite
            or self.widget.current_animation not in self.widget.animated_sprite.animations
        ):
            return

        frames = self.widget.animated_sprite.animations[self.widget.current_animation]
        if frame_index >= len(frames):
            return

        # Calculate which 4-frame window should be shown
        frames_per_view = self.widget.FRAMES_PER_VIEW
        current_start_frame = self.widget.scroll_offset // (
            self.widget.frame_width + self.widget.tab_width + 2
        )
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
        self.widget.scroll_offset = new_start_frame * (
            self.widget.frame_width + self.widget.tab_width + 2
        )

        LOG.debug(
            'FilmStripWidget: Scrolling to show frame '
            f'{frame_index}, new window: '
            f'{new_start_frame}-{new_start_frame + frames_per_view - 1}',
        )

        # Recalculate layout with new scroll offset
        self.calculate_layout()
        self.update_height()
        self.widget.mark_dirty()

    def calculate_layout(self) -> None:
        """Calculate the layout of frames and sprockets."""
        if not self.widget.animated_sprite:
            return

        self.clear_layouts()
        self.calculate_animation_layouts()
        self.calculate_frame_layouts()
        self.calculate_preview_layouts()
        self.calculate_sprocket_layouts()

    def clear_layouts(self) -> None:
        """Clear all layout caches."""
        self.widget.frame_layouts.clear()
        self.widget.animation_layouts.clear()
        self.widget.sprocket_layouts.clear()
        self.widget.preview_rects.clear()

    def calculate_animation_layouts(self) -> None:
        """Calculate layout for animation labels."""
        if not self.widget.animated_sprite:
            return

        available_width = (
            self.widget.rect.width - self.widget.preview_width - self.widget.preview_padding
        )
        # Add top margin for delete button
        top_margin = 20  # Space for the [-] delete button at the top
        y_offset = top_margin - 9  # Move labels up to align with film strip area

        # Calculate the center position between sprocket groups
        # Left group ends at x=61, right group starts at preview_start_x + 10
        preview_start_x = available_width + self.widget.preview_padding
        left_group_end = 61
        right_group_start = preview_start_x + 10
        center_x = (left_group_end + right_group_start) // 2

        # Calculate label width dynamically for each animation
        for anim_name in self.widget.animated_sprite.animations:
            # Get text width for this animation
            font = FontManager.get_font()
            text_surface = font.render(anim_name, fgcolor=(255, 255, 255), size=12)
            if isinstance(text_surface, tuple):  # freetype returns (surface, rect)
                text_surface, text_rect = text_surface
            else:  # pygame.font returns surface
                text_rect = text_surface.get_rect()

            label_width = text_rect.width + 20  # Add padding  # ty: ignore[unresolved-attribute]
            label_x = center_x - (label_width // 2)  # Center the label

            self.widget.animation_layouts[anim_name] = pygame.Rect(
                label_x,
                y_offset,
                label_width,
                self.widget.animation_label_height,
            )
            # Only increment Y offset if there are multiple animations
            # For single animation, all elements should be at the same Y position
            if len(self.widget.animated_sprite.animations) > 1:
                y_offset += self.widget.animation_label_height + self.widget.frame_height + 20

    def calculate_sprocket_start_x(self) -> int:
        """Calculate sprocket start x position to align frames with sprockets.

        Returns:
            The x position where sprockets start.

        """
        sprocket_spacing = 17
        total_width = self.widget.rect.width - 20  # Leave 10px margin on each side
        num_sprockets = (total_width // sprocket_spacing) + 1
        sprockets_width = (num_sprockets - 1) * sprocket_spacing
        return 10 + (total_width - sprockets_width) // 2

    def calculate_frame_y(self, y_offset: int) -> int:
        """Calculate the Y position for frames.

        Returns:
            The y position for frames.

        """
        assert self.widget.animated_sprite is not None
        if len(self.widget.animated_sprite.animations) == 1:
            # Center frames between top sprockets (y=7) and bottom sprockets (y=rect.height-15)
            top_sprocket_y = 7
            bottom_sprocket_y = self.widget.rect.height - 15
            center_y = (top_sprocket_y + bottom_sprocket_y) // 2
            return center_y - (self.widget.frame_height // 2) + 3
        return y_offset + self.widget.animation_label_height + 3  # Moved down 3 pixels

    def add_removal_button(
        self,
        anim_name: str,
        actual_frame_idx: int,
        frame_x: int,
        frame_y: int,
    ) -> None:
        """Add a removal button layout for a frame."""
        removal_button_width = 11  # Narrower than insertion tabs, reduced by 4
        removal_button_height = 30  # Same as tab_height
        removal_button_x = frame_x - removal_button_width  # No gap - touching the frame
        removal_button_y = (
            frame_y + (self.widget.frame_height - removal_button_height) // 2
        )  # Center vertically
        removal_button_rect = pygame.Rect(
            removal_button_x,
            removal_button_y,
            removal_button_width,
            removal_button_height,
        )
        LOG.debug(
            'FilmStripWidget: Created removal button '
            f'rect for {anim_name}[{actual_frame_idx}] '
            f'at {removal_button_rect}',
        )
        if not hasattr(self.widget, 'removal_button_layouts'):
            self.widget.removal_button_layouts = {}
            LOG.debug('FilmStripWidget: Initialized removal_button_layouts dictionary')
        self.widget.removal_button_layouts[anim_name, actual_frame_idx] = removal_button_rect
        LOG.debug(
            f'FilmStripWidget: Added removal button to layouts: {anim_name}[{actual_frame_idx}]',
        )

    def calculate_frame_layouts(self) -> None:
        """Calculate layout for frame positions."""
        if not self.widget.animated_sprite:
            LOG.debug(
                'FilmStripWidget: No animated sprite, skipping frame layout calculation',
            )
            return

        LOG.debug(
            'FilmStripWidget: Calculating frame layouts for '
            f'{len(self.widget.animated_sprite.animations)} animations',
        )

        # CRITICAL: Clear old removal button layouts to prevent stale data
        self.widget.removal_button_layouts = {}

        # Add top margin for delete button
        top_margin = 20  # Space for the [-] delete button at the top
        y_offset = top_margin

        sprocket_start_x = self.calculate_sprocket_start_x()

        for anim_name, frames in self.widget.animated_sprite.animations.items():
            # Show only frames at a time (0-3), with scrolling to navigate
            frames_per_view = self.widget.FRAMES_PER_VIEW
            start_frame = self.widget.scroll_offset // (
                self.widget.frame_width + self.widget.tab_width + 2
            )
            end_frame = min(start_frame + frames_per_view, len(frames))
            frames_to_show = frames[start_frame:end_frame]
            LOG.debug(
                'FilmStripWidget: Processing '
                f'{len(frames_to_show)} frames for animation '
                f'{anim_name} (frames {start_frame}-{end_frame - 1})',
            )
            for frame_idx, _frame in enumerate(frames_to_show):
                actual_frame_idx = start_frame + frame_idx

                if frame_idx == 0:
                    # First frame positioned 2 pixels after the [+] button
                    frame_x = sprocket_start_x + self.widget.tab_width
                else:
                    # Subsequent frames: positioned after previous frame's [+] button + 11px gap
                    frame_spacing = self.widget.frame_width + self.widget.tab_width + 11
                    frame_x = sprocket_start_x + self.widget.tab_width + frame_idx * frame_spacing

                frame_y = self.calculate_frame_y(y_offset)
                frame_rect = pygame.Rect(
                    frame_x, frame_y, self.widget.frame_width, self.widget.frame_height
                )
                LOG.debug(
                    'FilmStripWidget: Created frame rect for '
                    f'{anim_name}[{actual_frame_idx}] at {frame_rect}',
                )
                self.widget.frame_layouts[anim_name, actual_frame_idx] = frame_rect

                # Add removal button (only for multi-frame animations)
                if len(frames) > 1:
                    self.add_removal_button(anim_name, actual_frame_idx, frame_x, frame_y)
                else:
                    LOG.debug(
                        'FilmStripWidget: Skipping removal button '
                        f'for {anim_name}[{actual_frame_idx}] '
                        f'- only {len(frames)} frame(s)',
                    )

            # Only increment Y offset if there are multiple animations
            if len(self.widget.animated_sprite.animations) > 1:
                y_offset += self.widget.animation_label_height + self.widget.frame_height + 20

    def calculate_preview_layouts(self) -> None:
        """Calculate layout for preview areas."""
        if not self.widget.animated_sprite:
            return

        # Add top margin for delete button
        top_margin = 20  # Space for the [-] delete button at the top
        y_offset = top_margin
        preview_x = self.widget.rect.width - self.widget.preview_width - 1

        for anim_name in self.widget.animated_sprite.animations:
            # Center the preview between top and bottom sprockets, moved down 3 pixels
            if len(self.widget.animated_sprite.animations) == 1:
                # Calculate center between top sprockets (y=7)
                # and bottom sprockets (y=rect.height-15)
                top_sprocket_y = 7
                bottom_sprocket_y = self.widget.rect.height - 15
                center_y = (top_sprocket_y + bottom_sprocket_y) // 2
                preview_center_y = self.widget.preview_height // 2
                preview_y = (
                    center_y - preview_center_y + 3
                )  # Center the preview vertically, moved down 3 pixels
            else:
                # Center the preview vertically with this animation's frames
                frame_visual_start_y = (
                    y_offset + self.widget.animation_label_height + 4
                )  # Match per-frame Y position
                frame_visual_height = self.widget.frame_height - 8  # 4px padding top and bottom
                frame_visual_center_y = frame_visual_start_y + frame_visual_height // 2
                preview_center_y = self.widget.preview_height // 2
                preview_y = (
                    frame_visual_center_y - preview_center_y - 2 + 3
                )  # Move up 2 pixels to match per-frame Y, moved down 3 pixels
            # Ensure preview doesn't go above the film strip
            preview_y = max(0, preview_y)
            self.widget.preview_rects[anim_name] = pygame.Rect(
                preview_x,
                preview_y,
                self.widget.preview_width,
                self.widget.preview_height,
            )

            # Only increment Y offset if there are multiple animations
            # For single animation, all elements should be at the same Y position
            if len(self.widget.animated_sprite.animations) > 1:
                y_offset += self.widget.animation_label_height + self.widget.frame_height + 20

    def calculate_sprocket_layouts(self) -> None:
        """Calculate layout for sprocket separators."""
        if not self.widget.animated_sprite:
            return

        x_offset = 0
        # Add top margin for delete button
        top_margin = 20  # Space for the [-] delete button at the top
        y_offset = top_margin
        animation_names = list(self.widget.animated_sprite.animations.keys())

        for anim_name in animation_names:
            # Add sprocket separator (except for last animation)
            if anim_name != animation_names[-1]:
                sprocket_rect = pygame.Rect(
                    x_offset,
                    0,
                    self.widget.sprocket_width,
                    self.widget.frame_height + self.widget.animation_label_height,
                )
                self.widget.sprocket_layouts.append(sprocket_rect)
                x_offset += self.widget.sprocket_width

            # Only increment Y offset if there are multiple animations
            # For single animation, all elements should be at the same Y position
            if len(self.widget.animated_sprite.animations) > 1:
                y_offset += self.widget.animation_label_height + self.widget.frame_height + 20

    def get_frame_at_position(self, pos: tuple[int, int]) -> tuple[str, int] | None:
        """Get the animation and frame at the given position.

        Returns:
            tuple[str, int] | None: The frame at position.

        """
        LOG.debug(
            'FilmStripWidget: Checking position '
            f'{pos} against {len(self.widget.frame_layouts)} frame layouts',
        )
        for (anim_name, frame_idx), frame_rect in self.widget.frame_layouts.items():
            LOG.debug(
                f'FilmStripWidget: Checking {anim_name}[{frame_idx}] at {frame_rect}',
            )
            if frame_rect.collidepoint(pos):
                LOG.debug(
                    f'FilmStripWidget: Found collision with {anim_name}[{frame_idx}]',
                )
                return (anim_name, frame_idx)
        LOG.debug('FilmStripWidget: No collision found')
        return None

    def get_animation_at_position(self, pos: tuple[int, int]) -> str | None:
        """Get the animation at the given position.

        Returns:
            str | None: The animation at position.

        """
        for anim_name, anim_rect in self.widget.animation_layouts.items():
            if anim_rect.collidepoint(pos):
                return anim_name
        return None

    def get_preview_at_position(self, pos: tuple[int, int]) -> str | None:
        """Get the preview animation at the given position.

        Returns:
            str | None: The preview at position.

        """
        for anim_name, preview_rect in self.widget.preview_rects.items():
            if preview_rect.collidepoint(pos):
                return anim_name
        return None

    def get_removal_button_at_position(self, pos: tuple[int, int]) -> tuple[str, int] | None:
        """Get the removal button at the given position.

        Args:
            pos: The position to check (x, y)

        Returns:
            Tuple of (animation_name, frame_idx) if a removal button is found, None otherwise

        """
        if (
            not hasattr(self.widget, 'removal_button_layouts')
            or not self.widget.removal_button_layouts
        ):
            return None

        for (anim_name, frame_idx), button_rect in self.widget.removal_button_layouts.items():
            if button_rect.collidepoint(pos):
                return (anim_name, frame_idx)
        return None

    def calculate_frames_width(self) -> int:
        """Calculate the total width needed for all frames and sprockets.

        Returns:
            int: The resulting integer value.

        """
        assert self.widget.animated_sprite is not None
        frames_width = 0
        animation_names = list(self.widget.animated_sprite.animations.keys())
        for i, (_, frames) in enumerate(self.widget.animated_sprite.animations.items()):
            frames_width += len(frames) * (self.widget.frame_width + self.widget.frame_spacing)
            # Add sprocket width between animations (not after the last one)
            if i < len(animation_names) - 1:
                frames_width += self.widget.sprocket_width
        return frames_width

    def get_total_width(self) -> int:
        """Get the total width needed for the film strip.

        Returns:
            int: The total width.

        """
        if not self.widget.animated_sprite:
            return 0

        frames_width = self.calculate_frames_width()
        # Add individual preview area width and padding
        return frames_width + self.widget.preview_width + self.widget.preview_padding

    def has_valid_canvas_sprite(self) -> bool:
        """Check if the parent scene has a valid canvas with an animated sprite.

        Returns:
            True if the parent scene has a valid canvas sprite.

        """
        if not (hasattr(self.widget, 'parent_scene') and self.widget.parent_scene):
            return False
        parent = self.widget.parent_scene
        return (
            hasattr(parent, 'canvas')
            and parent.canvas
            and hasattr(parent.canvas, 'animated_sprite')
        )

    def create_film_tabs(self) -> None:
        """Create film tabs for frame insertion points."""
        from glitchygames.bitmappy.film_strip import (
            FilmStripDeleteTab,
            FilmStripTab,
            FilmTabWidget,
        )

        self.widget.film_tabs.clear()

        if not self.widget.animated_sprite or not self.widget.animated_sprite.animations:
            return

        # Get the current animation frames
        current_animation = self.widget.current_animation
        if current_animation not in self.widget.animated_sprite.animations:
            return

        frames = self.widget.animated_sprite.animations[current_animation]
        if not frames:
            return

        # Calculate tab positions based on frame layouts
        for frame_idx in range(len(frames)):
            frame_key = (current_animation, frame_idx)
            if frame_key in self.widget.frame_layouts:
                frame_rect = self.widget.frame_layouts[frame_key]

                # Create "before" tab (to the left of the frame) - only for the first frame
                if frame_idx == 0:
                    before_tab = FilmTabWidget(
                        x=-2,  # Move 2px left of film strip border
                        y=frame_rect.y
                        + (frame_rect.height - self.widget.tab_height) // 2,  # Center vertically
                        width=self.widget.tab_width,
                        height=self.widget.tab_height,
                    )
                    before_tab.set_insertion_type('before', frame_idx)
                    self.widget.film_tabs.append(before_tab)

                # Create "after" tab (to the right of the frame) - for all frames
                after_tab = FilmTabWidget(
                    x=frame_rect.x + frame_rect.width - 2,  # 2px overlap with frame
                    y=frame_rect.y
                    + (frame_rect.height - self.widget.tab_height) // 2,  # Center vertically
                    width=self.widget.tab_width,
                    height=self.widget.tab_height,
                )
                after_tab.set_insertion_type('after', frame_idx)
                self.widget.film_tabs.append(after_tab)
            else:
                continue

        # Add a horizontal top tab (delete) at the center of the film strip
        # Show delete button if there's more than one animation
        # (to prevent deleting the last strip)
        if frames and self.has_valid_canvas_sprite():
            animations = list(self.widget.parent_scene.canvas.animated_sprite.animations.keys())
            if len(animations) > 1:
                # Calculate center x position of the film strip
                center_x = self.widget.rect.width // 2
                top_tab = FilmStripDeleteTab(
                    x=center_x - 20,  # Center horizontally (40px wide, so 20px offset)
                    y=5,  # Position at top of film strip with small margin
                    width=40,  # Wider than vertical tabs
                    height=10,  # Shorter than vertical tabs
                )
                top_tab.set_insertion_type('delete', 0)  # Delete current strip
                self.widget.film_tabs.append(top_tab)

        # Add a horizontal bottom tab (add) at the center of the film strip
        if frames:  # Only add bottom tab if there are frames
            # Calculate center x position of the film strip
            center_x = self.widget.rect.width // 2
            bottom_tab = FilmStripTab(
                x=center_x - 20,  # Center horizontally (40px wide, so 20px offset)
                y=self.widget.rect.height
                - 13,  # Position 13 pixels from bottom (moved down 2 pixels)
                width=40,  # Wider than vertical tabs
                height=10,  # Shorter than vertical tabs (reduced by half)
            )
            bottom_tab.set_insertion_type('after', len(frames) - 1)  # Insert after last frame
            self.widget.film_tabs.append(bottom_tab)
