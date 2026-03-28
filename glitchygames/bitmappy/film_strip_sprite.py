"""FilmStripSprite — sprite wrapper bridging the film strip widget and pygame sprite system."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

import pygame

from glitchygames import events
from glitchygames.color import RGBA_COMPONENT_COUNT
from glitchygames.sprites import BitmappySprite

from .constants import LOG

if TYPE_CHECKING:
    from glitchygames.bitmappy.animated_canvas import AnimatedCanvasSprite
    from glitchygames.bitmappy.editor import BitmapEditorScene
    from glitchygames.sprites.animated import SpriteFrame

    from .film_strip import FilmStripWidget


class FilmStripSprite(BitmappySprite):
    """Sprite wrapper for the film strip widget.

    CRITICAL ARCHITECTURE NOTE:
    This sprite is the bridge between the film strip widget and the pygame sprite system.
    It MUST be updated continuously (every frame) to ensure preview animations run smoothly.

    KEY RESPONSIBILITIES:
    1. Continuous Animation Updates:
       - Updates film_strip_widget.update_animations() every frame
       - Passes delta time from the scene for smooth animation timing
       - Ensures preview animations run independently of user interaction

    2. Dirty Flag Management:
       - Marks itself as dirty when animations are running
       - This triggers redraws in the sprite group system
       - Ensures visual updates when animation frames advance

    3. Rendering Coordination:
       - Calls force_redraw() when needed (dirty or animations running)
       - Manages the relationship between animation state and visual updates

    DEBUGGING NOTES:
    - If animations stop: Check that this sprite's update() is called every frame
    - If animations are choppy: Verify _last_dt contains reasonable values
    - If no visual updates: Check that dirty flag is being set when animations run
    - If wrong timing: Verify delta time is being passed from scene update loop
    """

    def __init__(  # noqa: PLR0913
        self,
        film_strip_widget: FilmStripWidget,
        *,
        x: int = 0,
        y: int = 0,
        width: int = 800,
        height: int = 100,
        groups: pygame.sprite.LayeredDirty | None = None,  # type: ignore[type-arg]
    ) -> None:
        """Initialize the film strip sprite."""
        super().__init__(x=x, y=y, width=width, height=height, groups=groups)  # type: ignore[arg-type]
        self.film_strip_widget: FilmStripWidget | None = film_strip_widget
        self.parent_scene: BitmapEditorScene | None = None
        self.name = 'Film Strip'

        # Create initial surface with alpha support
        self.image = pygame.Surface((width, height), pygame.SRCALPHA)
        self.rect = self.image.get_rect(x=x, y=y)

        # Force initial render
        self.dirty = 1

    @override
    def update(self) -> None:
        """Update the film strip sprite.

        Animation timing is handled by FilmStripCoordinator.update_film_strip_animation_timing(),
        which calls update_animations() on each widget and conditionally sets dirty=1
        only when a frame actually advances. This method only needs to re-render the
        sprite surface when the dirty flag has been set.
        """
        # Check if this sprite has been killed - if so, don't update
        if not hasattr(self, 'groups') or not self.groups() or len(self.groups()) == 0:
            if hasattr(self, 'film_strip_widget'):
                self.film_strip_widget = None
            return

        if self.dirty and self.film_strip_widget:
            self.force_redraw()

    def force_redraw(self) -> None:
        """Force a redraw of the film strip."""
        assert self.film_strip_widget is not None
        # Clear the surface with copper brown to match film strip
        self.image.fill((100, 70, 55))  # Copper brown background

        # Render the film strip widget
        self.film_strip_widget.render(self.image)

    @override
    def kill(self) -> None:
        """Kill the sprite and clean up the widget reference."""
        # Clear the widget reference to prevent any lingering updates
        if hasattr(self, 'film_strip_widget'):
            self.film_strip_widget = None
        # Call the parent kill method
        super().kill()

    @override
    def on_left_mouse_button_down_event(self, event: events.HashableEvent) -> None:
        """Handle mouse clicks on the film strip."""
        LOG.debug(f'FilmStripSprite: Mouse click at {event.pos}, rect: {self.rect}')
        if self.rect.collidepoint(event.pos) and self.film_strip_widget and self.visible:
            LOG.debug(
                'FilmStripSprite: Click is within bounds and sprite is visible, converting '
                'coordinates',
            )
            # Convert screen coordinates to film strip coordinates
            film_x = event.pos[0] - self.rect.x
            film_y = event.pos[1] - self.rect.y

            # Check for shift-click using pygame's current key state
            is_shift_click = (
                pygame.key.get_pressed()[pygame.K_LSHIFT]
                or pygame.key.get_pressed()[pygame.K_RSHIFT]
            )

            # Handle click in the film strip widget
            LOG.debug(
                f'FilmStripSprite: Calling handle_click with coordinates ({film_x}, {film_y}),'
                f' shift={is_shift_click}',
            )
            clicked_frame = self.film_strip_widget.handle_click(
                (film_x, film_y),
                is_shift_click=is_shift_click,
            )
            LOG.debug(f'FilmStripSprite: Clicked frame: {clicked_frame}')

            if clicked_frame:
                animation, frame_idx = clicked_frame
                LOG.debug(f'FilmStripSprite: Loading frame {frame_idx} of animation {animation}')

                # Notify the canvas to change frame
                if hasattr(self, 'parent_canvas') and self.parent_canvas:
                    self.parent_canvas.show_frame(animation, frame_idx)

                # Notify the parent scene about the selection change
                if hasattr(self, 'parent_scene') and self.parent_scene:
                    self.parent_scene.on_film_strip_frame_selected(
                        self.film_strip_widget,
                        animation,
                        frame_idx,
                    )
            else:
                LOG.debug('FilmStripSprite: No frame clicked, handle_click returned None')
        else:
            LOG.debug('FilmStripSprite: Click is outside bounds or no widget')

    @override
    def on_right_mouse_button_up_event(self, event: events.HashableEvent) -> bool | None:  # type: ignore[override] # ty: ignore[invalid-method-override]
        """Handle right mouse clicks on the film strip for onion skinning and color sampling.

        Returns:
            bool | None: True if the event was handled, False if not, None if not applicable.

        """
        LOG.info(f'FilmStripSprite: Right mouse UP at {event.pos}, rect: {self.rect}')
        if self.rect.collidepoint(event.pos) and self.film_strip_widget and self.visible:
            LOG.info(
                'FilmStripSprite: Right click UP is within '
                'bounds and sprite is visible, '
                'converting coordinates',
            )
            # Convert screen coordinates to film strip coordinates
            film_x = event.pos[0] - self.rect.x
            film_y = event.pos[1] - self.rect.y

            # Check for shift-right-click (screen sampling)
            is_shift_click = (
                pygame.key.get_pressed()[pygame.K_LSHIFT]
                or pygame.key.get_pressed()[pygame.K_RSHIFT]
            )

            # First check if we clicked on a frame for color sampling
            clicked_frame = self.film_strip_widget.get_frame_at_position((film_x, film_y))
            if clicked_frame:
                animation, frame_idx = clicked_frame
                LOG.info(
                    f'FilmStripSprite: Right-clicked frame {animation}[{frame_idx}] for color'
                    f' sampling',
                )

                if is_shift_click:
                    # Shift-right-click: sample screen directly (RGB only)
                    LOG.info(
                        'FilmStripSprite: Shift-right-click detected - sampling screen directly',
                    )
                    if hasattr(self, 'parent_scene') and self.parent_scene:
                        self.parent_scene._slider_manager.sample_color_from_screen(event.pos)  # type: ignore[reportPrivateUsage]
                else:
                    # Regular right-click: sample from sprite frame pixel data (RGBA)
                    self._sample_color_from_frame(animation, frame_idx, film_x, film_y)
                LOG.info('FilmStripSprite: Color sampling completed, returning early')
                return True  # Event was handled

            # Handle right-click in the film strip widget for onion skinning
            LOG.debug(
                f'FilmStripSprite: Calling handle_click with coordinates ({film_x}, {film_y}),'
                f' right_click=True',
            )
            clicked_frame = self.film_strip_widget.handle_click(
                (film_x, film_y),
                is_right_click=True,
            )
            LOG.debug(f'FilmStripSprite: Right-clicked frame: {clicked_frame}')
            return True  # Event was handled
        LOG.debug('FilmStripSprite: Right click UP is outside bounds or no widget')
        return False  # Event not handled

    def _get_frame_pixel_data(
        self,
        animation: str,
        frame_idx: int,
    ) -> tuple[Any, list[tuple[int, ...]]] | None:
        """Get pixel data and frame object for a specific animation frame.

        Args:
            animation: Animation name.
            frame_idx: Frame index.

        Returns:
            Tuple of (frame, pixel_data) or None if unavailable.

        """
        assert self.film_strip_widget is not None
        if not self.film_strip_widget.animated_sprite:
            LOG.debug('FilmStripSprite: No animated sprite available for color sampling')
            return None

        frames = self.film_strip_widget.animated_sprite._animations.get(animation, [])  # type: ignore[reportPrivateUsage]
        if frame_idx >= len(frames):
            LOG.debug(f'FilmStripSprite: Frame index {frame_idx} out of range')
            return None

        frame = frames[frame_idx]

        if hasattr(frame, 'get_pixel_data'):
            pixel_data = frame.get_pixel_data()
        elif hasattr(frame, 'pixels'):
            pixel_data = frame.pixels
        else:
            LOG.debug('FilmStripSprite: Frame has no pixel data available')
            return None

        if not pixel_data:
            LOG.debug('FilmStripSprite: Frame pixel data is empty')
            return None

        return frame, pixel_data

    def _get_frame_dimensions(self, frame: SpriteFrame) -> tuple[int, int]:
        """Get the actual pixel dimensions of a frame.

        Args:
            frame: The sprite frame object.

        Returns:
            Tuple of (width, height).

        """
        if hasattr(frame, 'image') and frame.image:
            return frame.image.get_size()

        assert self.film_strip_widget is not None
        parent_canvas = self.film_strip_widget.parent_canvas
        width = parent_canvas.pixels_across if parent_canvas else 32
        height = parent_canvas.pixels_tall if parent_canvas else 32
        return width, height

    def _find_frame_layout(self, animation: str, frame_idx: int) -> pygame.Rect | None:
        """Find the screen layout rectangle for a specific animation frame.

        Args:
            animation: Animation name.
            frame_idx: Frame index.

        Returns:
            The frame layout Rect, or None if not found.

        """
        assert self.film_strip_widget is not None
        for (
            anim_name,
            frame_idx_check,
        ), frame_rect in self.film_strip_widget.frame_layouts.items():
            if anim_name == animation and frame_idx_check == frame_idx:
                return frame_rect

        LOG.debug(f'FilmStripSprite: Could not find frame layout for {animation}[{frame_idx}]')
        return None

    def _screen_to_pixel_coords(
        self,
        film_x: int,
        film_y: int,
        frame_layout: pygame.Rect,
        actual_width: int,
        actual_height: int,
    ) -> tuple[int, int] | None:
        """Convert film strip screen coordinates to pixel coordinates within a frame.

        Args:
            film_x: X coordinate within the film strip.
            film_y: Y coordinate within the film strip.
            frame_layout: The frame's screen layout Rect.
            actual_width: Actual pixel width of the frame.
            actual_height: Actual pixel height of the frame.

        Returns:
            Tuple of (pixel_x, pixel_y) or None if outside bounds.

        """
        relative_x = film_x - frame_layout.x
        relative_y = film_y - frame_layout.y

        if not (0 <= relative_x < frame_layout.width and 0 <= relative_y < frame_layout.height):
            LOG.debug('FilmStripSprite: Click outside frame bounds')
            return None

        # Account for frame border (4px on each side)
        frame_content_width = frame_layout.width - 8
        frame_content_height = frame_layout.height - 8

        pixel_x = int((relative_x - 4) * actual_width / frame_content_width)
        pixel_y = int((relative_y - 4) * actual_height / frame_content_height)

        pixel_x = max(0, min(pixel_x, actual_width - 1))
        pixel_y = max(0, min(pixel_y, actual_height - 1))
        return pixel_x, pixel_y

    def _update_color_sliders(self, red: int, green: int, blue: int, alpha: int) -> None:
        """Update parent scene color sliders with sampled RGBA values.

        Args:
            red: Red channel value.
            green: Green channel value.
            blue: Blue channel value.
            alpha: Alpha channel value.

        """
        if not (hasattr(self, 'parent_scene') and self.parent_scene):
            return

        for channel_name, channel_value in [('R', red), ('G', green), ('B', blue), ('A', alpha)]:
            trigger = events.HashableEvent(0, name=channel_name, value=channel_value)
            self.parent_scene.on_slider_event(event=events.HashableEvent(0), trigger=trigger)

        LOG.info(
            f'FilmStripSprite: Updated sliders with sampled color R:{red}, G:{green},'
            f' B:{blue}, A:{alpha}',
        )

    def _sample_color_from_frame(
        self,
        animation: str,
        frame_idx: int,
        film_x: int,
        film_y: int,
    ) -> None:
        """Sample color from a sprite frame pixel data.

        Args:
            animation: Animation name
            frame_idx: Frame index
            film_x: X coordinate within the film strip
            film_y: Y coordinate within the film strip

        """
        try:
            result = self._get_frame_pixel_data(animation, frame_idx)
            if result is None:
                return

            frame, pixel_data = result
            actual_width, actual_height = self._get_frame_dimensions(frame)

            frame_layout = self._find_frame_layout(animation, frame_idx)
            if not frame_layout:
                return

            pixel_coords = self._screen_to_pixel_coords(
                film_x,
                film_y,
                frame_layout,
                actual_width,
                actual_height,
            )
            if pixel_coords is None:
                return

            pixel_x, pixel_y = pixel_coords
            pixel_num = pixel_y * actual_width + pixel_x

            if pixel_num >= len(pixel_data):
                LOG.debug(
                    f'FilmStripSprite: Pixel index {pixel_num} out of range for pixel data length'
                    f' {len(pixel_data)}',
                )
                return

            color = pixel_data[pixel_num]
            if len(color) == RGBA_COMPONENT_COUNT:
                red, green, blue, alpha = color
            else:
                red, green, blue = color
                alpha = 255

            LOG.debug(
                f'FilmStripSprite: Sampled color from frame {animation}[{frame_idx}] pixel'
                f' ({pixel_x}, {pixel_y}) - R:{red}, G:{green}, B:{blue}, A:{alpha}',
            )

            self._update_color_sliders(red, green, blue, alpha)

        except IndexError, ValueError, TypeError:
            LOG.exception('FilmStripSprite: Error sampling color from frame')

    @override
    def on_key_down_event(self, event: events.HashableEvent) -> bool | None:  # type: ignore[override] # ty: ignore[invalid-method-override]
        """Handle keyboard events for copy/paste functionality.

        Returns:
            bool | None: True if the event was handled, False if not, None if not applicable.

        """
        if not self.film_strip_widget:
            return None

        # Check for Ctrl+C (copy)
        if event.key == pygame.K_c and (event.get('mod', 0) & pygame.KMOD_CTRL):
            LOG.debug('FilmStripSprite: Ctrl+C detected - copying current frame')
            success = self.film_strip_widget.copy_current_frame()
            if success:
                LOG.debug('FilmStripSprite: Frame copied successfully')
            else:
                LOG.debug('FilmStripSprite: Failed to copy frame')
            return True

        # Check for Ctrl+V (paste)
        if event.key == pygame.K_v and (event.get('mod', 0) & pygame.KMOD_CTRL):
            LOG.debug('FilmStripSprite: Ctrl+V detected - pasting to current frame')
            success = self.film_strip_widget.paste_to_current_frame()
            if success:
                LOG.debug('FilmStripSprite: Frame pasted successfully')
            else:
                LOG.debug('FilmStripSprite: Failed to paste frame')
            return True

        return False

    def set_parent_canvas(self, canvas: AnimatedCanvasSprite) -> None:
        """Set the parent canvas for frame changes."""
        self.parent_canvas = canvas

    def on_drop_file_event(self, event: events.HashableEvent) -> bool:
        """Handle drop file event on film strip.

        Args:
            event: The pygame event containing the dropped file information.

        Returns:
            True if the drop was handled, False otherwise.

        """
        # Get current mouse position since drop events don't include position
        mouse_pos = pygame.mouse.get_pos()

        # Check if the drop is within the film strip bounds
        if not self.rect.collidepoint(mouse_pos):
            return False

        # Get the file path from the event
        file_path = event.file
        LOG.debug(f'FilmStripSprite: File dropped on film strip: {file_path}')

        # Check if it's an image file we can handle
        if not file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
            LOG.debug(f'FilmStripSprite: Unsupported file type: {file_path}')
            return False

        # Convert screen coordinates to film strip coordinates
        film_x = mouse_pos[0] - self.rect.x
        film_y = mouse_pos[1] - self.rect.y

        assert self.film_strip_widget is not None
        # Check if drop is on a specific frame
        clicked_frame = self.film_strip_widget.get_frame_at_position((int(film_x), int(film_y)))

        if clicked_frame:
            # Drop on existing frame - replace its contents
            animation, frame_idx = clicked_frame
            LOG.debug(f'FilmStripSprite: Dropping on frame {animation}[{frame_idx}]')
            return self._replace_frame_with_image(file_path, animation, frame_idx)
        # Drop on film strip but not on a frame - insert new frame
        LOG.debug('FilmStripSprite: Dropping on film strip area, inserting new frame')
        return self._insert_image_as_new_frame(file_path, int(film_x), int(film_y))

    @override
    def on_mouse_motion_event(self, event: events.HashableEvent) -> None:
        """Handle mouse motion events for drag hover effects.

        Args:
            event: The pygame mouse motion event.

        """
        if not self.film_strip_widget or not self.visible:
            return

        if self.rect.collidepoint(event.pos):
            # Convert screen coordinates to film strip coordinates
            film_x = event.pos[0] - self.rect.x
            film_y = event.pos[1] - self.rect.y

            # Snapshot previous hover state to detect changes
            previous_hovered_frame = self.film_strip_widget.hovered_frame
            previous_hovered_preview = self.film_strip_widget.hovered_preview

            # Handle all hover effects (frames, previews, removal buttons)
            self.film_strip_widget.handle_hover((film_x, film_y))

            # Check if hovering over a specific frame
            hovered_frame = self.film_strip_widget.get_frame_at_position((film_x, film_y))

            if hovered_frame:
                self.film_strip_widget.hovered_frame = hovered_frame
            else:
                self.film_strip_widget.hovered_frame = None
                # Check if hovering over preview area
                hovered_preview = self.film_strip_widget.get_preview_at_position((film_x, film_y))
                if hovered_preview:
                    self.film_strip_widget.hovered_preview = hovered_preview
                else:
                    self.film_strip_widget.hovered_preview = None
                    self.film_strip_widget.is_hovering_strip = True

            # Only mark dirty if hover state actually changed
            hover_changed = (
                self.film_strip_widget.hovered_frame != previous_hovered_frame
                or self.film_strip_widget.hovered_preview != previous_hovered_preview
            )
            if hover_changed:
                self.film_strip_widget.mark_dirty()
        elif (
            self.film_strip_widget.hovered_frame is not None
            or self.film_strip_widget.hovered_preview is not None
            or self.film_strip_widget.is_hovering_strip
        ):
            # Only clear and redirty if we were previously hovering
            self._clear_hover_effects()

    def _show_frame_hover_effect(self, frame_info: tuple[str, int]) -> None:
        """Show visual feedback for hovering over a frame.

        Args:
            frame_info: Tuple of (animation, frame_idx) for the hovered frame.

        """
        assert self.film_strip_widget is not None
        animation, frame_idx = frame_info
        LOG.debug(f'FilmStripSprite: Hovering over frame {animation}[{frame_idx}]')

        # Set hover state in the film strip widget
        self.film_strip_widget.hovered_frame = frame_info
        # Keep strip hover active even when hovering over frame
        self.film_strip_widget.mark_dirty()

        # Mark this sprite as dirty to trigger redraw
        self.dirty = 1

    def _show_preview_hover_effect(self, animation_name: str) -> None:
        """Show visual feedback for hovering over a preview area.

        Args:
            animation_name: Name of the animation being previewed.

        """
        assert self.film_strip_widget is not None
        LOG.debug(f'FilmStripSprite: Hovering over preview {animation_name}')

        # Set hover state in the film strip widget
        self.film_strip_widget.hovered_preview = animation_name
        # Keep strip hover active even when hovering over preview
        self.film_strip_widget.mark_dirty()

        # Mark this sprite as dirty to trigger redraw
        self.dirty = 1

    def _show_strip_hover_effect(self) -> None:
        """Show visual feedback for hovering over the film strip area."""
        assert self.film_strip_widget is not None
        LOG.debug('FilmStripSprite: Hovering over film strip area')

        # Set hover state in the film strip widget
        self.film_strip_widget.hovered_frame = None
        self.film_strip_widget.is_hovering_strip = True
        self.film_strip_widget.mark_dirty()

        # Mark this sprite as dirty to trigger redraw
        self.dirty = 1

    def _clear_hover_effects(self) -> None:
        """Clear all hover effects, only marking dirty if state changed."""
        if not self.film_strip_widget:
            return

        self.film_strip_widget.hovered_frame = None
        self.film_strip_widget.hovered_preview = None
        self.film_strip_widget.is_hovering_strip = False
        self.film_strip_widget.hovered_removal_button = None
        self.film_strip_widget.mark_dirty()

    def _get_canvas_dimensions(self) -> tuple[int, int]:
        """Get the current canvas dimensions for image resizing.

        Returns:
            Tuple of (width, height) for the canvas.

        """
        if hasattr(self, 'parent_canvas') and self.parent_canvas:
            return self.parent_canvas.pixels_across, self.parent_canvas.pixels_tall
        if (
            hasattr(self, 'parent_scene')
            and self.parent_scene
            and hasattr(self.parent_scene, 'canvas')
        ):
            return self.parent_scene.canvas.pixels_across, self.parent_scene.canvas.pixels_tall
        return 32, 32  # Default fallback

    def _convert_image_to_sprite_frame(self, file_path: str) -> SpriteFrame | None:
        """Convert an image file to a SpriteFrame.

        Args:
            file_path: Path to the image file to convert.

        Returns:
            SpriteFrame object or None if conversion failed.

        """
        try:
            # Load the image
            image = pygame.image.load(file_path)

            # Get current canvas size for resizing
            canvas_width, canvas_height = self._get_canvas_dimensions()

            # Resize image to match canvas size
            if image.get_size() != (canvas_width, canvas_height):
                image = pygame.transform.scale(image, (canvas_width, canvas_height))

            # Convert to RGBA if needed, preserving transparency
            if image.get_flags() & pygame.SRCALPHA:
                # Image already has alpha - keep it
                pass
            else:
                # Convert RGB to RGBA by adding alpha channel
                rgba_image = pygame.Surface((canvas_width, canvas_height), pygame.SRCALPHA)
                rgba_image.blit(image, (0, 0))
                image = rgba_image

            # Get pixel data with alpha support
            pixels: list[tuple[int, ...]] = []
            if image.get_flags() & pygame.SRCALPHA:
                # Image has alpha channel - use array4d to preserve alpha
                pixel_array: Any = pygame.surfarray.array4d(image)  # type: ignore[attr-defined] # ty: ignore[unresolved-attribute]
                for y in range(canvas_height):
                    for x in range(canvas_width):
                        r, g, b, a = pixel_array[x, y]  # type: ignore[index]
                        pixels.append((int(r), int(g), int(b), int(a)))  # type: ignore[arg-type]
            else:
                # Image has no alpha channel - use array3d and add alpha
                pixel_array = pygame.surfarray.array3d(image)  # type: ignore[assignment]
                for y in range(canvas_height):
                    for x in range(canvas_width):
                        r, g, b = pixel_array[x, y]
                        pixels.append((int(r), int(g), int(b), 255))  # Add full alpha

            # Create a new SpriteFrame with the surface
            from glitchygames.sprites import SpriteFrame

            frame = SpriteFrame(image, duration=0.1)  # 0.1 second duration
            frame.set_pixel_data(pixels)

            LOG.debug('FilmStripSprite: Successfully converted image to sprite frame')

        except pygame.error, OSError, ValueError, AttributeError:
            LOG.exception(f'FilmStripSprite: Failed to convert image {file_path}')
            return None
        else:
            return frame

    def _should_update_canvas_frame(self, animation: str, frame_idx: int) -> bool:
        """Check if the canvas should be updated for a given animation frame.

        Args:
            animation: Animation name.
            frame_idx: Frame index.

        Returns:
            True if the canvas should be updated.

        """
        if not (hasattr(self, 'parent_scene') and self.parent_scene):
            return False
        parent = self.parent_scene
        return bool(
            hasattr(parent, 'selected_animation')
            and hasattr(parent, 'selected_frame')
            and parent.selected_animation == animation
            and parent.selected_frame == frame_idx
            and hasattr(parent, 'canvas')
            and parent.canvas,
        )

    def _replace_frame_with_image(self, file_path: str, animation: str, frame_idx: int) -> bool:
        """Replace an existing frame with image content.

        Args:
            file_path: Path to the image file.
            animation: Animation name.
            frame_idx: Frame index to replace.

        Returns:
            True if successful, False otherwise.

        """
        assert self.film_strip_widget is not None
        LOG.debug(f'FilmStripSprite: Replacing frame {animation}[{frame_idx}] with image')

        # Convert image to sprite frame
        new_frame = self._convert_image_to_sprite_frame(file_path)
        if not new_frame:
            return False

        # Get the current frame and replace it
        if not self.film_strip_widget.animated_sprite:
            LOG.error('FilmStripSprite: No animated sprite available')
            return False

        frames = self.film_strip_widget.animated_sprite._animations.get(animation, [])  # type: ignore[reportPrivateUsage]
        if frame_idx >= len(frames):
            LOG.error(f'FilmStripSprite: Frame index {frame_idx} out of range')
            return False

        # Replace the frame
        frames[frame_idx] = new_frame

        # Mark as dirty for redraw
        self.film_strip_widget.mark_dirty()

        # Update canvas if this is the current frame
        if self._should_update_canvas_frame(animation, frame_idx):
            assert self.parent_scene is not None
            self.parent_scene.canvas.show_frame(animation, frame_idx)

        LOG.debug(f'FilmStripSprite: Successfully replaced frame {animation}[{frame_idx}]')
        return True

    def _insert_image_as_new_frame(self, file_path: str, _film_x: int, _film_y: int) -> bool:
        """Insert image as a new frame in the film strip.

        Args:
            file_path: Path to the image file.
            _film_x: X coordinate of drop position (unused, kept for API compatibility).
            _film_y: Y coordinate of drop position (unused, kept for API compatibility).

        Returns:
            True if successful, False otherwise.

        """
        assert self.film_strip_widget is not None
        LOG.debug('FilmStripSprite: Inserting new frame from image')

        # Convert image to sprite frame
        new_frame = self._convert_image_to_sprite_frame(file_path)
        if not new_frame:
            return False

        # Determine which animation to add to
        current_animation = self.film_strip_widget.current_animation
        if not current_animation:
            LOG.error('FilmStripSprite: No current animation selected')
            return False

        # Determine insertion position based on drop location.
        # Currently inserts at the end; position-based insertion could be added later.
        assert self.film_strip_widget.animated_sprite is not None
        insert_index = len(self.film_strip_widget.animated_sprite._animations[current_animation])  # type: ignore[reportPrivateUsage]

        # Insert the frame
        self.film_strip_widget.animated_sprite.add_frame(current_animation, new_frame, insert_index)

        # Mark as dirty for redraw
        self.film_strip_widget.mark_dirty()

        # Notify the parent scene about the frame insertion
        if (
            hasattr(self, 'parent_scene')
            and self.parent_scene
            and hasattr(self.parent_scene, 'on_frame_inserted')
        ):
            self.parent_scene.on_frame_inserted(current_animation, insert_index)  # type: ignore[reportPrivateUsage] # ty: ignore[call-non-callable]

        # Select the newly created frame
        self.film_strip_widget.set_current_frame(current_animation, insert_index)

        LOG.debug(
            'FilmStripSprite: Successfully inserted new frame at'
            f' {current_animation}[{insert_index}]',
        )
        return True
