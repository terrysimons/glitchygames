"""Film strip widget for animated sprite frame selection.

This module provides a film reel-style interface for selecting and navigating
between frames in animated sprites, with sprocket separators between animations.
"""

# No typing imports needed

import pygame
from glitchygames.fonts import FontManager
from glitchygames.sprites import AnimatedSprite


class FilmStripWidget:
    """Film reel-style widget for frame selection in animated sprites."""

    def __init__(self, x: int, y: int, width: int, height: int):
        """Initialize the film strip widget."""
        self.rect = pygame.Rect(x, y, width, height)
        self.animated_sprite: AnimatedSprite | None = None
        self.current_animation = ""  # Will be set when sprite is loaded
        self.current_frame = 0
        self.hovered_frame: tuple[str, int] | None = None
        self.hovered_animation: str | None = None

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
        self.film_background = (40, 40, 40)
        self.sprocket_color = (20, 20, 20)
        self.frame_border = (60, 60, 60)
        self.selection_color = (0, 255, 255)  # Bright cyan for good contrast against yellow
        self.hover_color = (100, 100, 100)
        self.frame_background = (255, 255, 0)  # Yellow film strip background
        self.preview_background = (60, 60, 60)  # Darker background for preview area
        self.preview_border = (100, 100, 100)  # Border color for preview

        # Layout cache
        self.frame_layouts: dict[tuple[str, int], pygame.Rect] = {}
        self.animation_layouts: dict[str, pygame.Rect] = {}
        self.sprocket_layouts: list[pygame.Rect] = []
        self.preview_rects: dict[str, pygame.Rect] = {}  # Individual previews for each animation

        # Animation timing for previews
        self.preview_animation_times: dict[str, float] = {}  # Current time for each animation
        self.preview_animation_speeds: dict[str, float] = {}  # Speed multiplier for each animation
        self.preview_frame_durations: dict[str, list[float]] = {}  # Frame durations

        # Animation change detection threshold
        self.ANIMATION_CHANGE_THRESHOLD = 0.001

    def set_animated_sprite(self, animated_sprite: AnimatedSprite) -> None:
        """Set the animated sprite to display."""
        self.animated_sprite = animated_sprite
        # Use sprite introspection to find the first animation
        if animated_sprite._animations:
            if hasattr(animated_sprite, "_animation_order") and animated_sprite._animation_order:
                # Use the first animation in the file order
                self.current_animation = animated_sprite._animation_order[0]
            else:
                # Fall back to the first key in _animations
                self.current_animation = next(iter(animated_sprite._animations.keys()))
        else:
            self.current_animation = ""
        self.current_frame = 0
        self.scroll_offset = 0  # Horizontal scroll offset for rolling effect

        # Initialize animation timing for previews
        self._initialize_preview_animations()

        self._calculate_layout()
        self._update_height()

    def _initialize_preview_animations(self) -> None:
        """Initialize animation timing for all previews."""
        if not self.animated_sprite:
            return

        for anim_name, frames in self.animated_sprite._animations.items():
            # Initialize timing for this animation
            self.preview_animation_times[anim_name] = 0.0
            self.preview_animation_speeds[anim_name] = 1.0  # Normal speed

            # Extract frame durations
            frame_durations = []
            for frame in frames:
                if hasattr(frame, "duration"):
                    frame_durations.append(frame.duration)
                else:
                    frame_durations.append(1.0)  # Default 1 second
            self.preview_frame_durations[anim_name] = frame_durations

    def update_animations(self, dt: float) -> None:
        """Update animation timing for all previews."""
        if not self.animated_sprite:
            return

        # Always mark as dirty when animations are running to ensure continuous updates
        # This ensures the film strip redraws even when animations are smoothly transitioning
        has_animations = len(self.animated_sprite._animations) > 0
        if has_animations:
            self.mark_dirty()

        # Update independent timing for each animation preview
        for anim_name in self.animated_sprite._animations:
            if anim_name in self.preview_animation_times:
                # Update animation time
                speed = self.preview_animation_speeds[anim_name]
                self.preview_animation_times[anim_name] += dt * speed

                # Get total duration of this animation
                total_duration = sum(self.preview_frame_durations.get(anim_name, [1.0]))

                # Loop animation time continuously (no pause)
                if total_duration > 0:
                    self.preview_animation_times[anim_name] %= total_duration

    def get_current_preview_frame(self, anim_name: str) -> int:
        """Get the current frame index for a preview animation."""
        if (
            anim_name not in self.preview_animation_times
            or anim_name not in self.preview_frame_durations
        ):
            return 0

        current_time = self.preview_animation_times[anim_name]
        frame_durations = self.preview_frame_durations[anim_name]

        # Find which frame we should be showing during animation
        accumulated_time = 0.0
        for frame_idx, duration in enumerate(frame_durations):
            if current_time <= accumulated_time + duration:
                return frame_idx
            accumulated_time += duration

        # Fallback to last frame
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
        # This will be called when the canvas changes to force a re-render
        if (
            hasattr(self, "parent_canvas")
            and self.parent_canvas
            and hasattr(self.parent_canvas, "film_strip_sprite")
        ):
            self.parent_canvas.film_strip_sprite.dirty = 2

        # Force a complete re-render by clearing any cached data
        # This ensures that frame thumbnails and preview are updated
        self._force_redraw = True

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

        # Calculate the position of the selected frame
        frame_width = self.frame_width + self.frame_spacing
        selected_frame_x = frame_index * frame_width

        # Calculate the center of the visible area
        visible_center = self.rect.width // 2

        # Calculate the scroll offset to center the selected frame
        target_scroll = selected_frame_x - visible_center + (self.frame_width // 2)

        # Clamp the scroll offset to reasonable bounds
        max_scroll = max(0, len(frames) * frame_width - self.rect.width)
        self.scroll_offset = max(0, min(target_scroll, max_scroll))

        # Recalculate layout with new scroll offset
        self._calculate_layout()
        self._update_height()
        self.mark_dirty()

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
            self.animation_label_height + self.frame_height + 10
        ) * visible_animations + 20

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

        self.frame_layouts.clear()
        self.animation_layouts.clear()
        self.sprocket_layouts.clear()
        self.preview_rects.clear()

        # Calculate available width for frames (total width minus preview area)
        available_width = self.rect.width - self.preview_width - self.preview_padding

        x_offset = 0
        y_offset = 0
        for anim_name, frames in self.animated_sprite._animations.items():
            # Calculate animation label area for this row (limited to available width)
            self.animation_layouts[anim_name] = pygame.Rect(
                0, y_offset, available_width, self.animation_label_height
            )

            # Calculate frame positions with scroll offset for this row
            for frame_idx, _frame in enumerate(frames):
                frame_x = frame_idx * (self.frame_width + self.frame_spacing) - self.scroll_offset
                frame_rect = pygame.Rect(
                    frame_x,
                    y_offset + self.animation_label_height,
                    self.frame_width,
                    self.frame_height,
                )
                self.frame_layouts[anim_name, frame_idx] = frame_rect

            # Calculate individual preview for this animation
            preview_x = self.rect.width - self.preview_width
            # Center the preview vertically with this animation's frames
            frame_visual_start_y = y_offset + self.animation_label_height + 4  # 4px padding
            frame_visual_height = self.frame_height - 8  # 4px padding top and bottom
            frame_visual_center_y = frame_visual_start_y + frame_visual_height // 2
            preview_center_y = self.preview_height // 2
            preview_y = frame_visual_center_y - preview_center_y
            # Ensure preview doesn't go above the film strip
            preview_y = max(0, preview_y)
            self.preview_rects[anim_name] = pygame.Rect(
                preview_x, preview_y, self.preview_width, self.preview_height
            )

            # Move to next row
            y_offset += (
                self.animation_label_height + self.frame_height + 10
            )  # 10px spacing between animations

            # Add sprocket separator (except for last animation)
            if anim_name != list(self.animated_sprite._animations.keys())[-1]:
                sprocket_rect = pygame.Rect(
                    x_offset,
                    0,
                    self.sprocket_width,
                    self.frame_height + self.animation_label_height,
                )
                self.sprocket_layouts.append(sprocket_rect)
                x_offset += self.sprocket_width

    def get_frame_at_position(self, pos: tuple[int, int]) -> tuple[str, int] | None:
        """Get the animation and frame at the given position."""
        for (anim_name, frame_idx), frame_rect in self.frame_layouts.items():
            if frame_rect.collidepoint(pos):
                return (anim_name, frame_idx)
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
            self.current_animation = animation
            self.current_frame = frame
            # Mark as dirty to trigger preview update
            self.mark_dirty()

    def handle_click(self, pos: tuple[int, int]) -> tuple[str, int] | None:
        """Handle a click on the film strip."""
        # Check if clicking on a frame
        clicked_frame = self.get_frame_at_position(pos)
        if clicked_frame:
            animation, frame_idx = clicked_frame
            self.set_current_frame(animation, frame_idx)
            return clicked_frame

        # Check if clicking on an animation label
        clicked_animation = self.get_animation_at_position(pos)
        if clicked_animation and clicked_animation in self.animated_sprite._animations:
            # Switch to first frame of that animation
            self.set_current_frame(clicked_animation, 0)
            return (clicked_animation, 0)

        return None

    def handle_hover(self, pos: tuple[int, int]) -> None:
        """Handle mouse hover over the film strip."""
        self.hovered_frame = self.get_frame_at_position(pos)
        self.hovered_animation = self.get_animation_at_position(pos)

    def render_frame_thumbnail(
        self, frame, *, is_selected: bool = False, is_hovered: bool = False
    ) -> pygame.Surface:
        """Render a single frame thumbnail with film strip styling."""
        # Create frame surface with yellow film strip background
        frame_surface = pygame.Surface((self.frame_width, self.frame_height))
        frame_surface.fill(self.frame_background)  # Yellow film strip background

        # Draw the actual frame image - use current canvas content for selected frame,
        # stored data for others
        if is_selected and hasattr(self, "parent_canvas") and self.parent_canvas:
            # For the selected frame, use current canvas content
            frame_img = self.parent_canvas.get_canvas_surface()
        elif hasattr(frame, "image") and frame.image:
            # For non-selected frames, use stored frame data
            frame_img = frame.image
        else:
            frame_img = None

        # If we're forcing a redraw, always get fresh data for the selected frame
        if (
            is_selected
            and hasattr(self, "_force_redraw")
            and self._force_redraw
            and hasattr(self, "parent_canvas")
            and self.parent_canvas
        ):
            frame_img = self.parent_canvas.get_canvas_surface()
            # Reset the force redraw flag after getting fresh data
            self._force_redraw = False

        if frame_img:
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

            # Center the scaled image within the frame
            x_offset = (self.frame_width - new_width) // 2
            y_offset = (self.frame_height - new_height) // 2
            frame_surface.blit(scaled_image, (x_offset, y_offset))
        else:
            # If no frame data, create a placeholder
            placeholder = pygame.Surface((self.frame_width - 8, self.frame_height - 8))
            placeholder.fill((128, 128, 128))  # Gray placeholder
            # Center the placeholder
            x_offset = (self.frame_width - placeholder.get_width()) // 2
            y_offset = (self.frame_height - placeholder.get_height()) // 2
            frame_surface.blit(placeholder, (x_offset, y_offset))

        # Add film strip perforations (top and bottom)
        for hole_x in range(4, self.frame_width - 4, 8):
            # Top row holes
            pygame.draw.circle(frame_surface, self.sprocket_color, (hole_x, 2), 1)
            # Bottom row holes
            pygame.draw.circle(
                frame_surface, self.sprocket_color, (hole_x, self.frame_height - 3), 1
            )

        # Add film strip edges
        pygame.draw.line(frame_surface, self.frame_border, (0, 0), (0, self.frame_height), 1)
        pygame.draw.line(
            frame_surface,
            self.frame_border,
            (self.frame_width - 1, 0),
            (self.frame_width - 1, self.frame_height),
            1,
        )

        # Add selection highlighting
        if is_selected:
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

        # Add hover highlighting
        if is_hovered:
            pygame.draw.rect(
                frame_surface, self.hover_color, (0, 0, self.frame_width, self.frame_height), 2
            )

        return frame_surface

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
            # Clear the preview area
            surface.fill(self.preview_background, preview_rect)

            # Draw preview border
            pygame.draw.rect(surface, self.preview_border, preview_rect, 2)

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

                    surface.blit(scaled_image, (center_x, center_y))
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

    def render(self, surface: pygame.Surface) -> None:
        """Render the film strip to the given surface."""
        if not self.animated_sprite:
            return

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
                    frame, is_selected=is_selected, is_hovered=is_hovered
                )

                # Blit to surface
                if is_selected:
                    # For selected frames, the thumbnail already includes the selection border
                    # so we need to center it properly
                    surface.blit(frame_thumbnail, (frame_rect.x - 2, frame_rect.y - 2))
                else:
                    surface.blit(frame_thumbnail, frame_rect)

        # Render sprocket separators
        for sprocket_rect in self.sprocket_layouts:
            sprocket = self.render_sprocket_separator(0, 0, sprocket_rect.height)
            surface.blit(sprocket, sprocket_rect)

        # Render the animated preview
        self.render_preview(surface)

    def get_total_width(self) -> int:
        """Get the total width needed for the film strip."""
        if not self.animated_sprite:
            return 0

        # Calculate width needed for frames
        frames_width = 0
        for anim_name, frames in self.animated_sprite._animations.items():
            frames_width += len(frames) * (self.frame_width + self.frame_spacing)
            if anim_name != list(self.animated_sprite._animations.keys())[-1]:
                frames_width += self.sprocket_width

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

        # Check if click is on a frame
        for (anim_name, frame_idx), frame_rect in self.frame_layouts.items():
            if frame_rect.collidepoint(local_x, local_y):
                # Frame was clicked - return the animation and frame info
                return (anim_name, frame_idx)

        return None
