"""Film strip widget for animated sprite frame selection.

This module provides a film reel-style interface for selecting and navigating
between frames in animated sprites, with sprocket separators between animations.
"""

# No typing imports needed

import pygame
from glitchygames.sprites import AnimatedSprite


class FilmStripWidget:
    """Film reel-style widget for frame selection in animated sprites."""

    def __init__(self, x: int, y: int, width: int, height: int):
        """Initialize the film strip widget."""
        self.rect = pygame.Rect(x, y, width, height)
        self.animated_sprite: AnimatedSprite | None = None
        self.current_animation = "idle"  # Default, will be updated when sprite is set
        self.current_frame = 0
        self.hovered_frame: tuple[str, int] | None = None
        self.hovered_animation: str | None = None

        # Film strip styling
        self.frame_width = 64
        self.frame_height = 64
        self.sprocket_width = 20
        self.frame_spacing = 2
        self.animation_label_height = 20

        # Colors
        self.film_background = (40, 40, 40)
        self.sprocket_color = (20, 20, 20)
        self.frame_border = (60, 60, 60)
        self.selection_color = (255, 255, 0)  # Yellow film leader
        self.hover_color = (100, 100, 100)

        # Layout cache
        self.frame_layouts: dict[tuple[str, int], pygame.Rect] = {}
        self.animation_layouts: dict[str, pygame.Rect] = {}
        self.sprocket_layouts: list[pygame.Rect] = []

    def set_animated_sprite(self, animated_sprite: AnimatedSprite) -> None:
        """Set the animated sprite to display."""
        self.animated_sprite = animated_sprite
        # Prefer "idle" animation if available, otherwise use first animation
        if "idle" in animated_sprite.frames:
            self.current_animation = "idle"
        else:
            self.current_animation = (
                next(iter(animated_sprite.frames.keys())) if animated_sprite.frames else "idle"
            )
        self.current_frame = 0
        self._calculate_layout()

    def _calculate_layout(self) -> None:
        """Calculate the layout of frames and sprockets."""
        if not self.animated_sprite:
            return

        self.frame_layouts.clear()
        self.animation_layouts.clear()
        self.sprocket_layouts.clear()

        x_offset = 0

        for anim_name, frames in self.animated_sprite.frames.items():
            # Calculate animation label area
            animation_width = len(frames) * (self.frame_width + self.frame_spacing)
            self.animation_layouts[anim_name] = pygame.Rect(
                x_offset, 0, animation_width, self.animation_label_height
            )

            # Calculate frame positions
            for frame_idx, _frame in enumerate(frames):
                frame_x = x_offset + frame_idx * (self.frame_width + self.frame_spacing)
                frame_rect = pygame.Rect(
                    frame_x, self.animation_label_height, self.frame_width, self.frame_height
                )
                self.frame_layouts[anim_name, frame_idx] = frame_rect

            x_offset += animation_width

            # Add sprocket separator (except for last animation)
            if anim_name != list(self.animated_sprite.frames.keys())[-1]:
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
        if (self.animated_sprite and animation in self.animated_sprite.frames and
            0 <= frame < len(self.animated_sprite.frames[animation])):
            self.current_animation = animation
            self.current_frame = frame

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
        if clicked_animation and clicked_animation in self.animated_sprite.frames:
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
        # Create frame surface
        frame_surface = pygame.Surface((self.frame_width, self.frame_height))
        frame_surface.fill(self.film_background)

        # Draw the actual frame image
        if hasattr(frame, "image") and frame.image:
            # Scale the frame image to fit
            scaled_image = pygame.transform.scale(
                frame.image, (self.frame_width - 8, self.frame_height - 8)
            )
            frame_surface.blit(scaled_image, (4, 4))

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

    def render(self, surface: pygame.Surface) -> None:
        """Render the film strip to the given surface."""
        if not self.animated_sprite:
            return

        # Clear the film strip area
        surface.fill(self.film_background, self.rect)

        # Render animation labels
        for anim_name, anim_rect in self.animation_layouts.items():
            # Draw animation label background
            label_surface = pygame.Surface((anim_rect.width, anim_rect.height))
            label_surface.fill(self.film_background)

            # Add animation name text
            font = pygame.font.Font(None, 16)
            text = font.render(anim_name, antialias=True, color=(255, 255, 255))
            text_rect = text.get_rect(center=(anim_rect.width // 2, anim_rect.height // 2))
            label_surface.blit(text, text_rect)

            # Add hover highlighting
            if self.hovered_animation == anim_name:
                pygame.draw.rect(
                    label_surface, self.hover_color, (0, 0, anim_rect.width, anim_rect.height), 2
                )

            surface.blit(label_surface, anim_rect)

        # Render frames
        for (anim_name, frame_idx), frame_rect in self.frame_layouts.items():
            if anim_name in self.animated_sprite.frames and frame_idx < len(
                self.animated_sprite.frames[anim_name]
            ):
                frame = self.animated_sprite.frames[anim_name][frame_idx]

                # Determine if this frame is selected or hovered
                is_selected = (
                    anim_name == self.current_animation and frame_idx == self.current_frame
                )
                is_hovered = self.hovered_frame == (anim_name, frame_idx)

                # Render frame thumbnail
                frame_thumbnail = self.render_frame_thumbnail(frame, is_selected, is_hovered)

                # Blit to surface
                if is_selected:
                    # For selected frames, blit the selection border
                    surface.blit(frame_thumbnail, (frame_rect.x - 2, frame_rect.y - 2))
                else:
                    surface.blit(frame_thumbnail, frame_rect)

        # Render sprocket separators
        for sprocket_rect in self.sprocket_layouts:
            sprocket = self.render_sprocket_separator(0, 0, sprocket_rect.height)
            surface.blit(sprocket, sprocket_rect)

    def get_total_width(self) -> int:
        """Get the total width needed for the film strip."""
        if not self.animated_sprite:
            return 0

        total_width = 0
        for anim_name, frames in self.animated_sprite.frames.items():
            total_width += len(frames) * (self.frame_width + self.frame_spacing)
            if anim_name != list(self.animated_sprite.frames.keys())[-1]:
                total_width += self.sprocket_width

        return total_width
