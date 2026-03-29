"""Film strip widget for animated sprite frame selection.

This module provides a film reel-style interface for selecting and navigating
between frames in animated sprites, with sprocket separators between animations.

The FilmStripWidget class delegates to four composition classes:
- FilmStripLayout: Layout calculation, caches, scroll, hit-testing
- FilmStripRendering: All rendering/drawing operations
- FilmStripAnimation: Animation preview timing and frame calculation
- FilmStripEventHandler: Click/hover/keyboard handling, copy/paste, frame ops
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

import pygame

if TYPE_CHECKING:
    from glitchygames.bitmappy.editor import AnimatedCanvasSprite
    from glitchygames.events.base import HashableEvent
    from glitchygames.sprites import AnimatedSprite, SpriteFrame

from .film_strip_animation import FilmStripAnimation
from .film_strip_events import FilmStripEventHandler
from .film_strip_layout import FilmStripLayout
from .film_strip_rendering import FilmStripRendering

ANIMATION_NAME_MAX_LENGTH = 50
CURSOR_BLINK_INTERVAL_MS = 530

LOG = logging.getLogger('game.tools.film_strip')
LOG.addHandler(logging.NullHandler())


class FilmStripWidget:  # noqa: PLR0904
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

    def __init__(self, x: int, y: int, width: int, height: int) -> None:  # noqa: PLR0915
        """Initialize the film strip widget."""
        self.rect = pygame.Rect(x, y, width, height)
        self.animated_sprite: AnimatedSprite | None = None
        self.current_animation = ''  # Will be set when sprite is loaded
        self.current_frame = 0  # Animation preview frame (right side)
        self.selected_frame = 0  # Selected frame in static thumbnails (left side)
        self.is_selected = False  # Track if this film strip is currently selected
        self.hovered_frame: tuple[str, int] | None = None
        self.hovered_animation: str | None = None
        self.hovered_preview: str | None = None
        self.is_hovering_strip: bool = False
        self.hovered_removal_button: tuple[str, int] | None = (
            None  # Track which removal button is hovered
        )

        # Animation rename editing state
        self.editing_animation: str | None = (
            None  # Animation name being edited (None = not editing)
        )
        self.editing_text: str = ''  # Text buffer for editing
        self.original_animation_name: str | None = None  # Original name before editing started
        self.cursor_blink_time: int = 0  # Last time cursor blink toggled
        self.cursor_visible: bool = True  # Whether cursor is currently visible

        # Color cycling state
        self.background_color_index = 2  # Start with gray instead of cyan
        self.background_color = self.BACKGROUND_COLORS[self.background_color_index]

        # Instance variables assigned outside __init__ but need declarations
        self.scroll_offset: int = 0
        self.debug_last_dump_time: float = 0.0
        self.debug_start_time: float = 0.0
        self.force_redraw: bool = False
        self.render_count: int = 0

        # Styling attributes (initialized by layout delegate)
        self.frame_width: int = 0
        self.frame_height: int = 0
        self.sprocket_width: int = 0
        self.frame_spacing: int = 0
        self.animation_label_height: int = 0
        self.preview_width: int = 0
        self.preview_height: int = 0
        self.preview_padding: int = 0
        self.film_background: tuple[int, int, int] = (0, 0, 0)
        self.sprocket_color: tuple[int, int, int] = (0, 0, 0)
        self.frame_border: tuple[int, int, int] = (0, 0, 0)
        self.selection_color: tuple[int, int, int] = (0, 0, 0)
        self.first_frame_color: tuple[int, int, int] = (0, 0, 0)
        self.hover_color: tuple[int, int, int] = (0, 0, 0)
        self.frame_background: tuple[int, int, int] = (0, 0, 0)
        self.preview_background: tuple[int, int, int] = (0, 0, 0)
        self.preview_border: tuple[int, int, int] = (0, 0, 0)
        self.animation_border: tuple[int, int, int] = (0, 0, 0)
        self.film_tabs: list[Any] = []
        self.tab_width: int = 0
        self.tab_height: int = 0
        self.inter_frame_gap: int = 0
        self.ANIMATION_CHANGE_THRESHOLD: float = 0.0

        # Layout caches (initialized by layout delegate)
        self.frame_layouts: dict[tuple[str, int], pygame.Rect] = {}
        self.animation_layouts: dict[str, pygame.Rect] = {}
        self.sprocket_layouts: list[pygame.Rect] = []
        self.preview_rects: dict[str, pygame.Rect] = {}
        self.preview_animation_times: dict[str, float] = {}
        self.preview_animation_speeds: dict[str, float] = {}
        self.preview_frame_durations: dict[str, list[float]] = {}
        self.removal_button_layouts: dict[tuple[str, int], pygame.Rect] = {}

        # External references (initialized by layout delegate)
        self.copied_frame: Any = None
        self.parent_canvas: Any = None
        self.parent_scene: Any = None
        self.film_strip_sprite: Any = None

        # Create composition delegates
        self.layout = FilmStripLayout(widget=self)
        self.renderer = FilmStripRendering(widget=self)
        self.animation = FilmStripAnimation(widget=self)
        self.event_handler = FilmStripEventHandler(widget=self)

        # Initialize styling, layout caches, and external references (from layout delegate)
        self.layout.initialize_styling()
        self.layout.initialize_layout_caches()
        self.layout.initialize_external_references()

    def set_animated_sprite(self, animated_sprite: AnimatedSprite) -> None:
        """Set the animated sprite to display."""
        LOG.debug(f'FilmStripWidget: set_animated_sprite called with sprite: {animated_sprite}')
        LOG.debug(
            f'FilmStripWidget: Sprite has {len(animated_sprite.animations)} animations: '
            f'{list(animated_sprite.animations.keys())}',
        )

        self.animated_sprite = animated_sprite

        # Clear any stale animation state from previous sprites
        self.preview_animation_times.clear()
        self.preview_animation_speeds.clear()
        self.preview_frame_durations.clear()

        # Use sprite introspection to find the first animation
        if animated_sprite.animations:
            if hasattr(animated_sprite, '_animation_order') and animated_sprite.animation_order:
                # Use the first animation in the file order
                self.current_animation = animated_sprite.animation_order[0]
                LOG.debug(
                    'FilmStripWidget: Using first animation from _animation_order: '
                    f'{self.current_animation}',
                )
            else:
                # Fall back to the first key in _animations
                self.current_animation = next(iter(animated_sprite.animations.keys()))
                LOG.debug(
                    'FilmStripWidget: Using first animation from _animations: '
                    f'{self.current_animation}',
                )

            # Configure the animated sprite to loop and start playing for preview
            LOG.debug(f"FilmStripWidget: Setting animation to '{self.current_animation}'")
            animated_sprite.set_animation(self.current_animation)
            LOG.debug(
                'FilmStripWidget: After set_animation - current_animation: '
                f'{getattr(animated_sprite, "current_animation", "None")}',
            )

            LOG.debug('FilmStripWidget: Setting is_looping to True')
            animated_sprite.is_looping = True  # Enable looping for continuous preview
            LOG.debug(
                'FilmStripWidget: After setting is_looping - is_looping: '
                f'{getattr(animated_sprite, "is_looping", "None")}',
            )

            LOG.debug('FilmStripWidget: Calling play()')
            animated_sprite.play()  # Start playing the animation
            LOG.debug(
                'FilmStripWidget: After play() - is_playing: '
                f'{getattr(animated_sprite, "is_playing", "None")}',
            )
            LOG.debug(
                'FilmStripWidget: After play() - current_frame: '
                f'{getattr(animated_sprite, "current_frame", "None")}',
            )
        else:
            self.current_animation = ''
            LOG.debug(
                'FilmStripWidget: No animations found, setting current_animation to empty string',
            )
        self.current_frame = 0
        self.scroll_offset = 0  # Horizontal scroll offset for rolling effect
        LOG.debug(
            f'FilmStripWidget: Final state - current_animation: {self.current_animation}, '
            f'current_frame: {self.current_frame}',
        )

        # Initialize animation timing for previews
        self.animation.initialize_preview_animations()

        # Mark as dirty since we've set up animations to play
        self.mark_dirty()
        LOG.debug('FilmStripWidget: Marked as dirty after setting up animations')
        LOG.debug(
            'FilmStripWidget: _force_redraw after mark_dirty: '
            f'{getattr(self, "force_redraw", False)}',
        )

        self.layout.calculate_layout()
        self.layout.update_height()

    def set_parent_canvas(self, canvas: AnimatedCanvasSprite) -> None:
        """Set the parent canvas for getting current canvas data."""
        self.parent_canvas = canvas

    def mark_dirty(self) -> None:
        """Mark the film strip widget as needing a re-render.

        Sets dirty=1 on this film strip's sprite so that the next
        Scene.update() call triggers force_redraw() and LayeredDirty
        blits the updated surface to the screen.
        """
        self.force_redraw = True

        if hasattr(self, 'film_strip_sprite') and self.film_strip_sprite:
            self.film_strip_sprite.dirty = 1

    # ---- Forwarding methods for backward compatibility ----
    # These preserve the existing external API so callers don't need to change.

    def render(self, surface: pygame.Surface) -> None:
        """Render the film strip to the given surface."""
        self.renderer.render(surface)

    def update_animations(self, dt: float) -> None:
        """Update animation timing for all previews."""
        self.animation.update_animations(dt)

    def update_layout(self) -> None:
        """Update the layout of frames and sprockets."""
        self.layout.update_layout()

    def update_scroll_for_frame(self, frame_index: int) -> None:
        """Update scroll offset to keep the selected frame visible and centered."""
        self.layout.update_scroll_for_frame(frame_index)

    def handle_click(
        self,
        pos: tuple[int, int],
        *,
        is_right_click: bool = False,
        is_shift_click: bool = False,
    ) -> tuple[str, int] | None:
        """Handle a click on the film strip.

        Returns:
            tuple[str, int] | None: The clicked animation and frame, or None.

        """
        return self.event_handler.handle_click(
            pos, is_right_click=is_right_click, is_shift_click=is_shift_click
        )

    def handle_hover(self, pos: tuple[int, int]) -> None:
        """Handle mouse hover over the film strip."""
        self.event_handler.handle_hover(pos)

    def handle_keyboard_input(self, event: HashableEvent) -> bool:
        """Handle keyboard input for animation renaming.

        Returns:
            True if the event was handled.

        """
        return self.event_handler.handle_keyboard_input(event)

    def handle_frame_click(self, pos: tuple[int, int]) -> tuple[str, int] | None:
        """Handle mouse click on the film strip.

        Returns:
            tuple[str, int] | None: The clicked animation and frame, or None.

        """
        return self.event_handler.handle_frame_click(pos)

    def handle_preview_click(self, pos: tuple[int, int]) -> tuple[str, int] | None:
        """Handle mouse click on the preview area.

        Returns:
            tuple[str, int] | None: The clicked animation and frame, or None.

        """
        return self.event_handler.handle_preview_click(pos)

    def set_current_frame(self, animation: str, frame: int) -> None:
        """Set the current animation and selected frame."""
        self.event_handler.set_current_frame(animation, frame)

    def set_frame_index(self, frame_index: int) -> None:
        """Set the current frame and update the canvas."""
        self.event_handler.set_frame_index(frame_index)

    def copy_current_frame(self) -> bool:
        """Copy the currently selected frame to the clipboard.

        Returns:
            True if copy was successful.

        """
        return self.event_handler.copy_current_frame()

    def paste_to_current_frame(self) -> bool:
        """Paste the copied frame to the currently selected frame.

        Returns:
            True if paste was successful.

        """
        return self.event_handler.paste_to_current_frame()

    def reset_all_tab_states(self) -> None:
        """Reset click and hover states for all tabs."""
        self.event_handler.reset_all_tab_states()

    def get_frame_at_position(self, pos: tuple[int, int]) -> tuple[str, int] | None:
        """Get the animation and frame at the given position.

        Returns:
            tuple[str, int] | None: The frame at position, or None.

        """
        return self.layout.get_frame_at_position(pos)

    def get_animation_at_position(self, pos: tuple[int, int]) -> str | None:
        """Get the animation at the given position.

        Returns:
            str | None: The animation name, or None.

        """
        return self.layout.get_animation_at_position(pos)

    def get_preview_at_position(self, pos: tuple[int, int]) -> str | None:
        """Get the preview animation at the given position.

        Returns:
            str | None: The preview animation name, or None.

        """
        return self.layout.get_preview_at_position(pos)

    def get_removal_button_at_position(self, pos: tuple[int, int]) -> tuple[str, int] | None:
        """Get the removal button at the given position.

        Returns:
            tuple[str, int] | None: The animation and frame of the button, or None.

        """
        return self.layout.get_removal_button_at_position(pos)

    def get_total_width(self) -> int:
        """Get the total width needed for the film strip.

        Returns:
            int: The total width.

        """
        return self.layout.get_total_width()

    def get_current_preview_frame(self, anim_name: str) -> int:
        """Get the current frame index for a preview animation.

        Returns:
            int: The current preview frame index.

        """
        return self.animation.get_current_preview_frame(anim_name)

    def _initialize_preview_animations(self) -> None:
        """Initialize animation timing for all previews."""
        self.animation.initialize_preview_animations()

    def _remove_frame(self, animation_name: str, frame_index: int) -> None:
        """Remove a frame from the animated sprite."""
        self.event_handler.remove_frame(animation_name, frame_index)

    def _update_height(self) -> None:
        """Update the film strip height based on the number of animations."""
        self.layout.update_height()

    def _calculate_scroll_offset(self, frame_index: int, frames: list[SpriteFrame]) -> int:
        """Calculate the scroll offset to center a frame.

        Returns:
            int: The scroll offset.

        """
        return self.layout.calculate_scroll_offset(frame_index, frames)

    @staticmethod
    def _get_frame_image(frame: SpriteFrame) -> pygame.Surface | None:
        """Get the image surface for a frame.

        Returns:
            pygame.Surface | None: The frame image.

        """
        return FilmStripAnimation.get_frame_image(frame)

    def _get_frame_image_for_rendering(
        self,
        frame: SpriteFrame,
        *,
        is_selected: bool = False,
    ) -> pygame.Surface | None:
        """Get the appropriate frame image for rendering.

        Returns:
            pygame.Surface | None: The frame image for rendering.

        """
        return self.renderer.get_frame_image_for_rendering(frame, is_selected=is_selected)

    # ---- Layout delegate forwarding (internal) ----

    def _calculate_layout(self) -> None:
        """Calculate the layout of frames and sprockets."""
        self.layout.calculate_layout()

    def _clear_layouts(self) -> None:
        """Clear all layout caches."""
        self.layout.clear_layouts()

    def _calculate_animation_layouts(self) -> None:
        """Calculate layout for animation labels."""
        self.layout.calculate_animation_layouts()

    def _calculate_frame_layouts(self) -> None:
        """Calculate layout for frame positions."""
        self.layout.calculate_frame_layouts()

    def _calculate_preview_layouts(self) -> None:
        """Calculate layout for preview areas."""
        self.layout.calculate_preview_layouts()

    def _calculate_sprocket_layouts(self) -> None:
        """Calculate layout for sprocket separators."""
        self.layout.calculate_sprocket_layouts()

    def _calculate_sprocket_start_x(self) -> int:
        """Calculate sprocket start x position.

        Returns:
            int: The x position.

        """
        return self.layout.calculate_sprocket_start_x()

    def _calculate_frame_y(self, y_offset: int) -> int:
        """Calculate the Y position for frames.

        Returns:
            int: The y position.

        """
        return self.layout.calculate_frame_y(y_offset)

    def _add_removal_button(
        self, anim_name: str, actual_frame_idx: int, frame_x: int, frame_y: int
    ) -> None:
        """Add a removal button layout for a frame."""
        self.layout.add_removal_button(anim_name, actual_frame_idx, frame_x, frame_y)

    def _calculate_frames_width(self) -> int:
        """Calculate the total width needed for all frames and sprockets.

        Returns:
            int: The width.

        """
        return self.layout.calculate_frames_width()

    def _has_valid_canvas_sprite(self) -> bool:
        """Check if the parent scene has a valid canvas with an animated sprite.

        Returns:
            bool: True if valid.

        """
        return self.layout.has_valid_canvas_sprite()

    def _create_film_tabs(self) -> None:
        """Create film tabs for frame insertion points."""
        self.layout.create_film_tabs()

    # ---- Animation delegate forwarding (internal) ----

    def _dump_animation_debug_state(self, dt: float) -> None:
        """Dump animation state for debugging."""
        self.animation.dump_animation_debug_state(dt)

    def _dump_animated_sprite_debug(self) -> None:
        """Dump animated sprite debug info."""
        self.animation.dump_animated_sprite_debug()

    @staticmethod
    def _get_stale_frame_surface(frame: SpriteFrame) -> pygame.Surface | None:
        """Build a surface from pixel data when the cached image is stale.

        Returns:
            pygame.Surface | None: The surface.

        """
        return FilmStripAnimation.get_stale_frame_surface(frame)

    # ---- Rendering delegate forwarding (internal) ----

    def render_frame_thumbnail(
        self,
        frame: SpriteFrame,
        *,
        is_selected: bool = False,
        is_hovered: bool = False,
        frame_index: int = 0,
        animation_name: str = '',
    ) -> pygame.Surface:
        """Render a single frame thumbnail.

        Returns:
            pygame.Surface: The rendered thumbnail.

        """
        return self.renderer.render_frame_thumbnail(
            frame,
            is_selected=is_selected,
            is_hovered=is_hovered,
            frame_index=frame_index,
            animation_name=animation_name,
        )

    def render_preview(self, surface: pygame.Surface) -> None:
        """Render individual previews for each animation."""
        self.renderer.render_preview(surface)

    def render_sprocket_separator(self, _x: int, _y: int, height: int) -> pygame.Surface:
        """Render a sprocket separator.

        Returns:
            pygame.Surface: The separator surface.

        """
        return self.renderer.render_sprocket_separator(_x, _y, height)

    def _add_film_strip_styling(self, frame_surface: pygame.Surface) -> None:
        """Add film strip edges to the frame surface."""
        self.renderer.add_film_strip_styling(frame_surface)

    def _add_hover_highlighting(self, frame_surface: pygame.Surface) -> None:
        """Add hover highlighting to the frame surface."""
        self.renderer.add_hover_highlighting(frame_surface)

    def _create_selection_border(self, frame_surface: pygame.Surface) -> pygame.Surface:
        """Create a selection border for the selected frame.

        Returns:
            pygame.Surface: The selection border.

        """
        return self.renderer.create_selection_border(frame_surface)

    def _add_3d_beveled_border(self, frame_surface: pygame.Surface) -> None:
        """Add 3D beveled border like the right side animation frame."""
        self.renderer.add_3d_beveled_border(frame_surface)

    def _draw_placeholder(self, frame_surface: pygame.Surface) -> None:
        """Draw a placeholder when no frame data is available."""
        self.renderer.draw_placeholder(frame_surface)

    def _draw_film_sprockets(self, surface: pygame.Surface) -> None:
        """Draw film strip sprockets on the main background."""
        self.renderer.draw_film_sprockets(surface)

    def _draw_multi_controller_indicators(
        self,
        surface: pygame.Surface,
        keyboard_animation: str,
        keyboard_frame: int,
        controller_selections: list[dict[str, Any]],
    ) -> None:
        """Draw indicators for keyboard and multiple controllers."""
        self.renderer.draw_multi_controller_indicators(
            surface, keyboard_animation, keyboard_frame, controller_selections
        )

    def _draw_triforce_indicator(self, surface: pygame.Surface) -> None:
        """Draw triangle indicators for keyboard and multi-controller selections."""
        self.renderer.draw_triforce_indicator(surface)

    def _draw_multi_controller_indicators_new(self, surface: pygame.Surface) -> None:
        """Draw multi-controller indicators using the controller selections system."""
        self.renderer.draw_multi_controller_indicators_new(surface)

    def _get_active_controller_selections(self) -> list[dict[str, Any]]:
        """Get active controller selections for the current animation.

        Returns:
            list[dict[str, Any]]: The selections.

        """
        return self.renderer.get_active_controller_selections()

    def _draw_preview_triangle(self, surface: pygame.Surface, preview_rect: pygame.Rect) -> None:
        """Draw a triangle underneath the animation preview."""
        self.renderer.draw_preview_triangle(surface, preview_rect)

    def _render_animation_label(self, anim_name: str, anim_rect: pygame.Rect) -> pygame.Surface:
        """Render a single animation label surface.

        Returns:
            pygame.Surface: The label surface.

        """
        return self.renderer.render_animation_label(anim_name, anim_rect)

    def _render_editing_label(self, label_surface: pygame.Surface, anim_rect: pygame.Rect) -> None:
        """Render an animation label in editing mode."""
        self.renderer.render_editing_label(label_surface, anim_rect)

    def _render_vertical_divider(self, surface: pygame.Surface) -> None:
        """Render a vertical divider between the frames and preview area."""
        self.renderer.render_vertical_divider(surface)

    def _render_preview_background(self, surface: pygame.Surface) -> None:
        """Render a darker background for the preview area."""
        self.renderer.render_preview_background(surface)

    def _render_removal_button(
        self, surface: pygame.Surface, anim_name: str, frame_idx: int
    ) -> None:
        """Render a removal button for a specific frame."""
        self.renderer.render_removal_button(surface, anim_name, frame_idx)

    @staticmethod
    def _convert_magenta_to_transparent(surface: pygame.Surface) -> pygame.Surface:
        """Convert magenta pixels to transparent.

        Returns:
            pygame.Surface: The converted surface.

        """
        return FilmStripRendering.convert_magenta_to_transparent(surface)

    # ---- Event handler delegate forwarding (internal) ----

    def _is_keyboard_selected(self, animation_name: str, frame_index: int) -> bool:
        """Check if a frame is selected via keyboard navigation.

        Returns:
            bool: True if keyboard-selected.

        """
        return self.event_handler.is_keyboard_selected(animation_name, frame_index)

    def _get_controller_selection_color(
        self, animation_name: str, frame_index: int
    ) -> tuple[int, int, int] | None:
        """Get the controller color if a controller has this frame selected.

        Returns:
            tuple[int, int, int] | None: The controller color.

        """
        return self.event_handler.get_controller_selection_color(animation_name, frame_index)

    def _toggle_onion_skinning(self, animation_name: str, frame_index: int) -> None:
        """Toggle onion skinning for a specific frame."""
        self.event_handler.toggle_onion_skinning(animation_name, frame_index)

    def _handle_tab_click(self, pos: tuple[int, int]) -> bool:
        """Handle mouse click on film tabs.

        Returns:
            bool: True if a tab was clicked.

        """
        return self.event_handler.handle_tab_click(pos)

    def _handle_tab_hover(self, pos: tuple[int, int]) -> bool:
        """Handle mouse hover over film tabs.

        Returns:
            bool: True if hovering.

        """
        return self.event_handler.handle_tab_hover(pos)

    def _handle_add_animation_tab_click(self) -> None:
        """Handle click on the add-animation tab."""
        self.event_handler.handle_add_animation_tab_click()

    def _handle_delete_animation_tab_click(self) -> None:
        """Handle click on the delete-animation tab."""
        self.event_handler.handle_delete_animation_tab_click()

    def _handle_removal_button_click(self, pos: tuple[int, int]) -> bool:
        """Handle clicks on removal buttons.

        Returns:
            bool: True if a removal button was clicked.

        """
        return self.event_handler.handle_removal_button_click(pos)

    def _stop_animation_before_deletion(self, animation_name: str, frame_index: int) -> None:
        """Stop animation and adjust frame index before frame deletion."""
        self.event_handler.stop_animation_before_deletion(animation_name, frame_index)

    def _track_frame_deletion_for_undo(
        self, frames: list[SpriteFrame], animation_name: str, frame_index: int
    ) -> None:
        """Capture frame data and track deletion for undo/redo."""
        self.event_handler.track_frame_deletion_for_undo(frames, animation_name, frame_index)

    def _adjust_current_frame_after_deletion(self, animation_name: str, frame_index: int) -> None:
        """Adjust the widget's current frame after a frame deletion."""
        self.event_handler.adjust_current_frame_after_deletion(animation_name, frame_index)

    def _clamp_animated_sprite_frame(self, animation_name: str, frames: list[SpriteFrame]) -> None:
        """Ensure the animated sprite's current frame is within bounds after deletion."""
        self.event_handler.clamp_animated_sprite_frame(animation_name, frames)

    def _insert_frame_at_tab(self, tab: FilmTabWidget) -> None:
        """Insert a new frame at the position specified by the tab."""
        self.event_handler.insert_frame_at_tab(tab)

    def _update_film_tabs(self) -> None:
        """Update film tabs (alias for create_film_tabs)."""
        self.layout.create_film_tabs()


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

    def __init__(self, x: int, y: int, width: int = 20, height: int = 30) -> None:
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
        self.insertion_type = 'before'  # "before" or "after"
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
        pygame.draw.rect(surface, border_color, (center_x - 1, center_y, 3, 1))
        # Draw vertical bar (1 pixel wide, 3 pixels tall)
        pygame.draw.rect(surface, border_color, (center_x, center_y - 1, 1, 3))

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

    def __init__(self, x: int, y: int, width: int = 40, height: int = 10) -> None:
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
        self.insertion_type = 'delete'  # Always deletes the current strip
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
        pygame.draw.rect(surface, border_color, (center_x - 1, center_y, 3, 1))

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

    def __init__(self, x: int, y: int, width: int = 40, height: int = 10) -> None:
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
        self.insertion_type = 'after'  # Always adds after the last frame
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
        pygame.draw.rect(surface, border_color, (center_x - 1, center_y, 3, 1))
        # Draw vertical bar (1 pixel wide, 3 pixels tall) - same as vertical tabs
        pygame.draw.rect(surface, border_color, (center_x, center_y - 1, 1, 3))

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
