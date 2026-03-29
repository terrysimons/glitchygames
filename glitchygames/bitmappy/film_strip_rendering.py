"""Film strip rendering delegate.

This module contains all rendering and drawing methods for the FilmStripWidget,
including frame thumbnails, sprocket separators, preview areas, labels,
multi-controller indicators, and film sprockets.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import pygame

from glitchygames.color import RGB_COMPONENT_COUNT
from glitchygames.fonts import FontManager

if TYPE_CHECKING:
    from glitchygames.bitmappy.film_strip import FilmStripWidget
    from glitchygames.sprites import SpriteFrame

LOG = logging.getLogger('game.tools.film_strip')


class FilmStripRendering:  # noqa: PLR0904
    """Delegate providing rendering/drawing methods for FilmStripWidget."""

    def __init__(self, widget: FilmStripWidget) -> None:
        """Initialize the rendering delegate.

        Args:
            widget: The parent FilmStripWidget instance.

        """
        self.widget = widget

    def render_frame_thumbnail(
        self,
        frame: SpriteFrame,
        *,
        is_selected: bool = False,
        is_hovered: bool = False,
        frame_index: int = 0,
        animation_name: str = '',
    ) -> pygame.Surface:
        """Render a single frame thumbnail with 3D beveled border.

        Returns:
            pygame.Surface: The rendered frame thumbnail surface.

        """
        frame_surface = self._create_frame_surface()

        # Fill with cycling background color (with alpha support)
        frame_surface.fill(self.widget.background_color)

        frame_img = self.get_frame_image_for_rendering(frame, is_selected=is_selected)

        if frame_img:
            self._draw_scaled_image(frame_surface, frame_img)
        else:
            self.draw_placeholder(frame_surface)

        # Add 3D beveled border like the right side animation frame
        self.add_3d_beveled_border(frame_surface)

        # Add border for selected frame - use same color as indicator
        selection_color = None

        # Check keyboard selection (white indicator)
        if self.widget.event_handler.is_keyboard_selected(animation_name, frame_index):
            selection_color = (255, 255, 255)  # White for keyboard

        # Check controller selection (use controller's color)
        if not selection_color:
            selection_color = self.widget.event_handler.get_controller_selection_color(
                animation_name, frame_index
            )

        # Draw selection border with the appropriate color
        if selection_color:
            pygame.draw.rect(
                frame_surface,
                selection_color,
                (0, 0, self.widget.frame_width, self.widget.frame_height),
                3,
            )

        # Draw hover effect
        if is_hovered:
            # Draw a bright blue border for hover effect
            pygame.draw.rect(
                frame_surface,
                (0, 255, 255),
                (0, 0, self.widget.frame_width, self.widget.frame_height),
                2,
            )

        # Draw frame number at the bottom center
        self._draw_frame_number(frame_surface, frame_index)

        # Draw onion skinning indicator
        self._draw_onion_skinning_indicator(frame_surface, animation_name, frame_index)

        return frame_surface

    def _create_frame_surface(self) -> pygame.Surface:
        """Create the base frame surface with transparent background.

        Returns:
            pygame.Surface: The result.

        """
        # No background fill - transparent so only the 3D beveled border shows
        return pygame.Surface((self.widget.frame_width, self.widget.frame_height), pygame.SRCALPHA)

    def _draw_frame_number(self, surface: pygame.Surface, frame_index: int) -> None:
        """Draw the frame number at the bottom center of the frame."""
        try:
            # Create font for frame number
            font = pygame.font.Font(None, 12)  # Small font size

            # Get total frames for current animation
            total_frames = 1  # Default fallback
            if (
                hasattr(self.widget, 'animated_sprite')
                and self.widget.animated_sprite
                and hasattr(self.widget, 'current_animation')
                and self.widget.current_animation
                and self.widget.current_animation in self.widget.animated_sprite.animations
            ):
                total_frames = len(
                    self.widget.animated_sprite.animations[self.widget.current_animation]
                )

            # Render frame number text in format "current+1/total"
            frame_text = f'{frame_index + 1}/{total_frames}'
            text_surface = font.render(
                frame_text,
                antialias=True,
                color=(255, 255, 255),
            )  # White text
            text_rect = text_surface.get_rect()

            # Position at bottom center of the frame (like animation preview)
            target_rect = pygame.Rect(0, 0, self.widget.frame_width, self.widget.frame_height)
            text_rect.centerx = target_rect.centerx
            text_rect.bottom = target_rect.bottom - 2  # Small margin from bottom edge

            # Draw text
            surface.blit(text_surface, text_rect)
        except Exception:
            # Log font rendering failures
            LOG.exception('Font rendering failed')

    def _draw_onion_skinning_indicator(
        self,
        surface: pygame.Surface,
        animation_name: str,
        frame_index: int,
    ) -> None:
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
                overlay_x = self.widget.frame_width - overlay_size - 2  # 2 pixels from right edge
                overlay_y = 2  # 2 pixels from top edge

                # Create semi-transparent surface for overlay
                overlay_surface = pygame.Surface((overlay_size, overlay_size), pygame.SRCALPHA)
                overlay_surface.fill((255, 255, 0, 128))  # Semi-transparent yellow

                # Draw a small circle or square to indicate onion skinning
                pygame.draw.circle(
                    overlay_surface,
                    (255, 255, 0, 200),
                    (overlay_size // 2, overlay_size // 2),
                    overlay_size // 2 - 1,
                )

                # Blit the overlay to the frame surface
                surface.blit(overlay_surface, (overlay_x, overlay_y))

        except Exception:
            # Log onion skinning indicator failures
            LOG.exception('Onion skinning indicator rendering failed')

    def get_frame_image_for_rendering(
        self,
        frame: SpriteFrame,
        *,
        is_selected: bool,  # noqa: ARG002
    ) -> pygame.Surface | None:
        """Get the appropriate frame image for rendering.

        Returns:
            pygame.Surface: The frame image for rendering.

        """
        # Always use the actual animation frame data, not canvas content
        if hasattr(frame, 'image') and frame.image:
            # Use stored frame data for all frames
            frame_img = frame.image
        else:
            # Fall back to creating image from pixel data (same as get_frame_image)
            from glitchygames.bitmappy.film_strip_animation import FilmStripAnimation

            frame_img = FilmStripAnimation.get_frame_image(frame)
            if not frame_img:
                LOG.debug('Film strip: No frame data available')

        return frame_img

    def _draw_scaled_image(self, frame_surface: pygame.Surface, frame_img: pygame.Surface) -> None:
        """Draw a scaled image onto the frame surface."""
        # Calculate scaling to fit within the frame area (leaving some padding)
        max_width = self.widget.frame_width - 8  # Leave 4px padding on each side
        max_height = self.widget.frame_height - 8  # Leave 4px padding on top/bottom

        # Calculate scale factor to fit the image
        scale = min(max_width / frame_img.get_width(), max_height / frame_img.get_height())

        # Scale the image
        new_width = int(frame_img.get_width() * scale)
        new_height = int(frame_img.get_height() * scale)
        scaled_image = pygame.transform.scale(frame_img, (new_width, new_height))

        # Center the scaled image within the frame, nudged right by 1 pixel
        x_offset = (self.widget.frame_width - new_width) // 2 + 1
        y_offset = (self.widget.frame_height - new_height) // 2

        # Convert magenta pixels to transparent and blit
        rgba_surface = self.convert_magenta_to_transparent(scaled_image)
        frame_surface.blit(rgba_surface, (x_offset, y_offset))

    @staticmethod
    def convert_magenta_to_transparent(surface: pygame.Surface) -> pygame.Surface:
        """Convert magenta (255, 0, 255) pixels to transparent in a surface.

        Returns:
            A new SRCALPHA surface with magenta pixels made transparent.

        """
        rgba_surface = pygame.Surface(surface.get_size(), pygame.SRCALPHA)

        for y in range(surface.get_height()):
            for x in range(surface.get_width()):
                color = surface.get_at((x, y))
                r, g, b = color[0], color[1], color[2]
                if (r, g, b) == (255, 0, 255):
                    rgba_surface.set_at((x, y), (255, 0, 255, 0))  # Transparent magenta
                elif len(color) == RGB_COMPONENT_COUNT:
                    rgba_surface.set_at((x, y), (r, g, b, 255))  # Full opacity
                else:
                    rgba_surface.set_at((x, y), color)  # Keep original RGBA

        return rgba_surface

    def draw_placeholder(self, frame_surface: pygame.Surface) -> None:
        """Draw a placeholder when no frame data is available."""
        # If no frame data, create a placeholder
        placeholder = pygame.Surface(
            (self.widget.frame_width - 8, self.widget.frame_height - 8), pygame.SRCALPHA
        )
        placeholder.fill((120, 90, 70))  # Copper brown placeholder
        # Center the placeholder
        x_offset = (self.widget.frame_width - placeholder.get_width()) // 2
        y_offset = (self.widget.frame_height - placeholder.get_height()) // 2
        frame_surface.blit(placeholder, (x_offset, y_offset))

    def add_film_strip_styling(self, frame_surface: pygame.Surface) -> None:
        """Add film strip edges to the frame surface."""
        # Add film strip edges (no sprockets on individual frames)
        pygame.draw.line(
            frame_surface, self.widget.frame_border, (0, 0), (0, self.widget.frame_height), 1
        )
        pygame.draw.line(
            frame_surface,
            self.widget.frame_border,
            (self.widget.frame_width - 1, 0),
            (self.widget.frame_width - 1, self.widget.frame_height),
            1,
        )

    def create_selection_border(self, frame_surface: pygame.Surface) -> pygame.Surface:
        """Create a selection border for the selected frame.

        Returns:
            pygame.Surface: The result.

        """
        # Yellow film leader color for selection
        selection_border = pygame.Surface(
            (self.widget.frame_width + 4, self.widget.frame_height + 4),
            pygame.SRCALPHA,
        )
        selection_border.fill(self.widget.selection_color)
        # Add film strip perforations to selection border
        for hole_x in range(4, self.widget.frame_width, 8):
            pygame.draw.circle(selection_border, (200, 200, 0), (hole_x, 2), 1)
            pygame.draw.circle(
                selection_border,
                (200, 200, 0),
                (hole_x, self.widget.frame_height + 1),
                1,
            )
        # Blit the frame content onto the selection border (centered)
        selection_border.blit(frame_surface, (2, 2))
        return selection_border

    def add_hover_highlighting(self, frame_surface: pygame.Surface) -> None:
        """Add hover highlighting to the frame surface."""
        pygame.draw.rect(
            frame_surface,
            self.widget.hover_color,
            (0, 0, self.widget.frame_width, self.widget.frame_height),
            2,
        )

    def add_3d_beveled_border(self, frame_surface: pygame.Surface) -> None:
        """Add 3D beveled border like the right side animation frame."""
        # Draw the same border as preview, aligned with sprockets
        pygame.draw.rect(
            frame_surface,
            self.widget.preview_border,
            (0, 0, self.widget.frame_width, self.widget.frame_height),
            2,
        )

    def render_sprocket_separator(self, _x: int, _y: int, height: int) -> pygame.Surface:
        """Render a sprocket separator between animations.

        Returns:
            pygame.Surface: The result.

        """
        separator = pygame.Surface((self.widget.sprocket_width, height), pygame.SRCALPHA)
        separator.fill(self.widget.film_background)

        # Draw sprocket holes (perforations)
        hole_spacing = 8
        for hole_y in range(4, height - 4, hole_spacing):
            # Left side holes
            pygame.draw.circle(separator, self.widget.sprocket_color, (6, hole_y), 2)
            # Right side holes
            pygame.draw.circle(separator, self.widget.sprocket_color, (14, hole_y), 2)

        # Draw film strip edges
        pygame.draw.line(separator, self.widget.frame_border, (0, 0), (0, height), 1)
        pygame.draw.line(
            separator,
            self.widget.frame_border,
            (self.widget.sprocket_width - 1, 0),
            (self.widget.sprocket_width - 1, height),
            1,
        )

        return separator

    def render_preview(self, surface: pygame.Surface) -> None:
        """Render individual previews for each animation."""
        if not self.widget.animated_sprite:
            return

        # Render preview for each animation
        for anim_name, preview_rect in self.widget.preview_rects.items():
            # Fill with cycling background color (with alpha support)
            surface.fill(self.widget.background_color, preview_rect)

            # Draw preview border (animation frame only - use darker border)
            pygame.draw.rect(surface, self.widget.animation_border, preview_rect, 2)

            # Draw preview hover effect (different color to distinguish from static frames)
            if self.widget.hovered_preview == anim_name:
                # Draw a distinct hover effect for preview area
                # (orange/yellow to distinguish from cyan frames)
                pygame.draw.rect(
                    surface,
                    (255, 165, 0),
                    preview_rect,
                    3,
                )  # Orange border for preview hover

            # Get the current animated frame for this animation's preview
            if (
                anim_name in self.widget.animated_sprite.animations
                and len(self.widget.animated_sprite.animations[anim_name]) > 0
            ):
                # Get the current frame index based on animation timing
                current_frame_idx = self.widget.animation.get_current_preview_frame(anim_name)

                # CRITICAL: Add bounds checking to prevent index out of range errors
                frames = self.widget.animated_sprite.animations[anim_name]
                if current_frame_idx >= len(frames) or current_frame_idx < 0:
                    LOG.error(
                        'FilmStripWidget: CRITICAL - Invalid preview '
                        f'frame index {current_frame_idx} for animation '
                        f"'{anim_name}' with {len(frames)} frames",
                    )
                    # Reset to frame 0 if invalid
                    current_frame_idx = 0
                    # Also reset the preview animation time to prevent future issues
                    if (
                        hasattr(self.widget, 'preview_animation_times')
                        and anim_name in self.widget.preview_animation_times
                    ):
                        self.widget.preview_animation_times[anim_name] = 0.0

                frame = frames[current_frame_idx]

                # Get the frame image for the current animation frame
                from glitchygames.bitmappy.film_strip_animation import FilmStripAnimation

                frame_img = FilmStripAnimation.get_frame_image(frame)

                if frame_img:
                    self._draw_scaled_preview_image(surface, frame_img, preview_rect)
                else:
                    # Draw placeholder if no frame data
                    placeholder_rect = pygame.Rect(
                        preview_rect.x + self.widget.preview_padding,
                        preview_rect.y + self.widget.preview_padding,
                        self.widget.preview_width - (self.widget.preview_padding * 2),
                        self.widget.preview_height - (self.widget.preview_padding * 2),
                    )
                    pygame.draw.rect(surface, (128, 128, 128), placeholder_rect)
                    pygame.draw.rect(surface, (200, 200, 200), placeholder_rect, 1)

            # Draw triangle underneath the animation preview
            self.draw_preview_triangle(surface, preview_rect)

            # Draw current frame index on the animation preview
            self._draw_preview_frame_index(surface, preview_rect, anim_name)

    def _draw_scaled_preview_image(
        self,
        surface: pygame.Surface,
        frame_img: pygame.Surface,
        preview_rect: pygame.Rect,
    ) -> None:
        """Draw a scaled and centered image within a preview area."""
        # Calculate scaling to fit within the preview area
        preview_inner_width = self.widget.preview_width - (self.widget.preview_padding * 2)
        preview_inner_height = self.widget.preview_height - (self.widget.preview_padding * 2)

        # Calculate scale factor
        scale_x = preview_inner_width / frame_img.get_width()
        scale_y = preview_inner_height / frame_img.get_height()
        scale = min(scale_x, scale_y)

        # Scale the image
        new_width = int(frame_img.get_width() * scale)
        new_height = int(frame_img.get_height() * scale)
        scaled_image = pygame.transform.scale(frame_img, (new_width, new_height))

        # Center the scaled image within the preview area
        center_x = preview_rect.x + (self.widget.preview_width - new_width) // 2
        center_y = preview_rect.y + (self.widget.preview_height - new_height) // 2

        # Make magenta (255, 0, 255) transparent for testing
        scaled_image.set_colorkey((255, 0, 255))
        surface.blit(scaled_image, (center_x, center_y))

    def render_vertical_divider(self, surface: pygame.Surface) -> None:
        """Render a vertical divider between the frames and preview area."""
        if not self.widget.animated_sprite:
            return

        # Calculate divider position - 2 pixels wide, positioned between frames and preview
        divider_x = (
            self.widget.rect.width - self.widget.preview_width - 2 - 4
        )  # 2 pixels before preview area, then 4 pixels left
        divider_y = 0
        divider_width = 2
        divider_height = self.widget.rect.height

        # Draw the divider as a dark copper/bronze line
        divider_rect = pygame.Rect(divider_x, divider_y, divider_width, divider_height)
        pygame.draw.rect(surface, (92, 58, 26), divider_rect)

    def render_preview_background(self, surface: pygame.Surface) -> None:
        """Render a darker background for the preview area (right of the divider)."""
        if not self.widget.animated_sprite:
            return

        # Calculate preview background area - from divider to end of film strip
        divider_x = (
            self.widget.rect.width - self.widget.preview_width - 2 - 4
        )  # Same as divider position
        preview_bg_x = divider_x + 2  # Start after the divider (2px wide)
        preview_bg_y = 0
        preview_bg_width = self.widget.rect.width - preview_bg_x
        preview_bg_height = self.widget.rect.height

        # Draw darker background - slightly darker than the divider
        preview_bg_rect = pygame.Rect(
            preview_bg_x,
            preview_bg_y,
            preview_bg_width,
            preview_bg_height,
        )
        pygame.draw.rect(surface, (80, 50, 22), preview_bg_rect)

    def _render_frame_thumbnails(self, surface: pygame.Surface) -> None:
        """Render all frame thumbnails onto the surface."""
        assert self.widget.animated_sprite is not None
        for (anim_name, frame_idx), frame_rect in self.widget.frame_layouts.items():
            if anim_name not in self.widget.animated_sprite.animations:
                continue
            if frame_idx >= len(self.widget.animated_sprite.animations[anim_name]):
                continue

            frame = self.widget.animated_sprite.animations[anim_name][frame_idx]

            # Determine if this frame is selected or hovered
            is_selected = (
                anim_name == self.widget.current_animation
                and frame_idx == self.widget.current_frame
            )
            is_hovered = self.widget.hovered_frame == (anim_name, frame_idx)

            # Render frame thumbnail for ALL frames (not just selected ones)
            frame_thumbnail = self.render_frame_thumbnail(
                frame,
                is_selected=is_selected,
                is_hovered=is_hovered,
                frame_index=frame_idx,
                animation_name=anim_name,
            )

            # Blit to surface - use consistent positioning for all frames
            surface.blit(frame_thumbnail, frame_rect)

            # Render removal button for this frame
            self.render_removal_button(surface, anim_name, frame_idx)

    def render_animation_label(self, anim_name: str, anim_rect: pygame.Rect) -> pygame.Surface:
        """Render a single animation label surface.

        Returns:
            The rendered label surface.

        """
        label_surface = pygame.Surface((anim_rect.width, anim_rect.height), pygame.SRCALPHA)
        label_surface.fill(self.widget.film_background)

        if self.widget.editing_animation == anim_name:
            self.render_editing_label(label_surface, anim_rect)
        else:
            # Add animation name text
            font = FontManager.get_font()
            text = font.render(anim_name, fgcolor=(255, 255, 255), size=12)
            if isinstance(text, tuple):  # freetype returns (surface, rect)
                text, text_rect = text
            else:  # pygame.font returns surface
                text_rect = text.get_rect()
            text_rect.center = (anim_rect.width // 2, anim_rect.height // 2)  # ty: ignore[unresolved-attribute]
            label_surface.blit(text, text_rect)  # ty: ignore[invalid-argument-type]

        # Add hover highlighting (only if not editing)
        if (
            self.widget.hovered_animation == anim_name
            and self.widget.editing_animation != anim_name
        ):
            pygame.draw.rect(
                label_surface,
                self.widget.hover_color,
                (0, 0, anim_rect.width, anim_rect.height),
                2,
            )

        return label_surface

    def render_editing_label(self, label_surface: pygame.Surface, anim_rect: pygame.Rect) -> None:
        """Render an animation label in editing mode."""
        from glitchygames.bitmappy.film_strip import CURSOR_BLINK_INTERVAL_MS

        # Update cursor blink state
        current_time = pygame.time.get_ticks()
        if current_time - self.widget.cursor_blink_time > CURSOR_BLINK_INTERVAL_MS:
            self.widget.cursor_visible = not self.widget.cursor_visible
            self.widget.cursor_blink_time = current_time

        font = FontManager.get_font()
        text_color = (200, 220, 255)  # Light blue for editing
        display_text = self.widget.editing_text

        if display_text:
            text = font.render(display_text, fgcolor=text_color, size=12)
            if isinstance(text, tuple):  # freetype returns (surface, rect)
                text, text_rect = text
            else:  # pygame.font returns surface
                text_rect = text.get_rect()
            text_rect.center = (anim_rect.width // 2, anim_rect.height // 2)  # ty: ignore[unresolved-attribute]
            label_surface.blit(text, text_rect)  # ty: ignore[invalid-argument-type]

            # Draw blinking I-beam cursor after the text
            if self.widget.cursor_visible:
                cursor_height = 12
                pygame.draw.line(
                    label_surface,
                    text_color,
                    (text_rect.right + 2, text_rect.centery - cursor_height // 2),  # ty: ignore[unresolved-attribute]
                    (text_rect.right + 2, text_rect.centery + cursor_height // 2),  # ty: ignore[unresolved-attribute]
                    2,
                )
        elif self.widget.cursor_visible:
            # No text yet - show blinking cursor at center
            cursor_height = 12
            center_x = anim_rect.width // 2
            center_y = anim_rect.height // 2
            pygame.draw.line(
                label_surface,
                text_color,
                (center_x, center_y - cursor_height // 2),
                (center_x, center_y + cursor_height // 2),
                2,
            )

        # Add edit mode highlight - subtle cyan border
        pygame.draw.rect(
            label_surface,
            (100, 180, 220),
            (0, 0, anim_rect.width, anim_rect.height),
            2,
        )

    def render(self, surface: pygame.Surface) -> None:
        """Render the film strip to the given surface."""
        if not self.widget.animated_sprite:
            return

        # Debug: Track render calls
        if not hasattr(self.widget, 'render_count'):
            self.widget.render_count = 0
        self.widget.render_count += 1

        # Debug: Print render count every 50 renders
        if self.widget.render_count % 50 == 0:
            LOG.debug(
                'FilmStripWidget: Render #%s, current_frame=%s',
                self.widget.render_count,
                self.widget.current_frame,
            )

        # Clear the film strip area
        surface.fill(self.widget.film_background)

        # Render animation labels
        for anim_name, anim_rect in self.widget.animation_layouts.items():
            label_surface = self.render_animation_label(anim_name, anim_rect)
            surface.blit(label_surface, anim_rect)

        # Render film tabs for frame insertion (before frames so they appear behind borders)
        for tab in self.widget.film_tabs:
            tab.render(surface)

        # Render frames
        self._render_frame_thumbnails(surface)

        # Render sprocket separators
        for sprocket_rect in self.widget.sprocket_layouts:
            sprocket = self.render_sprocket_separator(0, 0, sprocket_rect.height)
            surface.blit(sprocket, sprocket_rect)

        # Render vertical divider between frames and preview
        self.render_vertical_divider(surface)

        # Render darker background for preview area
        self.render_preview_background(surface)

        # Render the animated preview
        self.render_preview(surface)

        # Reset the force redraw flag after all frames have been rendered
        if hasattr(self.widget, 'force_redraw') and self.widget.force_redraw:
            self.widget.force_redraw = False

        # Draw film strip sprockets after everything else
        self.draw_film_sprockets(surface)

        # Draw hover effect for film strip area (when actively hovering over strip)
        # This must be drawn after all other content to appear on top
        if self.widget.is_hovering_strip:
            # Draw a subtle hover effect around the entire film strip
            # Use the surface dimensions, not the rect dimensions
            hover_rect = pygame.Rect(0, 0, surface.get_width(), surface.get_height())
            pygame.draw.rect(surface, (100, 100, 255), hover_rect, 2)

        # Draw multi-controller indicators using new unified system
        self.draw_multi_controller_indicators_new(surface)

    def get_active_controller_selections(self) -> list[dict[str, Any]]:
        """Get active controller selections for the current animation.

        Returns:
            List of dicts with controller_id, frame, and color.

        """
        selections: list[dict[str, Any]] = []
        if not (
            hasattr(self.widget, 'parent_scene')
            and self.widget.parent_scene
            and hasattr(self.widget.parent_scene, 'controller_selections')
        ):
            return selections

        for (
            controller_id,
            controller_selection,
        ) in self.widget.parent_scene.controller_selections.items():
            if not controller_selection.is_active():
                continue
            animation, frame = controller_selection.get_selection()
            if animation != self.widget.current_animation:
                continue
            # Get controller color
            controller_info = None
            for info in self.widget.parent_scene.multi_controller_manager.controllers.values():
                if info.controller_id == controller_id:
                    controller_info = info
                    break
            if controller_info:
                selections.append({
                    'controller_id': controller_id,
                    'frame': frame,
                    'color': controller_info.color,
                })
        return selections

    def draw_multi_controller_indicators_new(self, surface: pygame.Surface) -> None:
        """Draw multi-controller indicators using the controller selections system."""
        # Check if this film strip has any selections
        if not self.widget.animated_sprite or not self.widget.current_animation:
            return

        # Get keyboard selection info
        keyboard_animation = ''
        keyboard_frame = -1
        if (
            hasattr(self.widget, 'parent_scene')
            and self.widget.parent_scene
            and hasattr(self.widget.parent_scene, 'selected_animation')
            and hasattr(self.widget.parent_scene, 'selected_frame')
        ):
            keyboard_animation = self.widget.parent_scene.selected_animation
            keyboard_frame = self.widget.parent_scene.selected_frame

        # Get controller selections from the parent scene
        controller_selections: list[dict[str, Any]] = []
        if (
            hasattr(self.widget, 'parent_scene')
            and self.widget.parent_scene
            and hasattr(self.widget.parent_scene, 'film_strip_controller_selections')
        ):
            # Use the pre-filtered controller selections from the parent scene
            controller_selections = self.widget.parent_scene.film_strip_controller_selections.get(
                self.widget.current_animation,
                [],
            )

        # Draw all indicators using the existing system
        # (collision avoidance handles both keyboard and controllers)
        self.draw_multi_controller_indicators(
            surface,
            keyboard_animation,
            keyboard_frame,
            controller_selections,
        )

    def draw_triforce_indicator(self, surface: pygame.Surface) -> None:
        """Draw triangle indicators for keyboard and multi-controller selections."""
        LOG.debug(
            f'Drawing triforce indicator for animation: {self.widget.current_animation}',
        )

        # Check if this film strip has any selections
        if not self.widget.animated_sprite or not self.widget.current_animation:
            LOG.debug('No animated sprite or current animation')
            return

        # Get keyboard selection info
        keyboard_animation = ''
        keyboard_frame = -1
        if (
            hasattr(self.widget, 'parent_scene')
            and self.widget.parent_scene
            and hasattr(self.widget.parent_scene, 'selected_animation')
            and hasattr(self.widget.parent_scene, 'selected_frame')
        ):
            keyboard_animation = self.widget.parent_scene.selected_animation
            keyboard_frame = self.widget.parent_scene.selected_frame
            # Only print if state changed
            if (
                hasattr(self.widget.parent_scene, '_last_debug_keyboard_animation')
                and hasattr(self.widget.parent_scene, '_last_debug_keyboard_frame')
                and (
                    self.widget.parent_scene._last_debug_keyboard_animation != keyboard_animation
                    or self.widget.parent_scene._last_debug_keyboard_frame != keyboard_frame
                )
            ):
                self.widget.parent_scene._last_debug_keyboard_animation = keyboard_animation
                self.widget.parent_scene._last_debug_keyboard_frame = keyboard_frame

        # Get multi-controller selections
        controller_selections = self.get_active_controller_selections()

        # Draw all indicators
        self.draw_multi_controller_indicators(
            surface,
            keyboard_animation,
            keyboard_frame,
            controller_selections,
        )

    @staticmethod
    def _color_priority(color: tuple[int, ...]) -> int:
        """Return a sort priority for a controller color.

        Args:
            color: RGB color tuple.

        Returns:
            Integer priority (lower is higher priority).

        """
        priority_map: dict[tuple[int, ...], int] = {
            (255, 0, 0): 0,  # Red
            (0, 255, 0): 1,  # Green
            (0, 0, 255): 2,  # Blue
            (255, 255, 0): 3,  # Yellow
        }
        return priority_map.get(color, 999)

    def draw_multi_controller_indicators(
        self,
        surface: pygame.Surface,
        keyboard_animation: str,
        keyboard_frame: int,
        controller_selections: list[dict[str, Any]],
    ) -> None:
        """Draw indicators for keyboard and multiple controllers with collision avoidance."""
        # Collect all selections for this animation
        all_selections: list[dict[str, Any]] = []

        # Add keyboard selection
        if keyboard_animation == self.widget.current_animation:
            all_selections.append({
                'type': 'keyboard',
                'frame': keyboard_frame,
                'color': (255, 255, 255),  # White for keyboard (distinct from controllers)
                'priority': 0,  # Keyboard has highest priority
            })

        # Add controller selections
        all_selections.extend(
            {
                'type': f'controller_{controller_selection["controller_id"]}',
                'frame': controller_selection['frame'],
                'color': controller_selection['color'],
                'priority': self._color_priority(controller_selection['color']),
            }
            for controller_selection in controller_selections
        )

        # Group selections by frame
        frame_groups: dict[Any, list[dict[str, Any]]] = {}
        for selection in all_selections:
            frame: Any = selection['frame']
            if frame not in frame_groups:
                frame_groups[frame] = []
            frame_groups[frame].append(selection)

        # Draw indicators for each frame group
        for frame, selections in frame_groups.items():
            frame_key = (self.widget.current_animation, frame)
            if frame_key in self.widget.frame_layouts:
                frame_rect = self.widget.frame_layouts[frame_key]
                self._draw_frame_indicators(surface, frame_rect, selections)

    def _draw_frame_indicators(
        self,
        surface: pygame.Surface,
        frame_rect: pygame.Rect,
        selections: list[dict[str, Any]],
    ) -> None:
        """Draw indicators for a specific frame with collision avoidance."""
        # Unified positioning for all scenarios
        self._draw_unified_indicators(surface, frame_rect, selections)

    def _draw_unified_indicators(
        self,
        surface: pygame.Surface,
        frame_rect: pygame.Rect,
        selections: list[dict[str, Any]],
    ) -> None:
        """Unified positioning for all scenarios with proper centering."""
        # Separate keyboard from controllers
        keyboard_selection: dict[str, Any] | None = None
        controller_selections: list[dict[str, Any]] = []

        for selection in selections:
            if selection['color'] == (255, 255, 255):  # White = keyboard
                keyboard_selection = selection
            else:
                controller_selections.append(selection)

        # Sort controllers by color order (Red, Green, Blue, Yellow)
        controller_selections.sort(key=lambda s: self._color_priority(s['color']))

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

    def draw_preview_triangle(self, surface: pygame.Surface, preview_rect: pygame.Rect) -> None:
        """Draw a triangle underneath the animation preview that moves from left to right."""
        # Calculate position below the preview
        preview_bottom_y = preview_rect.bottom

        # Position triangle 4 pixels below the preview
        triangle_y = preview_bottom_y + 4

        # Calculate animation progress for this preview
        anim_name = None
        for name, rect in self.widget.preview_rects.items():
            if rect == preview_rect:
                anim_name = name
                break

        if anim_name and anim_name in self.widget.preview_animation_times:
            # Get animation progress using actual frame timings
            current_time = self.widget.preview_animation_times[anim_name]

            # Get the current frame index and progress within that frame
            current_frame_idx = self.widget.animation.get_current_preview_frame(anim_name)
            assert self.widget.animated_sprite is not None
            frames = self.widget.animated_sprite.animations.get(anim_name, [])

            # Check if there's only one frame - if so, center the triangle and disable animation
            if frames and len(frames) == 1:
                # Single frame: center the triangle and don't animate
                triangle_x = preview_rect.centerx
            elif frames and current_frame_idx < len(frames):
                # Multiple frames: animate the triangle
                # Calculate overall animation progress
                total_duration = sum(self.widget.preview_frame_durations.get(anim_name, [0.5]))
                overall_progress = (
                    (current_time % total_duration) / total_duration if total_duration > 0 else 0.0
                )

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
        self._draw_triangle_preview(surface, int(triangle_x), triangle_y)

    def _draw_preview_frame_index(
        self,
        surface: pygame.Surface,
        preview_rect: pygame.Rect,
        anim_name: str,
    ) -> None:
        """Draw the current frame index on the animation preview."""
        try:
            # Get the current frame index for this animation
            current_frame_idx = self.widget.animation.get_current_preview_frame(anim_name)

            # Get total frames for this animation
            total_frames = 1  # Default fallback
            if (
                hasattr(self.widget, 'animated_sprite')
                and self.widget.animated_sprite
                and anim_name in self.widget.animated_sprite.animations
            ):
                total_frames = len(self.widget.animated_sprite.animations[anim_name])

            # Create font for frame index
            font = pygame.font.Font(None, 14)  # Slightly larger than frame numbers

            # Render frame index text in format "current+1/total"
            frame_text = f'{current_frame_idx + 1}/{total_frames}'
            text_surface = font.render(
                frame_text,
                antialias=True,
                color=(255, 255, 255),
            )  # White text
            text_rect = text_surface.get_rect()

            # Position at bottom center of the preview
            text_x = preview_rect.x + (preview_rect.width - text_rect.width) // 2
            text_y = (
                preview_rect.y + preview_rect.height - text_rect.height - 4
            )  # 4 pixels from bottom

            # Draw text
            surface.blit(text_surface, (text_x, text_y))
        except Exception:
            # Log font rendering failures
            LOG.exception('Font rendering failed')

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
            (center_x + size, center_y + size),  # Bottom right
        ]

        # Draw filled triangle
        pygame.draw.polygon(surface, color, triangle_points)
        # Draw border
        pygame.draw.polygon(surface, border_color, triangle_points, 1)

    def _draw_triangle(
        self,
        surface: pygame.Surface,
        center_x: int,
        center_y: int,
        color: tuple[int, ...] = (255, 0, 0),
    ) -> None:
        """Draw a simple triangle pointing to the given center coordinates."""
        # Triangle properties
        size = 2  # Smaller size
        border_color: tuple[int, ...] = color  # Same color as fill

        # Calculate positions for a simple triangle pointing down
        triangle_points = [
            (center_x, center_y + size),  # Bottom point
            (center_x - size, center_y - size),  # Top left
            (center_x + size, center_y - size),  # Top right
        ]

        # Draw filled triangle
        pygame.draw.polygon(surface, color, triangle_points)
        # Draw border
        pygame.draw.polygon(surface, border_color, triangle_points, 1)

    def draw_film_sprockets(self, surface: pygame.Surface) -> None:
        """Draw film strip sprockets on the main background."""
        sprocket_color = (60, 50, 40)  # Even darker grey-brown color

        # Draw sprockets along the top edge - aligned with bottom sprockets, avoiding label area
        # Use pre-calculated animation layouts to avoid label area
        label_left = 0
        label_right = 0
        if (
            self.widget.current_animation
            and self.widget.current_animation in self.widget.animation_layouts
        ):
            # Use the pre-calculated animation layout
            label_rect = self.widget.animation_layouts[self.widget.current_animation]
            label_left = label_rect.left
            label_right = label_rect.right

        # Draw top sprockets aligned with bottom sprockets, avoiding label area
        # Use the same calculation as bottom sprockets to ensure perfect alignment
        sprocket_spacing = 17
        total_width = self.widget.rect.width - 20  # Leave 10px margin on each side

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
                    rect = pygame.Rect(
                        x - 3,
                        7 + top_margin - 20,
                        6,
                        6,
                    )  # 6x6 rectangle centered at (x, 10 + top_margin - 20)
                    pygame.draw.rect(surface, sprocket_color, rect, border_radius=3)

        # Draw two sets of sprockets along the bottom edge
        # - same distance from bottom as top sprockets are from top
        # Top sprockets are at y=7, so bottom sprockets should be at height-7
        bottom_sprocket_y = self.widget.rect.height - 7

        # Calculate how many sprockets we can fit across the full width
        sprocket_spacing = 17
        total_width = self.widget.rect.width - 20  # Leave 10px margin on each side

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
                    rect = pygame.Rect(
                        x - 3,
                        bottom_sprocket_y - 5,
                        6,
                        6,
                    )  # 6x6 rectangle 5 pixels above first set
                    pygame.draw.rect(surface, sprocket_color, rect, border_radius=3)

    def render_removal_button(
        self,
        surface: pygame.Surface,
        anim_name: str,
        frame_idx: int,
    ) -> None:
        """Render a removal button for a specific frame.

        Args:
            surface: Surface to render on
            anim_name: Animation name
            frame_idx: Frame index

        """
        if (
            not hasattr(self.widget, 'removal_button_layouts')
            or not self.widget.removal_button_layouts
        ):
            LOG.debug(
                f'FilmStripWidget: No removal button layouts for {anim_name}[{frame_idx}]',
            )
            return

        button_key = (anim_name, frame_idx)
        if button_key not in self.widget.removal_button_layouts:
            LOG.debug(
                f'FilmStripWidget: No removal button layout for {anim_name}[{frame_idx}]',
            )
            return

        button_rect = self.widget.removal_button_layouts[button_key]

        # Don't render removal button if this is the last frame (can't remove it)
        if (
            self.widget.animated_sprite
            and anim_name in self.widget.animated_sprite.animations
            and len(self.widget.animated_sprite.animations[anim_name]) <= 1
        ):
            LOG.debug(
                'FilmStripWidget: Skipping removal button for '
                f'{anim_name}[{frame_idx}] - only one frame',
            )
            return

        LOG.debug(
            'FilmStripWidget: Rendering removal button for '
            f'{anim_name}[{frame_idx}] at {button_rect}',
        )

        # Check if this removal button is being hovered
        is_hovered = self.widget.hovered_removal_button == (anim_name, frame_idx)

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
        pygame.draw.rect(surface, border_color, (center_x - 1, center_y, 3, 1))
